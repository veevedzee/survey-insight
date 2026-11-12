"""FastAPI application: the thin HTTP layer.

All real work lives in the sibling modules (loading, privacy, cleaning, ...).
This file only turns HTTP requests into plain function calls and turns the
results back into JSON. Keeping it thin means the logic can be unit-tested
without starting a web server.

Run locally (from the ``backend`` folder)::

    uvicorn survey_insight.api:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from survey_insight import __version__
from survey_insight.config import settings
from survey_insight.schemas import HealthResponse

app = FastAPI(
    title="Survey Insight API",
    version=__version__,
    description="Upload a survey export and get cleaned data, statistics and themes.",
)

# The frontend is served from a different origin (Vercel) than the API
# (Hugging Face Spaces), so the browser needs explicit CORS permission.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report that the API is running and which version is deployed."""
    return HealthResponse(status="ok", version=__version__)
