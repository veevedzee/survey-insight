"""Statistics on small datasets with answers worked out by hand."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from survey_insight.loading import ColumnProfile, ColumnType
from survey_insight.stats import (
    EFFECT_THRESHOLDS,
    alpha_label,
    analyse_scale,
    build_stats,
    cohens_d,
    compare_categorical,
    compare_numeric,
    compare_ordinal,
    cramers_v,
    cronbach_alpha,
    describe_question,
    effect_label,
    format_p,
    holm_adjust,
    rank_biserial,
    scale_label,
    scale_scores,
)

AGREE = ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"]


# --------------------------------------------------------------------------- #
# Building blocks with hand-computed answers
# --------------------------------------------------------------------------- #
def test_cronbach_alpha_by_hand() -> None:
    # a = [1,2,3], b = [1,3,2]: var(a) = var(b) = 1; totals [2,5,5] have var 3.
    # alpha = 2/1 * (1 - (1+1)/3) = 2/3
    items = pd.DataFrame({"a": [1, 2, 3], "b": [1, 3, 2]})
    assert cronbach_alpha(items) == pytest.approx(2 / 3)


def test_cronbach_alpha_identical_items_is_one() -> None:
    x = [1, 2, 3, 4, 5, 2]
    assert cronbach_alpha(pd.DataFrame({"a": x, "b": x, "c": x})) == pytest.approx(1.0)


def test_alpha_labels() -> None:
    assert alpha_label(0.84) == "good"
    assert alpha_label(0.65) == "questionable"
    assert alpha_label(0.795) == "good"  # shown as 0.80, so labelled as 0.80
    assert alpha_label(float("nan")) == "not computable"


def test_holm_adjustment_by_hand() -> None:
    # sorted: .01*3 = .03; .03*2 = .06; .04*1 = .04 -> raised to .06 (monotone)
    assert holm_adjust([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert holm_adjust([0.9, 0.8]) == pytest.approx([1.0, 1.0])


def test_cohens_d_by_hand() -> None:
    # means 2 and 4, both SDs 1 -> d = (2 - 4) / 1 = -2
    assert cohens_d(np.array([1.0, 2, 3]), np.array([3.0, 4, 5])) == pytest.approx(-2.0)


def test_rank_biserial_complete_separation() -> None:
    # Every value in group 1 is below every value in group 2: U1 = 0 -> r = -1.
    assert rank_biserial(0, 3, 3) == pytest.approx(-1.0)
    assert rank_biserial(4.5, 3, 3) == pytest.approx(0.0)


def test_cramers_v_by_hand() -> None:
    # chi2 = N(ad - bc)^2 / ((a+b)(c+d)(a+c)(b+d)) = 60 * 300^2 / 30^4 = 6.667
    # V = sqrt(6.667 / 60) = 1/3
    assert cramers_v(np.array([[10, 20], [20, 10]])) == pytest.approx(1 / 3)


def test_effect_labels() -> None:
    t = EFFECT_THRESHOLDS["cohens_d"]
    assert effect_label(0.85, t) == "large"
    assert effect_label(-0.55, t) == "medium"
    assert effect_label(0.25, t) == "small"
    assert effect_label(0.4999, t) == "medium"  # judged on the rounded value shown (0.50)


@pytest.mark.xfail(reason="TODO(you): add a 'negligible' category in effect_label", strict=False)
def test_effect_label_negligible() -> None:
    assert effect_label(0.05, EFFECT_THRESHOLDS["cohens_d"]) == "negligible"


def test_format_p() -> None:
    assert format_p(0.0004) == "p < .001"
    assert format_p(0.0312) == "p = .031"


def test_scale_label() -> None:
    assert scale_label("Study habits (1 = Strongly disagree, 5 = Strongly agree)") == "Study habits"
    assert scale_label("How satisfied are you?") == "How satisfied are you"


# --------------------------------------------------------------------------- #
# Test selection
# --------------------------------------------------------------------------- #
def test_two_group_ordinal_uses_mann_whitney() -> None:
    values = pd.Series([1, 2, 2, 3, 2, 4, 5, 4, 5, 5], dtype=float)
    groups = pd.Series(["A"] * 5 + ["B"] * 5)
    result = compare_ordinal(values, groups)
    assert result.test == "Mann-Whitney U"
    assert result.effect_size < 0  # group A lower
    assert result.effect_label == "large"


def test_three_group_ordinal_uses_kruskal_wallis() -> None:
    values = pd.Series([1, 2, 1, 2, 1, 3, 3, 4, 3, 3, 5, 4, 5, 5, 4], dtype=float)
    groups = pd.Series(["A"] * 5 + ["B"] * 5 + ["C"] * 5)
    result = compare_ordinal(values, groups)
    assert result.test == "Kruskal-Wallis H"
    assert result.effect_name == "epsilon²"
    assert result.p_value < 0.01


def test_normal_numeric_uses_welch_t_test() -> None:
    rng = np.random.default_rng(1)
    values = pd.Series(np.concatenate([rng.normal(10, 2, 40), rng.normal(12, 2, 40)]))
    groups = pd.Series(["A"] * 40 + ["B"] * 40)
    result = compare_numeric(values, groups)
    assert result.test == "Welch's t-test"
    assert result.effect_name == "Cohen's d"


def test_skewed_numeric_falls_back_to_rank_test() -> None:
    rng = np.random.default_rng(2)
    values = pd.Series(np.concatenate([rng.exponential(1, 40), rng.exponential(3, 40)]))
    groups = pd.Series(["A"] * 40 + ["B"] * 40)
    result = compare_numeric(values, groups)
    assert result.test == "Mann-Whitney U"
    assert "skewed" in result.test_reason


def test_numeric_three_groups_with_equal_variance_uses_anova() -> None:
    rng = np.random.default_rng(3)
    values = pd.Series(np.concatenate([rng.normal(m, 1, 40) for m in (5, 6, 7)]))
    groups = pd.Series(["A"] * 40 + ["B"] * 40 + ["C"] * 40)
    result = compare_numeric(values, groups)
    assert result.test == "One-way ANOVA"
    assert result.effect_name == "eta²"


def test_categorical_uses_chi_square_and_finds_telling_answer() -> None:
    groups = pd.Series(["Eng"] * 30 + ["Bus"] * 30)
    outcome = pd.Series(["Apartment"] * 20 + ["Family"] * 10 + ["Apartment"] * 10 + ["Family"] * 20)
    result, answer = compare_categorical(outcome, groups)
    assert result.test == "Chi-square test"
    assert result.effect_size == pytest.approx(1 / 3, abs=1e-3)
    assert answer in ("Apartment", "Family")


def test_small_2x2_uses_fisher_exact() -> None:
    groups = pd.Series(["A"] * 6 + ["B"] * 6)
    outcome = pd.Series(["yes"] * 5 + ["no"] + ["no"] * 5 + ["yes"])
    result, _ = compare_categorical(outcome, groups)
    assert result.test == "Fisher's exact test"


def test_small_groups_are_left_out() -> None:
    values = pd.Series([1, 2, 3, 4, 5, 1, 2, 3, 4, 5, 9, 9], dtype=float)
    groups = pd.Series(["A"] * 5 + ["B"] * 5 + ["Tiny"] * 2)
    result = compare_ordinal(values, groups)
    assert {g.group for g in result.groups} == {"A", "B"}


# --------------------------------------------------------------------------- #
# Descriptives and scales
# --------------------------------------------------------------------------- #
def test_likert_description_counts_every_level_in_order() -> None:
    series = pd.Series(["Agree", "Agree", "Strongly agree", "Disagree", None], name="Q")
    profile = ColumnProfile("Q", ColumnType.LIKERT, "", 1, 3, [], likert_levels=AGREE)
    summary = describe_question(series, ColumnType.LIKERT, profile)
    assert [c.count for c in summary.counts] == [0, 1, 0, 2, 1]
    assert summary.likert.agree_percent == 75.0
    assert summary.likert.median_label == "Agree"


def test_multiple_choice_percent_of_respondents() -> None:
    series = pd.Series(["Notes, Videos", "Notes", "Videos, Notes, Books"], name="M")
    summary = describe_question(series, ColumnType.MULTIPLE_CHOICE)
    counts = {c.label: c.percent for c in summary.counts}
    assert counts["Notes"] == 100.0 and counts["Books"] == pytest.approx(33.3)


def test_numeric_description() -> None:
    summary = describe_question(pd.Series(["1", "2", "3", "4", "100"], name="N"),
                                ColumnType.NUMERIC)
    assert summary.numeric.median == 3
    assert sum(b.count for b in summary.numeric.histogram) == 5


def test_half_hour_answers_get_one_bin_per_value() -> None:
    hours = ["6", "6.5", "7", "7", "8.5", "6.5", "9"]
    summary = describe_question(pd.Series(hours, name="Sleep"), ColumnType.NUMERIC).numeric
    assert summary.discrete
    assert [b.start for b in summary.histogram] == [6, 6.5, 7, 7.5, 8, 8.5, 9]
    assert [b.count for b in summary.histogram] == [1, 2, 2, 0, 0, 1, 1]


def test_reverse_worded_item_is_flagged() -> None:
    rng = np.random.default_rng(4)
    trait = rng.normal(size=60)
    items = pd.DataFrame({
        f"Q [item {i}]": np.clip(np.round(3 + trait + rng.normal(0, 0.5, 60)), 1, 5)
        for i in range(3)
    })
    items["Q [reversed]"] = 6 - items["Q [item 0]"]
    result = analyse_scale("Q", items)
    assert any("reverse" in w for w in result.warnings)


def test_scale_scores_need_half_the_items() -> None:
    items = pd.DataFrame({"a": [4, 4, None], "b": [2, None, None], "c": [3, None, 5.0]})
    scores = scale_scores(items)
    assert scores[0] == 3 and math.isnan(scores[1]) and math.isnan(scores[2])


def test_build_stats_end_to_end_with_planted_effect() -> None:
    rng = np.random.default_rng(5)
    n = 120
    faculty = np.where(np.arange(n) < 60, "Engineering", "Business")
    latent = np.where(faculty == "Engineering", 1.0, -0.5) + rng.normal(0, 0.8, n)
    df = pd.DataFrame({"Faculty": faculty})
    profiles = [ColumnProfile("Faculty", ColumnType.SINGLE_CHOICE, "", 0, 2, [])]
    types = {"Faculty": ColumnType.SINGLE_CHOICE}
    for i in range(4):
        col = f"Stress [item {i}]"
        idx = np.clip(np.round(2 + latent + rng.normal(0, 0.6, n)), 0, 4).astype(int)
        df[col] = [AGREE[j] for j in idx]
        profiles.append(ColumnProfile(col, ColumnType.LIKERT, "", 0, 5, [], scale_group="Stress",
                                      likert_levels=AGREE))
        types[col] = ColumnType.LIKERT

    report = build_stats(df, types, profiles)

    assert report.scales[0].reliable and report.scales[0].alpha > 0.7
    scale = next(c for c in report.comparisons if c.outcome_kind == "scale")
    assert scale.significant
    assert "Engineering" in scale.sentence.split("Highest:")[1].split(";")[0]
    assert all(c.p_adjusted >= c.p_value for c in report.comparisons)

    # Chart data: scale scores get a 1-5 axis; Likert items get per-group distributions.
    assert (scale.axis_min, scale.axis_max) == (1.0, 5.0)
    item = next(c for c in report.comparisons if c.outcome_kind == "likert")
    assert item.levels == AGREE
    for g in item.groups:
        assert sum(d.count for d in g.distribution) == g.n
