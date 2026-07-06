"""AI function output contracts (spec §8.2, §27.1).

Every AI interface function returns structured JSON validated against one of
these pydantic contracts, plus a confidence score; outputs below the
confidence threshold route to human review (§8.4). Contracts are the
provider-independent part of the interface — the stub provider and the
product's Bedrock provider satisfy the same shapes.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confidence: float = Field(ge=0.0, le=1.0)


class VarianceExplanation(Contract):
    """ExplainReconciliationVariance(): natural-language finding explanation.
    Guard (§27.1): must reference the actual delta values — the orchestrator
    rejects explanations containing numbers absent from the finding."""

    explanation: str
    likely_cause: str
    suggested_check: str


class ConversionSummary(Contract):
    """GenerateConversionSummary(): executive narrative for the sign-off
    package. Guard (§27.1): all figures must match the scoreboard verbatim."""

    executive_narrative: str
    key_risks: list[str]
    recommendation: str


class FindingClassification(Contract):
    """ClassifyFinding(): triage assistance — advisory only, never
    auto-applied (REQ-019)."""

    suggested_priority: str  # P1 | P2 | P3
    suggested_owner_role: str
    rationale: str


class FailureModeDraft(Contract):
    """SuggestFailureMode(): a draft failure mode from a confirmed-finding
    cluster. Human approval is mandatory before it enters a fingerprint
    (REQ-019) — author-mode is the approval path."""

    name: str
    category: str
    description: str
    data_domains: list[str]
    impact: float = Field(gt=0.0, le=1.0)
    probability: float = Field(ge=0.05, le=0.99)
    remediation: str
    candidate_rule_note: str


class FieldMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_field: str
    target_field: str
    transform_note: str
    confidence: float = Field(ge=0.0, le=1.0)


class FieldMappingSuggestions(Contract):
    """SuggestFieldMappings(): ranked candidate mappings (precision over
    recall, §27.1)."""

    mappings: list[FieldMapping]
