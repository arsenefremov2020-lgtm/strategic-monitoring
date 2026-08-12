"""Pure filtering and stable-cohort helpers for Dashboard execution v2."""
from __future__ import annotations

import re
from typing import Any, Iterable

import pandas as pd

from core.dashboard_finance import classify_finance_sources
from core.dashboard_periods import clean


def split_ssp(value: Any) -> set[str]:
    return set(re.findall(r"\d+", clean(value)))


def measure_ssp_memberships(row: pd.Series | dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for col in ["resp_main", "resp_co_1", "resp_co_2", "department", "department_co_1", "department_co_2"]:
        result |= split_ssp(row.get(col, ""))
    return result


def filter_measures(
    measures: pd.DataFrame,
    *,
    ssp: Iterable[Any] | None = None,
    goals: Iterable[Any] | None = None,
    tasks: Iterable[Any] | None = None,
    measure_codes: Iterable[Any] | None = None,
    product_types: Iterable[Any] | None = None,
    deputies: Iterable[Any] | None = None,
    statuses: Iterable[Any] | None = None,
    sources: Iterable[Any] | None = None,
    financing: Iterable[Any] | None = None,
    kpkvk: Iterable[Any] | None = None,
) -> pd.DataFrame:
    if measures is None or measures.empty:
        return measures.copy() if hasattr(measures, "copy") else pd.DataFrame()
    data = measures.copy()
    if "object_type" in data.columns:
        data = data[data["object_type"].astype(str).str.strip().eq("measure")].copy()

    wanted_ssp = {clean(v) for v in (ssp or []) if clean(v)}
    if wanted_ssp:
        data = data[data.apply(lambda r: bool(measure_ssp_memberships(r) & wanted_ssp), axis=1)].copy()

    def _isin(col: str, values: Iterable[Any] | None) -> None:
        nonlocal data
        wanted = {clean(v) for v in (values or []) if clean(v)}
        if wanted and col in data.columns:
            data = data[data[col].map(clean).isin(wanted)].copy()

    _isin("parent_goal_code", goals); _isin("parent_task_code", tasks); _isin("code", measure_codes)
    _isin("product_type", product_types); _isin("deputy_minister_raw", deputies)
    _isin("status", statuses); _isin("budget_kpkvk", kpkvk)

    wanted_sources = {clean(v) for v in (sources or []) if clean(v)}
    if wanted_sources:
        source_cols = [c for c in ["source_national", "source_global"] if c in data.columns]
        if source_cols:
            data = data[data.apply(lambda r: any(clean(r.get(c)) in wanted_sources for c in source_cols), axis=1)].copy()

    wanted_fin = {clean(v).casefold() for v in (financing or []) if clean(v)}
    if wanted_fin:
        data = data[data.apply(
            lambda row: bool({x.casefold() for x in classify_finance_sources(row)} & wanted_fin), axis=1
        )].copy()

    if "code" in data.columns:
        data = data.drop_duplicates(subset=["code"], keep="first")
    return data.reset_index(drop=True)


def status_filter_snapshot(snapshot: pd.DataFrame, statuses: Iterable[Any] | None) -> pd.DataFrame:
    wanted = {clean(v) for v in (statuses or []) if clean(v)}
    if not wanted or snapshot is None or snapshot.empty:
        return snapshot.copy() if hasattr(snapshot, "copy") else pd.DataFrame()
    return snapshot[snapshot["status"].map(clean).isin(wanted)].copy()


def stable_cohort_codes(latest_snapshot: pd.DataFrame, statuses: Iterable[Any] | None) -> set[str]:
    filtered = status_filter_snapshot(latest_snapshot, statuses)
    if filtered is None or filtered.empty:
        return set()
    return {clean(v) for v in filtered["code"].tolist() if clean(v)}


def apply_stable_cohort(snapshot: pd.DataFrame, codes: Iterable[Any]) -> pd.DataFrame:
    wanted = {clean(v) for v in codes if clean(v)}
    if snapshot is None or snapshot.empty:
        return snapshot.copy() if hasattr(snapshot, "copy") else pd.DataFrame()
    if not wanted:
        return snapshot.iloc[0:0].copy()
    return snapshot[snapshot["code"].map(clean).isin(wanted)].copy()


def expand_ssp_rows(snapshot: pd.DataFrame, selected_ssp: Iterable[Any] | None = None) -> pd.DataFrame:
    """One row per measure×SSP for organizational charts only."""
    if snapshot is None or snapshot.empty:
        return pd.DataFrame()
    wanted = {clean(v) for v in (selected_ssp or []) if clean(v)}
    rows = []
    for _, row in snapshot.iterrows():
        memberships = measure_ssp_memberships(row)
        if wanted:
            memberships &= wanted
        for ssp in sorted(memberships, key=lambda x: int(x) if x.isdigit() else 9999):
            out = row.to_dict(); out["ssp"] = ssp; rows.append(out)
    return pd.DataFrame(rows)
