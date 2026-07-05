"""field_compare executor tests (spec §11.2.1 unit-test spec): exact match
passes; 0.01 variance fails at tolerance 0.00; tolerance honored; validity
fires on nulls, over-length, bad pattern, out-of-range."""

from datetime import date
from decimal import Decimal

import pytest

from src.rules import ExecutionContext, execute
from tests.conftest import make_datasets, make_rule


def loan_rule(tolerance="0.00"):
    return make_rule({
        "rule_id": "RULE-LOAN-BAL-001", "type": "field_compare",
        "failure_mode": "FM-001",
        "source_dataset": "loans", "target_dataset": "loans",
        "join_keys": ["plan_id", "participant_id", "loan_id"],
        "params": {"compare": [
            {"field": "outstanding_balance", "kind": "money", "tolerance": tolerance}
        ]},
        "severity": "HIGH",
    })


def loan_row(participant="P0001", loan="L1", balance="100.00"):
    return {
        "plan_id": "PLN001", "participant_id": participant, "loan_id": loan,
        "outstanding_balance": Decimal(balance) if balance is not None else None,
    }


def test_exact_match_passes():
    datasets = make_datasets("loans", [loan_row()], [loan_row()])
    outcome = execute(loan_rule(), datasets)
    assert outcome.passed
    assert outcome.affected == []


def test_penny_variance_fails_at_tolerance_zero():
    datasets = make_datasets("loans",
                             [loan_row(balance="100.00")],
                             [loan_row(balance="99.99")])
    outcome = execute(loan_rule(), datasets)
    assert not outcome.passed
    record = outcome.affected[0]
    assert record.keys == {"plan_id": "PLN001", "participant_id": "P0001",
                           "loan_id": "L1"}
    assert record.source == {"outstanding_balance": "100.00"}
    assert record.target == {"outstanding_balance": "99.99"}
    assert record.delta == Decimal("-0.01")


def test_tolerance_honored():
    within = make_datasets("loans", [loan_row(balance="100.00")],
                           [loan_row(balance="100.03")])
    beyond = make_datasets("loans", [loan_row(balance="100.00")],
                           [loan_row(balance="100.06")])
    assert execute(loan_rule(tolerance="0.05"), within).passed
    assert not execute(loan_rule(tolerance="0.05"), beyond).passed


def test_text_field_mismatch():
    rule = make_rule({
        "rule_id": "RULE-VEST-SCHED-001", "type": "field_compare",
        "failure_mode": "FM-002",
        "source_dataset": "vesting", "target_dataset": "vesting",
        "join_keys": ["plan_id", "participant_id"],
        "params": {"compare": [{"field": "schedule_id", "kind": "text"}]},
        "severity": "MEDIUM",
    })
    datasets = make_datasets(
        "vesting",
        [{"plan_id": "PLN001", "participant_id": "P0001", "schedule_id": "GRADED6"}],
        [{"plan_id": "PLN001", "participant_id": "P0001", "schedule_id": "CLIFF3"}],
    )
    outcome = execute(rule, datasets)
    assert outcome.affected[0].source == {"schedule_id": "GRADED6"}
    assert outcome.affected[0].target == {"schedule_id": "CLIFF3"}
    assert outcome.affected[0].delta is None


def date_rule():
    return make_rule({
        "rule_id": "RULE-DATE-001", "type": "field_compare",
        "failure_mode": "FM-008",
        "source_dataset": "participants", "target_dataset": "participants",
        "join_keys": ["plan_id", "participant_id"],
        "params": {"compare": [{"field": "dob", "kind": "date"}]},
        "severity": "MEDIUM",
    })


def test_date_mismatch_reported_iso():
    datasets = make_datasets(
        "participants",
        [{"plan_id": "PLN001", "participant_id": "P0001", "dob": date(1980, 3, 12)}],
        [{"plan_id": "PLN001", "participant_id": "P0001", "dob": date(1880, 3, 12)}],
    )
    record = execute(date_rule(), datasets).affected[0]
    assert record.source == {"dob": "1980-03-12"}
    assert record.target == {"dob": "1880-03-12"}


def test_null_on_one_side_is_mismatch_both_null_equal():
    one_null = make_datasets(
        "participants",
        [{"plan_id": "PLN001", "participant_id": "P0001", "dob": date(1980, 1, 1)}],
        [{"plan_id": "PLN001", "participant_id": "P0001", "dob": None}],
    )
    both_null = make_datasets(
        "participants",
        [{"plan_id": "PLN001", "participant_id": "P0001", "dob": None}],
        [{"plan_id": "PLN001", "participant_id": "P0001", "dob": None}],
    )
    assert not execute(date_rule(), one_null).passed
    assert execute(date_rule(), both_null).passed


