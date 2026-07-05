"""MS-1.2 CLI: `fingerprint validate` (exit 0/3) and `fingerprint suite`
with table and --json output (CLI_SPEC.md)."""

import copy
import json
from pathlib import Path

from src.cli import main

REPO = Path(__file__).resolve().parents[1]
SEED_STORE = REPO / "data" / "fingerprints"
SEED_PAIR = "omni-zos-to-omni-linux"
SEED_FILE = SEED_STORE / SEED_PAIR / "1.0.0" / "fingerprint.json"


def seed_payload() -> dict:
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))


def corrupted_store(tmp_path: Path) -> Path:
    payload = copy.deepcopy(seed_payload())
    payload["detection_rules"][0]["type"] = "fuzzy_match"
    store = tmp_path / "fingerprints"
    d = store / SEED_PAIR / "1.0.0"
    d.mkdir(parents=True)
    (d / "fingerprint.json").write_text(json.dumps(payload), encoding="utf-8")
    return store


# --- validate -------------------------------------------------------------


def test_validate_seed_ok(capsys):
    rc = main(["validate", str(SEED_FILE)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK omni-zos-to-omni-linux 1.0.0" in out
    assert "18 modes, 23 rules" in out


def test_validate_json_output(capsys):
    rc = main(["validate", str(SEED_FILE), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload == {
        "ok": True, "pair": SEED_PAIR, "version": "1.0.0",
        "status": "published", "modes": 18, "rules": 23,
    }


def test_validate_corrupted_exits_3_with_pathed_errors(tmp_path, capsys):
    bad = corrupted_store(tmp_path) / SEED_PAIR / "1.0.0" / "fingerprint.json"
    rc = main(["validate", str(bad)])
    err = capsys.readouterr().err
    assert rc == 3
    assert "INVALID" in err
    assert "detection_rules.0" in err  # pathed (REQ-010)


def test_validate_missing_file_exits_1(capsys):
    rc = main(["validate", "no/such/file.json"])
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_validate_malformed_json_exits_3(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    rc = main(["validate", str(bad)])
    assert rc == 3
    assert "not valid JSON" in capsys.readouterr().err


# --- suite ----------------------------------------------------------------


def test_suite_table_output(capsys):
    rc = main(["suite", "--pair", SEED_PAIR, "--fingerprint-dir", str(SEED_STORE)])
    out = capsys.readouterr().out
    assert rc == 0
    lines = [l for l in out.splitlines() if l.strip()]
    assert "omni-zos-to-omni-linux v1.0.0" in lines[0]
    assert "(23 rules)" in lines[0]
    first_row = lines[2]
    assert "RULE-BAL-TOTALS-001" in first_row
    assert "FM-007" in first_row
    assert "0.7125" in first_row
    assert "CRITICAL" in first_row


def test_suite_json_output(capsys):
    rc = main(["suite", "--pair", SEED_PAIR, "--version", "1.0.0",
               "--fingerprint-dir", str(SEED_STORE), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["pair"] == SEED_PAIR
    assert payload["version"] == "1.0.0"
    suite = payload["suite"]
    assert len(suite) == 23
    assert suite[0]["rule_id"] == "RULE-BAL-TOTALS-001"
    assert suite[0]["priority_score"] == "0.7125"  # Decimal serialized as string
    assert suite[0]["order"] == 1
    assert all(e["status"] == "pending" for e in suite)
    assert [e["order"] for e in suite] == list(range(1, 24))


def test_suite_unknown_pair_exits_1(capsys):
    rc = main(["suite", "--pair", "no-such-pair",
               "--fingerprint-dir", str(SEED_STORE)])
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_suite_corrupted_store_exits_3(tmp_path, capsys):
    rc = main(["suite", "--pair", SEED_PAIR,
               "--fingerprint-dir", str(corrupted_store(tmp_path))])
    err = capsys.readouterr().err
    assert rc == 3
    assert "detection_rules.0" in err
