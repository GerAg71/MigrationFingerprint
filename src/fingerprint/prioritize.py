"""Suite prioritization (MS-1.2; spec §12.2, REQ-001).

priority_score = probability × impact, computed per failure mode and applied
to each of its rules. Ordering: score descending; ties broken by severity rank
(CRITICAL > HIGH > MEDIUM > LOW), then failure-mode ID ascending, then rule ID
ascending (the last tie-break keeps sibling rules of one mode deterministic).
Disabled rules stay in their priority position marked skipped:disabled.

Scores use Decimal arithmetic on the JSON literals (0.65 × 0.95 = 0.6175
exactly), so the same fingerprint always yields the same suite (REQ-009).
"""

from __future__ import annotations

from decimal import Decimal

from src.fingerprint.models import (
    FailureMode,
    Fingerprint,
    PrioritizedSuiteEntry,
)

SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def priority_score(failure_mode: FailureMode) -> Decimal:
    """Exact probability × impact via the shortest decimal repr of each score.

    normalize() strips insignificant trailing zeros (0.360 -> 0.36) so the
    serialized score is canonical whatever the inputs' printed precision.
    """
    product = Decimal(str(failure_mode.probability)) * Decimal(str(failure_mode.impact))
    return product.normalize()


def prioritized_suite(fingerprint: Fingerprint) -> list[PrioritizedSuiteEntry]:
    """The ordered validation suite for a fingerprint (spec §12.2)."""
    modes = {fm.id: fm for fm in fingerprint.failure_modes}
    keyed = []
    for rule in fingerprint.detection_rules:
        score = priority_score(modes[rule.failure_mode])
        keyed.append(
            ((-score, SEVERITY_RANK[rule.severity], rule.failure_mode, rule.rule_id),
             score, rule)
        )
    keyed.sort(key=lambda item: item[0])
    return [
        PrioritizedSuiteEntry(
            order=position,
            rule_id=rule.rule_id,
            fm_id=rule.failure_mode,
            priority_score=score,
            severity=rule.severity,
            source_dataset=rule.source_dataset,
            target_dataset=rule.target_dataset,
            status="pending" if rule.enabled else "skipped:disabled",
        )
        for position, (_, score, rule) in enumerate(keyed, start=1)
    ]
