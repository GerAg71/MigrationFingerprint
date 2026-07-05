"""count_balance executor tests (spec §11.2.2 unit-test spec): matching
totals pass; a single moved penny is caught; drill-down includes exactly the
contributing groups."""

from decimal import Decimal

import pytest

from src.rules import execute
from tests.conftest import make_datasets, make_rule


def totals_rule():
    """FM-007 shape: plan-level sum + count, participant-level sum."""
    return make_rule({
        "rule_id": "RULE-BAL-TOTALS-001", "type": "count_balance",
        "failure_mode": "FM-007",
        "source_dataset": "balances", "target_dataset": "balances",
        "params": {"aggregations": [
            {"measure": "balance", "op": "sum", "group_by": ["plan_id"]},
            {"measure": "*", "op": "count", "group_by": ["plan_id"]},
            {"measure": "balance", "op": "sum",
             "group_by": ["plan_id", "participant_id"]},
        ]},
        "severity": "CRITICAL",
    })


def balance(participant, amount, money_type="PRETAX"):
    return {"plan_id": "PLN001", "participant_id": participant,
            "money_type_code": money_type, "investment_code": "F01",
            "balance": Decimal(amount)}


def test_matching_totals_pass():
    rows = [balance("P0001", "100.00"), balance("P0002", "250.50")]
    outcome = execute(totals_rule(), make_datasets("balances", rows, list(rows)))
    assert outcome.passed
    assert outcome.detail is None


def test_single_moved_penny_caught_with_exact_drilldown():
    source = [balance("P0001", "100.00"), balance("P0002", "250.50")]
    target = [balance("P0001", "100.00"), balance("P0002", "250.49")]  # 1 penny
    outcome = execute(totals_rule(), make_datasets("balances", source, target))
    assert not outcome.passed

    by_keys = {tuple(sorted(r.keys.items())): r for r in outcome.affected}
    plan_level = by_keys[(("plan_id", "PLN001"),)]
    assert plan_level.source == {"sum(balance)": "350.50"}
    assert plan_level.target == {"sum(balance)": "350.49"}
    assert plan_level.delta == Decimal("-0.01")

    participant_level = by_keys[(("participant_id", "P0002"), ("plan_id", "PLN001"))]
    assert participant_level.delta == Decimal("-0.01")

    # drill-down behind the plan variance names exactly the contributing group
    drill = outcome.detail["drill_down"]
    assert len(drill) == 1
    assert drill[0]["group"] == {"plan_id": "PLN001"}
    assert drill[0]["finer_level"] == ["plan_id", "participant_id"]
    contributing = drill[0]["contributing"]
    assert len(contributing) == 1
    assert contributing[0]["participant_id"] == "P0002"
    assert contributing[0]["delta"] == "-0.01"


def test_count_variance_from_missing_row():
    source = [balance("P0001", "100.00"), balance("P0002", "250.50")]
    target = [balance("P0001", "100.00")]
    outcome = execute(totals_rule(), make_datasets("balances", source, target))
    count_records = [r for r in outcome.affected if "count(*)" in (r.source or {})]
    assert count_records[0].source == {"count(*)": "2"}
    assert count_records[0].target == {"count(*)": "1"}
    assert count_records[0].delta == Decimal("-1")


def money_type_rule():
    return make_rule({
        "rule_id": "RULE-BAL-MT-001", "type": "count_balance",
        "failure_mode": "FM-012",
        "source_dataset": "balances", "target_dataset": "balances",
        "params": {"aggregations": [
            {"measure": "balance", "op": "sum",
             "group_by": ["plan_id", "money_type_code"]},
        ]},
        "severity": "CRITICAL",
    })


def test_group_missing_on_one_side_compares_against_zero():
    source = [balance("P0001", "100.00", "PRETAX"),
              balance("P0001", "50.00", "ROTH")]
    target = [balance("P0001", "100.00", "PRETAX")]  # ROTH bucket dropped
    outcome = execute(money_type_rule(), make_datasets("balances", source, target))
    record = outcome.affected[0]
    assert record.keys == {"plan_id": "PLN001", "money_type_code": "ROTH"}
    assert record.source == {"sum(balance)": "50.00"}
    assert record.target == {"sum(balance)": "0"}
    assert record.delta == Decimal("-50.00")


def test_offsetting_subtotal_variance_caught_though_plan_total_reconciles():
    """The FM-012 signature: plan total matches, money-type subtotals do not."""
    source = [balance("P0001", "100.00", "PRETAX"),
              balance("P0001", "100.00", "ROTH")]
    target = [balance("P0001", "150.00", "PRETAX"),
              balance("P0001", "50.00", "ROTH")]
    outcome = execute(money_type_rule(), make_datasets("balances", source, target))
    deltas = {r.keys["money_type_code"]: r.delta for r in outcome.affected}
    assert deltas == {"PRETAX": Decimal("50.00"), "ROTH": Decimal("-50.00")}


def contribution(participant, amount, period):
    return {"plan_id": "PLN001", "participant_id": participant,
            "money_type_code": "MATCH", "period": period,
            "amount": Decimal(amount)}


def contrib_rule(filter_value):
    return make_rule({
        "rule_id": "RULE-CONTRIB-001", "type": "count_balance",
        "failure_mode": "FM-015",
        "source_dataset": "contributions", "target_dataset": "contributions",
        "params": {
            "aggregations": [{"measure": "amount", "op": "sum",
                              "group_by": ["plan_id", "money_type_code"]}],
            "filter": {"period": filter_value},
        },
        "severity": "HIGH",
    })


def test_filter_literal_restricts_rows():
    source = [contribution("P0001", "10.00", "2026-05"),
              contribution("P0001", "20.00", "2026-06")]
    target = [contribution("P0001", "99.00", "2026-05"),  # variance outside filter
              contribution("P0001", "20.00", "2026-06")]
    outcome = execute(contrib_rule("2026-06"),
                      make_datasets("contributions", source, target))
    assert outcome.passed


def test_filter_symbolic_last_payroll_cycle_resolves_to_max_period():
    source = [contribution("P0001", "10.00", "2026-05"),
              contribution("P0001", "20.00", "2026-06")]
    target = [contribution("P0001", "10.00", "2026-05"),
              contribution("P0001", "25.00", "2026-06")]  # variance in latest
    outcome = execute(contrib_rule("last_payroll_cycle"),
                      make_datasets("contributions", source, target))
    assert not outcome.passed
    assert outcome.affected[0].delta == Decimal("5.00")


def test_sums_are_decimal_exact():
    """0.10 + 0.20 == 0.30 exactly — the float trap this engine must not have."""
    source = [balance("P0001", "0.10"), balance("P0002", "0.20")]
    target = [balance("P0003", "0.30")]
    rule = make_rule({
        "rule_id": "RULE-BAL-PLAN-001", "type": "count_balance",
        "failure_mode": "FM-007",
        "source_dataset": "balances", "target_dataset": "balances",
        "params": {"aggregations": [
            {"measure": "balance", "op": "sum", "group_by": ["plan_id"]},
        ]},
        "severity": "CRITICAL",
    })
    assert execute(rule, make_datasets("balances", source, target)).passed


def test_non_decimal_money_reaching_engine_is_an_error():
    rows_bad = [{"plan_id": "PLN001", "participant_id": "P0001",
                 "money_type_code": "PRETAX", "investment_code": "F01",
                 "balance": 100.0}]  # float smuggled in
    rule = money_type_rule()
    with pytest.raises(TypeError, match="REQ-017"):
        execute(rule, make_datasets("balances", rows_bad, rows_bad))
