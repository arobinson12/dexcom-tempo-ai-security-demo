"""
Unit and Integration Test Suite for Dexcom Stelo / FDA TEMPO Metabolic AI Portal
Runs automatically in CI/CD and CodeMender sandbox verification.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import init_db

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    init_db()

client = TestClient(app)


def test_healthcheck():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "dexcom" in data["service"]


def test_get_recent_egvs():
    response = client.get("/api/v1/egvs/recent?patient_id=patient_001&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "records" in data
    assert len(data["records"]) > 0
    record = data["records"][0]
    assert "glucose_value" in record
    assert "trend_arrow" in record


def test_export_cgm_records_normal():
    """
    Tests legitimate export of CGM records by event_type.
    """
    response = client.get("/api/v1/egvs/export?event_type=BREAKFAST")
    assert response.status_code == 200
    data = response.json()
    assert data["event_type"] == "BREAKFAST"
    assert "records" in data
    assert data["record_count"] >= 1
    for r in data["records"]:
        assert r["event_type"] == "BREAKFAST"


def test_oauth_callback_success():
    """
    Tests OAuth callback handling on successful authorization.
    """
    response = client.get("/api/v1/oauth/callback?code=dexcom_auth_xyz123")
    assert response.status_code == 200
    assert "Dexcom OAuth Authorization Successful" in response.text


def test_oauth_callback_error():
    """
    Tests OAuth callback handling when provider returns an error parameter.
    """
    response = client.get("/api/v1/oauth/callback?error=access_denied")
    assert response.status_code == 400
    assert "Dexcom OAuth Authorization Error" in response.text
    assert "access_denied" in response.text


def test_coach_analyze_with_guardrails():
    """
    Tests the 3-stage security guardrail endpoint.
    """
    payload = {
        "patient_note": "Patient Alex Vance had a spike after breakfast. Glucose is 145 mg/dL.",
        "recent_egvs": [95, 110, 135, 145],
        "guardrails_enabled": True,
        "model_name": "gemini-4-argon"
    }
    response = client.post("/api/v1/coach/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["guardrails_enabled"] is True
    assert "stage_1_dlp" in data
    assert "stage_2_model_armor" in data
    assert "stage_3_gemini" in data
