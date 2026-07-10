"""Synthetic Omni->Omni restore sample pairs (REQ-031: fake SSNs, fake
names, deterministic - no clock, no randomness).

Writes two committed pairs under data/samples:

  PLN-REST-CLEAN-01  source == target: a perfect restore, every rule green.
  PLN-REST-SEED-01   target carries one planted defect per restore failure
                     mode (FM-101..FM-106) - the REQ-032 manifest in
                     tests/test_restore_use_case.py is derived from the
                     mutations below BEFORE first execution.

Run: python -m tests.datagen.restore
"""

from __future__ import annotations

import copy
import csv
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SAMPLES = REPO / "data" / "samples"

PLANS = ["PLN-R001", "PLN-R002"]
PARTICIPANTS_PER_PLAN = 60
SERVICE_CYCLE = ["0.5", "2.0", "3.5", "4.5", "6.0", "9.0", "1.0", "7.5"]
STATES = ["IL", "CA", "TX", "NY"]
FIRST = ["Alice", "Bob", "Carol", "David", "Elena", "Frank", "Grace", "Hugo"]
LAST = ["Ng", "Rivera", "Okafor", "Smith", "Chen", "Dubois", "Kim", "Patel"]


def graded6(years: Decimal) -> Decimal:
    """The stock GRADED6 schedule (mirrors the engine's recomputer)."""
    if years < 2:
        return Decimal("0")
    return min((int(years) - 1) * Decimal("0.2"), Decimal("1"))


def build() -> dict[str, list[dict]]:
    """One internally consistent book of business across two plans."""
    data: dict[str, list[dict]] = {
        "plans": [], "participants": [], "balances": [], "contributions": [],
        "loans": [], "loan_payments": [], "vesting": [],
        "udf_definitions": [], "udf_values": [],
    }
    for plan_no, plan_id in enumerate(PLANS, start=1):
        data["plans"].append({
            "plan_id": plan_id, "plan_name": f"Restore Sample {plan_no} 401k",
            "plan_type": "401K", "status": "ACTIVE", "safe_harbor_flag": "Y",
            "catch_up_eligible": "Y", "auto_enroll_flag": "N",
            "auto_enroll_rate": "", "auto_increase_rate": "",
        })
        for kind, name, dtype, length in (
            ("UDF-01", "union_code", "X(7)", 7),
            ("UDF-02", "branch_code", "X(7)", 7),
            ("UDF-03", "review_date", "9(8)", 8),
        ):
            data["udf_definitions"].append({
                "plan_id": plan_id, "udf_id": kind, "udf_name": name,
                "record_kind": "PARTICIPANT", "data_type": dtype,
                "max_length": str(length),
            })
        for i in range(1, PARTICIPANTS_PER_PLAN + 1):
            pid = f"R{plan_no}{i:03d}"
            terminated = i % 9 == 0
            data["participants"].append({
                "plan_id": plan_id, "participant_id": pid,
                "ssn": f"900{plan_no}{i:05d}",
                "first_name": FIRST[i % len(FIRST)],
                "last_name": LAST[(i + plan_no) % len(LAST)],
                "address_1": f"{100 + i} Main St", "address_2": "",
                "city": "Springfield", "state": STATES[i % len(STATES)],
                "zip": f"627{i % 100:02d}",
                "dob": f"{1958 + i % 30}-{i % 12 + 1:02d}-{i % 27 + 1:02d}",
                "hire_date": f"{2005 + i % 15}-{i % 12 + 1:02d}-15",
                "term_date": f"{2023 + i % 3}-06-30" if terminated else "",
                "status": "TERMINATED" if terminated else "ACTIVE",
                "filler_442_448": "",  # a Not-Used position, carried by design
            })
            for money, fund, base in (("PRETAX", "F01", 1000),
                                      ("MATCH", "F02", 400)):
                data["balances"].append({
                    "plan_id": plan_id, "participant_id": pid,
                    "money_type_code": money, "investment_code": fund,
                    "balance": f"{base + i * 13}.{i % 100:02d}",
                    "units": f"{(base + i * 13) // 10}.5",
                    "as_of_date": "2026-06-30",
                })
            data["contributions"].append({
                "plan_id": plan_id, "participant_id": pid,
                "money_type_code": "PRETAX", "period": "2026-06",
                "amount": f"{50 + i}.00", "payroll_date": "2026-06-15",
            })
            service = Decimal(SERVICE_CYCLE[(i - 1) % len(SERVICE_CYCLE)])
            data["vesting"].append({
                "plan_id": plan_id, "participant_id": pid,
                "schedule_id": "GRADED6", "service_years": str(service),
                "vested_pct": f"{graded6(service):.4f}",
            })
            if i % 5 == 0:
                origination = Decimal(f"{9000 + i * 7}.00")
                paid_principal = Decimal("600.00")  # 4 payments below
                data["loans"].append({
                    "plan_id": plan_id, "participant_id": pid, "loan_id": "L1",
                    "origination_date": "2025-03-15",
                    "origination_amount": str(origination),
                    "rate": "0.0525", "term_months": "60",
                    "payment_amount": "228.00", "payment_frequency": "MONTHLY",
                    "maturity_date": "2030-03-15",
                    "outstanding_balance": str(origination - paid_principal),
                    "status": "ACTIVE",
                })
                for month in range(1, 5):
                    data["loan_payments"].append({
                        "plan_id": plan_id, "participant_id": pid,
                        "loan_id": "L1",
                        "payment_date": f"2026-{2 + month:02d}-15",
                        "principal": "150.00", "interest": "39.38",
                    })
            if i % 2 == 0:
                data["udf_values"].append({
                    "plan_id": plan_id, "participant_id": pid,
                    "udf_id": "UDF-01", "value": f"LOCAL{i % 9}",
                })
            if i % 3 == 0:
                data["udf_values"].append({
                    "plan_id": plan_id, "participant_id": pid,
                    "udf_id": "UDF-02", "value": f"BR{i % 5:03d}",
                })
    return data


