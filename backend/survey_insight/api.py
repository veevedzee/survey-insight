"""FastAPI application: the thin HTTP layer.

All real work lives in the sibling modules (loading, privacy, cleaning, ...).
This file only turns HTTP requests into plain function calls and turns the
results back into JSON. Keeping it thin means the logic can be unit-tested
without starting a web server.

Run locally (from the ``backend`` folder)::

    uvicorn survey_insight.api:app --reload --port 8000

Flow of one analysis::

    POST /api/sessions             upload a file      -> detected column types
    POST /api/sessions/sample      use the demo file  -> detected column types
    POST /api/sessions/{id}/columns confirm types     -> privacy report
    GET  /api/sessions/{id}/cleaning                  -> data-quality checks
    POST /api/sessions/{id}/cleaning choose exclusions -> before/after counts
    GET  /api/sessions/{id}/stats                     -> statistics
    GET  /api/sessions/{id}/themes                    -> themes in open-ended answers
    GET  /api/sessions/{id}/findings                  -> rule-based key findings
    GET  /api/sessions/{id}/export/csv                -> cleaned data download
    DELETE /api/sessions/{id}      forget everything now
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from survey_insight import __version__
from survey_insight.cleaning import apply_cleaning, build_report
from survey_insight.config import settings
from survey_insight.exporting import cleaned_table, export_filename, to_csv_bytes
from survey_insight.findings import Finding, build_findings
from survey_insight.loading import ColumnType, SurveyFileError, profile_columns, read_survey
from survey_insight.privacy import anonymize
from survey_insight.schemas import (
    ApplyCleaningRequest,
    CheckOut,
    CleaningReportOut,
    CleaningResultOut,
    ColumnProfileOut,
    ConfirmColumnsRequest,
    FlagExampleOut,
    HealthResponse,
    MaskedColumnOut,
    NormalizationOut,
    PrivacyReportOut,
    RemovedColumnOut,
    UploadResponse,
)
from survey_insight.session_store import Session, SessionNotFound, SessionStore
from survey_insight.stats import StatsReport, build_stats
from survey_insight.text_themes import (
    MODEL_NAME,
    Embedder,
    EmbeddingModel,
    ThemesReport,
    build_themes,
)

embedding_model = EmbeddingModel()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Start loading the embedding model as soon as the server starts.

    Loading takes a few seconds, so it runs in a background thread: the API
    answers health checks and uploads immediately, and by the time a user
    reaches the dashboard the model is usually ready.
    """
    if settings.load_model:
        embedding_model.start_loading()
    yield


def get_embedder() -> Embedder:
    """FastAPI dependency: the shared model (tests override this with a fake)."""
    return embedding_model


app = FastAPI(
    title="Survey Insight API",
    version=__version__,
    description="Upload a survey export and get cleaned data, statistics and themes.",
    lifespan=lifespan,
)

# The frontend is served from a different origin (Vercel) than the API
# (Hugging Face Spaces), so the browser needs explicit CORS permission.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_origin_regex=settings.allowed_origin_regex,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
    # Lets the browser read the download's file name across origins.
    expose_headers=["Content-Disposition"],
)

store = SessionStore(ttl_seconds=settings.session_ttl_minutes * 60)

PRIVACY_LIMITATIONS = [
    "Names inside written answers are only caught when the same name appears in a name column.",
    "Detection uses patterns (emails, phone numbers, ID-like numbers); unusual formats may slip "
    "through, so skim the masked examples above.",
]


def _get_session(session_id: str) -> Session:
    try:
        return store.get(session_id)
    except SessionNotFound:
        raise HTTPException(
            404, "This session has expired. Please upload the file again."
        ) from None


