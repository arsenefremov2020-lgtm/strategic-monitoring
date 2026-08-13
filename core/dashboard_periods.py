"""Quarter-period semantics for Dashboard execution v3.

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
from core.timeutils import now_kyiv

EXCLUDED_EXECUTION_STATUSES = {"Не настав час", "Втратило актуальність"}
APPROVED_STATUS = "Погоджено"
QUARTER_NUM = {"I": 1, "II": 2, "III": 3, "IV": 4}
QUARTER_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}


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

    # ``period_locks`` is the only centralized mechanism that disables
    # monitoring. Passing an explicit set keeps archive reconstruction/tests
    # pure while production reads the live lock table.
    if locked_periods is None:
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


def reporting_period_range(
    start_year: Any,
    start_quarter: Any,
    end_year: Any,
    end_quarter: Any,
) -> list[tuple[int, str]]:
    """Return an inclusive chronological reporting-quarter range.

    Year and quarter are treated as one period identity. The helper never
    creates a Cartesian product and never silently swaps an invalid range.
    """
    start_y = int(float(start_year))
    end_y = int(float(end_year))
    start_q = QUARTER_NUM[quarter_to_roman(start_quarter)]
    end_q = QUARTER_NUM[quarter_to_roman(end_quarter)]
    start_num = start_y * 10 + start_q
    end_num = end_y * 10 + end_q
    if start_num > end_num:
        raise ValueError("Початок періоду не може бути пізніше за кінець періоду.")

    result: list[tuple[int, str]] = []
    year, quarter = start_y, start_q
    while (year * 10 + quarter) <= end_num:
        result.append((year, QUARTER_ROMAN[quarter]))
        quarter += 1
        if quarter > 4:
            year += 1
            quarter = 1
    return result


def _calendar_ceiling(as_of: Any = None) -> tuple[int, int]:
    moment = pd.Timestamp(now_kyiv() if as_of is None else as_of)
    if pd.isna(moment):
        raise ValueError(f"Invalid as_of value: {as_of!r}")
    return int(moment.year), _quarter_from_month(int(moment.month))


def latest_reporting_period_in_year(
    requests_df: pd.DataFrame | None,
    year: int,
    *,
    locked_periods: Iterable[tuple[Any, Any]] | None = None,
    as_of: Any = None,
) -> tuple[int, str] | None:
    """Latest real, unlocked reporting period with data inside one year.

    Future quarters are excluded by the Kyiv-calendar ceiling. Unlike the
    system fallback, this helper does not invent a reporting quarter when the
    selected finance year has no reporting data.
    """
    if locked_periods is None:
        try:
            from core.period_locks import load_locked_periods
            locked_periods = load_locked_periods()
        except Exception:
            locked_periods = set()

    selected_year = int(year)
    calendar_year, calendar_quarter = _calendar_ceiling(as_of)
    if selected_year > calendar_year:
        return None
    ceiling_q = 4 if selected_year < calendar_year else calendar_quarter

    if requests_df is None or requests_df.empty:
        return None
    data = _prepare_requests(requests_df, approved_only=False)
    candidates: list[int] = []
    for _, row in data.iterrows():
        row_period = pd.to_numeric(pd.Series([row.get("_period")]), errors="coerce").iloc[0]
        if pd.isna(row_period):
            continue
        row_period = int(row_period)
        row_year, row_quarter = row_period // 10, row_period % 10
        if (
            row_year == selected_year
            and row_quarter in QUARTER_ROMAN
            and row_quarter <= ceiling_q
            and monitoring_conducted(row_year, row_quarter, locked_periods)
        ):
            candidates.append(int(row_quarter))
    if not candidates:
        return None
    quarter = max(candidates)
    return selected_year, QUARTER_ROMAN[quarter]


def current_reporting_period(
    requests_df: pd.DataFrame | None = None,
    *,
    locked_periods: Iterable[tuple[Any, Any]] | None = None,
    fallback_year: int | None = None,
    fallback_quarter: int | None = None,
    as_of: Any = None,
) -> tuple[int, str]:
    """Latest real unlocked reporting period not later than today in Kyiv.

    Monitoring rows from future calendar quarters can never move the default
    reporting period forward. If no real reporting rows exist, the fallback is
    the latest non-future, unlocked quarter.
    """
    if locked_periods is None:
        try:
            from core.period_locks import load_locked_periods
            locked_periods = load_locked_periods()
        except Exception:
            locked_periods = set()

    calendar_year, calendar_quarter = _calendar_ceiling(as_of)
    calendar_ceiling = calendar_year * 10 + calendar_quarter

    candidates: list[tuple[int, int]] = []
    if requests_df is not None and not requests_df.empty:
        data = _prepare_requests(requests_df, approved_only=False)
        for _, row in data.iterrows():
            row_period = pd.to_numeric(pd.Series([row.get("_period")]), errors="coerce").iloc[0]
            if pd.isna(row_period):
                continue
            candidate_num = int(row_period)
            y, q = candidate_num // 10, candidate_num % 10
            if q not in QUARTER_ROMAN or candidate_num > calendar_ceiling:
                continue
            if monitoring_conducted(y, q, locked_periods):
                candidates.append((y, q))
    if candidates:
        y, q = max(candidates)
        return y, QUARTER_ROMAN[q]

    if fallback_year is not None and fallback_quarter is not None:
        y, q = int(fallback_year), int(fallback_quarter)
        if y * 10 + q > calendar_ceiling:
            y, q = calendar_year, calendar_quarter
    else:
        y, q = calendar_year, calendar_quarter

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
