"""Execution scoring and hierarchy for Dashboard execution v3."""
from __future__ import annotations

import math
import re
from typing import Any, Iterable

import pandas as pd

from core.dashboard_periods import (
    EXCLUDED_EXECUTION_STATUSES,
    clean,
    latest_approved_exact_period,
    latest_approved_up_to_period,
    make_period_context,
    parse_measure_period,
    period_state,
    quarter_to_roman,
)
from core.dashboard_filters import main_ssp_deputy, main_ssp_index

DASHBOARD_FORMULA_VERSION = "dashboard-execution-v3"
STATUS_SCORE = {
    "Виконано": 100.0,
    "Частково виконано": 75.0,
    "Не виконано": 0.0,
    "Не подано": 0.0,
    "Не настав час": None,
    "Втратило актуальність": None,
}
YES_VALUES = {"так", "yes", "true", "1"}
NO_VALUES = {"ні", "нi", "no", "false", "0"}


def to_number(value: Any) -> float | None:
    text = clean(value).replace("\u00a0", " ").replace(" ", "").replace(",", ".")
    if not text:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        number = float(match.group(0))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def normalize_status(value: Any) -> str:
    text = clean(value)
    aliases = {
        "": "Не подано", "неподано": "Не подано", "не подано": "Не подано",
        "виконано": "Виконано", "частково виконано": "Частково виконано",
        "не виконано": "Не виконано", "не настав час": "Не настав час",
        "втратило актуальність": "Втратило актуальність",
    }
    return aliases.get(text.casefold(), text)


def actual_value(record: pd.Series | dict[str, Any] | None) -> Any:
    if record is None:
        return None
    numeric = record.get("numeric_value")
    return numeric if clean(numeric) else record.get("value_text")


def is_yes_no(value: Any) -> bool:
    return clean(value).casefold() in YES_VALUES | NO_VALUES


def numeric_attainment(actual: Any, target: Any) -> tuple[float | None, float | None]:
    fact, plan = to_number(actual), to_number(target)
    if fact is None or plan in (None, 0):
        return None, None
    raw = fact / plan * 100.0
    return raw, min(raw, 100.0)


def qualitative_score(status: Any) -> float | None:
    return STATUS_SCORE.get(normalize_status(status))


def data_quality_conflict(status: Any, actual: Any, target: Any) -> tuple[bool, str]:
    raw, _ = numeric_attainment(actual, target)
    if raw is None:
        return False, ""
    normalized = normalize_status(status)
    if normalized == "Частково виконано" and raw >= 100:
        return True, "Фактичне значення відповідає річному плану, але статус подано як «Частково виконано»."
    if normalized == "Не виконано" and raw >= 100:
        return True, "Фактичне значення відповідає річному плану, але статус подано як «Не виконано»."
    if normalized == "Виконано" and raw < 100:
        return True, "Статус подано як «Виконано», але фактичне значення нижче річного плану."
    return False, ""


def score_measure(status: Any, actual: Any, target: Any) -> dict[str, Any]:
    normalized = normalize_status(status)
    base = {
        "yes_no": False, "result_achieved": False,
        "data_quality_conflict": False, "data_quality_message": "",
    }
    if normalized in EXCLUDED_EXECUTION_STATUSES:
        return {**base, "execution_score": None, "raw_attainment_pct": None, "numeric": False}

    raw, execution = numeric_attainment(actual, target)
    conflict, message = data_quality_conflict(normalized, actual, target)
    if raw is not None:
        return {
            **base, "execution_score": round(float(execution), 6),
            "raw_attainment_pct": round(float(raw), 6), "numeric": True,
            "result_achieved": raw >= 100.0,
            "data_quality_conflict": conflict, "data_quality_message": message,
        }

    value_text = clean(actual).casefold()
    if value_text in YES_VALUES:
        return {**base, "execution_score": 100.0, "raw_attainment_pct": 100.0,
                "numeric": False, "yes_no": True, "result_achieved": True}
    if value_text in NO_VALUES:
        return {**base, "execution_score": 0.0, "raw_attainment_pct": 0.0,
                "numeric": False, "yes_no": True, "result_achieved": False}
    score = qualitative_score(normalized)
    return {**base, "execution_score": score, "raw_attainment_pct": None,
            "numeric": False, "result_achieved": normalized == "Виконано"}


def _measure_rows(strat_df: pd.DataFrame) -> pd.DataFrame:
    if strat_df is None or strat_df.empty or "object_type" not in strat_df.columns:
        return pd.DataFrame()
    return strat_df[strat_df["object_type"].astype(str).str.strip().eq("measure")].copy()


