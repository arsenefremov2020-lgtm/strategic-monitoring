import re
import streamlit as st
import pandas as pd
import plotly.express as px
from core.db import get_supabase_client
from core.ui import load_css
from core.notifications import render_notifications_panel
from core.config import FILE_PATH, SHEET_NAME
from core.excel_loader import read_excel_sheet
from datetime import datetime, timezone
from core.page_setup import page_setup, render_footer
from core.strategic_data import load_strat_matrix as core_load_strat_matrix
from core import monitoring_data

from core.access import (
    filter_requests_for_user,
    get_user_allowed_ssp_indexes,
    user_has_all_ssp_access,
    is_admin_user,
    is_super_admin_user,
)
from core import approval_schemes as schemes
from core import notify_events
from core.closeouts import load_manual_closeouts
from html import escape as _esc

current_user = page_setup("Адміністрування", page_name="Адміністрування")
supabase = get_supabase_client()
st.markdown("""
<style>
header[data-testid="stHeader"] {
    background: transparent !important;
}
/* ─── BACKGROUND — м'який нейтральний ─── */
.stApp {
    background: linear-gradient(160deg, #f0f4f8 0%, #e8edf5 40%, #edf1f8 100%);
    min-height: 100vh;
}

.main .block-container {
    max-width: 1560px;
    padding-top: 1.2rem;
    position: relative;
}

/* ─── UA LINE ─── */
.ua-line {
    height: 5px;
    border-radius: 999px;
    background: linear-gradient(90deg, #005BBB 0%, #005BBB 50%, #FFD500 50%, #FFD500 100%);
    margin-bottom: 10px;
}

.ministry-label {
    text-align: right;
    color: #64748b;
    font-size: 12.5px;
    font-weight: 700;
    margin-bottom: 6px;
    letter-spacing: 0.02em;
}

/* ─── HEADER ─── */
.header-box {
    background: #ffffff;
    border: 1px solid #dde3ef;
    border-radius: 14px;
    padding: 20px 26px;
    margin-bottom: 14px;
    box-shadow: 0 2px 12px rgba(30,50,100,0.07);
}

.header-title {
    font-size: 28px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 5px;
    letter-spacing: -0.01em;
}

.header-subtitle {
    font-size: 14px;
    color: #64748b;
    line-height: 1.5;
}

.status-pill-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin-top: 11px;
}

.status-pill {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 999px;
    padding: 5px 11px;
    font-size: 12px;
    color: #475569;
    font-weight: 600;
}

/* ─── CARDS ─── */
.card {
    background: #ffffff;
    border: 1px solid #dde3ef;
    border-radius: 14px;
    padding: 18px 22px;
    margin: 12px 0;
    box-shadow: 0 2px 10px rgba(30,50,100,0.055);
}

.card-title {
    font-size: 17px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 5px;
}

.card-subtitle {
    color: #64748b;
    font-size: 13px;
    margin-bottom: 10px;
}

/* ─── FLOW BOX ─── */
.flow-box {
    background: #f8faff;
    border: 1px solid #c7d7f5;
    border-left: 4px solid #3b82f6;
    border-radius: 12px;
    padding: 13px 18px;
    margin: 12px 0;
}

.flow-title {
    font-weight: 800;
    color: #1e40af;
    margin-bottom: 9px;
    font-size: 12px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

.flow-steps {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
}

.flow-step {
    padding: 6px 12px;
    border-radius: 999px;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    color: #1d4ed8;
    font-size: 13px;
    font-weight: 600;
}

/* ─── BADGES ─── */
.badge-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin: 9px 0 13px 0;
}

.badge {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    color: #1d4ed8;
    border-radius: 999px;
    padding: 5px 11px;
    font-size: 12px;
    font-weight: 700;
}

.badge-green {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    color: #15803d;
}

.badge-yellow {
    background: #fefce8;
    border: 1px solid #fde68a;
    color: #92400e;
}

.badge-red {
    background: #fef2f2;
    border: 1px solid #fecaca;
    color: #b91c1c;
}

/* ─── ATTENTION GRID — 5 блоків в один рядок ─── */
.attention-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 10px;
    margin: 10px 0;
}

.attention-card {
    border-radius: 11px;
    padding: 13px 15px;
    border: 1px solid transparent;
}

.attention-title {
    font-size: 11px;
    font-weight: 800;
    margin-bottom: 5px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

.attention-value {
    font-size: 32px;
    font-weight: 950;
    line-height: 1.05;
}

.attention-note {
    font-size: 11px;
    margin-top: 4px;
    line-height: 1.3;
    opacity: 0.75;
}

.att-red    { background: #fef2f2; border-color: #fecaca; }
.att-red .attention-title  { color: #b91c1c; }
.att-red .attention-value  { color: #dc2626; }
.att-red .attention-note   { color: #991b1b; }

.att-yellow { background: #fefce8; border-color: #fde68a; }
.att-yellow .attention-title { color: #92400e; }
.att-yellow .attention-value { color: #d97706; }
.att-yellow .attention-note  { color: #78350f; }

.att-blue   { background: #eff6ff; border-color: #bfdbfe; }
.att-blue .attention-title { color: #1e40af; }
.att-blue .attention-value { color: #2563eb; }
.att-blue .attention-note  { color: #1e3a8a; }

.att-green  { background: #f0fdf4; border-color: #bbf7d0; }
.att-green .attention-title { color: #14532d; }
.att-green .attention-value { color: #16a34a; }
.att-green .attention-note  { color: #166534; }

/* ─── KPI CARDS ─── */
.admin-kpi-card {
    background: #f8fafc;
    border: 1px solid #dde3ef;
    border-radius: 11px;
    padding: 11px 13px;
    min-height: 82px;
}

.admin-kpi-label {
    color: #64748b;
    font-size: 11px;
    font-weight: 700;
    margin-bottom: 5px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.admin-kpi-value {
    color: #0f172a;
    font-size: 19px;
    font-weight: 850;
    line-height: 1.2;
    word-break: break-word;
}

/* ─── QUALITY GRID ─── */
.quality-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 8px;
    margin-bottom: 12px;
}

.quality-card {
    background: #f8fafc;
    border: 1px solid #dde3ef;
    border-radius: 10px;
    padding: 9px 11px;
    min-height: 64px;
}

.quality-good { border-left: 3px solid #22c55e; background: #f0fdf4; border-color: #bbf7d0; }
.quality-warn { border-left: 3px solid #f59e0b; background: #fefce8; border-color: #fde68a; }

.quality-label {
    color: #64748b;
    font-size: 10px;
    font-weight: 700;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.quality-value {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 13px;
    font-weight: 700;
    line-height: 1.25;
    color: #0f172a;
}

/* ─── CONCLUSION BOX ─── */
.quality-conclusion {
    background: #f8faff;
    border: 1px solid #c7d7f5;
    border-left: 4px solid #3b82f6;
    border-radius: 10px;
    padding: 11px 16px;
    margin-top: 4px;
    display: flex;
    align-items: center;
    gap: 12px;
}

.quality-conclusion-label {
    color: #64748b;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    min-width: 110px;
}

.quality-conclusion-value {
    font-size: 14px;
    font-weight: 800;
    color: #1e40af;
}

.quality-conclusion-pct {
    font-size: 13px;
    color: #475569;
    font-weight: 600;
    margin-left: auto;
}

/* ─── REVIEW BOX ─── */
.review-box {
    background: #f8fafc;
    border: 1px solid #dde3ef;
    border-radius: 11px;
    padding: 13px 16px;
    margin: 9px 0;
    color: #334155;
    font-size: 14px;
    line-height: 1.6;
}

.review-title {
    font-size: 14px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 7px;
}

/* ─── RESOLUTION ─── */
.resolution-box {
    background: #f8faff;
    border: 1px solid #c7d7f5;
    border-left: 5px solid #3b82f6;
    border-radius: 11px;
    padding: 16px 20px;
    margin: 10px 0;
}

.resolution-title {
    font-size: 13px;
    font-weight: 800;
    color: #1e40af;
    margin-bottom: 9px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.resolution-text {
    color: #1e293b;
    font-size: 14px;
    line-height: 1.7;
}

/* ─── DECISION BOX ─── */
.decision-box {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 10px;
    padding: 11px 15px;
    margin: 9px 0;
    color: #1d4ed8;
    font-size: 14px;
    font-weight: 700;
}

/* ─── PROGRESS / RISK BOXES ─── */
.progress-risk-box {
    background: #f8fafc;
    border: 1px solid #dde3ef;
    border-radius: 11px;
    padding: 13px 15px;
    min-height: 110px;
}

.progress-risk-label {
    color: #64748b;
    font-size: 11px;
    font-weight: 700;
    margin-bottom: 7px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.progress-risk-value {
    color: #1e293b;
    font-size: 14px;
    line-height: 1.6;
    white-space: pre-wrap;
}

/* ─── PERSON BOX ─── */
.person-box {
    background: #f0f7ff;
    border: 1px solid #bfdbfe;
    border-radius: 11px;
    padding: 14px 18px;
    display: flex;
    gap: 32px;
    flex-wrap: wrap;
    align-items: center;
}

.person-field {
    display: flex;
    flex-direction: column;
    gap: 3px;
}

.person-field-label {
    color: #64748b;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.person-field-value {
    color: #1d4ed8;
    font-size: 14px;
    font-weight: 700;
}

/* ─── COMMENT HEADER ─── */
.comment-header {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 9px;
    padding: 9px 14px;
    margin-bottom: 6px;
    color: #1d4ed8;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

/* ─── SELECTBOX / INPUTS ─── */
div[data-testid="stSelectbox"] > div > div,
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    background: #ffffff !important;
    border: 1.5px solid #c7d4e8 !important;
    color: #0f172a !important;
    border-radius: 9px !important;
}

div[data-testid="stSelectbox"] > div > div:hover,
div[data-testid="stTextInput"] input:hover,
div[data-testid="stTextArea"] textarea:hover {
    border-color: #3b82f6 !important;
}

div[data-testid="stSelectbox"] label,
div[data-testid="stTextInput"] label,
div[data-testid="stTextArea"] label {
    color: #475569 !important;
    font-size: 13px !important;
    font-weight: 600 !important;
}

/* Radio */
div[data-testid="stRadio"] label {
    color: #334155 !important;
    font-size: 14px !important;
}

div[data-testid="stRadio"] > div {
    background: #f8fafc;
    border: 1.5px solid #dde3ef;
    border-radius: 11px;
    padding: 11px 15px;
}

/* Checkbox */
div[data-testid="stCheckbox"] label {
    color: #475569 !important;
}

/* Tabs */
button[data-baseweb="tab"] {
    color: #64748b !important;
    background: transparent !important;
    font-weight: 600 !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #1d4ed8 !important;
    border-bottom: 2px solid #3b82f6 !important;
}

/* Metric widgets */
div[data-testid="stMetric"] {
    background: #f8fafc;
    border: 1px solid #dde3ef;
    border-radius: 11px;
    padding: 11px 13px;
}

div[data-testid="stMetric"] label {
    color: #64748b !important;
}

div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: #0f172a !important;
}

/* Buttons */
div.stButton > button {
    border-radius: 9px;
    padding: 9px 16px;
    font-weight: 700;
    background: #eff6ff;
    border: 1.5px solid #bfdbfe;
    color: #1d4ed8;
    transition: all 0.15s;
}

div.stButton > button:hover {
    background: #dbeafe;
    border-color: #93c5fd;
}

div[data-testid="stFormSubmitButton"] button {
    border-radius: 11px;
    padding: 12px 18px;
    font-weight: 900;
    background: linear-gradient(135deg, #1d4ed8, #2563eb);
    border: none;
    color: white;
    box-shadow: 0 3px 12px rgba(37,99,235,0.35);
    transition: all 0.15s;
}

div[data-testid="stFormSubmitButton"] button:hover {
    background: linear-gradient(135deg, #2563eb, #3b82f6);
    box-shadow: 0 5px 18px rgba(37,99,235,0.5);
}

/* Expander */
div[data-testid="stExpander"] {
    background: #f8fafc;
    border: 1px solid #dde3ef;
    border-radius: 11px;
}

div[data-testid="stExpander"] summary {
    color: #1d4ed8 !important;
    font-weight: 700;
}

/* Dataframe */
div[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
}

/* Alerts */
div[data-testid="stWarning"] {
    background: #fefce8;
    border: 1px solid #fde68a;
    border-radius: 9px;
    color: #92400e;
}

div[data-testid="stInfo"] {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 9px;
    color: #1e40af;
}

div[data-testid="stSuccess"] {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 9px;
    color: #14532d;
}

div[data-testid="stCaptionContainer"] {
    color: #64748b !important;
}

/* Progress bar */
div[data-testid="stProgressBar"] > div {
    background: #e2e8f0;
    border-radius: 999px;
}

div[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, #2563eb, #06b6d4);
    border-radius: 999px;
}

/* Footer */
.footer {
    text-align: center;
    color: #94a3b8;
    font-size: 12px;
    margin-top: 48px;
    padding: 18px 0 10px 0;
    border-top: 1px solid #e2e8f0;
}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def clean(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value)


def has_value(value):
    return clean(value).strip() != ""


def to_datetime(value):
    text = clean(value).strip()
    if not text:
        return None
    try:
        dt = pd.to_datetime(text, errors="coerce", utc=True)
        if pd.isna(dt):
            return None
        return dt.to_pydatetime()
    except Exception:
        return None


def days_waiting(value):
    dt = to_datetime(value)
    if not dt:
        return None
    return (datetime.now(timezone.utc) - dt).days


def split_ssp_values(value):
    text = clean(value).strip()
    if not text:
        return []
    return re.findall(r"\d+", text)


def admin_kpi_card(label, value):
    value = "" if value is None else str(value)
    st.markdown(
        f'<div class="admin-kpi-card">'
        f'<div class="admin-kpi-label">{label}</div>'
        f'<div class="admin-kpi-value">{value}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


def attention_card(title, value, note, css_class):
    st.markdown(
        f'<div class="attention-card {css_class}">'
        f'<div class="attention-title">{title}</div>'
        f'<div class="attention-value">{value}</div>'
        f'<div class="attention-note">{note}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


# ──────────────────────────────────────────────
# DATA LOADING
# ──────────────────────────────────────────────

def load_strat_matrix():
    """ЄДИНЕ джерело — core.strategic_data (правка К1)."""
    return core_load_strat_matrix()


def load_requests():
    """ЄДИНЕ джерело — core.monitoring_data (правки К2, П2)."""
    df = monitoring_data.load_monitoring_requests()
    if not df.empty and "submitted_at" in df.columns:
        df = df.sort_values("submitted_at", ascending=False)
    return df


def load_logs(request_id):
    resp = (
        supabase.table("monitoring_logs")
        .select("*")
        .eq("request_id", int(request_id))
        .order("changed_at", desc=True)
        .execute()
    )
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()



def _actor_identity(role_label):
    """Повний підпис дії для журналу: роль + ПІБ + email поточного користувача."""
    try:
        name = str((current_user or {}).get("full_name", "")).strip()
        email = str((current_user or {}).get("email", "")).strip()
    except Exception:
        name, email = "", ""
    parts = [p for p in (role_label, name, f"<{email}>" if email else "") if p]
    return " · ".join(parts) if parts else role_label

def write_log(request_id, action, old_status, new_status, admin_comment):
    supabase.table("monitoring_logs").insert({
        "request_id":    int(request_id),
        "action":        action,
        "old_status":    old_status,
        "new_status":    new_status,
        "admin_comment": admin_comment,
        # Аудит: конкретний користувач, а не лише роль
        "changed_by":    _actor_identity("Адміністратор")
    }).execute()


# ──────────────────────────────────────────────
# QUALITY ASSESSMENT
# ──────────────────────────────────────────────

def quality_assessment(row):
    checks = []
    score = 0

    fields = [
        ("numeric_value",      "Фактичне значення"),
        ("progress_text",      "Опис прогресу"),
        ("responsible_person", "Відповідальна особа"),
        ("phone",              "Телефон"),
        ("email",              "Email"),
        ("status",             "Статус заходу"),
        ("start_date",         "Початок виконання"),
        ("end_date",           "Кінець виконання"),
    ]

    for field, label in fields:
        ok = has_value(row.get(field, ""))
        checks.append((label, "Заповнено" if ok else "Відсутнє", ok))
        if ok:
            score += 1

    # Ризики — інверсія: добре якщо немає
    has_risks = has_value(row.get("risks", ""))
    checks.append(("Ризики / відхилення", "Є запис ⚠" if has_risks else "Не зазначено", not has_risks))
    if not has_risks:
        score += 1

    total_fields = 9
    pct = round(score / total_fields * 100, 1)

    if score >= 8 and not has_risks:
        recommendation = "Можна направляти на підпис"
        badge = "badge-green"
    elif score >= 6:
        recommendation = "Потребує перевірки"
        badge = "badge-yellow"
    else:
        recommendation = "Краще повернути на доопрацювання"
        badge = "badge-red"

    return checks, recommendation, badge, score, total_fields, pct


# ──────────────────────────────────────────────
# СТАТУС — автоматична перевірка відповідності
# Пороги за єдиною шкалою моделі МіО: <75% → Не виконано |
# 75–99% → Частково виконано | ≥100% → Виконано
# ──────────────────────────────────────────────

def compute_execution_pct(fact_str, plan_str):
    """Повертає (float_pct або None, fact_float або None, plan_float або None)."""
    try:
        f = float(str(fact_str).replace(",", ".").strip())
        p = float(str(plan_str).replace(",", ".").strip())
        if p == 0:
            return None, f, p
        return round(f / p * 100, 1), f, p
    except Exception:
        return None, None, None


def expected_status(exec_pct):
    """Повертає очікуваний статус за відсотком виконання."""
    if exec_pct is None:
        return None
    if exec_pct >= 100:
        return "Виконано"
    if exec_pct >= 75:
        return "Частково виконано"
    return "Не виконано"


def analyze_request(row, plan_val_str):
    """
    Повний аналіз заявки. Повертає dict з усіма знахідками.
    plan_val_str — рядок планового значення з стратматриці.
    """
    fact_str   = clean(row.get("numeric_value", ""))
    status     = clean(row.get("status", ""))
    progress   = clean(row.get("progress_text", ""))
    risks      = clean(row.get("risks", ""))
    start_d    = clean(row.get("start_date", ""))
    end_d      = clean(row.get("end_date", ""))

    issues   = []   # критичні — треба повертати
    warnings = []   # застереження — для погодження з приміткою

    # 1. Відсутні обов'язкові поля
    missing_fields = []
    field_map = {
        "numeric_value":      "фактичне значення показника",
        "progress_text":      "опис прогресу виконання",
        "status":             "статус виконання заходу",
        "start_date":         "дата початку виконання",
        "end_date":           "дата завершення виконання",
        "responsible_person": "відповідальна особа",
        "phone":              "контактний телефон",
        "email":              "електронна пошта",
    }
    for field, label in field_map.items():
        if not has_value(row.get(field, "")):
            missing_fields.append(label)

    if missing_fields:
        issues.append({
            "type": "missing_fields",
            "fields": missing_fields,
            "text": f"не заповнені обов'язкові поля: {', '.join(missing_fields)}"
        })

    # 2. Перевірка відповідності статусу плановому значенню
    status_mismatch = None
    exec_pct, fact_num, plan_num = compute_execution_pct(fact_str, plan_val_str)
    exp_status = expected_status(exec_pct)

    if exec_pct is not None and exp_status is not None and has_value(status):
        if status.strip() != exp_status:
            status_mismatch = {
                "type":        "status_mismatch",
                "fact":        fact_num,
                "fact_num":    fact_num,
                "plan":        plan_num,
                "plan_num":    plan_num,
                "exec_pct":    exec_pct,
                "submitted":   status,
                "expected":    exp_status,
                "text": (
                    f"невідповідність статусу: подано «{status}», "
                    f"однак при виконанні {exec_pct}% від планового значення "
                    f"({fact_num} з {plan_num}) коректний статус — «{exp_status}»"
                )
            }
            issues.append(status_mismatch)

    # 3. Термін виконання минув, а статус не закритий
    deadline_overdue = False
    if has_value(end_d):
        try:
            end_dt = pd.to_datetime(end_d, errors="coerce")
            if not pd.isna(end_dt):
                if end_dt < pd.Timestamp.now():
                    closed = {"Виконано", "Втратило актуальність"}
                    if status not in closed:
                        deadline_overdue = True
                        issues.append({
                            "type": "deadline_overdue",
                            "text": (
                                f"термін виконання заходу ({end_d}) минув, "
                                f"однак статус не закрито — зазначено «{status}»"
                            )
                        })
        except Exception:
            pass

    # 4. Ризики при статусі «Виконано»
    if risks and status == "Виконано":
        warnings.append({
            "type": "risks_with_done",
            "text": (
                f"зафіксовано ризики/відхилення при статусі «Виконано» — "
                f"це потребує пояснення: {risks}"
            )
        })

    # 5. Опис прогресу є, але факт відсутній
    if has_value(progress) and not has_value(fact_str):
        warnings.append({
            "type": "progress_no_fact",
            "text": "опис прогресу надано, але фактичне числове значення відсутнє"
        })

    # 6. Факт є, але прогрес відсутній
    if has_value(fact_str) and not has_value(progress):
        warnings.append({
            "type": "fact_no_progress",
            "text": "фактичне значення вказано, але опис прогресу виконання відсутній"
        })

    # 7. Нульове фактичне значення при статусі, що не «Виконується» / «Термін не настав»
    if fact_num == 0.0 and status not in ("Не настав час", "Термін не настав", ""):
        warnings.append({
            "type": "zero_fact",
            "text": (
                f"фактичне значення дорівнює нулю при статусі «{status}» — "
                f"можлива помилка або дійсно нульовий результат"
            )
        })

    # 8. Ризики зафіксовані — завжди як застереження
    if risks and status != "Виконано":
        warnings.append({
            "type": "has_risks",
            "text": f"зафіксовано ризики/проблеми/відхилення: {risks}"
        })

    return {
        "issues":          issues,
        "warnings":        warnings,
        "missing_fields":  missing_fields,
        "status_mismatch": status_mismatch,
        "exec_pct":        exec_pct,
        "fact_num":        fact_num,
        "plan_num":        plan_num,
        "exp_status":      exp_status,
        "deadline_overdue": deadline_overdue,
    }


# ──────────────────────────────────────────────
# RESOLUTION GENERATOR — готовий до копіювання текст
# ──────────────────────────────────────────────

def generate_resolution(row, recommendation, plan_val_str):
    code      = clean(row.get("strat_code", ""))
    year      = clean(row.get("year", ""))
    quarter   = clean(row.get("quarter", ""))
    dept      = clean(row.get("department", ""))
    status    = clean(row.get("status", ""))
    fact      = clean(row.get("numeric_value", ""))
    progress  = clean(row.get("progress_text", ""))
    risks     = clean(row.get("risks", ""))
    person    = clean(row.get("responsible_person", ""))
    phone     = clean(row.get("phone", ""))
    email     = clean(row.get("email", ""))
    end_d     = clean(row.get("end_date", ""))

    analysis = analyze_request(row, plan_val_str)
    exec_pct  = analysis["exec_pct"]
    fact_num  = analysis["fact_num"]
    plan_num  = analysis["plan_num"]
    sm        = analysis["status_mismatch"]

    # Форматуємо план/факт рядки
    plan_str = str(plan_val_str).strip() if has_value(plan_val_str) else None
    fact_str = fact if has_value(fact) else None

    pf_clause = ""
    if plan_str and fact_str and exec_pct is not None:
        pf_clause = (
            f"Планове значення показника на {year} рік — {plan_str}, "
            f"фактичне значення за {quarter} квартал — {fact_str} "
            f"({exec_pct}% від річного плану). "
        )
    elif fact_str:
        pf_clause = f"Фактичне значення за {quarter} квартал — {fact_str}. "
    elif plan_str:
        pf_clause = f"Планове значення на {year} рік — {plan_str}. Фактичне значення не вказано. "

    header = (
        f"Відомості щодо заходу {code} за {quarter} квартал {year} року "
        f"від підрозділу {dept} (відповідальна особа: {person}"
        + (f", тел.: {phone}" if has_value(phone) else "")
        + (f", e-mail: {email}" if has_value(email) else "")
        + ") розглянуто. "
    )

    # ── ПОГОДЖЕННЯ ──
    if recommendation == "Можна направляти на підпис":
        warn_texts = [w["text"] for w in analysis["warnings"]]
        warn_clause = ""
        if warn_texts:
            warn_clause = (
                f" Разом із тим, звертаємо увагу на таке: {'; '.join(warn_texts)}. "
                f"Це підлягає врахуванню при підписанні та подальшому моніторингу."
            )
        return (
            header
            + pf_clause
            + f"Статус виконання — «{status}». "
            + (f"Прогрес: {progress}. " if has_value(progress) else "")
            + "Подані відомості визнано достатніми для погодження."
            + warn_clause
            + " Направляємо на підпис керівнику підрозділу."
        )

    # ── ПОВЕРНЕННЯ — невідповідність статусу ──
    if sm is not None and len(analysis["issues"]) == 1:
        # Єдина проблема — тільки статус не той
        fact_v = sm.get("fact") or sm.get("fact_num") or "—"
        plan_v = sm.get("plan") or sm.get("plan_num") or "—"
        return (
            header
            + pf_clause
            + f"Зазначений статус виконання — «{sm['submitted']}». "
            f"Однак при виконанні {sm['exec_pct']}% від річного планового значення "
            f"({fact_v} з {plan_v}) відповідно до методології моніторингу "
            f"коректний статус — «{sm['expected']}». "
            f"Відомості повертаються на доопрацювання. "
            f"Просимо виправити статус виконання на «{sm['expected']}» та подати відомості повторно."
        )

    # ── ПОВЕРНЕННЯ — загальне (кілька проблем) ──
    issue_parts = []

    if analysis["missing_fields"]:
        issue_parts.append(
            f"не заповнені обов'язкові поля: {', '.join(analysis['missing_fields'])}"
        )

    if sm is not None:
        fact_v = sm.get("fact") or sm.get("fact_num") or "—"
        plan_v = sm.get("plan") or sm.get("plan_num") or "—"
        issue_parts.append(
            f"невідповідність статусу: подано «{sm['submitted']}», "
            f"при виконанні {sm['exec_pct']}% ({fact_v} з {plan_v}) коректний статус — «{sm['expected']}»"
        )

    if analysis["deadline_overdue"]:
        issue_parts.append(
            f"термін виконання ({end_d}) минув, але статус не закрито"
        )

    # Додаємо застереження що стають причиною повернення
    for w in analysis["warnings"]:
        if w["type"] in ("progress_no_fact", "fact_no_progress"):
            issue_parts.append(w["text"])

    issues_text = "; ".join(issue_parts) if issue_parts else "виявлено невідповідності у поданих відомостях"

    # Формуємо інструкцію що виправити
    fix_parts = []
    if analysis["missing_fields"]:
        fix_parts.append(f"заповнити відсутні поля ({', '.join(analysis['missing_fields'])})")
    if sm is not None:
        fix_parts.append(f"змінити статус виконання на «{sm['expected']}»")
    if analysis["deadline_overdue"]:
        fix_parts.append("закрити або пояснити статус заходу з урахуванням минулого терміну")
    for w in analysis["warnings"]:
        if w["type"] == "progress_no_fact":
            fix_parts.append("внести числове фактичне значення показника")
        if w["type"] == "fact_no_progress":
            fix_parts.append("додати опис прогресу виконання заходу")

    fix_text = "; ".join(fix_parts) if fix_parts else "усунути зазначені розбіжності"

    return (
        header
        + pf_clause
        + f"Статус виконання — «{status if status else 'не вказано'}». "
        + f"За результатами перевірки встановлено: {issues_text}. "
        + f"Відомості повертаються на доопрацювання. "
        + f"Для повторного подання необхідно: {fix_text}."
    )


# ──────────────────────────────────────────────
# ATTENTION SUMMARY
# ──────────────────────────────────────────────

def build_attention_summary(df):
    data = df.copy()
    if data.empty:
        return {k: pd.DataFrame() for k in
                ["long_waiting", "waiting", "not_counted", "returned", "approved"]}

    data["days_waiting"] = data["submitted_at"].apply(days_waiting)

    return {
        "long_waiting": data[
            (data["approval_status"].astype(str).isin(schemes.ALL_WAITING_STATUSES)) &
            (data["days_waiting"].fillna(0) >= 5)
        ].copy(),
        "waiting": data[
            data["approval_status"].astype(str).isin(schemes.ALL_WAITING_STATUSES)
        ].copy(),
        "not_counted": data[
            ~data["approval_status"].astype(str).isin(["Погоджено"])
        ].copy(),
        "returned": data[
            data["approval_status"].astype(str) == "Повернуто на доопрацювання"
        ].copy(),
        "approved": data[
            data["approval_status"].astype(str) == "Погоджено"
        ].copy(),
    }


# ══════════════════════════════════════════════
# PAGE
# ══════════════════════════════════════════════

st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)
st.markdown(
    '<div class="ministry-label">🇺🇦 Міністерство економіки, довкілля та сільського господарства України</div>',
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="header-box">
        <div class="header-title">Адміністрування</div>
        <div class="header-subtitle">
            Кабінет адміністратора використовується для розгляду, перевірки та погодження
            поданих відомостей та відстеження історії змін.
        </div>
        <div class="status-pill-wrap">
            <div class="status-pill">● Режим: адміністрування</div>
            <div class="status-pill">● Дані: Supabase</div>
            <div class="status-pill">● Журнал змін: активний</div>
            <div class="status-pill">● Резолюція: автоматична</div>
            <div class="status-pill">● Оновлено: {datetime.now().strftime("%d.%m.%Y %H:%M")}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="flow-box">
        <div class="flow-title">Маршрут адміністратора</div>
        <div class="flow-steps">
            <div class="flow-step">1. Перегляд системних параметрів</div>
            <div class="flow-step">2. Вибір параметрів</div>
            <div class="flow-step">3. Перевірка</div>
            <div class="flow-step">4. Вибір рішення</div>
            <div class="flow-step">5. Підтвердження</div>
            <div class="flow-step">6. Погодження</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# ──────────────────────────────────────────────
# LOAD DATA
# ──────────────────────────────────────────────

df = load_requests()
strat_df = load_strat_matrix()

if df.empty:
    st.warning("Поки що немає поданих заявок.")
    st.stop()

required_cols = [
    "id", "department", "year", "quarter", "approval_status", "status",
    "strat_code", "responsible_person", "phone", "email",
    "numeric_value", "progress_text", "risks",
    "file_names", "file_urls", "admin_comment",
    "start_date", "end_date", "submitted_at"
]
for col in required_cols:
    if col not in df.columns:
        df[col] = ""

df = filter_requests_for_user(
    df,
    current_user,
    ssp_columns=["department"]
)

if df.empty:
    st.warning("Для цього користувача немає доступних заявок за закріпленими ССП.")
    st.stop()

render_notifications_panel(df, mode="admin")

attention = build_attention_summary(df)

# ──────────────────────────────────────────────
# СИСТЕМНИЙ АНАЛІЗ
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card">'
    '<div class="card-title">Системний аналіз</div>'
    '<div class="card-subtitle">Автоматичний контроль усіх поданих відомостей</div>',
    unsafe_allow_html=True
)

def _att(title, value, note, css):
    return (
        f'<div class="attention-card {css}">'
        f'<div class="attention-title">{title}</div>'
        f'<div class="attention-value">{value}</div>'
        f'<div class="attention-note">{note}</div>'
        f'</div>'
    )

_lw  = len(attention["long_waiting"])
_wt  = len(attention["waiting"])
_nc  = len(attention["not_counted"])
_ret = len(attention["returned"])
_appr= len(attention["approved"])

st.markdown(
    '<div class="attention-grid">'
    + _att("На розгляді понад 5 днів", _lw,   "Без рішення тривалий час",            "att-red"    if _lw   else "att-green")
    + _att("На розгляді",              _wt,   "Очікують рішення адміністратора",     "att-yellow" if _wt   else "att-green")
    + _att("Не враховано",             _nc,   "Не отримали статус «Погоджено»",      "att-red"    if _nc   else "att-green")
    + _att("На доопрацюванні",         _ret,  "Повернуті для виправлення",           "att-blue"   if _ret  else "att-green")
    + _att("Погоджено",                _appr, "Відомості погоджені адміністратором", "att-green")
    + '</div>',
    unsafe_allow_html=True
)

# Expander — таблиці з вкладками
RENAME_MAP = {
    "id":                 "ID",
    "department":         "ССП",
    "status":             "Статус заходу",
    "strat_code":         "Код заходу",
    "year":               "Рік",
    "quarter":            "Квартал",
    "approval_status":    "Статус погодження",
    "responsible_person": "Відповідальна особа",
    "submitted_at":       "Дата подання",
    "start_date":         "Початок виконання",
    "end_date":           "Кінець виконання",
    "numeric_value":      "Факт. значення",
    "progress_text":      "Опис прогресу",
    "risks":              "Ризики",
    "admin_comment":      "Коментар адміністратора",
}

PRIORITY_COLS_KEYS = [
    "id", "department", "status", "strat_code",
    "start_date", "end_date", "year", "quarter",
]

def sort_and_show(frame):
    if frame.empty:
        st.info("Записів немає.")
        return
    frame = frame.copy()
    frame["_s"] = pd.to_numeric(
        frame["department"].astype(str).str.extract(r"(\d+)")[0], errors="coerce"
    )
    frame = frame.sort_values("_s").drop(columns=["_s"])
    all_cols = list(frame.columns)
    priority = [c for c in PRIORITY_COLS_KEYS if c in all_cols]
    rest = [c for c in all_cols if c not in priority]
    frame = frame[priority + rest].rename(
        columns={k: v for k, v in RENAME_MAP.items() if k in frame.columns}
    )
    st.dataframe(frame, use_container_width=True, hide_index=True)

with st.expander("Перегляд записів"):
    t1, t2, t3, t4, t5 = st.tabs([
        "На розгляді понад 5 днів",
        "На розгляді",
        "Не враховано",
        "На доопрацюванні",
        "Погоджено"
    ])
    with t1: sort_and_show(attention["long_waiting"])
    with t2: sort_and_show(attention["waiting"])
    with t3: sort_and_show(attention["not_counted"])
    with t4: sort_and_show(attention["returned"])
    with t5: sort_and_show(attention["approved"])

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ІНФОГРАФІКА
# ──────────────────────────────────────────────

st.markdown('<div class="card"><div class="card-title">Інфографіка</div>', unsafe_allow_html=True)

status_counts = {
    "На розгляді понад 5 днів": len(attention["long_waiting"]),
    "На розгляді":              len(attention["waiting"]),
    "Не враховано":             len(attention["not_counted"]),
    "На доопрацюванні":         len(attention["returned"]),
    "Погоджено":                len(attention["approved"]),
}

chart_df = pd.DataFrame({
    "Статус":    list(status_counts.keys()),
    "Кількість": list(status_counts.values())
})
chart_df = chart_df[chart_df["Кількість"] > 0]

if not chart_df.empty:
    color_map = {
        "На розгляді понад 5 днів": "#ef4444",
        "На розгляді":              "#f59e0b",
        "Не враховано":             "#f97316",
        "На доопрацюванні":         "#3b82f6",
        "Погоджено":                "#22c55e",
    }
    fig = px.pie(
        chart_df, names="Статус", values="Кількість", hole=0.48,
        title="Розподіл заявок за статусом виконання",
        color="Статус", color_discrete_map=color_map
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#334155",
        title_font_color="#0f172a",
        legend=dict(font=dict(color="#475569"), bgcolor="rgba(0,0,0,0)")
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Даних для відображення немає.")

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ПАРАМЕТРИ ВІДБОРУ
# ──────────────────────────────────────────────

st.markdown('<div class="card"><div class="card-title">Параметри відбору</div>', unsafe_allow_html=True)

all_ssp_raw = sorted(
    {idx for _, row in df.iterrows() for idx in split_ssp_values(row.get("department", ""))},
    key=lambda x: int(x) if str(x).isdigit() else 9999
)

if user_has_all_ssp_access(current_user):
    available_ssp_raw = all_ssp_raw
else:
    allowed_ssp_indexes = get_user_allowed_ssp_indexes(current_user)
    available_ssp_raw = [
        index
        for index in all_ssp_raw
        if index in allowed_ssp_indexes
    ]

f1, f2, f3, f4 = st.columns(4)
with f1:
    selected_ssp = st.selectbox(
        "Самостійний структурний підрозділ",
        ["Усі"] + available_ssp_raw
    )
with f2:
    years = sorted(df["year"].dropna().astype(str).unique().tolist())
    selected_year = st.selectbox("Рік", ["Усі"] + years)
with f3:
    quarters = sorted(df["quarter"].dropna().astype(str).unique().tolist())
    selected_quarter = st.selectbox("Квартал", ["Усі"] + quarters)
with f4:
    selected_approval_status = st.selectbox(
        "Статус погодження",
        ["Активні до розгляду", "Усі", "Очікує погодження",
         "Очікує: Керівник управління", "Очікує: Заступник керівника ССП",
         "Повернуто на доопрацювання", "Направлено на підпис", "Погоджено"],
        index=0
    )

q1, q2 = st.columns([1, 2])
with q1:
    quick_filter = st.selectbox(
        "Швидкий фільтр",
        ["Усі заявки", "Тільки очікують", "Повернуті",
         "Із ризиками", "Останні подані", "На розгляді понад 5 днів"]
    )
with q2:
    search_query = st.text_input("Пошук за ID, назвою заходу, ПІБ або ССП")

# ── фільтрація ──
filtered = df.copy()

if selected_ssp != "Усі":
    filtered = filtered[filtered["department"].astype(str).str.contains(selected_ssp, na=False)]
if selected_year != "Усі":
    filtered = filtered[filtered["year"].astype(str) == str(selected_year)]
if selected_quarter != "Усі":
    filtered = filtered[filtered["quarter"].astype(str) == str(selected_quarter)]

if selected_approval_status == "Активні до розгляду":
    filtered = filtered[filtered["approval_status"].astype(str).isin(
        ["Очікує погодження", "Очікує: Керівник управління",
         "Очікує: Заступник керівника ССП",
         "Повернуто на доопрацювання", "Направлено на підпис"]
    )]
elif selected_approval_status != "Усі":
    filtered = filtered[filtered["approval_status"].astype(str) == str(selected_approval_status)]

if quick_filter == "Тільки очікують":
    # Усі заявки, що чекають рішення БУДЬ-ЯКОЇ ланки схеми
    filtered = filtered[filtered["approval_status"].isin(schemes.ALL_WAITING_STATUSES)]
elif quick_filter == "Повернуті":
    filtered = filtered[filtered["approval_status"] == "Повернуто на доопрацювання"]
elif quick_filter == "Із ризиками":
    filtered = filtered[filtered["risks"].fillna("").astype(str).str.strip() != ""]
elif quick_filter == "Останні подані":
    filtered = filtered.sort_values("submitted_at", ascending=False).head(10)
elif quick_filter == "На розгляді понад 5 днів":
    filtered = attention["long_waiting"].copy()

if search_query.strip():
    sq = search_query.strip().lower()
    filtered = filtered[
        filtered["id"].astype(str).str.lower().str.contains(sq, na=False)
        | filtered["strat_code"].astype(str).str.lower().str.contains(sq, na=False)
        | filtered["responsible_person"].astype(str).str.lower().str.contains(sq, na=False)
        | filtered["department"].astype(str).str.lower().str.contains(sq, na=False)
        | filtered["progress_text"].astype(str).str.lower().str.contains(sq, na=False)
    ]

st.caption(f"Знайдено заявок: {len(filtered)}")
st.markdown('</div>', unsafe_allow_html=True)

if filtered.empty:
    st.info("За обраними фільтрами заявок не знайдено.")
    st.stop()

# ──────────────────────────────────────────────
# ЧЕРГА НА РОЗГЛЯД
# ──────────────────────────────────────────────

queue_df = filtered[
    filtered["approval_status"].isin([
        "Очікує погодження", "Направлено на підпис",
        "Очікує: Керівник управління", "Очікує: Заступник керівника ССП",
    ])
].copy()

if not queue_df.empty:
    st.markdown(
        '<div class="card">'
        '<div class="card-title">Черга на розгляд</div>'
        '<div class="card-subtitle">Заявки, що потребують рішення адміністратора.</div>',
        unsafe_allow_html=True
    )

    queue_df["_s"] = pd.to_numeric(
        queue_df["department"].astype(str).str.extract(r"(\d+)")[0], errors="coerce"
    )
    queue_df = queue_df.sort_values("_s").drop(columns=["_s"])

    queue_show = queue_df.rename(columns={
        "id":                 "ID",
        "department":         "Самостійний структурний підрозділ",
        "strat_code":         "Код заходу",
        "year":               "Рік",
        "quarter":            "Квартал",
        "status":             "Статус заходу",
        "approval_status":    "Статус погодження",
        "responsible_person": "Відповідальна особа",
        "submitted_at":       "Дата подання"
    })

    display_cols = [c for c in [
        "ID", "Самостійний структурний підрозділ", "Код заходу",
        "Рік", "Квартал", "Статус заходу", "Статус погодження",
        "Відповідальна особа", "Дата подання"
    ] if c in queue_show.columns]

    st.dataframe(queue_show[display_cols], use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ВИБІР ЗАЯВКИ
# ──────────────────────────────────────────────

st.markdown('<div class="card"><div class="card-title">Вибір заявки</div>', unsafe_allow_html=True)

selected_options = [
    f"ID {row['id']} | ССП {row['department']} | {row['strat_code']} | "
    f"{row['year']} {row['quarter']} квартал | {row['approval_status']} | "
    f"{clean(row['submitted_at'])}"
    for _, row in filtered.iterrows()
]

selected_request = st.selectbox("Оберіть заявку для перегляду та погодження", selected_options)
selected_id  = int(selected_request.split("|")[0].replace("ID", "").strip())
selected_row = filtered[filtered["id"].astype(int) == selected_id].iloc[0]

st.markdown('</div>', unsafe_allow_html=True)

approval_status = clean(selected_row["approval_status"])
selected_code   = clean(selected_row["strat_code"])

# Планове значення — обчислюємо тут, щоб передати в резолюцію
target_year_val = ""
year_val = clean(selected_row.get("year", ""))
if year_val and year_val.isdigit():
    m_info_for_plan = strat_df[strat_df["code"].astype(str).str.strip() == selected_code]
    col_name = f"target_{year_val}"
    if not m_info_for_plan.empty and col_name in m_info_for_plan.columns:
        v = clean(m_info_for_plan.iloc[0].get(col_name, ""))
        if v:
            target_year_val = v

checks, recommendation, rec_badge, quality_score, total_fields, completeness_pct = quality_assessment(selected_row)
auto_resolution = generate_resolution(selected_row, recommendation, target_year_val)

# ──────────────────────────────────────────────
# КАРТКА ЗАЯВКИ  (без "Код заходу" — він у заголовку)
# ──────────────────────────────────────────────

st.markdown('<div class="card"><div class="card-title">Картка заявки</div>', unsafe_allow_html=True)

if approval_status == "Погоджено":
    status_badge = "badge-green"
elif approval_status == "Повернуто на доопрацювання":
    status_badge = "badge-red"
elif approval_status == "Направлено на підпис":
    status_badge = "badge"
else:
    status_badge = "badge-yellow"

st.markdown(
    f"""
    <div class="badge-wrap">
        <div class="badge {status_badge}">Статус: {approval_status}</div>
        <div class="badge">Захід № {selected_code}</div>
        <div class="badge">ID {clean(selected_row['id'])}</div>
        <div class="badge {rec_badge}">Рекомендація: {recommendation}</div>
    </div>
    """,
    unsafe_allow_html=True
)

k1, k2, k3, k4, k5 = st.columns(5)

with k1:
    admin_kpi_card("Індекс самостійного структурного підрозділу", clean(selected_row.get("department", "")))
with k2:
    admin_kpi_card("Рік / Квартал", f"{clean(selected_row.get('year', ''))} / {clean(selected_row.get('quarter', ''))}")
with k3:
    admin_kpi_card("Статус", clean(selected_row.get("status", "")))

with k4:
    display_plan = target_year_val if target_year_val else "—"
    admin_kpi_card(f"Планове значення ({year_val})", display_plan)
with k5:
    admin_kpi_card("Фактичне квартальне значення", clean(selected_row.get("numeric_value", "")))

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# СИСТЕМНА ОЦІНКА ЯКОСТІ — grid 5+4, висновок окремо
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card"><div class="card-title">Системна оцінка якості заявки</div>',
    unsafe_allow_html=True
)

# Рендеримо картки HTML-гридом, 5 per row
row1 = checks[:5]
row2 = checks[5:]

def render_quality_row(items):
    cols_html = ""
    for label, value, ok in items:
        css = "quality-good" if ok else "quality-warn"
        icon = "✅" if ok else "⚠️"
        cols_html += (
            f'<div class="quality-card {css}">'
            f'<div class="quality-label">{label}</div>'
            f'<div class="quality-value"><span>{icon}</span><span>{value}</span></div>'
            f'</div>'
        )
    st.markdown(f'<div class="quality-grid">{cols_html}</div>', unsafe_allow_html=True)

render_quality_row(row1)
if row2:
    render_quality_row(row2)

# Висновок системи
if recommendation == "Можна направляти на підпис":
    concl_color = "#15803d"
    concl_icon  = "✅"
elif recommendation == "Потребує перевірки":
    concl_color = "#92400e"
    concl_icon  = "⚠️"
else:
    concl_color = "#b91c1c"
    concl_icon  = "❌"

st.markdown(
    f"""
    <div class="quality-conclusion">
        <span class="quality-conclusion-label">Висновок системи</span>
        <span class="quality-conclusion-value" style="color:{concl_color};">
            {concl_icon} {recommendation}
        </span>
        <span class="quality-conclusion-pct">Заповненість: {completeness_pct}%</span>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# АВТОМАТИЧНА СЛУЖБОВА РЕЗОЛЮЦІЯ
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card">'
    '<div class="card-title">Автоматична службова резолюція</div>'
    '<div class="card-subtitle">Система формує текст на основі якості заявки, статусу, фактичного значення та ризиків.</div>',
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="resolution-box">
        <div class="resolution-title">Проєкт резолюції — готовий до копіювання</div>
        <div class="resolution-text">{auto_resolution}</div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ІНФОРМАЦІЯ ПРО ЗАХІД
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card"><div class="card-title">Інформація про захід зі стратегічного плану</div>',
    unsafe_allow_html=True
)

