"""Shared loader for the strategic matrix Excel file.

Used by new pages that need the full goal/task/measure hierarchy
without depending on app.py.
"""

from html import escape

import pandas as pd
import streamlit as st

from core.config import FILE_PATH, SHEET_NAME
from core.excel_loader import read_excel_sheet
from core.deputies import DEPUTY_MINISTER_BY_SSP


def raw_value(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value).strip()


def clean_value(value):
    return escape(raw_value(value))


def strip_leading_code(text, code):
    value = raw_value(text)
    code_value = raw_value(code)

    if code_value and value.startswith(code_value):
        value = value[len(code_value):].lstrip(" .—-–|:")

    return value


def extract_ssp_index(value):
    import re
    text = raw_value(value)
    if not text:
        return ""
    match = re.search(r"\d+", text)
    return match.group(0) if match else ""


def get_deputy_minister_by_main_ssp(value):
    index = extract_ssp_index(value)
    return DEPUTY_MINISTER_BY_SSP.get(index, "")


@st.cache_data
def load_strat_matrix():
    source_df = read_excel_sheet(FILE_PATH, SHEET_NAME)
    data = source_df.iloc[7:].copy()

    def safe_col(index):
        if index < source_df.shape[1]:
            return data.iloc[:, index]
        return pd.Series([""] * len(data), index=data.index)

    def find_col_by_keywords(keywords):
        keywords = [k.lower() for k in keywords]
        header_area = source_df.iloc[:7, :].copy()

        for col_idx in range(source_df.shape[1]):
            joined = " ".join(
                raw_value(header_area.iloc[row_idx, col_idx]).lower()
                for row_idx in range(len(header_area))
            )
            if all(keyword in joined for keyword in keywords):
                return col_idx
        return None

    def safe_keyword_col(keywords):
        col_idx = find_col_by_keywords(keywords)
        if col_idx is None:
            return pd.Series([""] * len(data), index=data.index)
        return safe_col(col_idx)

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

        "deputy_minister_raw": pd.Series([""] * len(data), index=data.index),
        "measure_period_years": safe_keyword_col(["період", "років"]),
        "measure_start_date": safe_keyword_col(["початкова", "дата"]),
        "measure_end_date": safe_keyword_col(["кінцева", "дата"]),

        "budget_kpkvk": safe_col(24),
        "budget_2026_approved": safe_col(25),
        "budget_2027_forecast": safe_col(26),
        "budget_2028_forecast": safe_col(27),
        "other_source": safe_col(28),
        "other_2026_plan": safe_col(29),
        "other_2027_forecast": safe_col(30),
        "other_2028_forecast": safe_col(31),

        "department": safe_col(17),
    })

    result = result.dropna(subset=["code"])
    result["code"] = result["code"].astype(str).str.strip()
    result["type_marker"] = result["type_marker"].astype(str).str.strip()
    result["deputy_minister_raw"] = result["resp_main"].apply(get_deputy_minister_by_main_ssp)

    current_goal_code = ""
    current_task_code = ""
    object_types = []
    parent_goal_codes = []
    parent_task_codes = []

    for _, row in result.iterrows():
        marker = raw_value(row["type_marker"]).lower()
        code = raw_value(row["code"])
        dots = code.count(".")

        if "стратегічна ціль" in marker:
            object_type = "goal"
            current_goal_code = code
            current_task_code = ""
        elif "завдання" in marker:
            object_type = "task"
            current_task_code = code
        elif "заходи" in marker or dots >= 3:
            object_type = "measure"
        else:
            object_type = "task_indicator" if current_task_code else "goal_indicator" if current_goal_code else "other"

        object_types.append(object_type)
        parent_goal_codes.append(current_goal_code)
        parent_task_codes.append(current_task_code)

    result["object_type"] = object_types
    result["parent_goal_code"] = parent_goal_codes
    result["parent_task_code"] = parent_task_codes

    return result
