import re
from datetime import datetime
from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from supabase import create_client


# ============================================================
# Page config
# ============================================================

st.set_page_config(
    page_title="Dashboard",
    layout="wide"
)

FILE_PATH = "Під моніторинг СП.xlsx"
SHEET_NAME = "Страт_матриця"

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
<style>
.stApp {
    background:
        radial-gradient(circle at top right, rgba(37,99,235,0.08), transparent 28%),
        radial-gradient(circle at bottom left, rgba(22,163,74,0.07), transparent 30%),
        linear-gradient(180deg, #f6f8fb 0%, #eef2f7 100%);
}

.main .block-container {
    max-width: 1550px;
    padding-top: 1.2rem;
}

.dashboard-header {
    background: rgba(255,255,255,0.95);
    border: 1px solid #d8dee9;
    box-shadow: 0 8px 22px rgba(15,23,42,0.055);
    border-radius: 18px;
    padding: 24px 28px;
    margin-bottom: 18px;
}

.dashboard-title {
    font-size: 31px;
    font-weight: 950;
    color: #0f172a;
    margin-bottom: 9px;
}

.dashboard-subtitle {
    font-size: 15px;
    color: #475569;
    line-height: 1.58;
}

.filter-box {
    background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(241,246,253,0.98));
    border: 1px solid #cbd8ea;
    box-shadow: 0 10px 24px rgba(15,23,42,0.07);
    border-radius: 18px;
    padding: 22px 24px 26px 24px;
    margin: 16px 0 24px 0;
}

.filter-title {
    color: #0f172a;
    font-size: 22px;
    font-weight: 950;
    margin-bottom: 6px;
}

.filter-legend {
    color: #475569;
    font-size: 14px;
    line-height: 1.45;
    margin-bottom: 16px;
}

.section-title {
    color: #111827;
    font-size: 25px;
    font-weight: 950;
    margin: 28px 0 14px 0;
}

.section-subtitle {
    color: #475569;
    font-size: 14px;
    margin-top: -6px;
    margin-bottom: 14px;
}

.card {
    background: rgba(255,255,255,0.96);
    border: 1px solid #d8dee9;
    box-shadow: 0 6px 18px rgba(15,23,42,0.045);
    border-radius: 16px;
    padding: 18px 20px;
    margin-bottom: 16px;
}

.card-title {
    font-size: 16px;
    font-weight: 900;
    color: #111827;
    margin-bottom: 10px;
}

.insight-box {
    background: rgba(255,255,255,0.96);
    border: 1px solid #d8dee9;
    box-shadow: 0 6px 18px rgba(15,23,42,0.045);
    border-radius: 16px;
    padding: 18px 20px;
    margin-bottom: 16px;
    line-height: 1.55;
}

.bad-box {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    color: #7c2d12;
    border-radius: 14px;
    padding: 15px 17px;
    font-size: 14px;
    line-height: 1.55;
    margin-bottom: 16px;
}

.metric-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 14px;
}

.metric-card {
    background: #ffffff;
    border: 1px solid #d8dee9;
    border-radius: 15px;
    padding: 14px 15px;
    box-shadow: 0 5px 16px rgba(15,23,42,0.04);
}

.metric-label {
    color: #64748b;
    font-size: 12px;
    font-weight: 850;
    min-height: 32px;
    line-height: 1.3;
}

.metric-value {
    color: #0f172a;
    font-size: 25px;
    font-weight: 950;
    line-height: 1.1;
    margin-top: 8px;
}

.methodology-box {
    background: #ffffff;
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 18px 20px;
    color: #334155;
    font-size: 14px;
    line-height: 1.6;
    margin-top: 20px;
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

div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background-color: #d7eaff !important;
    border: 1px solid #8fb3df !important;
    border-radius: 10px !important;
    min-height: 43px !important;
}

div[data-testid="stMultiSelect"] label,
div[data-testid="stSelectbox"] label {
    font-weight: 800 !important;
    color: #1e293b !important;
}

@media (max-width: 1100px) {
    .metric-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}