measure_info = strat_df[strat_df["code"].astype(str).str.strip() == selected_code].copy()

if measure_info.empty:
    st.warning("Захід не знайдено у стратегічній матриці.")
else:
    si = measure_info.iloc[0]
    st.markdown(
        f"""
        <div class="review-box">
            <div class="review-title">{clean(si.get("code",""))} — {clean(si.get("name",""))}</div>
            <div><b>Тип продукту:</b> {clean(si.get("product_type",""))}</div>
            <div><b>Індикатор:</b> {clean(si.get("indicator",""))}</div>
            <div><b>Одиниця виміру:</b> {clean(si.get("unit",""))}</div>
            <div><b>Відповідальний ССП:</b> {clean(si.get("resp_main",""))} &nbsp;|&nbsp;
                 Спів. 1: {clean(si.get("resp_co_1",""))} &nbsp;|&nbsp;
                 Спів. 2: {clean(si.get("resp_co_2",""))}</div>
            <div><b>Термін:</b> {clean(si.get("start_date_plan",""))} — {clean(si.get("end_date_plan",""))}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.expander("Детальна таблиця заходу"):
        measure_display = measure_info.rename(columns={
            "type_marker":     "Тип маркера",
            "code":            "Код заходу",
            "name":            "Назва заходу",
            "product_type":    "Тип продукту",
            "indicator":       "Індикатор",
            "unit":            "Одиниця виміру",
            "base_2021":       "Базове 2021",
            "fact_2024":       "Звіт 2024",
            "expected_2025":   "Очікуване 2025",
            "target_2026":     "План 2026",
            "target_2027":     "План 2027",
            "target_2028":     "План 2028",
            "resp_main":       "ССП Головний",
            "resp_co_1":       "ССП Спів. 1",
            "resp_co_2":       "ССП Спів. 2",
            "start_date_plan": "Початок (СП)",
            "end_date_plan":   "Кінець (СП)",
        })
        detail_cols = [
            "Тип маркера","Код заходу","Назва заходу","Тип продукту",
            "Індикатор","Одиниця виміру",
            "Базове 2021","Звіт 2024","Очікуване 2025",
            "План 2026","План 2027","План 2028",
            "ССП Головний","ССП Спів. 1","ССП Спів. 2",
            "Початок (СП)","Кінець (СП)",
        ]
        available = [c for c in detail_cols if c in measure_display.columns]
        st.dataframe(measure_display[available], use_container_width=True, hide_index=True)

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ДАНІ ВІДПОВІДАЛЬНОЇ ОСОБИ
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card"><div class="card-title">Дані відповідальної особи</div>',
    unsafe_allow_html=True
)

person_name  = clean(selected_row["responsible_person"])
person_phone = clean(selected_row["phone"])
person_email = clean(selected_row["email"])

st.markdown(
    f"""
    <div class="person-box">
        <div class="person-field">
            <span class="person-field-label">ПІБ</span>
            <span class="person-field-value">{person_name or "—"}</span>
        </div>
        <div class="person-field">
            <span class="person-field-label">Телефон</span>
            <span class="person-field-value">{person_phone or "—"}</span>
        </div>
        <div class="person-field">
            <span class="person-field-label">Email</span>
            <span class="person-field-value">{person_email or "—"}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ОПИС ПРОГРЕСУ ТА РИЗИКИ
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card"><div class="card-title">Опис прогресу та ризики</div>',
    unsafe_allow_html=True
)

