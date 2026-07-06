"""Sign-off package assembly (spec §13.4; REQ-005, §2.6 metrics).

For a designated final run, assemble a zip of HTML artifacts + manifest:
certification cover page (engagement, scope, fingerprint version, metrics vs
the §2.6 targets, dual IT/business sign-off lines per §15.3), the executive
narrative (GenerateConversionSummary() via the AI layer, analyst-approved —
or an analyst-provided override), the findings report, the five
reconciliation reports, the exception register with closure evidence, and
the audit-log extract (workflow, reviews, and the run's learning events).

The zip is deterministic for a given run + timestamp: fixed entry dates,
sorted names, canonical JSON manifest with per-file sha256 (REQ-009 spirit,
REQ-014 headers throughout).
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.ai.orchestrator import AIOrchestrator
from src.fingerprint.loader import DEFAULT_FINGERPRINT_DIR
from src.fingerprint.models import FindingsReport
from src.learning.workflow import exception_register
from src.learning.writeback import read_events
from src.report.html import RECON_KINDS, _env, _header, render_reconciliation_html
from src.runner.run import DEFAULT_RUNS_DIR

_ZIP_DATE = (2026, 1, 1, 0, 0, 0)  # fixed entry timestamp for determinism


@dataclass
class SignoffResult:
    package_path: Path
    manifest: dict


def _metrics(recon: dict, register: list[dict], findings_count: int) -> list[dict]:
    """The §2.6 success metrics evaluated from run artifacts."""
    plans = recon.get("plans", {})
    source_participants = sum(
        int(p["participant_count"]["source"]) for p in plans.values())
    target_participants = sum(
        int(p["participant_count"]["target"]) for p in plans.values())
    participants_met = (source_participants == target_participants
                        and source_participants > 0)

    balances_met = all(
        p["balance_total"]["source"] == p["balance_total"]["target"]
        for p in plans.values())

    open_exceptions = sum(1 for row in register if row["status"] != "closed")
    exception_base = max(findings_count, 1)
    unresolved_pct = round(100 * open_exceptions / exception_base, 2)

    return [
        {"metric": "Participant records converted (REQ-003)",
         "target": "100%",
         "actual": f"{target_participants} of {source_participants}",
         "status": "MET" if participants_met else "NOT MET"},
        {"metric": "Account balances reconciled to the cent (REQ-004)",
         "target": "100%",
         "actual": "all plan totals equal" if balances_met
         else "plan-total variance present",
         "status": "MET" if balances_met else "NOT MET"},
        {"metric": "Unresolved exceptions (REQ-005)",
         "target": "< 0.1%",
         "actual": f"{open_exceptions} open ({unresolved_pct}% of findings)",
         "status": "MET" if open_exceptions == 0 else "NOT MET"},
    ]


def _render_certification(report: FindingsReport, metrics: list[dict],
                          narrative: dict, register: list[dict]) -> str:
    return _env().get_template("signoff_certification.html").render(
        header=_header(report, "Sign-Off Package — Certification"),
        summary=report.run.summary, metrics=metrics, narrative=narrative,
        open_exceptions=sum(1 for r in register if r["status"] != "closed"),
        total_exceptions=len(register),
    )


def _render_register(report: FindingsReport, register: list[dict]) -> str:
    return _env().get_template("signoff_register.html").render(
        header=_header(report, "Exception Register — Closure Evidence"),
        register=register,
    )


def build_signoff_package(
    run_id: str,
    *,
    runs_dir: Path | str = DEFAULT_RUNS_DIR,
    fingerprint_dir: Path | str = DEFAULT_FINGERPRINT_DIR,
    narrative: str | None = None,
    approved_by: str | None = None,
    now: datetime | None = None,
) -> SignoffResult:
    """Assemble the package into <run_dir>/signoff/PKG-<run_id>.zip."""
    runs_dir = Path(runs_dir)
    run_dir = runs_dir / run_id
    findings_path = run_dir / "findings.json"
    if not findings_path.is_file():
        raise FileNotFoundError(f"no findings report for run {run_id!r}")
    report = FindingsReport.model_validate(
        json.loads(findings_path.read_text(encoding="utf-8")))
    recon_path = run_dir / "reconciliation.json"
    recon = (json.loads(recon_path.read_text(encoding="utf-8"))
             if recon_path.is_file() else {"plans": {}})
    register = exception_register(run_id, runs_dir)
    metrics = _metrics(recon, register, len(report.findings))

    if narrative is not None:
        narrative_view = {"text": narrative, "source": "analyst-provided",
                          "needs_review": False, "approved_by": approved_by}
    else:
        result = AIOrchestrator(
            audit_path=runs_dir / "ai_audit.jsonl").conversion_summary(report)
        narrative_view = {
            "text": result.output.executive_narrative,
            "key_risks": result.output.key_risks,
            "recommendation": result.output.recommendation,
            "source": f"AI-generated ({result.provider} provider, "
                      f"confidence {result.confidence})",
            "needs_review": result.needs_review,
            "approved_by": approved_by,
        }

    entries: dict[str, bytes] = {
        "certification.html": _render_certification(
            report, metrics, narrative_view, register).encode("utf-8"),
        "exception_register.html": _render_register(
            report, register).encode("utf-8"),
    }

    findings_html = run_dir / "findings.html"
    if findings_html.is_file():
        entries["findings.html"] = findings_html.read_bytes()
    for kind in RECON_KINDS:
        entries[f"reconciliation_{kind}.html"] = render_reconciliation_html(
            kind, recon, report).encode("utf-8")

    for name in ("workflow.jsonl", "reviews.jsonl"):
        source = run_dir / name
        if source.is_file():
            entries[f"audit/{name}"] = source.read_bytes()
    run_events = [e for e in read_events(report.run.pair_id, fingerprint_dir)
                  if e.run_id == run_id]
    if run_events:
        entries["audit/learning_events.jsonl"] = "".join(
            json.dumps(e.model_dump(mode="json"), sort_keys=True) + "\n"
            for e in run_events).encode("utf-8")

    created_at = (now or datetime.now(timezone.utc)).isoformat()
    manifest = {
        "package_id": f"PKG-{run_id}",
        "run_id": run_id,
        "pair_id": report.run.pair_id,
        "fingerprint_version": report.run.fingerprint_version,
        "dataset_hashes": dict(sorted(report.run.dataset_hashes.items())),
        "created_at": created_at,
        "metrics": metrics,
        "narrative_source": narrative_view["source"],
        "files": {name: "sha256:" + hashlib.sha256(data).hexdigest()
                  for name, data in sorted(entries.items())},
    }
    entries["manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True)
                                + "\n").encode("utf-8")

    package_path = run_dir / "signoff" / f"PKG-{run_id}.zip"
    package_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, entries[name])
    return SignoffResult(package_path=package_path, manifest=manifest)