def _record_map(data: pd.DataFrame) -> dict[str, pd.Series]:
    if data is None or data.empty:
        return {}
    return {clean(row.get("strat_code")): row for _, row in data.iterrows() if clean(row.get("strat_code"))}


def build_quarter_snapshot(
    strat_df: pd.DataFrame,
    requests_df: pd.DataFrame,
    year: int,
    quarter: Any,
    *,
    locked_periods: Iterable[tuple[Any, Any]] | None = None,
    approved_only: bool = True,
) -> pd.DataFrame:
    """Single source of truth for one reporting quarter under v3 semantics.

    Active measures without a current-quarter submission retain the latest
    confirmed result from the *same year* for execution, while their reporting
    status remains ``Не подано`` and coverage is penalized. That carried result
    is never treated as a new trajectory observation.
    """
    ctx = make_period_context(year, quarter, locked_periods=locked_periods)
    measures = _measure_rows(strat_df)
    if measures.empty:
        return pd.DataFrame()

    exact = _record_map(latest_approved_exact_period(
        requests_df, ctx.year, ctx.quarter, approved_only=approved_only,
        locked_periods=locked_periods,
    ))
    carried = _record_map(latest_approved_up_to_period(
        requests_df, ctx.year, ctx.quarter, approved_only=approved_only,
        locked_periods=locked_periods,
    ))

    target_col = f"target_{ctx.year}"
    rows: list[dict[str, Any]] = []
    for _, measure in measures.iterrows():
        code = clean(measure.get("code"))
        start = parse_measure_period(measure.get("measure_start_date", measure.get("start_period")), end=False)
        end = parse_measure_period(measure.get("measure_end_date", measure.get("end_period")), end=True)
        state = period_state(start, end, ctx.period_num)
        if state == "future":
            continue

        exact_record = exact.get(code) if ctx.monitoring_conducted else None
        historical_record = carried.get(code) if ctx.monitoring_conducted else None
        record = None
        carry_forward = False
        carry_forward_kind = ""
        submitted_current_period = False
        has_previous_confirmed_result = False

        if ctx.monitoring_conducted:
            if state == "active":
                if exact_record is not None:
                    record = exact_record
                    submitted_current_period = True
                elif historical_record is not None:
                    # Quarterly monitoring facts are annual cumulative/YTD
                    # observations. Never carry an active result across years.
                    try:
                        historical_year = int(float(historical_record.get("year")))
                    except (TypeError, ValueError):
                        historical_year = None
                    if historical_year == ctx.year:
                        record = historical_record
                        carry_forward = True
                        carry_forward_kind = "active_previous_result"
                        has_previous_confirmed_result = True
            elif state == "ended":
                record = historical_record
                if record is not None:
                    carry_forward = True
                    carry_forward_kind = "ended_final"
                    has_previous_confirmed_result = True

        has_monitoring_data = record is not None
        effective_result_status = normalize_status(record.get("status") if record is not None else "Не подано")
        reporting_status = effective_result_status
        if state == "active" and not submitted_current_period and ctx.monitoring_conducted:
            reporting_status = "Не подано"
        fact = actual_value(record)
        target = measure.get(target_col, "")

        period_quality_issue = state == "unknown_period"
        final_missing_result = state == "ended" and record is None and ctx.monitoring_conducted
        missing_required_submission = state == "active" and not submitted_current_period and ctx.monitoring_conducted
        management_zero_due_to_missing_data = bool(missing_required_submission and record is None)

        if not ctx.monitoring_conducted:
            score = {"execution_score": None, "raw_attainment_pct": None, "numeric": False,
                     "yes_no": False, "result_achieved": False,
                     "data_quality_conflict": False, "data_quality_message": ""}
            assessed = coverage_eligible = risk_eligible = False
        elif state == "unknown_period":
            reporting_status = "Не визначено"
            score = {"execution_score": None, "raw_attainment_pct": None, "numeric": False,
                     "yes_no": False, "result_achieved": False,
                     "data_quality_conflict": True,
                     "data_quality_message": "Не вдалося визначити період застосовності заходу."}
            assessed = coverage_eligible = risk_eligible = False
        elif missing_required_submission and record is not None:
            # Keep the last confirmed same-year result for management execution,
            # but do not pretend that the current quarter was submitted.
            score = score_measure(effective_result_status, fact, target)
            assessed = score.get("execution_score") is not None
            coverage_eligible, risk_eligible = True, False
        elif missing_required_submission:
            # No confirmed result exists in the current year. Management
            # assessment uses 0 so missing data cannot inflate aggregates.
            score = {"execution_score": 0.0, "raw_attainment_pct": None, "numeric": False,
                     "yes_no": False, "result_achieved": False,
                     "data_quality_conflict": False, "data_quality_message": ""}
            assessed, coverage_eligible, risk_eligible = True, True, False
        elif final_missing_result:
            reporting_status = "Не подано"
            score = {"execution_score": 0.0, "raw_attainment_pct": None, "numeric": False,
                     "yes_no": False, "result_achieved": False,
                     "data_quality_conflict": True,
                     "data_quality_message": "Захід завершився без жодного валідного підтвердженого результату."}
            assessed, coverage_eligible, risk_eligible = True, False, False
        else:
            score = score_measure(effective_result_status, fact, target)
            assessed = score.get("execution_score") is not None
            coverage_eligible = state == "active"
            # ended/Q4 outcomes are final, not forecast-risk observations
            risk_eligible = assessed and state == "active" and reporting_status not in EXCLUDED_EXECUTION_STATUSES

        main_ssp = main_ssp_index(measure)
        deputy = main_ssp_deputy(measure)
        source_year = None
        if record is not None and clean(record.get("year")):
            try:
                source_year = int(float(record.get("year")))
            except (TypeError, ValueError):
                source_year = None
        out = measure.to_dict()
        out.update({
            "code": code,
            "goal_code": clean(measure.get("parent_goal_code")),
            "task_code": clean(measure.get("parent_task_code")),
            "strategic_goal": clean(measure.get("parent_goal_name")),
            "department": clean(measure.get("resp_main", measure.get("department"))),
            "department_co_1": clean(measure.get("resp_co_1", measure.get("department_co_1"))),
            "department_co_2": clean(measure.get("resp_co_2", measure.get("department_co_2"))),
            "main_ssp": main_ssp,
            "deputy_minister_by_ssp": deputy,
            "start_period": measure.get("measure_start_date", measure.get("start_period", "")),
            "end_period": measure.get("measure_end_date", measure.get("end_period", "")),
            "year": ctx.year, "quarter": ctx.quarter, "period_number": ctx.period_num,
            "period_label": f"{ctx.year} {ctx.quarter}",
            "period_state": state, "monitoring_conducted": ctx.monitoring_conducted,
            # ``submitted`` means current-quarter submission, not existence of
            # any historical effective result.
            "submitted": bool(submitted_current_period),
            "submitted_current_period": bool(submitted_current_period),
            "has_monitoring_data": bool(has_monitoring_data),
            "has_previous_confirmed_result": bool(has_previous_confirmed_result),
            "carry_forward": bool(carry_forward),
            "carry_forward_kind": carry_forward_kind,
            "status": reporting_status,
            "status_display": reporting_status,
            "effective_result_status": effective_result_status,
            "actual": fact, "fact_value": fact, "annual_target": target,
            "selected_target": target,
            "execution_score": score.get("execution_score"),
            "performance_score": score.get("execution_score"),
            "raw_attainment_pct": score.get("raw_attainment_pct"),
            "numeric": bool(score.get("numeric", False)),
            "yes_no": bool(score.get("yes_no", is_yes_no(fact))),
            "result_achieved": bool(score.get("result_achieved", False)),
            "data_quality_conflict": bool(score.get("data_quality_conflict", False)),
            "data_quality_message": score.get("data_quality_message", ""),
            "period_data_quality_issue": bool(period_quality_issue),
            "missing_required_submission": bool(missing_required_submission),
            "management_zero_due_to_missing_data": management_zero_due_to_missing_data,
            "final_missing_result": bool(final_missing_result),
            "attention_signal": bool(period_quality_issue or missing_required_submission or final_missing_result or score.get("data_quality_conflict", False)),
            "assessed": bool(assessed), "included_in_assessment": bool(assessed),
            "coverage_eligible": bool(coverage_eligible), "risk_eligible": bool(risk_eligible),
            "included_in_risk_assessment": bool(risk_eligible),
            "risks_text": clean(record.get("risks")) if record is not None else "",
            "risks": clean(record.get("risks")) if record is not None else "",
            "progress_text": clean(record.get("progress_text")) if record is not None else "",
            # Current approval status is intentionally blank for stale carry.
            "approval_status": exact_record.get("approval_status") if exact_record is not None else "",
            "effective_approval_status": record.get("approval_status") if record is not None else "",
            "request_submitted_at": record.get("submitted_at") if record is not None else None,
            "request_id": record.get("id") if record is not None else None,
            "current_request_id": exact_record.get("id") if exact_record is not None else None,
            "source_request_id": record.get("id") if record is not None else None,
            "source_year": source_year,
            "source_quarter": quarter_to_roman(record.get("quarter")) if record is not None else None,
            "formula_version": DASHBOARD_FORMULA_VERSION,
        })
        rows.append(out)
    return pd.DataFrame(rows)

