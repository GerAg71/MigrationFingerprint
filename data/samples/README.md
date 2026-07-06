# Synthetic Sample Data — Seeding Manifest (spec Ch. 25)

Generated deterministically by `tests/datagen/` (fixed seed 20260705).
Regenerate with `uv run python -m tests.datagen` — output is byte-identical,
and `tests/test_sample_data.py` asserts it against these committed files.

**Absolute rule (REQ-031):** synthetic data only. Every SSN is in the 900-xx
range, all names are fake, plans are 120 participants.

## Pairs

- **PLN-CLEAN-01** — source and target emitted from the same canonical truth.
  Proves zero false noise: every executable rule passes (spec §25.2).
- **PLN-SEED-01** — same truth; the **target** side carries exactly one
  deliberate defect per seed failure mode, injected by the named mutators in
  `tests/datagen/mutators.py` (the manifest is code, spec §25.4).

Shape per spec §25.2: 120 participants, money types PRETAX/ROTH/MATCH,
investments F01–F05, 6 loans, graded 6-year vesting.

## Seeded defects (PLN-SEED-01 target)

Phase 1 rules run today; phase 2 rules (`derived_recompute`,
`encoding_check`, `sort_order_check`) execute from MS-2.1, and the
fixed-width/EBCDIC variant carrying FM-006 is emitted from MS-2.2.

| FM | Defect | Where | Detected by | Phase |
|----|--------|-------|-------------|-------|
| FM-001 | Loan L2 balance short by 33.62 | loans P0021/L2 | RULE-LOAN-BAL-001 (+ sum in RULE-LOAN-CNT-001) | 1 |
| FM-002 | Vested 60% vs recomputed 80% | vesting P0017 | RULE-VEST-PCT-001 | 2 |
| FM-003 | `svc_points` value with no mapping provenance | participants P0042 | RULE-DERIVED-TRACE-001 | 1 |
| FM-004 | Safe-harbor flag dropped; catch-up inverted | plans | RULE-PROV-MATRIX-001 | 1 |
| FM-005 | Mojibake name `JosÃ© RamÃ­rez`; collation divergence | participants P0044 | RULE-ENC-001 / RULE-SORT-001 | 2 |
| FM-006 | Packed decode ×100; sign nibble flipped | EBCDIC variant (MS-2.2) | RULE-PACKED-001 | 2 |
| FM-007 | Plan PRETAX total off by 0.01 | balances P0007 | RULE-BAL-TOTALS-001 (drill-down) | 1 |
| FM-008 | DOB 1897 (century window); zero date as 0001-01-01 | participants P0008, P0009 | RULE-DATE-001 | 1 |
| FM-009 | TERMINATED counted ACTIVE | participants P0010 | RULE-PCOUNT-001 | 1 |
| FM-010 | Blank SSN | participants P0030 | RULE-KEYS-001 | 1 |
| FM-011 | Duplicate SSN across two participants | participants P0100/P0101 | RULE-DUP-001 (both rows) | 1 |
| FM-012 | ROTH −250.00 offset by PRETAX +250.00 | balances P0012 | RULE-BAL-MT-001 (plan total reconciles) | 1 |
| FM-013 | Fund F03 subtotal +75.25 | balances P0013 | RULE-BAL-INV-001 | 1 |
| FM-014 | Loan L6 dropped; L3 missing maturity | loans | RULE-LOAN-CNT-001, RULE-LOAN-TERMS-001 | 1 |
| FM-015 | Employer MATCH +50.00, last payroll cycle | contributions P0002 | RULE-CONTRIB-001 | 1 |
| FM-016 | 41-char address; `#` in a name | participants P0060, P0061 | RULE-LEN-001 (1) / RULE-CHAR-001 (2) | 1+2 |
| FM-017 | Termination 2019-05-01 precedes hire 2021-03-15 | participants P0020 | RULE-DATEVAL-001 (also RULE-DATE-001 compare) | 1 |
| FM-018 | Negative MATCH balance −412.06 | balances P0018 | RULE-NEG-001 (+ totals rules) | 1 |

## Expected Phase-1 run over PLN-SEED-01 (REQ-032)

One defect can fire several rules — the totals rules intentionally backstop
the subtotal modes. The exact rule-level manifest (16 findings, 32 affected
records, 1 pass, 6 skipped) is asserted by
`tests/test_sample_data.py::test_seeded_pair_matches_manifest_exactly`.
