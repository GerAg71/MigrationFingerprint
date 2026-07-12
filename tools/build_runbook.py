"""Build the plain-English technical runbook (docs/runbook.html).

The catalog sections are GENERATED from the published fingerprint JSONs in
data/fingerprints, so every failure mode, rule, probability, impact, and
severity shown is exactly what the engine executes - the runbook can never
drift from the application. Static sections (concepts, scoring, severity,
learning-loop math, provenance, CLI) are maintained here.

Run:  python -m tools.build_runbook          (writes docs/runbook.html)

Deterministic: same fingerprints in, byte-identical page out.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STORE = REPO / "data" / "fingerprints"
OUT = REPO / "docs" / "runbook.html"

SEVERITY_MEANING = {
    "CRITICAL": ("Participant money or record counts are wrong. A finding at "
                 "this level blocks sign-off until resolved - there is no "
                 "acceptable error rate when the data is someone's "
                 "retirement account."),
    "HIGH": ("Values that must be remediated before cutover - balances, "
             "derived amounts, required fields. Wrong today, visible to the "
             "client tomorrow."),
    "MEDIUM": ("Provisions, formats, and mappings that need analyst review. "
               "May be acceptable with documentation, never silently."),
    "LOW": ("Cosmetic or monitoring-level issues. Tracked so nothing is "
            "invisible, prioritized last."),
}
SEVERITY_COLOR = {"CRITICAL": "#b91c1c", "HIGH": "#ea580c",
                  "MEDIUM": "#d97e06", "LOW": "#64748b"}

PAIR_BLURB = {
    "omni-zos-to-omni-linux": (
        "The transformation path: Omni on the mainframe to Omni on Linux via "
        "extract-and-load. 18 seed failure modes - FM-001..FM-008 from real "
        "conversion experience, FM-009..FM-018 from the standard validation "
        "methodology catalog."),
    "omni-to-trac": (
        "A cross-product migration: Omni to TRAC. Placeholder fingerprint - "
        "the mainframe-transition modes are absent and cross-platform "
        "mapping risks (vesting, money types, provisions) lead the suite."),
    "omni-zos-to-omni-linux-restore": (
        "The backup/restore path: same product on both sides, so a clean "
        "restore is value-identical and every rule runs at tolerance zero. "
        "Restore-specific modes FM-101..FM-106 cover custom-code drift, UDF "
        "loss, off-label usage, required-field regression, truncation, and "
        "the tolerance-zero net. See docs/Omni_to_Omni_Restore_Strategy.md."),
}


def esc(text) -> str:
    return html.escape(str(text), quote=True)


def load_pairs() -> list[dict]:
    pairs = []
    for pair_dir in sorted(STORE.iterdir()):
        if not pair_dir.is_dir():
            continue
        versions = sorted((d for d in pair_dir.iterdir()
                           if d.is_dir() and d.name[0].isdigit()),
                          key=lambda d: [int(x) for x in d.name.split(".")])
        if not versions:
            continue
        payload = json.loads((versions[-1] / "fingerprint.json")
                             .read_text(encoding="utf-8"))
        pairs.append(payload)
    return pairs


# --- plain-English rule descriptions, derived from type + params ---------------


def describe_rule(rule: dict) -> str:
    params = rule.get("params", {})
    joins = ", ".join(rule.get("join_keys") or [])
    t = rule["type"]
    if t == "field_compare":
        parts = []
        compare = params.get("compare") or []
        if compare:
            fields = ", ".join(
                f"{c['field']}"
                + (f" (tolerance {c['tolerance']})" if c.get("tolerance")
                   is not None else "")
                for c in compare)
            parts.append(
                f"Matches source and target rows on <code>{esc(joins)}</code> "
                f"and compares {esc(fields)} field by field. A value on one "
                f"side and blank on the other always counts as a mismatch.")
        validity = params.get("validity") or []
        if validity:
            checks = "; ".join(
                f"{v['field']}: " + ", ".join(
                    k if not isinstance(val, str) else f"{k} {val}"
                    for k, val in v.items()
                    if k != "field" and val not in (None, False))
                for v in validity)
            parts.append(f"Also validates target values on their own: "
                         f"{esc(checks)}.")
        return " ".join(parts)
    if t == "count_balance":
        aggs = "; ".join(
            (f"row count per {', '.join(a['group_by'])}" if a["op"] == "count"
             else f"sum of {a['measure']} per {', '.join(a['group_by'])}")
            for a in params.get("aggregations", []))
        return (f"Totals both sides and requires exact equality: {esc(aggs)}. "
                "A variance at a coarse level automatically attaches the "
                "finer-level breakdown, so you can see which group moved.")
    if t == "referential":
        extra = ""
        if params.get("unique"):
            extra = (f" Also enforces uniqueness of "
                     f"{', '.join(params['unique'])} on each side - every row "
                     "of a duplicate group is reported.")
        if params.get("unmapped_target_fields"):
            extra += (" Flags target values that no mapping rule accounts "
                      "for (untraceable derived data).")
        return (f"Every <code>{esc(joins)}</code> present on one side must "
                f"exist on the other; orphans are reported in both "
                f"directions (missing_in_target / unexpected_in_target)."
                + esc(extra))
    if t == "derived_recompute":
        return (f"Recomputes <code>{esc(params.get('recompute'))}</code> from "
                f"its inputs using the engine's stock formula and compares "
                f"the result to the stored "
                f"<code>{esc(params.get('compare_field'))}</code> at "
                f"tolerance {esc(params.get('tolerance'))}. Where the stored "
                "value disagrees with the stock computation, custom logic "
                "produced it - detected without reading any source code.")
    if t == "encoding_check":
        return (f"Scans {esc(', '.join(params.get('fields', [])))} for "
                f"characters outside the allowed set "
                f"(<code>{esc(params.get('allowed'))}</code>) and for "
                "mojibake signatures (the Ã/Â/&#65533; artifacts of a "
                "wrong-codepage decode) even when characters are technically "
                "representable.")
    if t == "sort_order_check":
        return (f"Checks that rows ordered by "
                f"{esc(', '.join(params.get('order_by', [])))} follow "
                f"<code>{esc(params.get('collation'))}</code> collation; "
                "adjacent inversions are reported. EBCDIC sorts digits after "
                "letters - the opposite of ASCII - so resorted extracts "
                "betray themselves at digit/letter boundaries.")
    if t == "format_conformance":
        rows = []
        for f in params.get("fields", []):
            expectation = []
            if f.get("must_be_blank"):
                expectation.append("must be BLANK (a 'Not Used' position - "
                                   "any data is off-label usage)")
            if f.get("required"):
                expectation.append("required (blank = finding)")
            if f.get("picture"):
                expectation.append(f"must fit Picture {f['picture']}")
            if f.get("domain"):
                expectation.append(f"must be one of {', '.join(f['domain'])}")
            rows.append(f"{f['field']}: {'; '.join(expectation)}")
        side = params.get("side", "target")
        return (f"Validates the {esc(side)} dataset against the Format "
                f"Matrix expectation model - {esc(' | '.join(rows))}. "
                "Pictures are COBOL: X(n) is text up to n chars; 9(n) is "
                "digits only; S9(n)V99 is a signed number with two implied "
                "decimal places.")
    return "(no description available for this rule type)"


RULE_TYPE_DOCS = [
    ("field_compare", "Field compare",
     "The workhorse. Joins source and target rows on key fields and compares "
     "chosen columns value by value - money at an exact Decimal tolerance "
     "(0.00 unless a rule says otherwise), text and dates by strict "
     "equality. Can also run one-sided validity checks (not-null, length, "
     "pattern, ranges, cross-field rules like term_date >= hire_date). "
     "Unmatched rows are deliberately NOT its job - that's referential's."),
    ("count_balance", "Count / balance reconciliation",
     "Proves completeness with totals: row counts and money sums per "
     "grouping level (plan, money type, investment, participant), source vs "
     "target, exact equality required. Coarse variances automatically carry "
     "the finer-level contributing groups, which is the 'drill down behind "
     "any variance' behavior on the reconciliation reports."),
    ("referential", "Referential integrity",
     "Every record on one side must trace to the other side, in both "
     "directions. Also enforces key uniqueness (duplicate SSNs, duplicate "
     "IDs) and can flag target values with no mapping-rule provenance."),
    ("derived_recompute", "Derived-value recompute",
     "Recomputes what the software SHOULD produce - vested percent from the "
     "schedule and service years, loan balances by re-amortizing from "
     "origination with half-even rounding per period - and compares to what "
     "is stored. This is how custom code on a source system is detected "
     "without ever reading it: the stored value disagrees with the stock "
     "formula."),
    ("encoding_check", "Encoding check",
     "Finds the fingerprints of a bad EBCDIC-to-ASCII conversion: characters "
     "outside the allowed set and mojibake signatures (Jos&Atilde;&copy; "
     "instead of Jos&eacute;). Catches wrong-codepage decodes even when the "
     "bytes are printable."),
    ("sort_order_check", "Sort-order check",
     "EBCDIC and ASCII disagree about whether digits sort before letters. "
     "Extracts that were resorted on the wrong platform betray themselves "
     "at digit/letter boundaries; this rule reports adjacent ordering "
     "inversions under the declared collation."),
    ("format_conformance", "Format conformance",
     "Validates a dataset against the platform's format dictionary (compiled "
     "from the Omni Format Matrix): COBOL Picture domains, Required flags, "
     "enumerated code domains, and 'Not Used' filler positions that must "
     "stay blank - data hiding in a filler is off-label usage no restore "
     "will ever report. Runs one-sided, so the same rules can profile the "
     "source before cutover (Pass A) or audit the target after restore "
     "(Pass B)."),
]

GLOSSARY = [
    ("Platform pair", "A directional source-to-target combination (Omni z/OS "
     "to Omni Linux). Direction matters: A-to-B fails differently than "
     "B-to-A. Each pair-and-method gets its own fingerprint."),
    ("Fingerprint", "A versioned JSON library of the failure modes one "
     "platform pair is known to produce, each bound to executable detection "
     "rules. It is data, not code - the engine only knows the seven generic "
     "rule types."),
    ("Failure mode (FM)", "One named, codified defect pattern - e.g. 'Loan "
     "balance carry-over'. Carries a probability (how often this pair "
     "produces it), an impact (how much it hurts), the detection rules that "
     "catch it, a remediation playbook, and history counters."),
    ("Detection rule (RULE)", "One executable check bound to a failure mode. "
     "Seven types exist (see Rule types). Rules bind to canonical datasets, "
     "never platform-specific file formats."),
    ("Canonical dataset", "The platform-neutral vocabulary: plans, "
     "participants, balances, contributions, loans, loan_payments, vesting, "
     "transactions, prices, udf_definitions, udf_values. Adapters translate "
     "each platform's extracts into these; rules never see platform names."),
    ("Prioritized suite", "All enabled rules of a fingerprint ordered by "
     "their failure mode's probability x impact, descending. Frozen as an "
     "immutable snapshot with every run, so the ordering is auditable."),
    ("Conversion run", "One execution of the suite over a source extract "
     "directory and a target extract directory. Produces the findings "
     "report, reconciliation reports, and drill-down CSVs."),
    ("Finding", "One rule tripping: which failure mode, which rule, "
     "severity, how many records, sample records inline (up to 25), a full "
     "drill-down CSV, and the remediation text from the failure mode."),
    ("Dataset gate (REQ-021)", "Before any rule runs, every dataset required "
     "by an enabled rule must be registered on both sides. Missing extracts "
     "refuse the whole run loudly - rules are never silently skipped."),
    ("Learning loop", "Analyst reviews write back into the fingerprint: "
     "confirmations raise a mode's probability, false positives lower it "
     "(see the math section). Publishing mints a new immutable version."),
    ("Draft / publish", "Reviews accumulate in a draft; publishing freezes "
     "it as the next semantic version. Past runs stay pinned to the version "
     "they executed against - history never rewrites."),
    ("Exception register", "Every finding not marked false positive, tracked "
     "with owner, status, opened/closed dates, and resolution evidence. "
     "Feeds the sign-off package and the under-0.1%-unresolved metric."),
    ("Sign-off package", "The client deliverable zip: certification page "
     "with success metrics vs targets, findings report, five reconciliation "
     "reports, the exception register with closure evidence, and the audit "
     "extract - with per-file SHA-256 hashes in a manifest."),
    ("Determinism (REQ-009)", "Same extracts + same fingerprint version + "
     "same run id = byte-identical findings. No clock, randomness, or "
     "dictionary-order dependence anywhere in rules or reports. This is "
     "what makes results auditable."),
    ("Tolerance zero", "The restore-path standard: same product on both "
     "sides means any difference at all - one cent, one character - is a "
     "finding."),
    ("Manifest (REQ-032)", "For seeded test pairs, the exact expected "
     "finding counts, derived from the planted defects BEFORE first "
     "execution. The engine must match it exactly - every defect found, "
     "nothing else flagged."),
    ("LayoutSpec", "A JSON description of a fixed-width record: field "
     "positions, lengths, types, implied decimals, packed fields. Drives "
     "EBCDIC ingest and is what the Format Matrix compiles into."),
    ("UDF", "User-Defined Field - a client's custom field beyond the stock "
     "data model. A restore drops values whose definitions were never "
     "created on the target; the udf_definitions/udf_values datasets make "
     "that loss countable."),
]

CLI_COMMANDS = [
    ("validate <file>", "Validate a fingerprint JSON against the schemas; "
     "pathed errors on refusal (exit 3)."),
    ("pairs", "List every platform pair in the store with version, status, "
     "mode and rule counts."),
    ("suite --pair <id>", "Print the prioritized suite without running."),
    ("run --pair <id> --source-dir D1 --target-dir D2 [--layout-dir L]",
     "Execute a conversion run; writes findings.json/html, reconciliation "
     "reports, and drill-down CSVs under data/runs/<run-id>."),
    ("findings <run> / show <finding>", "List a run's findings in priority "
     "order; drill into one finding's records."),
    ("report <run> [--recon plan|participant|loan|contribution|quality|all]",
     "Render the self-contained HTML reports."),
    ("review <finding> --decision confirmed|false_positive",
     "Adjudicate a finding - this is what moves probabilities."),
    ("assign / comment / resolve / close", "The exception workflow: set an "
     "owner, note progress, mark remediated (note required), close with "
     "evidence (re-run reference)."),
    ("exceptions <run>", "The exception register - every non-false-positive "
     "finding tracked to closure."),
    ("history --pair <id> / publish --pair <id> --bump patch|minor",
     "See probability timelines; freeze the draft as the next version."),
    ("diff --pair <id> --from A --to B", "What changed between two "
     "fingerprint versions."),
    ("author-mode --pair <id> ...", "Add a newly-discovered failure mode to "
     "the draft (human authoring - how tribal knowledge gets banked)."),
    ("signoff <run> [--narrative ... --approved-by ...]",
     "Assemble the certification zip for a designated final run."),
    ("compile-matrix <xlsx> --out DIR [--decks]", "Compile the Omni Format "
     "Matrix into card layouts and COBOL extract-deck skeletons."),
]

PROVENANCE = [
    ("Failure modes FM-001..FM-008 (z/OS pair)",
     "Real conversion experience - the recurring defects documented in "
     "'Retirement Recordkeeping Conversion Issues and Resolutions' "
     "(loan carry-over, vesting mapping, custom fields...), codified per "
     "spec Chapter 6.2.", "docs/ background documents; spec Ch. 6.2"),
    ("Failure modes FM-009..FM-018 (z/OS pair)",
     "The standard conversion validation methodology's report catalog, "
     "productized into executable rules per spec Chapter 6.3.",
     "spec Ch. 6.3"),
    ("Failure modes FM-101..FM-106 (restore pair)",
     "The Omni-to-Omni backup/restore strategy: gaps a vendor restore "
     "cannot see (custom code drift, UDF loss, off-label usage, "
     "truncation).", "docs/Omni_to_Omni_Restore_Strategy.md"),
    ("Probabilities and impacts",
     "Seeded by the conversion team's judgment per mode, then TUNED BY "
     "EVIDENCE: every confirmed finding raises a probability, every false "
     "positive lowers it (learning loop, spec Ch. 14.2). Impact is human "
     "judgment and is never auto-adjusted.", "fingerprint JSONs; spec Ch. 14"),
    ("Severities",
     "Assigned per detection rule by the fingerprint author, using the "
     "scale documented in the Severity section. Stored in the fingerprint "
     "JSON, editable via author-mode and versioned like everything else.",
     "fingerprint JSONs; spec Ch. 5.4"),
    ("Rule semantics (the seven types)",
     "Spec Chapter 11 defines each type's contract; the executors implement "
     "them deterministically (Decimal money, no clock, no randomness).",
     "spec Ch. 11; src/rules/"),
    ("Suite ordering", "Spec Chapter 12.2: probability x impact descending; "
     "ties by severity, then failure-mode id.", "spec Ch. 12.2; "
     "src/fingerprint/prioritize.py"),
    ("Format expectations (restore pair)",
     "The Omni Format Matrix workbook - 15 processes, 53 card layouts, 710 "
     "field definitions with COBOL Pictures and Required flags - compiled "
     "into machine-readable layouts by the compile-matrix command.",
     "docs/Omni_Format_Matrix_Complete.xlsx; data/layouts/omni-restore/"),
    ("This runbook's catalog",
     "Generated directly from the published fingerprint JSONs by "
     "tools/build_runbook.py - the numbers on this page are the numbers "
     "the engine runs. Regenerate after any publish.",
     "data/fingerprints/*/*/fingerprint.json"),
]


def sev_chip(severity: str) -> str:
    return (f'<span class="sev" style="background:{SEVERITY_COLOR[severity]}">'
            f'{severity}</span>')


def score_bar(score: float) -> str:
    return (f'<span class="bar"><i style="width:{score * 100:.0f}%"></i>'
            f'</span> <b>{score:.4g}</b>')


def fm_anchor(pair_id: str, fm_id: str) -> str:
    return f"{pair_id}--{fm_id}"


def render_fm_card(pair_id: str, fm: dict, rules_by_id: dict) -> str:
    score = fm["probability"] * fm["impact"]
    rules = "".join(
        f'<a class="xref" href="#{esc(fm_anchor(pair_id, rid))}">'
        f'{esc(rid)}</a>' for rid in fm["detection_rules"])
    sample = (f'<p><b>Example defect:</b> {esc(fm["sample_defect"])}</p>'
              if fm.get("sample_defect") else "")
    origin = {"seed:experience": "conversion experience",
              "seed:methodology": "validation methodology catalog",
              "learned": "learned during an engagement"}[fm["origin"]]
    return f"""
