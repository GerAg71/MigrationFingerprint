"""Pydantic schemas for the Migration Fingerprint domain (MS-1.1).

Single source of truth for every schema (spec Ch. 5, 10.2, 24.1; REQ-030).
Money amounts and tolerances are Decimal, never float (REQ-004, REQ-017);
JSON carries them as strings. Models forbid unknown fields so schema-invalid
fingerprints are rejected with pathed errors (REQ-010).

Schema extensions required by the seed fingerprint (CLI_SPEC.md, MS-1.1 notes):
top-level ``detection_rules`` array on Fingerprint, ``sample_defect`` per
failure mode, validity ``gte_field`` / ``max: "today"``, and
``allowed: "custom-set"`` with ``custom_set`` on encoding_check params.
"""

from __future__ import annotations

import codecs
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated, Any, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

SEMVER_PATTERN = r"^\d+\.\d+\.\d+$"
FM_ID_PATTERN = r"^FM-\d{3}$"
RULE_ID_PATTERN = r"^RULE-[A-Z0-9]+(-[A-Z0-9]+)*$"
RUN_ID_PATTERN = r"^RUN-\d{4}-\d{2}-\d{2}-\d{4}$"

Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
DataDomain = Literal[
    "PLAN", "PARTICIPANT", "BALANCE", "CONTRIBUTION", "LOAN",
    "VESTING", "TRANSACTION", "ENCODING", "FORMAT",
]
Origin = Literal["seed:experience", "seed:methodology", "learned"]
FingerprintStatus = Literal["draft", "published", "superseded"]
RunStatus = Literal["created", "ingesting", "running", "review", "completed", "failed"]
FindingStatus = Literal["new", "in_review", "confirmed", "false_positive", "remediated", "closed"]
RuleOutcome = Literal["pass", "fail", "skipped"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Detection-rule params, one typed model per rule type (spec Ch. 11.2)
# ---------------------------------------------------------------------------


class CompareField(StrictModel):
    field: str
    kind: Literal["money", "text", "date"] | None = None
    tolerance: Decimal | None = None

    @field_validator("tolerance")
    @classmethod
    def _non_negative(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v < 0:
            raise ValueError("tolerance must be >= 0")
        return v


class ValidityCheck(StrictModel):
    """Single-sided validity constraint (spec §11.2.1 ``validity`` block).

    ``min``/``max`` are strings parsed at execution time: an ISO date or a
    decimal amount; ``max`` additionally accepts the literal ``"today"``.
    ``gte_field`` requires this field's value >= the named field's value
    (cross-field comparison, e.g. term_date >= hire_date).
    """

    field: str
    not_null: bool = False
    max_length: int | None = Field(default=None, ge=1)
    pattern: str | None = None
    min: str | None = None
    max: str | None = None
    gte_field: str | None = None

    @field_validator("min", "max")
    @classmethod
    def _bound_parsable(cls, v: str | None, info) -> str | None:
        if v is None:
            return v
        if v == "today":
            if info.field_name == "max":
                return v
            raise ValueError('"today" is only valid for max')
        try:
            date.fromisoformat(v)
            return v
        except ValueError:
            pass
        try:
            Decimal(v)
            return v
        except InvalidOperation:
            raise ValueError(
                f"{info.field_name} must be an ISO date, a decimal string, "
                f'or "today" (max only); got {v!r}'
            )

    @model_validator(mode="after")
    def _has_constraint(self) -> "ValidityCheck":
        if not (
            self.not_null
            or self.max_length is not None
            or self.pattern is not None
            or self.min is not None
            or self.max is not None
            or self.gte_field is not None
        ):
            raise ValueError("validity entry must declare at least one constraint")
        return self


class FieldCompareParams(StrictModel):
    compare: list[CompareField] = []
    validity: list[ValidityCheck] = []

    @model_validator(mode="after")
    def _not_empty(self) -> "FieldCompareParams":
        if not self.compare and not self.validity:
            raise ValueError("field_compare params need at least one compare or validity entry")
        return self


class Aggregation(StrictModel):
    dataset: str | None = None
    measure: str  # a field name, or "*" for row counts
    op: Literal["sum", "count"]
    group_by: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _sum_needs_field(self) -> "Aggregation":
        if self.op == "sum" and self.measure == "*":
            raise ValueError('op "sum" requires a field measure, not "*"')
        return self


class CountBalanceParams(StrictModel):
    aggregations: list[Aggregation] = Field(min_length=1)
    filter: dict[str, str] | None = None


class UnmappedTargetFields(StrictModel):
    fields: list[str] = Field(min_length=1)
    mapping_manifest: str


class ReferentialParams(StrictModel):
    """Empty params = plain bidirectional orphan detection on join_keys."""

    unique: list[str] | None = None
    unmapped_target_fields: UnmappedTargetFields | None = None


class DerivedRecomputeParams(StrictModel):
    # Shipped recomputers: vested_pct, loan_balance, packed_decode_control_total
    recompute: str
    inputs: dict[str, str]
    compare_field: str
    tolerance: Decimal | None = None

    @field_validator("tolerance")
    @classmethod
    def _non_negative(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v < 0:
            raise ValueError("tolerance must be >= 0")
        return v


class EncodingCheckParams(StrictModel):
    fields: list[str] = Field(min_length=1)
    allowed: Literal["ascii", "latin1", "custom-set"]
    custom_set: str | None = None

    @model_validator(mode="after")
    def _custom_set_matches(self) -> "EncodingCheckParams":
        if self.allowed == "custom-set" and not self.custom_set:
            raise ValueError('allowed "custom-set" requires custom_set')
        if self.allowed != "custom-set" and self.custom_set is not None:
            raise ValueError('custom_set is only valid with allowed "custom-set"')
        return self


class SortOrderCheckParams(StrictModel):
    dataset: str | None = None
    order_by: list[str] = Field(min_length=1)
    collation: Literal["ascii", "ebcdic"]


# ---------------------------------------------------------------------------
# Detection rule envelope — discriminated union on `type` (spec §5.4, 5.8)
# ---------------------------------------------------------------------------


class RuleBase(StrictModel):
    rule_id: str = Field(pattern=RULE_ID_PATTERN)
    failure_mode: str = Field(pattern=FM_ID_PATTERN)
    source_dataset: str | None = None
    target_dataset: str
    join_keys: list[str] | None = None
    severity: Severity
    enabled: bool = True


class FieldCompareRule(RuleBase):
    type: Literal["field_compare"]
    params: FieldCompareParams

    @model_validator(mode="after")
    def _compare_needs_join(self) -> "FieldCompareRule":
        # validity-only rules are single-sided (target only); comparisons join
        if self.params.compare:
            if self.source_dataset is None:
                raise ValueError("field_compare with compare entries requires source_dataset")
            if not self.join_keys:
                raise ValueError("field_compare with compare entries requires join_keys")
        return self


class CountBalanceRule(RuleBase):
    type: Literal["count_balance"]
    params: CountBalanceParams

    @model_validator(mode="after")
    def _needs_source(self) -> "CountBalanceRule":
        if self.source_dataset is None:
            raise ValueError("count_balance requires source_dataset")
        return self


class ReferentialRule(RuleBase):
    type: Literal["referential"]
    params: ReferentialParams = ReferentialParams()

    @model_validator(mode="after")
    def _needs_source_and_keys(self) -> "ReferentialRule":
        if self.source_dataset is None:
            raise ValueError("referential requires source_dataset")
        if not self.join_keys:
            raise ValueError("referential requires join_keys")
        return self


class DerivedRecomputeRule(RuleBase):
    type: Literal["derived_recompute"]
    params: DerivedRecomputeParams

    @model_validator(mode="after")
    def _needs_source_and_keys(self) -> "DerivedRecomputeRule":
        if self.source_dataset is None:
            raise ValueError("derived_recompute requires source_dataset")
        if not self.join_keys:
            raise ValueError("derived_recompute requires join_keys")
        return self


class EncodingCheckRule(RuleBase):
    type: Literal["encoding_check"]
    params: EncodingCheckParams


class SortOrderCheckRule(RuleBase):
    type: Literal["sort_order_check"]
    params: SortOrderCheckParams


DetectionRule = Annotated[
    Union[
        FieldCompareRule,
        CountBalanceRule,
        ReferentialRule,
        DerivedRecomputeRule,
        EncodingCheckRule,
        SortOrderCheckRule,
    ],
    Field(discriminator="type"),
]

DetectionRuleAdapter: TypeAdapter = TypeAdapter(DetectionRule)


# ---------------------------------------------------------------------------
# Failure mode and Fingerprint (spec §5.2–5.3)
# ---------------------------------------------------------------------------


class FailureModeHistory(StrictModel):
    times_detected: int = Field(default=0, ge=0)
    times_confirmed: int = Field(default=0, ge=0)
    false_positives: int = Field(default=0, ge=0)


class FailureMode(StrictModel):
    id: str = Field(pattern=FM_ID_PATTERN)
    name: str
    category: str
    description: str
    probability: float = Field(ge=0.05, le=0.99)
    impact: float = Field(gt=0.0, le=1.0)
    data_domains: list[DataDomain] = Field(min_length=1)
    detection_rules: list[str] = Field(min_length=1)
    sample_defect: str | None = None
    remediation: str
    history: FailureModeHistory = Field(default_factory=FailureModeHistory)
    origin: Origin

    @field_validator("detection_rules")
    @classmethod
    def _rule_id_shape(cls, v: list[str]) -> list[str]:
        import re

        for rid in v:
            if not re.fullmatch(RULE_ID_PATTERN, rid):
                raise ValueError(f"invalid rule id reference: {rid!r}")
        return v

    @property
    def priority_score(self) -> float:
        return self.probability * self.impact


class PlatformPairRef(StrictModel):
    source: str
    target: str


class Fingerprint(StrictModel):
    fingerprint_id: str
    platform_pair: PlatformPairRef
    version: str = Field(pattern=SEMVER_PATTERN)
    status: FingerprintStatus
    updated_at: datetime | None = None
    updated_by: str | None = None
    changelog: str | None = None
    failure_modes: list[FailureMode] = Field(min_length=1)
    detection_rules: list[DetectionRule] = []

    @model_validator(mode="after")
    def _cross_references(self) -> "Fingerprint":
        fm_ids = [fm.id for fm in self.failure_modes]
        dupes = {i for i in fm_ids if fm_ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate failure-mode ids: {sorted(dupes)}")
        # Cross-reference checks apply when the rule library is present;
        # excerpt payloads without detection_rules (Appendix D.1) still validate.
        if self.detection_rules:
            rule_ids = [r.rule_id for r in self.detection_rules]
            rdupes = {i for i in rule_ids if rule_ids.count(i) > 1}
            if rdupes:
                raise ValueError(f"duplicate rule ids: {sorted(rdupes)}")
            fm_set, rule_set = set(fm_ids), set(rule_ids)
            for rule in self.detection_rules:
                if rule.failure_mode not in fm_set:
                    raise ValueError(
                        f"rule {rule.rule_id} references undefined failure mode {rule.failure_mode}"
                    )
            for fm in self.failure_modes:
                for rid in fm.detection_rules:
                    if rid not in rule_set:
                        raise ValueError(
                            f"failure mode {fm.id} references undefined rule {rid}"
                        )
        return self

    def rules_for(self, fm_id: str) -> list[DetectionRule]:
        return [r for r in self.detection_rules if r.failure_mode == fm_id]


# ---------------------------------------------------------------------------
# Conversion run, suite, findings (spec §5.5–5.6, Appendix D.3)
# ---------------------------------------------------------------------------


class RunScope(StrictModel):
    plans: list[str] | None = None
    wave: str | None = None


class RunDatasets(StrictModel):
    source: dict[str, str] = {}
    target: dict[str, str] = {}


class RunSummary(StrictModel):
    rules_run: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    records_affected: int = Field(ge=0)
    severity_mix: dict[Severity, int] = {}


class SuiteItem(StrictModel):
    """One entry of a run's immutable suite snapshot (spec §12.2)."""

    rule_id: str = Field(pattern=RULE_ID_PATTERN)
    fm_id: str | None = Field(default=None, pattern=FM_ID_PATTERN)
    priority_score: float = Field(ge=0.0, le=1.0)
    order: int = Field(ge=1)
    outcome: RuleOutcome | None = None
    records_affected: int | None = Field(default=None, ge=0)


class PrioritizedSuiteEntry(StrictModel):
    """One row of the prioritized suite view (spec §12.2, CLI_SPEC `suite`).

    Disabled rules stay in their priority position, marked skipped:disabled.
    priority_score is exact Decimal arithmetic so the suite is reproducible
    byte-for-byte (REQ-009).
    """

    order: int = Field(ge=1)
    rule_id: str = Field(pattern=RULE_ID_PATTERN)
    fm_id: str = Field(pattern=FM_ID_PATTERN)
    priority_score: Decimal = Field(ge=0, le=1)
    severity: Severity
    source_dataset: str | None = None
    target_dataset: str
    status: Literal["pending", "skipped:disabled"] = "pending"


class ConversionRun(StrictModel):
    run_id: str = Field(pattern=RUN_ID_PATTERN)
    pair_id: str
    fingerprint_version: str = Field(pattern=SEMVER_PATTERN)
    scope: RunScope = Field(default_factory=RunScope)
    datasets: RunDatasets = Field(default_factory=RunDatasets)
    suite_snapshot: list[SuiteItem] = []
    status: RunStatus = "created"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    summary: RunSummary | None = None


class AffectedRecord(StrictModel):
    keys: dict[str, str]
    source: dict[str, str | None] | None = None
    target: dict[str, str | None] | None = None
    delta: Decimal | None = None


class Finding(StrictModel):
    finding_id: str
    run_id: str = Field(pattern=RUN_ID_PATTERN)
    failure_mode: str = Field(pattern=FM_ID_PATTERN)
    rule_id: str = Field(pattern=RULE_ID_PATTERN)
    severity: Severity
    status: FindingStatus = "new"
    records_affected: int = Field(ge=0)
    sample_records: list[AffectedRecord] = Field(default=[], max_length=25)
    full_detail_uri: str | None = None
    remediation: str | None = None


class ReportRun(StrictModel):
    """Run header of findings.json (Appendix D.3)."""

    run_id: str = Field(pattern=RUN_ID_PATTERN)
    pair_id: str
    fingerprint_version: str = Field(pattern=SEMVER_PATTERN)
    dataset_hashes: dict[str, str] = {}
    summary: RunSummary


class FindingsReport(StrictModel):
    run: ReportRun
    suite: list[SuiteItem]
    findings: list[Finding] = []


# ---------------------------------------------------------------------------
# LayoutSpec — copybook-style fixed-width layout (spec §10.2)
# ---------------------------------------------------------------------------


class LayoutField(StrictModel):
    name: str
    start: int = Field(ge=1)  # 1-based byte offset
    length: int = Field(ge=1)
    type: Literal["char", "zoned", "packed", "binary"]
    decimals: int | None = Field(default=None, ge=0)
    date_format: str | None = None
    zero_is_null: bool = False


class LayoutSpec(StrictModel):
    layout_id: str
    record_length: int = Field(ge=1)
    encoding: str  # e.g. cp037, cp1140, ascii, latin-1
    fields: list[LayoutField] = Field(min_length=1)

    @field_validator("encoding")
    @classmethod
    def _known_codec(cls, v: str) -> str:
        try:
            codecs.lookup(v)
        except LookupError:
            raise ValueError(f"unknown encoding: {v!r}")
        return v

    @model_validator(mode="after")
    def _fields_in_bounds(self) -> "LayoutSpec":
        for f in self.fields:
            if f.start + f.length - 1 > self.record_length:
                raise ValueError(
                    f"field {f.name!r} ends at byte {f.start + f.length - 1}, "
                    f"beyond record_length {self.record_length}"
                )
        return self


# ---------------------------------------------------------------------------
# JSON Schema export (MS-1.1 done-when)
# ---------------------------------------------------------------------------

_EXPORTED_MODELS: dict[str, type[BaseModel]] = {
    "PlatformPair": PlatformPairRef,
    "Fingerprint": Fingerprint,
    "FailureMode": FailureMode,
    "ConversionRun": ConversionRun,
    "SuiteItem": SuiteItem,
    "PrioritizedSuiteEntry": PrioritizedSuiteEntry,
    "Finding": Finding,
    "FindingsReport": FindingsReport,
    "LayoutSpec": LayoutSpec,
}


def export_json_schemas() -> dict[str, dict[str, Any]]:
    """JSON Schema for every top-level entity, keyed by entity name."""
    schemas: dict[str, dict[str, Any]] = {
        name: model.model_json_schema() for name, model in _EXPORTED_MODELS.items()
    }
    schemas["DetectionRule"] = DetectionRuleAdapter.json_schema()
    return schemas


def write_json_schemas(directory: Path) -> list[Path]:
    """Write one <Entity>.schema.json per entity; returns the paths written."""
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, schema in sorted(export_json_schemas().items()):
        path = directory / f"{name}.schema.json"
        path.write_text(json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8")
        written.append(path)
    return written
