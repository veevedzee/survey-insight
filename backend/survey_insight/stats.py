"""Descriptive statistics, scale reliability and group comparisons.

Principles
----------
* **The data type picks the test**, never the result. Likert answers are
  ordinal (the gap between "Agree" and "Strongly agree" is not a known
  distance), so they get rank-based tests. Means-based tests (t-test, ANOVA)
  are used only for numeric data whose assumptions we checked.
* **Effect size beside every p-value.** With 300 people a trivial difference
  can be "significant"; the effect size says whether it matters.
* **Correct for many tests.** We run dozens of comparisons, so p-values are
  adjusted with the Holm method before anything is called significant.
* **Plain English, no overclaiming.** "No significant difference" is never
  phrased as "the groups are the same", and correlations never imply cause.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats as sps

from survey_insight.loading import ColumnProfile, ColumnType, likert_group, likert_score

ALPHA = 0.05  # significance level, after Holm correction
MIN_GROUP_SIZE = 5  # smaller groups are left out of comparisons
MAX_GROUPS = 8
RELIABLE_ALPHA = 0.7  # Cronbach's alpha needed to combine items into a scale score

# Conventional thresholds (small, medium, large).
# Cohen (1988) for d, r and V; Tomczak & Tomczak (2014) for epsilon squared.
EFFECT_THRESHOLDS: dict[str, tuple[float, float, float]] = {
    "cohens_d": (0.2, 0.5, 0.8),
    "rank_biserial": (0.1, 0.3, 0.5),
    "eta_squared": (0.01, 0.06, 0.14),
    "epsilon_squared": (0.01, 0.08, 0.26),
    "spearman_rho": (0.1, 0.3, 0.5),
    "cramers_v_df1": (0.1, 0.3, 0.5),
    "cramers_v_df2": (0.07, 0.21, 0.35),
    "cramers_v_df3": (0.06, 0.17, 0.29),
}


# --------------------------------------------------------------------------- #
# Small building blocks (each one tested against known answers)
# --------------------------------------------------------------------------- #
def effect_label(value: float, thresholds: tuple[float, float, float]) -> str:
    """Describe an effect size in words: negligible, small, medium or large.

    Anything below the "small" threshold is "negligible": with a big sample a
    tiny difference can be statistically significant, and calling r = 0.02 a
    "small effect" would overclaim.
    """
    small, medium, large = thresholds
    size = round(abs(value), 2)  # judge the same rounded number the user sees
    if size >= large:
        return "large"
    if size >= medium:
        return "medium"
    if size >= small:
        return "small"
    return "negligible"


def holm_adjust(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (same order as the input).

    Sort p-values from smallest to largest; multiply the i-th smallest by
    (m - i), where m is the number of tests and i starts at 0; then make the
    sequence non-decreasing and cap it at 1. Less conservative than Bonferroni
    but still controls the chance of *any* false positive.
    """
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running_max = 0.0
    for rank, i in enumerate(order):
        value = min(1.0, (m - rank) * p_values[i])
        running_max = max(running_max, value)
        adjusted[i] = running_max
    return adjusted


def cronbach_alpha(items: pd.DataFrame) -> float:
    """Cronbach's alpha for a respondents x items matrix with no missing values.

    alpha = k / (k - 1) * (1 - sum of item variances / variance of total score)

    It rises when items move together (people who agree with one item agree
    with the others), i.e. when they seem to measure the same thing.
    """
    k = items.shape[1]
    if k < 2 or len(items) < 2:
        raise ValueError("Need at least 2 items and 2 respondents.")
    item_var = items.var(axis=0, ddof=1).sum()
    total_var = items.sum(axis=1).var(ddof=1)
    if total_var == 0:
        return float("nan")
    return float(k / (k - 1) * (1 - item_var / total_var))


