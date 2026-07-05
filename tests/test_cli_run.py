"""MS-1.5 CLI tests: `fingerprint run` scoreboard + exit codes (0/2/3),
`fingerprint findings`, `fingerprint show` (CLI_SPEC.md)."""

import json

from src.cli import main
from tests.conftest import REPO, write_extract_dirs

STORE = REPO / "data" / "fingerprints"
PAIR = "omni-zos-to-omni-linux"


def run_args(source_dir, target_dir, runs_dir, *extra):
    return ["run", "--pair", PAIR,
            "--source-dir", str(source_dir), "--target-dir", str(target_dir),
            "--fingerprint-dir", str(STORE), "--runs-dir", str(runs_dir),
            *extra]


def seeded_mutations():
    return {"loans": lambda t: t.replace("10432.17", "10398.55")}


def test_run_clean_prints_green_scoreboard(tmp_path, capsys):
    source_dir, target_dir = write_extract_dirs(tmp_path)
    rc = main(run_args(source_dir, target_dir, tmp_path / "runs"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "17 run, 17 passed, 0 failed, 6 skipped" in out
    assert "Records affected: 0" in out
    assert "Severity mix: none" in out


def test_run_with_findings_still_exits_0(tmp_path, capsys):
    """CLI_SPEC: a run that produced findings still exits 0 — the run succeeded.
    The loan mutation trips both the field compare and the plan-level sum."""
    source_dir, target_dir = write_extract_dirs(tmp_path, seeded_mutations())
    rc = main(run_args(source_dir, target_dir, tmp_path / "runs"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "2 failed" in out
    assert "Severity mix: HIGH=2" in out


def test_fail_on_findings_gates_exit_2(tmp_path, capsys):
    source_dir, target_dir = write_extract_dirs(tmp_path, seeded_mutations())
    rc = main(run_args(source_dir, target_dir, tmp_path / "runs",
                       "--fail-on-findings"))
    assert rc == 2


def test_fail_on_findings_severity_threshold(tmp_path, capsys):
    source_dir, target_dir = write_extract_dirs(tmp_path, seeded_mutations())
    # the seeded finding is HIGH: gate at CRITICAL passes, at HIGH trips
    rc_critical = main(run_args(source_dir, target_dir, tmp_path / "runs" / "a",
                                "--fail-on-findings", "CRITICAL"))
    rc_high = main(run_args(source_dir, target_dir, tmp_path / "runs" / "b",
                            "--fail-on-findings", "HIGH"))
    assert rc_critical == 0
    assert rc_high == 2


def test_run_gate_refusal_exits_3(tmp_path, capsys):
    source_dir, target_dir = write_extract_dirs(tmp_path)
    (target_dir / "loans.csv").unlink()
    rc = main(run_args(source_dir, target_dir, tmp_path / "runs"))
    err = capsys.readouterr().err
    assert rc == 3
    assert "refused" in err
    assert "target/loans" in err


def test_run_json_output(tmp_path, capsys):
    source_dir, target_dir = write_extract_dirs(tmp_path, seeded_mutations())
    rc = main(run_args(source_dir, target_dir, tmp_path / "runs", "--json"))
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["findings"] == 2
    assert payload["summary"]["failed"] == 2
    assert payload["run_id"].startswith("RUN-")


def _completed_run(tmp_path, capsys) -> str:
    source_dir, target_dir = write_extract_dirs(tmp_path, seeded_mutations())
    main(run_args(source_dir, target_dir, tmp_path / "runs", "--json"))
    return json.loads(capsys.readouterr().out)["run_id"]


def test_findings_lists_run_findings(tmp_path, capsys):
    run_id = _completed_run(tmp_path, capsys)
    rc = main(["findings", run_id, "--runs-dir", str(tmp_path / "runs")])
    out = capsys.readouterr().out
    assert rc == 0
    assert f"{run_id}-F001" in out
    assert "RULE-LOAN-BAL-001" in out
    assert "FM-001" in out


def test_findings_severity_filter(tmp_path, capsys):
    run_id = _completed_run(tmp_path, capsys)
    rc = main(["findings", run_id, "--severity", "CRITICAL",
               "--runs-dir", str(tmp_path / "runs")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "0 of 2 shown" in out


def test_show_prints_sample_records_and_remediation(tmp_path, capsys):
    run_id = _completed_run(tmp_path, capsys)
    rc = main(["show", f"{run_id}-F001", "--runs-dir", str(tmp_path / "runs")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "10432.17" in out          # source value
    assert "10398.55" in out          # target value
    assert "-33.62" in out            # delta
    assert "Remediation: Recompute amortization" in out
    assert "Drill-down CSV:" in out


def test_show_unknown_finding_exits_1(tmp_path, capsys):
    run_id = _completed_run(tmp_path, capsys)
    rc = main(["show", f"{run_id}-F999", "--runs-dir", str(tmp_path / "runs")])
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_findings_unknown_run_exits_1(tmp_path, capsys):
    rc = main(["findings", "RUN-2026-01-01-0001",
               "--runs-dir", str(tmp_path / "runs")])
    assert rc == 1
