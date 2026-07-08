"""ЄДИНЕ джерело читання стратегічної матриці (правка К1).

Раніше майже кожна сторінка мала власну копію load_strat_matrix з трохи
різними назвами колонок. Тепер Excel читається РІВНО В ОДНОМУ місці, а
DataFrame містить СУПЕРНАБІР колонок з усіма історичними назвами-синонімами
(та сама фізична колонка доступна під кількома іменами), тому внутрішній
код сторінок працює без змін.

Фізична колонка → імена в DataFrame:
  B(1)  type_marker
  C(2)  code
  D(3)  name
  E(4)  product_type
  F(5)  indicator
  G(6)  unit
  H(7)  base_2021
  I(8)  fact_2024
  J(9)  fact_2025 = expected_2025
  K..M(10..12) target_2026 / 2027 / 2028
  N(13) strategic_target_2028 = target_2028_end
  O(14) strategic_target_2034 = target_2034
  P(15) source_global
  Q(16) source_national
  R(17) resp_main = department
  S(18) resp_co_1 = department_co_1 = co_executor
  T(19) resp_co_2 = department_co_2
  U(20) deputy_minister (та deputy_minister_raw — за головним ССП)
  V(21) measure_period_years            (пошук за ключовими словами)
  W(22) measure_start_date = start_period = start_date_plan
  X(23) measure_end_date   = end_period  = end_date_plan
  Y(24) budget_kpkvk = kpkvk = finance_y
  Z(25) budget_2026_approved = budget_2026 = fin_plan_2026 = finance_z
  AA(26) budget_2027_forecast = budget_2027 = fin_plan_2027 = finance_aa
  AB(27) budget_2028_forecast = budget_2028 = fin_plan_2028 = finance_ab
  AC(28) other_source = fin_other_source = finance_ac
  AD(29) other_2026_plan = other_2026 = finance_ad
  AE(30) other_2027_forecast = other_2027 = finance_ae
  AF(31) other_2028_forecast = other_2028 = finance_af

Плюс ієрархія: object_type, parent_goal_code/name, parent_task_code/name.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.config import FILE_PATH, SHEET_NAME
from core.excel_loader import read_excel_sheet
from core.deputies import DEPUTY_MINISTER_BY_SSP
from core.text_utils import (  # noqa: F401 — реекспорт для сумісності
    raw_value,
    clean_value,
    strip_leading_code,
    extract_ssp_index,
)


def get_deputy_minister_by_main_ssp(value):
    index = extract_ssp_index(value)
    return DEPUTY_MINISTER_BY_SSP.get(index, "")


# Синоніми: канонічна колонка → додаткові імена тієї самої колонки
_ALIASES = {
    "fact_2025": ["expected_2025"],
    "strategic_target_2028": ["target_2028_end"],
    "strategic_target_2034": ["target_2034"],
    "resp_main": ["department"],
    "resp_co_1": ["department_co_1", "co_executor"],
    "resp_co_2": ["department_co_2"],
    "measure_start_date": ["start_period", "start_date_plan"],
    "measure_end_date": ["end_period", "end_date_plan"],
    "budget_kpkvk": ["kpkvk", "finance_y", "kpkvk_code_raw"],
    "budget_2026_approved": ["budget_2026", "fin_plan_2026", "finance_z"],
    "budget_2027_forecast": ["budget_2027", "fin_plan_2027", "finance_aa"],
    "budget_2028_forecast": ["budget_2028", "fin_plan_2028", "finance_ab"],
    "other_source": ["fin_other_source", "finance_ac"],
    "other_2026_plan": ["other_2026", "finance_ad"],
    "other_2027_forecast": ["other_2027", "finance_ae"],
    "other_2028_forecast": ["other_2028", "finance_af"],
}


@st.cache_data(ttl=300)
def load_strat_matrix():
    source_df = read_excel_sheet(FILE_PATH, SHEET_NAME)
    data = source_df.iloc[7:].copy()

    def safe_col(index):
        if index < source_df.shape[1]:
            return data.iloc[:, index]
        return pd.Series([""] * len(data), index=data.index)

    def find_col_by_keywords(keywords, forbidden=None, header_rows=12):
        keywords = [k.lower() for k in keywords]
        forbidden = [f.lower() for f in (forbidden or [])]
        max_rows = min(header_rows, source_df.shape[0])
        for col_idx in range(source_df.shape[1]):
            joined = " ".join(
                raw_value(source_df.iloc[row_idx, col_idx]).lower()
                for row_idx in range(max_rows)
            )
            if all(k in joined for k in keywords) and not any(f in joined for f in forbidden):
                return col_idx
        return None

    def safe_keyword_col(keywords, fallback_idx=None, forbidden=None):
        col_idx = find_col_by_keywords(keywords, forbidden=forbidden)
        if col_idx is not None:
            return safe_col(col_idx)
        if fallback_idx is not None:
            return safe_col(fallback_idx)
        return pd.Series([""] * len(data), index=data.index)

    result = pd.DataFrame({
        "type_marker": safe_col(1),
        "code": safe_col(2),
        "name": safe_col(3),
        "product_type": safe_col(4),

        "indicator": safe_col(5),
        "unit": safe_col(6),
        "base_2021": safe_col(7),
        "fact_2024": safe_col(8),
        "fact_2025": safe_col(9),
        "target_2026": safe_col(10),
        "target_2027": safe_col(11),
        "target_2028": safe_col(12),

        "strategic_target_2028": safe_col(13),
        "strategic_target_2034": safe_col(14),
        "source_global": safe_col(15),
        "source_national": safe_col(16),

        "resp_main": safe_col(17),
        "resp_co_1": safe_col(18),
        "resp_co_2": safe_col(19),

        "deputy_minister": safe_keyword_col(["заступник", "міністра"], 20),
        "measure_period_years": safe_keyword_col(["період", "років"], 21),
        "measure_start_date": safe_keyword_col(["початк", "виконання"], 22,
                                               forbidden=["кінц"]),
        "measure_end_date": safe_keyword_col(["кінц", "виконання"], 23,
                                             forbidden=["початк"]),

        "budget_kpkvk": safe_col(24),
        "budget_2026_approved": safe_col(25),
        "budget_2027_forecast": safe_col(26),
        "budget_2028_forecast": safe_col(27),
        "other_source": safe_col(28),
        "other_2026_plan": safe_col(29),
        "other_2027_forecast": safe_col(30),
        "other_2028_forecast": safe_col(31),
    })

    result = result.dropna(subset=["code"])
    result["code"] = result["code"].astype(str).str.strip()
    result["type_marker"] = result["type_marker"].astype(str).str.strip()
    result["deputy_minister_raw"] = result["resp_main"].apply(get_deputy_minister_by_main_ssp)

    # ── Ієрархія: тип обʼєкта + батьківські ціль/завдання (з назвами) ──
    cur_goal_code, cur_goal_name = "", ""
    cur_task_code, cur_task_name = "", ""
    obj_types, pg_codes, pg_names, pt_codes, pt_names = [], [], [], [], []

    for _, row in result.iterrows():
        marker = raw_value(row["type_marker"]).lower()
        code = raw_value(row["code"])
        name = raw_value(row["name"])
        dots = code.count(".")

        if "стратегічна ціль" in marker:
            obj_type = "goal"
            cur_goal_code, cur_goal_name = code, name
            cur_task_code, cur_task_name = "", ""
        elif "завдання" in marker:
            obj_type = "task"
            cur_task_code, cur_task_name = code, name
        elif "заход" in marker or dots >= 3:
            obj_type = "measure"
        elif cur_task_code:
            obj_type = "task_indicator"
        elif cur_goal_code:
            obj_type = "goal_indicator"
        else:
            obj_type = "other"

        obj_types.append(obj_type)
        pg_codes.append(cur_goal_code)
        pg_names.append(cur_goal_name)
        pt_codes.append(cur_task_code)
        pt_names.append(cur_task_name)

    result["object_type"] = obj_types
    result["parent_goal_code"] = pg_codes
    result["parent_goal_name"] = pg_names
    result["parent_task_code"] = pt_codes
    result["parent_task_name"] = pt_names

    # ── Синоніми (та сама фізична колонка під історичними іменами) ──
    for canonical, aliases in _ALIASES.items():
        for alias in aliases:
            result[alias] = result[canonical]

    return result


def measure_name_by_code(strat_df) -> dict:
    """{код заходу → поточна назва} — для звірки знімків назв у поданнях."""
    result = {}
    if strat_df is None or strat_df.empty:
        return result
    measures = strat_df[strat_df["object_type"] == "measure"]
    for _, m in measures.iterrows():
        code = raw_value(m.get("code"))
        if code and code not in result:
            result[code] = raw_value(m.get("name"))
    return result
