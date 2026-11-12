"""Remove personal data before any analysis happens.

Two layers:

1. **Identifier columns** (names, emails, phone numbers, student IDs) are
   dropped entirely. Statistics never need them.
2. **Free-text answers** are scanned, because people type personal data into
   comment boxes ("email me at ..."). Matches are replaced with placeholders
   such as ``[EMAIL]`` so the rest of the answer can still be analysed.

Limitation (stated in the UI): names written inside free text are only caught
when they also appear in a name column of the same file. Recognising arbitrary
names, especially in Arabic, needs a named-entity model, which costs memory we
don't have on a free hosting tier.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

import pandas as pd

from survey_insight.loading import EMAIL_RE, ColumnType

# A run of digits that may contain spaces, dashes, dots or brackets, optionally
# starting with "+". The (?<!...) / (?!...) parts stop us matching inside words.
_DIGIT_RUN = re.compile(r"(?<![\w@.])\+?\d[\d\s().-]{5,}\d(?![\w@])")
_NAME_HEADER = re.compile(r"\bname\b|الاسم|اسم", re.IGNORECASE)

PLACEHOLDERS = {"email": "[EMAIL]", "phone": "[PHONE]", "id": "[ID]", "name": "[NAME]"}


@dataclass
class RemovedColumn:
    """An identifier column that was dropped."""

    name: str
    n_values: int


@dataclass
class MaskedColumn:
    """What was masked inside one free-text column."""

    name: str
    counts: dict[str, int]
    examples: list[str] = field(default_factory=list)


@dataclass
class PrivacyReport:
    """Everything the privacy step removed, shown to the user."""

    removed_columns: list[RemovedColumn]
    masked_columns: list[MaskedColumn]

    @property
    def total_masked(self) -> int:
        return sum(sum(c.counts.values()) for c in self.masked_columns)


def classify_digit_run(match: str) -> str | None:
    """Decide whether a run of digits is a phone number, an ID, or harmless.

    * 10-15 digits (with or without separators) -> phone number
      e.g. ``01012345678``, ``+20 101 234 5678``, ``0101-234-5678``
    * 7-9 or exactly 14 digits written without separators -> ID
      (9-digit student IDs, 14-digit Egyptian national IDs)
    * anything else (years like ``2024-2025``, ``3 4 5``) -> leave alone
    """
    digits = re.sub(r"\D", "", match)
    contiguous = match.lstrip("+").isdigit()
    if contiguous and (7 <= len(digits) <= 9 or len(digits) == 14):
        return "id"
    if 10 <= len(digits) <= 15:
        if not contiguous and len(re.findall(r"\d+", match)) > 4:
            return None  # many small groups: more likely a list of numbers
        return "phone"
    return None


def build_name_pattern(names: list[str]) -> re.Pattern[str] | None:
    """Compile a pattern matching any known full name (two words or more).

    Single first names are skipped on purpose: "Nour" is also the Arabic word
    for light and "Hana" means happiness, so masking them would damage answers.
    """
    full_names = {" ".join(n.split()) for n in names if isinstance(n, str) and len(n.split()) >= 2}
    if not full_names:
        return None
    # Longest first, so "Omar Mahmoud Ali" wins over "Omar Mahmoud".
    alternatives = sorted((re.escape(n).replace(r"\ ", r"\s+") for n in full_names),
                          key=len, reverse=True)
    return re.compile(r"(?<!\w)(?:" + "|".join(alternatives) + r")(?!\w)", re.IGNORECASE)


def mask_text(text: str, name_pattern: re.Pattern[str] | None = None) -> tuple[str, Counter[str]]:
    """Replace emails, known names, phone numbers and IDs inside one answer.

    Returns the masked text and how many of each kind were replaced.
    Order matters: emails first, so the digits inside an email address are not
    later mistaken for a phone number.
    """
    counts: Counter[str] = Counter()

    def sub_email(_: re.Match[str]) -> str:
        counts["email"] += 1
        return PLACEHOLDERS["email"]

    text = EMAIL_RE.sub(sub_email, text)

    if name_pattern is not None:
        def sub_name(_: re.Match[str]) -> str:
            counts["name"] += 1
            return PLACEHOLDERS["name"]

        text = name_pattern.sub(sub_name, text)

    def sub_digits(match: re.Match[str]) -> str:
        kind = classify_digit_run(match.group())
        if kind is None:
            return match.group()
        counts[kind] += 1
        return PLACEHOLDERS[kind]

    text = _DIGIT_RUN.sub(sub_digits, text)
    return text, counts


def anonymize(df: pd.DataFrame, types: dict[str, ColumnType]) -> tuple[pd.DataFrame, PrivacyReport]:
    """Drop identifier columns and mask personal data in free-text columns.

    Args:
        df: The survey as uploaded.
        types: The confirmed type of every column.

    Returns:
        A new DataFrame without personal data, and a report of what was removed.
    """
    identifier_cols = [c for c in df.columns if types.get(c) == ColumnType.IDENTIFIER]
    names: list[str] = []
    for col in identifier_cols:
        if _NAME_HEADER.search(col):
            names.extend(df[col].dropna().astype(str).tolist())
    name_pattern = build_name_pattern(names)

    removed = [RemovedColumn(c, int(df[c].notna().sum())) for c in identifier_cols]
    clean = df.drop(columns=identifier_cols).copy()

    masked: list[MaskedColumn] = []
    for col in clean.columns:
        if types.get(col) != ColumnType.TEXT:
            continue
        total: Counter[str] = Counter()
        examples: list[str] = []
        new_values = []
        for value in clean[col]:
            if not isinstance(value, str):
                new_values.append(value)
                continue
            masked_value, counts = mask_text(value, name_pattern)
            if counts:
                total.update(counts)
                if len(examples) < 3:
                    examples.append(masked_value)
            new_values.append(masked_value)
        clean[col] = pd.Series(new_values, index=clean.index, dtype=clean[col].dtype)
        if total:
            masked.append(MaskedColumn(col, dict(total), examples))

    return clean, PrivacyReport(removed, masked)