<div class="card" id="{esc(fm_anchor(pair_id, fm['id']))}">
  <div class="cardhead"><span class="fmid">{esc(fm['id'])}</span>
    <h4>{esc(fm['name'])}</h4>
    <span class="chip">{esc(fm['category'])}</span></div>
  <div class="scorerow">probability <b>{fm['probability']:.2f}</b> &times;
    impact <b>{fm['impact']:.2f}</b> = {score_bar(score)}
    <span class="chip ghost">origin: {esc(origin)}</span>
    <span class="chip ghost">domains: {esc(', '.join(fm['data_domains']))}</span></div>
  <p>{esc(fm['description'])}</p>
  {sample}
  <p><b>How to correct it:</b> {esc(fm['remediation'])}</p>
  <p><b>Detected by:</b> {rules}</p>
</div>"""


def render_rule_card(pair_id: str, rule: dict) -> str:
    datasets = (f"{rule.get('source_dataset') or '&mdash;'} &rarr; "
                f"{rule['target_dataset']}")
    return f"""
<div class="card" id="{esc(fm_anchor(pair_id, rule['rule_id']))}">
  <div class="cardhead"><span class="ruleid">{esc(rule['rule_id'])}</span>
    <span class="chip type">{esc(rule['type'])}</span>
    {sev_chip(rule['severity'])}
    <a class="xref" href="#{esc(fm_anchor(pair_id, rule['failure_mode']))}">
      {esc(rule['failure_mode'])}</a></div>
  <div class="scorerow"><span class="chip ghost">datasets: {datasets}</span>
    {'' if rule.get('enabled', True) else '<span class="chip">DISABLED</span>'}</div>
  <p><b>What it checks:</b> {describe_rule(rule)}</p>
