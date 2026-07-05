# MAPTIVA™ Migration Fingerprint™ Solution Specification
## Master Document Outline — Draft v0.1

**Document type:** Single master specification, built part by part
**Target length:** ~180–240 pages
**Audiences:** Product/architects (Parts I–III), developers & Claude Code (Parts IV–IX), QA/compliance (Parts IV, VIII, Appendices)
**Formatting conventions:** Word (.docx) with hyperlinked TOC, bookmarked glossary (first use of every glossary term hyperlinks to its entry), numbered headings to 3 levels, one traceability ID per requirement (`REQ-xxx`), one milestone ID per build item (`MS-x.x`).

---

## FRONT MATTER (~8 pages)

- **0.1 Title Page & Document Control** — version history table, approvers, distribution
- **0.2 Table of Contents** — auto-generated, hyperlinked to all headings
- **0.3 How to Use This Document**
  - 0.3.1 Reading path for Product Managers & Architects (Parts I–III)
  - 0.3.2 Reading path for Developers (Parts IV–VII, IX)
  - 0.3.3 Reading path for Claude Code sessions (Part IX first, then referenced specs)
  - 0.3.4 Notation: requirement IDs, milestone IDs, glossary hyperlinks, sample-payload blocks
- **0.4 Executive Summary** — one page: what MAPTIVA Fingerprint is, why targeted validation beats generic validation, what this document enables

---

## PART I — BUSINESS ARCHITECTURE & THE FINGERPRINT CONCEPT (~22 pages)

### Chapter 1. Vision & Value Proposition
- 1.1 The problem: recordkeeping platform conversions fail in *repeatable* ways
- 1.2 The Migration Fingerprint™ concept — codified failure signatures per platform pair
- 1.3 "Targeted, not generic": pre-populating the validation suite by probability × impact
- 1.4 The Learning Loop: every conversion makes the next one smarter
- 1.5 Product positioning: POC → product → AI Operating System for Retirement Administration
- 1.6 Relationship to MAPTIVA / AI-Mapper (shared stack, shared role model, future integration point for row-level payroll validation)

### Chapter 2. Conversion Methodology (Business Context)
*Source: Congruent Client Data Conversion Methodology; Congruent Plan Conversion Pricing*
- 2.1 Guiding principles: accuracy, security, auditability, transparency, efficiency
- 2.2 The seven-phase conversion lifecycle (Discovery → Extraction → Transformation & Mapping → Loading → Validation & Reconciliation → Testing & Parallel Runs → Final Cutover)
- 2.3 Where the Fingerprint engine plugs into each phase
- 2.4 Batch/wave conversion approach (50–100 plans per wave) and how runs map to waves
- 2.5 Standard deliverables the application must produce (mapping workbook, runbook, validation & exception reports, reconciliation reports, sign-off package, audit logs)
- 2.6 Success metrics (100% records converted, 100% balances reconciled, <0.1% unresolved exceptions, on-window cutover) → traced to REQ IDs

### Chapter 3. Personas, Roles & Use Cases
*Source: AI-Mapper CLAUDE.md role model*
- 3.1 Role model: site_admin, record_keeper_admin, record_keeper_user, plan_sponsor_admin, plan_sponsor_user + new role: **conversion_analyst** (reviews findings, drives learning loop)
- 3.2 Role/feature access matrix (extends the AI-Mapper matrix with Fingerprint features)
- 3.3 Primary use cases (each with actor, preconditions, flow, postconditions):
  - UC-01 Load fingerprint for a platform pair & view prioritized suite
  - UC-02 Execute a conversion run (single plan / batch)
  - UC-03 Review findings with record-level drill-down
  - UC-04 Confirm / reject findings (learning loop)
  - UC-05 Author a new failure mode & detection rule
  - UC-06 Generate reconciliation & sign-off package
  - UC-07 Manage platform pairs and fingerprint versions
  - UC-08 Automated (scheduled) runs on extract arrival
