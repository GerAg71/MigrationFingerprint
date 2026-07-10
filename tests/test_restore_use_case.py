"""The Omni->Omni restore use case end to end (strategy doc: docs/
Omni_to_Omni_Restore_Strategy.md).

Same platform pair as the transformation path, different methodology: a
backup/restore should be value-identical, so the restore fingerprint runs
at tolerance zero and every difference is a finding. The clean pair proves
zero false noise; the seeded pair's manifest below was derived from
tests/datagen/restore.py's mutations BEFORE first execution (REQ-032
discipline) - one planted defect per restore failure mode, all surfacing.
"""

import json

import pytest

from src.fingerprint.loader import load
from src.fingerprint.prioritize import prioritized_suite
from src.runner.run import run
from tests.conftest import REPO, copy_fingerprint_store

SAMPLES = REPO / "data" / "samples"
PAIR = "omni-zos-to-omni-linux-restore"
RUN_ID = "RUN-2026-07-10-0001"

# rule -> (records_affected) for PLN-REST-SEED-01; every rule fires
SEEDED_MANIFEST = {
    "RULE-RST-VEST-001": 1,   # FM-101: vested_pct disagrees with GRADED6
    "RULE-RST-UDF-001": 1,    # FM-102: UDF-03 definition missing_in_target
    "RULE-RST-UDF-002": 1,    # FM-102: (PLN-R001, UDF-01) value count short
    "RULE-RST-FMT-001": 2,    # FM-103: BR-EAST hiding in two fillers
    "RULE-RST-FMT-002": 1,    # FM-103: letter inside a 9(9) SSN
    "RULE-RST-REQ-001": 1,    # FM-104: dob blanked
    "RULE-RST-REQ-002": 1,    # FM-104: loan origination_date blanked
    "RULE-RST-CNT-001": 1,    # FM-105: PLN-R002 participant count 60 -> 59
    "RULE-RST-CNT-002": 1,    # FM-105: PLN-R001 loan payments short by two
    "RULE-RST-DIFF-001": 1,   # FM-106: balance moved 10.00
    "RULE-RST-DIFF-002": 1,   # FM-106: outstanding moved -25.00
    "RULE-RST-DIFF-003": 2,   # FM-106: renamed surname + the blanked dob
}


def run_pair(tmp_path, plan: str, run_id: str = RUN_ID):
    store = copy_fingerprint_store(tmp_path)
    return run(PAIR, SAMPLES / "source" / plan, SAMPLES / "target" / plan,
               fingerprint_dir=store, runs_dir=tmp_path / "runs",
               run_id=run_id)


# --- the fingerprint itself -----------------------------------------------------


def test_restore_fingerprint_validates_and_prioritizes():
    fp = load(PAIR, fingerprint_dir=REPO / "data" / "fingerprints")
    assert fp.platform_pair.source == "OMNI_MAINFRAME_ZOS"
    assert fp.platform_pair.target == "OMNI_LINUX_RHEL"
    assert len(fp.failure_modes) == 6
    assert len(fp.detection_rules) == 12
    assert "backup/restore" in fp.changelog

    suite = prioritized_suite(fp)
    # custom-code drift leads (0.70 x 0.90); the tolerance-zero net second
    assert suite[0].rule_id == "RULE-RST-VEST-001"
    assert [e.rule_id for e in suite[1:4]] == [
        "RULE-RST-DIFF-001", "RULE-RST-DIFF-002", "RULE-RST-DIFF-003"]
    # every rule type in play, including the new one
    assert {r.type for r in fp.detection_rules} == {
        "derived_recompute", "referential", "count_balance",
        "format_conformance", "field_compare"}


# --- clean restore: green board, zero false noise --------------------------------


def test_clean_restore_is_green(tmp_path):
    result = run_pair(tmp_path, "PLN-REST-CLEAN-01")
    summary = result.report.run.summary
    assert summary.rules_run == 12
    assert summary.passed == 12
    assert summary.failed == 0
    assert summary.records_affected == 0
    assert result.findings == []


# --- seeded restore: every planted defect surfaces (REQ-032) ---------------------


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("restore")
    return run_pair(tmp, "PLN-REST-SEED-01"), tmp


def test_seeded_manifest_exact(seeded):
    result, _ = seeded
    actual = {f.rule_id: f.records_affected for f in result.findings}
    assert actual == SEEDED_MANIFEST
    summary = result.report.run.summary
    assert summary.failed == len(SEEDED_MANIFEST)
    assert summary.passed == 0  # every rule tripped on the seeded pair
    assert summary.records_affected == sum(SEEDED_MANIFEST.values())


def test_seeded_findings_carry_the_stories(seeded):
    result, _ = seeded
    by_rule = {f.rule_id: f for f in result.findings}

    # off-label: the filler value is named in the drill-down
    filler = by_rule["RULE-RST-FMT-001"].sample_records
    assert {r.target["filler_442_448"] for r in filler} == {"BR-EAST"}
    assert all(r.target["_check"] == "data_in_unused_position" for r in filler)

    # UDF gap: the lost definition is identified by plan + udf id
    udf = by_rule["RULE-RST-UDF-001"].sample_records[0]
    assert udf.keys == {"plan_id": "PLN-R001", "udf_id": "UDF-03"}
    assert udf.source["_set"] == "missing_in_target"

    # truncation: the count delta is signed and grouped by plan
    cnt = by_rule["RULE-RST-CNT-001"].sample_records[0]
    assert cnt.keys == {"plan_id": "PLN-R002"}
    assert cnt.delta == -1

    # tolerance zero: the 10.00 balance move is exact
    diff = by_rule["RULE-RST-DIFF-001"].sample_records[0]
    assert str(diff.delta) == "10.00"


def test_seeded_run_is_deterministic(seeded, tmp_path):
    """REQ-009 holds for the new pair and rule type: same inputs + same
    fingerprint + same run id => byte-identical findings.json."""
    result, tmp = seeded
    first = (tmp / "runs" / RUN_ID / "findings.json").read_bytes()
    rerun = run_pair(tmp_path, "PLN-REST-SEED-01")
    second = (tmp_path / "runs" / RUN_ID / "findings.json").read_bytes()
    assert first == second
    assert rerun.report.run.summary.failed == len(SEEDED_MANIFEST)


# --- the pair is a first-class citizen --------------------------------------------


def test_pairs_cli_lists_the_restore_pair(capsys):
    from src.cli import main

    rc = main(["pairs", "--fingerprint-dir",
               str(REPO / "data" / "fingerprints"), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    by_pair = {p["pair_id"]: p for p in payload}
    assert by_pair[PAIR] == {"pair_id": PAIR, "version": "1.0.0",
                             "status": "published", "modes": 6, "rules": 12}


def test_api_serves_the_restore_suite(tmp_path):
    from fastapi.testclient import TestClient
    from src.api.app import create_app

    store = copy_fingerprint_store(tmp_path)
    client = TestClient(create_app(fingerprint_dir=store,
                                   runs_dir=tmp_path / "runs"))
    pairs = {p["pair_id"] for p in client.get("/platform-pairs").json()}
    assert PAIR in pairs
    suite = client.get(f"/fingerprints/{PAIR}/suite").json()
    assert suite["suite"][0]["rule_id"] == "RULE-RST-VEST-001"