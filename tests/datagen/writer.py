"""Sample-pair emission (spec §25.4): CSV pairs, plus EBCDIC pairs where the
loans dataset is a cp037 fixed-width .dat (same canonical truth, exercising
ingestion equivalence) and FM-006 decode defects are seeded.

Deterministic output: canonical column order (plus any extra seeded columns,
sorted), LF line endings, UTF-8 for CSV; block-framed cp037 records for .dat.
"""

from __future__ import annotations

import copy
import csv
import json
from decimal import Decimal
from pathlib import Path

from src.fingerprint.models import LayoutSpec
from src.ingest.canonical import CANONICAL_DATASETS
from src.ingest.ebcdic import EBCDIC_SPACE, encode_packed, encode_zoned
from tests.datagen.layouts import LOANS_LAYOUT
from tests.datagen.mutators import apply_ebcdic_mutations, apply_mutations
from tests.datagen.truth import build_truth


def _fieldnames(dataset: str, rows: list[dict[str, str]]) -> list[str]:
    canonical = CANONICAL_DATASETS[dataset].column_names()
    extras = sorted({k for row in rows for k in row} - set(canonical))
    return canonical + extras


def write_dataset(path: Path, dataset: str, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_fieldnames(dataset, rows),
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _encode_record(row: dict[str, str], layout: LayoutSpec) -> bytes:
    record = bytearray([EBCDIC_SPACE] * layout.record_length)
    for field in layout.fields:
        value = row.get(field.name) or ""
        if field.type == "packed":
            raw = encode_packed(Decimal(value or "0"), field.length,
                                field.decimals or 0)
        elif field.type == "zoned":
            raw = encode_zoned(Decimal(value or "0"), field.length,
                               field.decimals or 0)
        else:  # char; dates as YYYYMMDD, null dates as zeros
            text = value.replace("-", "") if field.date_format else value
            if field.date_format and text == "":
                text = "0" * field.length
            raw = text.ljust(field.length).encode(layout.encoding)
        record[field.start - 1: field.start - 1 + field.length] = raw
    return bytes(record)


def write_dat(path: Path, layout: LayoutSpec, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(_encode_record(row, layout) for row in rows))


def write_pair(plan_id: str, source_dir: Path, target_dir: Path,
               seeded: bool, ebcdic_loans: bool = False) -> None:
    """Emit one plan pair. Source is always the pristine truth; the target is
    identical (clean pair) or carries every seeded defect (seeded pair).
    With ebcdic_loans the loans dataset emits as a cp037 .dat and the seeded
    variant additionally carries the FM-006 decode defects."""
    truth = build_truth(plan_id)
    target = copy.deepcopy(truth)
    if seeded:
        apply_mutations(target)
        if ebcdic_loans:
            apply_ebcdic_mutations(target)
    for side_dir, side_truth in ((Path(source_dir), truth),
                                 (Path(target_dir), target)):
        for dataset, rows in side_truth.items():
            if ebcdic_loans and dataset == "loans":
                write_dat(side_dir / "loans.dat", LOANS_LAYOUT, rows)
            else:
                write_dataset(side_dir / f"{dataset}.csv", dataset, rows)


def write_samples(samples_dir: Path) -> None:
    """Regenerate data/samples: CSV pairs (spec §25.2–25.3) and the EBCDIC
    variants (§25.4), plus the LayoutSpec the runner needs (--layout-dir)."""
    samples_dir = Path(samples_dir)
    for plan_id, seeded, ebcdic in (
        ("PLN-CLEAN-01", False, False),
        ("PLN-SEED-01", True, False),
        ("PLN-CLEAN-EB", False, True),
        ("PLN-SEED-EB", True, True),
    ):
        write_pair(plan_id,
                   samples_dir / "source" / plan_id,
                   samples_dir / "target" / plan_id,
                   seeded=seeded, ebcdic_loans=ebcdic)
    layouts_dir = samples_dir / "layouts"
    layouts_dir.mkdir(parents=True, exist_ok=True)
    (layouts_dir / "loans.json").write_bytes(
        (json.dumps(LOANS_LAYOUT.model_dump(mode="json"), indent=2,
                    sort_keys=True) + "\n").encode("utf-8")
    )
