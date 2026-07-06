"""sort_order_check executor (spec §11.2.6).

Serves FM-005 (collation sensitivity: EBCDIC collates digits after letters,
ASCII the reverse). Verifies an ordering-sensitive extract against the
declared collation and reports the divergent positions — each adjacent pair
where row[i] sorts strictly after row[i+1] under the collation ("the first
digit-vs-letter boundary"). A file correctly ordered under EBCDIC therefore
trips the ascii check exactly at the boundary rows, not wholesale.

Collation keys: ascii -> UTF-8 byte order (codepoint order); ebcdic ->
cp037-encoded byte order.
"""

from __future__ import annotations

from src.fingerprint.models import AffectedRecord, SortOrderCheckRule
from src.ingest.canonical import CANONICAL_DATASETS
from src.rules._common import ExecutionContext, display, key_dict

def _collation_key(values: tuple[str, ...], collation: str) -> tuple[bytes, ...]:
    if collation == "ebcdic":
        return tuple(v.encode("cp037", errors="replace") for v in values)
    return tuple(v.encode("utf-8") for v in values)


def execute(rule: SortOrderCheckRule, datasets, context: ExecutionContext):
    dataset_name = rule.params.dataset or rule.target_dataset
    frame = datasets.target[dataset_name]
    spec = CANONICAL_DATASETS.get(dataset_name)
    key_columns = [c.name for c in spec.columns if c.kind == "key"] if spec else []
    order_by = list(rule.params.order_by)
    collation = rule.params.collation

    affected = []
    previous_values: tuple[str, ...] | None = None
    previous_key: tuple[bytes, ...] | None = None
    for position, row in enumerate(frame.to_dict("records")):
        values = tuple(display(row.get(c)) for c in order_by)
        key = _collation_key(values, collation)
        if previous_key is not None and previous_key > key:
            affected.append(AffectedRecord(
                keys=key_dict(key_columns, row),
                source=None,
                target={
                    "_check": f"out_of_order:{collation}",
                    "position": str(position),
                    "value": " | ".join(values),
                    "previous": " | ".join(previous_values),
                },
                delta=None,
            ))
        previous_values, previous_key = values, key
    # file order is the evidence — records stay in positional order
    return affected, None
