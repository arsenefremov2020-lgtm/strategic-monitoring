from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

import pandas as pd

from .models import AnalyticsContext


def _normalise_scalar(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, (str, int, bool)):
        return value
    return str(value)


def _frame_digest(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    records: list[dict[str, Any]] = []
    for row in frame.to_dict("records"):
        records.append({str(k): _normalise_scalar(v) for k, v in sorted(row.items(), key=lambda item: str(item[0]))})
    records.sort(key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True, default=str))
    return records


def build_signature(filters: Mapping[str, Any], metrics: Mapping[str, Any], frames: Mapping[str, pd.DataFrame]) -> str:
    payload = {
        "filters": {str(k): _normalise_scalar(v) if not isinstance(v, (list, tuple, set)) else sorted(map(str, v)) for k, v in sorted(filters.items())},
        "metrics": {str(k): _normalise_scalar(v) for k, v in sorted(metrics.items())},
        "frames": {name: _frame_digest(frame) for name, frame in sorted(frames.items())},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_context(
    *,
    filters: Mapping[str, Any],
    metrics: Mapping[str, Any],
    goal_progress: pd.DataFrame,
    task_progress: pd.DataFrame,
    department_progress: pd.DataFrame,
    product_progress: pd.DataFrame,
    status_counts: pd.DataFrame,
    period_dynamics: pd.DataFrame,
    yoy_comparison: pd.DataFrame,
    active: pd.DataFrame,
) -> AnalyticsContext:
    frames = {
        "goal": goal_progress,
        "task": task_progress,
        "department": department_progress,
        "product": product_progress,
        "status": status_counts,
        "dynamics": period_dynamics,
        "yoy": yoy_comparison,
    }
    return AnalyticsContext(
        filters=dict(filters),
        metrics=dict(metrics),
        goal_progress=goal_progress.copy() if goal_progress is not None else pd.DataFrame(),
        task_progress=task_progress.copy() if task_progress is not None else pd.DataFrame(),
        department_progress=department_progress.copy() if department_progress is not None else pd.DataFrame(),
        product_progress=product_progress.copy() if product_progress is not None else pd.DataFrame(),
        status_counts=status_counts.copy() if status_counts is not None else pd.DataFrame(),
        period_dynamics=period_dynamics.copy() if period_dynamics is not None else pd.DataFrame(),
        yoy_comparison=yoy_comparison.copy() if yoy_comparison is not None else pd.DataFrame(),
        active=active.copy() if active is not None else pd.DataFrame(),
        signature=build_signature(filters, metrics, frames),
    )
