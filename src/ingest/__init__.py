"""Ingestion: CSV (MS-1.3); fixed-width/copybook + EBCDIC arrive in MS-2.2."""

from src.ingest.canonical import CANONICAL_DATASETS, DatasetColumn, DatasetSpec
from src.ingest.csv import (
    IngestTypeError,
    ParsedDataset,
    RejectedRow,
    detect_header,
    ingest_csv,
    parse_date,
    parse_money,
)
from src.ingest.registration import (
    IngestedDataset,
    PartialFileError,
    RegistrationIndex,
    content_hash,
    register_dataset,
)

__all__ = [
    "CANONICAL_DATASETS",
    "DatasetColumn",
    "DatasetSpec",
    "IngestTypeError",
    "IngestedDataset",
    "ParsedDataset",
    "PartialFileError",
    "RegistrationIndex",
    "RejectedRow",
    "content_hash",
    "detect_header",
    "ingest_csv",
    "parse_date",
    "parse_money",
    "register_dataset",
]
