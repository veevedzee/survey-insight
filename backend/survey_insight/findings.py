"""Turn computed statistics into a short list of plain-English key findings.

Every finding comes from an explicit rule applied to numbers we already
computed and tested. No language model writes anything, so each sentence can
be traced back to a specific test, and nothing appears that the statistics
don't support.

Ranking: results that answer research questions (attitudes, wellbeing scales)
come before results that only describe who took part (e.g. "older students
are in later years"), and bigger effects come before smaller ones.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from survey_insight.stats import Comparison, Correlation, StatsReport
from survey_insight.text_themes import ThemesReport

MAX_DIFFERENCES = 4
MAX_RELATIONSHIPS = 2

# Outcomes that describe the sample rather than the research topic.
_DEMOGRAPHIC = re.compile(
    r"\b(age|gender|sex|year of study|year|faculty|major|department|college|nationality|"
    r"living|residence|semester|level)\b|السن|العمر|النوع|الكلية|السنة",
    re.IGNORECASE,
)
_KIND_WEIGHT = {"scale": 3.0, "likert": 2.0, "numeric": 1.5, "categorical": 1.0}
_EFFECT_WEIGHT = {"large": 3.0, "medium": 2.0, "small": 1.0, "negligible": 0.5}


@dataclass
class Finding:
    """One key finding.

    Attributes:
        kind: difference | relationship | reliability | agreement | theme | choice | quality
        title: A few words for the card heading.
        text: The full plain-English sentence.
        importance: Used for ordering (higher first).
        evidence: The test and numbers behind it, for the "how do we know" line.
    """

    kind: str
    title: str
    text: str
    importance: float
    evidence: str = ""


def is_demographic(name: str) -> bool:
    return bool(_DEMOGRAPHIC.search(name))


def difference_score(c: Comparison) -> float:
    """How interesting a significant group difference is."""
    weight = _KIND_WEIGHT.get(c.outcome_kind, 1.0) * _EFFECT_WEIGHT.get(c.effect_label, 1.0)
    if is_demographic(c.outcome) and is_demographic(c.group_by):
        weight *= 0.3  # describes the sample, not the topic
    return weight


# --------------------------------------------------------------------------- #
# Rules
# --------------------------------------------------------------------------- #
def rule_group_differences(stats: StatsReport) -> list[Finding]:
    """The largest significant group differences, without repeating scale items.

    If a whole scale differs between groups, we report the scale once instead
    of also listing each of its items for the same grouping.
    """
    significant = [c for c in stats.comparisons if c.significant]
    scale_groups = {(c.group_by, c.outcome.removeprefix("Scale score: "))
                    for c in significant if c.outcome_kind == "scale"}
    scale_of_item = {item.column: scale.label for scale in stats.scales if scale.reliable
                     for item in scale.items}
    kept = [c for c in significant
            if not (c.outcome_kind == "likert"
                    and (c.group_by, scale_of_item.get(c.outcome, "")) in scale_groups)]
    kept.sort(key=lambda c: (-difference_score(c), -abs(c.effect_size)))
    findings = []
    for c in kept[:MAX_DIFFERENCES]:
        p = "< .001" if c.p_adjusted < 0.001 else f"= {c.p_adjusted:.3f}"
        findings.append(Finding(
            kind="difference",
            title=f"{c.outcome_label} by {c.group_by}",
            text=_difference_text(c),
            importance=10 + difference_score(c),
            evidence=f"{c.test}, p(adj.) {p}, {c.effect_name} = {c.effect_size:.2f} "
                     f"({c.effect_label}), n = {c.n_total}",
        ))
    return findings


def _difference_text(c: Comparison) -> str:
    if c.outcome_kind == "categorical":
        ranked = sorted(c.groups, key=lambda g: g.percent or 0, reverse=True)
        return (f"{c.outcome_label} differs across {c.group_by} groups "
                f"({ranked[0].group}: {ranked[0].percent:.0f}% vs {ranked[-1].group}: "
                f"{ranked[-1].percent:.0f}% for the most telling answer).")
    use_mean = c.test in ("Welch's t-test", "One-way ANOVA")
    key = (lambda g: g.mean or 0) if use_mean else (lambda g: (g.median or 0, g.mean or 0))
    ranked = sorted(c.groups, key=key, reverse=True)
    hi, lo = ranked[0], ranked[-1]
    centre = "average" if use_mean else "median"
    hi_v, lo_v = (hi.mean, lo.mean) if use_mean else (hi.median, lo.median)
    return (f"“{c.outcome_label}” is highest for {hi.group} ({centre} {hi_v:g}, n = {hi.n}) "
            f"and lowest for {lo.group} ({centre} {lo_v:g}, n = {lo.n}): "
            f"a {c.effect_label} difference.")


def rule_relationships(stats: StatsReport) -> list[Finding]:
    """Significant correlations of at least medium strength."""
    strong = [c for c in stats.correlations
              if c.significant and c.effect_label in ("medium", "large")]
    strong.sort(key=lambda c: -abs(c.rho))
    return [_relationship(c) for c in strong[:MAX_RELATIONSHIPS]]


def _relationship(c: Correlation) -> Finding:
    direction = "more" if c.rho > 0 else "less"
    return Finding(
        kind="relationship",
        title=f"{c.x_label} and {c.y_label}",
        text=(f"Higher “{c.x_label}” goes with {direction} “{c.y_label}” "
              f"({c.effect_label} relationship). This is an association, not proof of cause."),
        importance=8 + abs(c.rho) * 5,
        evidence=f"Spearman ρ = {c.rho:.2f}, n = {c.n}",
    )


def rule_reliability(stats: StatsReport) -> list[Finding]:
    """Say which grids can be trusted as scales, and warn about the ones that can't."""
    findings = []
    for s in stats.scales:
        if s.reliable:
            findings.append(Finding(
                "reliability", f"{s.label} is a reliable scale",
                f"The {len(s.items)} “{s.label}” items measure one consistent idea "
                f"(Cronbach's α = {s.alpha:.2f}, {s.interpretation}), so they are combined "
                "into a single score.", 4, f"α = {s.alpha:.2f}, n = {s.n_complete}"))
        elif s.alpha == s.alpha:  # not NaN
            findings.append(Finding(
                "reliability", f"{s.label} items don't hang together",
                f"The “{s.label}” items are not consistent enough to combine "
                f"(α = {s.alpha:.2f}). Interpret them one by one.", 6,
                f"α = {s.alpha:.2f}"))
    return findings


