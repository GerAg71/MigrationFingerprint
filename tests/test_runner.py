"""MS-1.5 runner tests (spec §12.1–12.4, §13.1): suite snapshot persisted
before execution, priority-order execution through the REQ-021 gate, and a
deterministic findings.json (REQ-009)."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.fingerprint.models import ConversionRun, FindingsReport
from src.runner.run import DatasetGateError, allocate_run_id, run
from tests.conftest import REPO, write_extract_dirs

STORE = REPO / "data" / "fingerprints"
PAIR = "omni-zos-to-omni-linux"
RUN_ID = "RUN-2026-07-05-0001"


def clean_run(tmp_path, run_id=RUN_ID, **kwargs):
    source_dir, target_dir = write_extract_dirs(
        tmp_path, kwargs.pop("target_mutations", None))
    return run(
        PAIR, source_dir, target_dir,
        fingerprint_dir=STORE, runs_dir=tmp_path / "runs", run_id=run_id,
        **kwargs,
    )


def seeded_mutations():
    """FM-001 loan delta (-33.62) + FM-011 duplicate SSN in target."""
    return {
        "loans": lambda t: t.replace("10432.17", "10398.55"),
        "participants": lambda t: t.replace("900441208", "900441207"),
    }


# --- clean pair ---------------------------------------------------------------


def test_clean_pair_green_scoreboard(tmp_path):
    result = clean_run(tmp_path)
    summary = result.report.run.summary
    assert result.findings == []
    assert summary.failed == 0
    assert summary.records_affected == 0
    assert summary.severity_mix == {}
    assert summary.rules_run == 22  # 23 seed rules - RULE-PACKED-001 (MS-2.2)
    assert summary.passed == 22
    skipped = [i for i in result.report.suite if i.outcome == "skipped"]
    assert len(skipped) == 1
    assert result.run.status == "review"


def test_passes_reported_not_silent(tmp_path):
    """REQ-024: every executed rule appears in the suite results."""
    result = clean_run(tmp_path)
    outcomes = {i.rule_id: i.outcome for i in result.report.suite}
    assert len(result.report.suite) == 23
    assert outcomes["RULE-BAL-TOTALS-001"] == "pass"
    assert outcomes["RULE-VEST-PCT-001"] == "pass"     # executes since MS-2.1
    assert outcomes["RULE-PACKED-001"] == "skipped"    # EBCDIC decode, MS-2.2


# --- seeded defects: findings in priority order ---------------------------------


def test_seeded_defects_surface_in_priority_order(tmp_path):
    """The loan-balance mutation legitimately trips three rules since
    MS-2.1: the field compare, the re-amortization recompute, and the
    plan-level outstanding-balance sum."""
    result = clean_run(tmp_path, target_mutations=seeded_mutations())
    assert [f.rule_id for f in result.findings] == [
        "RULE-LOAN-BAL-001",     # FM-001, score 0.63,   suite order 2
        "RULE-LOAN-RECOMP-001",  # FM-001, score 0.63,   suite order 3
        "RULE-DUP-001",          # FM-011, score 0.34,   suite order 15
        "RULE-LOAN-CNT-001",     # FM-014, score 0.3375, suite order 16
    ]
    assert [f.finding_id for f in result.findings] == [
        f"{RUN_ID}-F001", f"{RUN_ID}-F002", f"{RUN_ID}-F003", f"{RUN_ID}-F004",
    ]
    loan = result.findings[0]
    assert loan.sample_records[0].delta == Decimal("-33.62")
    assert loan.remediation.startswith("Recompute amortization")
    dup = result.findings[2]
    assert dup.records_affected == 2  # both rows of the duplicate group
    summary = result.report.run.summary
    assert summary.failed == 4
    assert summary.severity_mix == {"HIGH": 4}
    assert summary.records_affected == 5


def test_drilldown_csv_written_per_finding(tmp_path):
    result = clean_run(tmp_path, target_mutations=seeded_mutations())
    for finding in result.findings:
        # URI is run-relative so the report stays byte-identical (REQ-009)
        assert finding.full_detail_uri == f"findings/{finding.finding_id}.csv"
        csv_path = result.run_dir / finding.full_detail_uri
        assert csv_path.is_file()
        content = csv_path.read_text(encoding="utf-8")
        assert "source" in content.splitlines()[0]
    loan_csv = (result.run_dir / result.findings[0].full_detail_uri).read_text(
        encoding="utf-8")
    assert "10432.17" in loan_csv and "10398.55" in loan_csv


# --- suite snapshot (REQ-001) ----------------------------------------------------


def test_suite_snapshot_persisted_with_full_ordering(tmp_path):
    result = clean_run(tmp_path)
    snapshot_path = result.run_dir / "suite_snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert len(snapshot) == 23
    assert snapshot[0] == {
        "order": 1, "rule_id": "RULE-BAL-TOTALS-001", "fm_id": "FM-007",
        "priority_score": "0.7125", "severity": "CRITICAL",
        "source_dataset": "balances", "target_dataset": "balances",
        "status": "pending",
    }


def test_snapshot_and_failed_run_persisted_when_gate_refuses(tmp_path):
    source_dir, target_dir = write_extract_dirs(tmp_path)
    (target_dir / "loans.csv").unlink()  # loans unregistered on target side
    with pytest.raises(DatasetGateError) as exc:
        run(PAIR, source_dir, target_dir,
            fingerprint_dir=STORE, runs_dir=tmp_path / "runs", run_id=RUN_ID)
    assert "target/loans" in str(exc.value)
    assert "RULE-LOAN-BAL-001" in str(exc.value)

    run_dir = tmp_path / "runs" / RUN_ID
    assert (run_dir / "suite_snapshot.json").is_file()  # persisted pre-execution
    failed = ConversionRun.model_validate(
        json.loads((run_dir / "run.json").read_text(encoding="utf-8")))
    assert failed.status == "failed"
    assert "REQ-021" in (run_dir / "failure.txt").read_text(encoding="utf-8")


# --- determinism (REQ-009) --------------------------------------------------------


def test_findings_json_byte_identical_across_reruns(tmp_path):
    a = clean_run(tmp_path / "a", target_mutations=seeded_mutations())
    b = clean_run(tmp_path / "b", target_mutations=seeded_mutations())
    findings_a = (a.run_dir / "findings.json").read_bytes()
    findings_b = (b.run_dir / "findings.json").read_bytes()
    assert findings_a == findings_b
    snapshot_a = (a.run_dir / "suite_snapshot.json").read_bytes()
    snapshot_b = (b.run_dir / "suite_snapshot.json").read_bytes()
    assert snapshot_a == snapshot_b


def test_report_records_version_and_dataset_hashes(tmp_path):
    """REQ-014: report header carries fingerprint version + content hashes."""
    result = clean_run(tmp_path)
    header = result.report.run
    assert header.fingerprint_version == "1.0.0"
    assert set(header.dataset_hashes) == {
        f"{side}/{name}" for side in ("source", "target")
        for name in ("plans", "participants", "balances", "contributions",
                     "loans", "loan_payments", "vesting")
    }
    assert all(h.startswith("sha256:") for h in header.dataset_hashes.values())
    # identical clean files on both sides -> identical hashes per dataset
    assert (header.dataset_hashes["source/loans"]
            == header.dataset_hashes["target/loans"])


def test_findings_json_round_trips_through_model(tmp_path):
    result = clean_run(tmp_path, target_mutations=seeded_mutations())
    payload = json.loads((result.run_dir / "findings.json").read_text(encoding="utf-8"))
    report = FindingsReport.model_validate(payload)
    assert report == result.report


# --- scope + allocation -------------------------------------------------------------


def test_plans_scope_filters_datasets(tmp_path):
    """A defect in PLN001 is invisible to a run scoped to another plan."""
    result = clean_run(tmp_path, target_mutations=seeded_mutations(),
                       plans=["PLN999"])
    assert result.findings == []
    assert result.run.scope.plans == ["PLN999"]


def test_run_id_allocation_daily_sequence(tmp_path):
    from datetime import date
    runs = tmp_path / "runs"
    (runs / "RUN-2026-07-05-0001").mkdir(parents=True)
    (runs / "RUN-2026-07-05-0007").mkdir()
    (runs / "RUN-2026-07-04-0099").mkdir()  # other day ignored
    assert allocate_run_id(runs, date(2026, 7, 5)) == "RUN-2026-07-05-0008"
    assert allocate_run_id(runs, date(2026, 7, 6)) == "RUN-2026-07-06-0001"


def test_no_datasets_found_is_runtime_error(tmp_path):
    source_dir, target_dir = write_extract_dirs(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError, match="no canonical datasets"):
        run(PAIR, source_dir, empty,
            fingerprint_dir=STORE, runs_dir=tmp_path / "runs", run_id=RUN_ID)
