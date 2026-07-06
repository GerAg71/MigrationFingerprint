"""Exception workflow (spec Ch. 15, REQ-020): the full triage lifecycle,
invalid transitions refused, the audit trail, and the §13.3 register."""

import json
from datetime import datetime, timezone

import pytest

from src.learning.workflow import (
    WorkflowError,
    assign,
    close,
    comment,
    exception_register,
    history,
    resolve,
)
from src.learning.writeback import apply_review
from src.runner.run import run
from tests.conftest import REPO, copy_fingerprint_store

SAMPLES = REPO / "data" / "samples"
PAIR = "omni-zos-to-omni-linux"
RUN_ID = "RUN-2026-07-06-0001"
NOW = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def seeded(tmp_path):
    store = copy_fingerprint_store(tmp_path)
    result = run(
        PAIR, SAMPLES / "source" / "PLN-SEED-01",
        SAMPLES / "target" / "PLN-SEED-01",
        fingerprint_dir=store, runs_dir=tmp_path / "runs", run_id=RUN_ID,
    )
    return tmp_path, store, result


def finding_for(result, rule_id):
    return next(f.finding_id for f in result.findings if f.rule_id == rule_id)


def current_status(tmp_path, finding_id):
    payload = json.loads((tmp_path / "runs" / RUN_ID / "findings.json")
                         .read_text(encoding="utf-8"))
    finding = next(f for f in payload["findings"]
                   if f["finding_id"] == finding_id)
    return finding["status"], finding.get("assignee")


def test_full_lifecycle_new_to_closed(seeded):
    """new -> in_review (assign) -> confirmed (review) -> remediated
    (resolve) -> closed with evidence (spec §15.1)."""
    tmp_path, store, result = seeded
    fid = finding_for(result, "RULE-LOAN-BAL-001")
    runs_dir = tmp_path / "runs"

    event = assign(fid, "jsmith", actor="lead", comment="take this one",
                   runs_dir=runs_dir, now=NOW)
    assert (event.from_status, event.to_status) == ("new", "in_review")
    assert current_status(tmp_path, fid) == ("in_review", "jsmith")

    comment(fid, "payment order confirmed against source ledger",
            actor="jsmith", runs_dir=runs_dir, now=NOW)

    apply_review(fid, "confirmed", reviewer="jsmith",
                 runs_dir=runs_dir, fingerprint_dir=store)
    assert current_status(tmp_path, fid)[0] == "confirmed"

    resolve(fid, "remapped payment application order; ticket CONV-214",
            actor="jsmith", runs_dir=runs_dir, now=NOW)
    assert current_status(tmp_path, fid)[0] == "remediated"

    close(fid, "re-run RUN-2026-07-06-0002 clean", actor="lead",
          runs_dir=runs_dir, now=NOW)
    assert current_status(tmp_path, fid)[0] == "closed"

    # full audit trail, review included (REQ-020, §15.2)
    actions = [(e.action, e.to_status) for e in history(fid, runs_dir)]
    assert actions == [
        ("assign", "in_review"), ("comment", None),
        ("transition", "confirmed"), ("transition", "remediated"),
        ("transition", "closed"),
    ]


def test_invalid_transitions_refused(seeded):
    tmp_path, store, result = seeded
    fid = finding_for(result, "RULE-DUP-001")
    runs_dir = tmp_path / "runs"

    with pytest.raises(WorkflowError, match="requires 'confirmed'"):
        resolve(fid, "too early", runs_dir=runs_dir)   # still new
    with pytest.raises(WorkflowError, match="requires 'remediated'"):
        close(fid, "too early", runs_dir=runs_dir)

    apply_review(fid, "false_positive", runs_dir=runs_dir,
                 fingerprint_dir=store)
    with pytest.raises(WorkflowError, match="terminal"):
        assign(fid, "jsmith", runs_dir=runs_dir)       # false_positive is terminal
    with pytest.raises(WorkflowError, match="not found"):
        assign(f"{RUN_ID}-F999", "jsmith", runs_dir=runs_dir)


def test_transitions_require_notes(seeded):
    tmp_path, store, result = seeded
    fid = finding_for(result, "RULE-LEN-001")
    apply_review(fid, "confirmed", runs_dir=tmp_path / "runs",
                 fingerprint_dir=store)
    with pytest.raises(WorkflowError, match="requires a note"):
        resolve(fid, "", runs_dir=tmp_path / "runs")


def test_exception_register_tracks_to_closure(seeded):
    tmp_path, store, result = seeded
    runs_dir = tmp_path / "runs"
    loan = finding_for(result, "RULE-LOAN-BAL-001")
    dup = finding_for(result, "RULE-DUP-001")

    assign(loan, "jsmith", runs_dir=runs_dir, now=NOW)
    apply_review(loan, "confirmed", runs_dir=runs_dir, fingerprint_dir=store)
    resolve(loan, "remapped order", runs_dir=runs_dir, now=NOW)
    close(loan, "re-run clean", runs_dir=runs_dir, now=NOW)
    apply_review(dup, "false_positive", runs_dir=runs_dir,
                 fingerprint_dir=store)

    register = exception_register(RUN_ID, runs_dir)
    by_id = {row["exception"]: row for row in register}
    # false positives are not exceptions (§13.3)
    assert dup not in by_id
    assert len(register) == 20  # 21 findings - 1 false positive

    closed = by_id[loan]
    assert closed["status"] == "closed"
    assert closed["owner"] == "jsmith"
    assert closed["opened"] == "2026-07-06"
    assert closed["closed"] == "2026-07-06"
    assert "remapped order" in closed["resolution"]
    assert "re-run clean" in closed["resolution"]
    assert closed["plan"] == "PLN-SEED-01"

    still_open = [row for row in register if row["status"] != "closed"]
    assert len(still_open) == 19