- 3.4 Anchor case study: Omni → CORE conversion (400–500 plans, 15K+ participants, 18–24 week timeline)

---

## PART II — DOMAIN & DATA MODEL (~35 pages)

### Chapter 4. Canonical Retirement Data Model (Validation-Scoped)
- 4.1 Scope statement: entities modeled only to the depth the Fingerprint validates
- 4.2 Entity catalog with ER diagram:
  - Plan (indicative data, provisions, investment menu, money sources)
  - Participant (demographics, status, employment/service history)
  - Account / Balance (by money type × investment)
  - Contribution
  - Loan (balance, schedule, repayment history)
  - Vesting (schedule, service rules, vested %)
  - Transaction history / Price history
- 4.3 Key attribute dictionary per entity (name, type, nullability, canonical format)
- 4.4 Money-type and investment-code normalization model
- 4.5 Status taxonomies (Active, Terminated, Retired, Beneficiary)

### Chapter 5. The Fingerprint Data Model
*Source: CLAUDE_1.md schemas — expanded to full specification*
- 5.1 Platform Pair — registry, identifiers, versioned pairing
- 5.2 Fingerprint — versioning rules, storage format (JSON), lifecycle states
- 5.3 Failure Mode — full schema: category, description, probability, impact, data domains, detection rules, remediation, history counters
- 5.4 Detection Rule — full schema per rule type; join keys, tolerances, severity
- 5.5 Conversion Run — run metadata, inputs, suite snapshot, status flow
- 5.6 Finding — failure mode + rule + severity + affected records + remediation
- 5.7 Learning Loop entities — review decisions, probability adjustment log, fingerprint version diffs
- 5.8 Complete JSON Schemas / pydantic model listings for every entity
- 5.9 Sample payloads (one full example each)

### Chapter 6. Seed Failure-Mode Library
*Source: CLAUDE_1.md seed list + Congruent validation-report catalog*
- 6.1 Library structure and how modes are cataloged (`FM-xxx` IDs)
- 6.2 Seed modes from conversion experience (each with description, detection rule(s), sample defect, remediation):
  - FM-001 Loan outstanding-balance carry-over
  - FM-002 Participant-level vesting schedule mapping
  - FM-003 Custom calculated-field dependencies (scripted/derived fields)
  - FM-004 Plan-provision mismatches (safe harbor, catch-up eligibility)
  - FM-005 Sort order / encoding sensitivity (EBCDIC vs. ASCII)
  - FM-006 Packed/binary field handling (COMP-3, sign nibbles, implied decimals)
  - FM-007 Balance / count-balance totals (plan, fund, participant level)
  - FM-008 Date & format drift (century windows, Julian dates, zero/blank semantics)
- 6.3 Seed modes derived from the Congruent validation catalog:
  - FM-009 Participant count mismatch by status
  - FM-010 Missing key fields (SSN, DOB, plan ID)
  - FM-011 Duplicate participant IDs / SSNs
  - FM-012 Balance mismatch by money type
  - FM-013 Balance mismatch by investment option
  - FM-014 Loan count / missing repayment terms or maturity dates
  - FM-015 Contribution & distribution totals (last payroll cycle)
  - FM-016 Field-length violations & invalid characters
  - FM-017 Invalid/future dates
  - FM-018 Unexpected negative balances
- 6.4 Failure mode ↔ detection rule ↔ conversion-phase traceability table

---

## PART III — SYSTEM ARCHITECTURE (~25 pages)

### Chapter 7. Solution Architecture
*Source: AI-Mapper tech stack*
- 7.1 Architecture principles: POC-simple monolith with clean module boundaries → serverless product
- 7.2 Target AWS architecture diagram:
  - React (Vite + Tailwind) SPA on S3 + CloudFront
  - API Gateway (REST + WebSocket) → Python Lambdas
  - SQS-based async job processing (run orchestration = long-running jobs)
  - RDS PostgreSQL (SQLModel ORM, Alembic migrations)
  - S3: fingerprints, extracts, run outputs, reports
  - Cognito authentication with role scopes
