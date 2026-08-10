import re
from datetime import datetime
from io import BytesIO
from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st
from core.period_locks import exclude_locked_periods, is_period_locked
from core.timeutils import now_kyiv
from core.db import fetch_all, get_supabase_client
from core.deputies import DEPUTY_MINISTER_BY_SSP
from core.ui import load_css, render_readonly_table
from core.config import FILE_PATH, SHEET_NAME
from core.excel_loader import read_excel_sheet
from core.exports import fig_png_bytes
from core import exports as core_exports
import plotly.express as _px_rep

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

from core.page_setup import page_setup, render_footer
from core.strategic_data import load_strat_matrix as core_load_strat_matrix
from core import monitoring_data
from core import statuses as core_statuses
from core import operational
from core import dashboard_metrics
from core import periods as core_periods
from core.closeouts import append_confirmed_closeout_facts
from core.errors import show_warning
from core.stage4 import (
    build_approval_speed_analytics,
    build_return_analytics,
    data_read_caption,
    kyiv_now,
)


# ============================================================
# Page config
# ============================================================

current_user = page_setup("Аналітика", page_name="Аналітика")


supabase = get_supabase_client()
# ============================================================
# CSS
# ============================================================

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
.filter-box,
.card,
.report-box,
.export-box,
.table-box {
    background: rgba(255,255,255,0.96);
    border: 1px solid #DCE4F0;
    border-radius: 16px;
    box-shadow: 0 8px 24px rgba(15,23,42,0.06);
}

.header-box {
    padding: 22px 26px;
    margin-bottom: 18px;
    backdrop-filter: blur(8px);
}

.header-title {
    font-size: 32px;
    font-weight: 950;
    color: #132238;
    margin-bottom: 8px;
}

.header-subtitle,
.card-subtitle,
.filter-subtitle {
    font-size: 15px;
    color: #61708A;
    line-height: 1.55;
}

.badge-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 14px;
}

.badge {
    background: #EAF1FF;
    border: 1px solid #BFD3F2;
    color: #005BBB;
    border-radius: 999px;
    padding: 7px 11px;
    font-size: 13px;
    font-weight: 850;
}

.badge-green {
    background: #E4F5EC;
    border-color: #1E9E57;
    color: #0C713A;
}

.badge-yellow {
    background: #FDF3D8;
    border-color: #F4B400;
    color: #8A6400;
}

.filter-box,
.card,
.export-box,
.table-box {
    padding: 22px 24px;
    margin-bottom: 18px;
}

.card-title,
.filter-title,
.report-title {
    font-size: 21px;
    font-weight: 950;
    color: #132238;
    margin-bottom: 8px;
}

.filter-box {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
}

.filter-section-title {
    color: #132238;
    font-size: 15px;
    font-weight: 950;
    margin: 14px 0 10px 0;
    padding-bottom: 5px;
    border-bottom: 1px solid rgba(148,163,184,0.35);
}

/* Stronger color for all report filters */
[data-testid="stMain"] div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stMain"] div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
[data-testid="stMain"] div[data-testid="stTextInput"] input {
    background-color: #EAF1FF !important;
    border: 1px solid #BFD3F2 !important;
    border-radius: 10px !important;
    min-height: 43px !important;
    box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.08) !important;
}

[data-testid="stMain"] div[data-testid="stSelectbox"] label,
[data-testid="stMain"] div[data-testid="stMultiSelect"] label,
[data-testid="stMain"] div[data-testid="stTextInput"] label {
    font-weight: 850 !important;
    color: #132238 !important;
}

.alert-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    margin: 14px 0 18px 0;
}

.alert-card {
    border-radius: 16px;
    padding: 17px 18px;
    border: 1px solid #DCE4F0;
    box-shadow: 0 8px 20px rgba(15,23,42,0.06);
}

.alert-title {
    font-size: 13px;
    color: #61708A;
    font-weight: 900;
    line-height: 1.35;
    min-height: 36px;
}

.alert-value {
    font-size: 28px;
    color: #132238;
    font-weight: 950;
    margin-top: 8px;
}

.alert-note {
    font-size: 12px;
    color: #61708A;
    margin-top: 6px;
    line-height: 1.3;
}

.alert-blue {
    background: #EAF1FF;
    border-color: #BFD3F2;
}

.alert-green {
    background: #E4F5EC;
    border-color: #1E9E57;
}

.alert-yellow {
    background: #FDF3D8;
    border-color: #F4B400;
}

.alert-red {
    background: #FBE5E5;
    border-color: #DC4A4A;
}

.report-box {
    border-left: 7px solid #005BBB;
    padding: 24px 28px;
    margin: 18px 0;
}

.report-title {
    font-size: 24px;
    margin-bottom: 12px;
}

.report-text {
    font-size: 15px;
    line-height: 1.75;
    color: #61708A;
    text-align: justify;
}

.report-meta {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-radius: 12px;
    padding: 12px 14px;
    color: #61708A;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 12px;
}

[data-testid="stMain"] div.stDownloadButton > button,
[data-testid="stMain"] div.stButton > button {
    border-radius: 12px;
    padding: 12px 18px;
    font-weight: 850;
}

.footer {
    text-align: center;
    color: #61708A;
    font-size: 13px;
    margin-top: 50px;
    padding: 22px 0 12px 0;
    border-top: 1px solid #DCE4F0;
}

@media (max-width: 1100px) {
    .alert-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}
