"""Period parsing and period-state helpers."""

from __future__ import annotations

import re
from typing import Literal

import pandas as pd

PeriodState = Literal["active", "not_started", "ended", "unknown_period"]


def clean_text(value: object) -> str:
    """Return a stripped string while preserving non-empty textual content."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _normalise_period_text(value: object) -> str:
    text = clean_text(value).upper().replace("\u00a0", " ")
    text = text.replace("\u0406", "I").replace("\u0407", "I").replace("\u04C0", "I")
    return re.sub(r"\s+", " ", text).strip()


def _extract_quarter_number(value: object) -> int | None:
    """Extract a quarter from a period label without confusing it with the year."""
    text = _normalise_period_text(value)
    if not text:
        return None

    without_year = re.sub(r"20\d{2}", " ", text)
    without_year = re.sub(r"\s+", " ", without_year).strip(" .,-–—")

    if "9 МІСЯЦ" in without_year or "9 МIСЯЦ" in without_year:
        return 3
    if "ПІВРІЧЧ" in without_year or "ПIВРIЧЧ" in without_year:
        return 2
    if without_year in {"РІК", "РIК", "ВЕСЬ РІК", "ВЕСЬ РIК"}:
        return 4

    digit_match = re.search(
        r"(?<!\d)([1-4])(?:-?(?:Й|ИЙ|А|Я))?\s*(?:КВАРТАЛ|КВ\.?)(?!\w)",
        without_year,
    )
    if digit_match:
        return int(digit_match.group(1))

    roman_match = re.search(r"(?<![A-Z])(IV|III|II|I)(?![A-Z])", without_year)
    if roman_match:
        return {"I": 1, "II": 2, "III": 3, "IV": 4}[roman_match.group(1)]

    plain = (
        without_year.replace("КВАРТАЛ", "")
        .replace("КВ.", "")
        .replace("КВ", "")
        .strip(" .,-–—")
    )
    return {"I": 1, "II": 2, "III": 3, "IV": 4, "1": 1, "2": 2, "3": 3, "4": 4}.get(plain)


def quarter_to_number(value: object) -> int:
    """Convert Ukrainian/Roman/Arabic quarter labels into an integer 1-4."""
    return _extract_quarter_number(value) or 1


def quarter_to_roman(value: object) -> str:
    """Convert a quarter label into I, II, III or IV."""
    return {1: "I", 2: "II", 3: "III", 4: "IV"}.get(quarter_to_number(value), "I")


def parse_period(value: object) -> int | None:
    """Convert a period label into YYYYQ; return None when year or quarter is unavailable."""
    text = clean_text(value)
    if not text:
        return None
    year_match = re.search(r"20\d{2}", text)
    quarter = _extract_quarter_number(text)
    if not year_match or quarter is None:
        return None
    return int(year_match.group(0)) * 10 + quarter


def period_number(year: object, quarter: object) -> int:
    """Return a sortable YYYYQ number for a separate year and quarter value."""
    year_match = re.search(r"20\d{2}", clean_text(year))
    if not year_match:
        raise ValueError(f"Invalid reporting year: {year!r}")
    return int(year_match.group(0)) * 10 + quarter_to_number(quarter)


def period_label(year: object, quarter: object) -> str:
    """Return a compact reporting-period label, for example ``2026 III``."""
    year_match = re.search(r"20\d{2}", clean_text(year))
    year_text = year_match.group(0) if year_match else clean_text(year)
    return f"{year_text} {quarter_to_roman(quarter)}".strip()


def get_period_state(start_num: object, end_num: object, selected_period_num: int) -> PeriodState:
    """Classify a measure relative to the selected reporting period.

    A measure is active only when both boundaries are known and the selected
    reporting period lies inside the inclusive interval.
    """
    start_missing = start_num is None
    end_missing = end_num is None
    try:
        start_missing = start_missing or bool(pd.isna(start_num))
    except (TypeError, ValueError):
        pass
    try:
        end_missing = end_missing or bool(pd.isna(end_num))
    except (TypeError, ValueError):
        pass

    if start_missing or end_missing:
        return "unknown_period"
    if int(start_num) > selected_period_num:
        return "not_started"
    if int(end_num) < selected_period_num:
        return "ended"
    return "active"


def is_measure_not_started(start_num: object, selected_period_num: int) -> bool:
    """Return True when a measure starts after the selected period."""
    return False if start_num is None or pd.isna(start_num) else int(start_num) > selected_period_num


def quarter_key(value) -> str:
    """Нормалізує позначення кварталу до I / II / III / IV (латиниця),
    стійко до кирилиці та словесних періодів («I півріччя», «9 місяців», «РІК»).
    ЄДИНА версія для всіх сторінок (правка К8)."""
    t = _normalise_period_text(value)
    t = t.replace("КВАРТАЛ", "").replace(".", "").strip()
    if t in ("1", "I"):
        return "I"
    if t in ("2", "II", "ПІВРІЧЧЯ", "ПIВРIЧЧЯ", "I ПІВРІЧЧЯ", "I ПIВРIЧЧЯ"):
        return "II"
    if t in ("3", "III", "9 МІСЯЦІВ", "9 МIСЯЦIВ"):
        return "III"
    if t in ("4", "IV", "РІК", "РIК"):
        return "IV"
    extracted = _extract_quarter_number(value)
    return {1: "I", 2: "II", 3: "III", 4: "IV"}.get(extracted, t)
