"""`fingerprint` CLI (CLI_SPEC.md). MS-1.2 surface: validate, suite.

Exit codes (uniform across commands, CLI_SPEC):
  0  success
  1  runtime error (missing file/pair, bad arguments, unhandled exception)
  2  findings present with --fail-on-findings (run command; later milestone)
  3  refusal by validation gate (schema-invalid fingerprint, REQ-010;
     store-consistency faults)

Every command accepts --json for machine-readable output (default: table).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from src.fingerprint.loader import (
    DEFAULT_FINGERPRINT_DIR,
    FingerprintDirectoryError,
    load,
    load_file,
)
from src.fingerprint.models import FindingsReport
from src.fingerprint.prioritize import SEVERITY_RANK, prioritized_suite
from src.ingest.registration import PartialFileError
from src.runner.run import DEFAULT_RUNS_DIR, DatasetGateError, run as run_conversion

EXIT_OK = 0
EXIT_RUNTIME = 1
EXIT_FINDINGS = 2
EXIT_REFUSED = 3


def _pathed_errors(exc: ValidationError) -> list[str]:
    """One line per error: dotted.path: message (REQ-010)."""
    lines = []
    for err in exc.errors(include_url=False):
        path = ".".join(str(part) for part in err["loc"]) or "(root)"
        lines.append(f"{path}: {err['msg']}")
    return lines


def _print_validation_failure(exc: ValidationError, source: str, as_json: bool) -> None:
    if as_json:
        print(json.dumps(
            {"ok": False, "file": source, "errors": _pathed_errors(exc)}, indent=2
        ))
    else:
        print(f"INVALID {source}", file=sys.stderr)
        for line in _pathed_errors(exc):
            print(f"  {line}", file=sys.stderr)


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        fingerprint = load_file(args.file)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    except json.JSONDecodeError as exc:
        print(f"INVALID {args.file}: not valid JSON — {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except ValidationError as exc:
        _print_validation_failure(exc, str(args.file), args.json)
        return EXIT_REFUSED

    modes, rules = len(fingerprint.failure_modes), len(fingerprint.detection_rules)
    if args.json:
        print(json.dumps({
            "ok": True,
            "pair": fingerprint.fingerprint_id,
            "version": fingerprint.version,
            "status": fingerprint.status,
            "modes": modes,
            "rules": rules,
        }))
    else:
        print(f"OK {fingerprint.fingerprint_id} {fingerprint.version} — "
              f"{modes} modes, {rules} rules")
    return EXIT_OK


def cmd_pairs(args: argparse.Namespace) -> int:
    """List platform pairs discovered under the fingerprint dir (CLI_SPEC)."""
    fingerprint_dir = Path(args.fingerprint_dir)
    pairs = []
    if fingerprint_dir.is_dir():
        for entry in sorted(fingerprint_dir.iterdir()):
            if not entry.is_dir():
                continue
            try:
                fp = load(entry.name, fingerprint_dir=fingerprint_dir)
            except (FileNotFoundError, FingerprintDirectoryError):
                continue
            except ValidationError as exc:
                _print_validation_failure(exc, entry.name, args.json)
                return EXIT_REFUSED
            pairs.append({
                "pair_id": fp.fingerprint_id, "version": fp.version,
                "status": fp.status, "modes": len(fp.failure_modes),
                "rules": len(fp.detection_rules),
            })
    if args.json:
        print(json.dumps(pairs, indent=2))
        return EXIT_OK
    print(f"{'PAIR':<28} {'VERSION':<9} {'STATUS':<10} {'MODES':>5} {'RULES':>5}")
    for pair in pairs:
        print(f"{pair['pair_id']:<28} {pair['version']:<9} "
              f"{pair['status']:<10} {pair['modes']:>5} {pair['rules']:>5}")
    return EXIT_OK


def cmd_suite(args: argparse.Namespace) -> int:
    try:
        fingerprint = load(args.pair, args.version, args.fingerprint_dir)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    except FingerprintDirectoryError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except ValidationError as exc:
        _print_validation_failure(exc, f"{args.pair}@{args.version or 'latest'}", args.json)
        return EXIT_REFUSED

    suite = prioritized_suite(fingerprint)
    if args.json:
        print(json.dumps({
            "pair": fingerprint.fingerprint_id,
            "version": fingerprint.version,
            "suite": [entry.model_dump(mode="json") for entry in suite],
        }, indent=2))
        return EXIT_OK

    print(f"Prioritized suite — {fingerprint.fingerprint_id} v{fingerprint.version} "
          f"({len(suite)} rules)")
    header = f"{'ORDER':>5}  {'RULE':<24} {'FM':<7} {'SCORE':<7} {'SEVERITY':<9} "
    header += f"{'DATASETS':<28} STATUS"
    print(header)
    for entry in suite:
        datasets = f"{entry.source_dataset or '-'} -> {entry.target_dataset}"
        print(f"{entry.order:>5}  {entry.rule_id:<24} {entry.fm_id:<7} "
              f"{str(entry.priority_score):<7} {entry.severity:<9} "
              f"{datasets:<28} {entry.status}")
    return EXIT_OK


def _load_report(runs_dir: str, run_id: str) -> FindingsReport:
    path = Path(runs_dir) / run_id / "findings.json"
    if not path.is_file():
        raise FileNotFoundError(f"no findings report for run {run_id!r} at {path}")
    return FindingsReport.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _severity_mix_text(mix: dict) -> str:
    return (" ".join(f"{sev}={mix[sev]}" for sev in SEVERITY_RANK if sev in mix)
            or "none")


def cmd_run(args: argparse.Namespace) -> int:
    if args.fail_on_findings not in (None, "ANY") and \
            args.fail_on_findings not in SEVERITY_RANK:
        print(f"error: --fail-on-findings must be one of {list(SEVERITY_RANK)}",
              file=sys.stderr)
        return EXIT_RUNTIME
    try:
        result = run_conversion(
            args.pair, args.source_dir, args.target_dir,
            version=args.version,
            plans=args.plans.split(",") if args.plans else None,
            wave=args.wave,
            fingerprint_dir=args.fingerprint_dir,
            runs_dir=args.runs_dir,
            layout_dir=args.layout_dir,
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    except (FingerprintDirectoryError, DatasetGateError, PartialFileError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except ValidationError as exc:
        _print_validation_failure(exc, f"{args.pair}@{args.version or 'latest'}",
                                  args.json)
        return EXIT_REFUSED

    summary = result.report.run.summary
    skipped = sum(1 for item in result.report.suite if item.outcome == "skipped")
    if args.json:
        print(json.dumps({
            "run_id": result.run.run_id,
            "pair": result.run.pair_id,
            "fingerprint_version": result.run.fingerprint_version,
            "summary": summary.model_dump(mode="json"),
            "skipped": skipped,
            "findings": len(result.findings),
            "report": str(result.run_dir / "findings.json"),
        }, indent=2))
    else:
        print(f"Run {result.run.run_id} — {result.run.pair_id} "
              f"v{result.run.fingerprint_version}")
        print(f"Rules: {summary.rules_run} run, {summary.passed} passed, "
              f"{summary.failed} failed, {skipped} skipped")
        print(f"Records affected: {summary.records_affected}   "
              f"Severity mix: {_severity_mix_text(summary.severity_mix)}")
        print(f"Report: {result.run_dir / 'findings.json'}")

    if args.fail_on_findings and result.findings:
        if args.fail_on_findings == "ANY":
            return EXIT_FINDINGS
        gate = SEVERITY_RANK[args.fail_on_findings]
        if any(SEVERITY_RANK[f.severity] <= gate for f in result.findings):
            return EXIT_FINDINGS
    return EXIT_OK


def cmd_findings(args: argparse.Namespace) -> int:
    try:
        report = _load_report(args.runs_dir, args.run_id)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME

    findings = report.findings
    if args.severity:
        findings = [f for f in findings if f.severity == args.severity]
    if args.status:
        findings = [f for f in findings if f.status == args.status]

    if args.json:
        print(json.dumps([f.model_dump(mode="json") for f in findings], indent=2))
        return EXIT_OK

    print(f"Findings for {args.run_id} — {len(findings)} of "
          f"{len(report.findings)} shown")
    print(f"{'FINDING':<28} {'FM':<7} {'RULE':<24} {'SEVERITY':<9} "
          f"{'RECORDS':>7} STATUS")
    for f in findings:
        print(f"{f.finding_id:<28} {f.failure_mode:<7} {f.rule_id:<24} "
              f"{f.severity:<9} {f.records_affected:>7} {f.status}")
    return EXIT_OK


def cmd_show(args: argparse.Namespace) -> int:
    run_id = args.finding_id.rsplit("-F", 1)[0]
    try:
        report = _load_report(args.runs_dir, run_id)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    finding = next((f for f in report.findings
                    if f.finding_id == args.finding_id), None)
    if finding is None:
        print(f"error: finding {args.finding_id!r} not found in run {run_id}",
              file=sys.stderr)
        return EXIT_RUNTIME

    if args.json:
        print(json.dumps(finding.model_dump(mode="json"), indent=2))
        return EXIT_OK

    print(f"{finding.finding_id}  [{finding.severity}]  "
          f"{finding.failure_mode} / {finding.rule_id}  status={finding.status}")
    print(f"Records affected: {finding.records_affected} "
          f"(showing {len(finding.sample_records)} inline)")
    if finding.sample_records:
        key_cols = sorted({k for r in finding.sample_records for k in r.keys})
        print(f"{' | '.join(key_cols)} | source | target | delta")
        for record in finding.sample_records:
            keys = " | ".join(record.keys.get(k, "") for k in key_cols)
            print(f"{keys} | {record.source or ''} | {record.target or ''} | "
                  f"{record.delta if record.delta is not None else ''}")
    if finding.full_detail_uri:
        print(f"Drill-down CSV: {finding.full_detail_uri}")
    if finding.remediation:
        print(f"Remediation: {finding.remediation}")
    return EXIT_OK


def cmd_report(args: argparse.Namespace) -> int:
    from src.report.html import RECON_KINDS, render_findings_html, \
        render_reconciliation_html

    run_dir = Path(args.runs_dir) / args.run_id
    try:
        report = _load_report(args.runs_dir, args.run_id)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME

    written: list[Path] = []
    if args.recon:
        recon_path = run_dir / "reconciliation.json"
        if not recon_path.is_file():
            print(f"error: no reconciliation aggregates at {recon_path}",
                  file=sys.stderr)
            return EXIT_RUNTIME
        recon = json.loads(recon_path.read_text(encoding="utf-8"))
        kinds = list(RECON_KINDS) if args.recon == "all" else [args.recon]
        for kind in kinds:
            html = render_reconciliation_html(kind, recon, report)
            path = run_dir / f"reconciliation_{kind}.html"
            path.write_bytes(html.encode("utf-8"))
            written.append(path)
    elif args.format == "json":
        print((run_dir / "findings.json").read_text(encoding="utf-8"))
        return EXIT_OK
    else:
        path = run_dir / "findings.html"
        path.write_bytes(render_findings_html(report).encode("utf-8"))
        written.append(path)

    if args.json:
        print(json.dumps({"written": [str(p) for p in written]}, indent=2))
    else:
        for path in written:
            print(f"rendered: {path}")
    return EXIT_OK


def cmd_review(args: argparse.Namespace) -> int:
    from src.learning.writeback import ReviewError, apply_review

    try:
        outcome = apply_review(
            args.finding_id, args.decision,
            reviewer=args.reviewer, comment=args.comment,
            runs_dir=args.runs_dir, fingerprint_dir=args.fingerprint_dir,
        )
    except ReviewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME

    event = outcome.event
    if args.json:
        print(json.dumps(event.model_dump(mode="json"), indent=2, default=str))
        return EXIT_OK
    before, after = event.counters_before, event.counters_after
    print(f"{event.finding_id}: {event.decision} by {event.reviewer}")
    print(f"{event.fm_id} counters: detected {before.times_detected} -> "
          f"{after.times_detected}, confirmed {before.times_confirmed} -> "
          f"{after.times_confirmed}, false positives "
          f"{before.false_positives} -> {after.false_positives}")
    print(f"{event.fm_id} probability: {event.probability_before} -> "
          f"{event.probability_after} "
          f"(p_seed={event.formula_inputs['p_seed']}, k={event.formula_inputs['k']})")
    print(f"draft {event.draft_version} pending — run `fingerprint publish "
          f"--pair {event.pair_id} --bump patch` to finalize")
    return EXIT_OK


def cmd_publish(args: argparse.Namespace) -> int:
    from src.learning.versioning import PublishError, publish_draft

    try:
        result = publish_draft(
            args.pair, args.bump, changelog=args.changelog,
            fingerprint_dir=args.fingerprint_dir,
        )
    except (PublishError, FileNotFoundError, FingerprintDirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    except ValidationError as exc:
        _print_validation_failure(exc, f"{args.pair}@draft", args.json)
        return EXIT_REFUSED

    if args.json:
        print(json.dumps({
            "pair": args.pair, "old_version": result.old_version,
            "new_version": result.new_version, "diff": result.diff,
        }, indent=2))
        return EXIT_OK
    print(f"published {args.pair}: {result.old_version} -> {result.new_version}")
    _print_diff(result.diff)
    return EXIT_OK


def _print_diff(diff: dict) -> None:
    for key in ("modes_added", "modes_removed", "rules_added", "rules_removed"):
        if diff.get(key):
            print(f"{key.replace('_', ' ')}: {', '.join(diff[key])}")
    for entry in diff.get("modes_changed", []):
        parts = []
        if "probability" in entry:
            p = entry["probability"]
            parts.append(f"probability {p['before']} -> {p['after']} "
                         f"({p['delta']:+})")
        if "counters" in entry:
            after = entry["counters"]["after"]
            parts.append(f"counters detected={after['times_detected']} "
                         f"confirmed={after['times_confirmed']} "
                         f"fp={after['false_positives']}")
        if entry.get("rules_added"):
            parts.append(f"rules added: {', '.join(entry['rules_added'])}")
        if entry.get("remediation_changed"):
            parts.append("remediation changed")
        print(f"  {entry['fm_id']}: {'; '.join(parts)}")


def cmd_diff(args: argparse.Namespace) -> int:
    from src.learning.versioning import diff_versions

    try:
        diff = diff_versions(args.pair, getattr(args, "from"), args.to,
                             args.fingerprint_dir)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    except ValidationError as exc:
        _print_validation_failure(exc, args.pair, args.json)
        return EXIT_REFUSED
    if args.json:
        print(json.dumps(diff, indent=2))
    else:
        print(f"{args.pair}: {getattr(args, 'from')} -> {args.to}")
        _print_diff(diff)
        if not any(diff.values()):
            print("  no differences")
    return EXIT_OK


def cmd_history(args: argparse.Namespace) -> int:
    from src.learning.writeback import read_events

    events = read_events(args.pair, args.fingerprint_dir)
    if args.fm:
        events = [e for e in events if e.fm_id == args.fm]
    if args.json:
        print(json.dumps([e.model_dump(mode="json") for e in events],
                         indent=2, default=str))
        return EXIT_OK
    print(f"Learning history — {args.pair} ({len(events)} event(s))")
    for event in events:
        print(f"{event.fm_id}  {event.decision:<14} {event.probability_before}"
              f" -> {event.probability_after}  [{event.finding_id}] "
              f"by {event.reviewer}")
    return EXIT_OK


def _workflow_call(args: argparse.Namespace, fn, **kwargs) -> int:
    from src.learning.workflow import WorkflowError

    try:
        event = fn(**kwargs)
    except WorkflowError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    if args.json:
        print(json.dumps(event.model_dump(mode="json"), indent=2, default=str))
        return EXIT_OK
    detail = f" ({event.from_status} -> {event.to_status})" \
        if event.to_status else ""
    print(f"{event.finding_id}: {event.action}{detail} by {event.actor}")
    return EXIT_OK


def cmd_assign(args: argparse.Namespace) -> int:
    from src.learning.workflow import assign

    return _workflow_call(args, assign, finding_id=args.finding_id,
                          assignee=args.to, actor=args.actor,
                          comment=args.comment, runs_dir=args.runs_dir)


def cmd_comment(args: argparse.Namespace) -> int:
    from src.learning.workflow import comment

    return _workflow_call(args, comment, finding_id=args.finding_id,
                          text=args.text, actor=args.actor,
                          runs_dir=args.runs_dir)


def cmd_resolve(args: argparse.Namespace) -> int:
    from src.learning.workflow import resolve

    return _workflow_call(args, resolve, finding_id=args.finding_id,
                          note=args.note, actor=args.actor,
                          runs_dir=args.runs_dir)


def cmd_close(args: argparse.Namespace) -> int:
    from src.learning.workflow import close

    return _workflow_call(args, close, finding_id=args.finding_id,
                          evidence=args.evidence, actor=args.actor,
                          runs_dir=args.runs_dir)


def cmd_exceptions(args: argparse.Namespace) -> int:
    from src.learning.workflow import WorkflowError, exception_register

    try:
        register = exception_register(args.run_id, args.runs_dir)
    except WorkflowError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    if args.status:
        register = [row for row in register if row["status"] == args.status]
    if args.json:
        print(json.dumps(register, indent=2))
        return EXIT_OK
    open_count = sum(1 for row in register if row["status"] != "closed")
    print(f"Exception register — {args.run_id}: {len(register)} exception(s), "
          f"{open_count} open (spec §13.3)")
    print(f"{'EXCEPTION':<28} {'FM':<7} {'SEVERITY':<9} {'OWNER':<10} "
          f"{'STATUS':<15} {'CLOSED':<11} RESOLUTION")
    for row in register:
        print(f"{row['exception']:<28} {row['failure_mode']:<7} "
              f"{row['severity']:<9} {row['owner']:<10} {row['status']:<15} "
              f"{row['closed']:<11} {row['resolution']}")
    return EXIT_OK


def cmd_compile_matrix(args: argparse.Namespace) -> int:
    """Compile an Omni Format Matrix workbook into card layouts (+ optional
    COBOL extract-deck skeletons) — the Omni→Omni restore toolchain."""
    import zipfile

    from src.ingest.matrix import MatrixError, compile_matrix, write_artifacts

    try:
        result = compile_matrix(args.workbook)
        manifest = write_artifacts(result, args.out, decks=args.decks)
    except (FileNotFoundError, MatrixError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    totals = manifest["totals"]
    if args.json:
        print(json.dumps(manifest, indent=2))
        return EXIT_OK
    print(f"compiled {args.workbook} -> {args.out}")
    print(f"  {totals['processes']} processes, {totals['cards']} cards, "
          f"{totals['fields']} fields")
    print(f"  {totals['required_fields']} required, "
          f"{totals['filler_fields']} 'Not Used' fillers materialized"
          + ("; decks stamped" if args.decks else ""))
    for note in manifest["discrepancies"]:
        print(f"  WARNING: {note}")
    return EXIT_OK


def cmd_signoff(args: argparse.Namespace) -> int:
    from src.report.signoff import build_signoff_package

    try:
        result = build_signoff_package(
            args.run_id, runs_dir=args.runs_dir,
            fingerprint_dir=args.fingerprint_dir,
            narrative=args.narrative, approved_by=args.approved_by,
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    if args.json:
        print(json.dumps({"package": str(result.package_path),
                          "manifest": result.manifest}, indent=2))
        return EXIT_OK
    print(f"sign-off package: {result.package_path}")
    print(f"narrative: {result.manifest['narrative_source']}")
    for metric in result.manifest["metrics"]:
        print(f"  [{metric['status']:<7}] {metric['metric']} — "
              f"target {metric['target']}, actual {metric['actual']}")
    return EXIT_OK


def cmd_explain(args: argparse.Namespace) -> int:
    """AI-assisted variance explanation (spec §8.2) — stub provider, fully
    local; output is a suggestion, visibly labeled AI-generated."""
    from src.ai.orchestrator import AIGuardError, AIOrchestrator

    run_id = args.finding_id.rsplit("-F", 1)[0]
    try:
        report = _load_report(args.runs_dir, run_id)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME
    finding = next((f for f in report.findings
                    if f.finding_id == args.finding_id), None)
    if finding is None:
        print(f"error: finding {args.finding_id!r} not found", file=sys.stderr)
        return EXIT_RUNTIME
    failure_mode = None
    try:
        fingerprint = load(report.run.pair_id,
                           version=report.run.fingerprint_version,
                           fingerprint_dir=args.fingerprint_dir)
        failure_mode = next((m for m in fingerprint.failure_modes
                             if m.id == finding.failure_mode), None)
    except (FileNotFoundError, FingerprintDirectoryError, ValidationError):
        pass
    try:
        result = AIOrchestrator(
            audit_path=Path(args.runs_dir) / "ai_audit.jsonl"
        ).explain_variance(finding, failure_mode)
    except AIGuardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME

    if args.json:
        print(json.dumps(result.to_payload(), indent=2))
        return EXIT_OK
    output = result.output
    print(f"[AI-generated — provider {result.provider}, "
          f"confidence {result.confidence}"
          f"{', needs human review' if result.needs_review else ''}]")
    print(f"Explanation: {output.explanation}")
    print(f"Likely cause: {output.likely_cause}")
    print(f"Suggested check: {output.suggested_check}")
    return EXIT_OK


def cmd_author_mode(args: argparse.Namespace) -> int:
    from src.learning.versioning import author_failure_mode

    def ask(flag_value, prompt):
        if flag_value is not None:
            return flag_value
        if not sys.stdin.isatty():
            print(f"error: --{prompt} required in non-interactive use",
                  file=sys.stderr)
            raise SystemExit(EXIT_RUNTIME)
        return input(f"{prompt}: ")

    try:
        name = ask(args.name, "name")
        category = ask(args.category, "category")
        description = ask(args.description, "description")
        domains = ask(args.domains, "domains").split(",")
        impact = float(ask(args.impact, "impact"))
        remediation = ask(args.remediation, "remediation")
        rule_raw = ask(args.rule_json, "rule-json")
        rule_payload = json.loads(Path(rule_raw).read_text(encoding="utf-8")
                                  if Path(rule_raw).is_file() else rule_raw)
        mode = author_failure_mode(
            args.pair, name=name, category=category, description=description,
            data_domains=[d.strip() for d in domains], impact=impact,
            remediation=remediation, rule_payload=rule_payload,
            probability=args.probability,
            fingerprint_dir=args.fingerprint_dir,
        )
    except SystemExit as exc:
        return int(exc.code)
    except ValidationError as exc:
        _print_validation_failure(exc, f"{args.pair}@draft", args.json)
        return EXIT_REFUSED
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME

    print(f"added {mode.id} '{mode.name}' (probability {mode.probability}, "
          f"impact {mode.impact}) to the {args.pair} draft — publish with "
          f"--bump minor")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fingerprint",
        description="MAPTIVA Migration Fingerprint — targeted conversion validation",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser(
        "validate", help="Schema-validate a fingerprint file (exit 0/3)"
    )
    p_validate.add_argument("file", help="path to a fingerprint.json")
    p_validate.add_argument("--json", action="store_true", help="JSON output")
    p_validate.set_defaults(func=cmd_validate)

    p_pairs = sub.add_parser(
        "pairs", help="List platform pairs in the fingerprint store"
    )
    p_pairs.add_argument("--fingerprint-dir", default=str(DEFAULT_FINGERPRINT_DIR))
    p_pairs.add_argument("--json", action="store_true", help="JSON output")
    p_pairs.set_defaults(func=cmd_pairs)

    p_suite = sub.add_parser(
        "suite", help="Print the prioritized suite without running (spec §12.2)"
    )
    p_suite.add_argument("--pair", required=True, help="platform pair id")
    p_suite.add_argument("--version", help="fingerprint version (default: highest published)")
    p_suite.add_argument(
        "--fingerprint-dir", default=str(DEFAULT_FINGERPRINT_DIR),
        help="fingerprint store root (default: data/fingerprints/)",
    )
    p_suite.add_argument("--json", action="store_true", help="JSON output")
    p_suite.set_defaults(func=cmd_suite)

    p_run = sub.add_parser(
        "run", help="Execute a conversion run (spec §12.1; MS-1.5)"
    )
    p_run.add_argument("--pair", required=True, help="platform pair id")
    p_run.add_argument("--source-dir", required=True, help="source extract dir")
    p_run.add_argument("--target-dir", required=True, help="target extract dir")
    p_run.add_argument("--version", help="fingerprint version (default: highest published)")
    p_run.add_argument("--plans", help="comma-separated plan ids to scope the run")
    p_run.add_argument("--wave", help="wave label recorded in run scope")
    p_run.add_argument(
        "--layout-dir", default=None,
        help="directory of <dataset>.json LayoutSpecs for fixed-width .dat extracts",
    )
    p_run.add_argument(
        "--fail-on-findings", nargs="?", const="ANY", default=None,
        metavar="SEV",
        help="exit 2 when findings exist (optionally gate on minimum severity)",
    )
    p_run.add_argument("--fingerprint-dir", default=str(DEFAULT_FINGERPRINT_DIR))
    p_run.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    p_run.add_argument("--json", action="store_true", help="JSON output")
    p_run.set_defaults(func=cmd_run)

    p_findings = sub.add_parser("findings", help="List findings for a run")
    p_findings.add_argument("run_id")
    p_findings.add_argument("--severity", choices=list(SEVERITY_RANK))
    p_findings.add_argument("--status")
    p_findings.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    p_findings.add_argument("--json", action="store_true",
                            help="JSON output incl. sample records")
    p_findings.set_defaults(func=cmd_findings)

    p_show = sub.add_parser("show", help="Full detail for one finding")
    p_show.add_argument("finding_id")
    p_show.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    p_show.add_argument("--json", action="store_true", help="JSON output")
    p_show.set_defaults(func=cmd_show)

    p_report = sub.add_parser(
        "report", help="Re-render report artifacts for a run (MS-2.3)"
    )
    p_report.add_argument("run_id")
    p_report.add_argument("--format", choices=["json", "html"], default="html")
    p_report.add_argument(
        "--recon",
        choices=["plan", "participant", "loan", "contribution", "quality", "all"],
        help="render the client-facing reconciliation suite (spec §13.2)",
    )
    p_report.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    p_report.add_argument("--json", action="store_true", help="JSON output")
    p_report.set_defaults(func=cmd_report)

    def _workflow_parser(name: str, help_text: str, func):
        parser_ = sub.add_parser(name, help=help_text)
        parser_.add_argument("finding_id")
        parser_.add_argument("--actor", default="analyst")
        parser_.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
        parser_.add_argument("--json", action="store_true", help="JSON output")
        parser_.set_defaults(func=func)
        return parser_

    p_assign = _workflow_parser(
        "assign", "Assign an owner (new -> in_review; spec §15.2)", cmd_assign)
    p_assign.add_argument("--to", required=True, help="assignee")
    p_assign.add_argument("--comment")

    p_comment = _workflow_parser(
        "comment", "Add a comment to a finding's history", cmd_comment)
    p_comment.add_argument("--text", required=True)

    p_resolve = _workflow_parser(
        "resolve", "Mark a confirmed finding remediated (spec §15.1)", cmd_resolve)
    p_resolve.add_argument("--note", required=True, help="remediation note")

    p_close = _workflow_parser(
        "close", "Close a remediated finding with evidence (spec §15.1)", cmd_close)
    p_close.add_argument("--evidence", required=True,
                         help="re-run reference or resolution note")

    p_exceptions = sub.add_parser(
        "exceptions", help="Exception register for a run (spec §13.3)")
    p_exceptions.add_argument("run_id")
    p_exceptions.add_argument("--status")
    p_exceptions.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    p_exceptions.add_argument("--json", action="store_true", help="JSON output")
    p_exceptions.set_defaults(func=cmd_exceptions)

    p_review = sub.add_parser(
        "review", help="Record a review and apply the probability write-back "
                       "(spec §14.1–14.2; MS-2.4)"
    )
    p_review.add_argument("finding_id")
    p_review.add_argument("--decision", required=True,
                          choices=["confirmed", "false_positive"])
    p_review.add_argument("--comment")
    p_review.add_argument("--reviewer", default="analyst")
    p_review.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    p_review.add_argument("--fingerprint-dir", default=str(DEFAULT_FINGERPRINT_DIR))
    p_review.add_argument("--json", action="store_true", help="JSON output")
    p_review.set_defaults(func=cmd_review)

    p_publish = sub.add_parser(
        "publish", help="Finalize the draft fingerprint version (spec §14.5–14.6)"
    )
    p_publish.add_argument("--pair", required=True)
    p_publish.add_argument("--bump", required=True,
                           choices=["patch", "minor", "major"])
    p_publish.add_argument("--changelog")
    p_publish.add_argument("--fingerprint-dir", default=str(DEFAULT_FINGERPRINT_DIR))
    p_publish.add_argument("--json", action="store_true", help="JSON output")
    p_publish.set_defaults(func=cmd_publish)

    p_diff = sub.add_parser("diff", help="Version diff (spec §14.5)")
    p_diff.add_argument("--pair", required=True)
    p_diff.add_argument("--from", required=True, help="from version")
    p_diff.add_argument("--to", required=True, help="to version")
    p_diff.add_argument("--fingerprint-dir", default=str(DEFAULT_FINGERPRINT_DIR))
    p_diff.add_argument("--json", action="store_true", help="JSON output")
    p_diff.set_defaults(func=cmd_diff)

    p_history = sub.add_parser(
        "history", help="Learning history: probability timeline per failure mode"
    )
    p_history.add_argument("--pair", required=True)
    p_history.add_argument("--fm", help="filter to one failure mode id")
    p_history.add_argument("--fingerprint-dir", default=str(DEFAULT_FINGERPRINT_DIR))
    p_history.add_argument("--json", action="store_true", help="JSON output")
    p_history.set_defaults(func=cmd_history)

    p_matrix = sub.add_parser(
        "compile-matrix",
        help="Compile an Omni Format Matrix xlsx into card layouts and "
             "extract-deck skeletons (Omni->Omni restore)")
    p_matrix.add_argument("workbook")
    p_matrix.add_argument("--out", required=True, help="output directory")
    p_matrix.add_argument("--decks", action="store_true",
                          help="also stamp COBOL extract-deck skeletons")
    p_matrix.add_argument("--json", action="store_true", help="JSON output")
    p_matrix.set_defaults(func=cmd_compile_matrix)

    p_signoff = sub.add_parser(
        "signoff", help="Assemble the sign-off package for a run (spec §13.4)")
    p_signoff.add_argument("run_id")
    p_signoff.add_argument("--narrative",
                           help="analyst-provided executive narrative "
                                "(default: AI-generated, needing approval)")
    p_signoff.add_argument("--approved-by", help="narrative approver")
    p_signoff.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    p_signoff.add_argument("--fingerprint-dir",
                           default=str(DEFAULT_FINGERPRINT_DIR))
    p_signoff.add_argument("--json", action="store_true", help="JSON output")
    p_signoff.set_defaults(func=cmd_signoff)

    p_explain = sub.add_parser(
        "explain", help="AI-assisted variance explanation (spec §8.2; "
                        "stub provider, fully local)")
    p_explain.add_argument("finding_id")
    p_explain.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    p_explain.add_argument("--fingerprint-dir", default=str(DEFAULT_FINGERPRINT_DIR))
    p_explain.add_argument("--json", action="store_true", help="JSON output")
    p_explain.set_defaults(func=cmd_explain)

    p_author = sub.add_parser(
        "author-mode", help="Draft a new failure mode + rule (spec §14.4); "
                            "interactive when flags are omitted"
    )
    p_author.add_argument("--pair", required=True)
    p_author.add_argument("--name")
    p_author.add_argument("--category")
    p_author.add_argument("--description")
    p_author.add_argument("--domains", help="comma-separated data domains")
    p_author.add_argument("--impact")
    p_author.add_argument("--probability", type=float, default=0.30,
                          help="initial probability (default 0.30)")
    p_author.add_argument("--remediation")
    p_author.add_argument("--rule-json",
                          help="rule JSON, inline or a file path")
    p_author.add_argument("--fingerprint-dir", default=str(DEFAULT_FINGERPRINT_DIR))
    p_author.add_argument("--json", action="store_true", help="JSON output")
    p_author.set_defaults(func=cmd_author_mode)

    return parser


def _utf8_streams() -> None:
    # Windows consoles may default to a legacy codepage; the CLI_SPEC output
    # format includes non-ASCII (em dash), so pin UTF-8 where supported.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    _utf8_streams()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # uniform runtime-error exit (CLI_SPEC)
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_RUNTIME


if __name__ == "__main__":
    sys.exit(main())