</style>
""",
    unsafe_allow_html=True
)


# ============================================================
# Basic helpers
# ============================================================

def raw_value(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value).strip()


def normalize_text(value):
    return raw_value(value).lower().replace(" ", "")


def is_empty_or_nd(value):
    return normalize_text(value) in {"", "н.д.", "нд", "nan", "none", "-", "—"}


def safe_html(value):
    return escape(raw_value(value))


def to_number(value):
    if value is None or pd.isna(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    text = text.replace("%", "").replace(" ", "").replace(",", ".")

    try:
        return float(text)
    except Exception:
        return None


def extract_ssp_index(value):
    text = raw_value(value)
    match = re.search(r"\d+", text)
    return match.group(0) if match else ""


def split_ssp_values(value):
    return re.findall(r"\d+", raw_value(value))


def value_contains_any_ssp(value, selected_indices):
    if not selected_indices:
        return True
    found = set(split_ssp_values(value))
    return bool(found.intersection(set(selected_indices)))


def strip_leading_code(text, code):
    value = raw_value(text)
    code_value = raw_value(code)

    if code_value and value.startswith(code_value):
        value = value[len(code_value):].lstrip(" .—-–|:")

    return value


def unique_clean_values(series):
    if series is None:
        return []

    values = []
    for item in series.dropna().astype(str).tolist():
        item = item.strip()
        if item and item.lower() not in {"nan", "none", "н.д.", "нд", "-", "—"}:
            values.append(item)

    return sorted(set(values))


def contains_selected_value(value, selected_values):
    if not selected_values:
        return True

    text = raw_value(value)
    if not text:
        return False

    return any(raw_value(v) in text for v in selected_values)


def code_sort_key(code):
    parts = re.findall(r"\d+", raw_value(code))
    return tuple(int(p) for p in parts) if parts else (9999,)


def render_metric_card(label, value):
    return f"""
    <div class="metric-card">
        <div class="metric-label">{safe_html(label)}</div>
        <div class="metric-value">{safe_html(value)}</div>
    </div>
    """


def render_metric_grid(metrics):
    html = '<div class="metric-grid">'
    for label, value in metrics:
        html += render_metric_card(label, value)
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# ============================================================
# Data loading
# ============================================================

@st.cache_data
def load_strat_matrix():
    source_df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=None, engine="openpyxl")
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
        "measure_end_date": safe_keyword_col(["кінцева", "дата"])
    })

    result = result.dropna(subset=["code"]).copy()
    result["code"] = result["code"].astype(str).str.strip()
    result["type_marker"] = result["type_marker"].astype(str).str.strip()

    current_goal_code = ""
    current_goal_name = ""
    current_task_code = ""
    current_task_name = ""

    object_types = []
    parent_goal_codes = []
    parent_goal_names = []
    parent_task_codes = []
    parent_task_names = []

    for _, row in result.iterrows():
        marker = raw_value(row["type_marker"]).lower()
        code = raw_value(row["code"])
        name = raw_value(row["name"])
        dots = code.count(".")

        if "стратегічна ціль" in marker:
            object_type = "goal"
            current_goal_code = code
            current_goal_name = strip_leading_code(name, code)
            current_task_code = ""
            current_task_name = ""
        elif "завдання" in marker:
            object_type = "task"
            current_task_code = code
            current_task_name = strip_leading_code(name, code)
        elif "заходи" in marker or dots >= 3:
            object_type = "measure"
        else:
            object_type = "other"

        object_types.append(object_type)
        parent_goal_codes.append(current_goal_code)
        parent_goal_names.append(current_goal_name)
        parent_task_codes.append(current_task_code)
        parent_task_names.append(current_task_name)

    result["object_type"] = object_types
    result["parent_goal_code"] = parent_goal_codes
    result["parent_goal_name"] = parent_goal_names
    result["parent_task_code"] = parent_task_codes
    result["parent_task_name"] = parent_task_names

    result["resp_all"] = (
        result["resp_main"].astype(str) + " | " +
        result["resp_co_1"].astype(str) + " | " +
        result["resp_co_2"].astype(str)
    )

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


# ============================================================
# Status and risk logic
# ============================================================

APPROVAL_APPROVED = "Погоджено"
APPROVAL_REVIEW = "Очікує погодження"
APPROVAL_RETURNED = "Повернуто на доопрацювання"

EXECUTION_STATUSES = [
    "Виконано",
    "Частково виконано",
    "Не виконано",
    "Не настав час",
    "Втратило актуальність",
    "Виконується"
]

EXCLUDED_FROM_RISK = {"Не настав час", "Втратило актуальність", "Термін не настав", "Втратив актуальність"}


def normalize_execution_status(value):
    text = raw_value(value)

    replacements = {
        "Не настав час": "Не настав час",
        "Термін не настав": "Не настав час",
        "Втратило актуальність": "Втратило актуальність",
        "Втратив актуальність": "Втратило актуальність",
        "Виконується": "Виконується",
        "Виконано": "Виконано",
        "Частково виконано": "Частково виконано",
        "Не виконано": "Не виконано",
    }

    return replacements.get(text, text)


def get_measure_records(monitoring_df, code, years=None, quarters=None):
    if monitoring_df.empty:
        return pd.DataFrame()

    data = monitoring_df.copy()
    data = data[data["strat_code"].astype(str).str.strip() == str(code).strip()]

    if years:
        years_as_str = [str(y) for y in years]
        data = data[data["year"].astype(str).str.strip().isin(years_as_str)]

    if quarters:
        quarters_as_str = [str(q).replace(" квартал", "").strip() for q in quarters]
        data = data[data["quarter"].astype(str).str.strip().isin(quarters_as_str)]

    return data.copy()


def get_latest_record(records):
    if records.empty:
        return None

    data = records.copy()
    data["_submitted_at"] = pd.to_datetime(data.get("submitted_at", ""), errors="coerce")
    data = data.sort_values("_submitted_at", ascending=False, na_position="last")

    return data.iloc[0].to_dict()


def get_measure_approval_status(records):
    if records.empty:
        return "Не враховано"

    approvals = records["approval_status"].astype(str).str.strip().tolist()

    if APPROVAL_APPROVED in approvals:
        return "Погоджено"
    if APPROVAL_REVIEW in approvals:
        return "На розгляді"
    if APPROVAL_RETURNED in approvals:
        return "Не враховано"

    return "Не враховано"


def is_quantitative_measure(row):
    unit = normalize_text(row.get("unit", ""))
    indicator = normalize_text(row.get("indicator", ""))

    non_numeric_units = {
        "так/ні",
        "такні",
        "наявність",
        "відсутність"
    }

    if unit in non_numeric_units:
        return False

    for year in [2026, 2027, 2028]:
        if to_number(row.get(f"target_{year}", "")) is not None:
            return True

    if any(word in indicator for word in ["кількість", "обсяг", "частка", "%", "відсот"]):
        return True

    return False


def get_target_for_period(row, selected_years):
    years = [int(y) for y in selected_years] if selected_years else [2026, 2027, 2028]

    values = []
    for year in years:
        value = to_number(row.get(f"target_{year}", ""))
        if value is not None:
            values.append(value)

    if not values:
        return None

    return values[-1]


def get_measure_progress(row, records, selected_years):
    latest = get_latest_record(records)

    if latest is None:
        return {
            "progress_pct": 0.0,
            "execution_status": "Не виконано",
            "approval_status": "Не враховано",
            "fact_value": None,
            "target_value": get_target_for_period(row, selected_years),
            "deviation_pct": None,
            "risk_level": "Середній ризик",
            "risk_score": 45,
            "risk_reason": "за активним заходом не подано моніторингові дані",
            "has_submission": False
        }

    approval_status = get_measure_approval_status(records)
    execution_status = normalize_execution_status(latest.get("status", ""))
    fact_value = to_number(latest.get("numeric_value", ""))
    target_value = get_target_for_period(row, selected_years)

    progress_pct = None
    deviation_pct = None

    if execution_status in {"Не настав час", "Втратило актуальність"}:
        progress_pct = None
        risk_level = "Не оцінюється"
        risk_score = 0
        risk_reason = "захід не включається до ризикового розрахунку за поточним статусом"
    else:
        if is_quantitative_measure(row) and fact_value is not None and target_value not in [None, 0]:
            progress_pct = max(0.0, min(150.0, fact_value / target_value * 100))
            deviation_pct = progress_pct - 100

            if progress_pct >= 100:
                risk_level = "Низький ризик"
                risk_score = 5
                risk_reason = "фактичне значення досягло або перевищило планове"
                execution_status = execution_status or "Виконано"
            elif progress_pct >= 75:
                risk_level = "Середній ризик"
                risk_score = 25
                risk_reason = "показник частково виконано, але він нижчий за план"
                execution_status = execution_status or "Частково виконано"
            else:
                risk_level = "Середній ризик"
                risk_score = 45
                risk_reason = "значне відставання фактичного значення від планового"
                execution_status = execution_status or "Не виконано"
        else:
            if execution_status == "Виконано":
                progress_pct = 100.0
                deviation_pct = 0.0
                risk_level = "Низький ризик"
                risk_score = 5
                risk_reason = "захід позначено як виконаний"
            elif execution_status == "Частково виконано":
                progress_pct = 75.0
                deviation_pct = -25.0
                risk_level = "Середній ризик"
                risk_score = 25
                risk_reason = "захід позначено як частково виконаний"
            elif execution_status == "Виконується":
                progress_pct = 50.0
                deviation_pct = -50.0
                risk_level = "Середній ризик"
                risk_score = 35
                risk_reason = "захід перебуває у виконанні"
            elif execution_status == "Не виконано":
                progress_pct = 0.0
                deviation_pct = -100.0
                risk_level = "Середній ризик"
                risk_score = 45
                risk_reason = "захід позначено як невиконаний"
            else:
                progress_pct = 0.0
                deviation_pct = -100.0
                risk_level = "Середній ризик"
                risk_score = 45
                risk_reason = "немає достатніх даних для підтвердження виконання"

    if approval_status != "Погоджено" and execution_status not in {"Не настав час", "Втратило актуальність"}:
        risk_level = "Середній ризик"
        risk_score = max(risk_score, 40)
        risk_reason = "подані дані не погоджені або не враховані в оцінці"

    return {
        "progress_pct": progress_pct,
        "execution_status": execution_status or "Не виконано",
        "approval_status": approval_status,
        "fact_value": fact_value,
        "target_value": target_value,
        "deviation_pct": deviation_pct,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_reason": risk_reason,
        "has_submission": True,
        "progress_text": raw_value(latest.get("progress_text", "")),
        "risks_info": raw_value(latest.get("risks", ""))
    }


def build_dashboard_dataset(measures_df, monitoring_df, selected_years, selected_quarters):
    rows = []

    for _, row in measures_df.iterrows():
        code = raw_value(row.get("code", ""))
        records = get_measure_records(monitoring_df, code, selected_years, selected_quarters)
        progress = get_measure_progress(row, records, selected_years)

        resp_values = []
        for field in ["resp_main", "resp_co_1", "resp_co_2"]:
            val = raw_value(row.get(field, ""))
            if val:
                resp_values.append(val)

        rows.append({
            "code": code,
            "measure_name": strip_leading_code(row.get("name", ""), code),
            "product_type": raw_value(row.get("product_type", "")),
            "indicator": raw_value(row.get("indicator", "")),
            "unit": raw_value(row.get("unit", "")),
            "parent_goal_code": raw_value(row.get("parent_goal_code", "")),
            "parent_goal_name": raw_value(row.get("parent_goal_name", "")),
            "parent_task_code": raw_value(row.get("parent_task_code", "")),
            "parent_task_name": raw_value(row.get("parent_task_name", "")),
            "resp_main": raw_value(row.get("resp_main", "")),
            "resp_co_1": raw_value(row.get("resp_co_1", "")),
            "resp_co_2": raw_value(row.get("resp_co_2", "")),
            "resp_all": " | ".join(resp_values),
            "deputy_minister": raw_value(row.get("deputy_minister_raw", "")),
            "source_national": raw_value(row.get("source_national", "")),
            "target_value": progress["target_value"],
            "fact_value": progress["fact_value"],
            "progress_pct": progress["progress_pct"],
            "deviation_pct": progress["deviation_pct"],
            "execution_status": progress["execution_status"],
            "approval_status": progress["approval_status"],
            "risk_level": progress["risk_level"],
            "risk_score": progress["risk_score"],
            "risk_reason": progress["risk_reason"],
            "has_submission": progress["has_submission"],
            "is_quantitative": is_quantitative_measure(row),
            "progress_text": progress.get("progress_text", ""),
            "risks_info": progress.get("risks_info", "")
        })

    return pd.DataFrame(rows)


# ============================================================
# Filtering
# ============================================================

def apply_filters(df, filters):
    data = df.copy()

    if filters["years"]:
        pass

    if filters["ssp_indices"]:
        data = data[
            data["resp_all"].apply(lambda x: value_contains_any_ssp(x, filters["ssp_indices"]))
        ]

    if filters["goals"]:
        data = data[data["parent_goal_code"].isin(filters["goals"])]

    if filters["tasks"]:
        data = data[data["parent_task_code"].isin(filters["tasks"])]

    if filters["measures"]:
        data = data[data["code"].isin(filters["measures"])]

    if filters["product_types"]:
        data = data[data["product_type"].isin(filters["product_types"])]

    if filters["deputies"]:
        data = data[data["deputy_minister"].isin(filters["deputies"])]

    if filters["execution_statuses"]:
        data = data[data["execution_status"].isin(filters["execution_statuses"])]

    if filters["financing"]:
        # Поки даних немає. Фільтр залишений як технічна заготовка.
        pass

    if filters["sources_national"]:
        data = data[data["source_national"].isin(filters["sources_national"])]

    return data.copy()


def reset_dashboard_filters():
    for key in [
        "dash_years",
        "dash_quarters",
        "dash_ssp",
        "dash_goals",
        "dash_tasks",
        "dash_measures",
        "dash_product_types",
        "dash_deputies",
        "dash_statuses",
        "dash_financing",
        "dash_sources",
        "dash_presentation_mode"
    ]:
        if key in st.session_state:
            del st.session_state[key]


# ============================================================
# Aggregations
# ============================================================

def weighted_failure_group(df, group_col):
    if df.empty or group_col not in df.columns:
        return None

    active = df[~df["execution_status"].isin(["Не настав час", "Втратило актуальність"])].copy()

    if active.empty:
        return None

    grouped = active.groupby(group_col).agg(
        total=("code", "count"),
        failed=("execution_status", lambda x: (x == "Не виконано").sum()),
        avg_progress=("progress_pct", "mean")
    ).reset_index()

    grouped["failure_weight"] = grouped["failed"] / max(len(active), 1)
    grouped = grouped.sort_values(
        ["failure_weight", "failed", "total"],
        ascending=[False, False, False]
    )

    if grouped.empty:
        return None

    return grouped.iloc[0].to_dict()


def count_status(df, status):
    if df.empty:
        return 0
    return int((df["execution_status"] == status).sum())


def pct(value, total):
    if total == 0:
        return "0.0%"
    return f"{value / total * 100:.1f}%"


def average_progress(df):
    active = df[~df["execution_status"].isin(["Не настав час", "Втратило актуальність"])].copy()

    if active.empty:
        return 0.0

    return float(active["progress_pct"].fillna(0).mean())


def average_deviation(df):
    active = df[~df["execution_status"].isin(["Не настав час", "Втратило актуальність"])].copy()

    if active.empty:
        return 0.0

    return float(active["deviation_pct"].fillna(-100).mean())


# ============================================================
# Chart helpers
# ============================================================

def empty_chart(message="Немає даних для відображення."):
    st.info(message)


def plot_gauge(value):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": "%", "font": {"size": 54}},
            title={"text": "Середній прогрес виконання", "font": {"size": 20}},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#2563eb"},
                "steps": [
                    {"range": [0, 40], "color": "#fee2e2"},
                    {"range": [40, 70], "color": "#fef3c7"},
                    {"range": [70, 100], "color": "#dcfce7"},
                ],
                "threshold": {
                    "line": {"color": "#111827", "width": 4},
                    "thickness": 0.75,
                    "value": value,
                },
            },
        )
    )

    fig.update_layout(height=390, margin=dict(l=20, r=20, t=55, b=20))
    st.plotly_chart(fig, use_container_width=True)


def plot_progress_bars(df):
    indicators = pd.DataFrame({
        "Показник": [
            "Середній прогрес виконання",
            "Покриття моніторингом",
            "Погоджені відомості",
            "Середнє відхилення від плану"
        ],
        "Значення": [
            average_progress(df),
            df["has_submission"].mean() * 100 if not df.empty else 0,
            (df["approval_status"] == "Погоджено").mean() * 100 if not df.empty else 0,
            max(0, 100 + average_deviation(df))
        ]
    })

    fig = px.bar(
        indicators,
        x="Значення",
        y="Показник",
        orientation="h",
        text=indicators["Значення"].round(1).astype(str) + "%"
    )

    fig.update_layout(
        height=310,
        xaxis_title="%",
        yaxis_title="",
        xaxis_range=[0, 100],
        margin=dict(l=10, r=20, t=20, b=20)
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_traffic_light(df):
    if df.empty:
        empty_chart()
        return

    traffic = df.copy()

    def traffic_status(row):
        if row["execution_status"] in ["Не настав час", "Втратило актуальність"]:
            return "Не включається до оцінки"
        if row["progress_pct"] is not None and row["progress_pct"] >= 100 and row["approval_status"] == "Погоджено":
            return "У графіку"
        if row["progress_pct"] is not None and row["progress_pct"] >= 75:
            return "Потребує уваги"
        return "Відстає"

    traffic["traffic_light"] = traffic.apply(traffic_status, axis=1)

    grouped = traffic["traffic_light"].value_counts().reset_index()
    grouped.columns = ["Статус", "Кількість"]

    fig = px.pie(
        grouped,
        names="Статус",
        values="Кількість",
        hole=0.55,
        color="Статус",
        color_discrete_map={
            "У графіку": "#22c55e",
            "Потребує уваги": "#facc15",
            "Відстає": "#ef4444",
            "Не включається до оцінки": "#94a3b8"
        }
    )

    fig.update_layout(
        height=410,
        margin=dict(l=10, r=10, t=35, b=10),
        title="Розподіл активних заходів за станом виконання"
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_goal_performance(df):
    if df.empty:
        empty_chart()
        return

    grouped = df.groupby("parent_goal_code", dropna=False).agg(
        progress=("progress_pct", "mean"),
        total=("code", "count")
    ).reset_index()

    grouped["parent_goal_code"] = grouped["parent_goal_code"].replace("", "Без СЦ")
    grouped = grouped.sort_values("parent_goal_code", key=lambda s: s.map(code_sort_key))

    fig = px.bar(
        grouped,
        x="parent_goal_code",
        y="progress",
        text=grouped["progress"].fillna(0).round(1).astype(str) + "%",
        hover_data=["total"]
    )

    fig.update_layout(
        height=440,
        xaxis_title="Стратегічна ціль",
        yaxis_title="Середній прогрес, %",
        yaxis_range=[0, 100],
        margin=dict(l=10, r=20, t=25, b=80)
    )

    st.plotly_chart(fig, use_container_width=True)


def explode_by_ssp(df):
    rows = []

    for _, row in df.iterrows():
        values = []
        for field in ["resp_main", "resp_co_1", "resp_co_2"]:
            val = raw_value(row.get(field, ""))
            if val:
                values.append(val)

        if not values:
            values = ["Не визначено"]

        for value in values:
            item = row.to_dict()
            item["ssp"] = value
            rows.append(item)

    return pd.DataFrame(rows)


def plot_ssp_rating_table(df):
    if df.empty:
        st.info("Немає даних для рейтингу.")
        return

    exploded = explode_by_ssp(df)

    rating = exploded.groupby("ssp").agg(
        Виконання=("progress_pct", "mean"),
        Покриття_моніторингом=("has_submission", "mean"),
        Ризикових=("risk_score", lambda x: (x >= 40).sum()),
        Критичних=("risk_score", lambda x: (x >= 60).sum()),
        Активних_заходів=("code", "count")
    ).reset_index()

    rating["Виконання"] = rating["Виконання"].fillna(0).round(1)
    rating["Покриття_моніторингом"] = (rating["Покриття_моніторингом"] * 100).round(1)
    rating = rating.sort_values(["Виконання", "Покриття_моніторингом"], ascending=[False, False]).reset_index(drop=True)
    rating.insert(0, "Місце", rating.index + 1)

    def row_style(row):
        place = row["Місце"]
        total = len(rating)

        if place <= 3:
            return ["background-color: #dcfce7; color: #14532d; font-weight: 750"] * len(row)
        if place <= 10:
            return ["background-color: #e0f2fe; color: #0c4a6e"] * len(row)
        if place > max(total - 7, 10):
            return ["background-color: #fee2e2; color: #7f1d1d"] * len(row)

        return ["background-color: #f8fafc; color: #334155"] * len(row)

    styled = (
        rating.style
        .apply(row_style, axis=1)
        .set_properties(**{
            "text-align": "center",
            "border": "1px solid #d8dee9"
        })
        .set_table_styles([
            {
                "selector": "th",
                "props": [
                    ("text-align", "center"),
                    ("background-color", "#e9eef7"),
                    ("color", "#111827"),
                    ("font-weight", "900"),
                    ("border", "1px solid #d8dee9")
                ]
            }
        ])
    )

    st.dataframe(styled, use_container_width=True, hide_index=True)


def plot_ssp_performance(df):
    if df.empty:
        empty_chart()
        return

    exploded = explode_by_ssp(df)

    grouped = exploded.groupby("ssp").agg(
        progress=("progress_pct", "mean"),
        total=("code", "count")
    ).reset_index()

    grouped["progress"] = grouped["progress"].fillna(0)
    grouped = grouped.sort_values("progress", ascending=False)

    fig = px.bar(
        grouped,
        x="ssp",
        y="progress",
        text=grouped["progress"].round(1).astype(str) + "%",
        hover_data=["total"]
    )

    fig.update_layout(
        height=520,
        xaxis_title="Самостійний структурний підрозділ",
        yaxis_title="Середній прогрес, %",
        yaxis_range=[0, 100],
        margin=dict(l=10, r=20, t=25, b=120)
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_deputy_performance(df):
    if df.empty:
        empty_chart()
        return

    grouped = df.groupby("deputy_minister").agg(
        progress=("progress_pct", "mean"),
        total=("code", "count")
    ).reset_index()

    grouped["deputy_minister"] = grouped["deputy_minister"].replace("", "Не визначено")
    grouped["progress"] = grouped["progress"].fillna(0)

    fig = px.bar(
        grouped,
        x="deputy_minister",
        y="progress",
        text=grouped["progress"].round(1).astype(str) + "%",
        hover_data=["total"]
    )

    fig.update_layout(
        height=420,
        xaxis_title="Заступник Міністра",
        yaxis_title="Середній прогрес, %",
        yaxis_range=[0, 100],
        margin=dict(l=10, r=20, t=25, b=90)
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_risk_structure(df):
    if df.empty:
        empty_chart()
        return

    active = df[~df["execution_status"].isin(["Не настав час", "Втратило актуальність"])].copy()

    grouped = active["risk_level"].value_counts().reset_index()
    grouped.columns = ["Рівень ризику", "Кількість"]

    fig = px.pie(
        grouped,
        names="Рівень ризику",
        values="Кількість",
        hole=0.55,
        color="Рівень ризику",
        color_discrete_map={
            "Низький ризик": "#60a5fa",
            "Середній ризик": "#2563eb",
            "Не оцінюється": "#94a3b8"
        }
    )

    fig.update_layout(
        height=400,
        title="Рівень ризику недосягнення",
        margin=dict(l=10, r=10, t=45, b=10)
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_risks_by_ssp(df):
    if df.empty:
        empty_chart()
        return

    exploded = explode_by_ssp(df)
    active = exploded[~exploded["execution_status"].isin(["Не настав час", "Втратило актуальність"])].copy()

    grouped = active.groupby(["ssp", "risk_level"]).size().reset_index(name="Кількість")

    fig = px.bar(
        grouped,
        x="ssp",
        y="Кількість",
        color="risk_level",
        barmode="group",
        color_discrete_map={
            "Низький ризик": "#60a5fa",
            "Середній ризик": "#2563eb",
            "Не оцінюється": "#94a3b8"
        }
    )

    fig.update_layout(
        height=470,
        xaxis_title="Самостійний структурний підрозділ",
        yaxis_title="Кількість заходів",
        legend_title="Ризик",
        margin=dict(l=10, r=20, t=25, b=110)
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_progress_dynamics(measures_df, monitoring_df, selected_years):
    rows = []

    years = selected_years if selected_years else [2026, 2027, 2028]

    for year in years:
        for quarter in ["1", "2", "3", "4"]:
            period_df = build_dashboard_dataset(measures_df, monitoring_df, [year], [quarter])
            rows.append({
                "Період": f"{year} {quarter}",
                "Виконання": average_progress(period_df),
                "Відхилення": average_deviation(period_df)
            })

    trend = pd.DataFrame(rows)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=trend["Період"],
        y=trend["Виконання"],
        mode="lines+markers",
        name="Виконання, %"
    ))

    fig.add_trace(go.Scatter(
        x=trend["Період"],
        y=trend["Відхилення"],
        mode="lines+markers",
        name="Відхилення від плану, в.п."
    ))

    fig.update_layout(
        height=430,
        xaxis_title="Період",
        yaxis_title="Значення",
        margin=dict(l=10, r=20, t=25, b=70)
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_heatmap(df):
    if df.empty:
        empty_chart()
        return

    exploded = explode_by_ssp(df)

    pivot = exploded.pivot_table(
        index="ssp",
        columns="parent_goal_code",
        values="progress_pct",
        aggfunc="mean"
    ).fillna(0)

    if pivot.empty:
        empty_chart()
        return

    pivot = pivot.sort_index()
    pivot = pivot.reindex(sorted(pivot.columns, key=code_sort_key), axis=1)

    fig = px.imshow(
        pivot,
        text_auto=".1f",
        aspect="auto",
        color_continuous_scale="Blues",
        zmin=0,
        zmax=100
    )

    fig.update_layout(
        height=max(420, 24 * len(pivot.index)),
        xaxis_title="Стратегічна ціль",
        yaxis_title="Самостійний структурний підрозділ",
        coloraxis_colorbar_title="Середній прогрес, %",
        margin=dict(l=10, r=20, t=25, b=80)
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_top_low_quantitative(df):
    data = df[
        (df["is_quantitative"] == True) &
        (~df["execution_status"].isin(["Не настав час", "Втратило актуальність"]))
    ].copy()

    if data.empty:
        empty_chart("Немає кількісних заходів для порівняння план / факт.")
        return

    data["progress_pct"] = data["progress_pct"].fillna(0)
    data = data.sort_values("progress_pct").head(25)

    fig = px.bar(
        data,
        x="code",
        y="progress_pct",
        text=data["progress_pct"].round(1).astype(str) + "%",
        hover_data=["measure_name", "fact_value", "target_value"]
    )

    fig.update_layout(
        height=470,
        xaxis_title="Код заходу",
        yaxis_title="План / факт, %",
        yaxis_range=[0, 100],
        margin=dict(l=10, r=20, t=25, b=80)
    )

    st.plotly_chart(fig, use_container_width=True)


def render_problem_measures(df):
    if df.empty:
        st.info("Проблемних заходів за обраними параметрами не знайдено.")
        return

    data = df[
        (
            (df["risk_score"] >= 40) |
            (df["has_submission"] == False) |
            (df["progress_pct"].fillna(0) < 75)
        ) &
        (~df["execution_status"].isin(["Не настав час", "Втратило актуальність"]))
    ].copy()

    if data.empty:
        st.success("За обраними параметрами немає заходів із суттєвими ризиками.")
        return

    data = data.sort_values(["risk_score", "progress_pct"], ascending=[False, True])

    table = data[[
        "code",
        "measure_name",
        "parent_goal_code",
        "resp_main",
        "target_value",
        "fact_value",
        "progress_pct",
        "approval_status",
        "execution_status",
        "risk_level",
        "risk_score",
        "risk_reason",
        "progress_text"
    ]].copy()

    table.columns = [
        "Код",
        "Захід",
        "СЦ",
        "Головний ССП",
        "Планове значення",
        "Фактичне значення",
        "Виконання, %",
        "Статус погодження",
        "Статус виконання",
        "Рівень ризику",
        "Risk score",
        "Причина ризику",
        "Опис прогресу"
    ]

    table["Виконання, %"] = table["Виконання, %"].fillna(0).round(1)

    st.dataframe(table, use_container_width=True, hide_index=True)


# ============================================================
# Render page
# ============================================================

st.markdown(
    """