- 7.3 Module map (mirrors repo layout): `fingerprint/`, `ingest/`, `rules/`, `runner/`, `learning/`, `report/`, `api/`
- 7.4 POC-to-product evolution path (local CLI monolith → Lambda deployment); what stays identical (schemas, rule engine) and what changes (storage, orchestration)
- 7.5 Non-functional requirements: determinism (same inputs + fingerprint version = same report), auditability, performance envelope, data-volume assumptions

### Chapter 8. AI Orchestration Layer
*Source: MaptivaFingerprintSolutionDoc architecture recommendation*
- 8.1 Design rule: MAPTIVA owns the retirement intelligence; the AI model is swappable
- 8.2 Common AI interface (function catalog):
  - `SuggestFieldMappings()` — propose source→target mappings
  - `ExplainReconciliationVariance()` — natural-language finding explanations
  - `SuggestFailureMode()` — draft new failure modes from confirmed defect clusters
  - `GenerateConversionSummary()` — executive run summaries
  - `ClassifyFinding()` — assist triage of findings
- 8.3 Bedrock integration (Claude via Bedrock, temperature 0.1, deterministic), fallback behavior, model registry
- 8.4 Prompt template management, confidence scoring, human-review gates
- 8.5 What is deliberately *not* AI: rule execution, reconciliation math, probability write-back (deterministic code only)

### Chapter 9. Data & File Flow
- 9.1 End-to-end pipeline: Extract arrival → Ingest → Run → Findings → Review → Learning write-back → Report/sign-off
- 9.2 S3 layout & naming conventions (fingerprints/, samples/, runs/, reports/)
- 9.3 Job/run status state machine (created → ingesting → running → review → completed / failed)
- 9.4 WebSocket status events; SQS message contracts
- 9.5 Security of data in motion & at rest (SFTP/PGP intake assumption, KMS, encryption in transit)

---

## PART IV — FUNCTIONAL SPECIFICATIONS (~45 pages)

### Chapter 10. Ingestion Engine
- 10.1 Supported formats & phased delivery: CSV (Phase 1) → fixed-width with copybook-style layouts (Phase 2) → EBCDIC decode incl. COMP-3 packed fields (Phase 2)
- 10.2 Layout definition format (copybook-style spec, field offsets, types, implied decimals)
- 10.3 Header detection & headerless-file column resolution (pattern reuse from AI-Mapper)
- 10.4 Dataset registration: how ingested files bind to rule `source_dataset`/`target_dataset`
- 10.5 Error handling: malformed rows, encoding faults, partial loads
- 10.6 Acceptance criteria + REQ IDs

### Chapter 11. Detection Rule Engine
- 11.1 Engine architecture: data-driven rules (JSON), no failure-mode logic hardcoded
- 11.2 Rule type specifications (each with schema, algorithm, worked example, edge cases, unit-test spec):
  - 11.2.1 `field_compare` — keyed join, field comparison with tolerance (money = Decimal, default tolerance 0.00)
  - 11.2.2 `count_balance` — aggregate sum/count per grouping level, exact match
  - 11.2.3 `referential` — bidirectional orphan detection
  - 11.2.4 `derived_recompute` — recompute derived values (vested %, loan amortization) and compare
  - 11.2.5 `encoding_check` — mojibake / non-ASCII artifact detection
  - 11.2.6 `sort_order_check` — collation-sensitive output verification
- 11.3 Severity model and finding construction
- 11.4 Extensibility: adding a new rule type (contract, registration, tests)

