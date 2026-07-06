"""Fixed-width / copybook ingestion (MS-2.2; spec §10.1–10.2, §10.5).

Slices records per a LayoutSpec (offsets are 1-based, lengths in bytes) and
decodes each field by its layout type via src/ingest/ebcdic.py, then applies
the canonical semantics: implied decimals land as Decimal (REQ-017), date
fields honor date_format and zero_is_null (zeros/blanks -> null with an
annotation, never 0001-01-01; FM-008), char fields are stripped and blank ->
null.

Record framing: mainframe block files carry no separators (file length must
be a multiple of record_length); text fixed-width files may be newline
separated — detected from the byte(s) following the first record. A short
trailing record is quarantined with a reason (§10.5); field-level decode
faults (invalid digit/sign nibbles) annotate and continue — they are
FM-005/FM-006 evidence, not dropped rows.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from src.fingerprint.models import LayoutField, LayoutSpec
from src.ingest.canonical import CANONICAL_DATASETS
from src.ingest.csv import ParsedDataset, RejectedRow, parse_date
from src.ingest.ebcdic import (
    EBCDIC_CODEPAGES,
    FieldDecodeError,
    decode_binary,
    decode_packed,
    decode_zoned,
)

ZERO_DATE_DIGITS = {"", "0", "00000000"}


def _split_records(data: bytes, record_length: int) -> tuple[list[bytes], str]:
    """Records plus a framing note. Separator sniffed after record one."""
    if len(data) > record_length and data[record_length:record_length + 1] in (b"\n", b"\r"):
        separator = b"\r\n" if data[record_length:record_length + 2] == b"\r\n" else b"\n"
        chunks = [c for c in data.split(separator) if c != b""]
        return chunks, f"framing: newline-separated ({separator!r})"
    return ([data[i:i + record_length] for i in range(0, len(data), record_length)],
            "framing: block (no separator)")


def _decode_field(raw: bytes, field: LayoutField, encoding: str) -> object:
    decimals = field.decimals or 0
    if field.type == "packed":
        return decode_packed(raw, decimals)
    if field.type == "zoned":
        return decode_zoned(raw, decimals, ebcdic=encoding in EBCDIC_CODEPAGES)
    if field.type == "binary":
        return decode_binary(raw, decimals)
    return raw.decode(encoding).strip()  # char


def _canonicalize(value: object, field: LayoutField, kind: str | None,
                  notes: list[str]) -> object:
    """Apply canonical semantics on top of the layout-type decode."""
    if isinstance(value, str):
        if field.date_format or kind == "date":
            cleaned = value.strip()
            if field.zero_is_null and cleaned.strip("0") == "":
                notes.append(f"zero/blank date in {field.name!r} -> null")
                return None
            if cleaned in ZERO_DATE_DIGITS:
                notes.append(f"zero/blank date in {field.name!r} -> null")
                return None
            parsed, note = parse_date(cleaned, field.name)
            if note:
                notes.append(note)
            return parsed
        return value if value != "" else None
    if kind == "integer" and isinstance(value, Decimal):
        return int(value)
    return value


def ingest_fixed_width(
    path: Path | str, dataset_name: str, layout: LayoutSpec
) -> ParsedDataset:
    """Parse one fixed-width extract into a typed canonical dataset."""
    if dataset_name not in CANONICAL_DATASETS:
        raise KeyError(
            f"unknown canonical dataset {dataset_name!r}; "
            f"rules bind to canonical names only (REQ-008)"
        )
    spec = CANONICAL_DATASETS[dataset_name]
    data = Path(path).read_bytes()
    records, framing_note = _split_records(data, layout.record_length)

    columns = [f.name for f in layout.fields]
    resolution = {
        f"bytes[{f.start}:{f.start + f.length - 1}]": f.name for f in layout.fields
    }
    parsed = ParsedDataset(
        dataset_name=dataset_name, spec=spec, encoding_used=layout.encoding,
        header_detected=False, column_resolution=resolution, columns=columns,
        annotations=[f"layout: {layout.layout_id} ({layout.record_length} bytes)",
                     framing_note],
    )

    known = set(spec.column_names())
    for name in columns:
        if name not in known:
            parsed.annotations.append(
                f"layout: field {name!r} not in canonical spec {spec.name!r}; "
                f"carried as decoded"
            )
    missing = [c for c in spec.column_names() if c not in columns]
    if missing:
        parsed.annotations.append(
            f"columns absent from layout (filled as null): {', '.join(missing)}"
        )

    note_counts: dict[str, int] = {}
    for index, record in enumerate(records, start=1):
        if len(record) != layout.record_length:
            parsed.rejects.append(RejectedRow(
                line=index,
                reason=(f"record length {len(record)} != layout "
                        f"record_length {layout.record_length}"),
                raw=[record.hex()],
            ))
            continue
        row: dict[str, object] = {}
        notes: list[str] = []
        for field in layout.fields:
            raw = record[field.start - 1: field.start - 1 + field.length]
            kind = spec.kind_of(field.name)
            try:
                value = _decode_field(raw, field, layout.encoding)
            except (FieldDecodeError, UnicodeDecodeError) as exc:
                # field-level annotation; ingestion continues (§10.5)
                notes.append(f"decode fault in {field.name!r}: {exc}")
                row[field.name] = None
                continue
            try:
                row[field.name] = _canonicalize(value, field, kind, notes)
            except ValueError as exc:
                notes.append(f"decode fault in {field.name!r}: {exc}")
                row[field.name] = None
        for column in spec.column_names():
            row.setdefault(column, None)
        parsed.rows.append(row)
        for note in notes:
            note_counts[note] = note_counts.get(note, 0) + 1

    for note, count in sorted(note_counts.items()):
        parsed.annotations.append(f"fields: {count} x {note}")
    return parsed
