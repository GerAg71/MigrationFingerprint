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

from pydantic import ValidationError

from src.fingerprint.loader import (
    DEFAULT_FINGERPRINT_DIR,
    FingerprintDirectoryError,
    load,
    load_file,
)
from src.fingerprint.prioritize import prioritized_suite

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
