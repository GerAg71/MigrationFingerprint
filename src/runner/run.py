"""Run orchestration (MS-1.5; spec §12.1–12.4, §13.1).

Lifecycle: load fingerprint (pinned version) -> build + persist the suite
snapshot -> discover and register datasets -> dataset gate (REQ-021) ->
execute rules in priority order -> write findings.json + run.json -> review.

Determinism (REQ-009): same inputs + same fingerprint version + same run_id
reproduce suite_snapshot.json and findings.json byte-for-byte. Wall-clock
timestamps live only in run.json metadata; the validity "as of" date derives
from the run_id's date portion, so re-running a pinned run_id reproduces
date-bound checks exactly.

Run directory layout (local mirror of spec §9.2):
  data/runs/<run_id>/suite_snapshot.json      persisted before execution
  data/runs/<run_id>/findings.json            deterministic report (§13.1)
  data/runs/<run_id>/findings/<fid>.csv       full drill-down per finding
  data/runs/<run_id>/findings/<fid>.detail.json  extra detail (drill-down tree)
  data/runs/<run_id>/ingest/*.rejects.csv     quarantined rows (§10.5)
  data/runs/<run_id>/run.json                 run metadata (timestamps here)
"""

from __future__ import annotations

import csv as _csv
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from src.fingerprint.loader import DEFAULT_FINGERPRINT_DIR, load
from src.fingerprint.models import (
    ConversionRun,
    Finding,
    FindingsReport,
    Fingerprint,
    PrioritizedSuiteEntry,
    ReportRun,
    RunDatasets as RunDatasetManifest,
    RunScope,
    RunSummary,
    SuiteItem,
)
from src.fingerprint.prioritize import prioritized_suite
from src.ingest.canonical import CANONICAL_DATASETS
from src.ingest.registration import RegistrationIndex, register_dataset
from src.rules import ExecutionContext, RuleDatasets, UnsupportedRuleTypeError
from src.rules import build_finding, execute as execute_rule

DEFAULT_RUNS_DIR = Path("data") / "runs"
_RUN_DIR_RE = re.compile(r"^RUN-(\d{4}-\d{2}-\d{2})-(\d{4})$")


class DatasetGateError(Exception):
    """An enabled rule's datasets are not registered on both sides — the run
    refuses to execute rather than silently skipping (REQ-021)."""


@dataclass
class RunResult:
    run: ConversionRun
    report: FindingsReport
    suite: list[PrioritizedSuiteEntry]
    findings: list[Finding]
    run_dir: Path


def allocate_run_id(runs_dir: Path | str, today: date | None = None) -> str:
    """Next RUN-YYYY-MM-DD-NNNN (zero-padded daily sequence, CLI_SPEC)."""
    today = today or date.today()
    prefix = f"RUN-{today.isoformat()}-"
    highest = 0
    runs_dir = Path(runs_dir)
    if runs_dir.is_dir():
        for entry in runs_dir.iterdir():
            match = _RUN_DIR_RE.match(entry.name)
            if match and entry.name.startswith(prefix):
                highest = max(highest, int(match.group(2)))
    return f"{prefix}{highest + 1:04d}"


def _as_of_from_run_id(run_id: str) -> date:
    return date.fromisoformat(run_id[4:14])


def _dump_json_bytes(payload: object) -> bytes:
    """Canonical JSON bytes: sorted keys, LF newlines, UTF-8 (REQ-009)."""
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n").encode("utf-8")


def _discover_datasets(directory: Path) -> dict[str, Path]:
    """Every <canonical>.csv or <canonical>.dat in the directory (CLI_SPEC
    run step 2). Both formats for one dataset is ambiguous — refuse."""
    found = {}
    for name in sorted(CANONICAL_DATASETS):
        csv_path = directory / f"{name}.csv"
        dat_path = directory / f"{name}.dat"
        if csv_path.is_file() and dat_path.is_file():
            raise ValueError(
                f"ambiguous dataset {name!r}: both {csv_path.name} and "
                f"{dat_path.name} present in {directory}"
            )
        if csv_path.is_file():
            found[name] = csv_path
        elif dat_path.is_file():
            found[name] = dat_path
    return found


def _load_layout(layout_dir: Path | None, dataset_name: str, dat_path: Path):
    """LayoutSpec for a fixed-width extract: <layout_dir>/<dataset>.json."""
    from src.fingerprint.models import LayoutSpec

    if layout_dir is None:
        raise FileNotFoundError(
            f"{dat_path.name} is fixed-width and needs a LayoutSpec: pass "
            f"--layout-dir containing {dataset_name}.json (spec §10.2)"
        )
    layout_path = Path(layout_dir) / f"{dataset_name}.json"
    if not layout_path.is_file():
        raise FileNotFoundError(
            f"no LayoutSpec for {dat_path.name}: expected {layout_path}"
        )
    return LayoutSpec.model_validate(
        json.loads(layout_path.read_text(encoding="utf-8"))
    )


