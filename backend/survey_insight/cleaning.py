"""Flag low-quality responses so the user can decide what to exclude.

Nothing is removed silently. Each check returns the rows it flagged, a reason
per row, and a suggested action; the user ticks which checks to apply and
sees the before/after counts.

Checks
------
duplicates     Same answers as an earlier response (double submission, copy-paste).
incomplete     Answered fewer than 80% of the closed questions (dropped out).
straight_lining Same answer to every item of every Likert grid (not reading).
speeders       Finished much faster than is possible when reading the questions.
outliers       Numeric answers far outside the rest (typos such as age 199).
               These blank the *value* instead of excluding the whole response,
               because the rest of that person's answers are usually fine.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field, replace

import pandas as pd

from survey_insight.loading import ColumnProfile, ColumnType, likert_score

INCOMPLETE_THRESHOLD = 0.8  # share of closed questions that must be answered
OUTLIER_IQR_FACTOR = 3.0  # Tukey's "far out" fence
MIN_STRAIGHT_LINE_ITEMS = 6

_QUESTION_TYPES = {ColumnType.LIKERT, ColumnType.SINGLE_CHOICE, ColumnType.MULTIPLE_CHOICE,
                   ColumnType.NUMERIC, ColumnType.TEXT}
_CLOSED_TYPES = _QUESTION_TYPES - {ColumnType.TEXT}  # open text is often optional
_START = re.compile(r"start", re.IGNORECASE)
_END = re.compile(r"complet|end|finish|submit", re.IGNORECASE)


@dataclass
class FlagExample:
    """One flagged response and why. ``row`` is the 0-based row index."""

    row: int
    detail: str


@dataclass
class Check:
    """Result of one quality check."""

    key: str
    label: str
    description: str
    action: str  # "exclude" (drop the response) or "blank" (clear the value)
    available: bool
    unavailable_reason: str | None = None
    flagged_rows: list[int] = field(default_factory=list)
    examples: list[FlagExample] = field(default_factory=list)


@dataclass
class Normalization:
    """Spelling variants merged in one choice column."""

    column: str
    n_changed: int
    changes: list[tuple[str, str]]  # (original, merged into)


@dataclass
class CleaningReport:
    """All checks for one survey. ``outlier_cells`` maps column -> flagged rows."""

    n_rows: int
    checks: list[Check]
    normalizations: list[Normalization]
    outlier_cells: dict[str, list[int]] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Normalisation of choice answers
# --------------------------------------------------------------------------- #
def _fold(value: str) -> str:
    return " ".join(value.split()).casefold()


def normalize_choices(
    df: pd.DataFrame, types: dict[str, ColumnType]
) -> tuple[pd.DataFrame, list[Normalization]]:
    """Merge answers that differ only in case or spacing ("engineering " -> "Engineering").

    The most common spelling of each answer wins, so we never invent a spelling.
    """
    out = df.copy()
    report: list[Normalization] = []
    for col in df.columns:
        kind = types.get(col)
        if kind not in (ColumnType.SINGLE_CHOICE, ColumnType.MULTIPLE_CHOICE):
            continue
        values = df[col].dropna().astype(str)
        if kind == ColumnType.MULTIPLE_CHOICE:
            sep = ";" if values.str.contains(";").mean() > values.str.contains(",").mean() else ","
            tokens = values.str.split(sep).explode().str.strip()
        else:
            sep = ""
            tokens = values.str.strip()
        canonical = _canonical_spellings(tokens[tokens != ""])

        def fix(value: object, sep: str = sep, canonical: dict[str, str] = canonical) -> object:
            if not isinstance(value, str):
                return value
            if not sep:
                return canonical.get(_fold(value), value.strip())
            parts = [p.strip() for p in value.split(sep) if p.strip()]
            return ", ".join(canonical.get(_fold(p), p) for p in parts)

        new = df[col].map(fix)
        changed = df[col].notna() & (new != df[col])
        if changed.any():
            pairs = Counter(zip(df.loc[changed, col], new[changed], strict=True))
            out[col] = new
            report.append(Normalization(col, int(changed.sum()),
                                        [pair for pair, _ in pairs.most_common(5)]))
    return out, report


def _canonical_spellings(tokens: pd.Series) -> dict[str, str]:
    """Map each folded answer to its most common original spelling."""
    canonical: dict[str, str] = {}
    for spelling, _count in tokens.value_counts().items():
        canonical.setdefault(_fold(str(spelling)), str(spelling))
    return canonical


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #
def find_duplicates(df: pd.DataFrame, columns: list[str]) -> Check:
    """Flag responses whose answers exactly repeat an earlier response."""
    check = Check("duplicates", "Duplicate responses",
                  "Identical answers submitted more than once (double submission or "
                  "copy-paste). The first copy is kept.", "exclude", available=bool(columns))
    if not columns:
        check.unavailable_reason = "No question columns to compare."
        return check
    answers = df[columns].astype("string").fillna("<blank>")
    first_seen: dict[tuple[str, ...], int] = {}
    for row, values in zip(df.index, answers.itertuples(index=False, name=None), strict=True):
        if values in first_seen:
            check.flagged_rows.append(int(row))
            check.examples.append(FlagExample(
                int(row), f"Same answers as response #{first_seen[values] + 1}"))
        else:
            first_seen[values] = int(row)
    return check


def find_incomplete(df: pd.DataFrame, closed_columns: list[str],
                    threshold: float = INCOMPLETE_THRESHOLD) -> Check:
    """Flag responses that answered less than ``threshold`` of the closed questions."""
    check = Check("incomplete", "Incomplete responses",
                  f"Answered fewer than {threshold:.0%} of the closed questions, usually "
                  "because the person stopped part-way.", "exclude",
                  available=bool(closed_columns))
    if not closed_columns:
        check.unavailable_reason = "No closed questions to count."
        return check
    answered = df[closed_columns].notna().sum(axis=1)
    share = answered / len(closed_columns)
    for row in share[share < threshold].index:
        check.flagged_rows.append(int(row))
        check.examples.append(FlagExample(
            int(row), f"Answered {answered[row]} of {len(closed_columns)} questions "
                      f"({share[row]:.0%})"))
    return check


def find_straight_lining(df: pd.DataFrame, profiles: list[ColumnProfile]) -> Check:
    """Flag people who gave the same answer to every item of every Likert grid.

    One identical grid can be honest ("I agree with all of these"). Identical
    answers across *all* grids, covering at least six items, rarely are.
    """
    groups: dict[str, list[ColumnProfile]] = {}
    for p in profiles:
        if p.name in df.columns and p.detected_type == ColumnType.LIKERT and p.scale_group:
            groups.setdefault(p.scale_group, []).append(p)
    groups = {g: items for g, items in groups.items() if len(items) >= 3}

    check = Check("straight_lining", "Straight-lining",
                  "The same answer to every item of every rating grid, which suggests the "
                  "questions weren't read. People with genuinely extreme views can look the "
                  "same, so skim the examples before excluding.", "exclude",
                  available=bool(groups))
    if not groups:
        check.unavailable_reason = "Needs at least one grid of 3+ Likert items."
        return check

    # Answers as positions on their scale (1 = lowest), so grids are comparable.
    positions = {
        p.name: df[p.name].map(lambda v, lv=p.likert_levels: _position(v, lv or []))
        for items in groups.values() for p in items
    }
    for row in df.index:
        n_items, all_flat = 0, True
        for items in groups.values():
            answered = [positions[p.name][row] for p in items
                        if positions[p.name][row] is not None
                        and not pd.isna(positions[p.name][row])]
            if len(answered) < 3:
                continue
            n_items += len(answered)
            if len(set(answered)) > 1:
                all_flat = False
                break
        if all_flat and n_items >= MIN_STRAIGHT_LINE_ITEMS:
            check.flagged_rows.append(int(row))
            check.examples.append(FlagExample(
                int(row), f"Same answer to all {n_items} grid items"))
    return check


def _position(value: object, levels: list[str]) -> float | None:
    score = likert_score(value, levels)
    if score is None or not levels:
        return score
    if levels[0].lstrip("-").isdigit():
        return score - int(levels[0]) + 1
    return score


def speeder_cutoff_seconds(durations: pd.Series) -> float:
    """Return the completion time (seconds) below which a response counts as a speeder.

    The cut-off is one third of the median completion time, a common rule of
    thumb in survey methodology. It is relative on purpose: a fixed limit such as
    90 seconds would be too strict for a 3-question survey and far too lenient
    for a 60-question one. The median (not the mean) is used because a few
    people who leave the form open for hours would drag the mean up.

    Args:
        durations: Completion times in seconds of all responses (no missing values).
    """
    return float(durations.median()) / 3


def find_speeders(df: pd.DataFrame, timestamp_columns: list[str]) -> Check:
    """Flag responses completed implausibly fast (needs start and end times)."""
    check = Check("speeders", "Speeders",
                  "Finished far faster than it takes to read the questions.", "exclude",
                  available=False)
    start = next((c for c in timestamp_columns if _START.search(c)), None)
    end = next((c for c in timestamp_columns if c != start and _END.search(c)), None)
    if start is None or end is None:
        check.unavailable_reason = ("Needs both a start and a completion time. Microsoft Forms "
                                    "exports both; Google Forms only records submission time.")
        return check
    begin = pd.to_datetime(df[start], errors="coerce", format="mixed")
    finish = pd.to_datetime(df[end], errors="coerce", format="mixed")
    seconds = (finish - begin).dt.total_seconds()
    valid = seconds[(seconds > 0) & seconds.notna()]
    if len(valid) < 5:
        check.unavailable_reason = "Too few valid start/completion times."
        return check

    check.available = True
    cutoff = speeder_cutoff_seconds(valid)
    median = float(valid.median())
    check.description = (f"Finished in under {_fmt_duration(cutoff)}; the typical response "
                         f"took {_fmt_duration(median)}.")
    for row in valid[valid < cutoff].index:
        check.flagged_rows.append(int(row))
        check.examples.append(FlagExample(int(row),
                                          f"Finished in {_fmt_duration(valid[row])}"))
    return check


def _fmt_duration(seconds: float) -> str:
    seconds = round(seconds)
    if seconds < 60:
        return f"{seconds} s"
    return f"{seconds // 60} min {seconds % 60:02d} s"


def find_outliers(df: pd.DataFrame, numeric_columns: list[str],
                  factor: float = OUTLIER_IQR_FACTOR) -> tuple[Check, dict[str, list[int]]]:
    """Flag numeric values beyond ``factor`` x IQR outside the middle half of answers.

    Why IQR and not "more than 3 standard deviations"? The mean and standard
    deviation are themselves pulled by the outlier (one age of 199 inflates both),
    so a z-score can hide the very value we're looking for. Quartiles barely move.
    """
    check = Check("outliers", "Numeric outliers",
                  "Values far outside the rest of the answers, usually typos (age 199). "
                  "Only the value is cleared; the rest of the response is kept.", "blank",
                  available=bool(numeric_columns))
    cells: dict[str, list[int]] = {}
    if not numeric_columns:
        check.unavailable_reason = "No numeric columns."
        return check, cells
    for col in numeric_columns:
        x = pd.to_numeric(df[col], errors="coerce")
        valid = x.dropna()
        if len(valid) < 10:
            continue
        q1, q3 = valid.quantile(0.25), valid.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        low, high = q1 - factor * iqr, q3 + factor * iqr
        bad = valid[(valid < low) | (valid > high)]
        if bad.empty:
            continue
        cells[col] = [int(r) for r in bad.index]
        for row, value in bad.items():
            check.examples.append(FlagExample(
                int(row), f"{col} = {value:g} (middle half of answers: {q1:g}–{q3:g})"))
    check.flagged_rows = sorted({r for rows in cells.values() for r in rows})
    return check, cells


# --------------------------------------------------------------------------- #
# Putting it together
# --------------------------------------------------------------------------- #
def build_report(df: pd.DataFrame, types: dict[str, ColumnType],
                 profiles: list[ColumnProfile]) -> tuple[pd.DataFrame, CleaningReport]:
    """Normalise choice spellings, then run every check.

    Returns the normalised DataFrame (to be used from now on) and the report.
    """
    df, normalizations = normalize_choices(df, types)
    present = [c for c in df.columns if c in types]
    questions = [c for c in present if types[c] in _QUESTION_TYPES]
    closed = [c for c in present if types[c] in _CLOSED_TYPES]
    timestamps = [c for c in present if types[c] == ColumnType.TIMESTAMP]
    numeric = [c for c in present if types[c] == ColumnType.NUMERIC]

    # Use the confirmed types, not the original guesses (copies: profiles are shared).
    likert_profiles = [replace(p, detected_type=ColumnType.LIKERT) for p in profiles
                       if types.get(p.name) == ColumnType.LIKERT]

    outlier_check, cells = find_outliers(df, numeric)
    checks = [
        find_duplicates(df, questions),
        find_incomplete(df, closed),
        find_straight_lining(df, likert_profiles),
        find_speeders(df, timestamps),
        outlier_check,
    ]
    return df, CleaningReport(len(df), checks, normalizations, cells)


@dataclass
class CleaningResult:
    """What applying the chosen checks did."""

    n_before: int
    n_after: int
    n_values_blanked: int
    applied: list[str]


def apply_cleaning(df: pd.DataFrame, report: CleaningReport,
                   apply: list[str]) -> tuple[pd.DataFrame, CleaningResult]:
    """Apply the checks the user ticked: drop flagged responses, blank outlier values."""
    unknown = set(apply) - {c.key for c in report.checks}
    if unknown:
        raise ValueError(f"Unknown checks: {sorted(unknown)}")
    out = df.copy()
    blanked = 0
    drop: set[int] = set()
    for check in report.checks:
        if check.key not in apply or not check.available:
            continue
        if check.action == "blank":
            for col, rows in report.outlier_cells.items():
                out[col] = out[col].astype("object")
                out.loc[rows, col] = pd.NA
                blanked += len(rows)
        else:
            drop.update(check.flagged_rows)
    out = out.drop(index=sorted(drop))
    return out, CleaningResult(len(df), len(out), blanked, sorted(apply))
