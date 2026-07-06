"""Shared helpers for rule executors (MS-1.4).

Executors are pure functions of (rule, datasets, context) — no I/O, clock, or
randomness (REQ-009); anything environmental (the run's as-of date, a loaded
mapping manifest) arrives via ExecutionContext.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

NULL_DISPLAY = "(null)"


class UnsupportedRuleTypeError(NotImplementedError):
    """No executor (or recomputer) implemented for this rule yet — the
    runner records the rule as skipped rather than failing the run."""


@dataclass(frozen=True)
class ExecutionContext:
    """Deterministic run-level inputs to executors.

    as_of — resolves validity bounds of "today" (RULE-DATEVAL-001); the runner
    sets it from run metadata so re-runs reproduce (REQ-009).
    mapped_target_fields — target fields with mapping-rule provenance, loaded
    from the mapping manifest at the run layer (referential
    unmapped_target_fields params, FM-003).
    """

    as_of: date | None = None
    mapped_target_fields: frozenset[str] | None = None


def is_null(value: object) -> bool:
    """None, or the float NaN pandas may introduce for missing cells."""
    if value is None:
        return True
    return isinstance(value, float) and value != value


def stringify(value: object) -> str | None:
    if is_null(value):
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def display(value: object) -> str:
    return NULL_DISPLAY if is_null(value) else str(stringify(value))


def key_dict(columns: list[str], row: dict) -> dict[str, str]:
    return {c: display(row.get(c)) for c in columns}


def parse_bound(bound: str, sample_value: object, as_of: date | None) -> object:
    """Interpret a validity min/max bound against the value's type: "today"
    (max only, resolved via context), an ISO date, or a Decimal amount."""
    if bound == "today":
        if as_of is None:
            raise ValueError(
                'validity bound "today" requires ExecutionContext.as_of '
                "(set from run metadata; REQ-009 forbids clocks in executors)"
            )
        return as_of
    if isinstance(sample_value, date):
        return date.fromisoformat(bound)
    if isinstance(sample_value, Decimal):
        return Decimal(bound)
    # untyped (text) values: try date, then Decimal, else string compare
    try:
        return date.fromisoformat(bound)
    except ValueError:
        pass
    try:
        return Decimal(bound)
    except InvalidOperation:
        return bound


def sort_records(records: list) -> list:
    """Deterministic record ordering: by keys, then record content (REQ-009)."""
    return sorted(
        records,
        key=lambda r: (
            tuple(sorted(r.keys.items())),
            str(r.source),
            str(r.target),
        ),
    )
