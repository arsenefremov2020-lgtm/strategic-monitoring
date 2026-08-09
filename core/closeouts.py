"""Shared helper for the admin/super-admin manual closeout workflow.

Reads confirmed ("Підтверджено") closeout_requests rows so the "Закрито
вручну" badge can be rendered consistently wherever a measure's status is
shown (app.py, monitoring submission page, dashboard).

Особливості:
- закриття з масштабом «Рік» (scope='Рік' або period_quarter у
  {'Рік','РІК',''}) розгортається на всі чотири квартали цього року;
- скасовані супер-адміном закриття (approval_status='Скасовано')
  сюди не потрапляють — фільтр лише за «Підтверджено».
"""

import streamlit as st
import pandas as pd

from core.data_types import quarter_to_display, year_to_display
from core.db import fetch_all
from core.errors import show_warning
from core.strategic_data import raw_value

_YEAR_MARKERS = {"рік", "весь рік", ""}
_ALL_QUARTERS = ("I", "II", "III", "IV")


@st.cache_data(ttl=300)
def load_manual_closeouts():
    """Returns a set of (strat_code, year, quarter) confirmed as 'Закрито вручну'."""
    try:
        rows = fetch_all(
            "closeout_requests",
            "strat_code,period_year,period_quarter,approval_status",
            filters=[("eq", "approval_status", "Підтверджено")],
            order=("id", False),
        )
    except Exception as exc:
        show_warning(
            "Не вдалося прочитати ручні закриття; відповідні статуси тимчасово не враховуються.",
            exc,
            "Читання closeout_requests",
        )
        return set()

    if not rows:
        return set()

    result = set()
    for r in rows:
        code = raw_value(r.get("strat_code"))
        year = year_to_display(r.get("period_year"))
        quarter = quarter_to_display(r.get("period_quarter"))

        if quarter.strip().lower() in _YEAR_MARKERS:
            # Закриття на весь рік — позначає всі квартали
            for q in _ALL_QUARTERS:
                result.add((code, year, q))
        else:
            result.add((code, year, quarter))

    return result


@st.cache_data(ttl=300)
def load_manual_closeout_records() -> pd.DataFrame:
    """Return confirmed closeouts with their actual recorded facts.

    Unlike :func:`load_manual_closeouts`, this keeps the closeout payload so
    analytical pages do not have to invent an execution status when a
    materialised monitoring request is missing. Year-scope closeouts are
    expanded into four logical quarter rows for read-only consumption.
    """
    columns = [
        "id", "strat_code", "period_year", "period_quarter", "scope",
        "approval_status", "fact_status", "fact_numeric_value",
        "fact_value_text", "fact_progress_text", "department",
        "object_name", "indicator_name", "materialized_request_ids",
        "requested_at", "decided_at",
    ]
    try:
        rows = fetch_all(
            "closeout_requests",
            ",".join(columns),
            filters=[("eq", "approval_status", "Підтверджено")],
            order=("id", False),
        )
    except Exception as exc:
        show_warning(
            "Не вдалося прочитати деталі ручних закриттів; відповідні факти тимчасово не враховуються.",
            exc,
            "Читання деталей closeout_requests",
        )
        return pd.DataFrame(columns=columns + ["year", "quarter", "materialization_ok", "valid_materialized_request_ids"])

    try:
        request_rows = fetch_all(
            "monitoring_requests",
            "id,strat_code,year,quarter,approval_status,scheme_label,object_kind",
        ) or []
        request_by_id = {
            int(r.get("id")): dict(r)
            for r in request_rows
            if r.get("id") is not None
        }
    except Exception:
        request_by_id = {}

    expanded = []
    for source in rows or []:
        row = dict(source)
        code = raw_value(row.get("strat_code"))
        year = year_to_display(row.get("period_year"))
        quarter = quarter_to_display(row.get("period_quarter"))
        scope = raw_value(row.get("scope")).strip().lower()
        quarter_values = _ALL_QUARTERS if scope == "рік" or quarter.strip().lower() in _YEAR_MARKERS else (quarter,)
        ids = row.get("materialized_request_ids")
        materialized_ids = ids if isinstance(ids, list) else []
        parsed_ids = []
        for value in materialized_ids:
            try:
                parsed_ids.append(int(value))
            except (TypeError, ValueError):
                continue

        for q in quarter_values:
            # P0-02: existence of *some* request ID is not enough. The linked
            # row must represent this exact closeout code/year/quarter and be
            # the final approved manual-closeout materialisation.
            valid_materialized_ids = []
            for request_id in parsed_ids:
                request = request_by_id.get(request_id)
                if not request:
                    continue
                if raw_value(request.get("strat_code")) != code:
                    continue
                if year_to_display(request.get("year")) != year:
                    continue
                if quarter_to_display(request.get("quarter")) != q:
                    continue
                if raw_value(request.get("approval_status")) != "Погоджено":
                    continue
                if raw_value(request.get("scheme_label")) != "Ручне закриття":
                    continue
                if raw_value(request.get("object_kind")).strip().lower() == "indicator":
                    continue
                valid_materialized_ids.append(request_id)

            item = dict(row)
            item["strat_code"] = code
            item["year"] = year
            item["quarter"] = q
            item["materialization_ok"] = bool(valid_materialized_ids)
            item["valid_materialized_request_ids"] = valid_materialized_ids
            expanded.append(item)
    return pd.DataFrame(expanded, columns=columns + ["year", "quarter", "materialization_ok", "valid_materialized_request_ids"])


