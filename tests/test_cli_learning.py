"""MS-2.4 CLI: demo step 4 end to end — confirm two findings, mark one false
positive, show history, publish a patch version (CLI_SPEC review/publish/
diff/history/author-mode)."""

import json

from src.cli import main
from tests.conftest import REPO, copy_fingerprint_store

SAMPLES = REPO / "data" / "samples"
PAIR = "omni-zos-to-omni-linux"


def run_seeded(tmp_path, store) -> str:
    """Run the seeded pair via the CLI and return the allocated run id.
    The CLI allocates RUN-<today>-NNNN from the wall clock, so tests must
    discover it rather than hardcode a date (UTC CI vs local clocks)."""
    rc = main(["run", "--pair", PAIR,
               "--source-dir", str(SAMPLES / "source" / "PLN-SEED-01"),
               "--target-dir", str(SAMPLES / "target" / "PLN-SEED-01"),
               "--fingerprint-dir", str(store),
               "--runs-dir", str(tmp_path / "runs")])
    assert rc == 0
    (run_dir,) = (tmp_path / "runs").iterdir()
    return run_dir.name


def finding_id(tmp_path, run_id, rule_id) -> str:
    payload = json.loads(
        (tmp_path / "runs" / run_id / "findings.json").read_text(encoding="utf-8"))
    return next(f["finding_id"] for f in payload["findings"]
                if f["rule_id"] == rule_id)


def review(tmp_path, run_id, store, rule_id, decision, capsys) -> str:
    fid = finding_id(tmp_path, run_id, rule_id)
    rc = main(["review", fid, "--decision", decision,
               "--reviewer", "jsmith",
               "--runs-dir", str(tmp_path / "runs"),
               "--fingerprint-dir", str(store)])
    out = capsys.readouterr().out
    assert rc == 0
    return out


def test_demo_step_4_full_flow(tmp_path, capsys):
    """Confirm two findings + one false positive -> probabilities and
    history update -> publish creates the new patch version (spec §23.5)."""
    store = copy_fingerprint_store(tmp_path)
    run_id = run_seeded(tmp_path, store)
    capsys.readouterr()

    out = review(tmp_path, run_id, store, "RULE-LOAN-BAL-001", "confirmed", capsys)
    assert "FM-001 probability: 0.7 -> 0.727" in out
    assert "confirmed 0 -> 1" in out
    assert "draft 1.0.1 pending" in out

    out = review(tmp_path, run_id, store, "RULE-BAL-TOTALS-001", "confirmed", capsys)
    assert "FM-007 probability: 0.75 -> 0.773" in out

    out = review(tmp_path, run_id, store, "RULE-LEN-001", "false_positive", capsys)
    assert "FM-016 probability: 0.5 -> 0.455" in out
    assert "false positives 0 -> 1" in out

    rc = main(["history", "--pair", PAIR, "--fingerprint-dir", str(store)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "3 event(s)" in out
    assert "FM-001  confirmed" in out
    assert "FM-016  false_positive" in out

    rc = main(["history", "--pair", PAIR, "--fm", "FM-001",
               "--fingerprint-dir", str(store)])
    out = capsys.readouterr().out
    assert "1 event(s)" in out

    rc = main(["publish", "--pair", PAIR, "--bump", "patch",
               "--changelog", "wave-1 write-backs",
               "--fingerprint-dir", str(store)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "published omni-zos-to-omni-linux: 1.0.0 -> 1.0.1" in out
    assert "FM-001: probability 0.7 -> 0.727" in out

    # the suite now loads the published 1.0.1
    rc = main(["suite", "--pair", PAIR, "--fingerprint-dir", str(store)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "v1.0.1" in out

    # findings list reflects adjudication
    rc = main(["findings", run_id, "--runs-dir", str(tmp_path / "runs"),
               "--status", "confirmed"])
    out = capsys.readouterr().out
    assert "2 of 21 shown" in out


def test_review_duplicate_and_unknown_exit_1(tmp_path, capsys):
    store = copy_fingerprint_store(tmp_path)
    run_id = run_seeded(tmp_path, store)
    capsys.readouterr()
    review(tmp_path, run_id, store, "RULE-DUP-001", "confirmed", capsys)
    fid = finding_id(tmp_path, run_id, "RULE-DUP-001")
    rc = main(["review", fid, "--decision", "false_positive",
               "--runs-dir", str(tmp_path / "runs"),
               "--fingerprint-dir", str(store)])
    assert rc == 1
    assert "immutable" in capsys.readouterr().err

    rc = main(["review", f"{run_id}-F999", "--decision", "confirmed",
               "--runs-dir", str(tmp_path / "runs"),
               "--fingerprint-dir", str(store)])
    assert rc == 1


def test_publish_without_draft_exits_1(tmp_path, capsys):
    store = copy_fingerprint_store(tmp_path)
    rc = main(["publish", "--pair", PAIR, "--bump", "patch",
               "--fingerprint-dir", str(store)])
    assert rc == 1
    assert "no draft" in capsys.readouterr().err


def test_diff_cli(tmp_path, capsys):
    store = copy_fingerprint_store(tmp_path)
    run_id = run_seeded(tmp_path, store)
    capsys.readouterr()
    review(tmp_path, run_id, store, "RULE-LOAN-BAL-001", "confirmed", capsys)
    main(["publish", "--pair", PAIR, "--bump", "patch",
          "--fingerprint-dir", str(store)])
    capsys.readouterr()
    rc = main(["diff", "--pair", PAIR, "--from", "1.0.0", "--to", "1.0.1",
               "--fingerprint-dir", str(store)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "1.0.0 -> 1.0.1" in out
    assert "FM-001: probability 0.7 -> 0.727" in out


def test_author_mode_cli_with_flags(tmp_path, capsys):
    store = copy_fingerprint_store(tmp_path)
    rule_json = json.dumps({
        "rule_id": "RULE-BENEF-001", "type": "field_compare",
        "target_dataset": "participants",
        "params": {"validity": [{"field": "ssn", "not_null": True}]},
        "severity": "MEDIUM",
    })
    rc = main(["author-mode", "--pair", PAIR,
               "--name", "Beneficiary allocation drift",
               "--category", "PARTICIPANT",
               "--description", "Beneficiary percentages fail to total 100.",
               "--domains", "PARTICIPANT",
               "--impact", "0.7",
               "--remediation", "Re-normalize allocations.",
               "--rule-json", rule_json,
               "--fingerprint-dir", str(store)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "added FM-019" in out
    rc = main(["publish", "--pair", PAIR, "--bump", "minor",
               "--fingerprint-dir", str(store)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "1.0.0 -> 1.1.0" in out
    assert "modes added: FM-019" in out