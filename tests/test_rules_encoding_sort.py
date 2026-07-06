"""encoding_check + sort_order_check executor tests (spec §11.2.5–11.2.6):
seeded JosÃ© caught, clean Jose passes, custom allowed-set honored;
digit-vs-letter ordering difference between EBCDIC and ASCII detected."""

from src.rules import execute
from tests.conftest import make_datasets, make_rule


def participant(pid, first="Jose", last="Ramirez", city="Springfield"):
    return {"plan_id": "PLN001", "participant_id": pid,
            "first_name": first, "last_name": last, "city": city}


def enc_rule(allowed="ascii", custom_set=None, fields=None):
    params = {"fields": fields or ["first_name", "last_name", "city"],
              "allowed": allowed}
    if custom_set is not None:
        params["custom_set"] = custom_set
    return make_rule({
        "rule_id": "RULE-ENC-001", "type": "encoding_check",
        "failure_mode": "FM-005", "target_dataset": "participants",
        "params": params, "severity": "MEDIUM",
    })


def test_mojibake_jose_caught():
    datasets = make_datasets("participants", [],
                             [participant("P0001", first="JosÃ©")])
    outcome = execute(enc_rule(), datasets)
    record = outcome.affected[0]
    assert record.target["first_name"] == "JosÃ©"
    assert "chars_outside_ascii" in record.target["_check"]
    assert "mojibake_signature" in record.target["_check"]


def test_clean_jose_passes():
    datasets = make_datasets("participants", [], [participant("P0001")])
    assert execute(enc_rule(), datasets).passed


def test_latin1_allows_accents_but_flags_mojibake():
    proper = make_datasets("participants", [], [participant("P0001", first="José")])
    garbled = make_datasets("participants", [], [participant("P0002", first="JosÃ©")])
    assert execute(enc_rule(allowed="latin1"), proper).passed
    outcome = execute(enc_rule(allowed="latin1"), garbled)
    assert outcome.affected[0].target["_check"] == "mojibake_signature"


def test_replacement_char_flagged():
    datasets = make_datasets("participants", [],
                             [participant("P0001", last="Ram�rez")])
    outcome = execute(enc_rule(allowed="latin1"), datasets)
    assert "mojibake_signature" in outcome.affected[0].target["_check"]


def test_custom_allowed_set_honored():
    rule = enc_rule(allowed="custom-set", custom_set="A-Za-z '.,-",
                    fields=["first_name", "last_name"])
    clean = make_datasets("participants", [], [participant("P0001", last="O'Neil-Ray")])
    hashed = make_datasets("participants", [], [participant("P0002", first="Ha#nk")])
    assert execute(rule, clean).passed
    outcome = execute(rule, hashed)
    assert "chars_outside_custom-set:#" in outcome.affected[0].target["_check"]


# --- sort_order_check ----------------------------------------------------------


def sort_rule(collation):
    return make_rule({
        "rule_id": "RULE-SORT-001", "type": "sort_order_check",
        "failure_mode": "FM-005", "target_dataset": "participants",
        "params": {"order_by": ["last_name", "first_name"],
                   "collation": collation},
        "severity": "LOW",
    })


EBCDIC_ORDERED = [  # letters first, digit-leading name last (EBCDIC collation)
    participant("P0002", first="Ana", last="Adams"),
    participant("P0003", first="Ben", last="Brown"),
    participant("P0004", first="Zoe", last="Zink"),
    participant("P0001", first="Drew", last="2Baker"),
]


def test_digit_letter_collation_difference_detected():
    """The same file passes under EBCDIC and trips ASCII at the boundary."""
    datasets = make_datasets("participants", [], list(EBCDIC_ORDERED))
    assert execute(sort_rule("ebcdic"), datasets).passed
    outcome = execute(sort_rule("ascii"), datasets)
    assert outcome.records_affected == 1
    record = outcome.affected[0]
    assert record.keys["participant_id"] == "P0001"
    assert record.target["_check"] == "out_of_order:ascii"
    assert record.target["position"] == "3"
    assert record.target["value"] == "2Baker | Drew"
    assert record.target["previous"] == "Zink | Zoe"


def test_ascii_sorted_file_passes_ascii():
    rows = sorted(EBCDIC_ORDERED, key=lambda r: (r["last_name"], r["first_name"]))
    datasets = make_datasets("participants", [], rows)
    assert execute(sort_rule("ascii"), datasets).passed


def test_each_inversion_boundary_reported():
    rows = [
        participant("P0001", last="Meyer"),
        participant("P0002", last="Adams"),   # boundary 1
        participant("P0003", last="Silva"),
        participant("P0004", last="Brown"),   # boundary 2
    ]
    outcome = execute(sort_rule("ascii"), make_datasets("participants", [], rows))
    assert outcome.records_affected == 2
    assert [r.target["position"] for r in outcome.affected] == ["1", "3"]
