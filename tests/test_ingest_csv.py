"""MS-1.3: CSV parsing — header detection, headerless resolution, boundary
typing (Decimal money, zero-date semantics), reject quarantine (§10.1–10.5)."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.ingest.csv import (
    IngestTypeError,
    detect_header,
    ingest_csv,
    parse_date,
    parse_money,
)
from src.ingest.canonical import CANONICAL_DATASETS


def write(tmp_path: Path, name: str, text: str, encoding: str = "utf-8") -> Path:
    path = tmp_path / name
    path.write_bytes(text.encode(encoding))
    return path


# --- header detection (§10.3) ----------------------------------------------


def test_header_row_detected(tmp_path):
    path = write(tmp_path, "b.csv",
                 "plan_id,participant_id,money_type_code,investment_code,balance\n"
                 "PLN001,P0001,PRETAX,F01,1234.56\n")
    parsed = ingest_csv(path, "balances")
    assert parsed.header_detected is True
    assert parsed.row_count == 1
    assert parsed.rows[0]["plan_id"] == "PLN001"


def test_headerless_detected_and_resolved_by_canonical_order(tmp_path):
    path = write(tmp_path, "b.csv",
                 "PLN001,P0001,PRETAX,F01,1234.56\n"
                 "PLN001,P0002,ROTH,F02,99.10\n")
    parsed = ingest_csv(path, "balances")
    assert parsed.header_detected is False
    # Column_1..N resolved by the balances spec order
    assert parsed.column_resolution["Column_1"] == "plan_id"
    assert parsed.column_resolution["Column_5"] == "balance"
    assert parsed.rows[1]["money_type_code"] == "ROTH"
    assert parsed.rows[1]["balance"] == Decimal("99.10")
    # the resolution decision is logged for the registration (§10.3)
    assert any("headerless: resolved by canonical order" in a and
               "Column_1->plan_id" in a for a in parsed.annotations)


def test_detect_header_heuristic_direct():
    spec = CANONICAL_DATASETS["participants"]
    assert detect_header(["plan_id", "participant_id", "ssn", "dob"], spec)
    assert detect_header(["Plan ID", "Participant-ID", "SSN", "DOB"], spec)  # normalized
    assert not detect_header(["PLN001", "P0001", "900441207", "1980-01-01"], spec)


def test_header_with_unknown_column_annotated(tmp_path):
    path = write(tmp_path, "b.csv",
                 "plan_id,participant_id,money_type_code,investment_code,balance,mystery\n"
                 "PLN001,P0001,PRETAX,F01,10.00,x\n")
    parsed = ingest_csv(path, "balances")
    assert parsed.header_detected
    assert any("unknown column 'mystery'" in a for a in parsed.annotations)
    assert parsed.rows[0]["mystery"] == "x"  # carried as text


# --- typing at the boundary (REQ-017, §4.3) ---------------------------------


def test_money_lands_as_decimal_never_float(tmp_path):
    path = write(tmp_path, "b.csv",
                 "plan_id,participant_id,money_type_code,investment_code,balance\n"
                 "PLN001,P0001,PRETAX,F01,1234.56\n")
    value = ingest_csv(path, "balances").rows[0]["balance"]
    assert isinstance(value, Decimal)
    assert not isinstance(value, float)
    assert value == Decimal("1234.56")


def test_exponent_notation_money_is_rejected_as_float_artifact(tmp_path):
    path = write(tmp_path, "b.csv",
                 "plan_id,participant_id,money_type_code,investment_code,balance\n"
                 "PLN001,P0001,PRETAX,F01,1.2E3\n")
    parsed = ingest_csv(path, "balances")
    assert parsed.row_count == 0
    assert len(parsed.rejects) == 1
    assert "float artifact" in parsed.rejects[0].reason


def test_binary_float_in_money_field_raises():
    with pytest.raises(IngestTypeError, match="REQ-017"):
        parse_money(1.5, "balance")


def test_blank_money_is_null(tmp_path):
    path = write(tmp_path, "l.csv",
                 "plan_id,participant_id,loan_id,outstanding_balance,payment_amount\n"
                 "PLN001,P0001,L1,100.00,\n")
    row = ingest_csv(path, "loans").rows[0]
    assert row["payment_amount"] is None


def test_integer_column_typed(tmp_path):
    path = write(tmp_path, "l.csv",
                 "plan_id,participant_id,loan_id,term_months\n"
                 "PLN001,P0001,L1,60\n")
    assert ingest_csv(path, "loans").rows[0]["term_months"] == 60


# --- date semantics (§4.3, FM-008) ------------------------------------------


def test_iso_and_compact_dates_parse(tmp_path):
    path = write(tmp_path, "p.csv",
                 "plan_id,participant_id,dob,hire_date\n"
                 "PLN001,P0001,1980-02-29,20200131\n")
    row = ingest_csv(path, "participants").rows[0]
    assert row["dob"] == date(1980, 2, 29)
    assert row["hire_date"] == date(2020, 1, 31)


@pytest.mark.parametrize("literal", ["", "0", "00000000", "0000-00-00"])
def test_zero_and_blank_dates_become_null_with_annotation(tmp_path, literal):
    path = write(tmp_path, "p.csv",
                 f"plan_id,participant_id,dob,term_date\n"
                 f"PLN001,P0001,1980-01-01,{literal}\n")
    parsed = ingest_csv(path, "participants")
    assert parsed.rows[0]["term_date"] is None
    assert any("zero/blank date in 'term_date' -> null" in a
               for a in parsed.annotations)
    # never mapped to the epoch-zero sentinel
    assert parsed.rows[0]["term_date"] != date(1, 1, 1)


def test_literal_epoch_zero_date_is_retained_but_annotated():
    value, note = parse_date("0001-01-01", "dob")
    assert value == date(1, 1, 1)
    assert "0001-01-01" in note


def test_impossible_date_quarantines_row(tmp_path):
    path = write(tmp_path, "p.csv",
                 "plan_id,participant_id,dob\n"
                 "PLN001,P0001,2020-13-45\n"
                 "PLN001,P0002,1975-06-30\n")
    parsed = ingest_csv(path, "participants")
    assert parsed.row_count == 1
    assert len(parsed.rejects) == 1
    assert "dob" in parsed.rejects[0].reason


# --- reject quarantine (§10.5) ----------------------------------------------


def test_malformed_rows_quarantined_and_ingestion_continues(tmp_path):
    path = write(tmp_path, "b.csv",
                 "plan_id,participant_id,money_type_code,investment_code,balance\n"
                 "PLN001,P0001,PRETAX,F01,100.00\n"
                 "PLN001,P0002,PRETAX,F01\n"                # short row
                 "PLN001,P0003,PRETAX,F01,not-a-number\n"   # bad amount
                 "PLN001,P0004,PRETAX,F01,200.00\n")
    parsed = ingest_csv(path, "balances")
    assert parsed.row_count == 2
    assert [r.line for r in parsed.rejects] == [3, 4]
    assert "field count 4 != expected 5" in parsed.rejects[0].reason
    assert "unparsable amount" in parsed.rejects[1].reason


# --- RFC 4180, encodings, delimiter (§10.1) ----------------------------------


def test_rfc4180_quoted_fields_with_comma_and_newline(tmp_path):
    path = write(tmp_path, "p.csv",
                 'plan_id,participant_id,address_1\n'
                 'PLN001,P0001,"123 Main St, Apt 4\nRear entrance"\n')
    row = ingest_csv(path, "participants").rows[0]
    assert row["address_1"] == "123 Main St, Apt 4\nRear entrance"


def test_latin1_fallback_with_annotation(tmp_path):
    path = tmp_path / "p.csv"
    path.write_bytes("plan_id,participant_id,first_name\nPLN001,P0001,José\n"
                     .encode("latin-1"))
    parsed = ingest_csv(path, "participants")
    assert parsed.encoding_used == "latin-1"
    assert parsed.rows[0]["first_name"] == "José"
    assert any("fell back to latin-1" in a for a in parsed.annotations)


def test_utf8_preferred_when_valid(tmp_path):
    path = write(tmp_path, "p.csv",
                 "plan_id,participant_id,first_name\nPLN001,P0001,José\n")
    parsed = ingest_csv(path, "participants")
    assert parsed.encoding_used == "utf-8"
    assert parsed.rows[0]["first_name"] == "José"


def test_configurable_delimiter(tmp_path):
    path = write(tmp_path, "b.psv",
                 "plan_id|participant_id|money_type_code|investment_code|balance\n"
                 "PLN001|P0001|PRETAX|F01|55.25\n")
    parsed = ingest_csv(path, "balances", delimiter="|")
    assert parsed.rows[0]["balance"] == Decimal("55.25")


# --- canonical binding (REQ-008) ---------------------------------------------


def test_unknown_dataset_name_rejected(tmp_path):
    path = write(tmp_path, "x.csv", "a,b\n1,2\n")
    with pytest.raises(KeyError, match="REQ-008"):
        ingest_csv(path, "not_a_dataset")


def test_absent_canonical_columns_filled_null_and_annotated(tmp_path):
    path = write(tmp_path, "p.csv",
                 "plan_id,participant_id\nPLN001,P0001\n")
    parsed = ingest_csv(path, "participants")
    assert parsed.rows[0]["ssn"] is None
    assert any("columns absent from file" in a for a in parsed.annotations)
