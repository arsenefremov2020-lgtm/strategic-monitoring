from __future__ import annotations

"""Shared numerical preparation for the Analytics surface.

All Analytics-specific numeric facts are prepared here, outside the Streamlit page
and outside the narrative engine. Dashboard and MIO methodology is delegated to
their existing shared modules; this module only adapts those shared outputs and
prepares descriptive analytical tables on the already filtered canonical cohort.
"""

from typing import Any, Callable

import pandas as pd

from core.deputies import DEPUTY_MINISTER_BY_SSP
from core.periods import quarter_to_number
from core.dashboard_breakdowns import (
    build_period_results, aggregate_plan, aggregate_objects, dynamics_frame,
    ssp_summary, deputy_summary, filter_results_by_ssp,
)
from core.dashboard_execution import plan_scores
from core.dashboard_risk import attention_mask, risk_summary


def snapshot_rows_from_period_results(results: dict) -> pd.DataFrame:
    parts = []
    for (year, quarter), result in results.items():
        snap = result.get("snapshot")
        if snap is None or snap.empty:
            continue
        part = snap.copy()
        part["report_year"] = int(year)
        part["report_quarter"] = quarter
        part["report_quarter_num"] = quarter_to_number(quarter)
        part["report_period"] = f"{year} {quarter} квартал"
        part["task_name"] = part.get("parent_task_name", pd.Series("", index=part.index)).astype(str)
        part["ssp_index"] = part.get("main_ssp", "").astype(str)
        part["deputy_minister"] = part.get("deputy_minister_by_ssp", "").astype(str)
        part["numeric_value"] = part.get("actual", "")
        part["has_submission"] = part.get("submitted", False).fillna(False).astype(bool)
        part["is_problem_status"] = attention_mask(part).reindex(part.index, fill_value=False).astype(bool)
        parts.append(part)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def prepare_analysis_context(strat_df: pd.DataFrame, requests_df: pd.DataFrame, years, quarters):
    pairs = [(int(year), quarter) for year in (years or []) for quarter in (quarters or [])]
    results = build_period_results(strat_df, requests_df, pairs)
    return results, snapshot_rows_from_period_results(results)


def prepare_analysis_data(strat_df: pd.DataFrame, requests_df: pd.DataFrame, years, quarters) -> pd.DataFrame:
    return prepare_analysis_context(strat_df, requests_df, years, quarters)[1]


def rebuild_filtered_results(results: dict, row_filter: Callable[[pd.DataFrame], pd.DataFrame]) -> dict:
    output = {}
    for key, item in results.items():
        snap = item.get("snapshot")
        filtered = row_filter(snap.copy()) if snap is not None and not snap.empty else pd.DataFrame()
        scores = plan_scores(filtered)
        output[key] = {**item, "snapshot": filtered, **scores, "risk_summary": risk_summary(filtered)}
    return output


def build_analytics_result_context(results, selected_ssp, selected_deputies, selected_goals, selected_tasks, selected_product_types):
    def row_filter(snap):
        data = snap.copy()
        if selected_goals:
            data = data[data["goal_code"].astype(str).isin(set(map(str, selected_goals)))]
        if selected_tasks:
            data = data[data["task_code"].astype(str).isin(set(map(str, selected_tasks)))]
        if selected_product_types:
            data = data[data["product_type"].astype(str).isin(set(map(str, selected_product_types)))]
        return data

    base_results = rebuild_filtered_results(results, row_filter)
    if selected_deputies:
        wanted_ssp = [str(k) for k, v in DEPUTY_MINISTER_BY_SSP.items() if str(v) in set(map(str, selected_deputies))]
        base_results = filter_results_by_ssp(base_results, wanted_ssp)
    display_results = filter_results_by_ssp(base_results, selected_ssp) if selected_ssp else base_results
    return base_results, display_results


def filter_analysis_period_results(results, selected_ssp, selected_deputies, selected_goals, selected_tasks, selected_product_types):
    return build_analytics_result_context(
        results, selected_ssp, selected_deputies, selected_goals, selected_tasks, selected_product_types
    )[1]


