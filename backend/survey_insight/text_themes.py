"""Find themes in open-ended answers without any paid AI.

Pipeline for one free-text column
---------------------------------
1. **Clean**: drop empty and filler answers ("N/A", "nothing", "لا يوجد").
2. **Embed**: a small multilingual sentence-transformers model turns each
   answer into a 384-number vector. Answers with similar *meaning* get nearby
   vectors, even across languages ("the commute is long" ~ "المواصلات بتاخد وقت").
   The model runs **in the visitor's browser** (Transformers.js, ONNX version
   of the same model); the browser sends only the vectors back. That keeps
   this server small enough for a free 512 MB host.
3. **Cluster**: k-means groups the vectors. The number of themes k is chosen
   automatically: we try k = 2..8 and keep the k with the best silhouette score
   (how much closer answers are to their own theme than to the next one).
4. **Label**: class-based TF-IDF (c-TF-IDF) finds words that are frequent in one
   theme but rare in the others; the top ones become the theme's label.
5. **Quote**: the 3 answers closest to the theme's centre are shown as real
   examples, so readers can judge the label themselves.
6. **Sentiment**: VADER scores English answers only. It is a word-list method
   built for English; scoring Arabic with it would produce confident nonsense,
   so Arabic answers are counted but not scored.

Steps 1, 3-6 run here. ``texts_to_embed`` defines exactly which answers the
browser must embed, and ``find_themes`` re-derives the same list, so the
vectors line up with the answers.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
import pandas as pd

# The browser loads the ONNX conversion of this model from Hugging Face.
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
BROWSER_MODEL_ID = "Xenova/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384
MAX_TEXTS = 2000  # larger columns are sampled to keep memory and time bounded
MIN_TEXTS = 10  # fewer answers than this: no clustering, just list them
MAX_THEMES = 8
QUOTES_PER_THEME = 3

JUNK_ANSWERS = {
    "n/a", "na", "none", "nothing", "no", "nope", "idk", "-", ".", "..", "...", "nil",
    "no comment", "no comments", "not sure", "لا", "لا يوجد", "لايوجد", "مفيش", "لا شيء",
}

_ARABIC_LETTER = re.compile(r"[؀-ۿ]")
_LATIN_LETTER = re.compile(r"[A-Za-z]")
_DIACRITICS = re.compile(r"[ؗ-ًؚ-ْـ]")  # harakat + tatweel

# Words that say nothing about the theme. English starts from scikit-learn's list.
EXTRA_ENGLISH_STOPWORDS = {
    "honestly", "think", "really", "just", "lot", "mainly", "like", "also", "especially",
    "things", "thing", "dont", "don", "don't", "im", "i'm", "ve", "able", "make",
    "want", "need", "get", "feel", "better", "help", "would", "lots", "always", "every",
}
ARABIC_STOPWORDS = {
    "و", "في", "من", "على", "علي", "الى", "الي", "عن", "مع", "ان", "انا", "انت", "هو", "هي",
    "اللي", "ده", "دي", "دا", "كل", "بس", "كمان", "جدا", "اوي", "عشان", "علشان", "مش",
    "حاجه", "حاجة", "بصراحه", "بصراحة", "اكتر", "يعني", "لما", "ما", "لو", "او", "ولا", "اني",
    "انى", "بتاع", "بتاعت", "كده", "كدا", "زي", "عليا", "ليا", "لي", "ايه", "اللى",
}


# --------------------------------------------------------------------------- #
# Embeddings (computed in the browser, swappable in tests)
# --------------------------------------------------------------------------- #
class Embedder(Protocol):
    """Anything that turns texts into L2-normalised vectors (one row per text)."""

    def encode(self, texts: list[str]) -> np.ndarray: ...


class EmbeddingError(ValueError):
    """The vectors sent by the browser don't match the answers they should describe."""


