"""MS-1.1: the shipped seed fingerprint must validate against the models,
including the CLI_SPEC.md schema extensions (top-level detection_rules,
sample_defect, validity gte_field / max:"today", encoding custom-set)."""

import json
from decimal import Decimal
from pathlib import Path

from src.fingerprint.models import (
    EncodingCheckParams,
    FieldCompareParams,
    Fingerprint,
)

SEED_PATH = (
    Path(__file__).resolve().parents[1]
    / "data" / "fingerprints" / "omni-zos-to-omni-linux" / "1.0.0" / "fingerprint.json"
)


def load_seed() -> Fingerprint:
    return Fingerprint.model_validate(json.loads(SEED_PATH.read_text(encoding="utf-8")))


def test_seed_file_validates():
    fp = load_seed()
    assert fp.fingerprint_id == "omni-zos-to-omni-linux"
    assert fp.version == "1.0.0"
    assert fp.status == "published"
    assert len(fp.failure_modes) == 18
    assert len(fp.detection_rules) == 23


def test_seed_failure_mode_ids_complete():
    fp = load_seed()
    assert [fm.id for fm in fp.failure_modes] == [f"FM-{n:03d}" for n in range(1, 19)]


def test_every_seed_mode_has_sample_defect_and_rules():
    fp = load_seed()
    rule_ids = {r.rule_id for r in fp.detection_rules}
    for fm in fp.failure_modes:
        assert fm.sample_defect, f"{fm.id} missing sample_defect"
        assert fm.detection_rules, f"{fm.id} has no rules"
        assert set(fm.detection_rules) <= rule_ids


def test_all_six_rule_types_present():
    fp = load_seed()
    assert {r.type for r in fp.detection_rules} == {
        "field_compare", "count_balance", "referential",
        "derived_recompute", "encoding_check", "sort_order_check",
    }


def test_money_tolerances_are_decimal():
    fp = load_seed()
    rule = next(r for r in fp.detection_rules if r.rule_id == "RULE-LOAN-BAL-001")
    tol = rule.params.compare[0].tolerance
    assert isinstance(tol, Decimal)
    assert tol == Decimal("0.00")
    assert not isinstance(tol, float)


def test_validity_extensions_gte_field_and_max_today():
    """CLI_SPEC.md MS-1.1 note: RULE-DATEVAL-001 uses gte_field and max:"today"."""
    fp = load_seed()
    rule = next(r for r in fp.detection_rules if r.rule_id == "RULE-DATEVAL-001")
    assert isinstance(rule.params, FieldCompareParams)
    checks = {v.field: v for v in rule.params.validity}
    assert checks["dob"].max == "today"
    assert checks["term_date"].gte_field == "hire_date"


def test_encoding_custom_set_extension():
    """CLI_SPEC.md MS-1.1 note: RULE-CHAR-001 uses allowed:"custom-set" + custom_set."""
    fp = load_seed()
    rule = next(r for r in fp.detection_rules if r.rule_id == "RULE-CHAR-001")
    assert isinstance(rule.params, EncodingCheckParams)
    assert rule.params.allowed == "custom-set"
    assert rule.params.custom_set == "A-Za-z '.,-"


def test_seed_round_trips_through_json():
    fp = load_seed()
    again = Fingerprint.model_validate(fp.model_dump(mode="json"))
    assert again == fp


def test_priority_score_worked_example():
    """Spec §12.2 worked example: FM-007 > FM-001 > FM-012/13 > … > FM-018."""
    fp = load_seed()
    scores = {fm.id: fm.priority_score for fm in fp.failure_modes}
    assert abs(scores["FM-007"] - 0.7125) < 1e-9
    assert abs(scores["FM-001"] - 0.63) < 1e-9
    assert scores["FM-007"] > scores["FM-001"] > scores["FM-012"] > scores["FM-018"]
