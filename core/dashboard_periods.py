"""Quarter-period semantics for Dashboard execution v2.

This module is the single source of truth for reporting-period applicability.
It contains no Streamlit code and performs no writes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import re
from typing import Any, Iterable

import pandas as pd

from core.periods import period_number, quarter_key, quarter_to_roman

EXCLUDED_EXECUTION_STATUSES = {"Не настав час", "Втратило актуальність"}
APPROVED_STATUS = "Погоджено"
QUARTER_NUM = {"I": 1, "II": 2, "III": 3, "IV": 4}
QUARTER_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}

# Historical reporting periods in which monitoring was not conducted.
# Kept centrally so UI pages and trajectory history cannot diverge.
SYSTEM_MONITORING_NOT_CONDUCTED = {("2026", 1), ("2026", 2)}


def clean(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null", "nat"} else text


def normalize_code(value: Any) -> str:
    return clean(value)


def _quarter_from_month(month: int) -> int:
    return ((int(month) - 1) // 3) + 1


def parse_measure_period(value: Any, *, end: bool = False) -> int | None:
    """Parse a strategic-matrix boundary into sortable ``YYYYQ``.

    A bare year is deliberately handled *before* generic date parsing because
    ``pandas.to_datetime('2026')`` may interpret it as a date-like value.  A
    bare start year means Q1; a bare end year means Q4.
    """
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, (pd.Timestamp, datetime, date)):
        ts = pd.Timestamp(value)
        return int(ts.year) * 10 + _quarter_from_month(ts.month)

    text = clean(value)
    if not text:
        return None

    bare_year = re.fullmatch(r"\s*(20\d{2})\s*", text)
    if bare_year:
        return int(bare_year.group(1)) * 10 + (4 if end else 1)

    year_match = re.search(r"20\d{2}", text)
    if year_match:
        q = quarter_key(text)
        q_num = QUARTER_NUM.get(q)
        if q_num:
            return int(year_match.group(0)) * 10 + q_num

    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.notna(parsed):
        return int(parsed.year) * 10 + _quarter_from_month(parsed.month)
    return None


def period_state(start_period: int | None, end_period: int | None, selected_period: int) -> str:
    """Return ``future`` / ``active`` / ``ended`` / ``unknown_period``.

    Missing or unparseable applicability boundaries are never silently treated
    as active.  Such rows remain visible to data-quality checks but are excluded
    from execution/risk until applicability is resolved.
    """
    if start_period is None or end_period is None:
        return "unknown_period"
    if int(start_period) > int(selected_period):
        return "future"
    if int(end_period) < int(selected_period):
        return "ended"
    return "active"


def _normalise_locked_periods(locked_periods: Iterable[tuple[Any, Any]] | None) -> set[tuple[str, int]]:
    result: set[tuple[str, int]] = set()
    for year, quarter in locked_periods or []:
        try:
            y = str(int(float(year)))
        except (TypeError, ValueError):
            y = clean(year)
        q_num = QUARTER_NUM.get(quarter_to_roman(quarter))
        if y and q_num:
            result.add((y, q_num))
    return result


def monitoring_conducted(
    year: Any,
    quarter: Any,
    locked_periods: Iterable[tuple[Any, Any]] | None = None,
) -> bool:
    q_num = QUARTER_NUM.get(quarter_to_roman(quarter))
    try:
        year_key = str(int(float(year)))
    except (TypeError, ValueError):
        year_key = clean(year)
    if not q_num or not year_key:
        return False

    # ``locked_periods=None`` means production/system semantics: historical
    # non-monitoring periods plus live period_locks.  Passing an explicit set
    # is a pure-calculation override used by archive reconstruction/tests.
    if locked_periods is None:
        if (year_key, q_num) in SYSTEM_MONITORING_NOT_CONDUCTED:
            return False
        try:
            from core.period_locks import is_period_locked
            return not is_period_locked(year, quarter)
        except Exception:
            return True
    return (year_key, q_num) not in _normalise_locked_periods(locked_periods)


def _safe_period_number(year: Any, quarter: Any) -> int | None:
    try:
        return period_number(year, quarter)
    except Exception:
        return None


def _prepare_requests(requests_df: pd.DataFrame, *, approved_only: bool) -> pd.DataFrame:
    if requests_df is None or requests_df.empty:
        return pd.DataFrame(columns=["strat_code", "_period"])
    data = requests_df.copy()
    if "_auto_inherited" in data.columns:
        data = data.loc[~data["_auto_inherited"].eq(True)].copy()
    for col in [
        "id", "year", "quarter", "strat_code", "status", "approval_status",
        "submitted_at", "updated_at", "object_kind", "numeric_value", "value_text",
        "risks", "progress_text", "npa_link",
    ]:
        if col not in data.columns:
            data[col] = ""
    kind = data["object_kind"].fillna("").astype(str).str.strip().str.lower()
    data = data[kind.ne("indicator")].copy()
    if approved_only:
        data = data[data["approval_status"].astype(str).str.strip().eq(APPROVED_STATUS)].copy()
    data["_period"] = data.apply(lambda r: _safe_period_number(r.get("year"), r.get("quarter")), axis=1)
    return data


def _latest_per_code(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return data
    data = data.copy()
    data["_updated_sort"] = pd.to_datetime(data["updated_at"], errors="coerce", utc=True)
    data["_submitted_sort"] = pd.to_datetime(data["submitted_at"], errors="coerce", utc=True)
    data["_id_sort"] = pd.to_numeric(data["id"], errors="coerce").fillna(-1)
    sort_cols = ["strat_code", "_period", "_updated_sort", "_submitted_sort", "_id_sort"]
    return (
        data.sort_values(sort_cols, na_position="first")
        .groupby("strat_code", as_index=False, sort=False)
        .tail(1)
        .drop(columns=["_updated_sort", "_submitted_sort", "_id_sort"], errors="ignore")
        .reset_index(drop=True)
    )


def latest_approved_exact_period(
    requests_df: pd.DataFrame,
    year: int,
    quarter: Any,
    *,
    approved_only: bool = True,
    locked_periods: Iterable[tuple[Any, Any]] | None = None,
) -> pd.DataFrame:
    """Newest real measure submission in exactly one *valid* reporting period."""
    if not monitoring_conducted(year, quarter, locked_periods):
        return pd.DataFrame(columns=["strat_code"])
    data = _prepare_requests(requests_df, approved_only=approved_only)
    selected = _safe_period_number(year, quarter)
    data = data[data["_period"].eq(selected)].copy()
    return _latest_per_code(data).drop(columns=["_period"], errors="ignore")


def latest_approved_up_to_period(
    requests_df: pd.DataFrame,
    selected_year: int,
    selected_quarter: Any,
    *,
    approved_only: bool = True,
    locked_periods: Iterable[tuple[Any, Any]] | None = None,
) -> pd.DataFrame:
    """Newest effective real submission not later than the selected period.

    Records from locked / monitoring-not-conducted quarters are excluded even
    when rows accidentally exist in the database.
    """
    data = _prepare_requests(requests_df, approved_only=approved_only)
    selected = _safe_period_number(selected_year, selected_quarter)
    if selected is None or data.empty:
        return data.iloc[0:0].copy()
    data = data[data["_period"].notna() & (data["_period"] <= selected)].copy()
    if data.empty:
        return data
    data = data[data.apply(
        lambda r: monitoring_conducted(r.get("year"), r.get("quarter"), locked_periods),
        axis=1,
    )].copy()
    return _latest_per_code(data).drop(columns=["_period"], errors="ignore")


def valid_observation_history(
    requests_df: pd.DataFrame,
    code: Any,
    year: int,
    *,
    approved_only: bool = True,
    locked_periods: Iterable[tuple[Any, Any]] | None = None,
) -> pd.DataFrame:
    """One real effective observation per valid quarter for trajectory work."""
    data = _prepare_requests(requests_df, approved_only=approved_only)
    code_key = clean(code)
    data = data[
        data["strat_code"].map(clean).eq(code_key)
        & pd.to_numeric(data["year"], errors="coerce").eq(int(year))
    ].copy()
    if data.empty:
        return data
    data = data[data.apply(
        lambda r: monitoring_conducted(r.get("year"), r.get("quarter"), locked_periods), axis=1
    )].copy()
    if data.empty:
        return data
    data = data.sort_values(["_period", "updated_at", "submitted_at", "id"], na_position="first")
    return data.groupby("_period", as_index=False, sort=False).tail(1).sort_values("_period").reset_index(drop=True)


@dataclass(frozen=True)
class PeriodContext:
    year: int
    quarter: str
    quarter_num: int
    period_num: int
    monitoring_conducted: bool


def make_period_context(
    year: Any,
    quarter: Any,
    *,
    locked_periods: Iterable[tuple[Any, Any]] | None = None,
) -> PeriodContext:
    y = int(float(year))
    q = quarter_to_roman(quarter)
    q_num = QUARTER_NUM[q]
    return PeriodContext(
        year=y,
        quarter=q,
        quarter_num=q_num,
        period_num=period_number(y, q),
        monitoring_conducted=monitoring_conducted(y, q, locked_periods),
    )


def current_reporting_period(
    requests_df: pd.DataFrame | None = None,
    *,
    locked_periods: Iterable[tuple[Any, Any]] | None = None,
    fallback_year: int | None = None,
    fallback_quarter: int | None = None,
) -> tuple[int, str]:
    """Latest real unlocked reporting period, with a completed-quarter fallback."""
    if locked_periods is None:
        try:
            from core.period_locks import load_locked_periods
            locked_periods = load_locked_periods()
        except Exception:
            locked_periods = set()

    candidates: list[tuple[int, int]] = []
    if requests_df is not None and not requests_df.empty:
        data = _prepare_requests(requests_df, approved_only=False)
        for _, row in data.iterrows():
            try:
                y = int(float(row.get("year")))
                q = QUARTER_NUM.get(quarter_to_roman(row.get("quarter")))
            except Exception:
                continue
            if q and monitoring_conducted(y, q, locked_periods):
                candidates.append((y, q))
    if candidates:
        y, q = max(candidates)
        return y, QUARTER_ROMAN[q]

    if fallback_year is not None and fallback_quarter is not None:
        y, q = int(fallback_year), int(fallback_quarter)
    else:
        from datetime import datetime as _dt
        now = _dt.now()
        current_q = _quarter_from_month(now.month)
        if current_q == 1:
            y, q = now.year - 1, 4
        else:
            y, q = now.year, current_q - 1
    while not monitoring_conducted(y, q, locked_periods):
        q -= 1
        if q < 1:
            y -= 1
            q = 4
    return y, QUARTER_ROMAN[q]


def selected_reporting_period(years: Iterable[Any], quarters: Iterable[Any]) -> tuple[int, str] | None:
    pairs = []
    for year in years or []:
        for quarter in quarters or []:
            try:
                y = int(float(year)); q = quarter_to_roman(quarter)
                pairs.append((period_number(y, q), y, q))
            except Exception:
                continue
    if not pairs:
        return None
    _, y, q = max(pairs)
    return y, q
