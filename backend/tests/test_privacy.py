"""Personal data is removed, and harmless numbers are left alone."""

from __future__ import annotations

import pandas as pd
import pytest

from survey_insight.loading import ColumnType
from survey_insight.privacy import anonymize, build_name_pattern, mask_text


@pytest.mark.parametrize(
    ("text", "expected", "kind"),
    [
        ("mail me: sara.k@example.com", "mail me: [EMAIL]", "email"),
        ("call 01012345678 please", "call [PHONE] please", "phone"),
        ("call +20 101 234 5678", "call [PHONE]", "phone"),
        ("call 0101-234-5678", "call [PHONE]", "phone"),
        ("على ٠١٠١٢٣٤٥٦٧٨", "على [PHONE]", "phone"),  # Arabic-Indic digits
        ("my ID is 231004567.", "my ID is [ID].", "id"),
        ("national id 29901011234567", "national id [ID]", "id"),
    ],
)
def test_masks_personal_data(text: str, expected: str, kind: str) -> None:
    masked, counts = mask_text(text)
    assert masked == expected
    assert counts == {kind: 1}


@pytest.mark.parametrize(
    "text",
    [
        "I study 3 hours a day",
        "Between 2024-2025 it was hard",
        "Rooms 101, 102 and 103",
        "Scores 1 2 3 4 5 6 7 8",
        "GPA dropped from 3.45 to 2.9",
    ],
)
def test_leaves_harmless_numbers_alone(text: str) -> None:
    masked, counts = mask_text(text)
    assert masked == text
    assert not counts


def test_known_full_names_are_masked_but_single_words_are_not() -> None:
    pattern = build_name_pattern(["Nour Kamal", "Omar  Mahmoud", "Ali"])
    masked, counts = mask_text("Thanks - omar mahmoud. Nour is light.", pattern)
    assert masked == "Thanks - [NAME]. Nour is light."
    assert counts == {"name": 1}


def test_anonymize_drops_identifiers_and_masks_text() -> None:
    df = pd.DataFrame({
        "Name": ["Nour Kamal", "Omar Mahmoud"],
        "Email": ["n@example.com", "o@example.com"],
        "Age": ["20", "21"],
        "Comment": ["Ask Nour Kamal", "fine"],
    })
    types = {"Name": ColumnType.IDENTIFIER, "Email": ColumnType.IDENTIFIER,
             "Age": ColumnType.NUMERIC, "Comment": ColumnType.TEXT}

    clean, report = anonymize(df, types)

    assert list(clean.columns) == ["Age", "Comment"]
    assert clean["Comment"].tolist() == ["Ask [NAME]", "fine"]
    assert [c.name for c in report.removed_columns] == ["Name", "Email"]
    assert report.masked_columns[0].counts == {"name": 1}
    assert report.total_masked == 1
    assert "Name" in df.columns  # the input is not modified
