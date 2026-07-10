"""format_conformance executor (Omni->Omni restore use case).

Serves FM-103 (off-label field usage) and FM-104 (required-field
regression) of the restore fingerprint: validates one dataset against the platform's
format expectation model, expressed in the Omni Format Matrix's own
vocabulary - COBOL Picture clauses, Required flags, and "Not Used" filler
positions that must be blank (data found in one is evidence of
repurposing). Checks per field:

  must_be_blank  -> any value present is an off-label finding
  required       -> blank/missing value is a regression finding
  picture        -> value must conform to X(n) / 9(n) / S9(n)V9(m) semantics
  domain         -> value must be one of an enumerated set

Single-sided like encoding_check; ``params.side`` selects the frame
(default "target"; a pre-cutover profile run points it at the source).
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from src.fingerprint.models import AffectedRecord, FormatConformanceRule
from src.ingest.canonical import CANONICAL_DATASETS
from src.rules._common import ExecutionContext, is_null, key_dict, sort_records

_TEXT_PIC = re.compile(r"^X(?:\((\d+)\))?$")
_NUM_PIC = re.compile(r"^(S)?9(?:\((\d+)\))?(?:V(9(?:\((\d+)\))?|9+))?$")


def _picture_lengths(picture: str):
    """Parse a Picture into (kind, int_digits/max_len, frac_digits, signed)."""
    m = _TEXT_PIC.fullmatch(picture)
    if m:
        return "text", int(m.group(1) or 1), 0, False
    m = _NUM_PIC.fullmatch(picture)
    if m:
        signed = m.group(1) is not None
        int_digits = int(m.group(2) or 1)
        frac = m.group(3) or ""
        if frac.startswith("9(") and m.group(4):
            frac_digits = int(m.group(4))
        else:
            frac_digits = frac.count("9")
        return "numeric", int_digits, frac_digits, signed
    return None  # unparseable pictures never fire (schema already vets them)


def _blank(value) -> bool:
    return is_null(value) or str(value).strip() == ""


def picture_violation(value, picture: str) -> str | None:
    """Reason string when a value cannot live in the given Picture."""
    parsed = _picture_lengths(picture)
    if parsed is None:
        return None
    kind, int_digits, frac_digits, signed = parsed
    text = str(value)

    if kind == "text":
        if len(text) > int_digits:
            return f"length_{len(text)}_exceeds_{picture}"
        return None

    # numeric picture: dates are never valid, letters are never valid
    if isinstance(value, date):
        return f"date_in_numeric_{picture}"
    try:
        number = Decimal(text)
    except InvalidOperation:
        return f"non_numeric_in_{picture}"
    if not number.is_finite():
        return f"non_numeric_in_{picture}"
    if number < 0 and not signed:
        return f"negative_in_unsigned_{picture}"
    sign, digits, exponent = number.as_tuple()
    frac = max(0, -exponent)
    integer = max(1, len(digits) - frac)
    if frac > frac_digits:
        return f"fraction_{frac}dp_exceeds_{picture}"
    if integer > int_digits:
        return f"integer_{integer}_digits_exceed_{picture}"
    return None


def execute(rule: FormatConformanceRule, datasets, context: ExecutionContext):
    dataset_name = (rule.source_dataset if rule.params.side == "source"
                    else rule.target_dataset)
    frame = getattr(datasets, rule.params.side)[dataset_name]
    spec = CANONICAL_DATASETS.get(dataset_name)
    key_columns = [c.name for c in spec.columns if c.kind == "key"] if spec else []

    affected = []
    counts = {"off_label": 0, "required_blank": 0, "picture": 0, "domain": 0}
    for row in frame.to_dict("records"):
        for expectation in rule.params.fields:
            value = row.get(expectation.field)
            blank = _blank(value)
            reasons = []
            if expectation.must_be_blank and not blank:
                reasons.append("data_in_unused_position")
                counts["off_label"] += 1
            if expectation.required and blank:
                reasons.append("required_field_blank")
                counts["required_blank"] += 1
            if not blank:
                if expectation.picture:
                    reason = picture_violation(value, expectation.picture)
                    if reason:
                        reasons.append(reason)
                        counts["picture"] += 1
                if expectation.domain and str(value) not in expectation.domain:
                    reasons.append("outside_domain")
                    counts["domain"] += 1
            if reasons:
                payload = {expectation.field: "" if blank else str(value),
                           "_check": ";".join(reasons)}
                affected.append(AffectedRecord(
                    keys=key_dict(key_columns, row),
                    source=payload if rule.params.side == "source" else None,
                    target=payload if rule.params.side == "target" else None,
                    delta=None,
                ))
    detail = {k: v for k, v in counts.items() if v}
    return sort_records(affected), detail or None
