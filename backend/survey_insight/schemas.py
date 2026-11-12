"""Pydantic models describing what the API sends and receives.

FastAPI uses these to validate data and to generate the interactive docs at
``/docs``. The frontend mirrors them in ``frontend/src/api/types.ts``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from survey_insight.loading import ColumnType


class HealthResponse(BaseModel):
    """Answer of ``GET /api/health``: lets the frontend (and the host) check we are up."""

    status: str
    version: str


class ColumnProfileOut(BaseModel):
    """One detected column, as shown in the column-review table."""

    name: str
    detected_type: ColumnType
    reason: str
    n_missing: int
    n_unique: int
    examples: list[str]
    scale_group: str | None = None
    likert_levels: list[str] | None = None


class UploadResponse(BaseModel):
    """Answer to an upload: a session id plus what we detected."""

    session_id: str
    filename: str
    n_rows: int
    n_columns: int
    columns: list[ColumnProfileOut]


class ConfirmColumnsRequest(BaseModel):
    """Column types the user confirmed or corrected; omitted columns keep the detected type."""

    types: dict[str, ColumnType] = Field(default_factory=dict)


class RemovedColumnOut(BaseModel):
    name: str
    n_values: int


class MaskedColumnOut(BaseModel):
    name: str
    counts: dict[str, int]
    examples: list[str]


class PrivacyReportOut(BaseModel):
    """What the privacy step removed before any analysis."""

    removed_columns: list[RemovedColumnOut]
    masked_columns: list[MaskedColumnOut]
    total_masked: int
    n_rows: int
    n_columns: int
    limitations: list[str]
