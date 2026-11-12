"""Pydantic models describing what the API sends and receives.

FastAPI uses these to validate data and to generate the interactive docs at
``/docs``. The frontend mirrors them in ``frontend/src/api/types.ts``.
"""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Answer of ``GET /api/health``: lets the frontend (and the host) check we are up."""

    status: str
    version: str
