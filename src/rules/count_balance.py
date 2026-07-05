"""count_balance executor (spec §11.2.2).

Serves FM-007 (master reconciliation), FM-009 (counts by status), FM-012/013
(money-type / investment subtotals), FM-014 (loan counts), FM-015
(contribution totals).

Aggregates sum/count per grouping level and requires exact equality — sums in
Decimal, counts exact integers. Levels execute coarsest first; a variance at
a coarse level automatically attaches the finer-level contributing breakdown
(the FM-007 "drill down behind any variance" behavior) in the outcome detail.

The optional filter param restricts rows by column equality; the symbolic
value "last_payroll_cycle" resolves to the maximum value of that column
present across both sides — data-driven, so re-runs reproduce (REQ-009).
"""

from __future__ import annotations

from decimal import Decimal

from src.fingerprint.models import AffectedRecord, Aggregation, CountBalanceRule
from src.rules._common import ExecutionContext, display, is_null

LAST_PAYROLL_CYCLE = "last_payroll_cycle"


def _resolve_filter(filt: dict[str, str], source_rows, target_rows) -> dict[str, str]:
    resolved = {}
    for column, value in filt.items():
        if value == LAST_PAYROLL_CYCLE:
            candidates = [
                row[column]
                for rows in (source_rows, target_rows)
                for row in rows
                if not is_null(row.get(column))
            ]
            if not candidates:
                raise ValueError(
                    f"filter {column}={LAST_PAYROLL_CYCLE!r}: no non-null "
                    f"{column!r} values on either side"
                )
            resolved[column] = max(str(c) for c in candidates)
        else:
            resolved[column] = value
    return resolved


def _apply_filter(rows, filt: dict[str, str]):
    return [
        row for row in rows
        if all(display(row.get(col)) == val for col, val in filt.items())
    ]


def _aggregate(rows, agg: Aggregation) -> dict[tuple[str, ...], object]:
    """Group key tuple -> Decimal sum or int count. Null measures contribute
    nothing to sums; counts count rows."""
    groups: dict[tuple[str, ...], object] = {}
    for row in rows:
        key = tuple(display(row.get(col)) for col in agg.group_by)
        if agg.op == "count":
            groups[key] = groups.get(key, 0) + 1
        else:
            value = row.get(agg.measure)
            if is_null(value):
                continue
            if not isinstance(value, Decimal):
                raise TypeError(
                    f"sum({agg.measure}): non-Decimal value {value!r} reached "
                    f"the rule engine (REQ-017)"
                )
            groups[key] = groups.get(key, Decimal("0")) + value
    return groups


def _metric(agg: Aggregation) -> str:
    return f"{agg.op}({agg.measure})"


def _variances(agg: Aggregation, source_rows, target_rows):
    """Per-group (key, source value, target value) where sides disagree."""
    source_groups = _aggregate(source_rows, agg)
    target_groups = _aggregate(target_rows, agg)
    zero = 0 if agg.op == "count" else Decimal("0")
    out = []
    for key in sorted(set(source_groups) | set(target_groups)):
        source_value = source_groups.get(key, zero)
        target_value = target_groups.get(key, zero)
        if source_value != target_value:
            out.append((key, source_value, target_value))
    return out


def execute(rule: CountBalanceRule, datasets, context: ExecutionContext):
    source_rows = datasets.source[rule.source_dataset].to_dict("records")
    target_rows = datasets.target[rule.target_dataset].to_dict("records")

    if not source_rows and not target_rows:
        return [], None  # nothing in scope on either side reconciles trivially

    if rule.params.filter:
        filt = _resolve_filter(rule.params.filter, source_rows, target_rows)
        source_rows = _apply_filter(source_rows, filt)
        target_rows = _apply_filter(target_rows, filt)

    # coarsest level first (spec §11.2.2); stable for equal widths
    aggregations = sorted(
        rule.params.aggregations, key=lambda a: (len(a.group_by), a.group_by, a.op)
    )

    affected: list[AffectedRecord] = []
    level_variances: list[tuple[Aggregation, list]] = []
    for agg in aggregations:
        variances = _variances(agg, source_rows, target_rows)
        level_variances.append((agg, variances))
        for key, source_value, target_value in variances:
            delta = target_value - source_value
            affected.append(AffectedRecord(
                keys=dict(zip(agg.group_by, key)),
                source={_metric(agg): str(source_value)},
                target={_metric(agg): str(target_value)},
                delta=Decimal(str(delta)),
            ))

    # attach finer-level contributing groups behind each coarse variance
    drill_down = []
    for i, (coarse, coarse_vars) in enumerate(level_variances):
        for key, _, _ in coarse_vars:
            coarse_group = dict(zip(coarse.group_by, key))
            for finer, finer_vars in level_variances[i + 1:]:
                if finer.measure != coarse.measure or finer.op != coarse.op:
                    continue
                if not set(finer.group_by) > set(coarse.group_by):
                    continue
                contributing = [
                    {
                        **dict(zip(finer.group_by, fkey)),
                        "source": str(fsource),
                        "target": str(ftarget),
                        "delta": str(ftarget - fsource),
                    }
                    for fkey, fsource, ftarget in finer_vars
                    if all(
                        dict(zip(finer.group_by, fkey))[col] == val
                        for col, val in coarse_group.items()
                    )
                ]
                if contributing:
                    drill_down.append({
                        "level": list(coarse.group_by),
                        "group": coarse_group,
                        "metric": _metric(coarse),
                        "finer_level": list(finer.group_by),
                        "contributing": contributing,
                    })

    detail = {"drill_down": drill_down} if drill_down else None
    return affected, detail
