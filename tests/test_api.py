"""MS-3.1 (spec Ch. 18): the endpoint-catalog subset live, REQ-030 bodies
mirroring the domain models, the §18.5 error envelope, and the generated
OpenAPI companion artifact."""

import json

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.fingerprint.models import ConversionRun, Finding, Fingerprint
from tests.conftest import REPO, copy_fingerprint_store

SAMPLES = REPO / "data" / "samples"
PAIR = "omni-zos-to-omni-linux"


@pytest.fixture()
def client(tmp_path):
    store = copy_fingerprint_store(tmp_path)
    app = create_app(fingerprint_dir=store, runs_dir=tmp_path / "runs")
    return TestClient(app, raise_server_exceptions=False)


def start_seeded_run(client) -> str:
    response = client.post("/runs", json={
        "pair_id": PAIR,
        "source_dir": str(SAMPLES / "source" / "PLN-SEED-01"),
        "target_dir": str(SAMPLES / "target" / "PLN-SEED-01"),
    })
    assert response.status_code == 202, response.text
    return response.json()["run_id"]


# --- fingerprints ---------------------------------------------------------------


def test_platform_pairs(client):
    payload = client.get("/platform-pairs").json()
    by_pair = {p["pair_id"]: p for p in payload}
    assert by_pair[PAIR] == {"pair_id": PAIR, "current_version": "1.0.0",
                             "modes": 18, "rules": 23}
    assert "omni-to-trac" in by_pair  # MS-3.3 second fingerprint


def test_get_fingerprint_mirrors_domain_model(client):
    """REQ-030: the body round-trips through the domain model unchanged."""
    response = client.get(f"/fingerprints/{PAIR}")
    assert response.status_code == 200
    fingerprint = Fingerprint.model_validate(response.json())
    assert fingerprint.version == "1.0.0"
    assert len(fingerprint.failure_modes) == 18


def test_suite_endpoint_is_prioritized(client):
    payload = client.get(f"/fingerprints/{PAIR}/suite").json()
    assert payload["version"] == "1.0.0"
    first = payload["suite"][0]
    assert first["rule_id"] == "RULE-BAL-TOTALS-001"
    assert first["priority_score"] == "0.7125"


def test_unknown_pair_uses_error_envelope(client):
    response = client.get("/fingerprints/no-such-pair")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == 404
    assert "no-such-pair" in error["message"]
    assert error["request_id"]
    assert response.headers["x-request-id"] == error["request_id"]


# --- runs ------------------------------------------------------------------------


def test_run_clean_pair_green(client):
    response = client.post("/runs", json={
        "pair_id": PAIR,
        "source_dir": str(SAMPLES / "source" / "PLN-CLEAN-01"),
        "target_dir": str(SAMPLES / "target" / "PLN-CLEAN-01"),
    })
    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "review"
    assert payload["findings"] == 0
    assert payload["summary"]["passed"] == 23

    run = ConversionRun.model_validate(
        client.get(f"/runs/{payload['run_id']}").json())
    assert run.status == "review"


def test_run_seeded_findings_and_detail(client):
    run_id = start_seeded_run(client)
    findings = client.get(f"/runs/{run_id}/findings").json()
    assert len(findings) == 21
    assert [Finding.model_validate(f) for f in findings]  # REQ-030

    high = client.get(f"/runs/{run_id}/findings",
                      params={"severity": "CRITICAL"}).json()
    assert len(high) == 3

    finding_id = findings[0]["finding_id"]
    detail = client.get(f"/findings/{finding_id}").json()
    assert detail["finding_id"] == finding_id
    assert detail["sample_records"]

    suite = client.get(f"/runs/{run_id}/suite").json()
    assert len(suite) == 23
    assert suite[0]["rule_id"] == "RULE-BAL-TOTALS-001"


def test_run_gate_refusal_is_422(client, tmp_path):
    source = SAMPLES / "source" / "PLN-CLEAN-01"
    broken = tmp_path / "broken-target"
    broken.mkdir()
    (broken / "plans.csv").write_text(
        (SAMPLES / "target" / "PLN-CLEAN-01" / "plans.csv")
        .read_text(encoding="utf-8"), encoding="utf-8")
    response = client.post("/runs", json={
        "pair_id": PAIR, "source_dir": str(source), "target_dir": str(broken),
    })
    assert response.status_code == 422
    assert "REQ-021" in response.json()["error"]["message"]


