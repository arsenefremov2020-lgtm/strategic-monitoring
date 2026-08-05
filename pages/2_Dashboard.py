import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core.period_locks import is_period_locked
from core.timeutils import now_kyiv
from core.db import get_supabase_client
from core.deputies import DEPUTY_MINISTER_BY_SSP
from core.config import FILE_PATH, SHEET_NAME
from core.excel_loader import read_excel_sheet
from core.page_setup import page_setup, render_footer
from core.strategic_data import load_strat_matrix as core_load_strat_matrix
from core import monitoring_data
from core import statuses as core_statuses
from core.periods import quarter_key as core_quarter_key
from core.periods import parse_period as core_parse_period
from core.periods import period_number as core_period_number
from core import operational
from core.closeouts import load_manual_closeouts
from core.exports import build_presentation_pdf
from core.errors import log_cosmetic_error, show_incident
from core.periods import get_period_state
from core.filters import get_source_options, match_source
from core.access import (
    filter_actions_for_user,
    filter_requests_for_user,
    is_scope_lockable_user,
    is_scope_override_active,
    get_user_ssp_index,
)
from core.ui import render_scope_toggle, render_auto_refresh_notice
from core.stage4 import render_measure_rows_with_card_links
from datetime import datetime
from html import escape
import re

current_user = page_setup("Dashboard", page_name="Dashboard")
render_auto_refresh_notice("Dashboard", minutes=5)
supabase = get_supabase_client()

# ============================================================
# STYLE
# ============================================================

