import re
from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st
from core.db import get_supabase_client
from core.config import ANNOUNCEMENT
from core.page_setup import page_setup, render_footer
from core.text_utils import (
    raw_value, clean_value, strip_leading_code,
)
from core import statuses as core_statuses
from core.period_locks import all_periods_locked, is_period_locked
from core.timeutils import now_kyiv
from core import monitoring_data
from core import exports as core_exports
from core.strategic_data import load_strat_matrix as core_load_strat_matrix
from core.access import (
    is_scope_lockable_user,
    is_scope_override_active,
    get_user_ssp_index,
)
from core.ui import render_scope_toggle
from config.roles import ROLE_SSP, ROLE_SSP_HEAD, ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY

current_user = page_setup("Стратегічний план", page_name="app")
supabase = get_supabase_client()
# ------------------------------------------------------------
# CSS
# ------------------------------------------------------------

st.markdown(
    """
<style>
header[data-testid="stHeader"] {
    background: transparent !important;
}
.stApp {
    background: #F7F9FC;
}
.main .block-container {
    max-width: 1550px;
    padding-top: 1.2rem;
    position: relative;
    z-index: 1;
}

.ua-line {
    height: 7px;
    border-radius: 999px;
    background: linear-gradient(90deg, #005BBB 0%, #005BBB 50%, #FFD500 50%, #FFD500 100%);
    margin-bottom: 14px;
}

.ministry-label {
    text-align: right;
    color: #61708A;
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 8px;
}

.header-box,
.flow-box,
.summary-box,
.info-card,
.note-box,
.search-result-box {
    background: rgba(255,255,255,0.94);
    border: 1px solid #DCE4F0;
    box-shadow: 0 6px 18px rgba(15,23,42,0.045);
}

.header-box {
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 18px;
    backdrop-filter: blur(8px);
}

.header-title {
    font-size: 32px;
    font-weight: 900;
    color: #132238;
    margin-bottom: 8px;
}

.header-subtitle {
    font-size: 15px;
    color: #61708A;
    line-height: 1.55;
}


.cta-box {
    background: #118847;
    color: white;
    border-radius: 16px;
    padding: 22px 26px;
    margin: 7px 0 18px 0;
    box-shadow: 0 10px 24px rgba(22,163,74,0.25);
}

.cta-title {
    font-size: 23px;
    font-weight: 900;
}

.flow-box {
    border-radius: 16px;
    padding: 18px 20px;
    margin: 18px 0;
}

.flow-title,
.summary-title,
.filter-title,
.guide-title,
.info-card-title,
.search-result-title {
    color: #132238;
    font-weight: 900;
}

.flow-title {
    font-size: 17px;
    margin-bottom: 12px;
}

.flow-steps {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 10px;
}

.flow-step {
    min-height: 58px;
    padding: 10px 12px;
    border-radius: 14px;
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    color: #61708A;
    font-size: 13px;
    font-weight: 800;
    line-height: 1.25;
}

.summary-box,
.search-result-box {
    border-radius: 16px;
    padding: 18px 20px;
    margin: 18px 0;
}

.summary-title,
.search-result-title,
.filter-title {
    font-size: 20px;
    margin-bottom: 12px;
}

.summary-grid {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 12px;
    align-items: stretch;
}

.summary-grid-7 {
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    gap: 12px;
    align-items: stretch;
}

.summary-card {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-radius: 13px;
    padding: 14px 15px;
    min-height: 96px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.summary-label {
    color: #61708A;
    font-size: 12px;
    font-weight: 800;
    line-height: 1.35;
    min-height: 34px;
    margin-bottom: 8px;
}

.summary-value {
    color: #132238;
    font-size: 24px;
    line-height: 1;
    font-weight: 950;
}

.guide-title {
    font-size: 20px;
    margin: 18px 0 10px 0;
}

.info-grid {
    display: grid;
    grid-template-columns: 0.85fr 1.15fr;
    gap: 14px;
    margin-bottom: 20px;
}

.info-card {
    border-radius: 14px;
    padding: 17px 19px;
    color: #032A63;
    line-height: 1.55;
}

.info-card-title {
    font-size: 16px;
    margin-bottom: 8px;
}

.legend-item {
    margin-bottom: 7px;
    font-size: 14px;
}


.filter-title {
    font-size: 22px;
    margin-bottom: 18px;
}

.filter-subtitle {
    color: #132238;
    font-size: 15px;
    font-weight: 950;
    margin: 18px 0 10px 0;
    padding-bottom: 4px;
    border-bottom: 1px solid rgba(148,163,184,0.35);
}


div[data-testid="stExpander"] {
    border: none;
    margin-bottom: 14px;
}

div[data-testid="stExpander"] > details > summary {
    background: #005BBB !important;
    color: white !important;
    border-radius: 13px !important;
    padding: 18px 22px !important;
    font-weight: 850 !important;
    box-shadow: 0 7px 18px rgba(29,78,216,0.20);
}

div[data-testid="stExpander"] > details > summary p {
    color: white !important;
    font-size: 16px !important;
    font-weight: 850 !important;
}

div[data-testid="stExpander"] div[data-testid="stExpander"] > details > summary {
    background: #032A63 !important;
    color: white !important;
    border-radius: 11px !important;
    padding: 15px 18px !important;
    font-weight: 800 !important;
    box-shadow: none;
}

div[data-testid="stExpander"] div[data-testid="stExpander"] > details > summary p {
    color: white !important;
    font-size: 15px !important;
    font-weight: 800 !important;
}

/* Компактний expander додаткових параметрів: візуально як на Dashboard. */
.st-key-main_additional_parameters div[data-testid="stExpander"] {
    border: 1px solid #DCE4F0 !important;
    border-radius: 10px !important;
    margin: 8px 0 14px 0 !important;
    background: #FFFFFF !important;
    overflow: hidden;
}

.st-key-main_additional_parameters div[data-testid="stExpander"] > details > summary {
    background: #F7F9FC !important;
    color: #132238 !important;
    border-radius: 9px !important;
    padding: 9px 12px !important;
    min-height: 38px !important;
    font-weight: 700 !important;
    box-shadow: none !important;
}

.st-key-main_additional_parameters div[data-testid="stExpander"] > details > summary:hover {
    background: #EEF3F9 !important;
}

.st-key-main_additional_parameters div[data-testid="stExpander"] > details > summary p {
    color: #132238 !important;
    font-size: 14px !important;
    font-weight: 700 !important;
}

.st-key-main_additional_parameters div[data-testid="stExpander"] > details > summary svg {
    color: #61708A !important;
    fill: #61708A !important;
}

.main-filter-subtitle {
    margin-top: 0 !important;
}


.section-title {
    font-size: 16px;
    font-weight: 850;
    color: #132238;
    margin: 18px 0 12px 0;
}

.note-box {
    border-radius: 10px;
    padding: 13px 17px;
    color: #032A63;
    margin: 12px 0 18px 0;
    font-size: 14px;
    line-height: 1.55;
}

.table-scroll {
    overflow: auto;
    width: 100%;
    border: 1px solid #DCE4F0;
    border-radius: 10px;
    margin-bottom: 18px;
    background: white;
}

.table-scroll.measures-scroll {
    max-height: 325px;
}

.th-sub {
    display: block;
    color: #61708A;
    font-size: 11px;
    font-weight: 600;
    margin-top: 2px;
}

.th-note-scroll {
    max-height: 60px;
    overflow-y: auto;
    font-size: 10px;
    line-height: 1.3;
    color: #61708A;
    font-weight: 500;
    margin-top: 2px;
    text-align: left;
}

table.custom-table {
    border-collapse: collapse;
    table-layout: fixed;
    font-size: 13px;
}

table.custom-table th {
    background-color: #EAF1FF;
    color: #132238;
    padding: 9px 10px;
    border: 1px solid #DCE4F0;
    text-align: center;
    vertical-align: middle;
    white-space: normal;
    font-weight: 850;
    line-height: 1.22;
}

table.custom-table thead th {
    position: sticky;
    top: 0;
    z-index: 3;
}

table.custom-table thead tr:nth-child(2) th {
    top: 38px;
    z-index: 4;
}

table.custom-table thead tr:nth-child(3) th {
    top: 76px;
    z-index: 5;
}

table.custom-table td {
    padding: 8px 10px;
    border: 1px solid #DCE4F0;
    vertical-align: middle;
    text-align: center;
    white-space: normal;
    word-wrap: break-word;
    overflow-wrap: break-word;
    line-height: 1.32;
}

/* Числові й текстові значення показників у річних колонках.
   Правило застосовується лише до звичайного вмісту make_cell();
   кольорові статусні бейджі мають власні inline-кольори й не зачіпаються. */
table.custom-table td.col-year:not(.status-review):not(.status-approved):not(.status-returned):not(.status-empty):not(.status-notyet):not(.status-manual-closeout):not(.risk-cell) > .cell-nowrap,
table.custom-table td.col-year:not(.status-review):not(.status-approved):not(.status-returned):not(.status-empty):not(.status-notyet):not(.status-manual-closeout):not(.risk-cell) > .cell-fixed {
    color: #132238;
    font-weight: 850;
}

table.custom-table tr:nth-child(even) {
    background-color: #F7F9FC;
}

table.custom-table tr:nth-child(odd) {
    background-color: #ffffff;
}

.cell-fixed {
    display: block;
    max-height: 74px;
    overflow: hidden;
}

.cell-fixed:hover {
    overflow: auto;
}

.cell-nowrap {
    display: block;
    max-height: 42px;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
}

td.status-review {
    background-color: transparent !important;
    color: #032A63;
    font-weight: 850;
}

td.status-approved {
    background-color: transparent !important;
    color: #0C713A;
    font-weight: 850;
}

td.status-returned {
    background-color: transparent !important;
    color: #8A6400;
    font-weight: 850;
}

td.status-empty {
    background-color: transparent !important;
    color: #DC4A4A;
    font-weight: 850;
}

td.status-notyet {
    background-color: transparent !important;
    border-color: #DCE4F0 !important;
    color: #61708A;
    font-weight: 850;
}


/* Значення періоду, закритого адміністратором вручну: фіолетовий стандарт збережено */
td.status-manual-closeout {
    background-color: transparent !important;
    color: #5b21b6;
    font-weight: 850;
}
td.status-manual-closeout .cell-nowrap,
td.status-manual-closeout .cell-fixed {
    display: inline-block;
    background-color: #ede9fe;
    color: #5b21b6;
    border-radius: 5px;
    padding: 1px 5px;
}

td.risk-cell {
    background-color: #FBE5E5 !important;
    color: #DC4A4A;
    font-weight: 850;
}

.col-code { width: 90px; }
.col-measure { width: 360px; }
.col-product { width: 170px; }
.col-indicator { width: 430px; }
.col-unit { width: 180px; }
.col-year { width: 130px; }
.col-long { width: 300px; }
.col-resp { width: 210px; }
.col-status { width: 160px; }
.col-budget { width: 145px; }
.col-budget-source { width: 260px; }

.footer {
    text-align: center;
    color: #61708A;
    font-size: 13px;
    margin-top: 50px;
    padding: 22px 0 12px 0;
    border-top: 1px solid #DCE4F0;
}

.footer strong {
    color: #61708A;
}


@media (max-width: 1100px) {
    .summary-grid,
    .summary-grid-7,
    .flow-steps {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .info-grid {
        grid-template-columns: 1fr;
    }

}
</style>
""",
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# Basic helpers
# ------------------------------------------------------------

def normalize_text(value):
    return raw_value(value).lower().replace(" ", "")


def is_empty_or_nd(value):
    return normalize_text(value) in {"", "н.д.", "нд", "nan", "none", "-", "—"}


def split_ssp_values(value):
    """
    Дає список усіх індексів ССП із комірки, якщо там кілька значень.
    """
    text = raw_value(value)
    if not text:
        return []

    return re.findall(r"\d+", text)



def value_contains_ssp(value, selected_indices):
    if not selected_indices:
        return True

    found = set(split_ssp_values(value))
    return bool(found.intersection(set(selected_indices)))


def make_summary_card(label, value):
    return (
        f'<div class="summary-card">'
        f'<div class="summary-label">{escape(str(label))}</div>'
        f'<div class="summary-value">{escape(str(value))}</div>'
        f'</div>'
    )


def format_indicator_value(value, field_name=""):
    if value is None or pd.isna(value):
        return ""

    if isinstance(value, (pd.Timestamp, datetime)):
        if field_name in {"strategic_target_2028", "strategic_target_2034"}:
            return f"{value.day}-{value.month}"
        return value.strftime("%d.%m.%Y")

    text = raw_value(value)

    if "00:00:00" in text and field_name in {"strategic_target_2028", "strategic_target_2034"}:
        parsed = pd.to_datetime(text, errors="coerce")
        if pd.notna(parsed):
            return f"{parsed.day}-{parsed.month}"

    return text

def make_cell(value, mode="fixed"):
    title = clean_value(value)

    if mode == "nowrap":
        return f'<span class="cell-nowrap" title="{title}">{title}</span>'

    return f'<span class="cell-fixed" title="{title}">{title}</span>'

# ------------------------------------------------------------
# Data loading
# ------------------------------------------------------------

def load_strat_matrix():
    """ЄДИНЕ джерело — core.strategic_data (правка К1)."""
    return core_load_strat_matrix()


def load_monitoring():
    """ЄДИНЕ джерело — core.monitoring_data (правки К2, П2)."""
    return monitoring_data.load_monitoring_requests()



from core.closeouts import load_manual_closeouts, append_confirmed_closeout_facts


# ------------------------------------------------------------
# Monitoring status logic — єдина реалізація в core.statuses
# ------------------------------------------------------------

get_measure_records = core_statuses.get_measure_records
get_record_visual_status = core_statuses.get_record_visual_status
get_measure_status = core_statuses.get_measure_status
visual_status_class = core_statuses.visual_status_class


def has_monitoring_submission(monitoring_df, code, selected_years, selected_quarters):
    return not get_measure_records(monitoring_df, code, selected_years, selected_quarters).empty


def has_approved_monitoring(monitoring_df, code, selected_years, selected_quarters):
    return get_measure_status(monitoring_df, code, selected_years, selected_quarters) == "Погоджено"


def has_waiting_monitoring(monitoring_df, code, selected_years, selected_quarters):
    return get_measure_status(monitoring_df, code, selected_years, selected_quarters) == "На розгляді"


def has_returned_monitoring(monitoring_df, code, selected_years, selected_quarters):
    return get_measure_status(monitoring_df, code, selected_years, selected_quarters) == "На доопрацюванні"


def has_not_counted_monitoring(monitoring_df, code, selected_years, selected_quarters):
    return get_measure_status(monitoring_df, code, selected_years, selected_quarters) == "Не враховано"


def get_measure_execution_status(monitoring_df, code, selected_years, selected_quarters):
    """Latest approved execution status, kept separate from approval workflow status."""
    records = get_measure_records(monitoring_df, code, selected_years, selected_quarters)
    if records.empty or "status" not in records.columns:
        return ""
    if "approval_status" in records.columns:
        records = records[records["approval_status"].astype(str).str.strip() == "Погоджено"].copy()
    if records.empty:
        return ""
    sort_cols = [c for c in ["updated_at", "submitted_at", "id"] if c in records.columns]
    if sort_cols:
        records = records.sort_values(sort_cols, ascending=[False] * len(sort_cols), na_position="last")
    return raw_value(records.iloc[0].get("status", ""))


def measure_has_real_risk(monitoring_df, code, selected_years, selected_quarters):
    records = get_measure_records(monitoring_df, code, selected_years, selected_quarters)
    if records.empty or "risks" not in records.columns:
        return False
    empty_markers = {"", "—", "-", "немає", "відсутні", "відсутній", "не виявлено"}
    return any(raw_value(value).strip().casefold() not in empty_markers for value in records["risks"].tolist())



def measure_matches_status_mode(monitoring_df, code, selected_years, selected_quarters, mode):
    status = get_measure_status(monitoring_df, code, selected_years, selected_quarters)
    if mode == "Усі заходи стратегічного плану":
        return True
    if mode == "Лише погоджені":
        return status == "Погоджено"
    if mode == "Лише на розгляді":
        return status == "На розгляді"
    if mode == "Лише не враховані":
        return status == "Не враховано"
    return True

# ------------------------------------------------------------
# Strategic plan filtering
# ------------------------------------------------------------

def extract_year_from_text(value):
    text = raw_value(value)
    match = re.search(r"(20\d{2})", text)
    return int(match.group(1)) if match else None


def is_active_in_any_selected_year(row, selected_years):
    if not selected_years:
        return True

    selected_years = [int(y) for y in selected_years]

    start_year = extract_year_from_text(row.get("measure_start_date", ""))
    end_year = extract_year_from_text(row.get("measure_end_date", ""))

    if start_year and end_year:
        return any(start_year <= year <= end_year for year in selected_years)

    if start_year and not end_year:
        return any(year >= start_year for year in selected_years)

    if end_year and not start_year:
        return any(year <= end_year for year in selected_years)

    # fallback, якщо дати не заповнені: дивимось на річні цільові колонки
    for year in selected_years:
        col = f"target_{year}"
        if col in row and not is_empty_or_nd(row.get(col, "")):
            return True

    return False



def row_contains_selected_ssp(row, selected_ssp_indices):
    if not selected_ssp_indices:
        return True

    values = [
        row.get("resp_main", ""),
        row.get("resp_co_1", ""),
        row.get("resp_co_2", ""),
        row.get("department", "")
    ]

    return any(value_contains_ssp(value, selected_ssp_indices) for value in values)


def row_matches_search(row, search_query):
    query = raw_value(search_query).lower()

    if not query:
        return True

    values = [
        row.get("code", ""),
        row.get("name", ""),
        row.get("indicator", ""),
        row.get("product_type", ""),
        row.get("resp_main", ""),
        row.get("resp_co_1", ""),
        row.get("resp_co_2", "")
    ]

    return any(query in raw_value(value).lower() for value in values)

def indicator_row_matches_search(row, search_query):
    query = raw_value(search_query).lower()

    if not query:
        return True

    values = [
        row.get("code", ""),
        row.get("name", ""),
        row.get("indicator", ""),
        row.get("unit", ""),
        row.get("base_2021", ""),
        row.get("fact_2024", ""),
        row.get("fact_2025", ""),
        row.get("strategic_target_2028", ""),
        row.get("strategic_target_2034", ""),
        row.get("source_global", ""),
        row.get("source_national", ""),
        row.get("resp_main", ""),
        row.get("resp_co_1", ""),
        row.get("resp_co_2", "")
    ]

    return any(query in raw_value(value).lower() for value in values)

def row_matches_product_type(row, selected_product_types):
    if not selected_product_types:
        return True

    return raw_value(row.get("product_type", "")) in selected_product_types


def row_matches_deputy(row, selected_deputies):
    if not selected_deputies:
        return True

    deputy_value = raw_value(row.get("deputy_minister_raw", ""))

    if not deputy_value:
        return False

    return deputy_value in selected_deputies


def apply_measure_filters(
    measures,
    monitoring_df,
    selected_ssp_indices,
    selected_years,
    selected_quarters,
    status_mode,
    selected_goal_codes,
    selected_product_types,
    selected_deputies,
    search_query
):
    filtered = measures.copy()

    if selected_goal_codes:
        filtered = filtered[filtered["parent_goal_code"].astype(str).str.strip().isin(selected_goal_codes)]

    filtered["matches_ssp"] = filtered.apply(lambda row: row_contains_selected_ssp(row, selected_ssp_indices), axis=1)
    filtered["matches_product_type"] = filtered.apply(lambda row: row_matches_product_type(row, selected_product_types), axis=1)
    filtered["matches_deputy"] = filtered.apply(lambda row: row_matches_deputy(row, selected_deputies), axis=1)
    filtered["matches_search"] = filtered.apply(lambda row: row_matches_search(row, search_query), axis=1)
    filtered["active_in_selected_years"] = filtered.apply(lambda row: is_active_in_any_selected_year(row, selected_years), axis=1)

    filtered["monitoring_status"] = filtered["code"].apply(
        lambda code: get_measure_status(monitoring_df, code, selected_years, selected_quarters)
    )

    filtered["has_submission"] = filtered["code"].apply(
        lambda code: has_monitoring_submission(monitoring_df, code, selected_years, selected_quarters)
    )

    filtered["has_approved"] = filtered["code"].apply(
        lambda code: has_approved_monitoring(monitoring_df, code, selected_years, selected_quarters)
    )

    filtered["has_waiting"] = filtered["code"].apply(
        lambda code: has_waiting_monitoring(monitoring_df, code, selected_years, selected_quarters)
    )

    filtered["has_returned"] = filtered["code"].apply(
        lambda code: has_returned_monitoring(monitoring_df, code, selected_years, selected_quarters)
    )

    filtered["has_not_counted"] = filtered["code"].apply(
        lambda code: has_not_counted_monitoring(monitoring_df, code, selected_years, selected_quarters)
    )

    filtered["execution_status"] = filtered["code"].apply(
        lambda code: get_measure_execution_status(monitoring_df, code, selected_years, selected_quarters)
    )

    filtered["has_risks"] = filtered["code"].apply(
        lambda code: measure_has_real_risk(monitoring_df, code, selected_years, selected_quarters)
    )

    filtered["matches_status_mode"] = filtered["code"].apply(
        lambda code: measure_matches_status_mode(
            monitoring_df,
            code,
            selected_years,
            selected_quarters,
            status_mode
        )
    )

    filtered = filtered[
        filtered["matches_ssp"]
        & filtered["matches_product_type"]
        & filtered["matches_deputy"]
        & filtered["matches_search"]
        & filtered["active_in_selected_years"]
        & filtered["matches_status_mode"]
    ]

    return filtered.copy()


def unique_measure_count(data, condition=None):
    if data.empty:
        return 0

    tmp = data.copy()

    if condition is not None:
        tmp = tmp[condition(tmp)]

    return len(set(tmp["strat_code"].dropna().astype(str).str.strip()))


def count_filtered_status(filtered_measures, status_name):
    if filtered_measures.empty or "monitoring_status" not in filtered_measures.columns:
        return 0

    return len(filtered_measures[filtered_measures["monitoring_status"] == status_name])


def calculate_completion(filtered_measures, years=None, quarters=None):
    if filtered_measures.empty:
        return 0, 0
    if years is not None and quarters is not None and all_periods_locked(years, quarters):
        return 0, 0

    done_count = len(filtered_measures[filtered_measures.get("execution_status", pd.Series(index=filtered_measures.index, dtype=str)) == "Виконано"])
    total_count = len(filtered_measures)

    percent = round((done_count / total_count) * 100, 2) if total_count else 0

    return done_count, percent


# ------------------------------------------------------------
# Quarter values
# ------------------------------------------------------------

@st.cache_data(ttl=300)
def build_quarter_data(monitoring_df):
    quarter_data = {}

    if monitoring_df.empty:
        return quarter_data

    visible_monitoring = monitoring_df.copy()

    if "submitted_at" in visible_monitoring.columns:
        visible_monitoring = visible_monitoring.sort_values("submitted_at")

    for _, row in visible_monitoring.iterrows():
        code = raw_value(row.get("strat_code", ""))
        year = raw_value(row.get("year", ""))
        quarter = raw_value(row.get("quarter", ""))

        if not code or not year or not quarter:
            continue

        key = f"{year}_{quarter}"
        visual_status = get_record_visual_status(row)

        quarter_data.setdefault(code, {})[key] = {
            "value": row.get("numeric_value", ""),
            "visual_status": visual_status,
            "class": visual_status_class(visual_status)
        }

    return quarter_data


def get_quarter_columns(selected_years, selected_quarters):
    columns = []

    quarter_map = {
        "I": "Q1",
        "II": "Q2",
        "III": "Q3",
        "IV": "Q4"
    }

    for year in selected_years:
        for quarter in selected_quarters:
            q = str(quarter).replace(" квартал", "").strip()
            q_label = quarter_map.get(q, q)
            columns.append((year, q, f"{q_label} {year}"))

    return columns




# ------------------------------------------------------------
# HTML table rendering
# ------------------------------------------------------------

def clean_html(html: str) -> str:
    return "\n".join(
        line.strip()
        for line in html.splitlines()
        if line.strip()
    )


def latest_indicator_submission(code, indicator_name, fact_year):
    """Останнє подання конкретного індикатора за ключем код + назва у вибраному році."""
    if indicator_monitoring_df.empty:
        return ""
    code_key, name_key = monitoring_data.indicator_identity_key(code, indicator_name)
    data = indicator_monitoring_df.copy()
    data = data[data["strat_code"].astype(str).str.strip() == code_key]
    if "year" in data.columns:
        data = data[data["year"].astype(str).str.strip() == str(fact_year).strip()]
    if name_key and not data.empty:
        data = data[
            data["indicator_name"].apply(
                lambda value: monitoring_data.indicator_identity_key(code_key, value)[1] == name_key
            )
        ]
    if data.empty:
        return ""
    data["_submitted_at"] = pd.to_datetime(data.get("submitted_at"), errors="coerce")
    data = data.sort_values(["_submitted_at", "id"], ascending=[False, False])
    row = data.iloc[0]
    value = raw_value(row.get("numeric_value", "")) or raw_value(row.get("value_text", "")) or "—"
    return core_statuses.legend_badge(
        core_statuses.get_record_visual_status(row),
        display_value=value,
    )


def build_indicator_rows(parent_row, child_rows, selected_ssp_indices=None, search_query="", fact_year=None):
    selected_ssp_indices = selected_ssp_indices or []

    rows = []

    indicator_cols = [
        "indicator",
        "unit",
        "base_2021",
        "fact_2024",
        "fact_2025",
        "_latest_monitoring",
        "strategic_target_2028",
        "strategic_target_2034",
        "source_global",
        "source_national",
        "resp_main",
        "resp_co_1",
        "deputy_minister_raw"
    ]

    def indicator_row_matches_filters(row):
        if selected_ssp_indices and not row_contains_selected_ssp(row, selected_ssp_indices):
            return False

        if raw_value(search_query) and not indicator_row_matches_search(row, search_query):
            return False

        return True

    def add_row(row):
        if not raw_value(row.get("indicator", "")):
            return

        if not indicator_row_matches_filters(row):
            return

        prepared_row = []

        row_for_display = dict(row)
        row_for_display["_latest_monitoring"] = latest_indicator_submission(
            row.get("code", ""), row.get("indicator", ""), fact_year
        )
        for col in indicator_cols:
            prepared_row.append(format_indicator_value(row_for_display.get(col, ""), col))

        rows.append(prepared_row)

    add_row(parent_row)

    for _, child in child_rows.iterrows():
        add_row(child)

    return rows

def render_indicator_table(rows, fact_year):
    if not rows:
        st.info("Індикаторів не знайдено.")
        return

    html = f"""
    <div class="table-scroll">
    <table class="custom-table" style="min-width:2940px;">
    <thead>
        <tr>
            <th class="col-indicator" rowspan="2">Індикатор</th>
            <th class="col-unit" rowspan="2">Одиниці виміру</th>
            <th class="col-year" rowspan="2">2021<br><span style='font-size:11px;color:#61708A;'>базовий рівень (факт)</span></th>
            <th class="col-year" rowspan="2">2024<br><span style='font-size:11px;color:#61708A;'>звіт</span></th>
            <th class="col-year" rowspan="2">2025<br><span style='font-size:11px;color:#61708A;'>факт</span></th>
            <th class="col-long" rowspan="2">{fact_year} Факт</th>
            <th class="col-long" rowspan="2">Проміжний цільовий орієнтир на кінець 2028 року<span class="th-sub">(для цілей і завдань)</span></th>
            <th class="col-long" rowspan="2">Цільовий орієнтир на кінець 2034 року для цілей і завдань<div class="th-note-scroll">відповідає цілі, визначеній в НЕС-2030, ЦСР-2030 для показників, де це зазначено. Ціль перенесена на 2034 рік через «втрату» 4-х років — 2022-2025 внаслідок повномасштабної війни. Інші індикативні значення мають встановлюватись такими, що є кількісно узгодженими з цілями НЕС і ЦСР</div></th>
            <th class="col-long" colspan="2">Джерело даних</th>
            <th class="col-resp" colspan="2">Відповідальні самостійні структурні підрозділи</th>
            <th class="col-resp" rowspan="2">Заступник Міністра</th>
        </tr>
        <tr>
            <th class="col-long">Глобальний рівень</th>
            <th class="col-long">Національний рівень</th>
            <th class="col-resp">Головний</th>
            <th class="col-resp">Співвиконавець</th>
        </tr>
    </thead>
    <tbody>
    """

    for row in rows:
        html += "<tr>"
        html += f"<td class='col-indicator'>{make_cell(row[0], 'fixed')}</td>"
        html += f"<td class='col-unit'>{make_cell(row[1], 'fixed')}</td>"
        html += f"<td class='col-year'>{make_cell(row[2], 'nowrap')}</td>"
        html += f"<td class='col-year'>{make_cell(row[3], 'nowrap')}</td>"
        html += f"<td class='col-year'>{make_cell(row[4], 'nowrap')}</td>"
        html += f"<td class='col-long'>{row[5] or ''}</td>"
        html += f"<td class='col-long'>{make_cell(row[6], 'fixed')}</td>"
        html += f"<td class='col-long'>{make_cell(row[7], 'fixed')}</td>"
        html += f"<td class='col-long'>{make_cell(row[8], 'fixed')}</td>"
        html += f"<td class='col-long'>{make_cell(row[9], 'fixed')}</td>"
        html += f"<td class='col-resp'>{make_cell(row[10], 'nowrap')}</td>"
        html += f"<td class='col-resp'>{make_cell(row[11], 'nowrap')}</td>"
        html += f"<td class='col-resp'>{make_cell(row[12], 'nowrap')}</td>"
        html += "</tr>"

    html += "</tbody></table></div>"

    st.markdown(clean_html(html), unsafe_allow_html=True)


def render_measure_table(measures, monitoring_df, quarter_data, selected_years, selected_quarters, show_context_codes=False):
    quarter_columns = get_quarter_columns(selected_years, selected_quarters)

    context_headers = ""
    if show_context_codes:
        context_headers = """
            <th class="col-code" rowspan="3">Код цілі</th>
            <th class="col-code" rowspan="3">Код завдання</th>
        """

    html = f"""
    <div class="table-scroll measures-scroll">
    <table class="custom-table" style="min-width:{5350 + (220 if show_context_codes else 0)}px;">
    <thead>
        <tr>
            {context_headers}
            <th class="col-code" rowspan="3">Код</th>
            <th class="col-measure" rowspan="3">Захід</th>
            <th class="col-product" rowspan="3">Тип продукту</th>
            <th class="col-indicator" rowspan="3">Індикатор</th>
            <th class="col-unit" rowspan="3">Одиниці виміру</th>
            <th class="col-year" rowspan="3">2021<br><span style='font-size:11px;color:#61708A;'>базовий рівень (факт)</span></th>
            <th class="col-year" rowspan="3">2024<br><span style='font-size:11px;color:#61708A;'>звіт</span></th>
            <th class="col-year" rowspan="3">2025<br><span style='font-size:11px;color:#61708A;'>факт</span></th>
    """

    for year in [2026, 2027, 2028]:
        html += f"<th class='col-year' rowspan='3'>{year}<br><span style='font-size:11px;color:#61708A;'>цільовий орієнтир для заходів на рік</span></th>"

        year_quarters = [label for y, _, label in quarter_columns if int(y) == year]

        for label in year_quarters:
            html += f"<th class='col-year' rowspan='3'>{escape(label)}</th>"

    html += """
            <th class="col-long" colspan="2">Підстава для включення до стратегічного плану</th>
            <th class="col-resp" colspan="2">Відповідальні самостійні структурні підрозділи</th>
            <th class="col-resp" rowspan="3">Заступник Міністра</th>
            <th class="col-year" rowspan="3">Період дії заходу в межах планового періоду, років</th>
            <th class="col-year" rowspan="3">Початкова дата</th>
            <th class="col-year" rowspan="3">Кінцева дата</th>
            <th class="col-budget" colspan="8">Фінансування</th>
        </tr>
        <tr>
            <th class="col-long" rowspan="2">Глобальний рівень</th>
            <th class="col-long" rowspan="2">Національний рівень</th>
            <th class="col-resp" rowspan="2">Головний</th>
            <th class="col-resp" rowspan="2">Співвиконавець</th>
            <th class="col-budget" colspan="4">Державний бюджет України</th>
            <th class="col-budget" colspan="4">Інші джерела</th>
        </tr>
        <tr>
            <th class="col-budget">КПКВК</th>
            <th class="col-budget">2026<br><span style='font-size:11px;color:#61708A;'>затверджено, млрд грн</span></th>
            <th class="col-budget">2027<br><span style='font-size:11px;color:#61708A;'>прогноз, млрд грн</span></th>
            <th class="col-budget">2028<br><span style='font-size:11px;color:#61708A;'>прогноз, млрд грн</span></th>
            <th class="col-budget-source">Джерело<br><span style='font-size:11px;color:#61708A;'>МТД, кошти партнерів, інші небюджетні джерела</span></th>
            <th class="col-budget">2026<br><span style='font-size:11px;color:#61708A;'>план</span></th>
            <th class="col-budget">2027<br><span style='font-size:11px;color:#61708A;'>прогноз</span></th>
            <th class="col-budget">2028<br><span style='font-size:11px;color:#61708A;'>прогноз</span></th>
        </tr>
    </thead>
    <tbody>
    """

    for _, measure in measures.iterrows():
        code = raw_value(measure.get("code", ""))

        html += "<tr>"
        if show_context_codes:
            html += f"<td class='col-code'>{make_cell(measure.get('parent_goal_code', ''), 'nowrap')}</td>"
            html += f"<td class='col-code'>{make_cell(measure.get('parent_task_code', ''), 'nowrap')}</td>"
        html += f"<td class='col-code'>{make_cell(measure.get('code', ''), 'nowrap')}</td>"
        html += f"<td class='col-measure'>{make_cell(strip_leading_code(measure.get('name', ''), code), 'fixed')}</td>"
        html += f"<td class='col-product'>{make_cell(measure.get('product_type', ''), 'fixed')}</td>"
        html += f"<td class='col-indicator'>{make_cell(measure.get('indicator', ''), 'fixed')}</td>"
        html += f"<td class='col-unit'>{make_cell(measure.get('unit', ''), 'fixed')}</td>"
        html += f"<td class='col-year'>{make_cell(measure.get('base_2021', ''), 'nowrap')}</td>"
        html += f"<td class='col-year'>{make_cell(measure.get('fact_2024', ''), 'nowrap')}</td>"
        html += f"<td class='col-year'>{make_cell(measure.get('fact_2025', ''), 'nowrap')}</td>"

        for year in [2026, 2027, 2028]:
            html += f"<td class='col-year'>{make_cell(measure.get(f'target_{year}', ''), 'nowrap')}</td>"

            year_quarters = [(y, q, label) for y, q, label in quarter_columns if int(y) == year]

            for y, q, _ in year_quarters:
                key = f"{y}_{q}"
                item = quarter_data.get(code, {}).get(key, None)

                if item is None:
                    if is_period_locked(y, q):
                        badge = core_statuses.legend_badge(
                            "Не настав час",
                            display_value="—",
                        )
                        html += f"<td class='col-year'>{badge}</td>"
                    else:
                        html += "<td class='col-year status-empty'></td>"
                else:
                    value = raw_value(item.get("value", "")) or "—"
                    if is_period_locked(y, q):
                        badge_state = "Не настав час"
                    elif item.get("manual_closeout"):
                        badge_state = "Закрито адміністратором"
                    else:
                        badge_state = item.get("visual_status", "Не враховано")

                    badge = core_statuses.legend_badge(
                        badge_state,
                        display_value=value,
                    )
                    html += f"<td class='col-year'>{badge}</td>"

        html += f"<td class='col-long'>{make_cell(measure.get('source_global', ''), 'fixed')}</td>"
        html += f"<td class='col-long'>{make_cell(measure.get('source_national', ''), 'fixed')}</td>"
        html += f"<td class='col-resp'>{make_cell(measure.get('resp_main', ''), 'nowrap')}</td>"
        html += f"<td class='col-resp'>{make_cell(measure.get('resp_co_1', ''), 'nowrap')}</td>"
        html += f"<td class='col-resp'>{make_cell(measure.get('deputy_minister_raw', ''), 'nowrap')}</td>"
        html += f"<td class='col-year'>{make_cell(measure.get('measure_period_years', ''), 'nowrap')}</td>"
        html += f"<td class='col-year'>{make_cell(measure.get('measure_start_date', ''), 'nowrap')}</td>"
        html += f"<td class='col-year'>{make_cell(measure.get('measure_end_date', ''), 'nowrap')}</td>"
        html += f"<td class='col-budget'>{make_cell(measure.get('budget_kpkvk', ''), 'nowrap')}</td>"
        html += f"<td class='col-budget'>{make_cell(measure.get('budget_2026_approved', ''), 'nowrap')}</td>"
        html += f"<td class='col-budget'>{make_cell(measure.get('budget_2027_forecast', ''), 'nowrap')}</td>"
        html += f"<td class='col-budget'>{make_cell(measure.get('budget_2028_forecast', ''), 'nowrap')}</td>"
        html += f"<td class='col-budget-source'>{make_cell(measure.get('other_source', ''), 'fixed')}</td>"
        html += f"<td class='col-budget'>{make_cell(measure.get('other_2026_plan', ''), 'nowrap')}</td>"
        html += f"<td class='col-budget'>{make_cell(measure.get('other_2027_forecast', ''), 'nowrap')}</td>"
        html += f"<td class='col-budget'>{make_cell(measure.get('other_2028_forecast', ''), 'nowrap')}</td>"
        html += "</tr>"

    html += "</tbody></table></div>"

    st.markdown(clean_html(html), unsafe_allow_html=True)

# ------------------------------------------------------------
# Interface state
# ------------------------------------------------------------

def default_state():
    defaults = {
        "expand_all_goals": False,
        "ssp_filter": [],
        "selected_years_main": [],
        "selected_quarters_main": [],
        "status_mode_main": "Усі заходи стратегічного плану",
        "selected_goal_codes_main": [],
        "selected_product_types_main": [],
        "search_main": ""
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_main_filters():
    st.session_state["ssp_filter"] = []
    st.session_state["selected_years_main"] = []
    st.session_state["selected_quarters_main"] = []
    st.session_state["status_mode_main"] = "Усі заходи стратегічного плану"
    st.session_state["selected_goal_codes_main"] = []
    st.session_state["selected_product_types_main"] = []
    st.session_state["search_main"] = ""
    st.session_state["expand_all_goals"] = False
    st.session_state["applied_filters"] = {
        "ssp_filter": [],
        "selected_years_main": [],
        "selected_quarters_main": [],
        "status_mode_main": "Усі заходи стратегічного плану",
        "selected_goal_codes_main": [],
        "selected_product_types_main": [],
        "search_main": ""
    }


def apply_main_filters_form():
    """Безпечно зберігає значення форми, навіть якщо окремого ключа ще немає."""
    st.session_state["applied_filters"] = {
        "ssp_filter": list(st.session_state.get("ssp_filter") or []),
        "selected_years_main": list(st.session_state.get("selected_years_main") or []),
        "selected_quarters_main": list(st.session_state.get("selected_quarters_main") or []),
        "status_mode_main": st.session_state.get(
            "status_mode_main", "Усі заходи стратегічного плану"
        ),
        "selected_goal_codes_main": list(
            st.session_state.get("selected_goal_codes_main") or []
        ),
        "selected_product_types_main": list(
            st.session_state.get("selected_product_types_main") or []
        ),
        "search_main": st.session_state.get("search_main", "") or "",
    }


def expand_all_main():
    st.session_state.expand_all_goals = True


def collapse_all_main():
    st.session_state.expand_all_goals = False

# ------------------------------------------------------------
# Load data
# ------------------------------------------------------------

df = load_strat_matrix()
_all_monitoring_df = load_monitoring()
# Основна матриця заходів рахується окремо від подань індикаторів.
monitoring_df = append_confirmed_closeout_facts(monitoring_data.measures_only(_all_monitoring_df))
indicator_monitoring_df = monitoring_data.indicators_only(_all_monitoring_df)
quarter_data = build_quarter_data(monitoring_df)

manual_closeouts = load_manual_closeouts()
for closeout_code, closeout_year, closeout_quarter in manual_closeouts:
    closeout_key = f"{closeout_year}_{closeout_quarter}"
    quarter_data.setdefault(closeout_code, {}).setdefault(closeout_key, {"value": "", "visual_status": "", "class": "status-empty"})
    quarter_data[closeout_code][closeout_key]["manual_closeout"] = True
    quarter_data[closeout_code][closeout_key]["class"] = (
        "status-notyet" if is_period_locked(closeout_year, closeout_quarter) else "status-manual-closeout"
    )

default_state()

if "applied_filters" not in st.session_state:
    apply_main_filters_form()

all_measures = df[df["object_type"] == "measure"].copy()
goals = df[df["object_type"] == "goal"].copy()
tasks_all = df[df["object_type"] == "task"].copy()

# ------------------------------------------------------------
# Lists for filters
# ------------------------------------------------------------

@st.cache_data
def build_all_ssp_indices(df):
    return sorted(
        {
            index
            for _, row in df.iterrows()
            for value in [
                row.get("resp_main", ""),
                row.get("resp_co_1", ""),
                row.get("resp_co_2", ""),
                row.get("department", "")
            ]
            for index in split_ssp_values(value)
        },
        key=lambda x: int(x) if str(x).isdigit() else 9999
    )


@st.cache_data
def build_goal_options(goals):
    return {
        raw_value(row["code"]): f'{raw_value(row["code"])} {strip_leading_code(row["name"], row["code"])}'
        for _, row in goals.iterrows()
    }


@st.cache_data
def build_product_type_options(df):
    return sorted(
        [
            raw_value(value)
            for value in df["product_type"].dropna().unique()
            if raw_value(value)
        ]
    )


all_ssp_indices = build_all_ssp_indices(df)

year_options = list(range(2026, 2035))
quarter_options = ["I", "II", "III", "IV"]

status_options = [
    "Усі заходи стратегічного плану",
    "Лише погоджені",
    "Лише на розгляді",
    "Лише не враховані"
]

goal_options = build_goal_options(goals)

product_type_options = build_product_type_options(df)


# ------------------------------------------------------------
# Header
# ------------------------------------------------------------

st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="ministry-label">
    🇺🇦 Міністерство економіки, довкілля та сільського господарства України
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="header-box">
        <div class="header-title">Стратегічний план Мінекономіки на 2026-2028 роки</div>
        <div class="header-subtitle">
            Інтерактивна демо-версія системи моніторингу, аналізу та оцінки виконання заходів і прогресу досягнення завдань та стратегічних цілей
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

if str(ANNOUNCEMENT or "").strip():
    st.warning(str(ANNOUNCEMENT).strip(), icon="📢")

st.markdown(
    """
    <div class="cta-box">
        <div class="cta-title">Моніторинг і оцінка стратегічних результатів</div>
    </div>
    """,
    unsafe_allow_html=True
)

# ------------------------------------------------------------
# Flow block
# ------------------------------------------------------------

st.markdown(
    """
    <div class="flow-box">
        <div class="flow-title">Маршрут моніторингових даних</div>
        <div class="flow-steps">
            <div class="flow-step">👁️ Перегляд</div>
            <div class="flow-step">📝 Подання відомостей</div>
            <div class="flow-step">🔎 Збір та обробка</div>
            <div class="flow-step">🧩 Опрацювання та узгодження</div>
            <div class="flow-step">✅ Погодження відомостей</div>
            <div class="flow-step">📈 Оцінка виконання</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# Current monitoring status
# ------------------------------------------------------------

total_measures = len(all_measures)

submitted_count = unique_measure_count(monitoring_df)

_monitoring_visual = monitoring_df.copy()
if not _monitoring_visual.empty:
    _monitoring_visual["_visual_status"] = _monitoring_visual.apply(get_record_visual_status, axis=1)

reviewed_count = unique_measure_count(
    _monitoring_visual,
    lambda x: x["_visual_status"].isin(["Погоджено", "На доопрацюванні"])
)

waiting_count = unique_measure_count(
    _monitoring_visual,
    lambda x: x["_visual_status"] == "На розгляді"
)

returned_count = unique_measure_count(
    _monitoring_visual,
    lambda x: x["_visual_status"] == "На доопрацюванні"
)

approved_count = unique_measure_count(
    _monitoring_visual,
    lambda x: x["_visual_status"] == "Погоджено"
)

current_state_cards = "".join([
    make_summary_card("Заходів усього", total_measures),
    make_summary_card("Поданих відомостей за заходами", submitted_count),
    make_summary_card("Розглянуто", reviewed_count),
    make_summary_card("Очікує розгляду", waiting_count),
    make_summary_card("Повернуто на доопрацювання", returned_count),
    make_summary_card("Погоджено", approved_count)
])

st.markdown(
    f'<div class="summary-box">'
    f'<div class="summary-title">Поточний стан моніторингу Стратегічного плану</div>'
    f'<div class="summary-grid">{current_state_cards}</div>'
    f'</div>',
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# User guide
# ------------------------------------------------------------

st.markdown(
    """
    <div class="guide-title">Гід користувача</div>
    <div class="info-grid">
        <div class="info-card">
            <div class="info-card-title">Інструкція по роботі з системою</div>
            <div>
                1. Оберіть параметри фільтрації із випадних списків: індекс самостійного структурного підрозділу, звітний період та необхідний режим перегляду даних.<br>
                2. Система автоматично застосує обрані параметри та відобразить відповідні дані.<br>
                3. Розгорніть відповідні блоки та перегляньте усі відомості щодо стратегічних цілей, завдань та заходів.<br>
                4. Для переходу до внесення відомостей натисніть зелену кнопку.
            </div>
        </div>
        <div class="info-card">
            <div class="info-card-title">Легенда звітних даних</div>
            <div class="legend-item">🟦 На розгляді — відомості подані та перебувають на розгляді координатора або керівника самостійного структурного підрозділу</div>
            <div class="legend-item">🟨 На доопрацюванні — дані потребують уточнення та доопрацювання</div>
            <div class="legend-item">🟩 Погоджено — відомості узгоджено та враховано.</div>
            <div class="legend-item">⬜ Не настав час — період виконання заходу ще не почався або він не має враховуватися в розрахунках за обраний період</div>
            <div class="legend-item">🟥 Не враховано — відомості не подані або перебувають на погодженні більше 5 робочих днів</div>
            <div class="legend-item">🟪 Закрито адміністратором — захід закрито вручну на підставі внутрішньої інформації чи іншого звітного документа (підтверджено супер-адміном); подане значення відображається фіолетовим</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# Filters
# ------------------------------------------------------------

# Старе значення вилученого режиму не повинно ламати selectbox після rerun.
if st.session_state.get("status_mode_main") not in status_options:
    st.session_state["status_mode_main"] = status_options[0]

st.markdown('<div class="filter-title">Параметри відбору (для перегляду)</div>', unsafe_allow_html=True)

with st.form("main_filters_form"):
    st.markdown(
        '<div class="filter-subtitle main-filter-subtitle">Основні параметри</div>',
        unsafe_allow_html=True,
    )
    top_1, top_2, top_3, top_4 = st.columns([1.35, 0.8, 0.8, 1.15])

    _scope_field_locked = (
        is_scope_lockable_user(current_user)
        and not is_scope_override_active("app")
    )
    _own_ssp_index = get_user_ssp_index(current_user) if _scope_field_locked else None
    _ssp_widget_options = list(all_ssp_indices)
    if _own_ssp_index and _own_ssp_index not in _ssp_widget_options:
        _ssp_widget_options = [_own_ssp_index, *_ssp_widget_options]
    if _scope_field_locked:
        st.session_state["ssp_filter"] = [_own_ssp_index] if _own_ssp_index else []

    with top_1:
        st.markdown(
            '<div class="filter-field-label">Індекс самостійного структурного підрозділу</div>',
            unsafe_allow_html=True,
        )
        st.multiselect(
            "Індекс самостійного структурного підрозділу",
            _ssp_widget_options,
            key="ssp_filter",
            placeholder="Оберіть індекс ССП",
            label_visibility="collapsed",
            disabled=_scope_field_locked,
        )

    with top_2:
        st.markdown(
            '<div class="filter-field-label">Звітний період</div>',
            unsafe_allow_html=True,
        )
        st.multiselect(
            "Рік",
            year_options,
            key="selected_years_main",
            placeholder="Рік",
            label_visibility="collapsed",
        )

    with top_3:
        st.markdown(
            '<div class="filter-field-label">&nbsp;</div>',
            unsafe_allow_html=True,
        )
        st.multiselect(
            "Квартал",
            quarter_options,
            key="selected_quarters_main",
            placeholder="Квартал",
            label_visibility="collapsed",
        )

    with top_4:
        st.markdown(
            '<div class="filter-field-label">Режим перегляду даних</div>',
            unsafe_allow_html=True,
        )
        st.selectbox(
            "Режим перегляду даних",
            status_options,
            key="status_mode_main",
            label_visibility="collapsed",
        )

    with st.container(key="main_additional_parameters"):
        with st.expander("Додаткові параметри", expanded=False):
            bottom_1, bottom_2, bottom_3 = st.columns([1.1, 1.0, 1.8])

            with bottom_1:
                st.markdown(
                    '<div class="filter-field-label">Стратегічна ціль</div>',
                    unsafe_allow_html=True,
                )
                st.multiselect(
                    "Стратегічна ціль",
                    list(goal_options.values()),
                    key="selected_goal_codes_main",
                    placeholder="Оберіть стратегічну ціль",
                    label_visibility="collapsed",
                )

            with bottom_2:
                st.markdown(
                    '<div class="filter-field-label">Тип продукту</div>',
                    unsafe_allow_html=True,
                )
                st.multiselect(
                    "Тип продукту",
                    product_type_options,
                    key="selected_product_types_main",
                    placeholder="Оберіть тип продукту",
                    label_visibility="collapsed",
                )

            with bottom_3:
                st.markdown(
                    '<div class="filter-field-label">Додаткові параметри пошуку (код завдання, заходу, ключові слова)</div>',
                    unsafe_allow_html=True,
                )
                st.text_input(
                    "Додаткові параметри пошуку (код завдання, заходу, ключові слова)",
                    key="search_main",
                    placeholder="Введіть код, назву або ключове слово",
                    label_visibility="collapsed",
                )

    apply_col, reset_col = st.columns([1, 1])
    with apply_col:
        st.form_submit_button(
            "Застосувати параметри відбору",
            use_container_width=True,
            on_click=apply_main_filters_form,
        )
    with reset_col:
        st.form_submit_button(
            "Скинути фільтри",
            use_container_width=True,
            on_click=reset_main_filters,
        )

render_scope_toggle("app", current_user)


# ------------------------------------------------------------
# Filter processing (за останньо застосованими параметрами)
# ------------------------------------------------------------

applied = st.session_state.get("applied_filters", {})

selected_ssp_indices = list(applied.get("ssp_filter") or [])

# Поле ССП завжди існує. Для ролей, замкнених на власний ССП, воно disabled
# до режиму загальної інформації; серверне звуження лишається додатковим
# захистом від випадкового послаблення scope через session_state.
if is_scope_lockable_user(current_user) and not is_scope_override_active("app"):
    _own_ssp_index = get_user_ssp_index(current_user)
    if _own_ssp_index:
        selected_ssp_indices = [_own_ssp_index]

selected_years_raw = list(applied.get("selected_years_main") or [])
selected_quarters_raw = list(applied.get("selected_quarters_main") or [])
selected_status_mode = applied.get(
    "status_mode_main", "Усі заходи стратегічного плану"
)
if selected_status_mode not in status_options:
    selected_status_mode = status_options[0]
selected_goal_labels = list(applied.get("selected_goal_codes_main") or [])
selected_product_types = list(applied.get("selected_product_types_main") or [])
search_query = applied.get("search_main", "") or ""

selected_goal_codes = [
    code
    for code, label in goal_options.items()
    if label in selected_goal_labels
]

# Порожній вибір періоду візуально лишається порожнім, але для вибірки та
# розрахунків означає весь поточний рік і всі чотири квартали.
_current_year = now_kyiv().year
selected_years = [
    year for year in year_options if year in selected_years_raw
] or [_current_year]
selected_quarters = [
    quarter for quarter in quarter_options if quarter in selected_quarters_raw
] or list(quarter_options)
indicator_fact_year = max(selected_years) if selected_years else _current_year

filtered_measures = apply_measure_filters(
    all_measures,
    monitoring_df,
    selected_ssp_indices,
    selected_years,
    selected_quarters,
    selected_status_mode,
    selected_goal_codes,
    selected_product_types,
    [],
    search_query
)

filtered_goal_codes = set(filtered_measures["parent_goal_code"].astype(str).str.strip()) if not filtered_measures.empty else set()
filtered_task_codes = set(filtered_measures["parent_task_code"].astype(str).str.strip()) if not filtered_measures.empty else set()

visible_goals = goals[goals["code"].astype(str).str.strip().isin(filtered_goal_codes)].copy()
visible_tasks = tasks_all[tasks_all["code"].astype(str).str.strip().isin(filtered_task_codes)].copy()

done_count, completion_percent = calculate_completion(filtered_measures, selected_years, selected_quarters)

approved_filtered = count_filtered_status(filtered_measures, "Погоджено")
waiting_filtered = count_filtered_status(filtered_measures, "На розгляді")
not_counted_filtered = count_filtered_status(filtered_measures, "Не враховано")
risk_count = int(filtered_measures["has_risks"].fillna(False).sum()) if not filtered_measures.empty and "has_risks" in filtered_measures.columns else 0

search_cards = "".join([
    make_summary_card("Стратегічних цілей", len(visible_goals)),
    make_summary_card("Завдань", len(visible_tasks)),
    make_summary_card("Заходів", len(filtered_measures)),
    make_summary_card("Виконано", done_count),
    make_summary_card("Погоджено", approved_filtered),
    make_summary_card("На розгляді", waiting_filtered),
    make_summary_card("Не враховано", not_counted_filtered)
])

st.markdown(
    f'<div class="search-result-box">'
    f'<div class="search-result-title">Результати пошуку</div>'
    f'<div class="summary-grid-7">{search_cards}</div>'
    f'</div>',
    unsafe_allow_html=True
)

years_label = ", ".join(str(year) for year in selected_years)
quarters_label = ", ".join(str(q) for q in selected_quarters)
ssp_label = ", ".join([f"деп. {x}" for x in selected_ssp_indices]) if selected_ssp_indices else "Усі"

st.caption(
    f"Рік: {years_label}. "
    f"Квартал: {quarters_label}. "
    f"ССП: {ssp_label}. "
    f"Параметри: {selected_status_mode}. "
    f"Заходів із ризиками: {risk_count}."
)

# ------------------------------------------------------------
# Strategic plan view
# ------------------------------------------------------------

st.subheader("Відомості для моніторингу")

st.markdown(
    """
    <div class="note-box">
        Фільтрація застосовується до всієї ієрархії Стратегічного плану: стратегічна ціль → завдання → захід.<br>
        Стратегічні цілі та завдання без відповідних заходів не відображаються.<br>
        Відсоток виконання розраховується за відібраними заходами.
    </div>
    """,
    unsafe_allow_html=True
)

if filtered_measures.empty:
    st.warning("За обраними параметрами відбору відомостей не знайдено.")
    render_footer()
    st.stop()

if len(filtered_goal_codes) == 1:
    st.markdown(
        '<div class="section-title">Заходи (плоский перелік — звужено до однієї стратегічної цілі)</div>',
        unsafe_allow_html=True
    )
    render_measure_table(
        filtered_measures,
        monitoring_df,
        quarter_data,
        selected_years,
        selected_quarters,
        show_context_codes=True
    )
else:
    for _, goal in visible_goals.iterrows():
        goal_code = raw_value(goal["code"])
        goal_name = strip_leading_code(goal["name"], goal_code)

        goal_filtered_measures = filtered_measures[
            filtered_measures["parent_goal_code"].astype(str).str.strip() == goal_code
        ].copy()

        goal_indicator_children = df[
            (df["object_type"] == "goal_indicator")
            & (df["parent_goal_code"].astype(str).str.strip() == goal_code)
            & (df["parent_task_code"].astype(str).str.strip() == "")
        ].copy()

        goal_indicators = build_indicator_rows(
            goal,
            goal_indicator_children,
            selected_ssp_indices,
            search_query,
            indicator_fact_year,
        )

        if goal_filtered_measures.empty and not goal_indicators:
            continue

        goal_task_codes = set(goal_filtered_measures["parent_task_code"].astype(str).str.strip()) if not goal_filtered_measures.empty else set()
        tasks = tasks_all[tasks_all["code"].astype(str).str.strip().isin(goal_task_codes)].copy()

        goal_done, goal_percent = calculate_completion(goal_filtered_measures, selected_years, selected_quarters)

        goal_label = (
            f"{goal_code} {goal_name} | "
            f"Завдань — {len(tasks)} | "
            f"Заходів — {len(goal_filtered_measures)} | "
            f"Виконання — {goal_percent}%"
        )

        with st.expander(goal_label, expanded=st.session_state.expand_all_goals):
            st.progress(min(goal_percent / 100, 1.0))

            if goal_indicators:
                st.markdown(
                    '<div class="section-title">Індикатори досягнення стратегічної цілі</div>',
                    unsafe_allow_html=True
                )
                render_indicator_table(goal_indicators, indicator_fact_year)

            for _, task in tasks.iterrows():
                task_code = raw_value(task["code"])
                task_name = strip_leading_code(task["name"], task_code)

                task_measures = goal_filtered_measures[
                    goal_filtered_measures["parent_task_code"].astype(str).str.strip() == task_code
                ].copy()

                task_indicator_children = df[
                    (df["object_type"] == "task_indicator")
                    & (df["parent_task_code"].astype(str) == task_code)
                ].copy()

                task_indicators = build_indicator_rows(
                    task,
                    task_indicator_children,
                    selected_ssp_indices,
                    search_query,
                    indicator_fact_year,
                )

                if task_measures.empty and not task_indicators:
                    continue

                task_done, task_percent = calculate_completion(task_measures, selected_years, selected_quarters)

                task_label = (
                    f"{task_code} {task_name} | "
                    f"Заходів — {len(task_measures)} | "
                    f"Виконання — {task_percent}%"
                )

                with st.expander(task_label, expanded=st.session_state.expand_all_goals):
                    if task_indicators:
                        st.markdown(
                            '<div class="section-title">Індикатори досягнення завдання</div>',
                            unsafe_allow_html=True
                        )
                        render_indicator_table(task_indicators, indicator_fact_year)

                    st.markdown(
                        '<div class="section-title">Заходи</div>',
                        unsafe_allow_html=True
                    )

                    render_measure_table(
                        task_measures,
                        monitoring_df,
                        quarter_data,
                        selected_years,
                        selected_quarters
                    )


# ------------------------------------------------------------
# Expand / collapse controls under blue blocks
# ------------------------------------------------------------

btn1, btn2 = st.columns([1, 1])

with btn1:
    st.button(
        "Розгорнути всі релевантні відомості",
        use_container_width=True,
        on_click=expand_all_main
    )

with btn2:
    st.button(
        "Згорнути всі відомості",
        use_container_width=True,
        on_click=collapse_all_main
    )

if str(current_user.get("role") or "") in {ROLE_SSP, ROLE_SSP_HEAD, ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY}:
    if st.button("🖊️ Подати відомості", use_container_width=True, key="go_to_monitoring_submission"):
        st.switch_page("pages/1_Моніторинг_виконання.py")

# ------------------------------------------------------------
# Єдиний повний Excel-експорт — у самому низу сторінки
# ------------------------------------------------------------

_export_bytes = core_exports.build_main_monitoring_export(
    strat_df=df,
    filtered_measures=filtered_measures,
    monitoring_df=monitoring_df,
    indicator_monitoring_df=indicator_monitoring_df,
    selected_years=selected_years,
    selected_quarters=selected_quarters,
    selected_ssp_indices=selected_ssp_indices,
    selected_product_types=selected_product_types,
    search_query=search_query,
    manual_closeouts=manual_closeouts,
)

st.download_button(
    "⬇️ Завантажити Excel",
    data=_export_bytes,
    file_name=f"SP_моніторинг_{now_kyiv().strftime('%Y%m%d_%H%M')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    key="main_full_excel_export",
    use_container_width=False,
)

# ------------------------------------------------------------
# Footer
# ------------------------------------------------------------

render_footer()
