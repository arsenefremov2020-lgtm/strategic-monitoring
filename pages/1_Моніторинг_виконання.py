import re
from datetime import datetime, timezone
from html import escape

import pandas as pd
import streamlit as st
from supabase import create_client


# ------------------------------------------------------------
# Page config
# ------------------------------------------------------------

st.set_page_config(
    page_title="Моніторинг (внесення відомостей)",
    layout="wide"
)

FILE_PATH = "Під моніторинг СП.xlsx"
SHEET_NAME = "Страт_матриця"

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)


# ------------------------------------------------------------
# CSS
# ------------------------------------------------------------

st.markdown(
    """
<style>
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
.note-box {
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

.user-box {
    border-radius: 18px;
    padding: 22px 26px 24px 26px;
    margin: 18px 0 18px 0;
    background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(241,246,253,0.98));
    border: 1px solid #cbd8ea;
    box-shadow: 0 10px 24px rgba(15,23,42,0.07);
}

.user-title,
.flow-title,
.summary-title,
.filter-title,
.guide-title,
.table-title {
    color: #0f172a;
    font-weight: 900;
}

.user-title {
    font-size: 20px;
    margin-bottom: 14px;
}

.flow-box {
    border-radius: 16px;
    padding: 18px 20px;
    margin: 18px 0;
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

.summary-box {
    border-radius: 16px;
    padding: 18px 20px;
    margin: 18px 0;
}

.summary-title {
    font-size: 20px;
    margin-bottom: 12px;
}

.summary-grid {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
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
    margin-bottom: 10px;
}

.filter-legend {
    color: #475569;
    font-size: 14px;
    line-height: 1.55;
    margin-bottom: 16px;
}

.info-grid {
    display: grid;
    grid-template-columns: 1fr;
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
    color: #0f172a;
    font-size: 16px;
    font-weight: 900;
    margin-bottom: 8px;
}

.instruction-item {
    margin-bottom: 7px;
    font-size: 14px;
}

.note-box {
    border-radius: 10px;
    padding: 13px 17px;
    color: #374151;
    font-size: 14px;
    margin: 12px 0 18px 0;
}

.table-title {
    font-size: 20px;
    margin: 24px 0 12px 0;
}

div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    background-color: #d7eaff !important;
    border: 1px solid #8fb3df !important;
    border-radius: 10px !important;
    min-height: 43px !important;
    box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.08) !important;
}

div[data-testid="stSelectbox"] label,
div[data-testid="stTextInput"] label,
div[data-testid="stTextArea"] label {
    font-weight: 750 !important;
    color: #1e293b !important;
}

.html-table-wrap {
    width: 100%;
    max-width: 1280px;
    margin: 0 auto 26px auto;
    border-radius: 14px;
    border: 1px solid #cbd5e1;
    background: rgba(255,255,255,0.96);
    box-shadow: 0 8px 22px rgba(15,23,42,0.06);
    overflow-x: auto;
    overflow-y: auto;
    max-height: 640px;
}

.ref-table {
    border-collapse: collapse;
    width: max-content;
    min-width: 100%;
    table-layout: fixed;
    font-size: 12px;
    color: #0f172a;
}

.ref-table th {
    background: #e8eef7;
    border: 1px solid #cbd5e1;
    padding: 10px 8px;
    text-align: center;
    vertical-align: middle;
    font-weight: 900;
    line-height: 1.25;
    white-space: normal;
}

.ref-table td {
    border: 1px solid #cbd5e1;
    padding: 10px 8px;
    text-align: center;
    vertical-align: middle;
    line-height: 1.35;
    background: rgba(255,255,255,0.96);
    white-space: normal;
    word-break: normal;
    overflow-wrap: break-word;
}

.ref-table tbody tr:nth-child(even) td {
    background: #f8fafc;
}

.ref-table .col-code {
    width: 80px;
    min-width: 80px;
}

.ref-table .col-measure {
    width: 370px;
    min-width: 370px;
    text-align: left;
}

.ref-table .col-product {
    width: 180px;
    min-width: 180px;
}

.ref-table .col-indicator {
    width: 360px;
    min-width: 360px;
    text-align: left;
}

.ref-table .col-unit {
    width: 180px;
    min-width: 180px;
}

.ref-table .col-year {
    width: 130px;
    min-width: 130px;
}

.ref-table .col-quarter {
    width: 130px;
    min-width: 130px;
}

.ref-table .col-source {
    width: 300px;
    min-width: 300px;
}

.ref-table .col-resp {
    width: 210px;
    min-width: 210px;
}

.ref-table .col-period {
    width: 160px;
    min-width: 160px;
}

.ref-table .col-date {
    width: 150px;
    min-width: 150px;
}

.edit-table-wrap {
    max-width: 1280px;
    margin: 0 auto 20px auto;
}

div[data-testid="stDataEditor"] {
    border-radius: 12px !important;
    overflow: hidden !important;
}

div[data-testid="stDataEditor"] div[role="gridcell"],
div[data-testid="stDataEditor"] div[role="columnheader"],
div[data-testid="stDataEditor"] div[role="gridcell"] div,
div[data-testid="stDataEditor"] div[role="columnheader"] div,
div[data-testid="stDataEditor"] div[role="gridcell"] p,
div[data-testid="stDataEditor"] div[role="columnheader"] p,
div[data-testid="stDataEditor"] div[role="gridcell"] span,
div[data-testid="stDataEditor"] div[role="columnheader"] span {
    text-align: center !important;
    justify-content: center !important;
    align-items: center !important;
}

div[data-testid="stDataEditor"] [data-testid="stCheckbox"] {
    display: flex !important;
    justify-content: center !important;
}

div[data-testid="stButton"] > button {
    width: 100%;
    min-height: 68px;
    background: linear-gradient(135deg, #dc2626 0%, #f97316 52%, #facc15 100%) !important;
    color: #ffffff !important;
    border: 0 !important;
    border-radius: 18px !important;
    font-size: 20px !important;
    font-weight: 950 !important;
    letter-spacing: 0.3px !important;
    box-shadow: 0 18px 34px rgba(249,115,22,0.34), inset 0 1px 0 rgba(255,255,255,0.25) !important;
}

div[data-testid="stButton"] > button:hover {
    filter: brightness(1.05);
    transform: translateY(-1px);
}

.final-footer {
    text-align: center;
    color: #475569;
    font-size: 13px;
    margin-top: 48px;
    padding-top: 24px;
    border-top: 1px solid #cbd5e1;
    line-height: 1.7;
}

.final-footer-main {
    font-weight: 700;
    color: #334155;
}

.final-footer-sub {
    color: #64748b;
    font-size: 12px;
}

@media (max-width: 1100px) {
    .summary-grid,
    .flow-steps {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}
</style>
""",
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def raw_value(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value).strip()


def clean_value(value):
    return escape(raw_value(value))


def is_empty_or_nd(value):
    text = raw_value(value).lower().replace(" ", "")
    return text in {"", "н.д.", "нд", "nan", "none", "-", "—"}


def strip_leading_code(text, code):
    value = raw_value(text)
    code_value = raw_value(code)

    if code_value and value.startswith(code_value):
        value = value[len(code_value):].lstrip(" .—-–|:")

    return value


def split_ssp_values(value):
    text = raw_value(value)
    if not text:
        return []
    return re.findall(r"\d+", text)


def value_contains_ssp(value, selected_index):
    if not selected_index:
        return True
    return selected_index in split_ssp_values(value)


def make_summary_card(label, value):
    return (
        f'<div class="summary-card">'
        f'<div class="summary-label">{escape(str(label))}</div>'
        f'<div class="summary-value">{escape(str(value))}</div>'
        f'</div>'
    )


def quarter_to_q_label(quarter):
    mapping = {
        "I": "Q1",
        "II": "Q2",
        "III": "Q3",
        "IV": "Q4"
    }
    return mapping.get(raw_value(quarter), raw_value(quarter))


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


def has_target_for_year(row, year):
    col = f"target_{year}"
    if col not in row:
        return True
    return not is_empty_or_nd(row.get(col, ""))


def get_record_visual_status(row):
    approval = raw_value(row.get("approval_status", ""))

    if approval == "Погоджено":
        return "Погоджено"

    if approval == "Повернуто на доопрацювання":
        return "Повернуто на доопрацювання"

    if approval in {"Очікує погодження", "На розгляді", "Очікує розгляду"}:
        return "Очікує розгляду"

    return "Не враховано"


def subset_monitoring_for_selection(monitoring_df, selected_codes, selected_year, selected_quarter):
    if monitoring_df.empty:
        return pd.DataFrame()

    data = monitoring_df.copy()
    data["strat_code_clean"] = data["strat_code"].astype(str).str.strip()
    data["year_clean"] = data["year"].astype(str).str.strip()
    data["quarter_clean"] = data["quarter"].astype(str).str.strip()

    return data[
        data["strat_code_clean"].isin([str(code).strip() for code in selected_codes])
        & (data["year_clean"] == str(selected_year))
        & (data["quarter_clean"] == str(selected_quarter))
    ].copy()


def unique_measure_count(data):
    if data.empty or "strat_code" not in data.columns:
        return 0
    return data["strat_code"].astype(str).str.strip().replace("", pd.NA).dropna().nunique()


def render_reference_table(data, selected_year, quarter_label):
    target_col = f"target_{selected_year}"

    html = """
    <div class="html-table-wrap">
        <table class="ref-table">
            <thead>
                <tr>
                    <th class="col-code" rowspan="2">Код</th>
                    <th class="col-measure" rowspan="2">Захід</th>
                    <th class="col-product" rowspan="2">Тип продукту</th>
                    <th class="col-indicator" rowspan="2">Індикатор</th>
                    <th class="col-unit" rowspan="2">Одиниці виміру</th>
                    <th class="col-year" rowspan="2">2021<br>базовий рівень<br>(факт)</th>
                    <th class="col-year" rowspan="2">2024<br>звіт</th>
                    <th class="col-year" rowspan="2">2025<br>факт</th>
                    <th class="col-year" rowspan="2">""" + escape(str(selected_year)) + """<br>цільовий орієнтир<br>для заходів на рік</th>
                    <th class="col-quarter" rowspan="2">""" + escape(str(quarter_label)) + """</th>
                    <th colspan="2">Підстава для включення до стратегічного плану</th>
                    <th colspan="3">Відповідальні самостійні структурні підрозділи</th>
                    <th class="col-period" rowspan="2">Період дії заходу<br>в межах планового<br>періоду, років</th>
                    <th class="col-date" rowspan="2">Початкова дата</th>
                    <th class="col-date" rowspan="2">Кінцева дата</th>
                </tr>
                <tr>
                    <th class="col-source">Глобальний рівень</th>
                    <th class="col-source">Національний рівень</th>
                    <th class="col-resp">Головний</th>
                    <th class="col-resp">Співвиконавець 1</th>
                    <th class="col-resp">Співвиконавець 2</th>
                </tr>
            </thead>
            <tbody>
    """

    for _, row in data.iterrows():
        code = raw_value(row.get("code", ""))
        name = strip_leading_code(row.get("name", ""), code)

        html += f"""
            <tr>
                <td class="col-code">{clean_value(code)}</td>
                <td class="col-measure">{clean_value(name)}</td>
                <td class="col-product">{clean_value(row.get("product_type", ""))}</td>
                <td class="col-indicator">{clean_value(row.get("indicator", ""))}</td>
                <td class="col-unit">{clean_value(row.get("unit", ""))}</td>
                <td class="col-year">{clean_value(row.get("base_2021", ""))}</td>
                <td class="col-year">{clean_value(row.get("fact_2024", ""))}</td>
                <td class="col-year">{clean_value(row.get("fact_2025", ""))}</td>
                <td class="col-year">{clean_value(row.get(target_col, ""))}</td>
                <td class="col-quarter">—</td>
                <td class="col-source">{clean_value(row.get("source_global", ""))}</td>
                <td class="col-source">{clean_value(row.get("source_national", ""))}</td>
                <td class="col-resp">{clean_value(row.get("resp_main", ""))}</td>
                <td class="col-resp">{clean_value(row.get("resp_co_1", ""))}</td>
                <td class="col-resp">{clean_value(row.get("resp_co_2", ""))}</td>
                <td class="col-period">{clean_value(row.get("measure_period_years", ""))}</td>
                <td class="col-date">{clean_value(row.get("measure_start_date", ""))}</td>
                <td class="col-date">{clean_value(row.get("measure_end_date", ""))}</td>
            </tr>
        """

    html += """
            </tbody>
        </table>
    </div>
    """

    st.markdown(html, unsafe_allow_html=True)


# ------------------------------------------------------------
# Data loading
# ------------------------------------------------------------

@st.cache_data
def load_strat_matrix():
    source_df = pd.read_excel(
        FILE_PATH,
        sheet_name=SHEET_NAME,
        header=None,
        engine="openpyxl"
    )

    data = source_df.iloc[7:].copy()

    def safe_col(index):
        if index < source_df.shape[1]:
            return data.iloc[:, index]
        return pd.Series([""] * len(data), index=data.index)

    def find_col_by_keywords(keywords):
        keywords = [keyword.lower() for keyword in keywords]
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

        "source_global": safe_col(15),
        "source_national": safe_col(16),

        "resp_main": safe_col(17),
        "resp_co_1": safe_col(18),
        "resp_co_2": safe_col(19),

        "measure_period_years": safe_keyword_col(["період", "років"]),
        "measure_start_date": safe_keyword_col(["початкова", "дата"]),
        "measure_end_date": safe_keyword_col(["кінцева", "дата"]),

        "department": safe_col(17)
    })

    result = result.dropna(subset=["code"])
    result["code"] = result["code"].astype(str).str.strip()
    result["type_marker"] = result["type_marker"].astype(str).str.strip()

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