def rule_strongest_agreement(stats: StatsReport) -> list[Finding]:
    """The Likert statement with the most agreement, and the one with the least."""
    items = [q for q in stats.questions if q.likert and q.n >= 10]
    if len(items) < 2:
        return []
    top = max(items, key=lambda q: q.likert.agree_percent)  # type: ignore[union-attr]
    low = min(items, key=lambda q: q.likert.agree_percent)  # type: ignore[union-attr]
    return [Finding(
        "agreement", "Most and least agreed statements",
        f"Most agreement: “{top.label}” ({top.likert.agree_percent:.0f}% in the top two levels). "  # type: ignore[union-attr]
        f"Least: “{low.label}” ({low.likert.agree_percent:.0f}%).",  # type: ignore[union-attr]
        7, f"n = {top.n} and {low.n}")]


def rule_top_themes(themes: ThemesReport | None) -> list[Finding]:
    """The largest theme of each open-ended question."""
    if themes is None:
        return []
    findings = []
    for col in themes.columns:
        if not col.themes:
            continue
        top = col.themes[0]
        findings.append(Finding(
            "theme", f"Top theme: {top.label}",
            f"In “{col.column}”, the most common theme is “{top.label}” "
            f"({top.percent:.0f}% of {col.n_used} answers), e.g. “{top.quotes[0].text}”.",
            6 + top.percent / 20, f"{col.k} themes found, {col.quality}"))
    return findings


def rule_top_choices(stats: StatsReport) -> list[Finding]:
    """The most selected options of each multiple-choice question.

    Shares are of respondents, not of ticks, so they can add up to more than
    100% ("80% use lecture notes, 65% use YouTube").
    """
    findings = []
    for q in stats.questions:
        if q.type != "multiple_choice" or not q.counts or q.n < 10:
            continue
        top = q.counts[0]
        text = f"In “{q.label}”, the most selected option is “{top.label}” ({top.percent:.0f}% of "
        if len(q.counts) > 1:
            second = q.counts[1]
            text += f"respondents), followed by “{second.label}” ({second.percent:.0f}%)."
        else:
            text += "respondents)."
        findings.append(Finding("choice", f"Most selected: {top.label}", text, 5,
                                f"n = {q.n}; several answers allowed"))
    return findings


# --------------------------------------------------------------------------- #
def build_findings(stats: StatsReport, themes: ThemesReport | None = None,
                   n_excluded: int = 0, limit: int = 8) -> list[Finding]:
    """Apply every rule and return the most important findings first."""
    findings = (rule_group_differences(stats) + rule_relationships(stats)
                + rule_strongest_agreement(stats) + rule_top_themes(themes)
                + rule_reliability(stats) + rule_top_choices(stats))
    if n_excluded:
        findings.append(Finding(
            "quality", "Data cleaning",
            f"{n_excluded} low-quality responses were excluded before analysis, leaving "
            f"{stats.n_responses}.", 1, ""))
    findings.sort(key=lambda f: -f.importance)
    return findings[:limit]