def manual_closeout_record_index(records: pd.DataFrame | None = None) -> dict[tuple[str, str, str], dict]:
    """Index confirmed closeout facts by ``(code, year, quarter)``."""
    frame = load_manual_closeout_records() if records is None else records
    if frame is None or frame.empty:
        return {}
    result = {}
    ordered = frame.copy()
    if "id" in ordered.columns:
        ordered = ordered.sort_values("id")
    for _, row in ordered.iterrows():
        key = (
            raw_value(row.get("strat_code")),
            year_to_display(row.get("year")),
            quarter_to_display(row.get("quarter")),
        )
        result[key] = row.to_dict()
    return result


def closeout_integrity_issues(records: pd.DataFrame | None = None) -> pd.DataFrame:
    """Confirmed closeouts whose materialised monitoring request is missing.

    This is a read-only diagnostic used by administrative screens.  It does
    not attempt to repair data automatically: legacy rows without a recorded
    fact require manual reconciliation.
    """
    frame = load_manual_closeout_records() if records is None else records.copy()
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["id", "strat_code", "year", "quarter", "fact_status", "materialization_ok"])
    issues = frame[~frame.get("materialization_ok", pd.Series(False, index=frame.index)).fillna(False)].copy()
    if issues.empty:
        return issues
    subset = [
        col for col in [
            "id", "strat_code", "year", "quarter", "fact_status",
            "fact_numeric_value", "fact_value_text", "fact_progress_text",
            "materialized_request_ids", "materialization_ok",
        ] if col in issues.columns
    ]
    return issues[subset].drop_duplicates(subset=[col for col in ["id", "strat_code", "year", "quarter"] if col in subset])


def closeout_fact_value(record: dict | None):
    """Return numeric or textual closeout fact without fabricating a value."""
    record = record or {}
    numeric = record.get("fact_numeric_value")
    if numeric is not None and raw_value(numeric) != "":
        return numeric
    return record.get("fact_value_text")


def append_confirmed_closeout_facts(
    requests: pd.DataFrame | None,
    records: pd.DataFrame | None = None,
    *,
    include_incomplete: bool = True,
) -> pd.DataFrame:
    """Append confirmed manual closeouts as ordinary read-only measure facts.

    This is the shared bridge between ``closeout_requests`` and analytical
    consumers.  It never fabricates ``Виконано``.  When a confirmed closeout
    has a valid materialised approved request for the same period, that request
    remains the source of truth and no synthetic duplicate is added.  Broken
    materialisation is represented from the fact stored on the closeout itself.

    ``include_incomplete=False`` is intended for methodologies that must not
    receive a legacy closeout without a recorded fact (notably MіО inputs).
    """
    frame = requests.copy() if isinstance(requests, pd.DataFrame) else pd.DataFrame()
    closeout_frame = load_manual_closeout_records() if records is None else records.copy()
    if closeout_frame is None or closeout_frame.empty:
        return frame

    def _key(code, year, quarter):
        return (
            raw_value(code).strip(),
            year_to_display(year),
            quarter_to_display(quarter),
        )

    approved_keys = set()
    if not frame.empty:
        approval = frame.get("approval_status", pd.Series("", index=frame.index)).astype(str).str.strip()
        kind = frame.get("object_kind", pd.Series("measure", index=frame.index)).astype(str).str.strip().str.lower()
        for _, row in frame[(approval == "Погоджено") & (kind != "indicator")].iterrows():
            approved_keys.add(_key(row.get("strat_code"), row.get("year"), row.get("quarter")))

    additions = []
    for _, row in closeout_frame.iterrows():
        key = _key(row.get("strat_code"), row.get("year"), row.get("quarter"))
        if key in approved_keys and bool(row.get("materialization_ok")):
            continue

        fact_status = raw_value(row.get("fact_status"))
        fact_value = closeout_fact_value(row.to_dict())
        has_fact = bool(fact_status or raw_value(fact_value) or raw_value(row.get("fact_progress_text")))
        if not has_fact and not include_incomplete:
            continue

        try:
            closeout_id = int(row.get("id"))
        except Exception:
            closeout_id = 0
        quarter_display = key[2]
        try:
            quarter_index = _ALL_QUARTERS.index(quarter_display) + 1
        except ValueError:
            quarter_index = 0
        synthetic_id = -(closeout_id * 10 + quarter_index) if closeout_id else None

        numeric = row.get("fact_numeric_value")
        value_text = row.get("fact_value_text")
        additions.append({
            "id": synthetic_id,
            "year": int(key[1]) if key[1].isdigit() else key[1],
            "quarter": quarter_display,
            "department": raw_value(row.get("department")),
            "strat_code": key[0],
            "status": fact_status if fact_status else "Не подано",
            "numeric_value": numeric if raw_value(numeric) else None,
            "value_text": value_text if raw_value(value_text) else None,
            "progress_text": raw_value(row.get("fact_progress_text")),
            "risks": "",
            "approval_status": "Погоджено",
            "submitted_at": row.get("decided_at") or row.get("requested_at"),
            "updated_at": row.get("decided_at") or row.get("requested_at"),
            "object_kind": "measure",
            "object_name": raw_value(row.get("object_name")),
            "indicator_name": "",
            "scheme_label": "Ручне закриття",
            "_manual_closeout": True,
            "_closeout_id": closeout_id,
            "_closeout_materialization_ok": bool(row.get("materialization_ok")),
            "_closeout_needs_reconciliation": not bool(row.get("materialization_ok")),
        })

    if not additions:
        return frame
    additions_df = pd.DataFrame(additions)
    for column in additions_df.columns:
        if column not in frame.columns:
            frame[column] = None
    for column in frame.columns:
        if column not in additions_df.columns:
            additions_df[column] = None
    return pd.concat([frame, additions_df[frame.columns]], ignore_index=True, sort=False)
