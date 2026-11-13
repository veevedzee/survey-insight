"""In-browser entry point: lets JavaScript call the service through Pyodide.

On the hosted demo there is no server. The browser runs Python (Pyodide), loads
this package, and the frontend calls ``handle()`` with the same method and path
it would send to the HTTP API. Responses come back as JSON strings shaped like
HTTP responses ({"status": ..., "body": ...}), so the frontend code is the
same in both modes, and the survey file never leaves the visitor's device.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from survey_insight import service
from survey_insight.service import ServiceError, to_jsonable

_ID = r"(?P<sid>[0-9a-f]{32})"

# (method, path pattern) -> handler(match, body) -> JSON-able value
_ROUTES: list[tuple[str, re.Pattern[str], Callable[[re.Match[str], Any], Any]]] = [
    ("GET", re.compile(r"/api/health"), lambda m, b: service.health()),
    ("POST", re.compile(r"/api/sessions/sample"), lambda m, b: service.sample_session()),
    ("POST", re.compile(rf"/api/sessions/{_ID}/columns"),
     lambda m, b: service.confirm_columns(m["sid"], (b or {}).get("types", {}))),
    ("GET", re.compile(rf"/api/sessions/{_ID}/cleaning"),
     lambda m, b: service.cleaning_report(m["sid"])),
    ("POST", re.compile(rf"/api/sessions/{_ID}/cleaning"),
     lambda m, b: service.apply_cleaning(m["sid"], (b or {}).get("apply", []))),
    ("GET", re.compile(rf"/api/sessions/{_ID}/stats"),
     lambda m, b: service.statistics(m["sid"])),
    ("GET", re.compile(rf"/api/sessions/{_ID}/texts"),
     lambda m, b: service.texts_for_embedding(m["sid"])),
    ("POST", re.compile(rf"/api/sessions/{_ID}/themes"),
     lambda m, b: service.themes(m["sid"], (b or {}).get("columns", []))),
    ("GET", re.compile(rf"/api/sessions/{_ID}/findings"),
     lambda m, b: service.findings(m["sid"])),
    ("GET", re.compile(rf"/api/sessions/{_ID}/export/csv"), lambda m, b: _csv(m["sid"])),
    ("DELETE", re.compile(rf"/api/sessions/{_ID}"),
     lambda m, b: service.delete_session(m["sid"])),
]


def _csv(session_id: str) -> dict[str, str]:
    filename, content = service.export_csv(session_id)
    # Decoding with utf-8 keeps the byte-order mark as "﻿", so the file the
    # browser saves is byte-for-byte the same as the server's download.
    return {"filename": filename, "content": content.decode("utf-8")}


def _response(status: int, body: Any) -> str:
    return json.dumps({"status": status, "body": to_jsonable(body)}, ensure_ascii=False)


def handle(method: str, path: str, body_json: str | None = None) -> str:
    """Route one API call; returns {"status": int, "body": ...} as JSON."""
    try:
        body = json.loads(body_json) if body_json else None
        for route_method, pattern, handler in _ROUTES:
            match = pattern.fullmatch(path)
            if match and route_method == method.upper():
                result = handler(match, body)
                return _response(204 if result is None else 200, result)
        return _response(404, {"detail": f"No route for {method} {path}"})
    except ServiceError as exc:
        return _response(exc.status, {"detail": exc.detail})
    except Exception as exc:  # pragma: no cover - surfaced to the UI instead of a crash
        return _response(500, {"detail": f"Unexpected error: {exc}"})


def upload(filename: str, data: bytes) -> str:
    """Start a session from file bytes read in the browser (never sent anywhere)."""
    try:
        return _response(200, service.start_session(bytes(data), filename))
    except ServiceError as exc:
        return _response(exc.status, {"detail": exc.detail})


def upload_js(filename: str, js_bytes: Any) -> str:  # pragma: no cover - Pyodide only
    """``upload`` for a JavaScript Uint8Array (a Pyodide JsProxy)."""
    return upload(filename, js_bytes.to_bytes())
