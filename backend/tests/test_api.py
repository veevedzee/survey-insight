"""HTTP flow: upload -> confirm columns -> privacy report -> delete."""

from __future__ import annotations

from fastapi.testclient import TestClient

from survey_insight.api import app, store

client = TestClient(app)


def test_sample_upload_detects_columns() -> None:
    response = client.post("/api/sessions/sample")
    assert response.status_code == 200
    body = response.json()
    assert body["n_rows"] == 300
    assert body["n_columns"] == 27
    types = {c["name"]: c["detected_type"] for c in body["columns"]}
    assert types["Email"] == "identifier"


def test_upload_csv_file() -> None:
    files = {"file": ("s.csv", b"Faculty,Age\nEngineering,20\nBusiness,21\n", "text/csv")}
    response = client.post("/api/sessions", files=files)
    assert response.status_code == 200
    assert response.json()["n_rows"] == 2


def test_upload_rejects_bad_file() -> None:
    files = {"file": ("s.pdf", b"%PDF-1.4", "application/pdf")}
    response = client.post("/api/sessions", files=files)
    assert response.status_code == 400
    assert "csv" in response.json()["detail"].lower()


def test_confirm_columns_removes_personal_data_and_raw_copy() -> None:
    session_id = client.post("/api/sessions/sample").json()["session_id"]
    # The user corrects one type: treat Age as single choice (just to test overrides).
    response = client.post(f"/api/sessions/{session_id}/columns",
                           json={"types": {"Age": "single_choice"}})
    assert response.status_code == 200
    report = response.json()
    removed = {c["name"] for c in report["removed_columns"]}
    assert removed == {"Email", "Name", "Student ID", "WhatsApp number (optional)"}
    assert report["total_masked"] >= 5
    assert report["n_columns"] == 23

    session = store.get(session_id)
    assert session.raw is None
    assert session.types["Age"] == "single_choice"

    again = client.post(f"/api/sessions/{session_id}/columns", json={"types": {}})
    assert again.status_code == 409


def test_confirm_rejects_unknown_columns() -> None:
    session_id = client.post("/api/sessions/sample").json()["session_id"]
    response = client.post(f"/api/sessions/{session_id}/columns",
                           json={"types": {"Not a column": "text"}})
    assert response.status_code == 422


def test_cleaning_flow_on_sample_data() -> None:
    session_id = client.post("/api/sessions/sample").json()["session_id"]
    assert client.get(f"/api/sessions/{session_id}/cleaning").status_code == 409

    client.post(f"/api/sessions/{session_id}/columns", json={"types": {}})
    report = client.get(f"/api/sessions/{session_id}/cleaning").json()
    checks = {c["key"]: c for c in report["checks"]}
    assert checks["duplicates"]["n_flagged"] == 8
    assert checks["outliers"]["n_flagged"] == 4
    assert checks["speeders"]["available"]
    assert checks["straight_lining"]["n_flagged"] >= 10
    assert report["normalizations"]

    result = client.post(f"/api/sessions/{session_id}/cleaning",
                         json={"apply": ["duplicates"]}).json()
    assert result == {"n_before": 300, "n_after": 292, "n_values_blanked": 0,
                      "applied": ["duplicates"]}
    assert len(store.get(session_id).analysis) == 292


def test_stats_endpoint_on_sample_data() -> None:
    session_id = client.post("/api/sessions/sample").json()["session_id"]
    client.post(f"/api/sessions/{session_id}/columns", json={"types": {}})
    assert client.get(f"/api/sessions/{session_id}/stats").status_code == 409

    report = client.get(f"/api/sessions/{session_id}/cleaning").json()
    client.post(f"/api/sessions/{session_id}/cleaning",
                json={"apply": [c["key"] for c in report["checks"]]})
    body = client.get(f"/api/sessions/{session_id}/stats").json()

    assert body["n_responses"] == 262
    assert {s["label"] for s in body["scales"]} == {"Stress over the past month", "Study habits"}
    assert all(s["reliable"] for s in body["scales"])
    stress_by_faculty = next(c for c in body["comparisons"]
                             if c["outcome_kind"] == "scale" and c["group_by"] == "Faculty"
                             and "Stress" in c["outcome"])
    assert stress_by_faculty["significant"]
    sleep_stress = next(c for c in body["correlations"]
                        if "sleep" in c["x"] and "Stress" in c["y"])
    assert sleep_stress["rho"] < 0 and sleep_stress["significant"]


def test_themes_and_findings_endpoints_with_fake_model() -> None:
    from survey_insight.api import get_embedder
    from tests.fakes import FakeEmbedder

    app.dependency_overrides[get_embedder] = FakeEmbedder
    try:
        session_id = client.post("/api/sessions/sample").json()["session_id"]
        client.post(f"/api/sessions/{session_id}/columns", json={"types": {}})
        report = client.get(f"/api/sessions/{session_id}/cleaning").json()
        client.post(f"/api/sessions/{session_id}/cleaning",
                    json={"apply": [c["key"] for c in report["checks"]]})

        themes = client.get(f"/api/sessions/{session_id}/themes").json()
        assert len(themes["columns"]) == 2
        challenge = themes["columns"][0]
        assert challenge["n_filler"] > 0
        assert challenge["themes"] and challenge["themes"][0]["quotes"]
        assert "English" in themes["sentiment_note"]

        findings = client.get(f"/api/sessions/{session_id}/findings").json()
        kinds = [f["kind"] for f in findings]
        assert "difference" in kinds and "theme" in kinds
        assert all(f["text"] for f in findings)
    finally:
        app.dependency_overrides.clear()


def test_delete_and_unknown_session() -> None:
    session_id = client.post("/api/sessions/sample").json()["session_id"]
    assert client.delete(f"/api/sessions/{session_id}").status_code == 204
    response = client.post(f"/api/sessions/{session_id}/columns", json={"types": {}})
    assert response.status_code == 404
