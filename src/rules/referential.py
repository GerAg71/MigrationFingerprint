"""referential executor (spec §11.2.3).

Serves FM-011 (duplicate IDs/SSNs), FM-003 (untraceable derived fields), and
the 100%-conversion proof of REQ-003.

Bidirectional orphan detection on join_keys: every target row must trace to a
source row and vice versa; the two orphan sets are reported separately as
missing_in_target and unexpected_in_target. The unique param enforces key
uniqueness per side, reporting every row of a duplicate group. The
unmapped_target_fields param flags target values carrying no mapping-rule
provenance; the manifest is loaded at the run layer and arrives via
ExecutionContext (executors do no I/O, REQ-009).
"""

from __future__ import annotations

from src.fingerprint.models import AffectedRecord, ReferentialRule
from src.ingest.canonical import CANONICAL_DATASETS
from src.rules._common import (
    ExecutionContext,
    display,
    is_null,
    key_dict,
    stringify,
)


def _key_tuples(rows, join_keys):
    """Join-key tuples for rows with fully non-null keys."""
    out = set()
    for row in rows:
        values = [row.get(k) for k in join_keys]
        if any(is_null(v) for v in values):
            continue  # unkeyable rows are validity's problem (FM-010)
        out.add(tuple(display(v) for v in values))
    return out


def _duplicates(rows, unique_cols, join_keys, side):
    groups: dict[tuple[str, ...], list[dict]] = {}
    for row in rows:
        values = [row.get(c) for c in unique_cols]
        if any(is_null(v) for v in values):
            continue
        groups.setdefault(tuple(display(v) for v in values), []).append(row)

    records = []
    for key, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        for row in members:  # every row of the duplicate group is reported
            identity = {k: display(row.get(k)) for k in (join_keys or [])}
            identity["_set"] = f"duplicate_{side}"
            records.append(AffectedRecord(
                keys=dict(zip(unique_cols, key)),
                source=identity if side == "source" else None,
                target=identity if side == "target" else None,
                delta=None,
            ))
    return records


def execute(rule: ReferentialRule, datasets, context: ExecutionContext):
    source_rows = datasets.source[rule.source_dataset].to_dict("records")
    target_rows = datasets.target[rule.target_dataset].to_dict("records")
    join_keys = list(rule.join_keys)

    affected: list[AffectedRecord] = []
    source_keys = _key_tuples(source_rows, join_keys)
    target_keys = _key_tuples(target_rows, join_keys)

    missing_in_target = sorted(source_keys - target_keys)
    unexpected_in_target = sorted(target_keys - source_keys)

    for key in missing_in_target:
        affected.append(AffectedRecord(
            keys=dict(zip(join_keys, key)),
            source={"_set": "missing_in_target"},
            target=None,
            delta=None,
        ))
    for key in unexpected_in_target:
        affected.append(AffectedRecord(
            keys=dict(zip(join_keys, key)),
            source=None,
            target={"_set": "unexpected_in_target"},
            delta=None,
        ))

    duplicate_count = 0
    if rule.params.unique:
        unique_cols = list(rule.params.unique)
        for side, rows in (("source", source_rows), ("target", target_rows)):
            records = _duplicates(rows, unique_cols, join_keys, side)
            duplicate_count += len(records)
            affected.extend(records)

    unmapped_count = 0
    if rule.params.unmapped_target_fields:
        mapped = context.mapped_target_fields
        if mapped is None:
            raise ValueError(
                "unmapped_target_fields requires the mapping manifest "
                f"({rule.params.unmapped_target_fields.mapping_manifest}) "
                "loaded into ExecutionContext.mapped_target_fields at the "
                "run layer (executors do no I/O, REQ-009)"
            )
        spec = CANONICAL_DATASETS.get(rule.target_dataset)
        key_columns = (
            [c.name for c in spec.columns if c.kind == "key"] if spec else join_keys
        )
        for field in rule.params.unmapped_target_fields.fields:
            if field in mapped:
                continue  # traced to a mapping rule
            for row in target_rows:
                value = row.get(field)
                if is_null(value):
                    continue
                unmapped_count += 1
                affected.append(AffectedRecord(
                    keys=key_dict(key_columns, row),
                    source=None,
                    target={
                        field: stringify(value),
                        "_check": "no mapping-rule provenance (FM-003)",
                    },
                    delta=None,
                ))

    detail = {
        "missing_in_target": len(missing_in_target),
        "unexpected_in_target": len(unexpected_in_target),
        "duplicate_rows": duplicate_count,
        "unmapped_values": unmapped_count,
    }
    return affected, detail if any(detail.values()) else None