def alpha_label(alpha: float) -> str:
    """Conventional wording for Cronbach's alpha (George & Mallery)."""
    if math.isnan(alpha):
        return "not computable"
    alpha = round(alpha, 2)  # judge the same rounded number the user sees
    for cut, label in ((0.9, "excellent"), (0.8, "good"), (0.7, "acceptable"),
                       (0.6, "questionable"), (0.5, "poor")):
        if alpha >= cut:
            return label
    return "unacceptable"


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Standardised mean difference using the pooled standard deviation."""
    n1, n2 = len(a), len(b)
    pooled = math.sqrt(((n1 - 1) * a.var(ddof=1) + (n2 - 1) * b.var(ddof=1)) / (n1 + n2 - 2))
    return float((a.mean() - b.mean()) / pooled) if pooled > 0 else 0.0


def rank_biserial(u_statistic: float, n1: int, n2: int) -> float:
    """Rank-biserial correlation from Mann-Whitney U (for the first group).

    +1: every value in group 1 is higher than every value in group 2; 0: no
    tendency either way. It equals P(a > b) - P(a < b) for random picks.
    """
    return float(2 * u_statistic / (n1 * n2) - 1)


def cramers_v(table: np.ndarray) -> float:
    """Cramér's V: strength of association in a contingency table (0 to 1)."""
    chi2 = sps.chi2_contingency(table, correction=False)[0]
    n = table.sum()
    dof = min(table.shape) - 1
    return float(math.sqrt(chi2 / (n * dof))) if n and dof else 0.0


def format_p(p: float) -> str:
    return "p < .001" if p < 0.001 else f"p = {p:.3f}".replace("0.", ".", 1)


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #
@dataclass
class ChoiceCount:
    label: str
    count: int
    percent: float


@dataclass
class HistogramBin:
    start: float
    end: float
    count: int


@dataclass
class NumericSummary:
    mean: float
    sd: float
    median: float
    q1: float
    q3: float
    min: float
    max: float
    histogram: list[HistogramBin]
    discrete: bool = False  # one bin per possible value (label bins by their value)


@dataclass
class LikertSummary:
    median_label: str
    mean_score: float
    agree_percent: float  # top two levels
    disagree_percent: float  # bottom two levels


@dataclass
class QuestionSummary:
    """Descriptive statistics for one question."""

    column: str
    label: str  # short label: the item text for grid columns
    type: ColumnType
    n: int
    n_missing: int
    scale_group: str | None = None
    counts: list[ChoiceCount] | None = None  # choice / Likert distributions
    numeric: NumericSummary | None = None
    likert: LikertSummary | None = None


@dataclass
class ItemStat:
    column: str
    label: str
    item_total_r: float  # correlation with the sum of the *other* items
    alpha_if_deleted: float


@dataclass
class ScaleResult:
    """Reliability of a group of Likert items (a grid)."""

    name: str  # the full grid question
    label: str  # short display name
    items: list[ItemStat]
    n_complete: int
    alpha: float
    interpretation: str
    reliable: bool
    score_column: str | None  # name of the averaged score, if reliable
    warnings: list[str] = field(default_factory=list)


@dataclass
class GroupStat:
    group: str
    n: int
    median: float | None = None
    mean: float | None = None
    q1: float | None = None
    q3: float | None = None
    # For categorical outcomes: the share choosing the most telling answer.
    percent: float | None = None
    # Answer distribution within the group (Likert levels or categories), for charts.
    distribution: list[ChoiceCount] | None = None


@dataclass
class Comparison:
    """One outcome compared across the groups of one variable."""

    outcome: str
    outcome_label: str
    outcome_kind: str  # likert | numeric | scale | categorical
    group_by: str
    test: str
    test_reason: str
    statistic: float
    p_value: float
    p_adjusted: float
    significant: bool
    effect_name: str
    effect_size: float
    effect_label: str
    n_total: int
    groups: list[GroupStat]
    sentence: str = ""
    warnings: list[str] = field(default_factory=list)
    # For charts: answer order (Likert levels / categories) and the value axis range.
    levels: list[str] | None = None
    axis_min: float | None = None
    axis_max: float | None = None


@dataclass
class Correlation:
    x: str
    y: str
    x_label: str
    y_label: str
    rho: float
    p_value: float
    p_adjusted: float
    significant: bool
    effect_label: str
    n: int
    sentence: str = ""


