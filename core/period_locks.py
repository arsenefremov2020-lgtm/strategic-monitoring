"""Централізовані винятки періодів, у яких моніторинг не проводиться."""

from __future__ import annotations

from typing import Iterable

import pandas as pd
import streamlit as st

from core.db import fetch_all
from core.errors import log_cosmetic_error
from core.periods import quarter_key


def _year_key(value: object) -> str:
    text = str(value or "").strip()
    try:
        return str(int(float(text)))
    except (TypeError, ValueError):
        return text


def _quarter_num(value: object) -> int | None:
    q = quarter_key(value)
    return {"I": 1, "II": 2, "III": 3, "IV": 4}.get(q)


@st.cache_data(ttl=300, show_spinner=False)
def load_locked_periods() -> set[tuple[str, int]]:
    """Завантажує активні period_locks; до міграції безпечно повертає порожню множину."""
    try:
        rows = fetch_all(
            "period_locks",
            "year,quarter,locked",
            filters=[("eq", "locked", True)],
            order=("year", False),
        )
    except Exception as exc:
        log_cosmetic_error("Читання period_locks (таблиця може ще не існувати)", exc)
        return set()

    result: set[tuple[str, int]] = set()
    for row in rows or []:
        year = _year_key(row.get("year"))
        q_num = _quarter_num(row.get("quarter"))
        if year and q_num:
            result.add((year, q_num))
    return result


def is_period_locked(year: object, quarter: object, locked_periods: Iterable[tuple[str, int]] | None = None) -> bool:
    """True, якщо моніторинг для (рік, квартал) централізовано вимкнено."""
    periods = set(locked_periods) if locked_periods is not None else load_locked_periods()
    q_num = _quarter_num(quarter)
    return bool(q_num and (_year_key(year), q_num) in periods)


def all_periods_locked(years: Iterable[object], quarters: Iterable[object]) -> bool:
    """True, коли кожна обрана комбінація рік×квартал заблокована."""
    combos = [(year, quarter) for year in (years or []) for quarter in (quarters or [])]
    return bool(combos) and all(is_period_locked(year, quarter) for year, quarter in combos)


def unlocked_periods(years: Iterable[object], quarters: Iterable[object]) -> list[tuple[object, object]]:
    return [
        (year, quarter)
        for year in (years or [])
        for quarter in (quarters or [])
        if not is_period_locked(year, quarter)
    ]


def locked_mask(df: pd.DataFrame, year_col: str = "year", quarter_col: str = "quarter") -> pd.Series:
    if df is None or df.empty or year_col not in df.columns or quarter_col not in df.columns:
        return pd.Series(False, index=getattr(df, "index", pd.Index([])), dtype=bool)
    periods = load_locked_periods()
    return df.apply(
        lambda row: is_period_locked(row.get(year_col), row.get(quarter_col), periods),
        axis=1,
    )


def exclude_locked_periods(df: pd.DataFrame, year_col: str = "year", quarter_col: str = "quarter") -> pd.DataFrame:
    """Відсіває заблоковані квартали перед розрахунками, не змінюючи вихідні дані."""
    if df is None or df.empty:
        return df.copy() if hasattr(df, "copy") else pd.DataFrame()
    mask = locked_mask(df, year_col=year_col, quarter_col=quarter_col)
    return df.loc[~mask].copy()


def apply_locked_status(df: pd.DataFrame, status_col: str = "status", *, year_col: str = "year", quarter_col: str = "quarter") -> pd.DataFrame:
    """Для відображення примусово ставить «Не настав час» у заблокованих періодах."""
    if df is None or df.empty:
        return df.copy() if hasattr(df, "copy") else pd.DataFrame()
    result = df.copy()
    if status_col not in result.columns:
        result[status_col] = ""
    mask = locked_mask(result, year_col=year_col, quarter_col=quarter_col)
    result.loc[mask, status_col] = "Не настав час"
    return result
