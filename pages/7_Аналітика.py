import os
import re
import hashlib
from datetime import datetime
from io import BytesIO
from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st
from core.period_locks import apply_locked_status, exclude_locked_periods, is_period_locked
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
from core.access import is_super_admin_user
from core.strategic_data import load_strat_matrix as core_load_strat_matrix
from core import monitoring_data
from core import statuses as core_statuses
from core import operational
from core import mio_shared
from core import analytics_calculations
from core import periods as core_periods
from core.dashboard_breakdowns import (
    build_period_results, aggregate_plan, aggregate_objects, dynamics_frame,
    ssp_summary, deputy_summary, filter_results_by_ssp,
)
from core.dashboard_execution import plan_scores
from core.dashboard_risk import attention_mask, risk_summary
from core.closeouts import append_confirmed_closeout_facts
from core.errors import show_warning, log_exception
from core.analytics_text import build_context as build_analytics_text_context, generate_analytics_note
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

# Production Analytics is a super-admin-only surface. Guard before analytical data access.
if not is_super_admin_user(current_user):
    st.error("У вас немає доступу до розділу «Аналітика».")
    st.stop()

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
.card-subtitle {
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

.card,
.export-box,
.table-box {
    padding: 22px 24px;
    margin-bottom: 18px;
}

.card-title,
.report-title {
    font-size: 21px;
    font-weight: 950;
    color: #132238;
    margin-bottom: 8px;
}

/* Filter fields, labels and controls intentionally inherit the single system template from assets/app.css, identical to Dashboard. */

.alert-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
    margin: 10px 0 14px 0;
}

.alert-card {
    border-radius: 12px;
    padding: 11px 14px;
    border: 1px solid #DCE4F0;
    box-shadow: 0 8px 20px rgba(15,23,42,0.06);
}

.alert-title {
    font-size: 13px;
    color: #61708A;
    font-weight: 900;
    line-height: 1.35;
    min-height: 30px;
}

.alert-value {
    font-size: 24px;
    color: #132238;
    font-weight: 950;
    margin-top: 4px;
}