def build_metrics(active: pd.DataFrame) -> dict[str, Any]:
    total = len(active)
    submitted = int(active.get("submitted", pd.Series(False, index=active.index)).fillna(False).astype(bool).sum()) if total else 0
    unique_measures = active["code"].nunique() if total else 0
    goals = active["goal_code"].nunique() if total else 0
    tasks = active["task_code"].nunique() if total else 0
    no_data = int(active.get("missing_required_submission", pd.Series(False, index=active.index)).fillna(False).astype(bool).sum()) if total else 0
    completed = int(active.get("result_achieved", pd.Series(False, index=active.index)).fillna(False).astype(bool).sum()) if total else 0
    problem = int(active.get("is_problem_status", pd.Series(False, index=active.index)).fillna(False).astype(bool).sum()) if total else 0
    return {
        "total_rows": total, "unique_measures": unique_measures, "submitted": submitted,
        "coverage": None, "completion": None,
        "goals": goals, "tasks": tasks, "no_data": no_data, "completed": completed, "problem": problem,
    }


def build_year_over_year_comparison(period_results) -> pd.DataFrame:
    if not period_results:
        return pd.DataFrame()
    by_year = {}
    for year in sorted({key[0] for key in period_results}):
        subset = {key: value for key, value in period_results.items() if key[0] == year}
        plan = aggregate_plan(subset)
        rows = snapshot_rows_from_period_results(subset)
        metrics = build_metrics(rows)
        metrics["completion"] = plan.get("execution_by_measures_average")
        metrics["coverage"] = plan.get("coverage_average")
        by_year[int(year)] = metrics
    years = sorted(by_year)
    if len(years) < 2:
        return pd.DataFrame()
    indicators = [
        ("Унікальні заходи", "unique_measures", "од."), ("Записи захід-період", "total_rows", "од."),
        ("Покриття моніторингом", "coverage", "%"), ("Рівень виконання СП", "completion", "%"),
        ("Без поданих погоджених даних", "no_data", "од."), ("Виконано", "completed", "од."),
        ("Проблемні / ризикові", "problem", "од."),
    ]
    rows = []
    for previous_year, current_year in zip(years[:-1], years[1:]):
        previous, current = by_year[previous_year], by_year[current_year]
        for label, key, unit in indicators:
            prev_value, current_value = previous.get(key), current.get(key)
            change = None if prev_value is None or current_value is None else round(float(current_value) - float(prev_value), 2)
            rows.append({
                "Період порівняння": f"{current_year} до {previous_year}", "Показник": label,
                "Попередній рік": prev_value, "Поточний рік": current_value, "Зміна": change, "Одиниця": unit,
            })
    return pd.DataFrame(rows)


def build_analytics_plan_summary(period_results):
    return aggregate_plan(period_results)


def detail_counts(active: pd.DataFrame, group_cols) -> pd.DataFrame:
    if active.empty:
        return pd.DataFrame()
    rows = []
    for keys, group in active.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        coverage_pop = group[group.get("coverage_eligible", pd.Series(False, index=group.index)).fillna(False).astype(bool)]
        row = dict(zip(group_cols, keys))
        row.update({
            "Заходів_періодів": int(len(group)),
            "Унікальних_заходів": int(group["code"].nunique()),
            "Покриття_eligible": int(len(coverage_pop)),
            "Подано": int(coverage_pop.get("submitted", pd.Series(False, index=coverage_pop.index)).fillna(False).astype(bool).sum()),
            "Без_даних": int(group.get("missing_required_submission", pd.Series(False, index=group.index)).fillna(False).astype(bool).sum()),
            "Проблемних": int(group.get("is_problem_status", pd.Series(False, index=group.index)).fillna(False).astype(bool).sum()),
        })
        rows.append(row)
    return pd.DataFrame(rows)


def object_period_coverage(period_results, object_type: str) -> pd.DataFrame:
    frame_key = "goal_scores" if object_type == "goal" else "task_scores"
    code_col = "goal_code" if object_type == "goal" else "task_code"
    rows = []
    for (year, quarter), result in period_results.items():
        frame = result.get(frame_key)
        if frame is None or frame.empty or "coverage" not in frame.columns:
            continue
        part = frame[[code_col, "coverage"]].copy()
        part["year"] = year
        part["quarter"] = quarter
        rows.append(part)
    if not rows:
        return pd.DataFrame(columns=[code_col, "Покриття_%"])
    data = pd.concat(rows, ignore_index=True)
    data["coverage"] = pd.to_numeric(data["coverage"], errors="coerce")
    return data.groupby(code_col, as_index=False)["coverage"].mean().rename(columns={"coverage": "Покриття_%"})