<div class="dashboard-header">
    <div class="dashboard-title">Аналітичний дашборд результативності стратегічного плану</div>
    <div class="dashboard-subtitle">
        Аналітична панель забезпечує комплексне представлення результатів виконання Стратегічного плану.
        Інфографіка та моніторингові звіти формуються за результатами проведення оцінки на основі
        моніторингу й оцінювання стратегічних результатів як у цілому, так і в розрізі кожного
        самостійного структурного підрозділу окремо.
    </div>
</div>
""",
    unsafe_allow_html=True
)

strat_df = load_strat_matrix()
monitoring_df = ensure_monitoring_columns(load_monitoring())

all_measures = strat_df[strat_df["object_type"] == "measure"].copy()

available_years = sorted(
    set([2026, 2027, 2028] + [
        int(y) for y in monitoring_df["year"].dropna().astype(str).tolist()
        if str(y).isdigit()
    ])
)

available_quarters = ["1", "2", "3", "4"]

goals_for_filter = (
    all_measures[["parent_goal_code", "parent_goal_name"]]
    .drop_duplicates()
    .sort_values("parent_goal_code", key=lambda s: s.map(code_sort_key))
)

tasks_for_filter = (
    all_measures[["parent_task_code", "parent_task_name"]]
    .drop_duplicates()
    .sort_values("parent_task_code", key=lambda s: s.map(code_sort_key))
)

measures_for_filter = (
    all_measures[["code", "name"]]
    .drop_duplicates()
    .sort_values("code", key=lambda s: s.map(code_sort_key))
)

ssp_options = sorted(
    set(
        split_ssp_values(" | ".join(
            all_measures[["resp_main", "resp_co_1", "resp_co_2"]]
            .fillna("")
            .astype(str)
            .agg(" | ".join, axis=1)
            .tolist()
        ))
    ),
    key=lambda x: int(x) if x.isdigit() else 9999
)

source_options = unique_clean_values(all_measures["source_national"])
product_type_options = unique_clean_values(all_measures["product_type"])
deputy_options = unique_clean_values(all_measures["deputy_minister_raw"])

st.markdown(
    """
