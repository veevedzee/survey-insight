"""Runtime settings, read once from environment variables.

Keeping configuration in one place means the same code runs locally and on the
free hosting tier; only the environment variables differ.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _split_csv(value: str) -> tuple[str, ...]:
    """Turn ``"a, b,c"`` into ``("a", "b", "c")``, ignoring empty parts."""
    return tuple(part.strip() for part in value.split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    """Application settings.

    Attributes:
        allowed_origins: Frontend URLs allowed to call the API from a browser (CORS).
        max_upload_mb: Largest survey file we accept, to protect free-tier memory.
        session_ttl_minutes: How long an uploaded survey stays in memory before it
            is deleted. Nothing is ever written to disk.
    """

    allowed_origins: tuple[str, ...]
    max_upload_mb: int
    session_ttl_minutes: int


def load_settings() -> Settings:
    """Build :class:`Settings` from environment variables with safe local defaults."""
    return Settings(
        allowed_origins=_split_csv(
            os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        ),
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "10")),
        session_ttl_minutes=int(os.getenv("SESSION_TTL_MINUTES", "30")),
    )


settings = load_settings()