def build_analytics_goal_summary(period_results, active):
    shared = aggregate_objects(period_results, object_type="goal").rename(columns={
        "goal_name": "strategic_goal", "average_by_tasks": "Виконання", "latest_by_tasks": "Останнє_виконання", "change_by_tasks": "Зміна"
    })
    coverage = object_period_coverage(period_results, "goal")
    counts = detail_counts(active, ["goal_code", "strategic_goal"])
    if shared.empty:
        return shared
    return shared.merge(coverage, on="goal_code", how="left").merge(counts, on=["goal_code", "strategic_goal"], how="left")


def build_analytics_task_summary(period_results, active):
    shared = aggregate_objects(period_results, object_type="task").rename(columns={
        "average_execution": "Виконання", "latest_execution": "Останнє_виконання", "change_execution": "Зміна"
    })
    coverage = object_period_coverage(period_results, "task")
    counts = detail_counts(active, ["goal_code", "task_code", "task_name"])
    if shared.empty:
        return shared
    return shared.merge(coverage, on="task_code", how="left").merge(
        counts.drop(columns=["goal_code"], errors="ignore"), on=["task_code", "task_name"], how="left"
    )


def build_analytics_ssp_summary(period_results, active, base_results=None):
    shared = ssp_summary(period_results, base_results=base_results if base_results is not None else period_results).rename(columns={
        "ssp": "ssp_index", "average": "Виконання", "latest": "Останнє_виконання", "change": "Зміна", "average_coverage": "Покриття_%"
    })
    counts = detail_counts(active, ["ssp_index", "department", "deputy_minister"])
    if shared.empty:
        return shared
    return shared.merge(counts, on="ssp_index", how="left")


def build_analytics_deputy_summary(period_results):
    return deputy_summary(period_results)


def build_analytics_dynamics(period_results) -> pd.DataFrame:
    frame = dynamics_frame(period_results)
    if frame.empty:
        return pd.DataFrame()
    exec_rows = frame[frame["series"] == "Виконання за заходами"].copy()
    cov_rows = frame[frame["series"] == "Покриття"][["year", "quarter", "value"]].rename(columns={"value": "Покриття_%"})
    exec_rows = exec_rows.rename(columns={"year": "report_year", "quarter": "report_quarter", "value": "Виконання"})
    exec_rows["report_quarter_num"] = exec_rows["report_quarter"].map(quarter_to_number)
    exec_rows["Період"] = exec_rows["report_year"].astype(str) + " " + exec_rows["report_quarter"].astype(str)
    return exec_rows.merge(cov_rows, left_on=["report_year", "report_quarter"], right_on=["year", "quarter"], how="left").drop(columns=["year", "quarter"], errors="ignore")


def aggregate_product_progress(period_results, active) -> pd.DataFrame:
    if active.empty:
        return pd.DataFrame()
    rows = []
    for product in sorted(active["product_type"].fillna("").astype(str).unique()):
        subset = rebuild_filtered_results(period_results, lambda snap, p=product: snap[snap["product_type"].fillna("").astype(str).eq(p)].copy())
        plan = aggregate_plan(subset)
        detail = active[active["product_type"].fillna("").astype(str).eq(product)]
        counts = detail_counts(detail, ["product_type"]).iloc[0].to_dict() if not detail.empty else {}
        rows.append({
            "product_type": product or "н/д", "Унікальних_заходів": int(detail["code"].nunique()),
            "Виконання": plan.get("execution_by_measures_average"), "Покриття_%": plan.get("coverage_average"),
            "Проблемних": counts.get("Проблемних", 0), "Без_даних": counts.get("Без_даних", 0),
        })
    return pd.DataFrame(rows).sort_values("Унікальних_заходів", ascending=False)
