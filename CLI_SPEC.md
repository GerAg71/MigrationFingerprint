# MAPTIVA Migration Fingerprint™ — CLI Specification (Addendum to Solution Spec v1.0)

Defines the POC command surface. Binds to spec chapters 10–14 and milestones MS-1.2 through MS-2.4. Place at `docs/CLI_SPEC.md` in the repo. Entry point: `fingerprint` (console script → `src/cli.py`).

## Global conventions

- All commands accept `--json` to emit machine-readable JSON to stdout instead of the human-readable table (default: table).
- All paths are relative to the repo root unless absolute.
- Timestamps in output metadata only, never in findings bodies (REQ-009).
- `--fingerprint-dir` (default `data/fingerprints/`), `--runs-dir` (default `data/runs/`) are overridable on every command.

## Exit codes (uniform across commands)

| Code | Meaning |
| --- | --- |
| 0 | Success (a run that produced findings still exits 0 — the run succeeded) |
| 1 | Runtime error (unhandled exception, missing file, bad arguments) |
| 2 | Findings present AND `--fail-on-findings` was passed (CI gate; optionally `--fail-on-findings=HIGH` to gate on a minimum severity) |
| 3 | Refusal by validation gate: schema-invalid fingerprint (REQ-010), unregistered rule datasets (REQ-021), partial file (REQ-022) |

## Commands

### fingerprint validate <fingerprint.json>
Schema-validate a fingerprint file (MS-1.2). Prints `OK <pair> <version> — N modes, M rules` or pathed pydantic errors. Exit 0 / 3.

### fingerprint pairs
List platform pairs discovered under the fingerprint dir with current version, mode count, and status.

### fingerprint suite --pair <pair_id> [--version <v>]
Print the prioritized suite (spec §12.2) without running: order, rule_id, fm_id, priority_score, severity, datasets required. Defaults to the highest published version. This is the "targeted, not generic" view (demo step 1).

### fingerprint run --pair <pair_id> --source-dir <dir> --target-dir <dir> [--version <v>] [--plans P1,P2] [--wave W1] [--layout-dir <dir>] [--fail-on-findings[=SEV]]
Execute a conversion run (MS-1.5):
1. Load + validate fingerprint (exit 3 on failure).
2. Register datasets: every `<canonical>.csv` (Phase 1) or `<canonical>.dat` with a matching LayoutSpec in `--layout-dir` (Phase 2) found in each dir, per spec §10.4. Content-hash each file.
3. Refuse (exit 3) if any enabled rule's datasets are unregistered on either side.
4. Persist suite snapshot; execute in priority order; write `data/runs/<run_id>/findings.json` (+ `findings.html` from MS-2.3, + per-finding drill-down CSVs).
5. Print the summary scoreboard: rules run / passed / failed, records affected, severity mix, run_id.

`run_id` format: `RUN-YYYY-MM-DD-NNNN` (NNNN = zero-padded daily sequence).

### fingerprint findings <run_id> [--severity SEV] [--status STATUS]
List findings for a run: finding_id, fm_id, rule_id, severity, records_affected, status. `--json` includes sample records.

### fingerprint show <finding_id>
Full detail for one finding: sample-record table (keys | source | target | delta), drill-down CSV path, remediation text.

### fingerprint review <finding_id> --decision confirmed|false_positive [--comment "..."] [--reviewer <name>]
Record a review (MS-2.4). Applies the probability write-back (spec §14.2: k=10, clamp [0.05, 0.99]), appends the learning event, and prints: fm_id, counters before → after, probability before → after, and the new patch version created (or pending, see `publish`). POC policy: write-backs accumulate in a draft version; `publish` finalizes.

### fingerprint publish --pair <pair_id> --bump patch|minor|major [--changelog "..."]
Finalize the draft fingerprint version (spec §14.5–14.6). Prints old → new version and a mode-level diff summary.

### fingerprint diff --pair <pair_id> --from <v1> --to <v2>
Version diff: added/removed/changed modes and rules, probability deltas.

### fingerprint history --pair <pair_id> [--fm FM-001]
Learning history: per-mode probability timeline from the learning-event log (demo step 4 evidence).

### fingerprint author-mode --pair <pair_id>
Guided interactive flow to draft a new failure mode + rule (spec §14.4): prompts for name, category, description, domains, impact, initial probability (default 0.30), rule type + params; schema-validates; appends to the draft version.

### fingerprint report <run_id> [--format json|html] [--recon plan|participant|loan|contribution|quality|all]
Re-render report artifacts for a run (MS-2.3). `--recon` renders the reconciliation suite (spec §13.2).

## Demo script → command mapping (spec §23.5)

| Demo step | Command |
| --- | --- |
| 1. Prioritized suite | `fingerprint suite --pair omni-zos-to-omni-linux` |
| 2. Clean pair, green board | `fingerprint run --pair omni-zos-to-omni-linux --source-dir data/samples/source/PLN-CLEAN-01 --target-dir data/samples/target/PLN-CLEAN-01` |
| 3. Seeded pair, prioritized findings | same, with `PLN-SEED-01` dirs; then `fingerprint findings <run_id>` and `fingerprint show <finding_id>` |
| 4. Learning loop | `fingerprint review <id> --decision confirmed` ×2, `--decision false_positive` ×1; `fingerprint history --pair …`; `fingerprint publish --bump patch` |
| 5. Different pair, different suite | `fingerprint suite --pair omni-to-trac` |

## Notes for MS-1.1 (schema impact)

Two small param extensions used by the seed fingerprint that the pydantic models must include: `validity` entries support `gte_field` (cross-field comparison, RULE-DATEVAL-001) and `max: "today"`; `encoding_check` params support `allowed: "custom-set"` with `custom_set`. The seed file also carries a top-level `detection_rules` array (rules referenced by ID from failure modes) and a `sample_defect` field per mode — reflect both in the models.