def _safe_mean(values: pd.Series | Iterable[Any]) -> float | None:
    series = pd.to_numeric(pd.Series(values if isinstance(values, pd.Series) else list(values)), errors="coerce").dropna()
    return None if series.empty else float(series.mean())


def snapshot_execution(snapshot: pd.DataFrame) -> dict[str, Any]:
    if snapshot is None or snapshot.empty:
        return {"execution_by_measures": None, "coverage": None, "assessed_measure_count": 0, "total_measure_count": 0}
    if "monitoring_conducted" in snapshot.columns and not bool(snapshot["monitoring_conducted"].iloc[0]):
        return {"execution_by_measures": None, "coverage": None, "assessed_measure_count": 0, "total_measure_count": int(len(snapshot))}
    assessed = snapshot[snapshot["execution_score"].notna()].copy()
    coverage_pop = snapshot[snapshot.get("coverage_eligible", pd.Series(False, index=snapshot.index)).fillna(False).astype(bool)]
    coverage = None if coverage_pop.empty else float(coverage_pop["submitted"].fillna(False).astype(bool).mean() * 100.0)
    return {"execution_by_measures": _safe_mean(assessed["execution_score"]), "coverage": coverage,
            "assessed_measure_count": int(len(assessed)), "total_measure_count": int(len(snapshot))}


