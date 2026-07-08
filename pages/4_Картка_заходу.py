import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from core.db import get_supabase_client
from core.deputies import DEPUTY_MINISTER_BY_SSP
from core.ui import load_css
from core.errors import log_exception
from core.config import FILE_PATH, SHEET_NAME
from core.excel_loader import read_excel_sheet
from core import operational
from core.closeouts import load_manual_closeouts
from datetime import datetime
from html import escape
from textwrap import dedent
import re

from core.page_setup import page_setup, render_footer
from core.strategic_data import load_strat_matrix as core_load_strat_matrix
from core import monitoring_data
from config.roles import ROLE_SSP, ROLE_SSP_HEAD, ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY, ROLE_ADMIN, ROLE_SUPER_ADMIN, ENABLE_PERSONAL_CABINETS
from core.access import filter_actions_for_user, filter_requests_for_user
from core.ui import render_scope_toggle


current_user = page_setup("Картка заходу", page_name="Картка заходу")
current_role = current_user.get("role")
can_view_submission_history = (
    not ENABLE_PERSONAL_CABINETS or current_role in [ROLE_ADMIN, ROLE_SUPER_ADMIN]
)
can_submit_monitoring_data = (
    # Пункт 2 нового ТЗ: подавати відомості можуть не тільки "Відповідальний
    # від ССП", а й керівник ССП / керівник управління / заступник —
    # схема погодження для них автоматично звужується до координатора
    # (див. core/approval_schemes.py: scheme_options_for_submitter).
    not ENABLE_PERSONAL_CABINETS
    or current_role in [ROLE_SSP, ROLE_SSP_HEAD, ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY]
)



supabase = get_supabase_client()
# ============================================================
# STYLE
# ============================================================