<div class="filter-box">
    <div class="filter-title">Параметри відбору</div>
    <div class="filter-legend">
        Оберіть необхідні параметри: період, індекс ССП та режим перегляду даних.
    </div>
</div>
""",
    unsafe_allow_html=True
)

with st.container():
    top_cols = st.columns([1.2, 1.2, 1.2, 1.2])

    with top_cols[0]:
        selected_years = st.multiselect(
            "Звітний період: рік",
            options=available_years,
            default=[2026] if 2026 in available_years else available_years[:1],
            key="dash_years"
        )

    with top_cols[1]:
        selected_quarters = st.multiselect(
            "Звітний період: квартал",
            options=available_quarters,
            default=available_quarters,
            key="dash_quarters"
        )

    with top_cols[2]:
        selected_ssp = st.multiselect(
            "Індекс самостійного структурного підрозділу",
            options=ssp_options,
            key="dash_ssp"
        )

    with top_cols[3]:
        presentation_mode = st.toggle(
            "Presentation mode",
            value=False,
            key="dash_presentation_mode",
            help="Показує скорочену презентаційну версію: ключові показники, висновок, інсайти та основні графіки."
        )

    row_2 = st.columns([1, 1, 1])

    with row_2[0]:
        selected_goals = st.multiselect(
            "Стратегічна ціль",
            options=goals_for_filter["parent_goal_code"].tolist(),
            format_func=lambda x: f"{x} — {goals_for_filter.loc[goals_for_filter['parent_goal_code'] == x, 'parent_goal_name'].iloc[0]}",
            key="dash_goals"
        )

    with row_2[1]:
        selected_tasks = st.multiselect(
            "Завдання",
            options=tasks_for_filter["parent_task_code"].tolist(),
            format_func=lambda x: f"{x} — {tasks_for_filter.loc[tasks_for_filter['parent_task_code'] == x, 'parent_task_name'].iloc[0]}",
            key="dash_tasks"
        )

    with row_2[2]:
        selected_measures = st.multiselect(
            "Захід",
            options=measures_for_filter["code"].tolist(),
            format_func=lambda x: f"{x} — {strip_leading_code(measures_for_filter.loc[measures_for_filter['code'] == x, 'name'].iloc[0], x)}",
            key="dash_measures"
        )

    row_3 = st.columns([1, 1, 1])

    with row_3[0]:
        selected_product_types = st.multiselect(
            "Тип продукту",
            options=product_type_options,
            key="dash_product_types"
        )

    with row_3[1]:
        selected_deputies = st.multiselect(
            "Заступник Міністра",
            options=deputy_options,
            key="dash_deputies",
            help="Поки поле є технічною заготовкою, бо заступники ще не прив’язані."
        )

    with row_3[2]:
        selected_statuses = st.multiselect(
            "Статус виконання",
            options=EXECUTION_STATUSES,
            key="dash_statuses"
        )

    row_4 = st.columns([1, 1, 1])

    with row_4[0]:
        selected_financing = st.multiselect(
            "Фінансування",
            options=[],
            key="dash_financing",
            help="Поки даних немає. Фільтр залишений як технічна заготовка."
        )

    with row_4[1]:
        selected_sources = st.multiselect(
            "Джерело даних: національний рівень",
            options=source_options,
            key="dash_sources"
        )

    with row_4[2]:
        st.write("")
        st.write("")
        if st.button("Скинути фільтри", use_container_width=True):
            reset_dashboard_filters()
            st.rerun()


base_dashboard_df = build_dashboard_dataset(
    all_measures,
    monitoring_df,
    selected_years,
    selected_quarters
)

filters = {
    "years": selected_years,
    "quarters": selected_quarters,
    "ssp_indices": selected_ssp,
    "goals": selected_goals,
    "tasks": selected_tasks,
    "measures": selected_measures,
    "product_types": selected_product_types,
    "deputies": selected_deputies,
    "execution_statuses": selected_statuses,
    "financing": selected_financing,
    "sources_national": selected_sources
}

dashboard_df = apply_filters(base_dashboard_df, filters)

total_measures = len(dashboard_df)
approved_count = int((dashboard_df["approval_status"] == "Погоджено").sum()) if not dashboard_df.empty else 0
review_count = int((dashboard_df["approval_status"] == "На розгляді").sum()) if not dashboard_df.empty else 0
not_counted_count = int((dashboard_df["approval_status"] == "Не враховано").sum()) if not dashboard_df.empty else 0

completed_count = count_status(dashboard_df, "Виконано")
partly_count = count_status(dashboard_df, "Частково виконано")
not_done_count = count_status(dashboard_df, "Не виконано")
not_time_count = count_status(dashboard_df, "Не настав час")
obsolete_count = count_status(dashboard_df, "Втратило актуальність")
in_progress_count = count_status(dashboard_df, "Виконується")

avg_progress_value = average_progress(dashboard_df)
avg_deviation_value = average_deviation(dashboard_df)

st.markdown('<div class="section-title">Прогрес виконання: висновок системи</div>', unsafe_allow_html=True)

if avg_progress_value < 40 or approved_count / max(total_measures, 1) < 0.3:
    st.markdown(
        """