def seed_defects(data: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """One planted defect per restore failure mode (target side only).
    The REQ-032 manifest derives from exactly these mutations."""
    seeded = copy.deepcopy(data)

    def row(dataset, **match):
        for r in seeded[dataset]:
            if all(r[k] == v for k, v in match.items()):
                return r
        raise LookupError(f"{dataset}: {match}")

    # FM-101 custom code drift: vested_pct differs from the stock schedule
    row("vesting", plan_id="PLN-R001", participant_id="R1003")["vested_pct"] = "0.9000"
    # FM-102 UDF definition gap: UDF-03 definition lost on PLN-R001 ...
    seeded["udf_definitions"] = [
        r for r in seeded["udf_definitions"]
        if not (r["plan_id"] == "PLN-R001" and r["udf_id"] == "UDF-03")]
    # ... and three UDF-01 values dropped for the same plan
    drop_values = {("PLN-R001", "R1002"), ("PLN-R001", "R1004"),
                   ("PLN-R001", "R1006")}
    seeded["udf_values"] = [
        r for r in seeded["udf_values"]
        if not (r["udf_id"] == "UDF-01"
                and (r["plan_id"], r["participant_id"]) in drop_values)]
    # FM-103 off-label: data hiding in a Not-Used filler on two rows ...
    row("participants", participant_id="R1010")["filler_442_448"] = "BR-EAST"
    row("participants", participant_id="R1020")["filler_442_448"] = "BR-EAST"
    # ... and a letter inside a 9(9) SSN
    row("participants", participant_id="R1007")["ssn"] = "90010A007"
    # FM-104 required-field regression: dob blanked; a loan loses its
    # origination date
    row("participants", participant_id="R2005")["dob"] = ""
    row("loans", plan_id="PLN-R001", participant_id="R1015")["origination_date"] = ""
    # FM-105 truncation: one whole participant gone; two loan payments gone
    seeded["participants"] = [
        r for r in seeded["participants"] if r["participant_id"] != "R2033"]
    payments = [r for r in seeded["loan_payments"]
                if r["participant_id"] == "R1010"]
    for victim in payments[:2]:
        seeded["loan_payments"].remove(victim)
    # FM-106 value drift at tolerance zero: money on both datasets + a name
    balance_row = row("balances", plan_id="PLN-R002", participant_id="R2008",
                      money_type_code="PRETAX")
    balance_row["balance"] = str(Decimal(balance_row["balance"]) + Decimal("10.00"))
    loan_row = row("loans", plan_id="PLN-R001", participant_id="R1020")
    loan_row["outstanding_balance"] = str(
        Decimal(loan_row["outstanding_balance"]) - Decimal("25.00"))
    row("participants", participant_id="R2014")["last_name"] = "Nguyen-Restore"
    return seeded


def write_pair(base: Path, name: str, source: dict[str, list[dict]],
               target: dict[str, list[dict]]) -> None:
    for side, book in (("source", source), ("target", target)):
        directory = base / side / name
        directory.mkdir(parents=True, exist_ok=True)
        for dataset, rows in book.items():
            path = directory / f"{dataset}.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()),
                                        lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)


def write_restore_samples(base: Path) -> None:
    """Regenerate both restore pairs under base (spec §25.4 determinism)."""
    book = build()
    write_pair(base, "PLN-REST-CLEAN-01", book, book)
    write_pair(base, "PLN-REST-SEED-01", book, seed_defects(book))


def main() -> None:
    write_restore_samples(SAMPLES)
    print(f"wrote PLN-REST-CLEAN-01 and PLN-REST-SEED-01 under {SAMPLES}")


if __name__ == "__main__":
    main()