st.markdown("""
<style>
header[data-testid="stHeader"] {
    background: transparent !important;
}
@import url('https://fonts.googleapis.com/css2?family=e-Ukraine:wght@300;400;500;700&display=swap');

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Helvetica Neue', 'Arial', sans-serif;
}

.stApp {
    background: #F7F9FC;
}

/* Subtle geometric background pattern */
.main .block-container {
    max-width: min(1500px, 98vw);
    padding: clamp(0.5rem, 2vw, 1.5rem) clamp(0.5rem, 2vw, 2rem);
    position: relative;
    z-index: 1;
}

/* ── UA accent stripe ── */
.ua-stripe {
    height: 5px;
    border-radius: 0 0 6px 6px;
    background: linear-gradient(90deg, #005BBB 50%, #FFD500 50%);
    margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(0,91,187,0.15);
}

/* ── Ministry label ── */
.ministry-label {
    text-align: right;
    color: #61708A;
    font-size: clamp(11px, 1.1vw, 14px);
    font-weight: 700;
    margin-bottom: 10px;
    letter-spacing: 0.01em;
}

/* ── Header card ── */
.header-card {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-left: 5px solid #005BBB;
    border-radius: 12px;
    padding: clamp(16px, 2.5vw, 28px) clamp(16px, 2.5vw, 32px);
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(0,91,187,0.08), 0 1px 4px rgba(0,0,0,0.04);
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 16px;
}

.header-main {
    flex: 1 1 100%;
    width: 100%;
    min-width: 200px;
}

.header-title {
    font-size: clamp(20px, 2.5vw, 30px);
    font-weight: 900;
    color: #032A63;
    margin: 0 0 6px 0;
    line-height: 1.2;
}

.header-subtitle {
    font-size: clamp(12px, 1.1vw, 14px);
    color: #61708A;
    line-height: 1.6;
    max-width: none;
    width: 100%;
}

.header-pills {
    flex: 0 1 auto;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: flex-start;
    padding-top: 4px;
}

.pill {
    background: #EAF1FF;
    border: 1px solid #BFD3F2;
    border-radius: 20px;
    padding: 5px 12px;
    font-size: clamp(10px, 0.9vw, 12px);
    color: #032A63;
    font-weight: 600;
    white-space: nowrap;
}

/* ── Section card ── */
.section-card {
    background: #ffffff;
    border: 1px solid #DCE4F0;
    border-radius: 12px;
    padding: clamp(14px, 2vw, 22px) clamp(14px, 2vw, 24px);
    margin-bottom: 18px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}

div[data-testid="stMarkdownContainer"] .section-card:empty {
    display: none !important;
}

.section-title {
    font-size: clamp(15px, 1.4vw, 19px);
    font-weight: 800;
    color: #032A63;
    margin: 0 0 4px 0;
}

.section-subtitle {
    font-size: clamp(11px, 0.95vw, 13px);
    color: #61708A;
    margin: 0 0 14px 0;
}

/* ── Dashboard filter form ── */
/* Поля, підписи та кнопки використовують єдиний системний шаблон
   з assets/app.css. Тут залишається лише компактне оформлення
   expander додаткових параметрів, ідентичне сторінці «Головна». */
.st-key-dashboard_additional_parameters div[data-testid="stExpander"] {
    border: 1px solid #DCE4F0 !important;
    border-radius: 10px !important;
    margin: 8px 0 14px 0 !important;
    background: #FFFFFF !important;
    overflow: hidden;
}

.st-key-dashboard_additional_parameters div[data-testid="stExpander"] > details > summary {
    background: #F7F9FC !important;
    color: #132238 !important;
    border-radius: 9px !important;
    padding: 9px 12px !important;
    min-height: 38px !important;
    font-weight: 700 !important;
    box-shadow: none !important;
}

.st-key-dashboard_additional_parameters div[data-testid="stExpander"] > details > summary:hover {
    background: #EEF3F9 !important;
}

.st-key-dashboard_additional_parameters div[data-testid="stExpander"] > details > summary p {
    color: #132238 !important;
    font-size: 14px !important;
    font-weight: 700 !important;
}

.st-key-dashboard_additional_parameters div[data-testid="stExpander"] > details > summary svg {
    color: #61708A !important;
    fill: #61708A !important;
}

.dashboard-filter-subtitle {
    margin-top: 0 !important;
}

/* ── Compact section summaries ── */
.section-summary {
    background: #F8FAFD;
    border: 1px solid #DCE4F0;
    border-left: 4px solid #BFD3F2;
    border-radius: 10px;
    padding: 12px 16px;
    margin: 8px 0 18px 0;
    min-height: 84px;
    box-shadow: 0 1px 5px rgba(15, 35, 65, 0.035);
}

.section-summary-risk-high { border-left-color: #DC4A4A; }
.section-summary-risk-medium { border-left-color: #F4B400; }
.section-summary-risk-low { border-left-color: #118847; }
.section-summary-neutral { border-left-color: #4D8DFF; }

.section-summary-head {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 6px;
}

.section-summary-title {
    font-size: clamp(13px, 1.1vw, 15px);
    font-weight: 900;
    color: #032A63;
    line-height: 1.25;
}

.section-summary-badge {
    background: #FFFFFF;
    border: 1px solid #DCE4F0;
    border-radius: 999px;
    padding: 3px 9px;
    font-size: clamp(10px, 0.85vw, 12px);
    font-weight: 800;
    color: #44546A;
    white-space: nowrap;
}

.section-summary-text {
    font-size: clamp(11px, 0.95vw, 13px);
    color: #61708A;
    line-height: 1.5;
}

.section-summary-metrics {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin-top: 8px;
}

.section-summary-chip {
    background: #FFFFFF;
    border: 1px solid #DCE4F0;
    border-radius: 999px;
    padding: 3px 9px;
    font-size: clamp(10px, 0.85vw, 12px);
    font-weight: 700;
    color: #44546A;
    white-space: nowrap;
}

/* ── KPI status grid ── */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: clamp(8px, 1.2vw, 14px);
    margin: 6px 0 4px 0;
}

.kpi-card {
    border-radius: 10px;
    padding: clamp(10px, 1.4vw, 16px);
    border: 1px solid transparent;
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.kpi-title {
    font-size: clamp(10px, 0.85vw, 12px);
    font-weight: 700;
    color: #61708A;
    min-height: 28px;
    line-height: 1.3;
}

.kpi-value {
    font-size: clamp(22px, 2.5vw, 32px);
    font-weight: 900;
    color: #032A63;
    line-height: 1;
    margin-top: 2px;
}

.kpi-pct {
    font-size: clamp(11px, 0.95vw, 13px);
    font-weight: 700;
    color: #61708A;
    margin-top: 4px;
}

.kpi-blue  { background: #E3EDFF; border-color: #BFD3F2; }
.kpi-blue .kpi-value { color: #4D8DFF; }
.kpi-green { background: #E4F5EC; border-color: #1E9E57; }
.kpi-red   { background: #FBE5E5; border-color: #DC4A4A; }
.kpi-red .kpi-value { color: #FF7A45; }
.kpi-yellow{ background: #FDF3D8; border-color: #F4B400; }
.kpi-yellow .kpi-value { color: #FF7A45; }
.kpi-gray  { background: #F7F9FC; border-color: #DCE4F0; }
.kpi-gray .kpi-value { color: #8A96A8; }
.kpi-card { display:block; text-decoration:none !important; cursor:pointer; color:inherit !important; }
.kpi-card:hover { transform:translateY(-2px); box-shadow:0 8px 18px rgba(15,23,42,.10); }
.kpi-card.kpi-active { outline:3px solid rgba(37,99,235,.22); border-color:#4D8DFF; }

/* ── Insight items ── */
.insight-item {
    background: #F7F9FC;
    border-left: 4px solid #005BBB;
    border-radius: 0 8px 8px 0;
    padding: clamp(8px, 1vw, 12px) clamp(12px, 1.5vw, 16px);
    margin-bottom: 8px;
    font-size: clamp(12px, 1vw, 14px);
    color: #132238;
    line-height: 1.5;
}

.insight-item.warn { border-left-color: #FF7A45; background: #FDF3D8; }
.insight-item.danger { border-left-color: #DC4A4A; background: #FBE5E5; }
.insight-item.info { border-left-color: #00A8A8; background: #EAF1FF; }

/* ── Linear indicator rows ── */
.indicator-row {
    margin-bottom: 10px;
}

.indicator-label {
    display: flex;
    justify-content: space-between;
    font-size: clamp(11px, 0.95vw, 13px);
    font-weight: 600;
    color: #61708A;
    margin-bottom: 4px;
}

.indicator-bar-bg {
    background: #DCE4F0;
    border-radius: 99px;
    height: 8px;
    overflow: hidden;
}

.indicator-bar-fill {
    height: 100%;
    border-radius: 99px;
    transition: width 0.4s ease;
}

/* ── Chart container ── */
.chart-wrap {
    background: #ffffff;
    border: 1px solid #EAF1FF;
    border-radius: 10px;
    padding: clamp(10px, 1.5vw, 16px);
    margin-bottom: 10px;
}

.chart-title {
    font-size: clamp(12px, 1.1vw, 15px);
    font-weight: 800;
    color: #032A63;
    margin-bottom: 6px;
}

/* ── Dashboard tables: єдиний HTML-стандарт системи ── */
.dashboard-html-table-wrap .myreq-html-table th,
.dashboard-html-table-wrap .myreq-html-table td {
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
    overflow-wrap: anywhere !important;
    word-break: normal !important;
    height: auto !important;
    line-height: 1.35 !important;
}

.dashboard-html-table-wrap .myreq-html-table th,
.dashboard-html-table-wrap .myreq-html-table td {
    vertical-align: middle;
}

.dashboard-html-table-wrap .dashboard-rank-green td {
    background: #E4F5EC !important;
    color: #0C713A !important;
    font-weight: 800;
}

.dashboard-html-table-wrap .dashboard-rank-yellow td {
    background: #FDF3D8 !important;
    color: #7A5A00 !important;
}

.dashboard-html-table-wrap .dashboard-rank-red td {
    background: #FBE5E5 !important;
    color: #B42318 !important;
}

/* ── Methodology ── */
.methodology-box {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-radius: 10px;
    padding: 16px 20px;
    font-size: clamp(11px, 0.95vw, 13px);
    color: #61708A;
    line-height: 1.7;
}

/* ── Footer ── */
.footer {
    text-align: center;
    color: #8A96A8;
    font-size: clamp(10px, 0.9vw, 12px);
    margin-top: 40px;
    padding: 18px 0 10px;
    border-top: 1px solid #DCE4F0;
}

/* ── Separator ── */
.vis-separator {
    border: none;
    border-top: 1px solid #DCE4F0;
    margin: 22px 0;
}

/* ══════════════════════════════════════════════
   PRESENTATION MODE — PowerPoint-like design
   ══════════════════════════════════════════════ */

.pres-overlay {
    position: fixed;
    inset: 0;
    background: #032A63;
    z-index: 9999;
    overflow-y: auto;
    font-family: 'Helvetica Neue', 'Arial', sans-serif;
    padding: 0;
}

/* Navigation bar */
.pres-nav {
    position: sticky;
    top: 0;
    z-index: 10001;
    background: rgba(10,15,30,0.95);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid rgba(255,255,255,0.08);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 32px;
}

.pres-nav-title {
    color: rgba(255,255,255,0.5);
    font-size: 12px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    font-weight: 600;
}

.pres-nav-dots {
    display: flex;
    gap: 8px;
    align-items: center;
}

.pres-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: rgba(255,255,255,0.2);
    cursor: pointer;
    transition: all 0.2s;
}

.pres-dot.active {
    background: #FFD500;
    width: 24px;
    border-radius: 4px;
}

.pres-ua-bar {
    height: 3px;
    background: linear-gradient(90deg, #005BBB 50%, #FFD500 50%);
    width: 100%;
}

/* Individual slide */
.pres-slide {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 48px 64px;
    position: relative;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}

.pres-slide:last-child { border-bottom: none; }

/* Slide number */
.pres-slide-num {
    position: absolute;
    top: 24px; right: 40px;
    font-size: 11px;
    color: rgba(255,255,255,0.2);
    letter-spacing: 0.1em;
    font-weight: 600;
}

/* Slide 1 — Title slide */
.pres-slide-title {
    background: #032A63;
}

.pres-title-eyebrow {
    font-size: 11px;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #FFD500;
    font-weight: 700;
    margin-bottom: 20px;
}

.pres-title-h1 {
    font-size: clamp(32px, 4vw, 56px);
    font-weight: 900;
    color: #ffffff;
    line-height: 1.1;
    margin-bottom: 16px;
    max-width: 800px;
}

.pres-title-sub {
    font-size: clamp(14px, 1.4vw, 18px);
    color: rgba(255,255,255,0.5);
    max-width: 600px;
    line-height: 1.6;
    margin-bottom: 40px;
}

.pres-filter-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 8px;
}

.pres-filter-pill {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 20px;
    padding: 6px 16px;
    font-size: 12px;
    color: rgba(255,255,255,0.7);
    font-weight: 600;
}

/* Slide 2 — Conclusion / Status */
.pres-slide-conclusion {
    background: #032A63;
}

.pres-slide-conclusion.ok {
    background: #032A63;
}

.pres-slide-conclusion.medium {
    background: #032A63;
}

.pres-section-label {
    font-size: 11px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: rgba(255,255,255,0.35);
    font-weight: 700;
    margin-bottom: 24px;
}

.pres-verdict-badge {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 10px 24px;
    border-radius: 10px;
    font-size: clamp(18px, 2vw, 26px);
    font-weight: 900;
    margin-bottom: 20px;
}

.pres-verdict-badge.high { background: rgba(220,38,38,0.2); border: 1.5px solid #DC4A4A; color: #DC4A4A; }
.pres-verdict-badge.medium { background: rgba(217,119,6,0.2); border: 1.5px solid #FF7A45; color: #F4B400; }
.pres-verdict-badge.low { background: rgba(22,163,74,0.2); border: 1.5px solid #118847; color: #1E9E57; }

.pres-verdict-text {
    font-size: clamp(13px, 1.2vw, 16px);
    color: rgba(255,255,255,0.55);
    max-width: 680px;
    line-height: 1.7;
    margin-bottom: 40px;
}

/* Slide 3 — KPI Metrics */
.pres-slide-kpis {
    background: #032A63;
}

.pres-kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    margin-top: 32px;
}

.pres-kpi-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 28px 24px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    position: relative;
    overflow: hidden;
}

.pres-kpi-card::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: 14px 14px 0 0;
}

.pres-kpi-card.blue::before { background: #4D8DFF; }
.pres-kpi-card.green::before { background: #00A8A8; }
.pres-kpi-card.red::before { background: #FF7A45; }
.pres-kpi-card.yellow::before { background: #F4B400; }
.pres-kpi-card.gray::before { background: #8A96A8; }

.pres-kpi-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: rgba(255,255,255,0.4);
}

.pres-kpi-value {
    font-size: clamp(36px, 4vw, 56px);
    font-weight: 900;
    color: #ffffff;
    line-height: 1;
}

.pres-kpi-sub {
    font-size: 13px;
    color: rgba(255,255,255,0.35);
    font-weight: 600;
}

/* Slide 4 — Goals */
.pres-slide-goals {
    background: #032A63;
}

.pres-goal-bar-wrap {
    margin-top: 28px;
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.pres-goal-row {
    display: flex;
    align-items: center;
    gap: 16px;
}

.pres-goal-code {
    font-size: 11px;
    font-weight: 800;
    color: rgba(255,255,255,0.4);
    min-width: 36px;
    text-align: right;
}

.pres-goal-name {
    font-size: 13px;
    color: rgba(255,255,255,0.7);
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 320px;
}

.pres-goal-bar-bg {
    flex: 2;
    background: rgba(255,255,255,0.06);
    border-radius: 99px;
    height: 10px;
    overflow: hidden;
}

.pres-goal-bar-fill {
    height: 100%;
    border-radius: 99px;
}

.pres-goal-pct {
    font-size: 13px;
    font-weight: 800;
    color: #ffffff;
    min-width: 44px;
    text-align: right;
}

/* Slide 5 — Risk */
.pres-slide-risks {
    background: #032A63;
}

.pres-risk-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
    margin-top: 32px;
}

.pres-risk-card {
    border-radius: 14px;
    padding: 28px 24px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.pres-risk-card.high { background: rgba(220,38,38,0.12); border: 1.5px solid rgba(220,38,38,0.3); }
.pres-risk-card.medium { background: rgba(217,119,6,0.1); border: 1.5px solid rgba(217,119,6,0.25); }
.pres-risk-card.low { background: rgba(22,163,74,0.1); border: 1.5px solid rgba(22,163,74,0.25); }

.pres-risk-label { font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; }
.pres-risk-card.high .pres-risk-label { color: #DC4A4A; }
.pres-risk-card.medium .pres-risk-label { color: #F4B400; }
.pres-risk-card.low .pres-risk-label { color: #1E9E57; }

.pres-risk-val {
    font-size: clamp(40px, 5vw, 64px);
    font-weight: 900;
    line-height: 1;
}
.pres-risk-card.high .pres-risk-val { color: #DC4A4A; }
.pres-risk-card.medium .pres-risk-val { color: #F4B400; }
.pres-risk-card.low .pres-risk-val { color: #1E9E57; }

.pres-risk-sub { font-size: 13px; color: rgba(255,255,255,0.4); font-weight: 600; }

/* Slide heading */
.pres-slide-h2 {
    font-size: clamp(24px, 2.8vw, 38px);
    font-weight: 900;
    color: #ffffff;
    margin-bottom: 4px;
    line-height: 1.15;
}

.pres-slide-hsub {
    font-size: clamp(12px, 1.1vw, 15px);
    color: rgba(255,255,255,0.4);
    margin-bottom: 0;
}

/* Progress bar for metrics slide */
.pres-metric-rows {
    margin-top: 32px;
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.pres-metric-row {
    display: flex;
    align-items: center;
    gap: 20px;
}

.pres-metric-label {
    font-size: 13px;
    font-weight: 700;
    color: rgba(255,255,255,0.55);
    min-width: 220px;
}

.pres-metric-bar-bg {
    flex: 1;
    background: rgba(255,255,255,0.06);
    border-radius: 99px;
    height: 12px;
    overflow: hidden;
}

.pres-metric-bar-fill {
    height: 100%;
    border-radius: 99px;
}

.pres-metric-val {
    font-size: 16px;
    font-weight: 900;
    color: #ffffff;
    min-width: 56px;
    text-align: right;
}

/* Exit button (handled by Streamlit toggle) */
.pres-exit-hint {
    position: fixed;
    bottom: 24px;
    right: 32px;
    z-index: 10002;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 11px;
    color: rgba(255,255,255,0.35);
    letter-spacing: 0.08em;
    pointer-events: none;
}



/* ── Responsive: narrow screens ── */
@media (max-width: 900px) {
    .header-card { flex-direction: column; }
    .header-pills { flex-direction: row; }
    .kpi-grid { grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 600px) {
    .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# DATA LOAD
# ============================================================

@st.cache_data
def load_strat_matrix():
    """Джерело даних — core.strategic_data (правка К1);
    тут лишається тільки нормалізація фінансових колонок Dashboard."""
    result = core_load_strat_matrix().copy()

    # ── Нормалізація фінансових колонок ──────────────────────────────────────
    _empty_str = ["nan", "none", "х", "x", "", "н.д.", "-", "—"]

    def _clean_kpkvk(val):
        s = str(val).strip()
        return "" if s.lower() in _empty_str else s

    def _clean_other_source(val):
        s = str(val).strip()
        if s.lower() in _empty_str:
            return ""
        return s.rstrip()

    result["budget_kpkvk"] = result["budget_kpkvk"].apply(_clean_kpkvk)
    result["other_source"] = result["other_source"].apply(_clean_other_source)
    result["budget_2026"] = pd.to_numeric(result["budget_2026"], errors="coerce")
    result["budget_2027"] = pd.to_numeric(result["budget_2027"], errors="coerce")
    result["budget_2028"] = pd.to_numeric(result["budget_2028"], errors="coerce")
    result["other_2026"] = result["other_2026"].apply(
        lambda v: str(v).strip() if str(v).strip().lower() not in _empty_str else "")
    result["other_2027"] = result["other_2027"].apply(
        lambda v: str(v).strip() if str(v).strip().lower() not in _empty_str else "")
    result["other_2028"] = result["other_2028"].apply(
        lambda v: str(v).strip() if str(v).strip().lower() not in _empty_str else "")

    result["has_state_budget"] = result["budget_kpkvk"].astype(bool)
    result["has_other_financing"] = result["other_source"].astype(bool)

    def _financing_type(row):
        types = []
        if row["has_state_budget"]:
            types.append("Державний бюджет")
        src = str(row["other_source"]).lower()
        if row["has_other_financing"]:
            if any(kw in src for kw in ["мтд", "мбрр", "партнер", "eu ", "єс ", "iprsa"]):
                types.append("МТД / кошти партнерів")
            elif any(kw in src for kw in ["фонд", "страхування", "небюджет"]):
                types.append("Небюджетні / інші")
            else:
                types.append("МТД / кошти партнерів")
        if not types:
            types.append("Без фінансування")
        return types

    result["financing_types"] = result.apply(_financing_type, axis=1)

    return result


def load_requests():
    """ЄДИНЕ джерело — core.monitoring_data (правки К2, П2).
    Dashboard аналізує ЗАХОДИ, тому подання індикаторів (object_kind='indicator')
    відфільтровуються одразу."""
    return monitoring_data.measures_only(monitoring_data.load_monitoring_requests())


# ============================================================
# HELPERS
# ============================================================

def clean(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value).strip()


def normalize_text(value):
    return str(value).strip().lower().replace("і", "i")


def to_number(value):
    text = str(value).replace(",", ".").replace("%", "").strip()
    if text.lower() in ["", "nan", "none", "н.д.", "нд", "x", "х", "так", "ні", "да", "нет", "-", "—"]:
        return None
    match = re.search(r"-?\d+(\.\d+)?", text)
    if match:
        try:
            return float(match.group())
        except Exception:
            return None
    return None


def parse_period(value):
    """Єдиний строгий розбір періоду через core.periods."""
    return core_parse_period(value)


def quarter_to_number(q):
    q = str(q).strip()
    mapping = {"I": 1, "II": 2, "III": 3, "IV": 4, "1": 1, "2": 2, "3": 3, "4": 4}
    return mapping.get(q, 1)


def quarter_to_roman(q):
    q = str(q).strip()
    mapping = {"1": "I", "2": "II", "3": "III", "4": "IV", "I": "I", "II": "II", "III": "III", "IV": "IV"}
    return mapping.get(q, "I")


def get_goal_code(code):
    parts = str(code).split(".")
    return parts[0] + "." if parts else ""


def get_task_code(code):
    parts = str(code).split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}."
    return ""


def code_sort_key(code):
    parts = re.findall(r"\d+", str(code))
    return tuple(int(p) for p in parts) if parts else (9999,)


def strip_code_from_name(code, name):
    code = clean(code)
    name = clean(name)
    if code and name.startswith(code):
        return name[len(code):].lstrip(" .—-–|:")
    return name


def unique_clean_values(series):
    if series is None:
        return []
    values = []
    for item in series.dropna().astype(str).tolist():
        item = item.strip()
        if item and item.lower() not in ["nan", "none", "н.д.", "нд", "-", "—"]:
            values.append(item)
    return sorted(set(values))


def get_all_department_values(row):
    values = []
    for col in ["department", "department_co_1", "department_co_2"]:
        value = clean(row.get(col, ""))
        if value:
            values.append(value)
    return values


def split_department_indices(value):
    return re.findall(r"\d+", clean(value))


def ssp_sort_value(value):
    """Сортування ССП за першим числовим індексом у назві/позначенні."""
    match = re.search(r"\d+", clean(value))
    return int(match.group()) if match else 9999


def department_matches_indices(row, selected_indices):
    if not selected_indices:
        return True
    found = set()
    for value in get_all_department_values(row):
        found.update(split_department_indices(value))
    return bool(found.intersection(set(selected_indices)))


def get_main_department_index(row):
    """Повертає індекс головного ССП із колонки головного виконавця."""
    indices = split_department_indices(row.get("department", ""))
    return indices[0] if indices else ""


def get_deputy_minister_by_main_ssp(value):
    """Повертає заступника Міністра за індексом головного виконавця."""
    indices = split_department_indices(value)
    if not indices:
        return ""
    return DEPUTY_MINISTER_BY_SSP.get(indices[0], "")


def add_deputy_by_ssp_column(df):
    """Додає службову колонку з заступником за головним Індексом ССП."""
    data = df.copy()
    if data.empty:
        data["deputy_minister_by_ssp"] = ""
        return data
    data["deputy_minister_by_ssp"] = data["department"].apply(get_deputy_minister_by_main_ssp)
    data["deputy_minister_by_ssp"] = data["deputy_minister_by_ssp"].replace("", "Не визначено")
    return data


def deputy_matches(row, selected_deputies):
    if not selected_deputies:
        return True
    deputy = clean(row.get("deputy_minister_by_ssp", ""))
    return deputy in selected_deputies


def status_display(status):
    """ЄДИНА шкала — core.statuses (правки П5/К5, стандарт моделі МіО).
    Для «Не подано» зберігаємо окреме відображення (немає даних)."""
    raw = clean(status)
    if raw == "Не подано" or raw == "":
        return "Не виконано"
    disp = core_statuses.status_display(raw)
    if disp == core_statuses.ST_NOTYET:
        return "Не настав час"
    if disp == core_statuses.ST_OBSOLETE:
        return "Втратило актуальність"
    return disp


def is_excluded_status(status):
    return status_display(status) in ["Не настав час", "Втратило актуальність"]


def status_score(status):
    """Бали лише за 5-статусною шкалою моделі МіО (Виконано=100,
    Частково=75, Не виконано=0, «х»/«в/а» → None)."""
    return core_statuses.status_score(status)


def plan_fact_percent(actual, target):
    actual_num = to_number(actual)
    target_num = to_number(target)
    actual_text = normalize_text(actual)
    target_text = normalize_text(target)
    if actual_num is not None and target_num is not None and target_num != 0:
        return round(min((actual_num / target_num) * 100, 100), 2)
    if target_text in ["так", "yes"] or actual_text in ["так", "нi", "yes", "no"]:
        if actual_text in ["так", "yes"]:
            return 100
        if actual_text in ["нi", "no"]:
            return 0
    return None


def is_quantitative_plan_fact(row):
    actual_num = to_number(row.get("numeric_value", ""))
    target_num = to_number(row.get("selected_target", ""))
    return actual_num is not None and target_num is not None and target_num != 0


def traffic_light(score):
    if score is None or pd.isna(score):
        return "⚪ Не оцінюється"
    if score >= 100:
        return "🟢 У графіку"
    if score >= 75:
        return "🟡 Часткове виконання"
    return "🔴 Відстає"


QUARTER_FRACTIONS = {1: 0.25, 2: 0.50, 3: 0.75, 4: 1.00}
RISKY_LEVELS = ("Критичний ризик", "Високий ризик", "Середній ризик")
RISK_RESULT_COLUMNS = [
    "risk_score",
    "risk_probability",
    "risk_reason",
    "auto_risk",
    "included_in_risk_assessment",
    "risk_current_fact",
    "risk_previous_fact",
    "risk_current_quarter",
    "risk_previous_quarter",
    "risk_current_quarter_fraction",
    "risk_previous_quarter_fraction",
    "risk_forecast_year",
    "risk_tempo",
]


def _format_risk_number(value):
    if value is None or pd.isna(value):
        return "н/д"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return clean(value) or "н/д"
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return f"{number:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _format_probability(value):
    if value is None or pd.isna(value):
        return "н/д"
    number = float(value)
    if abs(number - round(number)) < 1e-9:
        return f"{int(round(number))}%"
    return f"{number:.1f}%".replace(".", ",")


def _risk_quarter_text(quarter_num):
    roman = {1: "I", 2: "II", 3: "III", 4: "IV"}.get(int(quarter_num or 0), "")
    return f"{roman} квартал" if roman else "невизначений квартал"


def _normalise_yes_no(value):
    text = clean(value).casefold().replace("’", "'")
    if text in {"так", "yes", "true", "да"}:
        return "так"
    if text in {"ні", "нi", "no", "false", "нет"}:
        return "ні"
    return None


def _clamp_probability(value):
    try:
        return min(max(float(value), 0.0), 100.0)
    except (TypeError, ValueError):
        return None


def risk_level_from_probability(probability):
    if probability is None or pd.isna(probability):
        return "Не оцінюється"
    probability = float(probability)
    if probability > 85:
        return "Низький ризик"
    if probability >= 51:
        return "Середній ризик"
    if probability >= 20:
        return "Високий ризик"
    return "Критичний ризик"


def risk_level_from_score(score):
    """Backward-compatible mapping: greater score still means worse risk."""
    if score is None or pd.isna(score):
        return "Не оцінюється"
    return risk_level_from_probability(100 - float(score))


def build_risk_observation_map(approved_requests, year, selected_quarter_num):
    """Return latest effective submission per measure and quarter for risk forecast.

    The source frame has already been reduced to confirmed rows or to the
    operational overlay, so the history automatically follows the selected data
    source. Dashboard filters are intentionally not involved here.
    """
    if approved_requests is None or approved_requests.empty:
        return {}

    history = approved_requests.copy()
    for column in ["id", "year", "quarter", "strat_code", "status", "numeric_value", "submitted_at"]:
        if column not in history.columns:
            history[column] = ""

    history["_risk_year"] = pd.to_numeric(history["year"], errors="coerce")
    history["_risk_quarter_key"] = history["quarter"].apply(core_quarter_key)
    history["_risk_quarter_num"] = history["_risk_quarter_key"].map({
        "I": 1, "II": 2, "III": 3, "IV": 4
    })
    history["_risk_code"] = history["strat_code"].apply(clean)
    history = history[
        (history["_risk_year"] == int(year))
        & history["_risk_quarter_num"].notna()
        & (history["_risk_quarter_num"] <= int(selected_quarter_num))
        & (history["_risk_code"] != "")
    ].copy()
    if history.empty:
        return {}

    history["_risk_submitted_sort"] = pd.to_datetime(
        history["submitted_at"], errors="coerce", utc=True
    )
    history["_risk_id_sort"] = pd.to_numeric(history["id"], errors="coerce").fillna(-1)
    history = (
        history
        .sort_values(
            ["_risk_code", "_risk_quarter_num", "_risk_submitted_sort", "_risk_id_sort"],
            na_position="first",
        )
        .groupby(["_risk_code", "_risk_quarter_num"], as_index=False, sort=False)
        .tail(1)
        .sort_values(["_risk_code", "_risk_quarter_num"])
    )

    result = {}
    for code, rows in history.groupby("_risk_code", sort=False):
        result[code] = [
            {
                "quarter_num": int(record["_risk_quarter_num"]),
                "quarter_fraction": QUARTER_FRACTIONS[int(record["_risk_quarter_num"])],
                "fact": record.get("numeric_value", ""),
                "status": record.get("status", ""),
            }
            for _, record in rows.iterrows()
        ]
    return result


def _risk_result(
    probability,
    reason,
    *,
    included=True,
    current_fact=None,
    previous_fact=None,
    current_quarter=None,
    previous_quarter=None,
    forecast_year=None,
    tempo=None,
):
    probability = _clamp_probability(probability)
    if probability is None:
        risk_score = 0.0
        auto_risk = "Не оцінюється"
    else:
        risk_score = round(100.0 - probability, 2)
        auto_risk = risk_level_from_probability(probability)
    if not included:
        auto_risk = "Не оцінюється"

    current_fraction = QUARTER_FRACTIONS.get(int(current_quarter or 0))
    previous_fraction = QUARTER_FRACTIONS.get(int(previous_quarter or 0))
    return {
        "risk_score": risk_score,
        "risk_probability": round(probability, 2) if probability is not None else None,
        "risk_reason": reason,
        "auto_risk": auto_risk,
        "included_in_risk_assessment": bool(included),
        "risk_current_fact": current_fact,
        "risk_previous_fact": previous_fact,
        "risk_current_quarter": int(current_quarter) if current_quarter else None,
        "risk_previous_quarter": int(previous_quarter) if previous_quarter else None,
        "risk_current_quarter_fraction": current_fraction,
        "risk_previous_quarter_fraction": previous_fraction,
        "risk_forecast_year": round(float(forecast_year), 4) if forecast_year is not None else None,
        "risk_tempo": round(float(tempo), 4) if tempo is not None else None,
    }


def _forecast_gap_text(forecast_year, target):
    gap = max(float(target) - float(forecast_year), 0.0)
    if gap <= 1e-9:
        return "прогнозованого відставання від річного плану немає"
    gap_pct = min(gap / float(target) * 100, 100) if float(target) > 0 else 0
    return (
        f"прогнозоване відставання від річного плану — "
        f"{_format_risk_number(gap)} ({_format_probability(gap_pct)})"
    )


def risk_score_calc(row, selected_quarter_num, observations=None):
    """Forecast probability of reaching the annual plan from cumulative facts."""
    observations = list(observations or [])
    selected_quarter_num = int(selected_quarter_num)
    current_display_status = status_display(row.get("status", "Не подано"))

    if selected_quarter_num == 4:
        return _risk_result(
            None,
            "IV квартал є фактичним річним результатом; прогнозна оцінка ризику не розраховується.",
            included=False,
        )

    if current_display_status in ["Не настав час", "Втратило актуальність"]:
        return _risk_result(
            None,
            f"Захід не включається до ризикової оцінки: статус «{current_display_status}».",
            included=False,
        )

    if observations:
        latest_submitted_status = status_display(observations[-1].get("status", ""))
        if latest_submitted_status in ["Не настав час", "Втратило актуальність"]:
            return _risk_result(
                None,
                f"Захід не включається до ризикової оцінки: останній поданий статус «{latest_submitted_status}».",
                included=False,
            )

    target = row.get("selected_target", "")
    target_num = to_number(target)

    if target_num is not None:
        numeric_observations = []
        for observation in observations:
            fact_num = to_number(observation.get("fact", ""))
            if fact_num is None:
                continue
            numeric_observations.append({**observation, "fact_num": fact_num})

        if not numeric_observations:
            return _risk_result(
                20,
                "Прогнозована вірогідність — 20%; дані не подано: немає придатного "
                "числового фактичного значення за квартали поточного року, тому темп і "
                "відставання від річного плану не можуть бути розраховані.",
                included=True,
            )

        current = numeric_observations[-1]
        previous = numeric_observations[-2] if len(numeric_observations) >= 2 else None
        fact_n = float(current["fact_num"])
        q_n = int(current["quarter_num"])
        q_n_fraction = float(current["quarter_fraction"])
        fact_p = float(previous["fact_num"]) if previous is not None else None
        q_p = int(previous["quarter_num"]) if previous is not None else None
        latest_fact_status = status_display(current.get("status", ""))

        if target_num == 0:
            if fact_n == 0 and latest_fact_status == "Виконано":
                return _risk_result(
                    100,
                    "Річний план досягнуто: фактичне значення дорівнює нульовому плану, "
                    "статус «Виконано»; прогнозний ризик не розраховується.",
                    included=False,
                    current_fact=fact_n,
                    previous_fact=fact_p,
                    current_quarter=q_n,
                    previous_quarter=q_p,
                    forecast_year=fact_n,
                )
            return _risk_result(
                20,
                "Прогнозована вірогідність — 20%; річний план дорівнює нулю, тому "
                "співвідношення прогнозу до плану не може бути коректно розраховане.",
                included=True,
                current_fact=fact_n,
                previous_fact=fact_p,
                current_quarter=q_n,
                previous_quarter=q_p,
            )

        if target_num < 0:
            return _risk_result(
                20,
                "Прогнозована вірогідність — 20%; від'ємне річне планове значення не "
                "підтримується методикою прямої екстраполяції факт / план.",
                included=True,
                current_fact=fact_n,
                previous_fact=fact_p,
                current_quarter=q_n,
                previous_quarter=q_p,
            )

        if fact_n >= target_num and latest_fact_status == "Виконано":
            return _risk_result(
                100,
                f"Річний план досягнуто: факт {_format_risk_number(fact_n)} за плану "
                f"{_format_risk_number(target_num)}, статус «Виконано»; прогнозний ризик "
                "не розраховується.",
                included=False,
                current_fact=fact_n,
                previous_fact=fact_p,
                current_quarter=q_n,
                previous_quarter=q_p,
                forecast_year=fact_n,
            )

        if previous is not None:
            q_p_fraction = float(previous["quarter_fraction"])
            period_fraction = q_n_fraction - q_p_fraction
            growth = fact_n - fact_p
            if period_fraction <= 0:
                previous = None
            elif growth <= 0:
                forecast_year = fact_n + (growth / period_fraction) * (1 - q_n_fraction)
                movement = "не змінився" if abs(growth) < 1e-9 else "зменшився"
                reason = (
                    "Прогнозована вірогідність — 0%; кумулятивний факт "
                    f"{movement}: з {_format_risk_number(fact_p)} у {_risk_quarter_text(q_p)} "
                    f"до {_format_risk_number(fact_n)} у {_risk_quarter_text(q_n)} "
                    f"({ _format_risk_number(growth) }); за нульової або від'ємної динаміки "
                    "річний план недосяжний без зміни темпу; "
                    f"поточне відставання від плану — "
                    f"{_format_risk_number(max(target_num - fact_n, 0))}."
                )
                return _risk_result(
                    0,
                    reason,
                    included=True,
                    current_fact=fact_n,
                    previous_fact=fact_p,
                    current_quarter=q_n,
                    previous_quarter=q_p,
                    forecast_year=forecast_year,
                    tempo=growth / period_fraction,
                )

        if previous is not None:
            q_p_fraction = float(previous["quarter_fraction"])
            period_fraction = q_n_fraction - q_p_fraction
            growth = fact_n - fact_p
            tempo = growth / period_fraction
            forecast_year = fact_n + tempo * (1 - q_n_fraction)
            probability_raw = forecast_year / target_num * 100
            probability = _clamp_probability(probability_raw)
            reason = (
                f"Прогнозована вірогідність — {_format_probability(probability)}; "
                f"кумулятивний факт зріс з {_format_risk_number(fact_p)} у "
                f"{_risk_quarter_text(q_p)} до {_format_risk_number(fact_n)} у "
                f"{_risk_quarter_text(q_n)} (+{_format_risk_number(growth)}); "
                f"розрахунковий річний темп — {_format_risk_number(tempo)}, прогноз на "
                f"кінець року — {_format_risk_number(forecast_year)} за плану "
                f"{_format_risk_number(target_num)}; {_forecast_gap_text(forecast_year, target_num)}."
            )
            return _risk_result(
                probability,
                reason,
                included=True,
                current_fact=fact_n,
                previous_fact=fact_p,
                current_quarter=q_n,
                previous_quarter=q_p,
                forecast_year=forecast_year,
                tempo=tempo,
            )

        tempo = fact_n / q_n_fraction
        forecast_year = fact_n / q_n_fraction
        probability_raw = forecast_year / target_num * 100
        probability = _clamp_probability(probability_raw)
        reason = (
            f"Прогнозована вірогідність — {_format_probability(probability)}; доступне "
            f"одне кумулятивне значення: {_format_risk_number(fact_n)} у "
            f"{_risk_quarter_text(q_n)} ({_format_probability(q_n_fraction * 100)} року); "
            f"середній темп від початку року — {_format_risk_number(tempo)}, прогноз на "
            f"кінець року — {_format_risk_number(forecast_year)} за плану "
            f"{_format_risk_number(target_num)}; {_forecast_gap_text(forecast_year, target_num)}."
        )
        return _risk_result(
            probability,
            reason,
            included=True,
            current_fact=fact_n,
            current_quarter=q_n,
            forecast_year=forecast_year,
            tempo=tempo,
        )

    yes_no_observations = []
    for observation in observations:
        yes_no_value = _normalise_yes_no(observation.get("fact", ""))
        if yes_no_value is None:
            continue
        yes_no_observations.append({**observation, "yes_no_value": yes_no_value})

    if not yes_no_observations:
        return _risk_result(
            20,
            "Прогнозована вірогідність — 20%; дані не подано: немає фактичного "
            "значення «так/ні» за квартали поточного року; позитивна динаміка до "
            "річного результату не підтверджена.",
            included=True,
        )

    current = yes_no_observations[-1]
    previous = yes_no_observations[-2] if len(yes_no_observations) >= 2 else None
    current_value = current["yes_no_value"]
    current_quarter = int(current["quarter_num"])
    previous_value = previous["yes_no_value"] if previous is not None else None
    previous_quarter = int(previous["quarter_num"]) if previous is not None else None

    if current_value == "так":
        return _risk_result(
            100,
            f"Річний результат досягнуто: останнє кумулятивне значення «так» за "
            f"{_risk_quarter_text(current_quarter)}; прогнозний ризик не розраховується.",
            included=False,
            current_fact="так",
            previous_fact=previous_value,
            current_quarter=current_quarter,
            previous_quarter=previous_quarter,
        )

    dynamics_text = ""
    if previous is not None:
        dynamics_text = (
            f"; динаміка з {_risk_quarter_text(previous_quarter)} до "
            f"{_risk_quarter_text(current_quarter)} не змінила результат «ні»"
        )
    return _risk_result(
        20,
        f"Прогнозована вірогідність — 20%; останнє кумулятивне значення «ні» за "
        f"{_risk_quarter_text(current_quarter)}{dynamics_text}; для досягнення річного "
        "результату потрібне суттєве прискорення.",
        included=True,
        current_fact="ні",
        previous_fact=previous_value,
        current_quarter=current_quarter,
        previous_quarter=previous_quarter,
    )


def dashboard_conclusion(completion, risk_share, coverage):
    if completion >= 75 and risk_share <= 15 and coverage >= 70:
        return "План переважно виконується", "Поточний стан виконання виглядає контрольованим.", "risk-low"
    if completion >= 45 and risk_share <= 35:
        return "Є помірні відхилення", "Потрібна увага до окремих заходів, самостійних структурних підрозділів або стратегічних цілей.", "risk-medium"
    return (
        "Високий ризик невиконання",
        "Поточні дані вказують на недостатній рівень подання та погодження відомостей або на суттєві відхилення від планових показників.",
        "risk-high"
    )


def expected_completion_for_quarter(quarter_num):
    """Calendar progress expected by the end of the selected quarter."""
    try:
        quarter_num = int(quarter_num)
    except (TypeError, ValueError):
        quarter_num = 4
    return round(QUARTER_FRACTIONS.get(quarter_num, 1.0) * 100, 2)


def deviation_for_period(completion, quarter_num):
    expected = expected_completion_for_quarter(quarter_num)
    return round(float(completion or 0) - expected, 2)


def gauge_chart(value, title):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": "%", "font": {"size": 28, "color": "#032A63"}},
        title={"text": title, "font": {"size": 14, "color": "#61708A"}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#8A96A8", "tickfont": {"size": 11}},
            "bar": {"color": "#00A8A8", "thickness": 0.3},
            "bgcolor": "white",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 35], "color": "#FBE5E5"},
                {"range": [35, 70], "color": "#FDF3D8"},
                {"range": [70, 100], "color": "#E4F5EC"},
            ],
            "threshold": {
                "line": {"color": "#032A63", "width": 3},
                "thickness": 0.75,
                "value": value
            }
        }
    ))
    fig.update_layout(
        height=260,
        margin=dict(l=20, r=20, t=50, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    return fig


def summary_indicators_chart(
    completion,
    coverage,
    deviation,
    low_risk_share,
    expected_completion,
):
    """Render the four summary indicators as a downloadable Plotly chart."""
    deviation_direction = "Відставання" if deviation < 0 else "Випередження"
    if abs(float(deviation)) < 0.005:
        deviation_direction = "Відповідає плановому темпу"

    labels = [
        "Виконання СП",
        "Покриття моніторингом",
        "Відхилення за звітний період",
        "Частка заходів без ризику",
    ]
    subtitles = [
        "",
        "",
        (
            f"{deviation_direction} від планового темпу; "
            f"очікуваний рівень — {expected_completion:.0f}%"
        ),
        "Заходи низького ризику — висока вірогідність досягнення",
    ]
    display_values = [
        f"{float(completion):.1f}%",
        f"{float(coverage):.1f}%",
        f"{float(deviation):+.1f} в.п.",
        f"{float(low_risk_share):.1f}%",
    ]
    bar_values = [
        min(max(float(completion), 0.0), 100.0),
        min(max(float(coverage), 0.0), 100.0),
        min(abs(float(deviation)), 100.0),
        min(max(float(low_risk_share), 0.0), 100.0),
    ]
    colors = ["#005BBB", "#00A8A8", "#FF7A45", "#118847"]
    y_positions = [3, 2, 1, 0]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[100] * 4,
        y=y_positions,
        orientation="h",
        width=0.16,
        marker=dict(color="#EAF0F7"),
        hoverinfo="skip",
        showlegend=False,
    ))
    fig.add_trace(go.Bar(
        x=bar_values,
        y=y_positions,
        orientation="h",
        width=0.16,
        marker=dict(color=colors),
        customdata=[
            [label, value, subtitle]
            for label, value, subtitle in zip(labels, display_values, subtitles)
        ],
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "%{customdata[1]}<br>"
            "%{customdata[2]}<extra></extra>"
        ),
        showlegend=False,
    ))

    for y_pos, label, subtitle, display_value, color in zip(
        y_positions, labels, subtitles, display_values, colors
    ):
        label_text = f"<b>{label}</b>"
        if subtitle:
            label_text += (
                f"<br><span style='font-size:10px;color:#8A96A8'>{subtitle}</span>"
            )
        fig.add_annotation(
            x=0,
            y=y_pos + 0.30,
            text=label_text,
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
            align="left",
            font=dict(size=12, color="#33415C"),
        )
        fig.add_annotation(
            x=103,
            y=y_pos,
            text=f"<b>{display_value}</b>",
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            font=dict(size=12, color=color),
        )

    fig.update_layout(
        barmode="overlay",
        height=360,
        margin=dict(l=10, r=20, t=28, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            range=[0, 118],
            visible=False,
            fixedrange=True,
        ),
        yaxis=dict(
            range=[-0.48, 3.62],
            visible=False,
            fixedrange=True,
        ),
        bargap=0.72,
    )
    return fig


def annualised_plan_tempo_percent(row):
    """Normalise the already calculated risk tempo to the annual plan."""
    tempo = to_number(row.get("risk_tempo", ""))
    target = to_number(row.get("selected_target", ""))
    if tempo is None or target is None or target <= 0:
        return None
    return round(float(tempo) / float(target) * 100, 4)


def pct_value(count, total):
    if total == 0:
        return "0.0%"
    return f"{round(count / total * 100, 2)}%"


def render_kpi_grid(items, *, interactive=False, query_key="kpi"):
    selected = ""
    if interactive:
        try:
            selected = str(st.query_params.get(query_key, "") or "")
        except Exception:
            selected = ""

    cards = []
    for item in items:
        key = str(item.get("key", ""))
        active_class = " kpi-active" if interactive and key and selected == key else ""
        if interactive and key:
            href = "?" if selected == key else f"?{query_key}={key}"
            opening = f'<a class="kpi-card {item["color"]}{active_class}" href="{href}" target="_self">'
            closing = "</a>"
        else:
            opening = f'<div class="kpi-card {item["color"]}">'
            closing = "</div>"
        cards.append(
            opening
            + f'<div class="kpi-title">{item["title"]}</div>'
            + f'<div class="kpi-value">{item["count"]}</div>'
            + f'<div class="kpi-pct">{item["percent"]}</div>'
            + closing
        )

    st.markdown(f'<div class="kpi-grid">{"".join(cards)}</div>', unsafe_allow_html=True)
    return selected if interactive else ""


def render_insight(text, kind="default"):
    css_class = "insight-item"
    if kind == "warn":
        css_class += " warn"
    elif kind == "danger":
        css_class += " danger"
    elif kind == "info":
        css_class += " info"
    st.markdown(f'<div class="{css_class}">{text}</div>', unsafe_allow_html=True)


def render_indicator_bar(
    label,
    value,
    max_val=100,
    color="#005BBB",
    *,
    display_value=None,
    subtitle="",
):
    pct = min(max(float(value) / max_val * 100, 0), 100) if max_val else 0
    rendered_value = display_value
    if rendered_value is None:
        rendered_value = f"{value}{'%' if max_val == 100 else ''}"
    subtitle_html = (
        f'<div style="font-size:10px;font-weight:500;color:#8A96A8;margin-top:1px;">{subtitle}</div>'
        if subtitle else ""
    )
    st.markdown(f"""
    <div class="indicator-row">
        <div class="indicator-label">
            <div>{label}{subtitle_html}</div>
            <span style="color:{color};font-weight:800;white-space:nowrap;">{rendered_value}</span>
        </div>
        <div class="indicator-bar-bg">
            <div class="indicator-bar-fill" style="width:{pct}%;background:{color};"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)




# ============================================================
# CORE DATA FUNCTIONS
# ============================================================

def prepare_period_data(strat_df, requests_df, year, quarter, department="Усі"):
    measures = strat_df[strat_df["object_type"] == "measure"].copy()
    goals = strat_df[strat_df["object_type"] == "goal"].copy()

    measures["goal_code"] = measures["code"].apply(get_goal_code)
    measures["task_code"] = measures["code"].apply(get_task_code)
    measures["strategic_goal"] = measures["goal_code"].map(goals.set_index("code")["name"].to_dict())

    measures["start_num"] = measures["start_period"].apply(parse_period)
    measures["end_num"] = measures["end_period"].apply(parse_period)

    selected_q_num = quarter_to_number(quarter)
    selected_period_num = core_period_number(year, quarter)
    period_locked = is_period_locked(year, quarter)

    measures["period_state"] = measures.apply(
        lambda row: get_period_state(row.get("start_num"), row.get("end_num"), selected_period_num),
        axis=1,
    )

    # До квартальної вибірки входять лише заходи, строк виконання яких
    # охоплює саме цей звітний період. Невизначені та майбутні періоди
    # не перетворюються на штучний статус «Не настав час».
    active = measures[measures["period_state"] == "active"].copy()

    if department != "Усі":
        active = active[active["department"].astype(str) == str(department)]

    requests = requests_df.copy() if isinstance(requests_df, pd.DataFrame) else pd.DataFrame()
    required_cols = [
        "id", "year", "quarter", "strat_code", "status", "numeric_value",
        "risks", "progress_text", "approval_status", "submitted_at",
    ]
    for column in required_cols:
        if column not in requests.columns:
            requests[column] = ""

    approved_requests = requests[
        requests["approval_status"].astype(str).str.strip() == operational.CONFIRMED_STATUS
    ].copy()
    risk_observation_map = build_risk_observation_map(
        approved_requests, year, selected_q_num
    )

    period_request_columns = [
        "strat_code", "status", "numeric_value", "risks", "progress_text",
        "submitted_at", "id",
    ]
    if approved_requests.empty:
        period_requests = pd.DataFrame(columns=period_request_columns)
    else:
        selected_year = int(year)
        selected_quarter = core_quarter_key(quarter)
        request_years = pd.to_numeric(approved_requests["year"], errors="coerce")
        request_quarters = approved_requests["quarter"].apply(core_quarter_key)
        period_requests = approved_requests[
            (request_years == selected_year) & (request_quarters == selected_quarter)
        ].copy()

        if not period_requests.empty:
            period_requests["_submitted_sort"] = pd.to_datetime(
                period_requests["submitted_at"], errors="coerce", utc=True
            )
            period_requests["_id_sort"] = pd.to_numeric(
                period_requests["id"], errors="coerce"
            ).fillna(-1)
            period_requests = (
                period_requests
                .sort_values(["strat_code", "_submitted_sort", "_id_sort"], na_position="first")
                .groupby("strat_code", as_index=False, sort=False)
                .tail(1)
                .drop(columns=["_submitted_sort", "_id_sort"])
            )

    period_requests = period_requests.rename(columns={
        "submitted_at": "request_submitted_at",
        "id": "request_id",
    })
    active = active.merge(
        period_requests[[
            "strat_code", "status", "numeric_value", "risks", "progress_text",
            "request_submitted_at", "request_id",
        ]],
        left_on="code",
        right_on="strat_code",
        how="left",
    )

    active["has_monitoring_data"] = active["strat_code"].notna()
    active["status"] = active["status"].fillna("Не подано")
    if period_locked:
        active["status"] = "Не настав час"
    active["numeric_value"] = active["numeric_value"].fillna("")
    active["risks"] = active["risks"].fillna("")
    active["progress_text"] = active["progress_text"].fillna("")
    active["request_submitted_at"] = active["request_submitted_at"].fillna("")
    active["request_id"] = active["request_id"].fillna("")
    active["selected_target"] = active[f"target_{year}"] if f"target_{year}" in active.columns else ""

    active["status_display"] = active["status"].apply(status_display)
    active["status_score"] = active["status"].apply(status_score)
    active["plan_fact_percent"] = active.apply(
        lambda row: plan_fact_percent(row["numeric_value"], row["selected_target"]), axis=1
    )
    active["is_quantitative_pf"] = active.apply(is_quantitative_plan_fact, axis=1)
    active["performance_score"] = active.apply(
        lambda row: row["plan_fact_percent"] if pd.notna(row["plan_fact_percent"]) else row["status_score"],
        axis=1,
    )
    if period_locked:
        active[["status_score", "performance_score"]] = None
    active["included_in_assessment"] = ~active["status_display"].isin([
        "Не настав час", "Втратило актуальність"
    ])

    risk_results = [
        risk_score_calc(
            row,
            selected_q_num,
            risk_observation_map.get(clean(row.get("code", "")), []),
        )
        for _, row in active.iterrows()
    ]
    for column in RISK_RESULT_COLUMNS:
        active[column] = [result[column] for result in risk_results]

    active["traffic_light"] = active["performance_score"].apply(traffic_light)
    active.loc[~active["included_in_assessment"], "traffic_light"] = "⚪ Не оцінюється"

    active["period_year"] = int(year)
    active["period_quarter"] = quarter_to_roman(quarter)
    active["period_number"] = selected_period_num
    active["period_label"] = active["period_year"].astype(str) + " " + active["period_quarter"].astype(str)

    active = add_deputy_by_ssp_column(active)
    return active


def build_period_data(strat_df, requests_df, years, quarters):
    frames = []
    selected_periods = sorted(
        {(int(year), quarter_to_roman(quarter)) for year in years for quarter in quarters},
        key=lambda item: core_period_number(item[0], item[1]),
    )
    for year, quarter in selected_periods:
        period_frame = prepare_period_data(strat_df, requests_df, year, quarter, "Усі")
        if not period_frame.empty:
            frames.append(period_frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def apply_dashboard_filters(active, department_indices, goals, tasks, measures, product_types, deputies, statuses, sources, financing_types=None, kpkvk_codes=None):
    """Apply every selected criterion cumulatively and preserve an empty schema."""
    data = active.copy()
    if data.empty:
        return data

    if department_indices:
        mask = data.apply(lambda row: department_matches_indices(row, department_indices), axis=1)
        data = data.loc[mask.astype(bool)].copy()
        if data.empty:
            return data
    if goals:
        data = data[data["goal_code"].isin(goals)].copy()
        if data.empty:
            return data
    if tasks:
        data = data[data["task_code"].isin(tasks)].copy()
        if data.empty:
            return data
    if measures:
        data = data[data["code"].isin(measures)].copy()
        if data.empty:
            return data
    if product_types:
        data = data[data["product_type"].isin(product_types)].copy()
        if data.empty:
            return data
    if deputies:
        mask = data.apply(lambda row: deputy_matches(row, deputies), axis=1)
        data = data.loc[mask.astype(bool)].copy()
        if data.empty:
            return data
    if statuses:
        data = data[data["status_display"].isin(statuses)].copy()
        if data.empty:
            return data
    if sources:
        mask = data["source_national"].apply(lambda value: match_source(value, sources))
        data = data.loc[mask.astype(bool)].copy()
        if data.empty:
            return data
    if financing_types:
        selected_financing = set(financing_types)

        def _ft_match(row):
            row_types = row.get("financing_types", [])
            if not isinstance(row_types, list):
                row_types = []
            return bool(set(row_types) & selected_financing)

        mask = data.apply(_ft_match, axis=1)
        data = data.loc[mask.astype(bool)].copy()
        if data.empty:
            return data
    if kpkvk_codes:
        data = data[data["budget_kpkvk"].isin(kpkvk_codes)].copy()

    return data.copy()


def assessment_subset(active):
    if active.empty:
        return active
    return active[active["included_in_assessment"] == True].copy()


def risk_assessment_subset(active):
    if active.empty:
        return active
    assessed = assessment_subset(active)
    if "included_in_risk_assessment" not in assessed.columns:
        return assessed
    return assessed[assessed["included_in_risk_assessment"] == True].copy()


def mean_completion(active):
    assessed = assessment_subset(active)
    if assessed.empty:
        return 0
    return round(assessed["performance_score"].fillna(0).mean(), 2)


def calc_coverage(active):
    if active.empty:
        return 0
    submitted = len(active[active["status"] != "Не подано"])
    return round(submitted / len(active) * 100, 2)


def calc_submitted(active):
    if active.empty:
        return 0
    return len(active[active["status"] != "Не подано"])


def calc_risk_share(active):
    assessed = risk_assessment_subset(active)
    if assessed.empty:
        return 0
    risk_count = len(assessed[assessed["auto_risk"].isin(RISKY_LEVELS)])
    return round(risk_count / len(assessed) * 100, 2)


def calc_low_risk_share(active):
    """Share of assessed measures with high probability of annual achievement."""
    assessed = risk_assessment_subset(active)
    if assessed.empty:
        return 0
    low_risk_count = len(assessed[assessed["auto_risk"] == "Низький ризик"])
    return round(low_risk_count / len(assessed) * 100, 2)


def build_goal_progress(active):
    """Aggregate goal achievement through tasks, not directly through measures.

    Measure score is the raw dashboard performance percentage. Excluded statuses
    have no score. Task score is the mean of its scored measures; goal score is
    the mean of its scored tasks, so tasks have equal weight within a goal.
    """
    columns = [
        "goal_code", "strategic_goal", "Активних_заходів", "Виконання",
        "Покриття", "Ризикових", "Середній_ризик", "Покриття_%",
    ]
    if active is None or active.empty:
        return pd.DataFrame(columns=columns)

    data = active.copy()
    for column in [
        "code", "goal_code", "task_code", "strategic_goal", "performance_score",
        "status", "status_display", "auto_risk", "risk_score",
    ]:
        if column not in data.columns:
            data[column] = ""

    data["_goal_measure_score"] = pd.to_numeric(
        data["performance_score"], errors="coerce"
    ).clip(lower=0, upper=100)
    eligible = ~data["status_display"].isin(["Не настав час", "Втратило актуальність"])
    if "included_in_assessment" in data.columns:
        eligible &= data["included_in_assessment"].fillna(False).astype(bool)

    def _valid_hierarchy(row):
        measure_code = clean(row.get("code", ""))
        task_code = clean(row.get("task_code", ""))
        goal_code = clean(row.get("goal_code", ""))
        return bool(
            measure_code and task_code and goal_code
            and measure_code.startswith(task_code)
            and task_code.startswith(goal_code)
        )

    hierarchy_valid = data.apply(_valid_hierarchy, axis=1)
    data.loc[~(eligible & hierarchy_valid), "_goal_measure_score"] = pd.NA

    summary = (
        data
        .groupby(["goal_code", "strategic_goal"], dropna=False)
        .agg(
            Активних_заходів=("code", "count"),
            Покриття=("status", lambda x: (x != "Не подано").sum()),
            Ризикових=("auto_risk", lambda x: x.isin(RISKY_LEVELS).sum()),
            Середній_ризик=("risk_score", "mean"),
        )
        .reset_index()
    )

    task_scores = (
        data
        .groupby(["goal_code", "strategic_goal", "task_code"], dropna=False)["_goal_measure_score"]
        .mean()
        .dropna()
        .reset_index(name="_task_score")
    )
    goal_scores = (
        task_scores
        .groupby(["goal_code", "strategic_goal"], dropna=False)["_task_score"]
        .mean()
        .reset_index(name="Виконання")
    )

    result = summary.merge(
        goal_scores,
        on=["goal_code", "strategic_goal"],
        how="left",
    )
    result["Виконання"] = pd.to_numeric(result["Виконання"], errors="coerce").round(2)
    result["Покриття_%"] = (
        result["Покриття"] / result["Активних_заходів"] * 100
    ).round(2)
    result["Середній_ризик"] = result["Середній_ризик"].fillna(0).round(2)
    return result[columns]


def is_failed_for_weight(row):
    if not row.get("included_in_assessment", True):
        return False
    if row.get("status", "") == "Не подано":
        return True
    if row.get("status_display", "") == "Не виконано":
        return True
    score = row.get("performance_score", 0)
    if pd.isna(score):
        score = 0
    return score < 75


def weighted_failure_group(active, group_cols):
    if active.empty:
        return pd.DataFrame()
    data = active.copy()
    data = data[data["included_in_assessment"] == True].copy()
    if data.empty:
        return pd.DataFrame()
    data["failed_weight_flag"] = data.apply(is_failed_for_weight, axis=1)
    grouped = (
        data
        .groupby(group_cols, dropna=False)
        .agg(
            Активних_заходів=("code", "count"),
            Невиконаних=("failed_weight_flag", "sum"),
            Виконання=("performance_score", "mean"),
            Ризик=("risk_score", "mean")
        )
        .reset_index()
    )
    grouped["Вага_невиконання"] = grouped["Невиконаних"] / len(data) * 100
    grouped["Виконання"] = grouped["Виконання"].fillna(0).round(2)
    grouped["Ризик"] = grouped["Ризик"].fillna(0).round(2)
    grouped["Вага_невиконання"] = grouped["Вага_невиконання"].fillna(0).round(2)
    return grouped.sort_values(
        ["Вага_невиконання", "Невиконаних", "Активних_заходів"],
        ascending=[False, False, False]
    )


def explode_departments(active):
    rows = []
    for _, row in active.iterrows():
        departments = get_all_department_values(row)
        if not departments:
            departments = ["Не визначено"]
        for dep in departments:
            item = row.to_dict()
            item["ssp_department"] = dep
            rows.append(item)
    return pd.DataFrame(rows)


def _dashboard_rank_row_class(row, total_rows):
    """CSS-клас кольорової групи рядка рейтингу ССП."""
    place = int(row.get("Місце", 0) or 0)
    if place <= 3:
        return "dashboard-rank-green"
    if place > max(total_rows - 7, 10):
        return "dashboard-rank-red"
    return "dashboard-rank-yellow"


def _dashboard_html_cell(value, formatter=None):
    """Безпечне повне HTML-представлення значення комірки."""
    if formatter is not None:
        try:
            value = formatter(value)
        except Exception as exc:
            log_cosmetic_error("Форматування значення таблиці Dashboard", exc)
    text = clean(value)
    return escape(text).replace("\n", "<br>") if text else "—"


def render_dashboard_table(
    table_data,
    *,
    hide_index=True,
    empty_message="Записів немає.",
    formatters=None,
    row_class_fn=None,
):
    """Рендерить DataFrame як системну HTML-таблицю зі скролами й повним текстом."""
    source = getattr(table_data, "data", table_data)
    if not isinstance(source, pd.DataFrame):
        source = pd.DataFrame(source)
    if source.empty:
        st.info(empty_message)
        return

    formatters = formatters or {}
    headers = list(source.columns)
    header_cells = []
    if not hide_index:
        header_cells.append("<th></th>")
    header_cells.extend(f"<th>{escape(str(column))}</th>" for column in headers)

    body_rows = []
    total_rows = len(source)
    for index_value, row in source.iterrows():
        row_class = ""
        if row_class_fn is not None:
            try:
                row_class = clean(row_class_fn(row, total_rows))
            except Exception as exc:
                log_cosmetic_error("Визначення стилю рядка таблиці Dashboard", exc)
        class_attr = f' class="{escape(row_class)}"' if row_class else ""
        cells = []
        if not hide_index:
            cells.append(f"<td>{_dashboard_html_cell(index_value)}</td>")
        for column in headers:
            cells.append(
                f"<td>{_dashboard_html_cell(row.get(column), formatters.get(column))}</td>"
            )
        body_rows.append(f"<tr{class_attr}>{''.join(cells)}</tr>")

    html = (
        '<div class="dashboard-html-table-wrap">'
        '<div class="myreq-table-scroll">'
        '<table class="myreq-html-table">'
        f"<thead><tr>{''.join(header_cells)}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def collapse_to_latest_measure_rows(df):
    """Return one row per measure for the multi-period current snapshot.

    The population is taken from the latest period with the maximum number of
    active measures in the selected range. Each measure then receives its latest
    available submitted value in the range; if it has no submission, its latest
    active-period row is retained as «Не подано».
    """
    if df.empty:
        return df

    data = df.copy()
    if "period_number" not in data.columns:
        data["period_number"] = data.apply(
            lambda row: core_period_number(row.get("period_year"), row.get("period_quarter")),
            axis=1,
        )
    if "has_monitoring_data" not in data.columns:
        data["has_monitoring_data"] = data.get("status", "").astype(str) != "Не подано"

    period_counts = data.groupby("period_number")["code"].nunique()
    maximum_count = int(period_counts.max()) if not period_counts.empty else 0
    if maximum_count <= 0:
        return data.iloc[0:0].copy()

    population_period = int(period_counts[period_counts == maximum_count].index.max())
    population_codes = set(
        data.loc[data["period_number"] == population_period, "code"].astype(str)
    )
    candidates = data[data["code"].astype(str).isin(population_codes)].copy()

    with_data = candidates[candidates["has_monitoring_data"].fillna(False)].copy()
    if not with_data.empty:
        with_data["_request_dt_sort"] = pd.to_datetime(
            with_data.get("request_submitted_at", ""), errors="coerce", utc=True
        )
        with_data["_request_id_sort"] = pd.to_numeric(
            with_data.get("request_id", ""), errors="coerce"
        ).fillna(-1)
        latest_with_data = (
            with_data
            .sort_values(
                ["code", "period_number", "_request_dt_sort", "_request_id_sort"],
                na_position="first",
            )
            .groupby("code", as_index=False, sort=False)
            .tail(1)
            .drop(columns=["_request_dt_sort", "_request_id_sort"])
        )
    else:
        latest_with_data = with_data

    selected_codes = set(latest_with_data["code"].astype(str)) if not latest_with_data.empty else set()
    without_data = candidates[~candidates["code"].astype(str).isin(selected_codes)].copy()
    latest_without_data = (
        without_data
        .sort_values(["code", "period_number"])
        .groupby("code", as_index=False, sort=False)
        .tail(1)
        if not without_data.empty
        else without_data
    )

    result = pd.concat([latest_with_data, latest_without_data], ignore_index=True, sort=False)
    result["_code_sort"] = result["code"].map(code_sort_key)
    return result.sort_values("_code_sort").drop(columns="_code_sort").reset_index(drop=True)


def _period_number_to_text(period_num):
    year = int(period_num) // 10
    quarter = {1: "I", 2: "II", 3: "III", 4: "IV"}.get(int(period_num) % 10, "I")
    return f"{quarter} квартал {year} року"


def resolve_snapshot_period_number(active_period_rows, years, quarters):
    selected_periods = sorted({
        core_period_number(year, quarter)
        for year in years
        for quarter in quarters
    })
    if not selected_periods:
        return None

    snapshot_period = selected_periods[-1]
    if not active_period_rows.empty and "has_monitoring_data" in active_period_rows.columns:
        periods_with_data = active_period_rows.loc[
            active_period_rows["has_monitoring_data"].fillna(False), "period_number"
        ]
        if not periods_with_data.empty:
            snapshot_period = int(periods_with_data.max())
    return int(snapshot_period)


def build_period_context(active_period_rows, years, quarters):
    selected_periods = sorted({
        core_period_number(year, quarter)
        for year in years
        for quarter in quarters
    })
    if not selected_periods:
        return "Зріз за обраним періодом", "Динаміка за обраним періодом"

    snapshot_period = resolve_snapshot_period_number(active_period_rows, years, quarters)
    first_period = selected_periods[0]
    last_period = selected_periods[-1]
    snapshot_label = f"Зріз станом на {_period_number_to_text(snapshot_period)}"
    dynamics_label = (
        f"Динаміка {_period_number_to_text(first_period)}"
        f"→{_period_number_to_text(last_period)}"
    )
    return snapshot_label, dynamics_label


# ─── Plotly theme helper ───────────────────────────────────────────────────────
CHART_COLORS = ["#005BBB", "#00A8A8", "#4D8DFF", "#FF7A45", "#1E9E57", "#F4B400", "#8A96A8", "#032A63"]

RISK_COLORS = {
    "Критичний ризик": "#FF7A45",
    "Високий ризик": "#FF7A45",
    "Середній ризик": "#F4B400",
    "Низький ризик": "#1E9E57",
    "Не оцінюється": "#8A96A8"
}

TRAFFIC_COLORS = {
    "🟢 У графіку": "#00A8A8",
    "🟡 Часткове виконання": "#F4B400",
    "🔴 Відстає": "#FF7A45",
    "⚪ Не оцінюється": "#8A96A8"
}

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Helvetica Neue, Arial, sans-serif", size=12, color="#61708A")
)

PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "toImageButtonOptions": {
        "format": "png",
        "scale": 2,
    },
}


def render_no_chart_data():
    st.info("Немає даних для цього графіка за обраними параметрами.")


def _plotly_figure_has_data(fig):
    """Не дозволяє Plotly створювати порожній білий блок."""

    def _has_numeric_value(value):
        if isinstance(value, (list, tuple)):
            return any(_has_numeric_value(item) for item in value)
        if hasattr(value, "tolist") and not isinstance(value, (str, bytes)):
            return _has_numeric_value(value.tolist())
        try:
            number = float(value)
        except (TypeError, ValueError):
            return False
        return not pd.isna(number)

    for trace in fig.data:
        if _has_numeric_value(getattr(trace, "value", None)):
            return True
        for attribute in ("x", "y", "values", "z", "r", "theta"):
            if _has_numeric_value(getattr(trace, attribute, None)):
                return True
    return False


def render_plotly_chart(fig, **kwargs):
    """Рендерить непорожній Plotly із штатною кнопкою збереження PNG."""
    if not _plotly_figure_has_data(fig):
        render_no_chart_data()
        return False
    st.plotly_chart(fig, config=PLOTLY_CONFIG, **kwargs)
    return True


def apply_safe_plotly_layout(fig, has_legend=True):
    """Ставить легенду в безпечне положення, що не накладається на сам графік."""
    if has_legend:
        fig.update_layout(
            legend=dict(
                orientation="h",
                x=0.5,
                xanchor="center",
                y=-0.25,
                yanchor="top",
                bgcolor="rgba(0,0,0,0)",
            ),
            margin=dict(l=10, r=10, t=40, b=90),
        )
    else:
        fig.update_layout(showlegend=False)
    return fig


def make_chart_frame(title, subtitle=""):
    st.markdown(
        f'<div class="chart-wrap"><div class="chart-title">{title}</div>'
        + (f'<div class="section-subtitle">{subtitle}</div>' if subtitle else ""),
        unsafe_allow_html=True
    )


def close_chart_frame():
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# HEADER
# ============================================================

st.markdown('<div class="ua-stripe"></div>', unsafe_allow_html=True)
st.markdown("""
<div class="ministry-label">
🇺🇦 Міністерство економіки, довкілля та сільського господарства України
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="header-card">
    <div class="header-main">
        <div class="header-title">Аналітичний дашборд результативності стратегічного плану</div>
        <div class="header-subtitle">
            Аналітична панель забезпечує комплексне представлення результатів виконання Стратегічного плану. Інфографіка та моніторингові звіти формуються за результатами проведення оцінки на основі моніторингу й оцінювання стратегічних результатів як у цілому, так і в розрізі кожного самостійного структурного підрозділу окремо.
        </div>
    </div>
</div>
""", unsafe_allow_html=True)



# ============================================================
# LOAD DATA
# ============================================================

strat_df = load_strat_matrix()
requests_df = load_requests()

# Ролі, звужені до власного ССП, бачать за замовчуванням тільки своє ССП.
# На цьому рівні звужуються лише подання; ієрархічна матриця залишається повною.
requests_df = filter_requests_for_user(
    requests_df, current_user, ssp_columns=["department"], page_key="Dashboard"
)

measures_all = strat_df[strat_df["object_type"] == "measure"].copy()
measures_all = filter_actions_for_user(measures_all, current_user, page_key="Dashboard")
goals_all = strat_df[strat_df["object_type"] == "goal"].copy()
tasks_all = strat_df[strat_df["object_type"] == "task"].copy()

measures_all["goal_code"] = measures_all["code"].apply(get_goal_code)
measures_all["task_code"] = measures_all["code"].apply(get_task_code)
measures_all["strategic_goal"] = measures_all["goal_code"].map(
    goals_all.set_index("code")["name"].to_dict()
)
measures_all = add_deputy_by_ssp_column(measures_all)

years_options = [2026, 2027, 2028]
quarters_options = ["I", "II", "III", "IV"]

department_indices_options = sorted(
    set(
        re.findall(
            r"\d+",
            " | ".join(
                measures_all[["department", "department_co_1", "department_co_2"]]
                .fillna("").astype(str).agg(" | ".join, axis=1).tolist()
            )
        )
    ),
    key=lambda x: int(x) if x.isdigit() else 9999,
)

goal_options = sorted(
    measures_all["goal_code"].dropna().astype(str).unique().tolist(),
    key=code_sort_key,
)
task_options = sorted(
    measures_all["task_code"].dropna().astype(str).unique().tolist(),
    key=code_sort_key,
)

goal_name_map = goals_all.set_index("code")["name"].to_dict()
task_name_map = tasks_all.set_index("code")["name"].to_dict()

product_type_options = unique_clean_values(measures_all["product_type"])
deputy_options = unique_clean_values(measures_all["deputy_minister_by_ssp"])
status_options = list(core_statuses.MODEL_STATUSES)
kpkvk_options = sorted(
    [value for value in measures_all["budget_kpkvk"].unique() if value],
    key=lambda value: str(value),
)


# ============================================================
# СПІЛЬНА ПАНЕЛЬ ВІДБОРУ
# ============================================================

_dash_common_defaults = {
    "data_source_mode": operational.MODE_CONFIRMED,
    "presentation_mode": False,
    "department_indices": [],
    "goals": [],
    "tasks": [],
    "product_types": [],
    "deputies": [],
    "statuses": [],
    "financing": [],
    "kpkvk": [],
}
if "dash_common_filters_applied_v20" not in st.session_state:
    st.session_state["dash_common_filters_applied_v20"] = _dash_common_defaults.copy()

_dashboard_common_widget_defaults = {
    "dash_data_source_mode": operational.MODE_CONFIRMED,
    "dash_presentation_mode": False,
    "dash_department_indices": [],
    "dash_goals": [],
    "dash_tasks": [],
    "dash_product_types": [],
    "dash_deputies": [],
    "dash_statuses": [],
    "dash_financing": [],
    "dash_kpkvk": [],
}
for _widget_key, _widget_default in _dashboard_common_widget_defaults.items():
    st.session_state.setdefault(_widget_key, _widget_default)


def _apply_dashboard_common_filters_v20():
    st.session_state["dash_common_filters_applied_v20"] = {
        "data_source_mode": st.session_state.get(
            "dash_data_source_mode", operational.MODE_CONFIRMED
        ),
        "presentation_mode": bool(
            st.session_state.get("dash_presentation_mode", False)
        ),
        "department_indices": list(
            st.session_state.get("dash_department_indices", []) or []
        ),
        "goals": list(st.session_state.get("dash_goals", []) or []),
        "tasks": list(st.session_state.get("dash_tasks", []) or []),
        "product_types": list(
            st.session_state.get("dash_product_types", []) or []
        ),
        "deputies": list(st.session_state.get("dash_deputies", []) or []),
        "statuses": list(st.session_state.get("dash_statuses", []) or []),
        "financing": list(st.session_state.get("dash_financing", []) or []),
        "kpkvk": list(st.session_state.get("dash_kpkvk", []) or []),
    }


def _reset_dashboard_common_filters_v20():
    st.session_state["dash_common_filters_applied_v20"] = _dash_common_defaults.copy()
    for _widget_key, _widget_default in _dashboard_common_widget_defaults.items():
        st.session_state[_widget_key] = (
            list(_widget_default)
            if isinstance(_widget_default, list)
            else _widget_default
        )


with st.form("dashboard_common_filters_form_v20"):
    st.markdown(
        '<div class="filter-title">Параметри відбору</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="filter-subtitle dashboard-filter-subtitle">Основні параметри</div>',
        unsafe_allow_html=True,
    )

    fa, fb, fc, fd = st.columns([1.55, 0.9, 1.55, 1.8])

    with fa:
        st.markdown(
            '<div class="filter-field-label">Джерело даних</div>',
            unsafe_allow_html=True,
        )
        st.radio(
            "Джерело даних",
            operational.MODE_OPTIONS,
            horizontal=True,
            key="dash_data_source_mode",
            label_visibility="collapsed",
        )

    with fb:
        st.markdown(
            '<div class="filter-field-label">Режим презентації</div>',
            unsafe_allow_html=True,
        )
        st.toggle(
            "Режим презентації",
            key="dash_presentation_mode",
            label_visibility="collapsed",
        )

    with fc:
        st.markdown(
            '<div class="filter-field-label">Самостійний структурний підрозділ</div>',
            unsafe_allow_html=True,
        )
        if is_scope_lockable_user(current_user) and not is_scope_override_active("Dashboard"):
            _own_dash_ssp = get_user_ssp_index(current_user) or "—"
            st.markdown(
                "<div style='min-height:43px;background:#EAF1FF;border:1px solid #BFD3F2;"
                "border-radius:10px;padding:10px 12px;font-weight:800;color:#132238;"
                "box-shadow:inset 0 1px 2px rgba(15,23,42,0.08);'>"
                f"Ваш ССП: №{_own_dash_ssp}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.multiselect(
                "Самостійний структурний підрозділ",
                department_indices_options,
                key="dash_department_indices",
                placeholder="Усі підрозділи",
                label_visibility="collapsed",
            )

    with fd:
        st.markdown(
            '<div class="filter-field-label">Стратегічна ціль</div>',
            unsafe_allow_html=True,
        )
        st.multiselect(
            "Стратегічна ціль",
            goal_options,
            format_func=lambda value: (
                f"{value} — {strip_code_from_name(value, goal_name_map.get(value, ''))}"
            ),
            key="dash_goals",
            placeholder="Усі стратегічні цілі",
            label_visibility="collapsed",
        )

    with st.container(key="dashboard_additional_parameters_v20"):
        with st.expander("Додаткові параметри", expanded=False):
            g1, g2, g3 = st.columns(3)
            with g1:
                st.markdown(
                    '<div class="filter-field-label">Завдання</div>',
                    unsafe_allow_html=True,
                )
                st.multiselect(
                    "Завдання",
                    task_options,
                    format_func=lambda value: (
                        f"{value} — {strip_code_from_name(value, task_name_map.get(value, ''))}"
                    ),
                    key="dash_tasks",
                    label_visibility="collapsed",
                )
            with g2:
                st.markdown(
                    '<div class="filter-field-label">Тип продукту</div>',
                    unsafe_allow_html=True,
                )
                st.multiselect(
                    "Тип продукту",
                    product_type_options,
                    key="dash_product_types",
                    label_visibility="collapsed",
                )
            with g3:
                st.markdown(
                    '<div class="filter-field-label">Заступник Міністра</div>',
                    unsafe_allow_html=True,
                )
                st.multiselect(
                    "Заступник Міністра",
                    deputy_options,
                    key="dash_deputies",
                    label_visibility="collapsed",
                )

            h1, h2, h3 = st.columns(3)
            with h1:
                st.markdown(
                    '<div class="filter-field-label">Статус виконання</div>',
                    unsafe_allow_html=True,
                )
                st.multiselect(
                    "Статус виконання",
                    status_options,
                    key="dash_statuses",
                    label_visibility="collapsed",
                )
            with h2:
                st.markdown(
                    '<div class="filter-field-label">Джерело фінансування</div>',
                    unsafe_allow_html=True,
                )
                st.multiselect(
                    "Джерело фінансування",
                    [
                        "Державний бюджет",
                        "МТД / кошти партнерів",
                        "Небюджетні / інші",
                        "Без фінансування",
                    ],
                    key="dash_financing",
                    label_visibility="collapsed",
                )
            with h3:
                st.markdown(
                    '<div class="filter-field-label">КПКВК</div>',
                    unsafe_allow_html=True,
                )
                st.multiselect(
                    "КПКВК",
                    kpkvk_options,
                    key="dash_kpkvk",
                    label_visibility="collapsed",
                )

    _apply_col, _reset_col = st.columns([1, 1])
    with _apply_col:
        st.form_submit_button(
            "Застосувати обрані параметри",
            type="primary",
            use_container_width=True,
            on_click=_apply_dashboard_common_filters_v20,
        )
    with _reset_col:
        st.form_submit_button(
            "Скинути параметри",
            use_container_width=True,
            on_click=_reset_dashboard_common_filters_v20,
        )

render_scope_toggle("Dashboard", current_user)

_dash_applied = st.session_state.get(
    "dash_common_filters_applied_v20", _dash_common_defaults.copy()
)
data_source_mode = _dash_applied.get(
    "data_source_mode", operational.MODE_CONFIRMED
)
presentation_mode = bool(_dash_applied.get("presentation_mode", False))
selected_department_indices = list(
    _dash_applied.get("department_indices", []) or []
)
selected_goals = list(_dash_applied.get("goals", []) or [])
selected_tasks = list(_dash_applied.get("tasks", []) or [])
selected_product_types = list(_dash_applied.get("product_types", []) or [])
selected_deputies = list(_dash_applied.get("deputies", []) or [])
selected_statuses = list(_dash_applied.get("statuses", []) or [])
selected_financing = list(_dash_applied.get("financing", []) or [])
selected_kpkvk = list(_dash_applied.get("kpkvk", []) or [])

# Ці фільтри свідомо не входять до нової спільної панелі.
selected_measures = []
selected_sources = []

if is_scope_lockable_user(current_user) and not is_scope_override_active("Dashboard"):
    _own_department_index = get_user_ssp_index(current_user)
    if _own_department_index:
        selected_department_indices = [_own_department_index]


# ============================================================
# ДЖЕРЕЛО ДАНИХ І РУЧНІ ЗАКРИТТЯ
# ============================================================

if data_source_mode == operational.MODE_OPERATIONAL and not requests_df.empty:
    _approval_logs = operational.load_monitoring_logs()
    requests_df, _ = operational.apply_operational_mode(
        requests_df,
        logs_df=_approval_logs,
    )

# Ручні закриття лишаються офіційною частиною обох режимів даних.
_manual_closeouts = load_manual_closeouts()
manual_closeout_rows = 0
if _manual_closeouts:
    _existing_keys = set()
    if not requests_df.empty:
        for _, _request_row in requests_df[
            requests_df["approval_status"].astype(str) == "Погоджено"
        ].iterrows():
            _existing_keys.add(
                (
                    str(_request_row.get("strat_code", "")).strip(),
                    str(_request_row.get("year", "")).strip(),
                    quarter_to_roman(_request_row.get("quarter", "")),
                )
            )
    _synthetic_rows = []
    for _code, _year, _quarter in _manual_closeouts:
        if (_code, _year, _quarter) in _existing_keys:
            continue
        _synthetic_rows.append(
            {
                "year": _year,
                "quarter": _quarter,
                "department": "",
                "strat_code": _code,
                "status": "Виконано",
                "numeric_value": "",
                "risks": "",
                "progress_text": (
                    "Закрито вручну адміністратором "
                    "(підтверджено супер-адміном)"
                ),
                "approval_status": "Погоджено",
                "submitted_at": "",
                "object_kind": "measure",
                "_manual_closeout": True,
            }
        )
    if _synthetic_rows:
        manual_closeout_rows = len(_synthetic_rows)
        requests_df = pd.concat(
            [requests_df, pd.DataFrame(_synthetic_rows)],
            ignore_index=True,
        )

if requests_df.empty:
    requests_df = pd.DataFrame(
        columns=[
            "year",
            "quarter",
            "department",
            "strat_code",
            "status",
            "numeric_value",
            "risks",
            "progress_text",
            "approval_status",
            "submitted_at",
        ]
    )


# ============================================================
# РОЗДІЛЬНІ ПАНЕЛІ ПЕРІОДІВ І КОНТЕКСТИ СЕКЦІЙ
# ============================================================

_now_for_defaults = now_kyiv()
_default_snapshot_year = (
    _now_for_defaults.year
    if _now_for_defaults.year in years_options
    else years_options[0]
)
_default_snapshot_quarter = quarters_options[
    min(max((_now_for_defaults.month - 1) // 3, 0), 3)
]

st.session_state.setdefault("dash_snapshot_year", _default_snapshot_year)
st.session_state.setdefault("dash_snapshot_quarter", _default_snapshot_quarter)
st.session_state.setdefault("dash_breakdown_years", list(years_options))
st.session_state.setdefault("dash_breakdown_quarters", list(quarters_options))
st.session_state.setdefault("dash_dynamics_years", list(years_options))
st.session_state.setdefault("dash_dynamics_quarters", list(quarters_options))


def _render_dashboard_section_intro(title, description):
    st.divider()
    st.markdown(
        f'<div class="section-title">{title}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="section-subtitle">{description}</div>',
        unsafe_allow_html=True,
    )


def _render_single_period_panel():
    with st.container(border=True, key="dashboard_snapshot_period_panel"):
        st.markdown(
            '<div class="filter-subtitle dashboard-filter-subtitle">Період секції</div>',
            unsafe_allow_html=True,
        )
        year_col, quarter_col = st.columns(2)
        with year_col:
            st.markdown(
                '<div class="filter-field-label">Рік</div>',
                unsafe_allow_html=True,
            )
            selected_year = st.selectbox(
                "Рік моментного зрізу",
                years_options,
                key="dash_snapshot_year",
                label_visibility="collapsed",
            )
        with quarter_col:
            st.markdown(
                '<div class="filter-field-label">Квартал</div>',
                unsafe_allow_html=True,
            )
            selected_quarter = st.selectbox(
                "Квартал моментного зрізу",
                quarters_options,
                key="dash_snapshot_quarter",
                label_visibility="collapsed",
            )
    return [int(selected_year)], [selected_quarter]


def _render_multi_period_panel(section_key, years_key, quarters_key):
    with st.container(border=True, key=f"dashboard_{section_key}_period_panel"):
        st.markdown(
            '<div class="filter-subtitle dashboard-filter-subtitle">Період секції</div>',
            unsafe_allow_html=True,
        )
        year_col, quarter_col = st.columns(2)
        with year_col:
            st.markdown(
                '<div class="filter-field-label">Роки</div>',
                unsafe_allow_html=True,
            )
            selected_years_local = st.multiselect(
                f"Роки секції {section_key}",
                years_options,
                key=years_key,
                placeholder="Усі роки",
                label_visibility="collapsed",
            )
        with quarter_col:
            st.markdown(
                '<div class="filter-field-label">Квартали</div>',
                unsafe_allow_html=True,
            )
            selected_quarters_local = st.multiselect(
                f"Квартали секції {section_key}",
                quarters_options,
                key=quarters_key,
                placeholder="Усі квартали",
                label_visibility="collapsed",
            )
    return (
        list(selected_years_local) if selected_years_local else list(years_options),
        list(selected_quarters_local)
        if selected_quarters_local
        else list(quarters_options),
    )


def _build_dashboard_context(years_for_calc, quarters_for_calc):
    active_raw = build_period_data(
        strat_df,
        requests_df,
        years_for_calc,
        quarters_for_calc,
    )
    if active_raw is None or active_raw.empty:
        return None

    active_filtered = apply_dashboard_filters(
        active_raw,
        selected_department_indices,
        selected_goals,
        selected_tasks,
        selected_measures,
        selected_product_types,
        selected_deputies,
        selected_statuses,
        selected_sources,
        selected_financing,
        selected_kpkvk,
    )
    if active_filtered.empty:
        return None

    active_period_rows = active_filtered.copy()
    snapshot_label, dynamics_label = build_period_context(
        active_period_rows,
        years_for_calc,
        quarters_for_calc,
    )
    snapshot_period_number = resolve_snapshot_period_number(
        active_period_rows,
        years_for_calc,
        quarters_for_calc,
    )
    snapshot_quarter_num = (
        int(snapshot_period_number) % 10 if snapshot_period_number else 4
    )
    expected_period_completion = expected_completion_for_quarter(
        snapshot_quarter_num
    )
    active = collapse_to_latest_measure_rows(active_period_rows)
    if active.empty:
        return None

    total_active = len(active)
    submitted_count = calc_submitted(active)
    coverage = calc_coverage(active)
    completion = mean_completion(active)
    deviation_current = deviation_for_period(completion, snapshot_quarter_num)

    risk_assessed = risk_assessment_subset(active)
    risk_count = len(
        risk_assessed[risk_assessed["auto_risk"].isin(RISKY_LEVELS)]
    )
    critical_count = len(
        risk_assessed[risk_assessed["auto_risk"] == "Критичний ризик"]
    )
    risk_share = calc_risk_share(active)
    low_risk_share = calc_low_risk_share(active)
    without_data = len(active[active["status"] == "Не подано"])

    completed_count = len(active[active["status_display"] == "Виконано"])
    partly_count = len(
        active[active["status_display"] == "Частково виконано"]
    )
    not_done_count = len(
        active[active["status_display"] == "Не виконано"]
    )
    obsolete_count = len(
        active[active["status_display"] == "Втратило актуальність"]
    )
    not_time_count = len(
        active[active["status_display"] == "Не настав час"]
    )

    approved_requests_count = submitted_count
    not_counted_count = len(active[active["status"] == "Не подано"])
    conclusion_title, conclusion_text, conclusion_badge = dashboard_conclusion(
        completion,
        risk_share,
        coverage,
    )

    status_counts = (
        active.groupby("status_display").size().reset_index(name="Кількість")
    )
    risk_counts = (
        risk_assessed.groupby("auto_risk").size().reset_index(name="Кількість")
    )
    traffic_counts = (
        active.groupby("traffic_light").size().reset_index(name="Кількість")
    )
    goal_progress = build_goal_progress(active)

    dep_active = explode_departments(active)
    dep_active["Темп_річного_плану"] = dep_active.apply(
        annualised_plan_tempo_percent,
        axis=1,
    )
    dep_progress = (
        dep_active.groupby("ssp_department")
        .agg(
            Активних_заходів=("code", "count"),
            Виконання=("performance_score", "mean"),
            Подано=("status", lambda values: (values != "Не подано").sum()),
            Ризикових=(
                "auto_risk",
                lambda values: values.isin(RISKY_LEVELS).sum(),
            ),
            Критичних=(
                "auto_risk",
                lambda values: (values == "Критичний ризик").sum(),
            ),
            Середній_ризик=("risk_score", "mean"),
            Середній_темп=("Темп_річного_плану", "mean"),
        )
        .reset_index()
    )
    dep_progress["Виконання"] = dep_progress["Виконання"].fillna(0).round(2)
    dep_progress["Покриття_%"] = (
        dep_progress["Подано"] / dep_progress["Активних_заходів"] * 100
    ).round(2)
    dep_progress["Середній_ризик"] = (
        dep_progress["Середній_ризик"].fillna(0).round(2)
    )
    dep_progress["Середній_темп"] = pd.to_numeric(
        dep_progress["Середній_темп"], errors="coerce"
    ).round(2)

    return {
        "years_for_calc": list(years_for_calc),
        "quarters_for_calc": list(quarters_for_calc),
        "active_raw": active_raw,
        "active_period_rows": active_period_rows,
        "active": active,
        "snapshot_label": snapshot_label,
        "dynamics_label": dynamics_label,
        "snapshot_period_number": snapshot_period_number,
        "snapshot_quarter_num": snapshot_quarter_num,
        "expected_period_completion": expected_period_completion,
        "total_active": total_active,
        "submitted_count": submitted_count,
        "coverage": coverage,
        "completion": completion,
        "deviation_current": deviation_current,
        "risk_assessed": risk_assessed,
        "risk_count": risk_count,
        "critical_count": critical_count,
        "risk_share": risk_share,
        "low_risk_share": low_risk_share,
        "without_data": without_data,
        "completed_count": completed_count,
        "partly_count": partly_count,
        "not_done_count": not_done_count,
        "obsolete_count": obsolete_count,
        "not_time_count": not_time_count,
        "approved_requests_count": approved_requests_count,
        "not_counted_count": not_counted_count,
        "conclusion_title": conclusion_title,
        "conclusion_text": conclusion_text,
        "conclusion_badge": conclusion_badge,
        "period_label": snapshot_label,
        "status_counts": status_counts,
        "risk_counts": risk_counts,
        "traffic_counts": traffic_counts,
        "goal_progress": goal_progress,
        "dep_active": dep_active,
        "dep_progress": dep_progress,
    }


def _activate_dashboard_context(context):
    if context:
        globals().update(context)


def _format_summary_number(value, digits=1):
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "н/д"
    rounded = round(float(number), digits)
    if digits == 0:
        return str(int(round(rounded)))
    text = f"{rounded:.{digits}f}"
    return text.rstrip("0").rstrip(".").replace("-", "−")


def _short_summary_label(value, limit=88):
    text = re.sub(r"\s+", " ", "" if value is None else str(value)).strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit - 1].rstrip()}…"


def _render_section_summary(title, text, *, badge="", metrics=None, tone="neutral"):
    metrics = metrics or []
    safe_title = escape(str(title))
    safe_text = escape(str(text))
    safe_badge = escape(str(badge)) if badge else ""
    badge_html = (
        f'<span class="section-summary-badge">{safe_badge}</span>'
        if safe_badge else ""
    )
    metrics_html = "".join(
        f'<span class="section-summary-chip">{escape(str(item))}</span>'
        for item in metrics
    )
    metrics_block = (
        f'<div class="section-summary-metrics">{metrics_html}</div>'
        if metrics_html else ""
    )
    summary_html = (
        f'<div class="section-summary section-summary-{tone}">'
        f'<div class="section-summary-head">'
        f'<div class="section-summary-title">{safe_title}</div>'
        f'{badge_html}'
        f'</div>'
        f'<div class="section-summary-text">{safe_text}</div>'
        f'{metrics_block}'
        f'</div>'
    )
    st.markdown(summary_html, unsafe_allow_html=True)


def _critical_probability_groups(data, group_cols):
    """Rank groups whose mean forecast probability is below the critical threshold."""
    columns = list(group_cols) + [
        "Прогнозована_вірогідність",
        "Оцінюваних_заходів",
        "Середній_темп",
    ]
    if data is None or data.empty:
        return pd.DataFrame(columns=columns)

    assessed = data.copy()
    for column in ["included_in_risk_assessment", "risk_probability"]:
        if column not in assessed.columns:
            return pd.DataFrame(columns=columns)

    assessed = assessed[
        assessed["included_in_risk_assessment"].fillna(False).astype(bool)
    ].copy()
    assessed["_forecast_probability"] = pd.to_numeric(
        assessed["risk_probability"], errors="coerce"
    )
    assessed = assessed.dropna(subset=["_forecast_probability"])
    if assessed.empty:
        return pd.DataFrame(columns=columns)

    assessed["_annual_tempo"] = assessed.apply(
        annualised_plan_tempo_percent,
        axis=1,
    )
    grouped = (
        assessed
        .groupby(group_cols, dropna=False)
        .agg(
            Прогнозована_вірогідність=("_forecast_probability", "mean"),
            Оцінюваних_заходів=("code", "nunique"),
            Середній_темп=("_annual_tempo", "mean"),
        )
        .reset_index()
    )
    grouped = grouped[grouped["Прогнозована_вірогідність"] < 20].copy()
    if grouped.empty:
        return pd.DataFrame(columns=columns)

    grouped["Прогнозована_вірогідність"] = grouped[
        "Прогнозована_вірогідність"
    ].round(2)
    grouped["Середній_темп"] = pd.to_numeric(
        grouped["Середній_темп"], errors="coerce"
    ).round(2)
    return grouped.sort_values(
        ["Прогнозована_вірогідність", "Оцінюваних_заходів"],
        ascending=[True, False],
    )


def _missing_data_by_department(active):
    """Return departments ranked by the number of measures without submitted data."""
    columns = ["ssp_department", "Заходів_без_даних"]
    if active is None or active.empty:
        return pd.DataFrame(columns=columns)

    departments = explode_departments(active)
    if departments.empty or "status" not in departments.columns:
        return pd.DataFrame(columns=columns)

    missing = departments[departments["status"] == "Не подано"].copy()
    if missing.empty:
        return pd.DataFrame(columns=columns)

    return (
        missing
        .drop_duplicates(subset=["ssp_department", "code"])
        .groupby("ssp_department", dropna=False)["code"]
        .nunique()
        .reset_index(name="Заходів_без_даних")
        .sort_values(
            ["Заходів_без_даних", "ssp_department"],
            ascending=[False, True],
        )
    )


def _fact_completion_score(actual, target):
    score = plan_fact_percent(actual, target)
    if score is not None and not pd.isna(score):
        return float(score)
    yes_no = _normalise_yes_no(actual)
    if yes_no == "так":
        return 100.0
    if yes_no == "ні":
        return 0.0
    return None


def _goal_quarter_drop_signals(active, minimum_drop=10.0):
    """Find material goal-level drops between consecutive submitted quarters."""
    columns = [
        "goal_code",
        "strategic_goal",
        "Попереднє_виконання",
        "Поточне_виконання",
        "Падіння_вп",
    ]
    if active is None or active.empty:
        return pd.DataFrame(columns=columns)

    required = {
        "risk_current_fact",
        "risk_previous_fact",
        "risk_current_quarter",
        "risk_previous_quarter",
        "selected_target",
        "period_quarter",
    }
    if not required.issubset(active.columns):
        return pd.DataFrame(columns=columns)

    comparable = active.copy()
    comparable["_current_quarter"] = pd.to_numeric(
        comparable["risk_current_quarter"], errors="coerce"
    )
    comparable["_previous_quarter"] = pd.to_numeric(
        comparable["risk_previous_quarter"], errors="coerce"
    )
    comparable["_selected_quarter"] = comparable["period_quarter"].apply(
        quarter_to_number
    )
    comparable = comparable[
        comparable["_current_quarter"].notna()
        & comparable["_previous_quarter"].notna()
        & (comparable["_current_quarter"] == comparable["_selected_quarter"])
        & (
            comparable["_current_quarter"]
            - comparable["_previous_quarter"]
            == 1
        )
    ].copy()
    if comparable.empty:
        return pd.DataFrame(columns=columns)

    comparable["_current_score"] = comparable.apply(
        lambda row: _fact_completion_score(
            row.get("risk_current_fact", ""),
            row.get("selected_target", ""),
        ),
        axis=1,
    )
    comparable["_previous_score"] = comparable.apply(
        lambda row: _fact_completion_score(
            row.get("risk_previous_fact", ""),
            row.get("selected_target", ""),
        ),
        axis=1,
    )
    comparable = comparable.dropna(
        subset=["_current_score", "_previous_score"]
    )
    if comparable.empty:
        return pd.DataFrame(columns=columns)

    current_data = comparable.copy()
    current_data["performance_score"] = current_data["_current_score"]
    previous_data = comparable.copy()
    previous_data["performance_score"] = previous_data["_previous_score"]

    current_goals = build_goal_progress(current_data)[
        ["goal_code", "strategic_goal", "Виконання"]
    ].rename(columns={"Виконання": "Поточне_виконання"})
    previous_goals = build_goal_progress(previous_data)[
        ["goal_code", "strategic_goal", "Виконання"]
    ].rename(columns={"Виконання": "Попереднє_виконання"})
    comparison = current_goals.merge(
        previous_goals,
        on=["goal_code", "strategic_goal"],
        how="inner",
    )
    comparison = comparison.dropna(
        subset=["Поточне_виконання", "Попереднє_виконання"]
    )
    if comparison.empty:
        return pd.DataFrame(columns=columns)

    comparison["Падіння_вп"] = (
        comparison["Попереднє_виконання"]
        - comparison["Поточне_виконання"]
    ).round(2)
    comparison = comparison[
        comparison["Падіння_вп"] >= float(minimum_drop)
    ].copy()
    if comparison.empty:
        return pd.DataFrame(columns=columns)

    return comparison[columns].sort_values(
        "Падіння_вп",
        ascending=False,
    )


