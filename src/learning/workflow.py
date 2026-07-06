"""Exception & workflow management (spec Ch. 15; REQ-005, REQ-020).

Finding triage states: new -> in_review -> confirmed | false_positive;
confirmed findings proceed -> remediated -> closed with evidence (a re-run
reference or resolution note). Terminal states: closed, false_positive.
Every action appends to the run's workflow.jsonl — the audit trail — and
status/assignee changes rewrite findings.json canonically.

The exception register (§13.3) is a filtered view of this data: every
finding not marked false positive, tracked with owner, status, opened and
closed dates, and resolution notes. It feeds the < 0.1% unresolved-exceptions
metric and the sign-off package's closure evidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from src.fingerprint.models import Finding, FindingsReport, WorkflowEvent
from src.runner.run import DEFAULT_RUNS_DIR

WORKFLOW_FILENAME = "workflow.jsonl"

# action -> (required current status, resulting status)
TRANSITIONS = {
    "resolve": ("confirmed", "remediated"),
    "close": ("remediated", "closed"),
}
ASSIGNABLE_STATUSES = ("new", "in_review", "confirmed", "remediated")
TERMINAL_STATUSES = ("closed", "false_positive")


class WorkflowError(Exception):
    """Invalid workflow action: unknown finding or a transition the §15.1
    state machine does not allow."""


def _dump_json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n").encode("utf-8")


@dataclass
class _Located:
    run_dir: Path
    report: FindingsReport
    finding: Finding


def _locate(finding_id: str, runs_dir: Path | str) -> _Located:
    run_id = finding_id.rsplit("-F", 1)[0]
    run_dir = Path(runs_dir) / run_id
    path = run_dir / "findings.json"
    if not path.is_file():
        raise WorkflowError(f"no findings report for run {run_id!r} at {path}")
    report = FindingsReport.model_validate(
        json.loads(path.read_text(encoding="utf-8")))
    finding = next((f for f in report.findings if f.finding_id == finding_id),
                   None)
    if finding is None:
        raise WorkflowError(f"finding {finding_id!r} not found in run {run_id}")
    return _Located(run_dir=run_dir, report=report, finding=finding)


def _persist(located: _Located, event: WorkflowEvent) -> WorkflowEvent:
    (located.run_dir / "findings.json").write_bytes(
        _dump_json_bytes(located.report.model_dump(mode="json")))
    with (located.run_dir / WORKFLOW_FILENAME).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event.model_dump(mode="json"), sort_keys=True) + "\n")
    return event


def record_event(run_dir: Path, event: WorkflowEvent) -> None:
    """Append an event without touching findings.json (used by apply_review
    to mirror review decisions into the unified workflow history)."""
    with (Path(run_dir) / WORKFLOW_FILENAME).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event.model_dump(mode="json"), sort_keys=True) + "\n")


def assign(finding_id: str, assignee: str, *, actor: str = "analyst",
           comment: str | None = None,
           runs_dir: Path | str = DEFAULT_RUNS_DIR,
           now: datetime | None = None) -> WorkflowEvent:
    """Set the finding's owner. A first assignment moves new -> in_review."""
    located = _locate(finding_id, runs_dir)
    finding = located.finding
    if finding.status not in ASSIGNABLE_STATUSES:
        raise WorkflowError(
            f"cannot assign {finding_id}: status {finding.status!r} is terminal")
    from_status = finding.status
    if finding.status == "new":
        finding.status = "in_review"
    finding.assignee = assignee
    event = WorkflowEvent(
        run_id=located.report.run.run_id, finding_id=finding_id,
        action="assign", actor=actor, assignee=assignee, text=comment,
        from_status=from_status, to_status=finding.status,
        created_at=now or datetime.now(timezone.utc),
    )
    return _persist(located, event)


def comment(finding_id: str, text: str, *, actor: str = "analyst",
            runs_dir: Path | str = DEFAULT_RUNS_DIR,
            now: datetime | None = None) -> WorkflowEvent:
    located = _locate(finding_id, runs_dir)
    event = WorkflowEvent(
        run_id=located.report.run.run_id, finding_id=finding_id,
        action="comment", actor=actor, text=text,
        created_at=now or datetime.now(timezone.utc),
    )
    return _persist(located, event)


