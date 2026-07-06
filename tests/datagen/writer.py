"""CSV emission for sample pairs (spec §25.4, Phase-1 CSV variant).

Deterministic output: canonical column order (plus any extra seeded columns,
sorted), LF line endings, UTF-8. The fixed-width/EBCDIC variant of the same
truth is added at MS-2.2.
"""

from __future__ import annotations

import copy
import csv
from pathlib import Path

from src.ingest.canonical import CANONICAL_DATASETS
from tests.datagen.mutators import apply_mutations
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


def write_pair(plan_id: str, source_dir: Path, target_dir: Path,
               seeded: bool) -> None:
    """Emit one plan pair. Source is always the pristine truth; the target is
    identical (clean pair) or carries every seeded defect (seeded pair)."""
    truth = build_truth(plan_id)
    target = copy.deepcopy(truth)
    if seeded:
        apply_mutations(target)
    for dataset, rows in truth.items():
        write_dataset(Path(source_dir) / f"{dataset}.csv", dataset, rows)
    for dataset, rows in target.items():
        write_dataset(Path(target_dir) / f"{dataset}.csv", dataset, rows)


def write_samples(samples_dir: Path) -> None:
    """Regenerate data/samples: the clean and seeded pairs (spec §25.2–25.3)."""
    samples_dir = Path(samples_dir)
    write_pair("PLN-CLEAN-01",
               samples_dir / "source" / "PLN-CLEAN-01",
               samples_dir / "target" / "PLN-CLEAN-01", seeded=False)
    write_pair("PLN-SEED-01",
               samples_dir / "source" / "PLN-SEED-01",
               samples_dir / "target" / "PLN-SEED-01", seeded=True)
