"""The synthetic dataset is reproducible and contains the mess we promise."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

GENERATOR = Path(__file__).resolve().parents[2] / "sample_data" / "generate_sample.py"


@pytest.fixture(scope="module")
def generator():
    spec = importlib.util.spec_from_file_location("generate_sample", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def survey(generator) -> pd.DataFrame:
    return generator.generate()


def test_has_300_rows(survey: pd.DataFrame) -> None:
    assert len(survey) == 300


def test_same_seed_gives_same_data(generator, survey: pd.DataFrame) -> None:
    pd.testing.assert_frame_equal(survey, generator.generate())


def test_contains_duplicate_answers(survey: pd.DataFrame) -> None:
    answers = survey.drop(columns=["ID", "Start time", "Completion time"])
    assert answers.duplicated().sum() >= 8


def test_contains_arabic_and_english_text(generator, survey: pd.DataFrame) -> None:
    text = survey[generator.COL_CHALLENGE].dropna().astype(str)
    assert text.str.contains(r"[؀-ۿ]").any()
    assert text.str.contains(r"[A-Za-z]{4,}").any()


def test_contains_email_inside_free_text(generator, survey: pd.DataFrame) -> None:
    assert survey[generator.COL_HELP].astype(str).str.contains("@example.com").any()
