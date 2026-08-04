# core/operational.py

"""Data-source modes for monitoring analytics.

Both modes use the submitted statistical value and the submitted execution
status without recalculation or automatic status substitution. Quarterly values
are cumulative year-to-date values and are therefore consumed exactly as stored.

Confirmed data includes only requests finally approved by the last link of the
approval chain. Operational data additionally includes the current contents of
requests for which the audit log proves that the coordinator previously passed
the request to a later link. That historical fact remains valid even when the
request was subsequently returned for revision.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config.roles import ROLE_ADMIN
from core.approval_schemes import (
    APPROVED_STATUS,
    STATUS_COORDINATOR_REVIEW,
    STATUS_MANAGER_REVIEW,
    STATUS_SUPERADMIN_REVIEW,
    STATUS_WAITING_MANAGER_SELECTION,
)
from core.db import fetch_all
from core.errors import show_warning
from core.periods import quarter_key

CONFIRMED_STATUS = APPROVED_STATUS

MODE_CONFIRMED = "✅ Підтверджені дані"
MODE_OPERATIONAL = "⚡ Оперативна оцінка"
MODE_OPTIONS = [MODE_CONFIRMED, MODE_OPERATIONAL]

MODE_HELP = (
    "«Підтверджені дані» — лише заявки, закриті останньою ланкою погодження. "
    "«Оперативна оцінка» — також заявки, щодо яких журнал дій підтверджує, що "
    "координатор уже передавав їх далі. В обох режимах використовуються однакові "
    "актуальні подані значення та реальний поданий статус виконання."
)

_FORWARD_AFTER_COORDINATOR_STATUSES = {
    STATUS_WAITING_MANAGER_SELECTION,
    STATUS_SUPERADMIN_REVIEW,
    STATUS_MANAGER_REVIEW,
    APPROVED_STATUS,
}

_LOG_COLUMNS = [
    "id",
    "request_id",
    "action",
    "old_status",
    "new_status",
    "changed_at",
    "actor_role",
    "related_table",
]


def _clean(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none", "null") else text


def _request_id(value) -> int | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _ensure_log_columns(logs_df: pd.DataFrame | None) -> pd.DataFrame:
    data = logs_df.copy() if isinstance(logs_df, pd.DataFrame) else pd.DataFrame()
    for column in _LOG_COLUMNS:
        if column not in data.columns:
            data[column] = ""
    return data


@st.cache_data(ttl=300, show_spinner=False)
def load_monitoring_logs() -> pd.DataFrame:
    """Read the approval audit trail used by the operational data mode."""
    try:
        rows = fetch_all("monitoring_logs", "*", order=("id", False))
        return _ensure_log_columns(pd.DataFrame(rows))
    except Exception as exc:
        show_warning(
            "Не вдалося прочитати журнал погодження; оперативна оцінка може бути неповною.",
            exc,
            "Читання monitoring_logs для оперативної оцінки",
        )
        return _ensure_log_columns(pd.DataFrame())


def coordinator_passed_request_ids(logs_df: pd.DataFrame | None) -> set[int]:
    """Return request IDs that the coordinator demonstrably passed onward.

    The decision is based on an audit transition from the coordinator-review
    state to a later state. The current request status is deliberately ignored.
    """
    logs = _ensure_log_columns(logs_df)
    if logs.empty:
        return set()

    passed: set[int] = set()
    for _, row in logs.iterrows():
        request_id = _request_id(row.get("request_id"))
        if request_id is None:
            continue

        related_table = _clean(row.get("related_table"))
        if related_table and related_table != "monitoring_requests":
            continue

        old_status = _clean(row.get("old_status"))
        new_status = _clean(row.get("new_status"))
        if old_status != STATUS_COORDINATOR_REVIEW:
            continue
        if new_status not in _FORWARD_AFTER_COORDINATOR_STATUSES:
            continue

        actor_role = _clean(row.get("actor_role"))
        action = _clean(row.get("action")).casefold()
        actor_is_coordinator = actor_role == ROLE_ADMIN
        action_is_coordinator = "координатор" in action and "повернен" not in action
        if actor_is_coordinator or action_is_coordinator:
            passed.add(request_id)

    return passed


def _year_key(value) -> str:
    text = _clean(value)
    if not text:
        return ""
    try:
        return str(int(float(text)))
    except (TypeError, ValueError):
        return text


def _period_key(record) -> tuple[str, str, str]:
    return (
        _clean(record.get("strat_code")),
        _year_key(record.get("year")),
        quarter_key(record.get("quarter")),
    )


def _latest_effective_rows(
    monitoring_df: pd.DataFrame,
    passed_request_ids: set[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = monitoring_df.copy()
    for column in [
        "id",
        "approval_status",
        "strat_code",
        "year",
        "quarter",
        "submitted_at",
        "object_kind",
    ]:
        if column not in data.columns:
            data[column] = ""

    measure_mask = data["object_kind"].fillna("measure").astype(str).str.strip().str.lower() != "indicator"
    request_ids = data["id"].apply(_request_id)
    confirmed_mask = data["approval_status"].astype(str).str.strip() == CONFIRMED_STATUS
    passed_mask = request_ids.isin(passed_request_ids)
    eligible_mask = measure_mask & (confirmed_mask | passed_mask)

    eligible = data[eligible_mask].copy()
    if eligible.empty:
        return data, eligible

    eligible["_period_code"] = eligible.apply(_period_key, axis=1)
    eligible["_sort_dt"] = pd.to_datetime(eligible["submitted_at"], errors="coerce", utc=True)
    eligible["_sort_id"] = eligible["id"].apply(lambda value: _request_id(value) or -1)
    eligible = (
        eligible
        .sort_values(["_period_code", "_sort_dt", "_sort_id"], na_position="first")
        .groupby("_period_code", as_index=False, sort=False)
        .tail(1)
        .drop(columns=["_period_code", "_sort_dt", "_sort_id"])
    )

    non_eligible = data[~eligible_mask].copy()
    return non_eligible, eligible


def build_operational_overlay(
    monitoring_df: pd.DataFrame,
    target_by_code_year=None,
    *,
    logs_df: pd.DataFrame | None = None,
) -> dict:
    """Build an operational overlay without changing submitted statistics.

    ``target_by_code_year`` is accepted only for backward compatibility and is
    intentionally ignored: annual targets no longer alter execution statuses.
    """
    if monitoring_df is None or monitoring_df.empty:
        return {}

    logs = load_monitoring_logs() if logs_df is None else logs_df
    passed_ids = coordinator_passed_request_ids(logs)
    _, effective = _latest_effective_rows(monitoring_df, passed_ids)
    overlay: dict = {}

    for _, record in effective.iterrows():
        if _clean(record.get("approval_status")) == CONFIRMED_STATUS:
            continue
        overlay[_period_key(record)] = {
            "record": record,
            "auto_completed": False,
            "status_override": None,
        }
    return overlay


def apply_operational_mode(
    monitoring_df: pd.DataFrame,
    target_by_code_year=None,
    *,
    logs_df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, list[dict]]:
    """Expose final and coordinator-passed requests through one downstream filter.

    For compatibility with existing pages, effective operational rows are marked
    with ``approval_status='Погоджено'``. Their submitted execution status and
    values remain untouched. The second return value is retained for the old API
    and is always empty because automatic completion no longer exists.
    """
    if monitoring_df is None or monitoring_df.empty:
        empty = monitoring_df.copy() if hasattr(monitoring_df, "copy") else pd.DataFrame()
        if isinstance(empty, pd.DataFrame):
            empty["_operational"] = False
            empty["_auto_completed"] = False
        return empty, []

    logs = load_monitoring_logs() if logs_df is None else logs_df
    passed_ids = coordinator_passed_request_ids(logs)
    non_eligible, effective = _latest_effective_rows(monitoring_df, passed_ids)

    if effective.empty:
        result = monitoring_df.copy()
        result["_operational"] = False
        result["_auto_completed"] = False
        return result, []

    effective = effective.copy()
    original_approval = effective["approval_status"].astype(str).str.strip()
    effective["_source_approval_status"] = effective["approval_status"]
    effective["_operational"] = original_approval != CONFIRMED_STATUS
    effective["_auto_completed"] = False
    effective.loc[effective["_operational"], "approval_status"] = CONFIRMED_STATUS

    non_eligible = non_eligible.copy()
    non_eligible["_source_approval_status"] = non_eligible.get("approval_status", "")
    non_eligible["_operational"] = False
    non_eligible["_auto_completed"] = False

    result = pd.concat([non_eligible, effective], ignore_index=True, sort=False)
    return result, []


def build_target_map(strat_df: pd.DataFrame) -> dict:
    """Backward-compatible target map; operational mode no longer consumes it."""
    result = {}
    if strat_df is None or strat_df.empty or "code" not in strat_df.columns:
        return result
    year_cols = {
        column: str(column).replace("target_", "")
        for column in strat_df.columns
        if str(column).startswith("target_")
    }
    for _, row in strat_df.iterrows():
        code = _clean(row.get("code"))
        if not code:
            continue
        for column, year in year_cols.items():
            result[(code, year)] = _clean(row.get(column))
    return result


def auto_completed_caption(auto_list: list[dict]) -> str:
    """Compatibility helper retained after removal of automatic completion."""
    return ""