</style>
""",
    unsafe_allow_html=True
)


# ============================================================
# Helpers
# ============================================================

QUARTERS = ["I", "II", "III", "IV"]
YEAR_OPTIONS = [2026, 2027, 2028]

def raw_value(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value).strip()


def clean(value):
    return escape(raw_value(value))


def normalize_text(value):
    return raw_value(value).lower().replace("і", "i")


def is_empty_or_nd(value):
    return normalize_text(value).replace(" ", "") in {"", "н.д.", "нд", "nan", "none", "-", "—"}


def extract_ssp_index(value):
    text = raw_value(value)
    match = re.search(r"\d+", text)
    return match.group(0) if match else ""


def split_ssp_values(value):
    return re.findall(r"\d+", raw_value(value))


def get_deputy_minister_by_main_ssp(value):
    index = extract_ssp_index(value)
    return DEPUTY_MINISTER_BY_SSP.get(index, "")


def ssp_sort_key(value):
    index = extract_ssp_index(value)
    return (int(index) if index.isdigit() else 10_000, raw_value(value))


def get_goal_code(code):
    parts = raw_value(code).split(".")
    return parts[0] + "." if parts and parts[0] else ""


def get_task_code(code):
    parts = raw_value(code).split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}."
    return ""


def quarter_to_number(q):
    """Business parser shared with Dashboard; invalid data is an explicit error."""
    return core_periods.quarter_to_number_strict(q)


def parse_period(value):
    text = normalize_text(value).strip()
    if text in ["", "nan", "none", "н.д.", "нд"]:
        return None

    q = None
    year = None

    if "1 квартал" in text or "i квартал" in text:
        q = 1
    elif "2 квартал" in text or "ii квартал" in text:
        q = 2
    elif "3 квартал" in text or "iii квартал" in text:
        q = 3
    elif "4 квартал" in text or "iv квартал" in text:
        q = 4

    year_match = re.search(r"20\d{2}", text)
    if year_match:
        year = int(year_match.group())

    if year and q:
        return year * 10 + q
    return None


def to_number(value):
    text = raw_value(value).replace(" ", "").replace(",", ".")
    if normalize_text(text) in ["", "nan", "none", "н.д.", "нд", "x", "х", "так", "ні", "yes", "no"]:
        return None
    match = re.search(r"-?\d+(\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group())
    except Exception:
        return None


def status_score(status):
    return dashboard_metrics.status_score(status)

def plan_fact_percent(actual, target):
    return dashboard_metrics.plan_fact_percent(actual, target)

def deviation_label(value):
    sign = "+" if value > 0 else ""
    return f"{sign}{round(value, 2)} в.п."


def deviation_card_class(value):
    if value >= 0:
        return "alert-green"
    if value >= -15:
        return "alert-yellow"
    return "alert-red"


def traffic_light(score):
    return dashboard_metrics.traffic_light(score)

def get_indicator_type(row):
    unit = normalize_text(row.get("unit", ""))
    if "так/нi" in unit or ("так" in unit and "нi" in unit):
        return "Так/ні"
    if "%" in unit or "відсот" in unit:
        return "Відсотковий"
    if any(x in unit for x in ["грн", "дол", "євро", "eur", "usd"]):
        return "Фінансовий"
    return "Кількісний"


def concise_list(values, limit=5):
    values = [raw_value(v) for v in values if raw_value(v)]
    if not values:
        return "н/д"
    if len(values) <= limit:
        return "; ".join(values)
    return "; ".join(values[:limit]) + f" та ще {len(values) - limit}"


def filter_label(selected, default_label="усі"):
    if not selected:
        return default_label
    return concise_list(selected, limit=4)


# ============================================================
# Data loading
# ============================================================

def load_strat_matrix():
    """ЄДИНЕ джерело — core.strategic_data (правка К1)."""
    return core_load_strat_matrix()


def load_requests():
    """ЄДИНЕ джерело — core.monitoring_data (правки К2, П2).
    Аналітика стосується ЗАХОДІВ — подання індикаторів відфільтровуються."""
    return monitoring_data.measures_only(monitoring_data.load_monitoring_requests())


def load_workflow_logs():
    """Повний журнал для тестової аналітики повернень і швидкості."""
    return pd.DataFrame(fetch_all("monitoring_logs", "*", order=("changed_at", False)))


def ensure_request_columns(requests_df):
    required = [
        "id", "year", "quarter", "department", "strat_code", "status", "numeric_value",
        "risks", "progress_text", "approval_status", "submitted_at", "responsible_person",
        "phone", "email", "file_names", "file_urls", "admin_comment", "start_date", "end_date"
    ]
    for col in required:
        if col not in requests_df.columns:
            requests_df[col] = ""
    return requests_df


# ============================================================
# Period and filtering logic
# ============================================================

def base_measures(strat_df):
    measures = strat_df[strat_df["object_type"] == "measure"].copy()
    goals = strat_df[strat_df["object_type"] == "goal"].copy()
    tasks = strat_df[strat_df["object_type"] == "task"].copy()

    goal_names = goals.set_index("code")["name"].to_dict()
    task_names = tasks.set_index("code")["name"].to_dict()

    measures["goal_code"] = measures["parent_goal_code"].where(measures["parent_goal_code"].astype(str).str.strip() != "", measures["code"].apply(get_goal_code))
    measures["task_code"] = measures["parent_task_code"].where(measures["parent_task_code"].astype(str).str.strip() != "", measures["code"].apply(get_task_code))
    measures["strategic_goal"] = measures["goal_code"].map(goal_names).fillna(measures["parent_goal_name"])
    measures["task_name"] = measures["task_code"].map(task_names).fillna(measures["parent_task_name"])
    measures["start_num"] = measures["start_period"].apply(parse_period)
    measures["end_num"] = measures["end_period"].apply(parse_period)
    measures["ssp_index"] = measures["resp_main"].apply(extract_ssp_index)
    measures["deputy_minister"] = measures["resp_main"].apply(get_deputy_minister_by_main_ssp)
    measures["indicator_type"] = measures.apply(get_indicator_type, axis=1)
    return measures


def is_active_for_period(row, year, quarter):
    selected_period_num = core_periods.period_number(year, quarter)
    return core_periods.get_period_state(
        row.get("start_num"), row.get("end_num"), selected_period_num
    ) == "active"

def latest_approved_records(requests_df, year, quarter):
    return dashboard_metrics.latest_approved_records(requests_df, year, quarter)

def prepare_period_slice(measures, requests_df, year, quarter):
    active = measures[measures.apply(lambda row: is_active_for_period(row, year, quarter), axis=1)].copy()

    target_col = f"target_{year}"
    active["selected_target"] = active[target_col] if target_col in active.columns else ""
    active["report_year"] = int(year)
    active["report_quarter"] = quarter
    active["report_quarter_num"] = quarter_to_number(quarter)
    active["report_period"] = f"{year} {quarter} квартал"
    active["expected_progress"] = dashboard_metrics.expected_completion_for_quarter(quarter_to_number(quarter))

    period_requests = latest_approved_records(requests_df, year, quarter)

    merge_cols = [
        "strat_code", "status", "numeric_value", "risks", "progress_text", "submitted_at",
        "responsible_person", "phone", "email", "file_names", "file_urls", "admin_comment"
    ]
    for col in merge_cols:
        if col not in period_requests.columns:
            period_requests[col] = ""

    active = active.merge(period_requests[merge_cols], left_on="code", right_on="strat_code", how="left")

    active["status"] = active["status"].fillna("Не подано").replace("", "Не подано")
    if is_period_locked(year, quarter):
        active["status"] = core_statuses.ST_NOTYET
    active["numeric_value"] = active["numeric_value"].fillna("")
    active["risks"] = active["risks"].fillna("")
    active["progress_text"] = active["progress_text"].fillna("")
    active["submitted_at"] = active["submitted_at"].fillna("")

    active["status_display"] = active["status"].map(dashboard_metrics.status_display)
    active["status_score"] = active["status"].map(dashboard_metrics.status_score)
    active["plan_fact_percent"] = active.apply(
        lambda r: dashboard_metrics.plan_fact_percent(r["numeric_value"], r["selected_target"]), axis=1
    )
    active["performance_score"] = active.apply(
        lambda r: dashboard_metrics.performance_score(r["status"], r["numeric_value"], r["selected_target"]),
        axis=1
    )
    active["expected_progress"] = dashboard_metrics.expected_completion_for_quarter(quarter_to_number(quarter))
    if is_period_locked(year, quarter):
        # Same Dashboard contract: locked periods are present but excluded.
        active["status_score"] = float("nan")
        active["performance_score"] = float("nan")
        active["expected_progress"] = float("nan")
    active["period_deviation"] = active.apply(
        lambda r: (r["performance_score"] - r["expected_progress"])
        if pd.notna(r["performance_score"]) and pd.notna(r["expected_progress"]) else float("nan"),
        axis=1,
    )
    active["traffic_light"] = active["performance_score"].map(dashboard_metrics.traffic_light)
    if is_period_locked(year, quarter):
        active["traffic_light"] = core_statuses.ST_NOTYET
    active["has_submission"] = active["status"] != "Не подано"
    _risk_empty = {"", "—", "-", "немає", "відсутні", "відсутній", "не виявлено"}
    active["has_text_risk"] = active["risks"].astype(str).str.strip().str.casefold().map(lambda v: v not in _risk_empty)
    active["is_problem_status"] = active.apply(
        lambda r: dashboard_metrics.is_problem(
            r.get("status"), r.get("performance_score"), has_risk=bool(r.get("has_text_risk"))
        ), axis=1
    )

    return active


def prepare_analysis_data(strat_df, requests_df, years, quarters):
    measures = base_measures(strat_df)
    parts = []
    for year in years:
        for quarter in quarters:
            parts.append(prepare_period_slice(measures, requests_df, year, quarter))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def apply_dimension_filters(data, selected_ssp, selected_deputies, selected_goals, selected_tasks, selected_product_types):
    filtered = data.copy()

    if selected_ssp:
        selected_indices = set(str(x) for x in selected_ssp)
        filtered = filtered[filtered["ssp_index"].astype(str).isin(selected_indices)]

    if selected_deputies:
        filtered = filtered[filtered["deputy_minister"].astype(str).isin(selected_deputies)]

    if selected_goals:
        filtered = filtered[filtered["goal_code"].astype(str).isin(selected_goals)]

    if selected_tasks:
        filtered = filtered[filtered["task_code"].astype(str).isin(selected_tasks)]

    if selected_product_types:
        filtered = filtered[filtered["product_type"].astype(str).isin(selected_product_types)]

    return filtered.copy()


# ============================================================
# Aggregations and report text
# ============================================================

def build_metrics(active):
    total = len(active)
    submitted = int(active["has_submission"].sum()) if total else 0
    coverage = round(submitted / total * 100, 2) if total else 0
    completion_base = exclude_locked_periods(active, year_col="report_year", quarter_col="report_quarter")
    completion = round(completion_base["performance_score"].mean(), 2) if not completion_base.empty else 0
    expected = round(completion_base["expected_progress"].mean(), 2) if not completion_base.empty else 0
    deviation = round(completion - expected, 2)
    unique_measures = active["code"].nunique() if total else 0
    goals = active["goal_code"].nunique() if total else 0
    tasks = active["task_code"].nunique() if total else 0
    no_data = int((active["status"] == "Не подано").sum()) if total else 0
    completed = int((active["status"] == "Виконано").sum()) if total else 0
    problem = int(active["is_problem_status"].fillna(False).sum()) if total else 0

    return {
        "total_rows": total,
        "unique_measures": unique_measures,
        "submitted": submitted,
        "coverage": coverage,
        "completion": completion,
        "expected": expected,
        "deviation": deviation,
        "goals": goals,
        "tasks": tasks,
        "no_data": no_data,
        "completed": completed,
        "problem": problem,
    }



def build_year_over_year_comparison(data):
    """Build year-to-year comparison using the same calculation base as analytics metrics."""
    if data.empty or "report_year" not in data.columns:
        return pd.DataFrame()

    rows = []
    by_year = {}
    for year, group in data.groupby("report_year"):
        by_year[int(year)] = build_metrics(group)

    years = sorted(by_year.keys())
    if len(years) < 2:
        return pd.DataFrame()

    indicators = [
        ("Унікальні заходи", "unique_measures", "од."),
        ("Записи захід-період", "total_rows", "од."),
        ("Покриття моніторингом", "coverage", "%"),
        ("Рівень виконання СП", "completion", "%"),
        ("Очікуваний темп", "expected", "%"),
        ("Відхилення", "deviation", "в.п."),
        ("Без поданих погоджених даних", "no_data", "од."),
        ("Виконано", "completed", "од."),
        ("Проблемні / ризикові", "problem", "од."),
    ]

    for previous_year, current_year in zip(years[:-1], years[1:]):
        previous = by_year[previous_year]
        current = by_year[current_year]
        for label, key, unit in indicators:
            prev_value = previous.get(key, 0)
            curr_value = current.get(key, 0)
            change = round(curr_value - prev_value, 2)
            rows.append({
                "Період порівняння": f"{current_year} до {previous_year}",
                "Показник": label,
                "Попередній рік": prev_value,
                "Поточний рік": curr_value,
                "Зміна": change,
                "Одиниця": unit,
            })

    return pd.DataFrame(rows)


def render_year_over_year_block(yoy_comparison):
    """Render the year-to-year analytics block when comparison data is available."""
    st.markdown(
        """
