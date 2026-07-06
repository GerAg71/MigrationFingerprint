"""MS-2.3 (spec §13.1–13.3): self-contained findings.html (REQ-025), the
five reconciliation reports rendered from the seeded pair (REQ-026),
deterministic rendering, and REQ-014 headers on every artifact."""

import json
import re
from pathlib import Path

import pytest

from src.cli import main
from src.report.html import RECON_KINDS
from src.runner.run import run
from tests.conftest import REPO

SAMPLES = REPO / "data" / "samples"
STORE = REPO / "data" / "fingerprints"
PAIR = "omni-zos-to-omni-linux"
RUN_ID = "RUN-2026-07-05-0001"


@pytest.fixture(scope="module")
def seeded_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ms23")
    return run(
        PAIR,
        SAMPLES / "source" / "PLN-SEED-01",
        SAMPLES / "target" / "PLN-SEED-01",
        fingerprint_dir=STORE, runs_dir=tmp / "runs", run_id=RUN_ID,
    )


def render_all(seeded_run) -> dict[str, str]:
    runs_dir = str(seeded_run.run_dir.parent)
    rc = main(["report", RUN_ID, "--recon", "all", "--runs-dir", runs_dir])
    assert rc == 0
    return {
        kind: (seeded_run.run_dir / f"reconciliation_{kind}.html")
        .read_text(encoding="utf-8")
        for kind in RECON_KINDS
    }


def assert_self_contained(html: str) -> None:
    """REQ-025: inline CSS, no external requests of any kind."""
    assert "<style>" in html
    assert "http://" not in html and "https://" not in html
    assert "<link" not in html
    assert "<script" not in html
    assert not re.search(r'src\s*=\s*["\']', html)


# --- findings.html (§13.1) -----------------------------------------------------


def test_run_writes_findings_html(seeded_run):
    path = seeded_run.run_dir / "findings.html"
    assert path.is_file()
    html = path.read_text(encoding="utf-8")
    assert_self_contained(html)


def test_findings_html_scoreboard_and_header(seeded_run):
    html = (seeded_run.run_dir / "findings.html").read_text(encoding="utf-8")
    # REQ-014 header: run id, pair, fingerprint version, dataset hashes
    assert RUN_ID in html
    assert "omni-zos-to-omni-linux" in html
    assert "1.0.0" in html
    assert "sha256:" in html
    # scoreboard numbers for the seeded pair (21 findings / 42 records)
    summary = seeded_run.report.run.summary
    assert f'<div class="n">{summary.rules_run}</div>' in html
    assert f'<div class="n">{summary.failed}</div>' in html
    assert f'<div class="n">{summary.records_affected}</div>' in html


def test_findings_html_suite_and_priority_order(seeded_run):
    html = (seeded_run.run_dir / "findings.html").read_text(encoding="utf-8")
    # prioritized suite present with outcomes; findings in priority order
    assert "RULE-BAL-TOTALS-001" in html
    first = html.index(f"{RUN_ID}-F001")
    second = html.index(f"{RUN_ID}-F002")
    assert first < second
    # drill-down link and severity chips
    assert f"findings/{RUN_ID}-F001.csv" in html
    assert "#b91c1c" in html  # CRITICAL color token (spec §20.4)
    # open exception register (§13.3): every finding is currently open
    assert "Exception register" in html


def test_findings_html_deterministic(seeded_run):
    from src.report.html import render_findings_html

    a = render_findings_html(seeded_run.report)
    b = render_findings_html(seeded_run.report)
    assert a == b
    assert a.encode("utf-8") == \
        (seeded_run.run_dir / "findings.html").read_bytes()


# --- reconciliation suite (§13.2, REQ-026) ---------------------------------------


def test_five_reconciliation_reports_render(seeded_run):
    reports = render_all(seeded_run)
    assert set(reports) == set(RECON_KINDS)
    for kind, html in reports.items():
        assert_self_contained(html)
        assert RUN_ID in html and "sha256:" in html, kind  # REQ-014


def test_plan_reconciliation_content(seeded_run):
    html = render_all(seeded_run)["plan"]
    assert "PLN-SEED-01" in html
    assert "PRETAX" in html and "ROTH" in html
    assert "250.01" in html    # PRETAX money-type delta
    assert "-250.00" in html   # ROTH delta
    assert "VARIANCE" in html  # rollup status


def test_participant_reconciliation_content(seeded_run):
    html = render_all(seeded_run)["participant"]
    assert "ACTIVE" in html and "TERMINATED" in html
    # FM-009: TERMINATED counted ACTIVE -> 106 vs 107
    assert ">106<" in html and ">107<" in html
    # per-participant mismatch listing includes the FM-018 participant
    assert "P0018" in html


def test_loan_reconciliation_content(seeded_run):
    html = render_all(seeded_run)["loan"]
    assert ">6<" in html and ">5<" in html  # loan count 6 -> 5 (FM-014)
    assert "missing repayment terms" in html
    assert 'class="status-pill bad">1<' in html  # L3 missing maturity


def test_contribution_reconciliation_content(seeded_run):
    html = render_all(seeded_run)["contribution"]
    assert "2026-06" in html          # last payroll cycle resolved from data
    assert "50.00" in html            # FM-015 MATCH delta
    assert "employer" in html and "employee" in html


def test_quality_report_content(seeded_run):
    html = render_all(seeded_run)["quality"]
    assert "Field-length violations" in html
    assert "P0060" in html                       # 41-char address
    assert "Invalid characters" in html
    assert "Ha#nk" in html or "Ha&#35;nk" in html
    assert "Negative balances" in html
    assert "-412.06" in html
    assert "Missing key fields" in html          # blank SSN
    assert "Invalid or future dates" in html
    assert "gte_field:hire_date" in html


def test_reconciliation_rendering_deterministic(seeded_run):
    first = render_all(seeded_run)
    second = render_all(seeded_run)
    assert first == second


# --- CLI report command -----------------------------------------------------------


def test_report_json_format_prints_findings(seeded_run, capsys):
    rc = main(["report", RUN_ID, "--format", "json",
               "--runs-dir", str(seeded_run.run_dir.parent)])
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["run"]["run_id"] == RUN_ID


def test_report_single_recon_kind(seeded_run, capsys):
    rc = main(["report", RUN_ID, "--recon", "loan",
               "--runs-dir", str(seeded_run.run_dir.parent)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "reconciliation_loan.html" in out


def test_report_unknown_run_exits_1(tmp_path, capsys):
    rc = main(["report", "RUN-2026-01-01-0001", "--runs-dir", str(tmp_path)])
    assert rc == 1


def test_clean_pair_reports_green(tmp_path):
    result = run(
        PAIR,
        SAMPLES / "source" / "PLN-CLEAN-01",
        SAMPLES / "target" / "PLN-CLEAN-01",
        fingerprint_dir=STORE, runs_dir=tmp_path / "runs", run_id=RUN_ID,
    )
    html = (result.run_dir / "findings.html").read_text(encoding="utf-8")
    assert "GREEN" in html
    assert "No open exceptions" in html
    rc = main(["report", RUN_ID, "--recon", "plan",
               "--runs-dir", str(tmp_path / "runs")])
    assert rc == 0
    plan_html = (result.run_dir / "reconciliation_plan.html").read_text(
        encoding="utf-8")
    assert "RECONCILED" in plan_html
    assert "VARIANCE" not in plan_html