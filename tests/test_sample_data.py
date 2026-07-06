"""MS-1.6 (spec Ch. 25, REQ-032): the clean pair produces zero findings; the
seeded pair produces exactly the expected manifest — every seeded defect
found, nothing else flagged. Plus data policy (REQ-031) and deterministic
regeneration checks."""

import csv
from decimal import Decimal
from pathlib import Path

from src.runner.run import run
from tests.conftest import REPO
from tests.datagen.writer import write_samples

SAMPLES = REPO / "data" / "samples"
STORE = REPO / "data" / "fingerprints"
PAIR = "omni-zos-to-omni-linux"
RUN_ID = "RUN-2026-07-05-0001"

# Exact Phase-1 manifest for PLN-SEED-01, hand-derived from the mutator
# definitions (tests/datagen/mutators.py) before first execution and verified
# against the engine. One defect may fire several rules (FM-007 backstops
# FM-012/13; the loan mutations feed both loan rules) — that is the spec'd
# behavior, and these are the exact rule-level expectations.
EXPECTED_MANIFEST: dict[str, int] = {
    "RULE-BAL-TOTALS-001": 4,    # plan sum + P0007/P0013/P0018 participant sums
    "RULE-LOAN-BAL-001": 1,      # FM-001: L2 delta -33.62
    "RULE-LOAN-RECOMP-001": 1,   # FM-001: L2 diverges from re-amortization (MS-2.1)
    "RULE-BAL-MT-001": 3,        # PRETAX +250.01, ROTH -250.00, MATCH net
    "RULE-BAL-INV-001": 4,       # F01, F02, F03, F04 subtotals
    "RULE-VEST-PCT-001": 1,      # FM-002: P0017 stored 60% vs recomputed 80% (MS-2.1)
    "RULE-PCOUNT-001": 2,        # FM-009: ACTIVE +1, TERMINATED -1
    "RULE-DERIVED-TRACE-001": 1, # FM-003: svc_points on P0042
    "RULE-PROV-MATRIX-001": 2,   # FM-004: safe_harbor dropped + catch_up inverted
    "RULE-KEYS-001": 1,          # FM-010: blank SSN P0030
    "RULE-CONTRIB-001": 1,       # FM-015: MATCH +50.00 last cycle
    "RULE-DATE-001": 4,          # dob cmp + dob<1900 (P0008), term cmp (P0009, P0020)
    "RULE-DUP-001": 2,           # FM-011: both duplicate-SSN rows
    "RULE-LOAN-CNT-001": 2,      # FM-014: count 6->5 + outstanding sum variance
    "RULE-LOAN-TERMS-001": 1,    # FM-014: L3 missing maturity
    "RULE-ENC-001": 2,           # FM-005: mojibake first+last name P0044 (MS-2.1)
    "RULE-SORT-001": 2,          # FM-005 digit-name boundary + FM-016 Ha#nk shift
    "RULE-NEG-001": 1,           # FM-018: MATCH -412.06
    "RULE-LEN-001": 1,           # FM-016: 41-char address
    "RULE-CHAR-001": 4,          # FM-016 '#' + P0044 mojibake x2 + P0115 digit name
    "RULE-DATEVAL-001": 2,       # FM-017 term<hire + P0009 epoch term<hire
}
PHASE2_SKIPPED = {"RULE-PACKED-001"}  # EBCDIC decode lands in MS-2.2


def run_pair(plan: str, tmp_path: Path):
    return run(
        PAIR,
        SAMPLES / "source" / plan,
        SAMPLES / "target" / plan,
        fingerprint_dir=STORE, runs_dir=tmp_path / "runs", run_id=RUN_ID,
    )


def test_clean_pair_zero_findings(tmp_path):
    """Spec §25.2: the clean pair proves the suite produces zero false noise."""
    result = run_pair("PLN-CLEAN-01", tmp_path)
    assert result.findings == []
    summary = result.report.run.summary
    assert (summary.rules_run, summary.passed, summary.failed) == (22, 22, 0)