@st.cache_data(ttl=60)
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


# ------------------------------------------------------------
# Load data
# ------------------------------------------------------------

df = load_strat_matrix()
monitoring_df = ensure_monitoring_columns(load_monitoring())

all_measures = df[df["object_type"] == "measure"].copy()

all_ssp_indices = sorted(
    {
        index
        for _, row in all_measures.iterrows()
        for index in split_ssp_values(row.get("resp_main", ""))
    },
    key=lambda x: int(x) if str(x).isdigit() else 9999
)

year_options = list(range(2026, 2035))
quarter_options = ["I", "II", "III", "IV"]

execution_status_options = [
    "Виконано",
    "Частково виконано",
    "Не виконано",
    "Не настав час",
    "Втратило актуальність"
]


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
    """
    <div class="header-box">
        <div class="header-title">Моніторинг стратегічних результатів</div>
        <div class="header-subtitle">
            Кабінет користувача призначений для щоквартального внесення відомостей 
            (до 15 числа місяця, наступного за звітним кварталом) з метою формування 
            результатів моніторингу виконання заходів, оцінки прогресу досягнення 
            стратегічних цілей, контролю статусу виконання заходів, своєчасного 
            виявлення відхилень і ризиків, формування коригувальних дій, а також 
            створення моніторингових звітів та інфографічних матеріалів.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# User info fields
# ------------------------------------------------------------

st.markdown(
    """
    <div class="user-box">
        <div class="user-title">Контактна інформація відповідальної особи</div>
    """,
    unsafe_allow_html=True
)

u1, u2, u3 = st.columns([1.2, 0.85, 1.1])

with u1:
    responsible_person = st.text_input(
        "ПІБ відповідальної особи",
        key="responsible_person_input",
        placeholder="Введіть ПІБ"
    )

with u2:
    responsible_phone = st.text_input(
        "Контактний номер телефону",
        key="responsible_phone_input",
        placeholder="+380..."
    )

with u3:
    responsible_email = st.text_input(
        "Електронна пошта відповідальної особи",
        key="responsible_email_input",
        placeholder="name@me.gov.ua"
    )

st.markdown("</div>", unsafe_allow_html=True)


# ------------------------------------------------------------
# Flow block
# ------------------------------------------------------------

st.markdown(
    """
    <div class="flow-box">
        <div class="flow-title">Маршрут подання відомостей</div>
        <div class="flow-steps">
            <div class="flow-step">1. Вибір параметрів</div>
            <div class="flow-step">2. Перегляд</div>
            <div class="flow-step">3. Позначення заходу</div>
            <div class="flow-step">4. Заповнення</div>
            <div class="flow-step">5. Відправлення на розгляд</div>
            <div class="flow-step">6. Погодження</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# User guide / filters
# ------------------------------------------------------------

st.markdown(
    """
    <div class="filter-box">
        <div class="filter-title">Гід користувача</div>
        <div class="filter-legend">
            Оберіть індекс самостійного структурнго підрозділу та звітний період. 
            Система автоматично відобразить лише ті заходи, за якими самостійний 
            структурний підрозділ, визначений головним виконавцем.
        </div>
        <div class="info-grid">
            <div class="info-card">
                <div class="info-card-title">Інструкція користувача</div>
                <div class="instruction-item">1. Перегляньте довідкову таблицю заходів</div>
                <div class="instruction-item">2. У таблиці внесення відомостей позначте у колонці «Подати» заходи, за якими подається інформація</div>
                <div class="instruction-item">3. Внесіть фактичні звітні відомості: показник за квартал, стан виконання, короткий опис прогресу та інформацію щодо ризиків</div>
                <div class="instruction-item">4. Натисніть «Подати на розгляд»</div>
                <div class="instruction-item">5. Після розгляду відомостей координатор направить інформацію на погодження (відповідальний виконавець, керівник ССП)</div>
            </div>
        </div>
    """,
    unsafe_allow_html=True
)

f1, f2, f3, f4 = st.columns([1.25, 0.7, 0.7, 1.6])

with f1:
    selected_ssp_index = st.selectbox(
        "Індекс самостійного структурного підрозділу",
        [""] + all_ssp_indices,
        key="ssp_submit_filter",
        placeholder="Оберіть індекс ССП"
    )

with f2:
    selected_year = st.selectbox(
        "Рік",
        year_options,
        index=0,
        key="year_submit_filter"
    )

with f3:
    selected_quarter = st.selectbox(
        "Квартал",
        quarter_options,
        index=0,
        key="quarter_submit_filter"
    )

with f4:
    search_query = st.text_input(
        "Додаткові параметри пошуку (код завдання, заходу, ключові слова)",
        key="search_submit_filter",
        placeholder="Введіть код, назву або ключове слово"
    )

st.markdown("</div>", unsafe_allow_html=True)


# ------------------------------------------------------------
# Filtering
# ------------------------------------------------------------

filtered_measures = all_measures.copy()

if selected_ssp_index:
    filtered_measures = filtered_measures[
        filtered_measures["resp_main"].apply(lambda value: value_contains_ssp(value, selected_ssp_index))
    ]

filtered_measures = filtered_measures[
    filtered_measures.apply(lambda row: row_matches_search(row, search_query), axis=1)
]

filtered_measures = filtered_measures[
    filtered_measures.apply(lambda row: has_target_for_year(row, selected_year), axis=1)
]

filtered_codes = filtered_measures["code"].astype(str).str.strip().tolist()
monitoring_selected = subset_monitoring_for_selection(
    monitoring_df,
    filtered_codes,
    selected_year,
    selected_quarter
)


# ------------------------------------------------------------
# Selection parameters summary
# ------------------------------------------------------------

total_count = len(filtered_measures)
submitted_count = unique_measure_count(monitoring_selected)

if monitoring_selected.empty:
    reviewed_count = 0
    waiting_count = 0
    returned_count = 0
    approved_count = 0
else:
    monitoring_selected["visual_status"] = monitoring_selected.apply(get_record_visual_status, axis=1)

    reviewed_count = unique_measure_count(
        monitoring_selected[
            monitoring_selected["visual_status"].isin(["Погоджено", "Повернуто на доопрацювання"])
        ]
    )

    waiting_count = unique_measure_count(
        monitoring_selected[
            monitoring_selected["visual_status"] == "Очікує розгляду"
        ]
    )

    returned_count = unique_measure_count(
        monitoring_selected[
            monitoring_selected["visual_status"] == "Повернуто на доопрацювання"
        ]
    )

    approved_count = unique_measure_count(
        monitoring_selected[
            monitoring_selected["visual_status"] == "Погоджено"
        ]
    )

summary_cards = "".join([
    make_summary_card("Заходів усього", total_count),
    make_summary_card("Поданих відомостей за заходами", submitted_count),
    make_summary_card("Розглянуто", reviewed_count),
    make_summary_card("Очікує розгляду", waiting_count),
    make_summary_card("Повернуто на доопрацювання", returned_count),
    make_summary_card("Погоджено", approved_count)
])

