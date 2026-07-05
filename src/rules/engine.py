"""Detection rule engine (MS-1.4; spec §11.1, §11.3–11.4).

Maps rule.type to an executor; executors are pure functions of
(rule, datasets, context) returning affected records plus optional detail —
no I/O, no clock, no randomness (REQ-009). Finding construction is uniform
here (§11.3): severity from the rule, remediation from the failure mode, up
to 25 inline sample records, records_affected and the drill-down URI set by
the engine. A rule that finds nothing yields a passed outcome the runner
reports explicitly — passes are never silent (REQ-024).

Extensibility contract (§11.4): a new rule type needs a params model
(models.py), an executor module registered in EXECUTORS below, a docstring
naming the failure modes it serves, unit tests, and a fixture that trips it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.fingerprint.models import (
    AffectedRecord,
    DetectionRule,
    Finding,
)
from src.ingest.registration import RegistrationIndex
from src.rules import count_balance, field_compare, referential
from src.rules._common import ExecutionContext

MAX_INLINE_SAMPLES = 25

EXECUTORS = {
    "field_compare": field_compare.execute,
    "count_balance": count_balance.execute,
    "referential": referential.execute,
    # derived_recompute, encoding_check, sort_order_check arrive in MS-2.1
}


class UnsupportedRuleTypeError(NotImplementedError):
    pass


@dataclass
class RuleDatasets:
    """Registered canonical datasets for one run, as DataFrames with
    Decimal-typed money columns (spec §11.1)."""

    source: dict[str, object] = field(default_factory=dict)
    target: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_index(cls, index: RegistrationIndex) -> "RuleDatasets":
        bundle = cls()
        for registration in index.registrations():
            ingested = index.get(registration.side, registration.dataset_name)
            frame = ingested.data.to_dataframe()
            getattr(bundle, registration.side)[registration.dataset_name] = frame
        return bundle


@dataclass(frozen=True)
class RuleOutcome:
    """Executor result for one rule: zero affected records = pass."""

    rule: DetectionRule
    affected: list[AffectedRecord]
    detail: dict | None = None

    @property
    def passed(self) -> bool:
        return not self.affected

    @property
    def records_affected(self) -> int:
        return len(self.affected)


def execute(
    rule: DetectionRule,
    datasets: RuleDatasets,
    context: ExecutionContext | None = None,
) -> RuleOutcome:
    """Run one rule against registered datasets. Raises
    UnsupportedRuleTypeError for types without an executor yet."""
    executor = EXECUTORS.get(rule.type)
    if executor is None:
        raise UnsupportedRuleTypeError(
            f"no executor for rule type {rule.type!r} "
            f"(rule {rule.rule_id}; derived_recompute/encoding_check/"
            f"sort_order_check land in MS-2.1)"
        )
    affected, detail = executor(rule, datasets, context or ExecutionContext())
    return RuleOutcome(rule=rule, affected=list(affected), detail=detail)


def build_finding(
    outcome: RuleOutcome,
    *,
    run_id: str,
    finding_id: str,
    remediation: str | None = None,
    full_detail_uri: str | None = None,
) -> Finding | None:
    """Uniform finding construction (§11.3). None when the rule passed —
    the runner records a pass entry instead (REQ-024)."""
    if outcome.passed:
        return None
    return Finding(
        finding_id=finding_id,
        run_id=run_id,
        failure_mode=outcome.rule.failure_mode,
        rule_id=outcome.rule.rule_id,
        severity=outcome.rule.severity,
        status="new",
        records_affected=outcome.records_affected,
        sample_records=outcome.affected[:MAX_INLINE_SAMPLES],
        full_detail_uri=full_detail_uri,
        remediation=remediation,
    )