<div class="card">
    <div class="card-title">Порівняння «рік до року»</div>
    <div class="card-subtitle">
        Порівняння сформовано за тією самою вибіркою, що й аналітична довідка.
    </div>
""",
        unsafe_allow_html=True,
    )

    if yoy_comparison.empty:
        st.info("Для порівняння «рік до року» потрібні дані щонайменше за два роки в межах обраної вибірки.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    render_readonly_table(yoy_comparison)

    chart_data = yoy_comparison[yoy_comparison["Показник"].isin([
        "Покриття моніторингом", "Рівень виконання СП", "Очікуваний темп", "Відхилення"
    ])].copy()
    if not chart_data.empty:
        fig = px.bar(
            chart_data,
            x="Показник",
            y="Зміна",
            color="Період порівняння",
            barmode="group",
            title="Зміна ключових показників рік до року",
            labels={"Зміна": "Зміна, в.п."},
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)


def aggregate_goal_progress(active):
    if active.empty:
        return pd.DataFrame()
    result = (
        active.groupby(["goal_code", "strategic_goal"], dropna=False)
        .agg(
            Заходів_періодів=("code", "count"),
            Унікальних_заходів=("code", "nunique"),
            Виконання=("performance_score", "mean"),
            Очікуваний_темп=("expected_progress", "mean"),
            Подано=("has_submission", "sum"),
            Без_даних=("status", lambda x: (x == "Не подано").sum()),
            Проблемних=("is_problem_status", "sum"),
        )
        .reset_index()
    )
    result["Виконання"] = result["Виконання"].round(2)
    result["Очікуваний_темп"] = result["Очікуваний_темп"].round(2)
    result["Відхилення"] = (result["Виконання"] - result["Очікуваний_темп"]).round(2)
    result["Покриття_%"] = (result["Подано"] / result["Заходів_періодів"] * 100).round(2)
    return result


def aggregate_dep_progress(active):
    if active.empty:
        return pd.DataFrame()
    result = (
        active.groupby(["ssp_index", "department", "deputy_minister"], dropna=False)
        .agg(
            Заходів_періодів=("code", "count"),
            Унікальних_заходів=("code", "nunique"),
            Виконання=("performance_score", "mean"),
            Очікуваний_темп=("expected_progress", "mean"),
            Подано=("has_submission", "sum"),
            Без_даних=("status", lambda x: (x == "Не подано").sum()),
            Проблемних=("is_problem_status", "sum"),
        )
        .reset_index()
        .sort_values("ssp_index", key=lambda s: s.apply(lambda x: int(x) if str(x).isdigit() else 10_000))
    )
    result["Виконання"] = result["Виконання"].round(2)
    result["Очікуваний_темп"] = result["Очікуваний_темп"].round(2)
    result["Відхилення"] = (result["Виконання"] - result["Очікуваний_темп"]).round(2)
    result["Покриття_%"] = (result["Подано"] / result["Заходів_періодів"] * 100).round(2)
    return result


def aggregate_task_progress(active):
    if active.empty:
        return pd.DataFrame()
    result = (
        active.groupby(["goal_code", "task_code", "task_name"], dropna=False)
        .agg(
            Заходів_періодів=("code", "count"),
            Унікальних_заходів=("code", "nunique"),
            Виконання=("performance_score", "mean"),
            Очікуваний_темп=("expected_progress", "mean"),
            Подано=("has_submission", "sum"),
            Без_даних=("status", lambda x: (x == "Не подано").sum()),
        )
        .reset_index()
    )
    result["Виконання"] = result["Виконання"].round(2)
    result["Очікуваний_темп"] = result["Очікуваний_темп"].round(2)
    result["Відхилення"] = (result["Виконання"] - result["Очікуваний_темп"]).round(2)
    result["Покриття_%"] = (result["Подано"] / result["Заходів_періодів"] * 100).round(2)
    return result.sort_values(["goal_code", "task_code"])


def aggregate_product_progress(active):
    if active.empty:
        return pd.DataFrame()
    result = (
        active.groupby("product_type", dropna=False)
        .agg(
            Заходів_періодів=("code", "count"),
            Унікальних_заходів=("code", "nunique"),
            Виконання=("performance_score", "mean"),
            Очікуваний_темп=("expected_progress", "mean"),
            Подано=("has_submission", "sum"),
            Без_даних=("status", lambda x: (x == "Не подано").sum()),
        )
        .reset_index()
    )
    result["product_type"] = result["product_type"].replace("", "н/д")
    result["Виконання"] = result["Виконання"].round(2)
    result["Очікуваний_темп"] = result["Очікуваний_темп"].round(2)
    result["Відхилення"] = (result["Виконання"] - result["Очікуваний_темп"]).round(2)
    result["Покриття_%"] = (result["Подано"] / result["Заходів_періодів"] * 100).round(2)
    return result.sort_values("Заходів_періодів", ascending=False)


def aggregate_status(active):
    if active.empty:
        return pd.DataFrame(columns=["status", "Кількість"])
    return active.groupby("status").size().reset_index(name="Кількість").sort_values("Кількість", ascending=False)


def aggregate_period_dynamics(active):
    if active.empty:
        return pd.DataFrame()
    result = (
        active.groupby(["report_year", "report_quarter", "report_quarter_num"], dropna=False)
        .agg(
            Заходів_періодів=("code", "count"),
            Виконання=("performance_score", "mean"),
            Очікуваний_темп=("expected_progress", "mean"),
            Подано=("has_submission", "sum"),
        )
        .reset_index()
        .sort_values(["report_year", "report_quarter_num"])
    )
    result["Період"] = result["report_year"].astype(str) + " " + result["report_quarter"].astype(str)
    result["Виконання"] = result["Виконання"].round(2)
    result["Очікуваний_темп"] = result["Очікуваний_темп"].round(2)
    result["Відхилення"] = (result["Виконання"] - result["Очікуваний_темп"]).round(2)
    result["Покриття_%"] = (result["Подано"] / result["Заходів_періодів"] * 100).round(2)
    return result


def generate_analytical_text(active, filters, metrics, goal_progress, dep_progress, task_progress, product_progress, status_counts, period_dynamics):
    years_text = ", ".join(map(str, filters["years"]))
    quarters_text = ", ".join(filters["quarters"])

    selected_scope = (
        f"роки: {years_text}; квартали: {quarters_text}; "
        f"самостійні структурні підрозділи: {filter_label(filters['ssp'], 'усі')}; "
        f"заступники Міністра: {filter_label(filters['deputies'], 'усі')}; "
        f"стратегічні цілі: {filter_label(filters['goal_labels'], 'усі')}; "
        f"завдання: {filter_label(filters['task_labels'], 'усі')}; "
        f"типи продукту: {filter_label(filters['product_types'], 'усі')}"
    )

    completion = metrics["completion"]
    coverage = metrics["coverage"]
    deviation = metrics["deviation"]
    expected = metrics["expected"]

    if completion >= 70 and deviation >= -10:
        general_assessment = (
            "Загальний стан виконання можна оцінити як контрольований: середній фактичний рівень виконання близький до очікуваного квартального темпу або перевищує його."
        )
    elif completion >= 40:
        general_assessment = (
            "Стан виконання характеризується помірними відхиленнями: частина заходів рухається в межах очікуваного темпу, однак окремі напрями потребують додаткового управлінського контролю."
        )
    else:
        general_assessment = (
            "Стан виконання свідчить про суттєві відхилення від очікуваного темпу та потребує концентрації уваги на причинах затримок, неповного подання даних і недостатньої фактичної динаміки."
        )

    if coverage >= 80:
        coverage_assessment = "Інформаційна база є достатньою для формування узагальнених управлінських висновків."
    elif coverage >= 40:
        coverage_assessment = "Інформаційна база є частковою, тому окремі висновки варто інтерпретувати з урахуванням неповного покриття моніторингом."
    else:
        coverage_assessment = "Інформаційна база є недостатньою; це знижує точність оцінки та підвищує ризик викривлення загальної картини виконання."

    best_goal_text = "н/д"
    worst_goal_text = "н/д"
    attention_goal_text = "н/д"
    if not goal_progress.empty:
        best_goal = goal_progress.sort_values(["Виконання", "Покриття_%"], ascending=False).iloc[0]
        worst_goal = goal_progress.sort_values(["Виконання", "Покриття_%"], ascending=True).iloc[0]
        attention_goal = goal_progress.sort_values(["Відхилення", "Без_даних"], ascending=[True, False]).iloc[0]
        best_goal_text = f"СЦ {best_goal['goal_code']} — {round(best_goal['Виконання'], 1)}% виконання, покриття {round(best_goal['Покриття_%'], 1)}%"
        worst_goal_text = f"СЦ {worst_goal['goal_code']} — {round(worst_goal['Виконання'], 1)}% виконання, покриття {round(worst_goal['Покриття_%'], 1)}%"
        attention_goal_text = f"СЦ {attention_goal['goal_code']} — відхилення {deviation_label(attention_goal['Відхилення'])}, без даних {int(attention_goal['Без_даних'])}"

    best_dep_text = "н/д"
    worst_dep_text = "н/д"
    if not dep_progress.empty:
        best_dep = dep_progress.sort_values(["Виконання", "Покриття_%"], ascending=False).iloc[0]
        worst_dep = dep_progress.sort_values(["Виконання", "Покриття_%"], ascending=True).iloc[0]
        best_dep_text = f"{best_dep['department']} — {round(best_dep['Виконання'], 1)}%"
        worst_dep_text = f"{worst_dep['department']} — {round(worst_dep['Виконання'], 1)}%, без даних {int(worst_dep['Без_даних'])}"

    task_attention_text = "н/д"
    if not task_progress.empty:
        task_attention = task_progress.sort_values(["Відхилення", "Без_даних"], ascending=[True, False]).head(3)
        task_attention_text = concise_list([
            f"{row['task_code']} — {round(row['Виконання'], 1)}%, відхилення {deviation_label(row['Відхилення'])}"
            for _, row in task_attention.iterrows()
        ], limit=3)

    product_text = "н/д"
    if not product_progress.empty:
        product_text = concise_list([
            f"{row['product_type']} — {int(row['Унікальних_заходів'])} заходів, виконання {round(row['Виконання'], 1)}%"
            for _, row in product_progress.head(4).iterrows()
        ], limit=4)

    status_text = "н/д"
    if not status_counts.empty:
        status_text = concise_list([
            f"{row['status']} — {int(row['Кількість'])}"
            for _, row in status_counts.iterrows()
        ], limit=6)

    dynamics_text = "н/д"
    if not period_dynamics.empty:
        dynamics_text = concise_list([
            f"{row['Період']}: виконання {round(row['Виконання'], 1)}%, покриття {round(row['Покриття_%'], 1)}%, відхилення {deviation_label(row['Відхилення'])}"
            for _, row in period_dynamics.iterrows()
        ], limit=6)

    text = f"""
