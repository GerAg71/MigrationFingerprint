# Strategy: Omni Mainframe → Omni Linux Backup/Restore Validation

**Using the Migration Fingerprint application, without engine code changes**

## 1. The use case

The Omni→Omni conversion path is backup/restore: the mainframe Omni is backed
up to a package and restored onto the Linux Omni by vendor tooling. The restore
is only clean if the source system is vanilla. In practice it never is:

| Gap source | What happens at restore |
|---|---|
| Modified code / custom COBOL / Omni scripting on the source | The custom logic's *outputs* restore, but the vanilla target recomputes them differently — silent value drift |
| UDFs defined on the source but absent on the target | Data lands with no definition, or is dropped — orphaned or lost user fields |
| Fields used differently than the software intended ("off-label") | Values restore into positions the new software interprets by the book — meaning changes without a byte changing |
| Changed layouts / filler repurposing | Data hidden in "Not Used" positions is invisible to the restore's own validation |

Today the conversion team hand-writes COBOL/Omni scripts per engagement to
probe for these gaps. The goal: pre-populate those scripts from a single
source of truth, run both sides through the Fingerprint engine, and report
what differs and how to correct it — with AI assisting the description and
script drafting, never the verdicts.

## 2. What the Omni Format Matrix gives us

`docs/Omni_Format_Matrix_Complete.xlsx` — 711 field definitions, 15 processes,
53 fixed-column card layouts. Columns: Process, Description, Card,
Columns (positions), Length, Picture, Field Name, Req/Opt.

- Pictures are COBOL: `X(n)`, `9(n)`, `9(n)V99` (implied decimals) — the same
  vocabulary the app's LayoutSpec fixed-width ingest already consumes.
- 176 Required fields → hard post-restore presence checks.
- 371 Optional fields → the client-divergence surface.
- 157 "Not Used" positions → the repurposing surface. **These are fields to
  us**, not filler: a vanilla system has blanks/zeros there; anything else is
  an off-label finding.
- Card ranges (e.g. `T813/02–T813/99`) → repeating user-field cards, the UDF
  surface.

The matrix is simultaneously three things:
1. **The extraction spec** — the logical order and layout to unload both sides.
2. **The expectation model** — what each position *should* contain (picture,
   required, domain).
3. **The correction vocabulary** — in Omni, corrections ARE transactions
   (T613 plan maint, T813 participant maint...). The same card formats that
   detect a gap define the corrective card deck that fixes it.

## 3. The strategy — five moves, no engine changes

### Move 1 — Compile the matrix into LayoutSpecs (configuration, not code)

Mechanically transform each of the 53 cards into a LayoutSpec JSON
(`data/layouts/omni-restore/<card>.json`): field name, start column, length,
type from Picture (`9(n)V99` → decimal with implied decimals — already
supported), required flag from Req/Opt. Two deliberate choices:

- **Materialize every "Not Used" range as a named field** (`filler_006_008`).
  Extraction carries them; rules can then assert "must be blank/zero" — data
  found there is a repurposing detection, which no restore-side validation
  will ever give you.
- Card→canonical mapping rides the app's existing dataset model: T600/T613 →
  plans, T801/T813 → participants, T114 → contributions, T384 → loans,
  T385 → loan_payments, T404/T444 → distribution datasets, T701/T650 →
  fund/product reference. Participant-level UDF cards land as additional
  columns on the datasets they belong to (the ingest already carries
  non-canonical columns through and annotates them).

This is a one-time transformation of the spreadsheet — authoring
configuration the engine already reads.

### Move 2 — Extract both sides in logical order (yes: that is the design)

The answer to "do we write scripts to extract the data in its logical order
and run it through the fingerprint" is **yes — and the scripts stop being
hand-written**:

- **Source extract**: unload the mainframe Omni to card-image files per the
  matrix layouts *before* the backup is cut.
- **Target extract**: the identical unload from the Linux Omni *after* the
  restore.
- Same layouts, same logical order (plan → product → funds → participants →
  money → loans → activity), both sides land in the app's ingest unchanged.

Because every extract program is the same skeleton (read master, MOVE fields
per card positions, WRITE card image), the COBOL/Omni scripting is
**generatable by template-stamping from the LayoutSpecs** — the matrix row
*is* the MOVE statement. Pre-population becomes mechanical, and the
engagement-specific part shrinks to file names and environment JCL.

### Move 3 — Author the restore fingerprint (JSON via `author-mode` + `publish`, zero code)

Extend the existing `omni-zos-to-omni-linux` pair — this exact pair is the
app's seed pair — with restore-specific failure modes, each carrying its
detection rules and its remediation playbook:

| New failure mode | Detection (existing rule types) | Remediation encoded on the mode |
|---|---|---|
| UDF definition gap | `referential`: every user field/table referenced by data must exist in the target's definitions; `count_balance` on definition tables | Re-key missing UDF definitions on target (T-card deck), re-run |
| Repurposed / off-label field usage | `field_compare` + validity (custom-set / format per Picture): letters in `9(n)`, data in Not Used fillers, out-of-domain codes | Map the hidden usage to a proper UDF on target; document the crosswalk |
| Custom code/script drift | `derived_recompute` with the *vanilla* formula: where source values disagree with stock recomputation, custom logic existed | Port or retire the custom routine; decide authoritative value pre-cutover |
| Restore truncation / record gaps | `count_balance` per card type per plan, tolerance 0 | Re-restore the affected region; escalate to vendor with the exact record list |
| Required-field regression | validity: the matrix's 176 Req fields non-blank post-restore | Corrective maintenance transactions from the matrix layouts |

Priorities are seeded from the conversion team's experience, and the
**learning loop** then tunes them per client: confirm/false-positive reviews
move probabilities, `publish` mints the next version, and the second wave of
plans is validated smarter than the first. Every hand-written probe script the
team has ever built is a candidate failure mode — this is where that tribal
knowledge gets banked permanently.

### Move 4 — Run the two-pass validation

- **Pass A (pre-cutover, source only)**: source extract vs the matrix's
  expectation model — validity rules only. This *predicts* the gaps before
  any data moves: repurposed fillers, off-domain values, UDF inventory. It is
  the "read the fingerprint before your data moves" briefing, delivered as a
  findings report the client sees up front.
- **Pass B (post-restore)**: source extract vs target extract, **tolerance
  0.00 everywhere**. An Omni→Omni restore is the strongest possible case for
  the engine: same schema both sides, so *any* difference is a finding. The
  prioritized suite orders the checks by the pair's failure history; findings
  carry record-level drill-down (plan / participant / field / source / target
  / delta); the exception workflow tracks every one to closure; the sign-off
  package assembles the certification evidence.

### Move 5 — Corrections close the loop in the same vocabulary

A confirmed finding's remediation is, in Omni terms, a transaction deck — and
the matrix defines those decks' formats. So the correction path is:
finding → failure mode's remediation playbook → corrective T-card deck
generated from the same LayoutSpecs → apply on target → clean re-run attached
as closure evidence. Detection and correction share one source of truth.

## 4. Where AI fits (and where it must not)

Within the app's existing AI layer (all read-only suggestions, REQ-019):

- **ExplainReconciliationVariance** — plain-language finding explanations
  citing the actual deltas (guard: no invented numbers).
- **SuggestFieldMappings** — proposes where an off-label source usage should
  land on the target (which UDF, which proper field).
- **SuggestFailureMode** — when analysts confirm a cluster of related gaps,
  drafts the new failure mode for author-mode approval, so the pattern is
  caught automatically next time.
- **GenerateConversionSummary** — the executive narrative in the sign-off
  package.

**AI-generated COBOL**: the request is "describe what needs to occur and let
AI create the COBOL scripts." Strategy:

1. **Near term (no code change)**: extraction scripts are *template-stamped*
   from the LayoutSpecs — deterministic generation, no model needed for the
   90% skeleton. AI drafts the engagement-specific residue (environment
   wiring, unusual record selection) as an authoring assistant, reviewed by
   the conversion team before anything runs.
2. **Product phase (one isolated addition)**: a `GenerateExtractScript`
   function inside `src/ai` — input: LayoutSpec + card selection; output:
   COBOL/Omni script draft with mandatory human approval before execution.
   REQ-018 already confines model SDKs to `src/ai`, so this lands without
   touching the engine, and the same prompt-library/guard pattern applies
   (generated code is validated against the LayoutSpec it claims to
   implement — field count, positions, pictures — before a human ever sees it).

The dividing line stays absolute: AI drafts scripts, explains variances, and
proposes mappings; **the numbers, the comparisons, and the verdicts come only
from the deterministic engine**.

## 5. Sequencing

| Step | Work | Nature |
|---|---|---|
| 1 | Matrix → 53 LayoutSpec JSONs (+ filler fields, Req flags) | Configuration authoring (mechanical) |
| 2 | Author restore failure modes + rules into `omni-zos-to-omni-linux`, publish minor version | Fingerprint JSON via existing CLI |
| 3 | Stamp extraction script skeletons from LayoutSpecs; team review | Template generation outside the engine |
| 4 | Pilot on one real plan: Pass A pre-cutover profile, Pass B post-restore diff | Existing run/report/workflow/sign-off |
| 5 | Reviews feed the learning loop; recurring patterns become authored modes | Existing learning machinery |
| 6 | (Product) `GenerateExtractScript` in `src/ai`; canonical dataset for UDF definitions if warranted | The only code, later, isolated |

**The one-line strategy:** compile the Format Matrix into the app's layout
language once; extract both Omnis through it in logical order; let the
fingerprint — extended with restore-specific failure modes — treat every
difference at tolerance zero as a prioritized, explainable, correctable
finding; and let each engagement's reviews make the next restore's fingerprint
sharper. Scripts stop being hand-written because the matrix writes them;
AI explains and drafts; the engine decides.
