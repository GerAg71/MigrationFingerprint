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
