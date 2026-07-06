"""Reconciliation aggregates (MS-2.3; spec §13.2, REQ-026).

Computed from the registered canonical datasets at run time and persisted as
reconciliation.json, so the client-facing reports re-render from artifacts
without re-ingesting. Pure and deterministic: Decimal sums, sorted keys,
no clock (REQ-009). All amounts serialize as strings (REQ-017).

The data-quality sections derive from the findings themselves: each sample
record's "_check" tag names the violation class, so the report stays
data-driven rather than hardcoding rule ids.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from src.fingerprint.models import Finding

# money types treated as employer-funded for the contribution split
# (spec §13.2 "by source (employee vs employer)")
EMPLOYER_MONEY_TYPES = {"MATCH", "SAFE_HARBOR", "QNEC", "QMAC", "PROFIT_SHARING"}


def _rows(datasets, side: str, name: str) -> list[dict]:
    frame = getattr(datasets, side).get(name)
    return frame.to_dict("records") if frame is not None else []


def _is_null(value) -> bool:
    return value is None or (isinstance(value, float) and value != value)


def _text(value) -> str:
    return "" if _is_null(value) else str(value)


def _pair() -> dict:
    return {"source": Decimal("0"), "target": Decimal("0")}


def _count_pair() -> dict:
    return {"source": 0, "target": 0}


def _stringify(node):
    if isinstance(node, Decimal):
        return str(node)
    if isinstance(node, dict):
        return {k: _stringify(v) for k, v in sorted(node.items())}
    if isinstance(node, list):
        return [_stringify(v) for v in node]
    return node


def _plan_ids(datasets) -> list[str]:
    ids = set()
    for side in ("source", "target"):
        for name in ("plans", "participants", "balances", "loans", "contributions"):
            for row in _rows(datasets, side, name):
                if not _is_null(row.get("plan_id")):
                    ids.add(str(row["plan_id"]))
    return sorted(ids)


def _last_cycle(datasets) -> str | None:
    periods = [
        _text(row.get("period"))
        for side in ("source", "target")
        for row in _rows(datasets, side, "contributions")
        if not _is_null(row.get("period"))
    ]
    return max(periods) if periods else None


def compute_reconciliation(datasets) -> dict:
    """The §13.2 aggregate payload: per-plan counts and totals on both sides
    for participants (by status), balances (total, by money type, by
    investment), loans (counts, outstanding, missing repayment terms), and
    last-cycle contributions (by money type, employer/employee split)."""
    plans = _plan_ids(datasets)
    last_cycle = _last_cycle(datasets)
    payload: dict = {"plans": {}, "last_payroll_cycle": last_cycle}

    source_plan_ids = {_text(r.get("plan_id")) for r in _rows(datasets, "source", "plans")}
    target_plan_ids = {_text(r.get("plan_id")) for r in _rows(datasets, "target", "plans")}
    payload["plan_presence"] = {
        "source_count": len(source_plan_ids),
        "target_count": len(target_plan_ids),
        "missing_in_target": sorted(source_plan_ids - target_plan_ids),
        "unexpected_in_target": sorted(target_plan_ids - source_plan_ids),
    }

    for plan_id in plans:
        plan: dict = {
            "participants_by_status": {},
            "participant_count": _count_pair(),
            "balance_total": _pair(),
            "balances_by_money_type": {},
            "balances_by_investment": {},
            "participant_balance_mismatches": [],
            "loan_count": _count_pair(),
            "loan_outstanding": _pair(),
            "loans_missing_terms_target": 0,
            "contributions_last_cycle": {},
            "contribution_split": {"employee": _pair(), "employer": _pair()},
        }

        for side in ("source", "target"):
            for row in _rows(datasets, side, "participants"):
                if _text(row.get("plan_id")) != plan_id:
                    continue
                plan["participant_count"][side] += 1
                status = _text(row.get("status")) or "(none)"
                plan["participants_by_status"].setdefault(status, _count_pair())
                plan["participants_by_status"][status][side] += 1

            per_participant: dict[str, Decimal] = {}
            for row in _rows(datasets, side, "balances"):
                if _text(row.get("plan_id")) != plan_id:
                    continue
                amount = row.get("balance")
                if _is_null(amount):
                    continue
                plan["balance_total"][side] += amount
                money_type = _text(row.get("money_type_code")) or "(none)"
                plan["balances_by_money_type"].setdefault(money_type, _pair())
                plan["balances_by_money_type"][money_type][side] += amount
                investment = _text(row.get("investment_code")) or "(none)"
                plan["balances_by_investment"].setdefault(investment, _pair())
                plan["balances_by_investment"][investment][side] += amount
                pid = _text(row.get("participant_id"))
                per_participant[pid] = per_participant.get(pid, Decimal("0")) + amount
            plan[f"_per_participant_{side}"] = per_participant

            for row in _rows(datasets, side, "loans"):
                if _text(row.get("plan_id")) != plan_id:
                    continue
                plan["loan_count"][side] += 1
                if not _is_null(row.get("outstanding_balance")):
                    plan["loan_outstanding"][side] += row["outstanding_balance"]
                if side == "target" and any(
                    _is_null(row.get(f))
                    for f in ("maturity_date", "payment_amount", "payment_frequency")
                ):
                    plan["loans_missing_terms_target"] += 1

            for row in _rows(datasets, side, "contributions"):
                if _text(row.get("plan_id")) != plan_id:
                    continue
                if last_cycle is not None and _text(row.get("period")) != last_cycle:
                    continue
                amount = row.get("amount")
                if _is_null(amount):
                    continue
                money_type = _text(row.get("money_type_code")) or "(none)"
                plan["contributions_last_cycle"].setdefault(money_type, _pair())
                plan["contributions_last_cycle"][money_type][side] += amount
                bucket = ("employer" if money_type in EMPLOYER_MONEY_TYPES
                          else "employee")
                plan["contribution_split"][bucket][side] += amount

        source_pp = plan.pop("_per_participant_source", {})
        target_pp = plan.pop("_per_participant_target", {})
        for pid in sorted(set(source_pp) | set(target_pp)):
            s = source_pp.get(pid, Decimal("0"))
            t = target_pp.get(pid, Decimal("0"))
            if s != t:
                plan["participant_balance_mismatches"].append(
                    {"participant_id": pid, "source": s, "target": t,
                     "delta": t - s}
                )

        payload["plans"][plan_id] = plan

    return _stringify(payload)


# --- data-quality sections from findings (spec §13.2 data-quality report) ------

QUALITY_SECTIONS = (
    "Field-length violations",
    "Invalid characters / encoding",
    "Invalid or future dates",
    "Negative balances",
    "Missing key fields",
)


def _classify_check(check: str) -> str | None:
    if check.startswith("max_length"):
        return "Field-length violations"
    if (check.startswith("chars_outside") or "mojibake" in check
            or check.startswith("pattern")):
        return "Invalid characters / encoding"
    if check == "not_null":
        return "Missing key fields"
    if check.startswith("gte_field") or check.startswith("max:"):
        return "Invalid or future dates"
    if check.startswith("min:"):
        bound = check.split(":", 1)[1]
        try:
            date.fromisoformat(bound)
            return "Invalid or future dates"
        except ValueError:
            pass
        try:
            Decimal(bound)
            return "Negative balances"
        except InvalidOperation:
            pass
    return None


def quality_sections(findings: list[Finding]) -> dict[str, list[dict]]:
    """Group findings' sample records into the §13.2 data-quality sections by
    their _check tags. Inline samples are capped at 25 per finding upstream;
    records_affected on each entry carries the true count."""
    sections: dict[str, list[dict]] = {name: [] for name in QUALITY_SECTIONS}
    for finding in findings:
        for record in finding.sample_records:
            check = (record.target or {}).get("_check")
            if not check:
                continue
            section = _classify_check(check)
            if section is None:
                continue
            value_items = {k: v for k, v in (record.target or {}).items()
                           if k != "_check"}
            sections[section].append({
                "finding_id": finding.finding_id,
                "failure_mode": finding.failure_mode,
                "rule_id": finding.rule_id,
                "severity": finding.severity,
                # NB: never name a template-context dict key "keys" — Jinja
                # attribute lookup would resolve the dict method instead
                "record": ", ".join(f"{k}={v}"
                                    for k, v in sorted(record.keys.items())),
                "value": ", ".join(f"{k}={v}"
                                   for k, v in sorted(value_items.items())),
                "check": check,
                "records_affected": finding.records_affected,
            })
    return sections