За результатами автоматизованого аналізу сформовано аналітичну довідку щодо стану виконання Стратегічного плану за обраним зрізом. Параметри аналізу: {selected_scope}. У межах відібраного масиву враховано {metrics['total_rows']} записів «захід-період», що відповідають {metrics['unique_measures']} унікальним заходам, {metrics['tasks']} завданням та {metrics['goals']} стратегічним цілям.

Середній розрахунковий рівень виконання Стратегічного плану в обраному періоді становить {completion}%. Очікуваний темп для відповідних кварталів становить {expected}%, тому відхилення у звітному періоді дорівнює {deviation_label(deviation)}. {general_assessment}

Покриття моніторингом становить {coverage}%: подано та погоджено дані за {metrics['submitted']} записами з {metrics['total_rows']}. Без поданих погоджених даних залишаються {metrics['no_data']} записів. {coverage_assessment}

У динаміці за періодами картина є такою: {dynamics_text}. Цей блок показує, чи накопичується відставання протягом року, чи навпаки спостерігається поступове наближення до планового темпу виконання.

У розрізі стратегічних цілей найвищий рівень виконання зафіксовано за напрямом {best_goal_text}. Найнижчий рівень виконання спостерігається за напрямом {worst_goal_text}. Окремої уваги потребує {attention_goal_text}, оскільки саме тут поєднуються відхилення від очікуваного темпу та/або неповнота моніторингових даних.

У розрізі завдань першочергової уваги потребують: {task_attention_text}. Ці завдання доцільно використовувати як основу для точкової управлінської комунікації з відповідальними самостійними структурними підрозділами.

У розрізі самостійних структурних підрозділів найкращий агрегований результат демонструє {best_dep_text}. Найнижчий показник зафіксовано у {worst_dep_text}. Такий розподіл може свідчити як про різну складність портфелів заходів, так і про відмінності у своєчасності подання та якості підтвердження результатів.

За типами продукту структура портфеля виглядає так: {product_text}. За статусами виконання розподіл є таким: {status_text}. Це дозволяє відокремити проблеми фактичного виконання від проблем дисципліни моніторингу.

