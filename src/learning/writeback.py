"""Probability write-back (MS-2.4; spec §14.1–14.3, REQ-002, REQ-027).

The §14.2 Beta-prior nudge, quantized to 3 decimal places:

    k = 10;  alpha0 = p_seed * k
    p_new = (alpha0 + confirmed_total) / (k + confirmed_total + fp_total)
    clamped to [0.05, 0.99]

p_seed is the mode's SEED prior, pinned into seed_probability when the mode
first enters a draft — probabilities always recompute from prior + cumulative
counters, never iteratively, which is what makes the write-back replayable
from the learning-event log alone (REQ-027).

POC policy (CLI_SPEC): write-backs accumulate in a draft version at
data/fingerprints/<pair>/draft/; publish (versioning.py) finalizes. Counter
semantics (POC simplification, §14.3): every adjudicated finding counts one
detection, so times_detected == times_confirmed + false_positives.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from src.fingerprint.loader import DEFAULT_FINGERPRINT_DIR, load, load_file
from src.fingerprint.models import (
    FailureModeHistory,
    FindingReview,
    Fingerprint,
    FindingsReport,
    LearningEvent,
)
from src.runner.run import DEFAULT_RUNS_DIR

K = 10
CLAMP_LOW = Decimal("0.05")
CLAMP_HIGH = Decimal("0.99")
_QUANTUM = Decimal("0.001")

DRAFT_DIRNAME = "draft"
EVENTS_FILENAME = "learning_events.jsonl"


class ReviewError(Exception):
    """Invalid review: unknown finding, or one already adjudicated
    (reviews are immutable, spec §14.1)."""


def compute_probability(p_seed: Decimal, confirmed_total: int,
                        false_positive_total: int) -> Decimal:
    """The §14.2 formula, exactly. Worked examples: (0.50, 3, 0) -> 0.615;
    (0.70, 2, 1) -> 0.692; (0.50, 0, 4) -> 0.357."""
    alpha0 = p_seed * K
    p_new = (alpha0 + confirmed_total) / (
        K + confirmed_total + false_positive_total)
    p_new = min(max(p_new, CLAMP_LOW), CLAMP_HIGH)
    return p_new.quantize(_QUANTUM, ROUND_HALF_EVEN)


def _dump_json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n").encode("utf-8")


def bump_version(version: str, bump: str) -> str:
    major, minor, patch = (int(p) for p in version.split("."))
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "major":
        return f"{major + 1}.0.0"
    raise ValueError(f"unknown bump {bump!r}")


def draft_path(pair_id: str, fingerprint_dir: Path | str) -> Path:
    return Path(fingerprint_dir) / pair_id / DRAFT_DIRNAME / "fingerprint.json"


def events_path(pair_id: str, fingerprint_dir: Path | str) -> Path:
    return Path(fingerprint_dir) / pair_id / EVENTS_FILENAME


def load_or_create_draft(
    pair_id: str, fingerprint_dir: Path | str = DEFAULT_FINGERPRINT_DIR
) -> Fingerprint:
    """The pair's accumulating draft; created from the latest published
    version on first use, with every mode's seed prior pinned (§14.2)."""
    path = draft_path(pair_id, fingerprint_dir)
    if path.is_file():
        return load_file(path)
    base = load(pair_id, fingerprint_dir=fingerprint_dir)
    draft = base.model_copy(deep=True)
    draft.status = "draft"
    draft.version = bump_version(base.version, "patch")
    draft.changelog = f"draft from {base.version}: pending publish"
    for mode in draft.failure_modes:
        if mode.seed_probability is None:
            mode.seed_probability = mode.probability
    return draft


def save_draft(draft: Fingerprint, pair_id: str,
               fingerprint_dir: Path | str) -> Path:
    path = draft_path(pair_id, fingerprint_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_dump_json_bytes(draft.model_dump(mode="json")))
    return path


@dataclass
class ReviewOutcome:
    review: FindingReview
    event: LearningEvent
    draft: Fingerprint


