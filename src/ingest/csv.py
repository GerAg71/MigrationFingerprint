"""CSV ingestion (MS-1.3; spec §10.1, §10.3, §10.5).

RFC 4180 parsing via the stdlib csv module (quoted fields, embedded
delimiters/newlines). UTF-8 with Latin-1 fallback, delimiter configurable.

Header handling (spec §10.3, AI-Mapper pattern): a header row is detected
heuristically; headerless files get Column_1..Column_N assigned and resolved
to canonical names by the DatasetSpec's column order, with the resolution
decision recorded as an annotation for the dataset registration.

Typing at the boundary: money/decimal -> Decimal (a float artifact in a money
field is an ingestion error, REQ-017); dates -> datetime.date, with zero/blank
dates mapped to None + annotation, never to 0001-01-01 (spec §4.3, FM-008).
Malformed rows are quarantined with a reason and ingestion continues (§10.5).
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from src.ingest.canonical import CANONICAL_DATASETS, DatasetSpec

ZERO_DATE_LITERALS = {"", "0", "00000000", "0000-00-00", "00/00/0000"}
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_COMPACT_DATE = re.compile(r"^\d{8}$")


class IngestTypeError(TypeError):
    """A binary float reached a money field (REQ-017)."""


@dataclass(frozen=True)
class RejectedRow:
    line: int
    reason: str
    raw: list[str]


@dataclass
class ParsedDataset:
    dataset_name: str
    spec: DatasetSpec
    encoding_used: str
    header_detected: bool
    column_resolution: dict[str, str]  # file column -> canonical name
    columns: list[str]                 # canonical columns present, in file order
    rows: list[dict[str, object]] = field(default_factory=list)
    rejects: list[RejectedRow] = field(default_factory=list)
    annotations: list[str] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def to_dataframe(self):
        """Rows as a pandas DataFrame, dtype=object throughout so Decimal
        money and None nulls survive untouched (spec §11.1, REQ-017)."""
        import pandas as pd

        if not self.rows:
            return pd.DataFrame(
                {c: pd.Series(dtype=object) for c in self.spec.column_names()}
            )
        return pd.DataFrame(self.rows, dtype=object)


def _normalize(name: str) -> str:
    return re.sub(r"[\s\-]+", "_", name.strip().lower())


def detect_header(first_row: list[str], spec: DatasetSpec) -> bool:
    """Heuristic (§10.3): a row is a header when at least half of its
    non-empty cells match canonical column names of the dataset spec."""
    known = set(spec.column_names())
    cells = [_normalize(c) for c in first_row if c.strip()]
    if not cells:
        return False
    matches = sum(1 for c in cells if c in known)
    return matches * 2 >= len(cells)


def parse_money(raw: object, column: str) -> Decimal | None:
    """Money/decimal parser. Rejects float artifacts: binary floats reaching
    this boundary and exponent/inf/nan notation in files (REQ-017)."""
    if raw is None:
        return None
    if isinstance(raw, float):
        raise IngestTypeError(
            f"float value {raw!r} in money field {column!r} (REQ-017: money is Decimal, never float)"
        )
    if isinstance(raw, Decimal):
        return raw
    text = str(raw).strip()
    if text == "":
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError(f"unparsable amount {text!r} in money field {column!r}")
    # Decimal happily accepts float notation (1.2E3, nan, inf) — those forms
    # are binary-float artifacts in extract data, not money (REQ-017).
    if not value.is_finite() or "e" in text.lower():
        raise ValueError(f"float artifact {text!r} in money field {column!r}")
    return value


def parse_date(text: str, column: str) -> tuple[date | None, str | None]:
    """Date parser. Returns (value, annotation). Zero/blank dates map to
    None with an annotation, never to 0001-01-01 (spec §4.3)."""
    cleaned = text.strip()
    if cleaned in ZERO_DATE_LITERALS:
        return None, f"zero/blank date in {column!r} -> null"
    try:
        if _ISO_DATE.match(cleaned):
            parsed = date.fromisoformat(cleaned)
        elif _COMPACT_DATE.match(cleaned):
            parsed = date(int(cleaned[0:4]), int(cleaned[4:6]), int(cleaned[6:8]))
        else:
            raise ValueError("unrecognized format")
    except ValueError as exc:  # includes impossible dates (month 13, day 45)
        raise ValueError(f"unparsable date {cleaned!r} in {column!r}: {exc}")
    if parsed == date(1, 1, 1):
        # A literal epoch-zero date is retained as evidence for FM-008 rules,
        # but flagged: our ingestion never *produces* it from a zero date.
        return parsed, f"suspicious 0001-01-01 date retained in {column!r}"
    return parsed, None


def _decode(data: bytes, encoding: str | None) -> tuple[str, str, list[str]]:
    """Decode file bytes: explicit encoding, else UTF-8 with Latin-1 fallback."""
    if encoding is not None:
        return data.decode(encoding), encoding, []
    try:
        return data.decode("utf-8"), "utf-8", []
    except UnicodeDecodeError:
        return (
            data.decode("latin-1"),
            "latin-1",
            ["encoding: utf-8 decode failed, fell back to latin-1 (spec §10.1)"],
        )


def _resolve_columns(
    first_row: list[str], spec: DatasetSpec, header_detected: bool
) -> tuple[dict[str, str], list[str], list[str]]:
    """Map file columns to canonical names. Returns (resolution, canonical
    column order for rows, annotations)."""
    annotations: list[str] = []
    resolution: dict[str, str] = {}
    columns: list[str] = []
    known = set(spec.column_names())

    if header_detected:
        for cell in first_row:
            normalized = _normalize(cell)
            resolution[cell] = normalized
            columns.append(normalized)
            if normalized not in known:
                annotations.append(
                    f"header: unknown column {cell!r} not in canonical spec "
                    f"{spec.name!r}; carried as text"
                )
    else:
        ordered = spec.column_names()
        for i in range(len(first_row)):
            positional = f"Column_{i + 1}"
            canonical = ordered[i] if i < len(ordered) else positional
            resolution[positional] = canonical
            columns.append(canonical)
            if i >= len(ordered):
                annotations.append(
                    f"headerless: {positional} has no canonical column in "
                    f"{spec.name!r}; carried as text"
                )
        mapping = ", ".join(f"{p}->{c}" for p, c in resolution.items())
        annotations.append(f"headerless: resolved by canonical order: {mapping}")

    missing = [c for c in spec.column_names() if c not in columns]
    if missing:
        annotations.append(
            f"columns absent from file (filled as null): {', '.join(missing)}"
        )
    return resolution, columns, annotations


def _type_row(
    cells: list[str], columns: list[str], spec: DatasetSpec
) -> tuple[dict[str, object], list[str]]:
    """Type one row's cells by canonical column kind. Raises ValueError for
    quarantinable faults; returns (typed row, date annotations)."""
    if len(cells) != len(columns):
        raise ValueError(f"field count {len(cells)} != expected {len(columns)}")
    row: dict[str, object] = {}
    annotations: list[str] = []
    for column, cell in zip(columns, cells):
        kind = spec.kind_of(column) or "text"
        if kind in ("money", "decimal"):
            row[column] = parse_money(cell, column)
        elif kind == "integer":
            text = cell.strip()
            if text == "":
                row[column] = None
            else:
                try:
                    row[column] = int(text)
                except ValueError:
                    raise ValueError(f"unparsable integer {text!r} in {column!r}")
        elif kind == "date":
            value, note = parse_date(cell, column)
            row[column] = value
            if note:
                annotations.append(note)
        else:  # key / text
            row[column] = cell if cell != "" else None
    for column in spec.column_names():
        row.setdefault(column, None)
    return row, annotations


def ingest_csv(
    path: Path | str,
    dataset_name: str,
    *,
    delimiter: str = ",",
    encoding: str | None = None,
) -> ParsedDataset:
    """Parse one CSV extract into a typed canonical dataset (spec §10.1–10.5).

    Malformed rows are quarantined into .rejects with a reason and parsing
    continues; the caller (registration) persists rejects.csv and carries the
    count. Raises KeyError for a non-canonical dataset name (REQ-008).
    """
    if dataset_name not in CANONICAL_DATASETS:
        raise KeyError(
            f"unknown canonical dataset {dataset_name!r}; "
            f"rules bind to canonical names only (REQ-008)"
        )
    spec = CANONICAL_DATASETS[dataset_name]

    data = Path(path).read_bytes()
    text, encoding_used, annotations = _decode(data, encoding)

    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    rows_iter = iter(reader)
    try:
        first_row = next(rows_iter)
    except StopIteration:
        return ParsedDataset(
            dataset_name=dataset_name, spec=spec, encoding_used=encoding_used,
            header_detected=False, column_resolution={}, columns=[],
            annotations=annotations + ["empty file: no rows"],
        )

    header = detect_header(first_row, spec)
    resolution, columns, column_notes = _resolve_columns(first_row, spec, header)
    annotations += column_notes

    parsed = ParsedDataset(
        dataset_name=dataset_name, spec=spec, encoding_used=encoding_used,
        header_detected=header, column_resolution=resolution, columns=columns,
        annotations=annotations,
    )

    date_notes: dict[str, int] = {}
    pending = [] if header else [first_row]
    for cells in pending:
        _consume_row(cells, reader.line_num, parsed, columns, spec, date_notes)
    for cells in rows_iter:
        _consume_row(cells, reader.line_num, parsed, columns, spec, date_notes)

    for note, count in sorted(date_notes.items()):
        parsed.annotations.append(f"dates: {count} x {note}")
    return parsed


def _consume_row(
    cells: list[str],
    line: int,
    parsed: ParsedDataset,
    columns: list[str],
    spec: DatasetSpec,
    date_notes: dict[str, int],
) -> None:
    if not cells:  # skip fully blank lines
        return
    try:
        row, notes = _type_row(cells, columns, spec)
    except ValueError as exc:  # quarantine and continue (§10.5)
        parsed.rejects.append(RejectedRow(line=line, reason=str(exc), raw=cells))
        return
    parsed.rows.append(row)
    for note in notes:
        date_notes[note] = date_notes.get(note, 0) + 1