З огляду на результати аналізу доцільно зосередити подальшу роботу на трьох напрямах: забезпечити повноту подання даних за заходами без погодженого моніторингу; уточнити причини відхилень у стратегічних цілях та завданнях із найнижчим темпом виконання; підготувати пропозиції щодо коригування строків, відповідальних виконавців або змісту заходів там, де фактичний прогрес системно не відповідає очікуваному квартальному темпу.
""".strip()

    return text


# ============================================================
# Export
# ============================================================

def create_excel_report(active, period_requests, goal_progress, dep_progress, task_progress, product_progress, status_counts, period_dynamics, yoy_comparison, metrics, filters):
    output = BytesIO()

    active_export = active.rename(columns={
        "report_year": "Рік",
        "report_quarter": "Квартал",
        "code": "Код заходу",
        "name": "Захід",
        "goal_code": "Код СЦ",
        "strategic_goal": "Стратегічна ціль",
        "task_code": "Код завдання",
        "task_name": "Завдання",
        "product_type": "Тип продукту",
        "department": "Самостійний структурний підрозділ",
        "deputy_minister": "Заступник Міністра",
        "indicator": "Індикатор",
        "unit": "Одиниця виміру",
        "selected_target": "Планове значення",
        "numeric_value": "Фактичне значення",
        "status": "Статус",
        "performance_score": "Виконання, %",
        "expected_progress": "Очікуваний темп, %",
        "period_deviation": "Відхилення, в.п.",
        "traffic_light": "Оцінка темпу",
        "progress_text": "Пояснення",
        "risks": "Ризики/відхилення",
    })

    active_cols = [
        "Рік", "Квартал", "Код заходу", "Захід", "Код СЦ", "Стратегічна ціль",
        "Код завдання", "Завдання", "Тип продукту", "Самостійний структурний підрозділ",
        "Заступник Міністра", "Індикатор", "Одиниця виміру", "Планове значення",
        "Фактичне значення", "Статус", "Виконання, %", "Очікуваний темп, %",
        "Відхилення, в.п.", "Оцінка темпу", "Пояснення", "Ризики/відхилення"
    ]

    summary_df = pd.DataFrame([
        ["Період", f"Роки: {', '.join(map(str, filters['years']))}; квартали: {', '.join(filters['quarters'])}"],
        ["ССП", filter_label(filters["ssp"], "Усі")],
        ["Заступники Міністра", filter_label(filters["deputies"], "Усі")],
        ["Стратегічні цілі", filter_label(filters["goal_labels"], "Усі")],
        ["Завдання", filter_label(filters["task_labels"], "Усі")],
        ["Типи продукту", filter_label(filters["product_types"], "Усі")],
        ["Дата формування", now_kyiv().strftime("%d.%m.%Y %H:%M")],
        ["Унікальних заходів", metrics["unique_measures"]],
        ["Покриття моніторингом", f"{metrics['coverage']}%"],
        ["Виконання СП", f"{metrics['completion']}%"],
        ["Відхилення", deviation_label(metrics["deviation"])],
    ], columns=["Показник", "Значення"])

    _sheets = {
        "Пояснення": summary_df,
        "Аналітичний масив": active_export[[c for c in active_cols if c in active_export.columns]],
        "Стратегічні цілі": goal_progress,
        "Завдання": task_progress,
        "ССП": dep_progress,
        "Типи продукту": product_progress,
        "Динаміка": period_dynamics,
        "Статуси": status_counts,
        "Рік до року": yoy_comparison,
        "Реєстр заявок": period_requests,
    }
    output = BytesIO(core_exports.write_styled_excel(_sheets, freeze_first_col=1))
    output.seek(0)
    return output


def build_report_charts(goal_progress, dep_progress, status_counts, period_dynamics):
    """
    Формує PNG-графіки для аналітичної довідки (правка №15):
    повертає [(підпис, png_bytes), ...]. Використовує ті самі агрегати,
    що й екранні візуалізації, тож графіки в довідці підтверджують текст.
    """
    charts = []
    _brand = ["#005BBB", "#4D8DFF", "#BFD3F2", "#FFD500", "#FF7A45", "#DC4A4A"]

    def _style(fig, h=430):
        fig.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            font=dict(family="Arial", size=13, color="#132238"),
            margin=dict(l=40, r=20, t=50, b=40), height=h,
        )
        return fig

    try:
        if period_dynamics is not None and not period_dynamics.empty:
            fig = _px_rep.line(
                period_dynamics, x="Період", y=["Виконання", "Очікуваний_темп"],
                markers=True, color_discrete_sequence=[_brand[0], _brand[4]],
                title="Динаміка виконання та очікуваний темп, %",
            )
            fig.update_layout(legend_title_text="")
            png = fig_png_bytes(_style(fig), scale=2, width=1000, height=430)
            if png:
                charts.append(("Рис. Динаміка рівня виконання СП у розрізі звітних періодів "
                               "порівняно з очікуваним темпом", png))

        if status_counts is not None and not status_counts.empty:
            fig = _px_rep.pie(
                status_counts, names="status", values="Кількість", hole=0.45,
                color_discrete_sequence=_brand,
                title="Розподіл заходів за статусами виконання",
            )
            png = fig_png_bytes(_style(fig), scale=2, width=900, height=430)
            if png:
                charts.append(("Рис. Структура портфеля заходів за статусами виконання", png))

        if goal_progress is not None and not goal_progress.empty:
            _g = goal_progress.sort_values("Виконання", ascending=True)
            fig = _px_rep.bar(
                _g, x="Виконання", y=_g["goal_code"].astype(str),
                orientation="h", color_discrete_sequence=[_brand[0]],
                title="Рівень виконання за стратегічними цілями, %",
            )
            fig.update_layout(yaxis_title="СЦ", xaxis_title="Виконання, %")
            png = fig_png_bytes(_style(fig, h=max(360, 34 * len(_g) + 120)),
                                scale=2, width=1000)
            if png:
                charts.append(("Рис. Порівняння рівня виконання у розрізі стратегічних цілей", png))

        if dep_progress is not None and not dep_progress.empty:
            _d = dep_progress.sort_values("Виконання", ascending=False).head(15)
            _d = _d.sort_values("Виконання", ascending=True)
            fig = _px_rep.bar(
                _d, x="Виконання", y=_d["ssp_index"].astype(str).apply(lambda v: f"ССП {v}"),
                orientation="h", color_discrete_sequence=[_brand[1]],
                title="Рівень виконання за ССП (топ-15), %",
            )
            fig.update_layout(yaxis_title="", xaxis_title="Виконання, %")
            png = fig_png_bytes(_style(fig, h=max(360, 30 * len(_d) + 120)),
                                scale=2, width=1000)
            if png:
                charts.append(("Рис. Рівень виконання у розрізі самостійних структурних підрозділів", png))
    except Exception as exc:
        show_warning(
            "Частину графіків аналітичного звіту не сформовано.",
            exc,
            "Підготовка графіків аналітичного звіту",
        )
    return charts


def create_docx_report(text, metrics, filters, goal_progress, dep_progress, product_progress,
                       status_counts=None, period_dynamics=None, flex_note=""):
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("АНАЛІТИЧНА ДОВІДКА")
    run.bold = True
    run.font.size = Pt(16)

    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("щодо стану виконання Стратегічного плану")
    run.font.size = Pt(12)

    scope = document.add_paragraph()
    scope.alignment = WD_ALIGN_PARAGRAPH.CENTER
    scope.add_run(
        f"Роки: {', '.join(map(str, filters['years']))}; квартали: {', '.join(filters['quarters'])}"
    ).italic = True

    document.add_paragraph("Ключові показники").runs[0].bold = True
    table = document.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "Показник"
    hdr[1].text = "Значення"

    metric_rows = {
        "Унікальних заходів": metrics["unique_measures"],
        "Записів захід-період": metrics["total_rows"],
        "Покриття моніторингом": f"{metrics['coverage']}%",
        "Рівень виконання СП": f"{metrics['completion']}%",
        "Очікуваний темп": f"{metrics['expected']}%",
        "Відхилення": deviation_label(metrics["deviation"]),
        "Без поданих погоджених даних": metrics["no_data"],
    }

    for key, value in metric_rows.items():
        row = table.add_row().cells
        row[0].text = str(key)
        row[1].text = str(value)

    if flex_note:
        row = table.add_row().cells
        row[0].text = "Виконання за обраною базою"
        row[1].text = str(flex_note)

    document.add_paragraph("Аналітичний висновок").runs[0].bold = True
    for paragraph in text.split("\n\n"):
        p = document.add_paragraph(paragraph.strip())
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        for run in p.runs:
            run.font.size = Pt(11)

    # ── Графічні матеріали на підтвердження висновків (правка №15) ──
    charts = build_report_charts(goal_progress, dep_progress, status_counts, period_dynamics)
    if charts:
        document.add_paragraph("Графічні матеріали").runs[0].bold = True
        intro = document.add_paragraph(
            "Наведені нижче рисунки ілюструють та підтверджують викладені вище висновки: "
            "динаміку виконання відносно очікуваного темпу, структуру портфеля за статусами "
            "та порівняльний рівень виконання у розрізі стратегічних цілей і ССП."
        )
        intro.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        for caption, png in charts:
            document.add_picture(BytesIO(png), width=Inches(6.3))
            cap = document.add_paragraph(caption)
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in cap.runs:
                run.italic = True
                run.font.size = Pt(10)
    else:
        note = document.add_paragraph(
            "Графічні матеріали не додано: у середовищі відсутній пакет kaleido "
            "(додайте його в requirements.txt для вбудовування графіків)."
        )
        note.italic = True

    document.add_paragraph("Додаткова структура даних").runs[0].bold = True
    document.add_paragraph(f"Стратегічні цілі в аналізі: {len(goal_progress)}.")
    document.add_paragraph(f"Самостійні структурні підрозділи в аналізі: {len(dep_progress)}.")
    document.add_paragraph(f"Типи продукту в аналізі: {len(product_progress)}.")

    document.add_paragraph("Сформовано автоматизованою системою моніторингу стратегічного плану.").italic = True
    document.add_paragraph("Розроблено департаментом стратегічного планування та макроекономічного прогнозування.").italic = True

    output = BytesIO()
    document.save(output)
    output.seek(0)
    return output


# ============================================================
# Header
# ============================================================

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
    <div class="header-title">Аналітичні відомості</div>
    <div class="header-subtitle">
        Формування управлінських матеріалів на основі результатів моніторингу й оцінювання стратегічних результатів
        для аналізу тенденцій, виявлення відхилень та підготовки пропозицій щодо коригування Стратегічного плану.
    </div>
    <div class="badge-wrap">
        <div class="badge">● Аналітична довідка</div>
        <div class="badge">● Динаміка виконання</div>
        <div class="badge">● Стратегічні цілі / завдання / ССП</div>
        <div class="badge badge-green">● DOCX та Excel</div>
        <div class="badge badge-yellow">● Оновлено: {now_kyiv().strftime('%d.%m.%Y %H:%M')}</div>
    </div>
</div>
""",
    unsafe_allow_html=True
)


