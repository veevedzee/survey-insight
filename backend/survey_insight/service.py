"""Every operation of the app as plain functions, with no web framework.

Two front doors use this module:

* ``api.py``: FastAPI, for running Survey Insight as a server.
* ``bridge.py``: Pyodide, for running the whole analysis inside the visitor's
  browser (the hosted demo), where no server exists at all.

Keeping the logic here means both modes behave identically and are tested once.
Errors are raised as ``ServiceError`` with an HTTP-style status code, which
each front door translates (an HTTP response or a JavaScript error).
"""

from __future__ import annotations

import math
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from survey_insight import __version__
from survey_insight.cleaning import apply_cleaning as _apply_cleaning
from survey_insight.cleaning import build_report
from survey_insight.config import settings
from survey_insight.exporting import cleaned_table, export_filename, to_csv_bytes
from survey_insight.findings import Finding, build_findings
from survey_insight.loading import ColumnType, SurveyFileError, profile_columns, read_survey
from survey_insight.privacy import anonymize
from survey_insight.session_store import Session, SessionNotFound, SessionStore
from survey_insight.stats import StatsReport, build_stats
from survey_insight.text_themes import (
    BROWSER_MODEL_ID,
    MODEL_NAME,
    EmbeddingError,
    PrecomputedEmbedder,
    ThemesReport,
    build_themes,
    texts_to_embed,
)

store = SessionStore(ttl_seconds=settings.session_ttl_minutes * 60)

PRIVACY_LIMITATIONS = [
    "Names inside written answers are only caught when the same name appears in a name column.",
    "Detection uses patterns (emails, phone numbers, ID-like numbers); unusual formats may slip "
    "through, so skim the masked examples above.",
]


