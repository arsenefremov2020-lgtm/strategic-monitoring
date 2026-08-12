"""Multi-period and organizational aggregations for Dashboard execution v2."""
from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

from core.dashboard_execution import hierarchy_for_period, plan_scores
from core.dashboard_filters import apply_stable_cohort, expand_ssp_rows, stable_cohort_codes
from core.dashboard_periods import clean, period_number, quarter_to_roman
from core.dashboard_risk import attach_risk, risk_summary


def period_pairs(years: Iterable[Any], quarters: Iterable[Any]) -> list[tuple[int, str]]:
    """Legacy Cartesian compatibility helper. Dashboard UI must pass explicit pairs."""
    pairs = set()
    for year in years or []:
        for quarter in quarters or []:
            try:
                pairs.add((int(float(year)), quarter_to_roman(quarter)))
            except Exception:
                continue
    return sorted(pairs, key=lambda x: period_number(x[0], x[1]))


def _previous_quarter_snapshot(
    strat_df, requests_df, year: int, quarter: str, *, locked_periods=None, cohort_codes=None
):
    qnum = {"I": 1, "II": 2, "III": 3, "IV": 4}[quarter_to_roman(quarter)]
    # V2 trajectory is within-year; Q1 is preliminary and needs no previous fact.
    if qnum <= 1:
        return None
    prev_q = {1: "I", 2: "II", 3: "III", 4: "IV"}[qnum - 1]
    prev = hierarchy_for_period(
        strat_df, requests_df, year, prev_q, locked_periods=locked_periods
    )["snapshot"]
    if cohort_codes is not None:
        prev = apply_stable_cohort(prev, cohort_codes)
    return prev


def build_period_results(
    strat_df: pd.DataFrame,
    requests_df: pd.DataFrame,
    pairs: Iterable[tuple[int, Any]],
    *,
    locked_periods=None,
    stable_statuses: Iterable[Any] | None = None,
    period_sources: dict[tuple[int, str], dict[str, Any]] | None = None,
) -> dict[tuple[int, str], dict[str, Any]]:
    """Build one shared snapshot per selected quarter, then aggregate later.

    ``period_sources`` optionally supplies immutable archive inputs for exact
    periods. Each value may contain ``strat_df``, ``requests_df`` and
    ``locked_periods``. This keeps archive/history on the same v2 formulas
    without making the calculation core depend on archive storage.

    When a status filter is active, its cohort is frozen from the latest
    selected quarter and the *same codes* are used for current, previous,
    average and delta calculations.
    """
    ordered = sorted({(int(y), quarter_to_roman(q)) for y, q in pairs}, key=lambda x: period_number(*x))
    if not ordered:
        return {}
    period_sources = period_sources or {}

    def _source_for(key: tuple[int, str]):
        source = period_sources.get(key) or {}
        return (
            source.get("strat_df", strat_df),
            source.get("requests_df", requests_df),
            source.get("locked_periods", locked_periods),
        )

    def _snapshot_for(key: tuple[int, str]) -> pd.DataFrame:
        src_strat, src_requests, src_locked = _source_for(key)
        return hierarchy_for_period(
            src_strat, src_requests, key[0], key[1], locked_periods=src_locked
        )["snapshot"]

    snapshots: dict[tuple[int, str], pd.DataFrame] = {key: _snapshot_for(key) for key in ordered}

    cohort: set[str] | None = None
    if stable_statuses:
        latest_key = ordered[-1]
        cohort = stable_cohort_codes(snapshots[latest_key], stable_statuses)
        snapshots = {key: apply_stable_cohort(snap, cohort) for key, snap in snapshots.items()}

    results: dict[tuple[int, str], dict[str, Any]] = {}
    for key in ordered:
        snap = snapshots[key]
        qnum = {"I": 1, "II": 2, "III": 3, "IV": 4}[key[1]]
        prev = None
        if qnum > 1:
            prev_key = (key[0], {1: "I", 2: "II", 3: "III", 4: "IV"}[qnum - 1])
            prev = _snapshot_for(prev_key)
            if cohort is not None:
                prev = apply_stable_cohort(prev, cohort)
        snap = attach_risk(snap, prev)
        scores = plan_scores(snap)
        results[key] = {
            "snapshot": snap, **scores, "risk_summary": risk_summary(snap),
            "stable_cohort_codes": set(cohort or []),
        }
    return results


