"""referential executor tests (spec §11.2.3 unit-test spec): clean pair no
orphans; removed target row reported; duplicate SSN reported with both rows."""

import pytest

from src.rules import ExecutionContext, execute
from tests.conftest import make_datasets, make_rule


def participant(pid, ssn="900441207"):
    return {"plan_id": "PLN001", "participant_id": pid, "ssn": ssn}


def orphan_rule():
    return make_rule({
        "rule_id": "RULE-REF-001", "type": "referential",
        "failure_mode": "FM-009",
        "source_dataset": "participants", "target_dataset": "participants",
        "join_keys": ["plan_id", "participant_id"],
        "params": {},
        "severity": "HIGH",
    })


def test_clean_pair_yields_no_orphans():
    rows = [participant("P0001"), participant("P0002", "900441208")]
    outcome = execute(orphan_rule(), make_datasets("participants", rows, list(rows)))
    assert outcome.passed
    assert outcome.detail is None


def test_removed_target_row_reported_as_missing_in_target():
    source = [participant("P0001"), participant("P0002", "900441208")]
    target = [participant("P0001")]
    outcome = execute(orphan_rule(), make_datasets("participants", source, target))
    record = outcome.affected[0]
    assert record.keys == {"plan_id": "PLN001", "participant_id": "P0002"}
    assert record.source == {"_set": "missing_in_target"}
    assert record.target is None
    assert outcome.detail["missing_in_target"] == 1
    assert outcome.detail["unexpected_in_target"] == 0


def test_extra_target_row_reported_as_unexpected_in_target():
    source = [participant("P0001")]
    target = [participant("P0001"), participant("P9999", "900449999")]
    outcome = execute(orphan_rule(), make_datasets("participants", source, target))
    record = outcome.affected[0]
    assert record.keys["participant_id"] == "P9999"
    assert record.target == {"_set": "unexpected_in_target"}
    assert record.source is None


def test_both_orphan_sets_reported_separately():
    source = [participant("P0001"), participant("P0002", "900441208")]
    target = [participant("P0001"), participant("P0003", "900441209")]
    outcome = execute(orphan_rule(), make_datasets("participants", source, target))
    sets = sorted((r.source or r.target)["_set"] for r in outcome.affected)
    assert sets == ["missing_in_target", "unexpected_in_target"]
    assert outcome.detail == {"missing_in_target": 1, "unexpected_in_target": 1,
                              "duplicate_rows": 0, "unmapped_values": 0}


# --- unique (FM-011) ----------------------------------------------------------


def dup_rule():
    return make_rule({
        "rule_id": "RULE-DUP-001", "type": "referential",
        "failure_mode": "FM-011",
        "source_dataset": "participants", "target_dataset": "participants",
        "join_keys": ["plan_id", "participant_id"],
        "params": {"unique": ["plan_id", "ssn"]},
        "severity": "HIGH",
    })


def test_duplicate_ssn_within_plan_reports_both_rows():
    source = [participant("P0001", "900441207"),
              participant("P0002", "900441208")]
    target = [participant("P0001", "900441207"),
              participant("P0002", "900441207")]  # duplicate SSN in target
    outcome = execute(dup_rule(), make_datasets("participants", source, target))
    dups = [r for r in outcome.affected
            if r.target and r.target.get("_set") == "duplicate_target"]
    assert len(dups) == 2  # both rows of the duplicate group
    identities = sorted(r.target["participant_id"] for r in dups)
    assert identities == ["P0001", "P0002"]
    for record in dups:
        assert record.keys == {"plan_id": "PLN001", "ssn": "900441207"}
    assert outcome.detail["duplicate_rows"] == 2


def test_null_unique_values_do_not_group_as_duplicates():
    target = [participant("P0001", None), participant("P0002", None)]
    source = list(target)
    outcome = execute(dup_rule(), make_datasets("participants", source, target))
    assert outcome.detail is None or outcome.detail["duplicate_rows"] == 0


# --- unmapped_target_fields (FM-003) --------------------------------------------


def trace_rule():
    return make_rule({
        "rule_id": "RULE-DERIVED-TRACE-001", "type": "referential",
        "failure_mode": "FM-003",
        "source_dataset": "participants", "target_dataset": "participants",
        "join_keys": ["plan_id", "participant_id"],
        "params": {"unmapped_target_fields": {
            "fields": ["svc_points"],
            "mapping_manifest": "data/mappings/field_mappings.json",
        }},
        "severity": "MEDIUM",
    })


def test_unmapped_target_field_values_flagged():
    source = [participant("P0001")]
    target = [participant("P0001") | {"svc_points": "142"}]
    context = ExecutionContext(mapped_target_fields=frozenset({"ssn"}))
    outcome = execute(trace_rule(), make_datasets("participants", source, target),
                      context)
    record = outcome.affected[0]
    assert record.target["svc_points"] == "142"
    assert "no mapping-rule provenance" in record.target["_check"]


def test_mapped_field_passes():
    source = [participant("P0001")]
    target = [participant("P0001") | {"svc_points": "142"}]
    context = ExecutionContext(mapped_target_fields=frozenset({"svc_points"}))
    outcome = execute(trace_rule(), make_datasets("participants", source, target),
                      context)
    assert outcome.passed


def test_missing_manifest_raises_instead_of_guessing():
    source = [participant("P0001")]
    target = [participant("P0001") | {"svc_points": "142"}]
    with pytest.raises(ValueError, match="mapping manifest"):
        execute(trace_rule(), make_datasets("participants", source, target))