@dataclass
class StatsReport:
    n_responses: int
    questions: list[QuestionSummary]
    scales: list[ScaleResult]
    comparisons: list[Comparison]
    correlations: list[Correlation]
    notes: list[str]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def short_label(column: str) -> str:
    """The item text of a grid column ("Q [item]" -> "item"), else the column."""
    group = likert_group(column)
    return column[len(group):].strip().strip("[]").strip() if group else column


def likert_numeric(series: pd.Series, levels: list[str]) -> pd.Series:
    """Likert answers as numbers on their scale."""
    return series.map(lambda v: likert_score(v, levels)).astype(float)


def _levels_for(profile: ColumnProfile | None, series: pd.Series) -> list[str]:
    if profile is not None and profile.likert_levels:
        return profile.likert_levels
    numbers = pd.to_numeric(series, errors="coerce").dropna()
    if numbers.empty:
        return []
    return [str(i) for i in range(int(numbers.min()), int(numbers.max()) + 1)]


def _round(x: float, digits: int = 3) -> float:
    return float(round(x, digits)) if x is not None and not math.isnan(x) else float("nan")


# --------------------------------------------------------------------------- #
# Descriptives
# --------------------------------------------------------------------------- #
def describe_question(series: pd.Series, kind: ColumnType,
                      profile: ColumnProfile | None = None) -> QuestionSummary:
    """Summarise one question according to its type."""
    present = series.dropna()
    summary = QuestionSummary(series.name, short_label(str(series.name)), kind, len(present),
                              int(series.isna().sum()),
                              scale_group=profile.scale_group if profile else None)
    if present.empty:
        return summary

    if kind == ColumnType.SINGLE_CHOICE:
        counts = present.astype(str).value_counts()
        summary.counts = [ChoiceCount(str(k), int(v), _round(100 * v / len(present), 1))
                          for k, v in counts.items()]
    elif kind == ColumnType.MULTIPLE_CHOICE:
        options = present.astype(str).str.split(",").explode().str.strip()
        counts = options[options != ""].value_counts()
        # Percent of respondents (not of ticks): totals can exceed 100%.
        summary.counts = [ChoiceCount(str(k), int(v), _round(100 * v / len(present), 1))
                          for k, v in counts.items()]
    elif kind == ColumnType.LIKERT:
        levels = _levels_for(profile, present)
        scores = likert_numeric(present, levels).dropna()
        summary.n = len(scores)
        summary.counts = [
            ChoiceCount(level, int((scores == i + float(_first_level(levels))).sum()),
                        _round(100 * (scores == i + float(_first_level(levels))).mean(), 1))
            for i, level in enumerate(levels)
        ]
        if len(scores):
            offset = _first_level(levels)
            median_index = int(round(float(scores.median()) - offset))
            median_index = min(max(median_index, 0), len(levels) - 1)
            summary.likert = LikertSummary(
                median_label=levels[median_index],
                mean_score=_round(float(scores.mean()), 2),
                agree_percent=_round(100 * float((scores >= offset + len(levels) - 2).mean()), 1),
                disagree_percent=_round(100 * float((scores <= offset + 1).mean()), 1),
            )
    elif kind == ColumnType.NUMERIC:
        x = pd.to_numeric(present, errors="coerce").dropna().astype(float)
        summary.n = len(x)
        if len(x):
            summary.numeric = _numeric_summary(x)
    return summary


def _first_level(levels: list[str]) -> int:
    """Numeric value of the lowest level (1 for text scales)."""
    return int(levels[0]) if levels and levels[0].lstrip("-").isdigit() else 1


def _grid_step(x: pd.Series) -> float | None:
    """The step answers are given in (1 for ages, 0.5 for "6.5 hours"), if there is one."""
    values = np.unique(x.to_numpy(dtype=float))
    if len(values) < 2:
        return None
    for step in (1.0, 0.5, 0.25, 0.1):
        offsets = (values - values[0]) / step
        if np.allclose(offsets, np.round(offsets), atol=1e-6):
            return step
    return None