def apply_review(
    finding_id: str,
    decision: str,
    *,
    reviewer: str = "analyst",
    comment: str | None = None,
    runs_dir: Path | str = DEFAULT_RUNS_DIR,
    fingerprint_dir: Path | str = DEFAULT_FINGERPRINT_DIR,
    now: datetime | None = None,
) -> ReviewOutcome:
    """Record one review and apply its write-back (spec §14.1–14.2):
    update the finding's status in the run's findings.json, mutate the
    pair's draft fingerprint, and append the learning event (REQ-002)."""
    run_id = finding_id.rsplit("-F", 1)[0]
    run_dir = Path(runs_dir) / run_id
    findings_path = run_dir / "findings.json"
    if not findings_path.is_file():
        raise ReviewError(f"no findings report for run {run_id!r} at {findings_path}")
    report = FindingsReport.model_validate(
        json.loads(findings_path.read_text(encoding="utf-8")))
    finding = next((f for f in report.findings if f.finding_id == finding_id),
                   None)
    if finding is None:
        raise ReviewError(f"finding {finding_id!r} not found in run {run_id}")
    if finding.status not in ("new", "in_review"):
        raise ReviewError(
            f"finding {finding_id} already adjudicated ({finding.status}); "
            f"reviews are immutable (spec §14.1) — correct by counter-review "
            f"on a later run"
        )

    pair_id = report.run.pair_id
    draft = load_or_create_draft(pair_id, fingerprint_dir)
    mode = next(m for m in draft.failure_modes if m.id == finding.failure_mode)

    counters_before = mode.history.model_copy()
    probability_before = mode.probability
    mode.history.times_detected += 1
    if decision == "confirmed":
        mode.history.times_confirmed += 1
    else:
        mode.history.false_positives += 1

    p_seed = Decimal(str(mode.seed_probability))
    p_new = compute_probability(
        p_seed, mode.history.times_confirmed, mode.history.false_positives)
    mode.probability = float(p_new)

    created_at = now or datetime.now(timezone.utc)
    review = FindingReview(
        finding_id=finding_id, run_id=run_id, decision=decision,
        reviewer=reviewer, comment=comment, created_at=created_at,
    )
    event = LearningEvent(
        pair_id=pair_id, fm_id=mode.id, finding_id=finding_id, run_id=run_id,
        decision=decision, reviewer=reviewer,
        counters_before=counters_before, counters_after=mode.history.model_copy(),
        probability_before=probability_before, probability_after=mode.probability,
        formula_inputs={
            "p_seed": str(p_seed), "k": str(K),
            "confirmed_total": str(mode.history.times_confirmed),
            "false_positive_total": str(mode.history.false_positives),
        },
        draft_version=draft.version, created_at=created_at,
    )

    save_draft(draft, pair_id, fingerprint_dir)
    with events_path(pair_id, fingerprint_dir).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event.model_dump(mode="json"), sort_keys=True) + "\n")
    with (run_dir / "reviews.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(review.model_dump(mode="json"), sort_keys=True) + "\n")

    finding.status = decision
    findings_path.write_bytes(_dump_json_bytes(report.model_dump(mode="json")))
    return ReviewOutcome(review=review, event=event, draft=draft)


def read_events(pair_id: str,
                fingerprint_dir: Path | str = DEFAULT_FINGERPRINT_DIR
                ) -> list[LearningEvent]:
    path = events_path(pair_id, fingerprint_dir)
    if not path.is_file():
        return []
    return [
        LearningEvent.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def replay_events(base: Fingerprint, events: list[LearningEvent]) -> dict:
    """Recompute per-mode counters and probabilities from the base published
    fingerprint plus the event log alone (REQ-027). Returns
    {fm_id: {counters, probability}} for every mode an event touched."""
    state: dict[str, dict] = {}
    for event in events:
        if event.fm_id not in state:
            mode = next(m for m in base.failure_modes if m.id == event.fm_id)
            state[event.fm_id] = {
                "p_seed": Decimal(str(mode.seed_probability
                                      if mode.seed_probability is not None
                                      else mode.probability)),
                "counters": FailureModeHistory(**mode.history.model_dump()),
            }
        entry = state[event.fm_id]
        entry["counters"].times_detected += 1
        if event.decision == "confirmed":
            entry["counters"].times_confirmed += 1
        else:
            entry["counters"].false_positives += 1
        entry["probability"] = float(compute_probability(
            entry["p_seed"], entry["counters"].times_confirmed,
            entry["counters"].false_positives))
    return {
        fm_id: {"counters": entry["counters"], "probability": entry["probability"]}
        for fm_id, entry in state.items()
    }