</div>"""


def build() -> str:
    pairs = load_pairs()

    catalog_sections = []
    for fp in pairs:
        pid = fp["fingerprint_id"]
        fms_by_score = sorted(
            fp["failure_modes"],
            key=lambda m: (-(m["probability"] * m["impact"]), m["id"]))
        rules_by_id = {r["rule_id"]: r for r in fp["detection_rules"]}
        fm_cards = "".join(render_fm_card(pid, fm, rules_by_id)
                           for fm in fms_by_score)
        rule_cards = "".join(render_rule_card(pid, r)
                             for r in fp["detection_rules"])
        catalog_sections.append(f"""
<section id="catalog-{esc(pid)}">
  <h2>{esc(pid)} <span class="chip">v{esc(fp['version'])}</span>
    <span class="chip ghost">{len(fp['failure_modes'])} failure modes &middot;
    {len(fp['detection_rules'])} rules</span></h2>
  <p class="lead">{esc(PAIR_BLURB.get(pid, ''))}</p>
  <h3>Failure modes (in priority order)</h3>
  {fm_cards}
  <h3>Detection rules</h3>
  {rule_cards}
</section>""")

    rule_type_cards = "".join(
        f'<div class="card" id="type-{name}"><div class="cardhead">'
        f'<span class="ruleid">{name}</span><h4>{title}</h4></div>'
        f'<p>{text}</p></div>'
        for name, title, text in RULE_TYPE_DOCS)

    severity_rows = "".join(
        f'<div class="card"><div class="cardhead">{sev_chip(s)}</div>'
        f'<p>{esc(text)}</p></div>'
        for s, text in SEVERITY_MEANING.items())

    glossary_cards = "".join(
        f'<div class="card"><div class="cardhead"><h4>{esc(term)}</h4></div>'
        f'<p>{esc(text)}</p></div>' for term, text in GLOSSARY)

    cli_rows = "".join(
        f'<div class="card"><div class="cardhead">'
        f'<code class="cmd">fingerprint {esc(cmd)}</code></div>'
        f'<p>{esc(text)}</p></div>' for cmd, text in CLI_COMMANDS)

    provenance_rows = "".join(
        f'<div class="card"><div class="cardhead"><h4>{esc(what)}</h4></div>'
        f'<p>{esc(where)}</p><p class="src">Source: {esc(src)}</p></div>'
        for what, where, src in PROVENANCE)

    nav_pairs = "".join(
        f'<a href="#catalog-{esc(fp["fingerprint_id"])}">'
        f'{esc(fp["fingerprint_id"])}</a>' for fp in pairs)

    total_fms = sum(len(fp["failure_modes"]) for fp in pairs)
    total_rules = sum(len(fp["detection_rules"]) for fp in pairs)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MAPTIVA&trade; Migration Fingerprint&trade; &mdash; Technical Runbook</title>
<style>
  :root{{--navy:#0D2440;--teal:#1F8A7D;--mint:#7FD4C4;--paper:#F4F7FB;
    --card:#fff;--ink:#16324F;--slate:#5B7086;--line:#DCE5EF;
    --mono:ui-monospace,'Cascadia Code',Consolas,monospace;
    --sans:'Segoe UI',system-ui,sans-serif}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--paper);color:var(--ink);font-family:var(--sans);
    line-height:1.55;font-size:14.5px}}
  header{{background:var(--navy);color:#fff;padding:22px 28px;position:sticky;
    top:0;z-index:20;box-shadow:0 4px 14px rgba(0,0,0,.15)}}
  header .t{{font-family:var(--mono);font-size:11px;letter-spacing:.16em;
    color:var(--mint)}}
  header h1{{font-size:20px;margin-top:3px}}
  #q{{margin-top:12px;width:100%;max-width:640px;padding:10px 15px;
    border-radius:10px;border:none;font-size:14.5px;font-family:var(--sans)}}
  #qcount{{font-family:var(--mono);font-size:11px;color:#9FB4CE;
    margin-left:12px}}
  .layout{{display:grid;grid-template-columns:230px 1fr;max-width:1240px;
    margin:0 auto;gap:26px;padding:24px 28px}}
  nav{{position:sticky;top:130px;align-self:start;font-size:13px;
    display:flex;flex-direction:column;gap:2px;max-height:calc(100vh - 150px);
    overflow-y:auto}}
  nav a{{color:var(--ink);text-decoration:none;padding:6px 10px;
    border-radius:7px;border-left:3px solid transparent}}
  nav a:hover{{background:#E8F0F9;border-left-color:var(--teal)}}
  nav .grp{{font-family:var(--mono);font-size:10px;letter-spacing:.12em;
    color:var(--slate);margin:10px 0 3px 10px}}
  section{{margin-bottom:34px;scroll-margin-top:150px}}
  h2{{color:var(--navy);font-size:20px;margin-bottom:6px;display:flex;
    align-items:center;gap:9px;flex-wrap:wrap}}
  h3{{color:var(--navy);font-size:15.5px;margin:18px 0 8px}}
  .lead{{color:var(--slate);max-width:88ch;margin-bottom:8px}}
  .card{{background:var(--card);border:1.5px solid var(--line);
    border-radius:11px;padding:13px 16px;margin-bottom:10px;
    scroll-margin-top:150px}}
  .card.hit{{border-color:var(--teal);box-shadow:0 0 0 3px rgba(31,138,125,.15)}}
  .cardhead{{display:flex;align-items:center;gap:9px;flex-wrap:wrap;
    margin-bottom:5px}}
  .cardhead h4{{font-size:14.5px;color:var(--navy)}}
  .fmid,.ruleid{{font-family:var(--mono);font-size:12px;font-weight:700;
    color:var(--teal)}}
  .chip{{font-family:var(--mono);font-size:10px;background:#E4EEF9;
    color:#28527F;padding:3px 9px;border-radius:99px;white-space:nowrap}}
  .chip.ghost{{background:#F0F5FB;color:var(--slate)}}
  .chip.type{{background:var(--navy);color:var(--mint)}}
  .sev{{font-family:var(--mono);font-size:9.5px;font-weight:700;color:#fff;
    padding:3px 9px;border-radius:99px;letter-spacing:.05em}}
  .bar{{display:inline-block;width:130px;height:8px;background:#EAF0F7;
    border-radius:99px;overflow:hidden;vertical-align:middle}}
  .bar i{{display:block;height:100%;background:linear-gradient(90deg,
    var(--teal),var(--mint))}}
  .scorerow{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;
    font-size:12.5px;color:var(--slate);margin-bottom:7px}}
  .xref{{font-family:var(--mono);font-size:11.5px;color:var(--teal);
    text-decoration:none;margin-right:8px}}
  .xref:hover{{text-decoration:underline}}
  p{{margin-bottom:6px;max-width:96ch}}
  code{{font-family:var(--mono);font-size:.92em;background:#EFF4FA;
    padding:1px 5px;border-radius:5px}}
  code.cmd{{background:var(--navy);color:var(--mint);padding:5px 11px;
    border-radius:8px;font-size:12px}}
  .src{{font-family:var(--mono);font-size:11px;color:var(--slate)}}
  .formula{{background:var(--navy);color:#EAF4FF;border-radius:11px;
    padding:15px 18px;font-family:var(--mono);font-size:13px;margin:9px 0;
    overflow-x:auto}}
  .formula b{{color:var(--mint)}}
  table.flow{{border-collapse:collapse;width:100%;margin:8px 0;font-size:13px}}
  table.flow td,table.flow th{{border:1px solid var(--line);padding:7px 11px;
    text-align:left;background:#fff}}
  table.flow th{{background:#F0F5FB;font-family:var(--mono);font-size:11px}}
  mark{{background:#FFE9A8;border-radius:3px;padding:0 2px}}
  .hidden{{display:none}}
  footer{{text-align:center;color:var(--slate);font-size:11.5px;
    padding:22px}}
  @media(max-width:900px){{.layout{{grid-template-columns:1fr}}
    nav{{position:static;max-height:none;flex-direction:row;flex-wrap:wrap}}}}
</style>
</head>
<body>
<header>
  <div class="t">MAPTIVA&trade; &middot; MIGRATION FINGERPRINT&trade; &middot; TECHNICAL RUNBOOK</div>
  <h1>How this application works &mdash; every mode, rule, score, and source</h1>
  <input id="q" type="search"
    placeholder="Search anything&hellip; FM-101, loan, tolerance, severity, UDF, picture, sign-off"
    autocomplete="off"><span id="qcount"></span>
</header>
<div class="layout">
<nav>
  <div class="grp">CONCEPTS</div>
  <a href="#overview">What this application is</a>
  <a href="#run">How a run works</a>
  <a href="#scoring">How the score is calculated</a>
  <a href="#severity">Severity: what the colors mean</a>
  <a href="#learning">The learning-loop math</a>
  <div class="grp">REFERENCE</div>
  <a href="#ruletypes">The seven rule types</a>
  {nav_pairs}
  <div class="grp">OPERATIONS</div>
  <a href="#cli">CLI reference</a>
  <a href="#provenance">Where the specs come from</a>
  <a href="#glossary">Glossary</a>
</nav>
<main>

<section id="overview">
  <h2>What this application is</h2>
  <p class="lead">Every platform pair fails in patterns. This application
  stores those patterns as a <b>fingerprint</b> &mdash; a versioned library of
  failure modes bound to executable detection rules &mdash; runs a validation
  suite ordered by where <em>this</em> migration is statistically most likely
  to break (<b>targeted, not generic</b>), drills every finding to the exact
  records affected, and writes every analyst decision back into the
  fingerprint so the next conversion starts smarter. Across the whole engine:
  money is exact decimal (never floating point), runs are deterministic
  (same inputs = byte-identical results), and passes are reported as
  explicitly as failures.</p>
  <p>The store currently holds <b>{len(pairs)} fingerprints</b> totalling
  <b>{total_fms} failure modes</b> and <b>{total_rules} detection rules</b>
  &mdash; every one documented on this page, generated from the same JSON the
  engine executes.</p>
</section>

<section id="run">
  <h2>How a run works</h2>
  <table class="flow">
    <tr><th>Stage</th><th>What happens</th><th>What can stop it</th></tr>
    <tr><td>1 &middot; Ingest</td><td>Source and target extract folders are
      read (CSV, or fixed-width/EBCDIC via LayoutSpecs). Values are typed at
      the boundary: money becomes exact Decimal, zero/blank dates become
      null, malformed rows are quarantined with reasons.</td>
      <td>A partially-delivered file halts that dataset (REQ-022).</td></tr>
    <tr><td>2 &middot; Register</td><td>Every dataset gets a content hash
      (SHA-256) recorded in the run &mdash; the audit anchor tying results to
      exact inputs.</td><td>&mdash;</td></tr>
    <tr><td>3 &middot; Gate</td><td>Every dataset required by any enabled
      rule must be present on both sides.</td><td>Missing extracts refuse
      the whole run with a list of what's missing (REQ-021) &mdash; rules
      are never silently skipped.</td></tr>
    <tr><td>4 &middot; Snapshot</td><td>The prioritized suite is frozen to
      suite_snapshot.json before execution &mdash; the ordering is auditable,
      not anecdotal.</td><td>&mdash;</td></tr>
    <tr><td>5 &middot; Execute</td><td>Rules run in priority order. A rule
      that finds nothing records an explicit PASS; a rule that trips builds
      a finding: severity, records affected, up to 25 sample records inline,
      a full drill-down CSV, and the failure mode's remediation text.</td>
      <td>&mdash;</td></tr>
    <tr><td>6 &middot; Report</td><td>findings.json (deterministic),
      findings.html (self-contained), reconciliation.json plus five
      client-facing reconciliation reports, drill-down CSVs.</td>
      <td>&mdash;</td></tr>
  </table>
  <p>After the run: findings are adjudicated (<code>review</code>), worked
  through the exception workflow (<code>assign &rarr; resolve &rarr;
  close</code> with evidence), and certified (<code>signoff</code>).</p>
</section>

<section id="scoring">
  <h2>How the score is calculated</h2>
  <div class="formula">score = <b>probability</b> &times; <b>impact</b><br><br>
probability &mdash; how likely this failure mode is for THIS platform pair
(0.05&ndash;0.99). Seeded by the conversion team, then moved by evidence:
every confirmed finding raises it, every false positive lowers it.<br>
impact &mdash; how much it hurts if it happens (0&ndash;1). Human judgment:
participant-money modes score high. Never auto-adjusted.</div>
  <p><b>Worked example</b> (top of the restore suite): FM-101 &ldquo;Custom
  code / script value drift&rdquo; has probability 0.70 and impact 0.90
  &rarr; score <b>0.63</b>. Its rule RULE-RST-VEST-001 therefore runs first.
  Every rule inherits its failure mode's score &mdash; that's why the three
  FM-106 rules all show 0.5525 (0.65 &times; 0.85).</p>
  <p><b>Tie-breaking</b> is deterministic (spec &sect;12.2): equal scores
  order by severity (CRITICAL &gt; HIGH &gt; MEDIUM &gt; LOW), then by
  failure-mode id. That's why RULE-RST-DIFF-001 (CRITICAL) sits above
  DIFF-002 (HIGH) above DIFF-003 (MEDIUM) in your screenshot &mdash; same
  score, severity breaks the tie.</p>
  <p>The suite is frozen with every run, and the &ldquo;compare against a
  generic ordering&rdquo; toggle on the suite screen shows exactly how much
  effort an alphabetical checklist would waste.</p>
</section>

<section id="severity">
  <h2>Severity: what the levels mean</h2>
  <p class="lead">Severity is assigned per detection rule by the fingerprint
  author (stored in the fingerprint JSON, versioned like everything else).
  It answers &ldquo;how bad is a finding from this rule&rdquo; &mdash;
  distinct from probability (&ldquo;how likely&rdquo;) and impact
  (&ldquo;how costly is the mode overall&rdquo;). It is used three ways:
  tie-breaking the suite order, the severity mix on the run scoreboard, and
  prioritizing the findings queue.</p>
  {severity_rows}
</section>

<section id="learning">
  <h2>The learning-loop math</h2>
  <p class="lead">Analyst reviews are not just record-keeping &mdash; they
  retune the fingerprint. The write-back is a Beta-style nudge anchored to
  the seed probability (spec &sect;14.2):</p>
  <div class="formula">k = 10&nbsp;&nbsp;(evidence weight of the prior)<br>
&alpha;&#8320; = p_seed &times; k<br>
p_new = (&alpha;&#8320; + confirmed) / (k + confirmed + false_positives)<br>
clamped to [0.05, 0.99], rounded half-even to 3 decimals</div>
  <p><b>Worked example:</b> FM-001 seeds at 0.70, so &alpha;&#8320; = 7.
  One confirmed finding: p = (7+1)/(10+1) = <b>0.727</b> &mdash; the mode
  rises in the next suite. One false positive instead:
  p = 7/11 = <b>0.636</b> &mdash; noise sinks. Ten confirmations:
  p = 17/20 = 0.850 &mdash; evidence accumulates but never saturates to
  certainty. The clamp means no mode is ever fully trusted (0.99 max) or
  fully dismissed (0.05 min) &mdash; dismissed checks still run, just last.</p>
  <p>Every event is recorded in an append-only log and replayable: the
  current probability is always recomputable from the seed plus the
  history counters. Publishing freezes the draft as the next version;
  past runs stay pinned to the version they ran against.</p>
</section>

<section id="ruletypes">
  <h2>The seven rule types</h2>
  <p class="lead">The engine knows exactly seven generic check types
  (spec Ch. 11); everything specific lives in fingerprint JSON. This is a
  hard rule (REQ-012) &mdash; it's why one rule library can serve every
  platform pair.</p>
  {rule_type_cards}
</section>

{''.join(catalog_sections)}

<section id="cli">
  <h2>CLI reference</h2>
  <p class="lead">Every command is also reachable through the dashboard and
  the REST API. Prefix with <code>uv run</code> (or use
  start-dashboard.ps1 for the UI).</p>
  {cli_rows}
</section>

<section id="provenance">
  <h2>Where the specs come from</h2>
  <p class="lead">Nothing on this page is invented by the application. Every
  number and definition traces to a source:</p>
  <p>The authoritative document is the <b>MAPTIVA Migration Fingerprint
  Solution Specification v1.0</b> (chapters cited below as
  &ldquo;spec Ch. n&rdquo;), supported by the CLI specification
  (CLI_SPEC.md) and the background conversion-practice documents in
  docs/.</p>
  {provenance_rows}
</section>

<section id="glossary">
  <h2>Glossary</h2>
  {glossary_cards}
</section>

</main>
</div>
<footer>Generated from the live fingerprint store by tools/build_runbook.py
&middot; {len(pairs)} pairs &middot; {total_fms} failure modes &middot;
{total_rules} rules &middot; regenerate after any publish</footer>

<script>
(function () {{
  const q = document.getElementById('q');
  const count = document.getElementById('qcount');
  const cards = Array.from(document.querySelectorAll('.card'));
  const sections = Array.from(document.querySelectorAll('section'));

  function clearMarks(root) {{
    root.querySelectorAll('mark').forEach(m => {{
      m.replaceWith(document.createTextNode(m.textContent));
    }});
    root.normalize();
  }}

  function markMatches(root, needle) {{
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const targets = [];
    while (walker.nextNode()) {{
      const node = walker.currentNode;
      if (node.parentElement.closest('script,style')) continue;
      const at = node.textContent.toLowerCase().indexOf(needle);
      if (at >= 0) targets.push([node, at]);
    }}
    targets.forEach(([node, at]) => {{
      const range = document.createRange();
      range.setStart(node, at);
      range.setEnd(node, at + needle.length);
      const mark = document.createElement('mark');
      try {{ range.surroundContents(mark); }} catch (err) {{}}
    }});
  }}

  function search() {{
    const needle = q.value.trim().toLowerCase();
    cards.forEach(card => clearMarks(card));
    if (!needle) {{
      cards.forEach(c => {{ c.classList.remove('hidden', 'hit'); }});
      sections.forEach(s => s.classList.remove('hidden'));
      count.textContent = '';
      return;
    }}
    let hits = 0;
    cards.forEach(card => {{
      const match = card.textContent.toLowerCase().includes(needle);
      card.classList.toggle('hidden', !match);
      card.classList.toggle('hit', match);
      if (match) {{ hits++; markMatches(card, needle); }}
    }});
    sections.forEach(section => {{
      const visible = section.querySelectorAll('.card:not(.hidden)').length;
      const hasCards = section.querySelectorAll('.card').length > 0;
      section.classList.toggle('hidden', hasCards && visible === 0);
    }});
    count.textContent = hits + ' matching entr' + (hits === 1 ? 'y' : 'ies');
  }}

  let timer = null;
  q.addEventListener('input', () => {{
    clearTimeout(timer); timer = setTimeout(search, 120);
  }});
}})();
</script>
</body>
</html>
"""


def main() -> None:
    page = build()
    OUT.write_text(page, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({len(page):,} chars)")


if __name__ == "__main__":
    main()