def test_unmatched_rows_are_not_compared():
    """Orphans belong to referential (§11.2.1); only matched rows compare."""
    datasets = make_datasets("loans",
                             [loan_row(loan="L1"), loan_row(loan="L2")],
                             [loan_row(loan="L1")])
    assert execute(loan_rule(), datasets).passed


def test_null_join_key_rows_skipped():
    datasets = make_datasets("loans",
                             [loan_row() | {"loan_id": None}],
                             [loan_row() | {"loan_id": None}])
    assert execute(loan_rule(), datasets).passed


# --- validity block ----------------------------------------------------------


def validity_rule(checks):
    return make_rule({
        "rule_id": "RULE-VALID-001", "type": "field_compare",
        "failure_mode": "FM-010",
        "target_dataset": "participants",
        "params": {"validity": checks},
        "severity": "HIGH",
    })


def participant(**overrides):
    row = {"plan_id": "PLN001", "participant_id": "P0001",
           "ssn": "900441207", "address_1": "12 Elm St",
           "dob": date(1980, 1, 1), "hire_date": date(2015, 5, 1),
           "term_date": None}
    row.update(overrides)
    return row


def test_not_null_fires_on_null_with_dataset_keys():
    rule = validity_rule([{"field": "ssn", "not_null": True}])
    datasets = make_datasets("participants", [], [participant(ssn=None)])
    record = execute(rule, datasets).affected[0]
    assert record.keys == {"plan_id": "PLN001", "participant_id": "P0001"}
    assert record.target == {"ssn": None, "_check": "not_null"}
    assert record.source is None


def test_max_length_violation():
    rule = validity_rule([{"field": "address_1", "max_length": 35}])
    long_addr = "1234 Extremely Long Boulevard Apt 41B"  # 37 chars
    datasets = make_datasets("participants", [], [participant(address_1=long_addr)])
    record = execute(rule, datasets).affected[0]
    assert record.target["_check"] == "max_length:35"


def test_pattern_violation():
    rule = validity_rule([{"field": "ssn", "pattern": "^[0-9]{9}$"}])
    datasets = make_datasets("participants", [], [participant(ssn="90044-120")])
    assert execute(rule, datasets).affected[0].target["_check"] == "pattern:^[0-9]{9}$"


def test_min_bound_on_money():
    rule = make_rule({
        "rule_id": "RULE-NEG-001", "type": "field_compare",
        "failure_mode": "FM-018", "target_dataset": "balances",
        "params": {"validity": [{"field": "balance", "min": "0.00"}]},
        "severity": "HIGH",
    })
    datasets = make_datasets("balances", [], [{
        "plan_id": "PLN001", "participant_id": "P0001",
        "money_type_code": "MATCH", "investment_code": "F01",
        "balance": Decimal("-412.06"),
    }])
    record = execute(rule, datasets).affected[0]
    assert record.target == {"balance": "-412.06", "_check": "min:0.00"}


def test_max_today_resolved_from_context():
    rule = validity_rule([{"field": "dob", "max": "today"}])
    datasets = make_datasets("participants", [], [participant(dob=date(2030, 1, 1))])
    context = ExecutionContext(as_of=date(2026, 7, 5))
    assert not execute(rule, datasets, context).passed
    ok = make_datasets("participants", [], [participant(dob=date(1980, 1, 1))])
    assert execute(rule, datasets=ok, context=context).passed


def test_max_today_without_as_of_raises():
    rule = validity_rule([{"field": "dob", "max": "today"}])
    datasets = make_datasets("participants", [], [participant()])
    with pytest.raises(ValueError, match="as_of"):
        execute(rule, datasets)


def test_gte_field_cross_field_violation():
    rule = validity_rule([{"field": "term_date", "gte_field": "hire_date"}])
    bad = make_datasets("participants", [], [participant(
        term_date=date(2019, 5, 1), hire_date=date(2021, 3, 15))])
    good = make_datasets("participants", [], [participant(
        term_date=date(2022, 5, 1), hire_date=date(2021, 3, 15))])
    record = execute(rule, bad).affected[0]
    assert record.target["_check"] == "gte_field:hire_date"
    assert execute(rule, good).passed
