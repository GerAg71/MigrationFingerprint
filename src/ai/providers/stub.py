"""Deterministic stub provider (spec §8.1: the application functions even if
no LLM is available). Produces rule-based outputs from the payload alone —
no model SDK, no network, no randomness — satisfying the same contracts the
product's Bedrock provider will. Confidence values are fixed per function so
threshold routing (§8.4) is exercisable in tests.
"""

from __future__ import annotations

from difflib import SequenceMatcher


def _first_sentence(text: str) -> str:
    return text.split(". ")[0].rstrip(".") + "."


def _explain_variance(payload: dict) -> dict:
    finding = payload["finding"]
    mode = payload.get("failure_mode") or {}
    fragments = []
    for record in finding.get("sample_records", [])[:3]:
        keys = ", ".join(f"{k}={v}" for k, v in sorted(record["keys"].items()))
        if record.get("delta") is not None:
            source = record.get("source") or {}
            target = record.get("target") or {}
            field = next((k for k in target if not k.startswith("_")), "value")
            fragments.append(
                f"{keys}: {field} moved from {source.get(field)} to "
                f"{target.get(field)} (delta {record['delta']})")
        else:
            checks = (record.get("target") or {}).get("_check", "mismatch")
            fragments.append(f"{keys}: {checks}")
    explanation = (
        f"Rule {finding['rule_id']} flagged {finding['records_affected']} "
        f"record(s) for {finding['failure_mode']}. " + " ".join(fragments))
    return {
        "explanation": explanation,
        "likely_cause": _first_sentence(
            mode.get("description", "Pattern consistent with the failure "
                                    "mode's known signature.")),
        "suggested_check": mode.get("remediation")
        or finding.get("remediation")
        or "Trace the affected records to their source rows.",
        "confidence": 0.85,
    }


def _conversion_summary(payload: dict) -> dict:
    run = payload["run"]
    summary = run["summary"]
    findings = payload.get("findings", [])
    mix = ", ".join(f"{count} {severity}" for severity, count
                    in sorted(summary.get("severity_mix", {}).items()))
    narrative = (
        f"Conversion run {run['run_id']} validated platform pair "
        f"{run['pair_id']} against fingerprint version "
        f"{run['fingerprint_version']}: {summary['rules_run']} rules executed, "
        f"{summary['passed']} passed, {summary['failed']} failed, "
        f"{summary['records_affected']} record(s) affected"
        + (f" ({mix})." if mix else "."))
    key_risks = [
        f"{f['failure_mode']} via {f['rule_id']}: {f['records_affected']} "
        f"record(s), severity {f['severity']}"
        for f in findings[:5]
    ]
    if summary["failed"] == 0:
        recommendation = ("All executed rules passed; proceed to "
                          "reconciliation sign-off.")
    else:
        recommendation = (
            f"Remediate the {summary['failed']} failing rule(s) — prioritize "
            f"the highest-severity findings — and re-run before sign-off.")
    return {
        "executive_narrative": narrative,
        "key_risks": key_risks,
        "recommendation": recommendation,
        "confidence": 0.90,
    }


def _classify_finding(payload: dict) -> dict:
    finding = payload["finding"]
    severity = finding["severity"]
    records = finding["records_affected"]
    if severity == "CRITICAL" or records >= 10:
        priority = "P1"
    elif severity == "HIGH":
        priority = "P2"
    else:
        priority = "P3"
    domain_owner = {
        "LOANS": "conversion_analyst", "VESTING": "conversion_analyst",
        "BALANCE": "record_keeper_admin", "CONTRIBUTION": "record_keeper_admin",
    }
    fm_category = (payload.get("failure_mode") or {}).get("category", "")
    owner = domain_owner.get(fm_category, "conversion_analyst")
    return {
        "suggested_priority": priority,
        "suggested_owner_role": owner,
        "rationale": (f"severity {severity} with {records} affected "
                      f"record(s); category {fm_category or 'unknown'}"),
        "confidence": 0.65,  # deliberately below the default threshold
    }


def _suggest_failure_mode(payload: dict) -> dict:
    findings = payload["findings"]
    first = findings[0]
    rule_ids = sorted({f["rule_id"] for f in findings})
    category = (payload.get("category") or "PLAN").upper()
    return {
        "name": f"Recurring {first['severity'].lower()}-severity cluster "
                f"on {first['rule_id']}",
        "category": category,
        "description": (
            f"{len(findings)} confirmed finding(s) across rule(s) "
            f"{', '.join(rule_ids)} for pair {payload.get('pair_id', '?')} "
            f"share a signature not yet catalogued as its own failure mode."),
        "data_domains": payload.get("data_domains") or ["PLAN"],
        "impact": 0.7,
        "probability": 0.30,  # learned-mode default (spec §14.4)
        "remediation": "Investigate the shared root cause across the "
                       "confirmed cluster; codify the fix as remediation.",
        "candidate_rule_note": (
            f"Start from {rule_ids[0]}'s params and narrow to the shared "
            f"signature."),
        "confidence": 0.75,
    }


def _suggest_field_mappings(payload: dict) -> dict:
    targets = payload["target_fields"]
    mappings = []
    for source in payload["source_fields"]:
        best, score = None, 0.0
        for target in targets:
            ratio = SequenceMatcher(None, source.lower(), target.lower()).ratio()
            if ratio > score:
                best, score = target, ratio
        if best is not None and score >= 0.6:
            mappings.append({
                "source_field": source, "target_field": best,
                "transform_note": "direct copy" if score > 0.95
                else "verify format/semantics",
                "confidence": round(score, 2),
            })
    return {"mappings": mappings, "confidence": 0.80}


FUNCTIONS = {
    "explain_reconciliation_variance": _explain_variance,
    "generate_conversion_summary": _conversion_summary,
    "classify_finding": _classify_finding,
    "suggest_failure_mode": _suggest_failure_mode,
    "suggest_field_mappings": _suggest_field_mappings,
}


class StubProvider:
    name = "stub"

    def run(self, function: str, payload: dict, prompt: str) -> dict:
        try:
            implementation = FUNCTIONS[function]
        except KeyError:
            raise ValueError(f"stub provider has no function {function!r}")
        return implementation(payload)
