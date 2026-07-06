"""API request/response DTOs (MS-3.1; spec §18.1–18.2).

Response bodies mirror the pydantic domain models in
src/fingerprint/models.py exactly — the API never invents a second schema
(REQ-030). The DTOs here are request envelopes and thin composition wrappers
only. POC divergence from the product catalog, documented: POST /runs takes
local extract directories (the CLI_SPEC discovery convention) instead of
per-dataset S3 URIs, and executes synchronously.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.fingerprint.models import (
    Fingerprint,
    LearningEvent,
    PrioritizedSuiteEntry,
    RunSummary,
)


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunRequest(StrictDTO):
    pair_id: str
    source_dir: str
    target_dir: str
    fingerprint_version: str | None = None
    layout_dir: str | None = None
    plans: list[str] | None = None
    wave: str | None = None


class RunAccepted(StrictDTO):
    run_id: str
    status: str
    fingerprint_version: str
    summary: RunSummary
    findings: int


class ReviewRequest(StrictDTO):
    decision: str = Field(pattern="^(confirmed|false_positive)$")
    comment: str | None = None
    reviewer: str = "analyst"


class ReviewAccepted(StrictDTO):
    """Mirrors the spec §18.2 sample response for POST review."""

    finding_status: str
    learning_event: dict


class PublishRequest(StrictDTO):
    bump: str = Field(pattern="^(patch|minor|major)$")
    changelog: str | None = None


class PublishAccepted(StrictDTO):
    pair_id: str
    old_version: str
    new_version: str
    diff: dict


class PairSummary(StrictDTO):
    pair_id: str
    current_version: str
    modes: int
    rules: int


class VersionInfo(StrictDTO):
    version: str
    status: str


class SuiteView(StrictDTO):
    pair_id: str
    version: str
    suite: list[PrioritizedSuiteEntry]


class FingerprintVersions(StrictDTO):
    pair_id: str
    current: str
    versions: list[VersionInfo]


__all__ = [
    "Fingerprint",
    "FingerprintVersions",
    "LearningEvent",
    "PairSummary",
    "PublishAccepted",
    "PublishRequest",
    "ReviewAccepted",
    "ReviewRequest",
    "RunAccepted",
    "RunRequest",
    "SuiteView",
    "VersionInfo",
]