# ============================================================
# Load data
# ============================================================

strat_df = load_strat_matrix()
requests_df = ensure_request_columns(load_requests())
workflow_logs = load_workflow_logs()
analytics_read_at = kyiv_now()
st.caption(data_read_caption(analytics_read_at))

analytics_data_mode = st.radio(
    "Джерело даних для аналітики",
    operational.MODE_OPTIONS,
    horizontal=True,
    key="analytics_data_mode_v19",
    help=operational.MODE_HELP,
)
if analytics_data_mode == operational.MODE_OPERATIONAL and not requests_df.empty:
    _analytics_targets = operational.build_target_map(strat_df)
    requests_df, _analytics_auto = operational.apply_operational_mode(requests_df, _analytics_targets)
    st.caption(f"⚡ Оперативний режим: додатково враховано подання після координатора; авто-зараховано: {len(_analytics_auto)}.")
else:
    st.caption("✅ Аналітика розраховується за офіційно погодженими даними.")

# Підтверджені ручні закриття — той самий фактичний шар, що й на Dashboard.
# Broken materialisation не приховує факт: беремо його з closeout_requests,
# але ніколи не вигадуємо статус «Виконано».
requests_df = ensure_request_columns(append_confirmed_closeout_facts(requests_df))

measures_all = base_measures(strat_df)

if measures_all.empty:
    st.warning("У стратегічній матриці не знайдено заходів для аналізу.")
    render_footer()
    st.stop()


# ============================================================
# Filter options
# ============================================================

ssp_options_df = (
    measures_all[["ssp_index", "department"]]
    .dropna()
    .drop_duplicates()
    .sort_values("department", key=lambda s: s.apply(ssp_sort_key))
)
ssp_options = [raw_value(x) for x in ssp_options_df["ssp_index"].tolist() if raw_value(x)]
ssp_labels = {
    raw_value(row["ssp_index"]): raw_value(row["department"])
    for _, row in ssp_options_df.iterrows()
    if raw_value(row["ssp_index"])
}

goal_rows = (
    measures_all[["goal_code", "strategic_goal"]]
    .drop_duplicates()
    .sort_values("goal_code")
)
goal_options = {
    raw_value(row["goal_code"]): f"{raw_value(row['goal_code'])} {raw_value(row['strategic_goal'])}"
    for _, row in goal_rows.iterrows()
    if raw_value(row["goal_code"])
}

task_rows = (
    measures_all[["task_code", "task_name"]]
    .drop_duplicates()
    .sort_values("task_code")
)
task_options = {
    raw_value(row["task_code"]): f"{raw_value(row['task_code'])} {raw_value(row['task_name'])}"
    for _, row in task_rows.iterrows()
    if raw_value(row["task_code"])
}

deputy_options = sorted([x for x in measures_all["deputy_minister"].dropna().astype(str).unique().tolist() if raw_value(x)])
product_type_options = sorted([x for x in measures_all["product_type"].dropna().astype(str).unique().tolist() if raw_value(x)])


# ============================================================
# Filters UI
# ============================================================

st.markdown(
    """
<div class="filter-box">
    <div class="filter-title">Параметри звіту</div>
    <div class="filter-subtitle">
        Можна обрати декілька років і кварталів. Якщо рік або квартал не обрано, система автоматично бере повний 2026 рік.
    </div>
    <div class="filter-section-title">Період</div>
""",
    unsafe_allow_html=True
)

p1, p2 = st.columns([1, 1])
with p1:
    selected_years_raw = st.multiselect(
        "Рік",
        YEAR_OPTIONS,
        default=[],
        placeholder="Усі роки або обрані роки"
    )
with p2:
    selected_quarters_raw = st.multiselect(
        "Квартал",
        QUARTERS,
        default=[],
        placeholder="Усі квартали або обрані квартали"
    )

st.markdown('<div class="filter-section-title">Організаційний та змістовий зріз</div>', unsafe_allow_html=True)

f1, f2, f3 = st.columns([1.2, 1.15, 1.3])
with f1:
    selected_ssp_indices = st.multiselect(
        "Самостійний структурний підрозділ",
        ssp_options,
        format_func=lambda x: ssp_labels.get(x, x),
        placeholder="Оберіть один або декілька ССП"
    )
with f2:
    selected_deputies = st.multiselect(
        "Заступник Міністра",
        deputy_options,
        placeholder="Оберіть заступника Міністра"
    )
with f3:
    selected_goal_labels = st.multiselect(
        "Стратегічна ціль",
        list(goal_options.values()),
        placeholder="Оберіть стратегічну ціль"
    )

f4, f5 = st.columns([1.4, 1])
with f4:
    selected_task_labels = st.multiselect(
        "Завдання",
        list(task_options.values()),
        placeholder="Оберіть завдання"
    )
with f5:
    selected_product_types = st.multiselect(
        "Тип продукту",
        product_type_options,
        placeholder="Оберіть тип продукту"
    )

st.markdown('</div>', unsafe_allow_html=True)

# DEMO 1.9: параметри аналітики застосовуються тільки після кнопки.
_an_defaults = {"years": [], "quarters": [], "ssp": [], "deputies": [], "goals": [], "tasks": [], "product_types": []}
if "analytics_filters_applied_v19" not in st.session_state:
    st.session_state["analytics_filters_applied_v19"] = _an_defaults.copy()
_an_a, _an_b, _an_c = st.columns([1, 1, 1.4])
with _an_a:
    if st.button("Застосувати обрані параметри", type="primary", use_container_width=True, key="analytics_apply_filters_v19"):
        st.session_state["analytics_filters_applied_v19"] = {
            "years": list(selected_years_raw or []),
            "quarters": list(selected_quarters_raw or []),
            "ssp": list(selected_ssp_indices or []),
            "deputies": list(selected_deputies or []),
            "goals": list(selected_goal_labels or []),
            "tasks": list(selected_task_labels or []),
            "product_types": list(selected_product_types or []),
        }
        pass  # no explicit rerun: the triggering user action completes in this run
with _an_b:
    if st.button("Скинути параметри", use_container_width=True, key="analytics_reset_filters_v19"):
        st.session_state["analytics_filters_applied_v19"] = _an_defaults.copy()
        pass  # no explicit rerun: the triggering user action completes in this run
with _an_c:
    st.caption("Аналітичні графіки, таблиці та експорти перебудовуються після застосування параметрів.")

_an_applied = st.session_state.get("analytics_filters_applied_v19", _an_defaults.copy())
selected_years_raw = _an_applied.get("years", [])
selected_quarters_raw = _an_applied.get("quarters", [])
selected_ssp_indices = _an_applied.get("ssp", [])
selected_deputies = _an_applied.get("deputies", [])
selected_goal_labels = _an_applied.get("goals", [])
selected_task_labels = _an_applied.get("tasks", [])
selected_product_types = _an_applied.get("product_types", [])

# Default rule requested by user: no period filters -> full 2026.
selected_years = selected_years_raw if selected_years_raw else [2026]
selected_quarters = selected_quarters_raw if selected_quarters_raw else QUARTERS.copy()

selected_goal_codes = [code for code, label in goal_options.items() if label in selected_goal_labels]
selected_task_codes = [code for code, label in task_options.items() if label in selected_task_labels]
selected_ssp_labels = [ssp_labels.get(x, x) for x in selected_ssp_indices]


# ============================================================
# Analysis dataset
# ============================================================

all_period_data = prepare_analysis_data(strat_df, requests_df, selected_years, selected_quarters)
active = apply_dimension_filters(
    all_period_data,
    selected_ssp_indices,
    selected_deputies,
    selected_goal_codes,
    selected_task_codes,
    selected_product_types,
)

if active.empty:
    st.warning("За обраними параметрами активних заходів не знайдено.")
    render_footer()
    st.stop()

period_requests = requests_df.copy()
if not period_requests.empty:
    period_requests = period_requests[
        period_requests["year"].astype(str).isin([str(y) for y in selected_years])
        & period_requests["quarter"].astype(str).isin([str(q) for q in selected_quarters])
    ].copy()
    if selected_ssp_indices:
        period_requests["department_index"] = period_requests["department"].apply(extract_ssp_index)
        period_requests = period_requests[period_requests["department_index"].astype(str).isin(set(selected_ssp_indices))]

