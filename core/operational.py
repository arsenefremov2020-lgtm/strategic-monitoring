# core/operational.py

"""Data-source modes for monitoring analytics.

Both modes use the submitted statistical value and the submitted execution
status without recalculation or automatic status substitution. Quarterly values
are cumulative year-to-date values and are therefore consumed exactly as stored.

Confirmed data includes only requests finally approved by the last link of the
approval chain. Operational data additionally includes the immutable request version that the
audit log proves had already passed the coordinator. If the request is later
returned and edited, the newer unapproved payload never replaces the version
that the coordinator actually reviewed.
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
    "значення відповідної погодженої/координаторської версії та її реальний статус виконання."
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


@st.cache_data(ttl=20, show_spinner=False)
def load_monitoring_versions() -> pd.DataFrame:
    """Read immutable request versions used to reconstruct coordinator-approved facts."""
    try:
        return pd.DataFrame(fetch_all("monitoring_request_versions", "*", order=("id", False)))
    except Exception as exc:
        show_warning(
            "Не вдалося прочитати версії заявок; оперативна оцінка використовуватиме підтверджені дані без неперевірених підмін.",
            exc,
            "Читання monitoring_request_versions для оперативної оцінки",
        )
        return pd.DataFrame()


def _coordinator_pass_events(logs_df: pd.DataFrame | None) -> dict[int, pd.Timestamp]:
    """Latest audit timestamp at which each request demonstrably passed coordinator."""
    logs = _ensure_log_columns(logs_df)
    events: dict[int, pd.Timestamp] = {}
    for _, row in logs.iterrows():
        request_id = _request_id(row.get("request_id"))
        if request_id is None:
            continue
        related_table = _clean(row.get("related_table"))
        if related_table and related_table != "monitoring_requests":
            continue
        old_status = _clean(row.get("old_status"))
        new_status = _clean(row.get("new_status"))
        if old_status != STATUS_COORDINATOR_REVIEW or new_status not in _FORWARD_AFTER_COORDINATOR_STATUSES:
            continue
        actor_role = _clean(row.get("actor_role"))
        action = _clean(row.get("action")).casefold()
        if not (actor_role == ROLE_ADMIN or ("координатор" in action and "повернен" not in action)):
            continue
        ts = pd.to_datetime(row.get("changed_at"), errors="coerce", utc=True)
        if pd.isna(ts):
            continue
        if request_id not in events or ts > events[request_id]:
            events[request_id] = ts
    return events


def _restore_coordinator_passed_versions(
    monitoring_df: pd.DataFrame,
    logs_df: pd.DataFrame | None,
    versions_df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, set[int]]:
    """Replace mutable payloads with the immutable version seen at coordinator pass.

    Final-approved rows remain current/final. Only non-final requests that have
    actually passed the coordinator are overlaid from version history. If a
    trustworthy version cannot be found, that request is excluded from the
    operational extension rather than presenting a later edited fact as approved.
    """
    data = monitoring_df.copy()
    events = _coordinator_pass_events(logs_df)
    if not events or data.empty:
        return data, set()
    versions = load_monitoring_versions() if versions_df is None else versions_df.copy()
    if versions.empty or "request_id" not in versions.columns:
        return data, set()

    versions = versions.copy()
    versions["_request_id"] = versions["request_id"].apply(_request_id)
    versions["_created_at"] = pd.to_datetime(versions.get("created_at"), errors="coerce", utc=True)
    versions["_version_number"] = pd.to_numeric(versions.get("version_number"), errors="coerce").fillna(-1)
    payload_columns = [
        "year", "quarter", "department", "responsible_person", "phone", "email",
        "strat_code", "status", "progress_text", "risks", "file_names", "file_urls",
        "approval_status", "admin_comment", "start_date", "end_date", "npa_link",
        "approval_chain", "chain_stage", "scheme_label", "object_kind", "object_name",
        "indicator_name", "as_of_date", "numeric_value", "value_text",
    ]
    trustworthy: set[int] = set()
    id_series = data.get("id", pd.Series(index=data.index, dtype=object)).apply(_request_id)
    for request_id, pass_ts in events.items():
        current_idx = data.index[id_series == request_id].tolist()
        if not current_idx:
            continue
        current_row = data.loc[current_idx[0]]
        if _clean(current_row.get("approval_status")) == CONFIRMED_STATUS:
            trustworthy.add(request_id)
            continue
        candidates = versions[
            (versions["_request_id"] == request_id)
            & (versions["_created_at"].notna())
            & (versions["_created_at"] <= pass_ts + pd.Timedelta(seconds=2))
        ].copy()
        if candidates.empty:
            continue
        version = candidates.sort_values(["_created_at", "_version_number"], ascending=[False, False]).iloc[0]
        for col in payload_columns:
            if col in data.columns and col in version.index:
                data.at[current_idx[0], col] = version.get(col)
        data.at[current_idx[0], "_coordinator_pass_version"] = int(version.get("version_number") or 0)
        data.at[current_idx[0], "_coordinator_passed_at"] = pass_ts.isoformat()
        trustworthy.add(request_id)
    return data, trustworthy


def coordinator_passed_request_ids(logs_df: pd.DataFrame | None) -> set[int]:
    """Return request IDs that demonstrably passed the coordinator."""
    return set(_coordinator_pass_events(logs_df).keys())


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
    versions_df: pd.DataFrame | None = None,
) -> dict:
    """Build an operational overlay without changing submitted statistics.

    ``target_by_code_year`` is accepted only for backward compatibility and is
    intentionally ignored: annual targets no longer alter execution statuses.
    """
    if monitoring_df is None or monitoring_df.empty:
        return {}

    logs = load_monitoring_logs() if logs_df is None else logs_df
    restored, passed_ids = _restore_coordinator_passed_versions(monitoring_df, logs, versions_df)
    _, effective = _latest_effective_rows(restored, passed_ids)
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
    versions_df: pd.DataFrame | None = None,
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
    restored, passed_ids = _restore_coordinator_passed_versions(monitoring_df, logs, versions_df)
    non_eligible, effective = _latest_effective_rows(restored, passed_ids)

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



def operational_indicator_rows(
    monitoring_df: pd.DataFrame,
    *,
    logs_df: pd.DataFrame | None = None,
    versions_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return one effective indicator request per indicator/year/quarter.

    Uses the same immutable coordinator-pass reconstruction as measure
    operational mode, but keeps ``indicator_name`` in the identity key so
    multiple indicators under the same strategic code never collapse together.
    """
    if monitoring_df is None or monitoring_df.empty:
        return pd.DataFrame(columns=getattr(monitoring_df, "columns", []))
    logs = load_monitoring_logs() if logs_df is None else logs_df
    restored, passed_ids = _restore_coordinator_passed_versions(
        monitoring_df, logs, versions_df
    )
    data = restored.copy()
    for col in ["id", "object_kind", "approval_status", "strat_code", "indicator_name", "year", "quarter", "submitted_at"]:
        if col not in data.columns:
            data[col] = ""
    ids = data["id"].apply(_request_id)
    indicator_mask = data["object_kind"].astype(str).str.strip().str.lower() == "indicator"
    final_mask = data["approval_status"].astype(str).str.strip() == CONFIRMED_STATUS
    passed_mask = ids.isin(passed_ids)
    eligible = data[indicator_mask & (final_mask | passed_mask)].copy()
    if eligible.empty:
        return eligible
    eligible["_indicator_key"] = eligible.apply(
        lambda r: (
            _clean(r.get("strat_code")), _clean(r.get("indicator_name")),
            _year_key(r.get("year")), quarter_key(r.get("quarter")),
        ),
        axis=1,
    )
    eligible["_sort_dt"] = pd.to_datetime(eligible["submitted_at"], errors="coerce", utc=True)
    eligible["_sort_id"] = eligible["id"].apply(lambda value: _request_id(value) or -1)
    eligible = (
        eligible.sort_values(["_indicator_key", "_sort_dt", "_sort_id"], na_position="first")
        .groupby("_indicator_key", as_index=False, sort=False).tail(1)
        .drop(columns=["_indicator_key", "_sort_dt", "_sort_id"])
    )
    eligible["_source_approval_status"] = eligible["approval_status"]
    eligible["_operational"] = eligible["approval_status"].astype(str).str.strip() != CONFIRMED_STATUS
    eligible.loc[eligible["_operational"], "approval_status"] = CONFIRMED_STATUS
    return eligible

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
