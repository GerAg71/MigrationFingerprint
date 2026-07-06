"""AI Orchestration Layer (spec Ch. 8; REQ-018, REQ-019).

The single component through which all AI calls flow: prompt-template
registry (Ch. 27 — versioned .md files with front matter, hashed per
invocation), provider selection (stub today, Bedrock in the product, §8.3),
contract validation, programmatic guards from the §27.1 evaluation notes,
confidence-threshold routing to human review (§8.4), and an audit log of
invocations (prompt name/version/hash, never payload PII).

What is deliberately NOT here (§8.5): rule execution, reconciliation math,
prioritization, probability write-back — those stay deterministic code.
Orchestrator outputs are suggestions only; nothing here mutates fingerprints,
findings, or reports (REQ-019).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from src.ai.contracts import (
    Contract,
    ConversionSummary,
    FailureModeDraft,
    FieldMappingSuggestions,
    FindingClassification,
    VarianceExplanation,
)
from src.ai.providers.stub import StubProvider
from src.fingerprint.models import FailureMode, Finding, FindingsReport

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
DEFAULT_CONFIDENCE_THRESHOLD = 0.70

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


class AIGuardError(Exception):
    """A provider output violated a §27.1 programmatic guard (e.g. invented
    numbers). The output is discarded, never surfaced."""


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    version: str
    body: str

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.body.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class AIResult:
    """Envelope every AI function returns. needs_review=True routes the
    output to a human before any use (§8.4); consumers must render outputs
    visibly labeled as AI-generated (§20.4)."""

    function: str
    provider: str
    prompt_version: str
    confidence: float
    needs_review: bool
    output: Contract

    def to_payload(self) -> dict:
        return {
            "function": self.function,
            "provider": self.provider,
            "prompt_version": self.prompt_version,
            "confidence": self.confidence,
            "needs_review": self.needs_review,
            "ai_generated": True,
            "output": self.output.model_dump(mode="json"),
        }


def load_prompt(name: str) -> PromptTemplate:
    """Ch. 27 template: YAML-ish front matter (version:, model:, temperature:)
    between --- markers, then the body."""
    path = PROMPTS_DIR / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    version = "0"
    body = text
    if text.startswith("---"):
        _, front, body = text.split("---", 2)
        for line in front.splitlines():
            if line.strip().startswith("version:"):
                version = line.split(":", 1)[1].strip()
    return PromptTemplate(name=name, version=version, body=body.strip())


def _numbers(text: str) -> set[str]:
    return {match.lstrip("-").lstrip("0") or "0"
            for match in _NUMBER.findall(text)}


def _guard_no_invented_numbers(output_text: str, payload: dict,
                               function: str) -> None:
    allowed = _numbers(json.dumps(payload))
    invented = _numbers(output_text) - allowed
    if invented:
        raise AIGuardError(
            f"{function}: output references numbers absent from the input "
            f"({', '.join(sorted(invented))}) — no invented numbers (§27.1)")


class AIOrchestrator:
    def __init__(self, provider=None, *,
                 confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
                 audit_path: Path | str | None = None) -> None:
        self.provider = provider or StubProvider()
        self.confidence_threshold = confidence_threshold
        self.audit_path = Path(audit_path) if audit_path else None

    # --- core ---------------------------------------------------------------

    def _invoke(self, function: str, payload: dict, contract) -> AIResult:
        prompt = load_prompt(function)
        raw = self.provider.run(function, payload, prompt.body)
        try:
            output = contract.model_validate(raw)
        except ValidationError as exc:
            raise AIGuardError(
                f"{function}: provider output failed contract validation — "
                f"{exc.errors(include_url=False)}")
        result = AIResult(
            function=function, provider=self.provider.name,
            prompt_version=f"{prompt.version}+{prompt.digest}",
            confidence=output.confidence,
            needs_review=output.confidence < self.confidence_threshold,
            output=output,
        )
        self._audit(result)
        return result

    def _audit(self, result: AIResult) -> None:
        if self.audit_path is None:
            return
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "function": result.function,
                "provider": result.provider,
                "prompt_version": result.prompt_version,
                "confidence": result.confidence,
                "needs_review": result.needs_review,
            }, sort_keys=True) + "\n")

    # --- the §8.2 function catalog -------------------------------------------

    def explain_variance(self, finding: Finding,
                         failure_mode: FailureMode | None = None) -> AIResult:
        payload = {
            "finding": finding.model_dump(mode="json"),
            "failure_mode": (failure_mode.model_dump(mode="json")
                             if failure_mode else None),
        }
        result = self._invoke("explain_reconciliation_variance", payload,
                              VarianceExplanation)
        _guard_no_invented_numbers(result.output.explanation, payload,
                                   result.function)
        return result

    def conversion_summary(self, report: FindingsReport) -> AIResult:
        payload = {
            "run": report.run.model_dump(mode="json"),
            "findings": [f.model_dump(mode="json") for f in report.findings],
        }
        result = self._invoke("generate_conversion_summary", payload,
                              ConversionSummary)
        _guard_no_invented_numbers(result.output.executive_narrative, payload,
                                   result.function)
        return result

    def classify_finding(self, finding: Finding,
                         failure_mode: FailureMode | None = None) -> AIResult:
        payload = {
            "finding": finding.model_dump(mode="json"),
            "failure_mode": (failure_mode.model_dump(mode="json")
                             if failure_mode else None),
        }
        return self._invoke("classify_finding", payload, FindingClassification)

    def suggest_failure_mode(self, findings: list[Finding], pair_id: str,
                             category: str | None = None,
                             data_domains: list[str] | None = None) -> AIResult:
        payload = {
            "findings": [f.model_dump(mode="json") for f in findings],
            "pair_id": pair_id, "category": category,
            "data_domains": data_domains,
        }
        return self._invoke("suggest_failure_mode", payload, FailureModeDraft)

    def suggest_field_mappings(self, source_fields: list[str],
                               target_fields: list[str]) -> AIResult:
        payload = {"source_fields": source_fields,
                   "target_fields": target_fields}
        return self._invoke("suggest_field_mappings", payload,
                            FieldMappingSuggestions)
