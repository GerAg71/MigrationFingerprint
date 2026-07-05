# CLAUDE.md — Migration Fingerprint™ POC

## What We Are Building

A proof-of-concept **plan conversion application** that demonstrates Convergent's Migration Fingerprint™ concept: every platform pair (e.g., Omni → TRAC, z/OS Omni → Linux Omni) has a repeatable "failure signature." This POC loads that signature, uses it to drive a targeted (not generic) validation of converted plan data, and feeds every defect found back into the fingerprint so it gets smarter with each conversion.

**Elevator pitch:** Before a single test scenario runs, the app loads the Fingerprint for the selected platform pair and pre-populates the validation suite with the failure modes most likely to affect this migration — prioritized by probability and impact.

## Core Concepts (Domain Vocabulary)

- **Platform Pair** — a source/target combination (e.g., `OMNI_MAINFRAME → OMNI_LINUX`, `OMNI → TRAC`). Every Fingerprint is keyed to exactly one pair.
- **Fingerprint** — a versioned, codified library of failure patterns for a platform pair, built from conversion post-mortems, QA defect logs, and platform-specific gotchas.
- **Failure Mode** — one named pattern (e.g., "Loan outstanding-balance carry-over mismatch"), with: category, description, detection rule(s), probability score, impact score, affected data domains, and remediation guidance.
- **Detection Rule** — executable validation logic bound to a failure mode (field compare, tolerance check, referential check, derived-value recomputation).
- **Conversion Run** — one execution: ingest source extract + target extract for a plan (or set of plans), run the prioritized test suite, produce a findings report.
- **Learning Loop** — confirmed defects (and false positives) from a run are written back to the Fingerprint, adjusting probability scores and adding new failure modes.

## Seed Failure Modes (Ship These in the POC)

Pre-load the POC Fingerprint with these pattern categories (from real recordkeeping-migration experience):

1. **Loan outstanding-balance carry-over** — balances don't always carry the way you expect; recompute expected balance from payment history and compare.
2. **Participant-level vesting schedule mapping** — service rules and vesting logic rarely line up perfectly; compare vested % per participant per source vs. target.
3. **Custom calculated-field dependencies** — source-side scripted/derived fields (e.g., OmniScript logic) with no direct equivalent in the target; flag fields whose target value cannot be traced to a mapping rule.
4. **Plan-provision mismatches** — safe harbor configuration and catch-up eligibility rules; compare provision-level configuration matrices.
5. **Sort order / encoding sensitivity (EBCDIC vs. ASCII)** — detect ordering-dependent outputs and character-encoding drift.
6. **Packed/binary field handling** — COMP-3 / binary numeric fields decoded incorrectly (sign nibbles, implied decimals).
7. **Balance carry-over / count-balance totals** — plan-, fund-, and participant-level totals must match to the decimal; drill down behind any variance.
8. **Date and format drift** — century windows, Julian vs. Gregorian, zero/blank date semantics.

Each seed failure mode needs at least one working detection rule and one sample dataset that trips it (see Test Data below).

## Architecture

Keep it simple — this is a POC, not production. Monolith with clean module boundaries:

```
fingerprint-poc/
├── CLAUDE.md
├── README.md
├── data/
│   ├── fingerprints/            # JSON/YAML fingerprint definitions per platform pair
│   ├── samples/
│   │   ├── source/              # sample source-side plan extracts (CSV/fixed-width)
│   │   └── target/              # sample target-side plan extracts
│   └── runs/                    # output: findings reports per run
├── src/
│   ├── fingerprint/             # load, version, and query fingerprints
│   ├── ingest/                  # parsers: CSV, fixed-width w/ copybook-style layouts, EBCDIC decode
│   ├── rules/                   # detection rule engine + built-in rule types
│   ├── runner/                  # conversion run orchestration; prioritization by probability x impact
│   ├── learning/                # write-back: confirmed defects update the fingerprint
│   ├── report/                  # findings report (JSON + HTML) with severity ranking
│   └── api/                     # thin REST API (optional for POC UI)
├── ui/                          # simple web dashboard (optional, phase 3)
└── tests/
```

### Recommended Stack

- **Language:** Python 3.11+ (fast to build, strong data tooling). Use `pydantic` for schemas, `pandas` for comparisons, `pytest` for tests.
- **Fingerprint storage:** JSON files under `data/fingerprints/` (versioned via a `version` field and git). No database for the POC.
- **API (optional):** FastAPI.
- **UI (optional, last):** single-page dashboard (plain HTML + a small JS framework or FastAPI + Jinja templates). Shows: loaded fingerprint, prioritized test suite, run results, learning-loop history.

## Data Model (Schemas)

### Fingerprint (JSON)

```json
{
  "fingerprint_id": "omni-zos-to-omni-linux",
  "platform_pair": { "source": "OMNI_MAINFRAME_ZOS", "target": "OMNI_LINUX_RHEL" },
  "version": "1.0.0",
  "updated_at": "2026-07-05",
  "failure_modes": [
    {
      "id": "FM-001",
      "name": "Loan outstanding-balance carry-over",
      "category": "LOANS",
      "description": "Converted loan balances diverge from source due to accrual/payment-application differences.",
      "probability": 0.7,
      "impact": 0.9,
      "data_domains": ["LOAN"],
      "detection_rules": ["RULE-LOAN-BAL-001"],
      "remediation": "Recompute amortization from origination; verify payment application order and accrual basis.",
      "history": { "times_detected": 0, "times_confirmed": 0, "false_positives": 0 }
    }
  ]
}
```

