"""field_compare executor (spec §11.2.1).

Serves FM-001 (loan balance carry-over), FM-002 (schedule id), FM-004
(provision matrix), FM-008 (date drift) via the compare block, and the
single-sided validity checks of FM-010/FM-014/FM-016/FM-017/FM-018.

compare: join source and target on join_keys and compare matched rows only —
unmatched keys are referential's job. Money compares by |target - source| >
tolerance in Decimal (default 0.00, REQ-004); text/date by equality; a null
on exactly one side is a mismatch.

validity: checks against the target dataset alone: not_null, max_length,
pattern, min, max (bounds are ISO dates, Decimal amounts, or "today" resolved
via ExecutionContext.as_of), and gte_field (cross-field: value must be >= the
named field's value).
"""

from __future__ import annotations

import re
from decimal import Decimal

from src.fingerprint.models import AffectedRecord, FieldCompareRule, ValidityCheck
from src.ingest.canonical import CANONICAL_DATASETS
from src.rules._common import (
    ExecutionContext,
    is_null,
    key_dict,
    parse_bound,
    sort_records,
    stringify,
)

DEFAULT_TOLERANCE = Decimal("0.00")


def _compare_values(source, target, tolerance: Decimal | None):
    """Returns (mismatch, delta). Decimal pairs use tolerance; everything
    else is strict equality. A single-sided null is always a mismatch."""
    if is_null(source) and is_null(target):
        return False, None
    if is_null(source) or is_null(target):
        return True, None
    if isinstance(source, Decimal) and isinstance(target, Decimal):
        delta = target - source
        limit = tolerance if tolerance is not None else DEFAULT_TOLERANCE
        return abs(delta) > limit, delta
    return source != target, None


def _violations(check: ValidityCheck, value, row: dict, context: ExecutionContext):
    found = []
    if check.not_null and (is_null(value) or value == ""):
        found.append("not_null")
    if is_null(value):
        return found
    if check.max_length is not None and len(str(value)) > check.max_length:
        found.append(f"max_length:{check.max_length}")
    if check.pattern is not None and not re.fullmatch(check.pattern, str(value)):
        found.append(f"pattern:{check.pattern}")
    if check.min is not None:
        bound = parse_bound(check.min, value, context.as_of)
        if type(bound) is type(value) or isinstance(value, type(bound)):
            if value < bound:
                found.append(f"min:{check.min}")
    if check.max is not None:
        bound = parse_bound(check.max, value, context.as_of)
        if type(bound) is type(value) or isinstance(value, type(bound)):
            if value > bound:
                found.append(f"max:{check.max}")
    if check.gte_field is not None:
        other = row.get(check.gte_field)
        if not is_null(other) and value < other:
            found.append(f"gte_field:{check.gte_field}")
    return found


def execute(rule: FieldCompareRule, datasets, context: ExecutionContext):
    affected: list[AffectedRecord] = []
    target_df = datasets.target[rule.target_dataset]

    if rule.params.compare:
        source_df = datasets.source[rule.source_dataset]
        join_keys = list(rule.join_keys)
        # rows with null join keys cannot be matched; referential owns orphans
        s = source_df.dropna(subset=join_keys)
        t = target_df.dropna(subset=join_keys)
        merged = s.merge(t, on=join_keys, how="inner", suffixes=("__src", "__tgt"))
        for row in merged.to_dict("records"):
            for compare in rule.params.compare:
                source_value = row.get(f"{compare.field}__src", row.get(compare.field))
                target_value = row.get(f"{compare.field}__tgt", row.get(compare.field))
                mismatch, delta = _compare_values(
                    source_value, target_value, compare.tolerance
                )
                if mismatch:
                    affected.append(AffectedRecord(
                        keys=key_dict(join_keys, row),
                        source={compare.field: stringify(source_value)},
                        target={compare.field: stringify(target_value)},
                        delta=delta,
                    ))

    if rule.params.validity:
        spec = CANONICAL_DATASETS.get(rule.target_dataset)
        key_columns = (
            [c.name for c in spec.columns if c.kind == "key"] if spec else []
        )
        for row in target_df.to_dict("records"):
            for check in rule.params.validity:
                value = row.get(check.field)
                for violation in _violations(check, value, row, context):
                    affected.append(AffectedRecord(
                        keys=key_dict(key_columns, row),
                        source=None,
                        target={
                            check.field: stringify(value),
                            "_check": violation,
                        },
                        delta=None,
                    ))

    return sort_records(affected), None