metrics = build_metrics(active)
goal_progress = aggregate_goal_progress(active)
dep_progress = aggregate_dep_progress(active)
task_progress = aggregate_task_progress(active)
product_progress = aggregate_product_progress(active)
status_counts = aggregate_status(active)
period_dynamics = aggregate_period_dynamics(active)

# ============================================================
# ГНУЧКИЙ РОЗРАХУНОК ВІДСОТКА ВИКОНАННЯ (правка №7)
# ============================================================
# Додатковий розріз: чисельник — заходи «Виконано» в аналітичній вибірці,
# знаменник — на вибір. Основні показники сторінки не змінюються;
# обрана база потрапляє в аналітичну довідку (DOCX).

st.markdown('<div class="card"><div class="card-title">Гнучкий розрахунок відсотка виконання</div>', unsafe_allow_html=True)
_flex_base = st.selectbox(
    "База розрахунку (знаменник)",
    [
        "Поточна методологія (записи захід-період аналітичної вибірки)",
        "Унікальні заходи аналітичної вибірки",
        "Усі заходи Стратегічного плану (за всі роки)",
        "Усі заходи обраних СЦ (за всі роки)",
        "Лише записи з поданою звітністю",
    ],
    key="analytics_flex_base",
)
_flex_num = int((active["status"].astype(str) == "Виконано").sum()) if not active.empty and "status" in active.columns else 0
_all_measures_count = int((strat_df["object_type"] == "measure").sum())
if _flex_base.startswith("Поточна методологія"):
    _flex_den = len(active)
elif _flex_base.startswith("Унікальні"):
    _flex_num = int(active[active["status"].astype(str) == "Виконано"]["code"].nunique()) if not active.empty else 0
    _flex_den = int(active["code"].nunique()) if not active.empty else 0
elif _flex_base.startswith("Усі заходи Стратегічного"):
    _flex_den = _all_measures_count
elif _flex_base.startswith("Усі заходи обраних СЦ"):
    if not active.empty and "goal_code" in active.columns:
        _gc = {str(g).split(".")[0] for g in active["goal_code"].astype(str).unique()}
        _mm = strat_df[strat_df["object_type"] == "measure"]
        _flex_den = int(_mm["code"].astype(str).apply(lambda c: str(c).split(".")[0] in _gc).sum())
    else:
        _flex_den = _all_measures_count
else:
    _flex_den = int(active["has_submission"].sum()) if not active.empty and "has_submission" in active.columns else 0

_flex_pct = round(100.0 * _flex_num / _flex_den, 1) if _flex_den else 0.0
flex_note_for_docx = f"{_flex_pct}% ({_flex_num} із {_flex_den}; база: {_flex_base})"
_fc1, _fc2 = st.columns([1, 2.2])
with _fc1:
    st.metric("Виконання за обраною базою", f"{_flex_pct}%", f"{_flex_num} із {_flex_den}")
with _fc2:
    st.caption(
        f"Чисельник: заходи/записи зі статусом «Виконано» ({_flex_num}). "
        f"Знаменник: {_flex_base.lower()} ({_flex_den}). Обрана база фіксується "
        f"в таблиці ключових показників аналітичної довідки DOCX."
    )
st.markdown("</div>", unsafe_allow_html=True)

comparison_years = sorted(set(selected_years + [max(selected_years) - 1])) if selected_years else []
yoy_source = prepare_analysis_data(strat_df, requests_df, comparison_years, selected_quarters) if comparison_years else pd.DataFrame()
yoy_active = apply_dimension_filters(
    yoy_source,
    selected_ssp_indices,
    selected_deputies,
    selected_goal_codes,
    selected_task_codes,
    selected_product_types,
) if not yoy_source.empty else pd.DataFrame()
yoy_comparison = build_year_over_year_comparison(yoy_active)

filters = {
    "years": selected_years,
    "quarters": selected_quarters,
    "ssp": selected_ssp_labels,
    "ssp_indices": selected_ssp_indices,
    "deputies": selected_deputies,
    "goal_labels": selected_goal_labels,
    "task_labels": selected_task_labels,
    "product_types": selected_product_types,
}

analytical_text = generate_analytical_text(
    active,
    filters,
    metrics,
    goal_progress,
    dep_progress,
    task_progress,
    product_progress,
    status_counts,
    period_dynamics,
)


# ============================================================
# KPI cards
# ============================================================

dev_class = deviation_card_class(metrics["deviation"])
st.markdown(
    f"""
<div class="alert-grid">
    <div class="alert-card alert-blue">
        <div class="alert-title">Рівень виконання Стратегічного плану в обраному періоді</div>
        <div class="alert-value">{metrics['completion']}%</div>
        <div class="alert-note">Середній фактичний прогрес за відібраним масивом</div>
    </div>
    <div class="alert-card {dev_class}">
        <div class="alert-title">Відхилення у звітному періоді</div>
        <div class="alert-value">{deviation_label(metrics['deviation'])}</div>
        <div class="alert-note">Факт мінус очікуваний квартальний темп {metrics['expected']}%</div>
    </div>
    <div class="alert-card alert-yellow">
        <div class="alert-title">Покриття моніторингом</div>
        <div class="alert-value">{metrics['coverage']}%</div>
        <div class="alert-note">Погоджені дані: {metrics['submitted']} із {metrics['total_rows']}</div>
    </div>
    <div class="alert-card alert-green">
        <div class="alert-title">Активних заходів у вибірці</div>
        <div class="alert-value">{metrics['unique_measures']}</div>
        <div class="alert-note">Унікальні заходи; записів захід-період: {metrics['total_rows']}</div>
    </div>
</div>
""",
    unsafe_allow_html=True
)

render_year_over_year_block(yoy_comparison)


# ============================================================
# Analytical note
# ============================================================

st.markdown(
    f"""
<div class="report-box">
    <div class="report-title">Автоматично сформована аналітична довідка</div>
    <div class="report-meta">
        Роки: {', '.join(map(str, selected_years))} | Квартали: {', '.join(selected_quarters)} | 
        ССП: {filter_label(selected_ssp_labels, 'усі')} | Заступники: {filter_label(selected_deputies, 'усі')}
    </div>
""",
    unsafe_allow_html=True
)