### Detection Rule

```json
{
  "rule_id": "RULE-LOAN-BAL-001",
  "type": "field_compare",
  "source_dataset": "loans",
  "target_dataset": "loans",
  "join_keys": ["plan_id", "participant_id", "loan_id"],
  "compare": [{ "field": "outstanding_balance", "tolerance": 0.00 }],
  "severity": "HIGH"
}
```

Rule `type` values to implement in the POC engine:
- `field_compare` — join source/target on keys, compare fields with optional tolerance
- `count_balance` — aggregate totals (sum/count) per grouping level, exact match
- `referential` — every target row traces to a source row (and vice versa; report orphans)
- `derived_recompute` — recompute a value from inputs (e.g., vested %) and compare to target
- `encoding_check` — detect non-ASCII artifacts / mojibake in target text fields
- `sort_order_check` — verify ordering-sensitive outputs against expected collation

### Findings Report

Per run: run metadata, fingerprint version used, prioritized suite executed, then findings — each with failure mode, rule, severity, affected records (keys + values), and suggested remediation. Output both `findings.json` and a readable `findings.html`.

## Execution Flow (What the Runner Does)

1. **Select platform pair** → load matching Fingerprint.
2. **Build the prioritized suite** → order detection rules by `probability × impact` (highest first). Show this ordering in the report — it's the differentiator.
3. **Ingest** source and target extracts (support CSV first; fixed-width + copybook layout second; EBCDIC decode third).
4. **Execute rules** in priority order; collect findings with record-level drill-down.
5. **Report** — JSON + HTML, with a summary scoreboard (rules run, pass/fail, records affected, severity mix).
6. **Learning loop** — a reviewer marks each finding `confirmed` or `false_positive` (CLI command or API endpoint). Write-back updates `history` counts and adjusts `probability` (simple Bayesian-style nudge is fine for POC; document the formula). New failure modes can be added via a guided CLI prompt.

## Test Data

Generate synthetic sample data — **never real participant data**. Fake SSNs (use 900-xx ranges or obviously fake values), fake names, small plans (50–200 participants). Build:

- One "clean" plan pair (source/target match) → proves no false noise.
- One "seeded defects" plan pair with at least one deliberate defect per seed failure mode → proves each detection rule fires and lands in the report at the right priority.

Include a `data/samples/README.md` explaining which defects were seeded where.

## Build Order (Milestones)

**Phase 1 — Core engine (build this first, CLI only):**
1. Pydantic schemas for Fingerprint, FailureMode, DetectionRule, Finding.
2. Fingerprint loader + prioritization.
3. CSV ingest.
4. Rule engine: `field_compare`, `count_balance`, `referential`.
5. Runner + JSON findings report.
6. Synthetic sample data (clean pair + seeded pair).
7. `pytest` coverage on every rule type.

**Phase 2 — Domain depth:**
8. `derived_recompute` (vesting %), `encoding_check`, `sort_order_check` rules.
9. Fixed-width ingest with copybook-style layout files; EBCDIC → ASCII decode incl. packed (COMP-3) fields.
10. HTML findings report.
11. Learning loop: confirm/false-positive CLI, probability write-back, fingerprint versioning.

**Phase 3 — Demo polish (optional):**
12. FastAPI endpoints: load fingerprint, start run, get report, submit review.
13. Dashboard UI: fingerprint view → prioritized suite view → run results → learning history.
14. A second fingerprint (e.g., `OMNI → TRAC`) to demonstrate the platform-pair concept.

## Conventions

- Type hints everywhere; pydantic models are the single source of truth for schemas.
- Every detection rule type has: unit tests, a docstring explaining the failure mode it serves, and a sample dataset that trips it.
- Money fields: `Decimal`, never float. Match to the decimal — tolerance defaults to 0.00 unless a rule says otherwise.
- Deterministic runs: same inputs + same fingerprint version = same report. Log fingerprint version in every report.
- Keep fingerprint content data-driven — no failure-mode logic hardcoded in Python that belongs in the JSON.
- Small commits per milestone item; run `pytest` before considering an item done.

## Out of Scope (POC)

- Real Omni/TRAC connectivity, FIS-licensed source, or client data of any kind.
- Authentication/authorization, multi-tenancy, production hardening.
- Full MAPTIVA file-intake features (row-level payroll validation) — mention as a future integration point only.
- Performance at scale (150K files/day is production; POC handles sample-sized files).

## Definition of Done (POC Demo Script)

The demo must show, end to end:
1. Load the z/OS→Linux fingerprint; display the prioritized test suite ("targeted, not generic").
2. Run against the clean plan pair → green scoreboard.
3. Run against the seeded pair → findings surface in priority order with record-level drill-down.
4. Confirm two findings, mark one false positive → show the fingerprint's probabilities and history update (the learning loop).
5. Switch platform pair to Omni→TRAC → show a different fingerprint loads a different suite.
