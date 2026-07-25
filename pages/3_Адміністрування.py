import json
import re
import streamlit as st
import pandas as pd
import plotly.express as px
from core.data_types import (
    normalise_closeout_frame,
    normalise_monitoring_frame,
    prepare_closeout_payload,
    prepare_monitoring_payload,
    quarter_to_db,
    year_to_db,
)
from core.db import fetch_all, get_supabase_client
from core.errors import log_cosmetic_error, show_incident, show_warning
from core.ui import load_css, prepare_human_log_table, render_request_timeline
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
from core.stage5 import failed_notifications_last_30_days
from core.stage4 import format_kyiv_datetime, quarter_to_roman
from core.archive import create_archive_snapshot, format_kyiv as format_archive_kyiv
from core.statuses import SUBMISSION_STATUS_OPTIONS
from core.validation import (
    YES_VALUES,
    is_yes_no_unit,
    status_value_conflict,
    validate_fact_value_for_target,
)
from config.roles import ROLE_SUPER_ADMIN
from core.access import filter_actions_for_user
from core.superadmin_routing import resolve_manual_closeout_route, can_superadmin_decide_closeout, senior_superadmin_for
from core.versioning import save_request_version
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

.admin-control-label {
    color: #132238;
    font-size: 14px;
    font-weight: 900;
    line-height: 1.35;
    margin: 4px 0 6px 0;
}

.admin-section-spacer {
    height: 16px;
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

/* ─── COMPACT REQUEST DETAILS ─── */
.admin-object-name {
    color: #132238;
    font-size: 18px;
    font-weight: 900;
    line-height: 1.45;
    margin: 8px 0 12px 0;
}

.admin-request-nature {
    border-radius: 10px;
    padding: 10px 12px;
    margin: 7px 0 11px 0;
    color: #132238;
    font-size: 13px;
    font-weight: 750;
    line-height: 1.5;
}

.admin-request-nature.manual {
    background: #F3EEFF;
    border: 1px solid #9B7BEA;
}

.admin-request-nature.super-review {
    background: #FFF4ED;
    border: 1px solid #FF7A45;
}

.admin-reference-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 9px;
}

.admin-submission-panel {
    background: transparent;
    border: 1px solid #DCE4F0;
    border-radius: 14px;
    padding: 18px 22px;
    margin: 12px 0;
}

.admin-submission-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 9px;
}

.admin-reference-row,
.admin-data-field {
    background: #EAF1FF;
    border: 1px solid #BFD3F2;
    border-radius: 10px;
    padding: 10px 12px;
    min-width: 0;
}

.admin-reference-row.wide,
.admin-data-field.wide {
    grid-column: 1 / -1;
}

.admin-data-field.admin-special-field {
    background: #F7F9FC;
    border-color: #DCE4F0;
}

.admin-reference-label,
.admin-data-label {
    color: #132238;
    font-size: 11px;
    font-weight: 900;
    line-height: 1.35;
    margin-bottom: 5px;
    text-transform: uppercase;
    letter-spacing: 0.035em;
}

.admin-reference-value,
.admin-data-value {
    color: #132238;
    font-size: 14px;
    font-weight: 850;
    line-height: 1.55;
    overflow-wrap: anywhere;
    white-space: pre-wrap;
}

.admin-special-field .admin-data-value {
    font-weight: 750;
}

.admin-data-value a {
    color: #005BBB;
    font-weight: 800;
    text-decoration: underline;
    text-underline-offset: 2px;
}

.admin-route-caption {
    color: #132238;
    font-size: 12px;
    font-weight: 800;
    margin-bottom: 7px;
}

.admin-route-row {
    display: flex;
    flex-wrap: nowrap;
    align-items: stretch;
    gap: 7px;
    overflow-x: auto;
    padding: 2px 0 5px 0;
    scrollbar-width: thin;
}

.admin-route-node {
    flex: 0 0 auto;
    min-width: 150px;
    max-width: 250px;
    background: #EAF1FF;
    border: 1px solid #BFD3F2;
    border-radius: 10px;
    padding: 8px 10px;
    color: #132238;
    font-size: 12px;
    font-weight: 800;
    line-height: 1.4;
}

.admin-route-node.current {
    background: #FFF4ED;
    border: 2px solid #FF7A45;
    box-shadow: 0 0 0 2px rgba(255,122,69,0.10);
}

.admin-route-role {
    display: block;
    color: #132238;
    font-size: 11px;
    font-weight: 900;
    margin-bottom: 3px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}

.admin-route-arrow {
    flex: 0 0 auto;
    align-self: center;
    color: #61708A;
    font-size: 18px;
    font-weight: 900;
}

.admin-contact-row {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 9px;
}

.admin-contact-item {
    background: #FFFFFF;
    border: 1px solid #DCE4F0;
    border-radius: 9px;
    padding: 8px 10px;
    color: #132238;
    font-weight: 800;
    overflow-wrap: anywhere;
}

.admin-contact-item strong {
    display: block;
    color: #132238;
    font-size: 10px;
    font-weight: 900;
    margin-bottom: 3px;
    text-transform: uppercase;
    letter-spacing: 0.035em;
}

.decision-card {
    padding: 13px 17px;
}

.decision-guidance {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-left: 4px solid #4D8DFF;
    border-radius: 10px;
    padding: 10px 13px;
    margin: 7px 0 10px 0;
    color: #132238;
    font-size: 13px;
    font-weight: 650;
    line-height: 1.55;
}

.decision-guidance p {
    margin: 0 0 7px 0;
}

.decision-guidance p:last-child {
    margin-bottom: 0;
}

@media (max-width: 1200px) {
    .admin-submission-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}