### Chapter 12. Run Orchestration & Prioritization
- 12.1 Run lifecycle: select platform pair → load fingerprint → build prioritized suite → ingest → execute → report
- 12.2 Prioritization algorithm: probability × impact ordering; tie-breaking; suite snapshot stored per run
- 12.3 Batch runs (multiple plans / conversion waves)
- 12.4 Determinism & reproducibility requirements; fingerprint version pinning per run
- 12.5 Scheduled/automated runs on extract arrival (auto-job pattern reuse from AI-Mapper)

### Chapter 13. Validation, Reconciliation & Reporting
*Source: Congruent validation report catalog → productized*
- 13.1 Findings report: JSON schema + HTML report spec (summary scoreboard: rules run, pass/fail, records affected, severity mix; drill-down to record level)
- 13.2 Reconciliation report suite (client-facing deliverables):
  - Plan reconciliation (plan counts, totals by money type & investment)
  - Participant-level reconciliation (counts by status, balances by money type & investment)
  - Loan reconciliation (counts, outstanding balance totals)
  - Contribution/distribution totals
  - Data-quality report (lengths, characters, dates, negatives)
- 13.3 Exception report & resolution register
- 13.4 Sign-off package assembly (certification of data accuracy)
- 13.5 Report rendering: HTML templates, PDF export (future), branding

### Chapter 14. Learning Loop
- 14.1 Review workflow: analyst marks each finding `confirmed` / `false_positive`
- 14.2 Probability write-back formula (documented Bayesian-style nudge; worked numeric examples)
- 14.3 History counters (`times_detected`, `times_confirmed`, `false_positives`)
- 14.4 New failure-mode authoring: guided flow (CLI in POC, UI in product), AI-assisted drafting via `SuggestFailureMode()`
- 14.5 Fingerprint versioning: semver rules, immutability of past run references, version diff view
- 14.6 Governance: who may confirm findings and publish fingerprint versions

### Chapter 15. Exception & Workflow Management
- 15.1 Finding triage states (new → in review → confirmed/false-positive → remediated → closed)
- 15.2 Assignments, comments, and audit trail per finding
- 15.3 Sign-off checkpoints mapped to conversion phases (dual sign-off: IT + business)

---

## PART V — PLATFORM ADAPTERS & INTEGRATIONS (~18 pages)

### Chapter 16. Platform Adapter Framework
- 16.1 Adapter contract: what an adapter must provide (extract layouts, code translation tables, known quirks feeding the fingerprint)
- 16.2 Adapter registry & configuration model
- 16.3 Adapter roadmap: Omni (first), TRAC, CORE, Relius, FT Williams (placeholders)

### Chapter 17. Omni → CORE Adapter (Reference Implementation)
*Source: Omni–CORE Integration doc*
- 17.1 Scope: census/demographic, eligibility & enrollment, contribution processing
- 17.2 Omni extract inventory: control files (CT.AUTO ENROLLMENT, CT.AUTO INCREASE, CT.LEAVE OF ABSENCE, CT.VESTING, VESTOVR, CT.CONTRIBUTION, CT.DISTRIBUTION, CT.RETIREMENT, CT.FEEDETAIL), loan & withdrawal text files, IC/FC/PF extracts
- 17.3 Extract strategy options (nightly files vs. Omnilink API vs. DB connect) with recommendation & rationale
- 17.4 Data build-up loads: census with rehire history, eligibility, enrollment, YTD contribution/hours/comp, loans with outstanding amounts & repayment data
- 17.5 Feedback-file flows (CORE → Omni and Omni → CORE change feedback)
- 17.6 Omni-specific fingerprint entries this adapter seeds (mainframe encoding, packed fields, control-file provision mapping)
- 17.7 Timing dependencies on Omni batch cycles; SSO considerations (noted, out of POC scope)

---

## PART VI — API & DATABASE DESIGN (~22 pages)