def _numeric_summary(x: pd.Series) -> NumericSummary:
    """Summary statistics plus histogram bins.

    Answers given on a regular grid (whole numbers, half hours...) with at most
    30 steps get one bin per possible value. numpy's "auto" rule would otherwise
    cut bins narrower than the grid, leaving every other bin empty (a "comb").
    """
    low, high = float(x.min()), float(x.max())
    step = _grid_step(x)
    discrete = step is not None and (high - low) / step <= 30
    if discrete:
        edges = low + step * np.arange(round((high - low) / step) + 2)
    else:
        edges = np.histogram_bin_edges(x, bins="auto")
        if len(edges) > 21:
            edges = np.histogram_bin_edges(x, bins=20)
    counts, edges = np.histogram(x, bins=edges)
    return NumericSummary(
        mean=_round(float(x.mean()), 2), sd=_round(float(x.std(ddof=1)) if len(x) > 1 else 0.0, 2),
        median=_round(float(x.median()), 2), q1=_round(float(x.quantile(0.25)), 2),
        q3=_round(float(x.quantile(0.75)), 2), min=_round(float(x.min()), 2),
        max=_round(float(x.max()), 2),
        histogram=[HistogramBin(_round(float(a), 2), _round(float(b), 2), int(c))
                   for a, b, c in zip(edges[:-1], edges[1:], counts, strict=True)],
        discrete=discrete,
    )


# --------------------------------------------------------------------------- #
# Scales
# --------------------------------------------------------------------------- #
def analyse_scale(name: str, items: pd.DataFrame) -> ScaleResult:
    """Cronbach's alpha plus per-item diagnostics for one Likert grid.

    ``items`` holds numeric scores (one column per item). Respondents with any
    missing item are left out of alpha (listwise deletion).
    """
    complete = items.dropna()
    warnings: list[str] = []
    label = scale_label(name)
    if items.shape[1] < 2 or len(complete) < 10:
        return ScaleResult(name, label, [], len(complete), float("nan"), "not computable", False,
                           None, ["Needs at least 2 items and 10 complete responses."])
    alpha = cronbach_alpha(complete)
    item_stats: list[ItemStat] = []
    for col in complete.columns:
        rest = complete.drop(columns=col)
        r = complete[col].corr(rest.sum(axis=1))
        a_del = cronbach_alpha(rest) if rest.shape[1] >= 2 else float("nan")
        item_stats.append(ItemStat(col, short_label(col), _round(float(r)), _round(a_del)))
        if r < 0:
            warnings.append(f"“{short_label(col)}” moves against the other items. It may be "
                            "worded in reverse and need reverse-scoring.")
        elif not math.isnan(a_del) and a_del > alpha + 0.05:
            warnings.append(f"Removing “{short_label(col)}” would raise alpha to {a_del:.2f}.")
    reliable = not math.isnan(alpha) and alpha >= RELIABLE_ALPHA
    if not reliable:
        warnings.append(f"Alpha is below {RELIABLE_ALPHA}, so items are analysed one by one "
                        "instead of as a combined score.")
    return ScaleResult(name, label, item_stats, len(complete), _round(alpha), alpha_label(alpha),
                       reliable, f"Scale score: {label}" if reliable else None, warnings)


def scale_label(question: str) -> str:
    """Short name for a grid: drop bracketed notes and trailing punctuation.

    "Study habits (1 = Strongly disagree, 5 = Strongly agree)" -> "Study habits"
    """
    text = re.sub(r"\s*\([^)]*\)", "", question).strip().rstrip("?:.").strip()
    return text or question


def scale_scores(items: pd.DataFrame) -> pd.Series:
    """Mean item score per respondent, if they answered at least half the items."""
    enough = items.notna().sum(axis=1) >= math.ceil(items.shape[1] / 2)
    return items.mean(axis=1).where(enough)


