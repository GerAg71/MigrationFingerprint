"""Canonical truth for one synthetic plan (spec §25.2).

Shape per spec: 120 participants, 3 money types (PRETAX, ROTH, MATCH),
5 investments (F01–F05), 6 loans, graded 6-year vesting. All cell values are
strings, CSV-ready. Deterministic: fixed RNG seed, fixed generation order.

Anchor cells: specific rows are pinned to constants so the seeded-defect
mutators (mutators.py) and the REQ-032 expected manifest reference exact
values instead of RNG output. Anchors exist identically in the clean pair —
they are ordinary data there.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

from src.rules.derived_recompute import simulate_level_payments, vested_pct

SEED = 20260705

FIRST_NAMES = [
    "Alice", "Bob", "Carla", "Dev", "Elena", "Frank", "Grace", "Hank",
    "Ivy", "Jamal", "Kira", "Liam", "Mona", "Nate", "Olga", "Pete",
    "Quinn", "Rosa", "Sam", "Tara", "Umar", "Vera", "Walt", "Xena",
    "Yuri", "Zoe", "Ana", "Ben", "Cleo", "Drew",
]
LAST_NAMES = [
    "Adams", "Brown", "Chen", "Diaz", "Evans", "Ford", "Gupta", "Hayes",
    "Ito", "Jones", "Klein", "Lopez", "Meyer", "Novak", "Ortiz", "Park",
    "Quist", "Reed", "Silva", "Tran", "Usher", "Voss", "Wong", "Xu",
    "Young", "Zink", "Abbot", "Blake", "Cole", "Dunn",
]
STREETS = ["Elm", "Oak", "Maple", "Cedar", "Birch", "Walnut", "Pine", "Ash"]

MONEY_TYPES = ("PRETAX", "ROTH", "MATCH")
INVESTMENTS = ("F01", "F02", "F03", "F04", "F05")

# (participant number, money_type, investment, amount) — pinned for mutators
BALANCE_ANCHORS = [
    (7, "PRETAX", "F01", "1500.00"),   # FM-007 penny target
    (12, "PRETAX", "F01", "900.00"),   # FM-012 offset (+250)
    (12, "ROTH", "F02", "800.00"),     # FM-012 variance (-250)
    (13, "MATCH", "F03", "2000.00"),   # FM-013 fund-F03 variance
    (18, "MATCH", "F04", "1200.00"),   # FM-018 negative balance
]

# Loan truth is amortization-consistent: outstanding balances and the
# loan_payments history are produced by the same amortizer the FM-001
# recompute rule uses (interest-first), so the clean pair recomputes clean.
LOANS = [
    # participant, loan, orig date, orig amt, rate, months, payment, maturity, payments made
    (3, "L1", "2023-02-15", "8000.00", "0.0450", "48", "182.50", "2027-02-15", 24),
    (21, "L2", "2024-01-15", "12000.00", "0.0525", "60", "228.00", "2029-01-15", 18),
    (33, "L3", "2022-07-01", "5000.00", "0.0400", "36", "147.60", "2025-07-01", 30),
    (47, "L4", "2025-03-10", "15000.00", "0.0575", "60", "288.10", "2030-03-10", 12),
    (71, "L5", "2023-11-20", "6500.00", "0.0500", "48", "149.70", "2027-11-20", 20),
    (99, "L6", "2024-06-05", "7000.00", "0.0475", "48", "160.55", "2028-06-05", 15),
]


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    return date(start.year + month_index // 12, month_index % 12 + 1, start.day)

PERIODS = ("2026-05", "2026-06")  # 2026-06 is the last payroll cycle


def _pid(i: int) -> str:
    return f"P{i:04d}"


def _status(i: int) -> str:
    if i % 25 == 0:
        return "RETIRED"
    if i % 10 == 0:
        return "TERMINATED"
    return "ACTIVE"


def _vested_pct(service_years: float) -> str:
    """GRADED6 per the rule engine's own schedule (src/rules/
    derived_recompute.py), so the clean pair recomputes clean."""
    return f"{vested_pct('GRADED6', Decimal(str(service_years))):.4f}"


def _amount(rng: random.Random) -> str:
    return f"{rng.randint(50, 5000)}.{rng.randint(0, 99):02d}"


def build_truth(plan_id: str, participants_n: int = 120) -> dict[str, list[dict[str, str]]]:
    """Canonical truth for one plan. participants_n defaults to the shipped
    120 (spec §25.2); the REQ-015 perf smoke generates 200. Anchored rows all
    sit at participant numbers <= 120, so anchors hold for any n >= 120."""
    if participants_n < 120:
        raise ValueError("participants_n must be >= 120 to keep anchor rows valid")
    rng = random.Random(SEED)

    plans = [{
        "plan_id": plan_id, "plan_name": "Maptiva Demo 401k",
        "plan_type": "401K", "status": "ACTIVE",
        "safe_harbor_flag": "Y", "catch_up_eligible": "Y",
        "auto_enroll_flag": "Y", "auto_enroll_rate": "0.0300",
        "auto_increase_rate": "0.0100",
    }]

    participants = []
    for i in range(1, participants_n + 1):
        status = _status(i)
        dob = date(1958 + i % 40, i % 12 + 1, i % 28 + 1)
        hire = date(2000 + i % 20, (i * 3) % 12 + 1, (i * 7) % 28 + 1)
        term = hire + timedelta(days=900 + i * 10) if status != "ACTIVE" else None
        participants.append({
            "plan_id": plan_id, "participant_id": _pid(i),
            "ssn": f"9004{40000 + i:05d}",
            "first_name": FIRST_NAMES[(i - 1) % len(FIRST_NAMES)],
            "last_name": LAST_NAMES[(i * 7) % len(LAST_NAMES)],
            "address_1": f"{100 + i} {STREETS[i % len(STREETS)]} St",
            "address_2": "", "city": "Springfield", "state": "IL",
            "zip": "62704",
            "dob": dob.isoformat(), "hire_date": hire.isoformat(),
            "term_date": term.isoformat() if term else "",
            "status": status,
        })
    by_pid = {row["participant_id"]: row for row in participants}
    # anchors: FM-008 century window (P0008), FM-017 term-before-hire
    # (P0020, spec sample: hire 2021-03-15), FM-005 mojibake source (P0044)
    by_pid["P0008"]["dob"] = "1997-03-12"
    by_pid["P0020"]["hire_date"] = "2021-03-15"
    by_pid["P0020"]["term_date"] = "2023-08-01"
    by_pid["P0044"]["first_name"] = "Jose"
    by_pid["P0044"]["last_name"] = "Ramirez"
    # the participants extract is ordering-sensitive (RULE-SORT-001): emitted
    # sorted by (last_name, first_name), stable on participant number
    participants.sort(key=lambda r: (r["last_name"], r["first_name"]))

    balances = []
    for i in range(1, participants_n + 1):
        cells = [("PRETAX", INVESTMENTS[(i - 1) % 5]),
                 ("MATCH", INVESTMENTS[(i + 1) % 5])]
        if i % 3 == 0:
            cells.append(("ROTH", INVESTMENTS[(i + 3) % 5]))
        for money_type, investment in cells:
            balances.append({
                "plan_id": plan_id, "participant_id": _pid(i),
                "money_type_code": money_type, "investment_code": investment,
                "balance": _amount(rng),
                "units": f"{rng.randint(10, 5000) / 10:.1f}",
                "as_of_date": "2026-06-30",
            })
    for pnum, money_type, investment, amount in BALANCE_ANCHORS:
        row = next(r for r in balances
                   if r["participant_id"] == _pid(pnum)
                   and r["money_type_code"] == money_type)
        row["investment_code"] = investment
        row["balance"] = amount

    contributions = []
    for i in range(1, participants_n + 1):
        if _status(i) != "ACTIVE":
            continue
        for period in PERIODS:
            for money_type in ("PRETAX", "MATCH"):
                contributions.append({
                    "plan_id": plan_id, "participant_id": _pid(i),
                    "money_type_code": money_type, "period": period,
                    "amount": _amount(rng),
                    "payroll_date": f"{period}-15",
                })
    anchor = next(r for r in contributions
                  if r["participant_id"] == "P0002"
                  and r["money_type_code"] == "MATCH" and r["period"] == "2026-06")
    anchor["amount"] = "150.00"  # FM-015 target

    loans = []
    loan_payments = []
    for pnum, loan_id, orig_date, orig_amt, rate, months, payment, maturity, \
            payments_made in LOANS:
        schedule, balance = simulate_level_payments(
            Decimal(orig_amt), Decimal(rate), Decimal(payment), payments_made)
        origination = date.fromisoformat(orig_date)
        for k, (principal, interest) in enumerate(schedule, start=1):
            loan_payments.append({
                "plan_id": plan_id, "participant_id": _pid(pnum),
                "loan_id": loan_id,
                "payment_date": _add_months(origination, k).isoformat(),
                "principal": f"{principal:.2f}", "interest": f"{interest:.2f}",
            })
        loans.append({
            "plan_id": plan_id, "participant_id": _pid(pnum), "loan_id": loan_id,
            "origination_date": orig_date, "origination_amount": orig_amt,
            "rate": rate, "term_months": months, "payment_amount": payment,
            "payment_frequency": "MONTHLY", "maturity_date": maturity,
            "outstanding_balance": f"{balance:.2f}", "status": "ACTIVE",
        })

    vesting = []
    for i in range(1, participants_n + 1):
        service = 5.5 if i == 17 else ((i * 5) % 9) + 0.5  # P0017: 80% vested
        vesting.append({
            "plan_id": plan_id, "participant_id": _pid(i),
            "schedule_id": "GRADED6", "service_years": f"{service:.1f}",
            "vested_pct": _vested_pct(service),
        })

    return {
        "plans": plans, "participants": participants, "balances": balances,
        "contributions": contributions, "loans": loans,
        "loan_payments": loan_payments, "vesting": vesting,
    }
