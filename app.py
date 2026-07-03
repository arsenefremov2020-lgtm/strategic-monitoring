from textwrap import dedent
import re
import io
from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st
from core.db import get_supabase_client
from core.deputies import DEPUTY_MINISTER_BY_SSP
from core.ui import load_css
from core.config import FILE_PATH, SHEET_NAME
from core.excel_loader import read_excel_sheet
from core.auth import init_auth_state, render_login_form
from core.navigation import render_role_page_links


st.set_page_config(page_title="Стратегічний план", layout="wide")

st.logo(
    "assets/Мінекономіки.png",
    size="large"
)


supabase = get_supabase_client()
load_css()
init_auth_state()
current_user = render_login_form()
render_role_page_links()
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
    background:
        radial-gradient(circle at top right, rgba(37,99,235,0.08), transparent 28%),
        radial-gradient(circle at bottom left, rgba(22,163,74,0.07), transparent 30%),
        linear-gradient(180deg, #f6f8fb 0%, #eef2f7 100%);
}

.stApp::before {
    content: "";
    position: fixed;
    top: -160px;
    right: -120px;
    width: 460px;
    height: 460px;
    border-radius: 50%;
    background: rgba(37, 99, 235, 0.045);
    z-index: 0;
}

.stApp::after {
    content: "";
    position: fixed;
    bottom: -180px;
    left: -120px;
    width: 390px;
    height: 390px;
    border-radius: 50%;
    background: rgba(22, 163, 74, 0.045);
    z-index: 0;
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
    color: #475569;
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 8px;
}

.header-box,
.flow-box,
.summary-box,
.filter-box,
.info-card,
.note-box,
.search-result-box {
    background: rgba(255,255,255,0.94);
    border: 1px solid #d8dee9;
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
    color: #0f172a;
    margin-bottom: 8px;
}

.header-subtitle {
    font-size: 15px;
    color: #475569;
    line-height: 1.55;
}

.system-status {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-top: 14px;
}

.status-pill {
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 10px;
    padding: 10px 12px;
    font-size: 13px;
    color: #334155;
}

