"""Pure data adapters for the two Dashboard goal-achievement matrix views.

The input is an already-built canonical Dashboard snapshot. No status, risk or
execution methodology is reimplemented here.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from core import dashboard_execution, dashboard_filters
from core.dashboard_periods import clean

GROUP_DEPUTY = "Заступники Міністра"
GROUP_SSP = "ССП"

# Exact execution-status palette used by the production Dashboard status chart.
# This is presentation metadata only; canonical status values still come from the snapshot.
_DASHBOARD_STATUS_COLORS = {
    "Виконано": "#118847",
    "Частково виконано": "#F4B400",
    "Не виконано": "#DC4A4A",
    "Не подано": "#B42318",
    "Не настав час": "#8A96A8",
    "Втратило актуальність": "#5B21B6",
    "Не визначено": "#61708A",
}


def status_color(status: Any) -> str:
    return _DASHBOARD_STATUS_COLORS.get(clean(status), "#8A96A8")


def group_value(row: pd.Series | dict[str, Any], grouping: str) -> str:
    if grouping == GROUP_SSP:
        index = dashboard_filters.main_ssp_index(row)
        return f"ССП {index}" if index else "ССП не визначено"
    return dashboard_filters.main_ssp_deputy(row)


def matrix_dataset(snapshot: pd.DataFrame, grouping: str) -> pd.DataFrame:
    """One row per measure, assigned only to its canonical main SSP/deputy."""
    columns = [
        "code", "goal_code", "goal_name", "task_code", "task_name", "group",
        "status_display", "execution_score", "monitoring_conducted",
        "coverage_eligible", "submitted",
    ]
    if snapshot is None or snapshot.empty:
        return pd.DataFrame(columns=columns)
    data = snapshot.drop_duplicates(subset=["code"], keep="first").copy()
    out = pd.DataFrame(index=data.index)
    out["code"] = data["code"].map(clean)
    out["goal_code"] = data.get("parent_goal_code", data.get("goal_code", "")).map(clean)
    out["goal_name"] = data.get("parent_goal_name", data.get("strategic_goal", "")).map(clean)
    out["task_code"] = data.get("parent_task_code", data.get("task_code", "")).map(clean)
    out["task_name"] = data.get("parent_task_name", pd.Series("", index=data.index)).map(clean)
    out["group"] = data.apply(lambda row: group_value(row, grouping), axis=1)
    out["status_display"] = data.get("status_display", data.get("status", "")).map(clean)
    out["execution_score"] = pd.to_numeric(data.get("execution_score"), errors="coerce")
    out["monitoring_conducted"] = data.get("monitoring_conducted", pd.Series(True, index=data.index))
    out["coverage_eligible"] = data.get("coverage_eligible", pd.Series(False, index=data.index))
    out["submitted"] = data.get("submitted", pd.Series(False, index=data.index))
    return out.reset_index(drop=True)


def all_groups(portfolio: pd.DataFrame, grouping: str) -> list[str]:
    if portfolio is None or portfolio.empty:
        return []
    values = {group_value(row, grouping) for _, row in portfolio.iterrows()}
    if grouping == GROUP_SSP:
        def key(value: str):
            import re
            match = re.search(r"\d+", value)
            return int(match.group()) if match else 9999
        return sorted(values, key=key)
    return sorted(values, key=lambda value: value.casefold())


def mosaic_frame(dataset: pd.DataFrame, goal_code: str) -> pd.DataFrame:
    """Area weights: unique measures per task -> group -> canonical status."""
    if dataset is None or dataset.empty:
        return pd.DataFrame(columns=["task", "group", "status", "measure_count"])
    data = dataset[dataset["goal_code"].map(clean).eq(clean(goal_code))].copy()
    if data.empty:
        return pd.DataFrame(columns=["task", "group", "status", "measure_count"])
    data["task"] = data.apply(
        lambda row: f"{clean(row['task_code'])} — {clean(row['task_name'])}".strip(" —"), axis=1
    )
    data["status"] = data["status_display"].where(data["status_display"].ne(""), "Не визначено")
    result = (
        data.groupby(["task", "group", "status"], dropna=False)["code"]
        .nunique().reset_index(name="measure_count")
    )
    return result[result["measure_count"] > 0].reset_index(drop=True)


def _canonical_snapshot_subset(dataset: pd.DataFrame) -> pd.DataFrame:
    """Shape a matrix subset so dashboard_execution.snapshot_execution can aggregate it."""
    if dataset is None or dataset.empty:
        return pd.DataFrame()
    data = dataset.copy()
    # snapshot_execution reads these canonical columns only.
    for column, default in (
        ("monitoring_conducted", True), ("coverage_eligible", False), ("submitted", False),
    ):
        if column not in data.columns:
            data[column] = default
    return data


def heatmap_payload(dataset: pd.DataFrame, goal_code: str, groups: list[str]) -> dict[str, Any]:
    """Task × group cells using canonical Dashboard execution aggregation."""
    if dataset is None or dataset.empty:
        return {"tasks": [], "groups": list(groups), "cells": {}}
    data = dataset[dataset["goal_code"].map(clean).eq(clean(goal_code))].copy()
    if data.empty:
        return {"tasks": [], "groups": list(groups), "cells": {}}

    task_meta: dict[str, str] = {}
    for _, row in data.iterrows():
        code = clean(row.get("task_code"))
        if not code:
            continue
        name = clean(row.get("task_name"))
        task_meta.setdefault(code, f"{code} — {name}" if name else code)

    def task_key(code: str):
        import re
        nums = re.findall(r"\d+", code)
        return tuple(int(v) for v in nums) if nums else (9999,)

    tasks = [(code, task_meta[code]) for code in sorted(task_meta, key=task_key)]
    cells: dict[tuple[str, str], dict[str, Any]] = {}
    for task_code, _ in tasks:
        task_rows = data[data["task_code"].eq(task_code)]
        for group in groups:
            cell_rows = task_rows[task_rows["group"].eq(group)].copy()
            measure_count = int(cell_rows["code"].nunique()) if not cell_rows.empty else 0
            if not measure_count:
                cells[(task_code, group)] = {
                    "measure_count": 0, "execution": None, "statuses": {},
                }
                continue
            metric = dashboard_execution.snapshot_execution(_canonical_snapshot_subset(cell_rows))
            statuses = (
                cell_rows.assign(_status=cell_rows["status_display"].where(cell_rows["status_display"].ne(""), "Не визначено"))
                .groupby("_status")["code"].nunique().to_dict()
            )
            cells[(task_code, group)] = {
                "measure_count": measure_count,
                "execution": metric.get("execution_by_measures"),
                "statuses": {clean(k): int(v) for k, v in statuses.items()},
            }
    return {"tasks": tasks, "groups": list(groups), "cells": cells}