.alert-note {
    font-size: 12px;
    color: #61708A;
    margin-top: 3px;
    line-height: 1.25;
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

.mio-summary-box {
    background: #FFFFFF;
    border: 1px solid #DCE4F0;
    border-radius: 12px;
    padding: 12px 14px;
    margin: 4px 0 14px 0;
    box-shadow: 0 2px 10px rgba(15,23,42,0.04);
}
.mio-summary-title {
    font-size: 13px;
    font-weight: 900;
    color: #032A63;
    margin-bottom: 8px;
}
.mio-summary-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 8px;
}
.mio-mini {
    background: #F7F9FC;
    border: 1px solid #E3E9F2;
    border-radius: 9px;
    padding: 8px 10px;
    min-height: 58px;
}
.mio-mini span { display:block; color:#61708A; font-size:11px; font-weight:750; line-height:1.2; }
.mio-mini b { display:block; color:#132238; font-size:20px; margin-top:4px; }

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
    color: #34445C;
    text-align: left;
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
    .mio-summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
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


def deviation_label(value):
    if value is None or pd.isna(value):
        return "—"
    sign = "+" if float(value) > 0 else ""
    return f"{sign}{round(float(value), 2)} в.п."


def deviation_card_class(value):
    if value is None or pd.isna(value):
        return "alert-blue"
    if value >= 0:
        return "alert-green"
    if value >= -15:
        return "alert-yellow"
    return "alert-red"


def _signal_delta_row_class(row, _total_rows):
    """Presentation-only edge from the already calculated change value."""
    value = to_number(row.get("Зміна, в.п.", row.get("Зміна")))
    if value is None or float(value) == 0:
        return ""
    return "rt-row-green" if float(value) > 0 else "rt-row-red"


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
    return measures


def is_active_for_period(row, year, quarter):
    selected_period_num = core_periods.period_number(year, quarter)
    return core_periods.get_period_state(
        row.get("start_num"), row.get("end_num"), selected_period_num
    ) == "active"

def _snapshot_rows_from_period_results(results):
    return analytics_calculations.snapshot_rows_from_period_results(results)


def prepare_analysis_context(strat_df, requests_df, years, quarters):
    return analytics_calculations.prepare_analysis_context(strat_df, requests_df, years, quarters)


def prepare_analysis_data(strat_df, requests_df, years, quarters):
    return analytics_calculations.prepare_analysis_data(strat_df, requests_df, years, quarters)


def _rebuild_filtered_results(results, row_filter):
    return analytics_calculations.rebuild_filtered_results(results, row_filter)


def build_analytics_result_context(results, selected_ssp, selected_deputies, selected_goals, selected_tasks, selected_product_types):
    return analytics_calculations.build_analytics_result_context(
        results, selected_ssp, selected_deputies, selected_goals, selected_tasks, selected_product_types
    )


def filter_analysis_period_results(results, selected_ssp, selected_deputies, selected_goals, selected_tasks, selected_product_types):
    return analytics_calculations.filter_analysis_period_results(
        results, selected_ssp, selected_deputies, selected_goals, selected_tasks, selected_product_types
    )

def format_pct(value):
    if value is None or pd.isna(value):
        return "—"
    number = float(value)
    return f"{int(number)}%" if number.is_integer() else f"{number:.1f}%"


def format_number_2(value):
    """Display-only number formatter: maximum two digits after the decimal point."""
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except (TypeError, ValueError):
        pass
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        text = raw_value(value)
        return text if text else "—"
    return f"{float(number):.2f}".rstrip("0").rstrip(".")


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
    return analytics_calculations.build_metrics(active)


def build_year_over_year_comparison(period_results):
    return analytics_calculations.build_year_over_year_comparison(period_results)


def build_analytics_plan_summary(period_results):
    return analytics_calculations.build_analytics_plan_summary(period_results)


def _detail_counts(active, group_cols):
    return analytics_calculations.detail_counts(active, group_cols)


def _object_period_coverage(period_results, object_type):
    return analytics_calculations.object_period_coverage(period_results, object_type)


def build_analytics_goal_summary(period_results, active):
    return analytics_calculations.build_analytics_goal_summary(period_results, active)


def build_analytics_task_summary(period_results, active):
    return analytics_calculations.build_analytics_task_summary(period_results, active)


def build_analytics_ssp_summary(period_results, active, base_results=None):
    return analytics_calculations.build_analytics_ssp_summary(period_results, active, base_results=base_results)


def build_analytics_deputy_summary(period_results):
    return analytics_calculations.build_analytics_deputy_summary(period_results)


def build_analytics_dynamics(period_results):
    return analytics_calculations.build_analytics_dynamics(period_results)


def aggregate_product_progress(period_results, active):
    return analytics_calculations.aggregate_product_progress(period_results, active)

def filter_period_requests_to_active_cohort(requests, active, selected_years, selected_quarters):
    """Registry/export cohort = selected periods intersect canonical active measure codes."""
    if requests is None or requests.empty:
        return requests.copy() if hasattr(requests, "copy") else pd.DataFrame()
    active_codes = {
        clean(code) for code in active.get("code", pd.Series(dtype=object)).tolist() if clean(code)
    }
    data = requests.copy()
    data = data[
        data["year"].astype(str).isin([str(y) for y in selected_years])
        & data["quarter"].astype(str).isin([str(q) for q in selected_quarters])
    ].copy()
    if not active_codes:
        return data.iloc[0:0].copy()
    return data[data["strat_code"].map(clean).isin(active_codes)].copy()

def aggregate_status(active):
    if active.empty:
        return pd.DataFrame(columns=["status", "Кількість"])
    return active.groupby("status").size().reset_index(name="Кількість").sort_values("Кількість", ascending=False)


def _pct_text(value):
    return format_pct(value)


def generate_analytical_text(active, filters, metrics, goal_progress, dep_progress, task_progress, product_progress, status_counts, period_dynamics):
    """Existing analytical note adapted to canonical execution, coverage and attention outputs."""
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
    general_assessment = (
        "Рівень виконання за обраною вибіркою не оцінюється через відсутність оцінених результатів."
        if completion is None else f"Канонічний рівень виконання за обраним зрізом: {format_pct(completion)}."
    )
    coverage_assessment = (
        "Покриття моніторингом за обраною вибіркою не оцінюється."
        if coverage is None else f"Канонічне покриття моніторингом: {format_pct(coverage)}."
    )

    def _best_worst(frame, label_col):
        valid = frame.dropna(subset=["Виконання"]) if not frame.empty and "Виконання" in frame.columns else pd.DataFrame()
        if valid.empty:
            return "н/д", "н/д"
        best = valid.sort_values("Виконання", ascending=False).iloc[0]
        worst = valid.sort_values("Виконання", ascending=True).iloc[0]
        return (f"{best[label_col]} — {_pct_text(best['Виконання'])}", f"{worst[label_col]} — {_pct_text(worst['Виконання'])}")

    best_goal_text, worst_goal_text = _best_worst(goal_progress, "goal_code")
    best_dep_text, worst_dep_text = _best_worst(dep_progress, "department")
    attention_goals = goal_progress.sort_values(["Проблемних", "Без_даних"], ascending=False).head(3) if not goal_progress.empty else pd.DataFrame()
    attention_goal_text = concise_list([f"СЦ {r['goal_code']} — сигналів уваги {int(r['Проблемних'])}, без поточного подання {int(r['Без_даних'])}" for _, r in attention_goals.iterrows()], 3) if not attention_goals.empty else "н/д"
    attention_tasks = task_progress.sort_values(["Проблемних", "Без_даних"], ascending=False).head(3) if not task_progress.empty else pd.DataFrame()
    task_attention_text = concise_list([f"{r['task_code']} — {_pct_text(r['Виконання'])}, сигналів уваги {int(r['Проблемних'])}" for _, r in attention_tasks.iterrows()], 3) if not attention_tasks.empty else "н/д"
    product_text = concise_list([f"{r['product_type']} — {int(r['Унікальних_заходів'])} заходів, виконання {_pct_text(r['Виконання'])}" for _, r in product_progress.head(4).iterrows()], 4) if not product_progress.empty else "н/д"
    status_text = concise_list([f"{r['status']} — {int(r['Кількість'])}" for _, r in status_counts.iterrows()], 6) if not status_counts.empty else "н/д"
    dynamics_text = concise_list([f"{r['Період']}: виконання {_pct_text(r['Виконання'])}, покриття {_pct_text(r['Покриття_%'])}" for _, r in period_dynamics.iterrows()], 6) if not period_dynamics.empty else "н/д"

    return f"""
За результатами автоматизованого аналізу сформовано аналітичну довідку щодо стану виконання Стратегічного плану за обраним зрізом. Параметри аналізу: {selected_scope}. У масиві враховано {metrics['total_rows']} записів «захід-період», що відповідають {metrics['unique_measures']} унікальним заходам, {metrics['tasks']} завданням та {metrics['goals']} стратегічним цілям.

Середній рівень виконання за канонічно оціненими результатами становить {_pct_text(completion)}. {general_assessment}

Покриття моніторингом становить {_pct_text(coverage)}. Відсутнє обов'язкове поточне подання за {metrics['no_data']} записами. {coverage_assessment}

Динаміка за періодами: {dynamics_text}. Неоцінювані майбутні періоди та періоди без проведеного моніторингу не підміняються нульовим виконанням.

За стратегічними цілями найвищий оцінений результат: {best_goal_text}; найнижчий: {worst_goal_text}. За канонічними сигналами ризику та якості даних уваги потребують: {attention_goal_text}.

За завданнями першочергової уваги потребують: {task_attention_text}. У розрізі самостійних структурних підрозділів найвищий оцінений результат: {best_dep_text}; найнижчий: {worst_dep_text}.

За типами продукту: {product_text}. За статусами: {status_text}. Управлінську увагу доцільно спрямовувати на канонічні сигнали ризику, відсутні обов'язкові подання та напрями з низьким оціненим виконанням, не використовуючи штучний квартальний темп.
""".strip()


# ============================================================
# Export
# ============================================================

def _excel_safe_value(value):
    """Convert structured/missing Python values to Excel-safe scalar values."""
    if isinstance(value, dict):
        return "; ".join(f"{key}: {item}" for key, item in value.items())

    if isinstance(value, (list, tuple, set)):
        return "; ".join(str(item) for item in value)

    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return value


def _excel_safe_frame(df):
    """Prepare a DataFrame for xlsxwriter without changing analytical values."""
    if df is None:
        return pd.DataFrame()

    result = df.copy()

    for column in result.columns:
        result[column] = result[column].map(_excel_safe_value)

    return result
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
        "execution_score": "Виконання, %",
        "risk_level": "Рівень ризику",
        "progress_text": "Пояснення",
        "risks": "Ризики/відхилення",
    })

    active_cols = [
        "Рік", "Квартал", "Код заходу", "Захід", "Код СЦ", "Стратегічна ціль",
        "Код завдання", "Завдання", "Тип продукту", "Самостійний структурний підрозділ",
        "Заступник Міністра", "Індикатор", "Одиниця виміру", "Планове значення",
        "Фактичне значення", "Статус", "Виконання, %", "Рівень ризику", "Пояснення", "Ризики/відхилення"
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
        ["Покриття моніторингом", format_pct(metrics["coverage"])],
        ["Виконання СП", format_pct(metrics["completion"])],
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
    _sheets = {
        sheet_name: _excel_safe_frame(frame)
        for sheet_name, frame in _sheets.items()
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
                period_dynamics, x="Період", y="Виконання",
                markers=True, color_discrete_sequence=[_brand[0], _brand[4]],
                title="Динаміка оціненого виконання, %",
            )
            fig.update_layout(legend_title_text="")
            png = fig_png_bytes(_style(fig), scale=2, width=1000, height=430)
            if png:
                charts.append(("Рис. Динаміка рівня виконання СП у розрізі звітних періодів", png))

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
            _g = goal_progress.sort_values("Виконання", ascending=True).copy()
            _g["Виконання"] = pd.to_numeric(_g["Виконання"], errors="coerce").round(2)
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
        "Покриття моніторингом": format_pct(metrics["coverage"]),
        "Рівень виконання СП": format_pct(metrics["completion"]),
        "Без поданих погоджених даних": metrics["no_data"],
    }

    for key, value in metric_rows.items():
        row = table.add_row().cells
        row[0].text = str(key)
        row[1].text = str(value)


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
            "динаміку оціненого виконання, структуру портфеля за статусами "
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
    """
<div class="header-box">
    <div class="header-title">Аналітика</div>
    <div class="header-subtitle">
        Автоматизований аналіз виконання Стратегічного плану, динаміки, структурних відхилень, результатів МіО та фінансової складової.
    </div>
</div>
""",
    unsafe_allow_html=True
)