class PrecomputedEmbedder:
    """Serves vectors the browser already computed, looked up by answer text.

    The server never trusts that the browser sent the right thing: shapes are
    checked, every requested answer must have a vector, and vectors are
    re-normalised to length 1.
    """

    def __init__(self, texts: list[str], vectors: list[list[float]]) -> None:
        if len(texts) != len(vectors):
            raise EmbeddingError(f"Got {len(vectors)} vectors for {len(texts)} answers.")
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or (len(texts) and matrix.shape[1] != EMBEDDING_DIM):
            raise EmbeddingError(f"Each vector must have {EMBEDDING_DIM} numbers.")
        if not np.isfinite(matrix).all():
            raise EmbeddingError("Vectors contain invalid numbers.")
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        self._index = {t: i for i, t in enumerate(texts)}
        self._matrix = matrix / np.where(norms == 0, 1, norms)

    def encode(self, texts: list[str]) -> np.ndarray:
        missing = [t for t in texts if t not in self._index]
        if missing:
            example = missing[0][:40]
            raise EmbeddingError(f"{len(missing)} answers have no vector, e.g. “{example}”.")
        return self._matrix[[self._index[t] for t in texts]]


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #
@dataclass
class SentimentSummary:
    """VADER sentiment of the English answers in a group."""

    n_english: int
    mean_compound: float  # -1 (very negative) .. +1 (very positive)
    positive_percent: float
    neutral_percent: float
    negative_percent: float


@dataclass
class ThemeQuote:
    text: str
    language: str  # "en" | "ar" | "mixed"


@dataclass
class Theme:
    id: int
    label: str
    keywords: list[str]
    size: int
    percent: float
    quotes: list[ThemeQuote]
    languages: dict[str, int]
    sentiment: SentimentSummary | None = None


@dataclass
class ColumnThemes:
    """Themes found in one free-text column."""

    column: str
    n_answers: int  # non-empty answers
    n_used: int  # answers that went into clustering
    n_filler: int  # "N/A", "nothing", ...
    sampled: bool
    k: int
    silhouette: float | None
    quality: str
    themes: list[Theme]
    sentiment: SentimentSummary | None
    notes: list[str] = field(default_factory=list)


@dataclass
class ThemesReport:
    model: str
    columns: list[ColumnThemes]
    sentiment_note: str = ("Sentiment uses VADER, which only understands English. Arabic "
                           "answers are grouped into themes but not scored for sentiment.")


# --------------------------------------------------------------------------- #
# Text helpers
# --------------------------------------------------------------------------- #
def language_of(text: str) -> str:
    """"ar", "en" or "mixed", from the share of Arabic vs Latin letters."""
    arabic = len(_ARABIC_LETTER.findall(text))
    latin = len(_LATIN_LETTER.findall(text))
    if arabic and latin:
        share = arabic / (arabic + latin)
        return "ar" if share > 0.7 else "en" if share < 0.3 else "mixed"
    return "ar" if arabic else "en"


def is_filler(text: str) -> bool:
    """True for answers that carry no content ("N/A", "nothing", "-")."""
    folded = " ".join(text.casefold().split()).strip(" .!?")
    return len(folded) < 2 or folded in JUNK_ANSWERS or not re.search(r"\w", folded)


def normalize_arabic(text: str) -> str:
    """Unify Arabic spelling variants so keyword counts aren't split.

    أ/إ/آ -> ا, ة -> ه, ى -> ي, and diacritics/tatweel removed. Only used for
    keyword extraction; quotes are always shown exactly as written.
    """
    text = _DIACRITICS.sub("", text)
    text = re.sub("[أإآ]", "ا", text)
    return text.replace("ة", "ه").replace("ى", "ي")


