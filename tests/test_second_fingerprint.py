"""MS-3.3 (spec Ch. 16.3): the Omni->TRAC placeholder fingerprint — demo
step 5: switching pairs demonstrably loads a different prioritized suite."""

import json

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.cli import main
from src.fingerprint.loader import load
from src.fingerprint.prioritize import prioritized_suite
from tests.conftest import REPO, copy_fingerprint_store

STORE = REPO / "data" / "fingerprints"
ZOS_PAIR = "omni-zos-to-omni-linux"
TRAC_PAIR = "omni-to-trac"


def test_trac_fingerprint_validates():
    fp = load(TRAC_PAIR, fingerprint_dir=STORE)
    assert fp.platform_pair.source == "OMNI"
    assert fp.platform_pair.target == "TRAC"
    assert fp.version == "1.0.0" and fp.status == "published"
    assert len(fp.failure_modes) == 16
    assert len(fp.detection_rules) == 19
    # the mainframe-transition modes belong to the z/OS pair only
    mode_ids = {m.id for m in fp.failure_modes}
    assert "FM-005" not in mode_ids and "FM-006" not in mode_ids
    assert "placeholder" in fp.changelog.lower()


def test_demo_step_5_different_pair_different_suite():
    """Spec §23.5 step 5: a different fingerprint loads a different suite."""
    zos = prioritized_suite(load(ZOS_PAIR, fingerprint_dir=STORE))
    trac = prioritized_suite(load(TRAC_PAIR, fingerprint_dir=STORE))

    # different leaders: reconciliation totals lead the same-product
    # migration; cross-product vesting mapping leads Omni->TRAC
    assert zos[0].rule_id == "RULE-BAL-TOTALS-001"
    assert trac[0].rule_id == "RULE-VEST-PCT-001"
    assert str(trac[0].priority_score) == "0.68"

    # different rule sets (no encoding/packed rules in TRAC) and ordering
    zos_rules = [e.rule_id for e in zos]
    trac_rules = [e.rule_id for e in trac]
    assert "RULE-ENC-001" in zos_rules and "RULE-ENC-001" not in trac_rules
    assert "RULE-PACKED-001" in zos_rules and "RULE-PACKED-001" not in trac_rules
    assert zos_rules != trac_rules
    # loan carry-over outranks vesting on z/OS; inverted on TRAC
    assert zos_rules.index("RULE-LOAN-BAL-001") < zos_rules.index("RULE-VEST-PCT-001")
    assert trac_rules.index("RULE-VEST-PCT-001") < trac_rules.index("RULE-LOAN-BAL-001")


def test_cli_pairs_lists_both(capsys):
    rc = main(["pairs", "--fingerprint-dir", str(STORE)])
    out = capsys.readouterr().out
    assert rc == 0
    assert ZOS_PAIR in out and TRAC_PAIR in out

    rc = main(["pairs", "--fingerprint-dir", str(STORE), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    by_pair = {p["pair_id"]: p for p in payload}
    assert by_pair[ZOS_PAIR]["modes"] == 18
    assert by_pair[TRAC_PAIR] == {"pair_id": TRAC_PAIR, "version": "1.0.0",
                                  "status": "published", "modes": 16,
                                  "rules": 19}


def test_cli_suite_for_trac(capsys):
    """The demo mapping's exact command: fingerprint suite --pair omni-to-trac."""
    rc = main(["suite", "--pair", TRAC_PAIR, "--fingerprint-dir", str(STORE)])
    out = capsys.readouterr().out
    assert rc == 0
    lines = [l for l in out.splitlines() if l.strip()]
    assert "omni-to-trac v1.0.0 (19 rules)" in lines[0]
    assert "RULE-VEST-PCT-001" in lines[2]  # first suite row


def test_api_lists_both_pairs(tmp_path):
    store = copy_fingerprint_store(tmp_path)
    client = TestClient(create_app(fingerprint_dir=store,
                                   runs_dir=tmp_path / "runs"))
    payload = client.get("/platform-pairs").json()
    assert {p["pair_id"] for p in payload} == {ZOS_PAIR, TRAC_PAIR}
    suite = client.get(f"/fingerprints/{TRAC_PAIR}/suite").json()
    assert suite["suite"][0]["rule_id"] == "RULE-VEST-PCT-001"