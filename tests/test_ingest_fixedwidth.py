"""MS-2.2 (spec §10.2, REQ-023): packed COMP-3 sign nibbles, implied
decimals, zoned overpunch, zero-date semantics, record framing, and the
Appendix D.4 golden fixture."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.fingerprint.models import LayoutSpec
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
from src.ingest.registration import register_dataset
from tests.datagen.layouts import LOANS_LAYOUT
from tests.datagen.truth import build_truth
from tests.datagen.writer import write_dat, write_dataset

EBCDIC_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ebcdic"


# --- packed COMP-3 (sign nibbles, implied decimals) ---------------------------


def test_packed_positive_c_sign():
    # bytes 10 43 21 7C: digits 1043217, sign nibble C -> +10432.17 at 2dp
    assert decode_packed(bytes.fromhex("1043217C"), 2) == Decimal("10432.17")


def test_packed_positive_f_sign():
    assert decode_packed(bytes.fromhex("12345F"), 2) == Decimal("123.45")


def test_packed_negative_d_sign():
    # bytes 25 07 5D: digits 25075, sign nibble D -> -250.75 at 2dp
    assert decode_packed(bytes.fromhex("25075D"), 2) == Decimal("-250.75")


@pytest.mark.parametrize("decimals,expected", [
    (0, Decimal("1043217")), (2, Decimal("10432.17")), (4, Decimal("104.3217")),
])
def test_packed_implied_decimal_positions(decimals, expected):
    assert decode_packed(bytes.fromhex("1043217C"), decimals) == expected


def test_packed_invalid_sign_nibble_is_field_fault():
    with pytest.raises(FieldDecodeError, match="sign nibble 0x3"):
        decode_packed(bytes.fromhex("123453"), 2)


def test_packed_invalid_digit_nibble_is_field_fault():
    with pytest.raises(FieldDecodeError, match="digit nibble"):
        decode_packed(bytes.fromhex("1B345C"), 2)


def test_packed_round_trip():
    for text in ("0.01", "-98765.43", "12345678.90", "0.00"):
        value = Decimal(text)
        assert decode_packed(encode_packed(value, 6, 2), 2) == value


def test_encode_packed_can_fabricate_sign_fault():
    raw = encode_packed(Decimal("100.00"), 6, 2, sign_nibble=0x3)
    with pytest.raises(FieldDecodeError):
        decode_packed(raw, 2)


# --- zoned decimal (overpunch signs) ------------------------------------------


def test_zoned_ebcdic_signs():
    positive = bytes([0xF0, 0xF0, 0xF5, 0xF2, 0xC5])  # 00525, C-zone +5
    negative = bytes([0xF0, 0xF0, 0xF5, 0xF2, 0xD5])  # D-zone -> negative
    unsigned = bytes([0xF0, 0xF0, 0xF5, 0xF2, 0xF5])  # F-zone -> positive
    assert decode_zoned(positive, 4) == Decimal("0.0525")
    assert decode_zoned(negative, 4) == Decimal("-0.0525")
    assert decode_zoned(unsigned, 4) == Decimal("0.0525")


def test_zoned_ebcdic_invalid_zone_is_field_fault():
    with pytest.raises(FieldDecodeError, match="sign zone"):
        decode_zoned(bytes([0xF1, 0xA5]), 0)


def test_zoned_ascii_overpunch():
    assert decode_zoned(b"12E", 0, ebcdic=False) == Decimal("125")   # E -> +5
    assert decode_zoned(b"12N", 0, ebcdic=False) == Decimal("-125")  # N -> -5
    assert decode_zoned(b"12{", 0, ebcdic=False) == Decimal("120")   # { -> +0
    assert decode_zoned(b"12}", 0, ebcdic=False) == Decimal("-120")  # } -> -0
    assert decode_zoned(b"125", 0, ebcdic=False) == Decimal("125")   # plain +


def test_zoned_round_trip_both_flavors():
    for value in (Decimal("0.0525"), Decimal("-0.0525")):
        assert decode_zoned(encode_zoned(value, 6, 4), 4) == value
        assert decode_zoned(encode_zoned(value, 6, 4, ebcdic=False), 4,
                            ebcdic=False) == value


def test_binary_signed_big_endian():
    assert decode_binary(encode_binary(Decimal("-5.00"), 4, 2), 2) \
        == Decimal("-5.00")
    assert decode_binary((1043217).to_bytes(4, "big"), 2) == Decimal("10432.17")


# --- Appendix D.4 golden fixture ------------------------------------------------


def d4_layout() -> LayoutSpec:
    return LayoutSpec.model_validate(json.loads(
        (EBCDIC_FIXTURES / "omni-loans-v1.json").read_text(encoding="utf-8")))


def test_appendix_d4_golden_decode():
    parsed = ingest_fixed_width(EBCDIC_FIXTURES / "loans.dat", "loans", d4_layout())
    assert parsed.row_count == 2
    assert parsed.rejects == []
    first, second = parsed.rows
    assert first["plan_id"] == "PLN00001"
    assert first["participant_id"] == "P0042"
    assert first["outstanding_balance"] == Decimal("10432.17")
    assert first["origination_date"] == date(2024, 1, 15)
    assert first["rate"] == Decimal("0.0525")
    assert second["outstanding_balance"] == Decimal("-250.75")
    assert second["origination_date"] is None  # zeros -> null, never 0001-01-01
    assert any("zero/blank date" in a for a in parsed.annotations)
    # canonical columns not in the layout are filled null and annotated
    assert first["term_months"] is None
    assert any("absent from layout" in a for a in parsed.annotations)


# --- framing, faults, registration ----------------------------------------------


def test_short_record_quarantined(tmp_path):
    layout = d4_layout()
    good = (EBCDIC_FIXTURES / "loans.dat").read_bytes()
    (tmp_path / "loans.dat").write_bytes(good + b"\x40" * 100)  # short tail
    parsed = ingest_fixed_width(tmp_path / "loans.dat", "loans", layout)
    assert parsed.row_count == 2
    assert len(parsed.rejects) == 1
    assert "record length 100" in parsed.rejects[0].reason


def test_field_fault_annotates_and_continues(tmp_path):
    layout = d4_layout()
    data = bytearray((EBCDIC_FIXTURES / "loans.dat").read_bytes())
    data[29] = (data[29] & 0xF0) | 0x03  # corrupt record 1's packed sign nibble
    (tmp_path / "loans.dat").write_bytes(bytes(data))
    parsed = ingest_fixed_width(tmp_path / "loans.dat", "loans", layout)
    assert parsed.row_count == 2  # row kept (§10.5), field nulled
    assert parsed.rows[0]["outstanding_balance"] is None
    assert parsed.rows[1]["outstanding_balance"] == Decimal("-250.75")
    assert any("decode fault in 'outstanding_balance'" in a
               for a in parsed.annotations)


def test_newline_separated_text_fixed_width(tmp_path):
    layout = LayoutSpec.model_validate({
        "layout_id": "text-v1", "record_length": 12, "encoding": "ascii",
        "fields": [
            {"name": "plan_id", "start": 1, "length": 6, "type": "char"},
            {"name": "balance", "start": 7, "length": 6, "type": "zoned",
             "decimals": 2},
        ],
    })
    path = tmp_path / "balances.dat"
    # zoned 01000{ -> +10000 cents; 02502N -> -25025 cents
    path.write_bytes(b"PLN00101000{\nPLN00102502N\n")
    parsed = ingest_fixed_width(path, "balances", layout)
    assert parsed.row_count == 2
    assert parsed.rows[0]["balance"] == Decimal("100.00")
    assert parsed.rows[1]["balance"] == Decimal("-250.25")
    assert any("newline-separated" in a for a in parsed.annotations)


def test_registration_with_layout_records_layout_id(tmp_path):
    truth = build_truth("PLN-EBT-01")
    write_dat(tmp_path / "loans.dat", LOANS_LAYOUT, truth["loans"])
    result = register_dataset(
        tmp_path / "loans.dat", run_id="RUN-2026-07-05-0001", side="source",
        dataset_name="loans", layout=LOANS_LAYOUT,
    )
    assert result.registration.layout_id == "omni-loans-full-v1"
    assert result.registration.row_count == 6
    assert result.registration.content_hash.startswith("sha256:")


def test_ingestion_equivalence_dat_vs_csv(tmp_path):
    """Spec §25.4: the EBCDIC variant of the same truth decodes to the same
    typed rows the CSV variant parses to."""
    truth = build_truth("PLN-EQ-01")
    write_dat(tmp_path / "loans.dat", LOANS_LAYOUT, truth["loans"])
    write_dataset(tmp_path / "loans.csv", "loans", truth["loans"])
    from src.ingest.csv import ingest_csv
    dat_rows = ingest_fixed_width(tmp_path / "loans.dat", "loans",
                                  LOANS_LAYOUT).rows
    csv_rows = ingest_csv(tmp_path / "loans.csv", "loans").rows
    assert dat_rows == csv_rows