# ============================================================
# Load data
# ============================================================

strat_df = load_strat_matrix()
# Dashboard/monitoring analytics operate on measure submissions only.  MIO also
# requires goal/task indicator submissions, so keep the full monitoring stream
# separately instead of feeding measures_only() into the MIO methodology.
_mio_requests_all = monitoring_data.load_monitoring_requests()
requests_df = ensure_request_columns(monitoring_data.measures_only(_mio_requests_all))
mio_requests_df = _mio_requests_all.copy() if isinstance(_mio_requests_all, pd.DataFrame) else pd.DataFrame()
workflow_logs = load_workflow_logs()
analytics_read_at = kyiv_now()


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
# Filters UI — pending values are isolated from the applied analytical context
# ============================================================

_an_defaults = {
    "data_mode": operational.MODE_CONFIRMED,
    "years": [], "quarters": [], "ssp": [], "deputies": [],
    "goals": [], "tasks": [], "product_types": [],
}
if "analytics_filters_applied_v20" not in st.session_state:
    st.session_state["analytics_filters_applied_v20"] = _an_defaults.copy()

_pending_defaults = {
    "analytics_pending_data_mode": st.session_state["analytics_filters_applied_v20"].get("data_mode", operational.MODE_CONFIRMED),
    "analytics_pending_years": list(st.session_state["analytics_filters_applied_v20"].get("years", [])),
    "analytics_pending_quarters": list(st.session_state["analytics_filters_applied_v20"].get("quarters", [])),
    "analytics_pending_ssp": list(st.session_state["analytics_filters_applied_v20"].get("ssp", [])),
    "analytics_pending_deputies": list(st.session_state["analytics_filters_applied_v20"].get("deputies", [])),
    "analytics_pending_goals": list(st.session_state["analytics_filters_applied_v20"].get("goals", [])),
    "analytics_pending_tasks": list(st.session_state["analytics_filters_applied_v20"].get("tasks", [])),
    "analytics_pending_products": list(st.session_state["analytics_filters_applied_v20"].get("product_types", [])),
}
for _key, _value in _pending_defaults.items():
    if _key not in st.session_state:
        st.session_state[_key] = _value


def _apply_analytics_filters_v20():
    st.session_state["analytics_filters_applied_v20"] = {
        "data_mode": st.session_state.get("analytics_pending_data_mode", operational.MODE_CONFIRMED),
        "years": list(st.session_state.get("analytics_pending_years", []) or []),
        "quarters": list(st.session_state.get("analytics_pending_quarters", []) or []),
        "ssp": list(st.session_state.get("analytics_pending_ssp", []) or []),
        "deputies": list(st.session_state.get("analytics_pending_deputies", []) or []),
        "goals": list(st.session_state.get("analytics_pending_goals", []) or []),
        "tasks": list(st.session_state.get("analytics_pending_tasks", []) or []),
        "product_types": list(st.session_state.get("analytics_pending_products", []) or []),
    }


def _reset_analytics_filters_v20():
    st.session_state["analytics_filters_applied_v20"] = _an_defaults.copy()
    st.session_state["analytics_pending_data_mode"] = operational.MODE_CONFIRMED
    st.session_state["analytics_pending_years"] = []
    st.session_state["analytics_pending_quarters"] = []
    st.session_state["analytics_pending_ssp"] = []
    st.session_state["analytics_pending_deputies"] = []
    st.session_state["analytics_pending_goals"] = []
    st.session_state["analytics_pending_tasks"] = []
    st.session_state["analytics_pending_products"] = []


