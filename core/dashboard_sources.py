"""Shared immutable period-source resolution for Dashboard execution v3.

This module owns *where* historical analytical inputs come from.  It does not
calculate execution, trajectory or risk; consumers still pass the returned
``period_sources`` into :func:`core.dashboard_breakdowns.build_period_results`.

The resolver mirrors the accepted Dashboard v3 archive semantics:
- only explicit v3-compatible archive periods are eligible;
- archived strategic matrix, monitoring requests, closeouts and period locks
  are used together as one immutable source;
- operational mode reconstructs coordinator-passed versions from archived logs
  and request versions;
- the immediate previous quarter is resolved together with each requested
  Q2/Q3/Q4 period so trajectory never mixes archived current data with mutable
  previous-quarter data.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

import pandas as pd

from core import dashboard_filters as dashboard_filters_v3
from core.dashboard_execution import DASHBOARD_FORMULA_VERSION
from core.dashboard_periods import clean
from core.periods import quarter_to_number_strict, quarter_to_roman


def archive_reporting_period(row: Mapping[str, Any] | None, payload: Mapping[str, Any] | None):
    """Return an explicit v3 reporting period or ``None`` for ambiguous archives."""
    if not isinstance(payload, Mapping):
        return None
    expected_formula = DASHBOARD_FORMULA_VERSION
    formula = str(payload.get("dashboard_formula_version") or "").strip()
    if formula and formula != expected_formula:
        return None

    reason = str((row or {}).get("reason") or "").strip()
    match = re.search(r"\b(IV|III|II|I)\s+квартал\s+(20\d{2})", reason, flags=re.I)
    if match:
        return int(match.group(2)), match.group(1).upper()

    trend = payload.get("dashboard_trend_kpi")
    if isinstance(trend, Mapping):
        trend_formula = str(trend.get("formula_version") or formula or "").strip()
        if trend_formula and trend_formula != expected_formula:
            return None
        try:
            year = int(float(trend.get("year")))
        except (TypeError, ValueError):
            return None
        quarter_raw = str(trend.get("quarter") or "").strip().upper()
        quarter = {
            "1": "I", "2": "II", "3": "III", "4": "IV",
            "I": "I", "II": "II", "III": "III", "IV": "IV",
        }.get(quarter_raw)
        if quarter:
            return year, quarter
    return None


def _cache_data(ttl: int = 300):
    """Use Streamlit cache in-app while keeping this module importable in pure tests."""
    try:
        import streamlit as st  # imported lazily so pure regression tests need no UI runtime
    except (ImportError, ModuleNotFoundError):
        return lambda fn: fn
    return st.cache_data(ttl=ttl, show_spinner=False)


@_cache_data(ttl=300)
def load_archive_payloads() -> dict[tuple[int, str], dict[str, Any]]:
    """Read immutable v3-compatible snapshots keyed only by explicit reporting period."""
    try:
        from core.archive import decode_snapshot_payload
        from core.db import fetch_all

        rows = fetch_all(
            "archive_snapshots",
            "id,year,quarter,reason,archived_at,snapshot_type,snapshot_gzip_b64",
            order=("archived_at", True),
        )
    except Exception:
        return {}

    result: dict[tuple[int, str], dict[str, Any]] = {}
    for row in rows or []:
        encoded = row.get("snapshot_gzip_b64")
        if not encoded:
            continue
        try:
            payload = decode_snapshot_payload(encoded)
        except Exception:
            continue
        period = archive_reporting_period(row, payload)
        if period is None:
            continue
        # Ordered oldest→newest; later explicit snapshots deliberately win.
        result[period] = payload
    return result


def apply_archived_closeouts(requests: pd.DataFrame | None, closeouts: Any) -> pd.DataFrame:
    """Materialise immutable closeout facts from an archive payload for analytics."""
    data = requests.copy() if isinstance(requests, pd.DataFrame) else pd.DataFrame()
    if not isinstance(closeouts, list) or not closeouts:
        return data

    existing: set[tuple[str, str, str]] = set()
    if not data.empty:
        approval = data.get("approval_status", pd.Series(index=data.index, dtype=str)).astype(str)
        for _, row in data[approval.eq("Погоджено")].iterrows():
            existing.add((
                clean(row.get("strat_code")),
                str(row.get("year")).strip(),
                quarter_to_roman(row.get("quarter")),
            ))

    additions: list[dict[str, Any]] = []
    for row in closeouts:
        if clean(row.get("approval_status")) != "Підтверджено":
            continue
        code = clean(row.get("strat_code"))
        year = str(row.get("period_year") or "").strip()
        scope = clean(row.get("scope")).casefold()
        quarter = quarter_to_roman(row.get("period_quarter"))
        quarters = ["I", "II", "III", "IV"] if scope == "рік" else [quarter]
        for q in quarters:
            if not q or (code, year, q) in existing:
                continue
            additions.append({
                "strat_code": code,
                "year": year,
                "quarter": q,
                "approval_status": "Погоджено",
                "status": clean(row.get("fact_status")) or "Не подано",
                "numeric_value": row.get("fact_numeric_value"),
                "value_text": row.get("fact_value_text"),
                "progress_text": clean(row.get("fact_progress_text")),
                "risks": "",
                "submitted_at": clean(row.get("decided_at")),
                "object_kind": "measure",
                "_manual_closeout": True,
            })
    if not additions:
        return data
    return pd.concat([data, pd.DataFrame(additions)], ignore_index=True, sort=False)


def archive_locked_periods(payload: Mapping[str, Any] | None) -> set[tuple[str, int]]:
    """Return period-lock state frozen inside one immutable archive payload."""
    locked: set[tuple[str, int]] = set()
    rows = payload.get("period_locks") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        return locked
    for row in rows:
        try:
            if bool(row.get("locked")):
                locked.add((str(int(row.get("year"))), quarter_to_number_strict(row.get("quarter"))))
        except (TypeError, ValueError):
            continue
    return locked


def required_source_periods(pairs: Iterable[tuple[Any, Any]]) -> set[tuple[int, str]]:
    """Requested periods plus each same-year immediate previous quarter."""
    required: set[tuple[int, str]] = set()
    for year, quarter in pairs or []:
        q = quarter_to_roman(quarter)
        if not q:
            continue
        key = (int(year), q)
        required.add(key)
        q_num = quarter_to_number_strict(q)
        if q_num > 1:
            required.add((int(year), {1: "I", 2: "II", 3: "III", 4: "IV"}[q_num - 1]))
    return required


def _measure_requests_only(data: pd.DataFrame) -> pd.DataFrame:
    """Use the repository helper in-app; pure fallback keeps tests UI-independent."""
    try:
        from core import monitoring_data
        return monitoring_data.measures_only(data)
    except (ImportError, ModuleNotFoundError):
        if data is None or data.empty:
            return data.copy() if hasattr(data, "copy") else pd.DataFrame()
        if "object_kind" not in data.columns:
            return data.copy()
        kind = data["object_kind"].fillna("measure").astype(str).str.strip().str.lower()
        return data[kind != "indicator"].copy()


def build_period_source_overrides(
    pairs: Iterable[tuple[Any, Any]],
    *,
    operational_mode: bool = False,
    ssp: Iterable[Any] | None = None,
    goals: Iterable[Any] | None = None,
    tasks: Iterable[Any] | None = None,
    measure_codes: Iterable[Any] | None = None,
    product_types: Iterable[Any] | None = None,
    deputies: Iterable[Any] | None = None,
    sources: Iterable[Any] | None = None,
    financing: Iterable[Any] | None = None,
    kpkvk: Iterable[Any] | None = None,
    payloads: Mapping[tuple[int, str], Mapping[str, Any]] | None = None,
) -> dict[tuple[int, str], dict[str, Any]]:
    """Resolve immutable archive inputs for selected periods and trajectory history.

    ``payloads`` is injectable for pure regression tests.  Production callers
    omit it and use the cached read-only archive loader.
    """
    archive_payloads = dict(load_archive_payloads() if payloads is None else payloads)
    if not archive_payloads:
        return {}

    result: dict[tuple[int, str], dict[str, Any]] = {}
    for key in required_source_periods(pairs):
        payload = archive_payloads.get(key)
        if not isinstance(payload, Mapping):
            continue

        archived_strat = pd.DataFrame(payload.get("main_table") or [])
        archived_requests = pd.DataFrame(payload.get("monitoring_requests") or [])
        if archived_strat.empty:
            continue

        archived_strat = dashboard_filters_v3.filter_measures(
            archived_strat,
            ssp=ssp,
            goals=goals,
            tasks=tasks,
            measure_codes=measure_codes,
            product_types=product_types,
            deputies=deputies,
            sources=sources,
            financing=financing,
            kpkvk=kpkvk,
        )
        if archived_strat.empty:
            continue

        archived_requests = apply_archived_closeouts(
            archived_requests, payload.get("closeout_requests") or []
        )
        if operational_mode and not archived_requests.empty:
            # Runtime-only import: pure source tests do not require Streamlit.
            from core import operational

            archived_requests, _ = operational.apply_operational_mode(
                archived_requests,
                logs_df=pd.DataFrame(payload.get("monitoring_logs") or []),
                versions_df=pd.DataFrame(payload.get("monitoring_request_versions") or []),
            )
        archived_requests = _measure_requests_only(archived_requests)
        result[key] = {
            "strat_df": archived_strat,
            "requests_df": archived_requests,
            "locked_periods": archive_locked_periods(payload),
        }
    return result
