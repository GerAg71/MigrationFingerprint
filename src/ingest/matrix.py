"""Omni Format Matrix compiler (Omni->Omni restore use case, move 1 & 2).

Compiles the conversion team's format dictionary (an .xlsx: Process, Card,
Columns, Length, Picture, Field Name, Req/Opt) into:

  1. Card layouts - one JSON per transaction card with named, positioned,
     typed fields. "Not Used" positions are MATERIALIZED as filler fields:
     a vanilla system has blanks there, so extraction must carry them for
     the off-label detection rules to probe.
  2. Extract-deck skeletons - deterministic COBOL record layouts + MOVE
     lists stamped per card. Pure templating from the matrix: no model, no
     randomness; the matrix row IS the MOVE statement.

Reads the workbook with the standard library only (an .xlsx is a zip of
XML) - no new dependencies. Deterministic: same workbook in, byte-identical
artifacts out.
"""

from __future__ import annotations

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
EXPECTED_HEADER = ["Process", "Description", "Card", "Columns", "Length",
                   "Picture", "Field Name", "Req/Opt"]


class MatrixError(Exception):
    """The workbook does not look like an Omni Format Matrix."""


@dataclass(frozen=True)
class MatrixField:
    name: str          # sanitized identifier (fillers: filler_<start>_<end>)
    label: str         # the matrix's original Field Name
    start: int         # 1-based first column
    length: int
    picture: str | None
    required: bool
    filler: bool       # a "Not Used" position that must stay blank

    @property
    def end(self) -> int:
        return self.start + self.length - 1


@dataclass
class CardLayout:
    card: str
    process: str
    description: str
    fields: list[MatrixField] = field(default_factory=list)

    @property
    def record_length(self) -> int:
        return max(f.end for f in self.fields)


# --- workbook reading (stdlib zip + XML) --------------------------------------


def _cell_value(cell, shared: list[str]) -> str:
    v = cell.find("m:v", _NS)
    if v is None or v.text is None:
        return ""
    if cell.get("t") == "s":
        return shared[int(v.text)]
    return v.text


def _column_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    index = 0
    for ch in letters:
        index = index * 26 + ord(ch) - 64
    return index - 1


