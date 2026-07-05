"""MS-1.1 done-when: models validate all Appendix D payloads (spec App. D)."""

import json
from decimal import Decimal
from pathlib import Path

from src.fingerprint.models import (
    ConversionRun,
    CountBalanceRule,
    DerivedRecomputeRule,
    DetectionRuleAdapter,
    EncodingCheckRule,
    FieldCompareRule,
    FindingsReport,
    Fingerprint,
    LayoutSpec,
    ReferentialRule,
    SortOrderCheckRule,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "appendix_d"


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_d1_fingerprint_excerpt():
    """D.1 excerpt: 2 of 18 modes, no top-level detection_rules array."""
    fp = Fingerprint.model_validate(load("fingerprint_excerpt.json"))
    assert [fm.id for fm in fp.failure_modes] == ["FM-007", "FM-001"]
    assert fp.detection_rules == []
    assert fp.failure_modes[0].sample_defect is None  # optional in excerpts


def test_d2_one_rule_per_type():
    payloads = load("rules.json")
    rules = [DetectionRuleAdapter.validate_python(p) for p in payloads]
    assert [type(r) for r in rules] == [
        FieldCompareRule, CountBalanceRule, ReferentialRule,
        DerivedRecomputeRule, EncodingCheckRule, SortOrderCheckRule,
    ]
    vest = rules[3]
    assert vest.params.recompute == "vested_pct"
    assert vest.params.tolerance == Decimal("0.0000")


def test_d3_findings_report():
    report = FindingsReport.model_validate(load("findings_report.json"))
    assert report.run.summary.rules_run == 24
    assert report.suite[0].priority_score == 0.7125
    finding = report.findings[0]
    assert finding.status == "new"
    assert finding.sample_records[0].delta == Decimal("-33.62")
    assert finding.sample_records[0].source["outstanding_balance"] == "10432.17"


def test_5_5_conversion_run():
    run = ConversionRun.model_validate(load("conversion_run.json"))
    assert run.status == "review"
    assert run.scope.plans == ["PLN001", "PLN002"]
    assert run.suite_snapshot[0].order == 1
    assert run.summary.severity_mix == {"HIGH": 2, "MEDIUM": 3}


def test_10_2_layout_spec():
    layout = LayoutSpec.model_validate(load("layout_omni_loans_v1.json"))
    assert layout.encoding == "cp037"
    packed = next(f for f in layout.fields if f.name == "outstanding_balance")
    assert packed.type == "packed"
    assert packed.decimals == 2
    orig = next(f for f in layout.fields if f.name == "origination_date")
    assert orig.zero_is_null is True
    assert orig.date_format == "YYYYMMDD"