def _load_mapping_manifests(fingerprint: Fingerprint, base_dir: Path) -> frozenset[str]:
    """Union of mapped target fields from every manifest referenced by
    referential unmapped_target_fields params. A missing manifest file means
    nothing is mapped — values in the listed fields have no provenance."""
    mapped: set[str] = set()
    for rule in fingerprint.detection_rules:
        params = getattr(rule.params, "unmapped_target_fields", None)
        if params is None:
            continue
        manifest_path = base_dir / params.mapping_manifest
        if manifest_path.is_file():
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            mapped.update(payload.get("mapped_fields", []))
    return frozenset(mapped)


def _write_drilldown_csv(path: Path, finding_records) -> None:
    key_columns = sorted({k for record in finding_records for k in record.keys})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = _csv.writer(handle, lineterminator="\n")
        writer.writerow([*key_columns, "source", "target", "delta"])
        for record in finding_records:
            writer.writerow([
                *(record.keys.get(k, "") for k in key_columns),
                json.dumps(record.source, sort_keys=True) if record.source else "",
                json.dumps(record.target, sort_keys=True) if record.target else "",
                str(record.delta) if record.delta is not None else "",
            ])


def run(
    pair_id: str,
    source_dir: Path | str,
    target_dir: Path | str,
    *,
    version: str | None = None,
    plans: list[str] | None = None,
    wave: str | None = None,
    fingerprint_dir: Path | str = DEFAULT_FINGERPRINT_DIR,
    runs_dir: Path | str = DEFAULT_RUNS_DIR,
    run_id: str | None = None,
    base_dir: Path | str = Path("."),
    layout_dir: Path | str | None = None,
) -> RunResult:
    """Execute one conversion run (spec §12.1). Raises pydantic
    ValidationError / FingerprintDirectoryError (bad fingerprint, exit 3),
    DatasetGateError (REQ-021, exit 3), PartialFileError (REQ-022, exit 3),
    FileNotFoundError (runtime, exit 1)."""
    source_dir, target_dir = Path(source_dir), Path(target_dir)
    runs_dir, base_dir = Path(runs_dir), Path(base_dir)

    fingerprint = load(pair_id, version, fingerprint_dir)
    suite = prioritized_suite(fingerprint)

    if run_id is None:
        run_id = allocate_run_id(runs_dir)
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # snapshot persists before any execution (REQ-001, §12.2)
    (run_dir / "suite_snapshot.json").write_bytes(
        _dump_json_bytes([entry.model_dump(mode="json") for entry in suite])
    )

    started_at = datetime.now(timezone.utc)
    scope = RunScope(plans=plans, wave=wave)
    try:
        result = _ingest_and_execute(
            fingerprint, suite, source_dir, target_dir, run_dir, run_id,
            scope, base_dir,
            Path(layout_dir) if layout_dir is not None else None,
        )
    except Exception as exc:
        _persist_failed_run(run_dir, run_id, pair_id, fingerprint.version,
                            scope, started_at, exc)
        raise

    report, findings, manifest, index = result
    conversion_run = ConversionRun(
        run_id=run_id,
        pair_id=pair_id,
        fingerprint_version=fingerprint.version,
        scope=scope,
        datasets=manifest,
        suite_snapshot=[
            SuiteItem(rule_id=e.rule_id, fm_id=e.fm_id,
                      priority_score=float(e.priority_score), order=e.order)
            for e in suite
        ],
        status="review",
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        summary=report.run.summary,
    )
    (run_dir / "run.json").write_bytes(
        _dump_json_bytes(conversion_run.model_dump(mode="json"))
    )
    (run_dir / "findings.json").write_bytes(
        _dump_json_bytes(report.model_dump(mode="json"))
    )
    return RunResult(run=conversion_run, report=report, suite=suite,
                     findings=findings, run_dir=run_dir)


def _persist_failed_run(run_dir, run_id, pair_id, version, scope,
                        started_at, exc) -> None:
    failed = ConversionRun(
        run_id=run_id, pair_id=pair_id, fingerprint_version=version,
        scope=scope, status="failed", started_at=started_at,
        completed_at=datetime.now(timezone.utc),
    )
    (run_dir / "run.json").write_bytes(
        _dump_json_bytes(failed.model_dump(mode="json"))
    )
    (run_dir / "failure.txt").write_text(
        f"{type(exc).__name__}: {exc}\n", encoding="utf-8"
    )