def _read_rows(xlsx_path: Path) -> list[list[str]]:
    with zipfile.ZipFile(xlsx_path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", _NS):
                shared.append("".join(t.text or "" for t in si.iter(_M + "t")))
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in sheet.find("m:sheetData", _NS).findall("m:row", _NS):
            values: dict[int, str] = {}
            for cell in row.findall("m:c", _NS):
                values[_column_index(cell.get("r"))] = _cell_value(cell, shared)
            rows.append([values.get(i, "").strip() for i in range(8)])
        return rows


# --- compilation ---------------------------------------------------------------


def _sanitize(label: str) -> str:
    name = re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_").lower()
    if not name:
        return "field"
    if name[0].isdigit():  # identifiers (and COBOL names) can't start digit
        name = "f_" + name
    return name


def _parse_columns(columns: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", columns)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.fullmatch(r"\d+", columns)
    if m:
        return int(columns), int(columns)
    raise MatrixError(f"unparseable Columns value: {columns!r}")


@dataclass
class CompileResult:
    layouts: list[CardLayout]
    discrepancies: list[str] = field(default_factory=list)
    """Rows where the matrix disagrees with itself (e.g. Length vs Columns).
    The compiler trusts the column POSITIONS - they are what extraction
    reads - and reports the disagreement for the team to fix upstream."""
    notes: list[str] = field(default_factory=list)
    """Annotation rows embedded in the workbook (Columns = '[NOTE]' etc.) -
    carried through so documentation is not silently dropped."""


def compile_matrix(xlsx_path: Path | str) -> CompileResult:
    """Parse the workbook into card layouts, in workbook order."""
    rows = _read_rows(Path(xlsx_path))
    if not rows or rows[0] != EXPECTED_HEADER:
        raise MatrixError(
            f"unexpected header {rows[0] if rows else '<empty>'!r}; "
            f"expected {EXPECTED_HEADER!r}")

    cards: dict[str, CardLayout] = {}
    discrepancies: list[str] = []
    notes: list[str] = []
    for line, row in enumerate(rows[1:], start=2):
        process, description, card, columns, length, picture, label, req = row
        if not card:
            continue
        if not re.fullmatch(r"\d+(\s*-\s*\d+)?", columns):
            # an annotation row, not a field (e.g. Columns = "[NOTE]")
            notes.append(
                f"row {line} card {card}: {' '.join(x for x in row if x)}")
            continue
        start, end = _parse_columns(columns)
        span = end - start + 1
        if length and int(length) != span:
            discrepancies.append(
                f"row {line} card {card} field {label!r}: Length {length} "
                f"disagrees with Columns {columns} ({span} positions); "
                f"using the positions")
        filler = label.lower() in ("not used", "filler") or req == "N/A"
        name = (f"filler_{start:03d}_{end:03d}" if filler
                else _sanitize(label))
        layout = cards.setdefault(card, CardLayout(
            card=card, process=process, description=description))
        existing = {f.name for f in layout.fields}
        if name in existing:  # matrix reuses labels; keep names unique
            name = f"{name}_{start:03d}"
        layout.fields.append(MatrixField(
            name=name, label=label, start=start, length=span,
            picture=picture or None,
            required=req.startswith("Req"), filler=filler,
        ))
    return CompileResult(layouts=list(cards.values()),
                         discrepancies=discrepancies, notes=notes)


# --- artifacts -------------------------------------------------------------------


def layout_payload(layout: CardLayout) -> dict:
    return {
        "card": layout.card,
        "process": layout.process,
        "description": layout.description,
        "record_length": layout.record_length,
        "fields": [
            {"name": f.name, "label": f.label, "start": f.start,
             "length": f.length, "picture": f.picture,
             "required": f.required, "filler": f.filler}
            for f in layout.fields
        ],
    }


def stamp_deck(layout: CardLayout) -> str:
    """A COBOL extract skeleton for one card: record layout + MOVE list.
    Deterministic templating - reviewable, diffable, no model involved."""
    tag = re.sub(r"[^A-Z0-9]+", "-", layout.card.upper()).strip("-")
    lines = [
        f"      *> MAPTIVA stamped extract skeleton - card {layout.card}",
        f"      *> {layout.process} - {layout.description}",
        "      *> Generated from the Omni Format Matrix. Do not hand-edit;",
        "      *> recompile the matrix instead.",
        f"       01  {tag}-REC.",
    ]
    for f in layout.fields:
        pic = f.picture or f"X({f.length})"
        note = "Not Used" if f.filler else ("Req" if f.required else "Opt")
        lines.append(
            f"           05  {f.name.upper().replace('_', '-'):<28} "
            f"PIC {pic:<12} *> cols {f.start}-{f.end} {note}")
    lines.append("      *> MOVE list (source master -> card image)")
    for f in layout.fields:
        target = f.name.upper().replace("_", "-")
        if f.filler:
            lines.append(f"           MOVE SPACES TO {target}")
        else:
            lines.append(f"           MOVE <source-field> TO {target}")
    return "\n".join(lines) + "\n"


def write_artifacts(result: CompileResult, out_dir: Path | str,
                    *, decks: bool = False) -> dict:
    """Write card layouts (+ optional decks) and a manifest. Returns the
    manifest payload."""
    layouts = result.layouts
    out = Path(out_dir)
    cards_dir = out / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    manifest_cards = []
    for layout in layouts:
        stem = re.sub(r"[^A-Za-z0-9]+", "-", layout.card).strip("-")
        (cards_dir / f"{stem}.json").write_text(
            json.dumps(layout_payload(layout), indent=2) + "\n",
            encoding="utf-8", newline="\n")
        if decks:
            decks_dir = out / "decks"
            decks_dir.mkdir(parents=True, exist_ok=True)
            (decks_dir / f"{stem}.cbl").write_text(
                stamp_deck(layout), encoding="utf-8", newline="\n")
        manifest_cards.append({
            "card": layout.card, "process": layout.process,
            "fields": len(layout.fields),
            "record_length": layout.record_length,
            "required_fields": sum(1 for f in layout.fields if f.required),
            "filler_fields": sum(1 for f in layout.fields if f.filler),
        })
    manifest = {
        "source": "Omni_Format_Matrix_Complete.xlsx",
        "discrepancies": result.discrepancies,
        "notes": result.notes,
        "cards": manifest_cards,
        "totals": {
            "processes": len({l.process for l in layouts}),
            "cards": len(layouts),
            "fields": sum(len(l.fields) for l in layouts),
            "required_fields": sum(
                1 for l in layouts for f in l.fields if f.required),
            "filler_fields": sum(
                1 for l in layouts for f in l.fields if f.filler),
        },
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest
