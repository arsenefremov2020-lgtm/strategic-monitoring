"""Shared calculation primitives for Dashboard-derived analytical views.

This module is the single source for basic execution scoring used by the
Dashboard and Analytics. It deliberately does **not** contain or replace any
formula from pages/3_Оцінка_МіО.py: MіО remains a separate methodology.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from core import statuses as core_statuses
from core.periods import quarter_key

QUARTER_FRACTIONS = {1: 0.25, 2: 0.50, 3: 0.75, 4: 1.00}


def clean(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def normalize_text(value: Any) -> str:
    return clean(value).lower().replace("і", "i")


def to_number(value: Any) -> float | None:
    text = clean(value).replace("\u00a0", " ").replace(" ", "").replace(",", ".")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def status_display(status: Any) -> str:
    """Dashboard execution display semantics.

    Missing submission intentionally remains a zero-performing state on the
    Dashboard, as required by the management methodology, but submission
    coverage is still tracked separately by the caller.
    """
    raw = clean(status)
    if raw in {"", "Не подано"}:
        return "Не виконано"
    disp = core_statuses.status_display(raw)
    if disp == core_statuses.ST_NOTYET:
        return "Не настав час"
    if disp == core_statuses.ST_OBSOLETE:
        return "Втратило актуальність"
    return disp


def status_score(status: Any) -> float | None:
    return core_statuses.status_score(status)


def plan_fact_percent(actual: Any, target: Any) -> float | None:
    actual_num = to_number(actual)
    target_num = to_number(target)
    actual_text = normalize_text(actual)
    target_text = normalize_text(target)
    if actual_num is not None and target_num is not None and target_num != 0:
        return round(min((actual_num / target_num) * 100, 100), 2)
    yes = {"так", "yes"}
    no = {"нi", "ні", "no"}
    if target_text in yes or actual_text in yes | no:
        if actual_text in yes:
            return 100.0
        if actual_text in no:
            return 0.0
    return None


def is_quantitative_plan_fact(actual: Any, target: Any) -> bool:
    actual_num = to_number(actual)
    target_num = to_number(target)
    return actual_num is not None and target_num is not None and target_num != 0


def traffic_light(score: Any) -> str:
    if score is None or pd.isna(score):
        return "⚪ Не оцінюється"
    score = float(score)
    if score >= 100:
        return "🟢 У графіку"
    if score >= 75:
        return "🟡 Часткове виконання"
    return "🔴 Відстає"


def expected_completion_for_quarter(quarter_num: Any) -> float:
    try:
        q = int(quarter_num)
    except (TypeError, ValueError):
        q = 4
    return round(QUARTER_FRACTIONS.get(q, 1.0) * 100, 2)


def deviation_for_period(completion: Any, quarter_num: Any) -> float:
    expected = expected_completion_for_quarter(quarter_num)
    return round(float(completion or 0) - expected, 2)


def latest_approved_records(requests_df: pd.DataFrame, year: Any, quarter: Any) -> pd.DataFrame:
    """One final-approved measure request per code for an exact period."""
    if requests_df is None or requests_df.empty:
        return pd.DataFrame(columns=["strat_code"])
    data = requests_df.copy()
    for col in ["id", "year", "quarter", "strat_code", "approval_status", "submitted_at", "object_kind"]:
        if col not in data.columns:
            data[col] = ""
    data = data[
        (pd.to_numeric(data["year"], errors="coerce") == int(year))
        & (data["quarter"].map(quarter_key) == quarter_key(quarter))
        & (data["approval_status"].astype(str).str.strip() == "Погоджено")
        & (data["object_kind"].fillna("measure").astype(str).str.strip().str.lower() != "indicator")
    ].copy()
    if data.empty:
        return data
    data["_submitted_sort"] = pd.to_datetime(data["submitted_at"], errors="coerce", utc=True)
    data["_id_sort"] = pd.to_numeric(data["id"], errors="coerce").fillna(-1)
    return (
        data.sort_values(["strat_code", "_submitted_sort", "_id_sort"], na_position="first")
        .groupby("strat_code", as_index=False, sort=False)
        .tail(1)
        .drop(columns=["_submitted_sort", "_id_sort"])
    )


def performance_score(status: Any, actual: Any, target: Any) -> float | None:
    ratio = plan_fact_percent(actual, target)
    return ratio if ratio is not None else status_score(status)


def is_problem(status: Any, performance: Any, *, has_risk: bool = False) -> bool:
    """Shared basic problem flag for analytical views.

    Mirrors the Dashboard's management threshold: missing data, an explicit
    risk, or performance below 75% requires attention. Non-assessable statuses
    are not labelled problematic solely because their score is missing.
    """
    display = status_display(status)
    if display in {"Не настав час", "Втратило актуальність"}:
        return bool(has_risk)
    if clean(status) in {"", "Не подано"}:
        return True
    if has_risk:
        return True
    if performance is None or pd.isna(performance):
        return False
    return float(performance) < 75

DASHBOARD_FORMULA_VERSION = "dashboard-execution-v1"


def build_period_kpi_snapshot(
    strat_df: pd.DataFrame,
    requests_df: pd.DataFrame,
    year: int,
    quarter: Any,
) -> dict[str, Any]:
    """Freeze the Dashboard execution/coverage KPI for one exact period.

    The function intentionally contains only the stable primitives needed by
    the historical line.  It does not import the Streamlit page and therefore
    can be used by the archive job.  Missing submissions keep the Dashboard's
    conservative score of zero, while non-assessable statuses are excluded.
    """
    from core import periods as core_periods

    if strat_df is None or strat_df.empty:
        return {
            "year": int(year),
            "quarter": core_periods.quarter_to_roman(quarter),
            "execution": 0.0,
            "coverage": 0.0,
            "formula_version": DASHBOARD_FORMULA_VERSION,
            "population_size": 0,
        }

    measures = strat_df[strat_df.get("object_type", "").astype(str) == "measure"].copy()
    if measures.empty:
        return {
            "year": int(year),
            "quarter": core_periods.quarter_to_roman(quarter),
            "execution": 0.0,
            "coverage": 0.0,
            "formula_version": DASHBOARD_FORMULA_VERSION,
            "population_size": 0,
        }

    selected_period = core_periods.period_number(year, quarter)
    measures["_active"] = measures.apply(
        lambda row: core_periods.get_period_state(
            core_periods.parse_period(row.get("measure_start_date", row.get("start_period", ""))),
            core_periods.parse_period(row.get("measure_end_date", row.get("end_period", ""))),
            selected_period,
        ) == "active",
        axis=1,
    )
    active = measures[measures["_active"]].copy()
    if active.empty:
        return {
            "year": int(year),
            "quarter": core_periods.quarter_to_roman(quarter),
            "execution": 0.0,
            "coverage": 0.0,
            "formula_version": DASHBOARD_FORMULA_VERSION,
            "population_size": 0,
        }

    period_requests = latest_approved_records(requests_df, year, quarter)
    request_cols = [
        col for col in ["strat_code", "status", "numeric_value", "value_text"]
        if col in period_requests.columns
    ]
    merged = active.merge(
        period_requests[request_cols] if request_cols else pd.DataFrame(columns=["strat_code"]),
        left_on="code",
        right_on="strat_code",
        how="left",
    )
    if "status" not in merged.columns:
        merged["status"] = ""
    merged["_submitted"] = merged["strat_code"].notna()
    merged["status"] = merged["status"].fillna("Не подано")
    target_col = f"target_{int(year)}"
    merged["_target"] = merged[target_col] if target_col in merged.columns else ""
    if "numeric_value" not in merged.columns:
        merged["numeric_value"] = None
    if "value_text" not in merged.columns:
        merged["value_text"] = None
    merged["_actual"] = merged.apply(
        lambda row: row.get("numeric_value")
        if clean(row.get("numeric_value"))
        else row.get("value_text"),
        axis=1,
    )
    merged["_display"] = merged["status"].map(status_display)
    merged["_assessed"] = ~merged["_display"].isin({"Не настав час", "Втратило актуальність"})
    merged["_performance"] = merged.apply(
        lambda row: performance_score(row.get("status"), row.get("_actual"), row.get("_target")),
        axis=1,
    )
    assessed = merged[merged["_assessed"]].copy()
    execution = 0.0 if assessed.empty else round(
        pd.to_numeric(assessed["_performance"], errors="coerce").fillna(0).mean(), 2
    )
    coverage = round(float(merged["_submitted"].sum()) / len(merged) * 100, 2) if len(merged) else 0.0
    return {
        "year": int(year),
        "quarter": core_periods.quarter_to_roman(quarter),
        "execution": float(execution),
        "coverage": float(coverage),
        "formula_version": DASHBOARD_FORMULA_VERSION,
        "population_size": int(len(merged)),
    }
