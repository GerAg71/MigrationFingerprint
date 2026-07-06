"""derived_recompute executor tests (spec §11.2.4 unit-test spec): golden
amortization tables; vesting boundary years; payment-application order
sensitivity demonstrated."""

from decimal import Decimal

import pytest

from src.rules import ExecutionContext, UnsupportedRuleTypeError, execute
from src.rules.derived_recompute import (
    amortize_balance,
    simulate_level_payments,
    vested_pct,
)
from tests.conftest import make_datasets, make_rule

import pandas as pd
from src.rules.engine import RuleDatasets


# --- golden amortization table (hand-computed) --------------------------------
# 1000.00 at 12%/yr (1%/mo), 100.00 payments, interest-first:
#   p1: interest 10.00, principal 90.00 -> 910.00
#   p2: interest  9.10, principal 90.90 -> 819.10
#   p3: interest  8.19, principal 91.81 -> 727.29


def test_golden_amortization_table():
    totals = [Decimal("100.00")] * 3
    balance = amortize_balance(Decimal("1000.00"), Decimal("0.12"), totals)
    assert balance == Decimal("727.29")


def test_simulate_matches_amortize():
    schedule, balance = simulate_level_payments(
        Decimal("1000.00"), Decimal("0.12"), Decimal("100.00"), 3)
    assert schedule[0] == (Decimal("90.00"), Decimal("10.00"))
    assert schedule[2] == (Decimal("91.81"), Decimal("8.19"))
    assert balance == Decimal("727.29")
    totals = [p + i for p, i in schedule]
    assert amortize_balance(Decimal("1000.00"), Decimal("0.12"), totals) == balance


def test_payment_application_order_sensitivity():
    """Same history, different order -> different balances (the FM-001 story)."""
    totals = [Decimal("100.00")] * 3
    interest_first = amortize_balance(
        Decimal("1000.00"), Decimal("0.12"), totals, "interest_first")
    principal_first = amortize_balance(
        Decimal("1000.00"), Decimal("0.12"), totals, "principal_first")
    assert interest_first == Decimal("727.29")
    assert principal_first == Decimal("700.00")
    assert interest_first != principal_first


def test_half_even_rounding_per_period():
    # 1000.00 at 3%/yr -> monthly interest 2.50 exactly: half-even keeps 2.50
    schedule, _ = simulate_level_payments(
        Decimal("1000.00"), Decimal("0.03"), Decimal("50.00"), 1)
    assert schedule[0] == (Decimal("47.50"), Decimal("2.50"))


# --- vesting boundaries (spec §11.2.4 test spec) --------------------------------


@pytest.mark.parametrize("service,expected", [
    ("0", "0"), ("1.9", "0"),          # before the schedule starts
    ("2", "0.2"),                      # first graded step
    ("4.0", "0.6"), ("5.5", "0.8"),    # graded steps
    ("6", "1"), ("9.0", "1"),          # fully vested, capped
])
def test_graded6_boundaries(service, expected):
    assert vested_pct("GRADED6", Decimal(service)) == Decimal(expected)


def test_cliff3_boundaries():
    assert vested_pct("CLIFF3", Decimal("2.9")) == Decimal("0")
    assert vested_pct("CLIFF3", Decimal("3")) == Decimal("1")


def test_unknown_schedule_raises():
    with pytest.raises(ValueError, match="unknown vesting schedule"):
        vested_pct("MYSTERY9", Decimal("5"))


# --- executor end-to-end ---------------------------------------------------------


def vest_rule():
    return make_rule({
        "rule_id": "RULE-VEST-PCT-001", "type": "derived_recompute",
        "failure_mode": "FM-002",
        "source_dataset": "vesting", "target_dataset": "vesting",
        "join_keys": ["plan_id", "participant_id"],
        "params": {"recompute": "vested_pct",
                   "inputs": {"schedule": "plan.provisions.vesting",
                              "service": "vesting.service_years"},
                   "compare_field": "vested_pct", "tolerance": "0.0000"},
        "severity": "HIGH",
    })


def vest_row(pid="P0017", service="5.5", pct="0.8000"):
    return {"plan_id": "PLN001", "participant_id": pid,
            "schedule_id": "GRADED6", "service_years": Decimal(service),
            "vested_pct": Decimal(pct)}


def test_vested_pct_rule_trips_on_divergence():
    datasets = make_datasets("vesting", [vest_row()], [vest_row(pct="0.6000")])
    outcome = execute(vest_rule(), datasets)
    record = outcome.affected[0]
    assert record.source == {"vested_pct_recomputed": "0.8"}
    assert record.target == {"vested_pct": "0.6000"}
    assert record.delta == Decimal("-0.2000")


def test_vested_pct_rule_passes_when_consistent():
    datasets = make_datasets("vesting", [vest_row()], [vest_row()])
    assert execute(vest_rule(), datasets).passed


def loan_rule():
    return make_rule({
        "rule_id": "RULE-LOAN-RECOMP-001", "type": "derived_recompute",
        "failure_mode": "FM-001",
        "source_dataset": "loans", "target_dataset": "loans",
        "join_keys": ["plan_id", "participant_id", "loan_id"],
        "params": {"recompute": "loan_balance",
                   "inputs": {"origination_amount": "loans.origination_amount",
                              "rate": "loans.rate",
                              "term_months": "loans.term_months",
                              "payments": "loan_payments"},
                   "compare_field": "outstanding_balance", "tolerance": "0.00"},
        "severity": "HIGH",
    })


