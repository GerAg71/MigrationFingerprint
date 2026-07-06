"""FastAPI application (MS-3.1; spec Ch. 18).

The endpoint-catalog subset of §18.2: platform pairs, fingerprints (current,
versions, suite, learning history, publish), runs (create, status, suite,
findings), findings (detail, review), and report artifacts (findings +
reconciliation suite). Bodies mirror the domain pydantic models (REQ-030);
errors follow the §18.5 envelope {"error": {code, message, detail,
request_id}} with a per-request id.

POC scope (Appendix F): no authentication — the product adds Cognito JWT
role scopes at this layer (§18.4) — and POST /runs executes synchronously
in-process; the product replaces that call with the SQS enqueue (§7.4). The
engine underneath is identical. Fully local: no AWS anything.

Run locally:  uv run uvicorn src.api.app:app --reload
OpenAPI companion artifact:  uv run python -m src.api  (writes docs/openapi.json)
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from pydantic import ValidationError

from src.api.schemas import (
    AssignRequest,
    CommentRequest,
    FingerprintVersions,
    PairSummary,
    PublishAccepted,
    PublishRequest,
    ReviewAccepted,
    ReviewRequest,
    RunAccepted,
    RunRequest,
    SuiteView,
    TransitionRequest,
    VersionInfo,
)
from src.fingerprint.loader import (
    DEFAULT_FINGERPRINT_DIR,
    FingerprintDirectoryError,
    list_versions,
    load,
    load_file,
)
from src.fingerprint.models import (
    ConversionRun,
    Finding,
    FindingsReport,
    Fingerprint,
    LearningEvent,
    WorkflowEvent,
)
from src.fingerprint.prioritize import prioritized_suite
from src.ingest.registration import PartialFileError
from src.learning.versioning import PublishError, publish_draft
from src.learning.workflow import (
    WorkflowError,
    assign as workflow_assign,
    close as workflow_close,
    comment as workflow_comment,
    exception_register,
    history as workflow_history,
    resolve as workflow_resolve,
)
from src.learning.writeback import ReviewError, apply_review, read_events
from src.report.html import (
    RECON_KINDS,
    render_findings_html,
    render_reconciliation_html,
)
from src.runner.run import DEFAULT_RUNS_DIR, DatasetGateError, run as run_conversion

API_VERSION = "0.1.0"
UI_INDEX = Path(__file__).resolve().parents[2] / "ui" / "index.html"


# --- error envelope (§18.5) -----------------------------------------------------


def _error(status: int, message: str, request: Request, detail=None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {
        "code": status,
        "message": message,
        "detail": detail,
        "request_id": getattr(request.state, "request_id", None),
    }})


class NotFoundError(Exception):
    pass


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    @app.exception_handler(FileNotFoundError)
    async def _not_found(request: Request, exc):
        return _error(404, str(exc), request)

    @app.exception_handler(ReviewError)
    @app.exception_handler(PublishError)
    async def _conflict(request: Request, exc):
        return _error(409, str(exc), request)

    @app.exception_handler(WorkflowError)
    async def _workflow(request: Request, exc):
        message = str(exc)
        not_found = "not found" in message or "no findings report" in message
        return _error(404 if not_found else 409, message, request)

    @app.exception_handler(DatasetGateError)
    @app.exception_handler(PartialFileError)
    @app.exception_handler(FingerprintDirectoryError)
    async def _gate(request: Request, exc):
        return _error(422, str(exc), request)

    @app.exception_handler(ValidationError)
    async def _pydantic(request: Request, exc: ValidationError):
        return _error(422, "schema validation failed", request,
                      detail=exc.errors(include_url=False))

    @app.exception_handler(RequestValidationError)
    async def _request_validation(request: Request, exc: RequestValidationError):
        return _error(422, "request validation failed", request,
                      detail=exc.errors())

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        return _error(500, f"{type(exc).__name__}: {exc}", request)


# --- helpers ----------------------------------------------------------------------


def _dirs(request: Request) -> tuple[Path, Path]:
    return request.app.state.fingerprint_dir, request.app.state.runs_dir


def _load_report(runs_dir: Path, run_id: str) -> FindingsReport:
    path = runs_dir / run_id / "findings.json"
    if not path.is_file():
        raise NotFoundError(f"no findings report for run {run_id!r}")
    return FindingsReport.model_validate(
        json.loads(path.read_text(encoding="utf-8")))


def _version_infos(fingerprint_dir: Path, pair_id: str) -> list[VersionInfo]:
    infos = []
    for version in list_versions(pair_id, fingerprint_dir):
        payload = json.loads(
            (fingerprint_dir / pair_id / version / "fingerprint.json")
            .read_text(encoding="utf-8"))
        infos.append(VersionInfo(version=version,
                                 status=payload.get("status", "unknown")))
    return infos


# --- application ------------------------------------------------------------------


def create_app(
    fingerprint_dir: Path | str = DEFAULT_FINGERPRINT_DIR,
    runs_dir: Path | str = DEFAULT_RUNS_DIR,
) -> FastAPI:
    app = FastAPI(
        title="MAPTIVA Migration Fingerprint API",
        version=API_VERSION,
        description=(
            "Targeted, not generic: prioritized plan-conversion validation "
            "driven by the platform pair's Migration Fingerprint. POC layer — "
            "no authentication (product adds Cognito role scopes, spec §18.4); "
            "runs execute synchronously in-process (product enqueues to SQS)."
        ),
    )
    app.state.fingerprint_dir = Path(fingerprint_dir)
    app.state.runs_dir = Path(runs_dir)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex[:12]
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    _register_error_handlers(app)

    # --- dashboard (MS-3.2, spec Ch. 20) — excluded from the OpenAPI catalog

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/ui")

    @app.get("/ui", include_in_schema=False)
    def dashboard():
        if not UI_INDEX.is_file():
            raise NotFoundError(f"dashboard not found at {UI_INDEX}")
        return FileResponse(UI_INDEX, media_type="text/html")

    # --- platform pairs & fingerprints (UC-01) ---------------------------------

    @app.get("/platform-pairs", response_model=list[PairSummary],
             tags=["fingerprints"])
    def get_pairs(request: Request):
        fingerprint_dir, _ = _dirs(request)
        pairs = []
        if fingerprint_dir.is_dir():
            for entry in sorted(fingerprint_dir.iterdir()):
                if not entry.is_dir():
                    continue
                try:
                    fp = load(entry.name, fingerprint_dir=fingerprint_dir)
                except (FileNotFoundError, FingerprintDirectoryError):
                    continue
                pairs.append(PairSummary(
                    pair_id=fp.fingerprint_id, current_version=fp.version,
                    modes=len(fp.failure_modes), rules=len(fp.detection_rules),
                ))
        return pairs

    @app.get("/fingerprints/{pair_id}", response_model=Fingerprint,
             tags=["fingerprints"])
    def get_fingerprint(pair_id: str, request: Request):
        fingerprint_dir, _ = _dirs(request)
        return load(pair_id, fingerprint_dir=fingerprint_dir)

    @app.get("/fingerprints/{pair_id}/versions",
             response_model=FingerprintVersions, tags=["fingerprints"])
    def get_versions(pair_id: str, request: Request):
        fingerprint_dir, _ = _dirs(request)
        current = load(pair_id, fingerprint_dir=fingerprint_dir).version
        return FingerprintVersions(
            pair_id=pair_id, current=current,
            versions=_version_infos(fingerprint_dir, pair_id),
        )

    @app.get("/fingerprints/{pair_id}/versions/{version}",
             response_model=Fingerprint, tags=["fingerprints"])
    def get_fingerprint_version(pair_id: str, version: str, request: Request):
        fingerprint_dir, _ = _dirs(request)
        return load(pair_id, version=version, fingerprint_dir=fingerprint_dir)

    @app.get("/fingerprints/{pair_id}/suite", response_model=SuiteView,
             tags=["fingerprints"])
    def get_suite(pair_id: str, request: Request,
                  version: str | None = Query(default=None)):
        fingerprint_dir, _ = _dirs(request)
        fp = load(pair_id, version=version, fingerprint_dir=fingerprint_dir)
        return SuiteView(pair_id=pair_id, version=fp.version,
                         suite=prioritized_suite(fp))

    @app.get("/fingerprints/{pair_id}/learning-history",
             response_model=list[LearningEvent], tags=["learning"])
    def get_learning_history(pair_id: str, request: Request,
                             fm: str | None = Query(default=None)):
        fingerprint_dir, _ = _dirs(request)
        events = read_events(pair_id, fingerprint_dir)
        return [e for e in events if fm is None or e.fm_id == fm]

    @app.post("/fingerprints/{pair_id}/publish",
              response_model=PublishAccepted, tags=["learning"])
    def post_publish(pair_id: str, body: PublishRequest, request: Request):
        fingerprint_dir, _ = _dirs(request)
        result = publish_draft(pair_id, body.bump, changelog=body.changelog,
                               fingerprint_dir=fingerprint_dir)
        return PublishAccepted(pair_id=pair_id, old_version=result.old_version,
                               new_version=result.new_version, diff=result.diff)

    # --- runs (UC-02) ------------------------------------------------------------

    @app.post("/runs", response_model=RunAccepted, status_code=202, tags=["runs"])
    def post_run(body: RunRequest, request: Request):
        fingerprint_dir, runs_dir = _dirs(request)
        result = run_conversion(
            body.pair_id, body.source_dir, body.target_dir,
            version=body.fingerprint_version, plans=body.plans, wave=body.wave,
            fingerprint_dir=fingerprint_dir, runs_dir=runs_dir,
            layout_dir=body.layout_dir,
        )
        return RunAccepted(
            run_id=result.run.run_id, status=result.run.status,
            fingerprint_version=result.run.fingerprint_version,
            summary=result.report.run.summary, findings=len(result.findings),
        )

    @app.get("/runs/{run_id}", response_model=ConversionRun, tags=["runs"])
    def get_run(run_id: str, request: Request):
        _, runs_dir = _dirs(request)
        path = runs_dir / run_id / "run.json"
        if not path.is_file():
            raise NotFoundError(f"run {run_id!r} not found")
        return ConversionRun.model_validate(
            json.loads(path.read_text(encoding="utf-8")))

    @app.get("/runs/{run_id}/suite", tags=["runs"])
    def get_run_suite(run_id: str, request: Request):
        _, runs_dir = _dirs(request)
        path = runs_dir / run_id / "suite_snapshot.json"
        if not path.is_file():
            raise NotFoundError(f"run {run_id!r} has no suite snapshot")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/runs/{run_id}/findings", response_model=list[Finding],
             tags=["findings"])
    def get_findings(run_id: str, request: Request,
                     severity: str | None = Query(default=None),
                     status: str | None = Query(default=None)):
        _, runs_dir = _dirs(request)
        findings = _load_report(runs_dir, run_id).findings
        if severity:
            findings = [f for f in findings if f.severity == severity]
        if status:
            findings = [f for f in findings if f.status == status]
        return findings

    @app.get("/findings/{finding_id}", response_model=Finding, tags=["findings"])
    def get_finding(finding_id: str, request: Request):
        _, runs_dir = _dirs(request)
        run_id = finding_id.rsplit("-F", 1)[0]
        report = _load_report(runs_dir, run_id)
        finding = next((f for f in report.findings
                        if f.finding_id == finding_id), None)
        if finding is None:
            raise NotFoundError(f"finding {finding_id!r} not found")
        return finding

    # --- reviews (UC-04, the Learning Loop) ---------------------------------------

    @app.post("/findings/{finding_id}/review", response_model=ReviewAccepted,
              tags=["learning"])
    def post_review(finding_id: str, body: ReviewRequest, request: Request):
        fingerprint_dir, runs_dir = _dirs(request)
        outcome = apply_review(
            finding_id, body.decision, reviewer=body.reviewer,
            comment=body.comment, runs_dir=runs_dir,
            fingerprint_dir=fingerprint_dir,
        )
        event = outcome.event
        return ReviewAccepted(
            finding_status=body.decision,
            learning_event={  # mirrors the §18.2 sample response
                "failure_mode": event.fm_id,
                "probability_before": event.probability_before,
                "probability_after": event.probability_after,
                "fingerprint_version_created": event.draft_version,
                "pending_publish": True,
            },
        )

    # --- exception workflow (spec Ch. 15) -------------------------------------------

    @app.post("/findings/{finding_id}/assign", response_model=WorkflowEvent,
              tags=["workflow"])
    def post_assign(finding_id: str, body: AssignRequest, request: Request):
        _, runs_dir = _dirs(request)
        return workflow_assign(finding_id, body.assignee, actor=body.actor,
                               comment=body.comment, runs_dir=runs_dir)

    @app.post("/findings/{finding_id}/comment", response_model=WorkflowEvent,
              tags=["workflow"])
    def post_comment(finding_id: str, body: CommentRequest, request: Request):
        _, runs_dir = _dirs(request)
        return workflow_comment(finding_id, body.text, actor=body.actor,
                                runs_dir=runs_dir)

    @app.post("/findings/{finding_id}/resolve", response_model=WorkflowEvent,
              tags=["workflow"])
    def post_resolve(finding_id: str, body: TransitionRequest, request: Request):
        _, runs_dir = _dirs(request)
        return workflow_resolve(finding_id, body.text, actor=body.actor,
                                runs_dir=runs_dir)

    @app.post("/findings/{finding_id}/close", response_model=WorkflowEvent,
              tags=["workflow"])
    def post_close(finding_id: str, body: TransitionRequest, request: Request):
        _, runs_dir = _dirs(request)
        return workflow_close(finding_id, body.text, actor=body.actor,
                              runs_dir=runs_dir)

    @app.get("/findings/{finding_id}/history", response_model=list[WorkflowEvent],
             tags=["workflow"])
    def get_finding_history(finding_id: str, request: Request):
        _, runs_dir = _dirs(request)
        return workflow_history(finding_id, runs_dir)

    @app.get("/runs/{run_id}/exceptions", tags=["workflow"])
    def get_exceptions(run_id: str, request: Request,
                       status: str | None = Query(default=None)):
        _, runs_dir = _dirs(request)
        register = exception_register(run_id, runs_dir)
        if status:
            register = [row for row in register if row["status"] == status]
        return register

    # --- AI assistance (spec Ch. 8; stub provider in the POC) -----------------------

    @app.get("/findings/{finding_id}/explanation", tags=["ai"])
    def get_explanation(finding_id: str, request: Request):
        """ExplainReconciliationVariance() — read-only suggestion (REQ-019),
        rendered visibly labeled as AI-generated (§20.4)."""
        from src.ai.orchestrator import AIOrchestrator

        fingerprint_dir, runs_dir = _dirs(request)
        run_id = finding_id.rsplit("-F", 1)[0]
        report = _load_report(runs_dir, run_id)
        finding = next((f for f in report.findings
                        if f.finding_id == finding_id), None)
        if finding is None:
            raise NotFoundError(f"finding {finding_id!r} not found")
        failure_mode = None
        try:
            fingerprint = load(report.run.pair_id,
                               version=report.run.fingerprint_version,
                               fingerprint_dir=fingerprint_dir)
            failure_mode = next((m for m in fingerprint.failure_modes
                                 if m.id == finding.failure_mode), None)
        except (FileNotFoundError, FingerprintDirectoryError):
            pass  # explanation still works without the mode context
        orchestrator = AIOrchestrator(audit_path=runs_dir / "ai_audit.jsonl")
        return orchestrator.explain_variance(finding, failure_mode).to_payload()

    # --- report artifacts (§13) -----------------------------------------------------

    @app.get("/runs/{run_id}/report", tags=["reports"])
    def get_report(run_id: str, request: Request,
                   format: str = Query(default="json", pattern="^(json|html)$")):
        _, runs_dir = _dirs(request)
        report = _load_report(runs_dir, run_id)
        if format == "json":
            return report
        return HTMLResponse(render_findings_html(report))

    @app.post("/reports/sign-off-package", tags=["reports"])
    def post_signoff(body: dict, request: Request):
        """Assemble the §13.4 sign-off package for a run. Body:
        {run_id, narrative?, approved_by?}."""
        from src.report.signoff import build_signoff_package

        fingerprint_dir, runs_dir = _dirs(request)
        run_id = body.get("run_id")
        if not run_id:
            raise RequestValidationError([{"loc": ("body", "run_id"),
                                           "msg": "field required",
                                           "type": "missing"}])
        result = build_signoff_package(
            run_id, runs_dir=runs_dir, fingerprint_dir=fingerprint_dir,
            narrative=body.get("narrative"),
            approved_by=body.get("approved_by"),
        )
        return {"package": str(result.package_path),
                "manifest": result.manifest}

    @app.get("/runs/{run_id}/reconciliation/{kind}", response_class=HTMLResponse,
             tags=["reports"])
    def get_reconciliation(run_id: str, kind: str, request: Request):
        if kind not in RECON_KINDS:
            raise NotFoundError(
                f"unknown reconciliation report {kind!r}; "
                f"expected one of {sorted(RECON_KINDS)}")
        _, runs_dir = _dirs(request)
        recon_path = runs_dir / run_id / "reconciliation.json"
        if not recon_path.is_file():
            raise NotFoundError(f"run {run_id!r} has no reconciliation aggregates")
        recon = json.loads(recon_path.read_text(encoding="utf-8"))
        report = _load_report(runs_dir, run_id)
        return HTMLResponse(render_reconciliation_html(kind, recon, report))

    return app


app = create_app()
