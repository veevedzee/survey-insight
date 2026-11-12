"""A tiny stand-in for the multilingual embedding model (which runs in the browser).

It maps each text to a direction based on which topic words it contains,
including Arabic synonyms, which mimics what a multilingual model does
(same meaning -> nearby vectors, whatever the language) with a known answer.
Vectors have the real model's 384 dimensions; only the first few are used.
"""

from __future__ import annotations

import hashlib

import numpy as np

TOPICS = [
    ("bus", "commute", "traffic", "المواصلات", "الطريق"),
    ("exam", "exams", "grades", "الامتحانات", "المعدل"),
    ("gym", "football", "sport", "الجيم", "كورة"),
]


class FakeEmbedder:
    name = "fake-embedder"

    def __init__(self) -> None:
        self.calls = 0

    def encode(self, texts: list[str]) -> np.ndarray:
        self.calls += 1
        rows = []
        for text in texts:
            lowered = text.casefold()
            vec = np.zeros(384)
            for i, words in enumerate(TOPICS):
                if any(w in lowered for w in words):
                    vec[i] = 1.0
            # Small deterministic "noise" so points aren't identical.
            seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
            n = len(TOPICS)
            vec[n:n + 2] = np.random.default_rng(seed).normal(0, 0.05, 2)
            if not vec[:n].any():
                vec[n + 1] += 1.0
            rows.append(vec / np.linalg.norm(vec))
        return np.array(rows)
