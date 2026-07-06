"""Dataset registration (MS-1.3; spec §10.4–10.5).

register_dataset() ingests one extract and produces the DatasetRegistration
record: content-hashed (sha256 over raw bytes, REQ-023), reject-quarantined
(§10.5), and halted on partial files (REQ-022). RegistrationIndex is the
lookup the runner uses to refuse rules whose datasets are not registered on
both sides (REQ-021, wired in MS-1.5).
"""

from __future__ import annotations

import csv as _csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

from src.fingerprint.models import DatasetRegistration, DetectionRule
from src.ingest.csv import ParsedDataset, ingest_csv


class PartialFileError(Exception):
    """Row count below the registered expectation — the run must halt at
    ingesting with this failure reason (REQ-022)."""


@dataclass(frozen=True)
class IngestedDataset:
    registration: DatasetRegistration
    data: ParsedDataset


def content_hash(path: Path | str) -> str:
    """sha256 over the raw file bytes; identical bytes give identical hashes
    regardless of location or timestamp (REQ-023)."""
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_rejects(
    rejects_dir: Path, side: str, dataset_name: str, parsed: ParsedDataset,
    delimiter: str,
) -> Path:
    rejects_dir.mkdir(parents=True, exist_ok=True)
    path = rejects_dir / f"{side}_{dataset_name}.rejects.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = _csv.writer(handle)
        writer.writerow(["line", "reason", "raw"])
        for reject in parsed.rejects:
            writer.writerow([reject.line, reject.reason, delimiter.join(reject.raw)])
    return path


def register_dataset(
    path: Path | str,
    *,
    run_id: str,
    side: Literal["source", "target"],
    dataset_name: str,
    delimiter: str = ",",
    encoding: str | None = None,
    expected_min_rows: int | None = None,
    rejects_dir: Path | str | None = None,
    layout_id: str | None = None,
    crosswalks_applied: Iterable[str] = (),
) -> IngestedDataset:
    """Ingest and register one extract (spec §10.4).

    Raises PartialFileError when the accepted row count falls below
    expected_min_rows (REQ-022) — the caller must halt the run at ingesting.
    """
    path = Path(path)
    parsed = ingest_csv(path, dataset_name, delimiter=delimiter, encoding=encoding)

    rejects_uri: str | None = None
    if parsed.rejects and rejects_dir is not None:
        rejects_path = _write_rejects(Path(rejects_dir), side, dataset_name, parsed, delimiter)
        rejects_uri = str(rejects_path)
        parsed.annotations.append(
            f"rejects: {len(parsed.rejects)} row(s) quarantined to {rejects_path.name}"
        )

    if expected_min_rows is not None and parsed.row_count < expected_min_rows:
        raise PartialFileError(
            f"partial file: {side}/{dataset_name} at {path} has "
            f"{parsed.row_count} accepted rows ({len(parsed.rejects)} rejected), "
            f"below the registered expectation of {expected_min_rows} — "
            f"run halted at ingesting (REQ-022)"
        )

    registration = DatasetRegistration(
        run_id=run_id,
        side=side,
        dataset_name=dataset_name,
        uri=str(path),
        row_count=parsed.row_count,
        content_hash=content_hash(path),
        layout_id=layout_id,
        crosswalks_applied=list(crosswalks_applied),
        annotations=list(parsed.annotations),
        reject_count=len(parsed.rejects),
        rejects_uri=rejects_uri,
    )
    return IngestedDataset(registration=registration, data=parsed)


class RegistrationIndex:
    """Registered datasets for one run, keyed by (side, dataset_name).

    Makes the REQ-021 gate trivial: a rule may execute only when
    missing_for_rule() returns an empty list.
    """

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], IngestedDataset] = {}

    def add(self, ingested: IngestedDataset) -> None:
        key = (ingested.registration.side, ingested.registration.dataset_name)
        if key in self._entries:
            raise ValueError(f"dataset already registered: {key[0]}/{key[1]}")
        self._entries[key] = ingested

    def get(self, side: str, dataset_name: str) -> IngestedDataset | None:
        return self._entries.get((side, dataset_name))

    def is_registered(self, side: str, dataset_name: str) -> bool:
        return (side, dataset_name) in self._entries

    def registrations(self) -> list[DatasetRegistration]:
        return [e.registration for _, e in sorted(self._entries.items())]

    def missing_for_rule(self, rule: DetectionRule) -> list[str]:
        """Datasets the rule declares that are not registered, as
        'side/dataset' strings; empty means the rule may execute (REQ-021).

        derived_recompute inputs may name additional canonical datasets
        (undotted values, e.g. "loan_payments"); those are source-side
        dependencies and gate the rule too."""
        from src.ingest.canonical import CANONICAL_DATASETS

        missing = []
        if rule.source_dataset and not self.is_registered("source", rule.source_dataset):
            missing.append(f"source/{rule.source_dataset}")
        if not self.is_registered("target", rule.target_dataset):
            missing.append(f"target/{rule.target_dataset}")
        if rule.type == "derived_recompute":
            for ref in rule.params.inputs.values():
                if "." in ref or ref not in CANONICAL_DATASETS:
                    continue
                gap = f"source/{ref}"
                if not self.is_registered("source", ref) and gap not in missing:
                    missing.append(gap)
        return missing

    def missing_for_rules(self, rules: Iterable[DetectionRule]) -> dict[str, list[str]]:
        """Per-rule gaps for every rule that cannot execute."""
        gaps = {}
        for rule in rules:
            missing = self.missing_for_rule(rule)
            if missing:
                gaps[rule.rule_id] = missing
        return gaps
