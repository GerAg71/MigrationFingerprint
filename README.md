# MAPTIVA Migration Fingerprint™ — POC

Plan-conversion validation driven by a **Migration Fingerprint**: a versioned,
codified library of the failure modes a specific platform pair (e.g. Omni z/OS →
Omni Linux) is known to produce, each bound to executable detection rules and
scored by probability × impact. Runs execute a *targeted, not generic* suite and
every analyst review is written back into the fingerprint (the Learning Loop).

Authoritative spec: `MAPTIVA_Fingerprint_Solution_Specification_v1.0.docx`
(REQ-xxx / MS-x.y IDs referenced throughout). CLI surface: `CLI_SPEC.md`.
Session rules for Claude Code: `CLAUDE.md`.

## Status

| Milestone | Item | Status |
|-----------|------|--------|
| MS-1.1 | Pydantic schemas (Fingerprint, FailureMode, DetectionRule, ConversionRun, Finding, LayoutSpec) + JSON Schema export | ✅ done |
| MS-1.2 | Fingerprint loader + prioritization; CLI `validate` / `suite` | ✅ done |
| MS-1.3 | CSV ingestion + dataset registration (Decimal boundary, reject quarantine, REQ-021 gate index) | ✅ done |
| MS-1.4 | Rule engine: `field_compare`, `count_balance`, `referential` executors + uniform finding construction | ✅ done |
| MS-1.5 … MS-3.3 | see spec Ch. 23 | open |

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```
uv sync
uv run pytest
```

CLI (CLI_SPEC.md; exit codes 0 ok / 1 runtime / 3 validation refusal):

```
uv run fingerprint validate data/fingerprints/omni-zos-to-omni-linux/1.0.0/fingerprint.json
uv run fingerprint suite --pair omni-zos-to-omni-linux [--version 1.0.0] [--json]
```

## Layout

```
data/fingerprints/<pair_id>/<version>/fingerprint.json   # versioned fingerprints
data/samples/                                            # synthetic extracts (MS-1.6)
data/runs/                                               # findings reports per run
src/fingerprint/models.py                                # all pydantic schemas (MS-1.1)
tests/                                                   # pytest suite + fixtures
```

The POC is fully local (no AWS) through Phases 1–2 and is entirely separate from
the AI-Mapper application.