# --------------------------------------------------------------------------- #
# Group comparisons
# --------------------------------------------------------------------------- #
def _assumptions_hold(groups: list[np.ndarray]) -> tuple[bool, str]:
    """Check whether a means-based test is appropriate for these groups.

    Each group must look roughly normal: Shapiro-Wilk p >= .05 for small groups
    (n < 30); for larger groups, where Shapiro-Wilk flags even harmless
    deviations, the central limit theorem helps and we only require
    |skewness| < 1.
    """
    for g in groups:
        if len(g) < 3 or np.ptp(g) == 0:
            return False, "a group is too small or has no variation"
        if len(g) < 30:
            if sps.shapiro(g).pvalue < 0.05:
                return False, "a small group is clearly not normally distributed"
        elif abs(sps.skew(g)) >= 1:
            return False, "a group is strongly skewed"
    return True, "groups look roughly normal"


def compare_ordinal(values: pd.Series, groups: pd.Series) -> Comparison:
    """Mann-Whitney U (2 groups) or Kruskal-Wallis H (3+ groups) for ordinal data."""
    data = _group_arrays(values, groups)
    names = list(data)
    arrays = list(data.values())
    n_total = sum(len(a) for a in arrays)
    stats_ = _group_stats(data)
    if len(arrays) == 2:
        res = sps.mannwhitneyu(arrays[0], arrays[1], alternative="two-sided")
        effect = rank_biserial(res.statistic, len(arrays[0]), len(arrays[1]))
        return Comparison("", "", "", "", "Mann-Whitney U",
                          "Two groups, ordinal or non-normal data: compares ranks, not means.",
                          _round(float(res.statistic)), float(res.pvalue), float(res.pvalue),
                          False, "rank-biserial r", _round(effect),
                          effect_label(effect, EFFECT_THRESHOLDS["rank_biserial"]), n_total,
                          stats_)
    res = sps.kruskal(*arrays)
    eps2 = float(res.statistic) / (n_total - 1)
    return Comparison("", "", "", "", "Kruskal-Wallis H",
                      f"{len(names)} groups, ordinal or non-normal data: compares ranks.",
                      _round(float(res.statistic)), float(res.pvalue), float(res.pvalue), False,
                      "epsilon²", _round(eps2),
                      effect_label(eps2, EFFECT_THRESHOLDS["epsilon_squared"]), n_total, stats_)


def compare_numeric(values: pd.Series, groups: pd.Series) -> Comparison:
    """Welch's t-test / one-way ANOVA when assumptions hold, else rank-based tests."""
    data = _group_arrays(values, groups)
    arrays = list(data.values())
    ok, why = _assumptions_hold(arrays)
    if len(arrays) >= 3 and ok:
        levene_p = sps.levene(*arrays).pvalue
        if levene_p < 0.05:
            ok, why = False, "group variances differ (Levene's test)"
    if not ok:
        result = compare_ordinal(values, groups)
        result.test_reason = f"Rank-based test because {why}."
        return result

    n_total = sum(len(a) for a in arrays)
    stats_ = _group_stats(data)
    if len(arrays) == 2:
        res = sps.ttest_ind(arrays[0], arrays[1], equal_var=False)
        d = cohens_d(arrays[0], arrays[1])
        return Comparison("", "", "", "", "Welch's t-test",
                          f"Two groups, numeric data, {why}; Welch's version does not assume "
                          "equal variances.", _round(float(res.statistic)), float(res.pvalue),
                          float(res.pvalue), False, "Cohen's d", _round(d),
                          effect_label(d, EFFECT_THRESHOLDS["cohens_d"]), n_total, stats_)
    res = sps.f_oneway(*arrays)
    grand = np.concatenate(arrays).mean()
    ss_between = sum(len(a) * (a.mean() - grand) ** 2 for a in arrays)
    ss_total = sum(((a - grand) ** 2).sum() for a in arrays)
    eta2 = float(ss_between / ss_total) if ss_total else 0.0
    return Comparison("", "", "", "", "One-way ANOVA",
                      f"{len(arrays)} groups, numeric data, {why} and similar variances.",
                      _round(float(res.statistic)), float(res.pvalue), float(res.pvalue), False,
                      "eta²", _round(eta2), effect_label(eta2, EFFECT_THRESHOLDS["eta_squared"]),
                      n_total, stats_)


