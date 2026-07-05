"""MS-1.3: dataset registration (§10.4), hash reproducibility (REQ-023),
partial-file halt (REQ-022), and the REQ-021 gate index."""

import json
from pathlib import Path

import pytest

from src.fingerprint.models import Fingerprint
from src.ingest.registration import (
    PartialFileError,
    RegistrationIndex,
    content_hash,
    register_dataset,
)

RUN_ID = "RUN-2026-07-05-0001"
SEED_FILE = (
    Path(__file__).resolve().parents[1]
    / "data" / "fingerprints" / "omni-zos-to-omni-linux" / "1.0.0" / "fingerprint.json"
)

BALANCES_CSV = (
    "plan_id,participant_id,money_type_code,investment_code,balance\n"
    "PLN001,P0001,PRETAX,F01,100.00\n"
    "PLN001,P0002,ROTH,F02,250.50\n"
)


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8", newline="")
    return path


def seed_rules():
    fp = Fingerprint.model_validate(json.loads(SEED_FILE.read_text(encoding="utf-8")))
    return {r.rule_id: r for r in fp.detection_rules}


# --- registration record (§10.4) ---------------------------------------------


def test_registration_carries_all_spec_fields(tmp_path):
    path = write(tmp_path, "balances.csv", BALANCES_CSV)
    result = register_dataset(
        path, run_id=RUN_ID, side="source", dataset_name="balances",
        crosswalks_applied=["money_type:omni-v1"],
    )
    reg = result.registration
    assert reg.run_id == RUN_ID
    assert reg.side == "source"
    assert reg.dataset_name == "balances"
    assert reg.uri == str(path)
    assert reg.row_count == 2
    assert reg.content_hash.startswith("sha256:") and len(reg.content_hash) == 71
    assert reg.layout_id is None
    assert reg.crosswalks_applied == ["money_type:omni-v1"]
    assert reg.reject_count == 0
    assert reg.rejects_uri is None


def test_headerless_resolution_logged_in_registration(tmp_path):
    path = write(tmp_path, "balances.csv", "PLN001,P0001,PRETAX,F01,100.00\n")
    reg = register_dataset(
        path, run_id=RUN_ID, side="target", dataset_name="balances"
    ).registration
    assert any("headerless: resolved by canonical order" in a for a in reg.annotations)


# --- content hash (REQ-023) ---------------------------------------------------


def test_hash_reproducible_for_identical_bytes(tmp_path):
    a = write(tmp_path, "a.csv", BALANCES_CSV)
    b = write(tmp_path, "b.csv", BALANCES_CSV)  # same bytes, different path
    assert content_hash(a) == content_hash(b)
    reg_a = register_dataset(a, run_id=RUN_ID, side="source",
                             dataset_name="balances").registration
    reg_b = register_dataset(b, run_id=RUN_ID, side="target",
                             dataset_name="balances").registration
    assert reg_a.content_hash == reg_b.content_hash


def test_hash_changes_when_bytes_change(tmp_path):
    a = write(tmp_path, "a.csv", BALANCES_CSV)
    b = write(tmp_path, "b.csv", BALANCES_CSV.replace("100.00", "100.01"))
    assert content_hash(a) != content_hash(b)


# --- reject quarantine into rejects.csv (§10.5) --------------------------------


def test_rejects_written_with_reason_and_counted(tmp_path):
    path = write(tmp_path, "balances.csv",
                 "plan_id,participant_id,money_type_code,investment_code,balance\n"
                 "PLN001,P0001,PRETAX,F01,100.00\n"
                 "PLN001,P0002,PRETAX,F01,oops\n")
    rejects_dir = tmp_path / "rejects"
    result = register_dataset(
        path, run_id=RUN_ID, side="target", dataset_name="balances",
        rejects_dir=rejects_dir,
    )
    reg = result.registration
    assert reg.row_count == 1
    assert reg.reject_count == 1
    rejects_file = Path(reg.rejects_uri)
    assert rejects_file.exists()
    content = rejects_file.read_text(encoding="utf-8")
    assert "line,reason,raw" in content
    assert "unparsable amount" in content
    assert any("quarantined" in a for a in reg.annotations)


# --- partial file halt (REQ-022) -----------------------------------------------


def test_partial_file_halts_with_clear_reason(tmp_path):
    path = write(tmp_path, "balances.csv", BALANCES_CSV)  # 2 rows
    with pytest.raises(PartialFileError) as exc:
        register_dataset(
            path, run_id=RUN_ID, side="source", dataset_name="balances",
            expected_min_rows=10,
        )
    message = str(exc.value)
    assert "partial file" in message
    assert "2 accepted rows" in message
    assert "expectation of 10" in message
    assert "REQ-022" in message


def test_expectation_met_does_not_halt(tmp_path):
    path = write(tmp_path, "balances.csv", BALANCES_CSV)
    result = register_dataset(
        path, run_id=RUN_ID, side="source", dataset_name="balances",
        expected_min_rows=2,
    )
    assert result.registration.row_count == 2


# --- the REQ-021 dataset gate ---------------------------------------------------


def test_gate_two_sided_rule_needs_both_sides(tmp_path):
    rules = seed_rules()
    loan_rule = rules["RULE-LOAN-BAL-001"]  # loans -> loans
    index = RegistrationIndex()
    loans_csv = write(tmp_path, "loans.csv",
                      "plan_id,participant_id,loan_id,outstanding_balance\n"
                      "PLN001,P0001,L1,100.00\n")
    assert index.missing_for_rule(loan_rule) == ["source/loans", "target/loans"]
    index.add(register_dataset(loans_csv, run_id=RUN_ID, side="source",
                               dataset_name="loans"))
    assert index.missing_for_rule(loan_rule) == ["target/loans"]
    index.add(register_dataset(loans_csv, run_id=RUN_ID, side="target",
                               dataset_name="loans"))
    assert index.missing_for_rule(loan_rule) == []


def test_gate_single_sided_rule_needs_target_only(tmp_path):
    rules = seed_rules()
    keys_rule = rules["RULE-KEYS-001"]  # validity-only, target participants
    index = RegistrationIndex()
    participants = write(tmp_path, "participants.csv",
                         "plan_id,participant_id,ssn\nPLN001,P0001,900441207\n")
    assert index.missing_for_rule(keys_rule) == ["target/participants"]
    index.add(register_dataset(participants, run_id=RUN_ID, side="target",
                               dataset_name="participants"))
    assert index.missing_for_rule(keys_rule) == []


def test_gate_reports_gaps_per_rule(tmp_path):
    rules = seed_rules()
    index = RegistrationIndex()
    balances = write(tmp_path, "balances.csv", BALANCES_CSV)
    index.add(register_dataset(balances, run_id=RUN_ID, side="source",
                               dataset_name="balances"))
    index.add(register_dataset(balances, run_id=RUN_ID, side="target",
                               dataset_name="balances"))
    gaps = index.missing_for_rules(rules.values())
    assert "RULE-BAL-TOTALS-001" not in gaps          # balances registered
    assert gaps["RULE-LOAN-BAL-001"] == ["source/loans", "target/loans"]
    assert gaps["RULE-KEYS-001"] == ["target/participants"]


def test_duplicate_registration_rejected(tmp_path):
    index = RegistrationIndex()
    path = write(tmp_path, "balances.csv", BALANCES_CSV)
    index.add(register_dataset(path, run_id=RUN_ID, side="source",
                               dataset_name="balances"))
    with pytest.raises(ValueError, match="already registered"):
        index.add(register_dataset(path, run_id=RUN_ID, side="source",
                                   dataset_name="balances"))
