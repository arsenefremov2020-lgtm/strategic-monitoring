"""Period parsing and period-state helpers."""

from __future__ import annotations

import re
from typing import Literal

import pandas as pd

PeriodState = Literal["active", "not_started", "ended", "unknown_period"]


def clean_text(value: object) -> str:
    """Return a stripped string while preserving non-empty textual content."""
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def quarter_to_number(value: object) -> int:
    """Convert Ukrainian/Roman/Arabic quarter labels into an integer 1-4."""
    text = clean_text(value).upper().replace("КВАРТАЛ", "").replace("КВ.", "").strip()
    mapping = {"I": 1, "ІІ": 2, "II": 2, "III": 3, "IV": 4, "1": 1, "2": 2, "3": 3, "4": 4}
    if text in mapping:
        return mapping[text]
    match = re.search(r"[1-4]", text)
    return int(match.group(0)) if match else 1


def quarter_to_roman(value: object) -> str:
    """Convert a quarter label into I, II, III or IV."""
    return {1: "I", 2: "II", 3: "III", 4: "IV"}.get(quarter_to_number(value), "I")


def parse_period(value: object) -> int | None:
    """Convert text like 'I квартал 2026' into 20261; return None if unavailable."""
    text = clean_text(value)
    if not text:
        return None
    year_match = re.search(r"20\d{2}", text)
    if not year_match:
        return None
    year = int(year_match.group(0))
    q = quarter_to_number(text)
    return year * 10 + q


def get_period_state(start_num: object, end_num: object, selected_period_num: int) -> PeriodState:
    """Classify a measure relative to the selected reporting period."""
    start_missing = pd.isna(start_num) if start_num is not None else True
    end_missing = pd.isna(end_num) if end_num is not None else True
    if start_missing and end_missing:
        return "unknown_period"
    if not start_missing and int(start_num) > selected_period_num:
        return "not_started"
    if not end_missing and int(end_num) < selected_period_num:
        return "ended"
    return "active"


def is_measure_not_started(start_num: object, selected_period_num: int) -> bool:
    """Return True when a measure starts after the selected period."""
    return False if start_num is None or pd.isna(start_num) else int(start_num) > selected_period_num
