"""format_conformance rule type (Omni->Omni restore use case): Picture
semantics, Required flags, Not-Used fillers, domains, and side selection."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.rules.engine import execute
from src.rules.format_conformance import picture_violation
from tests.conftest import make_datasets, make_rule


def conformance_rule(fields, side="target", dataset="participants",
                     **overrides):
    payload = {
        "rule_id": "RULE-FMT-T-001",
        "failure_mode": "FM-103",
        "type": "format_conformance",
        "target_dataset": dataset,
        "severity": "MEDIUM",
        "params": {"side": side, "fields": fields},
    }
    if side == "source":
        payload["source_dataset"] = dataset
    payload.update(overrides)
    return make_rule(payload)


ROW = {"plan_id": "PLN001", "participant_id": "P0001", "ssn": "900441207",
       "status": "ACTIVE", "state": "IL"}


# --- picture semantics --------------------------------------------------------


@pytest.mark.parametrize("value,picture,reason", [
    ("ABC", "X(3)", None),
    ("ABCD", "X(3)", "length_4_exceeds_X(3)"),
    ("A", "X", None),
    ("900441207", "9(9)", None),
    ("9004412A7", "9(9)", "non_numeric_in_9(9)"),
    ("1234567890", "9(9)", "integer_10_digits_exceed_9(9)"),
    (Decimal("1234.56"), "9(5)V99", None),
    (Decimal("1234.567"), "9(5)V99", "fraction_3dp_exceeds_9(5)V99"),
    (Decimal("123456.78"), "9(5)V99", "integer_6_digits_exceed_9(5)V99"),
    (Decimal("-10.00"), "9(5)V99", "negative_in_unsigned_9(5)V99"),
    (Decimal("-10.00"), "S9(5)V99", None),
    (Decimal("0.055"), "9(2)V9(3)", None),
    (date(2026, 6, 30), "9(8)", "date_in_numeric_9(8)"),
    (date(2026, 6, 30), "X(10)", None),
])
def test_picture_violations(value, picture, reason):
    assert picture_violation(value, picture) == reason


# --- executor: fillers, required, domain --------------------------------------


def test_data_in_unused_position_is_off_label():
    """The fixture that trips it (REQ-023): a 'Not Used' filler carrying
    data on the target — the classic repurposing signal."""
    rule = conformance_rule([{"field": "filler_442_448", "must_be_blank": True}])
    datasets = make_datasets("participants", [ROW], [
        dict(ROW, filler_442_448="BR-EAST"),
        dict(ROW, participant_id="P0002", filler_442_448=""),
        dict(ROW, participant_id="P0003"),  # column absent entirely
    ])
    outcome = execute(rule, datasets)
    assert outcome.records_affected == 1
    record = outcome.affected[0]
    assert record.keys["participant_id"] == "P0001"
    assert record.target["_check"] == "data_in_unused_position"
    assert record.target["filler_442_448"] == "BR-EAST"
    assert outcome.detail == {"off_label": 1}


def test_required_field_blank_after_restore():
    rule = conformance_rule([{"field": "dob", "required": True}])
    datasets = make_datasets("participants", [ROW], [
        dict(ROW, dob=None),
        dict(ROW, participant_id="P0002", dob=date(1980, 1, 15)),
    ])
    outcome = execute(rule, datasets)
    assert outcome.records_affected == 1
    assert outcome.affected[0].target["_check"] == "required_field_blank"


def test_picture_and_domain_checks_on_populated_values():
    rule = conformance_rule([
        {"field": "ssn", "picture": "9(9)", "required": True},
        {"field": "status", "domain": ["ACTIVE", "TERMINATED"]},
    ])
    datasets = make_datasets("participants", [ROW], [
        dict(ROW, ssn="9004412A7"),
        dict(ROW, participant_id="P0002", status="FROZEN"),
        dict(ROW, participant_id="P0003"),
    ])
    outcome = execute(rule, datasets)
    checks = {r.keys["participant_id"]: r.target["_check"]
              for r in outcome.affected}
    assert checks == {"P0001": "non_numeric_in_9(9)",
                      "P0002": "outside_domain"}


def test_side_source_profiles_the_pre_cutover_extract():
    """Pass A of the restore workflow: conformance against the SOURCE."""
    rule = conformance_rule([{"field": "state", "picture": "X(2)"}],
                            side="source")
    datasets = make_datasets("participants",
                            [dict(ROW, state="ILL")], [ROW])
    outcome = execute(rule, datasets)
    assert outcome.records_affected == 1
    assert outcome.affected[0].source["_check"] == "length_3_exceeds_X(2)"
    assert outcome.affected[0].target is None


def test_clean_dataset_passes():
    rule = conformance_rule([
        {"field": "ssn", "picture": "9(9)", "required": True},
        {"field": "filler_442_448", "must_be_blank": True},
    ])
    datasets = make_datasets("participants", [ROW], [ROW])
    assert execute(rule, datasets).passed


# --- schema guards -------------------------------------------------------------


def test_field_needs_an_expectation():
    with pytest.raises(ValidationError, match="must declare"):
        conformance_rule([{"field": "ssn"}])


def test_must_be_blank_excludes_other_expectations():
    with pytest.raises(ValidationError, match="excludes"):
        conformance_rule([{"field": "x", "must_be_blank": True,
                           "required": True}])


def test_invalid_picture_rejected():
    with pytest.raises(ValidationError, match="pattern"):
        conformance_rule([{"field": "ssn", "picture": "Z(9)"}])


def test_source_side_requires_source_dataset():
    with pytest.raises(ValidationError, match="requires source_dataset"):
        make_rule({
            "rule_id": "RULE-FMT-T-002", "failure_mode": "FM-103",
            "type": "format_conformance", "target_dataset": "participants",
            "severity": "LOW",
            "params": {"side": "source",
                       "fields": [{"field": "ssn", "required": True}]},
        })