def _build_dynamics_trend_df(active_rows, selected_years_for_calc, selected_quarters_for_calc):
    trend_rows = []
    selected_period_pairs = sorted(
        {
            (int(year), quarter_to_roman(quarter))
            for year in selected_years_for_calc
            for quarter in selected_quarters_for_calc
        },
        key=lambda item: core_period_number(item[0], item[1]),
    )

    for year, quarter in selected_period_pairs:
        period_num = core_period_number(year, quarter)
        period_rows = active_rows[active_rows["period_number"] == period_num].copy()
        monitoring_was_not_conducted = (
            int(year) == 2026 and quarter_to_number(quarter) in (1, 2)
        )
        has_submitted_data = (
            not period_rows.empty
            and "status" in period_rows.columns
            and bool((period_rows["status"] != "Не подано").any())
        )
        has_data = has_submitted_data and not monitoring_was_not_conducted

        if monitoring_was_not_conducted:
            value, coverage_value, deviation_value = 0, 0, 0
        elif period_rows.empty:
            value, coverage_value = 0, 0
            deviation_value = deviation_for_period(value, quarter_to_number(quarter))
        else:
            value = mean_completion(period_rows)
            coverage_value = calc_coverage(period_rows)
            deviation_value = deviation_for_period(value, quarter_to_number(quarter))

        trend_rows.append({
            "Період": f"{year} {quarter}",
            "Рік": int(year),
            "Квартал": quarter,
            "Номер_кварталу": quarter_to_number(quarter),
            "Частка_року": quarter_to_number(quarter) / 4,
            "Виконання": value,
            "Покриття": coverage_value,
            "Відхилення за звітний період": deviation_value,
            "Є_дані": has_data,
            "Моніторинг_не_проводився": monitoring_was_not_conducted,
        })

    return pd.DataFrame(trend_rows), selected_period_pairs


def _dynamics_summary_text(trend_df, selected_period_pairs):
    if len(selected_period_pairs) < 2:
        return "Для оцінки динаміки оберіть щонайменше два квартали."
    if trend_df.empty or "Є_дані" not in trend_df.columns:
        return "Для оцінки динаміки потрібні дані щонайменше за два квартали."

    data_periods = trend_df[trend_df["Є_дані"] == True].copy()
    if len(data_periods) < 2:
        return "Для оцінки динаміки потрібні дані щонайменше за два квартали."

    data_periods = data_periods.sort_values(["Рік", "Номер_кварталу"])
    latest = data_periods.iloc[-1]
    previous = data_periods.iloc[-2]
    latest_value = float(latest["Виконання"])
    previous_value = float(previous["Виконання"])
    delta = latest_value - previous_value

    if delta > 0.05:
        direction_text = f"Виконання зросло на {_format_summary_number(abs(delta))} в.п. проти попереднього кварталу."
    elif delta < -0.05:
        direction_text = f"Виконання знизилося на {_format_summary_number(abs(delta))} в.п. проти попереднього кварталу."
    else:
        direction_text = "Виконання не змінилося проти попереднього кварталу."

    same_year = int(latest["Рік"]) == int(previous["Рік"])
    latest_share = float(latest["Частка_року"])
    previous_share = float(previous["Частка_року"])

    if same_year and latest_share > previous_share:
        observed_tempo = delta / (latest_share - previous_share)
        forecast_year = latest_value + observed_tempo * max(1 - latest_share, 0)
        tempo_is_sufficient = forecast_year >= 100
    else:
        expected_level = latest_share * 100
        tempo_is_sufficient = latest_value >= expected_level

    tempo_text = (
        "За поточної динаміки темп достатній для виходу на річний план."
        if tempo_is_sufficient
        else "Темп нижчий за потрібний для виходу на річний план."
    )
    return f"{direction_text} {tempo_text}"


_snapshot_description = (
    "Знімок стану на один обраний квартал. Показує загальний рівень виконання, "
    "розподіл статусів і ризиків станом на цю дату. Оскільки це знімок одного "
    "моменту, тут обирається один рік і один квартал — кілька періодів у знімок "
    "не звести."
)
_breakdown_description = (
    "Підсумок за обраний період у розрізі цілей, підрозділів, заступників і "
    "фінансування — хто скільки виконав за весь вибраний діапазон. Тут можна "
    "обрати кілька років і кварталів: значення підсумовуються по кожному "
    "об'єкту, щоб порівняти їх між собою."
)
_dynamics_description = (
    "Зміна показників у часі. Показує, як виконання, покриття й ризики рухалися "
    "по кварталах обраного діапазону. Тут вибір кількох періодів розкладається "
    "по осі часу, щоб побачити тенденцію — зростання чи спад."
)

if presentation_mode:
    _render_dashboard_section_intro("Моментний зріз", _snapshot_description)
    snapshot_years, snapshot_quarters = _render_single_period_panel()
    snapshot_context = _build_dashboard_context(
        snapshot_years,
        snapshot_quarters,
    )
    if snapshot_context is None:
        st.warning(
            "Немає заходів, що відповідають усім обраним параметрам відбору."
        )
        render_footer()
        st.stop()
    _activate_dashboard_context(snapshot_context)
    selected_years = snapshot_years
    selected_quarters = snapshot_quarters
else:
    _render_dashboard_section_intro("Моментний зріз", _snapshot_description)
    snapshot_years, snapshot_quarters = _render_single_period_panel()
    snapshot_content = st.container(key="dashboard_snapshot_content")

    _render_dashboard_section_intro("За розрізом", _breakdown_description)
    breakdown_years, breakdown_quarters = _render_multi_period_panel(
        "breakdown",
        "dash_breakdown_years",
        "dash_breakdown_quarters",
    )
    breakdown_content = st.container(key="dashboard_breakdown_content")

    _render_dashboard_section_intro("Динаміка", _dynamics_description)
    dynamics_years, dynamics_quarters = _render_multi_period_panel(
        "dynamics",
        "dash_dynamics_years",
        "dash_dynamics_quarters",
    )
    dynamics_content = st.container(key="dashboard_dynamics_content")

    snapshot_context = _build_dashboard_context(
        snapshot_years,
        snapshot_quarters,
    )
    breakdown_context = _build_dashboard_context(
        breakdown_years,
        breakdown_quarters,
    )
    dynamics_context = _build_dashboard_context(
        dynamics_years,
        dynamics_quarters,
    )

    if snapshot_context is None:
        with snapshot_content:
            st.warning(
                "Немає заходів, що відповідають усім обраним параметрам відбору."
            )
    if breakdown_context is None:
        with breakdown_content:
            st.warning(
                "Немає заходів, що відповідають усім обраним параметрам відбору."
            )
    if dynamics_context is None:
        with dynamics_content:
            st.warning(
                "Немає заходів, що відповідають усім обраним параметрам відбору."
            )

    selected_years = snapshot_years
    selected_quarters = snapshot_quarters


# ============================================================
# PRESENTATION MODE — PowerPoint-style slides
# ============================================================