def _ingest_and_execute(fingerprint, suite, source_dir, target_dir, run_dir,
                        run_id, scope, base_dir, layout_dir=None):
    # --- ingest + register (§10.4); rejects quarantine under ingest/
    index = RegistrationIndex()
    manifest = RunDatasetManifest()
    for side, directory in (("source", source_dir), ("target", target_dir)):
        discovered = _discover_datasets(directory)
        if not discovered:
            raise FileNotFoundError(
                f"no canonical datasets (<name>.csv or <name>.dat) found in "
                f"{side} dir {directory}"
            )
        for name, path in discovered.items():
            layout = (_load_layout(layout_dir, name, path)
                      if path.suffix == ".dat" else None)
            ingested = register_dataset(
                path, run_id=run_id, side=side, dataset_name=name,
                rejects_dir=run_dir / "ingest", layout=layout,
            )
            index.add(ingested)
            getattr(manifest, side)[name] = str(path)

    # --- dataset gate (REQ-021): refuse, never silently skip
    enabled_rules = [r for r in fingerprint.detection_rules if r.enabled]
    gaps = index.missing_for_rules(enabled_rules)
    if gaps:
        detail = "; ".join(
            f"{rule_id} needs {', '.join(missing)}"
            for rule_id, missing in sorted(gaps.items())
        )
        raise DatasetGateError(
            f"refusing to run: datasets unregistered for enabled rules — {detail} "
            f"(REQ-021)"
        )

    # --- build frames; apply plan-scope filter (§12.3)
    datasets = RuleDatasets.from_index(index)
    if scope.plans:
        for side_frames in (datasets.source, datasets.target):
            for name, frame in side_frames.items():
                if "plan_id" in frame.columns:
                    side_frames[name] = frame[
                        frame["plan_id"].isin(scope.plans)
                    ].reset_index(drop=True)

    context = ExecutionContext(
        as_of=_as_of_from_run_id(run_id),
        mapped_target_fields=_load_mapping_manifests(fingerprint, base_dir),
    )

    # --- execute in priority order (§12.1-12.2)
    modes = {fm.id: fm for fm in fingerprint.failure_modes}
    rules = {r.rule_id: r for r in fingerprint.detection_rules}
    findings_dir = run_dir / "findings"
    suite_results: list[SuiteItem] = []
    findings: list[Finding] = []
    executed = passed = 0
    severity_mix: dict[str, int] = {}
    records_total = 0

    for entry in suite:
        item = SuiteItem(
            rule_id=entry.rule_id, fm_id=entry.fm_id,
            priority_score=float(entry.priority_score), order=entry.order,
        )
        rule = rules[entry.rule_id]
        if entry.status == "skipped:disabled":
            item.outcome = "skipped"
            suite_results.append(item)
            continue
        try:
            outcome = execute_rule(rule, datasets, context)
        except UnsupportedRuleTypeError:
            item.outcome = "skipped"  # executor lands in MS-2.1
            suite_results.append(item)
            continue

        executed += 1
        if outcome.passed:
            passed += 1
            item.outcome = "pass"  # passes reported, never silent (REQ-024)
            item.records_affected = 0
        else:
            finding_id = f"{run_id}-F{len(findings) + 1:03d}"
            findings_dir.mkdir(parents=True, exist_ok=True)
            csv_path = findings_dir / f"{finding_id}.csv"
            _write_drilldown_csv(csv_path, outcome.affected)
            if outcome.detail:
                (findings_dir / f"{finding_id}.detail.json").write_bytes(
                    _dump_json_bytes(outcome.detail)
                )
            finding = build_finding(
                outcome, run_id=run_id, finding_id=finding_id,
                remediation=modes[rule.failure_mode].remediation,
                # run-relative so findings.json is byte-identical wherever
                # the run directory lives (REQ-009)
                full_detail_uri=f"findings/{finding_id}.csv",
            )
            findings.append(finding)
            item.outcome = "fail"
            item.records_affected = outcome.records_affected
            records_total += outcome.records_affected
            severity_mix[rule.severity] = severity_mix.get(rule.severity, 0) + 1
        suite_results.append(item)

    summary = RunSummary(
        rules_run=executed, passed=passed, failed=executed - passed,
        records_affected=records_total, severity_mix=severity_mix,
    )
    report = FindingsReport(
        run=ReportRun(
            run_id=run_id,
            pair_id=fingerprint.fingerprint_id,
            fingerprint_version=fingerprint.version,
            dataset_hashes={
                f"{reg.side}/{reg.dataset_name}": reg.content_hash
                for reg in index.registrations()
            },
            summary=summary,
        ),
        suite=suite_results,
        findings=findings,
    )
    return report, findings, manifest, index
