from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

import pandas as pd

from .models import AnalyticsContext

_MISSING_TEXT = {"", "—", "–", "-", "н/д", "n/a", "na", "none", "null", "nan"}


def safe_number(value: Any) -> float | None:
    """Normalize a scalar to float without raising on production missing values."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in _MISSING_TEXT:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def safe_int(value: Any, default: int = 0) -> int:
    number = safe_number(value)
    return default if number is None else int(number)


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str) and value.strip().lower() in _MISSING_TEXT:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        return ""
    return str(value).strip()


def safe_dataframe(frame: pd.DataFrame | None) -> pd.DataFrame:
    """Return a detached production-safe frame; optional/missing values stay missing.

    This layer intentionally does not invent columns or recalculate KPI values. It
    only converts common textual missing markers to ``pd.NA`` so downstream
    analytics can use numeric coercion consistently.
    """
    if frame is None:
        return pd.DataFrame()
    out = frame.copy()
    for column in out.columns:
        if out[column].dtype == object or pd.api.types.is_string_dtype(out[column].dtype):
            out[column] = out[column].map(
                lambda value: pd.NA if isinstance(value, str) and value.strip().lower() in _MISSING_TEXT else value
            )
    return out


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
    goal_progress = safe_dataframe(goal_progress)
    task_progress = safe_dataframe(task_progress)
    department_progress = safe_dataframe(department_progress)
    product_progress = safe_dataframe(product_progress)
    status_counts = safe_dataframe(status_counts)
    period_dynamics = safe_dataframe(period_dynamics)
    yoy_comparison = safe_dataframe(yoy_comparison)
    active = safe_dataframe(active)
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
        goal_progress=goal_progress,
        task_progress=task_progress,
        department_progress=department_progress,
        product_progress=product_progress,
        status_counts=status_counts,
        period_dynamics=period_dynamics,
        yoy_comparison=yoy_comparison,
        active=active,
        signature=build_signature(filters, metrics, frames),
    )
