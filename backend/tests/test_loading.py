"""Reading files and detecting column types."""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import pytest

from survey_insight import loading
from survey_insight.loading import (
    ColumnType,
    SurveyFileError,
    detect_column,
    likert_group,
    likert_score,
    profile_columns,
    read_survey,
)

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "student_wellbeing_survey.csv"


def detect(values: list[object], name: str = "Question") -> ColumnType:
    return detect_column(pd.Series(values, dtype="object"), name).detected_type


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #
def test_reads_utf8_csv_with_bom_and_keeps_arabic() -> None:
    data = "Q1,Q2\nنعم,5\nلا,3\n".encode("utf-8-sig")
    df = read_survey(data, "survey.csv")
    assert list(df.columns) == ["Q1", "Q2"]
    assert df.loc[0, "Q1"] == "نعم"


def test_reads_windows_arabic_encoding() -> None:
    data = "Q1\nموافق\n".encode("cp1256")
    assert read_survey(data, "survey.csv").loc[0, "Q1"] == "موافق"


def test_detects_semicolon_delimiter() -> None:
    df = read_survey(b"a;b\n1;2\n3;4\n", "survey.csv")
    assert list(df.columns) == ["a", "b"]


def test_reads_xlsx() -> None:
    buffer = io.BytesIO()
    pd.DataFrame({"Age": [20, 21], "Gender": ["Male", "Female"]}).to_excel(buffer, index=False)
    df = read_survey(buffer.getvalue(), "survey.xlsx")
    assert df["Gender"].tolist() == ["Male", "Female"]


def test_keeps_none_as_a_real_answer_but_blank_as_missing() -> None:
    df = read_survey(b"Allergies,Comment\nNone,\nPeanuts,  \n", "s.csv")
    assert df.loc[0, "Allergies"] == "None"
    assert df["Comment"].isna().all()


def test_duplicate_headers_are_made_unique() -> None:
    df = read_survey(b"Q,Q\n1,2\n", "s.csv")
    assert list(df.columns) == ["Q", "Q (2)"]


@pytest.mark.parametrize("filename", ["survey.pdf", "survey"])
def test_rejects_unsupported_files(filename: str) -> None:
    with pytest.raises(SurveyFileError):
        read_survey(b"whatever", filename)


def test_rejects_file_without_rows() -> None:
    with pytest.raises(SurveyFileError):
        read_survey(b"Q1,Q2\n", "s.csv")


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #
def test_text_likert_labels() -> None:
    values = ["Agree", "strongly agree", "Neutral", "Disagree", None, "Agree"]
    profile = detect_column(pd.Series(values), "I enjoy my courses")
    assert profile.detected_type == ColumnType.LIKERT
    assert profile.likert_levels == ["Strongly disagree", "Disagree", "Neutral", "Agree",
                                     "Strongly agree"]


def test_numeric_likert_needs_a_rating_header() -> None:
    values = ["1", "2", "3", "4", "5", "3", "4"]
    assert detect(values, "Rate the course (1-5)") == ColumnType.LIKERT
    assert detect(values, "Grid question [item one]") == ColumnType.LIKERT
    assert detect(values, "Number of siblings") == ColumnType.NUMERIC


def test_grid_columns_share_a_scale_group() -> None:
    assert likert_group("How much do you agree? [I sleep well]") == "How much do you agree?"
    assert likert_group("Age") is None


def test_numeric() -> None:
    assert detect(["19", "20", "21.5", "199", None], "Age") == ColumnType.NUMERIC


def test_single_choice_ignores_case_and_spaces() -> None:
    values = ["Engineering", "engineering ", "Business", "BUSINESS", "Engineering"] * 4
    profile = detect_column(pd.Series(values).str.strip(), "Faculty")
    assert profile.detected_type == ColumnType.SINGLE_CHOICE
    assert profile.n_unique == 2


def test_multiple_choice() -> None:
    options = ["Notes, Videos", "Notes", "Videos, Past exams, Notes", "Past exams, Notes"] * 5
    assert detect(options, "Study methods") == ColumnType.MULTIPLE_CHOICE


def test_free_text_with_commas_is_not_multiple_choice() -> None:
    answers = [f"Answer number {i}, with some detail about topic {i * 7}" for i in range(40)]
    assert detect(answers, "Any comments?") == ColumnType.TEXT


def test_timestamp() -> None:
    assert detect(["3/1/2026 9:31:40", "3/2/2026 10:00:00"], "Start time") == ColumnType.TIMESTAMP
    assert detect(["2026-03-01 09:31", "2026-03-02 11:00"], "Submitted") == ColumnType.TIMESTAMP


def test_identifier_by_header_and_by_values() -> None:
    assert detect(["Ali Hassan", "Mona Adel"], "Full name") == ColumnType.IDENTIFIER
    assert detect(["Ali Hassan", "Mona Adel"], "الاسم") == ColumnType.IDENTIFIER
    emails = ["a@example.com", "b@example.org", "c@example.edu"]
    assert detect(emails, "Contact") == ColumnType.IDENTIFIER


def test_identifier_examples_are_masked() -> None:
    profile = detect_column(pd.Series(["ali.hassan@example.com"]), "Email")
    assert "ali.hassan" not in profile.examples[0]


def test_row_id_and_empty_columns_are_ignored() -> None:
    row_ids = [str(i) for i in range(1, 21)] + ["20"]  # one copy-pasted duplicate row
    assert detect(row_ids, "ID") == ColumnType.IGNORE
    assert detect([None, None], "Unused") == ColumnType.IGNORE


@pytest.mark.skipif(len(loading.ARABIC_AGREEMENT_LABELS) != 5,
                    reason="TODO(you): fill ARABIC_AGREEMENT_LABELS in loading.py")
def test_arabic_likert_labels() -> None:
    labels = loading.ARABIC_AGREEMENT_LABELS
    values = [labels[0], labels[2], labels[4], labels[3], labels[1], labels[3]]
    profile = detect_column(pd.Series(values), "رأيك في المقرر")
    assert profile.detected_type == ColumnType.LIKERT
    assert profile.likert_levels == labels


def test_likert_score() -> None:
    levels = ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"]
    assert likert_score("Agree", levels) == 4
    assert likert_score("somewhat agree", levels) == 4
    assert likert_score(None, levels) is None
    assert likert_score("4", ["1", "2", "3", "4", "5"]) == 4


def test_sample_dataset_types() -> None:
    """End-to-end check on the bundled sample: every column gets the right type."""
    df = read_survey(SAMPLE.read_bytes(), SAMPLE.name)
    types = {p.name: p.detected_type for p in profile_columns(df)}
    assert types["ID"] == ColumnType.IGNORE
    assert types["Start time"] == ColumnType.TIMESTAMP
    for col in ("Email", "Name", "Student ID", "WhatsApp number (optional)"):
        assert types[col] == ColumnType.IDENTIFIER
    for col in ("Age", "Average daily study hours", "Average hours of sleep per night"):
        assert types[col] == ColumnType.NUMERIC
    for col in ("Gender", "Year of study", "Faculty", "Living situation"):
        assert types[col] == ColumnType.SINGLE_CHOICE
    assert sum(t == ColumnType.LIKERT for t in types.values()) == 10
    assert sum(t == ColumnType.MULTIPLE_CHOICE for t in types.values()) == 1
    assert sum(t == ColumnType.TEXT for t in types.values()) == 2
