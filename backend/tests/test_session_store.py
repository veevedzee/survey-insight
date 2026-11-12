"""Sessions expire and the store never grows without bound."""

from __future__ import annotations

import time

import pandas as pd
import pytest

from survey_insight.session_store import SessionNotFound, SessionStore


def test_expired_sessions_are_forgotten() -> None:
    store = SessionStore(ttl_seconds=0.05)
    session = store.create("s.csv", pd.DataFrame({"a": [1]}), [])
    time.sleep(0.1)
    with pytest.raises(SessionNotFound):
        store.get(session.id)


def test_oldest_session_is_evicted_when_full() -> None:
    store = SessionStore(ttl_seconds=60, max_sessions=2)
    first = store.create("1.csv", pd.DataFrame(), [])
    store.create("2.csv", pd.DataFrame(), [])
    store.create("3.csv", pd.DataFrame(), [])
    assert len(store) == 2
    with pytest.raises(SessionNotFound):
        store.get(first.id)
