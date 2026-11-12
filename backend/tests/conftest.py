"""Shared test setup."""

import os

# Tests never download or load the real embedding model (they use a fake one),
# so the API must not start loading it on startup.
os.environ.setdefault("LOAD_MODEL", "0")