def loan_datasets(target_outstanding: str) -> RuleDatasets:
    loan = {"plan_id": "PLN001", "participant_id": "P0001", "loan_id": "L1",
            "origination_amount": Decimal("1000.00"), "rate": Decimal("0.12"),
            "term_months": 12, "outstanding_balance": Decimal("727.29")}
    target = dict(loan, outstanding_balance=Decimal(target_outstanding))
    payments = [
        {"plan_id": "PLN001", "participant_id": "P0001", "loan_id": "L1",
         "payment_date": f"2026-0{k}-15",
         "principal": p, "interest": i}
        for k, (p, i) in enumerate([
            (Decimal("90.00"), Decimal("10.00")),
            (Decimal("90.90"), Decimal("9.10")),
            (Decimal("91.81"), Decimal("8.19")),
        ], start=1)
    ]
    return RuleDatasets(
        source={"loans": pd.DataFrame([loan], dtype=object),
                "loan_payments": pd.DataFrame(payments, dtype=object)},
        target={"loans": pd.DataFrame([target], dtype=object)},
    )


def test_loan_balance_rule_passes_on_consistent_history():
    assert execute(loan_rule(), loan_datasets("727.29")).passed


def test_loan_balance_rule_trips_on_carryover_defect():
    outcome = execute(loan_rule(), loan_datasets("693.67"))  # -33.62
    record = outcome.affected[0]
    assert record.source == {"outstanding_balance_recomputed": "727.29"}
    assert record.delta == Decimal("-33.62")


def test_missing_payments_dataset_raises():
    datasets = loan_datasets("727.29")
    del datasets.source["loan_payments"]
    with pytest.raises(ValueError, match="loan_payments"):
        execute(loan_rule(), datasets)


def test_unknown_recomputer_is_skippable():
    rule = make_rule({
        "rule_id": "RULE-FUTURE-001", "type": "derived_recompute",
        "failure_mode": "FM-006",
        "source_dataset": "loans", "target_dataset": "loans",
        "join_keys": ["plan_id", "participant_id", "loan_id"],
        "params": {"recompute": "quantum_flux_total", "inputs": {},
                   "compare_field": "outstanding_balance", "tolerance": "0.00"},
        "severity": "HIGH",
    })
    with pytest.raises(UnsupportedRuleTypeError, match="quantum_flux_total"):
        execute(rule, loan_datasets("727.29"))


# --- packed_decode_control_total (FM-006, MS-2.2) --------------------------------


def packed_rule():
    return make_rule({
        "rule_id": "RULE-PACKED-001", "type": "derived_recompute",
        "failure_mode": "FM-006",
        "source_dataset": "loans", "target_dataset": "loans",
        "join_keys": ["plan_id", "participant_id", "loan_id"],
        "params": {"recompute": "packed_decode_control_total",
                   "inputs": {"layout": "omni-loans-v1",
                              "control_field": "outstanding_balance"},
                   "compare_field": "outstanding_balance", "tolerance": "0.00"},
        "severity": "HIGH",
    })


def packed_datasets(source_balances, target_balances):
    def rows(balances):
        return [{"plan_id": "PLN001", "participant_id": f"P{i:04d}",
                 "loan_id": f"L{i}", "outstanding_balance": Decimal(b)}
                for i, b in enumerate(balances, start=1)]
    return make_datasets("loans", rows(source_balances), rows(target_balances))


def test_packed_flags_implied_decimal_shift_x100():
    outcome = execute(packed_rule(),
                      packed_datasets(["13775.62"], ["1377562.00"]))
    record = outcome.affected[0]
    assert record.target["_check"] == "implied_decimal_shift:x100"
    assert record.delta == Decimal("1363786.38")
    assert outcome.detail["control_total"]["source"] == "13775.62"
    assert outcome.detail["control_total"]["target"] == "1377562.00"


def test_packed_flags_shrink_and_x10000():
    shrunk = execute(packed_rule(), packed_datasets(["13775.62"], ["137.7562"]))
    assert shrunk.affected[0].target["_check"] == "implied_decimal_shift:/100"
    wide = execute(packed_rule(),
                   packed_datasets(["137.7562"], ["1377562.0000"]))
    assert wide.affected[0].target["_check"] == "implied_decimal_shift:x10000"


def test_packed_flags_sign_flip():
    outcome = execute(packed_rule(), packed_datasets(["4102.33"], ["-4102.33"]))
    assert outcome.affected[0].target["_check"] == "sign_flip"


def test_packed_ignores_ordinary_variance():
    """Generic deltas are field_compare's finding, not a decode signature."""
    outcome = execute(packed_rule(), packed_datasets(["10432.17"], ["10398.55"]))
    assert outcome.passed


def test_packed_passes_on_equal_values():
    outcome = execute(packed_rule(), packed_datasets(["10432.17"], ["10432.17"]))
    assert outcome.passed
    assert outcome.detail is None
