"""LayoutSpec for the EBCDIC emission of the loans dataset (spec §25.4).

Covers every canonical loans column: char identity/status fields, packed
COMP-3 amounts (implied 2 decimals), zoned rate (4 decimals) and term, and
YYYYMMDD char dates with zero-is-null semantics. Shipped alongside the
sample data as data/samples/layouts/loans.json for `fingerprint run
--layout-dir`.
"""

from src.fingerprint.models import LayoutSpec

LOANS_LAYOUT = LayoutSpec.model_validate({
    "layout_id": "omni-loans-full-v1",
    "record_length": 88,
    "encoding": "cp037",
    "fields": [
        {"name": "plan_id", "start": 1, "length": 12, "type": "char"},
        {"name": "participant_id", "start": 13, "length": 12, "type": "char"},
        {"name": "loan_id", "start": 25, "length": 4, "type": "char"},
        {"name": "origination_date", "start": 29, "length": 8, "type": "char",
         "date_format": "YYYYMMDD", "zero_is_null": True},
        {"name": "origination_amount", "start": 37, "length": 6,
         "type": "packed", "decimals": 2},
        {"name": "rate", "start": 43, "length": 6, "type": "zoned", "decimals": 4},
        {"name": "term_months", "start": 49, "length": 3, "type": "zoned",
         "decimals": 0},
        {"name": "payment_amount", "start": 52, "length": 5, "type": "packed",
         "decimals": 2},
        {"name": "payment_frequency", "start": 57, "length": 8, "type": "char"},
        {"name": "maturity_date", "start": 65, "length": 8, "type": "char",
         "date_format": "YYYYMMDD", "zero_is_null": True},
        {"name": "outstanding_balance", "start": 73, "length": 6,
         "type": "packed", "decimals": 2},
        {"name": "status", "start": 79, "length": 10, "type": "char"},
    ],
})
