from __future__ import annotations

"""Analytics-specific preparation over canonical Dashboard v3 outputs.

The Dashboard calculation/risk methodology remains the source of truth.  This
module only adapts those prepared period snapshots to Analytics semantics:

* execution is the exact latest selected period (never a temporal average and
  never the last non-null value from an older period);
* coverage keeps both the mean of evaluable selected periods and the exact
  latest selected period;
* management attention is quarter-aware and is calculated only on the exact
  latest snapshot;
* the historical measure × period dataset is retained for dynamics/status/data
  completeness analysis, without exposing the retired accumulated attention metric.
"""

from typing import Any, Callable, Iterable

import pandas as pd

from core.deputies import DEPUTY_MINISTER_BY_SSP
from core.periods import quarter_to_number
from core.dashboard_breakdowns import (
    build_period_results,
    dynamics_frame,
    ssp_summary,
    ssp_period_frame,
    deputy_summary as _dashboard_deputy_summary,
    deputy_period_frame,
    filter_results_by_ssp,
)
from core.dashboard_execution import plan_scores
from core.dashboard_risk import RISKY_LEVELS, risk_summary


_QUARTERS = {"I": 1, "II": 2, "III": 3, "IV": 4, "1": 1, "2": 2, "3": 3, "4": 4}
_ATTENTION_LABELS = {
    "preliminary_attention": "Попередні сигнали управлінської уваги",
    "forecast_risk": "Високий або критичний ризик",
    "final_nonachievement": "Фінальний результат не досягнуто",
    "unavailable": "Не оцінюється",
}


def _period_sort_key(key: tuple[int, Any]) -> tuple[int, int]:
    year, quarter = key
    q = _QUARTERS.get(str(quarter).strip(), 0)
    return int(year), q


def latest_period_key(results: dict) -> tuple[int, str] | None:
    """Return the exact latest selected period, regardless of metric availability."""
    return max(results, key=_period_sort_key) if results else None


def first_period_key(results: dict) -> tuple[int, str] | None:
    return min(results, key=_period_sort_key) if results else None