def compare_categorical(outcome: pd.Series, groups: pd.Series) -> tuple[Comparison, str]:
    """Chi-square test of independence (Fisher's exact test for small 2x2 tables).

    Returns the comparison and the "most telling" answer: the one whose share
    differs most from what we'd expect if the variables were unrelated, used to
    give the plain-English sentence a concrete example.
    """
    mask = outcome.notna() & groups.notna()
    table = pd.crosstab(groups[mask], outcome[mask])
    table = table.loc[table.sum(axis=1) >= MIN_GROUP_SIZE]
    table = table.loc[:, table.sum(axis=0) > 0]
    observed = table.to_numpy()
    n_total = int(observed.sum())
    if observed.shape[0] < 2 or observed.shape[1] < 2:
        raise ValueError("Need at least a 2x2 table.")
    chi2, p, dof, expected = sps.chi2_contingency(observed, correction=False)
    warnings: list[str] = []
    test = "Chi-square test"
    reason = "Both variables are categories: tests whether they are related."
    small_cells = float((expected < 5).mean())
    if small_cells > 0.2:
        if observed.shape == (2, 2):
            p = float(sps.fisher_exact(observed).pvalue)
            test, reason = "Fisher's exact test", "A 2x2 table with small expected counts."
        else:
            warnings.append(f"{small_cells:.0%} of cells have expected counts below 5, so this "
                            "p-value is approximate.")
    v = cramers_v(observed)
    df_star = min(min(observed.shape) - 1, 3)
    label = effect_label(v, EFFECT_THRESHOLDS[f"cramers_v_df{df_star}"])

    # The most telling cell: where observed most exceeds what independence predicts.
    residuals = (observed - expected) / np.sqrt(expected)
    _, col_index = np.unravel_index(np.argmax(residuals), residuals.shape)
    answer = str(table.columns[col_index])
    percents = 100 * observed[:, col_index] / observed.sum(axis=1)
    # Categories in overall-frequency order, so every group's bar uses the same order.
    order = list(table.sum(axis=0).sort_values(ascending=False).index)
    stats_ = []
    for g, n, pct in zip(table.index, observed.sum(axis=1), percents, strict=True):
        row = table.loc[g]
        stats_.append(GroupStat(
            str(g), int(n), percent=_round(float(pct), 1),
            distribution=[ChoiceCount(str(c), int(row[c]), _round(100 * row[c] / n, 1))
                          for c in order]))
    result = Comparison("", "", "categorical", "", test, reason, _round(float(chi2)), float(p),
                        float(p), False, "Cramér's V", _round(v), label, n_total, stats_,
                        warnings=warnings, levels=[str(c) for c in order])
    return result, answer


def _group_stats(data: dict[str, np.ndarray]) -> list[GroupStat]:
    return [GroupStat(k, len(v), median=_round(float(np.median(v)), 2),
                      mean=_round(float(v.mean()), 2),
                      q1=_round(float(np.quantile(v, 0.25)), 2),
                      q3=_round(float(np.quantile(v, 0.75)), 2))
            for k, v in data.items()]


def _group_arrays(values: pd.Series, groups: pd.Series) -> dict[str, np.ndarray]:
    mask = values.notna() & groups.notna()
    data = {str(g): v.to_numpy(dtype=float) for g, v in values[mask].groupby(groups[mask])}
    data = {g: v for g, v in data.items() if len(v) >= MIN_GROUP_SIZE}
    if len(data) < 2:
        raise ValueError("Fewer than two groups with enough responses.")
    return data


def _add_chart_data(result: Comparison, kind: str, values: pd.Series, groups: pd.Series,
                    levels: list[str] | None) -> None:
    """Attach what the frontend needs to draw this comparison."""
    if kind == "likert" and levels:
        offset = _first_level(levels)
        result.levels = levels
        for g in result.groups:
            scores = values[(groups == g.group) & values.notna()]
            g.distribution = [
                ChoiceCount(level, int((scores == offset + i).sum()),
                            _round(100 * float((scores == offset + i).mean()), 1))
                for i, level in enumerate(levels)
            ]
    elif kind == "scale" and levels:
        result.axis_min, result.axis_max = float(_first_level(levels)), \
            float(_first_level(levels) + len(levels) - 1)
    else:
        present = values.dropna()
        if len(present):
            result.axis_min, result.axis_max = float(present.min()), float(present.max())