# --------------------------------------------------------------------------- #
# Clustering
# --------------------------------------------------------------------------- #
def choose_k(vectors: np.ndarray, k_max: int = MAX_THEMES,
             seed: int = 0) -> tuple[int, np.ndarray, float | None]:
    """Run k-means for k = 2..k_max and keep the k with the best silhouette score.

    Returns (k, labels, silhouette). With very few answers, everything is one theme.
    """
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    n = len(vectors)
    upper = min(k_max, n // 5)  # at least ~5 answers per theme on average
    if upper < 2:
        return 1, np.zeros(n, dtype=int), None
    best: tuple[float, int, np.ndarray] | None = None
    for k in range(2, upper + 1):
        labels = KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(vectors)
        if len(set(labels)) < 2:
            continue
        score = float(silhouette_score(vectors, labels, metric="cosine"))
        if best is None or score > best[0] + 1e-9:
            best = (score, k, labels)
    if best is None:
        return 1, np.zeros(n, dtype=int), None
    score, k, labels = best
    return k, labels, score


def silhouette_quality(score: float | None) -> str:
    """Plain-English reading of a silhouette score for sentence embeddings."""
    if score is None:
        return "too few answers to separate themes"
    if score >= 0.25:
        return "clearly separated themes"
    if score >= 0.1:
        return "moderately separated themes"
    return "weakly separated themes: treat labels as rough"


def ctfidf_keywords(docs_by_theme: dict[int, list[str]], top_n: int = 4) -> dict[int, list[str]]:
    """Class-based TF-IDF: words that characterise one theme compared with the rest.

    All answers of a theme are joined into one "class document". For each word:
    tf  = its frequency in the class, divided by the class's total word count
    idf = log(1 + average words per class / the word's frequency across all classes)
    Words common everywhere (e.g. "study" in a study-habits survey) get a low idf.
    """
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, CountVectorizer

    ids = list(docs_by_theme)
    class_docs = [normalize_arabic(" ".join(docs_by_theme[i])).casefold() for i in ids]
    stop = set(ENGLISH_STOP_WORDS) | EXTRA_ENGLISH_STOPWORDS | ARABIC_STOPWORDS
    vectorizer = CountVectorizer(token_pattern=r"(?u)\b[^\W\d_]{2,}\b", ngram_range=(1, 2),
                                 stop_words=sorted(stop))
    try:
        counts = vectorizer.fit_transform(class_docs).toarray().astype(float)
    except ValueError:  # every word was a stopword
        return {i: [] for i in ids}
    words = vectorizer.get_feature_names_out()
    tf = counts / np.maximum(counts.sum(axis=1, keepdims=True), 1)
    avg_words = counts.sum() / len(ids)
    idf = np.log(1 + avg_words / np.maximum(counts.sum(axis=0), 1))
    scores = tf * idf
    result: dict[int, list[str]] = {}
    for row, theme_id in enumerate(ids):
        ranked = [words[j] for j in np.argsort(-scores[row]) if counts[row, j] >= 2]
        chosen: list[str] = []
        for word in ranked:
            # Skip a single word already covered by a chosen bigram, and vice versa.
            if any(word in c.split() or c in word.split() for c in chosen):
                continue
            chosen.append(word)
            if len(chosen) == top_n:
                break
        result[theme_id] = chosen
    return result


# --------------------------------------------------------------------------- #
# Sentiment (English only)
# --------------------------------------------------------------------------- #
_vader = None


def _sentiment_analyzer():  # noqa: ANN202 - vaderSentiment has no type hints
    global _vader
    if _vader is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        _vader = SentimentIntensityAnalyzer()
    return _vader


def summarise_sentiment(texts: list[str]) -> SentimentSummary | None:
    """VADER compound scores for the English texts; None if there are none.

    Conventional cut-offs: compound >= 0.05 positive, <= -0.05 negative.
    """
    english = [t for t in texts if language_of(t) == "en"]
    if not english:
        return None
    analyzer = _sentiment_analyzer()
    scores = np.array([analyzer.polarity_scores(t)["compound"] for t in english])
    n = len(scores)
    return SentimentSummary(
        n_english=n,
        mean_compound=round(float(scores.mean()), 3),
        positive_percent=round(100 * float((scores >= 0.05).mean()), 1),
        neutral_percent=round(100 * float(((scores > -0.05) & (scores < 0.05)).mean()), 1),
        negative_percent=round(100 * float((scores <= -0.05).mean()), 1),
    )


# --------------------------------------------------------------------------- #
# Putting it together
# --------------------------------------------------------------------------- #
def pick_quotes(texts: list[str], vectors: np.ndarray, n: int = QUOTES_PER_THEME,
                max_similarity: float = 0.85) -> list[int]:
    """Choose representative but *different* example answers for a theme.

    Walk through answers from closest to the theme's centre outwards and keep
    one only if it is not a near-copy (cosine similarity > ``max_similarity``)
    of a quote already chosen. "The bus is late" and "Honestly, the bus is
    late." count as one voice; a theme that mixes two ideas shows both.
    If the theme is too uniform to find ``n`` different voices, the closest
    remaining distinct texts fill the gap.
    """
    centre = vectors.mean(axis=0)
    centre /= np.linalg.norm(centre) or 1.0
    order = list(np.argsort(-(vectors @ centre)))
    chosen: list[int] = []
    for j in order:
        if texts[j] in (texts[c] for c in chosen):
            continue
        if all(float(vectors[j] @ vectors[c]) <= max_similarity for c in chosen):
            chosen.append(int(j))
        if len(chosen) == n:
            return chosen
    for j in order:  # fallback: allow similar, but never identical, texts
        if len(chosen) == n:
            break
        if texts[j] not in (texts[c] for c in chosen):
            chosen.append(int(j))
    return chosen


def _useful_answers(series: pd.Series, seed: int = 0) -> tuple[list[str], list[str], bool]:
    """All non-empty answers, the ones worth clustering, and whether we sampled.

    Sampling uses a fixed seed, so calling this twice gives the same answers:
    that's what lets the browser embed them and the server cluster them later.
    """
    answers = [str(v).strip() for v in series.dropna() if str(v).strip()]
    useful = [t for t in answers if not is_filler(t)]
    sampled = len(useful) > MAX_TEXTS
    if sampled:
        rng = np.random.default_rng(seed)
        useful = [useful[i] for i in sorted(rng.choice(len(useful), MAX_TEXTS, replace=False))]
    return answers, useful, sampled


def texts_to_embed(series: pd.Series, seed: int = 0) -> list[str]:
    """The distinct answers the browser must turn into vectors for this column."""
    _, useful, _ = _useful_answers(series, seed)
    return list(dict.fromkeys(useful)) if len(useful) >= MIN_TEXTS else []


def find_themes(series: pd.Series, embedder: Embedder, seed: int = 0) -> ColumnThemes:
    """Find themes in one free-text column."""
    answers, useful, sampled = _useful_answers(series, seed)
    n_filler = len(answers) - len([t for t in answers if not is_filler(t)])
    notes: list[str] = []
    if sampled:
        notes.append(f"Large column: themes are based on a random sample of {MAX_TEXTS} answers.")

    base = ColumnThemes(str(series.name), len(answers), len(useful), n_filler, sampled, 0, None,
                        "", [], summarise_sentiment(useful), notes)
    if len(useful) < MIN_TEXTS:
        base.quality = "too few answers to find themes"
        base.notes.append(f"Needs at least {MIN_TEXTS} written answers.")
        return base

    # Embed each distinct answer once; identical answers share a vector.
    unique = list(dict.fromkeys(useful))
    unique_vectors = embedder.encode(unique)
    index = {t: i for i, t in enumerate(unique)}
    vectors = unique_vectors[[index[t] for t in useful]]

    k, labels, silhouette = choose_k(vectors, seed=seed)
    by_theme: dict[int, list[int]] = {}
    for i, label in enumerate(labels):
        by_theme.setdefault(int(label), []).append(i)
    keywords = ctfidf_keywords({t: [useful[i] for i in rows] for t, rows in by_theme.items()})

    themes: list[Theme] = []
    for theme_id, rows in by_theme.items():
        texts = [useful[i] for i in rows]
        picked = pick_quotes(texts, vectors[rows])
        quotes = [ThemeQuote(texts[j], language_of(texts[j])) for j in picked]
        words = keywords.get(theme_id, [])
        themes.append(Theme(
            id=theme_id,
            label=" · ".join(words[:3]) if words else quotes[0].text[:40],
            keywords=words,
            size=len(rows),
            percent=round(100 * len(rows) / len(useful), 1),
            quotes=quotes,
            languages=dict(Counter(language_of(t) for t in texts)),
            sentiment=summarise_sentiment(texts),
        ))
    themes.sort(key=lambda t: -t.size)
    for new_id, theme in enumerate(themes):
        theme.id = new_id

    base.k, base.silhouette = k, None if silhouette is None else round(silhouette, 3)
    base.quality = silhouette_quality(silhouette)
    base.themes = themes
    if n_filler:
        base.notes.append(f"{n_filler} filler answers (such as “N/A” or “nothing”) were left out.")
    return base


def build_themes(df: pd.DataFrame, text_columns: list[str], embedder: Embedder,
                 model_name: str = MODEL_NAME) -> ThemesReport:
    """Themes for every free-text column."""
    return ThemesReport(model_name, [find_themes(df[c], embedder) for c in text_columns
                                     if c in df.columns])
