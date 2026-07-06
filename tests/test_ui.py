"""MS-3.2 (spec Ch. 20): the dashboard serves from the API and covers the
five demo-script steps. The page is a no-build, self-contained single page
(the original POC brief's Phase-3 allowance); interaction logic is exercised
through the API endpoints it calls, which have their own tests."""

import re

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from tests.conftest import copy_fingerprint_store


@pytest.fixture()
def client(tmp_path):
    store = copy_fingerprint_store(tmp_path)
    app = create_app(fingerprint_dir=store, runs_dir=tmp_path / "runs")
    return TestClient(app, raise_server_exceptions=False)


def dashboard_html(client) -> str:
    response = client.get("/ui")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    return response.text


def test_root_redirects_to_dashboard(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/ui"


def test_dashboard_is_self_contained(client):
    html = dashboard_html(client)
    assert "<style>" in html
    assert "http://" not in html and "https://" not in html
    assert "<link" not in html
    assert not re.search(r'<script\s+[^>]*src=', html)


def test_dashboard_excluded_from_openapi(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/ui" not in paths and "/" not in paths


def test_dashboard_covers_the_demo_script(client):
    """Demo steps (spec §23.5) all have UI surfaces:
    1 prioritized suite, 2–3 runs with findings drill-down,
    4 review + history + publish, 5 pair switching."""
    html = dashboard_html(client)
    # step 1: prioritized suite view with the differentiator language
    assert "Prioritized suite" in html
    assert "targeted, not generic" in html
    assert "generic (alphabetical) ordering" in html  # §20.2.3 toggle
    # steps 2–3: run wizard with the sample-pair quick picks + drill-down
    assert "PLN-CLEAN-01" in html and "PLN-SEED-01" in html
    assert "PLN-SEED-EB" in html  # EBCDIC preset with layout dir
    assert "/runs" in html
    # step 4: review actions, learning history, publish
    assert "Confirm defect" in html and "False positive" in html
    assert "false_positive" in html and "confirmed" in html
    assert "Learning history" in html and "btnPublish" in html
    # step 5: pair switching from the library
    assert "Fingerprint Library" in html
    assert "/platform-pairs" in html
    # §20.4 severity color tokens
    for token in ("#b91c1c", "#ea580c", "#f59e0b", "#94a3b8"):
        assert token in html


def test_hover_help_mode(client):
    """Hover-help: a persisted on/off toggle plus data-help descriptions on
    objects across every view, rendered by the tooltip engine."""
    html = dashboard_html(client)
    # the toggle and its persistence key
    assert 'id="helpToggle"' in html
    assert "Hover help: OFF" in html
    assert "fp_help_mode" in html  # localStorage key
    # the tooltip engine and help-on styling
    assert 'id="tooltip"' in html
    assert "help-on" in html
    assert "data-help" in html
    # broad coverage: descriptions across the views. They live inside the
    # JS view templates as hlp(...) calls, rendered to data-help at runtime.
    assert html.count("hlp(") >= 25
    for fragment in (
        "probability x impact",            # suite/score explanations
        "RAISES its probability",          # confirm button
        "LOWERS the mode's probability",   # false-positive button
        "IMMUTABLE fingerprint version",   # publish button
        "codified failure signature",      # pair card
    ):
        assert fragment in html, fragment


def test_dashboard_calls_only_existing_endpoints(client):
    """Every API path template referenced by the page's JS exists in the app
    (fetch calls use template literals over these bases)."""
    html = dashboard_html(client)
    live = set(client.get("/openapi.json").json()["paths"])
    referenced = {
        "/platform-pairs": "/platform-pairs",
        "/fingerprints/${pairId}": "/fingerprints/{pair_id}",
        "/fingerprints/${pairId}/suite": "/fingerprints/{pair_id}/suite",
        "/fingerprints/${pairId}/learning-history":
            "/fingerprints/{pair_id}/learning-history",
        "/fingerprints/${pairId}/publish": "/fingerprints/{pair_id}/publish",
        "/runs/${runId}": "/runs/{run_id}",
        "/runs/${runId}/findings": "/runs/{run_id}/findings",
        "/runs/${runId}/suite": "/runs/{run_id}/suite",
        "/findings/${findingId}": "/findings/{finding_id}",
        "/findings/${findingId}/review": "/findings/{finding_id}/review",
        "/findings/${findingId}/history": "/findings/{finding_id}/history",
        "/findings/${findingId}/explanation":
            "/findings/{finding_id}/explanation",
        "/runs/${runId}/exceptions": "/runs/{run_id}/exceptions",
    }
    for js_path, api_path in referenced.items():
        assert js_path in html, js_path
        assert api_path in live, api_path