with st.form("analytics_filters_form_v20"):
    st.markdown('<div class="filter-title">Параметри відбору</div>', unsafe_allow_html=True)
    a0, a1, a2 = st.columns([1.45, 0.75, 0.9])
    with a0:
        st.markdown('<div class="filter-field-label">Джерело даних</div>', unsafe_allow_html=True)
        st.radio("Джерело даних", operational.MODE_OPTIONS, horizontal=True,
                 key="analytics_pending_data_mode", label_visibility="collapsed")
    with a1:
        st.markdown('<div class="filter-field-label">Рік</div>', unsafe_allow_html=True)
        st.multiselect("Рік", YEAR_OPTIONS, key="analytics_pending_years",
                       placeholder="Усі роки", label_visibility="collapsed")
    with a2:
        st.markdown('<div class="filter-field-label">Квартал</div>', unsafe_allow_html=True)
        st.multiselect("Квартал", QUARTERS, key="analytics_pending_quarters",
                       placeholder="Усі квартали", label_visibility="collapsed")

    f1, f2, f3 = st.columns([1.2, 1.15, 1.3])
    with f1:
        st.markdown('<div class="filter-field-label">Самостійний структурний підрозділ</div>', unsafe_allow_html=True)
        st.multiselect("Самостійний структурний підрозділ", ssp_options,
                       format_func=lambda x: ssp_labels.get(x, x), key="analytics_pending_ssp",
                       placeholder="Усі підрозділи", label_visibility="collapsed")
    with f2:
        st.markdown('<div class="filter-field-label">Заступник Міністра</div>', unsafe_allow_html=True)
        st.multiselect("Заступник Міністра", deputy_options, key="analytics_pending_deputies",
                       placeholder="Усі заступники", label_visibility="collapsed")
    with f3:
        st.markdown('<div class="filter-field-label">Стратегічна ціль</div>', unsafe_allow_html=True)
        st.multiselect("Стратегічна ціль", list(goal_options.values()), key="analytics_pending_goals",
                       placeholder="Усі стратегічні цілі", label_visibility="collapsed")

    f4, f5 = st.columns([1.4, 1])
    with f4:
        st.markdown('<div class="filter-field-label">Завдання</div>', unsafe_allow_html=True)
        st.multiselect("Завдання", list(task_options.values()), key="analytics_pending_tasks",
                       placeholder="Усі завдання", label_visibility="collapsed")
    with f5:
        st.markdown('<div class="filter-field-label">Тип продукту</div>', unsafe_allow_html=True)
        st.multiselect("Тип продукту", product_type_options, key="analytics_pending_products",
                       placeholder="Усі типи продукту", label_visibility="collapsed")

    _an_a, _an_b = st.columns([1, 1])
    with _an_a:
        st.form_submit_button("Застосувати обрані параметри", type="primary", use_container_width=True,
                              on_click=_apply_analytics_filters_v20)
    with _an_b:
        st.form_submit_button("Скинути параметри", use_container_width=True,
                              on_click=_reset_analytics_filters_v20)

_an_applied = st.session_state.get("analytics_filters_applied_v20", _an_defaults.copy())
analytics_data_mode = _an_applied.get("data_mode", operational.MODE_CONFIRMED)
selected_years_raw = list(_an_applied.get("years", []) or [])
selected_quarters_raw = list(_an_applied.get("quarters", []) or [])
selected_ssp_indices = list(_an_applied.get("ssp", []) or [])
selected_deputies = list(_an_applied.get("deputies", []) or [])
selected_goal_labels = list(_an_applied.get("goals", []) or [])
selected_task_labels = list(_an_applied.get("tasks", []) or [])
selected_product_types = list(_an_applied.get("product_types", []) or [])

# Apply the selected data source only after the form has committed its pending values.
# The MIO stream intentionally remains full (measures + indicator submissions) so
# its annual integral is identical to the shared MIO page for the same methodology.
if not mio_requests_df.empty:
    mio_requests_df = apply_locked_status(mio_requests_df, status_col="status")
if analytics_data_mode == operational.MODE_OPERATIONAL:
    _analytics_targets = operational.build_target_map(strat_df)
    if not requests_df.empty:
        requests_df, _analytics_auto = operational.apply_operational_mode(requests_df, _analytics_targets)
    if not mio_requests_df.empty:
        mio_requests_df, _analytics_mio_auto = operational.apply_operational_mode(mio_requests_df, _analytics_targets)
        mio_requests_df = apply_locked_status(mio_requests_df, status_col="status")
requests_df = ensure_request_columns(append_confirmed_closeout_facts(requests_df))
# MIO must ignore legacy manual closeouts without a recorded fact, matching its
# methodology on the dedicated page. Indicator rows remain untouched.
mio_requests_df = append_confirmed_closeout_facts(mio_requests_df, include_incomplete=False)

selected_years = selected_years_raw if selected_years_raw else [2026]
selected_quarters = selected_quarters_raw if selected_quarters_raw else QUARTERS.copy()
selected_goal_codes = [code for code, label in goal_options.items() if label in selected_goal_labels]
selected_task_codes = [code for code, label in task_options.items() if label in selected_task_labels]
selected_ssp_labels = [ssp_labels.get(x, x) for x in selected_ssp_indices]


# ============================================================
# Analysis dataset
# ============================================================

base_period_results, all_period_data = prepare_analysis_context(strat_df, requests_df, selected_years, selected_quarters)
ssp_base_period_results, period_results = build_analytics_result_context(
    base_period_results, selected_ssp_indices, selected_deputies, selected_goal_codes, selected_task_codes, selected_product_types
)
active = _snapshot_rows_from_period_results(period_results)

if active.empty:
    st.warning("За обраними параметрами активних заходів не знайдено.")
    render_footer()
    st.stop()

