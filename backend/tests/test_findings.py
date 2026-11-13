"""Key findings are built from rules on statistics we already computed."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from survey_insight.findings import (
    build_findings,
    difference_score,
    is_demographic,
    rule_group_differences,
    rule_top_choices,
)
from survey_insight.loading import ColumnProfile, ColumnType
from survey_insight.stats import Comparison, build_stats

AGREE = ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"]


@pytest.fixture(scope="module")
def stats():
    """A small survey where Engineering students are clearly more stressed."""
    rng = np.random.default_rng(7)
    n = 160
    faculty = np.where(np.arange(n) < 80, "Engineering", "Business")
    latent = np.where(faculty == "Engineering", 1.0, -0.6) + rng.normal(0, 0.7, n)
    df = pd.DataFrame({
        "Faculty": faculty,
        "Methods": rng.choice(["Notes, Videos", "Notes", "Videos, Notes, Books"], n),
        "Sleep": np.round(7 - 0.6 * latent + rng.normal(0, 0.5, n), 1).astype(str),
    })
    profiles = [ColumnProfile("Faculty", ColumnType.SINGLE_CHOICE, "", 0, 2, []),
                ColumnProfile("Methods", ColumnType.MULTIPLE_CHOICE, "", 0, 3, []),
                ColumnProfile("Sleep", ColumnType.NUMERIC, "", 0, 10, [])]
    types = {"Faculty": ColumnType.SINGLE_CHOICE, "Methods": ColumnType.MULTIPLE_CHOICE,
             "Sleep": ColumnType.NUMERIC}
    for i in range(4):
        col = f"Stress [item {i}]"
        idx = np.clip(np.round(2 + latent + rng.normal(0, 0.6, n)), 0, 4).astype(int)
        df[col] = [AGREE[j] for j in idx]
        profiles.append(ColumnProfile(col, ColumnType.LIKERT, "", 0, 5, [],
                                      scale_group="Stress", likert_levels=AGREE))
        types[col] = ColumnType.LIKERT
    return build_stats(df, types, profiles)


def test_scale_difference_is_reported_once_not_per_item(stats) -> None:
    findings = rule_group_differences(stats)
    assert findings, "expected at least one difference"
    assert "Stress (scale score)" in findings[0].text
    assert "Engineering" in findings[0].text.split("lowest")[0]
    # The scale was reported, so its individual items are not repeated for Faculty.
    assert not any("item" in f.text for f in findings)


def test_findings_include_relationship_and_reliability(stats) -> None:
    findings = build_findings(stats, None, n_excluded=12)
    kinds = {f.kind for f in findings}
    assert {"difference", "relationship", "reliability", "quality"} <= kinds
    relationship = next(f for f in findings if f.kind == "relationship")
    assert "not proof of cause" in relationship.text
    assert findings == sorted(findings, key=lambda f: -f.importance)


def test_demographic_by_demographic_is_ranked_lower() -> None:
    def comparison(outcome: str, group_by: str) -> Comparison:
        return Comparison(outcome, outcome, "numeric", group_by, "Kruskal-Wallis H", "", 1.0,
                          0.001, 0.001, True, "epsilon²", 0.3, "large", 100, [])

    assert is_demographic("Age") and is_demographic("Year of study")
    assert not is_demographic("Average hours of sleep per night")
    assert difference_score(comparison("Age", "Year of study")) < \
        difference_score(comparison("Average hours of sleep per night", "Year of study"))


def test_top_choices_rule(stats) -> None:
    findings = rule_top_choices(stats)
    assert len(findings) == 1  # one multiple-choice question
    finding = findings[0]
    assert finding.kind == "choice"
    # "Notes" appears in all three answer options, so every respondent picked it.
    assert "“Notes” (100% of respondents), followed by" in finding.text