def _number(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _exact_metric(results: dict, field: str, key: tuple[int, str] | None = None) -> float | None:
    """Metric in the requested/exact selected period; never carry from an older one."""
    key = key or latest_period_key(results)
    if key is None:
        return None
    return _number((results.get(key) or {}).get(field))


def _selection_change(results: dict, field: str) -> float | None:
    """Exact latest minus exact first selected period when both are evaluable."""
    first = first_period_key(results)
    latest = latest_period_key(results)
    if first is None or latest is None or first == latest:
        return None
    left = _exact_metric(results, field, first)
    right = _exact_metric(results, field, latest)
    return None if left is None or right is None else right - left


def _selection_average(results: dict, field: str) -> float | None:
    """Mean of evaluable values for one explicitly allowed Analytics field.

    Analytics uses this helper only for coverage. It intentionally does not call
    Dashboard ``aggregate_plan()``, so temporal execution averages are never
    calculated as a side effect of preparing the Analytics contract.
    """
    values: list[float] = []
    for key in sorted(results, key=_period_sort_key):
        value = _exact_metric(results, field, key)
        if value is not None:
            values.append(value)
    return (sum(values) / len(values)) if values else None


def _safe_bool(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=bool)
    if column not in frame.columns:
        return pd.Series(False, index=frame.index, dtype=bool)
    return frame[column].fillna(False).astype(bool)


def snapshot_rows_from_period_results(results: dict) -> pd.DataFrame:
    """Historical Analytics rows used for dynamics/status/completeness only.

    Deliberately does not attach Dashboard ``attention_mask`` or an accumulated
    retired multi-period flag. Current management attention is prepared separately from the
    exact latest snapshot so it cannot be summed across quarters accidentally.
    """
    parts: list[pd.DataFrame] = []
    for (year, quarter), result in sorted(results.items(), key=lambda item: _period_sort_key(item[0])):
        snap = result.get("snapshot")
        if snap is None or snap.empty:
            continue
        part = snap.copy()
        part["report_year"] = int(year)
        part["report_quarter"] = quarter
        part["report_quarter_num"] = quarter_to_number(quarter)
        part["report_period"] = f"{year} {quarter} квартал"
        if "goal_code" not in part.columns:
            part["goal_code"] = part.get("parent_goal_code", pd.Series("", index=part.index)).astype(str)
        if "task_code" not in part.columns:
            part["task_code"] = part.get("parent_task_code", pd.Series("", index=part.index)).astype(str)
        part["task_name"] = part.get("parent_task_name", pd.Series("", index=part.index)).astype(str)
        if "strategic_goal" not in part.columns:
            part["strategic_goal"] = part.get("parent_goal_name", pd.Series("", index=part.index)).astype(str)
        part["ssp_index"] = part.get("main_ssp", pd.Series("", index=part.index)).astype(str)
        part["deputy_minister"] = part.get("deputy_minister_by_ssp", pd.Series("", index=part.index)).astype(str)
        part["numeric_value"] = part.get("actual", "")
        part["has_submission"] = _safe_bool(part, "submitted")
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
        if filtered.empty or item.get("execution_by_measures") is None:
            # Analytics exact-latest semantics: an entity absent from an evaluated
            # latest cohort is unassessed, not zero and not a value reconstructed
            # from stale/object-level rows. Keep the shared Dashboard scorer
            # unchanged and neutralise only this Analytics filtering adapter.
            scores = {**scores, "execution_by_measures": None}
            if filtered.empty:
                scores = {**scores, "execution_by_goals": None, "coverage": None}
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


def _latest_snapshot(results: dict) -> tuple[tuple[int, str] | None, pd.DataFrame]:
    key = latest_period_key(results)
    if key is None:
        return None, pd.DataFrame()
    snap = (results.get(key) or {}).get("snapshot")
    return key, snap.copy() if isinstance(snap, pd.DataFrame) else pd.DataFrame()


def attention_semantics(quarter: Any) -> dict[str, str]:
    """Public label/type helper for the quarter-aware Analytics attention metric."""
    q = str(quarter).strip().upper()
    if q == "I":
        kind = "preliminary_attention"
    elif q in {"II", "III"}:
        kind = "forecast_risk"
    elif q == "IV":
        kind = "final_nonachievement"
    else:
        kind = "unavailable"
    return {"type": kind, "label": _ATTENTION_LABELS[kind]}


def management_attention_mask(snapshot: pd.DataFrame, quarter: Any) -> pd.Series:
    """Canonical quarter-aware Analytics headline cohort on one snapshot only."""
    if snapshot is None or snapshot.empty:
        return pd.Series(False, index=getattr(snapshot, "index", None), dtype=bool)
    q = str(quarter).strip().upper()
    if q == "I":
        return _safe_bool(snapshot, "preliminary_attention")
    if q in {"II", "III"}:
        risk_level = snapshot.get("risk_level", pd.Series("", index=snapshot.index)).fillna("").astype(str)
        return _safe_bool(snapshot, "included_in_risk_assessment") & risk_level.isin(RISKY_LEVELS)
    if q == "IV":
        # Final assessment cohort: final rows with a canonical execution_score.
        # Missing/unassessed rows are not silently converted into non-achievement.
        forecast_kind = snapshot.get("forecast_kind", pd.Series("", index=snapshot.index)).fillna("").astype(str)
        assessed = forecast_kind.eq("final") & pd.to_numeric(
            snapshot.get("execution_score", pd.Series(index=snapshot.index, dtype=float)), errors="coerce"
        ).notna()
        return assessed & ~_safe_bool(snapshot, "result_achieved")
    return pd.Series(False, index=snapshot.index, dtype=bool)


def management_attention_info(results: dict) -> dict[str, Any]:
    key, snapshot = _latest_snapshot(results)
    if key is None:
        return {
            "period": None, "quarter": None, "count": 0, "type": "unavailable",
            "label": _ATTENTION_LABELS["unavailable"], "assessed_count": 0,
        }
    _, quarter = key
    q = str(quarter).strip().upper()
    if q == "I":
        kind = "preliminary_attention"
    elif q in {"II", "III"}:
        kind = "forecast_risk"
    elif q == "IV":
        kind = "final_nonachievement"
    else:
        kind = "unavailable"
    mask = management_attention_mask(snapshot, quarter)
    count = int(snapshot.loc[mask, "code"].nunique()) if "code" in snapshot.columns else int(mask.sum())
    assessed_count = 0
    if q == "IV" and not snapshot.empty:
        forecast_kind = snapshot.get("forecast_kind", pd.Series("", index=snapshot.index)).fillna("").astype(str)
        assessed = forecast_kind.eq("final") & pd.to_numeric(
            snapshot.get("execution_score", pd.Series(index=snapshot.index, dtype=float)), errors="coerce"
        ).notna()
        assessed_count = int(snapshot.loc[assessed, "code"].nunique()) if "code" in snapshot.columns else int(assessed.sum())
    elif q in {"II", "III"}:
        included = _safe_bool(snapshot, "included_in_risk_assessment")
        assessed_count = int(snapshot.loc[included, "code"].nunique()) if "code" in snapshot.columns else int(included.sum())
    return {
        "period": key, "quarter": q, "count": count, "type": kind,
        "label": _ATTENTION_LABELS[kind], "assessed_count": assessed_count,
    }


def latest_attention_snapshot(results: dict) -> pd.DataFrame:
    key, snapshot = _latest_snapshot(results)
    if key is None or snapshot.empty:
        return pd.DataFrame()
    info = management_attention_info(results)
    snapshot = snapshot.copy()
    # Normalise the latest Dashboard snapshot to the same naming contract used by
    # the historical Analytics frame. This keeps current-period breakdowns mergeable
    # without changing the shared Dashboard snapshot itself.
    if "goal_code" not in snapshot.columns:
        snapshot["goal_code"] = snapshot.get("parent_goal_code", pd.Series("", index=snapshot.index)).astype(str)
    if "task_code" not in snapshot.columns:
        snapshot["task_code"] = snapshot.get("parent_task_code", pd.Series("", index=snapshot.index)).astype(str)
    if "strategic_goal" not in snapshot.columns:
        snapshot["strategic_goal"] = snapshot.get("parent_goal_name", pd.Series("", index=snapshot.index)).astype(str)
    if "task_name" not in snapshot.columns:
        snapshot["task_name"] = snapshot.get("parent_task_name", pd.Series("", index=snapshot.index)).astype(str)
    if "ssp_index" not in snapshot.columns:
        snapshot["ssp_index"] = snapshot.get("main_ssp", pd.Series("", index=snapshot.index)).astype(str)
    if "deputy_minister" not in snapshot.columns:
        snapshot["deputy_minister"] = snapshot.get("deputy_minister_by_ssp", pd.Series("", index=snapshot.index)).astype(str)
    snapshot["analytics_attention"] = management_attention_mask(snapshot, key[1]).astype(bool)
    snapshot["analytics_attention_type"] = info["type"]
    snapshot["analytics_attention_label"] = info["label"]
    return snapshot


def build_metrics(active: pd.DataFrame, period_results: dict | None = None) -> dict[str, Any]:
    """Prepare page counters without exposing the retired accumulated attention metric."""
    total = len(active)
    unique_measures = active["code"].nunique() if total and "code" in active.columns else 0
    goals = active["goal_code"].nunique() if total and "goal_code" in active.columns else 0
    tasks = active["task_code"].nunique() if total and "task_code" in active.columns else 0
    result: dict[str, Any] = {
        "total_rows": total,
        "unique_measures": int(unique_measures),
        "coverage": None,
        "coverage_latest": None,
        "completion": None,
        "goal_completion": None,
        "goals": int(goals),
        "tasks": int(tasks),
        "no_data": 0,
        "completed": 0,
        "submitted": 0,
        "latest_measure_count": 0,
        "attention_count": 0,
        "attention_type": "unavailable",
        "attention_label": _ATTENTION_LABELS["unavailable"],
    }
    if not period_results:
        return result

    key, latest = _latest_snapshot(period_results)
    if key is None or latest.empty:
        return result
    code_col = latest.get("code", pd.Series(index=latest.index, dtype=object))
    result["latest_measure_count"] = int(code_col.nunique())
    missing = _safe_bool(latest, "missing_required_submission")
    submitted = _safe_bool(latest, "submitted")
    achieved = _safe_bool(latest, "result_achieved") & pd.to_numeric(
        latest.get("execution_score", pd.Series(index=latest.index, dtype=float)), errors="coerce"
    ).notna()
    result["no_data"] = int(latest.loc[missing, "code"].nunique()) if "code" in latest.columns else int(missing.sum())
    result["submitted"] = int(latest.loc[submitted, "code"].nunique()) if "code" in latest.columns else int(submitted.sum())
    result["completed"] = int(latest.loc[achieved, "code"].nunique()) if "code" in latest.columns else int(achieved.sum())
    result.update({
        "attention_count": management_attention_info(period_results)["count"],
        "attention_type": management_attention_info(period_results)["type"],
        "attention_label": management_attention_info(period_results)["label"],
        "attention_assessed_count": management_attention_info(period_results)["assessed_count"],
    })
    return result


def build_analytics_plan_summary(period_results):
    """Analytics plan contract with exact-latest execution and dual coverage.

    Coverage average is prepared directly from the selected-period coverage
    series. No shared temporal execution aggregate is invoked in Analytics.
    """
    latest = latest_period_key(period_results)
    return {
        "execution_by_measures": _exact_metric(period_results, "execution_by_measures", latest),
        "execution_by_goals": _exact_metric(period_results, "execution_by_goals", latest),
        "execution_by_measures_change": _selection_change(period_results, "execution_by_measures"),
        "execution_by_goals_change": _selection_change(period_results, "execution_by_goals"),
        "coverage_average": _selection_average(period_results, "coverage"),
        "coverage_latest": _exact_metric(period_results, "coverage", latest),
        "coverage_change": _selection_change(period_results, "coverage"),
        "latest_period": latest,
        "latest_risk_summary": (period_results.get(latest) or {}).get("risk_summary", {}) if latest else {},
        "management_attention": management_attention_info(period_results),
    }


def _historical_detail_counts(active: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if active is None or active.empty:
        return pd.DataFrame()
    rows = []
    for keys, group in active.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        missing = _safe_bool(group, "missing_required_submission")
        row.update({
            "Заходів_періодів": int(len(group)),
            "Унікальних_заходів": int(group["code"].nunique()) if "code" in group.columns else int(len(group)),
            "Без_даних_періодів": int(missing.sum()),
        })
        rows.append(row)
    return pd.DataFrame(rows)


def _latest_detail_counts(period_results: dict, group_cols: list[str]) -> pd.DataFrame:
    latest = latest_attention_snapshot(period_results)
    if latest.empty:
        return pd.DataFrame()
    usable = [c for c in group_cols if c in latest.columns]
    if not usable:
        return pd.DataFrame()
    rows = []
    for keys, group in latest.groupby(usable, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(usable, keys))
        attention = _safe_bool(group, "analytics_attention")
        missing = _safe_bool(group, "missing_required_submission")
        row.update({
            "Актуальна_увага": int(group.loc[attention, "code"].nunique()) if "code" in group.columns else int(attention.sum()),
            "Без_даних": int(group.loc[missing, "code"].nunique()) if "code" in group.columns else int(missing.sum()),
            "Тип_уваги": str(group["analytics_attention_label"].iloc[0]) if "analytics_attention_label" in group.columns else "",
        })
        rows.append(row)
    return pd.DataFrame(rows)


def detail_counts(active: pd.DataFrame, group_cols, period_results: dict | None = None) -> pd.DataFrame:
    """Descriptive counts with explicit historical vs exact-latest semantics."""
    group_cols = list(group_cols)
    historical = _historical_detail_counts(active, group_cols)
    if not period_results:
        return historical
    current = _latest_detail_counts(period_results, group_cols)
    if historical.empty:
        return current
    if current.empty:
        historical["Актуальна_увага"] = 0
        historical["Без_даних"] = 0
        historical["Тип_уваги"] = ""
        return historical
    keys = [c for c in group_cols if c in historical.columns and c in current.columns]
    if not keys:
        return historical
    out = historical.merge(current, on=keys, how="left")
    out["Актуальна_увага"] = pd.to_numeric(out.get("Актуальна_увага"), errors="coerce").fillna(0).astype(int)
    out["Без_даних"] = pd.to_numeric(out.get("Без_даних"), errors="coerce").fillna(0).astype(int)
    out["Тип_уваги"] = out.get("Тип_уваги", pd.Series("", index=out.index)).fillna("")
    return out


def object_period_coverage(period_results, object_type: str) -> pd.DataFrame:
    frame_key = "goal_scores" if object_type == "goal" else "task_scores"
    code_col = "goal_code" if object_type == "goal" else "task_code"
    latest = latest_period_key(period_results)
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
        return pd.DataFrame(columns=[code_col, "Покриття_середнє_%", "Покриття_останній_%"])
    data = pd.concat(rows, ignore_index=True)
    data["coverage"] = pd.to_numeric(data["coverage"], errors="coerce")
    mean = data.groupby(code_col, as_index=False)["coverage"].mean().rename(columns={"coverage": "Покриття_середнє_%"})
    if latest is None:
        mean["Покриття_останній_%"] = pd.NA
        return mean
    exact = data[(data["year"].astype(int) == int(latest[0])) & (data["quarter"].astype(str) == str(latest[1]))][[code_col, "coverage"]]
    exact = exact.rename(columns={"coverage": "Покриття_останній_%"})
    return mean.merge(exact, on=code_col, how="left")


def _exact_object_summary(period_results: dict, object_type: str) -> pd.DataFrame:
    if object_type not in {"goal", "task"}:
        raise ValueError("object_type must be goal or task")
    frame_key = "goal_scores" if object_type == "goal" else "task_scores"
    code_col = "goal_code" if object_type == "goal" else "task_code"
    name_col = "goal_name" if object_type == "goal" else "task_name"
    metric = "by_tasks" if object_type == "goal" else "execution"
    frames = []
    for (year, quarter), result in sorted(period_results.items(), key=lambda item: _period_sort_key(item[0])):
        frame = result.get(frame_key)
        if frame is None or frame.empty or code_col not in frame.columns:
            continue
        part = frame.copy()
        part["_year"] = int(year)
        part["_quarter"] = quarter
        part["_period"] = int(year) * 10 + _QUARTERS.get(str(quarter), 0)
        frames.append(part)
    if not frames:
        return pd.DataFrame()
    data = pd.concat(frames, ignore_index=True)
    latest = latest_period_key(period_results)
    latest_num = int(latest[0]) * 10 + _QUARTERS.get(str(latest[1]), 0) if latest else None
    rows = []
    for code, group in data.groupby(code_col, sort=False, dropna=False):
        group = group.sort_values("_period")
        metadata = group.iloc[-1]
        exact_rows = group[group["_period"] == latest_num] if latest_num is not None else pd.DataFrame()
        exact_value = None
        if not exact_rows.empty:
            exact_value = _number(exact_rows.iloc[-1].get(metric))
        valid = group[pd.to_numeric(group.get(metric), errors="coerce").notna()].copy()
        first_valid = _number(valid.iloc[0].get(metric)) if not valid.empty else None
        change = None
        if exact_value is not None and first_valid is not None and len(valid) >= 2:
            change = exact_value - first_valid
        rows.append({
            code_col: code,
            name_col: str(metadata.get(name_col) or "").strip(),
            "Виконання": exact_value,
            "Зміна": change,
        })
    return pd.DataFrame(rows)


def build_analytics_goal_summary(period_results, active):
    shared = _exact_object_summary(period_results, "goal").rename(columns={"goal_name": "strategic_goal"})
    if shared.empty:
        return shared
    coverage = object_period_coverage(period_results, "goal")
    counts = detail_counts(active, ["goal_code", "strategic_goal"], period_results)
    out = shared.merge(coverage, on="goal_code", how="left")
    if not counts.empty:
        merge_keys = [c for c in ["goal_code", "strategic_goal"] if c in out.columns and c in counts.columns]
        out = out.merge(counts, on=merge_keys, how="left")
    return out.sort_values("Виконання", ascending=False, na_position="last")


def build_analytics_task_summary(period_results, active):
    shared = _exact_object_summary(period_results, "task")
    if shared.empty:
        return shared
    coverage = object_period_coverage(period_results, "task")
    counts = detail_counts(active, ["goal_code", "task_code", "task_name"], period_results)
    out = shared.merge(coverage, on="task_code", how="left")
    if not counts.empty:
        merge_keys = [c for c in ["task_code", "task_name"] if c in out.columns and c in counts.columns]
        out = out.merge(counts.drop(columns=["goal_code"], errors="ignore"), on=merge_keys, how="left")
    return out.sort_values("Виконання", ascending=False, na_position="last")


def _override_group_summary_exact_latest(
    shared: pd.DataFrame,
    period_frame: pd.DataFrame,
    period_results: dict,
    *,
    group_col: str,
) -> pd.DataFrame:
    """Keep shared portfolio context but force Analytics latest/change to the exact selected period.

    Shared Dashboard summaries intentionally infer their latest period from rows
    present in the group frame.  Analytics has a stricter contract: the latest
    period is the latest *selected* key even when that snapshot/group has no row.
    This adapter therefore never carries a prior SSP/deputy value forward.
    """
    if shared is None or shared.empty:
        return pd.DataFrame() if shared is None else shared.copy()
    out = shared.copy()
    latest = latest_period_key(period_results)
    out["latest"] = pd.NA
    out["latest_coverage"] = pd.NA
    out["change"] = pd.NA
    out["latest_period"] = [latest] * len(out)
    if latest is None or period_frame is None or period_frame.empty:
        return out

    data = period_frame.copy()
    data["_period"] = data.apply(
        lambda row: int(row.get("year")) * 10 + _QUARTERS.get(str(row.get("quarter")).strip(), 0),
        axis=1,
    )
    latest_num = int(latest[0]) * 10 + _QUARTERS.get(str(latest[1]).strip(), 0)
    exact = data[data["_period"] == latest_num].copy()
    exact_by_group = {str(row.get(group_col)): row for _, row in exact.iterrows()}

    latest_values = []
    latest_coverage = []
    changes = []
    for _, summary_row in out.iterrows():
        key = str(summary_row.get(group_col))
        exact_row = exact_by_group.get(key)
        latest_execution = _number(exact_row.get("execution")) if exact_row is not None else None
        latest_cov = _number(exact_row.get("coverage")) if exact_row is not None else None
        group = data[data[group_col].astype(str).eq(key)].sort_values("_period")
        valid = group[pd.to_numeric(group.get("execution"), errors="coerce").notna()].copy()
        first_value = _number(valid.iloc[0].get("execution")) if not valid.empty else None
        change = None
        if latest_execution is not None and first_value is not None and len(valid) >= 2:
            change = latest_execution - first_value
        latest_values.append(latest_execution)
        latest_coverage.append(latest_cov)
        changes.append(change)

    out["latest"] = latest_values
    out["latest_coverage"] = latest_coverage
    out["change"] = changes
    return out


def _recalculate_underperformance_contribution_exact_latest(frame: pd.DataFrame) -> pd.DataFrame:
    """Analytics-only SSP underperformance contribution from exact-latest execution.

    The shared Dashboard SSP summary intentionally keeps its own temporal-average
    contribution methodology. Analytics must not inherit that value after
    replacing ``latest`` execution with exact-latest semantics, otherwise a
    historically weak SSP can still appear to contribute to current
    underperformance even when its exact-latest execution is 100%.
    """
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame.copy()
    out = frame.copy()
    if "portfolio_weight_pct" not in out.columns or "latest" not in out.columns:
        out["underperformance_contribution_pct"] = None
        return out

    weight = pd.to_numeric(out["portfolio_weight_pct"], errors="coerce")
    execution = pd.to_numeric(out["latest"], errors="coerce")
    valid = weight.notna() & execution.notna()
    deficit_mass = (weight * (100.0 - execution).clip(lower=0.0)).where(valid)
    total_deficit = deficit_mass.sum(min_count=1)
    if pd.notna(total_deficit) and float(total_deficit) > 0:
        out["underperformance_contribution_pct"] = deficit_mass / float(total_deficit) * 100.0
    else:
        out["underperformance_contribution_pct"] = None
    return out


def build_analytics_ssp_summary(period_results, active, base_results=None):
    shared_raw = ssp_summary(
        period_results,
        base_results=base_results if base_results is not None else period_results,
    )
    shared_raw = _override_group_summary_exact_latest(
        shared_raw, ssp_period_frame(period_results), period_results, group_col="ssp"
    )
    shared_raw = _recalculate_underperformance_contribution_exact_latest(shared_raw)
    shared = shared_raw.rename(columns={
        "ssp": "ssp_index",
        "latest": "Виконання",
        "change": "Зміна",
        "average_coverage": "Покриття_середнє_%",
        "latest_coverage": "Покриття_останній_%",
    })
    shared = shared.drop(columns=["average"], errors="ignore")
    counts = detail_counts(active, ["ssp_index", "department", "deputy_minister"], period_results)
    if shared.empty:
        return shared
    out = shared.merge(counts, on="ssp_index", how="left") if not counts.empty else shared
    return out.sort_values("Виконання", ascending=False, na_position="last")


def build_analytics_deputy_summary(period_results):
    """Deputy summary with the same exact-latest Analytics contract; no temporal average API."""
    shared = _override_group_summary_exact_latest(
        # Build the shared frame only to preserve its naming/metadata shape.
        # The exposed Analytics contract below intentionally drops ``average``.
        _dashboard_deputy_summary(period_results),
        deputy_period_frame(period_results),
        period_results,
        group_col="deputy",
    )
    return shared.rename(columns={
        "latest": "Виконання",
        "change": "Зміна",
        "average_coverage": "Покриття_середнє_%",
        "latest_coverage": "Покриття_останній_%",
    }).drop(columns=["average"], errors="ignore")


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
    if active is None or active.empty or "product_type" not in active.columns:
        return pd.DataFrame()
    rows = []
    for product in sorted(active["product_type"].fillna("").astype(str).unique()):
        subset = rebuild_filtered_results(
            period_results,
            lambda snap, p=product: snap[snap["product_type"].fillna("").astype(str).eq(p)].copy(),
        )
        plan = build_analytics_plan_summary(subset)
        detail = active[active["product_type"].fillna("").astype(str).eq(product)]
        counts = detail_counts(detail, ["product_type"], subset)
        count_row = counts.iloc[0].to_dict() if not counts.empty else {}
        rows.append({
            "product_type": product or "н/д",
            "Унікальних_заходів": int(detail["code"].nunique()) if "code" in detail.columns else int(len(detail)),
            "Виконання": plan.get("execution_by_measures"),
            "Зміна": plan.get("execution_by_measures_change"),
            "Покриття_середнє_%": plan.get("coverage_average"),
            "Покриття_останній_%": plan.get("coverage_latest"),
            "Актуальна_увага": int(count_row.get("Актуальна_увага", 0) or 0),
            "Без_даних": int(count_row.get("Без_даних", 0) or 0),
            "Тип_уваги": count_row.get("Тип_уваги", ""),
        })
    return pd.DataFrame(rows).sort_values("Унікальних_заходів", ascending=False)
