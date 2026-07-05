"""MS-1.2: prioritized_suite ordering per spec §12.2 (REQ-001).

Note on the spec's worked example: it names FM-007 (0.7125) > FM-001 (0.63) >
FM-012/FM-013 (0.6175) and gives FM-018 = 0.2975, all asserted below. Its
"down to FM-018" phrasing does not make FM-018 literally last: by the normative
score algorithm FM-016 (0.25) and FM-017 (0.2475) rank below it.
"""

import copy
import json
from decimal import Decimal
from pathlib import Path

from src.fingerprint.models import Fingerprint
from src.fingerprint.prioritize import prioritized_suite

SEED_PATH = (
    Path(__file__).resolve().parents[1]
    / "data" / "fingerprints" / "omni-zos-to-omni-linux" / "1.0.0" / "fingerprint.json"
)

# Hand-computed full expectation over the 23 seed rules: score desc,
# ties by severity rank, then FM id, then rule id.
EXPECTED_ORDER = [
    ("RULE-BAL-TOTALS-001",   "FM-007", Decimal("0.7125")),
    ("RULE-LOAN-BAL-001",     "FM-001", Decimal("0.63")),
    ("RULE-LOAN-RECOMP-001",  "FM-001", Decimal("0.63")),
    ("RULE-BAL-MT-001",       "FM-012", Decimal("0.6175")),
    ("RULE-BAL-INV-001",      "FM-013", Decimal("0.6175")),
    ("RULE-VEST-PCT-001",     "FM-002", Decimal("0.5525")),
    ("RULE-VEST-SCHED-001",   "FM-002", Decimal("0.5525")),
    ("RULE-PCOUNT-001",       "FM-009", Decimal("0.495")),
    ("RULE-PACKED-001",       "FM-006", Decimal("0.4675")),
    ("RULE-DERIVED-TRACE-001","FM-003", Decimal("0.4125")),
    ("RULE-PROV-MATRIX-001",  "FM-004", Decimal("0.40")),
    ("RULE-KEYS-001",         "FM-010", Decimal("0.40")),
    ("RULE-CONTRIB-001",      "FM-015", Decimal("0.36")),
    ("RULE-DATE-001",         "FM-008", Decimal("0.36")),
    ("RULE-DUP-001",          "FM-011", Decimal("0.34")),
    ("RULE-LOAN-CNT-001",     "FM-014", Decimal("0.3375")),
    ("RULE-LOAN-TERMS-001",   "FM-014", Decimal("0.3375")),
    ("RULE-ENC-001",          "FM-005", Decimal("0.33")),
    ("RULE-SORT-001",         "FM-005", Decimal("0.33")),
    ("RULE-NEG-001",          "FM-018", Decimal("0.2975")),
    ("RULE-LEN-001",          "FM-016", Decimal("0.25")),
    ("RULE-CHAR-001",         "FM-016", Decimal("0.25")),
    ("RULE-DATEVAL-001",      "FM-017", Decimal("0.2475")),
]


def seed_payload() -> dict:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def seed_fingerprint() -> Fingerprint:
    return Fingerprint.model_validate(seed_payload())


def test_worked_example_anchors():
    """Spec §12.2: FM-007 (0.7125) before FM-001 (0.63) before FM-012/FM-013
    (0.6175); FM-018 scores 0.2975."""
    suite = prioritized_suite(seed_fingerprint())
    assert suite[0].fm_id == "FM-007"
    assert suite[0].priority_score == Decimal("0.7125")
    assert suite[1].fm_id == "FM-001" and suite[2].fm_id == "FM-001"
    assert suite[1].priority_score == Decimal("0.63")
    assert (suite[3].fm_id, suite[4].fm_id) == ("FM-012", "FM-013")
    assert suite[3].priority_score == Decimal("0.6175")
    neg = next(e for e in suite if e.fm_id == "FM-018")
    assert neg.priority_score == Decimal("0.2975")


def test_full_ordering_matches_hand_computation():
    suite = prioritized_suite(seed_fingerprint())
    assert [(e.rule_id, e.fm_id, e.priority_score) for e in suite] == EXPECTED_ORDER
    assert [e.order for e in suite] == list(range(1, 24))


def test_tie_break_by_severity_before_fm_id():
    """FM-015 (HIGH) and FM-008 (MEDIUM) tie at 0.36; severity wins even
    though FM-008 sorts first by id."""
    suite = prioritized_suite(seed_fingerprint())
    positions = {e.rule_id: e.order for e in suite}
    assert positions["RULE-CONTRIB-001"] < positions["RULE-DATE-001"]


def test_tie_break_by_fm_id_when_severity_equal():
    """FM-004 and FM-010 tie at 0.40, both HIGH -> FM id ascending."""
    suite = prioritized_suite(seed_fingerprint())
    positions = {e.rule_id: e.order for e in suite}
    assert positions["RULE-PROV-MATRIX-001"] < positions["RULE-KEYS-001"]
    # sibling rules of one mode: rule id ascending
    assert positions["RULE-LOAN-BAL-001"] < positions["RULE-LOAN-RECOMP-001"]


def test_disabled_rule_kept_in_position_marked_skipped():
    payload = seed_payload()
    top = next(r for r in payload["detection_rules"]
               if r["rule_id"] == "RULE-BAL-TOTALS-001")
    top["enabled"] = False
    suite = prioritized_suite(Fingerprint.model_validate(payload))
    assert suite[0].rule_id == "RULE-BAL-TOTALS-001"
    assert suite[0].status == "skipped:disabled"
    assert all(e.status == "pending" for e in suite[1:])


def test_deterministic_under_input_reordering():
    """Same fingerprint content in any list order -> identical suite."""
    payload = seed_payload()
    shuffled = copy.deepcopy(payload)
    shuffled["failure_modes"] = list(reversed(shuffled["failure_modes"]))
    shuffled["detection_rules"] = list(reversed(shuffled["detection_rules"]))
    a = prioritized_suite(Fingerprint.model_validate(payload))
    b = prioritized_suite(Fingerprint.model_validate(shuffled))
    assert a == b


def test_scores_are_exact_decimals_not_floats():
    suite = prioritized_suite(seed_fingerprint())
    for entry in suite:
        assert isinstance(entry.priority_score, Decimal)
    # 0.65 x 0.95 must be exactly 0.6175, not 0.61750000000000000000000001
    bal_mt = next(e for e in suite if e.rule_id == "RULE-BAL-MT-001")
    assert str(bal_mt.priority_score) == "0.6175"