def _valid_metric(results: dict, field: str) -> list[tuple[tuple[int, str], float]]:
    values = []
    for key, result in results.items():
        value = result.get(field)
        if value is not None and not pd.isna(value):
            values.append((key, float(value)))
    return sorted(values, key=lambda item: period_number(*item[0]))


def aggregate_plan(results: dict[tuple[int, str], dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for field in ["execution_by_measures", "execution_by_goals", "coverage"]:
        vals = _valid_metric(results, field)
        output[f"{field}_average"] = sum(v for _, v in vals) / len(vals) if vals else None
        output[f"{field}_latest"] = vals[-1][1] if vals else None
        output[f"{field}_change"] = vals[-1][1] - vals[0][1] if len(vals) >= 2 else None
    latest_key = max(results, key=lambda x: period_number(*x)) if results else None
    output["latest_period"] = latest_key
    if latest_key:
        output["latest_risk_summary"] = results[latest_key].get("risk_summary", {})
    else:
        output["latest_risk_summary"] = {}
    return output


def aggregate_objects(results: dict, *, object_type: str = "goal") -> pd.DataFrame:
    if object_type not in {"goal", "task"}:
        raise ValueError("object_type must be goal or task")
    frames = []
    for (year, quarter), result in results.items():
        frame = result["goal_scores"] if object_type == "goal" else result["task_scores"]
        if frame is None or frame.empty:
            continue
        frame = frame.copy(); frame["year"] = year; frame["quarter"] = quarter
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    data = pd.concat(frames, ignore_index=True)
    code_col = "goal_code" if object_type == "goal" else "task_code"
    name_col = "goal_name" if object_type == "goal" else "task_name"
    metrics = ["by_measures", "by_tasks"] if object_type == "goal" else ["execution"]
    rows = []
    for code, group in data.groupby(code_col, sort=False):
        group = group.copy(); group["_period"] = group.apply(lambda r: period_number(r["year"], r["quarter"]), axis=1)
        group = group.sort_values("_period")
        row = {code_col: code, name_col: clean(group[name_col].iloc[-1])}
        for metric in metrics:
            valid_group = group[pd.to_numeric(group[metric], errors="coerce").notna()].copy()
            valid = pd.to_numeric(valid_group[metric], errors="coerce")
            row[f"average_{metric}"] = float(valid.mean()) if not valid.empty else None
            row[f"latest_{metric}"] = float(valid.iloc[-1]) if not valid.empty else None
            row[f"change_{metric}"] = float(valid.iloc[-1] - valid.iloc[0]) if len(valid) >= 2 else None
        rows.append(row)
    return pd.DataFrame(rows)


def dynamics_frame(results: dict) -> pd.DataFrame:
    rows = []
    for key in sorted(results, key=lambda x: period_number(*x)):
        item = results[key]
        rows.extend([
            {"period": f"{key[1]} кв. {key[0]}", "year": key[0], "quarter": key[1], "series": "Виконання за заходами", "value": item.get("execution_by_measures")},
            {"period": f"{key[1]} кв. {key[0]}", "year": key[0], "quarter": key[1], "series": "Виконання за стратегічними цілями", "value": item.get("execution_by_goals")},
            {"period": f"{key[1]} кв. {key[0]}", "year": key[0], "quarter": key[1], "series": "Покриття", "value": item.get("coverage")},
        ])
    return pd.DataFrame(rows)


def _group_period_metrics(group: pd.DataFrame) -> dict[str, Any]:
    scores = pd.to_numeric(group["execution_score"], errors="coerce").dropna()
    coverage_pop = group[group.get("coverage_eligible", pd.Series(False, index=group.index)).fillna(False).astype(bool)]
    coverage = None if coverage_pop.empty else float(coverage_pop["submitted"].fillna(False).astype(bool).mean() * 100.0)
    rsum = risk_summary(group)
    return {
        "execution": float(scores.mean()) if not scores.empty else None,
        "coverage": coverage,
        "risk_without_substantial": rsum.get("share_without_substantial_risk"),
        "risk_high_critical": rsum.get("share_high_critical_risk"),
    }


def ssp_period_frame(results: dict, selected_ssp: Iterable[Any] | None = None) -> pd.DataFrame:
    rows = []
    for (year, quarter), item in results.items():
        expanded = expand_ssp_rows(item["snapshot"], selected_ssp)
        if expanded.empty:
            continue
        for ssp, group in expanded.groupby("ssp"):
            rows.append({"ssp": ssp, "year": year, "quarter": quarter, **_group_period_metrics(group)})
    return pd.DataFrame(rows)


def _summarize_group_frame(frame: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    base = frame.copy()
    base["_period"] = base.apply(lambda r: period_number(r["year"], r["quarter"]), axis=1)
    latest_selected_period = int(base["_period"].max())
    rows = []
    for value, group in base.groupby(group_col, dropna=False):
        group = group.sort_values("_period").copy()
        exec_valid = group[pd.to_numeric(group["execution"], errors="coerce").notna()].copy()
        cov_valid = group[pd.to_numeric(group["coverage"], errors="coerce").notna()].copy()
        latest_exact = group[group["_period"] == latest_selected_period]
        latest_row = latest_exact.iloc[-1] if not latest_exact.empty else None
        exec_vals = pd.to_numeric(exec_valid["execution"], errors="coerce")
        cov_vals = pd.to_numeric(cov_valid["coverage"], errors="coerce")
        latest_execution = None
        latest_coverage = None
        if latest_row is not None:
            latest_execution = pd.to_numeric(pd.Series([latest_row.get("execution")]), errors="coerce").iloc[0]
            latest_execution = None if pd.isna(latest_execution) else float(latest_execution)
            latest_coverage = pd.to_numeric(pd.Series([latest_row.get("coverage")]), errors="coerce").iloc[0]
            latest_coverage = None if pd.isna(latest_coverage) else float(latest_coverage)
        earliest_comparable = float(exec_vals.iloc[0]) if not exec_vals.empty else None
        rows.append({
            group_col: value,
            "average": float(exec_vals.mean()) if not exec_vals.empty else None,
            "latest": latest_execution,
            "change": (latest_execution - earliest_comparable) if latest_execution is not None and earliest_comparable is not None and len(exec_vals) >= 2 else None,
            "average_coverage": float(cov_vals.mean()) if not cov_vals.empty else None,
            "latest_coverage": latest_coverage,
            # Risk is never averaged and never silently carried from an older quarter.
            "risk_without_substantial_latest": latest_row.get("risk_without_substantial") if latest_row is not None else None,
            "risk_high_critical_latest": latest_row.get("risk_high_critical") if latest_row is not None else None,
            "latest_period": (int(latest_row["year"]), latest_row["quarter"]) if latest_row is not None else None,
        })
    return pd.DataFrame(rows).sort_values("average", ascending=False, na_position="last")


def ssp_summary(results: dict, selected_ssp: Iterable[Any] | None = None) -> pd.DataFrame:
    return _summarize_group_frame(ssp_period_frame(results, selected_ssp), "ssp")


def deputy_period_frame(results: dict) -> pd.DataFrame:
    rows = []
    for (year, quarter), item in results.items():
        snap = item.get("snapshot")
        if snap is None or snap.empty or "deputy_minister_raw" not in snap.columns:
            continue
        for deputy, group in snap.groupby("deputy_minister_raw", dropna=False):
            deputy = clean(deputy)
            if deputy:
                rows.append({"deputy": deputy, "year": year, "quarter": quarter, **_group_period_metrics(group)})
    return pd.DataFrame(rows)


def deputy_summary(results: dict) -> pd.DataFrame:
    return _summarize_group_frame(deputy_period_frame(results), "deputy")


def execution_forecast_matrix(snapshot: pd.DataFrame, *, group_col: str = "department") -> pd.DataFrame:
    """Group data for the Execution × Forecast matrix.

    Only measures with a valid numeric forecast contribute to a matrix point.
    Q4 returns an empty frame because forecast is no longer applicable.
    """
    if snapshot is None or snapshot.empty or quarter_to_roman(snapshot["quarter"].iloc[0]) == "IV":
        return pd.DataFrame()
    if group_col not in snapshot.columns:
        return pd.DataFrame()
    rows = []
    for group_name, group in snapshot.groupby(group_col, dropna=False):
        eligible = group.copy()
        eligible["_execution_num"] = pd.to_numeric(eligible.get("execution_score"), errors="coerce")
        eligible["_forecast_num"] = pd.to_numeric(eligible.get("forecast_attainment_pct"), errors="coerce")
        eligible = eligible[eligible["_execution_num"].notna() & eligible["_forecast_num"].notna()].copy()
        if eligible.empty:
            continue
        preliminary = quarter_to_roman(eligible["quarter"].iloc[0]) == "I"
        levels = eligible.get("risk_level", pd.Series(index=eligible.index, dtype=object)).dropna()
        risk = None
        if not preliminary:
            for candidate in ["Критичний ризик", "Високий ризик", "Середній ризик", "Низький ризик"]:
                if candidate in set(levels):
                    risk = candidate
                    break
        rows.append({
            "group": clean(group_name),
            "execution": float(eligible["_execution_num"].mean()),
            "forecast_attainment": float(eligible["_forecast_num"].mean()),
            "risk_level": "Попередній прогноз" if preliminary else (risk or "Не оцінюється"),
            "group_size": int(eligible["code"].nunique()),
            "preliminary": preliminary,
        })
    return pd.DataFrame(rows)


def execution_forecast_diagnostics(snapshot: pd.DataFrame, *, group_col: str = "department") -> dict[str, int]:
    """Explain how many measures can actually enter the forecast matrix.

    Submission coverage and matrix eligibility are deliberately separated: a
    measure needs a numeric current fact/annual target and, in Q2-Q3, a valid
    previous-quarter fact before a forecast exists.
    """
    empty = {
        "total_assessed": 0,
        "numeric_current_count": 0,
        "numeric_with_previous_fact_count": 0,
        "numeric_forecast_count": 0,
        "groups_in_matrix": 0,
    }
    if snapshot is None or snapshot.empty:
        return empty

    data = snapshot.copy()
    code = data.get("code", pd.Series(data.index.astype(str), index=data.index)).astype(str)
    assessed_mask = pd.to_numeric(data.get("execution_score"), errors="coerce").notna()
    numeric_mask = data.get("numeric", pd.Series(False, index=data.index)).fillna(False).astype(bool)
    numeric_current_mask = numeric_mask & assessed_mask
    forecast_mask = numeric_current_mask & pd.to_numeric(
        data.get("forecast_attainment_pct"), errors="coerce"
    ).notna()

    quarter = quarter_to_roman(data.get("quarter", pd.Series([""])).iloc[0])
    if quarter in {"II", "III"}:
        previous_mask = numeric_current_mask & pd.to_numeric(
            data.get("current_increment"), errors="coerce"
        ).notna()
    elif quarter == "I":
        previous_mask = pd.Series(False, index=data.index)
    else:
        previous_mask = pd.Series(False, index=data.index)

    matrix = execution_forecast_matrix(data, group_col=group_col)
    return {
        "total_assessed": int(code[assessed_mask].nunique()),
        "numeric_current_count": int(code[numeric_current_mask].nunique()),
        "numeric_with_previous_fact_count": int(code[previous_mask].nunique()),
        "numeric_forecast_count": int(code[forecast_mask].nunique()),
        "groups_in_matrix": int(len(matrix)),
    }
