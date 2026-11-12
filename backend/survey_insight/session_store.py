"""Keep each user's survey in memory for a short time. Nothing touches disk.

Why in memory?

* Privacy: there is no file to forget to delete. When a session expires, or
  the server restarts, the data is gone.
* Simplicity: no database to run on a free hosting tier.

Trade-off: it only works with a single server process. That's fine for a
portfolio demo; a multi-server deployment would need a shared store like Redis.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

import pandas as pd

from survey_insight.cleaning import CleaningReport
from survey_insight.loading import ColumnProfile, ColumnType
from survey_insight.privacy import PrivacyReport
from survey_insight.stats import StatsReport


@dataclass
class Session:
    """One user's analysis in progress.

    ``raw`` holds the upload *with* personal data and exists only between upload
    and column confirmation. After that, only the anonymised ``data`` is kept.
    """

    id: str
    filename: str
    profiles: list[ColumnProfile]
    raw: pd.DataFrame | None
    data: pd.DataFrame | None = None
    types: dict[str, ColumnType] = field(default_factory=dict)
    privacy: PrivacyReport | None = None
    cleaning: CleaningReport | None = None
    analysis: pd.DataFrame | None = None  # data after the user's cleaning choices
    stats: StatsReport | None = None  # cached; reset when cleaning choices change
    last_used: float = field(default_factory=time.monotonic)


class SessionNotFound(KeyError):
    """The session id is unknown or the session has expired."""


class SessionStore:
    """Thread-safe dictionary of sessions with expiry and a size cap."""

    def __init__(self, ttl_seconds: float, max_sessions: int = 50) -> None:
        self._ttl = ttl_seconds
        self._max = max_sessions
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, filename: str, raw: pd.DataFrame, profiles: list[ColumnProfile]) -> Session:
        """Store a new upload and return its session."""
        session = Session(id=uuid.uuid4().hex, filename=filename, profiles=profiles, raw=raw)
        with self._lock:
            self._purge_expired()
            while len(self._sessions) >= self._max:  # drop the least recently used
                oldest = min(self._sessions.values(), key=lambda s: s.last_used)
                del self._sessions[oldest.id]
            self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session:
        """Return a live session and refresh its expiry time."""
        with self._lock:
            self._purge_expired()
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFound(session_id)
            session.last_used = time.monotonic()
            return session

    def delete(self, session_id: str) -> None:
        """Forget a session immediately (the user pressed "Start over")."""
        with self._lock:
            self._sessions.pop(session_id, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [sid for sid, s in self._sessions.items() if now - s.last_used > self._ttl]
        for sid in expired:
            del self._sessions[sid]
