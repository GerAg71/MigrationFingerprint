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
| MS-1.5 | Runner: suite snapshot, REQ-021 gate, deterministic `findings.json`; CLI `run` / `findings` / `show` | ✅ done |
| MS-1.6 | Synthetic sample data: clean pair (zero noise) + seeded pair with exact REQ-032 manifest | ✅ done |
| MS-1.7 | Coverage audit: golden fixtures per rule type, REQ-015 perf smoke, CI workflow (95% line coverage) | ✅ done |
| **Phase 1 complete** | | |
| MS-2.1 | `derived_recompute` (vested %, loan amortization), `encoding_check`, `sort_order_check` | ✅ done |
| MS-2.2 | Fixed-width/copybook ingest; EBCDIC + COMP-3 decode; FM-006 active; EBCDIC sample pairs | ✅ done |
| MS-2.3 | Self-contained `findings.html` + five reconciliation reports; CLI `report` | ✅ done |
| MS-2.4 … MS-3.3 | see spec Ch. 23 | open |

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
uv run fingerprint run --pair omni-zos-to-omni-linux \
    --source-dir data/samples/source/PLN-SEED-01 \
    --target-dir data/samples/target/PLN-SEED-01 \
    [--plans P1,P2] [--wave W1] [--fail-on-findings[=SEV]]
uv run fingerprint findings <run_id> [--severity SEV] [--status STATUS]
uv run fingerprint show <finding_id>
uv run fingerprint report <run_id> [--format json|html] [--recon plan|participant|loan|contribution|quality|all]
```

A run writes `data/runs/<run_id>/`: `suite_snapshot.json` (persisted before
execution, REQ-001), deterministic `findings.json` (REQ-009), per-finding
drill-down CSVs under `findings/`, quarantined rows under `ingest/`, and
`run.json` (the only place timestamps live).

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