st.markdown(
    f"""
    <div class="summary-box">
        <div class="summary-title">Параметри відбору</div>
        <div class="summary-grid">{summary_cards}</div>
    </div>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# Status notes
# ------------------------------------------------------------

st.markdown(
    """
    <div class="note-box">
        <strong>Редагування звітних даних активне.</strong><br>
        <strong>Відомості відображаються автоматично.</strong><br>
        <strong>Перед поданням система виконає перевірку коректності та повноти даних.</strong>
    </div>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# Reference HTML table
# ------------------------------------------------------------

quarter_label = f"{quarter_to_q_label(selected_quarter)} {selected_year}"
target_col = f"target_{selected_year}"

if target_col not in filtered_measures.columns:
    filtered_measures[target_col] = ""

st.markdown('<div class="table-title">Заходи</div>', unsafe_allow_html=True)

if filtered_measures.empty:
    st.info("За обраними параметрами заходів не знайдено.")
    edited_df = pd.DataFrame()
else:
    render_reference_table(filtered_measures, selected_year, quarter_label)


# ------------------------------------------------------------
# Editor table for submission only
# ------------------------------------------------------------

editor_rows = []

for _, row in filtered_measures.iterrows():
    code = raw_value(row.get("code", ""))

    editor_rows.append({
        "Подати": False,
        "Код": code,
        "Захід": strip_leading_code(row.get("name", ""), code),
        quarter_label: "",
        "Статус виконання": "",
        "Опис прогресу": "",
        "Ризики / проблеми / відхилення": ""
    })

editor_df = pd.DataFrame(editor_rows)

if not editor_df.empty:
    st.markdown('<div class="table-title">Внесення відомостей</div>', unsafe_allow_html=True)
    st.markdown('<div class="edit-table-wrap">', unsafe_allow_html=True)

    dynamic_height = min(620, max(180, 92 + len(editor_df) * 78))

    edited_df = st.data_editor(
        editor_df,
        key=f"monitoring_editor_{selected_ssp_index}_{selected_year}_{selected_quarter}_{search_query}",
        use_container_width=True,
        hide_index=True,
        height=dynamic_height,
        row_height=74,
        num_rows="fixed",
        column_config={
            "Подати": st.column_config.CheckboxColumn(
                "Подати",
                help="Позначте заходи, за якими подається інформація",
                width=92
            ),
            "Код": st.column_config.TextColumn(
                "Код",
                disabled=True,
                width=90
            ),
            "Захід": st.column_config.TextColumn(
                "Захід",
                disabled=True,
                width=390
            ),
            quarter_label: st.column_config.TextColumn(
                quarter_label,
                help="Фактичне значення за обраний квартал",
                width=150
            ),
            "Статус виконання": st.column_config.SelectboxColumn(
                "Статус виконання",
                options=execution_status_options,
                required=False,
                width=190
            ),
            "Опис прогресу": st.column_config.TextColumn(
                "Опис прогресу",
                help="Коротко опишіть фактичний прогрес за звітний квартал",
                width=330
            ),
            "Ризики / проблеми / відхилення": st.column_config.TextColumn(
                "Ризики / проблеми / відхилення",
                help="Якщо ризиків немає, зазначте: відсутні",
                width=330
            )
        },
        disabled=[
            "Код",
            "Захід"
        ]
    )

    st.markdown('</div>', unsafe_allow_html=True)
else:
    edited_df = pd.DataFrame()


# ------------------------------------------------------------
# Submission validation and submit
# ------------------------------------------------------------

def validate_submission():
    errors = []

    if not raw_value(responsible_person):
        errors.append("Заповніть ПІБ відповідальної особи")

    if not raw_value(responsible_phone):
        errors.append("Заповніть контактний номер телефону")

    if not raw_value(responsible_email):
        errors.append("Заповніть електронну пошту відповідальної особи")

    if edited_df.empty:
        errors.append("Позначте хоча б один захід для подання")
        return errors

    selected_rows = edited_df[edited_df["Подати"] == True].copy()

    if selected_rows.empty:
        errors.append("Позначте хоча б один захід для подання")
        return errors

    for _, row in selected_rows.iterrows():
        code = raw_value(row.get("Код", ""))

        required_values = [
            row.get(quarter_label, ""),
            row.get("Статус виконання", ""),
            row.get("Опис прогресу", ""),
            row.get("Ризики / проблеми / відхилення", "")
        ]

        if any(not raw_value(value) for value in required_values):
            errors.append(f"Заповніть усі обов’язкові поля для заходу {code}")

    return errors


submit_clicked = st.button("Подати на розгляд", use_container_width=True)

if submit_clicked:
    validation_errors = validate_submission()

    if validation_errors:
        for error in validation_errors:
            st.error(error)
    else:
        selected_rows = edited_df[edited_df["Подати"] == True].copy()
        submitted_at = datetime.now(timezone.utc).isoformat()

        payload = []

        for _, row in selected_rows.iterrows():
            code = raw_value(row.get("Код", ""))

            reference_row = filtered_measures[
                filtered_measures["code"].astype(str).str.strip() == code
            ]

            if reference_row.empty:
                start_date = ""
                end_date = ""
            else:
                start_date = raw_value(reference_row.iloc[0].get("measure_start_date", ""))
                end_date = raw_value(reference_row.iloc[0].get("measure_end_date", ""))

            payload.append({
                "department": raw_value(selected_ssp_index),
                "year": str(selected_year),
                "quarter": raw_value(selected_quarter),
                "approval_status": "Очікує погодження",
                "status": raw_value(row.get("Статус виконання", "")),
                "strat_code": code,
                "responsible_person": raw_value(responsible_person),
                "phone": raw_value(responsible_phone),
                "email": raw_value(responsible_email),
                "numeric_value": raw_value(row.get(quarter_label, "")),
                "progress_text": raw_value(row.get("Опис прогресу", "")),
                "risks": raw_value(row.get("Ризики / проблеми / відхилення", "")),
                "file_names": "",
                "file_urls": "",
                "admin_comment": "",
                "start_date": start_date,
                "end_date": end_date,
                "submitted_at": submitted_at
            })

        try:
            supabase.table("monitoring_requests").insert(payload).execute()
            st.cache_data.clear()

            st.success("Відомості успішно подано на розгляд")
            st.info(
                "Відомості опрацьовуються координатором. "
                "Інформація про подальший статус відобразиться в особистому кабінеті."
            )

        except Exception as error:
            st.error(f"Не вдалося подати відомості. Технічна помилка: {error}")


# ------------------------------------------------------------
# Footer
# ------------------------------------------------------------

st.markdown(
    """
    <div class="final-footer">
        <div class="final-footer-main">
            Розроблено департаментом стратегічного планування та макроекономічного прогнозування
        </div>
        <div class="final-footer-sub">
            Версія DEMO 1.4 | 2026 | Внутрішня система моніторингу стратегічного плану
        </div>
    </div>
    """,
    unsafe_allow_html=True
)
