"""Theme detection on a tiny fixed example (fake embedder, known answer)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from survey_insight.text_themes import (
    EmbeddingError,
    PrecomputedEmbedder,
    choose_k,
    ctfidf_keywords,
    find_themes,
    is_filler,
    language_of,
    normalize_arabic,
    pick_quotes,
    silhouette_quality,
    summarise_sentiment,
    texts_to_embed,
)
from tests.fakes import FakeEmbedder

ANSWERS = [
    # commute (English + Arabic)
    "The bus to campus takes two hours", "Traffic on the commute is terrible",
    "Long commute every day", "The bus is always late", "commute and traffic",
    "المواصلات بتاخد وقت طويل", "الطريق للجامعة طويل",
    # exams
    "I panic during exams", "Worried about my grades", "Exams are stressful",
    "Fear of bad grades", "too many exams", "بتوتر قبل الامتحانات", "خايف على المعدل",
    # sport
    "Going to the gym", "Playing football with friends", "More sport on campus",
    "gym after class", "football helps me relax", "ألعب كورة", "أروح الجيم",
    # filler
    "N/A", "nothing", "-", "لا يوجد",
]


def test_language_detection() -> None:
    assert language_of("The bus is late") == "en"
    assert language_of("المواصلات بتاخد وقت") == "ar"
    assert language_of("الديدلاين is tomorrow and الامتحان") == "mixed"


@pytest.mark.parametrize("text", ["N/A", " nothing. ", "-", "لا يوجد", "...", "x"])
def test_filler_answers(text: str) -> None:
    assert is_filler(text)


def test_real_short_answers_are_not_filler() -> None:
    assert not is_filler("Sleep")
    assert not is_filler("نوم")


def test_normalize_arabic_unifies_spellings() -> None:
    assert normalize_arabic("أكتر إدارة آخر") == "اكتر اداره اخر"
    assert normalize_arabic("مَدرسة") == "مدرسه"


def test_choose_k_finds_three_clear_groups() -> None:
    rng = np.random.default_rng(0)
    centres = np.eye(3)
    vectors = np.vstack([c + rng.normal(0, 0.05, (8, 3)) for c in centres])
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    k, labels, score = choose_k(vectors)
    assert k == 3
    # Each block of 8 points shares one label, and the blocks differ.
    blocks = [set(labels[i * 8:(i + 1) * 8]) for i in range(3)]
    assert all(len(b) == 1 for b in blocks)
    assert len(set.union(*blocks)) == 3
    assert score is not None and score > 0.5
    assert silhouette_quality(score) == "clearly separated themes"


def test_choose_k_with_too_few_points_is_one_theme() -> None:
    k, labels, score = choose_k(np.eye(3)[:3])
    assert k == 1 and score is None and set(labels) == {0}


def test_quotes_are_representative_but_not_near_copies() -> None:
    texts = ["the bus is late", "Honestly, the bus is late.", "traffic is awful", "bus bus"]
    vectors = np.array([[1.0, 0.0], [0.99, 0.141], [0.8, 0.6], [0.995, 0.0999]])
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    picked = pick_quotes(texts, vectors, n=2, max_similarity=0.9)
    chosen = [texts[i] for i in picked]
    assert "traffic is awful" in chosen  # a different voice beats a near-copy
    assert len(set(chosen)) == 2


def test_quotes_fall_back_when_every_answer_is_similar() -> None:
    texts = ["late bus", "late bus!", "bus late"]
    vectors = np.array([[1.0, 0.0], [1.0, 0.001], [1.0, 0.002]])
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    assert len(pick_quotes(texts, vectors, n=3)) == 3


def test_ctfidf_prefers_words_unique_to_a_theme() -> None:
    docs = {
        0: ["the bus is late", "bus every day", "late bus again"],
        1: ["exam stress", "exam panic", "stress before exam"],
    }
    keywords = ctfidf_keywords(docs, top_n=2)
    assert keywords[0][0] in ("bus", "late", "late bus")
    assert "exam" in keywords[1]


def test_find_themes_groups_meaning_across_languages() -> None:
    embedder = FakeEmbedder()
    result = find_themes(pd.Series(ANSWERS, name="Biggest challenge"), embedder)

    assert result.n_filler == 4
    assert result.n_used == len(ANSWERS) - 4
    assert result.k == 3
    assert sorted(t.size for t in result.themes) == [7, 7, 7]
    for theme in result.themes:
        assert len(theme.quotes) == 3
        # Arabic and English answers about the same topic share a theme.
        assert theme.languages.get("ar", 0) >= 2 and theme.languages.get("en", 0) >= 5
    labels = " ".join(t.label for t in result.themes)
    assert "commute" in labels or "bus" in labels
    assert embedder.calls == 1  # embedded in one batch


def test_too_few_answers_are_not_clustered() -> None:
    result = find_themes(pd.Series(["bus", "exam", "N/A"], name="Q"), FakeEmbedder())
    assert result.themes == []
    assert "too few" in result.quality


def test_sentiment_scores_english_only() -> None:
    summary = summarise_sentiment(["I love this, it is great", "This is awful and sad",
                                   "المواصلات وحشة جدا"])
    assert summary is not None
    assert summary.n_english == 2
    assert summary.positive_percent == 50.0 and summary.negative_percent == 50.0
    assert summarise_sentiment(["المواصلات وحشة جدا"]) is None


def test_texts_to_embed_matches_what_clustering_uses() -> None:
    series = pd.Series(ANSWERS + ANSWERS[:3], name="Q")  # 3 repeated answers
    texts = texts_to_embed(series)
    assert len(texts) == len(set(texts)) == len(ANSWERS) - 4  # distinct, no filler
    # find_themes asks the embedder for exactly these texts, so browser vectors line up.
    recorder = FakeEmbedder()
    seen: list[str] = []
    original = recorder.encode
    recorder.encode = lambda t: (seen.extend(t), original(t))[1]  # type: ignore[method-assign]
    find_themes(series, recorder)
    assert seen == texts


def test_texts_to_embed_is_empty_for_tiny_columns() -> None:
    assert texts_to_embed(pd.Series(["bus", "exam"], name="Q")) == []


def test_precomputed_embedder_checks_and_normalises() -> None:
    texts = ["a", "b"]
    embedder = PrecomputedEmbedder(texts, [[3.0] + [0.0] * 383, [0.0, 2.0] + [0.0] * 382])
    vectors = embedder.encode(["b", "a"])
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1)
    assert vectors[0][1] == pytest.approx(1.0)

    with pytest.raises(EmbeddingError, match="no vector"):
        embedder.encode(["c"])
    with pytest.raises(EmbeddingError, match="384"):
        PrecomputedEmbedder(["a"], [[1.0, 2.0]])
    with pytest.raises(EmbeddingError, match="vectors for"):
        PrecomputedEmbedder(["a", "b"], [[0.0] * 384])
    with pytest.raises(EmbeddingError, match="invalid"):
        PrecomputedEmbedder(["a"], [[float("nan")] * 384])