def _start_session(data: bytes, filename: str) -> UploadResponse:
    try:
        df = read_survey(data, filename)
    except SurveyFileError as exc:
        raise HTTPException(400, str(exc)) from exc
    profiles = profile_columns(df)
    session = store.create(filename, df, profiles)
    return UploadResponse(
        session_id=session.id,
        filename=filename,
        n_rows=len(df),
        n_columns=df.shape[1],
        columns=[ColumnProfileOut(**asdict(p)) for p in profiles],
    )


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    """What visitors to the bare API URL (e.g. the Hugging Face Space page) see."""
    return {"name": "Survey Insight API", "docs": "/docs", "health": "/api/health"}


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report that the API is running and which version is deployed."""
    return HealthResponse(status="ok", version=__version__)


@app.post("/api/sessions", response_model=UploadResponse)
async def upload_survey(file: Annotated[UploadFile, File()]) -> UploadResponse:
    """Read an uploaded CSV/XLSX and detect the type of every column."""
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"Files up to {settings.max_upload_mb} MB are supported.")
    return _start_session(data, file.filename or "upload.csv")


@app.post("/api/sessions/sample", response_model=UploadResponse)
def use_sample_data() -> UploadResponse:
    """Start a session with the bundled synthetic student survey."""
    path = settings.sample_data_path
    if not path.exists():
        raise HTTPException(500, "Sample data is missing on the server.")
    return _start_session(path.read_bytes(), path.name)


@app.post("/api/sessions/{session_id}/columns", response_model=PrivacyReportOut)
def confirm_columns(session_id: str, body: ConfirmColumnsRequest) -> PrivacyReportOut:
    """Save the confirmed column types, then remove personal data.

    After this call the original upload (with personal data) is discarded.
    """
    session = _get_session(session_id)
    if session.raw is None:
        raise HTTPException(409, "Columns were already confirmed. Start over to change them.")
    known = {p.name for p in session.profiles}
    unknown = set(body.types) - known
    if unknown:
        raise HTTPException(422, f"Unknown columns: {', '.join(sorted(unknown))}")

    types = {p.name: body.types.get(p.name, p.detected_type) for p in session.profiles}
    clean, report = anonymize(session.raw, types)
    session.types = {c: t for c, t in types.items() if c in clean.columns}
    session.data = clean
    session.privacy = report
    session.raw = None  # the only copy with personal data is dropped here

    return PrivacyReportOut(
        removed_columns=[RemovedColumnOut(**asdict(c)) for c in report.removed_columns],
        masked_columns=[MaskedColumnOut(**asdict(c)) for c in report.masked_columns],
        total_masked=report.total_masked,
        n_rows=len(clean),
        n_columns=clean.shape[1],
        limitations=PRIVACY_LIMITATIONS,
    )


@app.get("/api/sessions/{session_id}/cleaning", response_model=CleaningReportOut)
def cleaning_report(session_id: str) -> CleaningReportOut:
    """Run every data-quality check on the anonymised data."""
    session = _get_session(session_id)
    if session.data is None:
        raise HTTPException(409, "Confirm the column types first.")
    if session.cleaning is None:  # computed once, then cached in the session
        session.data, session.cleaning = build_report(session.data, session.types,
                                                      session.profiles)
    report = session.cleaning
    return CleaningReportOut(
        n_rows=report.n_rows,
        checks=[
            CheckOut(
                key=c.key, label=c.label, description=c.description, action=c.action,
                available=c.available, unavailable_reason=c.unavailable_reason,
                n_flagged=len(c.flagged_rows), flagged_rows=c.flagged_rows,
                examples=[FlagExampleOut(**asdict(e)) for e in c.examples[:8]],
            )
            for c in report.checks
        ],
        normalizations=[NormalizationOut(**asdict(n)) for n in report.normalizations],
    )


@app.post("/api/sessions/{session_id}/cleaning", response_model=CleaningResultOut)
def apply_cleaning_choices(session_id: str, body: ApplyCleaningRequest) -> CleaningResultOut:
    """Apply the checks the user ticked. Can be called again to change the choice."""
    session = _get_session(session_id)
    if session.data is None or session.cleaning is None:
        raise HTTPException(409, "Open the cleaning report first.")
    try:
        session.analysis, result = apply_cleaning(session.data, session.cleaning, body.apply)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    session.stats = None  # different rows -> statistics must be recomputed
    session.themes = None
    return CleaningResultOut(**asdict(result))


# FastAPI accepts the plain dataclasses from stats.py as the response model,
# so the JSON shape is defined in one place. NaN values are sent as null.
@app.get("/api/sessions/{session_id}/stats", response_model=StatsReport)
def statistics(session_id: str) -> StatsReport:
    """Descriptives, scale reliability, group comparisons and correlations."""
    session = _get_session(session_id)
    if session.analysis is None:
        raise HTTPException(409, "Apply the cleaning choices first.")
    if session.stats is None:
        session.stats = build_stats(session.analysis, session.types, session.profiles)
    return session.stats


@app.get("/api/sessions/{session_id}/themes", response_model=ThemesReport)
def themes(session_id: str, embedder: Annotated[Embedder, Depends(get_embedder)]) -> ThemesReport:
    """Themes, example quotes and (English-only) sentiment for every free-text column."""
    session = _get_session(session_id)
    if session.analysis is None:
        raise HTTPException(409, "Apply the cleaning choices first.")
    if session.themes is None:
        text_cols = [c for c, t in session.types.items() if t == ColumnType.TEXT]
        try:
            session.themes = build_themes(session.analysis, text_cols, embedder,
                                          getattr(embedder, "name", MODEL_NAME))
        except RuntimeError as exc:  # model failed to load (e.g. no internet on first run)
            raise HTTPException(503, f"Theme detection is unavailable: {exc}") from exc
    return session.themes


@app.get("/api/sessions/{session_id}/findings", response_model=list[Finding])
def findings(session_id: str) -> list[Finding]:
    """Rule-based key findings from the statistics (and themes, once computed)."""
    session = _get_session(session_id)
    if session.analysis is None or session.data is None:
        raise HTTPException(409, "Apply the cleaning choices first.")
    if session.stats is None:
        session.stats = build_stats(session.analysis, session.types, session.profiles)
    n_excluded = len(session.data) - len(session.analysis)
    return build_findings(session.stats, session.themes, n_excluded)


@app.get("/api/sessions/{session_id}/export/csv")
def export_csv(session_id: str) -> Response:
    """Download the cleaned, anonymised data (with scale scores) as CSV."""
    session = _get_session(session_id)
    if session.analysis is None:
        raise HTTPException(409, "Apply the cleaning choices first.")
    if session.stats is None:
        session.stats = build_stats(session.analysis, session.types, session.profiles)
    table = cleaned_table(session.analysis, session.stats, session.profiles)
    filename = export_filename(session.filename, "cleaned.csv")
    return Response(
        content=to_csv_bytes(table),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.delete("/api/sessions/{session_id}", status_code=204)
def delete_session(session_id: str) -> None:
    """Forget a session and its data immediately."""
    store.delete(session_id)