pr1, pr2 = st.columns(2)
progress_val = clean(selected_row["progress_text"])
risks_val    = clean(selected_row["risks"])

with pr1:
    st.markdown(
        f'<div class="progress-risk-box">'
        f'<div class="progress-risk-label">Опис прогресу виконання</div>'
        f'<div class="progress-risk-value">{progress_val or "—"}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

with pr2:
    r_color = "#dc2626" if risks_val else "#64748b"
    r_text_color = "#b91c1c" if risks_val else "#94a3b8"
    st.markdown(
        f'<div class="progress-risk-box" style="border-left: 3px solid {r_color};">'
        f'<div class="progress-risk-label">Ризики / проблеми / відхилення</div>'
        f'<div class="progress-risk-value" style="color:{r_text_color};">'
        f'{risks_val or "Не зазначено"}'
        f'</div></div>',
        unsafe_allow_html=True
    )

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ПОСИЛАННЯ НА НПА (клікабельні) + СХЕМА ПОГОДЖЕННЯ
# ──────────────────────────────────────────────

_npa_raw = clean(selected_row.get("npa_link", "")) if "npa_link" in selected_row.index else ""
_req_chain = schemes.parse_chain(selected_row.get("approval_chain")) if "approval_chain" in selected_row.index else []
_req_stage = schemes.parse_stage(selected_row.get("chain_stage")) if "chain_stage" in selected_row.index else 0
_req_scheme_label = clean(selected_row.get("scheme_label", "")) if "scheme_label" in selected_row.index else ""
_req_kind = clean(selected_row.get("object_kind", "")) if "object_kind" in selected_row.index else "measure"

if _npa_raw or _req_chain:
    st.markdown('<div class="card"><div class="card-title">НПА та маршрут погодження</div>', unsafe_allow_html=True)
    if _npa_raw:
        _links_html = "".join(
            f'<div>🔗 <a href="{_esc(u.strip())}" target="_blank">{_esc(u.strip())}</a></div>'
            for u in re.split(r"[\n;,]+", _npa_raw) if u.strip()
        )
        st.markdown(
            f'<div class="progress-risk-box"><div class="progress-risk-label">Посилання на НПА / підтвердні документи</div>'
            f'<div class="progress-risk-value">{_links_html}</div></div>',
            unsafe_allow_html=True,
        )
    if _req_chain:
        st.markdown(
            f'<div class="progress-risk-box"><div class="progress-risk-label">'
            f'Схема погодження{(" · " + _esc(_req_scheme_label)) if _req_scheme_label else ""}</div>'
            f'<div class="progress-risk-value">{_esc(schemes.chain_route_text(_req_chain))}<br>'
            f'<b>{_esc(schemes.chain_progress_text(_req_chain, _req_stage, approval_status))}</b></div></div>',
            unsafe_allow_html=True,
        )

        # Зміна/підтвердження схеми адміністратором (фіксується в журналі)
        with st.expander("🧭 Підтвердити або змінити схему погодження"):
            _sch_c1, _sch_c2 = st.columns([1, 1])
            with _sch_c1:
                if st.button("✔ Підтвердити обрану подавачем схему", key=f"confirm_scheme_{selected_id}", use_container_width=True):
                    write_log(selected_id, "Схему погодження підтверджено адміністратором",
                              approval_status, approval_status,
                              f"Схема: {_req_scheme_label or schemes.chain_route_text(_req_chain)}")
                    st.success("Схему підтверджено (зафіксовано в журналі).")
            with _sch_c2:
                _dept_idx = re.findall(r"\d+", clean(selected_row.get("department", "")))
                _dept_idx = _dept_idx[0] if _dept_idx else ""
                _new_scheme = st.selectbox("Нова схема", schemes.scheme_options(), key=f"new_scheme_{selected_id}")
            _new_roles = schemes.APPROVAL_SCHEMES[_new_scheme]
            _new_persons = {}
            _new_ready = True
            _pcols = st.columns(len(_new_roles))
            for _i, _r in enumerate(_new_roles):
                with _pcols[_i]:
                    _cands = schemes.stage_candidates(_r, _dept_idx)
                    if not _cands:
                        st.warning(f"Немає користувачів ролі «{schemes.STAGE_LABELS.get(_r)}» для ССП {_dept_idx}")
                        _new_ready = False
                        continue
                    _opts = [schemes.candidate_label(c) for c in _cands]
                    _pk = st.selectbox(f"{_i+1}. {schemes.STAGE_LABELS.get(_r)}", _opts, key=f"chg_{selected_id}_{_r}")
                    _ch = _cands[_opts.index(_pk)]
                    _new_persons[_r] = {"email": _ch["email"], "name": _ch["name"]}
            if st.button("🔁 Застосувати нову схему", key=f"apply_scheme_{selected_id}",
                         use_container_width=True, disabled=not _new_ready):
                _new_chain = schemes.build_chain(_new_scheme, _new_persons)
                # Поточною ланкою нової схеми стає координатор (адмін якраз розглядає заявку)
                _admin_pos = next((i for i, stg in enumerate(_new_chain) if stg["role"] == "admin"), 0)
                _new_status = schemes.waiting_status_for_stage(_new_chain[_admin_pos])
                try:
                    supabase.table("monitoring_requests").update({
                        "approval_chain": schemes.chain_to_json(_new_chain),
                        "chain_stage": int(_admin_pos),
                        "scheme_label": _new_scheme,
                        "approval_status": _new_status,
                    }).eq("id", int(selected_id)).execute()
                    write_log(selected_id, "Схему погодження змінено адміністратором",
                              approval_status, _new_status,
                              f"Нова схема: {_new_scheme} · {schemes.chain_route_text(_new_chain)}")
                    st.success("Схему змінено та зафіксовано в журналі.")
                    st.rerun()
                except Exception as e:
                    st.error("Не вдалося змінити схему.")
                    st.exception(e)
    st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# КОНФЛІКТ: заявка по заходу, який уже ЗАКРИТО ВРУЧНУ
# ──────────────────────────────────────────────

_manual_set = load_manual_closeouts()
_req_year = clean(selected_row.get("year", ""))
_req_quarter = clean(selected_row.get("quarter", ""))
_is_conflict = (selected_code, _req_year, _req_quarter) in _manual_set

if _is_conflict and _req_kind != "indicator":
    st.markdown(
        f"""
        <div class="card" style="border:2px solid #b45309;background:#fffbeb;">
            <div class="card-title">⚠️ Увага: захід уже закрито вручну</div>
            <div class="card-subtitle">
                Захід <b>{_esc(selected_code)}</b> за період {_esc(_req_quarter)} кв. {_esc(_req_year)}
                було закрито адміністратором і підтверджено супер-адміном, а тепер по ньому
                надійшла звичайна заявка ССП. Порівняйте дані нижче.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _cf1, _cf2 = st.columns(2)
    with _cf1:
        st.markdown("**Подана заявка ССП:**")
        st.write(f"Фактичне значення: `{clean(selected_row.get('numeric_value','')) or '—'}`")
        st.write(f"Статус виконання: `{clean(selected_row.get('status','')) or '—'}`")
    with _cf2:
        st.markdown("**Ручне закриття:**")
        st.write("Статус: `Закрито вручну (= Виконано)`")
        st.caption("Деталі підстави — у розділі «Закриття заходу вручну» нижче.")

    _cfb1, _cfb2 = st.columns(2)
    with _cfb1:
        if st.button("✅ Дані збігаються — погодити заявку", key=f"conflict_ok_{selected_id}", use_container_width=True):
            try:
                supabase.table("monitoring_requests").update({
                    "approval_status": "Погоджено",
                    "admin_comment": "Погоджено: дані заявки збігаються з ручним закриттям заходу.",
                }).eq("id", int(selected_id)).execute()
                write_log(selected_id, "Погодження заявки (збіг із ручним закриттям)",
                          approval_status, "Погоджено",
                          "Дані заявки збігаються з підтвердженим ручним закриттям.")
                st.success("Заявку погоджено.")
                st.rerun()
            except Exception as e:
                st.error("Не вдалося погодити заявку.")
                st.exception(e)
    with _cfb2:
        _dispute_note = st.text_input("Опис розбіжності", key=f"dispute_note_{selected_id}",
                                      placeholder="Наприклад: у заявці факт 40%, захід закрито як виконаний")
        if st.button("⛔ Є розбіжність — передати Супер-адміну", key=f"conflict_bad_{selected_id}", use_container_width=True):
            if not clean(_dispute_note):
                st.error("Опишіть розбіжність перед передачею супер-адміну.")
            else:
                try:
                    _co = (
                        supabase.table("closeout_requests").select("id")
                        .eq("strat_code", selected_code).eq("period_year", _req_year)
                        .eq("approval_status", "Підтверджено").limit(1).execute()
                    )
                    if _co.data:
                        supabase.table("closeout_requests").update({
                            "dispute_request_id": int(selected_id),
                            "dispute_note": clean(_dispute_note),
                            "dispute_status": "На розгляді",
                        }).eq("id", int(_co.data[0]["id"])).execute()
                    write_log(selected_id, "Розбіжність із ручним закриттям — передано Супер-адміну",
                              approval_status, approval_status, clean(_dispute_note))
                    st.warning("Розбіжність зафіксовано та передано супер-адміну.")
                    st.rerun()
                except Exception as e:
                    st.error("Не вдалося зафіксувати розбіжність.")
                    st.exception(e)

# ──────────────────────────────────────────────
# РІШЕННЯ АДМІНІСТРАТОРА
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card">'
    '<div class="card-title">Рішення адміністратора</div>'
    '<div class="card-subtitle">Оберіть рішення та підтвердьте його однією кнопкою.</div>',
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="badge-wrap">
        <div class="badge {rec_badge}">Системна рекомендація: {recommendation}</div>
        <div class="badge">Заповненість: {completeness_pct}%</div>
        <div class="badge {status_badge}">Поточний статус: {approval_status}</div>
    </div>
    """,
    unsafe_allow_html=True
)

default_comment = clean(selected_row["admin_comment"])

# Наступна ланка після координатора (для заявок зі схемою)
_next_after_admin = None
if _req_chain and 0 <= _req_stage < len(_req_chain):
    _next_after_admin = schemes.current_stage(_req_chain, _req_stage + 1)

if _req_chain:
    _approve_option = (
        f"Погодити та передати далі (→ {_next_after_admin['label']})"
        if _next_after_admin else
        "Погодити (остання ланка — статус «Погоджено»)"
    )
else:
    _approve_option = "Направити на підпис керівнику ССП"

# Адресати повернення (подавач + попередні ланки, якщо є схема)
if _req_chain:
    _adm_targets = schemes.return_targets(_req_chain, _req_stage)
else:
    _adm_targets = [{"key": "submitter", "label": "Подавачу (відповідальній особі ССП)",
                     "status": "Повернуто на доопрацювання", "new_stage": 0}]
_adm_target_labels = [t["label"] for t in _adm_targets]

with st.form(key=f"admin_decision_form_{selected_id}"):
    decision = st.radio(
        "Оберіть рішення",
        [
            _approve_option,
            "Повернути на доопрацювання",
            "Залишити в очікуванні"
        ],
        horizontal=True,
        key=f"decision_radio_{selected_id}"
    )

    return_target_label = st.selectbox(
        "Кому повернути (якщо обрано повернення)",
        _adm_target_labels,
        key=f"adm_return_target_{selected_id}",
    )

    decision_labels = {
        _approve_option:
            ("🖊 Заявку буде передано на наступну ланку схеми погодження"
             if _req_chain and _next_after_admin else
             ("✅ Заявка отримає статус «Погоджено»" if _req_chain else
              "🖊 Направлено на підпис керівнику ССП — після підпису дані будуть підтверджені")),
        "Повернути на доопрацювання":
            "↩ Повернено на доопрацювання — адресат отримає сповіщення",
        "Залишити в очікуванні":
            "⏳ Залишено в очікуванні — без змін статусу",
    }

    st.markdown(
        f'<div class="decision-box">{decision_labels.get(decision, decision)}</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="comment-header">✏ Коментар адміністратора</div>',
        unsafe_allow_html=True
    )

    admin_comment = st.text_area(
        "Введіть коментар або обґрунтування рішення",
        value=default_comment,
        height=130,
        key=f"admin_comment_form_{selected_id}",
        label_visibility="collapsed"
    )

    confirm_decision = st.form_submit_button(
        "Застосувати рішення",
        use_container_width=True
    )

if confirm_decision:
    _extra_update = {}
    _notify_action = None   # ("stage", stage_dict) | ("approved",) | ("returned", target)

    if decision == _approve_option:
        if _req_chain:
            new_status, _new_stage = schemes.status_after_approve(_req_chain, _req_stage)
            _extra_update["chain_stage"] = int(_new_stage)
            if new_status == "Погоджено":
                action_text  = "Погодження координатором (остання ланка схеми)"
                success_text = "✅ Заявка пройшла всі етапи схеми. Статус: «Погоджено»."
                _notify_action = ("approved",)
            else:
                action_text  = f"Погодження координатором → передано далі: {new_status}"
                success_text = f"✅ Заявку передано на наступну ланку: «{new_status}»."
                _notify_action = ("stage", _next_after_admin)
        else:
            new_status   = "Направлено на підпис"
            action_text  = "Направлення на підпис керівнику ССП"
            success_text = "✅ Заявку направлено на підпис керівнику ССП. Після підпису дані будуть підтверджені на головній сторінці."
    elif decision == "Повернути на доопрацювання":
        _picked = _adm_targets[_adm_target_labels.index(return_target_label)]
        new_status   = _picked["status"]
        action_text  = f"Повернення на доопрацювання: {_picked['label']}"
        success_text = f"↩ Заявку повернуто: {_picked['label']}."
        if _req_chain:
            _extra_update["chain_stage"] = int(_picked["new_stage"])
        _notify_action = ("returned", _picked)
    else:
        new_status   = approval_status
        action_text  = "Заявку залишено в очікуванні"
        success_text = "⏳ Заявку залишено в очікуванні."

    try:
        supabase.table("monitoring_requests").update({
            "approval_status": new_status,
            "admin_comment":   admin_comment,
            **_extra_update,
        }).eq("id", int(selected_id)).execute()

        write_log(selected_id, action_text, approval_status, new_status, admin_comment)

        # Миттєві email-сповіщення (не ламають інтерфейс при помилці)
        try:
            if _notify_action and _notify_action[0] == "approved":
                notify_events.notify_approved(
                    clean(selected_row.get("email", "")),
                    clean(selected_row.get("responsible_person", "")),
                    selected_code, _req_year, _req_quarter, kind=_req_kind or "measure",
                )
            elif _notify_action and _notify_action[0] == "stage" and _notify_action[1]:
                _nx = _notify_action[1]
                notify_events.notify_stage_assigned(
                    _nx.get("email", ""), _nx.get("name", ""), _nx.get("label", ""),
                    selected_code, _req_year, _req_quarter,
                    submitter=clean(selected_row.get("responsible_person", "")),
                    kind=_req_kind or "measure",
                )
            elif _notify_action and _notify_action[0] == "returned":
                _tg = _notify_action[1]
                if _tg["key"] == "submitter":
                    notify_events.notify_returned(
                        clean(selected_row.get("email", "")),
                        clean(selected_row.get("responsible_person", "")),
                        selected_code, _req_year, _req_quarter,
                        by_label="Координатор", comment=clean(admin_comment),
                        kind=_req_kind or "measure",
                    )
                elif _tg["key"].startswith("stage:") and _req_chain:
                    _ts = _req_chain[_tg["new_stage"]]
                    notify_events.notify_returned(
                        _ts.get("email", ""), _ts.get("name", ""),
                        selected_code, _req_year, _req_quarter,
                        by_label="Координатор", comment=clean(admin_comment),
                        kind=_req_kind or "measure",
                    )
        except Exception:
            pass

        st.success(success_text)
        st.rerun()
    except Exception as e:
        st.error("Не вдалося застосувати рішення.")
        st.exception(e)

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ОСТАННЯ ДІЯ ТА ІСТОРІЯ ЗМІН
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card"><div class="card-title">Остання дія та історія змін</div>',
    unsafe_allow_html=True
)

