"""Smoke test: the API starts and answers the health check."""

from fastapi.testclient import TestClient

from survey_insight import __version__
from survey_insight.api import app

client = TestClient(app)


def test_root_points_to_docs() -> None:
    assert client.get("/").json()["docs"] == "/docs"


def test_health_returns_ok_and_version() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}