for paragraph in analytical_text.split("\n\n"):
    st.markdown(f"<p class='report-text'>{clean(paragraph)}</p>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# Graphs
# ============================================================

st.markdown(
    """
<div class="card">
    <div class="card-title">Графіки до довідки</div>
    <div class="card-subtitle">
        Візуальні матеріали сформовано за тією самою вибіркою, що й текст довідки.
    </div>
""",
    unsafe_allow_html=True
)

g1, g2 = st.columns(2)

with g1:
    if not period_dynamics.empty:
        fig = px.line(
            period_dynamics,
            x="Період",
            y=["Виконання", "Очікуваний_темп"],
            markers=True,
            title="Динаміка виконання проти очікуваного темпу",
            labels={"value": "Відсоток", "variable": "Показник"}
        )
        fig.update_layout(legend_title_text="Показник")
        st.plotly_chart(fig, use_container_width=True)

with g2:
    if not goal_progress.empty:
        fig = px.bar(
            goal_progress.sort_values("goal_code"),
            x="goal_code",
            y="Виконання",
            text="Виконання",
            hover_data=["strategic_goal", "Унікальних_заходів", "Покриття_%", "Відхилення", "Без_даних"],
            title="Виконання за стратегічними цілями",
            labels={"goal_code": "Стратегічна ціль", "Виконання": "Виконання, %"}
        )
        st.plotly_chart(fig, use_container_width=True)

g3, g4 = st.columns(2)

with g3:
    if not dep_progress.empty:
        dep_for_chart = dep_progress.copy()
        dep_for_chart["ССП"] = dep_for_chart["ssp_index"].astype(str) + " — " + dep_for_chart["department"].astype(str)
        fig = px.bar(
            dep_for_chart,
            x="ССП",
            y="Виконання",
            text="Виконання",
            hover_data=["deputy_minister", "Унікальних_заходів", "Покриття_%", "Відхилення", "Без_даних"],
            title="Виконання за самостійними структурними підрозділами",
            labels={"ССП": "ССП", "Виконання": "Виконання, %"}
        )
        fig.update_layout(xaxis_tickangle=-35)
        st.plotly_chart(fig, use_container_width=True)

with g4:
    if not product_progress.empty:
        fig = px.bar(
            product_progress,
            x="product_type",
            y="Унікальних_заходів",
            text="Унікальних_заходів",
            hover_data=["Виконання", "Покриття_%", "Відхилення", "Без_даних"],
            title="Структура заходів за типами продукту",
            labels={"product_type": "Тип продукту", "Унікальних_заходів": "Заходів"}
        )
        fig.update_layout(xaxis_tickangle=-25)
        st.plotly_chart(fig, use_container_width=True)

g5, g6 = st.columns(2)

with g5:
    if not status_counts.empty:
        fig = px.pie(
            status_counts,
            names="status",
            values="Кількість",
            hole=0.45,
            title="Структура статусів виконання"
        )
        st.plotly_chart(fig, use_container_width=True)

with g6:
    if not task_progress.empty:
        top_tasks = task_progress.sort_values("Відхилення", ascending=True).head(10).copy()
        top_tasks["Завдання"] = top_tasks["task_code"].astype(str)
        fig = px.bar(
            top_tasks,
            x="Завдання",
            y="Відхилення",
            text="Відхилення",
            hover_data=["task_name", "Виконання", "Покриття_%", "Без_даних"],
            title="Завдання з найбільшим відхиленням від очікуваного темпу",
            labels={"Відхилення": "Відхилення, в.п."}
        )
        st.plotly_chart(fig, use_container_width=True)

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# WORKFLOW ANALYTICS — TEST MODE
# ============================================================

_active_codes = set(active["code"].astype(str).str.strip().tolist()) if "code" in active.columns else set()
workflow_requests = period_requests.copy()
if not workflow_requests.empty and _active_codes:
    workflow_requests = workflow_requests[
        workflow_requests["strat_code"].astype(str).str.strip().isin(_active_codes)
    ].copy()
return_analytics = build_return_analytics(workflow_logs, workflow_requests)
approval_speed = build_approval_speed_analytics(
    workflow_logs,
    workflow_requests,
    now=analytics_read_at,
)

st.markdown(
    '<div class="card"><div class="card-title">Аналіз повернень на доопрацювання '
    '<span style="font-size:11px;color:#8A6400;background:#FDF3D8;border:1px solid #F4B400;'
    'border-radius:999px;padding:3px 8px;">тест</span></div>'
    '<div class="card-subtitle">Розрахунок виконується за журналом дій і поточним аналітичним зрізом.</div>',
    unsafe_allow_html=True,
)
_ret_c1, _ret_c2 = st.columns(2)
with _ret_c1:
    st.metric("Кількість повернень", return_analytics["total_returns"])
with _ret_c2:
    st.metric(
        "Середня кількість повернень на одну заявку",
        return_analytics["average_per_request"],
        help="Кількість подій повернення, поділена на кількість заявок у поточному зрізі.",
    )

_ret_left, _ret_right = st.columns(2)
with _ret_left:
    _ret_dep = return_analytics["by_department"]
    if _ret_dep.empty:
        st.info("У поточному зрізі повернень не зафіксовано.")
    else:
        _ret_dep_fig = px.bar(
            _ret_dep,
            x="ССП",
            y="Кількість повернень",
            text="Кількість повернень",
            title="Рейтинг ССП за кількістю повернень",
        )
        st.plotly_chart(_ret_dep_fig, use_container_width=True)
with _ret_right:
    _ret_stage = return_analytics["by_stage"]
    if not _ret_stage.empty:
        _ret_stage_fig = px.bar(
            _ret_stage,
            x="Ланка, що повернула",
            y="Кількість повернень",
            text="Кількість повернень",
            title="Розподіл за ланками, які повертають",
        )
        st.plotly_chart(_ret_stage_fig, use_container_width=True)

st.markdown("**Заявки з найбільшою кількістю повернень**")
_top_returned = return_analytics["top_requests"]
if _top_returned.empty:
    st.info("Заявок із поверненнями у поточному зрізі немає.")
else:
    render_readonly_table(_top_returned.head(20))
st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="card"><div class="card-title">Швидкість погодження '
    '<span style="font-size:11px;color:#8A6400;background:#FDF3D8;border:1px solid #F4B400;'
    'border-radius:999px;padding:3px 8px;">тест</span></div>'
    '<div class="card-subtitle">Час розраховано за датою подання і послідовністю подій у журналі.</div>',
    unsafe_allow_html=True,
)
_speed_c1, _speed_c2 = st.columns(2)
with _speed_c1:
    st.metric(
        "Середній час від подання до фінального погодження",
        f"{approval_speed['average_total_days']} дн.",
    )
with _speed_c2:
    st.metric("Фінально погоджених заявок у розрахунку", approval_speed["completed_requests"])

_speed_left, _speed_right = st.columns(2)
with _speed_left:
    st.markdown("**Середній час на кожній ланці**")
    if approval_speed["stage_average"].empty:
        st.info("Для розрахунку часу на ланках недостатньо завершених переходів.")
    else:
        render_readonly_table(approval_speed["stage_average"])
with _speed_right:
    st.markdown("**Заявки, що зараз очікують найдовше**")
    if approval_speed["hanging"].empty:
        st.info("У поточному зрізі немає заявок на активних ланках погодження.")
    else:
        render_readonly_table(approval_speed["hanging"].head(20))
st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# Export
# ============================================================

st.markdown(
    """
<div class="export-box">
    <div class="card-title">Експорт матеріалів</div>
    <div class="card-subtitle">Завантаження формуються відповідно до всіх обраних фільтрів.</div>
""",
    unsafe_allow_html=True
)

excel_file = create_excel_report(
    active,
    period_requests,
    goal_progress,
    dep_progress,
    task_progress,
    product_progress,
    status_counts,
    period_dynamics,
    yoy_comparison,
    metrics,
    filters,
)

docx_file = create_docx_report(
    analytical_text,
    metrics,
    filters,
    goal_progress,
    dep_progress,
    product_progress,
    status_counts=status_counts,
    period_dynamics=period_dynamics,
    flex_note=flex_note_for_docx,
)

e1, e2, e3 = st.columns(3)
with e1:
    st.download_button(
        "Завантажити Excel-звіт",
        data=excel_file,
        file_name=f"analytics_report_{'_'.join(map(str, selected_years))}_{'_'.join(selected_quarters)}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
with e2:
    st.download_button(
        "Аналітична довідка DOCX",
        data=docx_file,
        file_name=f"analytical_note_{'_'.join(map(str, selected_years))}_{'_'.join(selected_quarters)}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
    )
with e3:
    requests_output = BytesIO(core_exports.write_styled_excel({"Реєстр заявок": period_requests}))
    requests_output.seek(0)
    st.download_button(
        "Реєстр заявок",
        data=requests_output,
        file_name=f"requests_registry_{'_'.join(map(str, selected_years))}_{'_'.join(selected_quarters)}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# Tables for checking
# ============================================================

st.markdown('<div class="table-box"><div class="card-title">Таблиці для перевірки</div>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Аналітичний масив",
    "Стратегічні цілі",
    "Завдання",
    "ССП",
    "Типи продукту",
    "Реєстр заявок",
])

with tab1:
    show_active = active.rename(columns={
        "report_year": "Рік",
        "report_quarter": "Квартал",
        "code": "Код",
        "name": "Захід",
        "strategic_goal": "Стратегічна ціль",
        "task_name": "Завдання",
        "product_type": "Тип продукту",
        "department": "ССП",
        "deputy_minister": "Заступник Міністра",
        "selected_target": "Планове значення",
        "numeric_value": "Фактичне значення",
        "status": "Статус",
        "performance_score": "Виконання, %",
        "expected_progress": "Очікуваний темп, %",
        "period_deviation": "Відхилення, в.п.",
        "traffic_light": "Оцінка темпу",
    })
    cols = [
        "Рік", "Квартал", "Код", "Захід", "Стратегічна ціль", "Завдання", "Тип продукту",
        "ССП", "Заступник Міністра", "Планове значення", "Фактичне значення", "Статус",
        "Виконання, %", "Очікуваний темп, %", "Відхилення, в.п.", "Оцінка темпу"
    ]
    render_readonly_table(show_active[[c for c in cols if c in show_active.columns]])

with tab2:
    render_readonly_table(goal_progress)

with tab3:
    render_readonly_table(task_progress)

with tab4:
    render_readonly_table(dep_progress)

with tab5:
    render_readonly_table(product_progress)

with tab6:
    render_readonly_table(period_requests)

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# Footer
# ============================================================

render_footer()