# --------------------------------------------------------------------------- #
# Sentences
# --------------------------------------------------------------------------- #
def _comparison_sentence(c: Comparison, telling_answer: str | None = None) -> str:
    stat = f"{c.test}, {format_p(c.p_adjusted)} after correction, {c.effect_name} = " \
           f"{c.effect_size:.2f}"
    if c.outcome_kind == "categorical":
        ranked = sorted(c.groups, key=lambda g: g.percent or 0, reverse=True)
        hi, lo = ranked[0], ranked[-1]
        if not c.significant:
            return (f"No clear link between {c.group_by} and “{c.outcome_label}” ({stat}). "
                    "This does not prove there is none.")
        return (f"“{c.outcome_label}” is related to {c.group_by} ({c.effect_label} effect; "
                f"{stat}). For example, {hi.percent:.0f}% of {hi.group} (n = {hi.n}) answered "
                f"“{telling_answer}”, compared with {lo.percent:.0f}% of {lo.group} "
                f"(n = {lo.n}).")
    key = (lambda g: g.mean or 0) if c.test in ("Welch's t-test", "One-way ANOVA") else \
        (lambda g: (g.median or 0, g.mean or 0))
    ranked = sorted(c.groups, key=key, reverse=True)
    hi, lo = ranked[0], ranked[-1]
    centre = "mean" if c.test in ("Welch's t-test", "One-way ANOVA") else "median"
    hi_v = hi.mean if centre == "mean" else hi.median
    lo_v = lo.mean if centre == "mean" else lo.median
    if not c.significant:
        return (f"No clear difference in “{c.outcome_label}” across {c.group_by} ({stat}). "
                "This does not show the groups are the same, only that the data can't tell "
                "them apart.")
    return (f"“{c.outcome_label}” differs by {c.group_by} ({c.effect_label} effect; {stat}). "
            f"Highest: {hi.group} ({centre} {hi_v:g}, n = {hi.n}); lowest: {lo.group} "
            f"({centre} {lo_v:g}, n = {lo.n}).")


def _correlation_sentence(c: Correlation) -> str:
    stat = f"Spearman ρ = {c.rho:.2f}, {format_p(c.p_adjusted)} after correction, n = {c.n}"
    if not c.significant:
        return f"No clear relationship between “{c.x_label}” and “{c.y_label}” ({stat})."
    direction = "higher" if c.rho > 0 else "lower"
    return (f"People with higher “{c.x_label}” tend to have {direction} “{c.y_label}” "
            f"({c.effect_label} relationship; {stat}). This shows association, not cause.")


