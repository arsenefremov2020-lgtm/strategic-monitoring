import streamlit as st
import pandas as pd
from supabase import create_client
from html import escape
from datetime import datetime

st.set_page_config(page_title="Стратегічний план", layout="wide")

FILE_PATH = "Під моніторинг СП.xlsx"
SHEET_NAME = "Страт_матриця"

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

st.markdown("""
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

.header-box {
    background: rgba(255,255,255,0.92);
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 18px;
    box-shadow: 0 8px 24px rgba(15,23,42,0.06);
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
    margin-bottom: 6px;
}

.cta-text {
    font-size: 15px;
    opacity: 0.97;
}

div[data-testid="stPageLink"] a {
    background: linear-gradient(90deg, #15803d, #16a34a) !important;
    color: white !important;
    border-radius: 12px !important;
    padding: 15px 20px !important;
    font-weight: 850 !important;
    text-decoration: none !important;
    border: none !important;
    width: 100%;
    justify-content: center;
    box-shadow: 0 6px 14px rgba(22,163,74,0.20);
}

.flow-box {
    background: white;
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 18px;
    margin: 18px 0;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

.flow-title {
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 10px;
}

.flow-steps {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    color: #334155;
    font-size: 14px;
}

.flow-step {
    padding: 8px 12px;
    border-radius: 999px;
    background: #f1f5f9;
    border: 1px solid #d8dee9;
}

.info-grid {
    display: grid;
    grid-template-columns: 1.2fr 1fr;
    gap: 14px;
    margin-bottom: 20px;
}

.info-card {
    background: rgba(255,255,255,0.92);
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 17px 19px;
    color: #1f2937;
    box-shadow: 0 4px 14px rgba(15,23,42,0.045);
}

.info-card-title {
    font-size: 16px;
    font-weight: 900;
    margin-bottom: 8px;
    color: #0f172a;
}

.legend-item {
    margin-bottom: 6px;
    font-size: 14px;
}

.filter-box {
    background: rgba(255,255,255,0.94);
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 18px 20px;
    margin: 18px 0;
    box-shadow: 0 6px 18px rgba(15,23,42,0.045);
}

.filter-title {
    color: #0f172a;
    font-size: 20px;
    font-weight: 900;
    margin-bottom: 8px;
}

.summary-box {
    background: rgba(255,255,255,0.94);
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 18px 20px;
    margin: 18px 0;
    box-shadow: 0 6px 18px rgba(15,23,42,0.045);
}

.summary-title {
    color: #0f172a;
    font-size: 19px;
    font-weight: 900;
    margin-bottom: 12px;
}

.summary-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 10px;
}

.summary-card {
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 13px;
    padding: 13px 14px;
}

.summary-label {
    color: #64748b;
    font-size: 12px;
    font-weight: 800;
    margin-bottom: 6px;
}

.summary-value {
    color: #0f172a;
    font-size: 23px;
    font-weight: 950;
}

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.85);
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
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

.table-scroll {
    overflow-x: auto;
    width: 100%;
    border: 1px solid #d1d5db;
    border-radius: 9px;
    margin-bottom: 18px;
    background: white;
}

table.custom-table {
    min-width: 2200px;
    border-collapse: collapse;
    table-layout: fixed;
    font-size: 13px;
}

table.custom-table th {
    background-color: #e9eef7;
    color: #111827;
    padding: 10px;
    border: 1px solid #d1d5db;
    text-align: left;
    vertical-align: top;
    white-space: normal;
    font-weight: 850;
}

table.custom-table td {
    padding: 10px;
    border: 1px solid #d1d5db;
    vertical-align: top;
    white-space: normal;
    word-wrap: break-word;
    overflow-wrap: break-word;
    line-height: 1.45;
}

table.custom-table tr:nth-child(even) {
    background-color: #f8fafc;
}

table.custom-table tr:nth-child(odd) {
    background-color: #ffffff;
}

td.pending-cell {
    background-color: #fff3cd !important;
    font-weight: 850;
    color: #7a4d00;
}

td.status-approved {
    background-color: #dcfce7 !important;
    color: #166534;
    font-weight: 850;
}

td.status-waiting {
    background-color: #fff3cd !important;
    color: #854d0e;
    font-weight: 850;
}

td.status-returned {
    background-color: #fee2e2 !important;
    color: #991b1b;
    font-weight: 850;
}

td.status-empty {
    background-color: #f8fafc !important;
    color: #64748b;
    font-weight: 700;
}

td.risk-cell {
    background-color: #ffedd5 !important;
    color: #9a3412;
    font-weight: 850;
}

.col-code { width: 95px; }
.col-name { width: 360px; }
.col-indicator { width: 360px; }
.col-unit { width: 170px; }
.col-year { width: 130px; }
.col-quarter { width: 130px; }
.col-department { width: 130px; }
.col-status { width: 160px; }

.note-box {
    border: 1px solid #d6dce8;
    border-radius: 10px;
    padding: 13px 17px;
    background: #ffffff;
    color: #374151;
    margin-top: 18px;
    font-size: 14px;
}

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
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_strat_matrix():
    df = pd.read_excel(
        FILE_PATH,
        sheet_name=SHEET_NAME,
        header=None,
        engine="openpyxl"
    )

    data = df.iloc[7:].copy()

    result = pd.DataFrame({
        "type_marker": data.iloc[:, 1],
        "code": data.iloc[:, 2],
        "name": data.iloc[:, 3],
        "indicator": data.iloc[:, 5],
        "unit": data.iloc[:, 6],
        "base_2021": data.iloc[:, 7],
        "fact_2024": data.iloc[:, 8],
        "expected_2025": data.iloc[:, 9],
        "target_2026": data.iloc[:, 10],
        "target_2027": data.iloc[:, 11],
        "target_2028": data.iloc[:, 12],
        "department": data.iloc[:, 17]
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
        marker = str(row["type_marker"]).lower().strip()
        code = str(row["code"]).strip()
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
            if current_task_code:
                object_type = "task_indicator"
            elif current_goal_code:
                object_type = "goal_indicator"
            else:
                object_type = "other"

        object_types.append(object_type)
        parent_goal_codes.append(current_goal_code)
        parent_task_codes.append(current_task_code)

    result["object_type"] = object_types
    result["parent_goal_code"] = parent_goal_codes
    result["parent_task_code"] = parent_task_codes

    return result


def load_monitoring():
    response = supabase.table("monitoring_requests").select("*").execute()

    if not response.data:
        return pd.DataFrame()

    return pd.DataFrame(response.data)


def clean_value(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return escape(str(value))


def raw_value(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value).strip()


def normalize_text(value):
    return raw_value(value).lower().replace(" ", "")


def is_empty_or_nd(value):
    text = normalize_text(value)

    empty_values = [
        "",
        "н.д.",
        "нд",
        "nan",
        "none",
        "-",
        "—"
    ]

    return text in empty_values


def is_active_in_year(row, selected_year):
    col = f"target_{selected_year}"

    if col not in row:
        return False

    value = raw_value(row.get(col, ""))

    if is_empty_or_nd(value):
        return False

    return True


def get_indicator_type(row, selected_year):
    unit = raw_value(row.get("unit", "")).lower()
    plan_value = raw_value(row.get(f"target_{selected_year}", ""))

    if "так/ні" in unit or "так" in unit and "ні" in unit:
        return "так/ні"

    if "%" in unit or "відсот" in unit:
        return "Відсоткові"

    if "грн" in unit or "дол" in unit or "євро" in unit or "eur" in unit or "usd" in unit:
        return "Фінансові"

    if is_empty_or_nd(plan_value):
        return "Без планового значення"

    return "Кількісні"


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


def get_measure_records(monitoring_df, code, selected_year, selected_quarter):
    if monitoring_df.empty:
        return pd.DataFrame()

    data = monitoring_df.copy()

    data = data[
        data["strat_code"].astype(str).str.strip() == str(code).strip()
    ]

    data = data[
        data["year"].astype(str).str.strip() == str(selected_year).strip()
    ]

    if selected_quarter != "Усі квартали":
        q = selected_quarter.replace(" квартал", "").strip()
        data = data[
            data["quarter"].astype(str).str.strip() == q
        ]

    return data.copy()


def get_measure_status(monitoring_df, code, selected_year, selected_quarter):
    records = get_measure_records(monitoring_df, code, selected_year, selected_quarter)

    if records.empty:
        return "Без подання"

    statuses = records["approval_status"].fillna("").astype(str).str.strip().tolist()
    unique_statuses = list(set([s for s in statuses if s]))

    if "Погоджено" in unique_statuses and len(unique_statuses) == 1:
        return "Погоджено"

    if "Очікує погодження" in unique_statuses and len(unique_statuses) == 1:
        return "Очікує погодження"

    if "Повернуто на доопрацювання" in unique_statuses and len(unique_statuses) == 1:
        return "Повернуто на доопрацювання"

    if "Погоджено" in unique_statuses:
        return "Є погоджені дані"

    if "Очікує погодження" in unique_statuses:
        return "Є дані на погодженні"

    if "Повернуто на доопрацювання" in unique_statuses:
        return "Повернуто"

    return "Без подання"


def has_measure_risks(monitoring_df, code, selected_year, selected_quarter):
    records = get_measure_records(monitoring_df, code, selected_year, selected_quarter)

    if records.empty or "risks" not in records.columns:
        return False

    risks = records["risks"].fillna("").astype(str).str.strip()
    risks = risks[risks != ""]

    return not risks.empty


def has_monitoring_submission(monitoring_df, code, selected_year, selected_quarter):
    records = get_measure_records(monitoring_df, code, selected_year, selected_quarter)
    return not records.empty


def has_approved_monitoring(monitoring_df, code, selected_year, selected_quarter):
    records = get_measure_records(monitoring_df, code, selected_year, selected_quarter)

    if records.empty:
        return False

    return "Погоджено" in records["approval_status"].fillna("").astype(str).str.strip().tolist()


def has_waiting_monitoring(monitoring_df, code, selected_year, selected_quarter):
    records = get_measure_records(monitoring_df, code, selected_year, selected_quarter)

    if records.empty:
        return False

    return "Очікує погодження" in records["approval_status"].fillna("").astype(str).str.strip().tolist()


def apply_measure_filters(
    measures,
    monitoring_df,
    selected_dep,
    selected_year,
    selected_quarter,
    measure_mode,
    indicator_type_filter,
    search_query
):
    filtered = measures.copy()

    if selected_dep != "Усі":
        filtered = filtered[
            filtered["department"].astype(str).str.strip() == selected_dep
        ]

    filtered["active_in_selected_year"] = filtered.apply(
        lambda row: is_active_in_year(row, selected_year),
        axis=1
    )

    filtered["indicator_type"] = filtered.apply(
        lambda row: get_indicator_type(row, selected_year),
        axis=1
    )

    filtered["monitoring_status"] = filtered["code"].apply(
        lambda code: get_measure_status(monitoring_df, code, selected_year, selected_quarter)
    )

    filtered["has_risks"] = filtered["code"].apply(
        lambda code: has_measure_risks(monitoring_df, code, selected_year, selected_quarter)
    )

    filtered["has_submission"] = filtered["code"].apply(
        lambda code: has_monitoring_submission(monitoring_df, code, selected_year, selected_quarter)
    )

    filtered["has_approved"] = filtered["code"].apply(
        lambda code: has_approved_monitoring(monitoring_df, code, selected_year, selected_quarter)
    )

    filtered["has_waiting"] = filtered["code"].apply(
        lambda code: has_waiting_monitoring(monitoring_df, code, selected_year, selected_quarter)
    )

    if measure_mode == "Лише активні в обраному році":
        filtered = filtered[filtered["active_in_selected_year"] == True]

    elif measure_mode == "Лише заходи з поданим моніторингом":
        filtered = filtered[filtered["has_submission"] == True]

    elif measure_mode == "Лише заходи без моніторингу":
        filtered = filtered[filtered["has_submission"] == False]

    elif measure_mode == "Лише заходи з ризиками":
        filtered = filtered[filtered["has_risks"] == True]

    elif measure_mode == "Лише заходи, що очікують погодження":
        filtered = filtered[filtered["has_waiting"] == True]

    elif measure_mode == "Лише погоджені заходи":
        filtered = filtered[filtered["has_approved"] == True]

    if indicator_type_filter != "Усі":
        filtered = filtered[filtered["indicator_type"] == indicator_type_filter]

    if search_query.strip():
        sq = search_query.strip().lower()

        filtered = filtered[
            filtered["code"].astype(str).str.lower().str.contains(sq, na=False)
            |
            filtered["name"].astype(str).str.lower().str.contains(sq, na=False)
            |
            filtered["indicator"].astype(str).str.lower().str.contains(sq, na=False)
            |
            filtered["department"].astype(str).str.lower().str.contains(sq, na=False)
        ]

    return filtered.copy()


def render_table(df, pending_cells=None, status_cells=None, risk_cells=None, min_width=2200):
    if df.empty:
        st.info("Дані відсутні.")
        return

    if pending_cells is None:
        pending_cells = set()

    if status_cells is None:
        status_cells = {}

    if risk_cells is None:
        risk_cells = set()

    html = f"""
    <div class="table-scroll">
    <table class="custom-table" style="min-width:{min_width}px;">
    <thead><tr>
    """

    for col in df.columns:
        css_class = "col-year"

        if col == "Код":
            css_class = "col-code"
        elif col == "Захід":
            css_class = "col-name"
        elif col == "Індикатор":
            css_class = "col-indicator"
        elif col == "Одиниця виміру":
            css_class = "col-unit"
        elif "квартал" in col:
            css_class = "col-quarter"
        elif "Департамент" in col:
            css_class = "col-department"
        elif col in ["Статус моніторингу", "Ризики", "Активність у році", "Тип індикатора"]:
            css_class = "col-status"

        html += f"<th class='{css_class}'>{escape(str(col))}</th>"

    html += "</tr></thead><tbody>"

    for _, row in df.iterrows():
        code = str(row.get("Код", "")).strip()
        html += "<tr>"

        for col in df.columns:
            value = clean_value(row[col])
            cell_class = ""

            if (code, col) in pending_cells:
                cell_class = "pending-cell"

            if (code, col) in status_cells:
                cell_class = status_cells[(code, col)]

            if (code, col) in risk_cells:
                cell_class = "risk-cell"

            html += f"<td class='{cell_class}'>{value}</td>"

        html += "</tr>"

    html += "</tbody></table></div>"
    st.markdown(html, unsafe_allow_html=True)


def indicator_table(data):
    if data.empty:
        st.info("Індикаторів не знайдено.")
        return

    renamed = data.rename(columns={
        "indicator": "Індикатор",
        "unit": "Одиниця виміру",
        "base_2021": "Базове значення 2021",
        "fact_2024": "Звіт 2024",
        "expected_2025": "Очікуване 2025",
        "target_2026": "План 2026",
        "target_2027": "План 2027",
        "target_2028": "План 2028"
    })

    show_cols = [
        "Індикатор",
        "Одиниця виміру",
        "Базове значення 2021",
        "Звіт 2024",
        "Очікуване 2025",
        "План 2026",
        "План 2027",
        "План 2028"
    ]

    existing_cols = [col for col in show_cols if col in renamed.columns]
    render_table(renamed[existing_cols], min_width=1350)


def build_indicator_rows(parent_row, child_rows):
    rows = []

    parent_indicator = raw_value(parent_row.get("indicator", ""))

    if parent_indicator:
        rows.append({
            "indicator": parent_row.get("indicator", ""),
            "unit": parent_row.get("unit", ""),
            "base_2021": parent_row.get("base_2021", ""),
            "fact_2024": parent_row.get("fact_2024", ""),
            "expected_2025": parent_row.get("expected_2025", ""),
            "target_2026": parent_row.get("target_2026", ""),
            "target_2027": parent_row.get("target_2027", ""),
            "target_2028": parent_row.get("target_2028", "")
        })

    for _, child in child_rows.iterrows():
        child_indicator = raw_value(child.get("indicator", ""))

        if child_indicator:
            rows.append({
                "indicator": child.get("indicator", ""),
                "unit": child.get("unit", ""),
                "base_2021": child.get("base_2021", ""),
                "fact_2024": child.get("fact_2024", ""),
                "expected_2025": child.get("expected_2025", ""),
                "target_2026": child.get("target_2026", ""),
                "target_2027": child.get("target_2027", ""),
                "target_2028": child.get("target_2028", "")
            })

    return pd.DataFrame(rows)


def get_filtered_completion(filtered_measures, monitoring_df, selected_year, selected_quarter):
    if filtered_measures.empty:
        return 0

    total = len(filtered_measures)
    approved = 0

    for _, row in filtered_measures.iterrows():
        code = str(row["code"]).strip()

        if has_approved_monitoring(monitoring_df, code, selected_year, selected_quarter):
            approved += 1

    return round((approved / total) * 100, 1) if total else 0


def get_quarter_columns(selected_year, selected_quarter):
    if selected_quarter == "Усі квартали":
        return [
            ("I", f"{selected_year} I квартал"),
            ("II", f"{selected_year} II квартал"),
            ("III", f"{selected_year} III квартал"),
            ("IV", f"{selected_year} IV квартал")
        ]

    q = selected_quarter.replace(" квартал", "").strip()
    return [(q, f"{selected_year} {q} квартал")]


def make_summary_card(label, value):
    return f"""
    <div class="summary-card">
        <div class="summary-label">{label}</div>
        <div class="summary-value">{value}</div>
    </div>
    """


df = load_strat_matrix()
monitoring_df = load_monitoring()

if monitoring_df.empty:
    monitoring_df = pd.DataFrame()

monitoring_df = ensure_monitoring_columns(monitoring_df)

quarter_data = {}

if not monitoring_df.empty:
    visible_monitoring = monitoring_df[
        monitoring_df["approval_status"].isin(["Погоджено", "Очікує погодження"])
    ].copy()

    if not visible_monitoring.empty:
        visible_monitoring = visible_monitoring.sort_values("submitted_at")

        for _, row in visible_monitoring.iterrows():
            key = str(row["strat_code"]).strip()
            year = str(row["year"]).strip()
            q = str(row["quarter"]).strip()
            approval = str(row["approval_status"]).strip()

            quarter_key = f"{year}_{q}"

            quarter_data.setdefault(key, {})
            quarter_data[key][quarter_key] = {
                "value": row["numeric_value"],
                "approval": approval
            }


total_measures = len(df[df["object_type"] == "measure"])
submitted_count = 0
approved_count = 0
waiting_count = 0
returned_count = 0
risk_count = 0
last_update = datetime.now().strftime("%d.%m.%Y %H:%M")

if not monitoring_df.empty:
    submitted_count = len(monitoring_df)
    approved_count = len(monitoring_df[monitoring_df["approval_status"] == "Погоджено"])
    waiting_count = len(monitoring_df[monitoring_df["approval_status"] == "Очікує погодження"])
    returned_count = len(monitoring_df[monitoring_df["approval_status"] == "Повернуто на доопрацювання"])

    if "risks" in monitoring_df.columns:
        risk_count = len(
            monitoring_df[
                monitoring_df["risks"].fillna("").astype(str).str.strip() != ""
            ]
        )

    if "submitted_at" in monitoring_df.columns:
        try:
            last_update_value = pd.to_datetime(monitoring_df["submitted_at"], errors="coerce").max()
            if pd.notna(last_update_value):
                last_update = last_update_value.strftime("%d.%m.%Y %H:%M")
        except Exception:
            pass

approved_share = round((approved_count / submitted_count) * 100, 1) if submitted_count else 0

without_monitoring = max(
    total_measures - len(set(monitoring_df["strat_code"].astype(str))) if not monitoring_df.empty else total_measures,
    0
)


if "expand_all_goals" not in st.session_state:
    st.session_state.expand_all_goals = False

if "selected_dep_main" not in st.session_state:
    st.session_state.selected_dep_main = "Усі"

if "selected_year_main" not in st.session_state:
    st.session_state.selected_year_main = 2026

if "selected_quarter_main" not in st.session_state:
    st.session_state.selected_quarter_main = "Усі квартали"

if "measure_mode_main" not in st.session_state:
    st.session_state.measure_mode_main = "Усі заходи стратегічного плану"

if "indicator_type_main" not in st.session_state:
    st.session_state.indicator_type_main = "Усі"

if "search_main" not in st.session_state:
    st.session_state.search_main = ""

if "selected_goal_nav_main" not in st.session_state:
    st.session_state.selected_goal_nav_main = "Усі стратегічні цілі"


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
        <div class="header-title">Моніторинг виконання Стратегічного плану на 2026-2028 роки</div>
        <div class="header-subtitle">
            Інтерактивна демо-версія системи для проведення моніторингу, оцінки результатів та актуалізації Стратегічного плану на 2026-2028 роки
   
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
        <div class="cta-title">Внесення даних моніторингу виконання Стратегічного плану</div>
        <div class="cta-text">
            Подайте квартальні дані щодо заходів свого департаменту, додайте опис прогресу, ризики та підтвердні файли.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.page_link(
    "pages/1_Моніторинг_виконання.py",
    label="Перейти до внесення моніторингових даних",
    icon="🖊️"
)

st.markdown(
    """
    <div class="flow-box">
        <div class="flow-title">Маршрут моніторингових даних</div>
        <div class="flow-steps">
            <div class="flow-step">📝 Подання департаментом</div>
            <div class="flow-step">🔎 Перевірка адміністратором</div>
            <div class="flow-step">✅ Погодження</div>
            <div class="flow-step">📊 Відображення у стратегічному плані</div>
            <div class="flow-step">📈 Аналітика виконання</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Заходів у СП", total_measures)
k2.metric("Поданих заявок", submitted_count)
k3.metric("Погоджено", approved_count)
k4.metric("Погоджено, %", f"{approved_share}%")
k5.metric("Без моніторингу", without_monitoring)

k6, k7, k8 = st.columns(3)
k6.metric("Очікує погодження", waiting_count)
k7.metric("Повернуто", returned_count)
k8.metric("Заявок із ризиками", risk_count)

st.markdown(
    """
    <div class="info-grid">
        <div class="info-card">
            <div class="info-card-title">Як працювати з головною сторінкою</div>
            <div>
                1. Оберіть департамент, рік, квартал та режим відображення.<br>
                2. Система залишить тільки релевантні стратегічні цілі, завдання та заходи.<br>
                3. Відкрийте синій блок стратегічної цілі та темно-сірий блок завдання.<br>
                4. Перегляньте індикатори, заходи, планові та квартальні значення.<br>
                5. Для внесення нових даних перейдіть за зеленою кнопкою вище.
            </div>
        </div>
        <div class="info-card">
            <div class="info-card-title">Легенда квартальних даних</div>
            <div class="legend-item">🟨 Жовта комірка — дані подані, але ще очікують погодження адміністратора.</div>
            <div class="legend-item">🟩 Погоджено — дані враховані в моніторингу.</div>
            <div class="legend-item">🔴 Повернуті на доопрацювання дані не відображаються як погоджені.</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


departments = sorted(df["department"].dropna().astype(str).unique())
goals = df[df["object_type"] == "goal"].copy()

goal_options = ["Усі стратегічні цілі"] + [
    f"{row['code']} {row['name']}" for _, row in goals.iterrows()
]

st.markdown('<div class="filter-box"><div class="filter-title">Фільтри стратегічного плану</div>', unsafe_allow_html=True)

f1, f2, f3, f4 = st.columns([1, 1, 1, 1.2])

with f1:
    selected_dep = st.selectbox(
        "Департамент",
        ["Усі"] + departments,
        key="selected_dep_main"
    )

with f2:
    selected_year = st.selectbox(
        "Рік моніторингу",
        [2026, 2027, 2028],
        key="selected_year_main"
    )

with f3:
    selected_quarter = st.selectbox(
        "Квартал",
        ["Усі квартали", "I квартал", "II квартал", "III квартал", "IV квартал"],
        key="selected_quarter_main"
    )

with f4:
    selected_goal_nav = st.selectbox(
        "Швидкий перехід до стратегічної цілі",
        goal_options,
        key="selected_goal_nav_main"
    )

f5, f6, f7 = st.columns([1.4, 1, 1.4])

with f5:
    measure_mode = st.selectbox(
        "Режим відображення заходів",
        [
            "Усі заходи стратегічного плану",
            "Лише активні в обраному році",
            "Лише заходи з поданим моніторингом",
            "Лише заходи без моніторингу",
            "Лише заходи з ризиками",
            "Лише заходи, що очікують погодження",
            "Лише погоджені заходи"
        ],
        key="measure_mode_main"
    )

with f6:
    indicator_type_filter = st.selectbox(
        "Тип індикатора",
        [
            "Усі",
            "так/ні",
            "Кількісні",
            "Відсоткові",
            "Фінансові",
            "Без планового значення"
        ],
        key="indicator_type_main"
    )

with f7:
    search_query = st.text_input(
        "Пошук за кодом, назвою заходу, індикатором або департаментом",
        key="search_main"
    )

def expand_all_main():
    st.session_state.expand_all_goals = True


def collapse_all_main():
    st.session_state.expand_all_goals = False


def reset_main_filters():
    st.session_state.selected_dep_main = "Усі"
    st.session_state.selected_year_main = 2026
    st.session_state.selected_quarter_main = "Усі квартали"
    st.session_state.measure_mode_main = "Усі заходи стратегічного плану"
    st.session_state.indicator_type_main = "Усі"
    st.session_state.search_main = ""
    st.session_state.selected_goal_nav_main = "Усі стратегічні цілі"
    st.session_state.expand_all_goals = False


b1, b2, b3 = st.columns([1, 1, 4])

with b1:
    st.button(
        "Розгорнути всі релевантні цілі",
        use_container_width=True,
        on_click=expand_all_main
    )

with b2:
    st.button(
        "Згорнути все",
        use_container_width=True,
        on_click=collapse_all_main
    )

with b3:
    st.button(
        "Скинути фільтри",
        use_container_width=True,
        on_click=reset_main_filters
    )
st.markdown('</div>', unsafe_allow_html=True)


all_measures = df[df["object_type"] == "measure"].copy()

filtered_measures = apply_measure_filters(
    all_measures,
    monitoring_df,
    selected_dep,
    selected_year,
    selected_quarter,
    measure_mode,
    indicator_type_filter,
    search_query
)

selected_goal_code = None

if selected_goal_nav != "Усі стратегічні цілі":
    selected_goal_code = selected_goal_nav.split(" ")[0].strip()

if selected_goal_code:
    filtered_measures = filtered_measures[
        filtered_measures["parent_goal_code"].astype(str) == selected_goal_code
    ]

filtered_goal_codes = set(filtered_measures["parent_goal_code"].astype(str).str.strip())
filtered_task_codes = set(filtered_measures["parent_task_code"].astype(str).str.strip())

visible_goals = goals[
    goals["code"].astype(str).str.strip().isin(filtered_goal_codes)
].copy()

visible_tasks = df[
    (df["object_type"] == "task") &
    (df["code"].astype(str).str.strip().isin(filtered_task_codes))
].copy()

filtered_completion = get_filtered_completion(
    filtered_measures,
    monitoring_df,
    selected_year,
    selected_quarter
)

filtered_approved = len(filtered_measures[filtered_measures["has_approved"] == True]) if "has_approved" in filtered_measures.columns else 0
filtered_waiting = len(filtered_measures[filtered_measures["has_waiting"] == True]) if "has_waiting" in filtered_measures.columns else 0
filtered_without_submission = len(filtered_measures[filtered_measures["has_submission"] == False]) if "has_submission" in filtered_measures.columns else 0
filtered_risks = len(filtered_measures[filtered_measures["has_risks"] == True]) if "has_risks" in filtered_measures.columns else 0

st.markdown(
    """
    <div class="summary-box">
        <div class="summary-title">Результат після застосування фільтрів</div>
    </div>
    """,
    unsafe_allow_html=True
)

s1, s2, s3, s4, s5, s6, s7 = st.columns(7)

with s1:
    st.markdown(
        f"""
        <div class="summary-card">
            <div class="summary-label">Стратегічних цілей</div>
            <div class="summary-value">{len(visible_goals)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with s2:
    st.markdown(
        f"""
        <div class="summary-card">
            <div class="summary-label">Завдань</div>
            <div class="summary-value">{len(visible_tasks)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with s3:
    st.markdown(
        f"""
        <div class="summary-card">
            <div class="summary-label">Заходів</div>
            <div class="summary-value">{len(filtered_measures)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with s4:
    st.markdown(
        f"""
        <div class="summary-card">
            <div class="summary-label">Виконання</div>
            <div class="summary-value">{filtered_completion}%</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with s5:
    st.markdown(
        f"""
        <div class="summary-card">
            <div class="summary-label">Погоджено</div>
            <div class="summary-value">{filtered_approved}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with s6:
    st.markdown(
        f"""
        <div class="summary-card">
            <div class="summary-label">Очікує</div>
            <div class="summary-value">{filtered_waiting}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with s7:
    st.markdown(
        f"""
        <div class="summary-card">
            <div class="summary-label">Без подання</div>
            <div class="summary-value">{filtered_without_submission}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

st.caption(
    f"Рік: {selected_year}. Квартал: {selected_quarter}. "
    f"Департамент: {selected_dep}. Режим: {measure_mode}. "
    f"Заходів із ризиками: {filtered_risks}."
)

st.caption(
    f"Рік: {selected_year}. Квартал: {selected_quarter}. "
    f"Департамент: {selected_dep}. Режим: {measure_mode}. "
    f"Заходів із ризиками: {filtered_risks}."
)

st.markdown('</div>', unsafe_allow_html=True)


st.subheader("Стратегічний план")

if filtered_measures.empty:
    st.warning("За обраними фільтрами заходів не знайдено.")
    st.stop()


for _, goal in visible_goals.iterrows():
    goal_code = str(goal["code"]).strip()
    goal_name = str(goal["name"]).strip()

    goal_filtered_measures = filtered_measures[
        filtered_measures["parent_goal_code"].astype(str).str.strip() == goal_code
    ].copy()

    if goal_filtered_measures.empty:
        continue

    goal_task_codes = set(goal_filtered_measures["parent_task_code"].astype(str).str.strip())

    tasks = df[
        (df["object_type"] == "task") &
        (df["code"].astype(str).str.strip().isin(goal_task_codes))
    ].copy()

    tasks_count = len(tasks)
    measures_count = len(goal_filtered_measures)

    goal_percent = get_filtered_completion(
        goal_filtered_measures,
        monitoring_df,
        selected_year,
        selected_quarter
    )

    if selected_dep != "Усі":
        progress_label = f"Виконання {selected_dep} — {goal_percent}%"
    else:
        progress_label = f"Виконання за фільтрами — {goal_percent}%"

    goal_label = (
        f"{goal_code} {goal_name}  |  "
        f"Завдань — {tasks_count}  |  Заходів — {measures_count}  |  {progress_label}"
    )

    expand_goal = st.session_state.expand_all_goals or selected_goal_code == goal_code

    with st.expander(goal_label, expanded=expand_goal):
        st.progress(min(goal_percent / 100, 1.0))

        goal_indicator_children = df[
            (df["object_type"] == "goal_indicator") &
            (df["parent_goal_code"].astype(str) == goal_code) &
            (df["parent_task_code"].astype(str) == "")
        ].copy()

        goal_indicators = build_indicator_rows(goal, goal_indicator_children)

        if not goal_indicators.empty:
            st.markdown(
                '<div class="section-title">Індикатори досягнення стратегічної цілі</div>',
                unsafe_allow_html=True
            )
            indicator_table(goal_indicators)

        for _, task in tasks.iterrows():
            task_code = str(task["code"]).strip()
            task_name = str(task["name"]).strip()

            task_measures = goal_filtered_measures[
                goal_filtered_measures["parent_task_code"].astype(str).str.strip() == task_code
            ].copy()

            if task_measures.empty:
                continue

            task_percent = get_filtered_completion(
                task_measures,
                monitoring_df,
                selected_year,
                selected_quarter
            )

            task_label = (
                f"{task_code} {task_name}  |  "
                f"Заходів — {len(task_measures)}  |  "
                f"Виконання — {task_percent}%"
            )

            with st.expander(task_label, expanded=st.session_state.expand_all_goals):

                task_indicator_children = df[
                    (df["object_type"] == "task_indicator") &
                    (df["parent_task_code"].astype(str) == task_code)
                ].copy()

                task_indicators = build_indicator_rows(task, task_indicator_children)

                if not task_indicators.empty:
                    st.markdown(
                        '<div class="section-title">Індикатори досягнення завдання</div>',
                        unsafe_allow_html=True
                    )
                    indicator_table(task_indicators)

                measures = task_measures.copy()

                pending_cells = set()
                status_cells = {}
                risk_cells = set()

                quarter_columns = get_quarter_columns(selected_year, selected_quarter)

                for q, col_name in quarter_columns:
                    col_key = f"{selected_year}_{q}"

                    def get_q_value(code):
                        code = str(code).strip()
                        item = quarter_data.get(code, {}).get(col_key, None)

                        if item is None:
                            return ""

                        if item["approval"] in ["Очікує погодження", "Погоджено"]:
                            return item["value"]

                        return ""

                    measures[col_key] = measures["code"].apply(get_q_value)

                measures["monitoring_status_for_table"] = measures["code"].apply(
                    lambda code: get_measure_status(monitoring_df, code, selected_year, selected_quarter)
                )

                measures["risks_for_table"] = measures["has_risks"].apply(
                    lambda value: "Є ризики" if value else "Не зазначено"
                )

                measures["active_for_table"] = measures["active_in_selected_year"].apply(
                    lambda value: "Активний" if value else "Неактивний / немає плану"
                )

                measures = measures.rename(columns={
                    "code": "Код",
                    "name": "Захід",
                    "indicator": "Індикатор",
                    "unit": "Одиниця виміру",
                    "base_2021": "Базове значення 2021",
                    "fact_2024": "Звіт 2024",
                    "expected_2025": "Очікуване 2025",
                    "target_2026": "План 2026",
                    f"{selected_year}_I": f"{selected_year} I квартал",
                    f"{selected_year}_II": f"{selected_year} II квартал",
                    f"{selected_year}_III": f"{selected_year} III квартал",
                    f"{selected_year}_IV": f"{selected_year} IV квартал",
                    "target_2027": "План 2027",
                    "target_2028": "План 2028",
                    "department": "Департамент",
                    "monitoring_status_for_table": "Статус моніторингу",
                    "risks_for_table": "Ризики",
                    "active_for_table": "Активність у році",
                    "indicator_type": "Тип індикатора"
                })

                for _, measure_row in measures.iterrows():
                    code = str(measure_row["Код"]).strip()

                    status = str(measure_row.get("Статус моніторингу", "")).strip()

                    status_class = "status-empty"

                    if "Погоджено" in status or "погоджені" in status:
                        status_class = "status-approved"
                    elif "Очікує" in status or "погодженні" in status:
                        status_class = "status-waiting"
                    elif "Повернуто" in status:
                        status_class = "status-returned"

                    status_cells[(code, "Статус моніторингу")] = status_class

                    if str(measure_row.get("Ризики", "")).strip() == "Є ризики":
                        risk_cells.add((code, "Ризики"))

                    for q, col_name in quarter_columns:
                        col_key = f"{selected_year}_{q}"
                        item = quarter_data.get(code, {}).get(col_key, None)

                        if item is not None and item["approval"] == "Очікує погодження":
                            pending_cells.add((code, col_name))

                quarter_show_cols = [col_name for _, col_name in quarter_columns]

                show_cols = [
                    "Код",
                    "Захід",
                    "Індикатор",
                    "Одиниця виміру",
                    "Базове значення 2021",
                    "Звіт 2024",
                    "Очікуване 2025",
                    f"План {selected_year}",
                    *quarter_show_cols,
                    "Статус моніторингу",
                    "Ризики",
                    "Активність у році",
                    "Тип індикатора",
                    "Департамент"
                ]

                if selected_year == 2026:
                    plan_col = "План 2026"
                elif selected_year == 2027:
                    plan_col = "План 2027"
                else:
                    plan_col = "План 2028"

                show_cols = [
                    "Код",
                    "Захід",
                    "Індикатор",
                    "Одиниця виміру",
                    "Базове значення 2021",
                    "Звіт 2024",
                    "Очікуване 2025",
                    plan_col,
                    *quarter_show_cols,
                    "Статус моніторингу",
                    "Ризики",
                    "Активність у році",
                    "Тип індикатора",
                    "Департамент"
                ]

                existing_show_cols = [col for col in show_cols if col in measures.columns]

                st.markdown(
                    '<div class="section-title">Заходи</div>',
                    unsafe_allow_html=True
                )

                render_table(
                    measures[existing_show_cols],
                    pending_cells=pending_cells,
                    status_cells=status_cells,
                    risk_cells=risk_cells,
                    min_width=2500
                )

st.markdown(
    """
    <div class="note-box">
        Фільтри застосовуються до всієї ієрархії стратегічного плану: стратегічна ціль → завдання → захід.
        Якщо після фільтрації у стратегічній цілі або завданні не залишається релевантних заходів, такий блок не відображається.
        Відсоток виконання в заголовках розраховується саме за відфільтрованими заходами.
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="footer">
        <strong>Розроблено департаментом стратегічного планування та макроекономічного прогнозування</strong><br>
        Версія DEMO 1.2 | 2026 | Внутрішня система моніторингу стратегічного плану
    </div>
    """,
    unsafe_allow_html=True
)
