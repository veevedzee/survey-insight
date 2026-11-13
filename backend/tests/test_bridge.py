"""The in-browser bridge routes calls exactly like the HTTP API."""

from __future__ import annotations

import json

from survey_insight import bridge
from tests.fakes import FakeEmbedder


def call(method: str, path: str, body: dict | None = None) -> tuple[int, object]:
    response = json.loads(bridge.handle(method, path, json.dumps(body) if body else None))
    return response["status"], response["body"]


def test_full_flow_through_the_bridge() -> None:
    status, upload = call("POST", "/api/sessions/sample")
    assert status == 200 and upload["n_rows"] == 300
    sid = upload["session_id"]

    status, privacy = call("POST", f"/api/sessions/{sid}/columns", {"types": {}})
    assert status == 200 and len(privacy["removed_columns"]) == 4

    status, report = call("GET", f"/api/sessions/{sid}/cleaning")
    keys = [c["key"] for c in report["checks"]]
    status, result = call("POST", f"/api/sessions/{sid}/cleaning", {"apply": keys})
    assert result["n_after"] == 262

    status, stats = call("GET", f"/api/sessions/{sid}/stats")
    assert status == 200 and stats["n_responses"] == 262
    # NaN never reaches JavaScript: JSON has no NaN, so it must become null.
    assert "NaN" not in bridge.handle("GET", f"/api/sessions/{sid}/stats")

    status, to_embed = call("GET", f"/api/sessions/{sid}/texts")
    fake = FakeEmbedder()
    columns = [{"column": c["column"], "texts": c["texts"],
                "vectors": fake.encode(c["texts"]).round(4).tolist()}
               for c in to_embed["columns"]]
    status, themes = call("POST", f"/api/sessions/{sid}/themes", {"columns": columns})
    assert status == 200 and themes["columns"][0]["themes"]

    status, findings = call("GET", f"/api/sessions/{sid}/findings")
    assert status == 200 and any(f["kind"] == "theme" for f in findings)

    status, csv = call("GET", f"/api/sessions/{sid}/export/csv")
    assert csv["filename"] == "student_wellbeing_survey-cleaned.csv"
    assert csv["content"].startswith("﻿")  # byte-order mark for Excel

    assert call("DELETE", f"/api/sessions/{sid}")[0] == 204
    assert call("GET", f"/api/sessions/{sid}/stats")[0] == 404


def test_upload_and_errors() -> None:
    response = json.loads(bridge.upload("s.csv", b"Faculty,Age\nEngineering,20\nBusiness,21\n"))
    assert response["status"] == 200 and response["body"]["n_rows"] == 2

    bad = json.loads(bridge.upload("s.pdf", b"%PDF"))
    assert bad["status"] == 400 and "csv" in bad["body"]["detail"].lower()

    assert call("GET", "/api/nowhere")[0] == 404
    sid = response["body"]["session_id"]
    status, body = call("POST", f"/api/sessions/{sid}/columns", {"types": {"Age": "nonsense"}})
    assert status == 422