# --------------------------------------------------------------------------- #
# Everything together
# --------------------------------------------------------------------------- #
def build_stats(df: pd.DataFrame, types: dict[str, ColumnType],
                profiles: list[ColumnProfile]) -> StatsReport:
    """Run the full statistical analysis on the cleaned data."""
    by_name = {p.name: p for p in profiles}
    cols = [c for c in df.columns if c in types]
    notes: list[str] = []

    questions = [describe_question(df[c], types[c], by_name.get(c)) for c in cols
                 if types[c] in (ColumnType.SINGLE_CHOICE, ColumnType.MULTIPLE_CHOICE,
                                 ColumnType.LIKERT, ColumnType.NUMERIC)]

    # Numeric versions of Likert items, and scale scores for reliable grids.
    likert_cols = [c for c in cols if types[c] == ColumnType.LIKERT]
    likert_values = {c: likert_numeric(df[c], _levels_for(by_name.get(c), df[c]))
                     for c in likert_cols}
    grids: dict[str, list[str]] = {}
    for c in likert_cols:
        group = by_name[c].scale_group if c in by_name else None
        if group:
            grids.setdefault(group, []).append(c)
    scales: list[ScaleResult] = []
    scale_values: dict[str, pd.Series] = {}
    scale_levels: dict[str, list[str]] = {}  # score column -> its items' levels (axis range)
    for name, items in grids.items():
        if len(items) < 2:
            continue
        matrix = pd.DataFrame({c: likert_values[c] for c in items})
        result = analyse_scale(name, matrix)
        scales.append(result)
        if result.reliable and result.score_column:
            scale_values[result.score_column] = scale_scores(matrix)
            scale_levels[result.score_column] = _levels_for(by_name.get(items[0]), df[items[0]])

    # Group comparisons: every outcome against every grouping variable.
    group_cols = [c for c in cols if types[c] == ColumnType.SINGLE_CHOICE
                  and 2 <= df[c].dropna().astype(str).value_counts()
                  .loc[lambda s: s >= MIN_GROUP_SIZE].size <= MAX_GROUPS]
    numeric_cols = [c for c in cols if types[c] == ColumnType.NUMERIC]
    numeric_values = {c: pd.to_numeric(df[c], errors="coerce") for c in numeric_cols}

    comparisons: list[Comparison] = []
    telling: list[str | None] = []
    for g in group_cols:
        groups = df[g].astype("object").where(df[g].notna())
        outcomes: list[tuple[str, str, pd.Series]] = (
            [(c, "likert", likert_values[c]) for c in likert_cols]
            + [(c, "scale", s) for c, s in scale_values.items()]
            + [(c, "numeric", numeric_values[c]) for c in numeric_cols]
        )
        for name, kind, values in outcomes:
            try:
                result = (compare_ordinal(values, groups) if kind == "likert"
                          else compare_numeric(values, groups))
            except ValueError:
                continue
            result.outcome, result.outcome_kind, result.group_by = name, kind, g
            result.outcome_label = (name.removeprefix("Scale score: ") + " (scale score)"
                                    if kind == "scale" else short_label(name))
            _add_chart_data(result, kind, values, groups,
                            _levels_for(by_name.get(name), df[name]) if kind == "likert"
                            else scale_levels.get(name))
            comparisons.append(result)
            telling.append(None)
    for a, b in combinations(group_cols, 2):
        try:
            result, answer = compare_categorical(df[b], df[a])
        except ValueError:
            continue
        result.outcome, result.outcome_label, result.group_by = b, b, a
        comparisons.append(result)
        telling.append(answer)

    # Correlations between numeric answers and scale scores.
    continuous = {**{c: numeric_values[c] for c in numeric_cols}, **scale_values}
    correlations: list[Correlation] = []
    for x, y in combinations(continuous, 2):
        mask = continuous[x].notna() & continuous[y].notna()
        if mask.sum() < 10:
            continue
        rho, p = sps.spearmanr(continuous[x][mask], continuous[y][mask])
        if math.isnan(rho):
            continue
        correlations.append(Correlation(
            x, y, short_label(x).removeprefix("Scale score: "),
            short_label(y).removeprefix("Scale score: "), _round(float(rho)), float(p), float(p),
            False, effect_label(float(rho), EFFECT_THRESHOLDS["spearman_rho"]), int(mask.sum())))

    # One Holm correction across every test we ran.
    all_p = [c.p_value for c in comparisons] + [c.p_value for c in correlations]
    adjusted = holm_adjust(all_p) if all_p else []
    for c, p_adj in zip(comparisons + correlations, adjusted, strict=True):  # type: ignore[operator]
        c.p_adjusted = float(p_adj)
        c.significant = p_adj < ALPHA
    for c, answer in zip(comparisons, telling, strict=True):
        c.sentence = _comparison_sentence(c, answer)
    for c in correlations:
        c.sentence = _correlation_sentence(c)

    comparisons.sort(key=lambda c: (not c.significant, -abs(c.effect_size)))
    correlations.sort(key=lambda c: (not c.significant, -abs(c.rho)))
    if all_p:
        notes.append(f"{len(all_p)} tests were run, so p-values are Holm-adjusted to keep the "
                     "overall chance of a false positive at 5%.")
    notes.append(f"Groups with fewer than {MIN_GROUP_SIZE} responses are left out of comparisons.")
    return StatsReport(len(df), questions, scales, comparisons, correlations, notes)
