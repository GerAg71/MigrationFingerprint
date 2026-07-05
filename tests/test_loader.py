"""MS-1.2: load() selects the highest published version and rejects invalid
or inconsistent fingerprints loudly (REQ-010)."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.fingerprint.loader import (
    FingerprintDirectoryError,
    list_versions,
    load,
    load_file,
)

REPO = Path(__file__).resolve().parents[1]
SEED_STORE = REPO / "data" / "fingerprints"
SEED_PAIR = "omni-zos-to-omni-linux"


def seed_payload() -> dict:
    path = SEED_STORE / SEED_PAIR / "1.0.0" / "fingerprint.json"
    return json.loads(path.read_text(encoding="utf-8"))


def write_version(store: Path, payload: dict) -> None:
    d = store / payload["fingerprint_id"] / payload["version"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "fingerprint.json").write_text(json.dumps(payload), encoding="utf-8")


def make_store(tmp_path: Path, *payloads: dict) -> Path:
    store = tmp_path / "fingerprints"
    for p in payloads:
        write_version(store, p)
    return store


def variant(version: str, status: str = "published") -> dict:
    p = copy.deepcopy(seed_payload())
    p["version"] = version
    p["status"] = status
    return p


def test_load_seed_defaults_to_published_version():
    fp = load(SEED_PAIR, fingerprint_dir=SEED_STORE)
    assert fp.version == "1.0.0"
    assert fp.status == "published"
    assert len(fp.failure_modes) == 18


def test_load_explicit_version():
    fp = load(SEED_PAIR, version="1.0.0", fingerprint_dir=SEED_STORE)
    assert fp.version == "1.0.0"


def test_default_skips_drafts_and_picks_highest_published(tmp_path):
    store = make_store(
        tmp_path,
        variant("0.9.0"),
        variant("1.0.0"),
        variant("1.1.0", status="draft"),
    )
    assert load(SEED_PAIR, fingerprint_dir=store).version == "1.0.0"
    # explicit pin may load the draft
    assert load(SEED_PAIR, version="1.1.0", fingerprint_dir=store).status == "draft"


def test_semver_ordering_not_lexicographic(tmp_path):
    store = make_store(tmp_path, variant("1.9.0"), variant("1.10.0"))
    assert list_versions(SEED_PAIR, store) == ["1.9.0", "1.10.0"]
    assert load(SEED_PAIR, fingerprint_dir=store).version == "1.10.0"


def test_no_published_version_refused(tmp_path):
    store = make_store(tmp_path, variant("1.0.0", status="draft"))
    with pytest.raises(FingerprintDirectoryError, match="no published"):
        load(SEED_PAIR, fingerprint_dir=store)


def test_unknown_pair_raises_file_not_found():
    with pytest.raises(FileNotFoundError, match="no-such-pair"):
        load("no-such-pair", fingerprint_dir=SEED_STORE)


def test_unknown_version_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        load(SEED_PAIR, version="9.9.9", fingerprint_dir=SEED_STORE)


def test_fingerprint_id_directory_mismatch_refused(tmp_path):
    payload = variant("1.0.0")
    store = tmp_path / "fingerprints"
    d = store / "some-other-pair" / "1.0.0"
    d.mkdir(parents=True)
    (d / "fingerprint.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(FingerprintDirectoryError, match="does not match"):
        load("some-other-pair", version="1.0.0", fingerprint_dir=store)


def test_version_directory_mismatch_refused(tmp_path):
    payload = variant("2.0.0")
    store = tmp_path / "fingerprints"
    d = store / SEED_PAIR / "1.0.0"  # file says 2.0.0, dir says 1.0.0
    d.mkdir(parents=True)
    (d / "fingerprint.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(FingerprintDirectoryError, match="does not match"):
        load(SEED_PAIR, version="1.0.0", fingerprint_dir=store)


def test_unknown_rule_type_fails_loudly_with_path(tmp_path):
    payload = variant("1.0.0")
    payload["detection_rules"][0]["type"] = "fuzzy_match"
    store = make_store(tmp_path, payload)
    with pytest.raises(ValidationError) as exc:
        load(SEED_PAIR, fingerprint_dir=store)
    errors = exc.value.errors()
    assert any(e["loc"][:2] == ("detection_rules", 0) for e in errors)
    assert "fuzzy_match" in str(exc.value)


def test_rule_referencing_missing_failure_mode_fails_loudly(tmp_path):
    payload = variant("1.0.0")
    payload["detection_rules"][0]["failure_mode"] = "FM-099"
    store = make_store(tmp_path, payload)
    with pytest.raises(ValidationError) as exc:
        load(SEED_PAIR, fingerprint_dir=store)
    assert "FM-099" in str(exc.value)


def test_load_file_direct_on_seed():
    fp = load_file(SEED_STORE / SEED_PAIR / "1.0.0" / "fingerprint.json")
    assert fp.fingerprint_id == SEED_PAIR