def test_seeded_pair_matches_manifest_exactly(tmp_path):
    """REQ-032: every seeded defect found, nothing else flagged."""
    result = run_pair("PLN-SEED-01", tmp_path)
    got = {f.rule_id: f.records_affected for f in result.findings}
    assert got == EXPECTED_MANIFEST

    # findings surface in priority order (demo step 3)
    suite_order = {e.rule_id: e.order for e in result.suite}
    orders = [suite_order[f.rule_id] for f in result.findings]
    assert orders == sorted(orders)

    # the only executable rule the defects leave untouched
    passes = {i.rule_id for i in result.report.suite if i.outcome == "pass"}
    assert passes == {"RULE-VEST-SCHED-001"}

    skipped = {i.rule_id for i in result.report.suite if i.outcome == "skipped"}
    assert skipped == PHASE2_SKIPPED

    summary = result.report.run.summary
    assert summary.records_affected == 42
    assert summary.severity_mix == {"CRITICAL": 3, "HIGH": 10, "MEDIUM": 6,
                                    "LOW": 2}


def test_seeded_defect_details(tmp_path):
    """Spot-check the spec §25.3 signature values inside the findings."""
    result = run_pair("PLN-SEED-01", tmp_path)
    by_rule = {f.rule_id: f for f in result.findings}

    loan = by_rule["RULE-LOAN-BAL-001"].sample_records[0]
    assert loan.keys["loan_id"] == "L2"
    assert loan.delta == Decimal("-33.62")

    dup = by_rule["RULE-DUP-001"]
    assert {r.target["participant_id"] for r in dup.sample_records} == \
        {"P0100", "P0101"}

    roth = next(r for r in by_rule["RULE-BAL-MT-001"].sample_records
                if r.keys["money_type_code"] == "ROTH")
    assert roth.delta == Decimal("-250.00")

    f03 = next(r for r in by_rule["RULE-BAL-INV-001"].sample_records
               if r.keys["investment_code"] == "F03")
    assert f03.delta == Decimal("75.25")

    neg = by_rule["RULE-NEG-001"].sample_records[0]
    assert neg.target["balance"] == "-412.06"

    trace = by_rule["RULE-DERIVED-TRACE-001"].sample_records[0]
    assert trace.keys["participant_id"] == "P0042"
    assert trace.target["svc_points"] == "142"

    century = next(r for r in by_rule["RULE-DATE-001"].sample_records
                   if r.target and r.target.get("dob") == "1897-03-12")
    assert century.keys["participant_id"] == "P0008"

    # MS-2.1 detections
    vest = by_rule["RULE-VEST-PCT-001"].sample_records[0]
    assert vest.keys["participant_id"] == "P0017"
    assert vest.delta == Decimal("-0.2000")

    recomp = by_rule["RULE-LOAN-RECOMP-001"].sample_records[0]
    assert recomp.keys["loan_id"] == "L2"
    assert recomp.delta == Decimal("-33.62")

    enc_fields = {list(r.target)[0] for r in by_rule["RULE-ENC-001"].sample_records}
    assert enc_fields == {"first_name", "last_name"}  # JosÃ© + RamÃ­rez

    sort_checks = by_rule["RULE-SORT-001"].sample_records
    assert any("0degaard" in r.target["value"] for r in sort_checks)


def test_regeneration_is_byte_identical(tmp_path):
    """Spec §25.4: deterministic generator — regeneration reproduces the
    committed sample files exactly."""
    write_samples(tmp_path / "samples")
    committed = sorted(SAMPLES.rglob("*.csv"))
    assert committed, "no committed sample CSVs found"
    for committed_file in committed:
        relative = committed_file.relative_to(SAMPLES)
        regenerated = tmp_path / "samples" / relative
        assert regenerated.is_file(), f"missing regenerated {relative}"
        assert regenerated.read_bytes() == committed_file.read_bytes(), relative


def test_data_policy_synthetic_only():
    """REQ-031: 900-xx SSNs, plan size in the 50–200 band, spec §25.2 shape."""
    for pair in ("PLN-CLEAN-01", "PLN-SEED-01"):
        path = SAMPLES / "source" / pair / "participants.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert len(rows) == 120
        assert all(row["ssn"].startswith("900") for row in rows)
        with (SAMPLES / "source" / pair / "loans.csv").open(
                encoding="utf-8", newline="") as handle:
            assert len(list(csv.DictReader(handle))) == 6
