"""Format Matrix compiler (Omni->Omni restore): compiles the real workbook
in docs/ into card layouts and stamped COBOL decks, deterministically, and
reports the matrix's own internal defects instead of hiding them."""

import json

import pytest

from src.ingest.matrix import (
    MatrixError,
    compile_matrix,
    stamp_deck,
    write_artifacts,
)
from tests.conftest import REPO

WORKBOOK = REPO / "docs" / "Omni_Format_Matrix_Complete.xlsx"


@pytest.fixture(scope="module")
def result():
    return compile_matrix(WORKBOOK)


def test_full_inventory(result):
    """The complete matrix: 15 processes, 53 cards, 710 field rows (one
    workbook row is an embedded [NOTE] annotation, not a field)."""
    assert len(result.layouts) == 53
    assert len({l.process for l in result.layouts}) == 15
    assert sum(len(l.fields) for l in result.layouts) == 710
    assert len(result.notes) == 1
    assert "T385/01" in result.notes[0]


def test_fillers_are_materialized_as_named_fields(result):
    """'Not Used' positions become real fields - the off-label probe
    surface. Names encode their positions."""
    t600 = next(l for l in result.layouts if l.card == "T600/00")
    fillers = [f for f in t600.fields if f.filler]
    assert fillers, "T600/00 has Not-Used positions"
    assert fillers[0].name == f"filler_{fillers[0].start:03d}_{fillers[0].end:03d}"
    total_fillers = sum(1 for l in result.layouts for f in l.fields if f.filler)
    assert total_fillers == 160


def test_required_flags_and_pictures_carry_through(result):
    t600 = next(l for l in result.layouts if l.card == "T600/00")
    by_name = {f.name: f for f in t600.fields}
    assert by_name["tran_code"].required
    assert by_name["tran_code"].picture == "X(3)"
    assert by_name["plan_number"].length == 6
    assert by_name["plan_number"].start == 16


def test_length_vs_columns_defects_are_reported_not_hidden(result):
    """The workbook itself contains rows where Length disagrees with the
    column span. The compiler trusts positions and reports every case."""
    assert len(result.discrepancies) == 15
    assert any("row 133 card T701/00" in d for d in result.discrepancies)
    # positions won: the T701/00 filler at 65-80 is 16 long, not 15
    t701 = next(l for l in result.layouts if l.card == "T701/00")
    filler = next(f for f in t701.fields if f.start == 65)
    assert filler.length == 16


def test_field_names_are_valid_identifiers(result):
    for layout in result.layouts:
        for f in layout.fields:
            assert f.name[0].isalpha() or f.name[0] == "_", (layout.card, f.name)
            names = [x.name for x in layout.fields]
            assert len(names) == len(set(names)), f"dupes in {layout.card}"


def test_deck_stamping_is_deterministic_cobol(result):
    t384 = next(l for l in result.layouts if l.card == "T384/01")
    deck = stamp_deck(t384)
    assert deck == stamp_deck(t384)  # pure templating
    assert "01  T384-01-REC." in deck
    assert "PIC 9(7)V99" in deck            # implied-decimal money field
    assert "MOVE SPACES TO FILLER-006-008" in deck
    assert "F-1STPYMT" in deck              # digit-leading label sanitized
    assert "<source-field>" in deck         # the engagement fills these in


def test_artifacts_round_trip(tmp_path, result):
    manifest = write_artifacts(result, tmp_path, decks=True)
    cards = list((tmp_path / "cards").glob("*.json"))
    decks = list((tmp_path / "decks").glob("*.cbl"))
    assert len(cards) == 53 and len(decks) == 53
    assert manifest["totals"] == {
        "processes": 15, "cards": 53, "fields": 710,
        "required_fields": 182, "filler_fields": 160,
    }
    payload = json.loads((tmp_path / "cards" / "T600-00.json")
                         .read_text(encoding="utf-8"))
    assert payload["record_length"] == 80
    assert payload["fields"][0]["name"] == "tran_code"


def test_wrong_workbook_shape_is_refused(tmp_path):
    import zipfile
    bogus = tmp_path / "bogus.xlsx"
    with zipfile.ZipFile(bogus, "w") as zf:
        zf.writestr("xl/worksheets/sheet1.xml",
                    '<worksheet xmlns="http://schemas.openxmlformats.org/'
                    'spreadsheetml/2006/main"><sheetData/></worksheet>')
    with pytest.raises(MatrixError, match="unexpected header"):
        compile_matrix(bogus)


def test_cli_compile_matrix(tmp_path, capsys):
    from src.cli import main

    rc = main(["compile-matrix", str(WORKBOOK), "--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "15 processes, 53 cards, 710 fields" in out
    assert "160 'Not Used' fillers materialized" in out
    assert out.count("WARNING:") == 15