"""Structural portfolio helpers for the Dashboard test interface.

This module intentionally contains no period/status calculations. It applies the
same structural filters as Dashboard and summarizes the resulting measure set.
"""
from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

from config.npa_documents import CANONICAL_NPA_DOCUMENTS, normalize_for_match
from core import dashboard_filters
from core.dashboard_finance import classify_finance_sources
from core.dashboard_periods import clean


def structural_portfolio(
    measures: pd.DataFrame,
    *,
    ssp: Iterable[Any] | None = None,
    goals: Iterable[Any] | None = None,
    tasks: Iterable[Any] | None = None,
    measure_codes: Iterable[Any] | None = None,
    product_types: Iterable[Any] | None = None,
    deputies: Iterable[Any] | None = None,
    sources: Iterable[Any] | None = None,
    financing: Iterable[Any] | None = None,
    kpkvk: Iterable[Any] | None = None,
) -> pd.DataFrame:
    """Return the structural portfolio using Dashboard's canonical filters.

    Status is deliberately absent: it is period-dependent and belongs to the
    active analytical context, while this portfolio sits above period controls.
    """
    return dashboard_filters.filter_measures(
        measures,
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


def _document_in_cell(cell_value: Any, document_name: str) -> bool:
    """Canonical deterministic containment, matching Filter-by-document semantics."""
    wanted = normalize_for_match(document_name)
    cell = normalize_for_match(clean(cell_value))
    return bool(wanted and cell and (cell == wanted or wanted in cell))


def canonical_documents(portfolio: pd.DataFrame) -> list[str]:
    """Unique canonical NPA/strategic documents actually represented in portfolio."""
    if portfolio is None or portfolio.empty:
        return []
    cells: list[str] = []
    for column in ("source_global", "source_national"):
        if column in portfolio.columns:
            cells.extend(portfolio[column].dropna().astype(str).tolist())
    found = [
        label for label in CANONICAL_NPA_DOCUMENTS
        if any(_document_in_cell(cell, label) for cell in cells)
    ]
    return sorted(dict.fromkeys(found), key=lambda value: value.casefold())


def _coded_labels(data: pd.DataFrame, code_col: str, name_col: str) -> list[str]:
    if data is None or data.empty or code_col not in data.columns:
        return []
    values: dict[str, str] = {}
    for _, row in data.iterrows():
        code = clean(row.get(code_col))
        if not code:
            continue
        name = clean(row.get(name_col))
        values.setdefault(code, f"{code} — {name}" if name else code)
    def sort_key(item: tuple[str, str]):
        import re
        nums = re.findall(r"\d+", item[0])
        return tuple(int(v) for v in nums) if nums else (9999,)
    return [label for _, label in sorted(values.items(), key=sort_key)]


def _unique_clean(values: Iterable[Any]) -> list[str]:
    result = {clean(v) for v in values if clean(v)}
    return sorted(result, key=lambda value: value.casefold())


def build_portfolio_summary(portfolio: pd.DataFrame) -> dict[str, Any]:
    """Build KPI counts and full structural lists from one already-filtered set."""
    data = portfolio.copy() if portfolio is not None else pd.DataFrame()
    if data.empty:
        return {
            "measure_count": 0, "ssp_count": 0, "goal_count": 0, "task_count": 0,
            "npa_count": 0, "deputy_count": 0,
            "ssps": [], "goals": [], "tasks": [], "deputies": [],
            "product_types": [], "documents": [], "financing": [], "kpkvk": [],
        }

    if "code" in data.columns:
        data = data.drop_duplicates(subset=["code"], keep="first").copy()

    ssps = sorted(
        {dashboard_filters.main_ssp_index(row) for _, row in data.iterrows()
         if dashboard_filters.main_ssp_index(row)},
        key=lambda value: int(value) if str(value).isdigit() else 9999,
    )
    deputies = _unique_clean(
        dashboard_filters.main_ssp_deputy(row) for _, row in data.iterrows()
    )
    goals = _coded_labels(data, "parent_goal_code", "parent_goal_name")
    tasks = _coded_labels(data, "parent_task_code", "parent_task_name")
    documents = canonical_documents(data)

    financing_values: set[str] = set()
    for _, row in data.iterrows():
        financing_values.update(clean(v) for v in classify_finance_sources(row) if clean(v))

    product_types = _unique_clean(data.get("product_type", pd.Series(dtype=object)).tolist())
    kpkvk = _unique_clean(data.get("budget_kpkvk", pd.Series(dtype=object)).tolist())

    return {
        "measure_count": int(data["code"].nunique()) if "code" in data.columns else int(len(data)),
        "ssp_count": len(ssps),
        "goal_count": len(goals),
        "task_count": len(tasks),
        "npa_count": len(documents),
        "deputy_count": len(deputies),
        "ssps": [f"ССП {value}" for value in ssps],
        "goals": goals,
        "tasks": tasks,
        "deputies": deputies,
        "product_types": product_types,
        "documents": documents,
        "financing": sorted(financing_values, key=lambda value: value.casefold()),
        "kpkvk": kpkvk,
    }


def goal_sections(portfolio: pd.DataFrame) -> list[dict[str, Any]]:
    """All strategic goals in the structural portfolio with measure counts/shares."""
    if portfolio is None or portfolio.empty:
        return []
    data = portfolio.drop_duplicates(subset=["code"], keep="first").copy()
    total = int(data["code"].nunique())
    rows: list[dict[str, Any]] = []
    for goal_code, group in data.groupby("parent_goal_code", dropna=False, sort=False):
        code = clean(goal_code)
        if not code:
            continue
        name = clean(group.get("parent_goal_name", pd.Series([""])).iloc[0])
        count = int(group["code"].nunique())
        rows.append({
            "goal_code": code,
            "goal_name": name,
            "measure_count": count,
            "portfolio_share_pct": (count / total * 100.0) if total else 0.0,
        })
    def key(row: dict[str, Any]):
        import re
        nums = re.findall(r"\d+", row["goal_code"])
        return tuple(int(v) for v in nums) if nums else (9999,)
    return sorted(rows, key=key)


def build_portfolio_navigation(portfolio: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    """Prepare drill-down navigation from the *same* deduplicated structural cohort.

    Each measure belongs to one strategic goal, task and main SSP. Documents,
    deputy and financing memberships may overlap; counts in those categories
    therefore need not add up to the number of measures in the portfolio.
    All output is plain Python data, with no Streamlit state or period logic.
    """
    empty = {
        "goals": [], "tasks": [], "ssps": [], "documents": [],
        "deputies": [], "product_types": [], "financing": [], "kpkvk": [],
    }
    if portfolio is None or portfolio.empty or "code" not in portfolio.columns:
        return empty

    data = portfolio.drop_duplicates(subset=["code"], keep="first")
    goals: dict[str, dict[str, Any]] = {}
    tasks: dict[tuple[str, str], dict[str, Any]] = {}
    ssps: dict[str, dict[str, Any]] = {}
    extras: dict[str, dict[str, dict[str, Any]]] = {
        "deputies": {}, "product_types": {}, "financing": {}, "kpkvk": {},
    }
    documents: dict[str, dict[str, Any]] = {}
    document_matches = [
        (label, normalize_for_match(label))
        for label in dict.fromkeys(CANONICAL_NPA_DOCUMENTS)
    ]

    def add_measure(
        group: dict[str, dict[str, Any]], key: str, measure: dict[str, str],
        **metadata: Any,
    ) -> None:
        if not key:
            return
        item = group.setdefault(key, {**metadata, "label": metadata.get("label", key), "measures": []})
        item["measures"].append(measure)

    for row in data.to_dict("records"):
        code = clean(row.get("code"))
        if not code:
            continue
        measure = {"code": code, "name": clean(row.get("name"))}
        goal_code = clean(row.get("parent_goal_code"))
        goal_name = clean(row.get("parent_goal_name"))
        task_code = clean(row.get("parent_task_code"))
        task_name = clean(row.get("parent_task_name"))

        if goal_code:
            goal = goals.setdefault(goal_code, {
                "code": goal_code, "name": goal_name, "measures": [], "tasks": [],
            })
            if goal_name and not goal["name"]:
                goal["name"] = goal_name
            goal["measures"].append(measure)

        if task_code:
            task_key = (goal_code, task_code)
            task = tasks.setdefault(task_key, {
                "code": task_code, "name": task_name, "goal_code": goal_code,
                "goal_name": goal_name, "measures": [],
            })
            if task_name and not task["name"]:
                task["name"] = task_name
            task["measures"].append(measure)

        ssp_code = dashboard_filters.main_ssp_index(row)
        add_measure(ssps, ssp_code, measure, code=ssp_code, label=f"ССП {ssp_code}")
        add_measure(extras["deputies"], dashboard_filters.main_ssp_deputy(row), measure)
        add_measure(extras["product_types"], clean(row.get("product_type")), measure)
        add_measure(extras["kpkvk"], clean(row.get("budget_kpkvk")), measure)
        for value in {clean(source) for source in classify_finance_sources(row)}:
            add_measure(extras["financing"], value, measure)

        # Normalize sources only once per measure, preserving the same
        # exact-or-contained matching semantics as canonical_documents().
        source_cells = [
            normalize_for_match(clean(row.get(col)))
            for col in ("source_global", "source_national")
        ]
        source_cells = [cell for cell in source_cells if cell]
        for label, wanted in document_matches:
            if wanted and any(wanted in cell for cell in source_cells):
                add_measure(documents, label, measure)

    def sort_code(value: str) -> tuple[tuple[int, ...], str]:
        import re
        nums = tuple(int(number) for number in re.findall(r"\d+", value))
        return (nums if nums else (999999,), value.casefold())

    def finish(item: dict[str, Any]) -> dict[str, Any]:
        item["measure_count"] = len(item["measures"])
        item["measures"].sort(key=lambda row: sort_code(row["code"]))
        return item

    for task in tasks.values():
        finish(task)
        if task["goal_code"] in goals:
            goals[task["goal_code"]]["tasks"].append(task)
    for goal in goals.values():
        finish(goal)
        goal["tasks"].sort(key=lambda task: sort_code(task["code"]))

    return {
        "goals": sorted(goals.values(), key=lambda item: sort_code(item["code"])),
        "tasks": sorted(tasks.values(), key=lambda item: (sort_code(item["goal_code"]), sort_code(item["code"]))),
        "ssps": [finish(ssps[key]) for key in sorted(ssps, key=sort_code)],
        "documents": [finish(documents[key]) for key in sorted(documents, key=str.casefold)],
        **{
            category: [finish(values[key]) for key in sorted(values, key=str.casefold)]
            for category, values in extras.items()
        },
    }
