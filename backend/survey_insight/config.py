"""Runtime settings, read once from environment variables.

Keeping configuration in one place means the same code runs locally and on the
free hosting tier; only the environment variables differ.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SAMPLE = _REPO_ROOT / "sample_data" / "student_wellbeing_survey.csv"


def _split_csv(value: str) -> tuple[str, ...]:
    """Turn ``"a, b,c"`` into ``("a", "b", "c")``, ignoring empty parts."""
    return tuple(part.strip() for part in value.split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    """Application settings.

    Attributes:
        allowed_origins: Frontend URLs allowed to call the API from a browser (CORS).
        allowed_origin_regex: Optional pattern for extra origins, e.g. Vercel preview
            deployments (https://survey-insight-git-branch-you.vercel.app).
        max_upload_mb: Largest survey file we accept, to protect free-tier memory.
        session_ttl_minutes: How long an uploaded survey stays in memory before it
            is deleted. Nothing is ever written to disk.
        sample_data_path: The bundled demo survey behind "Try with sample data".
    """

    allowed_origins: tuple[str, ...]
    allowed_origin_regex: str | None
    max_upload_mb: int
    session_ttl_minutes: int
    sample_data_path: Path


def load_settings() -> Settings:
    """Build :class:`Settings` from environment variables with safe local defaults."""
    return Settings(
        allowed_origins=_split_csv(
            os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        ),
        allowed_origin_regex=os.getenv("ALLOWED_ORIGIN_REGEX") or None,
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "10")),
        session_ttl_minutes=int(os.getenv("SESSION_TTL_MINUTES", "30")),
        sample_data_path=Path(os.getenv("SAMPLE_DATA_PATH", str(_DEFAULT_SAMPLE))),
    )


settings = load_settings()
