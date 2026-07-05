# CLAUDE.md — MAPTIVA Migration Fingerprint™

## What this is
A plan-conversion validation application implementing the Migration Fingerprint™
concept: every platform pair has a repeatable failure signature. The app loads that
signature (the Fingerprint), runs a prioritized -- targeted, not generic --
validation of converted plan data, and writes every review back into the
Fingerprint (the Learning Loop).

Authoritative spec: "MAPTIVA Migration Fingerprint Solution Specification v1.0".
Requirement IDs (REQ-xxx) and milestones (MS-x.y) referenced below are defined there.

## Session protocol
1. Pick the next open milestone from Chapter 23 (Phase 1 -> 2 -> 3, in order).
2. Load the spec chapters listed for that milestone before writing code.
3. Implement; run `pytest`; a milestone is done only when its "Done when" holds.
4. Small commits per milestone item.

## Domain vocabulary
Platform Pair - directional source/target combo (e.g., OMNI_MAINFRAME_ZOS -> OMNI_LINUX_RHEL).
Fingerprint - versioned JSON library of Failure Modes for one pair (spec Ch. 5).
Failure Mode - named pattern with probability, impact, data domains, detection rules,
remediation, history counters. Seed library: FM-001..FM-018 (spec Ch. 6).
Detection Rule - executable validation bound to a failure mode; types:
field_compare, count_balance, referential, derived_recompute, encoding_check,
sort_order_check (spec Ch. 11).
Conversion Run - one execution: prioritized suite over source+target datasets ->
findings report (spec Ch. 12-13).
Learning Loop - confirmed/false-positive reviews update history and probability
via the Beta-nudge formula, k=10, clamp [0.05, 0.99] (spec Ch. 14.2).

## Hard rules
- Money = Decimal, never float. Default tolerance 0.00. (REQ-004, REQ-017)
- Deterministic runs: same inputs + fingerprint version = same report. No clock,
  randomness, or dict-order dependence in rules/reports. (REQ-009)
- Failure-mode logic lives in fingerprint JSON, not Python. (REQ-012)
- Every rule type: unit tests + docstring + a fixture that trips it. (REQ-023)
- Synthetic data only. Fake SSNs (900-xx), fake names, 50-200 participant plans. (REQ-031)
- Suite order = probability x impact desc; ties by severity, then FM id. (REQ-001)

## Repo layout
See spec Ch. 23.1. src/{fingerprint,ingest,rules,runner,learning,report,ai,api},
data/{fingerprints,samples,runs}, tests/fixtures.

## Stack
Python 3.11+, pydantic, pandas, pytest. Phase 3: FastAPI; React+Vite+Tailwind UI.
Product deploys on the AI-Mapper AWS stack (Lambda, SQS, S3, RDS Postgres, Cognito,
Bedrock behind src/ai). Nothing outside src/ai imports a model SDK. (REQ-018)

## Definition of done (demo script)
1) Load z/OS->Linux fingerprint; show prioritized suite.
2) Clean pair -> green scoreboard. 3) Seeded pair -> findings in priority order
with record drill-down. 4) Confirm two findings + one false positive -> probability
and history update, new patch version. 5) Switch to Omni->TRAC -> different suite.

## Local-only constraint (POC phases 1-2)
This POC is fully local until Phase 3 and never creates, modifies, or deploys AWS
resources during Phases 1-2. It is completely separate from the AI-Mapper
application: no shared code, buckets, queues, or stacks, ever.
