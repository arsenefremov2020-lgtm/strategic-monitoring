import re
import streamlit as st
import pandas as pd
import plotly.express as px
from core.data_types import (
    normalise_closeout_frame,
    normalise_monitoring_frame,
    prepare_closeout_payload,
    prepare_monitoring_payload,
    split_fact_value,
    year_to_db,
)
from core.db import fetch_all, get_supabase_client
from core.errors import log_cosmetic_error, show_incident, show_warning
from core.ui import load_css, render_human_log_table, render_request_timeline
from core.notifications import render_notifications_panel
from core.config import FILE_PATH, SHEET_NAME
from core.excel_loader import read_excel_sheet
from datetime import datetime, timezone
from core.page_setup import page_setup, render_footer
from core.timeutils import now_kyiv
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
from core.stage5 import failed_notifications_last_30_days, latest_system_update
from core.archive import create_archive_snapshot, format_kyiv as format_archive_kyiv
from core.statuses import SUBMISSION_STATUS_OPTIONS
from core.validation import status_value_conflict, validate_fact_value_for_target
from config.roles import ROLE_SUPER_ADMIN
from core.access import filter_actions_for_user
from core.superadmin_routing import resolve_manual_closeout_route, can_superadmin_decide_closeout, senior_superadmin_for
from core.transitions import (
    TransitionRejected,
    approve_request_step,
    correct_locked_request,
    create_closeout,
    decide_closeout,
    return_request as atomic_return_request,
)
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
    background: #F7F9FC;
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
    color: #61708A;
    font-size: 12.5px;
    font-weight: 700;
    margin-bottom: 6px;
    letter-spacing: 0.02em;
}

/* ─── HEADER ─── */
.header-box {
    background: #ffffff;
    border: 1px solid #DCE4F0;
    border-radius: 14px;
    padding: 20px 26px;
    margin-bottom: 14px;
    box-shadow: 0 2px 12px rgba(30,50,100,0.07);
}

.header-title {
    font-size: 28px;
    font-weight: 900;
    color: #132238;
    margin-bottom: 5px;
    letter-spacing: -0.01em;
}

.header-subtitle {
    font-size: 14px;
    color: #61708A;
    line-height: 1.5;
}

.status-pill-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin-top: 11px;
}

.status-pill {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-radius: 999px;
    padding: 5px 11px;
    font-size: 12px;
    color: #61708A;
    font-weight: 600;
}

/* ─── CARDS ─── */
.card {
    background: #ffffff;
    border: 1px solid #DCE4F0;
    border-radius: 14px;
    padding: 18px 22px;
    margin: 12px 0;
    box-shadow: 0 2px 10px rgba(30,50,100,0.055);
}

.card-title {
    font-size: 17px;
    font-weight: 900;
    color: #132238;
    margin-bottom: 5px;
}

.card-subtitle {
    color: #61708A;
    font-size: 13px;
    margin-bottom: 10px;
}

/* ─── FLOW BOX ─── */
.flow-box {
    background: #F7F9FC;
    border: 1px solid #BFD3F2;
    border-left: 4px solid #4D8DFF;
    border-radius: 12px;
    padding: 13px 18px;
    margin: 12px 0;
}

.flow-title {
    font-weight: 800;
    color: #032A63;
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
    background: #EAF1FF;
    border: 1px solid #BFD3F2;
    color: #005BBB;
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
    background: #EAF1FF;
    border: 1px solid #BFD3F2;
    color: #005BBB;
    border-radius: 999px;
    padding: 5px 11px;
    font-size: 12px;
    font-weight: 700;
}

.badge-green {
    background: #E4F5EC;
    border: 1px solid #1E9E57;
    color: #118847;
}

.badge-yellow {
    background: #FDF3D8;
    border: 1px solid #F4B400;
    color: #8A6400;
}

