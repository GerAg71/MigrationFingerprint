"""HTML report rendering (MS-2.3; spec §13.1–13.3, §13.5).

Jinja2 templates under src/report/templates/, rendered self-contained —
inline CSS, zero external requests — so reports can be emailed and archived
(REQ-025). Deterministic: no timestamps in bodies, sorted iteration, the
same artifacts render byte-identically (REQ-009). Every artifact header
carries run id, pair, fingerprint version, and dataset hashes (REQ-014).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.fingerprint.models import FindingsReport
from src.report.aggregates import quality_sections

TEMPLATES = Path(__file__).resolve().parent / "templates"

RECON_KINDS = ("plan", "participant", "loan", "contribution", "quality")

SEVERITY_COLORS = {  # spec §20.4 tokens
    "CRITICAL": "#b91c1c", "HIGH": "#ea580c", "MEDIUM": "#f59e0b",
    "LOW": "#94a3b8",
}


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.globals["severity_colors"] = SEVERITY_COLORS
    return env


def _header(report: FindingsReport, title: str, wave: str | None = None) -> dict:
    run = report.run
    return {
        "title": title,
        "run_id": run.run_id,
        "pair_id": run.pair_id,
        "fingerprint_version": run.fingerprint_version,
        "wave": wave,
        "dataset_hashes": dict(sorted(run.dataset_hashes.items())),
    }


def _pair_rows(mapping: dict[str, dict]) -> list[dict]:
    """{label: {source, target}} (string amounts/counts) -> display rows
    with exact deltas and a variance flag."""
    rows = []
    for label in sorted(mapping):
        source = Decimal(str(mapping[label]["source"]))
        target = Decimal(str(mapping[label]["target"]))
        rows.append({
            "label": label,
            "source": str(mapping[label]["source"]),
            "target": str(mapping[label]["target"]),
            "delta": str(target - source),
            "variance": source != target,
        })
    return rows


def render_findings_html(report: FindingsReport, wave: str | None = None) -> str:
    """The §13.1 findings report: scoreboard, prioritized suite with
    per-rule outcomes, findings in priority order with expandable samples
    and drill-down links, plus the open-exception register (§13.3)."""
    summary = report.run.summary
    severity_mix = [
        {"severity": sev, "count": summary.severity_mix[sev]}
        for sev in SEVERITY_COLORS if sev in summary.severity_mix
    ]
    exceptions = [f for f in report.findings if f.status != "false_positive"]
    findings = []
    for finding in report.findings:
        key_columns = sorted({k for r in finding.sample_records for k in r.keys})
        findings.append({
            "finding": finding,
            "key_columns": key_columns,
            "rows": [
                {
                    "key_values": [record.keys.get(c, "") for c in key_columns],
                    "source": ", ".join(f"{k}={v}" for k, v in
                                        sorted((record.source or {}).items())),
                    "target": ", ".join(f"{k}={v}" for k, v in
                                        sorted((record.target or {}).items())),
                    "delta": "" if record.delta is None else str(record.delta),
                }
                for record in finding.sample_records
            ],
        })
    return _env().get_template("findings.html").render(
        header=_header(report, "Findings Report", wave),
        summary=summary,
        severity_mix=severity_mix,
        suite=report.suite,
        findings=findings,
        exceptions=exceptions,
    )


def render_reconciliation_html(
    kind: str, recon: dict, report: FindingsReport, wave: str | None = None
) -> str:
    """One of the five §13.2 client-facing reconciliation reports (REQ-026),
    rendered per plan with a rollup banner per plan status."""
    if kind not in RECON_KINDS:
        raise ValueError(f"unknown reconciliation report {kind!r}; "
                         f"expected one of {RECON_KINDS}")
    env = _env()
    header = _header(report, f"{kind.title()} Reconciliation", wave)

    if kind == "quality":
        return env.get_template("recon_quality.html").render(
            header=header, sections=quality_sections(report.findings))

    plans = []
    for plan_id, plan in sorted(recon.get("plans", {}).items()):
        view = {"plan_id": plan_id}
        if kind == "plan":
            view["balance_total"] = _pair_rows({"Plan total": plan["balance_total"]})
            view["by_money_type"] = _pair_rows(plan["balances_by_money_type"])
            view["by_investment"] = _pair_rows(plan["balances_by_investment"])
        elif kind == "participant":
            view["by_status"] = _pair_rows(plan["participants_by_status"])
            view["participant_count"] = _pair_rows(
                {"Participants": plan["participant_count"]})
            view["mismatches"] = plan["participant_balance_mismatches"]
        elif kind == "loan":
            view["counts"] = _pair_rows({
                "Loan count": plan["loan_count"],
                "Outstanding balance": plan["loan_outstanding"],
            })
            view["missing_terms"] = plan["loans_missing_terms_target"]
        elif kind == "contribution":
            view["by_money_type"] = _pair_rows(plan["contributions_last_cycle"])
            view["split"] = _pair_rows(plan["contribution_split"])
        tables = [v for v in view.values() if isinstance(v, list)]
        view["reconciled"] = not any(
            row.get("variance") for table in tables for row in table
            if isinstance(row, dict)
        ) and not (kind == "loan" and plan["loans_missing_terms_target"])
        if kind == "participant" and view["mismatches"]:
            view["reconciled"] = False
        plans.append(view)

    template = env.get_template(f"recon_{kind}.html")
    return template.render(
        header=header, plans=plans,
        last_payroll_cycle=recon.get("last_payroll_cycle"),
        plan_presence=recon.get("plan_presence", {}),
    )