period_requests = filter_period_requests_to_active_cohort(
    requests_df, active, selected_years, selected_quarters
)

plan_summary = build_analytics_plan_summary(period_results)
metrics = build_metrics(active)
metrics["completion"] = plan_summary.get("execution_by_measures_average")
metrics["coverage"] = plan_summary.get("coverage_average")
# Additional canonical outputs are passed through for analytical interpretation only.
# The text engine does not recalculate monitoring methodology; it compares and
# localises values already produced by the shared Dashboard aggregation layer.
metrics["completion_latest"] = plan_summary.get("execution_by_measures_latest")
metrics["completion_change"] = plan_summary.get("execution_by_measures_change")
metrics["goal_completion"] = plan_summary.get("execution_by_goals_average")
metrics["goal_completion_latest"] = plan_summary.get("execution_by_goals_latest")
metrics["goal_completion_change"] = plan_summary.get("execution_by_goals_change")
metrics["coverage_latest"] = plan_summary.get("coverage_latest")
metrics["coverage_change"] = plan_summary.get("coverage_change")
metrics["latest_period"] = plan_summary.get("latest_period")
metrics["latest_risk_summary"] = plan_summary.get("latest_risk_summary") or {}
goal_progress = build_analytics_goal_summary(period_results, active)
dep_progress = build_analytics_ssp_summary(period_results, active, base_results=ssp_base_period_results)
task_progress = build_analytics_task_summary(period_results, active)
product_progress = aggregate_product_progress(period_results, active)
status_counts = aggregate_status(active)
period_dynamics = build_analytics_dynamics(period_results)

# Canonical execution is provided by the shared Dashboard v3 aggregation layer.
comparison_years = sorted(set(selected_years + [max(selected_years) - 1])) if selected_years else []
if comparison_years:
    yoy_base_results, _ = prepare_analysis_context(strat_df, requests_df, comparison_years, selected_quarters)
    _, yoy_results = build_analytics_result_context(
        yoy_base_results, selected_ssp_indices, selected_deputies, selected_goal_codes, selected_task_codes, selected_product_types
    )
    yoy_comparison = build_year_over_year_comparison(yoy_results)
else:
    yoy_comparison = pd.DataFrame()

# ============================================================
# Reusable MіO analytical outputs
# ============================================================
# Annual integral evaluation is methodologically compatible with a full-year
# selection and content filters at the strategic-goal level. Organisational,
# task/product and partial-quarter filters do not trigger a synthetic recalculation
# of the integral; financing, which is measure-level, may still be filtered to the
# active cohort.
mio_goal_evaluation = pd.DataFrame()
mio_goal_task_evaluation = pd.DataFrame()
mio_measure_evaluation = pd.DataFrame()
mio_financing = pd.DataFrame()
mio_filter_limited = False
try:
    _mio_years = [int(y) for y in selected_years if int(y) in (2026, 2027, 2028)]
    _mio_outputs = mio_shared.build_mio_analytics(strat_df, mio_requests_df, _mio_years or [2026])
    _all_mio_goals = _mio_outputs.get("goals", pd.DataFrame()).copy()
    _all_mio_goal_tasks = _mio_outputs.get("goals_tasks", pd.DataFrame()).copy()
    _all_mio_measures = _mio_outputs.get("measures", pd.DataFrame()).copy()
    _all_mio_financing = _mio_outputs.get("financing", pd.DataFrame()).copy()

    _annual_scope = set(selected_quarters) == set(QUARTERS)
    _integral_compatible = _annual_scope and not any((selected_ssp_indices, selected_deputies, selected_task_codes, selected_product_types))
    _mio_indicator_compatible = _annual_scope and not any((selected_ssp_indices, selected_deputies, selected_product_types))
    if _integral_compatible:
        mio_goal_evaluation = _all_mio_goals
        if selected_goal_codes and not mio_goal_evaluation.empty and "Код" in mio_goal_evaluation.columns:
            mio_goal_evaluation = mio_goal_evaluation[mio_goal_evaluation["Код"].astype(str).isin(set(map(str, selected_goal_codes)))].copy()
    else:
        mio_filter_limited = not _all_mio_goals.empty

    # Goal/task indicator evaluations are annual and can be narrowed by content
    # hierarchy, but not by organisational/product filters that have no valid
    # mapping to the MIO indicator methodology.
    if _mio_indicator_compatible and not _all_mio_goal_tasks.empty:
        mio_goal_task_evaluation = _all_mio_goal_tasks.copy()
        if selected_goal_codes and "Код" in mio_goal_task_evaluation.columns:
            _goal_prefixes = tuple(str(x) for x in selected_goal_codes)
            mio_goal_task_evaluation = mio_goal_task_evaluation[
                mio_goal_task_evaluation["Код"].astype(str).apply(lambda x: any(x == g or x.startswith(g + ".") for g in _goal_prefixes))
            ].copy()
        if selected_task_codes and "Код" in mio_goal_task_evaluation.columns:
            _task_set = set(map(str, selected_task_codes))
            mio_goal_task_evaluation = mio_goal_task_evaluation[
                (mio_goal_task_evaluation.get("Рівень", pd.Series("", index=mio_goal_task_evaluation.index)).astype(str).eq("goal"))
                | (mio_goal_task_evaluation["Код"].astype(str).isin(_task_set))
            ].copy()

    _active_codes_for_mio = set(active.get("code", pd.Series(dtype=object)).astype(str).str.strip())
    if _annual_scope and not _all_mio_measures.empty and "Захід" in _all_mio_measures.columns:
        mio_measure_evaluation = _all_mio_measures[_all_mio_measures["Захід"].astype(str).str.strip().isin(_active_codes_for_mio)].copy()
    if not _all_mio_financing.empty and "Захід" in _all_mio_financing.columns:
        mio_financing = _all_mio_financing[_all_mio_financing["Захід"].astype(str).str.strip().isin(_active_codes_for_mio)].copy()
except Exception as exc:
    log_exception("Analytics reusable MіO outputs", exc)
    mio_goal_evaluation = pd.DataFrame()
    mio_goal_task_evaluation = pd.DataFrame()
    mio_measure_evaluation = pd.DataFrame()
    mio_financing = pd.DataFrame()

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

