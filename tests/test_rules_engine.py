"""Engine tests (spec §11.1, §11.3): executor dispatch, uniform finding
construction with the 25-sample cap, pass entries (REQ-024), determinism
(REQ-009), and the ingest -> DataFrame -> rule end-to-end bridge."""

from decimal import Decimal
from pathlib import Path

import pytest

from src.ingest.registration import RegistrationIndex, register_dataset
from src.rules import (
    RuleDatasets,
    UnsupportedRuleTypeError,
    build_finding,
    execute,
)
from tests.conftest import load_seed_rules, make_datasets, make_rule

RUN_ID = "RUN-2026-07-05-0001"


def keys_rule():
    return make_rule({
        "rule_id": "RULE-KEYS-001", "type": "field_compare",
        "failure_mode": "FM-010", "target_dataset": "participants",
        "params": {"validity": [{"field": "ssn", "not_null": True}]},
        "severity": "HIGH",
    })


def test_unsupported_type_raises_with_milestone_pointer():
    rules = load_seed_rules()
    with pytest.raises(UnsupportedRuleTypeError, match="MS-2.1"):
        execute(rules["RULE-VEST-PCT-001"],  # derived_recompute
                make_datasets("vesting", [], []))


def test_pass_produces_no_finding_but_reportable_outcome():
    """REQ-024: passes are reported, not silent — the outcome carries what
    the runner needs for a pass entry."""
    datasets = make_datasets("participants", [],
                             [{"plan_id": "PLN001", "participant_id": "P0001",
                               "ssn": "900441207"}])
    outcome = execute(keys_rule(), datasets)
    assert outcome.passed
    assert outcome.records_affected == 0
    assert build_finding(outcome, run_id=RUN_ID,
                         finding_id=f"{RUN_ID}-F001") is None


def test_finding_construction_uniform_with_sample_cap():
    rows = [{"plan_id": "PLN001", "participant_id": f"P{i:04d}", "ssn": None}
            for i in range(30)]
    outcome = execute(keys_rule(), make_datasets("participants", [], rows))
    finding = build_finding(
        outcome, run_id=RUN_ID, finding_id=f"{RUN_ID}-F001",
        remediation="Trace to source; distinguish missing data from transform drops.",
        full_detail_uri="data/runs/RUN-2026-07-05-0001/findings/F001.csv",
    )
    assert finding.records_affected == 30
    assert len(finding.sample_records) == 25  # §11.3 inline cap
    assert finding.severity == "HIGH"
    assert finding.failure_mode == "FM-010"
    assert finding.status == "new"
    assert finding.remediation.startswith("Trace to source")
    assert finding.full_detail_uri.endswith("F001.csv")


def test_execution_is_deterministic():
    rows_source = [{"plan_id": "PLN001", "participant_id": "P0001",
                    "loan_id": "L1", "outstanding_balance": Decimal("10432.17")}]
    rows_target = [{"plan_id": "PLN001", "participant_id": "P0001",
                    "loan_id": "L1", "outstanding_balance": Decimal("10398.55")}]
    rule = load_seed_rules()["RULE-LOAN-BAL-001"]
    a = execute(rule, make_datasets("loans", rows_source, rows_target))
    b = execute(rule, make_datasets("loans", rows_source, rows_target))
    assert a == b


def test_end_to_end_ingest_to_finding(tmp_path):
    """CSV files -> registration -> gate -> DataFrames -> rule -> finding,
    reproducing the FM-001 sample defect (delta -33.62)."""
    source_csv = tmp_path / "source_loans.csv"
    target_csv = tmp_path / "target_loans.csv"
    header = "plan_id,participant_id,loan_id,outstanding_balance\n"
    source_csv.write_text(header + "PLN001,P0042,L1,10432.17\n", encoding="utf-8")
    target_csv.write_text(header + "PLN001,P0042,L1,10398.55\n", encoding="utf-8")

    index = RegistrationIndex()
    index.add(register_dataset(source_csv, run_id=RUN_ID, side="source",
                               dataset_name="loans"))
    index.add(register_dataset(target_csv, run_id=RUN_ID, side="target",
                               dataset_name="loans"))

    rule = load_seed_rules()["RULE-LOAN-BAL-001"]
    assert index.missing_for_rule(rule) == []  # REQ-021 gate clear

    datasets = RuleDatasets.from_index(index)
    outcome = execute(rule, datasets)
    finding = build_finding(outcome, run_id=RUN_ID, finding_id=f"{RUN_ID}-F017")
    assert finding.records_affected == 1
    record = finding.sample_records[0]
    assert record.keys == {"plan_id": "PLN001", "participant_id": "P0042",
                           "loan_id": "L1"}
    assert record.delta == Decimal("-33.62")