if presentation_mode:
    # ТЗ-правка (09.07.2026, п.4): кнопка повного екрана тепер ВСЕРЕДИНІ
    # самої презентації і розгортає САМЕ презентацію, а не сторінку.
    # ── PDF-версія презентації (той самий набір слайдів) ─────
    with st.expander("📄 Завантажити презентацію у PDF"):
        st.caption(
            "PDF повторює структуру presentation mode: титул, ключові показники, "
            "основні графіки та висновок — у фірмовому стилі, з поточними фільтрами."
        )
        if st.button("Сформувати PDF", key="build_pres_pdf", use_container_width=True):
            with st.spinner("Формуємо PDF-презентацію..."):
                try:
                    import plotly.express as _pdf_px
                    _pdf_kpis = [
                        ("Всього активних заходів", str(total_active)),
                        ("Виконано", str(completed_count)),
                        ("Частково виконано", str(partly_count)),
                        ("Не виконано", str(not_done_count)),
                        ("Не настав час", str(not_time_count)),
                        ("Втратило актуальність", str(obsolete_count)),
                        ("Виконання СП, %", f"{completion}%"),
                        ("Покриття моніторингом, %", f"{coverage}%"),
                        ("Частка ризикових, %", f"{risk_share}%"),
                    ]
                    _st_fig = _pdf_px.bar(
                        x=["Виконано", "Частково виконано", "Не виконано", "Не настав час", "Втратило актуальність"],
                        y=[completed_count, partly_count, not_done_count, not_time_count, obsolete_count],
                        color_discrete_sequence=["#005BBB"],
                        title="",
                    )
                    _st_fig.update_layout(xaxis_title="", yaxis_title="Кількість заходів",
                                          plot_bgcolor="white", paper_bgcolor="white")
                    _pdf_figures = [("Статуси виконання заходів", _st_fig),
                                    ("Виконання СП", gauge_chart(completion, "Виконання СП"))]

                    _gf = weighted_failure_group(active, ["goal_code", "strategic_goal"])
                    _de = explode_departments(active)
                    _df_ = weighted_failure_group(_de, ["ssp_department"])
                    _ins = []
                    if not _gf.empty:
                        _r = _gf.iloc[0]
                        _ins.append(f"Найбільша концентрація невиконання: СЦ {_r['goal_code']} — "
                                    f"{int(_r['Невиконаних'])} із {int(_r['Активних_заходів'])} "
                                    f"(вага {_r['Вага_невиконання']}%)")
                    if not _df_.empty:
                        _r = _df_.iloc[0]
                        _ins.append(f"ССП із найвищою концентрацією: {_r['ssp_department']} — "
                                    f"{int(_r['Невиконаних'])} із {int(_r['Активних_заходів'])} "
                                    f"(вага {_r['Вага_невиконання']}%)")
                    _ins.append(f"Джерело даних: {data_source_mode}")

                    _pdf_bytes = build_presentation_pdf(
                        "Моніторинг стратегічного плану",
                        f"Період: {period_label}",
                        _pdf_kpis, conclusion_text[:110],
                        {"risk-high": "high", "risk-medium": "medium", "risk-low": "low"}[conclusion_badge],
                        _ins, _pdf_figures,
                    )
                    if _pdf_bytes:
                        st.download_button(
                            "⬇️ Завантажити PDF", data=_pdf_bytes,
                            file_name=f"presentation_{now_kyiv().strftime('%Y%m%d_%H%M')}.pdf",
                            mime="application/pdf", key="dl_pres_pdf", use_container_width=True,
                        )
                    else:
                        st.warning("Для PDF потрібен пакет `reportlab` у requirements.txt.")
                except Exception as _pdf_err:
                    show_incident(_pdf_err, context="Формування PDF презентаційного режиму Dashboard")

    # ── helpers ──────────────────────────────────────────────
    verdict_class = {"risk-high": "high", "risk-medium": "medium", "risk-low": "low"}[conclusion_badge]
    verdict_emoji = {"risk-high": "🔴", "risk-medium": "🟡", "risk-low": "🟢"}[conclusion_badge]

    # goal progress data for slide
    goal_rows_html = ""
    if not goal_progress.empty:
        gp_sorted = goal_progress.copy()
        gp_sorted["_goal_sort"] = gp_sorted["goal_code"].apply(code_sort_key)
        gp_sorted = gp_sorted.sort_values("_goal_sort")
        for _, gr in gp_sorted.iterrows():
            raw_pct = pd.to_numeric(pd.Series([gr["Виконання"]]), errors="coerce").iloc[0]
            if pd.isna(raw_pct):
                pct = 0.0
                pct_label = "н/д"
                bar_color = "#8A96A8"
            else:
                pct = min(max(float(raw_pct), 0), 100)
                pct_label = f"{pct:.0f}%"
                if pct >= 70:
                    bar_color = "#118847"
                elif pct >= 35:
                    bar_color = "#FF7A45"
                else:
                    bar_color = "#DC4A4A"
            short_name = str(gr["strategic_goal"])[:45] + ("…" if len(str(gr["strategic_goal"])) > 45 else "")
            goal_rows_html += f"""
            <div class="pres-goal-row">
                <div class="pres-goal-code">{gr['goal_code']}</div>
                <div class="pres-goal-name" title="{gr['strategic_goal']}">{short_name}</div>
                <div class="pres-goal-bar-bg">
                    <div class="pres-goal-bar-fill" style="width:{pct}%;background:{bar_color};"></div>
                </div>
                <div class="pres-goal-pct">{pct_label}</div>
            </div>"""

    # risk counts for slide
    risk_map = risk_assessed.groupby("auto_risk").size().to_dict()
    count_high = (
        risk_map.get("Критичний ризик", 0)
        + risk_map.get("Високий ризик", 0)
    )
    count_medium = risk_map.get("Середній ризик", 0)
    count_low = risk_map.get("Низький ризик", 0)

    # filter context label
    filter_parts = []
    if selected_years:
        filter_parts.append(f"📅 {', '.join(str(y) for y in selected_years)}")
    else:
        filter_parts.append("📅 Усі роки")
    if selected_quarters:
        filter_parts.append(f"🗓 {', '.join(selected_quarters)} кв.")
    else:
        filter_parts.append("🗓 Усі квартали")
    if selected_department_indices:
        filter_parts.append(f"🏢 ССП: {', '.join(selected_department_indices)}")
    else:
        filter_parts.append("🏢 Усі підрозділи")

    filter_pills_html = "".join(
        f'<span class="pres-filter-pill">{p}</span>' for p in filter_parts
    )

    # metric bar helper
    def pres_bar(label, value, color):
        pct = min(max(float(value), 0), 100)
        return f"""
        <div class="pres-metric-row">
            <div class="pres-metric-label">{label}</div>
            <div class="pres-metric-bar-bg">
                <div class="pres-metric-bar-fill" style="width:{pct}%;background:{color};"></div>
            </div>
            <div class="pres-metric-val">{value}%</div>
        </div>"""

    # ── фінансові дані для слайду 7 ───────────────────────────
    pres_fin_total = len(active)
    pres_fin_db = int(active["has_state_budget"].sum()) if "has_state_budget" in active.columns else 0
    pres_fin_mtd = int(active[active["financing_types"].apply(
        lambda t: isinstance(t, list) and "МТД / кошти партнерів" in t)].shape[0])         if "financing_types" in active.columns else 0
    pres_fin_no = int(active[active["financing_types"].apply(
        lambda t: isinstance(t, list) and t == ["Без фінансування"])].shape[0])         if "financing_types" in active.columns else 0
    pres_budget_sum = active["budget_2026"].sum() if "budget_2026" in active.columns else 0
    pres_budget_str = f"{pres_budget_sum:.2f} млрд грн" if pres_budget_sum else "н/д"

    pres_fin_bars_html = ""
    _fin_types_slide = [
        ("Державний бюджет", pres_fin_db, "#005BBB"),
        ("МТД / кошти партнерів", pres_fin_mtd, "#00A8A8"),
        ("Без фінансування", pres_fin_no, "#8A96A8"),
    ]
    for _label, _cnt, _color in _fin_types_slide:
        _pct_v = round(_cnt / pres_fin_total * 100, 1) if pres_fin_total else 0
        pres_fin_bars_html += f"""
        <div style="margin-bottom:16px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:5px;">
                <span style="font-size:13px;font-weight:700;color:rgba(255,255,255,.7);">{_label}</span>
                <span style="font-size:13px;font-weight:900;color:#fff;">{_cnt} <span style="font-size:11px;color:rgba(255,255,255,.35);">({_pct_v}%)</span></span>
            </div>
            <div style="background:rgba(255,255,255,.07);border-radius:99px;height:10px;overflow:hidden;">
                <div style="width:{_pct_v}%;height:100%;background:{_color};border-radius:99px;"></div>
            </div>
        </div>"""

    pres_kpkvk_html = ""
    if "budget_kpkvk" in active.columns:
        _kp_tbl = (
            active[active["budget_kpkvk"] != ""]
            .groupby("budget_kpkvk")
            .agg(_Заходів=("code", "count"), _Бюджет=("budget_2026", "sum"))
            .reset_index()
            .sort_values("_Заходів", ascending=False)
            .head(6)
        )
        for _, _krow in _kp_tbl.iterrows():
            _b_str = f"{_krow['_Бюджет']:.2f}" if pd.notna(_krow["_Бюджет"]) and _krow["_Бюджет"] > 0 else "—"
            pres_kpkvk_html += (
                f'<div style="display:flex;justify-content:space-between;align-items:center;'                f'padding:10px 0;border-bottom:1px solid rgba(255,255,255,.06);">'                f'<span style="font-size:14px;font-weight:800;color:#FFD500;">{_krow["budget_kpkvk"]}</span>'                f'<span style="font-size:12px;color:rgba(255,255,255,.5);">{int(_krow["_Заходів"])} заходів</span>'                f'<span style="font-size:12px;color:rgba(255,255,255,.7);font-weight:700;">{_b_str} млрд грн</span>'                f'</div>'
            )
    if not pres_kpkvk_html:
        pres_kpkvk_html = '<div style="color:rgba(255,255,255,.3);margin-top:12px;">КПКВК не визначено</div>'

    # ── топ-5 проблемних заходів для слайду 6 ─────────────────
    top5_html = ""
    top5_data = active[
        (active["auto_risk"].isin(RISKY_LEVELS) |
         (active["status"] == "Не подано")) &
        (active["included_in_risk_assessment"] == True)
    ].copy()
    top5_data = top5_data.sort_values("risk_score", ascending=False).head(5)

    for _, tr in top5_data.iterrows():
        if tr["auto_risk"] == "Критичний ризик":
            risk_color = "#DC4A4A"
        elif tr["auto_risk"] == "Високий ризик":
            risk_color = "#FF7A45"
        else:
            risk_color = "#F4B400"
        dep_short = str(tr.get("department", ""))[:12]
        name_short = str(tr.get("name", ""))[:70] + ("…" if len(str(tr.get("name", ""))) > 70 else "")
        top5_html += (
            f'<div style="display:flex;align-items:flex-start;gap:14px;padding:14px 0;'
            f'border-bottom:1px solid rgba(255,255,255,0.06);">'
            f'<div style="background:{risk_color};color:#032A63;font-size:10px;font-weight:900;'
            f'border-radius:6px;padding:3px 8px;white-space:nowrap;margin-top:2px;">'
            f'{tr.get("auto_risk","")}</div>'
            f'<div style="flex:1;">'
            f'<div style="font-size:13px;color:rgba(255,255,255,0.85);font-weight:600;line-height:1.4;">'
            f'{name_short}</div>'
            f'<div style="display:flex;gap:10px;margin-top:5px;flex-wrap:wrap;">'
            f'<span style="font-size:10px;color:rgba(255,255,255,0.35);">📋 {tr.get("code","")}</span>'
            f'<span style="font-size:10px;color:rgba(255,255,255,0.35);">🏢 {dep_short}</span>'
            f'<span style="font-size:10px;color:rgba(255,255,255,0.35);">📊 {tr.get("status_display","")}</span>'
            f'<span style="font-size:10px;color:rgba(255,255,255,0.35);">🎯 Виконання: {tr.get("performance_score", 0) or 0:.0f}%</span>'
            f'</div></div></div>'
        )
    if not top5_html:
        top5_html = '<div style="color:rgba(255,255,255,0.3);margin-top:24px;">Критичних заходів не виявлено</div>'

    # ── render slides ─────────────────────────────────────────
    import streamlit.components.v1 as components
    _pres_css = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #032A63; font-family: 'Helvetica Neue', Arial, sans-serif; overflow-x: hidden; }
    .pres-overlay { min-height: 100vh; background: #032A63; overflow-y: auto; }
    .pres-ua-bar { height: 3px; background: linear-gradient(90deg,#005BBB 50%,#FFD500 50%); width: 100%; }
    .pres-nav { position: sticky; top: 0; z-index: 100; background: rgba(10,15,30,0.95); backdrop-filter: blur(12px); border-bottom: 1px solid rgba(255,255,255,0.08); display: flex; align-items: center; justify-content: space-between; padding: 10px 32px; }
    .pres-nav-title { color: rgba(255,255,255,0.5); font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; font-weight: 600; }
    .pres-nav-dots { display: flex; gap: 8px; align-items: center; }
    .pres-dot { width: 8px; height: 8px; border-radius: 50%; background: rgba(255,255,255,0.2); }
    .pres-dot.active { background: #FFD500; width: 24px; border-radius: 4px; }
    .pres-slide { min-height: 100vh; display: flex; flex-direction: column; justify-content: center; padding: 48px 64px; position: relative; border-bottom: 1px solid rgba(255,255,255,0.04); }
    .pres-slide:last-child { border-bottom: none; }
    .pres-slide-num { position: absolute; top: 24px; right: 40px; font-size: 11px; color: rgba(255,255,255,0.2); letter-spacing: 0.1em; font-weight: 600; }
    .pres-slide-title { background: #032A63; }
    .pres-title-eyebrow { font-size: 11px; letter-spacing: 0.2em; text-transform: uppercase; color: #FFD500; font-weight: 700; margin-bottom: 20px; }
    .pres-title-h1 { font-size: clamp(32px,4vw,56px); font-weight: 900; color: #fff; line-height: 1.1; margin-bottom: 16px; max-width: 800px; }
    .pres-title-sub { font-size: clamp(14px,1.4vw,18px); color: rgba(255,255,255,0.5); max-width: 600px; line-height: 1.6; margin-bottom: 40px; }
    .pres-filter-pills { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }
    .pres-filter-pill { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12); border-radius: 20px; padding: 6px 16px; font-size: 12px; color: rgba(255,255,255,0.7); font-weight: 600; }
    .pres-slide-conclusion { background: #032A63; }
    .pres-slide-conclusion.ok { background: #032A63; }
    .pres-slide-conclusion.medium { background: #032A63; }
    .pres-section-label { font-size: 11px; letter-spacing: 0.18em; text-transform: uppercase; color: rgba(255,255,255,0.35); font-weight: 700; margin-bottom: 24px; }
    .pres-verdict-badge { display: inline-flex; align-items: center; gap: 10px; padding: 10px 24px; border-radius: 10px; font-size: clamp(18px,2vw,26px); font-weight: 900; margin-bottom: 20px; }
    .pres-verdict-badge.high { background: rgba(220,38,38,0.2); border: 1.5px solid #DC4A4A; color: #DC4A4A; }
    .pres-verdict-badge.medium { background: rgba(217,119,6,0.2); border: 1.5px solid #FF7A45; color: #F4B400; }
    .pres-verdict-badge.low { background: rgba(22,163,74,0.2); border: 1.5px solid #118847; color: #1E9E57; }
    .pres-verdict-text { font-size: clamp(13px,1.2vw,16px); color: rgba(255,255,255,0.55); max-width: 680px; line-height: 1.7; margin-bottom: 40px; }
    .pres-slide-kpis { background: #032A63; }
    .pres-kpi-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 20px; margin-top: 32px; }
    .pres-kpi-card { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 28px 24px; display: flex; flex-direction: column; gap: 6px; position: relative; overflow: hidden; }
    .pres-kpi-card::before { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px; border-radius: 14px 14px 0 0; }
    .pres-kpi-card.blue::before { background: #4D8DFF; }
    .pres-kpi-card.green::before { background: #00A8A8; }
    .pres-kpi-card.red::before { background: #FF7A45; }
    .pres-kpi-card.yellow::before { background: #F4B400; }
    .pres-kpi-card.gray::before { background: #8A96A8; }
    .pres-kpi-label { font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: rgba(255,255,255,0.4); }
    .pres-kpi-value { font-size: clamp(36px,4vw,56px); font-weight: 900; color: #fff; line-height: 1; }
    .pres-kpi-sub { font-size: 13px; color: rgba(255,255,255,0.35); font-weight: 600; }
    .pres-slide-goals { background: #032A63; }
    .pres-goal-bar-wrap { margin-top: 28px; display: flex; flex-direction: column; gap: 14px; }
    .pres-goal-row { display: flex; align-items: center; gap: 16px; }
    .pres-goal-code { font-size: 11px; font-weight: 800; color: rgba(255,255,255,0.4); min-width: 36px; text-align: right; }
    .pres-goal-name { font-size: 13px; color: rgba(255,255,255,0.7); flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 320px; }
    .pres-goal-bar-bg { flex: 2; background: rgba(255,255,255,0.06); border-radius: 99px; height: 10px; overflow: hidden; }
    .pres-goal-bar-fill { height: 100%; border-radius: 99px; }
    .pres-goal-pct { font-size: 13px; font-weight: 800; color: #fff; min-width: 44px; text-align: right; }
    .pres-slide-risks { background: #032A63; }
    .pres-risk-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 20px; margin-top: 32px; }
    .pres-risk-card { border-radius: 14px; padding: 28px 24px; display: flex; flex-direction: column; gap: 8px; }
    .pres-risk-card.high { background: rgba(220,38,38,0.12); border: 1.5px solid rgba(220,38,38,0.3); }
    .pres-risk-card.medium { background: rgba(217,119,6,0.1); border: 1.5px solid rgba(217,119,6,0.25); }
    .pres-risk-card.low { background: rgba(22,163,74,0.1); border: 1.5px solid rgba(22,163,74,0.25); }
    .pres-risk-label { font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; }
    .pres-risk-card.high .pres-risk-label { color: #DC4A4A; }
    .pres-risk-card.medium .pres-risk-label { color: #F4B400; }
    .pres-risk-card.low .pres-risk-label { color: #1E9E57; }
    .pres-risk-val { font-size: clamp(40px,5vw,64px); font-weight: 900; line-height: 1; }
    .pres-risk-card.high .pres-risk-val { color: #DC4A4A; }
    .pres-risk-card.medium .pres-risk-val { color: #F4B400; }
    .pres-risk-card.low .pres-risk-val { color: #1E9E57; }
    .pres-risk-sub { font-size: 13px; color: rgba(255,255,255,0.4); font-weight: 600; }
    .pres-slide-h2 { font-size: clamp(24px,2.8vw,38px); font-weight: 900; color: #fff; margin-bottom: 4px; line-height: 1.15; }
    .pres-slide-hsub { font-size: clamp(12px,1.1vw,15px); color: rgba(255,255,255,0.4); margin-bottom: 0; }
    .pres-metric-rows { margin-top: 32px; display: flex; flex-direction: column; gap: 20px; }
    .pres-metric-row { display: flex; align-items: center; gap: 20px; }
    .pres-metric-label { font-size: 13px; font-weight: 700; color: rgba(255,255,255,0.55); min-width: 220px; }
    .pres-metric-bar-bg { flex: 1; background: rgba(255,255,255,0.06); border-radius: 99px; height: 12px; overflow: hidden; }
    .pres-metric-bar-fill { height: 100%; border-radius: 99px; }
    .pres-metric-val { font-size: 16px; font-weight: 900; color: #fff; min-width: 56px; text-align: right; }
    .pres-exit-hint { position: fixed; bottom: 24px; right: 32px; z-index: 200; background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; padding: 8px 16px; font-size: 11px; color: rgba(255,255,255,0.35); letter-spacing: 0.08em; pointer-events: none; }
    """
    components.html(f"""<!DOCTYPE html>
<html lang="uk">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>{_pres_css}</style>
</head>
<body>
    <div class="pres-overlay">
        <div class="pres-ua-bar"></div>

        <!-- FULLSCREEN (лише презентація) -->
        <button id="pres-fs-btn" style="position:fixed;top:14px;right:16px;z-index:9999;
            font-family:'Segoe UI',system-ui,sans-serif;font-size:13px;font-weight:800;
            color:#fff;background:#005BBB;border:none;border-radius:10px;
            padding:8px 14px;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,.35);">
            ⛶ На весь екран
        </button>
        <script>
          const _fsBtn = document.getElementById("pres-fs-btn");
          _fsBtn.addEventListener("click", () => {{
            if (document.fullscreenElement) {{
              document.exitFullscreen();
            }} else {{
              document.documentElement.requestFullscreen();
            }}
          }});
          document.addEventListener("fullscreenchange", () => {{
            _fsBtn.textContent = document.fullscreenElement
              ? "✕ Вийти з повного екрана" : "⛶ На весь екран";
          }});
        </script>

        <!-- NAV BAR -->
        <div class="pres-nav">
            <div class="pres-nav-title">Стратегічний моніторинг · Presentation mode</div>
            <div class="pres-nav-dots">
                <div class="pres-dot active"></div>
                <div class="pres-dot"></div>
                <div class="pres-dot"></div>
                <div class="pres-dot"></div>
                <div class="pres-dot"></div>
                <div class="pres-dot"></div>
                <div class="pres-dot"></div>
            </div>
            <div style="font-size:11px;color:rgba(255,255,255,0.3);letter-spacing:.08em;">
                ⬆ прокрутіть для перегляду слайдів
            </div>
        </div>

        <!-- ══ SLIDE 1 — TITLE ══ -->
        <div class="pres-slide pres-slide-title">
            <div class="pres-slide-num">01 / 07</div>
            <div class="pres-title-eyebrow">🇺🇦 Міністерство економіки, довкілля та сільського господарства України</div>
            <div class="pres-title-h1">Аналітичний дашборд результативності стратегічного плану</div>
            <div class="pres-title-sub">
                Комплексна панель моніторингу та оцінювання стратегічних результатів —
                в розрізі стратегічних цілей, завдань та самостійних структурних підрозділів.
            </div>
            <div class="pres-filter-pills">
                {filter_pills_html}
                <span class="pres-filter-pill">📌 {total_active} активних заходів</span>
                <span class="pres-filter-pill">🕐 {now_kyiv().strftime('%d.%m.%Y %H:%M')}</span>
            </div>
        </div>

        <!-- ══ SLIDE 2 — VERDICT ══ -->
        <div class="pres-slide pres-slide-conclusion {verdict_class}">
            <div class="pres-slide-num">02 / 07</div>
            <div class="pres-section-label">Висновок системи</div>
            <div class="pres-verdict-badge {verdict_class}">{verdict_emoji} {conclusion_title}</div>
            <div class="pres-verdict-text">{conclusion_text}</div>

            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:20px;max-width:680px;">
                <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:20px 18px;">
                    <div style="font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:rgba(255,255,255,.35);margin-bottom:8px;">Виконання СП</div>
                    <div style="font-size:44px;font-weight:900;color:#fff;line-height:1;">{completion}%</div>
                    <div style="font-size:12px;color:rgba(255,255,255,.35);margin-top:4px;">Середнє по активних заходах</div>
                </div>
                <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:20px 18px;">
                    <div style="font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:rgba(255,255,255,.35);margin-bottom:8px;">Покриття</div>
                    <div style="font-size:44px;font-weight:900;color:#fff;line-height:1;">{coverage}%</div>
                    <div style="font-size:12px;color:rgba(255,255,255,.35);margin-top:4px;">Заходів з поданими даними</div>
                </div>
                <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:20px 18px;">
                    <div style="font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:rgba(255,255,255,.35);margin-bottom:8px;">Відхилення</div>
                    <div style="font-size:44px;font-weight:900;color:{'#DC4A4A' if deviation_current < 0 else '#1E9E57'};line-height:1;">{deviation_current:+.1f}</div>
                    <div style="font-size:12px;color:rgba(255,255,255,.35);margin-top:4px;">В.п. від планового рівня</div>
                </div>
            </div>
        </div>

        <!-- ══ SLIDE 3 — KEY METRICS ══ -->
        <div class="pres-slide pres-slide-kpis">
            <div class="pres-slide-num">03 / 07</div>
            <div class="pres-section-label">Ключові показники</div>
            <div class="pres-slide-h2">Статистика виконання заходів</div>
            <div class="pres-slide-hsub">{period_label} · {total_active} активних заходів</div>

            <div class="pres-kpi-grid">
                <div class="pres-kpi-card blue">
                    <div class="pres-kpi-label">Всього заходів</div>
                    <div class="pres-kpi-value">{total_active}</div>
                    <div class="pres-kpi-sub">100%</div>
                </div>
                <div class="pres-kpi-card green">
                    <div class="pres-kpi-label">Виконано</div>
                    <div class="pres-kpi-value">{completed_count}</div>
                    <div class="pres-kpi-sub">{pct_value(completed_count, total_active)}</div>
                </div>
                <div class="pres-kpi-card green">
                    <div class="pres-kpi-label">Погоджено</div>
                    <div class="pres-kpi-value">{approved_requests_count}</div>
                    <div class="pres-kpi-sub">{pct_value(approved_requests_count, total_active)}</div>
                </div>
                <div class="pres-kpi-card yellow">
                    <div class="pres-kpi-label">Частково виконано</div>
                    <div class="pres-kpi-value">{partly_count}</div>
                    <div class="pres-kpi-sub">{pct_value(partly_count, total_active)}</div>
                </div>
                <div class="pres-kpi-card red">
                    <div class="pres-kpi-label">Не враховано</div>
                    <div class="pres-kpi-value">{not_counted_count}</div>
                    <div class="pres-kpi-sub">{pct_value(not_counted_count, total_active)}</div>
                </div>
                <div class="pres-kpi-card red">
                    <div class="pres-kpi-label">Не виконано</div>
                    <div class="pres-kpi-value">{not_done_count}</div>
                    <div class="pres-kpi-sub">{pct_value(not_done_count, total_active)}</div>
                </div>
                <div class="pres-kpi-card gray">
                    <div class="pres-kpi-label">Не настав час</div>
                    <div class="pres-kpi-value">{not_time_count}</div>
                    <div class="pres-kpi-sub">{pct_value(not_time_count, total_active)}</div>
                </div>
            </div>

            <div class="pres-metric-rows" style="max-width:680px;margin-top:40px;">
                {pres_bar('Виконання СП', completion, '#005BBB')}
                {pres_bar('Покриття моніторингом', coverage, '#00A8A8')}
                {pres_bar('Частка без ризику', round(low_risk_share, 1), '#118847')}
            </div>
        </div>

        <!-- ══ SLIDE 4 — STRATEGIC GOALS ══ -->
        <div class="pres-slide pres-slide-goals">
            <div class="pres-slide-num">04 / 07</div>
            <div class="pres-section-label">Стратегічні цілі</div>
            <div class="pres-slide-h2">Виконання за стратегічними цілями</div>
            <div class="pres-slide-hsub">Відсоток виконання по кожній стратегічній цілі · {period_label}</div>
            <div class="pres-goal-bar-wrap">
                {goal_rows_html if goal_rows_html else '<div style="color:rgba(255,255,255,0.3);margin-top:24px;">Дані відсутні за обраними фільтрами</div>'}
            </div>
        </div>

        <!-- ══ SLIDE 5 — RISKS ══ -->
        <div class="pres-slide pres-slide-risks">
            <div class="pres-slide-num">05 / 07</div>
            <div class="pres-section-label">Автоматична оцінка ризиків</div>
            <div class="pres-slide-h2">Розподіл ризиків недосягнення</div>
            <div class="pres-slide-hsub">{total_active} активних заходів · {period_label}</div>

            <div class="pres-risk-grid">
                <div class="pres-risk-card high">
                    <div class="pres-risk-label">🔴 Критичний / високий ризик</div>
                    <div class="pres-risk-val">{count_high}</div>
                    <div class="pres-risk-sub">{pct_value(count_high, total_active)} від усіх заходів</div>
                </div>
                <div class="pres-risk-card medium">
                    <div class="pres-risk-label">🟡 Середній ризик</div>
                    <div class="pres-risk-val">{count_medium}</div>
                    <div class="pres-risk-sub">{pct_value(count_medium, total_active)} від усіх заходів</div>
                </div>
                <div class="pres-risk-card low">
                    <div class="pres-risk-label">🟢 Низький ризик</div>
                    <div class="pres-risk-val">{count_low}</div>
                    <div class="pres-risk-sub">{pct_value(count_low, total_active)} від усіх заходів</div>
                </div>
            </div>

            <div style="margin-top:48px;padding:24px 28px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:14px;max-width:640px;">
                <div style="font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(255,255,255,.3);margin-bottom:12px;">Загальний висновок системи</div>
                <div style="font-size:15px;color:rgba(255,255,255,.7);line-height:1.7;">{conclusion_text}</div>
                <div style="margin-top:16px;display:flex;gap:12px;flex-wrap:wrap;">
                    <span style="background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:6px;padding:5px 12px;font-size:11px;color:rgba(255,255,255,.5);font-weight:600;">Частка з ризиком: {risk_share}%</span>
                    <span style="background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:6px;padding:5px 12px;font-size:11px;color:rgba(255,255,255,.5);font-weight:600;">Без даних: {without_data} заходів</span>
                </div>
            </div>
        </div>

        <div class="pres-exit-hint">↑ прокрутіть вверх · вимкніть тумблер щоб вийти</div>

        <!-- ══ SLIDE 6 — TOP-5 ПРОБЛЕМНІ ЗАХОДИ ══ -->
        <div class="pres-slide" style="background:#032A63;">
            <div class="pres-slide-num">06 / 07</div>
            <div class="pres-section-label">Увага керівництва</div>
            <div class="pres-slide-h2">Топ-5 критичних заходів</div>
            <div class="pres-slide-hsub">Заходи з найвищим ризиком недосягнення · {period_label}</div>
            <div style="margin-top:28px;max-width:860px;">
                {top5_html}
            </div>
        </div>


        <!-- ══ SLIDE 7 — ФІНАНСУВАННЯ ══ -->
        <div class="pres-slide" style="background:#032A63;">
            <div class="pres-slide-num">07 / 07</div>
            <div class="pres-section-label">Фінансування заходів</div>
            <div class="pres-slide-h2">Структура та обсяги фінансування</div>
            <div class="pres-slide-hsub">{period_label} · {pres_fin_total} активних заходів</div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:40px;margin-top:36px;max-width:900px;">
                <div>
                    <div style="font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(255,255,255,.3);margin-bottom:20px;">Джерела фінансування</div>
                    {pres_fin_bars_html}
                    <div style="margin-top:24px;background:rgba(0,91,187,.12);border:1px solid rgba(0,91,187,.25);border-radius:12px;padding:20px 22px;">
                        <div style="font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:rgba(255,255,255,.3);margin-bottom:8px;">Бюджет ДБ 2026</div>
                        <div style="font-size:36px;font-weight:900;color:#fff;line-height:1;">{pres_budget_str}</div>
                        <div style="font-size:12px;color:rgba(255,255,255,.3);margin-top:4px;">часткові дані — не всі заходи мають суми</div>
                    </div>
                </div>
                <div>
                    <div style="font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(255,255,255,.3);margin-bottom:20px;">Топ КПКВК за кількістю заходів</div>
                    {pres_kpkvk_html}
                </div>
            </div>
        </div>

    </div>
</body></html>""", height=600, scrolling=True)
    render_footer()
    st.stop()

# ============================================================
# СЕКЦІЯ: МОМЕНТНИЙ ЗРІЗ
# ============================================================

# Висновок, інсайти та панель показників моментного зрізу.
if snapshot_context is not None:
    _activate_dashboard_context(snapshot_context)
    with snapshot_content:
        _render_section_summary(
            "Стан зараз",
            conclusion_text,
            badge=conclusion_title,
            metrics=[
                f"Виконання: {_format_summary_number(completion)}%",
                f"Покриття: {_format_summary_number(coverage)}%",
                f"Відхилення: {_format_summary_number(deviation_current)} в.п.",
                f"Активних заходів: {total_active}",
            ],
            tone=conclusion_badge,
        )

        _main_kpi_items = [
            {"key": "all", "title": "Заходів", "count": total_active, "percent": "100.0%", "color": "kpi-blue"},
            {"key": "completed", "title": "Виконано", "count": completed_count, "percent": pct_value(completed_count, total_active), "color": "kpi-green"},
            {"key": "approved", "title": "Погоджено", "count": approved_requests_count, "percent": pct_value(approved_requests_count, total_active), "color": "kpi-green"},
            {"key": "not_counted", "title": "Не враховано", "count": not_counted_count, "percent": pct_value(not_counted_count, total_active), "color": "kpi-red"},
            {"key": "not_done", "title": "Не виконано", "count": not_done_count, "percent": pct_value(not_done_count, total_active), "color": "kpi-red"},
            {"key": "obsolete", "title": "Втратило актуальність", "count": obsolete_count, "percent": pct_value(obsolete_count, total_active), "color": "kpi-gray"},
            {"key": "not_time", "title": "Не настав час", "count": not_time_count, "percent": pct_value(not_time_count, total_active), "color": "kpi-gray"},
            {"key": "partly", "title": "Частково виконано", "count": partly_count, "percent": pct_value(partly_count, total_active), "color": "kpi-yellow"},
        ]
        _selected_kpi = render_kpi_grid(_main_kpi_items, interactive=True, query_key="kpi")

        _kpi_detail_frames = {
            "all": active.copy(),
            "completed": active[active["status_display"] == "Виконано"].copy(),
            "approved": active[active["status"] != "Не подано"].copy(),
            "not_counted": active[active["status"] == "Не подано"].copy(),
            "not_done": active[active["status_display"] == "Не виконано"].copy(),
            "obsolete": active[active["status_display"] == "Втратило актуальність"].copy(),
            "not_time": active[active["status_display"] == "Не настав час"].copy(),
            "partly": active[active["status_display"] == "Частково виконано"].copy(),
        }


        if _selected_kpi in _kpi_detail_frames:
            _selected_item = next(item for item in _main_kpi_items if item["key"] == _selected_kpi)
            _detail_frame = _kpi_detail_frames[_selected_kpi]
            st.markdown(
                '<div style="margin-top:16px;padding:16px 18px;background:#fff;border:1px solid #DCE4F0;'
                'border-radius:14px;"><div style="font-size:17px;font-weight:900;color:#132238;">'
                f'Деталізація KPI: {_selected_item["title"]} '
                '<span style="font-size:11px;color:#8A6400;background:#FDF3D8;border:1px solid #F4B400;'
                'border-radius:999px;padding:3px 8px;">тест</span></div>'
                f'<div style="font-size:13px;color:#61708A;margin-top:4px;">На картці: {_selected_item["count"]}; '
                f'у деталізації: {len(_detail_frame)}. Повторне натискання згортає блок.</div></div>',
                unsafe_allow_html=True,
            )
            if len(_detail_frame) != int(_selected_item["count"]):
                st.error("Кількість рядків деталізації не збігається з показником KPI.")
            render_measure_rows_with_card_links(
                _detail_frame,
                key_prefix=f"dashboard_kpi_{_selected_kpi}",
            )

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Автоматичні інсайти</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-subtitle">Пріоритетні загрози річному плану, прогалини даних та аномалії динаміки</div>', unsafe_allow_html=True)

        insight_count = 0

        goal_threats = _critical_probability_groups(
            active,
            ["goal_code", "strategic_goal"],
        )
        for _, row in goal_threats.head(3).iterrows():
            goal_code = escape(clean(row.get("goal_code", "")) or "Без коду")
            probability = _format_summary_number(
                row.get("Прогнозована_вірогідність"),
            )
            tempo = pd.to_numeric(
                pd.Series([row.get("Середній_темп")]),
                errors="coerce",
            ).iloc[0]
            tempo_text = (
                f"; середній темп — {_format_summary_number(tempo)}% річного плану"
                if pd.notna(tempo)
                else ""
            )
            render_insight(
                f"🔴 Ціль {goal_code} під загрозою зриву річного плану — "
                f"середня прогнозована вірогідність досягнення {probability}%, "
                f"нижча за критичний поріг 20%{tempo_text}.",
                "danger",
            )
            insight_count += 1

        department_threats = _critical_probability_groups(
            explode_departments(active),
            ["ssp_department"],
        )
        for _, row in department_threats.head(3).iterrows():
            department = escape(
                clean(row.get("ssp_department", "")) or "Не визначено"
            )
            probability = _format_summary_number(
                row.get("Прогнозована_вірогідність"),
            )
            tempo = pd.to_numeric(
                pd.Series([row.get("Середній_темп")]),
                errors="coerce",
            ).iloc[0]
            tempo_text = (
                f"; середній темп — {_format_summary_number(tempo)}% річного плану"
                if pd.notna(tempo)
                else ""
            )
            render_insight(
                f"🔴 Підрозділ {department} під загрозою зриву річного плану — "
                f"середня прогнозована вірогідність досягнення {probability}%, "
                f"нижча за критичний поріг 20%{tempo_text}.",
                "danger",
            )
            insight_count += 1

        missing_departments = _missing_data_by_department(active)
        for _, row in missing_departments.head(3).iterrows():
            department = escape(
                clean(row.get("ssp_department", "")) or "Не визначено"
            )
            missing_count = int(row.get("Заходів_без_даних", 0) or 0)
            render_insight(
                f"⚠️ Підрозділ {department} не подав дані по "
                f"{missing_count} заходах.",
                "warn",
            )
            insight_count += 1

        goal_drops = _goal_quarter_drop_signals(active)
        for _, row in goal_drops.head(3).iterrows():
            goal_code = escape(clean(row.get("goal_code", "")) or "Без коду")
            drop = _format_summary_number(row.get("Падіння_вп"))
            render_insight(
                f"📉 Різке зниження: виконання цілі {goal_code} впало на "
                f"{drop} в.п. проти попереднього кварталу.",
                "warn",
            )
            insight_count += 1

        if insight_count == 0:
            render_insight(
                "Критичних сигналів, що потребують негайної уваги, не виявлено.",
                "info",
            )

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Показники виконання стратегічного плану</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-subtitle">Щоб зберегти окремий графік — наведіть на нього курсор '
            'і натисніть значок 📷 (Download as PNG) у верхньому куті графіка.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(f'<div class="section-subtitle">{snapshot_label}</div>', unsafe_allow_html=True)

        ind_col1, ind_col2 = st.columns([1, 1.3])

        with ind_col1:
            fig_gauge = gauge_chart(completion, "Виконання СП")
            render_plotly_chart(fig_gauge, use_container_width=True)

        with ind_col2:
            fig_indicators = summary_indicators_chart(
                completion,
                coverage,
                deviation_current,
                low_risk_share,
                expected_period_completion,
            )
            render_plotly_chart(fig_indicators, use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)

# Статуси виконання моментного зрізу.
if snapshot_context is not None:
    _activate_dashboard_context(snapshot_context)
    with snapshot_content:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Статуси виконання за принципом світлофора</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-subtitle">Розподіл активних заходів за станом виконання</div>', unsafe_allow_html=True)
        fig_tl = px.pie(
            traffic_counts,
            names="traffic_light",
            values="Кількість",
            hole=0.52,
            color="traffic_light",
            color_discrete_map=TRAFFIC_COLORS,
            labels={
                "traffic_light": "Статус виконання",
                "Кількість": "Кількість заходів",
            },
        )
        fig_tl.update_traces(
            textfont_size=12,
            textposition="outside",
            texttemplate="%{label}: %{percent:.1%}",
            marker=dict(line=dict(color="#ffffff", width=2))
        )
        fig_tl.update_layout(uniformtext_minsize=10, uniformtext_mode="hide")
        fig_tl.update_layout(
            **CHART_LAYOUT,
            height=340,
            showlegend=True,
        )
        apply_safe_plotly_layout(fig_tl, has_legend=True)
        render_plotly_chart(fig_tl, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# СЕКЦІЯ: ЗА РОЗРІЗОМ — СТРАТЕГІЧНІ ЦІЛІ ТА ОРГАНІЗАЦІЙНІ РОЗРІЗИ
# ============================================================

# Виконання за стратегічними цілями.
if breakdown_context is not None:
    _activate_dashboard_context(breakdown_context)
    with breakdown_content:
        _breakdown_goal_failure = weighted_failure_group(
            active,
            ["goal_code", "strategic_goal"],
        )
        _breakdown_department_failure = weighted_failure_group(
            explode_departments(active),
            ["ssp_department"],
        )
        if not _breakdown_goal_failure.empty:
            _breakdown_goal_failure = _breakdown_goal_failure[
                _breakdown_goal_failure["Невиконаних"] > 0
            ]
        if not _breakdown_department_failure.empty:
            _breakdown_department_failure = _breakdown_department_failure[
                _breakdown_department_failure["Невиконаних"] > 0
            ]

        if (
            not _breakdown_goal_failure.empty
            and not _breakdown_department_failure.empty
        ):
            _top_goal_failure = _breakdown_goal_failure.iloc[0]
            _top_department_failure = _breakdown_department_failure.iloc[0]
            _breakdown_summary = (
                f"Найбільша концентрація невиконання — стратегічна ціль "
                f"{_top_goal_failure['goal_code']} «{_short_summary_label(_top_goal_failure['strategic_goal'])}» "
                f"та підрозділ «{_short_summary_label(_top_department_failure['ssp_department'])}». "
                f"У відповідних розрізах на них припадає найбільша вага "
                f"невиконаних заходів: {_format_summary_number(_top_goal_failure['Вага_невиконання'])}% "
                f"і {_format_summary_number(_top_department_failure['Вага_невиконання'])}%."
            )
        else:
            _breakdown_summary = (
                "Суттєвої концентрації невиконання за обраний період не виявлено."
            )

        _render_section_summary(
            "Де зосереджено невиконання",
            _breakdown_summary,
            tone="neutral",
        )

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Виконання за стратегічними цілями</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-subtitle">Відсоток виконання по кожній стратегічній цілі</div>', unsafe_allow_html=True)

        goal_sorted = goal_progress.copy()
        goal_sorted["_goal_sort"] = goal_sorted["goal_code"].apply(code_sort_key)
        goal_sorted = goal_sorted.sort_values("_goal_sort")
        def _wrap_goal_label(code, name, width=34):
            words, lines, cur = str(name).split(), [], ""
            for w in words:
                if len(cur) + len(w) + 1 > width and cur:
                    lines.append(cur)
                    cur = w
                else:
                    cur = (cur + " " + w).strip()
                if len(lines) == 2:
                    cur += "…"
                    break
            lines.append(cur)
            return f"{code} " + "<br>".join(lines[:2])

        goal_sorted["label"] = goal_sorted.apply(
            lambda r: _wrap_goal_label(r["goal_code"], r["strategic_goal"]), axis=1
        )

        fig_goals = px.bar(
            goal_sorted,
            x="Виконання",
            y="label",
            orientation="h",
            text=goal_sorted["Виконання"].apply(lambda x: "н/д" if pd.isna(x) else f"{x:.2f}%"),
            hover_data={"Активних_заходів": True, "Покриття_%": True, "Ризикових": True},
            color="Виконання",
            color_continuous_scale=["#DC4A4A", "#FDF3D8", "#118847"],
            range_color=[0, 100],
            labels={
                "Виконання": "Виконання, %",
                "label": "",
                "Активних_заходів": "Активних заходів",
                "Покриття_%": "Покриття, %",
                "Ризикових": "Ризикових заходів",
            },
        )
        fig_goals.update_traces(
            textposition="outside",
            textfont_size=11,
            marker_line_width=0
        )
        fig_goals.update_layout(
            **CHART_LAYOUT,
            height=max(200, len(goal_sorted) * 38 + 40),
            xaxis=dict(range=[0, 115], showgrid=True, gridcolor="#F7F9FC", ticksuffix="%"),
            yaxis=dict(
                title=None,
                showgrid=False,
                categoryorder="array",
                categoryarray=goal_sorted["label"].tolist()[::-1],
            ),
            coloraxis_showscale=False,
            margin=dict(l=10, r=60, t=10, b=10)
        )
        render_plotly_chart(fig_goals, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# Рейтинги й виконання за ССП та заступниками Міністра.
if breakdown_context is not None:
    _activate_dashboard_context(breakdown_context)
    with breakdown_content:
        st.markdown('<div class="section-title">Рейтинг самостійних структурних підрозділів</div>', unsafe_allow_html=True)

        rank_df = dep_progress.sort_values("Виконання", ascending=False).copy()
        rank_df["Місце"] = range(1, len(rank_df) + 1)

        rank_df["Виконання"] = rank_df["Виконання"].astype(float).round(2)
        rank_df["Покриття_%"] = rank_df["Покриття_%"].astype(float).round(2)
        rank_display = rank_df[[
            "Місце", "ssp_department", "Виконання", "Покриття_%",
            "Ризикових", "Критичних", "Активних_заходів"
        ]].rename(columns={
            "ssp_department": "Самостійний структурний підрозділ",
            "Покриття_%": "Покриття, %",
            "Активних_заходів": "Активних заходів"
        })

        render_dashboard_table(
            rank_display,
            hide_index=True,
            formatters={
                "Виконання": lambda value: f"{float(value):.2f}",
                "Покриття, %": lambda value: f"{float(value):.2f}",
            },
            row_class_fn=_dashboard_rank_row_class,
        )
        st.caption(
            "Кольори рядків: зелений — перші три місця; жовтий — середня група; "
            "червоний — нижня група рейтингу."
        )

        st.markdown("<hr class='vis-separator'>", unsafe_allow_html=True)

        # Chart: top 20 departments for readability
        top_n = min(30, len(rank_df))
        top_deps = rank_df.copy()
        top_deps["_ssp_sort"] = top_deps["ssp_department"].apply(
            lambda x: int(re.search(r"\d+", str(x)).group()) if re.search(r"\d+", str(x)) else 9999
        )
        top_deps = top_deps.sort_values("_ssp_sort").head(top_n)

        st.markdown('<div class="section-title">Виконання за самостійними структурними підрозділами</div>', unsafe_allow_html=True)

        fig_dep = px.bar(
            top_deps,
            x="ssp_department",
            y="Виконання",
            text=top_deps["Виконання"].apply(lambda x: f"{x:.2f}%"),
            hover_data={"Активних_заходів": True, "Покриття_%": True, "Ризикових": True, "Критичних": True},
            color="Виконання",
            color_continuous_scale=["#DC4A4A", "#FDF3D8", "#118847"],
            range_color=[0, 100],
            labels={
                "ssp_department": "Самостійний структурний підрозділ",
                "Виконання": "Виконання, %",
                "Активних_заходів": "Активних заходів",
                "Покриття_%": "Покриття, %",
                "Ризикових": "Ризикових заходів",
                "Критичних": "Критичний ризик",
            },
        )
        fig_dep.update_traces(
            textposition="outside",
            textfont_size=10,
            marker_line_width=0
        )
        fig_dep.update_layout(
            **CHART_LAYOUT,
            height=380,
            xaxis=dict(
                title="Самостійний структурний підрозділ",
                tickangle=-35,
                tickfont=dict(size=10),
                showgrid=False,
                categoryorder="array",
                categoryarray=top_deps["ssp_department"].tolist()
            ),
            yaxis=dict(
                range=[0, 115],
                showgrid=True,
                gridcolor="#F7F9FC",
                ticksuffix="%"
            ),
            coloraxis_showscale=False,
            margin=dict(l=10, r=10, t=30, b=100)
        )
        render_plotly_chart(fig_dep, use_container_width=True)

        st.markdown("<hr class='vis-separator'>", unsafe_allow_html=True)

        # Виконання за Заступниками Міністра
        st.markdown('<div class="section-title">Виконання за Заступниками Міністра</div>', unsafe_allow_html=True)

        deputy_data = active.copy()
        if "deputy_minister_by_ssp" not in deputy_data.columns:
            deputy_data = add_deputy_by_ssp_column(deputy_data)

        deputy_progress = (
            deputy_data
            .groupby("deputy_minister_by_ssp")
            .agg(
                Активних_заходів=("code", "count"),
                Виконання=("performance_score", "mean"),
                Покриття=("status", lambda x: (x != "Не подано").sum()),
                Ризикових=("auto_risk", lambda x: x.isin(RISKY_LEVELS).sum())
            )
            .reset_index()
            .rename(columns={"deputy_minister_by_ssp": "Заступник_Міністра"})
        )
        deputy_progress["Виконання"] = deputy_progress["Виконання"].fillna(0).round(2)
        deputy_progress["Покриття_%"] = (
            deputy_progress["Покриття"] / deputy_progress["Активних_заходів"] * 100
        ).fillna(0).round(2)
        deputy_progress["Dep_short"] = deputy_progress["Заступник_Міністра"].str[:30]
        deputy_progress_sorted = deputy_progress.sort_values("Заступник_Міністра", ascending=True)

        fig_dep2 = px.bar(
            deputy_progress_sorted,
            x="Dep_short",
            y="Виконання",
            text=deputy_progress_sorted["Виконання"].apply(lambda x: f"{x:.2f}%"),
            hover_data={"Активних_заходів": True, "Покриття_%": True, "Ризикових": True},
            color="Виконання",
            color_continuous_scale=["#DC4A4A", "#FDF3D8", "#118847"],
            range_color=[0, 100],
            custom_data=["Заступник_Міністра", "Активних_заходів", "Покриття_%", "Ризикових"],
            labels={
                "Dep_short": "Заступник Міністра",
                "Виконання": "Виконання, %",
                "Активних_заходів": "Активних заходів",
                "Покриття_%": "Покриття, %",
                "Ризикових": "Ризикових заходів",
            },
        )
        fig_dep2.update_traces(
            textposition="outside",
            textfont_size=10,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Виконання: %{y:.2f}%<br>"
                "Активних заходів: %{customdata[1]}<br>"
                "Покриття: %{customdata[2]:.2f}%<br>"
                "Ризикових: %{customdata[3]}"
                "<extra></extra>"
            ),
            marker_line_width=0
        )
        fig_dep2.update_layout(
            **CHART_LAYOUT,
            height=360,
            xaxis=dict(
                title="Заступник Міністра",
                tickangle=-30,
                tickfont=dict(size=9),
                showgrid=False,
                categoryorder="array",
                categoryarray=deputy_progress_sorted["Dep_short"].tolist()
            ),
            yaxis=dict(
                range=[0, 115],
                showgrid=True,
                gridcolor="#F7F9FC",
                ticksuffix="%"
            ),
            coloraxis_showscale=False,
            margin=dict(l=10, r=10, t=30, b=120)
        )
        render_plotly_chart(fig_dep2, use_container_width=True)


# ============================================================
# РИЗИКИ: КРУГОВА І МАТРИЦЯ — МОМЕНТНИЙ ЗРІЗ; СТРУКТУРА — ЗА РОЗРІЗОМ
# ============================================================

# Кругова автоматична оцінка ризиків.
if snapshot_context is not None:
    _activate_dashboard_context(snapshot_context)
    with snapshot_content:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Автоматична оцінка ризиків</div>', unsafe_allow_html=True)
        fig_risk_pie = px.pie(
            risk_counts,
            names="auto_risk",
            values="Кількість",
            hole=0.52,
            color="auto_risk",
            color_discrete_map=RISK_COLORS,
            labels={
                "auto_risk": "Рівень ризику",
                "Кількість": "Кількість заходів",
            },
        )
        fig_risk_pie.update_traces(
            textfont_size=12,
            marker=dict(line=dict(color="#ffffff", width=2))
        )
        fig_risk_pie.update_layout(
            **CHART_LAYOUT,
            height=320,
            showlegend=True,
        )
        apply_safe_plotly_layout(fig_risk_pie, has_legend=True)
        render_plotly_chart(fig_risk_pie, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# Структура ризиків за ССП.
if breakdown_context is not None:
    _activate_dashboard_context(breakdown_context)
    with breakdown_content:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title" style="margin-top:0;">Структура ризиків за самостійними структурними підрозділами</div>', unsafe_allow_html=True)

        stacked = dep_active.groupby(["ssp_department", "auto_risk"]).size().reset_index(name="Кількість")
        # Filter out "Не оцінюється" for cleaner view
        stacked_vis = stacked[stacked["auto_risk"] != "Не оцінюється"].copy()
        stacked_vis["_ssp_sort"] = stacked_vis["ssp_department"].apply(ssp_sort_value)
        stacked_vis = stacked_vis.sort_values("_ssp_sort")

        fig_risk_bar = px.bar(
            stacked_vis,
            x="ssp_department",
            y="Кількість",
            color="auto_risk",
            color_discrete_map=RISK_COLORS,
            barmode="stack",
            labels={
                "ssp_department": "Самостійний структурний підрозділ",
                "auto_risk": "Ризик",
                "Кількість": "Кількість заходів",
            }
        )
        fig_risk_bar.update_layout(
            **CHART_LAYOUT,
            height=310,
            xaxis=dict(
                tickangle=-35,
                tickfont=dict(size=9),
                showgrid=False,
                categoryorder="array",
                categoryarray=stacked_vis["ssp_department"].drop_duplicates().tolist()
            ),
            yaxis=dict(showgrid=True, gridcolor="#F7F9FC"),
        )
        apply_safe_plotly_layout(fig_risk_bar, has_legend=True)
        render_plotly_chart(fig_risk_bar, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# Матриця виконання × темп.
if snapshot_context is not None:
    _activate_dashboard_context(snapshot_context)
    with snapshot_content:
        # ── SCATTER: Виконання × темп по ССП ─────────────────────
        st.markdown("<hr class='vis-separator'>", unsafe_allow_html=True)
        st.markdown(
            '<div class="section-title" style="margin-top:0;">'
            'Матриця виконання × темп (по ССП)</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="section-subtitle">'
            'X — виконання підрозділу; Y — середній річний темп як частка річного плану '
            '(100% відповідає плановому темпу). Розмір бульбашки — кількість заходів.'
            '</div>',
            unsafe_allow_html=True,
        )

        scatter_df = dep_progress[
            (dep_progress["Активних_заходів"] >= 1)
            & dep_progress["Середній_темп"].notna()
        ].copy()
        scatter_df["dep_short"] = scatter_df["ssp_department"].astype(str).apply(
            lambda value: value if len(value) <= 24 else value[:23] + "…"
        )

        if not scatter_df.empty:
            performance_threshold = float(expected_period_completion)
            tempo_threshold = 100.0
            x_axis_min, x_axis_max = 0.0, 105.0

            tempo_min = min(
                float(scatter_df["Середній_темп"].min()),
                tempo_threshold,
            )
            tempo_max = max(
                float(scatter_df["Середній_темп"].max()),
                tempo_threshold,
            )
            tempo_span = max(tempo_max - tempo_min, 50.0)
            tempo_padding = max(10.0, tempo_span * 0.12)
            y_axis_min = min(0.0, tempo_min - tempo_padding)
            y_axis_max = max(200.0, tempo_max + tempo_padding)

            # Невелике детерміноване зміщення застосовується лише для візуального
            # розведення однакових/майже однакових координат. У hover залишаються
            # точні розрахункові значення виконання та темпу.
            scatter_df["plot_x"] = scatter_df["Виконання"].astype(float)
            scatter_df["plot_y"] = scatter_df["Середній_темп"].astype(float)
            scatter_df["_x_cluster"] = (scatter_df["Виконання"] / 2).round()
            scatter_df["_y_cluster"] = (scatter_df["Середній_темп"] / 5).round()
            jitter_offsets = [
                (0.0, 0.0),
                (-1.0, 1.0),
                (1.0, -1.0),
                (-1.0, -1.0),
                (1.0, 1.0),
                (0.0, 2.0),
                (0.0, -2.0),
                (-2.0, 0.0),
                (2.0, 0.0),
            ]
            y_jitter_unit = max((y_axis_max - y_axis_min) * 0.012, 2.0)
            for group_indices in scatter_df.groupby(
                ["_x_cluster", "_y_cluster"],
                dropna=False,
            ).groups.values():
                group_indices = list(group_indices)
                if len(group_indices) <= 1:
                    continue
                for position, row_index in enumerate(group_indices):
                    x_offset, y_offset = jitter_offsets[position % len(jitter_offsets)]
                    multiplier = 1 + position // len(jitter_offsets)
                    scatter_df.at[row_index, "plot_x"] = min(
                        max(
                            float(scatter_df.at[row_index, "Виконання"])
                            + x_offset * multiplier,
                            x_axis_min,
                        ),
                        100.0,
                    )
                    scatter_df.at[row_index, "plot_y"] = (
                        float(scatter_df.at[row_index, "Середній_темп"])
                        + y_offset * y_jitter_unit * multiplier
                    )

            point_colors = []
            for _, row in scatter_df.iterrows():
                high_completion = float(row["Виконання"]) >= performance_threshold
                high_tempo = float(row["Середній_темп"]) >= tempo_threshold
                if high_completion and high_tempo:
                    point_colors.append("#118847")
                elif high_completion:
                    point_colors.append("#F4B400")
                elif high_tempo:
                    point_colors.append("#00A8A8")
                else:
                    point_colors.append("#DC4A4A")

            fig_scatter = go.Figure()

            # Чотири змістовні квадранти.
            for x0, x1, y0, y1, fill in [
                (
                    x_axis_min,
                    performance_threshold,
                    tempo_threshold,
                    y_axis_max,
                    "rgba(0,168,168,0.065)",
                ),
                (
                    performance_threshold,
                    x_axis_max,
                    tempo_threshold,
                    y_axis_max,
                    "rgba(17,136,71,0.065)",
                ),
                (
                    performance_threshold,
                    x_axis_max,
                    y_axis_min,
                    tempo_threshold,
                    "rgba(244,180,0,0.065)",
                ),
                (
                    x_axis_min,
                    performance_threshold,
                    y_axis_min,
                    tempo_threshold,
                    "rgba(220,74,74,0.075)",
                ),
            ]:
                fig_scatter.add_shape(
                    type="rect",
                    x0=x0,
                    x1=x1,
                    y0=y0,
                    y1=y1,
                    fillcolor=fill,
                    line_width=0,
                    layer="below",
                )

            fig_scatter.add_shape(
                type="line",
                x0=performance_threshold,
                x1=performance_threshold,
                y0=y_axis_min,
                y1=y_axis_max,
                line=dict(color="#AAB6C8", dash="dot", width=1.2),
            )
            fig_scatter.add_shape(
                type="line",
                x0=x_axis_min,
                x1=x_axis_max,
                y0=tempo_threshold,
                y1=tempo_threshold,
                line=dict(color="#AAB6C8", dash="dot", width=1.2),
            )

            text_positions = [
                "top center",
                "bottom center",
                "middle right",
                "middle left",
            ]
            fig_scatter.add_trace(go.Scatter(
                x=scatter_df["plot_x"],
                y=scatter_df["plot_y"],
                mode="markers+text",
                marker=dict(
                    size=[
                        max(14, min(16 + float(count) ** 0.5 * 5, 50))
                        for count in scatter_df["Активних_заходів"]
                    ],
                    color=point_colors,
                    opacity=0.78,
                    line=dict(color="white", width=1.5),
                ),
                text=scatter_df["dep_short"],
                textposition=[
                    text_positions[index % len(text_positions)]
                    for index in range(len(scatter_df))
                ],
                textfont=dict(size=9, color="#61708A"),
                customdata=[
                    [
                        row["ssp_department"],
                        float(row["Виконання"]),
                        float(row["Середній_темп"]),
                        int(row["Активних_заходів"]),
                    ]
                    for _, row in scatter_df.iterrows()
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Виконання: %{customdata[1]:.2f}%<br>"
                    "Середній річний темп: %{customdata[2]:+.2f}% плану<br>"
                    "Активних заходів: %{customdata[3]}<extra></extra>"
                ),
                cliponaxis=False,
                showlegend=False,
            ))

            left_center = performance_threshold / 2
            right_center = performance_threshold + (
                x_axis_max - performance_threshold
            ) / 2
            lower_center = y_axis_min + (tempo_threshold - y_axis_min) / 2
            upper_center = tempo_threshold + (y_axis_max - tempo_threshold) / 2
            quadrant_labels = [
                (
                    "Наздоганяють",
                    left_center,
                    upper_center,
                    "#007C82",
                ),
                (
                    "Лідери, що<br>прискорюються",
                    right_center,
                    upper_center,
                    "#118847",
                ),
                (
                    "Досягли,<br>темп сповільнився",
                    right_center,
                    lower_center,
                    "#B77900",
                ),
                (
                    "Критична зона:<br>відстають і не прискорюються",
                    left_center,
                    lower_center,
                    "#B83232",
                ),
            ]
            for label, x_pos, y_pos, color in quadrant_labels:
                fig_scatter.add_annotation(
                    x=x_pos,
                    y=y_pos,
                    text=f"<b>{label}</b>",
                    showarrow=False,
                    font=dict(size=10, color=color),
                    xanchor="center",
                    yanchor="middle",
                    align="center",
                    bgcolor="rgba(255,255,255,0.78)",
                    borderpad=4,
                )

            fig_scatter.add_annotation(
                x=performance_threshold,
                y=y_axis_max,
                text=f"Очікуване виконання: {performance_threshold:.0f}%",
                showarrow=False,
                xanchor="left",
                yanchor="top",
                font=dict(size=9, color="#61708A"),
                bgcolor="rgba(255,255,255,0.82)",
                borderpad=3,
            )
            fig_scatter.add_annotation(
                x=x_axis_max,
                y=tempo_threshold,
                text="Плановий річний темп: 100%",
                showarrow=False,
                xanchor="right",
                yanchor="bottom",
                font=dict(size=9, color="#61708A"),
                bgcolor="rgba(255,255,255,0.82)",
                borderpad=3,
            )

            fig_scatter.update_layout(
                **CHART_LAYOUT,
                height=560,
                showlegend=False,
                hovermode="closest",
                xaxis=dict(
                    title="Виконання підрозділу, %",
                    range=[x_axis_min, x_axis_max],
                    showgrid=True,
                    gridcolor="#F7F9FC",
                    ticksuffix="%",
                    zeroline=False,
                ),
                yaxis=dict(
                    title="Середній річний темп, % плану",
                    range=[y_axis_min, y_axis_max],
                    showgrid=True,
                    gridcolor="#F7F9FC",
                    ticksuffix="%",
                    zeroline=False,
                ),
                margin=dict(l=75, r=35, t=30, b=70),
            )
            render_plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info(
                "Немає числових даних про темп виконання для побудови матриці "
                "за обраними параметрами."
            )


# ============================================================
# СЕКЦІЯ: ДИНАМІКА
# ============================================================

# Лінія динаміки та водоспад відхилень.
if dynamics_context is not None:
    _activate_dashboard_context(dynamics_context)
    with dynamics_content:
        trend_df, selected_period_pairs = _build_dynamics_trend_df(
            active_period_rows,
            years_for_calc,
            quarters_for_calc,
        )
        _render_section_summary(
            "Куди рухаємось",
            _dynamics_summary_text(trend_df, selected_period_pairs),
            tone="neutral",
        )

        st.markdown('<div class="section-title">Динаміка виконання</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle">{dynamics_label}</div>', unsafe_allow_html=True)

        fig_trend = px.line(
            trend_df,
            x="Період",
            y=["Виконання", "Покриття", "Відхилення за звітний період"],
            markers=True,
            color_discrete_map={
                "Виконання": "#005BBB",
                "Покриття": "#00A8A8",
                "Відхилення за звітний період": "#DC4A4A"
            },
            labels={
                "variable": "Показник",
                "value": "Значення, %",
                "Період": "Період",
            },
        )
        fig_trend.update_traces(line_width=2.5, marker_size=7)
        fig_trend.update_layout(
            **CHART_LAYOUT,
            height=340,
            xaxis=dict(showgrid=False, tickangle=-20),
            yaxis=dict(showgrid=True, gridcolor="#F7F9FC", ticksuffix="%"),
        )
        fig_trend.update_layout(legend_title_text="Показник")
        apply_safe_plotly_layout(fig_trend, has_legend=True)
        render_plotly_chart(fig_trend, use_container_width=True)
        if any(
            int(year) == 2026 and quarter_to_number(quarter) in (1, 2)
            for year, quarter in selected_period_pairs
        ):
            st.caption(
                "За I та II квартали 2026 року моніторинг не проводився, "
                "тому значення за ці періоди не враховуються."
            )

        # ── WATERFALL: внесок кожної стратегічної цілі у відхилення ──
        st.markdown("<hr class='vis-separator'>", unsafe_allow_html=True)
        st.markdown('<div class="section-title" style="margin-top:0;">Водоспад відхилень за стратегічними цілями</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-subtitle">{snapshot_label} · Внесок кожної стратегічної цілі у загальне відхилення від планового рівня виконання</div>',
            unsafe_allow_html=True,
        )

        _wf_has_data = (not goal_progress.empty) and bool(
            goal_progress["Виконання"].notna().any()
        )
        if _wf_has_data:
            wf_df = goal_progress.dropna(subset=["Виконання"]).copy()
            wf_df["Відхилення"] = (
                wf_df["Виконання"] - expected_period_completion
            ).round(2)
            wf_df["label"] = wf_df["goal_code"].astype(str) + " " + wf_df["strategic_goal"].astype(str).str[:30]
            wf_df = wf_df.sort_values("Відхилення", ascending=True)

            colors_wf = ["#DC4A4A" if v < 0 else "#118847" for v in wf_df["Відхилення"]]

            fig_wf = go.Figure(go.Waterfall(
                name="Відхилення",
                orientation="h",
                measure=["relative"] * len(wf_df) + ["total"],
                y=list(wf_df["label"]) + ["Загальне відхилення"],
                x=list(wf_df["Відхилення"]) + [deviation_current],
                text=[f"{v:+.1f}%" for v in wf_df["Відхилення"]] + [f"{deviation_current:+.1f}%"],
                textposition="outside",
                connector=dict(line=dict(color="#DCE4F0", width=1)),
                increasing=dict(marker=dict(color="#118847")),
                decreasing=dict(marker=dict(color="#DC4A4A")),
                totals=dict(marker=dict(color="#005BBB")),
            ))
            fig_wf.update_layout(
                **CHART_LAYOUT,
                height=max(260, len(wf_df) * 36 + 80),
                xaxis=dict(title="Відхилення, в.п.", showgrid=True, gridcolor="#F7F9FC", ticksuffix="%",
                           range=[-115, 15],
                           zeroline=True, zerolinecolor="#8A96A8", zerolinewidth=1.5),
                yaxis=dict(showgrid=False),
                margin=dict(l=10, r=80, t=10, b=30),
                showlegend=False
            )
            render_plotly_chart(fig_wf, use_container_width=True)
        else:
            st.info("Погоджених даних за обраний період ще немає — водоспад відхилень "
                    "з'явиться після перших погоджених подань.")

# Heatmap ССП × квартал.
if dynamics_context is not None:
    _activate_dashboard_context(dynamics_context)
    with dynamics_content:
        st.markdown('<div class="section-title">Heatmap: самостійний структурний підрозділ × квартал</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle">{dynamics_label}</div>', unsafe_allow_html=True)

        heat_rows = []

        for y in years_for_calc:
            for q in quarters_for_calc:
                temp_raw = build_period_data(strat_df, requests_df, [y], [q])
                temp = apply_dashboard_filters(
                    temp_raw,
                    selected_department_indices,
                    selected_goals,
                    selected_tasks,
                    selected_measures,
                    selected_product_types,
                    selected_deputies,
                    selected_statuses,
                    selected_sources,
                    selected_financing,
                    selected_kpkvk,
                )

                if temp.empty:
                    continue

                temp_dep = explode_departments(temp)
                dep_heat = temp_dep.groupby("ssp_department").agg(
                    Виконання=("performance_score", "mean")
                ).reset_index()

                for _, row in dep_heat.iterrows():
                    heat_rows.append({
                        "Самостійний структурний підрозділ": row["ssp_department"],
                        "Період": f"{y} {q}",
                        "Виконання": round(row["Виконання"], 1) if pd.notna(row["Виконання"]) else 0
                    })

        heat_df = pd.DataFrame(heat_rows)

        if not heat_df.empty:
            pivot = heat_df.pivot_table(
                index="Самостійний структурний підрозділ",
                columns="Період",
                values="Виконання",
                aggfunc="mean"
            )
            # «Немає подань» лишаємо порожнім (сіра клітинка), а не «0 = червоне»
            pivot = pivot.mask(pivot <= 0)
            pivot = pivot.loc[sorted(pivot.index, key=ssp_sort_value)]
            pivot = pivot.dropna(how="all")

            if pivot.empty:
                render_no_chart_data()
            else:
                fig_heat = px.imshow(
                    pivot,
                    color_continuous_scale=["#FBE5E5", "#FDF3D8", "#E4F5EC"],
                    zmin=0, zmax=100,
                    aspect="auto",
                    text_auto=".0f",
                    labels=dict(x="Період", y="Підрозділ", color="Виконання, %")
                )
                fig_heat.update_layout(
                    **CHART_LAYOUT,
                    height=max(300, len(pivot) * 22 + 80),
                    coloraxis_colorbar=dict(title="Викон., %", ticksuffix="%"),
                    xaxis=dict(side="top", tickfont=dict(size=10)),
                    yaxis=dict(tickfont=dict(size=9)),
                    margin=dict(l=10, r=60, t=60, b=10)
                )
                render_plotly_chart(fig_heat, use_container_width=True)
        else:
            render_no_chart_data()

# Таймлайн дедлайнів.
if dynamics_context is not None:
    _activate_dashboard_context(dynamics_context)
    with dynamics_content:
        st.markdown('<div class="section-title">Таймлайн дедлайнів</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-subtitle">{snapshot_label} · Кількість заходів із дедлайном у кожному кварталі · розбивка за статусом виконання</div>',
            unsafe_allow_html=True,
        )

        timeline_data = active.copy()
        timeline_data["end_num"] = timeline_data["end_period"].apply(parse_period)
        timeline_data = timeline_data[timeline_data["end_num"].notna()].copy()

        if not timeline_data.empty:
            def end_num_to_label(n):
                y = int(n) // 10
                q_map = {1: "I", 2: "II", 3: "III", 4: "IV"}
                q = q_map.get(int(n) % 10, "?")
                return f"{y} {q}"

            timeline_data["deadline_label"] = timeline_data["end_num"].apply(end_num_to_label)

            def _tl_status(row):
                status = clean(row.get("status_display", ""))
                return status if status in core_statuses.MODEL_STATUSES else core_statuses.ST_NOTDONE

            timeline_data["tl_status"] = timeline_data.apply(_tl_status, axis=1)

            tl_grouped = (
                timeline_data
                .groupby(["deadline_label", "end_num", "tl_status"])
                .size()
                .reset_index(name="Кількість")
                .sort_values("end_num")
            )

            tl_color_map = {
                "Виконано": "#118847",
                "Частково виконано": "#FF7A45",
                "Не виконано": "#DC4A4A",
                "Не настав час": "#8A96A8",
                "Втратило актуальність": "#8A96A8",
            }

            fig_tl2 = px.bar(
                tl_grouped,
                x="deadline_label",
                y="Кількість",
                color="tl_status",
                color_discrete_map=tl_color_map,
                barmode="stack",
                labels={
                    "deadline_label": "Квартал дедлайну",
                    "tl_status": "Статус",
                    "Кількість": "Кількість заходів",
                },
                text_auto=True,
            )
            fig_tl2.update_traces(textfont_size=10, textposition="inside")
            fig_tl2.update_layout(
                legend_title_text="Статус виконання",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            )
            fig_tl2.update_layout(
                **CHART_LAYOUT,
                height=360,
                xaxis=dict(showgrid=False, tickangle=-20),
                yaxis=dict(showgrid=True, gridcolor="#F7F9FC"),
            )
            apply_safe_plotly_layout(fig_tl2, has_legend=True)
            render_plotly_chart(fig_tl2, use_container_width=True)
        else:
            st.info("Дані про терміни виконання заходів відсутні.")


# ============================================================
# СЕКЦІЯ: ЗА РОЗРІЗОМ — ФІНАНСИ ТА ТАБЛИЦІ
# ============================================================

# Фінансовий блок.
if breakdown_context is not None:
    _activate_dashboard_context(breakdown_context)
    with breakdown_content:
        # ── Підготовка фінансових даних ───────────────────────────────────────────
        fin_measures = active.copy()

        # KPI лічильники
        fin_total = len(fin_measures)
        fin_db_count = int(fin_measures["has_state_budget"].sum()) if "has_state_budget" in fin_measures.columns else 0
        fin_mtd_count = int(fin_measures[fin_measures["financing_types"].apply(
            lambda t: isinstance(t, list) and "МТД / кошти партнерів" in t)].shape[0]) \
            if "financing_types" in fin_measures.columns else 0
        fin_other_count = int(fin_measures[fin_measures["financing_types"].apply(
            lambda t: isinstance(t, list) and "Небюджетні / інші" in t)].shape[0]) \
            if "financing_types" in fin_measures.columns else 0
        fin_no_count = int(fin_measures[fin_measures["financing_types"].apply(
            lambda t: isinstance(t, list) and t == ["Без фінансування"])].shape[0]) \
            if "financing_types" in fin_measures.columns else 0
        fin_budget_sum = fin_measures["budget_2026"].sum() if "budget_2026" in fin_measures.columns else 0
        fin_budget_count = int(fin_measures["budget_2026"].notna().sum()) if "budget_2026" in fin_measures.columns else 0

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">💰 Фінансування заходів</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-subtitle">{snapshot_label} · Структура джерел фінансування активних заходів за обраними фільтрами</div>',
            unsafe_allow_html=True
        )

        # ── KPI картки фінансування ───────────────────────────────────────────────
        render_kpi_grid([
            {"title": "Заходів з Держбюджетом", "count": fin_db_count,
             "percent": pct_value(fin_db_count, fin_total), "color": "kpi-blue"},
            {"title": "Заходів з МТД / партнерами", "count": fin_mtd_count,
             "percent": pct_value(fin_mtd_count, fin_total), "color": "kpi-green"},
            {"title": "Небюджетні / інші джерела", "count": fin_other_count,
             "percent": pct_value(fin_other_count, fin_total), "color": "kpi-yellow"},
            {"title": "Без фінансування", "count": fin_no_count,
             "percent": pct_value(fin_no_count, fin_total), "color": "kpi-gray"},
            {"title": f"Бюджет ДБ 2026 (млрд грн)*",
             "count": f"{fin_budget_sum:.2f}" if fin_budget_sum else "—",
             "percent": f"* {fin_budget_count} з {fin_total} заходів мають суму", "color": "kpi-blue"},
        ])

        st.markdown('<div style="margin-top:18px;"></div>', unsafe_allow_html=True)

        # ── Кільцева + Стовпчаста в одному рядку ─────────────────────────────────
        fin_col1, fin_col2 = st.columns([1, 1.5])

        with fin_col1:
            # Кільцева: структура джерел (кількість заходів)
            fin_donut_data = pd.DataFrame({
                "Тип": ["Державний бюджет", "МТД / кошти партнерів", "Небюджетні / інші", "Без фінансування"],
                "Кількість": [fin_db_count, fin_mtd_count, fin_other_count, fin_no_count]
            })
            fin_donut_data = fin_donut_data[fin_donut_data["Кількість"] > 0]

            if not fin_donut_data.empty:
                FIN_COLORS = {
                    "Державний бюджет": "#005BBB",
                    "МТД / кошти партнерів": "#00A8A8",
                    "Небюджетні / інші": "#FF7A45",
                    "Без фінансування": "#8A96A8",
                }
                fig_donut = px.pie(
                    fin_donut_data,
                    names="Тип",
                    values="Кількість",
                    hole=0.52,
                    color="Тип",
                    color_discrete_map=FIN_COLORS,
                    labels={
                        "Тип": "Джерело фінансування",
                        "Кількість": "Кількість заходів",
                    },
                )
                fig_donut.update_traces(
                    textfont_size=11,
                    textposition="outside",
                    texttemplate="%{label}: %{percent:.1%}",
                    marker=dict(line=dict(color="#ffffff", width=2))
                )
                fig_donut.update_layout(uniformtext_minsize=9, uniformtext_mode="hide")
                fig_donut.update_layout(
                    **CHART_LAYOUT,
                    title=dict(text="Структура джерел фінансування", font=dict(size=14, color="#032A63"), x=0),
                    height=340,
                    showlegend=True,
                )
                apply_safe_plotly_layout(fig_donut, has_legend=True)
                render_plotly_chart(fig_donut, use_container_width=True)
            else:
                st.info("Даних про фінансування за обраними фільтрами немає.")

        with fin_col2:
            # Стовпчаста: розподіл бюджету ДБ за стратегічними цілями
            if "goal_code" in fin_measures.columns and "budget_2026" in fin_measures.columns:
                goal_budget = (
                    fin_measures[fin_measures["budget_2026"].fillna(0) > 0]
                    .groupby("goal_code")
                    .agg(
                        Бюджет_2026=("budget_2026", "sum"),
                        Заходів=("code", "count")
                    )
                    .reset_index()
                )
                if not goal_budget.empty:
                    goal_budget["_sort"] = goal_budget["goal_code"].apply(code_sort_key)
                    goal_budget = goal_budget.sort_values("_sort")
                    goal_budget["label"] = goal_budget["goal_code"].astype(str)

                    fig_budget_bar = px.bar(
                        goal_budget,
                        x="label",
                        y="Бюджет_2026",
                        text=goal_budget["Бюджет_2026"].apply(lambda v: f"{v:.2f}"),
                        hover_data={"Заходів": True},
                        color="Бюджет_2026",
                        color_continuous_scale=["#BFD3F2", "#005BBB"],
                        labels={"label": "Стратегічна ціль", "Бюджет_2026": "млрд грн"},
                    )
                    fig_budget_bar.update_traces(
                        textposition="outside",
                        textfont_size=10,
                        marker_line_width=0
                    )
                    fig_budget_bar.update_layout(
                        **CHART_LAYOUT,
                        title=dict(text="Бюджет ДБ 2026 за стратегічними цілями (млрд грн)*",
                                   font=dict(size=14, color="#032A63"), x=0),
                        height=300,
                        xaxis=dict(showgrid=False, tickangle=0),
                        yaxis=dict(showgrid=True, gridcolor="#F7F9FC", title="млрд грн"),
                        coloraxis_showscale=False,
                        margin=dict(l=10, r=10, t=40, b=40)
                    )
                    render_plotly_chart(fig_budget_bar, use_container_width=True)
                    st.caption("* Лише заходи з наявними числовими даними про бюджет")
                else:
                    st.info("Числових даних про бюджет ДБ 2026 за обраними фільтрами немає.")
            else:
                st.info("Недостатньо даних для побудови діаграми бюджету.")

        st.markdown("<hr class='vis-separator'>", unsafe_allow_html=True)

        # ── Heatmap: виконання × тип фінансування ────────────────────────────────
        if "financing_types" in fin_measures.columns and "status_display" in fin_measures.columns:
            heat_fin_rows = []
            for _, row in fin_measures.iterrows():
                fts = row.get("financing_types", [])
                if not isinstance(fts, list):
                    fts = ["Без фінансування"]
                for ft in fts:
                    heat_fin_rows.append({
                        "Статус виконання": row["status_display"],
                        "Тип фінансування": ft,
                    })
            if heat_fin_rows:
                heat_fin_df = pd.DataFrame(heat_fin_rows)
                heat_fin_pivot = heat_fin_df.groupby(
                    ["Статус виконання", "Тип фінансування"]
                ).size().reset_index(name="Кількість")

                status_order = ["Виконано", "Частково виконано", "Не виконано",
                                "Не настав час", "Втратило актуальність"]
                fin_order = ["Державний бюджет", "МТД / кошти партнерів", "Небюджетні / інші", "Без фінансування"]

                pivot_tbl = heat_fin_pivot.pivot_table(
                    index="Статус виконання", columns="Тип фінансування",
                    values="Кількість", aggfunc="sum", fill_value=0
                )
                # Впорядкувати рядки/стовпці
                pivot_tbl = pivot_tbl.reindex(
                    index=[s for s in status_order if s in pivot_tbl.index],
                    columns=[f for f in fin_order if f in pivot_tbl.columns]
                ).fillna(0).astype(int)

                if not pivot_tbl.empty:
                    fig_heatmap_fin = px.imshow(
                        pivot_tbl,
                        text_auto=True,
                        color_continuous_scale=["#EAF1FF", "#032A63"],
                        aspect="auto",
                        labels=dict(x="Тип фінансування", y="Статус виконання", color="Заходів")
                    )
                    fig_heatmap_fin.update_layout(
                        **CHART_LAYOUT,
                        title=dict(text="Виконання × тип фінансування (кількість заходів)",
                                   font=dict(size=14, color="#032A63"), x=0),
                        height=max(220, len(pivot_tbl) * 44 + 80),
                        coloraxis_showscale=False,
                        xaxis=dict(side="bottom", tickfont=dict(size=11)),
                        yaxis=dict(tickfont=dict(size=11)),
                        margin=dict(l=10, r=10, t=44, b=10)
                    )
                    render_plotly_chart(fig_heatmap_fin, use_container_width=True)
                else:
                    render_no_chart_data()
            else:
                render_no_chart_data()
        else:
            render_no_chart_data()

        st.markdown("<hr class='vis-separator'>", unsafe_allow_html=True)

        # ── Таблиця топ-КПКВК ────────────────────────────────────────────────────
        if "budget_kpkvk" in fin_measures.columns:
            kpkvk_table = (
                fin_measures[fin_measures["budget_kpkvk"] != ""]
                .groupby("budget_kpkvk")
                .agg(
                    Заходів=("code", "count"),
                    Бюджет_2026=("budget_2026", "sum"),
                    Бюджет_2027=("budget_2027", "sum"),
                    Бюджет_2028=("budget_2028", "sum"),
                )
                .reset_index()
                .rename(columns={"budget_kpkvk": "КПКВК"})
            )
            kpkvk_table = kpkvk_table.sort_values("Заходів", ascending=False).reset_index(drop=True)
            kpkvk_table.index = kpkvk_table.index + 1

            def _fmt_budget(v):
                return f"{v:.3f}" if pd.notna(v) and v > 0 else "—"

            kpkvk_display = kpkvk_table.copy()
            kpkvk_display["Бюджет 2026 (млрд грн)"] = kpkvk_display["Бюджет_2026"].apply(_fmt_budget)
            kpkvk_display["Бюджет 2027 (млрд грн)"] = kpkvk_display["Бюджет_2027"].apply(_fmt_budget)
            kpkvk_display["Бюджет 2028 (млрд грн)"] = kpkvk_display["Бюджет_2028"].apply(_fmt_budget)

            st.markdown('<div class="section-title" style="margin-top:0;">Топ КПКВК за кількістю заходів</div>',
                        unsafe_allow_html=True)
            render_dashboard_table(
                kpkvk_display[[
                    "КПКВК", "Заходів", "Бюджет 2026 (млрд грн)",
                    "Бюджет 2027 (млрд грн)", "Бюджет 2028 (млрд грн)",
                ]],
                hide_index=False,
            )
            st.caption(
                "Суми — лише заходи з наявними числовими даними; «—» означає "
                "відсутність числових даних."
            )

        st.markdown("</div>", unsafe_allow_html=True)

# Таблиця фінансових даних.
if breakdown_context is not None:
    _activate_dashboard_context(breakdown_context)
    with breakdown_content:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Таблиця заходів: фінансові дані</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-subtitle">Заходи з відомостями про джерела фінансування за обраним фільтром</div>',
            unsafe_allow_html=True
        )

        fin_table_cols = {
            "code": "Код",
            "name": "Захід",
            "department": "Головний ССП",
            "status_display": "Статус виконання",
            "budget_kpkvk": "КПКВК",
            "budget_2026": "ДБ 2026 (млрд грн)",
            "budget_2027": "ДБ 2027 (млрд грн)",
            "budget_2028": "ДБ 2028 (млрд грн)",
            "other_source": "Інше джерело",
            "other_2026": "Інше 2026",
            "other_2027": "Інше 2027",
            "other_2028": "Інше 2028",
        }
        available_cols = [c for c in fin_table_cols if c in active.columns]
        fin_full = active[available_cols].rename(columns=fin_table_cols).copy()

        # Форматування бюджетних стовпців
        for col_label in ["ДБ 2026 (млрд грн)", "ДБ 2027 (млрд грн)", "ДБ 2028 (млрд грн)"]:
            if col_label in fin_full.columns:
                fin_full[col_label] = fin_full[col_label].apply(
                    lambda v: f"{v:.3f}" if pd.notna(v) else "—"
                )

        render_dashboard_table(
            fin_full,
            hide_index=True,
        )
        st.caption("Числові суми бюджету наявні лише для частини заходів. «—» — дані не вказані.")
        st.markdown("</div>", unsafe_allow_html=True)

# Проблемні заходи.
if breakdown_context is not None:
    _activate_dashboard_context(breakdown_context)
    with breakdown_content:
        with st.expander("Проблемні заходи", expanded=False):
            risk_table = active[
                (
                    active["auto_risk"].isin(RISKY_LEVELS) |
                    (active["status"] == "Не подано") |
                    (active["performance_score"].fillna(0) < 75)
                )
                & (active["included_in_risk_assessment"] == True)
            ].copy()

            if risk_table.empty:
                st.success("Ризикових заходів за обраний період не виявлено.")
            else:
                risk_table = risk_table.rename(columns={
                    "code": "Код",
                    "name": "Захід",
                    "indicator": "Індикатор",
                    "department": "Головний ССП",
                    "status_display": "Статус виконання",
                    "selected_target": "Планове значення",
                    "numeric_value": "Фактичне значення",
                    "auto_risk": "Рівень ризику",
                    "risk_score": "Risk score",
                    "traffic_light": "Traffic light",
                    "risk_reason": "Причина ризику",
                    "progress_text": "Опис прогресу",
                    "period_label": "Період"
                })

                render_dashboard_table(
                    risk_table[[
                        "Період", "Код", "Захід", "Індикатор", "Головний ССП",
                        "Статус виконання", "Планове значення", "Фактичне значення",
                        "Traffic light", "Рівень ризику", "Risk score",
                        "Причина ризику", "Опис прогресу",
                    ]],
                    hide_index=True,
                )

# Повна таблиця активних заходів.
if breakdown_context is not None:
    _activate_dashboard_context(breakdown_context)
    with breakdown_content:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Повна таблиця активних заходів</div>', unsafe_allow_html=True)

        full = active.rename(columns={
            "period_label": "Період",
            "code": "Код",
            "name": "Захід",
            "indicator": "Індикатор",
            "unit": "Одиниця виміру",
            "department": "Головний ССП",
            "product_type": "Тип продукту",
            "source_national": "Джерело даних",
            "start_period": "Початок",
            "end_period": "Кінець",
            "selected_target": "Планове значення",
            "numeric_value": "Фактичне значення",
            "status_display": "Статус виконання",
            "performance_score": "Оцінка виконання, %",
            "auto_risk": "Ризик",
            "risk_score": "Risk score",
            "traffic_light": "Traffic light",
            "risk_reason": "Причина ризику"
        })

        render_dashboard_table(
            full[[
                "Період", "Код", "Захід", "Індикатор", "Одиниця виміру", "Тип продукту",
                "Головний ССП", "Джерело даних", "Початок", "Кінець",
                "Планове значення", "Фактичне значення", "Статус виконання",
                "Оцінка виконання, %", "Traffic light", "Ризик", "Risk score", "Причина ризику"
            ]],
            hide_index=True,
        )

        st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# МЕТОДОЛОГІЯ ТА ТЕСТОВИЙ АВТОМАТИЧНИЙ ВИСНОВОК
# ============================================================

with st.expander("Методологія розрахунку"):
    st.markdown("""
    <div class="methodology-box">
    <strong>Активні заходи</strong> — заходи, період виконання яких охоплює обраний рік і квартал.<br><br>

    <strong>Виконання СП</strong> рахується як середня оцінка виконання активних заходів:
    <ul>
        <li>якщо є планове та фактичне значення — використовується співвідношення факт / план зі стелею 100%;</li>
        <li>якщо план / факт не можна порахувати числово — використовується статус виконання;</li>
        <li>«Виконано» = 100%; «Частково виконано» = 75%; «Не виконано» = 0% —
            єдина шкала моделі «Оцінка МіО» (Excel «РВ (Заходи)»);</li>
        <li>відсутність поданих даних прирівнюється до «Не виконано» (0%);</li>
        <li>«Не настав час» та «Втратило актуальність» не включаються до оцінки ризику.</li>
    </ul>

    <strong>Risk score</strong> = 100% мінус прогнозована вірогідність досягнення річного плану.
    Для числових заходів прогноз використовує останній приріст між двома доступними
    кумулятивними квартальними значеннями, а за наявності одного значення — середній темп
    від початку року. Для «так/ні» значення «так» означає досягнення, «ні» — низьку
    вірогідність. Для IV кварталу прогнозний ризик не розраховується.<br><br>

    <strong>Traffic light:</strong>
    🟢 100%+ — у графіку | 🟡 75–99% — часткове | 🔴 &lt;75% — відставання | ⚪ не оцінюється.<br><br>

    <strong>Досягнення стратегічної цілі</strong> рахується у два рівні:
    спочатку середнє відсотків виконання заходів у кожному завданні, потім середнє
    балів завдань у межах цілі. «Не настав час» та «Втратило актуальність» не мають
    числового бала і не входять до усереднення.<br><br>

    <strong>Відхилення за звітний період</strong> = середній відсоток виконання мінус
    очікуваний календарний рівень кварталу: 25% / 50% / 75% / 100%.
    </div>
    """, unsafe_allow_html=True)


if snapshot_context is not None:
    _activate_dashboard_context(snapshot_context)

def _render_dash_auto_summary():
    try:
        _q_order = ["I", "II", "III", "IV"]
        _cur_years = sorted(int(y) for y in (years_for_calc or []))
        _cur_quarters = [q for q in _q_order if q in (quarters_for_calc or [])]
        if not _cur_years or not _cur_quarters:
            return
        _cy, _cq = _cur_years[-1], _cur_quarters[-1]
        _cq_i = _q_order.index(_cq)
        if _cq_i > 0:
            _py, _pq = _cy, _q_order[_cq_i - 1]
        else:
            _py, _pq = _cy - 1, "IV"

        _prev = build_period_data(strat_df, requests_df, [_py], [_pq])
        if _prev is not None and not _prev.empty:
            _prev = collapse_to_latest_measure_rows(_prev)

        def _counts(df):
            if df is None or df.empty or "status" not in df.columns:
                return {}
            return df["status"].astype(str).value_counts().to_dict()

        _cur_c, _prev_c = _counts(active), _counts(_prev)
        _lines = []
        _better, _worse = [], []
        for _st_name, _good in [("Виконано", True), ("Частково виконано", True),
                                ("Не виконано", False)]:
            _d = _cur_c.get(_st_name, 0) - _prev_c.get(_st_name, 0)
            if _d == 0:
                continue
            _txt = (f"«{_st_name}»: {'+' if _d > 0 else ''}{_d} "
                    f"заходів проти {_pq} кв. {_py}")
            if (_d > 0) == _good:
                _better.append(_txt)
            else:
                _worse.append(_txt)
        _no_data = int(
            (active["status"].astype(str).isin(["", "Не подано", "Не враховано"])).sum()
        ) if "status" in active.columns else 0
        _not_yet = int(
            (active["status"].astype(str) == "Не настав час").sum()
        ) if "status" in active.columns else 0

        if _better:
            _lines.append("📈 <b>Покращилось:</b> " + "; ".join(_better) + ".")
        if _worse:
            _lines.append("📉 <b>Погіршилось:</b> " + "; ".join(_worse) + ".")
        if not _better and not _worse:
            _lines.append(
                f"➖ Суттєвих змін розподілу статусів проти {_pq} кв. {_py} "
                f"не зафіксовано."
            )
        _attn = []
        if _no_data:
            _attn.append(f"{_no_data} заходів без поданих відомостей")
        if _not_yet:
            _attn.append(f"{_not_yet} заходів у стані «Не настав час»")
        if _attn:
            _lines.append("👀 <b>На що звернути увагу:</b> " + "; ".join(_attn) + ".")

        st.markdown(
            '<div class="card">'
            '<div class="card-title">🧪 Автоматичний висновок '
            '<span style="font-size:12px;background:#FDF3D8;border:1px solid '
            '#F4B400;color:#8A6400;border-radius:8px;padding:2px 8px;'
            'vertical-align:middle;">тестовий режим</span></div>'
            f'<div class="card-subtitle">Порівняння: {_cq} кв. {_cy} проти '
            f'{_pq} кв. {_py} · за застосованими фільтрами</div>'
            + "".join(f'<div style="font-size:13px;color:#132238;'
                      f'margin:4px 0;">{l}</div>' for l in _lines)
            + '<div style="font-size:11.5px;color:#8A96A8;margin-top:6px;">'
              'Текст сформовано автоматично і він не є офіційним висновком.'
              '</div></div>',
            unsafe_allow_html=True,
        )
    except Exception as exc:
        # Тестовий режим не має права зламати Dashboard.
        log_cosmetic_error("Автоматичний текстовий підсумок Dashboard", exc)


if snapshot_context is not None:
    _render_dash_auto_summary()

render_footer()