### Chapter 18. API Specification
- 18.1 REST resource model (FastAPI): platform-pairs, fingerprints, failure-modes, rules, runs, findings, reviews, reports
- 18.2 Endpoint catalog with request/response JSON examples (OpenAPI 3.1 excerpted; full spec as companion artifact)
- 18.3 WebSocket message catalog (run progress events)
- 18.4 AuthN/AuthZ: Cognito JWT, role-scope enforcement per endpoint
- 18.5 Error model & status codes

### Chapter 19. Database Design
- 19.1 PostgreSQL schema (SQLModel): all tables with columns, types, constraints, indexes
  - user, record_keeper, plan_sponsor (reused pattern)
  - platform_pair, fingerprint, fingerprint_version, failure_mode, detection_rule
  - conversion_run, run_suite_item, finding, finding_review, learning_event
  - dataset_registration, report_artifact, audit_log
- 19.2 ER diagram
- 19.3 JSON-in-Postgres vs. file-based fingerprint storage: POC (JSON files in git/S3) → product (DB) migration plan
- 19.4 Alembic migration strategy & seed-data scripts
- 19.5 Audit & retention model

---

## PART VII — USER INTERFACE (~18 pages)

### Chapter 20. UI/UX Specification
- 20.1 Information architecture & navigation (extends AI-Mapper sidebar/layout patterns)
- 20.2 Screens (each with wireframe description, components, states, user stories + acceptance criteria):
  - Fingerprint Library (platform pairs, versions)
  - Fingerprint Detail (failure modes, probabilities, history sparklines)
  - Prioritized Suite view ("targeted, not generic" — the demo differentiator)
  - New Run wizard (pair → fingerprint version → datasets → execute)
  - Run Results dashboard (scoreboard, severity mix, findings table)
  - Finding drill-down (affected records, remediation, review actions)
  - Learning History (probability changes over time, version diffs)
  - Reconciliation Reports & sign-off package download
  - Admin: platform pairs, users, roles
- 20.3 Role-based visibility matrix per screen
- 20.4 Component conventions (React + Tailwind, shared with AI-Mapper design system)

---

## PART VIII — SECURITY, COMPLIANCE & DEVOPS (~15 pages)

### Chapter 21. Security & Compliance
- 21.1 Data classification: synthetic-only in POC; PII handling requirements for product (masking, encryption, role-based access)
- 21.2 Encryption: KMS at rest, TLS in transit, PGP/SFTP intake
- 21.3 RBAC enforcement model (API + UI)
- 21.4 Audit logging: every extraction, run, review, write-back, and report generation
- 21.5 Regulatory context: ERISA-standard plan data assumption, SOC 2 trajectory
- 21.6 Data retention & decommissioning alignment with conversion cutover practices

### Chapter 22. Deployment & Operations
- 22.1 Environments: local (POC CLI) → staging → production
- 22.2 Serverless Framework deployment, Docker/ECR build conventions, credential/SSO setup
- 22.3 CI/CD (GitHub Actions), migration invocation, CloudFront invalidation
- 22.4 Monitoring & alerting (CloudWatch), run-failure diagnostics
- 22.5 Cost considerations & scaling posture (POC scale explicitly bounded)

---

## PART IX — IMPLEMENTATION GUIDE (CLAUDE CODE LAYER) (~20 pages)

### Chapter 23. Build Plan & Milestones
- 23.1 Repository structure (authoritative tree)
- 23.2 Phase 1 — Core engine (CLI only): schemas → fingerprint loader/prioritization → CSV ingest → field_compare/count_balance/referential → runner + JSON report → synthetic data → pytest coverage (MS-1.1 … MS-1.7)
- 23.3 Phase 2 — Domain depth: derived_recompute/encoding_check/sort_order_check → fixed-width/copybook + EBCDIC/COMP-3 → HTML report → learning loop + versioning (MS-2.1 … MS-2.4)
- 23.4 Phase 3 — Demo polish: FastAPI endpoints → dashboard UI → second fingerprint (Omni→TRAC) (MS-3.1 … MS-3.3)
- 23.5 Definition of Done: the five-step demo script (clean pair green board; seeded pair prioritized findings; confirm/false-positive write-back; platform-pair switch)

