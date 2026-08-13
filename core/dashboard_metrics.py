"""Backward-compatible primitives for Dashboard execution v3.

Business formulas live in the specialized ``dashboard_*`` modules.  This file
keeps small compatibility helpers used by archive/older analytical code and
routes KPI snapshots to the v3 single source of truth.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from core import statuses as core_statuses
from core.dashboard_execution import (
    DASHBOARD_FORMULA_VERSION,
    normalize_status,
    numeric_attainment,
    plan_scores,
    score_measure,
    to_number,
    build_quarter_snapshot,
)
from core.dashboard_periods import clean, latest_approved_exact_period


def normalize_text(value: Any) -> str:
    return clean(value).lower().replace("і", "i")


def status_display(status: Any) -> str:
    """Legacy display primitive retained for non-v3 external callers."""
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
    _raw, execution = numeric_attainment(actual, target)
    if execution is not None:
        return round(float(execution), 2)
    scored = score_measure("", actual, target)
    return scored.get("execution_score") if scored.get("yes_no") else None


def is_quantitative_plan_fact(actual: Any, target: Any) -> bool:
    fact = to_number(actual)
    plan = to_number(target)
    return fact is not None and plan not in (None, 0)


# Legacy compatibility only.  Dashboard v3 never uses these quarter fractions
# for execution, risk, forecast or management conclusions.
QUARTER_FRACTIONS = {1: 0.25, 2: 0.50, 3: 0.75, 4: 1.00}


def traffic_light(score: Any) -> str:
    """Legacy display helper retained for external callers.

    It is intentionally not used by Dashboard v3 as an "on track / behind"
    assessment; risk is calculated in ``core.dashboard_risk``.
    """
    if score is None or pd.isna(score):
        return "⚪ Не оцінюється"
    score = float(score)
    if score >= 100:
        return "🟢 У графіку"
    if score >= 75:
        return "🟡 Часткове виконання"
    return "🔴 Відстає"


def expected_completion_for_quarter(quarter_num: Any) -> float:
    """Legacy compatibility helper; not a Dashboard v3 normative target."""
    try:
        q = int(quarter_num)
    except (TypeError, ValueError):
        q = 4
    return round(QUARTER_FRACTIONS.get(q, 1.0) * 100, 2)


def deviation_for_period(completion: Any, quarter_num: Any) -> float:
    """Legacy compatibility helper; Dashboard v3 does not consume it."""
    return round(float(completion or 0) - expected_completion_for_quarter(quarter_num), 2)

def latest_approved_records(requests_df: pd.DataFrame, year: Any, quarter: Any) -> pd.DataFrame:
    return latest_approved_exact_period(requests_df, int(year), quarter)


def performance_score(status: Any, actual: Any, target: Any) -> float | None:
    return score_measure(status, actual, target).get("execution_score")


def is_problem(status: Any, performance: Any, *, has_risk: bool = False) -> bool:
    """Legacy compatibility flag; Dashboard v3 never uses it for conclusions/risk."""
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


def build_period_kpi_snapshot(
    strat_df: pd.DataFrame,
    requests_df: pd.DataFrame,
    year: int,
    quarter: Any,
) -> dict[str, Any]:
    """Archive-compatible KPI payload calculated by the v3 shared methodology."""
    snapshot = build_quarter_snapshot(strat_df, requests_df, year, quarter)
    scores = plan_scores(snapshot)
    return {
        "year": int(year),
        "quarter": str(quarter),
        "execution": scores.get("execution_by_measures"),
        "execution_by_measures": scores.get("execution_by_measures"),
        "execution_by_goals": scores.get("execution_by_goals"),
        "coverage": scores.get("coverage"),
        "formula_version": DASHBOARD_FORMULA_VERSION,
        "population_size": int(len(snapshot)),
        "assessed_measure_count": int(scores.get("assessed_measure_count") or 0),
    }