<div class="bad-box">
    Поточні дані вказують на недостатній рівень подання та погодження відомостей
    або на суттєві відхилення від планових показників.
</div>
""",
        unsafe_allow_html=True
    )
else:
    st.success("Поточні дані не вказують на критичне відхилення за обраними параметрами.")

render_metric_grid([
    ("Заходів", total_measures),
    ("Виконано", completed_count),
    ("Погоджено", approved_count),
    ("На розгляді", review_count),
    ("Не враховано", not_counted_count),
])

render_metric_grid([
    ("Не виконано", not_done_count),
    ("Втратив актуальність", obsolete_count),
    ("Термін не настав", not_time_count),
    ("Частково виконано", partly_count),
    ("Виконується", in_progress_count),
])

render_metric_grid([
    ("Виконано, %", pct(completed_count, total_measures)),
    ("Погоджено, %", pct(approved_count, total_measures)),
    ("На розгляді, %", pct(review_count, total_measures)),
    ("Не враховано, %", pct(not_counted_count, total_measures)),
    ("Середній прогрес, %", f"{avg_progress_value:.1f}%"),
])


# ============================================================
# Insights
# ============================================================

st.markdown('<div class="section-title">Автоматичні інсайти</div>', unsafe_allow_html=True)

goal_failure = weighted_failure_group(dashboard_df, "parent_goal_code")
ssp_failure = weighted_failure_group(explode_by_ssp(dashboard_df), "ssp")

insight_lines = []

if goal_failure:
    insight_lines.append(
        f"Найбільша концентрація невиконаних заходів за стратегічною ціллю: "
        f"<strong>СЦ {safe_html(goal_failure['parent_goal_code'])}</strong> — "
        f"{goal_failure['failed']} невиконаних із {goal_failure['total']} заходів у групі; "
        f"вага невиконання в обраному портфелі — {goal_failure['failure_weight'] * 100:.1f}%."
    )

if ssp_failure:
    insight_lines.append(
        f"Самостійний структурний підрозділ із найвищою концентрацією невиконаних заходів: "
        f"<strong>{safe_html(ssp_failure['ssp'])}</strong> — "
        f"{ssp_failure['failed']} невиконаних із {ssp_failure['total']} заходів у групі; "
        f"вага невиконання в обраному портфелі — {ssp_failure['failure_weight'] * 100:.1f}%."
    )

insight_lines.append(
    f"Відхилення за звітний період: <strong>{avg_deviation_value:.1f} в.п.</strong> "
    f"відносно планового рівня."
)

st.markdown(
    '<div class="insight-box">' + "<br>".join(insight_lines) + "</div>",
    unsafe_allow_html=True
)


# ============================================================
# Presentation mode
# ============================================================

st.markdown('<div class="section-title">Показники виконання стратегічного плану</div>', unsafe_allow_html=True)

if dashboard_df.empty:
    st.warning("За обраними параметрами немає даних.")
else:
    col_1, col_2 = st.columns([1, 1])

    with col_1:
        st.markdown('<div class="card"><div class="card-title">Індикатор середнього прогресу</div>', unsafe_allow_html=True)
        plot_gauge(avg_progress_value)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_2:
        st.markdown('<div class="card"><div class="card-title">Лінійні індикатори стану</div>', unsafe_allow_html=True)
        plot_progress_bars(dashboard_df)
        st.markdown("</div>", unsafe_allow_html=True)

    col_3, col_4 = st.columns([1, 1])

    with col_3:
        st.markdown('<div class="card"><div class="card-title">Статуси виконання за принципом світлофора</div>', unsafe_allow_html=True)
        plot_traffic_light(dashboard_df)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_4:
        st.markdown('<div class="card"><div class="card-title">Виконання за стратегічними цілями</div>', unsafe_allow_html=True)
        plot_goal_performance(dashboard_df)
        st.markdown("</div>", unsafe_allow_html=True)


if not presentation_mode:
    st.markdown('<div class="section-title">Рейтинг самостійних структурних підрозділів</div>', unsafe_allow_html=True)
    plot_ssp_rating_table(dashboard_df)

    st.markdown('<div class="section-title">Виконання за самостійними структурними підрозділами</div>', unsafe_allow_html=True)
    plot_ssp_performance(dashboard_df)

    st.markdown('<div class="section-title">Виконання за Заступниками Міністра</div>', unsafe_allow_html=True)
    plot_deputy_performance(dashboard_df)

    risk_col_1, risk_col_2 = st.columns([1, 1])

    with risk_col_1:
        st.markdown('<div class="section-title">Автоматична оцінка ризиків</div>', unsafe_allow_html=True)
        plot_risk_structure(dashboard_df)

    with risk_col_2:
        st.markdown('<div class="section-title">Структура ризиків за самостійними структурними підрозділами</div>', unsafe_allow_html=True)
        plot_risks_by_ssp(dashboard_df)

    st.markdown('<div class="section-title">Динаміка виконання</div>', unsafe_allow_html=True)
    plot_progress_dynamics(
        all_measures,
        monitoring_df,
        selected_years if selected_years else [2026]
    )

    st.markdown('<div class="section-title">Теплова карта виконання</div>', unsafe_allow_html=True)
    plot_heatmap(dashboard_df)

    st.markdown('<div class="section-title">Порівняння план / факт</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtitle">ТОП-25 заходів із найнижчим виконанням планового показника. '
        'До розрахунку включаються лише заходи з кількісними показниками.</div>',
        unsafe_allow_html=True
    )
    plot_top_low_quantitative(dashboard_df)

    st.markdown('<div class="section-title">Проблемні заходи</div>', unsafe_allow_html=True)
    render_problem_measures(dashboard_df)

    st.markdown(
        """
<div class="methodology-box">
    <strong>Методологія автоматичної оцінки ризиків.</strong><br>
    Ризик визначається не за текстовим полем «ризики», а за фактичним станом виконання заходу.
    Якщо за активним заходом не подано моніторингові дані або дані не погоджені, такий захід
    позначається як ризиковий. Для кількісних показників система порівнює фактичне значення з
    плановим: 100% і більше — виконано або перевиконано; від 75% до 99% включно — часткове
    виконання; нижче 75% — істотне відставання. Заходи зі статусами «Не настав час» та
    «Втратило актуальність» не включаються до ризикової оцінки. Поле з описом ризиків у заявці
    використовується як довідкова інформація для адміністраторів і не є основою автоматичного
    розрахунку.
</div>
""",
        unsafe_allow_html=True
    )


st.markdown(
    """
<div class="footer">
    <strong>Розроблено департаментом стратегічного планування та макроекономічного прогнозування</strong><br>
    Версія DEMO 1.4 | 2026 | Внутрішня система моніторингу стратегічного плану
</div>
""",
    unsafe_allow_html=True
)