logs_df = load_logs(selected_id)

if logs_df.empty:
    st.info("Історії змін для цієї заявки поки що немає.")
else:
    latest_log = logs_df.iloc[0]
    st.markdown(
        f"""
        <div class="review-box">
            <div class="review-title">Остання дія: {clean(latest_log.get("action",""))}</div>
            <div><b>Статус:</b>
                {clean(latest_log.get("old_status",""))} → {clean(latest_log.get("new_status",""))}
            </div>
            <div><b>Коментар:</b> {clean(latest_log.get("admin_comment",""))}</div>
            <div><b>Дата:</b> {clean(latest_log.get("changed_at",""))}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.expander("Повна історія змін заявки"):
        show_logs = logs_df.rename(columns={
            "changed_at":    "Дата зміни",
            "action":        "Дія",
            "old_status":    "Попередній статус",
            "new_status":    "Новий статус",
            "admin_comment": "Коментар адміністратора",
            "changed_by":    "Ким змінено"
        })
        show_cols = ["Дата зміни","Дія","Попередній статус",
                     "Новий статус","Коментар адміністратора","Ким змінено"]
        st.dataframe(
            show_logs[[c for c in show_cols if c in show_logs.columns]],
            use_container_width=True, hide_index=True
        )

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ЗАКРИТТЯ ЗАХОДУ ВРУЧНУ (admin → super_admin)
# ──────────────────────────────────────────────


def load_closeout_requests():
    resp = (
        supabase.table("closeout_requests")
        .select("*")
        .order("requested_at", desc=True)
        .execute()
    )
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()


measure_codes = strat_df[strat_df["code"].astype(str).str.count(r"\.") >= 3]["code"].astype(str).tolist() \
    if "code" in strat_df.columns else []

st.markdown(
    '<div class="card"><div class="card-title">Закриття заходу вручну</div>',
    unsafe_allow_html=True
)

if is_admin_user(current_user) or is_super_admin_user(current_user):
    with st.form("closeout_request_form"):
        st.caption(
            "Подати запит на ручне закриття заходу за період. "
            "Підтверджений запит не підмінює статус подання моніторингу — "
            "він лише додає окрему позначку «Закрито вручну»."
        )
        co_code = st.selectbox("Код заходу", measure_codes)
        co_scope_col, co_year_col, co_quarter_col = st.columns(3)
        with co_scope_col:
            co_scope = st.selectbox("Масштаб закриття", ["Квартал", "Рік"])
        with co_year_col:
            co_year = st.selectbox("Рік", list(range(2026, 2035)))
        with co_quarter_col:
            co_quarter = st.selectbox("Квартал (якщо масштаб — квартал)", ["I", "II", "III", "IV"])
        co_reason = st.text_area("Підстава для закриття (внутрішня інформація, комунікація, інший звітний документ)")
        co_npa = st.text_area(
            "Посилання на НПА / джерела (по одному в рядку, опційно)",
            placeholder="https://zakon.rada.gov.ua/...\nhttps://docs.google.com/...",
        )
        co_evidence = st.text_area("Додаткові пояснення (опційно)")
        co_submit = st.form_submit_button("Надіслати на підтвердження супер-адміну")

    if co_submit:
        if not co_reason.strip():
            st.error("Заповніть підставу для закриття заходу.")
        else:
            try:
                supabase.table("closeout_requests").insert({
                    "strat_code":     co_code,
                    "period_year":    str(co_year),
                    "period_quarter": "Рік" if co_scope == "Рік" else co_quarter,
                    "scope":          co_scope,
                    "npa_links":      co_npa.strip(),
                    "admin_id":       current_user.get("id", ""),
                    "admin_email":    current_user.get("email", ""),
                    "reason":         co_reason.strip(),
                    "evidence_note":  co_evidence.strip(),
                    "approval_status": "Очікує підтвердження",
                }).execute()
                st.success("Запит на закриття заходу надіслано на підтвердження супер-адміну.")
                st.rerun()
            except Exception as e:
                st.error("Не вдалося надіслати запит на закриття заходу.")
                st.exception(e)
else:
    st.info("Подання запиту на закриття заходу доступне лише адміністратору або супер-адміну.")

closeout_df = load_closeout_requests()

if is_super_admin_user(current_user):
    st.markdown('<div class="card-title" style="margin-top:18px;">Підтвердження закриття заходів (супер-адмін)</div>', unsafe_allow_html=True)

    pending_closeouts = closeout_df[closeout_df["approval_status"] == "Очікує підтвердження"] if not closeout_df.empty else pd.DataFrame()

    if pending_closeouts.empty:
        st.info("Запитів на закриття, що очікують підтвердження, немає.")
    else:
        for _, co_row in pending_closeouts.iterrows():
            with st.container():
                st.markdown(
                    f"""
                    <div class="review-box">
                        <div class="review-title">Захід {clean(co_row.get("strat_code",""))}
                            — {clean(co_row.get("period_quarter",""))} кв. {clean(co_row.get("period_year",""))}</div>
                        <div><b>Підстава:</b> {clean(co_row.get("reason",""))}</div>
                        <div><b>Пояснення:</b> {clean(co_row.get("evidence_note",""))}</div>
                        <div><b>Подано:</b> {clean(co_row.get("admin_email",""))} о {clean(co_row.get("requested_at",""))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                co_decision_comment = st.text_input(
                    "Коментар рішення (опційно)",
                    key=f"co_decision_comment_{co_row.get('id')}"
                )
                co_col1, co_col2 = st.columns(2)
                with co_col1:
                    co_approve = st.button("Підтвердити", key=f"co_approve_{co_row.get('id')}", use_container_width=True)
                with co_col2:
                    co_reject = st.button("Відхилити", key=f"co_reject_{co_row.get('id')}", use_container_width=True)

                if co_approve or co_reject:
                    new_co_status = "Підтверджено" if co_approve else "Відхилено"
                    try:
                        _co_update = {
                            "approval_status":   new_co_status,
                            "superadmin_id":      current_user.get("id", ""),
                            "decided_at":         datetime.now(timezone.utc).isoformat(),
                            "decision_comment":   co_decision_comment,
                        }
                        if new_co_status == "Підтверджено":
                            _co_update["head_status"] = "Очікує реакції"
                        supabase.table("closeout_requests").update(_co_update).eq("id", int(co_row.get("id"))).execute()

                        # Сповіщення керівнику ССП «до відома» (може заперечити у кабінеті)
                        if new_co_status == "Підтверджено":
                            try:
                                _co_code = clean(co_row.get("strat_code", ""))
                                _m = strat_df[strat_df["code"].astype(str).str.strip() == _co_code]
                                _dept = str(_m.iloc[0].get("resp_main", "") or _m.iloc[0].get("department", "")) if not _m.empty else ""
                                _idx = re.findall(r"\d+", _dept)
                                _idx = _idx[0] if _idx else ""
                                from config.users import get_users_by_role
                                _heads = [
                                    u for u in get_users_by_role("ssp_head").values()
                                    if str(u.get("ssp_index")) == _idx
                                ]
                                if _heads:
                                    supabase.table("closeout_requests").update(
                                        {"head_email": _heads[0].get("email", "")}
                                    ).eq("id", int(co_row.get("id"))).execute()
                                    notify_events.notify_closeout_to_head(
                                        _heads[0].get("email", ""), _heads[0].get("full_name", ""),
                                        _co_code, clean(co_row.get("period_year", "")),
                                        clean(co_row.get("period_quarter", "")),
                                        clean(co_row.get("reason", "")), clean(co_decision_comment),
                                    )
                            except Exception:
                                pass

                        load_manual_closeouts.clear()
                        write_log(
                            co_row.get("id"),
                            f"Закриття заходу: {new_co_status}",
                            "Очікує підтвердження",
                            new_co_status,
                            co_decision_comment,
                        )
                        st.success(f"Запит на закриття заходу {new_co_status.lower()}.")
                        st.rerun()
                    except Exception as e:
                        st.error("Не вдалося застосувати рішення щодо закриття заходу.")
                        st.exception(e)

# ── Розбіжності «ручне закриття vs подана заявка» + заперечення керівників ──
if is_super_admin_user(current_user) and not closeout_df.empty:
    for _col in ("dispute_status", "dispute_note", "dispute_request_id",
                 "head_status", "head_comment"):
        if _col not in closeout_df.columns:
            closeout_df[_col] = ""

    _issues = closeout_df[
        (closeout_df["approval_status"] == "Підтверджено")
        & (
            (closeout_df["dispute_status"].astype(str) == "На розгляді")
            | (closeout_df["head_status"].astype(str) == "Заперечує")
        )
    ]
    if not _issues.empty:
        st.markdown(
            '<div class="card-title" style="margin-top:18px;">⚠️ Розбіжності та заперечення щодо ручних закриттів (супер-адмін)</div>',
            unsafe_allow_html=True,
        )
        for _, _iss in _issues.iterrows():
            _iss_id = int(_iss.get("id"))
            _problems = []
            if str(_iss.get("dispute_status")) == "На розгляді":
                _problems.append(f"розбіжність із заявкою №{clean(_iss.get('dispute_request_id'))}: «{clean(_iss.get('dispute_note'))}»")
            if str(_iss.get("head_status")) == "Заперечує":
                _problems.append(f"заперечення керівника ССП: «{clean(_iss.get('head_comment'))}»")
            st.markdown(
                f"""<div class="review-box">
                    <div class="review-title">Захід {clean(_iss.get("strat_code",""))} —
                        {clean(_iss.get("period_quarter",""))} · {clean(_iss.get("period_year",""))}</div>
                    <div>{"; ".join(_problems)}</div>
                </div>""",
                unsafe_allow_html=True,
            )
            _res_comment = st.text_input("Коментар рішення", key=f"iss_comment_{_iss_id}")
            _i1, _i2 = st.columns(2)
            with _i1:
                if st.button("🔒 Лишити закриття чинним", key=f"iss_keep_{_iss_id}", use_container_width=True):
                    try:
                        supabase.table("closeout_requests").update({
                            "dispute_status": "Вирішено",
                            "decision_comment": _res_comment or clean(_iss.get("decision_comment", "")),
                        }).eq("id", _iss_id).execute()
                        _dr = _iss.get("dispute_request_id")
                        if _dr and str(_dr).strip() not in ("", "nan", "None"):
                            supabase.table("monitoring_requests").update({
                                "approval_status": "Повернуто на доопрацювання",
                                "admin_comment": f"Супер-адмін лишив чинним ручне закриття заходу. {_res_comment}",
                            }).eq("id", int(float(_dr))).execute()
                            write_log(int(float(_dr)),
                                      "Розбіжність вирішено: ручне закриття лишено чинним",
                                      "", "Повернуто на доопрацювання", _res_comment)
                        load_manual_closeouts.clear()
                        st.success("Закриття лишено чинним; заявку (якщо була) повернуто подавачу.")
                        st.rerun()
                    except Exception as e:
                        st.error("Не вдалося застосувати рішення.")
                        st.exception(e)
            with _i2:
                if st.button("↩️ Скасувати закриття (заявка йде звичайним шляхом)", key=f"iss_cancel_{_iss_id}", use_container_width=True):
                    try:
                        supabase.table("closeout_requests").update({
                            "approval_status": "Скасовано",
                            "dispute_status": "Вирішено",
                            "decision_comment": _res_comment,
                        }).eq("id", _iss_id).execute()
                        _dr = _iss.get("dispute_request_id")
                        if _dr and str(_dr).strip() not in ("", "nan", "None"):
                            write_log(int(float(_dr)),
                                      "Розбіжність вирішено: ручне закриття скасовано",
                                      "", "", _res_comment)
                        load_manual_closeouts.clear()
                        st.success("Закриття скасовано. Подана заявка проходить звичайну схему погодження.")
                        st.rerun()
                    except Exception as e:
                        st.error("Не вдалося скасувати закриття.")
                        st.exception(e)

    # Скасування будь-якого підтвердженого закриття
    _confirmed = closeout_df[closeout_df["approval_status"] == "Підтверджено"]
    if not _confirmed.empty:
        with st.expander("↩️ Відкликати підтверджене закриття"):
            _rev_options = [
                f"#{int(r['id'])} · {clean(r.get('strat_code'))} · {clean(r.get('period_quarter'))} {clean(r.get('period_year'))}"
                for _, r in _confirmed.iterrows()
            ]
            _rev_pick = st.selectbox("Оберіть закриття", _rev_options, key="revoke_closeout_pick")
            _rev_comment = st.text_input("Причина відкликання", key="revoke_closeout_comment")
            if st.button("Відкликати закриття", key="revoke_closeout_btn"):
                _rev_id = int(_rev_pick.split("·")[0].strip().lstrip("#"))
                try:
                    supabase.table("closeout_requests").update({
                        "approval_status": "Скасовано",
                        "decision_comment": _rev_comment,
                    }).eq("id", _rev_id).execute()
                    write_log(_rev_id, "Ручне закриття відкликано супер-адміном",
                              "Підтверджено", "Скасовано", _rev_comment)
                    load_manual_closeouts.clear()
                    st.success("Закриття відкликано.")
                    st.rerun()
                except Exception as e:
                    st.error("Не вдалося відкликати закриття.")
                    st.exception(e)

if not closeout_df.empty:
    with st.expander("Усі запити на закриття заходів"):
        st.dataframe(closeout_df, use_container_width=True, hide_index=True)

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# АРХІВ (заморожені знімки періодів)
# ──────────────────────────────────────────────


def load_archive_snapshots():
    try:
        resp = (
            supabase.table("archive_snapshots")
            .select("id,year,quarter,archived_by,archived_at")
            .order("archived_at", desc=True)
            .execute()
        )
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()


st.markdown(
    '<div class="card"><div class="card-title">Архів</div>',
    unsafe_allow_html=True
)

if is_admin_user(current_user) or is_super_admin_user(current_user):
    st.caption(
        "Заархівувати рік (або рік+квартал) — фіксується «заморожений» знімок поточних "
        "даних моніторингу, який надалі не змінюється навіть якщо зміниться логіка розрахунків "
        "чи живі дані. Перегляд знімків доступний на сторінці «Архів»."
    )

    arc_year_col, arc_quarter_col = st.columns(2)
    with arc_year_col:
        arc_year = st.selectbox("Рік для архівування", list(range(2026, 2035)), key="arc_year")
    with arc_quarter_col:
        arc_quarter = st.selectbox(
            "Квартал (опційно — залишити «Весь рік», щоб заархівувати рік цілком)",
            ["Весь рік", "I", "II", "III", "IV"],
            key="arc_quarter",
        )

    arc_confirm = st.checkbox("Я підтверджую архівування цього періоду", key="arc_confirm")
    arc_submit = st.button("Заархівувати", key="arc_submit")

    if arc_submit:
        if not arc_confirm:
            st.error("Підтвердіть архівування, встановивши прапорець вище.")
        else:
            quarter_value = None if arc_quarter == "Весь рік" else arc_quarter
            try:
                requests_resp = supabase.table("monitoring_requests").select("*").eq(
                    "year", str(arc_year)
                )
                if quarter_value:
                    requests_resp = requests_resp.eq("quarter", quarter_value)
                requests_data = requests_resp.execute().data or []

                snapshot_data = {
                    "measures": strat_df.to_dict(orient="records"),
                    "monitoring": requests_data,
                }

                existing_query = supabase.table("archive_snapshots").select("id").eq("year", str(arc_year))
                existing_query = existing_query.is_("quarter", "null") if quarter_value is None else existing_query.eq("quarter", quarter_value)
                existing_snapshot = existing_query.execute().data or []

                payload = {
                    "year":          str(arc_year),
                    "quarter":       quarter_value,
                    "snapshot_data": snapshot_data,
                    "archived_by":   current_user.get("email", ""),
                    "archived_at":   datetime.now(timezone.utc).isoformat(),
                }
                if existing_snapshot:
                    supabase.table("archive_snapshots").update(payload).eq(
                        "id", existing_snapshot[0]["id"]
                    ).execute()
                else:
                    supabase.table("archive_snapshots").insert(payload).execute()

                st.success(
                    f"Період {arc_quarter if quarter_value else 'весь рік'} {arc_year} заархівовано."
                )
                st.rerun()
            except Exception as e:
                st.error("Не вдалося заархівувати період. Перевірте, чи застосована міграція archive_snapshots.")
                st.exception(e)
else:
    st.info("Архівування доступне лише адміністратору або супер-адміну.")

archive_snapshots_df = load_archive_snapshots()
if not archive_snapshots_df.empty:
    with st.expander("Заархівовані періоди"):
        st.dataframe(archive_snapshots_df, use_container_width=True, hide_index=True)

st.markdown('</div>', unsafe_allow_html=True)

with st.expander("Технічна таблиця заявок"):
    st.dataframe(filtered, use_container_width=True, hide_index=True)

render_footer()
