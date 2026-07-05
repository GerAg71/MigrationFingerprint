"""REQ-010: schema-invalid fingerprints are rejected with pathed errors."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.fingerprint.models import (
    DetectionRuleAdapter,
    FieldCompareParams,
    Fingerprint,
    LayoutSpec,
    ValidityCheck,
)

SEED_PATH = (
    Path(__file__).resolve().parents[1]
    / "data" / "fingerprints" / "omni-zos-to-omni-linux" / "1.0.0" / "fingerprint.json"
)


def seed_payload() -> dict:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def test_unknown_rule_type_rejected():
    payload = seed_payload()
    payload["detection_rules"][0]["type"] = "fuzzy_match"
    with pytest.raises(ValidationError) as exc:
        Fingerprint.model_validate(payload)
    assert "fuzzy_match" in str(exc.value)


def test_probability_out_of_range_rejected():
    payload = seed_payload()
    payload["failure_modes"][0]["probability"] = 1.5
    with pytest.raises(ValidationError) as exc:
        Fingerprint.model_validate(payload)
    # pathed error: names the offending location
    assert any(e["loc"][:2] == ("failure_modes", 0) for e in exc.value.errors())


def test_dangling_rule_reference_rejected():
    payload = seed_payload()
    payload["failure_modes"][0]["detection_rules"] = ["RULE-DOES-NOT-EXIST-001"]
    with pytest.raises(ValidationError) as exc:
        Fingerprint.model_validate(payload)
    assert "RULE-DOES-NOT-EXIST-001" in str(exc.value)
    assert "FM-001" in str(exc.value)


def test_rule_referencing_unknown_failure_mode_rejected():
    payload = seed_payload()
    payload["detection_rules"][0]["failure_mode"] = "FM-099"
    with pytest.raises(ValidationError) as exc:
        Fingerprint.model_validate(payload)
    assert "FM-099" in str(exc.value)


def test_duplicate_failure_mode_ids_rejected():
    payload = seed_payload()
    payload["failure_modes"][1]["id"] = "FM-001"
    with pytest.raises(ValidationError) as exc:
        Fingerprint.model_validate(payload)
    assert "duplicate" in str(exc.value).lower()


def test_extra_fields_rejected():
    payload = seed_payload()
    payload["failure_modes"][0]["probabillity"] = 0.5  # typo field
    with pytest.raises(ValidationError):
        Fingerprint.model_validate(payload)


def test_custom_set_required_when_allowed_is_custom_set():
    payload = seed_payload()
    char_rule = next(r for r in payload["detection_rules"] if r["rule_id"] == "RULE-CHAR-001")
    del char_rule["params"]["custom_set"]
    with pytest.raises(ValidationError) as exc:
        Fingerprint.model_validate(payload)
    assert "custom_set" in str(exc.value)


def test_today_invalid_for_min_bound():
    with pytest.raises(ValidationError) as exc:
        ValidityCheck.model_validate({"field": "dob", "min": "today"})
    assert "today" in str(exc.value)


def test_unparsable_bound_rejected():
    with pytest.raises(ValidationError):
        ValidityCheck.model_validate({"field": "dob", "max": "next-week"})


def test_validity_entry_needs_a_constraint():
    with pytest.raises(ValidationError) as exc:
        ValidityCheck.model_validate({"field": "dob"})
    assert "constraint" in str(exc.value)


def test_field_compare_params_need_compare_or_validity():
    with pytest.raises(ValidationError):
        FieldCompareParams.model_validate({})


def test_compare_without_join_keys_rejected():
    with pytest.raises(ValidationError) as exc:
        DetectionRuleAdapter.validate_python({
            "rule_id": "RULE-X-001", "type": "field_compare", "failure_mode": "FM-001",
            "source_dataset": "loans", "target_dataset": "loans",
            "params": {"compare": [{"field": "outstanding_balance", "tolerance": "0.00"}]},
            "severity": "HIGH",
        })
    assert "join_keys" in str(exc.value)


def test_sum_aggregation_of_star_rejected():
    with pytest.raises(ValidationError):
        DetectionRuleAdapter.validate_python({
            "rule_id": "RULE-X-002", "type": "count_balance", "failure_mode": "FM-007",
            "source_dataset": "balances", "target_dataset": "balances",
            "params": {"aggregations": [{"measure": "*", "op": "sum", "group_by": ["plan_id"]}]},
            "severity": "HIGH",
        })


def test_negative_tolerance_rejected():
    with pytest.raises(ValidationError):
        DetectionRuleAdapter.validate_python({
            "rule_id": "RULE-X-003", "type": "field_compare", "failure_mode": "FM-001",
            "source_dataset": "loans", "target_dataset": "loans", "join_keys": ["loan_id"],
            "params": {"compare": [{"field": "outstanding_balance", "tolerance": "-0.01"}]},
            "severity": "HIGH",
        })


def test_layout_field_beyond_record_length_rejected():
    with pytest.raises(ValidationError) as exc:
        LayoutSpec.model_validate({
            "layout_id": "bad", "record_length": 10, "encoding": "cp037",
            "fields": [{"name": "overflow", "start": 8, "length": 5, "type": "char"}],
        })
    assert "record_length" in str(exc.value)


def test_layout_unknown_encoding_rejected():
    with pytest.raises(ValidationError) as exc:
        LayoutSpec.model_validate({
            "layout_id": "bad", "record_length": 10, "encoding": "cp99999",
            "fields": [{"name": "f", "start": 1, "length": 5, "type": "char"}],
        })
    assert "encoding" in str(exc.value)


def test_bad_semver_rejected():
    payload = seed_payload()
    payload["version"] = "1.0"
    with pytest.raises(ValidationError) as exc:
        Fingerprint.model_validate(payload)
    assert any(e["loc"] == ("version",) for e in exc.value.errors())