def _transition(finding_id: str, action: str, text: str, actor: str,
                runs_dir: Path | str, now: datetime | None) -> WorkflowEvent:
    required, target = TRANSITIONS[action]
    located = _locate(finding_id, runs_dir)
    finding = located.finding
    if finding.status != required:
        raise WorkflowError(
            f"cannot {action} {finding_id}: status is {finding.status!r}, "
            f"{action} requires {required!r} (spec §15.1)")
    if not text:
        raise WorkflowError(f"{action} requires a note/evidence (spec §15.1)")
    from_status = finding.status
    finding.status = target
    event = WorkflowEvent(
        run_id=located.report.run.run_id, finding_id=finding_id,
        action="transition", actor=actor, text=text,
        from_status=from_status, to_status=target,
        created_at=now or datetime.now(timezone.utc),
    )
    return _persist(located, event)


def resolve(finding_id: str, note: str, *, actor: str = "analyst",
            runs_dir: Path | str = DEFAULT_RUNS_DIR,
            now: datetime | None = None) -> WorkflowEvent:
    """confirmed -> remediated, with the remediation note."""
    return _transition(finding_id, "resolve", note, actor, runs_dir, now)


def close(finding_id: str, evidence: str, *, actor: str = "analyst",
          runs_dir: Path | str = DEFAULT_RUNS_DIR,
          now: datetime | None = None) -> WorkflowEvent:
    """remediated -> closed, with evidence (re-run reference or note)."""
    return _transition(finding_id, "close", evidence, actor, runs_dir, now)


def history(finding_id: str,
            runs_dir: Path | str = DEFAULT_RUNS_DIR) -> list[WorkflowEvent]:
    run_id = finding_id.rsplit("-F", 1)[0]
    path = Path(runs_dir) / run_id / WORKFLOW_FILENAME
    if not path.is_file():
        return []
    events = [WorkflowEvent.model_validate(json.loads(line))
              for line in path.read_text(encoding="utf-8").splitlines()
              if line.strip()]
    return [e for e in events if e.finding_id == finding_id]


def exception_register(run_id: str,
                       runs_dir: Path | str = DEFAULT_RUNS_DIR) -> list[dict]:
    """The §13.3 register: every finding not marked false positive, with
    owner, status, opened/closed dates, and resolution notes."""
    run_dir = Path(runs_dir) / run_id
    findings_path = run_dir / "findings.json"
    if not findings_path.is_file():
        raise WorkflowError(f"no findings report for run {run_id!r}")
    report = FindingsReport.model_validate(
        json.loads(findings_path.read_text(encoding="utf-8")))
    events_path = run_dir / WORKFLOW_FILENAME
    events = []
    if events_path.is_file():
        events = [WorkflowEvent.model_validate(json.loads(line))
                  for line in events_path.read_text(encoding="utf-8").splitlines()
                  if line.strip()]

    opened = date.fromisoformat(run_id[4:14]).isoformat()
    register = []
    for finding in report.findings:
        if finding.status == "false_positive":
            continue
        finding_events = [e for e in events if e.finding_id == finding.finding_id]
        closed_at = next(
            (e.created_at.date().isoformat() for e in finding_events
             if e.action == "transition" and e.to_status == "closed"
             and e.created_at), None)
        resolution = "; ".join(
            e.text for e in finding_events
            if e.action == "transition" and e.text
            and e.to_status in ("remediated", "closed"))
        plan = ""
        if finding.sample_records:
            plan = finding.sample_records[0].keys.get("plan_id", "")
        register.append({
            "exception": finding.finding_id,
            "plan": plan,
            "failure_mode": finding.failure_mode,
            "severity": finding.severity,
            "owner": finding.assignee or "",
            "status": finding.status,
            "opened": opened,
            "closed": closed_at or "",
            "resolution": resolution,
        })
    return register
