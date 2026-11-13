"""Read survey exports and detect what kind of question each column holds.

Detection is rule-based on purpose: every decision comes with a human-readable
``reason`` the user can check, and the user can override any type in the UI.
A model that "guesses" column types would be harder to explain and to fix.

Rules are tried in a fixed order, from most specific to least specific::

    empty -> identifier -> row id -> timestamp -> Likert -> numeric
          -> multiple choice -> single choice -> free text
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from enum import StrEnum

import pandas as pd


class ColumnType(StrEnum):
    """The kinds of survey column we know how to analyse."""

    LIKERT = "likert"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    NUMERIC = "numeric"
    TEXT = "text"
    TIMESTAMP = "timestamp"
    IDENTIFIER = "identifier"  # personal data: removed by the privacy step
    IGNORE = "ignore"  # row numbers, empty columns: kept out of the analysis


class SurveyFileError(ValueError):
    """Raised when an uploaded file cannot be read as a survey table."""


# --------------------------------------------------------------------------- #
# Reading files
# --------------------------------------------------------------------------- #
# utf-8-sig first (Google/Microsoft exports, Excel "CSV UTF-8"), then cp1256,
# the legacy Windows Arabic encoding Excel uses for plain "CSV" on Arabic systems.
_ENCODINGS = ("utf-8-sig", "cp1256", "latin-1")


def read_survey(data: bytes, filename: str) -> pd.DataFrame:
    """Read a CSV or XLSX survey export into a DataFrame of strings.

    Every cell is read as text and type detection decides later what is a
    number. Only truly empty cells become missing: answers such as "None" or
    "N/A" are kept, because they can be real answers ("Any allergies? None").

    Args:
        data: Raw file bytes.
        filename: Original file name; its extension picks the reader.

    Raises:
        SurveyFileError: Unsupported extension, unreadable content or no rows.
    """
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix in ("xlsx", "xlsm"):
        try:
            df = pd.read_excel(io.BytesIO(data), dtype=str, keep_default_na=False,
                               na_values=[""], engine="openpyxl", header=None)
        except Exception as exc:  # openpyxl raises many different errors
            raise SurveyFileError("This Excel file could not be read.") from exc
    elif suffix in ("csv", "txt"):
        df = _read_csv(data)
    else:
        raise SurveyFileError("Please upload a .csv or .xlsx file.")

    # Files are read with header=None and the first row is promoted here, so we
    # control how duplicate headers are renamed (pandas would use "Q.1").
    if df.empty:
        raise SurveyFileError("The file is empty.")
    df.columns = _clean_headers(df.iloc[0].tolist())
    df = df.iloc[1:]
    # Whitespace-only cells are missing too.
    df = df.apply(lambda col: col.str.strip()).replace("", pd.NA)
    df = df.dropna(how="all").reset_index(drop=True)
    if df.empty or df.shape[1] == 0:
        raise SurveyFileError("The file has no responses.")
    return df


def _read_csv(data: bytes) -> pd.DataFrame:
    text = None
    for encoding in _ENCODINGS:
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:  # pragma: no cover - latin-1 decodes any byte string
        raise SurveyFileError("Could not detect the file's text encoding.")
    try:
        delimiter = csv.Sniffer().sniff(text[:5000], delimiters=",;\t").delimiter
    except csv.Error:
        delimiter = ","
    try:
        return pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str, header=None,
                           keep_default_na=False, na_values=[""])
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise SurveyFileError("This CSV file could not be parsed.") from exc


def _clean_headers(columns: list[object]) -> list[str]:
    """Strip whitespace from headers and make duplicates unique (Q, Q (2), ...)."""
    seen: dict[str, int] = {}
    cleaned: list[str] = []
    for i, raw in enumerate(columns):
        text = "" if raw is None or pd.isna(raw) else str(raw)  # type: ignore[arg-type]
        name = " ".join(text.split()) or f"Column {i + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name} ({seen[name]})"
        else:
            seen[name] = 1
        cleaned.append(name)
    return cleaned


# --------------------------------------------------------------------------- #
# Likert scales
# --------------------------------------------------------------------------- #
# Each scale lists its levels from lowest to highest; each level accepts a few
# spellings (lower-case). The first spelling, capitalised, is the display label.
LIKERT_SCALES: dict[str, list[list[str]]] = {
    "agreement": [
        ["strongly disagree"],
        ["disagree", "somewhat disagree"],
        ["neutral", "neither agree nor disagree", "undecided"],
        ["agree", "somewhat agree"],
        ["strongly agree"],
    ],
    "frequency": [["never"], ["rarely"], ["sometimes"], ["often", "usually"],
                  ["always", "very often"]],
    "satisfaction": [
        ["very dissatisfied"],
        ["dissatisfied"],
        ["neutral", "neither satisfied nor dissatisfied"],
        ["satisfied"],
        ["very satisfied"],
    ],
    # Arabic forms phrase agreement in two common ways ("أوافق" / "موافق",
    # "أعارض" / "غير موافق"), and people often type without the hamza (اوافق).
    # The first spelling of each level is the display label.
    "agreement_ar": [
        ["أعارض بشدة", "غير موافق بشدة", "لا أوافق بشدة", "اعارض بشدة", "لا اوافق بشدة"],
        ["أعارض", "غير موافق", "لا أوافق", "اعارض", "لا اوافق"],
        ["محايد", "محايدة"],
        ["أوافق", "موافق", "موافقة", "اوافق"],
        ["أوافق بشدة", "موافق بشدة", "موافقة بشدة", "اوافق بشدة"],
    ],
}

_LIKERT_HEADER_HINT = re.compile(
    r"\b1\s*=|\(\s*1\s*[-–]\s*\d+\s*\)|\bagree|\brate\b|\brating|satisf|\blikely|\bscale",
    re.IGNORECASE,
)
_GRID_HEADER = re.compile(r"^(?P<question>.+?)\s*\[(?P<item>[^\]]+)\]\s*$")


def likert_group(column_name: str) -> str | None:
    """Return the shared question of a grid column ``"Question [item]"``, if any."""
    match = _GRID_HEADER.match(column_name)
    return match.group("question") if match else None


# --------------------------------------------------------------------------- #
# Identifier hints
# --------------------------------------------------------------------------- #
_IDENTIFIER_HEADER = re.compile(
    r"\b(full\s*)?name\b|\be-?mail\b|\bphone\b|\bmobile\b|whats\s*app|\btelephone\b"
    r"|\bstudent\s*(id|number|no)\b|\bnational\s*id\b|\buniversity\s*id\b|\bid\s*(number|no)\b"
    r"|الاسم|البريد|ايميل|إيميل|الهاتف|موبايل|واتساب|الرقم الجامعي|الرقم القومي",
    re.IGNORECASE,
)
_ROW_ID_HEADERS = {"id", "#", "no", "no.", "response id", "respondent id", "row", "s/n"}
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE_VALUE = re.compile(r"^\+?[\d\s().-]{9,20}$")
_TIME_HEADER = re.compile(r"time|date|timestamp|submitted|تاريخ|وقت", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #
@dataclass
class ColumnProfile:
    """What we detected about one column, and why.

    Attributes:
        name: Column header.
        detected_type: Our best guess; the user can change it.
        reason: Plain-English explanation of the guess.
        n_missing: Empty cells.
        n_unique: Distinct non-empty answers (after trimming and ignoring case).
        examples: A few distinct answers, to help the user check the type.
        scale_group: For Likert grid items, the shared question text.
        likert_levels: For Likert columns, the answer labels from low to high.
    """

    name: str
    detected_type: ColumnType
    reason: str
    n_missing: int
    n_unique: int
    examples: list[str] = field(default_factory=list)
    scale_group: str | None = None
    likert_levels: list[str] | None = None


def profile_columns(df: pd.DataFrame) -> list[ColumnProfile]:
    """Detect the type of every column in ``df``."""
    return [detect_column(df[name], name) for name in df.columns]


def detect_column(series: pd.Series, name: str) -> ColumnProfile:
    """Detect what kind of survey question ``series`` holds."""
    values = series.dropna().astype(str).str.strip()
    values = values[values != ""]
    n_missing = int(len(series) - len(values))
    folded = values.str.casefold()
    n_unique = int(folded.nunique())
    examples = list(dict.fromkeys(values.tolist()))[:4]

    def make(kind: ColumnType, reason: str, **extra: object) -> ColumnProfile:
        shown = [_mask_example(e) for e in examples] if kind == ColumnType.IDENTIFIER else examples
        return ColumnProfile(name, kind, reason, n_missing, n_unique, shown, **extra)  # type: ignore[arg-type]

    if values.empty:
        return make(ColumnType.IGNORE, "The column is empty.")

    # 1. Personal identifiers: by header, then by what the values look like.
    if _IDENTIFIER_HEADER.search(name):
        return make(ColumnType.IDENTIFIER, "The header looks like a personal-data field.")
    if values.str.fullmatch(EMAIL_RE).mean() >= 0.5:
        return make(ColumnType.IDENTIFIER, "Most answers are email addresses.")
    if values.str.match(_PHONE_VALUE).mean() >= 0.5 and _digits_only(values).str.len().between(
        9, 15
    ).mean() >= 0.5:
        return make(ColumnType.IDENTIFIER, "Most answers look like phone numbers or IDs.")

    numbers = pd.to_numeric(values, errors="coerce")
    numeric_share = float(numbers.notna().mean())

    # 2. Row numbers added by the form tool. Not required to be fully unique:
    #    copy-pasted duplicate rows repeat their ID, and cleaning should catch those.
    if name.casefold() in _ROW_ID_HEADERS and numeric_share == 1 and n_unique / len(values) >= 0.9:
        return make(ColumnType.IGNORE, "A row number added by the form tool.")

    # 3. Timestamps.
    if numeric_share < 0.5:
        parsed = pd.to_datetime(values, errors="coerce", format="mixed")
        parse_share = float(parsed.notna().mean())
        has_date_chars = values.str.contains(r"[/:-]").mean() >= 0.9
        if has_date_chars and (parse_share >= 0.95 or (_TIME_HEADER.search(name)
                                                       and parse_share >= 0.8)):
            return make(ColumnType.TIMESTAMP, "Answers are dates/times.")

    # 4. Likert: text labels from a known scale...
    scale = _match_likert_labels(folded)
    group = likert_group(name)
    if scale is not None:
        levels = [level[0].capitalize() for level in LIKERT_SCALES[scale]]
        return make(ColumnType.LIKERT,
                    f"Answers are {scale.split('_')[0]} labels ({levels[0]} … {levels[-1]}).",
                    scale_group=group, likert_levels=levels)

    # ...or small whole numbers when the header says it is a rating.
    if numeric_share >= 0.95:
        whole = numbers.dropna()
        is_small_scale = (
            (whole % 1 == 0).all() and whole.min() >= 0 and whole.max() <= 10
            and 2 <= whole.nunique() <= 11
        )
        if is_small_scale and (group or _LIKERT_HEADER_HINT.search(name)):
            low, high = int(whole.min()), int(whole.max())
            low = min(low, 1)
            return make(ColumnType.LIKERT,
                        f"Whole numbers {low}-{high} and the header describes a rating.",
                        scale_group=group, likert_levels=[str(i) for i in range(low, high + 1)])
        # 5. Numeric.
        return make(ColumnType.NUMERIC, "Answers are numbers.")

    # 6. Multiple choice: answers are lists of a small set of repeated options.
    if _looks_multiple_choice(values):
        return make(ColumnType.MULTIPLE_CHOICE,
                    "Answers are lists of a few repeated options separated by commas.")

    # 7. Single choice: few distinct answers that repeat a lot.
    unique_ratio = n_unique / len(values)
    if n_unique <= 12 or (n_unique <= 30 and unique_ratio <= 0.1):
        return make(ColumnType.SINGLE_CHOICE, f"{n_unique} distinct answers that repeat.")

    # 8. Everything else is open-ended text.
    return make(ColumnType.TEXT, "Mostly unique, written answers.")


def _match_likert_labels(folded: pd.Series) -> str | None:
    """Return the name of the Likert scale that covers >= 95% of the answers."""
    best, best_share = None, 0.0
    for scale, levels in LIKERT_SCALES.items():
        accepted = {spelling for level in levels for spelling in level}
        share = float(folded.isin(accepted).mean())
        if share > best_share and folded[folded.isin(accepted)].nunique() >= 2:
            best, best_share = scale, share
    return best if best_share >= 0.95 else None


def likert_score(value: object, levels: list[str]) -> float | None:
    """Convert one Likert answer to a number (``"Agree"`` -> 4, ``"3"`` -> 3).

    Numeric scales return the number itself. Text answers return their 1-based
    position in ``levels``, also accepting the alternative spellings of the
    matching scale (``"Somewhat agree"`` counts as ``"Agree"``).
    """
    if value is None or pd.isna(value):  # type: ignore[arg-type]
        return None
    text = str(value).strip().casefold()
    if levels and levels[0].lstrip("-").isdigit():
        try:
            return float(text)
        except ValueError:
            return None
    for scale_levels in LIKERT_SCALES.values():
        if [lvl[0].capitalize() for lvl in scale_levels] == levels:
            for i, spellings in enumerate(scale_levels):
                if text in spellings:
                    return float(i + 1)
    folded = [label.casefold() for label in levels]
    return float(folded.index(text) + 1) if text in folded else None


def _looks_multiple_choice(values: pd.Series) -> bool:
    separator = ";" if values.str.contains(";").mean() > values.str.contains(",").mean() else ","
    has_separator = values.str.contains(separator, regex=False).mean()
    if has_separator < 0.1:
        return False
    tokens = values.str.split(separator).explode().str.strip().str.casefold()
    tokens = tokens[tokens != ""]
    n_unique_tokens = tokens.nunique()
    return bool(
        n_unique_tokens <= 25
        and n_unique_tokens / len(tokens) <= 0.2
        and tokens.str.len().mean() <= 40
    )


def _digits_only(values: pd.Series) -> pd.Series:
    return values.str.replace(r"\D", "", regex=True)


def _mask_example(value: str) -> str:
    """Hide most of a personal value so examples can be shown safely."""
    if len(value) <= 2:
        return "•" * len(value)
    return value[0] + "•" * (min(len(value), 10) - 2) + value[-1]
