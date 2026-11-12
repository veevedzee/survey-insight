"""Export the cleaned, anonymised data as CSV.

The export is the exact table the statistics ran on: personal data removed,
spelling variants merged, the user's chosen responses excluded and outlier
values cleared. Reliable scales get an extra column with each person's scale
score (the mean of their item scores), so the file can be reused in SPSS,
R or Excel without redoing that step.

(The HTML report is produced in the browser from the rendered dashboard;
see frontend/src/report.ts.)
"""

from __future__ import annotations

import re

import pandas as pd

from survey_insight.loading import ColumnProfile
from survey_insight.stats import StatsReport, _levels_for, likert_numeric, scale_scores


def cleaned_table(df: pd.DataFrame, stats: StatsReport,
                  profiles: list[ColumnProfile]) -> pd.DataFrame:
    """The analysed data plus one score column per reliable scale."""
    by_name = {p.name: p for p in profiles}
    out = df.copy()
    for scale in stats.scales:
        if not scale.reliable or not scale.score_column:
            continue
        items = pd.DataFrame({
            item.column: likert_numeric(df[item.column], _levels_for(by_name.get(item.column),
                                                                     df[item.column]))
            for item in scale.items if item.column in df.columns
        })
        out[scale.score_column] = scale_scores(items).round(3)
    return out


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """CSV encoded as UTF-8 *with* a byte-order mark.

    Without the BOM, Excel on Windows guesses the old ANSI encoding and shows
    Arabic answers as gibberish; with it, Excel, Google Sheets and pandas all
    read the file correctly.
    """
    return df.to_csv(index=False).encode("utf-8-sig")


def export_filename(original: str, suffix: str) -> str:
    """"Student Survey (2).xlsx" -> "Student_Survey_2-cleaned.csv" (safe for headers)."""
    stem = original.rsplit(".", 1)[0]
    stem = re.sub(r"[^\w-]+", "_", stem, flags=re.ASCII).strip("_") or "survey"
    return f"{stem}-{suffix}"
