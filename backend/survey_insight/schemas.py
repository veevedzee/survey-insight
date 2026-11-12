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


class FlagExampleOut(BaseModel):
    row: int  # 0-based row index; the UI shows "response #row+1"
    detail: str


class CheckOut(BaseModel):
    """One data-quality check and the responses it flagged."""

    key: str
    label: str
    description: str
    action: str  # "exclude" the response or "blank" the value
    available: bool
    unavailable_reason: str | None
    n_flagged: int
    flagged_rows: list[int]
    examples: list[FlagExampleOut]


class NormalizationOut(BaseModel):
    column: str
    n_changed: int
    changes: list[tuple[str, str]]


class CleaningReportOut(BaseModel):
    """Every check, so the user can choose what to exclude."""

    n_rows: int
    checks: list[CheckOut]
    normalizations: list[NormalizationOut]


class ApplyCleaningRequest(BaseModel):
    """Keys of the checks the user wants applied."""

    apply: list[str] = Field(default_factory=list)


class CleaningResultOut(BaseModel):
    n_before: int
    n_after: int
    n_values_blanked: int
    applied: list[str]


class PrivacyReportOut(BaseModel):
    """What the privacy step removed before any analysis."""

    removed_columns: list[RemovedColumnOut]
    masked_columns: list[MaskedColumnOut]
    total_masked: int
    n_rows: int
    n_columns: int
    limitations: list[str]