.cta-box {
    background: linear-gradient(90deg, #15803d, #16a34a);
    color: white;
    border-radius: 16px;
    padding: 22px 26px;
    margin: 14px 0 18px 0;
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
    color: #0f172a;
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
    background: linear-gradient(180deg, #f8fafc 0%, #eef4fb 100%);
    border: 1px solid #d8dee9;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    color: #334155;
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
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 13px;
    padding: 14px 15px;
    min-height: 96px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.summary-label {
    color: #64748b;
    font-size: 12px;
    font-weight: 800;
    line-height: 1.35;
    min-height: 34px;
    margin-bottom: 8px;
}

.summary-value {
    color: #0f172a;
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
    grid-template-columns: 1.2fr 1fr;
    gap: 14px;
    margin-bottom: 20px;
}

.info-card {
    border-radius: 14px;
    padding: 17px 19px;
    color: #1f2937;
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

.filter-box {
    border-radius: 18px;
    padding: 24px 26px 26px 26px;
    margin: 18px 0 24px 0;
    background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(241,246,253,0.98));
    border: 1px solid #cbd8ea;
    box-shadow: 0 10px 24px rgba(15,23,42,0.07);
}

.filter-title {
    font-size: 22px;
    margin-bottom: 18px;
}

.filter-subtitle {
    color: #1e293b;
    font-size: 15px;
    font-weight: 950;
    margin: 18px 0 10px 0;
    padding-bottom: 4px;
    border-bottom: 1px solid rgba(148,163,184,0.35);
}

div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
div[data-testid="stTextInput"] input {
    background-color: #d7eaff !important;
    border: 1px solid #8fb3df !important;
    border-radius: 10px !important;
    min-height: 43px !important;
    box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.08) !important;
}

div[data-testid="stSelectbox"] label,
div[data-testid="stMultiSelect"] label,
div[data-testid="stTextInput"] label {
    font-weight: 750 !important;
    color: #1e293b !important;
}

section[data-testid="stSidebar"] div[data-testid="stPageLink"] {
    width: 100% !important;
    display: block !important;
    margin-top: 3px !important;
    margin-bottom: 5px !important;
}

section[data-testid="stSidebar"] div[data-testid="stPageLink"] a {
    width: 100% !important;
    min-height: 36px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;

    background: rgba(255, 255, 255, 0.78) !important;
    color: #0f172a !important;

    border-radius: 9px !important;
    padding: 7px 10px !important;
    border: 1px solid rgba(148, 163, 184, 0.35) !important;

    font-size: 14px !important;
    font-weight: 700 !important;
    letter-spacing: 0 !important;
    text-decoration: none !important;

    box-shadow: 0 1px 5px rgba(15, 23, 42, 0.05) !important;
}

section[data-testid="stSidebar"] div[data-testid="stPageLink"] a p {
    color: #0f172a !important;
    font-size: 14px !important;
    font-weight: 700 !important;
    margin: 0 !important;
}

section[data-testid="stSidebar"] div[data-testid="stPageLink"] a svg {
    color: #334155 !important;
    fill: #334155 !important;
}

section[data-testid="stSidebar"] div[data-testid="stPageLink"] a:hover {
    background: rgba(241, 245, 249, 0.95) !important;
    border-color: rgba(22, 163, 74, 0.35) !important;
    transform: none !important;
    filter: none !important;
}

div[data-testid="stExpander"] {
    border: none;
    margin-bottom: 14px;
}

div[data-testid="stExpander"] > details > summary {
    background: linear-gradient(90deg, #1d4ed8, #0f55e8) !important;
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
    background: linear-gradient(90deg, #1f2937, #374151) !important;
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

.section-title {
    font-size: 16px;
    font-weight: 850;
    color: #111827;
    margin: 18px 0 12px 0;
}

.note-box {
    border-radius: 10px;
    padding: 13px 17px;
    color: #374151;
    margin: 12px 0 18px 0;
    font-size: 14px;
    line-height: 1.55;
}

.table-scroll {
    overflow: auto;
    width: 100%;
    border: 1px solid #d1d5db;
    border-radius: 10px;
    margin-bottom: 18px;
    background: white;
}

.table-scroll.measures-scroll {
    max-height: 325px;
}

.th-sub {
    display: block;
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
    margin-top: 2px;
}

.th-note-scroll {
    max-height: 60px;
    overflow-y: auto;
    font-size: 10px;
    line-height: 1.3;
    color: #64748b;
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
    background-color: #e9eef7;
    color: #111827;
    padding: 9px 10px;
    border: 1px solid #d1d5db;
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
    border: 1px solid #d1d5db;
    vertical-align: middle;
    text-align: center;
    white-space: normal;
    word-wrap: break-word;
    overflow-wrap: break-word;
    line-height: 1.32;
}

table.custom-table tr:nth-child(even) {
    background-color: #f8fafc;
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
    background-color: #dbeafe !important;
    color: #1e3a8a;
    font-weight: 850;
}

td.status-approved {
    background-color: #dcfce7 !important;
    color: #166534;
    font-weight: 850;
}

td.status-returned {
    background-color: #fef3c7 !important;
    color: #92400e;
    font-weight: 850;
}

td.status-empty {
    background-color: #fee2e2 !important;
    color: #991b1b;
    font-weight: 850;
}

.closeout-badge {
    display: inline-block;
    margin-left: 6px;
    padding: 1px 6px;
    border-radius: 4px;
    background-color: #6d28d9;
    color: #f8fafc !important;
    font-size: 10px;
    font-weight: 700;
    white-space: nowrap;
    vertical-align: middle;
}

/* Клітинка періоду, закритого адміністратором вручну */
.status-manual-closeout {
    background-color: #ede9fe !important;
    color: #5b21b6;
    font-weight: 850;
}

td.risk-cell {
    background-color: #fee2e2 !important;
    color: #991b1b;
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
    color: #64748b;
    font-size: 13px;
    margin-top: 50px;
    padding: 22px 0 12px 0;
    border-top: 1px solid #d8dee9;
}

.footer strong {
    color: #334155;
}

.submit-main-button {
    display: flex;
    width: 100%;
    min-height: 68px;
    align-items: center;
    justify-content: center;

    margin-top: 16px;
    margin-bottom: 34px;

    background: linear-gradient(135deg, #047857 0%, #16a34a 55%, #22c55e 100%);
    color: #ffffff !important;

    border-radius: 18px;
    border: 1px solid rgba(255,255,255,0.28);

    font-size: 18px;
    font-weight: 950;
    letter-spacing: 0.3px;
    text-decoration: none !important;

    box-shadow: 0 16px 32px rgba(22,163,74,0.34), inset 0 1px 0 rgba(255,255,255,0.22);
}

.submit-main-button:hover {
    color: #ffffff !important;
    filter: brightness(1.05);
    transform: translateY(-1px);
    text-decoration: none !important;
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

    .system-status {
        grid-template-columns: repeat(2, 1fr);
    }
}
</style>
""",
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# Basic helpers
# ------------------------------------------------------------

def raw_value(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value).strip()


def clean_value(value):
    return escape(raw_value(value))


def normalize_text(value):
    return raw_value(value).lower().replace(" ", "")


def is_empty_or_nd(value):
    return normalize_text(value) in {"", "н.д.", "нд", "nan", "none", "-", "—"}


def strip_leading_code(text, code):
    value = raw_value(text)
    code_value = raw_value(code)

    if code_value and value.startswith(code_value):
        value = value[len(code_value):].lstrip(" .—-–|:")

    return value


def extract_ssp_index(value):
    """
    Витягує чистий числовий індекс ССП.
    Приклади:
    'деп. 30' -> '30'
    'упр. 4' -> '4'
    'сек. 12' -> '12'
    """
    text = raw_value(value)
    if not text:
        return ""

    match = re.search(r"\d+", text)
    return match.group(0) if match else ""


def split_ssp_values(value):
    """
    Дає список усіх індексів ССП із комірки, якщо там кілька значень.
    """
    text = raw_value(value)
    if not text:
        return []

    return re.findall(r"\d+", text)


def get_deputy_minister_by_main_ssp(value):
    """Повертає заступника Міністра за індексом головного виконавця."""
    index = extract_ssp_index(value)
    return DEPUTY_MINISTER_BY_SSP.get(index, "")


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


def business_days_between(start, end):
    if pd.isna(start) or pd.isna(end):
        return 0

    start_date = start.date()
    end_date = end.date()

    if end_date <= start_date:
        return 0

    return len(pd.bdate_range(start=start_date, end=end_date, inclusive="right"))


# ------------------------------------------------------------
# Data loading
# ------------------------------------------------------------

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
        # базова структура
        "type_marker": safe_col(1),       # B
        "code": safe_col(2),              # C
        "name": safe_col(3),              # D
        "product_type": safe_col(4),      # E

        # індикаторний блок
        "indicator": safe_col(5),         # F
        "unit": safe_col(6),              # G
        "base_2021": safe_col(7),         # H
        "fact_2024": safe_col(8),         # I
        "fact_2025": safe_col(9),         # J
        "target_2026": safe_col(10),      # K
        "target_2027": safe_col(11),      # L
        "target_2028": safe_col(12),      # M

        # стратегічні орієнтири / підстави / джерела
        "strategic_target_2028": safe_col(13),     # N
        "strategic_target_2034": safe_col(14),     # O
        "source_global": safe_col(15),              # P
        "source_national": safe_col(16),            # Q

        # відповідальні ССП
        "resp_main": safe_col(17),          # R
        "resp_co_1": safe_col(18),          # S
        "resp_co_2": safe_col(19),          # T

        # службові / майбутні колонки
        "deputy_minister_raw": pd.Series([""] * len(data), index=data.index),
        "measure_period_years": safe_keyword_col(["період", "років"]),
        "measure_start_date": safe_keyword_col(["початкова", "дата"]),
        "measure_end_date": safe_keyword_col(["кінцева", "дата"]),

        # фінансування заходів: державний бюджет України та інші джерела
        "budget_kpkvk": safe_col(24),                 # Y
        "budget_2026_approved": safe_col(25),         # Z
        "budget_2027_forecast": safe_col(26),         # AA
        "budget_2028_forecast": safe_col(27),         # AB
        "other_source": safe_col(28),                 # AC
        "other_2026_plan": safe_col(29),              # AD
        "other_2027_forecast": safe_col(30),          # AE
        "other_2028_forecast": safe_col(31),          # AF

        # сумісність зі старим кодом
        "department": safe_col(17)
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


@st.cache_data(ttl=300)
def load_monitoring():
    response = supabase.table("monitoring_requests").select("*").execute()

    if not response.data:
        return pd.DataFrame()

    return pd.DataFrame(response.data)


def ensure_monitoring_columns(monitoring_df):
    required_cols = [
        "id",
        "department",
        "year",
        "quarter",
        "approval_status",
        "status",
        "strat_code",
        "responsible_person",
        "phone",
        "email",
        "numeric_value",
        "progress_text",
        "risks",
        "npa_link",
        "file_names",
        "file_urls",
        "admin_comment",
        "start_date",
        "end_date",
        "submitted_at"
    ]

    for col in required_cols:
        if col not in monitoring_df.columns:
            monitoring_df[col] = ""

    return monitoring_df


from core.closeouts import load_manual_closeouts


# ------------------------------------------------------------
# Monitoring status logic
# ------------------------------------------------------------

def get_measure_records(monitoring_df, code, selected_years, selected_quarters):
    if monitoring_df.empty:
        return pd.DataFrame()

    years_as_str = [str(y) for y in selected_years]
    quarters_as_str = [str(q).replace(" квартал", "").strip() for q in selected_quarters]

    data = monitoring_df.copy()
    data = data[data["strat_code"].astype(str).str.strip() == str(code).strip()]

    if years_as_str:
        data = data[data["year"].astype(str).str.strip().isin(years_as_str)]

    if quarters_as_str:
        data = data[data["quarter"].astype(str).str.strip().isin(quarters_as_str)]

    return data.copy()


def is_overdue_review_record(row):
    if raw_value(row.get("approval_status", "")) != "Очікує погодження":
        return False

    submitted = pd.to_datetime(row.get("submitted_at", None), errors="coerce")

    if pd.isna(submitted):
        return False

    return business_days_between(submitted, pd.Timestamp.now()) > 5


def get_record_visual_status(row):
    approval = raw_value(row.get("approval_status", ""))

    if approval == "Погоджено":
        return "Погоджено"

    if approval == "Повернуто на доопрацювання":
        return "На доопрацюванні"

    if approval == "Очікує погодження":
        return "Не враховано" if is_overdue_review_record(row) else "На розгляді"

    return "Не враховано"


def visual_status_class(status):
    if status == "Погоджено":
        return "status-approved"

    if status == "На розгляді":
        return "status-review"

    if status == "На доопрацюванні":
        return "status-returned"

    return "status-empty"


def get_measure_status(monitoring_df, code, selected_years, selected_quarters):
    records = get_measure_records(monitoring_df, code, selected_years, selected_quarters)

    if records.empty:
        return "Не враховано"

    statuses = [get_record_visual_status(row) for _, row in records.iterrows()]

    if "Погоджено" in statuses:
        return "Погоджено"

    if "На розгляді" in statuses:
        return "На розгляді"

    if "На доопрацюванні" in statuses:
        return "На доопрацюванні"

    return "Не враховано"


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


def has_measure_risks(monitoring_df, code, selected_years, selected_quarters):
    return has_not_counted_monitoring(monitoring_df, code, selected_years, selected_quarters)


def measure_matches_status_mode(monitoring_df, code, selected_years, selected_quarters, mode):
    status = get_measure_status(monitoring_df, code, selected_years, selected_quarters)

    if mode == "Усі заходи стратегічного плану":
        return True

    if mode == "Лише погоджені":
        return status == "Погоджено"

    if mode == "Лише на розгляді":
        return status == "На розгляді"

    if mode == "Лише на доопрацюванні":
        return status == "На доопрацюванні"

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


def get_indicator_type(row):
    unit = raw_value(row.get("unit", "")).lower()

    if "так/ні" in unit or ("так" in unit and "ні" in unit):
        return "Так/ні"

    if "%" in unit or "відсот" in unit:
        return "Відсотковий"

    if any(x in unit for x in ["грн", "дол", "євро", "eur", "usd"]):
        return "Фінансовий"

    return "Кількісний"


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

    filtered["has_risks"] = filtered["has_not_counted"]

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


def calculate_completion(filtered_measures):
    if filtered_measures.empty:
        return 0, 0

    done_count = len(filtered_measures[filtered_measures["monitoring_status"] == "Погоджено"])
    total_count = len(filtered_measures)

    percent = round((done_count / total_count) * 100, 1) if total_count else 0

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


def build_export_dataframe(measures, quarter_data, selected_years, selected_quarters):
    quarter_columns = get_quarter_columns(selected_years, selected_quarters)

    rows = []
    for _, measure in measures.iterrows():
        code = raw_value(measure.get("code", ""))

        row = {
            "Код": code,
            "Захід": strip_leading_code(measure.get("name", ""), code),
            "Тип продукту": raw_value(measure.get("product_type", "")),
            "Індикатор": raw_value(measure.get("indicator", "")),
            "Одиниці виміру": raw_value(measure.get("unit", "")),
            "Головний виконавець": raw_value(measure.get("resp_main", "")),
            "Співвиконавець": raw_value(measure.get("resp_co_1", "")),
        }

        for year, quarter, label in quarter_columns:
            key = f"{year}_{quarter}"
            item = quarter_data.get(code, {}).get(key, {})
            row[label] = item.get("value", "")

        rows.append(row)

    return pd.DataFrame(rows)


def build_export_excel(measures, quarter_data, selected_years, selected_quarters):
    export_df = build_export_dataframe(measures, quarter_data, selected_years, selected_quarters)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Заходи")

    return buffer.getvalue()


# ------------------------------------------------------------
# HTML table rendering
# ------------------------------------------------------------

def two_line_header(top, bottom):
    top_text = escape(str(top))
    bottom_text = escape(str(bottom))

    if bottom_text:
        return f"{top_text}<br><span style='font-size:11px;font-weight:700;color:#475569;'>{bottom_text}</span>"

    return top_text

def clean_html(html: str) -> str:
    return "\n".join(
        line.strip()
        for line in html.splitlines()
        if line.strip()
    )

def render_table(headers, rows, col_classes, min_width=2200, scroll_class="table-scroll"):
    if not rows:
        st.info("Дані відсутні.")
        return

    html = f"""
    <div class="{scroll_class}">
    <table class="custom-table" style="min-width:{min_width}px;">
    <thead>
    <tr>
    """

    for idx, header in enumerate(headers):
        col_class = col_classes[idx] if idx < len(col_classes) else "col-year"

        if isinstance(header, tuple):
            header_html = two_line_header(header[0], header[1])
        else:
            header_html = escape(str(header))

        html += f"<th class='{col_class}'>{header_html}</th>"

    html += "</tr></thead><tbody>"

    for row in rows:
        html += "<tr>"

        for idx, cell in enumerate(row):
            value = cell.get("value", "") if isinstance(cell, dict) else cell
            status_class = cell.get("status_class", "") if isinstance(cell, dict) else ""
            mode = cell.get("mode", "fixed") if isinstance(cell, dict) else "fixed"
            col_class = col_classes[idx] if idx < len(col_classes) else "col-year"
            classes = f"{col_class} {status_class}".strip()

            html += f"<td class='{classes}'>{make_cell(value, mode)}</td>"

        html += "</tr>"

    html += "</tbody></table></div>"

    st.markdown(clean_html(html), unsafe_allow_html=True)


def build_indicator_rows(parent_row, child_rows, selected_ssp_indices=None, search_query=""):
    selected_ssp_indices = selected_ssp_indices or []

    rows = []

    indicator_cols = [
        "indicator",
        "unit",
        "base_2021",
        "fact_2024",
        "fact_2025",
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

        for col in indicator_cols:
            prepared_row.append(format_indicator_value(row.get(col, ""), col))

        rows.append(prepared_row)

    add_row(parent_row)

    for _, child in child_rows.iterrows():
        add_row(child)

    return rows

def render_indicator_table(rows):
    if not rows:
        st.info("Індикаторів не знайдено.")
        return

    html = """
    <div class="table-scroll">
    <table class="custom-table" style="min-width:2770px;">
    <thead>
        <tr>
            <th class="col-indicator" rowspan="2">Індикатор</th>
            <th class="col-unit" rowspan="2">Одиниці виміру</th>
            <th class="col-year" rowspan="2">2021<br><span style='font-size:11px;color:#475569;'>базовий рівень (факт)</span></th>
            <th class="col-year" rowspan="2">2024<br><span style='font-size:11px;color:#475569;'>звіт</span></th>
            <th class="col-year" rowspan="2">2025<br><span style='font-size:11px;color:#475569;'>факт</span></th>
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
        html += f"<td class='col-long'>{make_cell(row[5], 'fixed')}</td>"
        html += f"<td class='col-long'>{make_cell(row[6], 'fixed')}</td>"
        html += f"<td class='col-long'>{make_cell(row[7], 'fixed')}</td>"
        html += f"<td class='col-long'>{make_cell(row[8], 'fixed')}</td>"
        html += f"<td class='col-resp'>{make_cell(row[9], 'nowrap')}</td>"
        html += f"<td class='col-resp'>{make_cell(row[10], 'nowrap')}</td>"
        html += f"<td class='col-resp'>{make_cell(row[11], 'nowrap')}</td>"
        html += "</tr>"

    html += "</tbody></table></div>"

    st.markdown(clean_html(html), unsafe_allow_html=True)

def build_measure_rows(measures, monitoring_df, quarter_data, selected_years, selected_quarters):
    rows = []
    quarter_columns = get_quarter_columns(selected_years, selected_quarters)

    for _, measure in measures.iterrows():
        code = raw_value(measure.get("code", ""))
        status = get_measure_status(monitoring_df, code, selected_years, selected_quarters)

        row = [
            {"value": measure.get("code", ""), "mode": "nowrap"},
            {"value": strip_leading_code(measure.get("name", ""), code), "mode": "fixed"},
            {"value": measure.get("product_type", ""), "mode": "fixed"},
            {"value": measure.get("indicator", ""), "mode": "fixed"},
            {"value": measure.get("unit", ""), "mode": "fixed"},
            {"value": measure.get("base_2021", ""), "mode": "nowrap"},
            {"value": measure.get("fact_2024", ""), "mode": "nowrap"},
            {"value": measure.get("fact_2025", ""), "mode": "nowrap"},
            {"value": measure.get("target_2026", ""), "mode": "nowrap"},
            {"value": measure.get("target_2027", ""), "mode": "nowrap"},
            {"value": measure.get("target_2028", ""), "mode": "nowrap"},
            {"value": measure.get("source_global", ""), "mode": "fixed"},
            {"value": measure.get("source_national", ""), "mode": "fixed"},
            {"value": measure.get("resp_main", ""), "mode": "nowrap"},
            {"value": measure.get("resp_co_1", ""), "mode": "nowrap"},
            {"value": measure.get("resp_co_2", ""), "mode": "nowrap"},
            {"value": measure.get("deputy_minister_raw", ""), "mode": "nowrap"},
            {"value": measure.get("budget_kpkvk", ""), "mode": "nowrap"},
            {"value": measure.get("budget_2026_approved", ""), "mode": "nowrap"},
            {"value": measure.get("budget_2027_forecast", ""), "mode": "nowrap"},
            {"value": measure.get("budget_2028_forecast", ""), "mode": "nowrap"},
            {"value": measure.get("other_source", ""), "mode": "fixed"},
            {"value": measure.get("other_2026_plan", ""), "mode": "nowrap"},
            {"value": measure.get("other_2027_forecast", ""), "mode": "nowrap"},
            {"value": measure.get("other_2028_forecast", ""), "mode": "nowrap"}
        ]

        for year, quarter, _ in quarter_columns:
            key = f"{year}_{quarter}"
            item = quarter_data.get(code, {}).get(key, None)

            if item is None:
                row.append({
                    "value": "",
                    "status_class": "status-empty",
                    "mode": "nowrap"
                })
            else:
                row.append({
                    "value": item.get("value", ""),
                    "status_class": item.get("class", "status-empty"),
                    "mode": "nowrap"
                })

        row.append({
            "value": status,
            "status_class": visual_status_class(status),
            "mode": "nowrap"
        })

        rows.append(row)

    return rows


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
            <th class="col-year" rowspan="3">2021<br><span style='font-size:11px;color:#475569;'>базовий рівень (факт)</span></th>
            <th class="col-year" rowspan="3">2024<br><span style='font-size:11px;color:#475569;'>звіт</span></th>
            <th class="col-year" rowspan="3">2025<br><span style='font-size:11px;color:#475569;'>факт</span></th>
    """

    for year in [2026, 2027, 2028]:
        html += f"<th class='col-year' rowspan='3'>{year}<br><span style='font-size:11px;color:#475569;'>цільовий орієнтир для заходів на рік</span></th>"

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
            <th class="col-budget">2026<br><span style='font-size:11px;color:#475569;'>затверджено, млрд грн</span></th>
            <th class="col-budget">2027<br><span style='font-size:11px;color:#475569;'>прогноз, млрд грн</span></th>
            <th class="col-budget">2028<br><span style='font-size:11px;color:#475569;'>прогноз, млрд грн</span></th>
            <th class="col-budget-source">Джерело<br><span style='font-size:11px;color:#475569;'>МТД, кошти партнерів, інші небюджетні джерела</span></th>
            <th class="col-budget">2026<br><span style='font-size:11px;color:#475569;'>план</span></th>
            <th class="col-budget">2027<br><span style='font-size:11px;color:#475569;'>прогноз</span></th>
            <th class="col-budget">2028<br><span style='font-size:11px;color:#475569;'>прогноз</span></th>
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
                    html += "<td class='col-year status-empty'></td>"
                else:
                    value = item.get("value", "")
                    cell_class = item.get("class", "status-empty")
                    closeout_badge = (
                        " <span class='closeout-badge' title='Закрито вручну адміністратором'>🔒 Закрито вручну</span>"
                        if item.get("manual_closeout") else ""
                    )
                    html += f"<td class='col-year {cell_class}'>{make_cell(value, 'nowrap')}{closeout_badge}</td>"

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
        "selected_years_main": [2026],
        "selected_quarters_main": ["I"],
        "status_mode_main": "Усі заходи стратегічного плану",
        "selected_goal_codes_main": [],
        "selected_product_types_main": [],
        "search_main": ""
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_main_filters():
    st.session_state.ssp_filter = []
    st.session_state.selected_years_main = [2026]
    st.session_state.selected_quarters_main = ["I"]
    st.session_state.status_mode_main = "Усі заходи стратегічного плану"
    st.session_state.selected_goal_codes_main = []
    st.session_state.selected_product_types_main = []
    st.session_state.search_main = ""
    st.session_state.expand_all_goals = False
    st.session_state.applied_filters = {
        "ssp_filter": [],
        "selected_years_main": [2026],
        "selected_quarters_main": ["I"],
        "status_mode_main": "Усі заходи стратегічного плану",
        "selected_goal_codes_main": [],
        "selected_product_types_main": [],
        "search_main": ""
    }


def apply_main_filters_form():
    st.session_state.applied_filters = {
        "ssp_filter": st.session_state.ssp_filter,
        "selected_years_main": st.session_state.selected_years_main,
        "selected_quarters_main": st.session_state.selected_quarters_main,
        "status_mode_main": st.session_state.status_mode_main,
        "selected_goal_codes_main": st.session_state.selected_goal_codes_main,
        "selected_product_types_main": st.session_state.selected_product_types_main,
        "search_main": st.session_state.search_main
    }


def expand_all_main():
    st.session_state.expand_all_goals = True


def collapse_all_main():
    st.session_state.expand_all_goals = False

# ------------------------------------------------------------
# Load data
# ------------------------------------------------------------

df = load_strat_matrix()
monitoring_df = ensure_monitoring_columns(load_monitoring())
quarter_data = build_quarter_data(monitoring_df)

manual_closeouts = load_manual_closeouts()
for closeout_code, closeout_year, closeout_quarter in manual_closeouts:
    closeout_key = f"{closeout_year}_{closeout_quarter}"
    quarter_data.setdefault(closeout_code, {}).setdefault(closeout_key, {"value": "", "visual_status": "", "class": "status-empty"})
    quarter_data[closeout_code][closeout_key]["manual_closeout"] = True
    quarter_data[closeout_code][closeout_key]["class"] = "status-manual-closeout"

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
    "Лише на доопрацюванні",
    "Лише не враховані"
]

goal_options = build_goal_options(goals)

product_type_options = build_product_type_options(df)

deputy_options = sorted([
    "АРТЕМЕНКО Анна Ігорівна",
    "БАШЛИК Денис Олександрович",
    "БЕЗКАРАВАЙНИЙ Ігор Володимирович",
    "ВИСОЦЬКИЙ Тарас Миколайович",
    "КІНДРАТІВ Віталій Зіновійович",
    "КРАСНОЛУЦЬКИЙ Олександр Васильович",
    "МАРЧАК Дарія Миколаївна",
    "ОВЧАРЕНКО Ірина Іванівна",
    "ПЕРЕЛИГІН Єгор Євгенович",
    "ПЕТРУК Віталій Вікторович",
    "ПИВОВАРОВ Андрій Андрійович",
    "ЦИБОРТ Олександр Сергійович"
])


# ------------------------------------------------------------
# Header
# ------------------------------------------------------------

last_update = datetime.now().strftime("%d.%m.%Y %H:%M")

if not monitoring_df.empty and "submitted_at" in monitoring_df.columns:
    try:
        last_update_value = pd.to_datetime(monitoring_df["submitted_at"], errors="coerce").max()

        if pd.notna(last_update_value):
            last_update = last_update_value.strftime("%d.%m.%Y %H:%M")
    except Exception:
        pass

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
        <div class="system-status">
            <div class="status-pill">● Supabase: активний</div>
            <div class="status-pill">● Моніторинг: працює</div>
            <div class="status-pill">● Статус системи: стабільний</div>
            <div class="status-pill">● Оновлено: {last_update}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="cta-box">
        <div class="cta-title">Моніторинг і оцінка стратегічних результатів</div>
    </div>
    """,
    unsafe_allow_html=True
)

# ------------------------------------------------------------
# Примусове оновлення даних із бази
# ------------------------------------------------------------
# Дані Supabase автоматично оновлюються кожні 5 хвилин (спільний кеш для
# всіх користувачів). Кнопка потрібна для випадку "щойно погодили заявку —
# хочу побачити результат негайно, не чекаючи 5 хвилин".

refresh_col, refresh_note_col = st.columns([1.4, 3.6])

with refresh_col:
    if st.button(
        "🔄 Підтягнути свіжі дані з бази",
        help="Дані з бази оновлюються автоматично кожні 5 хвилин. "
             "Натисніть, якщо потрібно побачити щойно внесені зміни негайно.",
        use_container_width=True,
        key="force_refresh_supabase",
    ):
        load_monitoring.clear()
        try:
            from core.closeouts import load_manual_closeouts as _lmc
            _lmc.clear()
        except Exception:
            pass
        st.rerun()

with refresh_note_col:
    st.caption(
        "Дані моніторингу оновлюються автоматично кожні 5 хвилин. "
        "Кнопка миттєво підтягує останні подані та погоджені відомості."
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

reviewed_count = unique_measure_count(
    monitoring_df,
    lambda x: x["approval_status"].isin(["Погоджено", "Повернуто на доопрацювання"])
)

waiting_count = unique_measure_count(
    monitoring_df,
    lambda x: x.apply(lambda row: get_record_visual_status(row) == "На розгляді", axis=1)
)

returned_count = unique_measure_count(
    monitoring_df,
    lambda x: x["approval_status"] == "Повернуто на доопрацювання"
)

approved_count = unique_measure_count(
    monitoring_df,
    lambda x: x["approval_status"] == "Погоджено"
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
            <div class="legend-item">🟥 Не враховано — відомості не подані або перебувають на погодженні більше 5 робочих днів</div>
            <div class="legend-item">🟪 Закрито адміністратором — захід закрито вручну на підставі внутрішньої інформації чи іншого звітного документа (підтверджено супер-адміном); клітинка підсвічується фіолетовим із позначкою 🔒</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# Filters
# ------------------------------------------------------------

st.markdown(
    """
    <div class="filter-box">
        <div class="filter-title">Параметри відбору (для перегляду)</div>
        <div class="filter-subtitle">Основні параметри</div>
    """,
    unsafe_allow_html=True
)

with st.form("main_filters_form"):
    top_1, top_2, top_3, top_4 = st.columns([1.35, 0.8, 0.8, 1.15])

    with top_1:
        st.multiselect(
            "Індекс самостійного структурного підрозділу",
            all_ssp_indices,
            key="ssp_filter",
            placeholder="Оберіть індекс ССП"
        )

    with top_2:
        st.markdown(
            "<div style='font-size:13px;font-weight:900;color:#1e293b;margin-bottom:4px;'>Звітний період (рік, квартал)</div>",
            unsafe_allow_html=True
        )
        st.multiselect(
            "Рік",
            year_options,
            key="selected_years_main",
            placeholder="Рік",
            label_visibility="collapsed"
        )

    with top_3:
        st.markdown(
            "<div style='font-size:13px;font-weight:900;color:#1e293b;margin-bottom:4px;'>&nbsp;</div>",
            unsafe_allow_html=True
        )
        st.multiselect(
            "Квартал",
            quarter_options,
            key="selected_quarters_main",
            placeholder="Квартал",
            label_visibility="collapsed"
        )

    with top_4:
        st.selectbox(
            "Режим перегляду даних",
            status_options,
            key="status_mode_main"
        )

    st.markdown('<div class="filter-subtitle">Додаткові параметри</div>', unsafe_allow_html=True)

    bottom_1, bottom_2, bottom_3 = st.columns([1.1, 1.0, 1.8])

    with bottom_1:
        st.multiselect(
            "Стратегічна ціль",
            list(goal_options.values()),
            key="selected_goal_codes_main",
            placeholder="Оберіть стратегічну ціль"
        )

    with bottom_2:
        st.multiselect(
            "Тип продукту",
            product_type_options,
            key="selected_product_types_main",
            placeholder="Оберіть тип продукту"
        )

    with bottom_3:
        st.text_input(
            "Додаткові параметри пошуку (код завдання, заходу, ключові слова)",
            key="search_main",
            placeholder="Введіть код, назву або ключове слово"
        )

    form_spacer, form_submit_col = st.columns([2.4, 1])

    with form_spacer:
        st.empty()

    with form_submit_col:
        st.form_submit_button(
            "Застосувати параметри відбору",
            use_container_width=True,
            on_click=apply_main_filters_form
        )

reset_spacer, reset_col = st.columns([2.4, 1])

with reset_spacer:
    st.empty()

with reset_col:
    st.button(
        "Скинути фільтри",
        use_container_width=True,
        on_click=reset_main_filters
    )


# ------------------------------------------------------------
# Filter processing (за останньо застосованими параметрами)
# ------------------------------------------------------------

applied = st.session_state.applied_filters

selected_ssp_indices = applied["ssp_filter"]
selected_years = applied["selected_years_main"]
selected_quarters = applied["selected_quarters_main"]
selected_status_mode = applied["status_mode_main"]
selected_goal_labels = applied["selected_goal_codes_main"]
selected_product_types = applied["selected_product_types_main"]
search_query = applied["search_main"]

selected_goal_codes = [
    code
    for code, label in goal_options.items()
    if label in selected_goal_labels
]

if not selected_years:
    selected_years = [2026]

if not selected_quarters:
    selected_quarters = ["I", "II", "III", "IV"]

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

if selected_ssp_indices or raw_value(search_query):
    matching_goal_indicator_rows = df[
        (df["object_type"].isin(["goal", "goal_indicator"]))
        & df.apply(
            lambda row: (
                row_contains_selected_ssp(row, selected_ssp_indices)
                and indicator_row_matches_search(row, search_query)
            ),
            axis=1
        )
    ].copy()

    matching_task_indicator_rows = df[
        (df["object_type"].isin(["task", "task_indicator"]))
        & df.apply(
            lambda row: (
                row_contains_selected_ssp(row, selected_ssp_indices)
                and indicator_row_matches_search(row, search_query)
            ),
            axis=1
        )
    ].copy()

    indicator_goal_codes = set(matching_goal_indicator_rows["parent_goal_code"].astype(str).str.strip())
    direct_goal_codes = set(matching_goal_indicator_rows["code"].astype(str).str.strip())

    indicator_task_goal_codes = set(matching_task_indicator_rows["parent_goal_code"].astype(str).str.strip())
    indicator_task_codes = set(matching_task_indicator_rows["parent_task_code"].astype(str).str.strip())
    direct_task_codes = set(matching_task_indicator_rows["code"].astype(str).str.strip())

    filtered_goal_codes = (
        filtered_goal_codes
        | indicator_goal_codes
        | direct_goal_codes
        | indicator_task_goal_codes
    )

    filtered_task_codes = (
        filtered_task_codes
        | indicator_task_codes
        | direct_task_codes
    )

visible_goals = goals[goals["code"].astype(str).str.strip().isin(filtered_goal_codes)].copy()
visible_tasks = tasks_all[tasks_all["code"].astype(str).str.strip().isin(filtered_task_codes)].copy()

done_count, completion_percent = calculate_completion(filtered_measures)

approved_filtered = count_filtered_status(filtered_measures, "Погоджено")
waiting_filtered = count_filtered_status(filtered_measures, "На розгляді")
not_counted_filtered = count_filtered_status(filtered_measures, "Не враховано")
risk_count = not_counted_filtered

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

if not filtered_measures.empty:
    st.download_button(
        "Завантажити в Excel",
        data=build_export_excel(filtered_measures, quarter_data, selected_years, selected_quarters),
        file_name="strategic_monitoring_export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # ── Повне вивантаження: АБСОЛЮТНО ВСІ колонки + квартальні дані (правка №15) ──
    with st.expander("📦 Повне вивантаження (усі колонки матриці + квартальні дані за обраними фільтрами)"):
        st.caption(
            "Excel з усіма колонками стратегічної матриці для відфільтрованих заходів "
            "(індикатори, базові/фактичні/цільові значення, стратегічні орієнтири, джерела, "
            "виконавці, дати, КПКВК і фінансування) + по кожному обраному року/кварталу — "
            "подане значення, статус виконання, статус погодження та позначка ручного закриття."
        )

        def build_full_export_excel():
            _col_labels = {
                "code": "Код", "name": "Назва", "type_marker": "Тип рядка",
                "product_type": "Тип продукту", "indicator": "Індикатор",
                "unit": "Одиниці виміру", "base_2021": "2021 (базовий)",
                "fact_2024": "2024 (звіт)", "fact_2025": "2025 (факт)",
                "target_2026": "2026 (цільовий орієнтир)",
                "target_2027": "2027 (цільовий орієнтир)",
                "target_2028": "2028 (цільовий орієнтир)",
                "strategic_target_2028": "Стратегічний орієнтир 2028",
                "strategic_target_2034": "Стратегічний орієнтир 2034",
                "source_global": "Глобальний рівень", "source_national": "Національний рівень",
                "resp_main": "Головний виконавець", "resp_co_1": "Співвиконавець 1",
                "resp_co_2": "Співвиконавець 2", "deputy_minister_raw": "Заступник Міністра",
                "measure_period_years": "Період (років)",
                "measure_start_date": "Початкова дата", "measure_end_date": "Кінцева дата",
                "budget_kpkvk": "КПКВК", "budget_2026_approved": "ДБ 2026 (затверджено)",
                "budget_2027_forecast": "ДБ 2027 (прогноз)", "budget_2028_forecast": "ДБ 2028 (прогноз)",
                "other_source": "Інше джерело", "other_2026_plan": "Інші 2026 (план)",
                "other_2027_forecast": "Інші 2027 (прогноз)", "other_2028_forecast": "Інші 2028 (прогноз)",
                "object_type": "Тип об'єкта", "parent_goal_code": "Код СЦ", "parent_task_code": "Код завдання",
            }
            _skip = {"type_marker", "department"}
            _full = filtered_measures.copy()
            _cols = [c for c in _full.columns if c not in _skip and not str(c).startswith("_")]
            _full = _full[_cols].rename(columns={c: _col_labels.get(c, c) for c in _cols})

            # Квартальні дані за обраними фільтрами року/кварталу
            _codes = filtered_measures["code"].astype(str).str.strip().tolist()
            _mon = monitoring_df.copy()
            for _c in ["strat_code", "year", "quarter", "numeric_value", "status", "approval_status"]:
                if _c not in _mon.columns:
                    _mon[_c] = ""
            for _y in selected_years:
                for _q in selected_quarters:
                    _sub = _mon[
                        (_mon["year"].astype(str).str.strip() == str(_y))
                        & (_mon["quarter"].astype(str).str.strip() == str(_q))
                    ]
                    _by_code = {}
                    for _, _r in _sub.iterrows():
                        _by_code.setdefault(raw_value(_r.get("strat_code")), _r)
                    _prefix = f"{_q} кв. {_y}"
                    _full[f"{_prefix} — значення"] = [
                        raw_value(_by_code.get(c, {}).get("numeric_value", "")) if c in _by_code else ""
                        for c in _codes
                    ]
                    _full[f"{_prefix} — статус виконання"] = [
                        raw_value(_by_code.get(c, {}).get("status", "")) if c in _by_code else ""
                        for c in _codes
                    ]
                    _full[f"{_prefix} — статус погодження"] = [
                        raw_value(_by_code.get(c, {}).get("approval_status", "")) if c in _by_code else ""
                        for c in _codes
                    ]
                    _full[f"{_prefix} — закрито адміном"] = [
                        "Так" if (c, str(_y), str(_q)) in manual_closeouts else ""
                        for c in _codes
                    ]

            _buf = io.BytesIO()
            with pd.ExcelWriter(_buf, engine="xlsxwriter") as _writer:
                _full.to_excel(_writer, index=False, sheet_name="Повні дані")
                _params = pd.DataFrame({
                    "Параметр": ["Роки", "Квартали", "ССП", "Режим", "Сформовано"],
                    "Значення": [
                        years_label, quarters_label, ssp_label, selected_status_mode,
                        datetime.now().strftime("%d.%m.%Y %H:%M"),
                    ],
                })
                _params.to_excel(_writer, index=False, sheet_name="Параметри вивантаження")
            return _buf.getvalue()

        st.download_button(
            "⬇️ Завантажити повний Excel",
            data=build_full_export_excel(),
            file_name=f"SP_повне_вивантаження_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="full_export_download",
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
            search_query
        )

        if goal_filtered_measures.empty and not goal_indicators:
            continue

        goal_task_codes = set(goal_filtered_measures["parent_task_code"].astype(str).str.strip()) if not goal_filtered_measures.empty else set()
        tasks = tasks_all[tasks_all["code"].astype(str).str.strip().isin(goal_task_codes)].copy()

        goal_done, goal_percent = calculate_completion(goal_filtered_measures)

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
                render_indicator_table(goal_indicators)

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
                    search_query
                )

                if task_measures.empty and not task_indicators:
                    continue

                task_done, task_percent = calculate_completion(task_measures)

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
                        render_indicator_table(task_indicators)

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

st.markdown(
    """
    <a class="submit-main-button" href="/~/+/Моніторинг_виконання" target="_self">
        🖊️ Подати відомості
    </a>
    """,
    unsafe_allow_html=True
)

st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------
# Footer
# ------------------------------------------------------------

st.markdown(
    """
    <div class="footer">
        <strong>Розроблено департаментом стратегічного планування та макроекономічного прогнозування</strong><br>
        Версія DEMO 1.4 | 2026 | Внутрішня система моніторингу стратегічного плану
    </div>
    """,
    unsafe_allow_html=True
)
