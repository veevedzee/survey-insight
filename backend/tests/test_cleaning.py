"""Data-quality checks on tiny datasets where we know the right answer."""

from __future__ import annotations

import pandas as pd
import pytest

from survey_insight.cleaning import (
    apply_cleaning,
    build_report,
    find_duplicates,
    find_incomplete,
    find_outliers,
    find_speeders,
    find_straight_lining,
    normalize_choices,
    speeder_cutoff_seconds,
)
from survey_insight.loading import ColumnProfile, ColumnType

AGREE = ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"]


def likert_profile(name: str, group: str, levels: list[str] = AGREE) -> ColumnProfile:
    return ColumnProfile(name, ColumnType.LIKERT, "", 0, 0, [], scale_group=group,
                         likert_levels=levels)


# --------------------------------------------------------------------------- #
def test_normalize_merges_case_and_spacing_into_most_common_spelling() -> None:
    df = pd.DataFrame({
        "Faculty": ["Engineering", "Engineering", "engineering", "ENGINEERING", "Business"],
        "Methods": ["Notes, videos", "Notes; Videos", "notes", "Videos", "Notes"],
    })
    types = {"Faculty": ColumnType.SINGLE_CHOICE, "Methods": ColumnType.MULTIPLE_CHOICE}
    out, report = normalize_choices(df, types)
    assert out["Faculty"].tolist() == ["Engineering"] * 4 + ["Business"]
    assert out["Methods"].tolist()[2] == "Notes"
    assert report[0].column == "Faculty" and report[0].n_changed == 2


def test_duplicates_keep_the_first_copy() -> None:
    df = pd.DataFrame({"q1": ["a", "b", "a", "a"], "q2": ["x", "y", "x", None]})
    check = find_duplicates(df, ["q1", "q2"])
    assert check.flagged_rows == [2]  # row 3 has a blank, so it is not identical
    assert "response #1" in check.examples[0].detail


def test_incomplete_uses_share_of_closed_questions() -> None:
    df = pd.DataFrame({
        "q1": ["a", "a", None], "q2": ["b", None, None], "q3": ["c", "c", None],
        "q4": ["d", "d", "d"], "q5": ["e", "e", None],
    })
    check = find_incomplete(df, ["q1", "q2", "q3", "q4", "q5"])
    assert check.flagged_rows == [2]  # 1/5 answered; row 1 has 4/5 = 80%, which is enough


def test_straight_lining_needs_every_grid_flat() -> None:
    profiles = [likert_profile(f"A{i}", "Grid A") for i in range(4)]
    profiles += [likert_profile(f"B{i}", "Grid B", ["1", "2", "3", "4", "5"]) for i in range(3)]
    # Grid A: everyone answers "Agree" to all 4 items.
    # Grid B: row 0 flat (4,4,4), row 1 varied (1,5,3), row 2 flat (2,2,2).
    grid_b = {"B0": ["4", "1", "2"], "B1": ["4", "5", "2"], "B2": ["4", "3", "2"]}
    df = pd.DataFrame({**{f"A{i}": ["Agree"] * 3 for i in range(4)}, **grid_b})
    check = find_straight_lining(df, profiles)
    assert check.flagged_rows == [0, 2]


def test_straight_lining_unavailable_without_grids() -> None:
    df = pd.DataFrame({"Q": ["Agree"]})
    check = find_straight_lining(df, [likert_profile("Q", "Only one item")])
    assert not check.available


def test_speeders_flag_very_fast_responses() -> None:
    starts = pd.Timestamp("2026-03-01 10:00")
    seconds = [600, 540, 660, 610, 30, 580]
    df = pd.DataFrame({
        "Start time": [str(starts)] * 6,
        "Completion time": [str(starts + pd.Timedelta(seconds=s)) for s in seconds],
    })
    check = find_speeders(df, ["Start time", "Completion time"])
    assert check.available
    assert check.flagged_rows == [4]


def test_speeders_unavailable_with_single_timestamp() -> None:
    df = pd.DataFrame({"Timestamp": ["2026-03-01 10:00"] * 6})
    check = find_speeders(df, ["Timestamp"])
    assert not check.available
    assert "Google Forms" in (check.unavailable_reason or "")


def test_speeder_cutoff_is_relative_to_median() -> None:
    short_survey = pd.Series([150.0, 180.0, 210.0])  # median 3 min
    long_survey = pd.Series([1500.0, 1800.0, 2100.0])  # median 30 min
    assert speeder_cutoff_seconds(short_survey) == pytest.approx(60)
    assert speeder_cutoff_seconds(long_survey) == pytest.approx(600)


def test_outliers_use_iqr_not_standard_deviation() -> None:
    ages = [19, 20, 20, 21, 21, 21, 22, 22, 23, 24, 199, 2]
    df = pd.DataFrame({"Age": [str(a) for a in ages]})
    check, cells = find_outliers(df, ["Age"])
    assert cells == {"Age": [10, 11]}
    assert check.action == "blank"


def test_apply_cleaning_drops_rows_and_blanks_outliers() -> None:
    df = pd.DataFrame({
        "Faculty": ["Engineering", "Business", "Engineering", "Business"] * 3,
        "Age": [str(a) for a in range(18, 29)] + ["300"],  # all different, one typo
    })
    df.loc[5] = df.loc[4]  # duplicate of row 4
    types = {"Faculty": ColumnType.SINGLE_CHOICE, "Age": ColumnType.NUMERIC}
    data, report = build_report(df, types, [])

    cleaned, result = apply_cleaning(data, report, ["duplicates", "outliers"])
    assert result.n_before == 12 and result.n_after == 11
    assert result.n_values_blanked == 1
    assert 5 not in cleaned.index
    assert pd.isna(cleaned.loc[11, "Age"])

    untouched, result = apply_cleaning(data, report, [])
    assert result.n_after == 12 and untouched.loc[11, "Age"] == "300"


def test_apply_cleaning_rejects_unknown_check() -> None:
    df = pd.DataFrame({"Age": ["20"]})
    data, report = build_report(df, {"Age": ColumnType.NUMERIC}, [])
    with pytest.raises(ValueError):
        apply_cleaning(data, report, ["not_a_check"])
