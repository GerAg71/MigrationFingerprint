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
| MS-1.2 … MS-3.3 | see spec Ch. 23 | open |

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```
uv sync
uv run pytest
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
