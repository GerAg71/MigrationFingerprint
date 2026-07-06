"""derived_recompute executor (spec §11.2.4).

Serves FM-002 (vested_pct: recompute vested % from the canonical schedule +
service and compare per participant) and FM-001 (loan_balance: re-amortize
from origination — level payments, payment history applied in the configured
order, Decimal throughout, half-even rounding per period). The
packed_decode_control_total recomputer (FM-006) needs the EBCDIC decode layer
and lands with MS-2.2; until then those rules execute as skipped.

Inputs convention (params.inputs): a dotted value ("loans.rate",
"plan.provisions.vesting") names a field/provision; an undotted value naming
a canonical dataset ("loan_payments") is a dataset dependency, registered on
the source side and enforced by the REQ-021 gate.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

from src.fingerprint.models import AffectedRecord, DerivedRecomputeRule
from src.rules._common import (
    ExecutionContext,
    UnsupportedRuleTypeError,
    is_null,
    key_dict,
    sort_records,
    stringify,
)

CENT = Decimal("0.01")
DEFAULT_PAYMENTS_DATASET = "loan_payments"

# Canonical vesting schedules (validation-scoped domain knowledge, like
# src/ingest/canonical.py). GRADED6: 0% before 2 years of service, then 20%
# per completed year to 100% at 6. CLIFF3: 0% before 3 years, then 100%.
VESTING_SCHEDULES = {
    "GRADED6": lambda years: (
        Decimal("0") if years < 2
        else min((int(years) - 1) * Decimal("0.2"), Decimal("1"))
    ),
    "CLIFF3": lambda years: Decimal("1") if years >= 3 else Decimal("0"),
}


def vested_pct(schedule_id: str, service_years: Decimal) -> Decimal:
    schedule = VESTING_SCHEDULES.get(schedule_id)
    if schedule is None:
        raise ValueError(f"unknown vesting schedule {schedule_id!r}")
    return schedule(service_years)


def amortize_balance(
    origination: Decimal,
    annual_rate: Decimal,
    payment_totals: list[Decimal],
    application_order: str = "interest_first",
) -> Decimal:
    """Outstanding balance after applying the payment history in order.
    Interest accrues monthly, rounded half-even per period (spec §11.2.4)."""
    balance = origination
    monthly = annual_rate / Decimal("12")
    for total in payment_totals:
        interest_due = (balance * monthly).quantize(CENT, ROUND_HALF_EVEN)
        if application_order == "interest_first":
            principal = total - min(interest_due, total)
        elif application_order == "principal_first":
            principal = min(total, balance)
        else:
            raise ValueError(f"unknown application_order {application_order!r}")
        balance -= principal
    return balance.quantize(CENT, ROUND_HALF_EVEN)


def simulate_level_payments(
    origination: Decimal,
    annual_rate: Decimal,
    payment_amount: Decimal,
    count: int,
) -> tuple[list[tuple[Decimal, Decimal]], Decimal]:
    """(principal, interest) split per period plus the final balance, using
    interest-first application — the generator's counterpart to
    amortize_balance, so synthetic truth is amortization-consistent."""
    balance = origination
    monthly = annual_rate / Decimal("12")
    schedule: list[tuple[Decimal, Decimal]] = []
    for _ in range(count):
        interest = (balance * monthly).quantize(CENT, ROUND_HALF_EVEN)
        principal = payment_amount - interest
        balance -= principal
        schedule.append((principal, interest))
    return schedule, balance.quantize(CENT, ROUND_HALF_EVEN)


def _merged(rule, datasets):
    join_keys = list(rule.join_keys)
    source = datasets.source[rule.source_dataset].dropna(subset=join_keys)
    target = datasets.target[rule.target_dataset].dropna(subset=join_keys)
    return join_keys, source.merge(target, on=join_keys, how="inner",
                                   suffixes=("__src", "__tgt"))


def _tolerance(rule) -> Decimal:
    return rule.params.tolerance if rule.params.tolerance is not None else CENT * 0


def _record(join_keys, row, field, expected, actual):
    return AffectedRecord(
        keys=key_dict(join_keys, row),
        source={f"{field}_recomputed": stringify(expected)},
        target={field: stringify(actual)},
        delta=None if is_null(actual) else actual - expected,
    )


def _vested(rule, datasets):
    join_keys, merged = _merged(rule, datasets)
    field = rule.params.compare_field
    tolerance = _tolerance(rule)
    affected = []
    for row in merged.to_dict("records"):
        schedule_id = row.get("schedule_id__src", row.get("schedule_id"))
        service = row.get("service_years__src", row.get("service_years"))
        if is_null(schedule_id) or is_null(service):
            continue  # missing inputs are validity rules' findings, not ours
        expected = vested_pct(str(schedule_id), service)
        actual = row.get(f"{field}__tgt", row.get(field))
        if is_null(actual) or abs(actual - expected) > tolerance:
            affected.append(_record(join_keys, row, field, expected, actual))
    return sort_records(affected), None


def _loan(rule, datasets, context):
    payments_name = rule.params.inputs.get("payments", DEFAULT_PAYMENTS_DATASET)
    if payments_name not in datasets.source:
        raise ValueError(
            f"loan_balance recompute needs dataset {payments_name!r} "
            f"registered on the source side (REQ-021)"
        )
    order = rule.params.inputs.get("application_order", "interest_first")
    join_keys, merged = _merged(rule, datasets)
    field = rule.params.compare_field
    tolerance = _tolerance(rule)

    payments_by_key: dict[tuple, list] = {}
    for row in datasets.source[payments_name].to_dict("records"):
        key = tuple(stringify(row.get(k)) for k in join_keys)
        if any(v is None for v in key):
            continue
        payments_by_key.setdefault(key, []).append(row)

    affected = []
    for row in merged.to_dict("records"):
        origination = row.get("origination_amount__src", row.get("origination_amount"))
        rate = row.get("rate__src", row.get("rate"))
        if is_null(origination) or is_null(rate):
            continue  # missing loan terms belong to validity rules (FM-014)
        key = tuple(stringify(row.get(k)) for k in join_keys)
        rows = sorted(
            payments_by_key.get(key, []),
            key=lambda p: (stringify(p.get("payment_date")) or "",
                           stringify(p.get("principal")) or ""),
        )
        totals = [
            (p.get("principal") or Decimal("0")) + (p.get("interest") or Decimal("0"))
            for p in rows
            if not (is_null(p.get("principal")) and is_null(p.get("interest")))
        ]
        expected = amortize_balance(origination, rate, totals, order)
        actual = row.get(f"{field}__tgt", row.get(field))
        if is_null(actual) or abs(actual - expected) > tolerance:
            affected.append(_record(join_keys, row, field, expected, actual))
    return sort_records(affected), None


def execute(rule: DerivedRecomputeRule, datasets, context: ExecutionContext):
    recompute = rule.params.recompute
    if recompute == "vested_pct":
        return _vested(rule, datasets)
    if recompute == "loan_balance":
        return _loan(rule, datasets, context)
    raise UnsupportedRuleTypeError(
        f"recomputer {recompute!r} not implemented "
        f"(packed_decode_control_total lands with the EBCDIC layer in MS-2.2)"
    )
