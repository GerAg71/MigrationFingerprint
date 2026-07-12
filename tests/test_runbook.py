"""The technical runbook (tools/build_runbook.py): generated from the live
fingerprint store, complete (every failure mode and rule of every pair),
deterministic, searchable, and served at /runbook."""

import html
import json

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from tools.build_runbook import build, describe_rule, load_pairs
from tests.conftest import REPO, copy_fingerprint_store


@pytest.fixture(scope="module")
def page() -> str:
    return build()


def test_every_mode_and_rule_is_documented(page):
    """Completeness: the runbook can never silently omit catalog entries."""
    pairs = load_pairs()
    assert len(pairs) == 3
    for fp in pairs:
        assert fp["fingerprint_id"] in page
        for fm in fp["failure_modes"]:
            assert fm["id"] in page, fm["id"]
            assert html.escape(fm["name"], quote=True) in page, fm["name"]
        for rule in fp["detection_rules"]:
            assert rule["rule_id"] in page, rule["rule_id"]


def test_core_sections_present(page):
    for anchor in ("id=\"overview\"", "id=\"run\"", "id=\"scoring\"",
                   "id=\"severity\"", "id=\"learning\"", "id=\"ruletypes\"",
                   "id=\"cli\"", "id=\"provenance\"", "id=\"glossary\""):
        assert anchor in page, anchor
    # the score math and the learning formula, with worked numbers
    assert "probability</b> &times; <b>impact" in page
    assert "0.63" in page                       # FM-101 worked example
    assert "(7+1)/(10+1)" in page               # learning-loop worked example
    assert "clamped to [0.05, 0.99]" in page
    # severity semantics and tie-breaking
    assert "CRITICAL &gt; HIGH &gt; MEDIUM &gt; LOW" in page
    # search machinery
    assert 'id="q"' in page and "markMatches" in page
    # all seven rule types documented
    for rule_type in ("field_compare", "count_balance", "referential",
                      "derived_recompute", "encoding_check",
                      "sort_order_check", "format_conformance"):
        assert f'id="type-{rule_type}"' in page, rule_type


def test_generation_is_deterministic(page):
    assert build() == page


def test_rule_descriptions_are_plain_english():
    store = REPO / "data" / "fingerprints"
    restore = json.loads(
        (store / "omni-zos-to-omni-linux-restore" / "1.0.0" /
         "fingerprint.json").read_text(encoding="utf-8"))
    by_id = {r["rule_id"]: r for r in restore["detection_rules"]}
    fmt = describe_rule(by_id["RULE-RST-FMT-001"])
    assert "must be BLANK" in fmt and "off-label" in fmt
    recompute = describe_rule(by_id["RULE-RST-VEST-001"])
    assert "stock formula" in recompute
    counts = describe_rule(by_id["RULE-RST-CNT-001"])
    assert "row count per plan_id" in counts


def test_served_at_runbook_and_out_of_openapi(tmp_path):
    store = copy_fingerprint_store(tmp_path)
    client = TestClient(create_app(fingerprint_dir=store,
                                   runs_dir=tmp_path / "runs"))
    response = client.get("/runbook")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Technical Runbook" in response.text
    assert "/runbook" not in client.get("/openapi.json").json()["paths"]


def test_committed_runbook_is_current():
    """docs/runbook.html must match a fresh build of the current store —
    regenerating after a publish is part of the workflow."""
    committed = (REPO / "docs" / "runbook.html").read_text(encoding="utf-8")
    assert committed == build()