def test_bad_request_body_is_422_envelope(client):
    response = client.post("/runs", json={"pair_id": PAIR})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == 422


# --- reviews + learning (demo step 4 over HTTP) -------------------------------------


def test_review_flow_matches_spec_sample(client):
    run_id = start_seeded_run(client)
    findings = client.get(f"/runs/{run_id}/findings").json()
    loan = next(f for f in findings if f["rule_id"] == "RULE-LOAN-BAL-001")

    response = client.post(f"/findings/{loan['finding_id']}/review", json={
        "decision": "confirmed", "comment": "ticket CONV-214",
        "reviewer": "jsmith",
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["finding_status"] == "confirmed"
    event = payload["learning_event"]
    assert event["failure_mode"] == "FM-001"
    assert event["probability_before"] == 0.70
    assert event["probability_after"] == 0.727
    assert event["fingerprint_version_created"] == "1.0.1"

    # duplicate review -> 409 conflict (spec §18.5)
    duplicate = client.post(f"/findings/{loan['finding_id']}/review",
                            json={"decision": "false_positive"})
    assert duplicate.status_code == 409

    history = client.get(f"/fingerprints/{PAIR}/learning-history").json()
    assert len(history) == 1
    assert history[0]["fm_id"] == "FM-001"

    publish = client.post(f"/fingerprints/{PAIR}/publish",
                          json={"bump": "patch", "changelog": "wave 1"})
    assert publish.status_code == 200
    assert publish.json()["new_version"] == "1.0.1"

    versions = client.get(f"/fingerprints/{PAIR}/versions").json()
    assert versions["current"] == "1.0.1"
    assert {v["version"] for v in versions["versions"]} == {"1.0.0", "1.0.1"}

    # publishing again without a draft -> 409
    again = client.post(f"/fingerprints/{PAIR}/publish", json={"bump": "patch"})
    assert again.status_code == 409


# --- report artifacts -----------------------------------------------------------------


def test_report_endpoints(client):
    run_id = start_seeded_run(client)
    as_json = client.get(f"/runs/{run_id}/report").json()
    assert as_json["run"]["run_id"] == run_id

    as_html = client.get(f"/runs/{run_id}/report", params={"format": "html"})
    assert as_html.status_code == 200
    assert as_html.headers["content-type"].startswith("text/html")
    assert "<style>" in as_html.text  # REQ-025 self-contained

    recon = client.get(f"/runs/{run_id}/reconciliation/plan")
    assert recon.status_code == 200
    assert "PRETAX" in recon.text

    missing = client.get(f"/runs/{run_id}/reconciliation/nonsense")
    assert missing.status_code == 404


def test_unknown_run_404(client):
    assert client.get("/runs/RUN-2026-01-01-0001").status_code == 404
    assert client.get("/runs/RUN-2026-01-01-0001/findings").status_code == 404


# --- OpenAPI (done-when: OpenAPI generated) ---------------------------------------------


EXPECTED_PATHS = {
    "/platform-pairs",
    "/fingerprints/{pair_id}",
    "/fingerprints/{pair_id}/versions",
    "/fingerprints/{pair_id}/versions/{version}",
    "/fingerprints/{pair_id}/suite",
    "/fingerprints/{pair_id}/learning-history",
    "/fingerprints/{pair_id}/publish",
    "/runs",
    "/runs/{run_id}",
    "/runs/{run_id}/suite",
    "/runs/{run_id}/findings",
    "/findings/{finding_id}",
    "/findings/{finding_id}/review",
    "/findings/{finding_id}/assign",
    "/findings/{finding_id}/comment",
    "/findings/{finding_id}/resolve",
    "/findings/{finding_id}/close",
    "/findings/{finding_id}/history",
    "/runs/{run_id}/exceptions",
    "/runs/{run_id}/report",
    "/runs/{run_id}/reconciliation/{kind}",
}


def test_openapi_served_with_all_endpoints(client):
    schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == EXPECTED_PATHS
    assert "Fingerprint" in schema["components"]["schemas"]  # REQ-030
    assert "Finding" in schema["components"]["schemas"]


def test_openapi_companion_artifact_current():
    """docs/openapi.json (spec §18.2 companion) matches the app. Regenerate
    with `python -m src.api` when endpoints change."""
    committed = json.loads(
        (REPO / "docs" / "openapi.json").read_text(encoding="utf-8"))
    live = create_app().openapi()
    assert committed["paths"].keys() == live["paths"].keys()
    assert committed["info"]["version"] == live["info"]["version"]