analytics_text_context = build_analytics_text_context(
    filters=filters,
    metrics=metrics,
    goal_progress=goal_progress,
    task_progress=task_progress,
    department_progress=dep_progress,
    product_progress=product_progress,
    status_counts=status_counts,
    period_dynamics=period_dynamics,
    yoy_comparison=yoy_comparison,
    active=active,
    mio_goal_evaluation=mio_goal_evaluation,
    mio_goal_task_evaluation=mio_goal_task_evaluation,
    mio_measure_evaluation=mio_measure_evaluation,
    mio_financing=mio_financing,
)

ANALYTICS_TEXT_DEBUG = str(os.getenv("ANALYTICS_TEXT_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on"}
analytics_text_engine_used = "new_success"
analytics_text_engine_incident = ""
analytics_text_available = True
try:
    analytical_text = generate_analytics_note(context=analytics_text_context)
except Exception as exc:
    # A failed analytical engine must never masquerade as a successful legacy
    # note. Keep the old function in the codebase for developer compatibility,
    # but do not expose it as a production fallback.
    _incident_seed = f"{type(exc).__name__}:{exc}".encode("utf-8", errors="replace")
    analytics_text_engine_incident = "AN-" + hashlib.sha256(_incident_seed).hexdigest()[:10].upper()
    # The same incident code shown in the UI is written with the full traceback.
    _validation_warnings = list(getattr(exc, "validation_warnings", ()) or ())
    log_exception(
        "Analytics rule-based text generator",
        exc,
        incident_code=analytics_text_engine_incident,
        diagnostics={
            "validation_warnings": _validation_warnings,
            "filters": filters,
        },
    )
    analytics_text_engine_used = "new_failed"
    analytics_text_available = False
    analytical_text = ""
    if ANALYTICS_TEXT_DEBUG:
        st.caption(f"Text engine: NEW ANALYTICS ENGINE — FAILED · Incident: {analytics_text_engine_incident}")
        if _validation_warnings:
            st.code("\n".join(_validation_warnings), language="text")
    if ANALYTICS_TEXT_DEBUG:
        raise
    st.error(
        "Аналітичну довідку не сформовано через технічну помилку. "
        f"Код інциденту: {analytics_text_engine_incident}."
    )

if ANALYTICS_TEXT_DEBUG:
    if analytics_text_engine_used == "new_success":
        st.caption("Text engine: NEW ANALYTICS ENGINE — SUCCESS")
    else:
        st.caption(f"Text engine: NEW ANALYTICS ENGINE — FAILED · Incident: {analytics_text_engine_incident}")


# ============================================================
# KPI cards
# ============================================================

_completion_label = format_pct(metrics["completion"])
_coverage_label = format_pct(metrics["coverage"])
st.markdown(
    f"""
<div class="alert-grid">
    <div class="alert-card alert-blue">
        <div class="alert-title">Рівень виконання Стратегічного плану в обраному періоді</div>
        <div class="alert-value">{_completion_label}</div>
    </div>
    <div class="alert-card alert-red">
        <div class="alert-title">Потребують управлінської уваги</div>
        <div class="alert-value">{metrics['problem']}</div>
    </div>
    <div class="alert-card alert-yellow">
        <div class="alert-title">Покриття моніторингом</div>
        <div class="alert-value">{_coverage_label}</div>
    </div>
    <div class="alert-card alert-green">
        <div class="alert-title">Заходів у вибірці</div>
        <div class="alert-value">{metrics['unique_measures']}</div>
    </div>
</div>
""",
    unsafe_allow_html=True
)

# Compact MіO result strip. Annual integral components are shown only when the
# applied filter set is methodologically compatible with the annual MіO model.
if not mio_goal_evaluation.empty:
    _mio_year = max([int(y) for y in selected_years if int(y) in (2026, 2027, 2028)] or [2026])
    _mio_summary = mio_shared.summarize_integral_goals(mio_goal_evaluation, _mio_year)
    # Semantically typed fields prevent a weighted component (e.g. 20% ×
    # measures) from ever being displayed as the final integral.
    _mio_integral = _mio_summary.average_integral
    _mio_measures = _mio_summary.average_measure_execution
    _mio_tasks = _mio_summary.average_task_score
    _mio_progress = _mio_summary.average_strategic_progress
    _fin_avg = analytics_text_context.factual_value("mio.fin.avg_financial_execution")
    st.markdown(
        f"""
<div class="mio-summary-box">
    <div class="mio-summary-title">Оцінка МіО · {_mio_year}</div>
    <div class="mio-summary-grid">
        <div class="mio-mini"><span>Інтегральна оцінка</span><b>{format_pct(_mio_integral)}</b></div>
        <div class="mio-mini"><span>Виконання заходів</span><b>{format_pct(_mio_measures)}</b></div>
        <div class="mio-mini"><span>Оцінка завдань</span><b>{format_pct(_mio_tasks)}</b></div>
        <div class="mio-mini"><span>Прогрес індикаторів цілей</span><b>{format_pct(_mio_progress)}</b></div>
        <div class="mio-mini"><span>Фінансове виконання</span><b>{format_pct(_fin_avg)}</b></div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )
elif mio_filter_limited:
    st.caption("Оцінка МіО не перераховується за застосованим організаційним, продуктовим або неповним квартальним зрізом; аналітика моніторингу нижче залишається повністю відфільтрованою.")

render_year_over_year_block(yoy_comparison)


# ============================================================
# Analytical note
# ============================================================

if analytics_text_available:
    st.markdown(
        """
<div class="report-box">
    <div class="report-title">Автоматично сформована аналітична довідка</div>
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
""",
    unsafe_allow_html=True
)

g1, g2 = st.columns(2)

with g1:
    if not period_dynamics.empty:
        fig = px.line(
            period_dynamics,
            x="Період",
            y="Виконання",
            markers=True,
            title="Динаміка оціненого виконання",
            labels={"value": "Відсоток", "variable": "Показник"}
        )
        fig.update_layout(legend_title_text="Показник")
        st.plotly_chart(fig, use_container_width=True)

with g2:
    if not goal_progress.empty:
        goal_chart = goal_progress.sort_values("goal_code").copy()
        for _column in ("Виконання", "Покриття_%"):
            if _column in goal_chart.columns:
                goal_chart[_column] = pd.to_numeric(goal_chart[_column], errors="coerce").round(2)
        fig = px.bar(
            goal_chart,
            x="goal_code",
            y="Виконання",
            text="Виконання",
            hover_data=["strategic_goal", "Унікальних_заходів", "Покриття_%", "Проблемних", "Без_даних"],
            title="Виконання за стратегічними цілями",
            labels={"goal_code": "Стратегічна ціль", "Виконання": "Виконання, %"}
        )
        fig.update_traces(texttemplate="%{text:.2f}")
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
            hover_data=["deputy_minister", "Унікальних_заходів", "Покриття_%", "Проблемних", "Без_даних"],
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
            hover_data=["Виконання", "Покриття_%", "Проблемних", "Без_даних"],
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
        top_tasks = task_progress.sort_values(["Проблемних", "Без_даних"], ascending=False).head(10).copy()
        top_tasks["Завдання"] = top_tasks["task_code"].astype(str)
        fig = px.bar(
            top_tasks,
            x="Завдання",
            y="Проблемних",
            text="Проблемних",
            hover_data=["task_name", "Виконання", "Покриття_%", "Без_даних"],
            title="Завдання з найбільшою кількістю сигналів управлінської уваги",
            labels={"Проблемних": "Сигнали уваги"}
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
    render_readonly_table(_top_returned.head(20), visual_style="signal", variant="ranking")
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
        render_readonly_table(approval_speed["stage_average"], visual_style="signal", variant="analytics")
with _speed_right:
    st.markdown("**Заявки, що зараз очікують найдовше**")
    if approval_speed["hanging"].empty:
        st.info("У поточному зрізі немає заявок на активних ланках погодження.")
    else:
        render_readonly_table(approval_speed["hanging"].head(20), visual_style="signal", variant="analytics")
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
    flex_note="",
) if analytics_text_available else None

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
        data=docx_file or b"",
        disabled=not analytics_text_available,
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
        "execution_score": "Виконання, %",
        "risk_level": "Рівень ризику",
    })
    cols = [
        "Рік", "Квартал", "Код", "Захід", "Стратегічна ціль", "Завдання", "Тип продукту",
        "ССП", "Заступник Міністра", "Планове значення", "Фактичне значення", "Статус",
        "Виконання, %", "Рівень ризику"
    ]
    render_readonly_table(
        show_active[[c for c in cols if c in show_active.columns]],
        visual_style="signal",
        variant="wide",
        metric_columns={"Виконання, %": "blue"},
        status_columns={"Статус"},
        risk_columns={"Рівень ризику"},
        column_widths={
            "Рік": 110,
            "Захід": 300,
            "Завдання": 300,
            "Тип продукту": 170,
        },
        scroll_columns={"Захід", "Завдання"},
        enforce_column_widths=True,
    )

with tab2:
    goal_check = goal_progress.rename(columns={
        "goal_code": "Код стратегічної цілі",
        "strategic_goal": "Стратегічна ціль",
        "average_by_measures": "Середнє виконання за заходами, %",
        "latest_by_measures": "Останнє виконання за заходами, %",
        "change_by_measures": "Зміна за заходами, в.п.",
        "Виконання": "Середнє виконання, %",
        "Останнє_виконання": "Останнє виконання, %",
        "Зміна": "Зміна, в.п.",
        "Покриття_%": "Покриття, %",
        "Заходів_періодів": "Записів захід-період",
        "Унікальних_заходів": "Унікальних заходів",
        "Покриття_eligible": "У покритті",
        "Без_даних": "Без даних",
    })
    goal_numeric = {
        "Середнє виконання за заходами, %", "Останнє виконання за заходами, %",
        "Зміна за заходами, в.п.", "Середнє виконання, %",
        "Останнє виконання, %", "Зміна, в.п.", "Покриття, %",
    }
    render_readonly_table(
        goal_check,
        visual_style="signal",
        variant="analytics",
        metric_columns={
            "Середнє виконання, %": "blue",
            "Останнє виконання, %": "blue",
            "Покриття, %": "blue",
        },
        delta_columns={"Зміна, в.п.", "Зміна за заходами, в.п."},
        formatters={column: format_number_2 for column in goal_numeric},
        column_groups={
            "Ідентифікація": {"columns": ["Код стратегічної цілі", "Стратегічна ціль"], "color": "navy"},
            "Виконання": {"columns": [
                "Середнє виконання за заходами, %", "Останнє виконання за заходами, %",
                "Зміна за заходами, в.п.", "Середнє виконання, %",
                "Останнє виконання, %", "Зміна, в.п."
            ], "color": "blue"},
            "Покриття": {"columns": ["Покриття, %", "У покритті", "Подано"], "color": "light-blue"},
            "Увага": {"columns": ["Проблемних", "Без даних"], "color": "red"},
        },
    )

with tab3:
    task_check = task_progress.rename(columns={
        "task_code": "Код завдання",
        "task_name": "Завдання",
        "Виконання": "Середнє виконання, %",
        "Останнє_виконання": "Останнє виконання, %",
        "Зміна": "Зміна, в.п.",
        "Покриття_%": "Покриття, %",
        "Заходів_періодів": "Записів захід-період",
        "Унікальних_заходів": "Унікальних заходів",
        "Покриття_eligible": "У покритті",
        "Без_даних": "Без даних",
    })
    task_numeric = {"Середнє виконання, %", "Останнє виконання, %", "Зміна, в.п.", "Покриття, %"}
    render_readonly_table(
        task_check,
        visual_style="signal",
        variant="analytics",
        metric_columns={"Середнє виконання, %": "blue", "Останнє виконання, %": "blue", "Покриття, %": "blue"},
        delta_columns={"Зміна, в.п."},
        formatters={column: format_number_2 for column in task_numeric},
        column_widths={"Завдання": 300},
        scroll_columns={"Завдання"},
        enforce_column_widths=True,
        column_groups={
            "Ідентифікація": {"columns": ["Код завдання", "Завдання"], "color": "navy"},
            "Виконання": {"columns": ["Середнє виконання, %", "Останнє виконання, %", "Зміна, в.п."], "color": "blue"},
            "Покриття": {"columns": ["Покриття, %", "У покритті", "Подано"], "color": "light-blue"},
            "Увага": {"columns": ["Проблемних", "Без даних"], "color": "red"},
        },
    )

with tab4:
    ssp_check = dep_progress.rename(columns={
        "ssp_index": "ССП",
        "Виконання": "Середнє виконання, %",
        "Останнє_виконання": "Останнє виконання, %",
        "Зміна": "Зміна, в.п.",
        "Покриття_%": "Середнє покриття, %",
        "latest_coverage": "Останнє покриття, %",
        "risk_without_substantial_latest": "Без суттєвого ризику, %",
        "risk_high_critical_latest": "Високий + критичний ризик, %",
        "latest_period": "Останній період",
        "portfolio_weight_pct": "Вага портфеля, %",
        "underperformance_contribution_pct": "Частка у недовиконанні, %",
        "risk_contribution_pct": "Частка у концентрації ризику, %",
        "portfolio_measure_count": "Заходів у портфелі",
        "department": "Самостійний структурний підрозділ",
        "deputy_minister": "Заступник Міністра",
        "Заходів_періодів": "Записів захід-період",
        "Унікальних_заходів": "Унікальних заходів",
        "Покриття_eligible": "У покритті",
        "Без_даних": "Без даних",
    })
    ssp_numeric = {
        "Середнє виконання, %", "Останнє виконання, %", "Зміна, в.п.",
        "Середнє покриття, %", "Останнє покриття, %",
        "Без суттєвого ризику, %", "Високий + критичний ризик, %",
        "Вага портфеля, %", "Частка у недовиконанні, %",
        "Частка у концентрації ризику, %",
    }
    render_readonly_table(
        ssp_check,
        visual_style="signal",
        variant="ranking",
        metric_columns={
            "Середнє виконання, %": "blue", "Останнє виконання, %": "blue",
            "Середнє покриття, %": "blue", "Останнє покриття, %": "blue",
        },
        delta_columns={"Зміна, в.п."},
        formatters={column: format_number_2 for column in ssp_numeric},
        column_groups={
            "Ідентифікація": {"columns": ["ССП", "Самостійний структурний підрозділ", "Заступник Міністра"], "color": "navy"},
            "Виконання": {"columns": ["Середнє виконання, %", "Останнє виконання, %", "Зміна, в.п."], "color": "blue"},
            "Покриття": {"columns": ["Середнє покриття, %", "Останнє покриття, %", "У покритті", "Подано"], "color": "light-blue"},
            "Ризик": {"columns": ["Без суттєвого ризику, %", "Високий + критичний ризик, %", "Проблемних", "Без даних"], "color": "red"},
            "Портфель": {"columns": ["Вага портфеля, %", "Частка у недовиконанні, %", "Частка у концентрації ризику, %"], "color": "navy"},
        },
        row_class_fn=_signal_delta_row_class,
        signal_edges=True,
    )

with tab5:
    product_check = product_progress.rename(columns={
        "product_type": "Тип продукту",
        "Унікальних_заходів": "Унікальних заходів",
        "Виконання": "Виконання, %",
        "Покриття_%": "Покриття, %",
        "Без_даних": "Без даних",
    })
    render_readonly_table(
        product_check,
        visual_style="signal",
        variant="analytics",
        metric_columns={"Виконання, %": "blue", "Покриття, %": "blue"},
        formatters={"Виконання, %": format_number_2, "Покриття, %": format_number_2},
        column_groups={
            "Ідентифікація": {"columns": ["Тип продукту"], "color": "navy"},
            "Виконання": {"columns": ["Виконання, %"], "color": "blue"},
            "Покриття": {"columns": ["Покриття, %"], "color": "light-blue"},
            "Увага": {"columns": ["Проблемних", "Без даних"], "color": "red"},
        },
    )

with tab6:
    registry_display = period_requests.rename(columns={
        "id": "ID заявки",
        "year": "Рік",
        "quarter": "Квартал",
        "department": "ССП",
        "responsible_person": "Відповідальна особа",
        "phone": "Номер телефону",
        "email": "Електронна пошта",
        "strat_code": "Код заходу",
        "object_name": "Назва заходу",
        "indicator_name": "Індикатор",
        "status": "Статус виконання",
        "progress_text": "Опис прогресу",
        "numeric_value": "Фактичне числове значення",
        "value_text": "Фактичне текстове значення",
        "risks": "Ризики / проблеми / відхилення",
        "submitted_at": "Дата подання",
        "approval_status": "Статус погодження",
        "admin_comment": "Коментар координатора",
        "created_at": "Дата створення",
        "updated_at": "Дата оновлення",
        "start_date": "Початок виконання",
        "end_date": "Кінець виконання",
        "file_names": "Файли",
        "file_urls": "Посилання на файли",
        "npa_link": "Посилання на НПА",
        "approval_chain": "Схема погодження",
        "chain_stage": "Етап погодження",
        "scheme_label": "Назва схеми",
        "object_kind": "Тип об'єкта",
        "as_of_date": "Дата станом на",
        "final_locked": "Фінально заблоковано",
        "final_locked_at": "Дата фінального блокування",
        "_auto_inherited": "Автоматично успадковано",
        "_inherited_from_quarter": "Успадковано з кварталу",
    })
    render_readonly_table(
        registry_display,
        visual_style="signal",
        variant="wide",
        column_widths={
            "Назва заходу": 300,
            "Індикатор": 300,
            "Статус виконання": 180,
            "Статус погодження": 180,
        },
        scroll_columns={"Назва заходу", "Індикатор"},
        enforce_column_widths=True,
        status_columns={"Статус виконання", "Статус погодження"},
    )

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# Footer
# ============================================================

render_footer()
