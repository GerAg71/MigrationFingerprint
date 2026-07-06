"""Sign-off package assembly (spec §13.4): contents, §2.6 metrics vs
targets, closure evidence, AI-narrative labeling, and deterministic zips."""

import io
import json
import zipfile
from datetime import datetime, timezone

import pytest

from src.learning.workflow import assign, close, resolve
from src.learning.writeback import apply_review
from src.report.signoff import build_signoff_package
from src.runner.run import run
from tests.conftest import REPO, copy_fingerprint_store

SAMPLES = REPO / "data" / "samples"
PAIR = "omni-zos-to-omni-linux"
RUN_ID = "RUN-2026-07-06-0001"
NOW = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)

EXPECTED_ENTRIES = {
    "certification.html", "exception_register.html", "findings.html",
    "manifest.json",
    "reconciliation_plan.html", "reconciliation_participant.html",
    "reconciliation_loan.html", "reconciliation_contribution.html",
    "reconciliation_quality.html",
}


def run_pair(tmp_path, plan: str):
    store = copy_fingerprint_store(tmp_path)
    result = run(PAIR, SAMPLES / "source" / plan, SAMPLES / "target" / plan,
                 fingerprint_dir=store, runs_dir=tmp_path / "runs",
                 run_id=RUN_ID)
    return store, result


@pytest.fixture()
def adjudicated(tmp_path):
    """Seeded run with one exception worked to closure and one FP."""
    store, result = run_pair(tmp_path, "PLN-SEED-01")
    runs_dir = tmp_path / "runs"
    loan = next(f.finding_id for f in result.findings
                if f.rule_id == "RULE-LOAN-BAL-001")
    dup = next(f.finding_id for f in result.findings
               if f.rule_id == "RULE-DUP-001")
    assign(loan, "jsmith", runs_dir=runs_dir, now=NOW)
    apply_review(loan, "confirmed", runs_dir=runs_dir, fingerprint_dir=store)
    resolve(loan, "remapped payment order", runs_dir=runs_dir, now=NOW)
    close(loan, "re-run clean", runs_dir=runs_dir, now=NOW)
    apply_review(dup, "false_positive", runs_dir=runs_dir,
                 fingerprint_dir=store)
    return tmp_path, store


def read_zip(path) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(path.read_bytes())) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_package_contents_and_manifest(adjudicated):
    tmp_path, store = adjudicated
    result = build_signoff_package(RUN_ID, runs_dir=tmp_path / "runs",
                                   fingerprint_dir=store, now=NOW)
    assert result.package_path.name == f"PKG-{RUN_ID}.zip"
    entries = read_zip(result.package_path)
    assert EXPECTED_ENTRIES <= set(entries)
    # audit extract present: workflow, reviews, and the run's learning events
    assert "audit/workflow.jsonl" in entries
    assert "audit/reviews.jsonl" in entries
    assert "audit/learning_events.jsonl" in entries

    manifest = json.loads(entries["manifest.json"])
    assert manifest["package_id"] == f"PKG-{RUN_ID}"
    assert manifest["fingerprint_version"] == "1.0.0"
    assert manifest["dataset_hashes"]  # REQ-014
    import hashlib
    for name, digest in manifest["files"].items():
        assert digest == "sha256:" + hashlib.sha256(entries[name]).hexdigest()


def test_certification_page_content(adjudicated):
    tmp_path, store = adjudicated
    result = build_signoff_package(RUN_ID, runs_dir=tmp_path / "runs",
                                   fingerprint_dir=store, now=NOW)
    html = read_zip(result.package_path)["certification.html"].decode("utf-8")
    # §2.6 metrics vs targets
    assert "Participant records converted" in html and "MET" in html
    assert "NOT MET" in html  # seeded balances do not reconcile
    # AI narrative labeled with provider + review requirement (§8.4, §20.4)
    assert "AI-generated (stub provider" in html
    # dual sign-off lines (§15.3)
    assert "IT — conversion lead" in html
    assert "Business — plan operations" in html
    # narrative figures verbatim from the scoreboard
    assert str(21) in html  # failed rules count appears in narrative


def test_register_carries_closure_evidence(adjudicated):
    tmp_path, store = adjudicated
    result = build_signoff_package(RUN_ID, runs_dir=tmp_path / "runs",
                                   fingerprint_dir=store, now=NOW)
    html = read_zip(result.package_path)["exception_register.html"] \
        .decode("utf-8")
    assert "remapped payment order" in html
    assert "re-run clean" in html
    assert "jsmith" in html
    # metrics reflect 19 open of 20 exceptions (FP excluded)
    manifest = json.loads(read_zip(result.package_path)["manifest.json"])
    unresolved = next(m for m in manifest["metrics"]
                      if "Unresolved" in m["metric"])
    assert "19 open" in unresolved["actual"]
    assert unresolved["status"] == "NOT MET"


def test_clean_run_metrics_all_met(tmp_path):
    store, _ = run_pair(tmp_path, "PLN-CLEAN-01")
    result = build_signoff_package(RUN_ID, runs_dir=tmp_path / "runs",
                                   fingerprint_dir=store, now=NOW)
    assert all(m["status"] == "MET" for m in result.manifest["metrics"])
    html = read_zip(result.package_path)["certification.html"].decode("utf-8")
    assert "NOT MET" not in html
    assert "sign-off" in html  # green-run recommendation


def test_analyst_narrative_override(adjudicated):
    tmp_path, store = adjudicated
    result = build_signoff_package(
        RUN_ID, runs_dir=tmp_path / "runs", fingerprint_dir=store,
        narrative="Wave 1 validated; loan carry-over remediated and re-run clean.",
        approved_by="j.smith (conversion lead)", now=NOW)
    html = read_zip(result.package_path)["certification.html"].decode("utf-8")
    assert "analyst-provided" in html
    assert "Wave 1 validated" in html
    assert "j.smith (conversion lead)" in html
    assert "AI-generated" not in html


def test_package_is_deterministic(adjudicated):
    tmp_path, store = adjudicated
    first = build_signoff_package(RUN_ID, runs_dir=tmp_path / "runs",
                                  fingerprint_dir=store, now=NOW)
    first_bytes = first.package_path.read_bytes()
    second = build_signoff_package(RUN_ID, runs_dir=tmp_path / "runs",
                                   fingerprint_dir=store, now=NOW)
    assert first_bytes == second.package_path.read_bytes()


def test_cli_signoff(adjudicated, capsys):
    from src.cli import main

    tmp_path, store = adjudicated
    rc = main(["signoff", RUN_ID, "--runs-dir", str(tmp_path / "runs"),
               "--fingerprint-dir", str(store)])
    out = capsys.readouterr().out
    assert rc == 0
    assert f"PKG-{RUN_ID}.zip" in out
    assert "AI-generated" in out
    assert "[MET" in out and "[NOT MET]" in out


def test_api_signoff(adjudicated):
    from fastapi.testclient import TestClient
    from src.api.app import create_app

    tmp_path, store = adjudicated
    client = TestClient(create_app(fingerprint_dir=store,
                                   runs_dir=tmp_path / "runs"),
                        raise_server_exceptions=False)
    response = client.post("/reports/sign-off-package",
                           json={"run_id": RUN_ID})
    assert response.status_code == 200
    payload = response.json()
    assert payload["manifest"]["package_id"] == f"PKG-{RUN_ID}"

    missing = client.post("/reports/sign-off-package", json={})
    assert missing.status_code == 422
    unknown = client.post("/reports/sign-off-package",
                          json={"run_id": "RUN-2026-01-01-0001"})
    assert unknown.status_code == 404