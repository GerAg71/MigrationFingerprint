"""Shared helpers for the rule-engine tests (MS-1.4)."""

import json
from pathlib import Path

import pandas as pd

from src.fingerprint.models import DetectionRuleAdapter, Fingerprint
from src.rules.engine import RuleDatasets

REPO = Path(__file__).resolve().parents[1]
SEED_FILE = REPO / "data" / "fingerprints" / "omni-zos-to-omni-linux" / "1.0.0" / "fingerprint.json"


def make_rule(payload: dict):
    return DetectionRuleAdapter.validate_python(payload)


def make_datasets(dataset_name: str, source_rows: list[dict],
                  target_rows: list[dict]) -> RuleDatasets:
    return RuleDatasets(
        source={dataset_name: pd.DataFrame(source_rows, dtype=object)},
        target={dataset_name: pd.DataFrame(target_rows, dtype=object)},
    )


def load_seed_rules() -> dict:
    fp = Fingerprint.model_validate(json.loads(SEED_FILE.read_text(encoding="utf-8")))
    return {r.rule_id: r for r in fp.detection_rules}


# --- clean-pair extract fixtures (MS-1.5 runner tests) -----------------------
# One small, internally consistent plan; source == target => every executable
# seed rule passes. Tests inject defects by mutating target CSV text.

CLEAN_CSVS: dict[str, str] = {
    "plans": (
        "plan_id,plan_name,plan_type,status,safe_harbor_flag,catch_up_eligible,"
        "auto_enroll_flag,auto_enroll_rate,auto_increase_rate\n"
        "PLN001,Acme 401k,401K,ACTIVE,Y,Y,Y,0.03,0.01\n"
    ),
    "participants": (
        "plan_id,participant_id,ssn,first_name,last_name,address_1,address_2,"
        "city,state,zip,dob,hire_date,term_date,status\n"
        "PLN001,P0001,900441207,Alice,Ng,12 Elm St,,Springfield,IL,62704,"
        "1980-01-15,2015-05-01,,ACTIVE\n"
        "PLN001,P0002,900441208,Bob,Ray,9 Oak Ave,,Springfield,IL,62704,"
        "1975-06-30,2010-03-15,2019-05-01,TERMINATED\n"
    ),
    "balances": (
        "plan_id,participant_id,money_type_code,investment_code,balance,units,"
        "as_of_date\n"
        "PLN001,P0001,PRETAX,F01,1000.00,10.5,2026-06-30\n"
        "PLN001,P0002,ROTH,F02,500.00,5.25,2026-06-30\n"
    ),
    "contributions": (
        "plan_id,participant_id,money_type_code,period,amount,payroll_date\n"
        "PLN001,P0001,PRETAX,2026-06,100.00,2026-06-15\n"
        "PLN001,P0002,MATCH,2026-06,50.00,2026-06-15\n"
    ),
    # freshly originated loan (no payments yet): outstanding == origination,
    # so the FM-001 recompute passes on the clean pair
    "loans": (
        "plan_id,participant_id,loan_id,origination_date,origination_amount,"
        "rate,term_months,payment_amount,payment_frequency,maturity_date,"
        "outstanding_balance,status\n"
        "PLN001,P0001,L1,2026-06-15,10432.17,0.0525,60,228.00,MONTHLY,"
        "2031-06-15,10432.17,ACTIVE\n"
    ),
    "loan_payments": (
        "plan_id,participant_id,loan_id,payment_date,principal,interest\n"
    ),
    "vesting": (
        "plan_id,participant_id,schedule_id,service_years,vested_pct\n"
        "PLN001,P0001,GRADED6,4.5,0.6000\n"
        "PLN001,P0002,GRADED6,9.0,1.0000\n"
    ),
}


def write_extract_dirs(tmp_path: Path, target_mutations: dict | None = None):
    """Write the clean pair under tmp_path/{source,target}. target_mutations
    maps dataset name -> callable(csv_text) -> csv_text for defect seeding."""
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)
    mutations = target_mutations or {}
    for name, text in CLEAN_CSVS.items():
        (source_dir / f"{name}.csv").write_text(text, encoding="utf-8", newline="")
        mutated = mutations.get(name, lambda t: t)(text)
        (target_dir / f"{name}.csv").write_text(mutated, encoding="utf-8", newline="")
    return source_dir, target_dir
