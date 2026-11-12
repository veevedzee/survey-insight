"""The CSV export is the analysed table, anonymised, Excel-friendly, with scale scores."""

from __future__ import annotations

import io

import pandas as pd
from fastapi.testclient import TestClient

from survey_insight.api import app
from survey_insight.exporting import export_filename, to_csv_bytes

client = TestClient(app)


def test_csv_has_byte_order_mark_for_excel() -> None:
    data = to_csv_bytes(pd.DataFrame({"Q": ["موافق"]}))
    assert data.startswith(b"\xef\xbb\xbf")
    assert "موافق" in data.decode("utf-8-sig")


def test_export_filename_is_header_safe() -> None:
    assert export_filename("Student Survey (2).xlsx", "cleaned.csv") == \
        "Student_Survey_2-cleaned.csv"
    assert export_filename("استبيان.csv", "cleaned.csv") == "survey-cleaned.csv"


def test_csv_endpoint_returns_cleaned_anonymised_data() -> None:
    session_id = client.post("/api/sessions/sample").json()["session_id"]
    client.post(f"/api/sessions/{session_id}/columns", json={"types": {}})
    assert client.get(f"/api/sessions/{session_id}/export/csv").status_code == 409

    report = client.get(f"/api/sessions/{session_id}/cleaning").json()
    client.post(f"/api/sessions/{session_id}/cleaning",
                json={"apply": [c["key"] for c in report["checks"]]})
    response = client.get(f"/api/sessions/{session_id}/export/csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="student_wellbeing_survey-cleaned.csv"' in \
        response.headers["content-disposition"]
    df = pd.read_csv(io.BytesIO(response.content), encoding="utf-8-sig")
    assert len(df) == 262
    for personal in ("Email", "Name", "Student ID", "WhatsApp number (optional)"):
        assert personal not in df.columns
    assert "Scale score: Stress over the past month" in df.columns
    assert df["Scale score: Stress over the past month"].between(1, 5).all()
    assert not df.astype(str).apply(lambda c: c.str.contains("@example")).any().any()
