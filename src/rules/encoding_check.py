"""encoding_check executor (spec §11.2.5).

Serves FM-005 (EBCDIC→ASCII mojibake) and FM-016 (invalid characters).
Scans configured text fields of the target dataset for characters outside
the allowed set and for mojibake signatures (Ã/Â sequences, U+FFFD) that
betray a wrong-codepage decode even when the characters themselves are
representable. allowed: "ascii" | "latin1" | "custom-set" (custom_set is a
regex character-class body, e.g. "A-Za-z '.,-").
"""

from __future__ import annotations

import re

from src.fingerprint.models import AffectedRecord, EncodingCheckRule
from src.ingest.canonical import CANONICAL_DATASETS
from src.rules._common import ExecutionContext, is_null, key_dict, sort_records

MOJIBAKE_SIGNATURE = re.compile("[ÃÂ�]")  # Ã, Â, replacement char


def _violations(value: str, allowed: str, custom_set: str | None) -> list[str]:
    reasons = []
    if allowed == "ascii":
        bad = sorted({c for c in value if ord(c) > 127})
    elif allowed == "latin1":
        bad = sorted({c for c in value if ord(c) > 255})
    else:  # custom-set
        bad = sorted(set(re.findall(f"[^{custom_set}]", value)))
    if bad:
        reasons.append(f"chars_outside_{allowed}:{''.join(bad)[:8]}")
    if MOJIBAKE_SIGNATURE.search(value):
        reasons.append("mojibake_signature")
    return reasons


def execute(rule: EncodingCheckRule, datasets, context: ExecutionContext):
    frame = datasets.target[rule.target_dataset]
    spec = CANONICAL_DATASETS.get(rule.target_dataset)
    key_columns = [c.name for c in spec.columns if c.kind == "key"] if spec else []
    affected = []
    for row in frame.to_dict("records"):
        for field in rule.params.fields:
            value = row.get(field)
            if is_null(value):
                continue
            reasons = _violations(str(value), rule.params.allowed,
                                  rule.params.custom_set)
            if reasons:
                affected.append(AffectedRecord(
                    keys=key_dict(key_columns, row),
                    source=None,
                    target={field: str(value), "_check": ";".join(reasons)},
                    delta=None,
                ))
    return sort_records(affected), None