### Chapter 24. Engineering Conventions
- 24.1 Python 3.11+, type hints everywhere, pydantic as single source of truth
- 24.2 Money = `Decimal`, never float; default tolerance 0.00
- 24.3 Determinism & fingerprint-version logging in every report
- 24.4 Data-driven fingerprints — no failure-mode logic in Python that belongs in JSON
- 24.5 Testing standard: every rule type has unit tests, docstring, and a sample dataset that trips it
- 24.6 Commit conventions, small commits per milestone, pytest gate

### Chapter 25. Synthetic Test Data Specification
- 25.1 Absolute rule: no real participant data; fake SSNs (900-xx range), fake names, small plans (50–200 participants)
- 25.2 Clean plan pair specification (proves zero false noise)
- 25.3 Seeded-defect plan pair: one deliberate defect per seed failure mode, with a seeding manifest (`data/samples/README.md`)
- 25.4 Data generator design (deterministic, seeded RNG)

### Chapter 26. Repo CLAUDE.md (Ready to Drop In)
- 26.1 Full text of the repository CLAUDE.md (derived from CLAUDE_1.md, updated to match this spec's IDs and structure)
- 26.2 Claude Code session guidance: which spec chapters to load per milestone

### Chapter 27. AI Prompt Library
- 27.1 Prompt templates for each AI Orchestration function (Ch. 8.2) with input/output contracts and evaluation notes
- 27.2 Prompt versioning & storage conventions

---

## APPENDICES (~20 pages)

- **Appendix A — Glossary** (bookmarked; hyperlink target for every first-use term)
  Terms include: Platform Pair, Fingerprint, Failure Mode, Detection Rule, Conversion Run, Finding, Learning Loop, Money Type/Source, Investment Menu, Vesting Schedule, Copybook, COMP-3 / Packed Decimal, EBCDIC, Reconciliation, Parallel Run, Cutover, RKS, CORE, Omni, TRAC, Control File (CT.*), Money-Type Reconciliation, Suite Snapshot, Probability Write-Back, Adapter, Canonical Model, plus all role names and status values
- **Appendix B — Requirements Traceability Matrix** — REQ ID → spec section → milestone (MS ID) → test reference
- **Appendix C — Assumptions & Risk Matrix** — adapted from the Congruent 15-item assumptions matrix (access, data readiness, customization variability, layout availability, spec freeze, SME availability, batch approach, transfer security, environment readiness, sign-offs, history scope, schema stability, automation, regulatory standardity, business stability)
- **Appendix D — Sample Payloads & Files** — full Fingerprint JSON, rule JSON per type, findings.json, sample copybook layout, sample extract fragments
- **Appendix E — Report Mockups** — findings HTML scoreboard, reconciliation report samples
- **Appendix F — Out of Scope Register** — real Omni/TRAC connectivity, FIS-licensed source, real client data, auth hardening for POC, MAPTIVA row-level payroll intake (future integration), production-scale performance

---

## BUILD SEQUENCE FOR THE MASTER DOCUMENT

| Step | Content | Est. Pages |
|------|---------|-----------|
| 1 | Front matter + Part I | ~30 |
| 2 | Part II (domain + fingerprint model + failure-mode library) | ~35 |
| 3 | Part III (architecture + AI orchestration) | ~25 |
| 4 | Part IV (functional specs) | ~45 |
| 5 | Part V (adapters) + Part VI (API/DB) | ~40 |
| 6 | Part VII (UI) + Part VIII (security/DevOps) | ~33 |
| 7 | Part IX (implementation guide) + Appendices | ~40 |
| — | **Total** | **~180–240** |

Each step delivers an updated master .docx with regenerated TOC and glossary hyperlinks, so the document is always complete and navigable at its current state of build.
