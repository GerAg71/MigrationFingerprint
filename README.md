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
| MS-2.4 | Learning loop: review write-back (§14.2), draft/publish versioning, `diff`/`history`/`author-mode` | ✅ done |
| **Phase 2 complete** | | |
| MS-3.1 | FastAPI endpoints (Ch. 18 subset) + OpenAPI companion (`docs/openapi.json`) | ✅ done |
| MS-3.2 | Dashboard UI at `/ui`: library → fingerprint → suite → run wizard → findings/review → history/publish | ✅ done |
| MS-3.3 | Second fingerprint (Omni→TRAC placeholder) + `pairs` CLI — demo step 5 | ✅ done |
| **POC complete — all phases done, five-step demo verified** | | |
| Phase 4.1 | Exception workflow (Ch. 15): assign/comment/resolve/close, audit trail, exception register | ✅ done |
| Phase 4.2 | AI Orchestration Layer (Ch. 8/27) with local stub provider; `explain` CLI/API/UI | ✅ done |
| Phase 4.3 | Sign-off package (§13.4): certification + metrics vs §2.6 targets + closure evidence, zip + manifest | ✅ done |
| Phase 4.4 | Omni→Omni restore use case: `compile-matrix` (Format Matrix → card layouts + COBOL decks), `format_conformance` rule type, UDF datasets, restore fingerprint + sample pairs | ✅ done |
| Phase 4.5 | Technical runbook at `/runbook` (📖 in the dashboard): searchable plain-English reference for every mode/rule/score, generated from the live store by `tools/build_runbook.py` | ✅ done |

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
uv run fingerprint compile-matrix docs/Omni_Format_Matrix_Complete.xlsx \
    --out data/layouts/omni-restore --decks   # Omni->Omni restore toolchain
uv run fingerprint run --pair omni-zos-to-omni-linux-restore \
    --source-dir data/samples/source/PLN-REST-SEED-01 \
    --target-dir data/samples/target/PLN-REST-SEED-01
uv run fingerprint run --pair omni-zos-to-omni-linux \
    --source-dir data/samples/source/PLN-SEED-01 \
    --target-dir data/samples/target/PLN-SEED-01 \
    [--plans P1,P2] [--wave W1] [--fail-on-findings[=SEV]]
uv run fingerprint findings <run_id> [--severity SEV] [--status STATUS]
uv run fingerprint show <finding_id>
uv run fingerprint report <run_id> [--format json|html] [--recon plan|participant|loan|contribution|quality|all]
uv run fingerprint review <finding_id> --decision confirmed|false_positive [--comment ...] [--reviewer ...]
uv run fingerprint history --pair <pair_id> [--fm FM-001]
uv run fingerprint publish --pair <pair_id> --bump patch|minor|major [--changelog ...]
uv run fingerprint diff --pair <pair_id> --from 1.0.0 --to 1.0.1
uv run fingerprint author-mode --pair <pair_id> [flags or interactive]
```

Reviews apply the §14.2 Beta write-back (k=10, clamp [0.05, 0.99]) to a
draft under `data/fingerprints/<pair>/draft/`; `publish` finalizes it as a
new immutable version. Learning events append to
`data/fingerprints/<pair>/learning_events.jsonl` and are replayable
(REQ-027).

## REST API + dashboard (MS-3.1 / MS-3.2)

```
uv run uvicorn src.api.app:app --reload
```

Open <code>http://127.0.0.1:8000/</code> for the dashboard (redirects to
`/ui`): Fingerprint Library → fingerprint detail → prioritized suite (with
the generic-ordering comparison toggle) → new-run wizard with sample-pair
quick picks → run scoreboard and findings → finding drill-down with
confirm/false-positive review → learning history with probability sparklines
and publish. The POC page is a no-build, self-contained single page served
by the API (the original POC brief's Phase-3 allowance); the product moves
to the React + Vite + Tailwind design system (spec §20.4).

Spec Ch. 18 subset over the identical engine: platform pairs, fingerprints
(current/versions/suite/learning-history/publish), runs (create — executes
synchronously in the POC — status, suite, findings), finding detail +
review, and report artifacts (findings JSON/HTML + the reconciliation
suite). Error envelope per §18.5 with per-request ids. No auth in the POC
(product adds Cognito role scopes). OpenAPI at `/openapi.json`; committed
companion at [docs/openapi.json](docs/openapi.json) (regenerate with
`uv run python -m src.api`).

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

The POC is fully local (no AWS) and entirely separate from the AI-Mapper
application.

## The five-step demo (spec §23.5 — Definition of Done)

```
# 1. targeted, not generic: the prioritized suite
uv run fingerprint suite --pair omni-zos-to-omni-linux

# 2. clean pair -> green scoreboard
uv run fingerprint run --pair omni-zos-to-omni-linux \
    --source-dir data/samples/source/PLN-CLEAN-01 --target-dir data/samples/target/PLN-CLEAN-01

# 3. seeded pair -> findings in priority order, record-level drill-down
uv run fingerprint run --pair omni-zos-to-omni-linux \
    --source-dir data/samples/source/PLN-SEED-01 --target-dir data/samples/target/PLN-SEED-01
uv run fingerprint findings <run_id>
uv run fingerprint show <finding_id>

# 4. the learning loop: reviews update probabilities; publish a new version
uv run fingerprint review <finding_id> --decision confirmed      # x2
uv run fingerprint review <finding_id> --decision false_positive
uv run fingerprint history --pair omni-zos-to-omni-linux
uv run fingerprint publish --pair omni-zos-to-omni-linux --bump patch

# 5. different pair -> different suite
uv run fingerprint suite --pair omni-to-trac
```

Step 4 mutates `data/fingerprints/` (a draft, the learning-event log, and
the published version) — demo against a copy if the store should stay
pristine. The same flow is clickable in the dashboard (`/ui`).
