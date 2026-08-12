"""Dashboard-specific financial preparation built on ``core.finance``.

The four source categories are kept distinct throughout Dashboard v2.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from core import finance as core_finance
from core.dashboard_periods import clean

SOURCE_STATE = "Державний бюджет"
SOURCE_MTD = "МТД / кошти партнерів"
SOURCE_OTHER = "Небюджетні / інші"
SOURCE_NONE = "Без фінансування"
FINANCE_SOURCE_CATEGORIES = [SOURCE_STATE, SOURCE_MTD, SOURCE_OTHER, SOURCE_NONE]

_MTD_KEYWORDS = ("мтд", "міжнарод", "партнер", "донор", "єс", "eu", "мбрр", "світов", "грант", "usaid", "undp", "giz", "kfw", "eib", "ebrd")
_OTHER_KEYWORDS = ("небюдж", "власн", "фонд", "страх", "приват", "кредит", "інш")


def classify_finance_sources(row: pd.Series | dict[str, Any]) -> list[str]:
    """Return the preserved four Dashboard source categories for one measure.

    A measure may legitimately belong to more than one financed category.
    Annual matrix amounts are considered even when a КПКВК/source label is
    blank, so filtering does not silently lose financed measures.
    """
    categories: list[str] = []

    def _has_numeric_or_text(*keys: str) -> bool:
        for key in keys:
            value = row.get(key)
            if not clean(value):
                continue
            number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
            if pd.notna(number):
                if float(number) != 0.0:
                    return True
            else:
                return True
        return False

    kpkvk = clean(row.get("budget_kpkvk", row.get("kpkvk", "")))
    has_state_plan = _has_numeric_or_text(
        "plan_bln", "_finance_plan_bln",
        "budget_2026_approved", "budget_2027_forecast", "budget_2028_forecast",
        "budget_2026", "budget_2027", "budget_2028",
    )
    if kpkvk or has_state_plan:
        categories.append(SOURCE_STATE)

    other_raw = clean(row.get("other_source", row.get("_finance_other_source", "")))
    has_other_plan = _has_numeric_or_text(
        "other_2026_plan", "other_2027_forecast", "other_2028_forecast",
        "other_2026", "other_2027", "other_2028",
    )
    other = other_raw.casefold()
    if other or has_other_plan:
        if other and any(key in other for key in _MTD_KEYWORDS):
            categories.append(SOURCE_MTD)
        else:
            # Unlabelled or unknown non-budget money is kept separate from MTD.
            categories.append(SOURCE_OTHER)
    if not categories:
        categories.append(SOURCE_NONE)
    return list(dict.fromkeys(categories))


def build_finance_frame(snapshot: pd.DataFrame, year: int, fin_index: dict | None = None) -> pd.DataFrame:
    if snapshot is None or snapshot.empty:
        return pd.DataFrame(columns=["code", "plan_bln", "fact_bln", "financial_execution_pct", "finance_categories"])
    fin_index = core_finance.load_financing_data() if fin_index is None else fin_index
    rows = []
    for _, measure in snapshot.drop_duplicates(subset=["code"]).iterrows():
        code = clean(measure.get("code"))
        record = fin_index.get((code, str(int(year)))) or fin_index.get((code, "")) or {}
        # Strategic-matrix annual plan stays authoritative where present.
        matrix_plan = measure.get(f"budget_{int(year)}", measure.get(f"budget_{int(year)}_approved"))
        matrix_plan_num = core_finance.parse_number(matrix_plan) if hasattr(core_finance, "parse_number") else None
        plan = matrix_plan_num if matrix_plan_num is not None else record.get("plan_bln")
        fact = record.get("fact_bln")
        kpkvk = clean(measure.get("budget_kpkvk")) or clean(record.get("kpkvk"))
        other_source = clean(measure.get("other_source")) or clean(record.get("other_source"))
        financial_pct = core_finance.financial_execution_percent(plan, fact)
        item = {
            "code": code, "name": clean(measure.get("name")),
            "goal_code": clean(measure.get("parent_goal_code", measure.get("goal_code"))),
            "strategic_goal": clean(measure.get("parent_goal_name", measure.get("strategic_goal"))),
            "department": clean(measure.get("resp_main", measure.get("department"))),
            "status": clean(measure.get("status")), "kpkvk": kpkvk,
            "budget_kpkvk": kpkvk, "other_source": other_source,
            "plan_bln": plan, "fact_bln": fact,
            "financial_execution_pct": financial_pct,
            "execution_score": measure.get("execution_score"),
            "elasticity": core_finance.financial_elasticity(financial_pct, measure.get("execution_score")),
        }
        item["finance_categories"] = classify_finance_sources(item)
        rows.append(item)
    return pd.DataFrame(rows)


def finance_kpis(frame: pd.DataFrame) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {"plan_bln": None, "fact_bln": None, "financial_execution_pct": None, "measure_count": 0,
                "source_counts": {category: 0 for category in FINANCE_SOURCE_CATEGORIES}}
    plans = pd.to_numeric(frame["plan_bln"], errors="coerce")
    facts = pd.to_numeric(frame["fact_bln"], errors="coerce")
    total_plan = float(plans.sum(min_count=1)) if plans.notna().any() else None
    total_fact = float(facts.sum(min_count=1)) if facts.notna().any() else None
    source_counts = {category: 0 for category in FINANCE_SOURCE_CATEGORIES}
    for categories in frame.get("finance_categories", pd.Series(index=frame.index, dtype=object)):
        for category in categories if isinstance(categories, list) else []:
            if category in source_counts:
                source_counts[category] += 1
    return {
        "plan_bln": total_plan, "fact_bln": total_fact,
        "financial_execution_pct": core_finance.financial_execution_percent(total_plan, total_fact),
        "measure_count": int(frame["code"].nunique() if "code" in frame else len(frame)),
        "source_counts": source_counts,
    }
