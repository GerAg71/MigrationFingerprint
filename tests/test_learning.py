"""MS-2.4 (spec Ch. 14): the §14.2 worked examples reproduce exactly, the
write-back is replayable from the learning-event log alone (REQ-027), and
published versions are immutable (REQ-028)."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.fingerprint.loader import load
from src.learning.versioning import (
    PublishError,
    author_failure_mode,
    diff_versions,
    next_fm_id,
    publish_draft,
)
from src.learning.writeback import (
    ReviewError,
    apply_review,
    compute_probability,
    draft_path,
    load_or_create_draft,
    read_events,
    replay_events,
)
from src.runner.run import run
from tests.conftest import REPO, copy_fingerprint_store

SAMPLES = REPO / "data" / "samples"
PAIR = "omni-zos-to-omni-linux"


def seeded_run(store: Path, tmp_path: Path, sequence: int = 1):
    run_id = f"RUN-2026-07-05-{sequence:04d}"
    return run(
        PAIR,
        SAMPLES / "source" / "PLN-SEED-01",
        SAMPLES / "target" / "PLN-SEED-01",
        fingerprint_dir=store, runs_dir=tmp_path / "runs", run_id=run_id,
    )


def finding_for(result, rule_id: str) -> str:
    return next(f.finding_id for f in result.findings if f.rule_id == rule_id)


# --- §14.2 worked examples, exactly ------------------------------------------


def test_worked_example_fm004_three_confirmations():
    """FM-004 seeded at 0.50: 3 confirmed, 0 FP -> (5+3)/13 = 0.615."""
    assert compute_probability(Decimal("0.50"), 3, 0) == Decimal("0.615")


def test_worked_example_fm001_mixed_evidence():
    """FM-001 seeded at 0.70: 2 confirmed, 1 FP -> (7+2)/13 = 0.692."""
    assert compute_probability(Decimal("0.70"), 2, 1) == Decimal("0.692")


def test_worked_example_fm016_noisy_check_sinks():
    """FM-016 seeded at 0.50: 0 confirmed, 4 FP -> 5/14 = 0.357."""
    assert compute_probability(Decimal("0.50"), 0, 4) == Decimal("0.357")


def test_clamp_bounds():
    assert compute_probability(Decimal("0.05"), 0, 200) == Decimal("0.05")
    assert compute_probability(Decimal("0.99"), 500, 0) == Decimal("0.99")


# --- review write-back --------------------------------------------------------


def test_apply_review_updates_draft_counters_and_probability(tmp_path):
    store = copy_fingerprint_store(tmp_path)
    result = seeded_run(store, tmp_path)
    finding_id = finding_for(result, "RULE-LOAN-BAL-001")  # FM-001, seed 0.70

    outcome = apply_review(finding_id, "confirmed", reviewer="jsmith",
                           comment="ticket CONV-214",
                           runs_dir=tmp_path / "runs", fingerprint_dir=store)
    event = outcome.event
    assert event.fm_id == "FM-001"
    assert event.counters_before.times_confirmed == 0
    assert event.counters_after.times_confirmed == 1
    assert event.counters_after.times_detected == 1
    assert event.probability_before == 0.70
    assert event.probability_after == 0.727  # (7+1)/11
    assert event.formula_inputs == {
        "p_seed": "0.7", "k": "10",
        "confirmed_total": "1", "false_positive_total": "0",
    }

    draft = load_or_create_draft(PAIR, store)
    mode = next(m for m in draft.failure_modes if m.id == "FM-001")
    assert mode.probability == 0.727
    assert mode.seed_probability == 0.70  # prior pinned
    assert draft.status == "draft"
    assert draft.version == "1.0.1"


def test_false_positive_sinks_probability(tmp_path):
    store = copy_fingerprint_store(tmp_path)
    result = seeded_run(store, tmp_path)
    finding_id = finding_for(result, "RULE-LEN-001")  # FM-016, seed 0.50
    outcome = apply_review(finding_id, "false_positive",
                           runs_dir=tmp_path / "runs", fingerprint_dir=store)
    assert outcome.event.probability_after == 0.455  # 5/11


def test_review_updates_finding_status_and_is_immutable(tmp_path):
    store = copy_fingerprint_store(tmp_path)
    result = seeded_run(store, tmp_path)
    finding_id = finding_for(result, "RULE-DUP-001")
    apply_review(finding_id, "confirmed",
                 runs_dir=tmp_path / "runs", fingerprint_dir=store)

    payload = json.loads((result.run_dir / "findings.json")
                         .read_text(encoding="utf-8"))
    status = next(f["status"] for f in payload["findings"]
                  if f["finding_id"] == finding_id)
    assert status == "confirmed"
    assert (result.run_dir / "reviews.jsonl").is_file()

    with pytest.raises(ReviewError, match="immutable"):
        apply_review(finding_id, "false_positive",
                     runs_dir=tmp_path / "runs", fingerprint_dir=store)


def test_unknown_finding_raises(tmp_path):
    store = copy_fingerprint_store(tmp_path)
    result = seeded_run(store, tmp_path)
    with pytest.raises(ReviewError, match="not found"):
        apply_review(f"{result.run.run_id}-F999", "confirmed",
                     runs_dir=tmp_path / "runs", fingerprint_dir=store)


def test_cumulative_worked_example_end_to_end(tmp_path):
    """§14.2 FM-004 example driven through real runs: three confirmations of
    the provision-matrix finding across three runs -> 0.615."""
    store = copy_fingerprint_store(tmp_path)
    for sequence in (1, 2, 3):
        result = seeded_run(store, tmp_path, sequence)
        apply_review(finding_for(result, "RULE-PROV-MATRIX-001"), "confirmed",
                     runs_dir=tmp_path / "runs", fingerprint_dir=store)
    draft = load_or_create_draft(PAIR, store)
    fm004 = next(m for m in draft.failure_modes if m.id == "FM-004")
    assert fm004.probability == 0.615
    assert fm004.history.times_confirmed == 3


# --- replayability (REQ-027) ----------------------------------------------------


def test_writeback_replayable_from_event_log_alone(tmp_path):
    store = copy_fingerprint_store(tmp_path)
    result = seeded_run(store, tmp_path)
    for rule_id, decision in (
        ("RULE-LOAN-BAL-001", "confirmed"),
        ("RULE-DUP-001", "confirmed"),
        ("RULE-LEN-001", "false_positive"),
        ("RULE-CHAR-001", "false_positive"),  # second FM-016 adjudication
    ):
        apply_review(finding_for(result, rule_id), decision,
                     runs_dir=tmp_path / "runs", fingerprint_dir=store)

    base = load(PAIR, version="1.0.0", fingerprint_dir=store)
    replayed = replay_events(base, read_events(PAIR, store))
    draft = load_or_create_draft(PAIR, store)
    for fm_id, state in replayed.items():
        mode = next(m for m in draft.failure_modes if m.id == fm_id)
        assert state["probability"] == mode.probability, fm_id
        assert state["counters"] == mode.history, fm_id
    assert set(replayed) == {"FM-001", "FM-011", "FM-016"}
    # FM-016 saw two false positives: (5+0)/12 = 0.417
    assert replayed["FM-016"]["probability"] == 0.417


# --- versioning (spec §14.5–14.6, REQ-028) ----------------------------------------


def test_publish_patch_creates_immutable_new_version(tmp_path):
    store = copy_fingerprint_store(tmp_path)
    result = seeded_run(store, tmp_path)
    apply_review(finding_for(result, "RULE-LOAN-BAL-001"), "confirmed",
                 runs_dir=tmp_path / "runs", fingerprint_dir=store)

    published = publish_draft(PAIR, "patch", changelog="wave-1 write-backs",
                              fingerprint_dir=store)
    assert (published.old_version, published.new_version) == ("1.0.0", "1.0.1")
    changed = {e["fm_id"]: e for e in published.diff["modes_changed"]}
    assert changed["FM-001"]["probability"]["after"] == 0.727

    # the loader now serves 1.0.1; 1.0.0 stays loadable forever (REQ-028)
    assert load(PAIR, fingerprint_dir=store).version == "1.0.1"
    old = load(PAIR, version="1.0.0", fingerprint_dir=store)
    fm001 = next(m for m in old.failure_modes if m.id == "FM-001")
    assert fm001.probability == 0.70
    assert not draft_path(PAIR, store).exists()  # draft consumed

    with pytest.raises(PublishError, match="no draft"):
        publish_draft(PAIR, "patch", fingerprint_dir=store)


def test_diff_versions_reports_probability_delta(tmp_path):
    store = copy_fingerprint_store(tmp_path)
    result = seeded_run(store, tmp_path)
    apply_review(finding_for(result, "RULE-LEN-001"), "false_positive",
                 runs_dir=tmp_path / "runs", fingerprint_dir=store)
    publish_draft(PAIR, "patch", fingerprint_dir=store)
    diff = diff_versions(PAIR, "1.0.0", "1.0.1", store)
    assert diff["modes_added"] == [] and diff["modes_removed"] == []
    entry = next(e for e in diff["modes_changed"] if e["fm_id"] == "FM-016")
    assert entry["probability"] == {"before": 0.50, "after": 0.455,
                                    "delta": -0.045}


# --- authoring (spec §14.4) -------------------------------------------------------


def test_author_failure_mode_appends_to_draft_and_publishes_minor(tmp_path):
    store = copy_fingerprint_store(tmp_path)
    mode = author_failure_mode(
        PAIR,
        name="Beneficiary allocation drift",
        category="PARTICIPANT",
        description="Beneficiary percentages fail to total 100 after conversion.",
        data_domains=["PARTICIPANT"],
        impact=0.7,
        remediation="Re-normalize allocations; audit the beneficiary crosswalk.",
        rule_payload={
            "rule_id": "RULE-BENEF-001", "type": "field_compare",
            "target_dataset": "participants",
            "params": {"validity": [{"field": "ssn", "not_null": True}]},
            "severity": "MEDIUM",
        },
        fingerprint_dir=store,
    )
    assert mode.id == "FM-019"
    assert mode.probability == 0.30  # learned-mode default
    assert mode.origin == "learned"

    published = publish_draft(PAIR, "minor", fingerprint_dir=store)
    assert published.new_version == "1.1.0"
    assert published.diff["modes_added"] == ["FM-019"]
    assert published.diff["rules_added"] == ["RULE-BENEF-001"]
    latest = load(PAIR, fingerprint_dir=store)
    assert next(m for m in latest.failure_modes if m.id == "FM-019")


def test_next_fm_id(tmp_path):
    store = copy_fingerprint_store(tmp_path)
    assert next_fm_id(load(PAIR, fingerprint_dir=store)) == "FM-019"