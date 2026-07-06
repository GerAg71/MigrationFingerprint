"""AI Orchestration Layer (spec Ch. 8). Only this package may import model
SDKs (REQ-018); with no model available every deterministic function of the
application still works — the stub provider keeps AI features demoable
fully locally (§8.1)."""

from src.ai.contracts import (
    ConversionSummary,
    FailureModeDraft,
    FieldMappingSuggestions,
    FindingClassification,
    VarianceExplanation,
)
from src.ai.orchestrator import (
    AIGuardError,
    AIOrchestrator,
    AIResult,
    load_prompt,
)
from src.ai.providers.stub import StubProvider

__all__ = [
    "AIGuardError",
    "AIOrchestrator",
    "AIResult",
    "ConversionSummary",
    "FailureModeDraft",
    "FieldMappingSuggestions",
    "FindingClassification",
    "StubProvider",
    "VarianceExplanation",
    "load_prompt",
]
