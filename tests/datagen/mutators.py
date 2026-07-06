"""Seeded-defect mutators (spec §25.3–25.4): one named mutator per seed
failure mode, applied to the TARGET side of PLN-SEED-01, so the seeding
manifest is code. Each mutator states the defect and the phase in which its
detection rule(s) execute (1 = field_compare/count_balance/referential
today; 2 = derived_recompute/encoding_check/sort_order_check from MS-2.1,
EBCDIC decode from MS-2.2).

One data defect may legitimately fire several rules (spec: FM-007 backstops
FM-012/FM-013); the REQ-032 test asserts the exact rule-level manifest in
tests/test_sample_data.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

Truth = dict[str, list[dict[str, str]]]


def _row(truth: Truth, dataset: str, **match: str) -> dict[str, str]:
    for row in truth[dataset]:
        if all(row.get(k) == v for k, v in match.items()):
            return row
    raise LookupError(f"no {dataset} row matching {match}")


@dataclass(frozen=True)
class SeededDefect:
    fm_id: str
    phase: int
    description: str
    mutate: Callable[[Truth], None]


def _fm001(t: Truth) -> None:  # loan balance short by 33.62
    _row(t, "loans", loan_id="L2")["outstanding_balance"] = "10398.55"


def _fm002(t: Truth) -> None:  # vested 60% vs recomputed 80% (phase 2 rule)
    _row(t, "vesting", participant_id="P0017")["vested_pct"] = "0.6000"


def _fm003(t: Truth) -> None:  # svc_points with no mapping provenance
    for row in t["participants"]:
        row["svc_points"] = "142" if row["participant_id"] == "P0042" else ""


def _fm004(t: Truth) -> None:  # safe harbor dropped; catch-up inverted
    plan = t["plans"][0]
    plan["safe_harbor_flag"] = ""
    plan["catch_up_eligible"] = "N"


def _fm005(t: Truth) -> None:  # mojibake name (phase 2 rule)
    row = _row(t, "participants", participant_id="P0044")
    row["first_name"] = "JosÃ©"
    row["last_name"] = "RamÃ­rez"


def _fm006(t: Truth) -> None:  # packed-decimal decode faults: EBCDIC variant
    pass  # seeded in the fixed-width/EBCDIC emission (MS-2.2), not the CSVs


def _fm007(t: Truth) -> None:  # plan-level PRETAX total off by one penny
    _row(t, "balances", participant_id="P0007",
         money_type_code="PRETAX")["balance"] = "1500.01"


def _fm008(t: Truth) -> None:  # century window; zero date -> 0001-01-01
    _row(t, "participants", participant_id="P0008")["dob"] = "1897-03-12"
    _row(t, "participants", participant_id="P0009")["term_date"] = "0001-01-01"


def _fm009(t: Truth) -> None:  # TERMINATED counted ACTIVE
    _row(t, "participants", participant_id="P0010")["status"] = "ACTIVE"


def _fm010(t: Truth) -> None:  # blank SSN
    _row(t, "participants", participant_id="P0030")["ssn"] = ""


def _fm011(t: Truth) -> None:  # duplicate SSN across two participants
    donor = _row(t, "participants", participant_id="P0100")
    _row(t, "participants", participant_id="P0101")["ssn"] = donor["ssn"]


def _fm012(t: Truth) -> None:  # ROTH -250 offset by PRETAX +250 (plan total holds)
    _row(t, "balances", participant_id="P0012",
         money_type_code="ROTH")["balance"] = "550.00"
    _row(t, "balances", participant_id="P0012",
         money_type_code="PRETAX")["balance"] = "1150.00"


def _fm013(t: Truth) -> None:  # fund F03 subtotal variance (wrong price date)
    _row(t, "balances", participant_id="P0013",
         money_type_code="MATCH")["balance"] = "2075.25"


def _fm014(t: Truth) -> None:  # loan count off by one; maturity date missing
    _row(t, "loans", loan_id="L3")["maturity_date"] = ""
    t["loans"] = [r for r in t["loans"] if r["loan_id"] != "L6"]


def _fm015(t: Truth) -> None:  # employer match total variance, last cycle
    _row(t, "contributions", participant_id="P0002",
         money_type_code="MATCH", period="2026-06")["amount"] = "200.00"


def _fm016(t: Truth) -> None:  # 41-char address; '#' in a name (char: phase 2)
    address = "4100 Extremely Long Boulevard West Apt 41"
    assert len(address) == 41
    _row(t, "participants", participant_id="P0060")["address_1"] = address
    _row(t, "participants", participant_id="P0061")["first_name"] = "Ha#nk"


def _fm017(t: Truth) -> None:  # termination precedes hire (hire 2021-03-15)
    _row(t, "participants", participant_id="P0020")["term_date"] = "2019-05-01"


def _fm018(t: Truth) -> None:  # negative MATCH balance, no offsetting context
    _row(t, "balances", participant_id="P0018",
         money_type_code="MATCH")["balance"] = "-412.06"


SEEDED_DEFECTS: list[SeededDefect] = [
    SeededDefect("FM-001", 1, "Loan L2 target balance short by 33.62", _fm001),
    SeededDefect("FM-002", 2, "P0017 vested 60% vs recomputed 80%", _fm002),
    SeededDefect("FM-003", 1, "svc_points populated with no mapping provenance (P0042)", _fm003),
    SeededDefect("FM-004", 1, "Safe-harbor flag dropped; catch-up eligibility inverted", _fm004),
    SeededDefect("FM-005", 2, "Mojibake name for P0044; collation divergence", _fm005),
    SeededDefect("FM-006", 2, "Packed decode x100 + sign flip (EBCDIC variant, MS-2.2)", _fm006),
    SeededDefect("FM-007", 1, "Plan-level PRETAX total off by 0.01 (P0007)", _fm007),
    SeededDefect("FM-008", 1, "DOB century-window 1897; zero date as 0001-01-01", _fm008),
    SeededDefect("FM-009", 1, "TERMINATED P0010 counted ACTIVE in target", _fm009),
    SeededDefect("FM-010", 1, "Blank SSN for P0030", _fm010),
    SeededDefect("FM-011", 1, "P0101 duplicates P0100's SSN", _fm011),
    SeededDefect("FM-012", 1, "ROTH -250.00 offset by PRETAX +250.00 (P0012)", _fm012),
    SeededDefect("FM-013", 1, "Fund F03 subtotal +75.25 (P0013 MATCH)", _fm013),
    SeededDefect("FM-014", 1, "Loan L6 dropped; L3 missing maturity date", _fm014),
    SeededDefect("FM-015", 1, "Employer MATCH +50.00 in last payroll cycle (P0002)", _fm015),
    SeededDefect("FM-016", 1, "41-char address (P0060); '#' in name (P0061, phase 2)", _fm016),
    SeededDefect("FM-017", 1, "P0020 termination 2019-05-01 precedes hire 2021-03-15", _fm017),
    SeededDefect("FM-018", 1, "Negative MATCH balance -412.06 (P0018)", _fm018),
]


def apply_mutations(truth: Truth) -> None:
    """Apply every seeded defect to a (target-side) truth, in FM order."""
    for defect in SEEDED_DEFECTS:
        defect.mutate(truth)
