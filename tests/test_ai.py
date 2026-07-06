"""AI Orchestration Layer (spec Ch. 8, 27): contract validation, the §27.1
programmatic guards, confidence routing, prompt registry, audit logging,
determinism, and REQ-018 (no model SDK outside src/ai)."""

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from src.ai.contracts import VarianceExplanation
from src.ai.orchestrator import (
    AIGuardError,
    AIOrchestrator,
    load_prompt,
)
from src.fingerprint.models import AffectedRecord, Finding, FindingsReport
from src.runner.run import run
from tests.conftest import REPO, copy_fingerprint_store

SAMPLES = REPO / "data" / "samples"
PAIR = "omni-zos-to-omni-linux"
RUN_ID = "RUN-2026-07-06-0001"


def make_finding(**overrides) -> Finding:
    base = dict(
        finding_id=f"{RUN_ID}-F001", run_id=RUN_ID,
        failure_mode="FM-001", rule_id="RULE-LOAN-BAL-001",
        severity="HIGH", records_affected=1,
        sample_records=[AffectedRecord(
            keys={"plan_id": "PLN001", "participant_id": "P0021",
                  "loan_id": "L2"},
            source={"outstanding_balance": "10432.17"},
            target={"outstanding_balance": "10398.55"},
            delta=Decimal("-33.62"),
        )],
        remediation="Recompute amortization from origination.",
    )
    base.update(overrides)
    return Finding(**base)


@pytest.fixture(scope="module")
def seeded_report(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ai")
    store = copy_fingerprint_store(tmp)
    result = run(PAIR, SAMPLES / "source" / "PLN-SEED-01",
                 SAMPLES / "target" / "PLN-SEED-01",
                 fingerprint_dir=store, runs_dir=tmp / "runs", run_id=RUN_ID)
    return result.report


# --- explain_variance (the demo function) -------------------------------------


def test_explanation_references_actual_deltas():
    result = AIOrchestrator().explain_variance(make_finding())
    output = result.output
    assert isinstance(output, VarianceExplanation)
    assert "-33.62" in output.explanation
    assert "10432.17" in output.explanation and "10398.55" in output.explanation
    assert result.needs_review is False  # 0.85 >= 0.70
    assert result.provider == "stub"
    assert re.match(r"^1\.0\+[0-9a-f]{16}$", result.prompt_version)


def test_explanation_is_deterministic():
    first = AIOrchestrator().explain_variance(make_finding())
    second = AIOrchestrator().explain_variance(make_finding())
    assert first.output == second.output


def test_guard_rejects_invented_numbers():
    """§27.1: no invented numbers — a provider hallucinating a figure is
    discarded, never surfaced."""

    class LyingProvider:
        name = "liar"

        def run(self, function, payload, prompt):
            return {"explanation": "The balance moved by 999999.99.",
                    "likely_cause": "n/a", "suggested_check": "n/a",
                    "confidence": 0.99}

    with pytest.raises(AIGuardError, match="999999.99"):
        AIOrchestrator(provider=LyingProvider()).explain_variance(make_finding())


def test_guard_rejects_contract_violations():
    class BrokenProvider:
        name = "broken"

        def run(self, function, payload, prompt):
            return {"explanation": "x"}  # missing required fields

    with pytest.raises(AIGuardError, match="contract validation"):
        AIOrchestrator(provider=BrokenProvider()).explain_variance(make_finding())


# --- conversion summary ---------------------------------------------------------


def test_summary_figures_match_scoreboard_verbatim(seeded_report):
    result = AIOrchestrator().conversion_summary(seeded_report)
    narrative = result.output.executive_narrative
    summary = seeded_report.run.summary
    for figure in (summary.rules_run, summary.passed, summary.failed,
                   summary.records_affected):
        assert str(figure) in narrative
    assert seeded_report.run.run_id in narrative
    assert len(result.output.key_risks) == 5
    assert "Remediate" in result.output.recommendation  # failures present


def test_green_run_recommends_signoff(seeded_report):
    green = FindingsReport(
        run=seeded_report.run.model_copy(update={
            "summary": seeded_report.run.summary.model_copy(update={
                "failed": 0, "records_affected": 0, "severity_mix": {}})}),
        suite=[], findings=[],
    )
    result = AIOrchestrator().conversion_summary(green)
    assert "sign-off" in result.output.recommendation


# --- classify / suggest ---------------------------------------------------------


def test_classification_routes_to_review_below_threshold():
    result = AIOrchestrator().classify_finding(make_finding())
    assert result.output.suggested_priority == "P2"  # HIGH, 1 record
    assert result.confidence == 0.65
    assert result.needs_review is True  # advisory AND below threshold (§8.4)


def test_suggest_failure_mode_draft_is_authorable():
    findings = [make_finding(), make_finding(finding_id=f"{RUN_ID}-F002")]
    result = AIOrchestrator().suggest_failure_mode(
        findings, PAIR, category="LOANS", data_domains=["LOAN"])
    draft = result.output
    assert draft.probability == 0.30  # learned-mode default (§14.4)
    assert draft.category == "LOANS"
    assert "RULE-LOAN-BAL-001" in draft.description


def test_suggest_field_mappings_by_similarity():
    result = AIOrchestrator().suggest_field_mappings(
        ["PART_SSN", "LOAN_BAL", "unrelated_xyz"],
        ["participant_ssn", "loan_balance", "plan_name"])
    pairs = {m.source_field: m.target_field for m in result.output.mappings}
    assert pairs["PART_SSN"] == "participant_ssn"
    assert pairs["LOAN_BAL"] == "loan_balance"
    assert "unrelated_xyz" not in pairs  # precision over recall (§27.1)


# --- registry, audit, REQ-018 ----------------------------------------------------


def test_all_five_prompt_templates_load():
    for name in ("explain_reconciliation_variance", "generate_conversion_summary",
                 "classify_finding", "suggest_failure_mode",
                 "suggest_field_mappings"):
        prompt = load_prompt(name)
        assert prompt.version == "1.0"
        assert prompt.digest


def test_audit_log_records_invocations_without_payloads(tmp_path):
    audit = tmp_path / "ai_audit.jsonl"
    AIOrchestrator(audit_path=audit).explain_variance(make_finding())
    lines = audit.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["function"] == "explain_reconciliation_variance"
    assert entry["provider"] == "stub"
    assert "prompt_version" in entry
    assert "10432.17" not in lines[0]  # no payload PII in the audit (§8.3)


def test_req_018_no_model_sdk_outside_src_ai():
    """REQ-018: nothing outside src/ai imports a model SDK."""
    sdk_pattern = re.compile(
        r"^\s*(?:import|from)\s+(anthropic|openai|boto3|botocore|google\.generativeai)",
        re.MULTILINE)
    offenders = []
    for path in (REPO / "src").rglob("*.py"):
        if (REPO / "src" / "ai") in path.parents:
            continue
        if sdk_pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path))
    assert offenders == []