"""Ingestion: CSV (MS-1.3), fixed-width/copybook + EBCDIC/COMP-3 (MS-2.2)."""

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
from src.ingest.ebcdic import (
    FieldDecodeError,
    decode_binary,
    decode_packed,
    decode_zoned,
    encode_binary,
    encode_packed,
    encode_zoned,
)
from src.ingest.fixedwidth import ingest_fixed_width
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
    "FieldDecodeError",
    "IngestTypeError",
    "IngestedDataset",
    "ParsedDataset",
    "PartialFileError",
    "RegistrationIndex",
    "RejectedRow",
    "content_hash",
    "decode_binary",
    "decode_packed",
    "decode_zoned",
    "detect_header",
    "encode_binary",
    "encode_packed",
    "encode_zoned",
    "ingest_csv",
    "ingest_fixed_width",
    "parse_date",
    "parse_money",
    "register_dataset",
]