class ServiceError(Exception):
    """A request that can't be served, with the matching HTTP status code."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def to_jsonable(value: Any) -> Any:
    """Dataclasses, enums and NaN -> plain JSON values (NaN becomes null)."""
    if is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):  # numpy scalars
        return to_jsonable(value.item())
    return value


# --------------------------------------------------------------------------- #
def _session(session_id: str) -> Session:
    try:
        return store.get(session_id)
    except SessionNotFound:
        raise ServiceError(404, "This session has expired. Please upload the file again.") from None


def _analysed(session_id: str) -> Session:
    session = _session(session_id)
    if session.analysis is None or session.data is None:
        raise ServiceError(409, "Apply the cleaning choices first.")
    return session


def _stats(session: Session) -> StatsReport:
    if session.stats is None:
        session.stats = build_stats(session.analysis, session.types, session.profiles)
    return session.stats


def _text_columns(session: Session) -> list[str]:
    return [c for c, t in session.types.items() if t == ColumnType.TEXT]


# --------------------------------------------------------------------------- #
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


def start_session(data: bytes, filename: str) -> dict[str, Any]:
    """Read a CSV/XLSX and detect the type of every column."""
    limit = settings.max_upload_mb * 1024 * 1024
    if len(data) > limit:
        raise ServiceError(413, f"Files up to {settings.max_upload_mb} MB are supported.")
    try:
        df = read_survey(data, filename)
    except SurveyFileError as exc:
        raise ServiceError(400, str(exc)) from exc
    profiles = profile_columns(df)
    session = store.create(filename, df, profiles)
    return {
        "session_id": session.id,
        "filename": filename,
        "n_rows": len(df),
        "n_columns": df.shape[1],
        "columns": to_jsonable(profiles),
    }


def sample_session() -> dict[str, Any]:
    """Start a session with the bundled synthetic student survey."""
    path = settings.sample_data_path
    if not path.exists():
        raise ServiceError(500, "Sample data is missing.")
    return start_session(path.read_bytes(), path.name)


def confirm_columns(session_id: str, types: dict[str, str]) -> dict[str, Any]:
    """Save the confirmed types, then remove personal data and the raw upload."""
    session = _session(session_id)
    if session.raw is None:
        raise ServiceError(409, "Columns were already confirmed. Start over to change them.")
    known = {p.name for p in session.profiles}
    unknown = set(types) - known
    if unknown:
        raise ServiceError(422, f"Unknown columns: {', '.join(sorted(unknown))}")
    try:
        chosen = {p.name: ColumnType(types.get(p.name, p.detected_type))
                  for p in session.profiles}
    except ValueError as exc:
        raise ServiceError(422, str(exc)) from exc

    clean, report = anonymize(session.raw, chosen)
    session.types = {c: t for c, t in chosen.items() if c in clean.columns}
    session.data = clean
    session.privacy = report
    session.raw = None  # the only copy with personal data is dropped here
    return {
        "removed_columns": to_jsonable(report.removed_columns),
        "masked_columns": to_jsonable(report.masked_columns),
        "total_masked": report.total_masked,
        "n_rows": len(clean),
        "n_columns": clean.shape[1],
        "limitations": PRIVACY_LIMITATIONS,
    }


def cleaning_report(session_id: str) -> dict[str, Any]:
    """Run every data-quality check on the anonymised data (cached per session)."""
    session = _session(session_id)
    if session.data is None:
        raise ServiceError(409, "Confirm the column types first.")
    if session.cleaning is None:
        session.data, session.cleaning = build_report(session.data, session.types,
                                                      session.profiles)
    report = session.cleaning
    return {
        "n_rows": report.n_rows,
        "checks": [
            {
                "key": c.key, "label": c.label, "description": c.description,
                "action": c.action, "available": c.available,
                "unavailable_reason": c.unavailable_reason,
                "n_flagged": len(c.flagged_rows), "flagged_rows": c.flagged_rows,
                "examples": to_jsonable(c.examples[:8]),
            }
            for c in report.checks
        ],
        "normalizations": to_jsonable(report.normalizations),
    }


def apply_cleaning(session_id: str, apply: list[str]) -> dict[str, Any]:
    """Apply the checks the user ticked; can be called again to change the choice."""
    session = _session(session_id)
    if session.data is None or session.cleaning is None:
        raise ServiceError(409, "Open the cleaning report first.")
    try:
        session.analysis, result = _apply_cleaning(session.data, session.cleaning, apply)
    except ValueError as exc:
        raise ServiceError(422, str(exc)) from exc
    session.stats = None  # different rows -> results must be recomputed
    session.themes = None
    return to_jsonable(result)


def statistics(session_id: str) -> StatsReport:
    return _stats(_analysed(session_id))


def texts_for_embedding(session_id: str) -> dict[str, Any]:
    """Step 1 of themes: the distinct, non-filler answers to turn into vectors."""
    session = _analysed(session_id)
    return {
        "model": BROWSER_MODEL_ID,
        "columns": [{"column": c, "texts": texts_to_embed(session.analysis[c])}
                    for c in _text_columns(session)],
    }


def themes(session_id: str, columns: list[dict[str, Any]]) -> ThemesReport:
    """Step 2 of themes: cluster the vectors into labelled themes."""
    session = _analysed(session_id)
    texts = [t for col in columns for t in col.get("texts", [])]
    vectors = [v for col in columns for v in col.get("vectors", [])]
    try:
        embedder = PrecomputedEmbedder(texts, vectors)
        session.themes = build_themes(session.analysis, _text_columns(session), embedder,
                                      MODEL_NAME)
    except EmbeddingError as exc:
        raise ServiceError(422, f"Could not use the answer vectors: {exc}") from exc
    return session.themes


def findings(session_id: str) -> list[Finding]:
    session = _analysed(session_id)
    n_excluded = len(session.data) - len(session.analysis)
    return build_findings(_stats(session), session.themes, n_excluded)


def export_csv(session_id: str) -> tuple[str, bytes]:
    """(file name, CSV bytes) of the cleaned, anonymised data with scale scores."""
    session = _analysed(session_id)
    table = cleaned_table(session.analysis, _stats(session), session.profiles)
    return export_filename(session.filename, "cleaned.csv"), to_csv_bytes(table)


def delete_session(session_id: str) -> None:
    store.delete(session_id)
