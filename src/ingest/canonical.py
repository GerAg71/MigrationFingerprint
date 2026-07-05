"""Canonical dataset specifications (spec Ch. 4.2–4.3, validation-scoped).

Detection rules bind to these dataset names and columns only (REQ-008);
adapters resolve platform-specific names at ingestion. Column order is the
layout/mapping order used to resolve headerless files (spec §10.3).

Column kinds drive typing at the ingestion boundary:
  key/text -> str (blank -> None)
  money/decimal -> Decimal, never float (REQ-017)
  integer -> int
  date -> datetime.date; zero/blank -> None with annotation (spec §4.3)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ColumnKind = Literal["key", "text", "money", "decimal", "integer", "date"]


class DatasetColumn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    kind: ColumnKind


class DatasetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    columns: tuple[DatasetColumn, ...] = Field(min_length=1)

    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def kind_of(self, column: str) -> ColumnKind | None:
        for c in self.columns:
            if c.name == column:
                return c.kind
        return None


def _spec(name: str, *columns: tuple[str, ColumnKind]) -> DatasetSpec:
    return DatasetSpec(
        name=name,
        columns=tuple(DatasetColumn(name=n, kind=k) for n, k in columns),
    )


CANONICAL_DATASETS: dict[str, DatasetSpec] = {
    spec.name: spec
    for spec in (
        _spec(
            "plans",
            ("plan_id", "key"), ("plan_name", "text"), ("plan_type", "text"),
            ("status", "text"), ("safe_harbor_flag", "text"),
            ("catch_up_eligible", "text"), ("auto_enroll_flag", "text"),
            ("auto_enroll_rate", "decimal"), ("auto_increase_rate", "decimal"),
        ),
        _spec(
            "plan_investments",
            ("plan_id", "key"), ("investment_code", "key"),
            ("investment_name", "text"), ("status", "text"),
        ),
        _spec(
            "plan_sources",
            ("plan_id", "key"), ("money_type_code", "key"),
            ("money_type_name", "text"), ("employer_flag", "text"),
        ),
        _spec(
            "participants",
            ("plan_id", "key"), ("participant_id", "key"), ("ssn", "text"),
            ("first_name", "text"), ("last_name", "text"),
            ("address_1", "text"), ("address_2", "text"), ("city", "text"),
            ("state", "text"), ("zip", "text"),
            ("dob", "date"), ("hire_date", "date"), ("term_date", "date"),
            ("status", "text"),
        ),
        _spec(
            "balances",
            ("plan_id", "key"), ("participant_id", "key"),
            ("money_type_code", "key"), ("investment_code", "key"),
            ("balance", "money"), ("units", "decimal"), ("as_of_date", "date"),
        ),
        _spec(
            "contributions",
            ("plan_id", "key"), ("participant_id", "key"),
            ("money_type_code", "key"), ("period", "text"),
            ("amount", "money"), ("payroll_date", "date"),
        ),
        _spec(
            "loans",
            ("plan_id", "key"), ("participant_id", "key"), ("loan_id", "key"),
            ("origination_date", "date"), ("origination_amount", "money"),
            ("rate", "decimal"), ("term_months", "integer"),
            ("payment_amount", "money"), ("payment_frequency", "text"),
            ("maturity_date", "date"), ("outstanding_balance", "money"),
            ("status", "text"),
        ),
        _spec(
            "loan_payments",
            ("plan_id", "key"), ("participant_id", "key"), ("loan_id", "key"),
            ("payment_date", "date"), ("principal", "money"),
            ("interest", "money"),
        ),
        _spec(
            "vesting",
            ("plan_id", "key"), ("participant_id", "key"),
            ("schedule_id", "text"), ("service_years", "decimal"),
            ("vested_pct", "decimal"),
        ),
        _spec(
            "transactions",
            ("plan_id", "key"), ("participant_id", "key"),
            ("transaction_id", "key"), ("trade_date", "date"),
            ("type_code", "text"), ("amount", "money"),
            ("investment_code", "text"),
        ),
        _spec(
            "prices",
            ("investment_code", "key"), ("price_date", "date"),
            ("price", "money"),
        ),
    )
}