st.markdown("""
<style>
header[data-testid="stHeader"] {
    background: transparent !important;
}
html, body, [class*="css"] {
    font-family: 'Helvetica Neue', 'Arial', sans-serif;
}

.stApp {
    background:
        linear-gradient(rgba(15,23,42,0.025) 1px, transparent 1px),
        linear-gradient(90deg, rgba(15,23,42,0.025) 1px, transparent 1px),
        radial-gradient(circle at top right, rgba(37,99,235,0.09), transparent 28%),
        radial-gradient(circle at bottom left, rgba(22,163,74,0.07), transparent 30%),
        linear-gradient(180deg, #f7f9fc 0%, #eef3f8 100%);
    background-size: 36px 36px, 36px 36px, auto, auto, auto;
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

.top-grid {
    display: grid;
    grid-template-columns: 1.4fr 0.8fr;
    gap: 16px;
    margin-bottom: 18px;
}

.hero-card {
    background: rgba(255,255,255,0.95);
    border: 1px solid #d8dee9;
    border-radius: 18px;
    padding: 26px 30px;
    box-shadow: 0 10px 26px rgba(15,23,42,0.07);
}

.ministry-card {
    background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(248,250,252,0.96));
    border: 1px solid #d8dee9;
    border-radius: 18px;
    padding: 22px 24px;
    box-shadow: 0 10px 26px rgba(15,23,42,0.055);
}

.hero-kicker {
    font-size: 13px;
    font-weight: 800;
    color: #1d4ed8;
    text-transform: uppercase;
    letter-spacing: .04em;
    margin-bottom: 8px;
}

.hero-title {
    font-size: 34px;
    font-weight: 950;
    color: #0f172a;
    line-height: 1.15;
    margin-bottom: 10px;
}

.hero-subtitle {
    color: #475569;
    font-size: 15px;
    line-height: 1.55;
}

.ministry-title {
    color: #0f172a;
    font-weight: 900;
    font-size: 16px;
    margin-bottom: 8px;
}

.ministry-line {
    color: #475569;
    font-size: 13px;
    line-height: 1.5;
}

.status-pill-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 14px;
}

.status-pill {
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 999px;
    padding: 7px 11px;
    font-size: 13px;
    color: #334155;
    font-weight: 700;
}

.card {
    background: rgba(255,255,255,0.94);
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 20px 22px;
    margin: 18px 0;
    box-shadow: 0 6px 18px rgba(15,23,42,0.045);
}

.card-title {
    font-size: 20px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 8px;
}

.card-subtitle {
    color: #64748b;
    font-size: 14px;
    margin-bottom: 12px;
}

.filter-panel {
    background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(241,246,253,0.98));
    border: 1px solid #cbd8ea;
    border-radius: 18px;
    padding: 18px 20px 10px 20px;
    margin-top: 12px;
    box-shadow: 0 10px 24px rgba(15,23,42,0.07);
}

div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stTextInput"] input {
    background-color: #d7eaff !important;
    border: 1px solid #8fb3df !important;
    border-radius: 10px !important;
    min-height: 43px !important;
    box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.08) !important;
}

div[data-testid="stSelectbox"] label,
div[data-testid="stTextInput"] label {
    font-weight: 750 !important;
    color: #1e293b !important;
}

/* Passport grid - flexible layout */
.passport-grid {
    display: grid;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    gap: 14px;
    margin-top: 12px;
}

/* Span sizes */
.col-2  { grid-column: span 2; }
.col-3  { grid-column: span 3; }
.col-4  { grid-column: span 4; }
.col-6  { grid-column: span 6; }
.col-8  { grid-column: span 8; }
.col-12 { grid-column: span 12; }

.passport-cell {
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    min-height: 90px;
    overflow-wrap: anywhere;
}

.passport-label {
    color: #64748b;
    font-size: 12px;
    margin-bottom: 6px;
    line-height: 1.35;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    font-weight: 600;
}

.passport-value {
    color: #0f172a;
    font-weight: 800;
    font-size: 15px;
    line-height: 1.35;
}

.passport-muted {
    color: #64748b;
    font-size: 13px;
    line-height: 1.45;
    margin-top: 4px;
}

/* Планові показники — горизонтальні чіпи */
.plan-chips {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 8px;
}

.plan-chip {
    background: linear-gradient(135deg, #eff6ff, #e0f2fe);
    border: 1px solid #bfdbfe;
    border-radius: 12px;
    padding: 8px 14px;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 90px;
}

.plan-chip-year {
    font-size: 11px;
    color: #64748b;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.plan-chip-val {
    font-size: 18px;
    font-weight: 900;
    color: #1d4ed8;
    line-height: 1.2;
    margin-top: 2px;
}

/* Фінансування */
.finance-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-top: 8px;
}

.finance-block {
    background: linear-gradient(135deg, #f0fdf4, #f7f9fc);
    border: 1px solid #bbf7d0;
    border-radius: 12px;
    padding: 12px 14px;
}

.finance-block-alt {
    background: linear-gradient(135deg, #fffbeb, #f7f9fc);
    border: 1px solid #fde68a;
    border-radius: 12px;
    padding: 12px 14px;
}

.finance-source {
    font-size: 11px;
    color: #64748b;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 4px;
}

.finance-kpkvk {
    font-size: 15px;
    font-weight: 900;
    color: #064e3b;
}

.finance-amount {
    font-size: 12px;
    color: #475569;
    margin-top: 4px;
}

.finance-single {
    background: linear-gradient(135deg, #f0fdf4, #f7f9fc);
    border: 1px solid #bbf7d0;
    border-radius: 12px;
    padding: 12px 14px;
    margin-top: 8px;
}

.split-box {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0;
}

.split-box > div:first-child {
    padding-right: 16px;
    border-right: 1px solid #cbd5e1;
}

.split-box > div:last-child {
    padding-left: 16px;
}

.badge-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 12px 0;
}

.badge {
    background: #eef6ff;
    border: 1px solid #bfdbfe;
    color: #1d4ed8;
    border-radius: 999px;
    padding: 7px 11px;
    font-size: 13px;
    font-weight: 800;
}

.badge-green {
    background: #dcfce7;
    border: 1px solid #bbf7d0;
    color: #166534;
}

.badge-yellow {
    background: #fef9c3;
    border: 1px solid #fde68a;
    color: #854d0e;
}

.badge-red {
    background: #fee2e2;
    border: 1px solid #fecaca;
    color: #991b1b;
}

.badge-gray {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    color: #475569;
}

/* Квартальна шкала — bar chart style */
.quarter-timeline {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
    margin-top: 10px;
}

.quarter-bar-wrap {
    display: flex;
    flex-direction: column;
    align-items: stretch;
}

.quarter-bar-label {
    font-size: 12px;
    font-weight: 800;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 6px;
    text-align: center;
}

.quarter-bar-outer {
    background: #e2e8f0;
    border-radius: 8px;
    height: 10px;
    overflow: hidden;
    margin-bottom: 8px;
}

.quarter-bar-inner {
    height: 100%;
    border-radius: 8px;
    transition: width 0.3s ease;
}

.quarter-card {
    border-radius: 16px;
    border: 1px solid #d8dee9;
    padding: 16px;
    background: #f8fafc;
    min-height: 145px;
    overflow-wrap: anywhere;
}

.quarter-title {
    font-weight: 950;
    color: #0f172a;
    margin-bottom: 8px;
    font-size: 16px;
}

.quarter-value {
    font-size: 23px;
    font-weight: 950;
    color: #0f172a;
    margin-bottom: 5px;
}

.quarter-plan {
    font-size: 13px;
    color: #475569;
    line-height: 1.45;
}

.quarter-status {
    margin-top: 10px;
    font-size: 12px;
    font-weight: 850;
    display: inline-block;
    border-radius: 999px;
    padding: 5px 9px;
}

.q-approved { background: #dcfce7; border-color: #bbf7d0; }
.q-approved .quarter-status { background: #bbf7d0; color: #166534; }
.q-waiting { background: #fef9c3; border-color: #fde68a; }
.q-waiting .quarter-status { background: #fde68a; color: #854d0e; }
.q-returned { background: #fee2e2; border-color: #fecaca; }
.q-returned .quarter-status { background: #fecaca; color: #991b1b; }
.q-empty { background: #f8fafc; }
.q-empty .quarter-status { background: #e2e8f0; color: #475569; }

/* Progress status badge */
.progress-status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border-radius: 999px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 800;
    margin-top: 8px;
}

.progress-status-done { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
.progress-status-partial { background: #fef9c3; color: #854d0e; border: 1px solid #fde68a; }
.progress-status-low { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
.progress-status-na { background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; }
.progress-status-obsolete { background: #f3e8ff; color: #6b21a8; border: 1px solid #d8b4fe; }

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.9);
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

div[data-testid="stMetricLabel"] { min-height: 48px !important; }
div[data-testid="stMetricLabel"] p {
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: unset !important;
    font-size: 12px !important;
    line-height: 1.25 !important;
}
div[data-testid="stMetricValue"] { font-size: 30px !important; }

/* Quick links */
.quick-links-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-top: 8px;
}

.quick-link-btn {
    display: flex;
    align-items: center;
    gap: 14px;
    background: linear-gradient(135deg, #005BBB 0%, #2563eb 45%, #FFD500 100%);
    border-radius: 18px;
    padding: 22px 28px;
    border: 1px solid rgba(255,255,255,0.32);
    box-shadow: 0 16px 32px rgba(0,91,187,0.28), inset 0 1px 0 rgba(255,255,255,0.24);
    text-decoration: none;
    cursor: pointer;
    transition: filter 0.2s, transform 0.2s;
}

.quick-link-btn:hover { filter: brightness(1.05); transform: translateY(-2px); }

.quick-link-icon {
    font-size: 28px;
    flex-shrink: 0;
}

.quick-link-text {
    font-size: 17px;
    font-weight: 900;
    color: #ffffff;
    line-height: 1.2;
}

.quick-link-sub {
    font-size: 12px;
    color: rgba(255,255,255,0.8);
    margin-top: 2px;
}

div[data-testid="stPageLink"] {
    width: 100% !important;
    display: block !important;
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}

div[data-testid="stPageLink"] a {
    width: 100% !important;
    min-height: 86px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: linear-gradient(135deg, #005BBB 0%, #2563eb 45%, #FFD500 100%) !important;
    color: #ffffff !important;
    border-radius: 18px !important;
    padding: 22px 28px !important;
    border: 1px solid rgba(255,255,255,0.32) !important;
    font-size: 18px !important;
    font-weight: 950 !important;
    letter-spacing: 0.2px !important;
    text-decoration: none !important;
    box-shadow: 0 16px 32px rgba(0,91,187,0.28), inset 0 1px 0 rgba(255,255,255,0.24) !important;
}

div[data-testid="stPageLink"] a p {
    color: #ffffff !important;
    font-size: 18px !important;
    font-weight: 950 !important;
    margin: 0 !important;
}

div[data-testid="stPageLink"] a svg {
    color: #ffffff !important;
    fill: #ffffff !important;
}

div[data-testid="stPageLink"] a:hover {
    filter: brightness(1.05);
    transform: translateY(-1px);
}

.footer {
    text-align: center;
    color: #94a3b8;
    font-size: clamp(10px, 0.9vw, 12px);
    margin-top: 40px;
    padding: 18px 0 10px;
    border-top: 1px solid #e2e8f0;
}

@media (max-width: 1100px) {
    .top-grid,
    .quarter-timeline,
    .split-box,
    .quick-links-grid,
    .finance-grid {
        grid-template-columns: 1fr;
    }
    .split-box > div:first-child {
        border-right: none;
        border-bottom: 1px solid #cbd5e1;
        padding-right: 0;
        padding-bottom: 12px;
        margin-bottom: 12px;
    }
    .split-box > div:last-child { padding-left: 0; }
    .col-2, .col-3, .col-4, .col-6, .col-8 { grid-column: span 12; }
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# HELPERS
# ============================================================

def render_html(html):
    html = str(html)
    html = "\n".join(line.lstrip() for line in html.splitlines() if line.strip())
    st.markdown(html, unsafe_allow_html=True)


def clean(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in ["none", "nan", "nat"]:
        return ""
    return text


def display_value(value, fallback="—"):
    text = clean(value)
    return escape(text) if text else fallback


def safe_col(data, idx):
    if idx < data.shape[1]:
        return data.iloc[:, idx]
    return pd.Series([""] * len(data), index=data.index)


def strip_leading_code(text, code):
    value = clean(text)
    code_value = clean(code)
    if code_value and value.startswith(code_value):
        value = value[len(code_value):].lstrip(" .—-–|:")
    return value


def to_number(value):
    text = str(value).replace(",", ".").replace("\u00a0", " ").strip()
    if text.lower() in ["", "nan", "none", "н.д.", "нд", "x", "х", "так", "ні", "да", "нет", "—", "-"]:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if match:
        try:
            return float(match.group())
        except Exception:
            return None
    return None


def normalize_text(value):
    return str(value).strip().lower().replace("і", "i")


def get_goal_code(code):
    parts = str(code).split(".")
    return parts[0] + "." if parts else ""


def get_task_code(code):
    parts = str(code).split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}."
    return ""


def split_first_executor(value):
    text = clean(value)
    if not text:
        return ""
    for sep in ["\n", ";", "|", ","]:
        if sep in text:
            return clean(text.split(sep)[0])
    return text


def format_quarter_period(val):
    """Convert quarter start/end value to human-readable Ukrainian text"""
    text = clean(val)
    if not text or text.lower() in ["x", "х", "—", "-", ""]:
        return "х"
    # Try to detect quarter pattern like "1 квартал 2026"
    if "квартал" in text.lower():
        return text
    # Try to detect date/numeric year patterns
    num = to_number(text)
    if num is not None:
        year = int(num)
        if 2020 <= year <= 2035:
            return str(year)
    return text


def get_period_label(raw_val):
    """Format start/end period properly from Excel values"""
    text = clean(raw_val)
    if not text or text.lower() in ["x", "х", "—", "-", ""]:
        return "х"
    # Already has "квартал" — keep as is
    if "квартал" in text.lower():
        return text
    # Pure number — might be a year
    num = to_number(text)
    if num is not None:
        val = int(num)
        if 2020 <= val <= 2035:
            return str(val)
        # Could be quarter number 1-4
        if 1 <= val <= 4:
            return f"{val} квартал"
    return text


# ============================================================
# DEPUTY MINISTER MAPPING BY SSP INDEX
# ============================================================

def get_primary_ssp_index(value):
    """
    Extracts the main SSP index from the 'Головний виконавець' field.
    Examples:
    - '20' -> '20'
    - '20. Департамент...' -> '20'
    - '20; 30' -> '20'
    """
    text = clean(value)
    if not text:
        return ""
    first_executor = split_first_executor(text)
    match = re.search(r"\d+", first_executor)
    return match.group(0) if match else ""


def get_deputy_minister_by_ssp(value):
    """Returns the Deputy Minister assigned to the main SSP index."""
    ssp_index = get_primary_ssp_index(value)
    deputy = clean(DEPUTY_MINISTER_BY_SSP.get(ssp_index, ""))
    return deputy if deputy else "Не визначено"


# ============================================================
# EXCEL LOGIC FOR PROGRESS (from М_заходи sheet)
# ============================================================

def compute_measure_progress(fact_value, plan_value, unit, execution_statuses=None):
    """
    Applies the progress logic from М_заходи Excel sheet:
    
    1. If any quarter has 'Втратило актуальність' → status = 'Втратило актуальність', progress = N/A
    2. If plan = 'х'/'x' or fact is empty → progress = 'х' (not yet due)
    3. If unit = 'так/ні':
       - fact == plan == 'так' → 100%
       - fact == 'ні' → 0%
       - else → 0%
    4. Numeric: (fact / plan) * 100, capped at 150%
    
    Status determination:
    > 99.99% → 'Виконано'
    74.99% < x < 100% → 'Частково виконано'
    = 0% → 'Не виконано'
    else → 'Не виконано'
    """
    # Check for obsolete status
    if execution_statuses:
        for s in execution_statuses:
            s_clean = clean(s).lower()
            if "втратило" in s_clean or "актуальн" in s_clean:
                return None, "Втратило актуальність"

    fact_clean = clean(fact_value)
    plan_clean = clean(plan_value)
    unit_clean = clean(unit).lower()

    # Check if plan is 'х' (not applicable)
    plan_is_x = plan_clean.lower() in ["x", "х", "—", "-", ""]
    fact_is_empty = fact_clean in ["", "—", "-"]

    if plan_is_x or fact_is_empty:
        return None, "Не настав час"

    # так/ні logic
    if "так" in unit_clean or "ні" in unit_clean or fact_clean.lower() in ["так", "ні", "yes", "no"]:
        fact_norm = normalize_text(fact_clean)
        plan_norm = normalize_text(plan_clean)
        if fact_norm == plan_norm and plan_norm in ["так", "yes"]:
            return 100.0, "Виконано"
        elif fact_norm in ["так", "yes"]:
            return 100.0, "Виконано"
        else:
            return 0.0, "Не виконано"

    # Numeric
    fact_num = to_number(fact_clean)
    plan_num = to_number(plan_clean)

    if fact_num is not None and plan_num is not None and plan_num != 0:
        pct = round(min((fact_num / plan_num) * 100, 150), 1)
        if pct > 99.99:
            status = "Виконано"
        elif pct > 74.99:
            status = "Частково виконано"
        else:
            status = "Не виконано"
        return pct, status

    return None, "Не настав час"


def gauge_chart(value, title):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": "%"},
        title={"text": title},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#1d4ed8"},
            "steps": [
                {"range": [0, 35], "color": "#fee2e2"},
                {"range": [35, 75], "color": "#fef3c7"},
                {"range": [75, 100], "color": "#dcfce7"},
            ],
            "threshold": {
                "line": {"color": "#111827", "width": 4},
                "thickness": 0.75,
                "value": value
            }
        }
    ))
    fig.update_layout(height=320, margin=dict(l=20, r=20, t=60, b=20))
    return fig


def format_amount_bln(value):
    text = clean(value)
    number = to_number(text)
    if number is None:
        return text if text else "—"
    return f"{number:g} млрд грн"


def looks_like_kpkvk(value):
    text = clean(value)
    return bool(re.search(r"\b\d{7}\b", text))


def extract_kpkvk_code(row):
    candidates = [
        row.get("kpkvk_code_raw", ""),
        row.get("finance_y", ""),
        row.get("finance_z", ""),
        row.get("finance_aa", ""),
        row.get("finance_ab", ""),
        row.get("finance_ac", ""),
        row.get("finance_ad", ""),
        row.get("finance_ae", ""),
        row.get("finance_af", ""),
    ]
    for value in candidates:
        match = re.search(r"\b\d{7}\b", clean(value))
        if match:
            return match.group(0)
    return ""


def first_money_value(values):
    """
    Повертає саме суму фінансування, а не код КПКВК.
    Тому 7-значні значення, роки й порожні значення ігноруються.
    """
    for value in values:
        text = clean(value)
        if not text or looks_like_kpkvk(text):
            continue

        number = to_number(text)
        if number is None:
            continue

        if 2020 <= number <= 2035 and re.fullmatch(r"\d{4}", str(int(number))):
            continue

        return text

    return ""


def get_measure_label(row):
    return f"{row['code']} — {row['name']}"


def get_goal_label(row):
    return f"{row['code']} — {row['name']}"


def get_task_label(row):
    return f"{row['code']} — {row['name']}"


def get_quarter_css(approval):
    if approval == "Погоджено":
        return "q-approved"
    if approval == "Очікує погодження":
        return "q-waiting"
    if approval == "Повернуто на доопрацювання":
        return "q-returned"
    return "q-empty"


def financing_html(row, kpkvk_reference=None):
    kpkvk_reference = kpkvk_reference or {}

    finance_values = [
        row.get("finance_y", ""),
        row.get("finance_z", ""),
        row.get("finance_aa", ""),
        row.get("finance_ab", ""),
        row.get("finance_ac", ""),
        row.get("finance_ad", ""),
        row.get("finance_ae", ""),
        row.get("finance_af", ""),
    ]
    finance_values_clean = [clean(v) for v in finance_values]

    kpkvk_code = extract_kpkvk_code(row)
    kpkvk_name = clean(kpkvk_reference.get(kpkvk_code, ""))

    if all(v == "" for v in finance_values_clean) and not kpkvk_code:
        return '<div class="passport-value">Відсутнє</div>'

    y, z, aa, ab, ac, ad, ae, af = finance_values_clean
    joined = " ".join(finance_values_clean).lower()

    state_candidates = [y, z, aa, ab, ac, clean(row.get("kpkvk_code_raw", ""))]
    other_candidates = [ad, ae, af]

    has_state_budget = (
        bool(kpkvk_code) or
        (
            any(v for v in state_candidates) and
            ("держ" in joined or "кпквк" in joined or any(v for v in [z, aa, ab, ac]))
        )
    )
    has_other = any(v for v in other_candidates) or "інш" in joined

    if not has_state_budget and not has_other:
        simple_text = "; ".join([v for v in finance_values_clean if v])
        return f'<div class="finance-single"><div class="finance-source">Фінансування</div><div class="finance-kpkvk">{escape(simple_text)}</div></div>'

    state_amount_2026 = first_money_value([aa, ab, ac, z, y])
    other_amount_2026 = first_money_value([ae, af, ad])

    state_html_inner = ""
    other_html_inner = ""

    if has_state_budget:
        amount_str = format_amount_bln(state_amount_2026)

        kpkvk_title_html = ""
        if kpkvk_name:
            kpkvk_title_html = f'<div class="finance-amount">{escape(kpkvk_name)}</div>'

        state_html_inner = f"""
        <div class="finance-block">
            <div class="finance-source">&#127968; Державний бюджет</div>
            <div class="finance-kpkvk">КПКВК&nbsp;{escape(kpkvk_code) if kpkvk_code else "—"}</div>
            {kpkvk_title_html}
            <div class="finance-amount">2026:&nbsp;{escape(amount_str)}</div>
        </div>"""

    if has_other:
        source = ""
        for item in [ad, y, z]:
            if item and "держ" not in item.lower() and "кпквк" not in item.lower() and not looks_like_kpkvk(item):
                source = item
                break
        if not source:
            source = "Інші джерела"
        amount_str = format_amount_bln(other_amount_2026)
        other_html_inner = f"""
        <div class="finance-block-alt">
            <div class="finance-source">&#128181; Інші джерела</div>
            <div class="finance-kpkvk">{escape(source)}</div>
            <div class="finance-amount">2026:&nbsp;{escape(amount_str)}</div>
        </div>"""

    if has_state_budget and has_other:
        return f'<div class="finance-grid">{state_html_inner.strip()}{other_html_inner.strip()}</div>'
    return (state_html_inner or other_html_inner).strip() or '<div class="passport-value">Відсутнє</div>'



# ============================================================
# DATA LOADING
# ============================================================

def load_strat_matrix():
    """ЄДИНЕ джерело — core.strategic_data (правка К1)."""
    return core_load_strat_matrix()


@st.cache_data
def load_kpkvk_reference():
    """
    Підтягує довідник КПКВК з окремої вкладки 'КПКВК'.
    Очікувана логіка: у вкладці є 7-значний код КПКВК і поруч/далі назва.
    """
    try:
        ref_df = read_excel_sheet(FILE_PATH, "КПКВК")
    except Exception as exc:
        log_exception("load_kpkvk_mapping", exc)
        st.warning("Не вдалося завантажити довідник КПКВК. Картка заходу може бути неповною.")
        return {}

    mapping = {}
    for _, row in ref_df.iterrows():
        row_values = [clean(v) for v in row.tolist()]
        for idx, cell in enumerate(row_values):
            match = re.search(r"\b\d{7}\b", cell)
            if not match:
                continue

            code = match.group(0)
            name = ""

            for candidate in row_values[idx + 1:]:
                if candidate and not re.fullmatch(r"\d{7}", candidate) and not re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", candidate):
                    name = candidate
                    break

            if not name:
                for candidate in reversed(row_values[:idx]):
                    if candidate and not re.fullmatch(r"\d{7}", candidate) and not re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", candidate):
                        name = candidate
                        break

            if code and name:
                mapping[code] = name

    return mapping



def load_requests():
    """ЄДИНЕ джерело — core.monitoring_data (правки К2, П2).
    Картка заходу працює з поданнями ЗАХОДІВ."""
    df = monitoring_data.measures_only(monitoring_data.load_monitoring_requests())
    if not df.empty and "submitted_at" in df.columns:
        df = df.sort_values("submitted_at", ascending=False)
    return df


# ============================================================
# HEADER
# ============================================================

render_html('<div class="ua-line"></div>')

render_html(
    f"""
    <div class="top-grid">
        <div class="hero-card">
            <div class="hero-kicker">Паспорт стратегічного заходу</div>
            <div class="hero-title">Картка заходу</div>
            <div class="hero-subtitle">
                Сторінка відображає повний профіль окремого заходу: його місце у Стратегічному плані,
                планові показники, результати квартального моніторингу, інформацію щодо ризиків та
                історію подання відомостей.
            </div>
        </div>
        <div class="ministry-card">
            <div class="ministry-title">&#127482;&#127462; Міністерство економіки, довкілля та сільського господарства України</div>
            <div class="ministry-line">Внутрішня демо-система моніторингу стратегічного плану.</div>
            <div class="status-pill-wrap">
                <div class="status-pill">&#9679; Режим: картка заходу</div>
                <div class="status-pill">&#9679; Джерело: Excel + Supabase</div>
                <div class="status-pill">&#9679; Оновлено: {datetime.now().strftime("%d.%m.%Y %H:%M")}</div>
            </div>
        </div>
    </div>
    """
)


# ============================================================
# MAIN DATA
# ============================================================

df = load_strat_matrix()
kpkvk_reference = load_kpkvk_reference()
requests_df = load_requests()

goals = df[df["object_type"] == "goal"].copy()
tasks = df[df["object_type"] == "task"].copy()
measures = df[df["object_type"] == "measure"].copy()

# Пункт 1 нового ТЗ: ролі, звужені до власного ССП, за замовчуванням
# бачать (і можуть обрати в переліку заходів) тільки заходи свого ССП.
# Стратегічні цілі/завдання НЕ звужуємо тут напряму (див. app.py/Dashboard —
# "Головний виконавець" для рядків цілей/завдань в Excel успадкований
# через об'єднані комірки і не є надійним індикатором власника); якщо
# ціль/завдання після цього не містить жодного видимого заходу — це
# вже коректно обробляють подальші перевірки "заходів не знайдено".
measures = filter_actions_for_user(measures, current_user, page_key="Картка заходу")
requests_df = filter_requests_for_user(
    requests_df, current_user, ssp_columns=["department"], page_key="Картка заходу"
)

if measures.empty:
    st.warning("Заходів у стратегічній матриці не знайдено.")
    st.stop()

measures["goal_code"] = measures["code"].apply(get_goal_code)
measures["task_code"] = measures["code"].apply(get_task_code)
tasks["goal_code"] = tasks["code"].apply(get_goal_code)


# ============================================================
# FILTERS
# ============================================================

render_html(
    """
    <div class="card">
        <div class="card-title">Вибір заходу</div>
        <div class="card-subtitle">
            Спочатку оберіть стратегічну ціль, потім завдання, після цього — конкретний захід.
            Пошук за ключовими словами додатково звужує перелік заходів.
        </div>
        <div class="filter-panel">
    """
)

f1, f2, f3, f4, f5 = st.columns([1.1, 1.1, 1.5, 1.05, 1.05])

goal_options = ["Усі стратегічні цілі"] + [
    get_goal_label(row) for _, row in goals.iterrows()
]

with f1:
    selected_goal_label = st.selectbox("Стратегічна ціль", goal_options, index=0)

if selected_goal_label == "Усі стратегічні цілі":
    selected_goal_code = ""
    filtered_tasks = tasks.copy()
    filtered_measures_by_goal = measures.copy()
else:
    selected_goal_code = selected_goal_label.split("—")[0].strip()
    filtered_tasks = tasks[tasks["goal_code"] == selected_goal_code].copy()
    filtered_measures_by_goal = measures[measures["goal_code"] == selected_goal_code].copy()

task_options = ["Усі завдання"] + [
    get_task_label(row) for _, row in filtered_tasks.iterrows()
]

with f2:
    selected_task_label = st.selectbox("Завдання", task_options, index=0)

if selected_task_label == "Усі завдання":
    filtered_measures_by_task = filtered_measures_by_goal.copy()
else:
    selected_task_code_filter = selected_task_label.split("—")[0].strip()
    filtered_measures_by_task = filtered_measures_by_goal[
        filtered_measures_by_goal["task_code"] == selected_task_code_filter
    ].copy()

with f4:
    keyword = st.text_input("За ключовими словами", value="", placeholder="Введіть слово або код")

with f5:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    render_scope_toggle("Картка заходу", current_user)

if clean(keyword):
    kw = clean(keyword).lower()
    filtered_measures_by_task = filtered_measures_by_task[
        filtered_measures_by_task["code"].astype(str).str.lower().str.contains(kw, na=False) |
        filtered_measures_by_task["name"].astype(str).str.lower().str.contains(kw, na=False) |
        filtered_measures_by_task["indicator"].astype(str).str.lower().str.contains(kw, na=False) |
        filtered_measures_by_task["department"].astype(str).str.lower().str.contains(kw, na=False)
    ].copy()

if filtered_measures_by_task.empty:
    render_html("</div></div>")
    st.warning("За обраними фільтрами заходів не знайдено.")
    st.stop()

measure_options = [
    get_measure_label(row)
    for _, row in filtered_measures_by_task.iterrows()
]

with f3:
    selected_option = st.selectbox("Захід", measure_options, index=0)

render_html("</div></div>")

selected_code = selected_option.split("—")[0].strip()

selected_measure = measures[
    measures["code"].astype(str).str.strip() == selected_code
].iloc[0]

goal_code = get_goal_code(selected_code)
task_code = get_task_code(selected_code)

goal_row = df[
    (df["object_type"] == "goal") &
    (df["code"].astype(str).str.strip() == goal_code)
]

task_row = df[
    (df["object_type"] == "task") &
    (df["code"].astype(str).str.strip() == task_code)
]

goal_name = clean(goal_row.iloc[0]["name"]) if not goal_row.empty else ""
task_name = clean(task_row.iloc[0]["name"]) if not task_row.empty else ""

goal_name = strip_leading_code(goal_name, goal_code)
task_name = strip_leading_code(task_name, task_code)


# ============================================================
# REQUEST DATA
# ============================================================

measure_requests = pd.DataFrame()

if not requests_df.empty and "strat_code" in requests_df.columns:
    measure_requests = requests_df[
        requests_df["strat_code"].astype(str).str.strip() == selected_code
    ].copy()

# ── Джерело даних: підтверджені / оперативна оцінка (правка №6) ──
card_data_mode = st.radio(
    "Джерело даних для оцінки прогресу",
    operational.MODE_OPTIONS,
    horizontal=True,
    key="card_data_source_mode",
    help=operational.MODE_HELP,
)

card_auto_list = []
if card_data_mode == operational.MODE_OPERATIONAL and not measure_requests.empty:
    _tgt_map = {}
    for _yr in ("2026", "2027", "2028"):
        _tv = selected_measure.get(f"target_{_yr}", "")
        _tgt_map[(selected_code, _yr)] = "" if _tv is None else str(_tv)
    measure_requests, card_auto_list = operational.apply_operational_mode(measure_requests, _tgt_map)

# Ручне закриття цього заходу (офіційне, показується завжди)
_card_closeouts = load_manual_closeouts()
card_closed_periods = sorted(
    f"{q} кв. {y}" for (c, y, q) in _card_closeouts if c == selected_code
)

has_monitoring = not measure_requests.empty

approved_requests = pd.DataFrame()

if has_monitoring and "approval_status" in measure_requests.columns:
    approved_requests = measure_requests[
        measure_requests["approval_status"].astype(str) == "Погоджено"
    ].copy()

latest_request = None

if has_monitoring and "submitted_at" in measure_requests.columns:
    latest_request = measure_requests.sort_values("submitted_at", ascending=False).iloc[0]
elif has_monitoring:
    latest_request = measure_requests.iloc[0]

latest_approved = None

if not approved_requests.empty and "submitted_at" in approved_requests.columns:
    latest_approved = approved_requests.sort_values("submitted_at", ascending=False).iloc[0]
elif not approved_requests.empty:
    latest_approved = approved_requests.iloc[0]

# Build execution_statuses from approved requests across quarters
execution_statuses = []
if has_monitoring and "status" in measure_requests.columns:
    execution_statuses = measure_requests["status"].dropna().tolist()

target_value = selected_measure.get("target_2026", "")
latest_actual = latest_approved.get("numeric_value", "") if latest_approved is not None else ""
unit_value = clean(selected_measure.get("unit", ""))

progress_percent, exec_status = compute_measure_progress(
    latest_actual, target_value, unit_value, execution_statuses
)

if progress_percent is None:
    display_progress = 0.0
else:
    display_progress = float(progress_percent)

total_requests = len(measure_requests)
approved_count = len(measure_requests[measure_requests["approval_status"] == "Погоджено"]) if has_monitoring and "approval_status" in measure_requests.columns else 0
returned_count = len(measure_requests[measure_requests["approval_status"] == "Повернуто на доопрацювання"]) if has_monitoring and "approval_status" in measure_requests.columns else 0
waiting_count = len(measure_requests[measure_requests["approval_status"] == "Очікує погодження"]) if has_monitoring and "approval_status" in measure_requests.columns else 0

co_executor_first = split_first_executor(selected_measure.get("co_executor", ""))
deputy_minister = get_deputy_minister_by_ssp(selected_measure.get("department", ""))

# Read start/end period correctly
start_period_raw = selected_measure.get("start_period", "")
end_period_raw = selected_measure.get("end_period", "")
start_period_display = get_period_label(start_period_raw)
end_period_display = get_period_label(end_period_raw)


# ============================================================
# PASSPORT
# ============================================================

render_html('<div class="card"><div class="card-title">Паспорт заходу</div>')

render_html(
    f"""
    <div class="badge-wrap">
        <div class="badge">Код: {display_value(selected_code)}</div>
        <div class="badge">Департамент: {display_value(selected_measure.get("department", ""))}</div>
        <div class="badge">Моніторингових заявок: {total_requests}</div>
    </div>
    <div style="font-size:24px;font-weight:900;color:#0f172a;line-height:1.25;margin-top:10px;margin-bottom:16px;">
        {display_value(selected_measure.get("name", ""))}
    </div>
    """
)

# Build planovi pokaznyky chips
t26 = clean(selected_measure.get("target_2026", ""))
t27 = clean(selected_measure.get("target_2027", ""))
t28 = clean(selected_measure.get("target_2028", ""))

plan_chips_html = '<div class="plan-chips">'
if t26:
    plan_chips_html += f'<div class="plan-chip"><div class="plan-chip-year">2026</div><div class="plan-chip-val">{escape(t26)}</div></div>'
if t27:
    plan_chips_html += f'<div class="plan-chip"><div class="plan-chip-year">2027</div><div class="plan-chip-val">{escape(t27)}</div></div>'
if t28 and t28.lower() not in ["x", "х"]:
    plan_chips_html += f'<div class="plan-chip"><div class="plan-chip-year">2028</div><div class="plan-chip-val">{escape(t28)}</div></div>'
plan_chips_html += '</div>'

render_html(f"""
<div class="passport-grid">
    <div class="passport-cell col-4">
        <div class="passport-label">Стратегічна ціль</div>
        <div class="passport-value">{display_value(goal_code)}</div>
        <div class="passport-muted">{display_value(goal_name)}</div>
    </div>
    <div class="passport-cell col-4">
        <div class="passport-label">Завдання</div>
        <div class="passport-value">{display_value(task_code)}</div>
        <div class="passport-muted">{display_value(task_name)}</div>
    </div>
    <div class="passport-cell col-4">
        <div class="split-box">
            <div>
                <div class="passport-label">Головний виконавець</div>
                <div class="passport-value">{display_value(selected_measure.get("department", ""))}</div>
            </div>
            <div>
                <div class="passport-label">Співвиконавець</div>
                <div class="passport-value">{display_value(co_executor_first)}</div>
            </div>
        </div>
    </div>

    <div class="passport-cell col-4">
        <div class="passport-label">Замміністра</div>
        <div class="passport-value">{display_value(deputy_minister)}</div>
    </div>

    <div class="passport-cell col-2">
        <div class="passport-label">Тип продукту</div>
        <div class="passport-value">{display_value(selected_measure.get("product_type", ""))}</div>
    </div>

    <div class="passport-cell col-2">
        <div class="passport-label">Початок виконання</div>
        <div class="passport-value">{escape(start_period_display)}</div>
    </div>

    <div class="passport-cell col-2">
        <div class="passport-label">Кінець виконання</div>
        <div class="passport-value">{escape(end_period_display)}</div>
    </div>

    <div class="passport-cell col-2">
        <div class="passport-label">Одиниця виміру</div>
        <div class="passport-value">{display_value(selected_measure.get("unit", ""))}</div>
    </div>

    <div class="passport-cell col-8">
        <div class="passport-label">Індикатор</div>
        <div class="passport-value">{display_value(selected_measure.get("indicator", ""))}</div>
    </div>

    <div class="passport-cell col-4">
        <div class="passport-label">Планові показники</div>
        {plan_chips_html}
    </div>

    <div class="passport-cell col-12">
        <div class="passport-label">Фінансування</div>
        {financing_html(selected_measure, kpkvk_reference)}
    </div>
</div>
""")

render_html('</div>')


# ============================================================
# METRICS
# ============================================================

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("План 2026", clean(selected_measure.get("target_2026", "")) or "—")
k2.metric("Останнє фактичне значення, подане ССП", clean(latest_actual) or "—")

if exec_status == "Втратило актуальність":
    k3.metric("Прогрес", "в/а")
elif exec_status == "Не настав час":
    k3.metric("Прогрес", "—")
else:
    k3.metric("Прогрес", f"{round(display_progress, 1)}%")

k4.metric("Погоджено", approved_count)
k5.metric("Очікує", waiting_count)

# ── Індивідуальні позначки цього заходу ──────────────────────
if card_auto_list:
    _a = card_auto_list[0]
    st.markdown(
        f"""
        <div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:12px;
             padding:12px 16px;margin:10px 0;color:#78350f;font-weight:700;">
            ⚡ За цим заходом є НЕПІДТВЕРДЖЕНІ дані, які система зарахувала автоматично:
            подане значення <b>{_a['value']}</b> за {_a['quarter']} кв. {_a['year']} відповідає
            річному цільовому орієнтиру (<b>{_a['target']}</b>) або краще. Заявка перебуває на
            етапі погодження після координатора («{_a['approval_status']}»); показники нижче
            розраховано в режимі оперативної оцінки і будуть перераховані (або залишаться без
            змін) після фінального підтвердження.
        </div>
        """,
        unsafe_allow_html=True,
    )
elif card_data_mode == operational.MODE_OPERATIONAL and "_operational" in measure_requests.columns         and bool(measure_requests["_operational"].any()):
    st.markdown(
        """
        <div style="background:#eff6ff;border:1px solid #93c5fd;border-radius:12px;
             padding:12px 16px;margin:10px 0;color:#1e3a8a;font-weight:700;">
            ⚡ Оперативна оцінка: враховано подання, що перебуває на етапі погодження після
            координатора (подане значення нижче річного орієнтира, тому авто-зарахування
            як «Виконано» не застосовано).
        </div>
        """,
        unsafe_allow_html=True,
    )

if card_closed_periods:
    st.markdown(
        f"""
        <div style="background:#ede9fe;border:1px solid #8b5cf6;border-radius:12px;
             padding:12px 16px;margin:10px 0;color:#5b21b6;font-weight:700;">
            🔒 Захід закрито адміністратором вручну (підтверджено супер-адміном) за періоди:
            {", ".join(card_closed_periods)}. Ці періоди враховуються як виконані незалежно
            від подань ССП; підстава та посилання на НПА — у розділі закриттів сторінки
            «Адміністрування».
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# ANALYTICAL CONCLUSION
# ============================================================

render_html('<div class="card"><div class="card-title">Аналітичний висновок</div>')

if exec_status == "Втратило актуальність":
    conclusion = (
        "Захід втратив актуальність відповідно до поданих моніторингових відомостей. "
        "Прогрес за цим заходом не розраховується."
    )
    badge_class = "badge badge-gray"
elif exec_status == "Не настав час":
    conclusion = (
        "За цим заходом ще не зафіксовано погоджених квартальних даних. "
        "Поточна оцінка прогресу базується на наявності або відсутності поданих ССП відомостей."
    )
    badge_class = "badge badge-gray"
elif display_progress >= 100:
    conclusion = (
        "Захід виконано відповідно до встановленого планового показника. "
        "Фактичне значення досягає або перевищує цільовий орієнтир поточного року."
    )
    badge_class = "badge badge-green"
elif display_progress >= 75:
    conclusion = (
        "Захід виконано частково: досягнуто понад 75% від планового значення. "
        "Рекомендується моніторинг для забезпечення досягнення цільового показника."
    )
    badge_class = "badge badge-yellow"
elif display_progress > 0:
    conclusion = (
        "Поточний прогрес заходу є низьким або недостатньо підтвердженим погодженими даними. "
        "Доцільно перевірити актуальність поданих ССП відомостей і планове значення на відповідний рік."
    )
    badge_class = "badge badge-red"
else:
    conclusion = (
        "За цим заходом фактичних погоджених даних не подано або прогрес складає 0%. "
        "Необхідне термінове оновлення відомостей у системі."
    )
    badge_class = "badge badge-red"

progress_label = "—" if exec_status in ["Втратило актуальність", "Не настав час"] else f"{round(display_progress, 1)}%"

render_html(
    f"""
    <div class="badge-wrap">
        <div class="{badge_class}">Прогрес: {progress_label}</div>
        <div class="badge">Заявок: {total_requests}</div>
        <div class="badge">Погоджено: {approved_count}</div>
        <div class="badge">Повернень: {returned_count}</div>
        <div class="badge">Статус: {escape(exec_status)}</div>
    </div>
    <div style="color:#475569;font-size:14px;line-height:1.55;">{escape(conclusion)}</div>
    """
)

render_html('</div>')


# ============================================================
# VISUALIZATIONS
# ============================================================

view_mode_options = [
    "Огляд",
    "Індикатор прогресу",
    "Квартальна динаміка",
]

if can_view_submission_history:
    view_mode_options.append("Історія подання відомостей")

view_mode = st.selectbox(
    "Тип візуалізації",
    view_mode_options
)

if view_mode in ["Огляд", "Індикатор прогресу"]:
    render_html('<div class="card"><div class="card-title">Індикатор прогресу заходу</div>')

    c1, c2 = st.columns([1, 1])

    with c1:
        # Індикатор має бути завжди. Якщо даних немає або строк ще не настав —
        # показуємо 0%, а не приховуємо блок.
        st.plotly_chart(
            gauge_chart(display_progress, "Прогрес заходу"),
            use_container_width=True
        )

    with c2:
        st.markdown("**Метод оцінки (відповідно до логіки МіО):**")
        st.write(
            "Якщо будь-який квартал позначено як 'Втратило актуальність' — захід визнається таким, що втратив актуальність. "
            "Якщо план = 'х' або факт не подано — індикатор залишається на 0%, а статус показує, що строк ще не настав або дані не подано. "
            "Якщо одиниця виміру — 'так/ні': факт = 'так' → 100%, 'ні' → 0%. "
            "Числово: (факт ÷ план) × 100%, де >100% = Виконано, 75–100% = Частково, <75% = Не виконано."
        )

        st.progress(min(display_progress / 100, 1.0), text=f"Прогрес: {round(display_progress, 1)}%")

        status_class_map = {
            "Виконано": "progress-status-done",
            "Частково виконано": "progress-status-partial",
            "Не виконано": "progress-status-low",
            "Не настав час": "progress-status-na",
            "Втратило актуальність": "progress-status-obsolete",
        }
        badge_cls = status_class_map.get(exec_status, "progress-status-na")
        render_html(
            f'<div class="progress-status-badge {badge_cls}">&#9679;&nbsp;{escape(exec_status)}</div>'
        )

    render_html('</div>')

if view_mode in ["Огляд", "Квартальна динаміка"]:
    render_html(
        """
        <div class="card">
            <div class="card-title">Динаміка планових, звітних даних</div>
            <div class="card-subtitle">
                Відображає фактичні значення та динаміку прогресу за кожним кварталом поточного року.
            </div>
        """
    )

    quarters = ["I", "II", "III", "IV"]
    quarter_html = ['<div class="quarter-timeline">']

    line_labels = []
    line_facts = []
    line_plans = []

    plan_num_val = to_number(clean(selected_measure.get("target_2026", "")))

    for q in quarters:
        q_data = pd.DataFrame()
        if has_monitoring and "quarter" in measure_requests.columns:
            q_data = measure_requests[
                measure_requests["quarter"].astype(str) == q
            ].copy()

        if q_data.empty:
            css = "q-empty"
            value = "—"
            approval = "Не подано"
            status = ""
            submitted = ""
            fact_n = None
        else:
            if "submitted_at" in q_data.columns:
                latest_q = q_data.sort_values("submitted_at", ascending=False).iloc[0]
            else:
                latest_q = q_data.iloc[0]

            approval = clean(latest_q.get("approval_status", ""))
            value = clean(latest_q.get("numeric_value", ""))
            status = clean(latest_q.get("status", ""))
            submitted = clean(latest_q.get("submitted_at", ""))
            css = get_quarter_css(approval)
            fact_n = to_number(value)

        line_labels.append(f"{q} кв.")
        line_facts.append(fact_n)
        line_plans.append(plan_num_val)

        q_pct = 0
        if fact_n is not None and plan_num_val and plan_num_val > 0:
            q_pct = min(round((fact_n / plan_num_val) * 100), 100)

        bar_color_css = "#22c55e" if css == "q-approved" else (
            "#f59e0b" if css == "q-waiting" else (
                "#ef4444" if css == "q-returned" else "#cbd5e1"
            )
        )

        quarter_html.append(
            dedent(f"""
            <div class="quarter-card {css}">
                <div class="quarter-title">{q} квартал</div>
                <div class="quarter-value">{escape(value) if value and value != "—" else "—"}</div>
                <div class="quarter-bar-outer">
                    <div class="quarter-bar-inner" style="width:{q_pct}%;background:{bar_color_css};"></div>
                </div>
                <div class="quarter-plan">План 2026: {display_value(selected_measure.get("target_2026", ""))}</div>
                <div class="quarter-plan">Статус виконання: {escape(status) if status else "—"}</div>
                <div class="quarter-plan">Дата подання: {escape(submitted[:10]) if submitted else "—"}</div>
                <div class="quarter-status">{escape(approval) if approval else "Не подано"}</div>
            </div>
            """).strip()
        )

    quarter_html.append("</div>")
    render_html("".join(quarter_html))

    # Графік має бути завжди. Якщо фактичних даних немає — осі та легенда
    # залишаються, але фактична крива не заповнюється.
    fig = go.Figure()

    if plan_num_val is not None:
        fig.add_trace(go.Scatter(
            x=line_labels,
            y=[plan_num_val] * 4,
            mode="lines+markers",
            name="Плановий показник 2026",
            line=dict(width=2, dash="dash"),
            connectgaps=False,
        ))

    fig.add_trace(go.Scatter(
        x=line_labels,
        y=line_facts,
        mode="lines+markers",
        name="Фактичне значення",
        line=dict(width=3, shape="spline"),
        connectgaps=False,
    ))

    fig.update_layout(
        title="Динаміка планових і фактичних значень за кварталами",
        height=340,
        margin=dict(l=20, r=20, t=50, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(gridcolor="#e2e8f0", rangemode="tozero"),
        xaxis=dict(showgrid=False),
    )

    st.plotly_chart(fig, use_container_width=True)

    render_html('</div>')

if can_view_submission_history and view_mode in ["Огляд", "Історія подання відомостей"]:
    render_html('<div class="card"><div class="card-title">Історія подання відомостей</div>')

    if measure_requests.empty:
        st.info("Для цього заходу ще немає поданих відомостей.")
    else:
        history_df = measure_requests.rename(columns={
            "id": "ID",
            "year": "Рік",
            "quarter": "Квартал",
            "status": "Статус виконання",
            "approval_status": "Статус погодження",
            "numeric_value": "Фактичне значення",
            "responsible_person": "Відповідальна особа",
            "submitted_at": "Дата подання",
            "admin_comment": "Коментар адміністратора"
        })

        show_cols = [
            "ID", "Рік", "Квартал", "Статус виконання", "Статус погодження",
            "Фактичне значення", "Відповідальна особа", "Дата подання",
            "Коментар адміністратора"
        ]

        available = [c for c in show_cols if c in history_df.columns]
        st.dataframe(history_df[available], use_container_width=True, hide_index=True)

    render_html('</div>')


# ============================================================
# QUICK LINKS
# ============================================================

render_html('<div class="card"><div class="card-title">Швидкі переходи</div>')

if can_submit_monitoring_data:
    n1, spacer, n2 = st.columns([1, 1.5, 1], gap="large")

    with n1:
        st.page_link(
            "pages/1_Моніторинг_виконання.py",
            label="&#9998; Подати відомості",
            icon="🖊️"
        )

    with n2:
        st.page_link(
            "pages/2_Dashboard.py",
            label="&#128202; Dashboard",
            icon="📊"
        )
else:
    _, n2, _ = st.columns([1, 1, 1], gap="large")

    with n2:
        st.page_link(
            "pages/2_Dashboard.py",
            label="&#128202; Dashboard",
            icon="📊"
        )

render_html('</div>')


# ============================================================
# FOOTER
# ============================================================

render_footer()