def task_scores(snapshot: pd.DataFrame) -> pd.DataFrame:
    columns = ["task_code", "task_name", "execution", "coverage", "assessed_measure_count", "total_measure_count"]
    if snapshot is None or snapshot.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    for task_code, group in snapshot.groupby("parent_task_code", dropna=False, sort=False):
        task_code = clean(task_code)
        if not task_code:
            continue
        assessed = group[group["execution_score"].notna()]
        coverage_pop = group[group.get("coverage_eligible", pd.Series(False, index=group.index)).fillna(False).astype(bool)]
        rows.append({
            "task_code": task_code,
            "task_name": clean(group["parent_task_name"].iloc[0]) if "parent_task_name" in group else "",
            "execution": _safe_mean(assessed["execution_score"]),
            "coverage": None if coverage_pop.empty else float(coverage_pop["submitted"].fillna(False).astype(bool).mean() * 100.0),
            "assessed_measure_count": int(len(assessed)), "total_measure_count": int(len(group)),
        })
    return pd.DataFrame(rows, columns=columns)


def goal_scores(snapshot: pd.DataFrame, tasks: pd.DataFrame | None = None) -> pd.DataFrame:
    columns = ["goal_code", "goal_name", "by_measures", "by_tasks", "coverage", "assessed_measure_count", "total_measure_count", "task_count"]
    if snapshot is None or snapshot.empty:
        return pd.DataFrame(columns=columns)
    tasks = task_scores(snapshot) if tasks is None else tasks.copy()
    rows = []
    for goal_code, group in snapshot.groupby("parent_goal_code", dropna=False, sort=False):
        goal_code = clean(goal_code)
        if not goal_code:
            continue
        assessed = group[group["execution_score"].notna()]
        coverage_pop = group[group.get("coverage_eligible", pd.Series(False, index=group.index)).fillna(False).astype(bool)]
        task_codes = {clean(v) for v in group["parent_task_code"].tolist() if clean(v)}
        task_group = tasks[tasks["task_code"].map(clean).isin(task_codes)] if not tasks.empty else tasks
        rows.append({
            "goal_code": goal_code,
            "goal_name": clean(group["parent_goal_name"].iloc[0]) if "parent_goal_name" in group else "",
            "by_measures": _safe_mean(assessed["execution_score"]),
            "by_tasks": _safe_mean(task_group["execution"]) if not task_group.empty else None,
            "coverage": None if coverage_pop.empty else float(coverage_pop["submitted"].fillna(False).astype(bool).mean() * 100.0),
            "assessed_measure_count": int(len(assessed)), "total_measure_count": int(len(group)),
            "task_count": int(len(task_group)),
        })
    return pd.DataFrame(rows, columns=columns)


def plan_scores(snapshot: pd.DataFrame) -> dict[str, Any]:
    base = snapshot_execution(snapshot)
    tasks = task_scores(snapshot); goals = goal_scores(snapshot, tasks)
    return {**base, "execution_by_goals": _safe_mean(goals["by_tasks"]) if not goals.empty else None,
            "task_scores": tasks, "goal_scores": goals, "formula_version": DASHBOARD_FORMULA_VERSION}


def hierarchy_for_period(strat_df: pd.DataFrame, requests_df: pd.DataFrame, year: int, quarter: Any, **kwargs: Any) -> dict[str, Any]:
    snapshot = build_quarter_snapshot(strat_df, requests_df, year, quarter, **kwargs)
    return {"snapshot": snapshot, **plan_scores(snapshot)}