.badge-red {
    background: #FBE5E5;
    border: 1px solid #DC4A4A;
    color: #DC4A4A;
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

.att-red    { background: #FBE5E5; border-color: #DC4A4A; }
.att-red .attention-title  { color: #DC4A4A; }
.att-red .attention-value  { color: #DC4A4A; }
.att-red .attention-note   { color: #DC4A4A; }

.att-yellow { background: #FDF3D8; border-color: #F4B400; }
.att-yellow .attention-title { color: #8A6400; }
.att-yellow .attention-value { color: #FF7A45; }
.att-yellow .attention-note  { color: #FF7A45; }

.att-blue   { background: #EAF1FF; border-color: #BFD3F2; }
.att-blue .attention-title { color: #032A63; }
.att-blue .attention-value { color: #005BBB; }
.att-blue .attention-note  { color: #032A63; }

.att-green  { background: #E4F5EC; border-color: #1E9E57; }
.att-green .attention-title { color: #0C713A; }
.att-green .attention-value { color: #118847; }
.att-green .attention-note  { color: #0C713A; }

/* ─── KPI CARDS ─── */
.admin-kpi-card {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-radius: 11px;
    padding: 11px 13px;
    min-height: 82px;
}

.admin-kpi-label {
    color: #61708A;
    font-size: 11px;
    font-weight: 700;
    margin-bottom: 5px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.admin-kpi-value {
    color: #132238;
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
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-radius: 10px;
    padding: 9px 11px;
    min-height: 64px;
}

.quality-good { border-left: 3px solid #1E9E57; background: #E4F5EC; border-color: #1E9E57; }
.quality-warn { border-left: 3px solid #FF7A45; background: #FDF3D8; border-color: #F4B400; }

.quality-label {
    color: #61708A;
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
    color: #132238;
}

/* ─── CONCLUSION BOX ─── */
.quality-conclusion {
    background: #F7F9FC;
    border: 1px solid #BFD3F2;
    border-left: 4px solid #4D8DFF;
    border-radius: 10px;
    padding: 11px 16px;
    margin-top: 4px;
    display: flex;
    align-items: center;
    gap: 12px;
}

.quality-conclusion-label {
    color: #61708A;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    min-width: 110px;
}

.quality-conclusion-value {
    font-size: 14px;
    font-weight: 800;
    color: #032A63;
}

.quality-conclusion-pct {
    font-size: 13px;
    color: #61708A;
    font-weight: 600;
    margin-left: auto;
}

/* ─── REVIEW BOX ─── */
.review-box {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-radius: 11px;
    padding: 13px 16px;
    margin: 9px 0;
    color: #61708A;
    font-size: 14px;
    line-height: 1.6;
}

.review-title {
    font-size: 14px;
    font-weight: 900;
    color: #132238;
    margin-bottom: 7px;
}

/* ─── RESOLUTION ─── */
.resolution-box {
    background: #F7F9FC;
    border: 1px solid #BFD3F2;
    border-left: 5px solid #4D8DFF;
    border-radius: 11px;
    padding: 16px 20px;
    margin: 10px 0;
}

.resolution-title {
    font-size: 13px;
    font-weight: 800;
    color: #032A63;
    margin-bottom: 9px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.resolution-text {
    color: #132238;
    font-size: 14px;
    line-height: 1.7;
}

/* ─── DECISION BOX ─── */
.decision-box {
    background: #EAF1FF;
    border: 1px solid #BFD3F2;
    border-radius: 10px;
    padding: 11px 15px;
    margin: 9px 0;
    color: #005BBB;
    font-size: 14px;
    font-weight: 700;
}

/* ─── PROGRESS / RISK BOXES ─── */
.progress-risk-box {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-radius: 11px;
    padding: 13px 15px;
    min-height: 110px;
}

.progress-risk-label {
    color: #61708A;
    font-size: 11px;
    font-weight: 700;
    margin-bottom: 7px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.progress-risk-value {
    color: #132238;
    font-size: 14px;
    line-height: 1.6;
    white-space: pre-wrap;
}

/* ─── PERSON BOX ─── */
.person-box {
    background: #EAF1FF;
    border: 1px solid #BFD3F2;
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
    color: #61708A;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.person-field-value {
    color: #005BBB;
    font-size: 14px;
    font-weight: 700;
}

/* ─── COMMENT HEADER ─── */
.comment-header {
    background: #EAF1FF;
    border: 1px solid #BFD3F2;
    border-radius: 9px;
    padding: 9px 14px;
    margin-bottom: 6px;
    color: #005BBB;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

/* ─── SELECTBOX / INPUTS ─── */
[data-testid="stMain"] div[data-testid="stSelectbox"] > div > div,
[data-testid="stMain"] div[data-testid="stTextInput"] input,
[data-testid="stMain"] div[data-testid="stTextArea"] textarea {
    background: #ffffff !important;
    border: 1.5px solid #BFD3F2 !important;
    color: #132238 !important;
    border-radius: 9px !important;
}

[data-testid="stMain"] div[data-testid="stSelectbox"] > div > div:hover,
[data-testid="stMain"] div[data-testid="stTextInput"] input:hover,
[data-testid="stMain"] div[data-testid="stTextArea"] textarea:hover {
    border-color: #4D8DFF !important;
}

[data-testid="stMain"] div[data-testid="stSelectbox"] label,
[data-testid="stMain"] div[data-testid="stTextInput"] label,
[data-testid="stMain"] div[data-testid="stTextArea"] label {
    color: #61708A !important;
    font-size: 13px !important;
    font-weight: 600 !important;
}

/* Radio */
div[data-testid="stRadio"] label {
    color: #61708A !important;
    font-size: 14px !important;
}

div[data-testid="stRadio"] > div {
    background: #F7F9FC;
    border: 1.5px solid #DCE4F0;
    border-radius: 11px;
    padding: 11px 15px;
}

/* Checkbox */
div[data-testid="stCheckbox"] label {
    color: #61708A !important;
}

/* Tabs */
button[data-baseweb="tab"] {
    color: #61708A !important;
    background: transparent !important;
    font-weight: 600 !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #005BBB !important;
    border-bottom: 2px solid #4D8DFF !important;
}

/* Metric widgets */
div[data-testid="stMetric"] {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-radius: 11px;
    padding: 11px 13px;
}

div[data-testid="stMetric"] label {
    color: #61708A !important;
}

div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: #132238 !important;
}

/* Buttons */
[data-testid="stMain"] div.stButton > button {
    border-radius: 9px;
    padding: 9px 16px;
    font-weight: 700;
    background: #EAF1FF;
    border: 1.5px solid #BFD3F2;
    color: #005BBB;
    transition: all 0.15s;
}

[data-testid="stMain"] div.stButton > button:hover {
    background: #E3EDFF;
    border-color: #BFD3F2;
}

[data-testid="stMain"] div[data-testid="stFormSubmitButton"] button {
    border-radius: 11px;
    padding: 12px 18px;
    font-weight: 900;
    background: #005BBB;
    border: none;
    color: white;
    box-shadow: 0 3px 12px rgba(37,99,235,0.35);
    transition: all 0.15s;
}

[data-testid="stMain"] div[data-testid="stFormSubmitButton"] button:hover {
    background: #005BBB;
    box-shadow: 0 5px 18px rgba(37,99,235,0.5);
}

/* Expander */
div[data-testid="stExpander"] {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-radius: 11px;
}

div[data-testid="stExpander"] summary {
    color: #005BBB !important;
    font-weight: 700;
}

/* Dataframe */
div[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
}

/* Alerts */
div[data-testid="stWarning"] {
    background: #FDF3D8;
    border: 1px solid #F4B400;
    border-radius: 9px;
    color: #8A6400;
}

div[data-testid="stInfo"] {
    background: #EAF1FF;
    border: 1px solid #BFD3F2;
    border-radius: 9px;
    color: #032A63;
}

div[data-testid="stSuccess"] {
    background: #E4F5EC;
    border: 1px solid #1E9E57;
    border-radius: 9px;
    color: #0C713A;
}

div[data-testid="stCaptionContainer"] {
    color: #61708A !important;
}

/* Progress bar */
div[data-testid="stProgressBar"] > div {
    background: #DCE4F0;
    border-radius: 999px;
}

div[data-testid="stProgressBar"] > div > div {
    background: #005BBB;
    border-radius: 999px;
}

/* Footer */
.footer {
    text-align: center;
    color: #8A96A8;
    font-size: 12px;
    margin-top: 48px;
    padding: 18px 0 10px 0;
    border-top: 1px solid #DCE4F0;
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
    return (now_kyiv() - dt).days


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
    df = monitoring_data.load_monitoring_requests_live()
    if not df.empty and "submitted_at" in df.columns:
        df = df.sort_values("submitted_at", ascending=False)
    return df


def load_logs(request_id):
    rows = fetch_all(
        "monitoring_logs",
        "*",
        filters=[("eq", "request_id", int(request_id))],
        order=("changed_at", True),
    )
    return pd.DataFrame(rows)


def load_versions(request_id):
    """Версії заявки — для розширення історії фактом та описом прогресу."""
    try:
        rows = fetch_all(
            "monitoring_request_versions",
            "*",
            filters=[("eq", "request_id", int(request_id))],
            order=("created_at", False),
        )
        return normalise_monitoring_frame(pd.DataFrame(rows))
    except Exception:
        return pd.DataFrame()


def render_requests_status_viewer(requests_frame):
    """ТЗ-правка (09.07.2026, п.3): «Перегляд статусу заявок».

    Випадний список усіх заявок за застосованими фільтрами (спершу — ті,
    що ще НЕ закриті) з чітким відображенням: статус, поточна ланка схеми,
    скільки днів на цьому кроці. Лише перегляд — без дій.
    """
    st.markdown(
        '<div class="card"><div class="card-title">Перегляд статусу заявок</div>'
        '<div class="card-subtitle">Стан будь-якої заявки за застосованими '
        'фільтрами: на якому етапі схеми погодження вона зараз перебуває. '
        'Лише перегляд — рішення ухвалюються у «Виборі заявки» вище, коли '
        'настає ваша ланка.</div>',
        unsafe_allow_html=True,
    )
    if requests_frame is None or requests_frame.empty:
        st.info("За застосованими фільтрами заявок немає.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    _mode = st.radio(
        "Які заявки показати",
        ["Ще не закриті (у процесі)", "Закриті (погоджені)", "Усі"],
        horizontal=True,
        key="status_viewer_mode_v19",
    )
    _frame = requests_frame.copy()
    _appr = _frame["approval_status"].astype(str).str.strip()
    if _mode.startswith("Ще не закриті"):
        _frame = _frame[_appr != "Погоджено"]
    elif _mode.startswith("Закриті"):
        _frame = _frame[_appr == "Погоджено"]
    if _frame.empty:
        st.info("У цій категорії заявок немає.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    _opts = [
        f"ID {r['id']} | ССП {r['department']} | {r['strat_code']} | "
        f"{r['year']} {r['quarter']} кв. | {clean(r['approval_status'])}"
        for _, r in _frame.iterrows()
    ]
    _pick = st.selectbox(
        "Оберіть заявку для перегляду статусу", _opts,
        key="status_viewer_pick_v19",
    )
    _pid = int(_pick.split("|")[0].replace("ID", "").strip())
    _prow = _frame[_frame["id"].astype(int) == _pid].iloc[0]

    _p_appr = clean(_prow.get("approval_status"))
    _p_chain = schemes.parse_chain(_prow.get("approval_chain"))
    _p_stage = schemes.parse_stage(_prow.get("chain_stage"))
    _ts = pd.to_datetime(clean(_prow.get("submitted_at")), errors="coerce", utc=True)
    _days = ""
    if pd.notna(_ts):
        _days = f" · подано {max(0, (now_kyiv() - _ts.to_pydatetime()).days)} дн. тому"

    if _p_appr == "Погоджено":
        _where = "✅ Погодження завершено — заявка закрита"
        _color = ("#E4F5EC", "#1E9E57", "#0C713A")
    elif _p_appr == "Повернуто на доопрацювання":
        _where = "↩️ У подавача — повернута на доопрацювання"
        _color = ("#FDF3D8", "#FF7A45", "#FF7A45")
    elif _p_chain:
        _st_cur = schemes.current_stage(_p_chain, _p_stage)
        _who = clean((_st_cur or {}).get("name", "")) or clean((_st_cur or {}).get("email", ""))
        _where = (f"⏳ Зараз на ланці: {clean((_st_cur or {}).get('label',''))}"
                  + (f" — {_who}" if _who else ""))
        _color = ("#EAF1FF", "#BFD3F2", "#032A63")
    else:
        _where = "⏳ На розгляді координатора"
        _color = ("#EAF1FF", "#BFD3F2", "#032A63")

    st.markdown(
        f'<div style="background:{_color[0]};border:1px solid {_color[1]};'
        f'border-radius:10px;padding:10px 14px;font-size:13px;font-weight:800;'
        f'color:{_color[2]};">{_where}{_days}</div>',
        unsafe_allow_html=True,
    )
    if _p_chain:
        _route_bits = []
        for _i, _stg in enumerate(_p_chain):
            _done = _i < _p_stage or _p_appr == "Погоджено"
            _cur = (_i == _p_stage and _p_appr != "Погоджено")
            _ic = "✅" if _done else ("🔵" if _cur else "⚪")
            _route_bits.append(f"{_ic} {clean(_stg.get('label',''))}")
        st.caption("Маршрут: " + "  →  ".join(_route_bits))
    st.markdown('</div>', unsafe_allow_html=True)


def _actor_identity(role_label):
    """Повний підпис дії для журналу: роль + ПІБ + email поточного користувача."""
    try:
        name = str((current_user or {}).get("full_name", "")).strip()
        email = str((current_user or {}).get("email", "")).strip()
    except Exception as exc:
        log_cosmetic_error("Формування підпису користувача в адмініструванні", exc)
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
        recommendation = "Можна підтверджувати"
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
                if end_dt.date() < now_kyiv().date():
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
        except Exception as exc:
            log_cosmetic_error("Перевірка простроченого терміну заявки", exc)

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
    if recommendation == "Можна підтверджувати":
        warn_texts = [w["text"] for w in analysis["warnings"]]
        warn_clause = ""
        if warn_texts:
            warn_clause = (
                f" Разом із тим, звертаємо увагу на таке: {'; '.join(warn_texts)}. "
                f"Це підлягає врахуванню при підтвердженні та подальшому моніторингу."
            )
        return (
            header
            + pf_clause
            + f"Статус виконання — «{status}». "
            + (f"Прогрес: {progress}. " if has_value(progress) else "")
            + "Подані відомості визнано достатніми для погодження."
            + warn_clause
            + " Передаємо на підтвердження керівнику підрозділу."
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
        # ТЗ-правка (09.07.2026, п.3): категорії ВЗАЄМОВИКЛЮЧНІ — кожна
        # заявка потрапляє рівно в одну картку, без дублювання.
        "long_waiting": data[
            (data["approval_status"].astype(str).isin(schemes.ALL_WAITING_STATUSES)) &
            (data["days_waiting"].fillna(0) > 5)
        ].copy(),
        "waiting": data[
            (data["approval_status"].astype(str).isin(schemes.ALL_WAITING_STATUSES)) &
            (data["days_waiting"].fillna(0) <= 5)
        ].copy(),
        "not_counted": data.iloc[0:0].copy(),
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

_stage5_latest_at, _stage5_latest_label = latest_system_update()

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
            <div class="status-pill">● Дані востаннє оновлено: {_stage5_latest_label}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.caption(f"Дані востаннє оновлено: {_stage5_latest_label}")

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

# ТЗ-правка (09.07.2026, п.3): відсутність заявок НЕ вимикає сторінку —
# режим «Ручне закриття заходів» працює із заходами стратегічної матриці
# і має бути доступним навіть за порожнього реєстру заявок.
_no_requests_at_all = df.empty

required_cols = [
    "id", "department", "year", "quarter", "approval_status", "status",
    "strat_code", "responsible_person", "phone", "email",
    "numeric_value", "progress_text", "risks", "npa_link",
    "file_names", "file_urls", "admin_comment", "approval_chain",
    "object_kind", "final_locked", "start_date", "end_date", "submitted_at"
]
for col in required_cols:
    if col not in df.columns:
        df[col] = ""

df = filter_requests_for_user(
    df,
    current_user,
    ssp_columns=["department"]
)

# ТЗ-правка (09.07.2026, п.3): панель «Сповіщення погодження» прибрано з адмінки.

# ──────────────────────────────────────────────
# РЕЖИМ РОБОТИ АДМІНІСТРУВАННЯ
# ──────────────────────────────────────────────

admin_work_mode = st.radio(
    "Режим адміністрування",
    ["Основний режим координатора", "Ручне закриття заходів"],
    horizontal=True,
    key="admin_work_mode",
)

# І2: єдиний реєстр недоставлених листів за останні 30 днів.
with st.expander("Розсилка: недоставлені листи", expanded=False):
    _failed_mail = failed_notifications_last_30_days()
    if _failed_mail.empty:
        st.success("Усі листи за останні 30 днів доставлено.")
    else:
        st.warning(f"Недоставлених листів за останні 30 днів: {len(_failed_mail)}")
        st.dataframe(_failed_mail, use_container_width=True, hide_index=True)

# З1–З5: ручне створення незмінного архівного знімка доступне лише супер-адміну.
if is_super_admin_user(current_user):
    with st.expander("Архівний знімок · ТЕСТОВИЙ РЕЖИМ", expanded=False):
        st.caption(
            "Знімок містить повну накопичену структуру, заявки, усі версії, "
            "розрахункові складові МіО та повний журнал дій. Після створення "
            "змінити або видалити його неможливо."
        )

        try:
            _archive_rows = fetch_all(
                "archive_snapshots",
                (
                    "id,archived_at,archived_by,snapshot_type,reason,replacement_reason,"
                    "replaces_snapshot_id,coverage_label,request_count,measure_count,log_count"
                ),
                order=("archived_at", True),
            )
        except Exception as _archive_list_exc:
            show_warning(
                "Перелік архівних знімків тимчасово недоступний.",
                _archive_list_exc,
                "Читання archive_snapshots в адмініструванні",
            )
            _archive_rows = []

        _archive_option_ids = [None] + [int(row["id"]) for row in _archive_rows if row.get("id") is not None]
        _archive_labels = {None: "Не замінює попередній знімок"}
        for _archive_row in _archive_rows:
            try:
                _archive_id = int(_archive_row.get("id"))
            except (TypeError, ValueError):
                continue
            _archive_labels[_archive_id] = (
                f"Знімок №{_archive_id} від {format_archive_kyiv(_archive_row.get('archived_at'))}"
                f" · {_archive_row.get('coverage_label') or 'усі доступні періоди'}"
            )

        _archive_reason = st.text_area(
            "Причина створення",
            key="stage6_archive_reason",
            placeholder="Наприклад: перед зимовою актуалізацією заходів",
        )
        _archive_replaces = st.selectbox(
            "Знімок, який замінюється (за потреби)",
            options=_archive_option_ids,
            format_func=lambda value: _archive_labels.get(value, str(value)),
            key="stage6_archive_replaces",
        )
        _archive_replacement_reason = ""
        if _archive_replaces is not None:
            _archive_replacement_reason = st.text_area(
                "Причина заміни",
                key="stage6_archive_replacement_reason",
                placeholder="Опишіть помилку або уточнення, через яке потрібен новий знімок.",
            )

        _archive_confirm_data = st.checkbox(
            "Я підтверджую, що перевірив(ла) живі дані перед архівацією.",
            key="stage6_archive_confirm_data",
        )
        _archive_confirm_lock = st.checkbox(
            "Я розумію, що після створення цей знімок неможливо змінити або видалити.",
            key="stage6_archive_confirm_lock",
        )

        if st.button(
            "Створити архівний знімок зараз",
            type="primary",
            use_container_width=True,
            key="stage6_create_archive_snapshot",
        ):
            _archive_errors = []
            if not _archive_reason.strip():
                _archive_errors.append("Заповніть поле «Причина створення».")
            if _archive_replaces is not None and not _archive_replacement_reason.strip():
                _archive_errors.append("Для знімка-заміни заповніть поле «Причина заміни».")
            if not _archive_confirm_data or not _archive_confirm_lock:
                _archive_errors.append("Потрібні обидва підтвердження перед створенням знімка.")

            if _archive_errors:
                for _archive_error in _archive_errors:
                    st.error(_archive_error)
            else:
                try:
                    with st.spinner("Створюємо повний незмінний архівний знімок…"):
                        _archive_result = create_archive_snapshot(
                            supabase,
                            actor=current_user,
                            reason=_archive_reason.strip(),
                            snapshot_type="manual",
                            replaces_snapshot_id=_archive_replaces,
                            replacement_reason=_archive_replacement_reason.strip(),
                        )
                    if _archive_result.get("success"):
                        st.success(
                            f"Архівний знімок №{_archive_result.get('snapshot_id')} створено. "
                            "Він доступний на сторінці «Архів»."
                        )
                    else:
                        st.error(
                            _archive_result.get("message")
                            or "Не вдалося створити архівний знімок."
                        )
                except Exception as _archive_create_exc:
                    show_incident(
                        _archive_create_exc,
                        context="Створення повного архівного знімка",
                    )

if admin_work_mode == "Ручне закриття заходів":
    # ──────────────────────────────────────────────
    # ЗАКРИТТЯ ЗАХОДУ ВРУЧНУ (admin → super_admin)
    # ──────────────────────────────────────────────


    def load_closeout_requests():
        rows = fetch_all(
            "closeout_requests",
            "*",
            order=("requested_at", True),
        )
        return normalise_closeout_frame(pd.DataFrame(rows))


    _closeout_scope_df = filter_actions_for_user(
        strat_df,
        current_user,
        executor_columns=["resp_main", "resp_co_1", "Головний\nвиконавець", "Співвиконавець"],
    )
    measure_codes = _closeout_scope_df[_closeout_scope_df["code"].astype(str).str.count(r"\.") >= 3]["code"].astype(str).tolist() \
        if "code" in _closeout_scope_df.columns else []

    st.markdown(
        '<div class="card"><div class="card-title">Закриття заходу вручну</div>',
        unsafe_allow_html=True
    )

    if is_admin_user(current_user) or is_super_admin_user(current_user):
        with st.form("closeout_request_form"):
            st.caption(
                "Подати запит на ручне закриття заходу за період. "
                "Після підтвердження супер-адміном ручне закриття вважається офіційними даними "
                "та рахується як виконання, але до реакції керівника ССП відображається фіолетовим."
            )
            co_code = st.selectbox("Код заходу", measure_codes)
            _co_measure = _closeout_scope_df[
                _closeout_scope_df["code"].astype(str).str.strip() == str(co_code).strip()
            ]
            _co_measure_row = _co_measure.iloc[0] if not _co_measure.empty else pd.Series(dtype=object)
            _co_unit = clean(_co_measure_row.get("unit", ""))
            _co_indicator = clean(_co_measure_row.get("indicator", ""))
            _co_object_name = clean(_co_measure_row.get("name", ""))
            _co_department = clean(
                _co_measure_row.get("resp_main", "")
                or _co_measure_row.get("department", "")
            )
            _co_targets = " ".join(
                clean(_co_measure_row.get(column, ""))
                for column in ("target_2026", "target_2027", "target_2028")
            ).lower()
            _co_boolean_fact = (
                any(token in _co_unit.lower() for token in ("так/ні", "так / ні", "наявн", "булев"))
                or _co_targets.strip() in {"так", "ні", "так ні", "ні так"}
            )

            co_scope_col, co_year_col, co_quarter_col = st.columns(3)
            with co_scope_col:
                co_scope = st.selectbox("Масштаб закриття", ["Квартал", "Рік"])
            with co_year_col:
                co_year = st.selectbox("Рік", list(range(2026, 2035)))
            with co_quarter_col:
                co_quarter = st.selectbox("Квартал (якщо масштаб — квартал)", ["I", "II", "III", "IV"])

            co_fact_status = st.selectbox(
                "Статус виконання",
                list(SUBMISSION_STATUS_OPTIONS),
            )
            if _co_boolean_fact:
                co_fact_value = st.selectbox("Фактичне значення", ["так", "ні"])
            else:
                co_fact_value = st.text_input(
                    "Фактичне значення (число)",
                    help=f"Одиниця виміру: {_co_unit or 'не зазначена'}",
                )
            co_fact_progress = st.text_area(
                "Пояснення фактичних даних",
                help="Обов'язково: що саме досягнуто і на підставі яких відомостей.",
            )
            co_reason = st.text_area(
                "Підстава для ручного закриття",
                help="Внутрішня інформація, комунікація або інший звітний документ.",
            )
            co_npa = st.text_area(
                "Посилання на НПА / джерела (по одному в рядку, опційно)",
                placeholder="https://zakon.rada.gov.ua/...\nhttps://docs.google.com/...",
            )
            co_evidence = st.text_area("Ризики / додаткові пояснення (опційно)")
            co_submit = st.form_submit_button(
                "Закрити вручну" if is_super_admin_user(current_user)
                else "Надіслати на підтвердження супер-адміну"
            )

        if co_submit:
            _fact_number, _fact_text = split_fact_value(co_fact_value)
            _form_errors = []
            if not co_reason.strip():
                _form_errors.append("Заповніть підставу для ручного закриття.")
            if not co_fact_progress.strip():
                _form_errors.append("Заповніть пояснення фактичних даних.")
            if not clean(co_fact_value):
                _form_errors.append("Зазначте фактичне значення.")
            elif not _co_boolean_fact and _fact_number is None:
                _form_errors.append("Фактичне значення цього заходу має бути числом.")

            if _form_errors:
                for _message in _form_errors:
                    st.error(_message)
            else:
                try:
                    _route = resolve_manual_closeout_route(current_user)
                    _is_super = is_super_admin_user(current_user)
                    _payload = {
                        "strat_code": co_code,
                        "period_year": str(co_year),
                        "period_quarter": "Рік" if co_scope == "Рік" else co_quarter,
                        "scope": co_scope,
                        "npa_links": co_npa.strip(),
                        "admin_id": current_user.get("full_name", "") or current_user.get("id", ""),
                        "admin_email": current_user.get("email", ""),
                        "reason": co_reason.strip(),
                        "evidence_note": co_evidence.strip(),
                        "fact_status": co_fact_status,
                        "fact_value": co_fact_value,
                        "fact_progress_text": co_fact_progress.strip(),
                        "department": _co_department,
                        "object_name": _co_object_name,
                        "indicator_name": _co_indicator,
                        "approval_status": "Підтверджено" if _is_super else "Очікує підтвердження",
                        **({
                            "superadmin_id": current_user.get("id", ""),
                            "decided_at": datetime.now(timezone.utc).isoformat(),
                            "head_status": "Очікує реакції",
                        } if _is_super else {}),
                        **_route,
                    }
                    _payload = prepare_closeout_payload(_payload)
                    create_closeout(payload=_payload, user=current_user)
                    st.success(
                        "Захід закрито вручну; фактичні дані записано в моніторинг."
                        if _is_super else
                        "Запит на закриття заходу надіслано на підтвердження відповідальному супер-адміну."
                    )
                    load_manual_closeouts.clear()
                    monitoring_data.invalidate_monitoring_cache()
                    st.rerun()
                except TransitionRejected as exc:
                    st.error(exc.message)
                except Exception as exc:
                    show_incident(exc, context="Атомарне подання запиту на ручне закриття заходу")
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
                            <div><b>Статус виконання:</b> {clean(co_row.get("fact_status",""))}</div>
                            <div><b>Фактичне значення:</b> {clean(co_row.get("fact_numeric_value","")) or clean(co_row.get("fact_value_text",""))}</div>
                            <div><b>Пояснення фактичних даних:</b> {clean(co_row.get("fact_progress_text",""))}</div>
                            <div><b>Ризики / додаткові пояснення:</b> {clean(co_row.get("evidence_note",""))}</div>
                            <div><b>Подано:</b> {clean(co_row.get("admin_email",""))} о {clean(co_row.get("requested_at",""))}</div>
                            <div><b>Маршрутизація:</b> {clean(co_row.get("routing_note", ""))}</div>
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
                            _co_code = clean(co_row.get("strat_code", ""))
                            _head_user = None
                            if new_co_status == "Підтверджено":
                                try:
                                    _m = strat_df[strat_df["code"].astype(str).str.strip() == _co_code]
                                    _dept = str(
                                        _m.iloc[0].get("resp_main", "")
                                        or _m.iloc[0].get("department", "")
                                    ) if not _m.empty else ""
                                    _idx = re.findall(r"\d+", _dept)
                                    _idx = _idx[0] if _idx else ""
                                    from config.users import get_users_by_role
                                    _heads = [
                                        u for u in get_users_by_role("ssp_head").values()
                                        if str(u.get("ssp_index")) == _idx
                                    ]
                                    _head_user = _heads[0] if _heads else None
                                except Exception as lookup_exc:
                                    show_warning(
                                        "Рішення буде збережено, але не вдалося визначити керівника ССП для листа.",
                                        lookup_exc,
                                        "Визначення керівника ССП для ручного закриття",
                                    )

                            decide_closeout(
                                closeout_id=int(co_row.get("id")),
                                expected_status="Очікує підтвердження",
                                new_status=new_co_status,
                                decision_comment=clean(co_decision_comment),
                                head_email=clean((_head_user or {}).get("email", "")),
                                user=current_user,
                            )

                            if new_co_status == "Підтверджено" and _head_user:
                                try:
                                    notify_events.notify_closeout_to_head(
                                        _head_user.get("email", ""),
                                        _head_user.get("full_name", ""),
                                        _co_code,
                                        clean(co_row.get("period_year", "")),
                                        clean(co_row.get("period_quarter", "")),
                                        clean(co_row.get("reason", "")),
                                        clean(co_decision_comment),
                                    )
                                except Exception as notify_exc:
                                    show_warning(
                                        "Закриття підтверджено, але керівнику ССП не відправлено миттєвий лист.",
                                        notify_exc,
                                        "Email керівнику ССП після ручного закриття",
                                    )

                            load_manual_closeouts.clear()
                            st.success(f"Запит на закриття заходу {new_co_status.lower()}.")
                            monitoring_data.invalidate_monitoring_cache()
                            st.rerun()
                        except TransitionRejected as exc:
                            st.error(exc.message)
                        except Exception as exc:
                            show_incident(exc, context="Атомарне рішення щодо ручного закриття")

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
                                _dr_id = int(float(_dr))
                                _dr_state_response = (
                                    supabase.table("monitoring_requests")
                                    .select("approval_status,chain_stage")
                                    .eq("id", _dr_id)
                                    .limit(1)
                                    .execute()
                                )
                                _dr_state = (_dr_state_response.data or [{}])[0]
                                _return_comment = (
                                    "Супер-адмін лишив чинним ручне закриття заходу. "
                                    + (clean(_res_comment) or "Розбіжність вирішено на користь ручного закриття.")
                                )
                                atomic_return_request(
                                    request_id=_dr_id,
                                    expected_status=clean(_dr_state.get("approval_status")),
                                    expected_chain_stage=int(_dr_state.get("chain_stage") or 0),
                                    new_status="Повернуто на доопрацювання",
                                    new_chain_stage=0,
                                    comment=_return_comment,
                                    action="Розбіжність вирішено: ручне закриття лишено чинним",
                                    user=current_user,
                                    created_by="Супер-адмін / вирішення розбіжності",
                                )
                            load_manual_closeouts.clear()
                            st.success("Закриття лишено чинним; заявку (якщо була) повернуто подавачу.")
                            monitoring_data.invalidate_monitoring_cache()
                            st.rerun()
                        except Exception as exc:
                            show_incident(exc, context="Збереження рішення щодо розбіжності ручного закриття")
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
                            monitoring_data.invalidate_monitoring_cache()
                            st.rerun()
                        except Exception as exc:
                            show_incident(exc, context="Скасування ручного закриття під час вирішення розбіжності")

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
                        monitoring_data.invalidate_monitoring_cache()
                        st.rerun()
                    except Exception as exc:
                        show_incident(exc, context="Відкликання підтвердженого ручного закриття")

    if not closeout_df.empty:
        with st.expander("Усі запити на закриття заходів"):
            st.dataframe(closeout_df, use_container_width=True, hide_index=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # ──────────────────────────────────────────────
    # АРХІВ (заморожені знімки періодів)
    # ──────────────────────────────────────────────



    render_footer()
    st.stop()

if _no_requests_at_all or df.empty:
    st.warning(
        "Поки що немає заявок, доступних за вашими закріпленими ССП. "
        "Режим «Ручне закриття заходів» доступний через перемикач вище."
    )
    render_footer()
    st.stop()


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
_ret = len(attention["returned"])
_appr= len(attention["approved"])

st.markdown(
    '<div class="attention-grid">'
    + _att("Погоджено",                _appr, "Пройшли всю схему погодження",          "att-green")
    + _att("На розгляді",              _wt,   "У процесі погодження (до 5 днів)",      "att-yellow" if _wt   else "att-green")
    + _att("На розгляді понад 5 днів", _lw,   "За легендою вважаються «Не враховано»", "att-red"    if _lw   else "att-green")
    + _att("На доопрацюванні",         _ret,  "Повернуті для виправлення",             "att-blue"   if _ret  else "att-green")
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
    t1, t2, t3, t4 = st.tabs([
        "Погоджено",
        "На розгляді",
        "На розгляді понад 5 днів",
        "На доопрацюванні",
    ])
    with t1: sort_and_show(attention["approved"])
    with t2: sort_and_show(attention["waiting"])
    with t3: sort_and_show(attention["long_waiting"])
    with t4: sort_and_show(attention["returned"])

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ІНФОГРАФІКА
# ──────────────────────────────────────────────

st.markdown('<div class="card"><div class="card-title">Інфографіка</div>', unsafe_allow_html=True)

# ТЗ-правка (09.07.2026, п.3): категорії інфографіки взаємовиключні —
# кожна заявка облікована рівно один раз.
status_counts = {
    "Погоджено":                len(attention["approved"]),
    "На розгляді":              len(attention["waiting"]),
    "На розгляді понад 5 днів": len(attention["long_waiting"]),
    "На доопрацюванні":         len(attention["returned"]),
}

chart_df = pd.DataFrame({
    "Статус":    list(status_counts.keys()),
    "Кількість": list(status_counts.values())
})
chart_df = chart_df[chart_df["Кількість"] > 0]

if not chart_df.empty:
    color_map = {
        "На розгляді понад 5 днів": "#DC4A4A",
        "На розгляді":              "#FF7A45",
        "Не враховано":             "#FF7A45",
        "На доопрацюванні":         "#4D8DFF",
        "Погоджено":                "#1E9E57",
    }
    fig = px.pie(
        chart_df, names="Статус", values="Кількість", hole=0.48,
        title="Розподіл заявок за статусом виконання",
        color="Статус", color_discrete_map=color_map
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#61708A",
        title_font_color="#132238",
        legend=dict(font=dict(color="#61708A"), bgcolor="rgba(0,0,0,0)")
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
         "Повернуто на доопрацювання", "Очікує: Керівник ССП", "Погоджено"],
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

# ТЗ Заг.1: фільтри спрацьовують ТІЛЬКИ після кнопки «Застосувати обрані
# параметри»; кнопка «Скинути параметри» повертає стандартний відбір.
_adm_flt_defaults = {
    "ssp": "Усі", "year": "Усі", "quarter": "Усі",
    "approval": "Активні до розгляду", "quick": "Усі заявки", "search": "",
}
if "admin_filters_applied_v19" not in st.session_state:
    st.session_state["admin_filters_applied_v19"] = _adm_flt_defaults.copy()
_bt1, _bt2 = st.columns([2, 1])
with _bt1:
    if st.button("Застосувати обрані параметри", type="primary",
                 use_container_width=True, key="admin_filters_apply_v19"):
        st.session_state["admin_filters_applied_v19"] = {
            "ssp": selected_ssp, "year": selected_year,
            "quarter": selected_quarter, "approval": selected_approval_status,
            "quick": quick_filter, "search": search_query,
        }
with _bt2:
    if st.button("Скинути параметри", use_container_width=True,
                 key="admin_filters_reset_v19"):
        st.session_state["admin_filters_applied_v19"] = _adm_flt_defaults.copy()
        st.rerun()
_adm_flt = st.session_state["admin_filters_applied_v19"]
selected_ssp = _adm_flt["ssp"]
selected_year = _adm_flt["year"]
selected_quarter = _adm_flt["quarter"]
selected_approval_status = _adm_flt["approval"]
quick_filter = _adm_flt["quick"]
search_query = _adm_flt["search"]
st.caption(
    f"Застосовано: ССП — {selected_ssp} · Рік — {selected_year} · "
    f"Квартал — {selected_quarter} · Статус — {selected_approval_status} · "
    f"Швидкий фільтр — {quick_filter}"
    + (f" · Пошук — «{search_query}»" if search_query else "")
)

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
         "Повернуто на доопрацювання", "Очікує: Керівник ССП"]
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

# ──────────────────────────────────────────────
# СУПЕР-АДМІН: КОРИГУВАННЯ ОСТАТОЧНО ЗАКРИТИХ ЗАЯВОК
# ──────────────────────────────────────────────
# Цей блок навмисно не залежить від фільтра «Активні до розгляду» та від
# черги погодження. Остаточно закриті заявки вже не можуть потрапити до
# черги, тому для них потрібен окремий реєстр і окремий вибір.
if is_super_admin_user(current_user):
    st.markdown(
        '<div class="card"><div class="card-title">🛠 Коригування остаточно закритої заявки</div>'
        '<div class="card-subtitle">Доступно лише супер-адміну. Коригуються тільки звітні дані; '
        'статус погодження, маршрут і ознака final_locked не змінюються. Кожне коригування '
        'потребує обґрунтування та створює версії до і після зміни.</div>',
        unsafe_allow_html=True,
    )

    _correction_notice = st.session_state.pop("sa_locked_correction_notice", None)
    if _correction_notice:
        st.success(_correction_notice)

    def _is_true_flag(value) -> bool:
        if isinstance(value, bool):
            return value
        return clean(value).lower() in {"true", "1", "yes", "так"}

    if "final_locked" in df.columns:
        _locked_df = df[
            df["final_locked"].map(_is_true_flag)
            & df["approval_status"].astype(str).str.strip().eq("Погоджено")
        ].copy()
    else:
        _locked_df = df.iloc[0:0].copy()

    _locked_search = st.text_input(
        "Пошук серед остаточно закритих заявок",
        key="sa_locked_requests_search",
        placeholder="ID, код заходу, ССП або відповідальна особа",
    )
    if _locked_search.strip() and not _locked_df.empty:
        _locked_sq = _locked_search.strip().lower()
        _locked_df = _locked_df[
            _locked_df["id"].astype(str).str.lower().str.contains(_locked_sq, na=False)
            | _locked_df["strat_code"].astype(str).str.lower().str.contains(_locked_sq, na=False)
            | _locked_df["department"].astype(str).str.lower().str.contains(_locked_sq, na=False)
            | _locked_df["responsible_person"].astype(str).str.lower().str.contains(_locked_sq, na=False)
        ]

    st.caption(f"Остаточно закритих заявок для коригування: {len(_locked_df)}")

    if _locked_df.empty:
        st.info("Остаточно погоджених і заблокованих заявок за цим пошуком немає.")
    else:
        if "submitted_at" in _locked_df.columns:
            _locked_df = _locked_df.sort_values("submitted_at", ascending=False)

        _locked_labels = {
            int(row["id"]): (
                f"ID {int(row['id'])} | {clean(row.get('strat_code'))} | "
                f"{clean(row.get('year'))} {clean(row.get('quarter'))} квартал | "
                f"ССП {clean(row.get('department'))} | {clean(row.get('responsible_person'))}"
            )
            for _, row in _locked_df.iterrows()
        }
        _locked_request_id = st.selectbox(
            "Оберіть остаточно закриту заявку",
            options=list(_locked_labels),
            format_func=lambda request_id: _locked_labels[request_id],
            key="sa_locked_request_id",
        )
        _locked_row = _locked_df[
            _locked_df["id"].astype(int).eq(int(_locked_request_id))
        ].iloc[0]

        _locked_code = clean(_locked_row.get("strat_code"))
        _locked_measure_info = strat_df[
            strat_df["code"].astype(str).str.strip().str.rstrip(".")
            == _locked_code.rstrip(".")
        ].copy()
        _locked_indicator_name = clean(_locked_row.get("indicator_name"))
        if (
            clean(_locked_row.get("object_kind")) == "indicator"
            and _locked_indicator_name
            and "indicator" in _locked_measure_info.columns
        ):
            _locked_indicator_match = _locked_measure_info[
                _locked_measure_info["indicator"].astype(str).str.strip().str.casefold()
                == _locked_indicator_name.casefold()
            ]
            if not _locked_indicator_match.empty:
                _locked_measure_info = _locked_indicator_match

        _locked_mi = _locked_measure_info.iloc[0] if not _locked_measure_info.empty else None
        try:
            _locked_year = int(str(_locked_row.get("year") or "").strip())
        except (TypeError, ValueError):
            _locked_year = None
        _locked_target = (
            clean(_locked_mi.get(f"target_{_locked_year}", ""))
            if _locked_mi is not None and _locked_year is not None
            else ""
        )
        _locked_future_targets = (
            [
                _locked_mi.get(f"target_{year}", "")
                for year in range(_locked_year + 1, 2035)
            ]
            if _locked_mi is not None and _locked_year is not None
            else []
        )

        st.markdown(
            f"""
            <div class="review-box">
                <div class="review-title">Заявка ID {int(_locked_request_id)} · захід {_esc(clean(_locked_row.get('strat_code')))}</div>
                <div><b>Період:</b> {_esc(clean(_locked_row.get('year')))} · {_esc(clean(_locked_row.get('quarter')))} квартал</div>
                <div><b>ССП:</b> {_esc(clean(_locked_row.get('department')))}</div>
                <div><b>Відповідальна особа:</b> {_esc(clean(_locked_row.get('responsible_person')))}</div>
                <div><b>Поточний статус виконання:</b> {_esc(clean(_locked_row.get('status')))}</div>
                <div><b>Поточне фактичне значення:</b> {_esc(clean(_locked_row.get('numeric_value')))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        _locked_status_options = [
            "Виконано",
            "Частково виконано",
            "Не виконано",
            "Не настав час",
            "Втратило актуальність",
        ]
        _locked_current_status = clean(_locked_row.get("status"))
        _locked_status_index = (
            _locked_status_options.index(_locked_current_status)
            if _locked_current_status in _locked_status_options
            else 0
        )

        with st.expander("✏️ Відкрити форму коригування", expanded=False):
            with st.form(f"sa_locked_correction_form_{int(_locked_request_id)}"):
                sa_locked_status = st.selectbox(
                    "Статус виконання",
                    _locked_status_options,
                    index=_locked_status_index,
                )
                sa_locked_value = st.text_input(
                    "Фактичне значення",
                    value=clean(_locked_row.get("numeric_value")),
                    help="Можна ввести число або текстове значення, наприклад «так» чи «ні».",
                )
                sa_locked_progress = st.text_area(
                    "Опис прогресу",
                    value=clean(_locked_row.get("progress_text")),
                    height=120,
                )
                sa_locked_risks = st.text_area(
                    "Ризики / проблеми / відхилення",
                    value=clean(_locked_row.get("risks")),
                    height=100,
                )
                sa_locked_npa = st.text_input(
                    "Посилання на НПА",
                    value=clean(_locked_row.get("npa_link")),
                )
                sa_locked_reason = st.text_area(
                    "Обґрунтування коригування",
                    height=110,
                    placeholder=(
                        "Наприклад: надійшов уточнений звіт від ССП; попередні дані "
                        "містили технічну помилку."
                    ),
                )
                sa_locked_submit = st.form_submit_button(
                    "Підтвердити коригування закритої заявки",
                    type="primary",
                    use_container_width=True,
                )

            if sa_locked_submit:
                sa_locked_errors = []
                if not clean(sa_locked_reason):
                    sa_locked_errors.append("Обґрунтування коригування є обов'язковим.")

                sa_locked_unit = clean(_locked_mi.get("unit")) if _locked_mi is not None else ""
                if clean(sa_locked_value):
                    sa_locked_value_ok, sa_locked_value_error = validate_fact_value_for_target(
                        sa_locked_value,
                        sa_locked_unit,
                        _locked_target,
                        _locked_future_targets,
                    )
                    if not sa_locked_value_ok:
                        sa_locked_errors.append(sa_locked_value_error)

                sa_locked_conflict_error = status_value_conflict(
                    sa_locked_status,
                    sa_locked_value,
                    _locked_target,
                    sa_locked_unit,
                    _locked_code,
                    _locked_future_targets,
                )
                if sa_locked_conflict_error:
                    sa_locked_errors.append(sa_locked_conflict_error)

                if sa_locked_errors:
                    for sa_locked_error in sa_locked_errors:
                        st.error(sa_locked_error)
                else:
                    try:
                        _locked_updates = prepare_monitoring_payload({
                            "status": sa_locked_status,
                            "numeric_value": sa_locked_value,
                            "progress_text": sa_locked_progress,
                            "risks": sa_locked_risks,
                            "npa_link": sa_locked_npa,
                        })
                        correct_locked_request(
                            request_id=int(_locked_request_id),
                            updates=_locked_updates,
                            reason=clean(sa_locked_reason),
                            user=current_user,
                        )

                        # Email не є частиною транзакції БД: помилка листа не відкочує
                        # вже виконане коригування, але отримує окремий код інциденту.
                        try:
                            _locked_chain = schemes.parse_chain(_locked_row.get("approval_chain"))
                            if _locked_chain:
                                _locked_last_stage = _locked_chain[-1]
                                notify_events.notify_superadmin_correction(
                                    _locked_last_stage.get("email", ""),
                                    _locked_last_stage.get("name", ""),
                                    clean(_locked_row.get("strat_code")),
                                    clean(_locked_row.get("year")),
                                    clean(_locked_row.get("quarter")),
                                    reason=clean(sa_locked_reason),
                                    editor_name=(
                                        clean(current_user.get("full_name"))
                                        or clean(current_user.get("name"))
                                        or "Супер-адміністратор"
                                    ),
                                    kind=clean(_locked_row.get("object_kind")) or "measure",
                                )
                        except Exception as notify_exc:
                            show_warning(
                                "Коригування збережено, але останній ланці не відправлено миттєвий лист.",
                                notify_exc,
                                "Email після коригування закритої заявки",
                            )

                        st.session_state["sa_locked_correction_notice"] = (
                            f"Заявку ID {int(_locked_request_id)} скориговано. "
                            "Вона залишається остаточно закритою."
                        )
                        monitoring_data.invalidate_monitoring_cache()
                        st.rerun()
                    except TransitionRejected as exc:
                        st.error(exc.message)
                    except Exception as exc:
                        show_incident(exc, context="Атомарне коригування закритої заявки")

    st.markdown('</div>', unsafe_allow_html=True)

if filtered.empty:
    st.info("За обраними фільтрами заявок не знайдено.")
    render_footer()
    st.stop()

# ──────────────────────────────────────────────
# ЧЕРГА НА РОЗГЛЯД
# ──────────────────────────────────────────────

# ТЗ-правка (09.07.2026, п.3): у черзі та в полі вибору — ЛИШЕ заявки,
# що очікують рішення САМЕ поточного користувача (його ланка в схемі).
# Заявки, що зараз на інших ланках, тут не показуються; їхній стан можна
# переглянути у блоці «Перегляд статусу заявок» нижче.
_me_email = clean(current_user.get("email")).lower()
_me_role = clean(current_user.get("role"))

def _request_is_actionable_by_me(row) -> bool:
    ap = clean(row.get("approval_status"))
    if ap not in set(schemes.ALL_WAITING_STATUSES):
        return False
    ch = schemes.parse_chain(row.get("approval_chain"))
    stg = schemes.parse_stage(row.get("chain_stage"))
    if not ch:
        # застарілі заявки без ланцюга — на розгляді координатора
        return ap == "Очікує погодження" and _me_role == "admin"
    cur = schemes.current_stage(ch, stg)
    if cur is None:
        return False
    cur_role = clean(cur.get("role"))
    cur_email = clean(cur.get("email")).lower()
    if _me_role == "super_admin":
        return cur_role == ROLE_SUPER_ADMIN and cur_email in ("", _me_email)
    if _me_role == "admin":
        return cur_role == schemes.ROLE_ADMIN
    return False

queue_df = filtered[filtered.apply(_request_is_actionable_by_me, axis=1)].copy()

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

# ТЗ-правка (09.07.2026, п.3): вибір — лише з черги, що очікує САМЕ вас.
_selectable = queue_df if not queue_df.empty else filtered.iloc[0:0]

if _selectable.empty:
    st.info(
        "Наразі немає заявок, що очікують саме вашого рішення. Стан усіх "
        "інших заявок можна переглянути у блоці «Перегляд статусу заявок» "
        "нижче."
    )
    st.markdown('</div>', unsafe_allow_html=True)
    render_requests_status_viewer(filtered)
    render_footer()
    st.stop()

selected_options = [
    f"ID {row['id']} | ССП {row['department']} | {row['strat_code']} | "
    f"{row['year']} {row['quarter']} квартал | {row['approval_status']} | "
    f"{clean(row['submitted_at'])}"
    for _, row in _selectable.iterrows()
]

selected_request = st.selectbox("Оберіть заявку для перегляду та погодження", selected_options)
selected_id  = int(selected_request.split("|")[0].replace("ID", "").strip())
selected_row = _selectable[_selectable["id"].astype(int) == selected_id].iloc[0]

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
elif approval_status == "Очікує: Керівник ССП":
    status_badge = "badge"
else:
    status_badge = "badge-yellow"

st.markdown(
    f"""
    <div class="badge-wrap">
        <div class="badge {status_badge}">Статус: {approval_status}</div>
        <div class="badge">Захід № {selected_code}</div>
        <div class="badge">ID {clean(selected_row['id'])}</div>
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

# ТЗ-правка (09.07.2026, п.3): блоки «Системна оцінка якості заявки» та
# «Автоматична службова резолюція» прибрано — за обов'язкових полів вони
# не несуть смислового навантаження.

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
    r_color = "#DC4A4A" if risks_val else "#61708A"
    r_text_color = "#DC4A4A" if risks_val else "#8A96A8"
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
_req_dept_nums = re.findall(r"\d+", clean(selected_row.get("department", "")))
_req_dept_idx = _req_dept_nums[0] if _req_dept_nums else ""

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
            f'Маршрут погодження{(" · " + _esc(_req_scheme_label)) if _req_scheme_label else ""}</div>'
            f'<div class="progress-risk-value">{_esc(schemes.chain_route_text(_req_chain))}<br>'
            f'<b>{_esc(schemes.chain_progress_text(_req_chain, _req_stage, approval_status))}</b></div></div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "ℹ️ Маршрут будується покроково: наступну ланку (якщо вона потрібна) "
            "призначає сама поточна ланка під час розгляду — заднім числом "
            "перепризначити чи змінити вже пройдені кроки маршруту не можна."
        )
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
        <div class="card" style="border:2px solid #FF7A45;background:#FDF3D8;">
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
                approve_request_step(
                    request_id=int(selected_id),
                    expected_status=approval_status,
                    expected_chain_stage=int(_req_stage),
                    new_status="Погоджено",
                    new_chain_stage=int(_req_stage) + 1,
                    approval_chain=(schemes.chain_to_json(_req_chain) if _req_chain else None),
                    comment="Погоджено: дані заявки збігаються з ручним закриттям заходу.",
                    action="Погодження заявки (збіг із ручним закриттям)",
                    user=current_user,
                    created_by="Координатор / погодження збігу з ручним закриттям",
                )
                st.success("Заявку погоджено.")
                monitoring_data.invalidate_monitoring_cache()
                st.rerun()
            except TransitionRejected as exc:
                st.error(exc.message)
            except Exception as exc:
                show_incident(exc, context="Атомарне погодження заявки при збігу з ручним закриттям")
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
                        .eq("strat_code", selected_code).eq("period_year", year_to_db(_req_year))
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
                    monitoring_data.invalidate_monitoring_cache()
                    st.rerun()
                except Exception as exc:
                    show_incident(exc, context="Фіксація розбіжності з ручним закриттям")

# ──────────────────────────────────────────────
# РІШЕННЯ АДМІНІСТРАТОРА
# ──────────────────────────────────────────────
#
# ВАЖЛИВО (виправлення бага, знайденого на тестуванні): раніше ця форма
# показувалася координатору для БУДЬ-ЯКОЇ заявки, незалежно від того,
# чия зараз черга в ланцюзі погодження. Через це координатор міг
# натиснути "Погодити" за ланку, чия черга ще не настала (напр. за
# заступника керівника ССП) — і заявка стрибала на наступний етап так,
# ніби та ланка щойно ухвалила рішення, хоча вона його не ухвалювала.
# Тепер дія координатора доступна ЛИШЕ тоді, коли поточна ланка
# ланцюга (chain_stage) — дійсно "admin". В іншому разі — лише
# інформаційний перегляд, без можливості щось змінити.

_is_admin_turn = (not _req_chain) or schemes.is_stage_role(_req_chain, _req_stage, schemes.ROLE_ADMIN)
_current_waiting_stage = schemes.current_stage(_req_chain, _req_stage) if _req_chain else None

# ТЗ Адм.1 / Заг.5: ланка «Супер-адмін» у схемі. Діяти може лише той
# супер-адмін, якому заявку направлено (email ланки), — інші супер-адміни
# бачать усе, але не втручаються. Якщо він сумнівається — ескалує вищому
# (Пастушина → Делюсто; Канєвська → Перун).
_my_email_norm = clean(current_user.get("email")).lower()
_is_super_turn = bool(
    _req_chain
    and _current_waiting_stage is not None
    and clean(_current_waiting_stage.get("role")) == ROLE_SUPER_ADMIN
    and clean(current_user.get("role")) == "super_admin"
    and clean(_current_waiting_stage.get("email")).lower() in ("", _my_email_norm)
)

if _is_super_turn and not schemes.is_final_locked(selected_row):
    st.markdown(
        '<div class="card">'
        '<div class="card-title">Рішення супер-адміна</div>'
        '<div class="card-subtitle">Заявку направлено вам координатором, '
        'який мав сумніви. Погодьте остаточно, ескалуйте вищому '
        'супер-адміну або поверніть на доопрацювання.</div>',
        unsafe_allow_html=True,
    )
    _sa_senior = senior_superadmin_for(_my_email_norm)
    _sa_options = ["Погодити остаточно"]
    if _sa_senior and clean(_sa_senior.get("email")).lower() not in ("", _my_email_norm):
        _sa_options.append(f"Передати вищому супер-адміну — {_sa_senior['name']}")
    _sa_options += ["Повернути на доопрацювання", "Залишити в очікуванні"]
    _sa_decision = st.radio(
        "Оберіть рішення", _sa_options, horizontal=True,
        key=f"sa_decision_{selected_id}",
    )
    _sa_targets = schemes.return_targets(_req_chain, _req_stage)
    _sa_target_labels = [t["label"] for t in _sa_targets]
    _sa_return_label = st.selectbox(
        "Кому повернути (якщо обрано повернення)", _sa_target_labels,
        key=f"sa_return_target_{selected_id}",
    )
    _sa_comment = st.text_area(
        "Коментар (обов'язковий при поверненні)", height=80,
        key=f"sa_comment_{selected_id}",
    )
    if st.button("Підтвердити рішення супер-адміна", type="primary",
                 use_container_width=True, key=f"sa_confirm_{selected_id}"):
        _sa_new_status, _sa_extra, _sa_action, _sa_notify = None, {}, "", None
        _sa_blocked = False
        if _sa_decision == "Погодити остаточно":
            _sa_new_status, _sa_new_stage = schemes.finalize_here(_req_stage)
            _sa_extra["chain_stage"] = int(_sa_new_stage)
            _sa_action = "Погодження супер-адміном (остаточно)"
            _sa_notify = ("approved",)
        elif _sa_decision.startswith("Передати вищому"):
            _sa_new_chain, _sa_new_status, _sa_new_stage = schemes.advance_with_new_stage(
                _req_chain, _req_stage, ROLE_SUPER_ADMIN, str(_req_dept_idx),
                {"email": _sa_senior["email"], "name": _sa_senior["name"]},
            )
            if _sa_new_chain is None:
                st.error("Не вдалося визначити вищого супер-адміна.")
                _sa_blocked = True
            else:
                _sa_extra["approval_chain"] = schemes.chain_to_json(_sa_new_chain)
                _sa_extra["chain_stage"] = int(_sa_new_stage)
                _sa_action = f"Ескалація вищому супер-адміну: {_sa_senior['name']}"
                _sa_notify = ("stage", _sa_new_chain[_sa_new_stage])
        elif _sa_decision == "Повернути на доопрацювання":
            if not clean(_sa_comment):
                st.error("Для повернення обов'язково вкажіть коментар.")
                _sa_blocked = True
            else:
                _sa_picked = _sa_targets[_sa_target_labels.index(_sa_return_label)]
                _sa_new_status = _sa_picked["status"]
                _sa_extra["chain_stage"] = int(_sa_picked["new_stage"])
                _sa_action = f"Повернення супер-адміном: {_sa_picked['label']}"
                _sa_notify = ("returned", _sa_picked)
        else:
            _sa_new_status = approval_status
            _sa_action = "Заявку залишено в очікуванні (супер-адмін)"
        if not _sa_blocked:
            try:
                _sa_comment_value = clean(_sa_comment) or clean(selected_row.get("admin_comment", ""))
                _sa_target_stage = int(_sa_extra.get("chain_stage", _req_stage))
                if _sa_decision == "Повернути на доопрацювання":
                    atomic_return_request(
                        request_id=int(selected_id),
                        expected_status=approval_status,
                        expected_chain_stage=int(_req_stage),
                        new_status=_sa_new_status,
                        new_chain_stage=_sa_target_stage,
                        comment=_sa_comment_value,
                        action=_sa_action,
                        user=current_user,
                        created_by="Супер-адмін / повернення",
                    )
                else:
                    approve_request_step(
                        request_id=int(selected_id),
                        expected_status=approval_status,
                        expected_chain_stage=int(_req_stage),
                        new_status=_sa_new_status,
                        new_chain_stage=_sa_target_stage,
                        approval_chain=_sa_extra.get("approval_chain"),
                        comment=_sa_comment_value,
                        action=_sa_action,
                        user=current_user,
                        created_by="Супер-адмін / рішення",
                    )
                try:
                    if _sa_notify and _sa_notify[0] == "approved":
                        notify_events.notify_approved(
                            clean(selected_row.get("email", "")),
                            clean(selected_row.get("responsible_person", "")),
                            selected_code, _req_year, _req_quarter,
                            kind=_req_kind or "measure",
                        )
                    elif _sa_notify and _sa_notify[0] == "stage" and _sa_notify[1]:
                        _nx = _sa_notify[1]
                        notify_events.notify_stage_assigned(
                            _nx.get("email", ""), _nx.get("name", ""),
                            _nx.get("label", ""), selected_code,
                            _req_year, _req_quarter,
                            submitter=clean(selected_row.get("responsible_person", "")),
                            kind=_req_kind or "measure",
                        )
                    elif _sa_notify and _sa_notify[0] == "returned":
                        notify_events.notify_returned(
                            clean(selected_row.get("email", "")),
                            clean(selected_row.get("responsible_person", "")),
                            selected_code, _req_year, _req_quarter,
                            by_label="Супер-адмін", comment=clean(_sa_comment),
                            kind=_req_kind or "measure",
                        )
                except Exception as notify_exc:
                    show_warning(
                        "Рішення збережено, але миттєве email-сповіщення не відправлено.",
                        notify_exc,
                        "Email після рішення супер-адміна",
                    )
                monitoring_data.invalidate_monitoring_cache()
                st.success("✅ Рішення супер-адміна зафіксовано.")
                st.rerun()
            except TransitionRejected as exc:
                st.error(exc.message)
            except Exception as exc:
                show_incident(exc, context="Атомарне рішення супер-адміна")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="card">'
    '<div class="card-title">Рішення адміністратора</div>'
    '<div class="card-subtitle">Оберіть рішення та підтвердьте його однією кнопкою.</div>',
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="badge-wrap">
        <div class="badge {status_badge}">Поточний статус: {approval_status}</div>
    </div>
    """,
    unsafe_allow_html=True
)

default_comment = clean(selected_row["admin_comment"])

if _req_chain and not _is_admin_turn and not _is_super_turn:
    st.info(
        f"⏳ Зараз черга ланки «{(_current_waiting_stage or {}).get('label','')}» "
        f"({(_current_waiting_stage or {}).get('name','') or (_current_waiting_stage or {}).get('email','')}). "
        "Координатор не може погодити, повернути чи будь-як вплинути на "
        "заявку замість цієї ланки — лише переглянути дані вище. Дочекайтеся "
        "її рішення; воно з'явиться тут автоматично."
    )
elif schemes.is_final_locked(selected_row):
    st.info(
        "🔒 Заявку остаточно закрито — останню ланку схеми погодження "
        "пройдено (статус «Погоджено»). Рішення координатора (погодити / "
        "повернути на доопрацювання / залишити в очікуванні) для цієї заявки "
        "більше не застосовуються.\n\n"
        "Якщо з'явилася нова, актуальніша інформація по заходу — "
        "скоригувати вже подані дані (не маршрут погодження) може "
        "лише супер-адмін через окрему дію «Скоригувати дані після закриття»."
    )
else:
    # Наступна ланка після координатора (для ЗАСТАРІЛИХ заявок, де весь
    # ланцюг уже був наперед побудований до цього виправлення — таким
    # ми не заважаємо, вони й далі йдуть по вже зафіксованому маршруту).
    _next_after_admin = None
    if _req_chain and 0 <= _req_stage < len(_req_chain):
        _next_after_admin = schemes.current_stage(_req_chain, _req_stage + 1)

    # НОВА МОДЕЛЬ: якщо наступної ланки ще НЕ визначено наперед — це
    # координатор вирішує зараз, потрібна вона взагалі і яка саме
    # (core/approval_schemes.py: next_stage_role_options). Він не може
    # призначити нікого "нижче" координатора — лише один із трьох
    # варіантів вище, або завершити заявку одразу на собі.
    _next_role_options = []
    if _req_chain and not _next_after_admin:
        _next_role_options = schemes.next_stage_role_options(schemes.ROLE_ADMIN)

    if _req_chain and _next_after_admin:
        _approve_option = f"Погодити та передати далі (→ {_next_after_admin['label']})"
    elif _req_chain:
        _approve_option = "Погодити"
    else:
        _approve_option = "Підтвердити (передати керівнику ССП)"

    # Адресати повернення (подавач + попередні ланки, якщо є схема)
    if _req_chain:
        _adm_targets = schemes.return_targets(_req_chain, _req_stage)
    else:
        _adm_targets = [{"key": "submitter", "label": "Подавачу (відповідальній особі ССП)",
                         "status": "Повернуто на доопрацювання", "new_stage": 0}]
    _adm_target_labels = [t["label"] for t in _adm_targets]

    decision = st.radio(
        "Оберіть рішення",
        [_approve_option, "Повернути на доопрацювання", "Залишити в очікуванні"],
        horizontal=True,
        key=f"decision_radio_{selected_id}"
    )

    # Динамічний вибір наступної ланки (поза формою — бо в st.form()
    # віджети не оновлюються один від одного до сабміту, а тут вибір
    # ролі має одразу показати вибір конкретної особи).
    _chosen_next_role = None
    _chosen_next_person = None
    _chain_override = None      # (new_chain, new_status, new_stage, excluded, action_text)

    # ТЗ-правка (09.07.2026, п.3) + Адм.6/8/10: навіть коли наступна ланка
    # вже визначена схемою подавача, координатор МОЖЕ змінити схему:
    # передати іншій (не нижчій) ланці — з email-сповіщенням усім, кого
    # виключено, — або вставити ПІСЛЯ СЕБЕ супер-адміна, якщо сумнівається.
    if decision == _approve_option and _req_chain and _next_after_admin:
        _sa_route = resolve_manual_closeout_route(current_user)
        _keep_option = f"За схемою подавача: → {_next_after_admin['label']}"
        _sa_insert_option = (
            f"Додати супер-адміна після себе (сумніваюсь) — "
            f"{_sa_route['assigned_superadmin_name']}"
        )
        _alt_roles = [
            r for r in schemes.next_stage_role_options(schemes.ROLE_ADMIN)
            if r != clean(_next_after_admin.get("role"))
        ]
        _override_labels = ([_keep_option, _sa_insert_option]
                            + [f"Змінити наступну ланку: «{schemes.STAGE_LABELS[r]}»"
                               for r in _alt_roles])
        _override_choice = st.selectbox(
            "Що далі після координатора",
            _override_labels,
            key=f"adm_chain_override_{selected_id}",
        )
        if _override_choice == _sa_insert_option:
            _sa_stage = {
                "role": ROLE_SUPER_ADMIN,
                "label": schemes.STAGE_LABELS[ROLE_SUPER_ADMIN],
                "email": clean(_sa_route["assigned_superadmin_email"]).lower(),
                "name": _sa_route["assigned_superadmin_name"],
            }
            _oc = list(_req_chain)
            _oc.insert(_req_stage + 1, _sa_stage)
            _chain_override = (
                _oc,
                schemes.waiting_status_for_stage(_sa_stage),
                _req_stage + 1,
                [],
                f"Погодження координатором → після себе додано супер-адміна "
                f"({_sa_route['assigned_superadmin_name']})",
            )
            st.caption(f"→ {_sa_route['routing_note']}. Після супер-адміна "
                       f"заявка продовжить рух за схемою подавача.")
        elif _override_choice != _keep_option:
            _alt_role = _alt_roles[_override_labels.index(_override_choice) - 2]
            _alt_candidates = schemes.stage_candidates(_alt_role, str(_req_dept_idx))
            _alt_person = None
            if len(_alt_candidates) > 1:
                _alt_labels = [schemes.candidate_label(c) for c in _alt_candidates]
                _alt_pick = st.selectbox(
                    f"Хто саме — {schemes.STAGE_LABELS[_alt_role]}",
                    _alt_labels, key=f"adm_override_person_{selected_id}",
                )
                _alt_person = _alt_candidates[_alt_labels.index(_alt_pick)]
            elif _alt_candidates:
                _alt_person = _alt_candidates[0]
                st.caption(f"→ {schemes.candidate_label(_alt_person)}")
            if _alt_person is None:
                st.error(
                    f"Немає користувача ролі «{schemes.STAGE_LABELS[_alt_role]}» "
                    f"для цього ССП — оберіть інший варіант."
                )
            else:
                _truncated = list(_req_chain[:_req_stage + 1])
                _oc, _ost, _ostg = schemes.advance_with_new_stage(
                    _truncated, _req_stage, _alt_role, str(_req_dept_idx), _alt_person
                )
                if _oc is not None:
                    _excluded = [
                        st_ for st_ in _req_chain[_req_stage + 1:]
                        if clean(st_.get("email")).lower()
                        != clean(_alt_person.get("email")).lower()
                    ]
                    _chain_override = (
                        _oc, _ost, _ostg, _excluded,
                        f"Погодження координатором → схему змінено: наступна "
                        f"ланка «{schemes.STAGE_LABELS[_alt_role]}»",
                    )
                    if _excluded:
                        st.warning(
                            "Зі схеми буде виключено: "
                            + ", ".join(
                                clean(x.get("name")) or clean(x.get("email"))
                                for x in _excluded
                            )
                            + " — кожному надійде email-сповіщення."
                        )

    if decision == _approve_option and _next_role_options:
        # ТЗ Адм.6 / Заг.5: якщо координатор сумнівається — він може ПІСЛЯ
        # СЕБЕ (і тільки після себе) поставити в схему супер-адміна. Хто
        # саме — визначає закріплена ієрархія (core/superadmin_routing):
        # Провицька/Курдибан/Бойко → Пастушина; Ковальчук/Єфремов/
        # Чемоданова → Канєвська.
        _sa_route = resolve_manual_closeout_route(current_user)
        _sa_option = (
            f"Передати супер-адміну (сумніваюсь) — "
            f"{_sa_route['assigned_superadmin_name']}"
        )
        _next_choice_labels = (
            ["Завершити на координаторі (без додаткової ланки)"]
            + [f"Передати ланці «{schemes.STAGE_LABELS[r]}»" for r in _next_role_options]
            + [_sa_option]
        )
        _next_choice = st.selectbox(
            "Що далі після координатора",
            _next_choice_labels,
            key=f"adm_next_stage_choice_{selected_id}",
        )
        if _next_choice == _sa_option:
            _chosen_next_role = ROLE_SUPER_ADMIN
            _chosen_next_person = {
                "email": _sa_route["assigned_superadmin_email"],
                "name": _sa_route["assigned_superadmin_name"],
                "extra": "супер-адмін (за закріпленою ієрархією)",
            }
            st.caption(
                f"→ {_sa_route['assigned_superadmin_name']} · "
                f"{_sa_route['routing_note']}"
            )
        elif _next_choice != _next_choice_labels[0]:
            _chosen_next_role = _next_role_options[_next_choice_labels.index(_next_choice) - 1]
            _next_candidates = schemes.stage_candidates(_chosen_next_role, str(_req_dept_idx))
            if len(_next_candidates) > 1:
                _cand_labels = [schemes.candidate_label(c) for c in _next_candidates]
                _picked_cand_label = st.selectbox(
                    f"Хто саме — {schemes.STAGE_LABELS[_chosen_next_role]}",
                    _cand_labels,
                    key=f"adm_next_stage_person_{selected_id}",
                )
                _chosen_next_person = _next_candidates[_cand_labels.index(_picked_cand_label)]
            elif _next_candidates:
                _chosen_next_person = _next_candidates[0]
                st.caption(f"→ {schemes.candidate_label(_chosen_next_person)}")
            else:
                st.error(
                    f"Немає користувача ролі «{schemes.STAGE_LABELS[_chosen_next_role]}» "
                    f"для ССП {_req_dept_idx}. Оберіть іншу ланку або зверніться до супер-адміна."
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
              "🖊 Заявка перейде до керівника ССП на підтвердження")),
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

    confirm_decision = st.button(
        "Застосувати рішення",
        use_container_width=True,
        key=f"admin_apply_decision_{selected_id}",
    )

    if confirm_decision:
        _extra_update = {}
        _notify_action = None   # ("stage", stage_dict) | ("approved",) | ("returned", target)
        _excluded_after_transition = []
        _decision_blocked = False

        if decision == _approve_option:
            if _req_chain and _next_after_admin and _chain_override is not None:
                # ТЗ-правка (09.07.2026, п.3): координатор перевизначив схему —
                # вставив супер-адміна після себе або змінив наступну ланку.
                _oc, _ost, _ostg, _excluded, _oact = _chain_override
                new_status = _ost
                _extra_update["approval_chain"] = schemes.chain_to_json(_oc)
                _extra_update["chain_stage"] = int(_ostg)
                action_text = _oact
                _who_next = (_oc[_ostg].get("name") or _oc[_ostg].get("email") or "")
                success_text = (
                    f"✅ Підтверджено. Схему оновлено; заявка надійшла ланці "
                    f"«{_oc[_ostg].get('label','')}»"
                    f"{f' ({_who_next})' if _who_next else ''}."
                )
                _notify_action = ("stage", _oc[_ostg])
                # Листи та додаткові записи про виключених учасників робимо
                # лише ПІСЛЯ успішного атомарного переходу.
                _excluded_after_transition = list(_excluded)
            elif _req_chain and _next_after_admin:
                # ЗАСТАРІЛИЙ ланцюг: наступна ланка вже була наперед відома.
                new_status, _new_stage = schemes.status_after_approve(_req_chain, _req_stage)
                _extra_update["chain_stage"] = int(_new_stage)
                if new_status == "Погоджено":
                    action_text  = "Погодження координатором (остання ланка схеми)"
                    success_text = "✅ Заявка пройшла всі етапи схеми. Статус: «Погоджено»."
                    _notify_action = ("approved",)
                else:
                    action_text  = f"Погодження координатором → передано далі: {new_status}"
                    _who_next = (_next_after_admin.get("name") or _next_after_admin.get("email") or "")
                    success_text = (
                        f"✅ Підтверджено. Заявка одразу надійшла наступній ланці — "
                        f"{_next_after_admin.get('label','')}"
                        f"{f' ({_who_next})' if _who_next else ''}. "
                        f"Вона вже бачить її у кабінеті у списку «Активні до розгляду»."
                    )
                    _notify_action = ("stage", _next_after_admin)
            elif _req_chain and _chosen_next_role:
                if not _chosen_next_person:
                    st.error("Оберіть конкретну особу для наступної ланки (або немає жодної — див. попередження вище).")
                    _decision_blocked = True
                else:
                    _new_chain, new_status, _new_stage = schemes.advance_with_new_stage(
                        _req_chain, _req_stage, _chosen_next_role, str(_req_dept_idx), _chosen_next_person
                    )
                    if _new_chain is None:
                        st.error("Не вдалося призначити наступну ланку.")
                        _decision_blocked = True
                    else:
                        _extra_update["approval_chain"] = schemes.chain_to_json(_new_chain)
                        _extra_update["chain_stage"] = int(_new_stage)
                        action_text = (
                            f"Погодження координатором → призначено наступною ланкою: "
                            f"{schemes.STAGE_LABELS[_chosen_next_role]}"
                        )
                        success_text = (
                            f"✅ Підтверджено. Заявку передано ланці "
                            f"«{schemes.STAGE_LABELS[_chosen_next_role]}» "
                            f"({schemes.candidate_label(_chosen_next_person)})."
                        )
                        _notify_action = ("stage", _new_chain[_new_stage])
            elif _req_chain:
                # Завершити на координаторі — додаткової ланки не потрібно.
                new_status, _new_stage = schemes.finalize_here(_req_stage)
                _extra_update["chain_stage"] = int(_new_stage)
                action_text  = "Погодження координатором (завершено на координаторі)"
                success_text = "✅ Заявка погоджена координатором остаточно. Статус: «Погоджено»."
                _notify_action = ("approved",)
            else:
                new_status   = "Очікує: Керівник ССП"
                action_text  = "Передано керівнику ССП на підтвердження"
                success_text = "✅ Заявку передано керівнику ССП на підтвердження. Після підтвердження дані відобразяться на головній сторінці."
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

        if not _decision_blocked:
            try:
                _target_stage = int(_extra_update.get("chain_stage", _req_stage))
                if decision == "Повернути на доопрацювання":
                    atomic_return_request(
                        request_id=int(selected_id),
                        expected_status=approval_status,
                        expected_chain_stage=int(_req_stage),
                        new_status=new_status,
                        new_chain_stage=_target_stage,
                        comment=clean(admin_comment),
                        action=action_text,
                        user=current_user,
                        created_by="Координатор / повернення",
                    )
                else:
                    approve_request_step(
                        request_id=int(selected_id),
                        expected_status=approval_status,
                        expected_chain_stage=int(_req_stage),
                        new_status=new_status,
                        new_chain_stage=_target_stage,
                        approval_chain=_extra_update.get("approval_chain"),
                        comment=clean(admin_comment),
                        action=action_text,
                        user=current_user,
                        created_by="Координатор / рішення",
                    )

                for _ex in _excluded_after_transition:
                    try:
                        write_log(
                            selected_id,
                            "Зміна схеми погодження координатором: виключено "
                            f"{clean(_ex.get('name')) or clean(_ex.get('email'))}",
                            approval_status, new_status, admin_comment,
                        )
                    except Exception as audit_exc:
                        show_warning(
                            "Рішення збережено, але додатковий запис про виключення з ланцюжка не створено.",
                            audit_exc,
                            "Додатковий журнал виключення з ланцюжка",
                        )
                    try:
                        notify_events.notify_excluded_from_chain(
                            _ex.get("email", ""), _ex.get("name", ""),
                            _actor_identity("Координатор"),
                            selected_code, _req_year, _req_quarter,
                            kind=_req_kind or "measure",
                        )
                    except Exception as notify_exc:
                        show_warning(
                            "Рішення збережено, але лист виключеній ланці не надіслано.",
                            notify_exc,
                            "Сповіщення про виключення з ланцюжка погодження",
                        )

                # Миттєві email-сповіщення не входять у транзакцію БД.
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
                except Exception as notify_exc:
                    show_warning(
                        "Рішення збережено, але миттєве email-сповіщення не відправлено.",
                        notify_exc,
                        "Email після рішення координатора",
                    )

                # Пункт із тестування: стале (не зникаюче) повідомлення, щоб
                # координатор точно побачив і зрозумів, що ЦЯ заявка вже
                # оброблена — і якщо список автоматично перейшов до іншої
                # заявки, це НОВА заявка, яку варто переглянути з початку,
                # а не "не зарахувалось попереднє рішення".
                st.session_state["adm_last_decision_notice"] = (
                    f"{success_text} Якщо в черзі є ще заявки — систему щойно "
                    f"переключило на НАСТУПНУ заявку. Це не помилка: перегляньте "
                    f"її дані з самого початку, перш ніж ухвалювати рішення."
                )
                monitoring_data.invalidate_monitoring_cache()
                st.rerun()
            except TransitionRejected as exc:
                st.error(exc.message)
            except Exception as exc:
                show_incident(exc, context="Атомарне рішення координатора")

st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.get("adm_last_decision_notice"):
    st.warning(st.session_state["adm_last_decision_notice"], icon="⚠️")
    if st.button("Зрозуміло, приховати це повідомлення", key="adm_dismiss_decision_notice"):
        st.session_state.pop("adm_last_decision_notice", None)
        st.rerun()



st.markdown(
    '<div class="card"><div class="card-title">Історія змін заявки</div>',
    unsafe_allow_html=True
)

logs_df = load_logs(selected_id)

if logs_df.empty:
    st.info("Історії змін для цієї заявки поки що немає.")
else:
    with st.expander("Повна історія змін заявки"):
        # ЄДИНИЙ компонент таймлайну для всієї системи (core/ui.py, ТЗ 16.13)
        render_request_timeline(logs_df, with_table_expander=False)
        show_logs = logs_df.copy()
        # ТЗ-правка (09.07.2026, п.3): історію розширено фактичним значенням
        # та описом прогресу — з версій заявки на момент кожної події, а за
        # їх відсутності — з поточних даних заявки.
        try:
            _vers = load_versions(selected_id)
        except Exception as exc:
            show_warning(
                "Історію версій завантажено не повністю.",
                exc,
                "Завантаження версій у повній історії заявки",
            )
            _vers = pd.DataFrame()
        _log_ts = pd.to_datetime(show_logs.get("changed_at"), errors="coerce", utc=True)
        _facts, _progress = [], []
        if _vers is not None and not _vers.empty and "created_at" in _vers.columns:
            _vers = _vers.copy()
            _vers["_ts"] = pd.to_datetime(_vers["created_at"], errors="coerce", utc=True)
            _vers = _vers.sort_values("_ts")
            for t in _log_ts:
                _snap = _vers[_vers["_ts"] <= t] if pd.notna(t) else _vers.iloc[0:0]
                _row = _snap.iloc[-1] if not _snap.empty else None
                _facts.append(clean((_row or {}).get("numeric_value", "")) if _row is not None
                              else clean(selected_row.get("numeric_value", "")))
                _progress.append(clean((_row or {}).get("progress_text", "")) if _row is not None
                                 else clean(selected_row.get("progress_text", "")))
        else:
            _facts = [clean(selected_row.get("numeric_value", ""))] * len(show_logs)
            _progress = [clean(selected_row.get("progress_text", ""))] * len(show_logs)
        show_logs["Фактичне значення"] = _facts
        show_logs["Опис прогресу"] = _progress
        render_human_log_table(
            show_logs,
            extra_columns=["Фактичне значення", "Опис прогресу"],
        )

st.markdown('</div>', unsafe_allow_html=True)

# ТЗ-правка (09.07.2026, п.3): перегляд статусу ВСІХ заявок за фільтрами —
# видно, на якому етапі схеми зараз кожна заявка (закрита чи ще ні).
render_requests_status_viewer(filtered)


# ТЗ Адм.3: функцію «Архівування» повністю прибрано з адміністрування —
# без заглушок і службових карток.

with st.expander("Технічна таблиця заявок"):
    st.dataframe(filtered, use_container_width=True, hide_index=True)

render_footer()
