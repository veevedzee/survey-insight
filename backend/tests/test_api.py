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


def test_delete_and_unknown_session() -> None:
    session_id = client.post("/api/sessions/sample").json()["session_id"]
    assert client.delete(f"/api/sessions/{session_id}").status_code == 204
    response = client.post(f"/api/sessions/{session_id}/columns", json={"types": {}})
    assert response.status_code == 404