@media (max-width: 900px) {
    .admin-reference-grid,
    .admin-contact-row {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 700px) {
    .admin-submission-grid {
        grid-template-columns: 1fr;
    }
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


@st.cache_data(ttl=5, show_spinner=False)
def load_closeout_requests():
    """Єдиний кешований реєстр запитів ручного закриття для сторінки."""
    rows = fetch_all(
        "closeout_requests",
        "*",
        order=("requested_at", True),
    )
    return normalise_closeout_frame(pd.DataFrame(rows))


def _quarter_number(value) -> int | None:
    try:
        return quarter_to_db(value)
    except (TypeError, ValueError):
        return None


def _quarter_label_ua(value) -> str:
    number = _quarter_number(value)
    roman = {1: "I", 2: "II", 3: "III", 4: "IV"}.get(number)
    return f"{roman} квартал" if roman else "квартал не визначено"


def _closeout_fact_value(record) -> str:
    return clean(record.get("fact_value_text")) or clean(record.get("fact_numeric_value"))


def _matrix_row_for_code(code) -> dict:
    lookup = globals().get("_strat_row_lookup", {}) or {}
    return lookup.get(clean(code).strip().rstrip("."), {}) or {}


def _closeout_carries_forward(record, matrix_row: dict | None = None) -> bool:
    """Чи підтверджене ручне закриття переносить «так» до кінця року."""
    if clean(record.get("approval_status")) != "Підтверджено":
        return False
    source_quarter = _quarter_number(record.get("period_quarter"))
    if source_quarter is None or source_quarter >= 4:
        return False
    matrix = matrix_row or _matrix_row_for_code(record.get("strat_code"))
    if not is_yes_no_unit(matrix.get("unit")):
        return False
    return clean(_closeout_fact_value(record)).casefold() in YES_VALUES


def _carry_quarters_text(quarters: list[int], year) -> str:
    labels = [{1: "I", 2: "II", 3: "III", 4: "IV"}[q] for q in quarters]
    if not labels:
        return ""
    if len(labels) == 1:
        return f"Значення «так» перенесено також на {labels[0]} квартал {clean(year)} року."
    joined = ", ".join(labels[:-1]) + f" та {labels[-1]}"
    return f"Значення «так» перенесено також на {joined} квартали {clean(year)} року."


def _related_closeout_logs(record) -> pd.DataFrame:
    """Журнал ручного закриття того самого заходу й звітного періоду."""
    if record is None:
        return pd.DataFrame()
    code = clean(record.get("strat_code")).strip().rstrip(".")
    year = _year_number(record.get("year"))
    try:
        quarter = quarter_to_db(record.get("quarter"))
    except ValueError:
        quarter = None
    if not code or year is None or quarter is None:
        return pd.DataFrame()

    closeouts = load_closeout_requests()
    if closeouts.empty:
        return pd.DataFrame()

    matching_ids = []
    for _, closeout in closeouts.iterrows():
        if clean(closeout.get("strat_code")).strip().rstrip(".") != code:
            continue
        if _year_number(closeout.get("period_year")) != year:
            continue
        raw_quarter = clean(closeout.get("period_quarter"))
        try:
            closeout_quarter = quarter_to_db(raw_quarter)
        except ValueError:
            closeout_quarter = None
        # Точний квартал завжди належить до цієї історії. Попередній квартал
        # охоплює поточний лише для підтвердженого бінарного значення «так».
        if closeout_quarter is not None:
            if closeout_quarter > quarter:
                continue
            if closeout_quarter < quarter and not _closeout_carries_forward(closeout):
                continue
        try:
            matching_ids.append(str(int(float(closeout.get("id")))))
        except (TypeError, ValueError):
            continue

    if not matching_ids:
        return pd.DataFrame()
    try:
        rows = fetch_all(
            "monitoring_logs",
            "*",
            filters=[
                ("eq", "related_table", "closeout_requests"),
                ("in_", "related_key", sorted(set(matching_ids))),
            ],
            order=("changed_at", False),
        )
    except Exception as exc:
        log_cosmetic_error("Завантаження пов'язаного журналу ручного закриття", exc)
        return pd.DataFrame()

    related = pd.DataFrame(rows)
    if related.empty:
        return related
    related = related.copy()
    related["request_id"] = record.get("id")
    related["action"] = related.get("action", pd.Series(index=related.index, dtype=object)).map(
        lambda value: (
            clean(value)
            if "ручн" in clean(value).lower()
            else f"Ручне закриття · {clean(value) or 'зміна статусу'}"
        )
    )
    return related


def load_logs(request_id, record=None):
    rows = fetch_all(
        "monitoring_logs",
        "*",
        filters=[("eq", "request_id", int(request_id))],
        order=("changed_at", True),
    )
    request_logs = pd.DataFrame(rows)
    related_logs = _related_closeout_logs(record)
    frames = [frame for frame in (request_logs, related_logs) if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True, sort=False)
    if "id" in merged.columns:
        merged = merged.drop_duplicates(subset=["id"], keep="first")
    merged["_history_ts"] = pd.to_datetime(merged.get("changed_at"), errors="coerce", utc=True)
    return merged.sort_values("_history_ts").drop(columns=["_history_ts"], errors="ignore")


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



def _html_cell(value) -> str:
    """Безпечне HTML-представлення значення комірки."""
    value_text = clean(value).strip()
    return _esc(value_text).replace("\n", "<br>") if value_text else "—"


def _period_label(year, quarter) -> str:
    """Формат звітного періоду, спільний зі сторінкою «Мої заявки»."""
    roman = quarter_to_roman(quarter)
    qnum = {"I": "1", "II": "2", "III": "3", "IV": "4"}.get(roman, clean(quarter))
    qnum = str(qnum).upper().removeprefix("Q")
    return f"{clean(year)} Q{qnum}" if clean(year) else f"Q{qnum}"


def _planned_quarter_label(value) -> str:
    """Перетворює планову дату на формат «N квартал YYYY року»."""
    raw = clean(value).strip()
    if not raw:
        return "—"
    try:
        day_first = bool(re.match(r"^\d{1,2}[./]\d{1,2}[./]\d{4}", raw))
        parsed = pd.to_datetime(raw, errors="coerce", dayfirst=day_first)
    except Exception:
        return "—"
    if pd.isna(parsed):
        return "—"
    quarter = ((int(parsed.month) - 1) // 3) + 1
    return f"{quarter} квартал {int(parsed.year)} року"


def _year_number(value) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _sort_by_ssp(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return frame.copy() if isinstance(frame, pd.DataFrame) else pd.DataFrame()
    result = frame.copy()
    result["_ssp_sort"] = pd.to_numeric(
        result["department"].astype(str).str.extract(r"(\d+)")[0],
        errors="coerce",
    )
    return result.sort_values("_ssp_sort", na_position="last").drop(
        columns=["_ssp_sort"], errors="ignore"
    )


def _render_html_table(headers: list[str], rows: list[list], empty_message: str = "Записів немає."):
    """Єдиний HTML-рендер таблиць через глобальні класи assets/app.css."""
    if not rows:
        st.info(empty_message)
        return
    header_html = "".join(f"<th>{_esc(str(header))}</th>" for header in headers)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{_html_cell(value)}</td>" for value in row) + "</tr>"
        for row in rows
    )
    st.markdown(
        '<div class="myreq-table-scroll"><table class="myreq-html-table">'
        f"<thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody>"
        "</table></div>",
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_initial_submitters(request_ids: tuple[int, ...]) -> dict[int, dict]:
    """Один масовий запит найперших версій для всіх потрібних заявок."""
    ids = sorted({int(request_id) for request_id in request_ids if request_id is not None})
    if not ids:
        return {}
    try:
        rows = fetch_all(
            "monitoring_request_versions",
            "request_id,version_number,created_at,responsible_person,phone",
            filters=[("in_", "request_id", ids)],
            order=[("request_id", False), ("version_number", False), ("created_at", False)],
        )
    except Exception as exc:
        log_cosmetic_error("Масове завантаження перших версій заявок", exc)
        return {}
    versions = pd.DataFrame(rows)
    if versions.empty or "request_id" not in versions.columns:
        return {}
    versions["_request_id"] = pd.to_numeric(versions["request_id"], errors="coerce")
    versions["_version_number"] = pd.to_numeric(
        versions.get("version_number"), errors="coerce"
    )
    versions["_created_at"] = pd.to_datetime(
        versions.get("created_at"), errors="coerce", utc=True
    )
    versions = versions.dropna(subset=["_request_id"]).sort_values(
        ["_request_id", "_version_number", "_created_at"],
        ascending=[True, True, True],
        na_position="last",
    )
    first_rows = versions.groupby("_request_id", sort=False).head(1)
    return {
        int(row["_request_id"]): {
            "responsible_person": clean(row.get("responsible_person")),
            "phone": clean(row.get("phone")),
        }
        for _, row in first_rows.iterrows()
    }


def _build_strat_row_lookup(frame: pd.DataFrame) -> dict[str, dict]:
    if frame is None or frame.empty or "code" not in frame.columns:
        return {}
    work = frame.copy()
    work["_code_key"] = work["code"].astype(str).str.strip().str.rstrip(".")
    priority = {"measure": 0, "task": 1, "goal": 2}
    if "object_type" in work.columns:
        work["_object_priority"] = work["object_type"].astype(str).map(priority).fillna(9)
    else:
        work["_object_priority"] = 9
    work = work.sort_values(["_code_key", "_object_priority"])
    result = {}
    for _, row in work.iterrows():
        key = clean(row.get("_code_key"))
        if key and key not in result:
            result[key] = row.to_dict()
    return result


def _matrix_values_for_request(record) -> tuple[str, str]:
    code_key = clean(record.get("strat_code")).strip().rstrip(".")
    matrix_row = _strat_row_lookup.get(code_key, {})
    name = clean(matrix_row.get("name")) or "—"
    year = _year_number(record.get("year"))
    target = clean(matrix_row.get(f"target_{year}")) if year is not None else ""
    return name, target or "—"


def _fact_for_request(record) -> str:
    return clean(record.get("numeric_value")) or clean(record.get("value_text")) or "—"


def _active_closeout_for_period(frame: pd.DataFrame, code, year, quarter, unit=""):
    """Точний дублікат або підтверджене перенесення бінарного «так»."""
    if frame is None or frame.empty:
        return None
    code_key = clean(code).strip().rstrip(".")
    selected_year = _year_number(year)
    selected_quarter = _quarter_number(quarter)
    if not code_key or selected_year is None or selected_quarter is None:
        return None

    exact_matches = []
    carry_matches = []
    matrix_row = {"unit": unit}
    for _, row in frame.iterrows():
        status = clean(row.get("approval_status"))
        if status not in {"Очікує підтвердження", "Підтверджено"}:
            continue
        if clean(row.get("strat_code")).strip().rstrip(".") != code_key:
            continue
        if _year_number(row.get("period_year")) != selected_year:
            continue
        row_quarter = _quarter_number(row.get("period_quarter"))
        if row_quarter is None:
            continue
        if row_quarter == selected_quarter:
            exact_matches.append(row)
        elif row_quarter < selected_quarter and _closeout_carries_forward(row, matrix_row):
            carry_matches.append(row)

    if exact_matches:
        row = sorted(exact_matches, key=lambda item: clean(item.get("requested_at")))[0]
        return {"kind": "exact", "row": row, "source_quarter": selected_quarter}
    if carry_matches:
        # Найближчий попередній квартал найточніше пояснює блокування.
        row = sorted(
            carry_matches,
            key=lambda item: (
                -(_quarter_number(item.get("period_quarter")) or 0),
                clean(item.get("requested_at")),
            ),
        )[0]
        return {
            "kind": "carry",
            "row": row,
            "source_quarter": _quarter_number(row.get("period_quarter")),
        }
    return None


def _closeout_duplicate_message(match, year, quarter) -> str:
    row = match["row"]
    when = format_kyiv_datetime(row.get("requested_at")) or "раніше"
    status = clean(row.get("approval_status")) or "статус не визначено"
    if match.get("kind") == "carry":
        source = _quarter_label_ua(match.get("source_quarter"))
        return (
            f"Захід уже підтверджено зі значенням «так» за {source} {clean(year)} року. "
            f"Тому {_quarter_label_ua(quarter)} та наступні квартали цього року "
            "вважаються закритими автоматичним перенесенням результату."
        )
    return (
        f"Запит за {_period_label(year, quarter)} уже подано {when}; "
        f"його статус — «{status}». Повторне надсилання за цей самий період вимкнено."
    )


def _transition_request_ids(result, closeout_id: int) -> list[int]:
    raw = getattr(result, "data", {}).get("request_ids") if result is not None else None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw = []
    ids = []
    for value in raw or []:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    if ids:
        return sorted(set(ids))
    try:
        response = (
            supabase.table("closeout_requests")
            .select("materialized_request_ids")
            .eq("id", int(closeout_id))
            .limit(1)
            .execute()
        )
        stored = (response.data or [{}])[0].get("materialized_request_ids") or []
        if isinstance(stored, str):
            stored = json.loads(stored)
        return sorted({int(value) for value in stored or []})
    except Exception as exc:
        log_cosmetic_error("Читання матеріалізованих заявок ручного закриття", exc)
        return []


def _sync_closeout_request_ids(closeout_id: int, request_ids: list[int]) -> None:
    request_ids = sorted({int(value) for value in request_ids})
    supabase.table("closeout_requests").update({
        "materialized_request_ids": request_ids,
    }).eq("id", int(closeout_id)).execute()
    try:
        logs = fetch_all(
            "monitoring_logs",
            "id,payload_json",
            filters=[
                ("eq", "related_table", "closeout_requests"),
                ("eq", "related_key", str(int(closeout_id))),
            ],
        )
        for log in logs:
            payload = log.get("payload_json") or "{}"
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except (TypeError, ValueError, json.JSONDecodeError):
                    payload = {}
            if not isinstance(payload, dict):
                payload = {}
            payload["request_ids"] = request_ids
            supabase.table("monitoring_logs").update({
                "payload_json": json.dumps(payload, ensure_ascii=False),
            }).eq("id", int(log["id"])).execute()
    except Exception as exc:
        log_cosmetic_error("Синхронізація ID у журналі ручного закриття", exc)


def _carry_origin_comment(source_quarter: int, year, reason) -> str:
    return (
        f"Закрито вручну. Перенесення результату «так» з "
        f"{_quarter_label_ua(source_quarter)} {clean(year)} року. "
        f"Підстава: {clean(reason) or 'не зазначена'}"
    )


def _mark_request_as_carry(request_id: int, source_quarter: int, year, reason) -> None:
    comment = _carry_origin_comment(source_quarter, year, reason)
    action = (
        f"Ручне закриття: перенесення результату з "
        f"{_quarter_label_ua(source_quarter)} {clean(year)} року"
    )
    supabase.table("monitoring_requests").update({
        "admin_comment": comment,
    }).eq("id", int(request_id)).execute()
    supabase.table("monitoring_request_versions").update({
        "admin_comment": comment,
        "created_by": action,
    }).eq("request_id", int(request_id)).execute()
    supabase.table("monitoring_logs").update({
        "action": action,
        "admin_comment": comment,
    }).eq("request_id", int(request_id)).execute()


def _insert_carried_request(
    base_row: dict,
    *,
    quarter: int,
    source_quarter: int,
    closeout_id: int,
    reason: str,
) -> int:
    copy_fields = [
        "year", "department", "responsible_person", "phone", "email",
        "strat_code", "status", "numeric_value", "value_text", "progress_text",
        "risks", "submitted_at", "approval_status", "npa_link", "approval_chain",
        "chain_stage", "scheme_label", "object_kind", "object_name", "indicator_name",
        "start_date", "end_date", "as_of_date", "file_names", "file_urls",
        "final_locked", "final_locked_at",
    ]
    payload = {field: base_row.get(field) for field in copy_fields if field in base_row}
    payload.update({
        "quarter": int(quarter),
        "approval_status": "Погоджено",
        "final_locked": True,
        "scheme_label": "Ручне закриття",
        "admin_comment": _carry_origin_comment(source_quarter, base_row.get("year"), reason),
    })
    response = supabase.table("monitoring_requests").insert(payload).execute()
    inserted = (response.data or [{}])[0]
    request_id = int(inserted["id"])

    version_source = dict(inserted)
    if clean(version_source.get("value_text")) and not clean(version_source.get("numeric_value")):
        version_source["numeric_value"] = version_source.get("value_text")
    save_request_version(
        request_id,
        version_source,
        created_by=(
            f"Ручне закриття / перенесення результату з "
            f"{_quarter_label_ua(source_quarter)}"
        ),
    )

    department = clean(inserted.get("department"))
    department_numbers = re.findall(r"\d+", department)
    actor_email = clean(current_user.get("email")).lower()
    actor_name = clean(current_user.get("full_name")) or clean(current_user.get("name")) or actor_email
    action = (
        f"Ручне закриття: перенесення результату з "
        f"{_quarter_label_ua(source_quarter)} {clean(inserted.get('year'))} року"
    )
    supabase.table("monitoring_logs").insert({
        "request_id": request_id,
        "action": action,
        "old_status": "",
        "new_status": "Погоджено",
        "admin_comment": payload["admin_comment"],
        "changed_by": _actor_identity("Супер-адміністратор"),
        "actor_email": actor_email,
        "actor_name": actor_name,
        "actor_role": clean(current_user.get("role")) or "super_admin",
        "ssp_index": department_numbers[0] if department_numbers else "",
        "strat_code": clean(inserted.get("strat_code")),
        "related_table": "monitoring_requests",
        "related_key": str(request_id),
        "payload_json": json.dumps({
            "closeout_id": int(closeout_id),
            "carry_forward": True,
            "source_quarter": int(source_quarter),
            "target_quarter": int(quarter),
        }, ensure_ascii=False),
    }).execute()
    return request_id


def _reconcile_confirmed_closeout(
    closeout_id: int,
    closeout_record,
    matrix_row,
    transition_result=None,
) -> list[int]:
    """Нормалізує серверну матеріалізацію до точного правила перенесення."""
    source_quarter = _quarter_number(closeout_record.get("period_quarter"))
    year = _year_number(closeout_record.get("period_year"))
    if source_quarter is None or year is None:
        return []

    linked_ids = _transition_request_ids(transition_result, int(closeout_id))
    linked_rows = []
    if linked_ids:
        linked_rows = fetch_all(
            "monitoring_requests",
            "*",
            filters=[("in_", "id", linked_ids)],
            order=("quarter", False),
        )

    should_carry = _closeout_carries_forward(closeout_record, dict(matrix_row or {}))
    rows_by_quarter = {
        _quarter_number(row.get("quarter")): row
        for row in linked_rows
        if _quarter_number(row.get("quarter")) is not None
    }

    if not should_carry:
        keep_ids = [
            int(row["id"])
            for row in linked_rows
            if _quarter_number(row.get("quarter")) == source_quarter
        ]
        unwanted_ids = sorted(set(linked_ids) - set(keep_ids))
        if unwanted_ids:
            # monitoring_logs і monitoring_request_versions мають ON DELETE CASCADE.
            supabase.table("monitoring_requests").delete().in_("id", unwanted_ids).execute()
        _sync_closeout_request_ids(int(closeout_id), keep_ids)
        return []

    base_row = rows_by_quarter.get(source_quarter)
    if base_row is None:
        existing_base = fetch_all(
            "monitoring_requests",
            "*",
            filters=[
                ("eq", "strat_code", clean(closeout_record.get("strat_code"))),
                ("eq", "year", int(year)),
                ("eq", "quarter", int(source_quarter)),
                ("neq", "approval_status", "Відкликано"),
            ],
            order=("id", True),
        )
        base_row = existing_base[0] if existing_base else None
    if base_row is None:
        raise RuntimeError("Не знайдено офіційний запис основного кварталу ручного закриття.")

    all_ids = list(linked_ids)
    carried_quarters = []
    reason = clean(closeout_record.get("reason"))
    code = clean(closeout_record.get("strat_code"))
    for target_quarter in range(source_quarter + 1, 5):
        carried_quarters.append(target_quarter)
        existing_row = rows_by_quarter.get(target_quarter)
        if existing_row is None:
            other_rows = fetch_all(
                "monitoring_requests",
                "*",
                filters=[
                    ("eq", "strat_code", code),
                    ("eq", "year", int(year)),
                    ("eq", "quarter", int(target_quarter)),
                    ("neq", "approval_status", "Відкликано"),
                ],
                order=("id", True),
            )
            if other_rows:
                raise RuntimeError(
                    f"За {_period_label(year, target_quarter)} уже існує офіційна заявка №"
                    f"{other_rows[0].get('id')}; автоматичне перенесення не може її замінити."
                )
            request_id = _insert_carried_request(
                base_row,
                quarter=target_quarter,
                source_quarter=source_quarter,
                closeout_id=int(closeout_id),
                reason=reason,
            )
            all_ids.append(request_id)
            existing_row = {"id": request_id, "quarter": target_quarter}
        _mark_request_as_carry(
            int(existing_row["id"]), source_quarter, year, reason,
        )

    _sync_closeout_request_ids(int(closeout_id), all_ids)
    return carried_quarters


def _request_nature_html(record, chain: list[dict], stage_index: int) -> str:
    """Позначка природи заявки лише для супер-адміна."""
    if not is_super_admin_user(current_user):
        return ""
    scheme_label = clean(record.get("scheme_label")).casefold()
    admin_comment = clean(record.get("admin_comment")).casefold()
    if "ручне закриття" in scheme_label or "закрито вручну" in admin_comment:
        return (
            '<div class="admin-request-nature manual"><b>Ручне закриття.</b> '
            'Ці відомості створені після підтвердження запиту адміністратора. '
            'Перевірте підставу, фактичне значення та зафіксований результат.</div>'
        )
    current_stage = schemes.current_stage(chain, stage_index) if chain else None
    previous_roles = {clean(stage.get("role")) for stage in (chain or [])[:stage_index]}
    if (
        current_stage
        and clean(current_stage.get("role")) == ROLE_SUPER_ADMIN
        and schemes.ROLE_ADMIN in previous_roles
    ):
        return (
            '<div class="admin-request-nature super-review"><b>Додаткова перевірка супер-адміна.</b> '
            'Координатор скерував заявку вам через сумніви. Потрібно погодити її, '
            'передати вищому супер-адміну або повернути на доопрацювання.</div>'
        )
    return ""


def _render_request_detail_cards(record) -> dict:
    """Спільний вигляд картки й поданих даних у звичайному та correction-режимі."""
    selected_code = clean(record.get("strat_code"))
    approval_status = clean(record.get("approval_status"))
    year_val = clean(record.get("year")).strip()
    code_key = selected_code.strip().rstrip(".")
    strat_record = _strat_row_lookup.get(code_key, {})
    target_year_val = clean(strat_record.get(f"target_{year_val}", "")) if year_val else ""

    object_type = clean(strat_record.get("object_type")).strip().lower()
    object_number_label = {
        "measure": "Захід №",
        "task": "Завдання №",
        "goal": "Стратегічна ціль №",
    }.get(object_type, "Об’єкт №")
    object_name = clean(strat_record.get("name")) or "—"
    product_type = clean(strat_record.get("product_type")) or "—"
    indicator = clean(strat_record.get("indicator")) or "—"
    unit = clean(strat_record.get("unit")) or "—"
    resp_main = clean(strat_record.get("resp_main")) or "—"
    resp_co_1 = clean(strat_record.get("resp_co_1")) or "—"
    resp_co_2 = clean(strat_record.get("resp_co_2")) or "—"
    start_quarter = _planned_quarter_label(strat_record.get("start_date_plan"))
    end_quarter = _planned_quarter_label(strat_record.get("end_date_plan"))
    term_label = "—" if start_quarter == "—" and end_quarter == "—" else f"{start_quarter} — {end_quarter}"

    person_name = clean(record.get("responsible_person")) or "—"
    person_phone = clean(record.get("phone")) or "—"
    person_email = clean(record.get("email")) or "—"
    fact_value = _fact_for_request(record)
    progress_value = clean(record.get("progress_text")) or "—"
    risks_value = clean(record.get("risks")) or "Не зазначено"
    npa_raw = clean(record.get("npa_link"))
    req_chain = schemes.parse_chain(record.get("approval_chain"))
    req_stage = schemes.parse_stage(record.get("chain_stage"))
    req_scheme_label = clean(record.get("scheme_label"))
    req_kind = clean(record.get("object_kind")) or "measure"
    req_dept_nums = re.findall(r"\d+", clean(record.get("department")))
    req_dept_idx = req_dept_nums[0] if req_dept_nums else ""

    if npa_raw:
        npa_links_html = "".join(
            f'<div>🔗 <a href="{_esc(link.strip())}" target="_blank" rel="noopener noreferrer">'
            f'{_esc(link.strip())}</a></div>'
            for link in re.split(r"[\n;,]+", npa_raw)
            if link.strip()
        ) or "—"
    else:
        npa_links_html = "—"

    route_nodes = [
        '<div class="admin-route-node">'
        '<span class="admin-route-role">Подавач</span>'
        f'{_esc(person_name if person_name != "—" else person_email)}'
        '</div>'
    ]
    current_route_stage = schemes.current_stage(req_chain, req_stage) if req_chain else None
    for stage_index, stage in enumerate(req_chain):
        stage_label = clean(stage.get("label")) or schemes.STAGE_LABELS.get(clean(stage.get("role")), "Ланка")
        stage_person = clean(stage.get("name")) or clean(stage.get("email")) or "—"
        current_class = " current" if current_route_stage is not None and stage_index == req_stage else ""
        route_nodes.append(
            f'<div class="admin-route-node{current_class}">'
            f'<span class="admin-route-role">{_esc(stage_label)}</span>'
            f'{_esc(stage_person)}</div>'
        )
    route_html = '<span class="admin-route-arrow">→</span>'.join(route_nodes)
    route_caption = _esc(req_scheme_label) if req_scheme_label else "Маршрут погодження"
    nature_html = _request_nature_html(record, req_chain, req_stage)

    reference_card_html = (
        '<div class="card">'
        '<div class="card-title">Картка заявки</div>'
        f'{nature_html}'
        '<div class="badge-wrap">'
        f'<div class="badge">{_esc(object_number_label)} {_esc(selected_code)}</div>'
        f'<div class="badge">ID {_esc(clean(record.get("id")))}</div>'
        '</div>'
        f'<div class="admin-object-name">{_esc(object_name)}</div>'
        '<div class="admin-reference-grid">'
        '<div class="admin-reference-row">'
        '<div class="admin-reference-label">Тип продукту</div>'
        f'<div class="admin-reference-value">{_esc(product_type)}</div>'
        '</div>'
        '<div class="admin-reference-row">'
        '<div class="admin-reference-label">Індикатор</div>'
        f'<div class="admin-reference-value">{_esc(indicator)}</div>'
        '</div>'
        '<div class="admin-reference-row">'
        '<div class="admin-reference-label">Одиниця виміру</div>'
        f'<div class="admin-reference-value">{_esc(unit)}</div>'
        '</div>'
        '<div class="admin-reference-row wide">'
        '<div class="admin-reference-label">Відповідальний ССП</div>'
        f'<div class="admin-reference-value">{_esc(resp_main)} &nbsp;·&nbsp; '
        f'Спів. 1: {_esc(resp_co_1)} &nbsp;·&nbsp; Спів. 2: {_esc(resp_co_2)}</div>'
        '</div>'
        '<div class="admin-reference-row wide">'
        '<div class="admin-reference-label">Термін</div>'
        f'<div class="admin-reference-value">{_esc(term_label)}</div>'
        '</div>'
        '</div>'
        '</div>'
    )
    st.html(reference_card_html)

    target_heading = f"Цільовий орієнтир на {year_val} рік" if year_val else "Цільовий орієнтир"
    submission_card_html = (
        '<div class="admin-submission-panel">'
        '<div class="card-title">Подані відомості</div>'
        '<div class="admin-submission-grid">'
        '<div class="admin-data-field">'
        '<div class="admin-data-label">Звітний період</div>'
        f'<div class="admin-data-value">{_esc(_period_label(record.get("year"), record.get("quarter")))}</div>'
        '</div>'
        '<div class="admin-data-field">'
        '<div class="admin-data-label">Статус виконання</div>'
        f'<div class="admin-data-value">{_esc(clean(record.get("status")) or "—")}</div>'
        '</div>'
        '<div class="admin-data-field">'
        f'<div class="admin-data-label">{_esc(target_heading)}</div>'
        f'<div class="admin-data-value">{_esc(target_year_val or "—")}</div>'
        '</div>'
        '<div class="admin-data-field">'
        '<div class="admin-data-label">Фактичне значення</div>'
        f'<div class="admin-data-value">{_esc(fact_value)}</div>'
        '</div>'
        '<div class="admin-data-field wide">'
        '<div class="admin-data-label">Опис прогресу виконання</div>'
        f'<div class="admin-data-value">{_html_cell(progress_value)}</div>'
        '</div>'
        '<div class="admin-data-field wide">'
        '<div class="admin-data-label">Ризики / проблеми / відхилення</div>'
        f'<div class="admin-data-value">{_html_cell(risks_value)}</div>'
        '</div>'
        '<div class="admin-data-field wide">'
        '<div class="admin-data-label">Посилання на НПА</div>'
        f'<div class="admin-data-value">{npa_links_html}</div>'
        '</div>'
        '<div class="admin-data-field wide admin-special-field">'
        '<div class="admin-data-label">Схема погодження</div>'
        f'<div class="admin-route-caption">{route_caption}</div>'
        f'<div class="admin-route-row">{route_html}</div>'
        '</div>'
        '<div class="admin-data-field wide admin-special-field">'
        '<div class="admin-data-label">Дані відповідальної особи</div>'
        '<div class="admin-contact-row">'
        f'<div class="admin-contact-item"><strong>ПІБ</strong>{_esc(person_name)}</div>'
        f'<div class="admin-contact-item"><strong>Телефон</strong>{_esc(person_phone)}</div>'
        f'<div class="admin-contact-item"><strong>Email</strong>{_esc(person_email)}</div>'
        '</div>'
        '</div>'
        '</div>'
        '</div>'
    )
    st.html(submission_card_html)

    return {
        "approval_status": approval_status,
        "selected_code": selected_code,
        "year_val": year_val,
        "target_year_val": target_year_val,
        "strat_record": strat_record,
        "unit": unit,
        "person_name": person_name,
        "person_phone": person_phone,
        "person_email": person_email,
        "req_chain": req_chain,
        "req_stage": req_stage,
        "req_kind": req_kind,
        "req_dept_idx": req_dept_idx,
    }


def _initial_submitter_for_request(record) -> tuple[str, str]:
    try:
        request_id = int(float(str(record.get("id"))))
    except (TypeError, ValueError):
        request_id = -1
    initial = _initial_submitter_lookup.get(request_id, {})
    person = clean(initial.get("responsible_person")) or clean(record.get("responsible_person")) or "—"
    phone = clean(initial.get("phone")) or clean(record.get("phone")) or "—"
    return person, phone


_REQUEST_TABLE_HEADERS = [
    "ID заявки", "ССП", "Код заходу", "Назва заходу", "Звітний період",
    "Початок виконання", "Кінець виконання", "Цільовий орієнтир",
    "Фактичне значення", "Опис прогресу", "Ризики / проблеми / відхилення",
    "Посилання на НПА", "Особа, яка подала заявку", "Номер телефону", "Дата подання",
]


def _request_table_values(record, coordinator: str | None = None) -> list:
    name, target = _matrix_values_for_request(record)
    person, phone = _initial_submitter_for_request(record)
    values = [
        record.get("id"), record.get("department"), record.get("strat_code"), name,
        _period_label(record.get("year"), record.get("quarter")),
        record.get("start_date"), record.get("end_date"), target,
        _fact_for_request(record), record.get("progress_text"), record.get("risks"),
        record.get("npa_link"), person, phone,
        format_kyiv_datetime(record.get("submitted_at")),
    ]
    if coordinator is not None:
        values.insert(12, coordinator)
    return values


def _review_days(value) -> int | None:
    waiting = days_waiting(value)
    return max(0, waiting) if waiting is not None else None


def _route_matches_current_superadmin(route: dict, user: dict) -> bool:
    current_email = clean((user or {}).get("email")).lower()
    current_name = (
        clean((user or {}).get("full_name"))
        or clean((user or {}).get("name"))
    ).casefold()
    for prefix in ("assigned_superadmin", "senior_superadmin"):
        route_email = clean(route.get(f"{prefix}_email")).lower()
        route_name = clean(route.get(f"{prefix}_name")).casefold()
        if route_email and current_email and route_email == current_email:
            return True
        if route_name and current_name and route_name in current_name:
            return True
    return False


def _assigned_admin_requests(frame: pd.DataFrame) -> list[tuple[pd.Series, str]]:
    matched = []
    if frame is None or frame.empty:
        return matched
    for _, row in frame.iterrows():
        if clean(row.get("approval_status")) not in set(schemes.ALL_WAITING_STATUSES):
            continue
        chain = schemes.parse_chain(row.get("approval_chain"))
        stage = schemes.current_stage(chain, schemes.parse_stage(row.get("chain_stage")))
        if not stage or clean(stage.get("role")) != schemes.ROLE_ADMIN:
            continue
        coordinator = clean(stage.get("name")) or clean(stage.get("email")) or "—"
        route = resolve_manual_closeout_route({
            "email": clean(stage.get("email")),
            "full_name": clean(stage.get("name")),
        })
        if _route_matches_current_superadmin(route, current_user):
            matched.append((row, coordinator))
    return matched


def _render_superadmin_bottom_tools():
    """Розсилка й архів доступні супер-адміну на всіх шляхах рендеру."""
    if not is_super_admin_user(current_user):
        return

    with st.expander("Розсилка: недоставлені листи", expanded=False):
        _failed_mail = failed_notifications_last_30_days()
        if _failed_mail.empty:
            st.success("Усі листи за останні 30 днів доставлено.")
        else:
            st.warning(f"Недоставлених листів за останні 30 днів: {len(_failed_mail)}")
            _mail_headers = [str(column) for column in _failed_mail.columns]
            _mail_rows = [
                [row.get(column) for column in _failed_mail.columns]
                for _, row in _failed_mail.iterrows()
            ]
            _render_html_table(_mail_headers, _mail_rows)

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

        _archive_option_ids = [None] + [
            int(row["id"]) for row in _archive_rows if row.get("id") is not None
        ]
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

st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)
st.markdown(
    '<div class="ministry-label">🇺🇦 Міністерство економіки, довкілля та сільського господарства України</div>',
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="header-box">
        <div class="header-title">Адміністрування</div>
        <div class="header-subtitle">
            Кабінет адміністратора використовується для розгляду, перевірки та погодження
            поданих відомостей та відстеження історії змін.
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
            <div class="flow-step">1. Оберіть режим адміністрування</div>
            <div class="flow-step">2. Перегляд системних параметрів</div>
            <div class="flow-step">3. Вибір параметрів</div>
            <div class="flow-step">4. Перевірка</div>
            <div class="flow-step">5. Вибір рішення</div>
            <div class="flow-step">6. Підтвердження</div>
            <div class="flow-step">7. Погодження</div>
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
    "numeric_value", "value_text", "progress_text", "risks", "npa_link",
    "file_names", "file_urls", "admin_comment", "approval_chain", "chain_stage",
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

_strat_row_lookup = _build_strat_row_lookup(strat_df)
_request_id_series = pd.to_numeric(
    df.get("id", pd.Series(dtype=object)),
    errors="coerce",
).dropna()
_request_ids = tuple(sorted(set(_request_id_series.astype(int).tolist())))
_initial_submitter_lookup = load_initial_submitters(_request_ids)


def _render_locked_correction_mode():
    """Окремий третій режим, доступний лише супер-адміну."""
    st.markdown(
        '<div class="card"><div class="card-title">🛠 Коригування остаточно закритої заявки</div>'
        '<div class="card-subtitle">Коригуються лише звітні дані. Статус погодження, '
        'маршрут і ознака final_locked не змінюються; кожна зміна фіксується у версіях і журналі.</div></div>',
        unsafe_allow_html=True,
    )

    correction_notice = st.session_state.pop("sa_locked_correction_notice", None)
    if correction_notice:
        st.success(correction_notice)

    def _is_true_flag(value) -> bool:
        if isinstance(value, bool):
            return value
        return clean(value).lower() in {"true", "1", "yes", "так"}

    if "final_locked" in df.columns:
        locked_df = df[
            df["final_locked"].map(_is_true_flag)
            & df["approval_status"].astype(str).str.strip().eq("Погоджено")
        ].copy()
    else:
        locked_df = df.iloc[0:0].copy()

    with st.container(border=True):
        st.markdown('<div class="filter-title">Вибір закритої заявки</div>', unsafe_allow_html=True)
        search_col, select_col = st.columns([1, 1.6])
        with search_col:
            st.markdown('<div class="filter-field-label">Пошук серед остаточно закритих заявок</div>', unsafe_allow_html=True)
            locked_search = st.text_input(
                "Пошук серед остаточно закритих заявок",
                key="sa_locked_requests_search",
                placeholder="ID, код заходу, ССП або відповідальна особа",
                label_visibility="collapsed",
            )

        if locked_search.strip() and not locked_df.empty:
            locked_sq = locked_search.strip().lower()
            locked_df = locked_df[
                locked_df["id"].astype(str).str.lower().str.contains(locked_sq, na=False)
                | locked_df["strat_code"].astype(str).str.lower().str.contains(locked_sq, na=False)
                | locked_df["department"].astype(str).str.lower().str.contains(locked_sq, na=False)
                | locked_df["responsible_person"].astype(str).str.lower().str.contains(locked_sq, na=False)
            ]
        if "submitted_at" in locked_df.columns and not locked_df.empty:
            locked_df = locked_df.sort_values("submitted_at", ascending=False)

        locked_labels = {
            int(row["id"]): (
                f"ID {int(row['id'])} | {clean(row.get('strat_code'))} | "
                f"{_period_label(row.get('year'), row.get('quarter'))} | "
                f"ССП {clean(row.get('department'))} | {clean(row.get('responsible_person'))}"
            )
            for _, row in locked_df.iterrows()
        }
        with select_col:
            st.markdown('<div class="filter-field-label">Оберіть остаточно закриту заявку</div>', unsafe_allow_html=True)
            if locked_labels:
                locked_request_id = st.selectbox(
                    "Оберіть остаточно закриту заявку",
                    options=list(locked_labels),
                    format_func=lambda request_id: locked_labels[request_id],
                    key="sa_locked_request_id",
                    label_visibility="collapsed",
                )
            else:
                locked_request_id = None
                st.info("Остаточно погоджених і заблокованих заявок за цим пошуком немає.")

    if locked_request_id is None:
        return

    locked_row = locked_df[locked_df["id"].astype(int).eq(int(locked_request_id))].iloc[0]
    detail = _render_request_detail_cards(locked_row)
    locked_code = detail["selected_code"]
    locked_strat = detail["strat_record"]
    locked_year = _year_number(locked_row.get("year"))
    locked_target = clean(locked_strat.get(f"target_{locked_year}", "")) if locked_year else ""
    locked_future_targets = (
        [locked_strat.get(f"target_{year}", "") for year in range(locked_year + 1, 2035)]
        if locked_year else []
    )

    locked_status_options = [
        "Виконано", "Частково виконано", "Не виконано", "Не настав час", "Втратило актуальність",
    ]
    locked_current_status = clean(locked_row.get("status"))
    locked_status_index = (
        locked_status_options.index(locked_current_status)
        if locked_current_status in locked_status_options else 0
    )

    with st.expander("✏️ Відкрити форму коригування", expanded=False):
        with st.form(f"sa_locked_correction_form_{int(locked_request_id)}"):
            sa_locked_status = st.selectbox(
                "Статус виконання", locked_status_options, index=locked_status_index,
            )
            sa_locked_value = st.text_input(
                "Фактичне значення",
                value=_fact_for_request(locked_row).replace("—", ""),
                help="Можна ввести число або текстове значення, наприклад «так» чи «ні».",
            )
            sa_locked_progress = st.text_area(
                "Опис прогресу", value=clean(locked_row.get("progress_text")), height=120,
            )
            sa_locked_risks = st.text_area(
                "Ризики / проблеми / відхилення", value=clean(locked_row.get("risks")), height=100,
            )
            sa_locked_npa = st.text_input(
                "Посилання на НПА", value=clean(locked_row.get("npa_link")),
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
            errors = []
            if not clean(sa_locked_reason).strip():
                errors.append("Обґрунтування коригування є обов'язковим.")
            locked_unit = clean(locked_strat.get("unit"))
            if clean(sa_locked_value):
                value_ok, value_error = validate_fact_value_for_target(
                    sa_locked_value, locked_unit, locked_target, locked_future_targets,
                )
                if not value_ok:
                    errors.append(value_error)
            conflict_error = status_value_conflict(
                sa_locked_status, sa_locked_value, locked_target, locked_unit,
                locked_code, locked_future_targets,
            )
            if conflict_error:
                errors.append(conflict_error)

            if errors:
                for error in errors:
                    st.error(error)
            else:
                try:
                    locked_updates = prepare_monitoring_payload({
                        "status": sa_locked_status,
                        "numeric_value": sa_locked_value,
                        "progress_text": sa_locked_progress,
                        "risks": sa_locked_risks,
                        "npa_link": sa_locked_npa,
                    })
                    correct_locked_request(
                        request_id=int(locked_request_id),
                        updates=locked_updates,
                        reason=clean(sa_locked_reason).strip(),
                        user=current_user,
                    )
                    try:
                        locked_chain = schemes.parse_chain(locked_row.get("approval_chain"))
                        if locked_chain:
                            locked_last_stage = locked_chain[-1]
                            notify_events.notify_superadmin_correction(
                                locked_last_stage.get("email", ""),
                                locked_last_stage.get("name", ""),
                                clean(locked_row.get("strat_code")),
                                clean(locked_row.get("year")),
                                clean(locked_row.get("quarter")),
                                reason=clean(sa_locked_reason).strip(),
                                editor_name=(
                                    clean(current_user.get("full_name"))
                                    or clean(current_user.get("name"))
                                    or "Супер-адміністратор"
                                ),
                                kind=clean(locked_row.get("object_kind")) or "measure",
                            )
                    except Exception as notify_exc:
                        show_warning(
                            "Коригування збережено, але останній ланці не відправлено миттєвий лист.",
                            notify_exc,
                            "Email після коригування закритої заявки",
                        )
                    st.session_state["sa_locked_correction_notice"] = (
                        f"Заявку ID {int(locked_request_id)} скориговано. Вона залишається остаточно закритою."
                    )
                    monitoring_data.invalidate_monitoring_cache()
                    st.rerun()
                except TransitionRejected as exc:
                    st.error(exc.message)
                except Exception as exc:
                    show_incident(exc, context="Атомарне коригування закритої заявки")


# ТЗ-правка (09.07.2026, п.3): панель «Сповіщення погодження» прибрано з адмінки.

# ──────────────────────────────────────────────
# РЕЖИМ РОБОТИ АДМІНІСТРУВАННЯ
# ──────────────────────────────────────────────

_admin_work_modes = ["Основний режим координатора", "Ручне закриття заходів"]
if is_super_admin_user(current_user):
    _admin_work_modes.append("Коригування закритих заявок")
if st.session_state.get("admin_work_mode") not in _admin_work_modes:
    st.session_state["admin_work_mode"] = _admin_work_modes[0]

st.markdown(
    '<div class="admin-control-label">Режим адміністрування</div>',
    unsafe_allow_html=True,
)
admin_work_mode = st.radio(
    "Режим адміністрування",
    _admin_work_modes,
    horizontal=True,
    key="admin_work_mode",
    label_visibility="collapsed",
)

if is_super_admin_user(current_user):
    with st.expander("Заявки закріплених адміністраторів", expanded=False):
        _assigned_rows = _assigned_admin_requests(df)
        if not _assigned_rows:
            st.info("Заявок на поточній ланці закріплених адміністраторів немає.")
        else:
            _assigned_frame = pd.DataFrame(
                [row.to_dict() for row, _ in _assigned_rows]
            )
            _coordinator_by_id = {
                clean(row.get("id")): coordinator for row, coordinator in _assigned_rows
            }
            _assigned_frame = _sort_by_ssp(_assigned_frame)
            _assigned_table_rows = [
                _request_table_values(
                    row,
                    coordinator=_coordinator_by_id.get(clean(row.get("id")), "—"),
                )
                for _, row in _assigned_frame.iterrows()
            ]
            _assigned_headers = _REQUEST_TABLE_HEADERS.copy()
            _assigned_headers.insert(12, "Координатор")
            _render_html_table(_assigned_headers, _assigned_table_rows)

if admin_work_mode == "Коригування закритих заявок":
    _render_locked_correction_mode()
    _render_superadmin_bottom_tools()
    render_footer()
    st.stop()

if admin_work_mode == "Ручне закриття заходів":
    # ──────────────────────────────────────────────
    # ЗАКРИТТЯ ЗАХОДУ ВРУЧНУ (admin → super_admin)
    # ──────────────────────────────────────────────


    _closeout_scope_df = filter_actions_for_user(
        strat_df,
        current_user,
        executor_columns=["resp_main", "resp_co_1", "Головний\nвиконавець", "Співвиконавець"],
    )
    _measure_rows = (
        _closeout_scope_df[
            _closeout_scope_df["code"].astype(str).str.count(r"\.") >= 3
        ].copy()
        if "code" in _closeout_scope_df.columns else pd.DataFrame()
    )
    _measure_options = []
    _measure_label_by_code = {}
    if not _measure_rows.empty:
        for _, _measure_row in _measure_rows.iterrows():
            _measure_code = clean(_measure_row.get("code")).strip()
            if not _measure_code or _measure_code in _measure_label_by_code:
                continue
            _measure_name = clean(_measure_row.get("name")) or "Назву не зазначено"
            _measure_label_by_code[_measure_code] = f"{_measure_code} | {_measure_name}"
            _measure_options.append(_measure_label_by_code[_measure_code])

    st.markdown(
        '<div class="card"><div class="card-title">Закриття заходу вручну</div>',
        unsafe_allow_html=True,
    )

    closeout_df = load_closeout_requests()

    if is_admin_user(current_user) or is_super_admin_user(current_user):
        st.caption(
            "Подати запит на ручне закриття заходу за конкретний квартал. "
            "Після підтвердження супер-адміном дані стають офіційними відомостями моніторингу."
        )
        if not _measure_options:
            st.info("Для вашої зони відповідальності заходів для ручного закриття не знайдено.")
            co_submit = False
        else:
            co_measure_label = st.selectbox(
                "Захід",
                _measure_options,
                key="closeout_measure_label",
            )
            co_code = co_measure_label.split("|", 1)[0].strip()
            _co_measure = _measure_rows[
                _measure_rows["code"].astype(str).str.strip() == co_code
            ]
            _co_measure_row = _co_measure.iloc[0] if not _co_measure.empty else pd.Series(dtype=object)
            _co_unit = clean(_co_measure_row.get("unit"))
            _co_indicator = clean(_co_measure_row.get("indicator"))
            _co_object_name = clean(_co_measure_row.get("name"))
            _co_product_type = clean(_co_measure_row.get("product_type")) or "—"
            _co_department = (
                clean(_co_measure_row.get("resp_main"))
                or clean(_co_measure_row.get("department"))
            )
            _co_start = clean(_co_measure_row.get("start_date_plan")) or "—"
            _co_end = clean(_co_measure_row.get("end_date_plan")) or "—"
            _co_target_items = [
                f"{year}: {clean(_co_measure_row.get(f'target_{year}'))}"
                for year in (2026, 2027, 2028)
                if clean(_co_measure_row.get(f"target_{year}"))
            ]
            _co_targets_label = " · ".join(_co_target_items) or "—"
            st.markdown(
                f"""
                <div class="review-box">
                    <div class="review-title">{_esc(co_code)} — {_esc(_co_object_name or '—')}</div>
                    <div><b>Індикатор виконання:</b> {_esc(_co_indicator or '—')}</div>
                    <div><b>Тип продукту:</b> {_esc(_co_product_type)}</div>
                    <div><b>Головний виконавець (ССП):</b> {_esc(_co_department or '—')}</div>
                    <div><b>Початкова дата:</b> {_esc(_co_start)} &nbsp;·&nbsp; <b>Кінцева дата:</b> {_esc(_co_end)}</div>
                    <div><b>Цільові орієнтири:</b> {_esc(_co_targets_label)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            co_year_col, co_quarter_col = st.columns(2)
            with co_year_col:
                co_year = st.selectbox("Рік", list(range(2026, 2035)), key="closeout_year")
            with co_quarter_col:
                co_quarter = st.selectbox("Квартал", ["I", "II", "III", "IV"], key="closeout_quarter")

            _co_duplicate = _active_closeout_for_period(
                closeout_df, co_code, co_year, co_quarter, _co_unit,
            )
            if _co_duplicate is not None:
                st.warning(_closeout_duplicate_message(_co_duplicate, co_year, co_quarter))

            _co_target = clean(_co_measure_row.get(f"target_{co_year}"))
            _co_future_targets = [
                _co_measure_row.get(f"target_{year}", "")
                for year in range(int(co_year) + 1, 2035)
            ]

            with st.form("closeout_request_form"):
                co_fact_status = st.selectbox(
                    "Статус виконання",
                    list(SUBMISSION_STATUS_OPTIONS),
                )
                co_fact_value = st.text_input(
                    "Фактичне значення",
                    help=(
                        f"Одиниця виміру: {_co_unit or 'не зазначена'}. Значення перевіряється "
                        "за тими самими правилами, що й звичайне подання відомостей."
                    ),
                )
                co_reason = st.text_area(
                    "Підстава для ручного закриття",
                    help="Обов'язкове поле. Внутрішня інформація, комунікація або інший звітний документ.",
                )
                co_npa = st.text_area(
                    "Посилання на НПА / джерела (по одному в рядку, опційно)",
                    placeholder="https://zakon.rada.gov.ua/...\nhttps://docs.google.com/...",
                )
                co_evidence = st.text_area("Ризики / додаткові пояснення (опційно)")
                co_submit = st.form_submit_button(
                    "Закрити вручну" if is_super_admin_user(current_user)
                    else "Надіслати на підтвердження супер-адміну",
                    disabled=_co_duplicate is not None,
                )

            if st.session_state.get("closeout_submit_notice"):
                st.success(st.session_state["closeout_submit_notice"])
                if st.button(
                    "Зрозуміло, приховати це повідомлення",
                    key="dismiss_closeout_submit_notice",
                ):
                    st.session_state.pop("closeout_submit_notice", None)
                    st.rerun()

            if co_submit:
                form_errors = []
                if not clean(co_reason).strip():
                    form_errors.append("Підстава для ручного закриття є обов'язковою.")
                if not clean(co_fact_value).strip():
                    form_errors.append("Зазначте фактичне значення.")
                else:
                    value_ok, value_error = validate_fact_value_for_target(
                        co_fact_value, _co_unit, _co_target, _co_future_targets,
                    )
                    if not value_ok:
                        form_errors.append(value_error)
                conflict_error = status_value_conflict(
                    co_fact_status, co_fact_value, _co_target, _co_unit,
                    co_code, _co_future_targets,
                )
                if conflict_error:
                    form_errors.append(conflict_error)

                # Повторна перевірка безпосередньо перед RPC; база лишається
                # остаточним захистом від одночасної роботи двох користувачів.
                load_closeout_requests.clear()
                latest_closeouts = load_closeout_requests()
                runtime_duplicate = _active_closeout_for_period(
                    latest_closeouts, co_code, co_year, co_quarter, _co_unit,
                )
                if runtime_duplicate is not None:
                    form_errors.append(
                        _closeout_duplicate_message(runtime_duplicate, co_year, co_quarter)
                    )

                if form_errors:
                    for message in dict.fromkeys(form_errors):
                        st.error(message)
                else:
                    try:
                        route = resolve_manual_closeout_route(current_user)
                        is_super = is_super_admin_user(current_user)
                        payload = {
                            "strat_code": co_code,
                            "period_year": str(co_year),
                            "period_quarter": co_quarter,
                            "scope": "Квартал",
                            "npa_links": clean(co_npa).strip(),
                            "admin_id": current_user.get("full_name", "") or current_user.get("id", ""),
                            "admin_email": current_user.get("email", ""),
                            "reason": clean(co_reason).strip(),
                            "evidence_note": clean(co_evidence).strip(),
                            "fact_status": co_fact_status,
                            "fact_value": co_fact_value,
                            # База вимагає fact_progress_text; єдине обов'язкове
                            # пояснення користувача передається сюди без дублювання поля.
                            "fact_progress_text": clean(co_reason).strip(),
                            "department": _co_department,
                            "object_name": _co_object_name,
                            "indicator_name": _co_indicator,
                            "approval_status": "Підтверджено" if is_super else "Очікує підтвердження",
                            **({
                                "superadmin_id": current_user.get("id", ""),
                                "decided_at": datetime.now(timezone.utc).isoformat(),
                                "head_status": "Очікує реакції",
                            } if is_super else {}),
                            **route,
                        }
                        prepared_payload = prepare_closeout_payload(payload)
                        result = create_closeout(
                            payload=prepared_payload,
                            user=current_user,
                        )
                        carried_quarters = []
                        if is_super:
                            closeout_id = int(result.data.get("closeout_id"))
                            carried_quarters = _reconcile_confirmed_closeout(
                                closeout_id,
                                prepared_payload,
                                _co_measure_row,
                                transition_result=result,
                            )
                        notice = (
                            "Захід закрито вручну; офіційні дані записано в моніторинг."
                            if is_super else
                            "Запит на ручне закриття надіслано на підтвердження відповідальному супер-адміну."
                        )
                        if carried_quarters:
                            notice += " " + _carry_quarters_text(carried_quarters, co_year)
                        st.session_state["closeout_submit_notice"] = notice
                        load_closeout_requests.clear()
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
                            <div class="admin-request-nature manual"><b>Запит на ручне закриття.</b> Адміністратор просить підтвердити офіційне закриття заходу без звичайної заявки ССП.</div>
                            <div class="review-title">Захід {clean(co_row.get("strat_code",""))}
                                — {clean(co_row.get("period_quarter",""))} кв. {clean(co_row.get("period_year",""))}</div>
                            <div><b>Підстава:</b> {clean(co_row.get("reason",""))}</div>
                            <div><b>Статус виконання:</b> {clean(co_row.get("fact_status",""))}</div>
                            <div><b>Фактичне значення:</b> {clean(co_row.get("fact_numeric_value","")) or clean(co_row.get("fact_value_text",""))}</div>
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

                            decision_result = decide_closeout(
                                closeout_id=int(co_row.get("id")),
                                expected_status="Очікує підтвердження",
                                new_status=new_co_status,
                                decision_comment=clean(co_decision_comment),
                                head_email=clean((_head_user or {}).get("email", "")),
                                user=current_user,
                            )
                            carried_quarters = []
                            if new_co_status == "Підтверджено":
                                _matrix_row = _m.iloc[0] if not _m.empty else {}
                                confirmed_record = co_row.to_dict()
                                confirmed_record["approval_status"] = "Підтверджено"
                                carried_quarters = _reconcile_confirmed_closeout(
                                    int(co_row.get("id")),
                                    confirmed_record,
                                    _matrix_row,
                                    transition_result=decision_result,
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

                            load_closeout_requests.clear()
                            load_manual_closeouts.clear()
                            decision_notice = f"Запит на закриття заходу {new_co_status.lower()}."
                            if carried_quarters:
                                decision_notice += " " + _carry_quarters_text(
                                    carried_quarters, co_row.get("period_year"),
                                )
                            st.session_state["closeout_submit_notice"] = decision_notice
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
                            load_closeout_requests.clear()
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
                            load_closeout_requests.clear()
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
                        load_closeout_requests.clear()
                        load_manual_closeouts.clear()
                        st.success("Закриття відкликано.")
                        monitoring_data.invalidate_monitoring_cache()
                        st.rerun()
                    except Exception as exc:
                        show_incident(exc, context="Відкликання підтвердженого ручного закриття")

    st.markdown('</div>', unsafe_allow_html=True)

    # ──────────────────────────────────────────────
    # АРХІВ (заморожені знімки періодів)
    # ──────────────────────────────────────────────



    _render_superadmin_bottom_tools()
    render_footer()
    st.stop()

if _no_requests_at_all or df.empty:
    st.warning(
        "Поки що немає заявок, доступних за вашими закріпленими ССП. "
        "Режим «Ручне закриття заходів» доступний через перемикач вище."
    )
    _render_superadmin_bottom_tools()
    render_footer()
    st.stop()


attention = build_attention_summary(df)

# ──────────────────────────────────────────────
# СИСТЕМНИЙ АНАЛІЗ
# ──────────────────────────────────────────────

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

def sort_and_show(frame):
    frame = _sort_by_ssp(frame)
    if frame.empty:
        st.info("Записів немає.")
        return
    table_rows = [
        _request_table_values(row)
        for _, row in frame.iterrows()
    ]
    _render_html_table(_REQUEST_TABLE_HEADERS, table_rows)


with st.expander("Перегляд записів"):
    t1, t2, t3, t4 = st.tabs([
        "Погоджено",
        "На розгляді",
        "На розгляді понад 5 днів",
        "На доопрацюванні",
    ])
    with t1:
        sort_and_show(attention["approved"])
    with t2:
        sort_and_show(attention["waiting"])
    with t3:
        sort_and_show(attention["long_waiting"])
    with t4:
        sort_and_show(attention["returned"])

# ──────────────────────────────────────────────
# ІНФОГРАФІКА
# ──────────────────────────────────────────────

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

# ──────────────────────────────────────────────
# ПАРАМЕТРИ ВІДБОРУ
# ──────────────────────────────────────────────

all_ssp_raw = sorted(
    {idx for _, row in df.iterrows() for idx in split_ssp_values(row.get("department", ""))},
    key=lambda x: int(x) if str(x).isdigit() else 9999,
)

if user_has_all_ssp_access(current_user):
    available_ssp_raw = all_ssp_raw
else:
    allowed_ssp_indexes = get_user_allowed_ssp_indexes(current_user)
    available_ssp_raw = [
        index for index in all_ssp_raw if index in allowed_ssp_indexes
    ]

years = sorted(df["year"].dropna().astype(str).unique().tolist())
quarters = sorted(df["quarter"].dropna().astype(str).unique().tolist())
approval_options = [
    "Активні до розгляду", "Усі", "Очікує погодження",
    "Очікує: Керівник управління", "Очікує: Заступник керівника ССП",
    "Повернуто на доопрацювання", "Очікує: Керівник ССП", "Погоджено",
]
quick_filter_options = [
    "Усі заявки", "Тільки очікують", "Повернуті", "Із ризиками",
    "Останні подані", "На розгляді понад 5 днів",
]

# ТЗ Заг.1: фільтри спрацьовують ТІЛЬКИ після кнопки застосування.
_adm_flt_defaults = {
    "ssp": "Усі", "year": "Усі", "quarter": "Усі",
    "approval": "Активні до розгляду", "quick": "Усі заявки", "search": "",
}
if "admin_filters_applied_v19" not in st.session_state:
    st.session_state["admin_filters_applied_v19"] = _adm_flt_defaults.copy()

_adm_pending_keys = {
    "ssp": "admin_filter_ssp_pending_v19",
    "year": "admin_filter_year_pending_v19",
    "quarter": "admin_filter_quarter_pending_v19",
    "approval": "admin_filter_approval_pending_v19",
    "quick": "admin_filter_quick_pending_v19",
    "search": "admin_filter_search_pending_v19",
}
for _filter_name, _filter_key in _adm_pending_keys.items():
    st.session_state.setdefault(
        _filter_key,
        st.session_state["admin_filters_applied_v19"].get(
            _filter_name, _adm_flt_defaults[_filter_name]
        ),
    )

_valid_options = {
    "ssp": ["Усі"] + available_ssp_raw,
    "year": ["Усі"] + years,
    "quarter": ["Усі"] + quarters,
    "approval": approval_options,
    "quick": quick_filter_options,
}
for _filter_name, _options in _valid_options.items():
    _filter_key = _adm_pending_keys[_filter_name]
    if st.session_state.get(_filter_key) not in _options:
        st.session_state[_filter_key] = _adm_flt_defaults[_filter_name]


def _apply_admin_filters_v19():
    st.session_state["admin_filters_applied_v19"] = {
        name: st.session_state.get(key, _adm_flt_defaults[name])
        for name, key in _adm_pending_keys.items()
    }


def _reset_admin_filters_v19():
    st.session_state["admin_filters_applied_v19"] = _adm_flt_defaults.copy()
    for name, key in _adm_pending_keys.items():
        st.session_state[key] = _adm_flt_defaults[name]


with st.form("admin_filters_form_v19"):
    st.markdown('<div class="filter-title">Параметри відбору</div>', unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        st.markdown('<div class="filter-field-label">ССП</div>', unsafe_allow_html=True)
        st.selectbox(
            "Самостійний структурний підрозділ",
            ["Усі"] + available_ssp_raw,
            key=_adm_pending_keys["ssp"],
            label_visibility="collapsed",
        )
    with f2:
        st.markdown('<div class="filter-field-label">Рік</div>', unsafe_allow_html=True)
        st.selectbox(
            "Рік", ["Усі"] + years,
            key=_adm_pending_keys["year"], label_visibility="collapsed",
        )
    with f3:
        st.markdown('<div class="filter-field-label">Квартал</div>', unsafe_allow_html=True)
        st.selectbox(
            "Квартал", ["Усі"] + quarters,
            key=_adm_pending_keys["quarter"], label_visibility="collapsed",
        )
    with f4:
        st.markdown('<div class="filter-field-label">Статус погодження</div>', unsafe_allow_html=True)
        st.selectbox(
            "Статус погодження", approval_options,
            key=_adm_pending_keys["approval"], label_visibility="collapsed",
        )

    q1, q2 = st.columns([1, 2])
    with q1:
        st.markdown('<div class="filter-field-label">Швидкий фільтр</div>', unsafe_allow_html=True)
        st.selectbox(
            "Швидкий фільтр", quick_filter_options,
            key=_adm_pending_keys["quick"], label_visibility="collapsed",
        )
    with q2:
        st.markdown(
            '<div class="filter-field-label">Пошук за ID, назвою заходу, ПІБ або ССП</div>',
            unsafe_allow_html=True,
        )
        st.text_input(
            "Пошук за ID, назвою заходу, ПІБ або ССП",
            key=_adm_pending_keys["search"],
            label_visibility="collapsed",
        )

    _bt1, _bt2 = st.columns([2, 1])
    with _bt1:
        st.form_submit_button(
            "Застосувати обрані параметри",
            use_container_width=True,
            on_click=_apply_admin_filters_v19,
        )
    with _bt2:
        st.form_submit_button(
            "Скинути параметри",
            use_container_width=True,
            on_click=_reset_admin_filters_v19,
        )

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

if filtered.empty:
    st.info("За обраними фільтрами заявок не знайдено.")
    _render_superadmin_bottom_tools()
    render_footer()
    st.stop()

# ──────────────────────────────────────────────
# ЧЕРГА НА РОЗГЛЯД
# ──────────────────────────────────────────────

# ТЗ-правка (09.07.2026, п.3): у черзі та в полі вибору — ЛИШЕ заявки,
# що очікують рішення САМЕ поточного користувача (його ланка в схемі).
# Заявки, що зараз на інших ланках, у черзі поточного користувача не показуються.
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
queue_df["_review_days"] = queue_df["submitted_at"].apply(_review_days)
queue_df = _sort_by_ssp(queue_df)

if not queue_df.empty:
    st.markdown(
        '<div class="myreq-section-header"><div class="myreq-section-title">'
        '📋 Черга на розгляд</div></div>',
        unsafe_allow_html=True,
    )
    _queue_headers = [
        "ID", "На розгляді (днів)", "ССП", "Код заходу", "Звітний період",
        "Особа, яка подала інформацію", "Дата подання",
    ]
    _queue_rows = []
    for _, row in queue_df.iterrows():
        person, _ = _initial_submitter_for_request(row)
        _queue_rows.append([
            row.get("id"),
            row.get("_review_days") if pd.notna(row.get("_review_days")) else "—",
            row.get("department"),
            row.get("strat_code"),
            _period_label(row.get("year"), row.get("quarter")),
            person,
            format_kyiv_datetime(row.get("submitted_at")),
        ])
    _render_html_table(_queue_headers, _queue_rows)
    st.markdown(
        '<div class="admin-section-spacer" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )

# ──────────────────────────────────────────────
# ВИБІР ЗАЯВКИ
# ──────────────────────────────────────────────

# Вибір має реагувати одразу, тому це стилізований контейнер, а не st.form.
_selectable = queue_df if not queue_df.empty else filtered.iloc[0:0]

if _selectable.empty:
    with st.container(border=True):
        st.markdown('<div class="filter-title">Вибір заявки</div>', unsafe_allow_html=True)
        st.info("Наразі немає заявок, що очікують саме вашого рішення.")
    _render_superadmin_bottom_tools()
    render_footer()
    st.stop()

selected_options = []
for _, row in _selectable.iterrows():
    person, _ = _initial_submitter_for_request(row)
    review_days = row.get("_review_days")
    review_days_text = str(int(review_days)) if pd.notna(review_days) else "—"
    selected_options.append(
        f"ID {row['id']} | {review_days_text} дн. | ССП {clean(row.get('department'))} | "
        f"{clean(row.get('strat_code'))} | {_period_label(row.get('year'), row.get('quarter'))} | "
        f"{person} | {format_kyiv_datetime(row.get('submitted_at'))}"
    )

with st.container(border=True):
    st.markdown('<div class="filter-title">Вибір заявки</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="filter-field-label">Оберіть заявку для перегляду та погодження</div>',
        unsafe_allow_html=True,
    )
    selected_request = st.selectbox(
        "Оберіть заявку для перегляду та погодження",
        selected_options,
        label_visibility="collapsed",
    )

selected_id = int(selected_request.split("|", 1)[0].replace("ID", "").strip())
selected_row = _selectable[_selectable["id"].astype(int) == selected_id].iloc[0]

_detail_context = _render_request_detail_cards(selected_row)
approval_status = _detail_context["approval_status"]
selected_code = _detail_context["selected_code"]
year_val = _detail_context["year_val"]
target_year_val = _detail_context["target_year_val"]
_strat_record = _detail_context["strat_record"]
_unit = _detail_context["unit"]
person_name = _detail_context["person_name"]
person_phone = _detail_context["person_phone"]
person_email = _detail_context["person_email"]
_req_chain = _detail_context["req_chain"]
_req_stage = _detail_context["req_stage"]
_req_kind = _detail_context["req_kind"]
_req_dept_idx = _detail_context["req_dept_idx"]

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
    _sa_options.append("Повернути на доопрацювання")
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
    '<div class="card decision-card">'
    '<div class="card-title">Рішення адміністратора</div>',
    unsafe_allow_html=True,
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
        "пройдено (статус «Погоджено»). Рішення координатора (погодити або "
        "повернути на доопрацювання) для цієї заявки "
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

    st.markdown(
        """
        <div class="decision-guidance">
            <p>Після звірки поданих відомостей, якщо зауважень немає і ви готові погодити заявку, перегляньте схему погодження. За потреби наступну ланку можна змінити або додати, але не на ланку, нижчу за вже пройдені. Якщо схема коректна, змінювати її не потрібно.</p>
            <p>Коментар адміністратора є обов’язковим для будь-якого рішення. Його побачить наступна ланка погодження, а текст буде зафіксовано в журналі дій.</p>
            <p>Якщо потрібна додаткова перевірка, у полі «Що далі після координатора» оберіть варіант із додаванням супер-адміна після себе. Якщо інформація потребує виправлення, оберіть «Повернути на доопрацювання», зазначте адресата повернення та чітко опишіть у коментарі, що саме потрібно виправити.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="admin-control-label">Оберіть рішення</div>',
        unsafe_allow_html=True,
    )
    decision = st.radio(
        "Оберіть рішення",
        [_approve_option, "Повернути на доопрацювання"],
        horizontal=True,
        key=f"decision_radio_{selected_id}",
        label_visibility="collapsed",
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

    return_target_label = None
    if decision == "Повернути на доопрацювання":
        return_target_label = st.selectbox(
            "Кому повернути",
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

        if not clean(admin_comment).strip():
            st.error("Коментар адміністратора є обов’язковим для будь-якого рішення.")
            _decision_blocked = True

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
    st.success(st.session_state["adm_last_decision_notice"])
    if st.button("Зрозуміло, приховати це повідомлення", key="adm_dismiss_decision_notice"):
        st.session_state.pop("adm_last_decision_notice", None)
        st.rerun()



logs_df = load_logs(selected_id, selected_row)

if logs_df.empty:
    st.info("Історії змін для цієї заявки поки що немає.")
else:
    # Хронологічний таймлайн завжди видно без додаткового розкривання.
    render_request_timeline(
        logs_df,
        title="Історія змін заявки",
        with_table_expander=False,
    )

    show_logs = logs_df.copy()
    # Історію розширено фактичним значенням та описом прогресу з версій
    # заявки на момент кожної події, а за їх відсутності — поточними даними.
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
            _facts.append(
                clean(_row.get("numeric_value", ""))
                if _row is not None
                else clean(selected_row.get("numeric_value", ""))
            )
            _progress.append(
                clean(_row.get("progress_text", ""))
                if _row is not None
                else clean(selected_row.get("progress_text", ""))
            )
    else:
        _facts = [clean(selected_row.get("numeric_value", ""))] * len(show_logs)
        _progress = [clean(selected_row.get("progress_text", ""))] * len(show_logs)
    show_logs["Фактичне значення"] = _facts
    show_logs["Опис прогресу"] = _progress

    history_table = prepare_human_log_table(
        show_logs,
        extra_columns=["Фактичне значення", "Опис прогресу"],
    )
    with st.expander("Повна історія змін заявки (табличний вигляд)"):
        _render_html_table(
            list(history_table.columns),
            [list(row) for row in history_table.itertuples(index=False, name=None)],
            empty_message="Історії змін для цієї заявки поки що немає.",
        )

_render_superadmin_bottom_tools()

# ТЗ Адм.3: функцію «Архівування» повністю прибрано з адміністрування —
# без заглушок і службових карток.

render_footer()
