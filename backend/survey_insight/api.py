"""FastAPI application: optional server mode.

The hosted demo needs no server: the same code runs inside the browser through
Pyodide (see ``bridge.py``). This module serves it over HTTP instead, for local
development or anyone who prefers to self-host. All logic lives in
``service.py``; this file only maps HTTP requests to those functions.

Run locally (from the ``backend`` folder)::

    uvicorn survey_insight.api:app --reload --port 8000

Flow of one analysis::

    POST /api/sessions             upload a file      -> detected column types
    POST /api/sessions/sample      use the demo file  -> detected column types
    POST /api/sessions/{id}/columns confirm types     -> privacy report
    GET  /api/sessions/{id}/cleaning                  -> data-quality checks
    POST /api/sessions/{id}/cleaning choose exclusions -> before/after counts
    GET  /api/sessions/{id}/stats                     -> statistics
    GET  /api/sessions/{id}/texts                     -> answers for the browser to embed
    POST /api/sessions/{id}/themes  answer vectors    -> themes in open-ended answers
    GET  /api/sessions/{id}/findings                  -> rule-based key findings
    GET  /api/sessions/{id}/export/csv                -> cleaned data download
    DELETE /api/sessions/{id}      forget everything now
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import FastAPI, File, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from survey_insight import __version__, service
from survey_insight.config import settings
from survey_insight.findings import Finding
from survey_insight.schemas import (
    ApplyCleaningRequest,
    CleaningReportOut,
    CleaningResultOut,
    ConfirmColumnsRequest,
    HealthResponse,
    PrivacyReportOut,
    TextsToEmbedOut,
    ThemesRequest,
    UploadResponse,
)
from survey_insight.service import ServiceError
from survey_insight.stats import StatsReport
from survey_insight.text_themes import ThemesReport

store = service.store  # re-exported for tests

app = FastAPI(
    title="Survey Insight API",
    version=__version__,
    description="Upload a survey export and get cleaned data, statistics and themes.",
)

# When the frontend is served from another origin than the API, the browser
# needs explicit CORS permission.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_origin_regex=settings.allowed_origin_regex,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # lets the browser read the download's name
)


@app.exception_handler(ServiceError)
async def service_error(_: Request, exc: ServiceError) -> JSONResponse:
    """Service errors become ordinary HTTP errors with a readable message."""
    return JSONResponse(status_code=exc.status, content={"detail": exc.detail})


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"name": "Survey Insight API", "docs": "/docs", "health": "/api/health"}


@app.get("/api/health", response_model=HealthResponse)
def health() -> dict[str, str]:
    """Report that the API is running and which version is deployed."""
    return service.health()


@app.post("/api/sessions", response_model=UploadResponse)
async def upload_survey(file: Annotated[UploadFile, File()]) -> dict[str, Any]:
    """Read an uploaded CSV/XLSX and detect the type of every column."""
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    return service.start_session(data, file.filename or "upload.csv")


@app.post("/api/sessions/sample", response_model=UploadResponse)
def use_sample_data() -> dict[str, Any]:
    """Start a session with the bundled synthetic student survey."""
    return service.sample_session()


@app.post("/api/sessions/{session_id}/columns", response_model=PrivacyReportOut)
def confirm_columns(session_id: str, body: ConfirmColumnsRequest) -> dict[str, Any]:
    """Save the confirmed column types, then remove personal data."""
    return service.confirm_columns(session_id, {k: v.value for k, v in body.types.items()})


@app.get("/api/sessions/{session_id}/cleaning", response_model=CleaningReportOut)
def cleaning_report(session_id: str) -> dict[str, Any]:
    """Run every data-quality check on the anonymised data."""
    return service.cleaning_report(session_id)


@app.post("/api/sessions/{session_id}/cleaning", response_model=CleaningResultOut)
def apply_cleaning_choices(session_id: str, body: ApplyCleaningRequest) -> dict[str, Any]:
    """Apply the checks the user ticked. Can be called again to change the choice."""
    return service.apply_cleaning(session_id, body.apply)


# FastAPI accepts the plain dataclasses from stats.py as the response model,
# so the JSON shape is defined in one place. NaN values are sent as null.
@app.get("/api/sessions/{session_id}/stats", response_model=StatsReport)
def statistics(session_id: str) -> StatsReport:
    """Descriptives, scale reliability, group comparisons and correlations."""
    return service.statistics(session_id)


@app.get("/api/sessions/{session_id}/texts", response_model=TextsToEmbedOut)
def texts_for_embedding(session_id: str) -> dict[str, Any]:
    """Step 1 of themes: the answers the browser should turn into vectors."""
    return service.texts_for_embedding(session_id)


@app.post("/api/sessions/{session_id}/themes", response_model=ThemesReport)
def themes(session_id: str, body: ThemesRequest) -> ThemesReport:
    """Step 2 of themes: cluster the browser's vectors into labelled themes."""
    return service.themes(session_id, [c.model_dump() for c in body.columns])


@app.get("/api/sessions/{session_id}/findings", response_model=list[Finding])
def findings(session_id: str) -> list[Finding]:
    """Rule-based key findings from the statistics (and themes, once computed)."""
    return service.findings(session_id)


@app.get("/api/sessions/{session_id}/export/csv")
def export_csv(session_id: str) -> Response:
    """Download the cleaned, anonymised data (with scale scores) as CSV."""
    filename, content = service.export_csv(session_id)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.delete("/api/sessions/{session_id}", status_code=204)
def delete_session(session_id: str) -> None:
    """Forget a session and its data immediately."""
    service.delete_session(session_id)
