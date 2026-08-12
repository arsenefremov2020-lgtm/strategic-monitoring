import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core.timeutils import now_kyiv
from core.db import get_supabase_client, fetch_all
from core.deputies import DEPUTY_MINISTER_BY_SSP
from core.page_setup import page_setup, render_footer
from core.strategic_data import load_strat_matrix as core_load_strat_matrix
from core import monitoring_data
from core import statuses as core_statuses
from core import dashboard_periods as dashboard_periods_v2
from core import dashboard_risk as dashboard_risk_v2
from core import dashboard_breakdowns as dashboard_breakdowns_v2
from core import dashboard_filters as dashboard_filters_v2
from core import dashboard_finance as dashboard_finance_v2
from core.periods import parse_period as core_parse_period
from core.periods import period_number as core_period_number
from core.periods import quarter_to_number_strict as core_quarter_to_number_strict
from core.periods import quarter_to_roman as core_quarter_to_roman
from core import operational
from core.closeouts import append_confirmed_closeout_facts
from core.exports import build_presentation_pdf
from core.archive import decode_snapshot_payload
from core.errors import log_cosmetic_error, show_incident
from core.access import (
    filter_actions_for_user,
    filter_requests_for_user,
    is_scope_lockable_user,
    is_scope_override_active,
    get_user_ssp_index,
    is_guest_user,
    is_admin_user,
    is_super_admin_user,
)
from core.ui import render_readonly_table, render_scope_toggle
from core.stage4 import render_measure_rows_with_card_links
from html import escape
import re

current_user = page_setup("Dashboard", page_name="Dashboard")
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

/* ── Rank table row colors; cell behavior comes only from assets/app.css ── */
.dashboard-rank-green td {
    background: #E4F5EC !important;
    color: #0C713A !important;
    font-weight: 800;
}

.dashboard-rank-yellow td {
    background: #FDF3D8 !important;
    color: #7A5A00 !important;
}

.dashboard-rank-red td {
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
    """Єдине читання всіх моніторингових подань для Dashboard.

    Заходи та індикатори розділяються вже після застосування однакової
    dashboard-scope логіки. Це важливо для графіків індикаторів: їхні фактичні
    подання не повинні зникати ще на етапі завантаження.
    """
    return monitoring_data.load_monitoring_requests()


# ============================================================
# HELPERS
# ============================================================

def clean(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value).strip()






def parse_period(value):
    """Єдиний строгий розбір періоду через core.periods."""
    return core_parse_period(value)


def quarter_to_number(q):
    """Business parser: invalid quarters must not silently become Q1."""
    return core_quarter_to_number_strict(q)


def quarter_to_roman(q):
    """Display normalisation; business calculations use strict quarter_to_number."""
    return core_quarter_to_roman(q)


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














RISKY_LEVELS = tuple(dashboard_risk_v2.RISKY_LEVELS)






def gauge_chart(value, title):
    number = 0.0 if value is None or pd.isna(value) else float(value)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=number,
        number={"suffix": "%", "font": {"size": 28, "color": "#032A63"}},
        title={"text": title, "font": {"size": 14, "color": "#61708A"}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#8A96A8", "tickfont": {"size": 11}},
            "bar": {"color": "#005BBB", "thickness": 0.3},
            "bgcolor": "#EEF3F9", "borderwidth": 0,
        },
    ))
    fig.update_layout(height=260, margin=dict(l=20, r=20, t=50, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


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






# ============================================================
# CORE DATA FUNCTIONS
# ============================================================










def is_failed_for_weight(row):
    risk_attention = clean(row.get("risk_level")) in dashboard_risk_v2.RISKY_LEVELS
    missing = bool(row.get("missing_required_submission", False))
    final_missing = bool(row.get("final_missing_result", False))
    conflict = bool(row.get("data_quality_conflict", False))
    final_failure = clean(row.get("forecast_kind")) == "final" and not bool(row.get("result_achieved", False))
    return bool(risk_attention or missing or final_missing or conflict or final_failure)

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
            Виконання=("performance_score", "mean")
        )
        .reset_index()
    )
    grouped["Вага_невиконання"] = grouped["Невиконаних"] / len(data) * 100
    grouped["Виконання"] = grouped["Виконання"].fillna(0).round(2)
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






def render_dashboard_table(
    table_data,
    *,
    hide_index=True,
    empty_message="Записів немає.",
    formatters=None,
    row_class_fn=None,
    height=325,
    min_width=None,
    max_cell_height=74,
    column_widths=None,
    scroll_columns=None,
    table_width=None,
):
    """Read-only table in the Home-page visual standard.

    Short tables stretch to the full available Dashboard width. Wide tables
    retain the shared external scroll and may define narrower text columns with
    their own internal cell scroll.
    """
    try:
        frame = table_data.data if hasattr(table_data, "data") else table_data
        column_count = len(frame.columns) if isinstance(frame, pd.DataFrame) else 0
    except Exception:
        column_count = 0
    if min_width is None:
        min_width = 0 if column_count <= 8 else max(
            1180, min(3600, column_count * 118)
        )
    render_readonly_table(
        table_data,
        height=height,
        min_width=min_width,
        max_cell_height=max_cell_height,
        compact=False,
        empty_message=empty_message,
        formatters=formatters or {},
        row_class_fn=row_class_fn,
        show_index=not hide_index,
        column_widths=column_widths or {},
        scroll_columns=scroll_columns or set(),
        table_width=table_width,
    )


def _period_number_to_text(period_num):
    year = int(period_num) // 10
    quarter = {1: "I", 2: "II", 3: "III", 4: "IV"}.get(int(period_num) % 10, "I")
    return f"{quarter} квартал {year} року"





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
all_requests_df = load_requests()

# Dashboard має окрему read-only модель видимості:
# - guest / admin / super-admin бачать усю аналітику;
# - ССП-родина за замовчуванням бачить лише свій ССП;
# - після переходу ССП у загальний режим звуження повністю знімається.
_dashboard_full_scope = (
    is_guest_user(current_user)
    or is_admin_user(current_user)
    or is_super_admin_user(current_user)
    or is_scope_override_active("Dashboard")
)

if _dashboard_full_scope:
    scoped_requests_df = all_requests_df.copy()
else:
    scoped_requests_df = filter_requests_for_user(
        all_requests_df,
        current_user,
        ssp_columns=["department"],
        page_key="Dashboard",
    )

requests_df = monitoring_data.measures_only(scoped_requests_df)

measures_all = strat_df[strat_df["object_type"] == "measure"].copy()
if not _dashboard_full_scope:
    measures_all = filter_actions_for_user(
        measures_all,
        current_user,
        page_key="Dashboard",
    )

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

# Shared current reporting period drives every Dashboard default.
_default_reporting_year, _default_reporting_quarter = dashboard_periods_v2.current_reporting_period(
    requests_df
)
if _default_reporting_year not in years_options:
    _default_reporting_year = years_options[-1]
_default_reporting_quarter = quarter_to_roman(_default_reporting_quarter)
_default_reporting_qnum = quarter_to_number(_default_reporting_quarter)
_default_range_quarters = quarters_options[:_default_reporting_qnum]

_period_widget_defaults = {
    "dash_snapshot_year": _default_reporting_year,
    "dash_snapshot_quarter": _default_reporting_quarter,
    "dash_breakdown_years": [_default_reporting_year],
    "dash_breakdown_quarters": list(_default_range_quarters),
    "dash_dynamics_years": [_default_reporting_year],
    "dash_dynamics_quarters": list(_default_range_quarters),
    "dash_finance_year": _default_reporting_year,
    "dash_finance_quarter": _default_reporting_quarter,
}
for _period_key, _period_default in _period_widget_defaults.items():
    st.session_state.setdefault(
        _period_key,
        list(_period_default) if isinstance(_period_default, list) else _period_default,
    )

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
    "snapshot_year": _default_reporting_year,
    "snapshot_quarter": _default_reporting_quarter,
    "breakdown_years": [_default_reporting_year],
    "breakdown_quarters": list(_default_range_quarters),
    "dynamics_years": [_default_reporting_year],
    "dynamics_quarters": list(_default_range_quarters),
    "finance_year": _default_reporting_year,
    "finance_quarter": _default_reporting_quarter,
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
        "snapshot_year": int(st.session_state.get("dash_snapshot_year", _default_reporting_year)),
        "snapshot_quarter": st.session_state.get("dash_snapshot_quarter", _default_reporting_quarter),
        "breakdown_years": list(st.session_state.get("dash_breakdown_years", [_default_reporting_year]) or [_default_reporting_year]),
        "breakdown_quarters": list(st.session_state.get("dash_breakdown_quarters", _default_range_quarters) or _default_range_quarters),
        "dynamics_years": list(st.session_state.get("dash_dynamics_years", [_default_reporting_year]) or [_default_reporting_year]),
        "dynamics_quarters": list(st.session_state.get("dash_dynamics_quarters", _default_range_quarters) or _default_range_quarters),
        "finance_year": int(st.session_state.get("dash_finance_year", _default_reporting_year)),
        "finance_quarter": st.session_state.get("dash_finance_quarter", _default_reporting_quarter),
    }


def _reset_dashboard_common_filters_v20():
    st.session_state["dash_common_filters_applied_v20"] = _dash_common_defaults.copy()
    for _widget_key, _widget_default in {**_dashboard_common_widget_defaults, **_period_widget_defaults}.items():
        st.session_state[_widget_key] = (
            list(_widget_default) if isinstance(_widget_default, list) else _widget_default
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
            "Застосувати фільтри",
            type="primary",
            use_container_width=True,
            on_click=_apply_dashboard_common_filters_v20,
        )
    with _reset_col:
        st.form_submit_button(
            "Скинути фільтри",
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
applied_snapshot_year = int(_dash_applied.get("snapshot_year", _default_reporting_year))
applied_snapshot_quarter = quarter_to_roman(_dash_applied.get("snapshot_quarter", _default_reporting_quarter))
applied_breakdown_years = list(_dash_applied.get("breakdown_years", [_default_reporting_year]) or [_default_reporting_year])
applied_breakdown_quarters = list(_dash_applied.get("breakdown_quarters", _default_range_quarters) or _default_range_quarters)
applied_dynamics_years = list(_dash_applied.get("dynamics_years", [_default_reporting_year]) or [_default_reporting_year])
applied_dynamics_quarters = list(_dash_applied.get("dynamics_quarters", _default_range_quarters) or _default_range_quarters)
applied_finance_year = int(_dash_applied.get("finance_year", _default_reporting_year))
applied_finance_quarter = quarter_to_roman(_dash_applied.get("finance_quarter", _default_reporting_quarter))

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

_indicator_requests_source = (
    scoped_requests_df[
        scoped_requests_df.get(
            "object_kind",
            pd.Series(index=scoped_requests_df.index, dtype=str),
        ).astype(str).str.lower().eq("indicator")
    ].copy()
    if not scoped_requests_df.empty
    else pd.DataFrame()
)
if data_source_mode == operational.MODE_OPERATIONAL and not _indicator_requests_source.empty:
    _indicator_requests_effective = operational.operational_indicator_rows(_indicator_requests_source)
elif not _indicator_requests_source.empty:
    _indicator_requests_effective = _indicator_requests_source[
        _indicator_requests_source.get("approval_status", pd.Series(index=_indicator_requests_source.index, dtype=str)).astype(str).str.strip().eq("Погоджено")
    ].copy()
else:
    _indicator_requests_effective = pd.DataFrame()

if data_source_mode == operational.MODE_OPERATIONAL and not requests_df.empty:
    _approval_logs = operational.load_monitoring_logs()
    requests_df, _ = operational.apply_operational_mode(
        requests_df,
        logs_df=_approval_logs,
    )

# Ручні закриття лишаються офіційною частиною обох режимів даних.
# Один shared resolver додає реальний closeout-факт лише коли валідної
# materialized заявки немає; статус «Виконано» ніколи не вигадується.
requests_df = append_confirmed_closeout_facts(requests_df, include_incomplete=True)

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
    return [applied_snapshot_year], [applied_snapshot_quarter]


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
    if section_key == "breakdown":
        return list(applied_breakdown_years), list(applied_breakdown_quarters)
    return list(applied_dynamics_years), list(applied_dynamics_quarters)


def _render_finance_period_panel():
    with st.container(border=True, key="dashboard_finance_period_panel"):
        st.markdown('<div class="filter-subtitle dashboard-filter-subtitle">Період секції</div>', unsafe_allow_html=True)
        year_col, quarter_col = st.columns(2)
        with year_col:
            st.markdown('<div class="filter-field-label">Рік</div>', unsafe_allow_html=True)
            st.selectbox("Рік фінансування", years_options, key="dash_finance_year", label_visibility="collapsed")
        with quarter_col:
            st.markdown('<div class="filter-field-label">Станом на квартал</div>', unsafe_allow_html=True)
            st.selectbox("Квартал фінансування", quarters_options, key="dash_finance_quarter", label_visibility="collapsed")
    return [applied_finance_year], [applied_finance_quarter]


def _build_dashboard_context(years_for_calc, quarters_for_calc):
    """Build one Dashboard context entirely from shared v2 calculations."""
    filtered_strat = dashboard_filters_v2.filter_measures(
        measures_all,
        ssp=selected_department_indices,
        goals=selected_goals,
        tasks=selected_tasks,
        measure_codes=selected_measures,
        product_types=selected_product_types,
        deputies=selected_deputies,
        sources=selected_sources,
        financing=selected_financing,
        kpkvk=selected_kpkvk,
    )
    if filtered_strat is None or filtered_strat.empty:
        return None

    pairs = dashboard_breakdowns_v2.period_pairs(years_for_calc, quarters_for_calc)
    if not pairs:
        return None
    period_results = dashboard_breakdowns_v2.build_period_results(
        filtered_strat,
        requests_df,
        pairs,
        stable_statuses=selected_statuses,
        period_sources=_build_period_source_overrides(pairs),
    )
    if not period_results:
        return None

    latest_key = max(period_results, key=lambda key: core_period_number(key[0], key[1]))
    latest_result = period_results[latest_key]
    active = latest_result["snapshot"].copy()
    active_period_rows = pd.concat(
        [item["snapshot"] for _, item in sorted(period_results.items(), key=lambda kv: core_period_number(kv[0][0], kv[0][1]))],
        ignore_index=True,
        sort=False,
    )
    active_raw = active_period_rows.copy()
    if active.empty:
        return None

    snapshot_label = f"Станом на {_period_number_to_text(core_period_number(*latest_key))}"
    first_key = min(period_results, key=lambda key: core_period_number(key[0], key[1]))
    dynamics_label = (
        f"{_period_number_to_text(core_period_number(*first_key))} → "
        f"{_period_number_to_text(core_period_number(*latest_key))}"
    )
    snapshot_period_number = core_period_number(*latest_key)
    snapshot_quarter_num = int(snapshot_period_number) % 10
    monitoring_ok = bool(active.get("monitoring_conducted", pd.Series([True])).iloc[0])

    total_active = int(active["code"].nunique())
    submitted_count = int(active.get("submitted", pd.Series(False, index=active.index)).fillna(False).astype(bool).sum())
    coverage = latest_result.get("coverage")
    completion = latest_result.get("execution_by_measures")
    goal_execution = latest_result.get("execution_by_goals")
    task_progress = latest_result.get("task_scores", pd.DataFrame()).copy()
    goal_scores_shared = latest_result.get("goal_scores", pd.DataFrame()).copy()

    rsummary = latest_result.get("risk_summary", {}) or {}
    risk_share = rsummary.get("share_high_critical_risk")
    low_risk_share = rsummary.get("share_without_substantial_risk")
    risk_assessed = active[
        active.get("included_in_risk_assessment", pd.Series(False, index=active.index)).fillna(False).astype(bool)
    ].copy()
    risk_count = int(active.get("risk_level", pd.Series(index=active.index, dtype=object)).isin(dashboard_risk_v2.RISKY_LEVELS).sum())
    critical_count = int(active.get("risk_level", pd.Series(index=active.index, dtype=object)).eq("Критичний ризик").sum())
    without_data = int(active.get("missing_required_submission", pd.Series(False, index=active.index)).fillna(False).astype(bool).sum())

    status_series = active.get("status_display", pd.Series(index=active.index, dtype=object)).fillna("")
    completed_count = int(status_series.eq("Виконано").sum())
    partly_count = int(status_series.eq("Частково виконано").sum())
    not_done_count = int(status_series.eq("Не виконано").sum())
    obsolete_count = int(status_series.eq("Втратило актуальність").sum())
    not_time_count = int(status_series.eq("Не настав час").sum())
    not_counted_count = int(active.get("status", pd.Series(index=active.index, dtype=object)).eq("Не подано").sum())

    if data_source_mode == operational.MODE_OPERATIONAL:
        approved_requests_count = submitted_count
    else:
        approved_requests_count = int(
            active.get("approval_status", pd.Series(index=active.index, dtype=str)).astype(str).str.strip().eq("Погоджено").sum()
        )
    approval_metric_label = "Пройшли координатора" if data_source_mode == operational.MODE_OPERATIONAL else "Погоджено"

    conclusion = dashboard_risk_v2.management_conclusion(
        active,
        execution_by_measures=completion,
        execution_by_goals=goal_execution,
        coverage=coverage,
    )
    conclusion_title = conclusion["title"]
    conclusion_text = conclusion["explanation"]
    conclusion_badge = {
        "high": "risk-high", "medium": "risk-medium", "low": "risk-low", "neutral": "risk-neutral"
    }.get(conclusion.get("severity"), "risk-neutral")

    status_order = ["Виконано", "Частково виконано", "Не виконано", "Не подано", "Не настав час", "Втратило актуальність", "Не визначено"]
    status_counts = (
        active.assign(_status_chart=active.get("status", status_series).where(~active.get("missing_required_submission", pd.Series(False, index=active.index)).fillna(False), "Не подано"))
        .groupby("_status_chart").size().reindex(status_order, fill_value=0).reset_index(name="Кількість").rename(columns={"_status_chart": "status_display"})
    )
    status_counts = status_counts[status_counts["Кількість"] > 0]
    risk_counts = (
        active[active.get("risk_level", pd.Series(index=active.index, dtype=object)).notna()]
        .groupby("risk_level").size().reset_index(name="Кількість").rename(columns={"risk_level": "auto_risk"})
    )

    # Existing rendering names remain available, but values come from shared hierarchy.
    goal_progress = goal_scores_shared.rename(columns={
        "goal_name": "strategic_goal",
        "by_tasks": "Виконання",
        "total_measure_count": "Активних_заходів",
        "coverage": "Покриття_%",
    }).copy()
    if not goal_progress.empty:
        goal_progress["Покриття"] = (
            goal_progress["Покриття_%"] / 100.0 * goal_progress["Активних_заходів"]
        ).round().fillna(0).astype(int)
        goal_progress["Ризикових"] = 0
        goal_progress["Середній_ризик"] = pd.NA
        goal_progress["За_заходами"] = goal_scores_shared["by_measures"].values
        goal_progress["За_завданнями"] = goal_scores_shared["by_tasks"].values

    # Multi-period shared analytical frames.
    plan_comparison = dashboard_breakdowns_v2.aggregate_plan(period_results)
    goal_comparison = dashboard_breakdowns_v2.aggregate_objects(period_results, object_type="goal")
    task_comparison = dashboard_breakdowns_v2.aggregate_objects(period_results, object_type="task")
    ssp_comparison = dashboard_breakdowns_v2.ssp_summary(period_results, selected_department_indices or None)
    deputy_comparison = dashboard_breakdowns_v2.deputy_summary(period_results)
    dynamics_shared = dashboard_breakdowns_v2.dynamics_frame(period_results)
    execution_forecast_matrix = dashboard_breakdowns_v2.execution_forecast_matrix(active, group_col="department")

    # Latest-period SSP frame retained for current presentation and status charts.
    dep_active = explode_departments(active)
    if not dep_active.empty:
        dep_progress = (
            dep_active.groupby("ssp_department", dropna=False)
            .agg(
                Активних_заходів=("code", "nunique"),
                Виконання=("execution_score", "mean"),
                Подано=("submitted", "sum"),
                Ризикових=("risk_level", lambda values: values.isin(dashboard_risk_v2.RISKY_LEVELS).sum()),
                Критичних=("risk_level", lambda values: values.eq("Критичний ризик").sum()),
            ).reset_index()
        )
        dep_progress["Виконання"] = pd.to_numeric(dep_progress["Виконання"], errors="coerce").round(2)
        dep_progress["Покриття_%"] = (dep_progress["Подано"] / dep_progress["Активних_заходів"] * 100.0).round(2)
        dep_progress["Середній_ризик"] = pd.NA
        dep_progress["Середній_темп"] = pd.NA
    else:
        dep_progress = pd.DataFrame()

    return {
        "years_for_calc": list(years_for_calc), "quarters_for_calc": list(quarters_for_calc),
        "period_results": period_results, "active_raw": active_raw, "active_period_rows": active_period_rows,
        "active": active, "snapshot_label": snapshot_label, "dynamics_label": dynamics_label,
        "snapshot_period_number": snapshot_period_number, "snapshot_quarter_num": snapshot_quarter_num,
        "monitoring_conducted": monitoring_ok,
        "total_active": total_active, "submitted_count": submitted_count, "coverage": coverage,
        "completion": completion, "goal_execution": goal_execution,
        "risk_assessed": risk_assessed, "risk_count": risk_count, "critical_count": critical_count,
        "risk_share": risk_share, "low_risk_share": low_risk_share, "without_data": without_data,
        "completed_count": completed_count, "partly_count": partly_count, "not_done_count": not_done_count,
        "obsolete_count": obsolete_count, "not_time_count": not_time_count,
        "approved_requests_count": approved_requests_count, "approval_metric_label": approval_metric_label,
        "not_counted_count": not_counted_count, "conclusion_title": conclusion_title,
        "conclusion_text": conclusion_text, "conclusion_badge": conclusion_badge,
        "period_label": snapshot_label, "status_counts": status_counts, "risk_counts": risk_counts,
        "goal_progress": goal_progress, "task_progress": task_progress,
        "dep_active": dep_active, "dep_progress": dep_progress,
        "plan_comparison": plan_comparison, "goal_comparison": goal_comparison,
        "task_comparison": task_comparison, "ssp_comparison": ssp_comparison,
        "deputy_comparison": deputy_comparison, "dynamics_shared": dynamics_shared,
        "execution_forecast_matrix": execution_forecast_matrix,
    }

def _activate_dashboard_context(context):
    if context:
        globals().update(context)


def _finance_selected_year(years):
    """Останній обраний рік є однозначним роком фінансових сум."""
    parsed = []
    for value in years or []:
        try:
            parsed.append(int(value))
        except (TypeError, ValueError):
            continue
    return max(parsed) if parsed else 2026


def _finance_numeric(value):
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return None
    return float(number)


def _finance_amount_text(value, digits=6):
    """Форматує суму лише після підсумовування, не округлюючи джерельні дані."""
    number = _finance_numeric(value)
    if number is None:
        return "—"
    text = f"{number:.{digits}f}".rstrip("0").rstrip(".")
    return text.replace("-", "−")


def _prepare_dashboard_finance_measures(active_rows, period_rows, year):
    """UI adapter over ``core.dashboard_finance``; one row per measure/year."""
    if active_rows is None or active_rows.empty or "code" not in active_rows.columns:
        return pd.DataFrame()
    data = active_rows.drop_duplicates(subset=["code"], keep="last").copy()
    shared_fin = dashboard_finance_v2.build_finance_frame(data, int(year))
    if shared_fin.empty:
        return pd.DataFrame()
    fin_map = shared_fin.set_index("code", drop=False)
    prepared = []
    for _, row in data.iterrows():
        code = clean(row.get("code"))
        if code not in fin_map.index:
            continue
        fin = fin_map.loc[code]
        if isinstance(fin, pd.DataFrame):
            fin = fin.iloc[-1]
        item = row.to_dict()
        categories = fin.get("finance_categories") if isinstance(fin.get("finance_categories"), list) else [dashboard_finance_v2.SOURCE_NONE]
        item.update({
            "_finance_year": int(year),
            "_finance_kpkvk": clean(fin.get("kpkvk")),
            "_finance_other_source": clean(fin.get("other_source")),
            "_finance_plan_bln": fin.get("plan_bln"),
            "_finance_fact_bln": fin.get("fact_bln"),
            "_finance_execution_pct": fin.get("financial_execution_pct"),
            "_finance_state_pct": fin.get("execution_score"),
            "_finance_elasticity": fin.get("elasticity"),
            "_finance_has_state_budget": dashboard_finance_v2.SOURCE_STATE in categories,
            "_finance_types": categories,
        })
        prepared.append(item)
    return pd.DataFrame(prepared)

def _finance_group_rows(fin_measures, key):
    if fin_measures is None or fin_measures.empty:
        return pd.DataFrame()
    if key == "state":
        mask = fin_measures["_finance_has_state_budget"].fillna(False).astype(bool)
    elif key == "mtd":
        mask = fin_measures["_finance_types"].apply(
            lambda values: isinstance(values, list) and "МТД / кошти партнерів" in values
        )
    elif key == "other":
        mask = fin_measures["_finance_types"].apply(
            lambda values: isinstance(values, list) and "Небюджетні / інші" in values
        )
    elif key == "none":
        mask = fin_measures["_finance_types"].apply(
            lambda values: isinstance(values, list) and values == ["Без фінансування"]
        )
    elif key == "budget":
        mask = pd.to_numeric(fin_measures["_finance_plan_bln"], errors="coerce").notna()
    else:
        return fin_measures.iloc[0:0].copy()
    return fin_measures.loc[mask].drop_duplicates(subset=["code"], keep="last").copy()


def _finance_detail_display(rows, year):
    if rows is None or rows.empty:
        return pd.DataFrame()
    display = pd.DataFrame({
        "Код": rows.get("code", ""),
        "Захід": rows.get("name", ""),
        "Головний ССП": rows.get("department", ""),
        "Статус виконання": rows.get("status_display", ""),
        "КПКВК": rows.get("_finance_kpkvk", ""),
        "Інше джерело": rows.get("_finance_other_source", ""),
        f"План {year}, млрд грн": rows.get("_finance_plan_bln", pd.Series(index=rows.index, dtype=float)).apply(_finance_amount_text),
        f"Факт {year}, млрд грн": rows.get("_finance_fact_bln", pd.Series(index=rows.index, dtype=float)).apply(_finance_amount_text),
        "% фінансового виконання": rows.get("_finance_execution_pct", pd.Series(index=rows.index, dtype=float)).apply(
            lambda value: f"{float(value):.2f}%" if _finance_numeric(value) is not None else "—"
        ),
        "Стан виконання заходу, %": rows.get("_finance_state_pct", pd.Series(index=rows.index, dtype=object)).apply(
            lambda value: f"{float(value):.2f}%" if _finance_numeric(value) is not None else (clean(value) or "—")
        ),
        "Коефіцієнт еластичності": rows.get("_finance_elasticity", pd.Series(index=rows.index, dtype=float)).apply(
            lambda value: f"{float(value):.4f}" if _finance_numeric(value) is not None else "—"
        ),
    })
    return display


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


def _high_risk_groups(data, group_cols):
    """Latest-quarter groups with high/critical v2 risk signals."""
    columns = list(group_cols) + ["Прогнозоване_досягнення", "Оцінюваних_заходів", "Достатність_темпу"]
    if data is None or data.empty:
        return pd.DataFrame(columns=columns)
    assessed = data[data.get("risk_level", pd.Series(index=data.index, dtype=object)).isin(dashboard_risk_v2.RISKY_LEVELS)].copy()
    if assessed.empty:
        return pd.DataFrame(columns=columns)
    assessed["_forecast"] = pd.to_numeric(assessed.get("forecast_attainment_pct"), errors="coerce")
    assessed["_pace"] = pd.to_numeric(assessed.get("pace_sufficiency_pct"), errors="coerce")
    grouped = (
        assessed.groupby(group_cols, dropna=False)
        .agg(
            Прогнозоване_досягнення=("_forecast", "mean"),
            Оцінюваних_заходів=("code", "nunique"),
            Достатність_темпу=("_pace", "mean"),
        ).reset_index()
    )
    return grouped.sort_values(["Прогнозоване_досягнення", "Оцінюваних_заходів"], ascending=[True, False], na_position="first")

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


def _goal_quarter_drop_signals(year, quarter, minimum_drop=10.0):
    """Material goal-level drops from two shared consecutive snapshots."""
    columns = [
        "goal_code", "strategic_goal", "Попереднє_виконання",
        "Поточне_виконання", "Падіння_вп",
    ]
    q_num = quarter_to_number(quarter)
    if q_num <= 1:
        return pd.DataFrame(columns=columns)
    prev_q = {1: "I", 2: "II", 3: "III", 4: "IV"}[q_num - 1]
    filtered_strat = dashboard_filters_v2.filter_measures(
        measures_all,
        ssp=selected_department_indices, goals=selected_goals, tasks=selected_tasks,
        measure_codes=selected_measures, product_types=selected_product_types,
        deputies=selected_deputies, sources=selected_sources, financing=selected_financing,
        kpkvk=selected_kpkvk,
    )
    if filtered_strat.empty:
        return pd.DataFrame(columns=columns)
    pairs = [(int(year), prev_q), (int(year), quarter_to_roman(quarter))]
    results = dashboard_breakdowns_v2.build_period_results(
        filtered_strat, requests_df, pairs, stable_statuses=selected_statuses,
        period_sources=_build_period_source_overrides(pairs),
    )
    comparison = dashboard_breakdowns_v2.aggregate_objects(results, object_type="goal")
    if comparison.empty:
        return pd.DataFrame(columns=columns)
    comparison = comparison.rename(columns={
        "goal_name": "strategic_goal",
        "latest_by_tasks": "Поточне_виконання",
        "change_by_tasks": "_change",
    })
    comparison["Попереднє_виконання"] = pd.to_numeric(
        comparison["Поточне_виконання"], errors="coerce"
    ) - pd.to_numeric(comparison["_change"], errors="coerce")
    comparison["Падіння_вп"] = -pd.to_numeric(comparison["_change"], errors="coerce")
    comparison = comparison[comparison["Падіння_вп"] >= float(minimum_drop)].copy()
    if comparison.empty:
        return pd.DataFrame(columns=columns)
    return comparison[columns].sort_values("Падіння_вп", ascending=False)


@st.cache_data(ttl=300, show_spinner=False)
def _load_dashboard_archive_payloads():
    """Immutable reporting-period snapshots for the historical trend line."""
    try:
        rows = fetch_all(
            "archive_snapshots",
            "id,year,quarter,reason,archived_at,snapshot_type,snapshot_gzip_b64",
            order=("archived_at", True),
        )
    except Exception:
        return {}
    result = {}
    roman_to_num = {"I": 1, "II": 2, "III": 3, "IV": 4}
    num_to_roman = {1: "I", 2: "II", 3: "III", 4: "IV"}
    for row in rows or []:
        encoded = row.get("snapshot_gzip_b64")
        if not encoded:
            continue
        try:
            payload = decode_snapshot_payload(encoded)
        except Exception:
            continue
        reason = clean(row.get("reason", ""))
        match = re.search(r"\b(IV|III|II|I)\s+квартал\s+(20\d{2})", reason, flags=re.I)
        if match:
            period = (int(match.group(2)), match.group(1).upper())
        else:
            # Legacy snapshots store the anchor quarter (the quarter in which
            # the snapshot was created). The reporting period is the previous one.
            try:
                anchor_year = int(float(row.get("year")))
                anchor_quarter = quarter_to_number(row.get("quarter"))
            except Exception:
                continue
            report_quarter = anchor_quarter - 1
            report_year = anchor_year
            if report_quarter <= 0:
                report_quarter = 4
                report_year -= 1
            period = (report_year, num_to_roman[report_quarter])
        # Ordered oldest→newest; replacements/latest snapshots deliberately win.
        result[period] = payload
    return result




def _apply_archived_closeouts(requests, closeouts):
    """Materialise immutable closeout facts from an archive payload for analytics."""
    data = requests.copy() if isinstance(requests, pd.DataFrame) else pd.DataFrame()
    if not isinstance(closeouts, list) or not closeouts:
        return data
    existing = set()
    if not data.empty:
        for _, row in data[data.get("approval_status", pd.Series(index=data.index, dtype=str)).astype(str).eq("Погоджено")].iterrows():
            existing.add((clean(row.get("strat_code")), str(row.get("year")).strip(), quarter_to_roman(row.get("quarter"))))
    additions = []
    for row in closeouts:
        if clean(row.get("approval_status")) != "Підтверджено":
            continue
        code = clean(row.get("strat_code"))
        year = str(row.get("period_year") or "").strip()
        scope = clean(row.get("scope")).casefold()
        quarter = quarter_to_roman(row.get("period_quarter"))
        quarters = ["I", "II", "III", "IV"] if scope == "рік" else [quarter]
        for q in quarters:
            if (code, year, q) in existing:
                continue
            additions.append({
                "strat_code": code, "year": year, "quarter": q,
                "approval_status": "Погоджено",
                "status": clean(row.get("fact_status")) or "Не подано",
                "numeric_value": row.get("fact_numeric_value"),
                "value_text": row.get("fact_value_text"),
                "progress_text": clean(row.get("fact_progress_text")),
                "risks": "", "submitted_at": clean(row.get("decided_at")),
                "object_kind": "measure", "_manual_closeout": True,
            })
    return pd.concat([data, pd.DataFrame(additions)], ignore_index=True, sort=False) if additions else data




def _archive_locked_periods(payload):
    """Period-lock state frozen inside one immutable archive payload."""
    locked = set(dashboard_periods_v2.SYSTEM_MONITORING_NOT_CONDUCTED)
    rows = payload.get("period_locks") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return locked
    for row in rows:
        try:
            if bool(row.get("locked")):
                locked.add((str(int(row.get("year"))), int(row.get("quarter"))))
        except (TypeError, ValueError):
            continue
    return locked


def _build_period_source_overrides(pairs):
    """Use immutable archive payloads as inputs, but always recalculate with v2.

    Selected periods and their immediate previous quarters are included so
    trajectory/risk never mixes an archived current fact with mutable history.
    """
    payloads = _load_dashboard_archive_payloads()
    if not payloads:
        return {}
    required = set((int(year), quarter_to_roman(quarter)) for year, quarter in pairs)
    for year, quarter in list(required):
        q_num = quarter_to_number(quarter)
        if q_num > 1:
            required.add((int(year), {1: "I", 2: "II", 3: "III", 4: "IV"}[q_num - 1]))

    sources = {}
    for key in required:
        payload = payloads.get(key)
        if not isinstance(payload, dict):
            continue
        archived_strat = pd.DataFrame(payload.get("main_table") or [])
        archived_requests = pd.DataFrame(payload.get("monitoring_requests") or [])
        if archived_strat.empty:
            continue
        archived_strat = dashboard_filters_v2.filter_measures(
            archived_strat,
            ssp=selected_department_indices,
            goals=selected_goals,
            tasks=selected_tasks,
            measure_codes=selected_measures,
            product_types=selected_product_types,
            deputies=selected_deputies,
            sources=selected_sources,
            financing=selected_financing,
            kpkvk=selected_kpkvk,
        )
        if archived_strat.empty:
            continue
        archived_requests = _apply_archived_closeouts(
            archived_requests, payload.get("closeout_requests") or []
        )
        if data_source_mode == operational.MODE_OPERATIONAL and not archived_requests.empty:
            archived_requests, _ = operational.apply_operational_mode(
                archived_requests,
                logs_df=pd.DataFrame(payload.get("monitoring_logs") or []),
                versions_df=pd.DataFrame(payload.get("monitoring_request_versions") or []),
            )
        archived_requests = monitoring_data.measures_only(archived_requests)
        sources[key] = {
            "strat_df": archived_strat,
            "requests_df": archived_requests,
            "locked_periods": _archive_locked_periods(payload),
        }
    return sources





_snapshot_description = "Що маємо на кінець обраного кварталу?"
_breakdown_description = "Де виконання вище, а де нижче за обраний період?"
_dynamics_description = "Як змінювалися результати від кварталу до кварталу?"
_finance_description = "Фінансові показники за один рік станом на один обраний квартал."

if presentation_mode:
    _render_dashboard_section_intro("Стан виконання", _snapshot_description)
    snapshot_years, snapshot_quarters = _render_single_period_panel()
    snapshot_context = _build_dashboard_context(snapshot_years, snapshot_quarters)
    if snapshot_context is None:
        st.warning("Немає заходів, що відповідають усім застосованим параметрам відбору.")
        render_footer()
        st.stop()
    _activate_dashboard_context(snapshot_context)
    selected_years = snapshot_years
    selected_quarters = snapshot_quarters
    breakdown_context = dynamics_context = finance_context = None
else:
    _render_dashboard_section_intro("Стан виконання", _snapshot_description)
    snapshot_years, snapshot_quarters = _render_single_period_panel()
    snapshot_content = st.container(key="dashboard_snapshot_content")

    _render_dashboard_section_intro("Порівняння результатів", _breakdown_description)
    breakdown_years, breakdown_quarters = _render_multi_period_panel(
        "breakdown", "dash_breakdown_years", "dash_breakdown_quarters"
    )
    breakdown_content = st.container(key="dashboard_breakdown_content")

    _render_dashboard_section_intro("Динаміка виконання", _dynamics_description)
    dynamics_years, dynamics_quarters = _render_multi_period_panel(
        "dynamics", "dash_dynamics_years", "dash_dynamics_quarters"
    )
    dynamics_content = st.container(key="dashboard_dynamics_content")

    _render_dashboard_section_intro("Фінансування", _finance_description)
    finance_years, finance_quarters = _render_finance_period_panel()
    finance_content = st.container(key="dashboard_finance_content")

    snapshot_context = _build_dashboard_context(snapshot_years, snapshot_quarters)
    breakdown_context = _build_dashboard_context(breakdown_years, breakdown_quarters)
    dynamics_context = _build_dashboard_context(dynamics_years, dynamics_quarters)
    finance_context = _build_dashboard_context(finance_years, finance_quarters)

    for _context, _container in [
        (snapshot_context, snapshot_content), (breakdown_context, breakdown_content),
        (dynamics_context, dynamics_content), (finance_context, finance_content),
    ]:
        if _context is None:
            with _container:
                st.warning("Немає заходів, що відповідають усім застосованим параметрам відбору.")

    selected_years = snapshot_years
    selected_quarters = snapshot_quarters

snapshot_monitoring_available = bool(
    snapshot_context is not None and snapshot_context.get("monitoring_conducted", True)
)
if snapshot_context is not None and not snapshot_monitoring_available:
    if presentation_mode:
        st.info("Моніторинг у цьому періоді не проводився.")
        render_footer()
        st.stop()
    with snapshot_content:
        st.info("Моніторинг у цьому періоді не проводився.")

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
                        ("Всього заходів у зрізі", str(total_active)),
                        ("Виконано", str(completed_count)),
                        ("Частково виконано", str(partly_count)),
                        ("Не виконано", str(not_done_count)),
                        ("Не настав час", str(not_time_count)),
                        ("Втратило актуальність", str(obsolete_count)),
                        ("Виконання за заходами, %", f"{_format_summary_number(completion)}%"),
                        ("Виконання за стратегічними цілями, %", f"{_format_summary_number(goal_execution)}%"),
                        ("Покриття моніторингом, %", f"{_format_summary_number(coverage)}%"),
                        (("Результатів досягнуто, %" if snapshot_quarter_num == 4 else "Високий + критичний ризик, %"),
                         f"{_format_summary_number(snapshot_context.get('period_results', {}).get((int(snapshot_years[0]), quarter_to_roman(snapshot_quarters[0])), {}).get('risk_summary', {}).get('share_results_achieved') if snapshot_quarter_num == 4 else risk_share)}%"),
                    ]
                    _st_fig = _pdf_px.bar(
                        x=["Виконано", "Частково виконано", "Не виконано", "Не подано", "Не настав час", "Втратило актуальність"],
                        y=[completed_count, partly_count, not_done_count, not_counted_count, not_time_count, obsolete_count],
                        color_discrete_sequence=["#005BBB"],
                        title="",
                    )
                    _st_fig.update_layout(xaxis_title="", yaxis_title="Кількість заходів",
                                          plot_bgcolor="white", paper_bgcolor="white")
                    _pdf_figures = [("Статуси виконання заходів", _st_fig),
                                    ("Виконання за заходами", gauge_chart(completion, "Виконання за заходами")),
                                    ("Виконання за стратегічними цілями", gauge_chart(goal_execution, "Виконання за стратегічними цілями"))]

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
                        {"risk-high": "high", "risk-medium": "medium", "risk-low": "low", "risk-neutral": "medium"}[conclusion_badge],
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
    verdict_class = {"risk-high": "high", "risk-medium": "medium", "risk-low": "low", "risk-neutral": "medium"}[conclusion_badge]
    verdict_emoji = {"risk-high": "🔴", "risk-medium": "🟡", "risk-low": "🟢", "risk-neutral": "ℹ️"}[conclusion_badge]

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
    _presentation_q4 = snapshot_quarter_num == 4
    if _presentation_q4:
        _assessed_final = active[active["execution_score"].notna()].copy()
        count_low = int(_assessed_final.get("result_achieved", pd.Series(False, index=_assessed_final.index)).fillna(False).astype(bool).sum())
        count_high = int(len(_assessed_final) - count_low)
        count_medium = partly_count
        _pres_risk_section = "Підсумок року"
        _pres_risk_title = "Фактичні річні результати"
        _pres_risk_high_label = "🔴 Результат не досягнуто"
        _pres_risk_medium_label = "🟡 Частково виконано"
        _pres_risk_low_label = "🟢 Результат досягнуто"
        _pres_risk_share_label = "Не досягнуто"
    else:
        _pres_risk_section = "Автоматична оцінка ризиків"
        _pres_risk_title = "Розподіл ризиків недосягнення"
        _pres_risk_high_label = "🔴 Критичний / високий ризик"
        _pres_risk_medium_label = "🟡 Середній ризик"
        _pres_risk_low_label = "🟢 Низький ризик"
        _pres_risk_share_label = "Частка з ризиком"
    _pres_fourth_label = "Результатів досягнуто" if _presentation_q4 else "Частка без суттєвого ризику"
    _pres_fourth_value = (
        (count_low / len(_assessed_final) * 100.0 if _presentation_q4 and len(_assessed_final) else 0.0)
        if _presentation_q4 else (float(low_risk_share) if low_risk_share is not None else 0.0)
    )

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
    pres_fin_year = _finance_selected_year(selected_years)
    pres_fin_measures = _prepare_dashboard_finance_measures(
        active,
        active_period_rows,
        pres_fin_year,
    )
    pres_fin_total = len(pres_fin_measures)
    pres_fin_db = len(_finance_group_rows(pres_fin_measures, "state"))
    pres_fin_mtd = len(_finance_group_rows(pres_fin_measures, "mtd"))
    pres_fin_other = len(_finance_group_rows(pres_fin_measures, "other"))
    pres_fin_no = len(_finance_group_rows(pres_fin_measures, "none"))
    pres_budget_rows = _finance_group_rows(pres_fin_measures, "budget")
    pres_budget_values = pd.to_numeric(
        pres_budget_rows.get("_finance_plan_bln", pd.Series(dtype=float)),
        errors="coerce",
    ).dropna()
    pres_budget_sum = float(pres_budget_values.sum()) if not pres_budget_values.empty else None
    pres_budget_str = (
        f"{_finance_amount_text(pres_budget_sum)} млрд грн"
        if pres_budget_sum is not None else "н/д"
    )

    pres_fin_bars_html = ""
    _fin_types_slide = [
        ("Державний бюджет", pres_fin_db, "#005BBB"),
        ("МТД / кошти партнерів", pres_fin_mtd, "#00A8A8"),
        ("Небюджетні / інші", pres_fin_other, "#FF7A45"),
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
    if not pres_fin_measures.empty:
        _kp_source = pres_fin_measures[
            pres_fin_measures["_finance_kpkvk"].astype(str).str.strip() != ""
        ].copy()
        if not _kp_source.empty:
            _kp_tbl = (
                _kp_source
                .groupby("_finance_kpkvk", dropna=False)
                .agg(
                    _Заходів=("code", "nunique"),
                    _Бюджет=("_finance_plan_bln", lambda values: values.dropna().sum() if values.notna().any() else None),
                )
                .reset_index()
                .sort_values("_Заходів", ascending=False)
                .head(6)
            )
            for _, _krow in _kp_tbl.iterrows():
                _b_str = _finance_amount_text(_krow["_Бюджет"])
                pres_kpkvk_html += (
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'padding:10px 0;border-bottom:1px solid rgba(255,255,255,.06);">'
                    f'<span style="font-size:14px;font-weight:800;color:#FFD500;">{_krow["_finance_kpkvk"]}</span>'
                    f'<span style="font-size:12px;color:rgba(255,255,255,.5);">{int(_krow["_Заходів"])} заходів</span>'
                    f'<span style="font-size:12px;color:rgba(255,255,255,.7);font-weight:700;">{_b_str} млрд грн</span>'
                    f'</div>'
                )
    if not pres_kpkvk_html:
        pres_kpkvk_html = '<div style="color:rgba(255,255,255,.3);margin-top:12px;">КПКВК не визначено</div>'

    # ── топ-5 проблемних заходів для слайду 6 ─────────────────
    top5_html = ""
    top5_data = active.loc[dashboard_risk_v2.attention_mask(active)].copy()
    _severity_rank = {"Критичний ризик": 4, "Високий ризик": 3, "Середній ризик": 2, "Низький ризик": 1}
    top5_data["_attention_rank"] = top5_data.get("risk_level", pd.Series(index=top5_data.index, dtype=object)).map(_severity_rank).fillna(0)
    top5_data.loc[top5_data.get("final_missing_result", False).fillna(False), "_attention_rank"] = 5
    top5_data.loc[(top5_data.get("forecast_kind", "") == "final") & ~top5_data.get("result_achieved", False).fillna(False), "_attention_rank"] = 5
    top5_data = top5_data.sort_values(["_attention_rank", "execution_score"], ascending=[False, True], na_position="last").head(5)

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
                <span class="pres-filter-pill">📌 {total_active} заходів у зрізі</span>
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
                    <div style="font-size:44px;font-weight:900;color:#fff;line-height:1;">{_format_summary_number(completion)}%</div>
                    <div style="font-size:12px;color:rgba(255,255,255,.35);margin-top:4px;">Середнє по заходах у зрізі</div>
                </div>
                <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:20px 18px;">
                    <div style="font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:rgba(255,255,255,.35);margin-bottom:8px;">Покриття</div>
                    <div style="font-size:44px;font-weight:900;color:#fff;line-height:1;">{_format_summary_number(coverage)}%</div>
                    <div style="font-size:12px;color:rgba(255,255,255,.35);margin-top:4px;">Заходів з поданими даними</div>
                </div>
                <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:20px 18px;">
                    <div style="font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:rgba(255,255,255,.35);margin-bottom:8px;">Виконання за цілями</div>
                    <div style="font-size:44px;font-weight:900;color:#4D8DFF;line-height:1;">{_format_summary_number(goal_execution)}%</div>
                    <div style="font-size:12px;color:rgba(255,255,255,.35);margin-top:4px;">Ієрархічна оцінка через завдання</div>
                </div>
            </div>
        </div>

        <!-- ══ SLIDE 3 — KEY METRICS ══ -->
        <div class="pres-slide pres-slide-kpis">
            <div class="pres-slide-num">03 / 07</div>
            <div class="pres-section-label">Ключові показники</div>
            <div class="pres-slide-h2">Статистика виконання заходів</div>
            <div class="pres-slide-hsub">{period_label} · {total_active} заходів у зрізі</div>

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
                    <div class="pres-kpi-label">{approval_metric_label}</div>
                    <div class="pres-kpi-value">{approved_requests_count}</div>
                    <div class="pres-kpi-sub">{pct_value(approved_requests_count, total_active)}</div>
                </div>
                <div class="pres-kpi-card yellow">
                    <div class="pres-kpi-label">Частково виконано</div>
                    <div class="pres-kpi-value">{partly_count}</div>
                    <div class="pres-kpi-sub">{pct_value(partly_count, total_active)}</div>
                </div>
                <div class="pres-kpi-card red">
                    <div class="pres-kpi-label">Не подано</div>
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
                {pres_bar('Виконання за заходами', completion or 0, '#005BBB')}
                {pres_bar('Виконання за цілями', goal_execution or 0, '#4D8DFF')}
                {pres_bar('Покриття моніторингом', coverage or 0, '#00A8A8')}
                {pres_bar(_pres_fourth_label, round(_pres_fourth_value, 1), '#118847')}
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
            <div class="pres-section-label">{_pres_risk_section}</div>
            <div class="pres-slide-h2">{_pres_risk_title}</div>
            <div class="pres-slide-hsub">{total_active} заходів у зрізі · {period_label}</div>

            <div class="pres-risk-grid">
                <div class="pres-risk-card high">
                    <div class="pres-risk-label">{_pres_risk_high_label}</div>
                    <div class="pres-risk-val">{count_high}</div>
                    <div class="pres-risk-sub">{pct_value(count_high, total_active)} від усіх заходів</div>
                </div>
                <div class="pres-risk-card medium">
                    <div class="pres-risk-label">{_pres_risk_medium_label}</div>
                    <div class="pres-risk-val">{count_medium}</div>
                    <div class="pres-risk-sub">{pct_value(count_medium, total_active)} від усіх заходів</div>
                </div>
                <div class="pres-risk-card low">
                    <div class="pres-risk-label">{_pres_risk_low_label}</div>
                    <div class="pres-risk-val">{count_low}</div>
                    <div class="pres-risk-sub">{pct_value(count_low, total_active)} від усіх заходів</div>
                </div>
            </div>

            <div style="margin-top:48px;padding:24px 28px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:14px;max-width:640px;">
                <div style="font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(255,255,255,.3);margin-bottom:12px;">Загальний висновок системи</div>
                <div style="font-size:15px;color:rgba(255,255,255,.7);line-height:1.7;">{conclusion_text}</div>
                <div style="margin-top:16px;display:flex;gap:12px;flex-wrap:wrap;">
                    <span style="background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:6px;padding:5px 12px;font-size:11px;color:rgba(255,255,255,.5);font-weight:600;">{_pres_risk_share_label}: {(_format_summary_number((count_high / total_active * 100) if total_active else None) if _presentation_q4 else _format_summary_number(risk_share))}%</span>
                    <span style="background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:6px;padding:5px 12px;font-size:11px;color:rgba(255,255,255,.5);font-weight:600;">Без даних: {without_data} заходів</span>
                </div>
            </div>
        </div>

        <div class="pres-exit-hint">↑ прокрутіть вверх · вимкніть тумблер щоб вийти</div>

        <!-- ══ SLIDE 6 — TOP-5 ПРОБЛЕМНІ ЗАХОДИ ══ -->
        <div class="pres-slide" style="background:#032A63;">
            <div class="pres-slide-num">06 / 07</div>
            <div class="pres-section-label">Увага керівництва</div>
            <div class="pres-slide-h2">Топ-5 проблемних заходів</div>
            <div class="pres-slide-hsub">V2 attention signals: ризик, відсутність подання, final failure або конфлікт даних · {period_label}</div>
            <div style="margin-top:28px;max-width:860px;">
                {top5_html}
            </div>
        </div>


        <!-- ══ SLIDE 7 — ФІНАНСУВАННЯ ══ -->
        <div class="pres-slide" style="background:#032A63;">
            <div class="pres-slide-num">07 / 07</div>
            <div class="pres-section-label">Фінансування заходів</div>
            <div class="pres-slide-h2">Структура та обсяги фінансування</div>
            <div class="pres-slide-hsub">{period_label} · {pres_fin_total} заходів у зрізі</div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:40px;margin-top:36px;max-width:900px;">
                <div>
                    <div style="font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(255,255,255,.3);margin-bottom:20px;">Джерела фінансування</div>
                    {pres_fin_bars_html}
                    <div style="margin-top:24px;background:rgba(0,91,187,.12);border:1px solid rgba(0,91,187,.25);border-radius:12px;padding:20px 22px;">
                        <div style="font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:rgba(255,255,255,.3);margin-bottom:8px;">Бюджет ДБ {pres_fin_year}</div>
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
if snapshot_context is not None and snapshot_monitoring_available:
    _activate_dashboard_context(snapshot_context)
    with snapshot_content:
        _render_section_summary(
            "Стан зараз",
            conclusion_text,
            badge=conclusion_title,
            metrics=[
                f"Виконання за заходами: {_format_summary_number(completion)}%",
                f"Виконання за цілями: {_format_summary_number(goal_execution)}%",
                f"Покриття: {_format_summary_number(coverage)}%",
                f"Заходів у зрізі: {total_active}",
            ],
            tone=conclusion_badge,
        )

        _main_kpi_items = [
            {"key": "all", "title": "Заходів", "count": total_active, "percent": "100.0%", "color": "kpi-blue"},
            {"key": "completed", "title": "Виконано", "count": completed_count, "percent": pct_value(completed_count, total_active), "color": "kpi-green"},
            {"key": "approved", "title": approval_metric_label, "count": approved_requests_count, "percent": pct_value(approved_requests_count, total_active), "color": "kpi-green"},
            {"key": "not_counted", "title": "Не подано", "count": not_counted_count, "percent": pct_value(not_counted_count, total_active), "color": "kpi-red"},
            {"key": "not_done", "title": "Не виконано", "count": not_done_count, "percent": pct_value(not_done_count, total_active), "color": "kpi-red"},
            {"key": "obsolete", "title": "Втратило актуальність", "count": obsolete_count, "percent": pct_value(obsolete_count, total_active), "color": "kpi-gray"},
            {"key": "not_time", "title": "Не настав час", "count": not_time_count, "percent": pct_value(not_time_count, total_active), "color": "kpi-gray"},
            {"key": "partly", "title": "Частково виконано", "count": partly_count, "percent": pct_value(partly_count, total_active), "color": "kpi-yellow"},
        ]
        _selected_kpi = render_kpi_grid(_main_kpi_items, interactive=True, query_key="kpi")

        if data_source_mode == operational.MODE_OPERATIONAL:
            _approved_detail = active[active.get("has_monitoring_data", False).fillna(False)].copy()
        else:
            _approved_detail = active[
                active.get("approval_status", pd.Series(index=active.index, dtype=str))
                .astype(str).str.strip() == "Погоджено"
            ].copy()

        _kpi_detail_frames = {
            "all": active.copy(),
            "completed": active[active["status_display"] == "Виконано"].copy(),
            "approved": _approved_detail,
            "not_counted": active[active["status"] == "Не подано"].copy(),
            "not_done": active[
                (active["status_display"] == "Не виконано") & (active["status"] != "Не подано")
            ].copy(),
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
                f'Dеталізація KPI: {_selected_item["title"]} '
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

        goal_threats = _high_risk_groups(
            active,
            ["goal_code", "strategic_goal"],
        )
        for _, row in goal_threats.head(3).iterrows():
            goal_code = escape(clean(row.get("goal_code", "")) or "Без коду")
            probability = _format_summary_number(
                row.get("Прогнозоване_досягнення"),
            )
            tempo = pd.to_numeric(
                pd.Series([row.get("Достатність_темпу")]),
                errors="coerce",
            ).iloc[0]
            tempo_text = (
                f"; достатність темпу — {_format_summary_number(tempo)}% річного плану"
                if pd.notna(tempo)
                else ""
            )
            render_insight(
                f"🔴 Ціль {goal_code} під загрозою зриву річного плану — "
                f"прогнозоване досягнення річного плану — {probability}%{tempo_text}.",
                "danger",
            )
            insight_count += 1

        department_threats = _high_risk_groups(
            explode_departments(active),
            ["ssp_department"],
        )
        for _, row in department_threats.head(3).iterrows():
            department = escape(
                clean(row.get("ssp_department", "")) or "Не визначено"
            )
            probability = _format_summary_number(
                row.get("Прогнозоване_досягнення"),
            )
            tempo = pd.to_numeric(
                pd.Series([row.get("Достатність_темпу")]),
                errors="coerce",
            ).iloc[0]
            tempo_text = (
                f"; достатність темпу — {_format_summary_number(tempo)}% річного плану"
                if pd.notna(tempo)
                else ""
            )
            render_insight(
                f"🔴 Підрозділ {department} під загрозою зриву річного плану — "
                f"прогнозоване досягнення річного плану — {probability}%{tempo_text}.",
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

        goal_drops = _goal_quarter_drop_signals(snapshot_years[0], snapshot_quarters[0])
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

        ind_col1, ind_col2 = st.columns(2)
        with ind_col1:
            fig_gauge = gauge_chart(completion, "Виконання за заходами")
            render_plotly_chart(fig_gauge, use_container_width=True)
            st.caption("Наскільки виконаний весь обсяг заходів?")
        with ind_col2:
            fig_goal_gauge = gauge_chart(goal_execution, "Виконання за стратегічними цілями")
            render_plotly_chart(fig_goal_gauge, use_container_width=True)
            st.caption("Наскільки збалансовано реалізуються стратегічні пріоритети?")

        _latest_risk_summary = snapshot_context.get("period_results", {}).get(
            (int(snapshot_years[0]), quarter_to_roman(snapshot_quarters[0])), {}
        ).get("risk_summary", {})
        _summary_items = [
            {"key":"coverage", "title":"Покриття моніторингом", "count": _format_summary_number(coverage) + "%", "percent":"Активні заходи з необхідним поданням", "color":"kpi-blue"},
            {"key":"achieved", "title":"Результатів уже досягнуто", "count": _format_summary_number(_latest_risk_summary.get("share_results_achieved")) + "%", "percent":"Частка оцінених заходів", "color":"kpi-green"},
            {"key":"safe", "title":"Без суттєвого ризику", "count": (_format_summary_number(low_risk_share) + "%") if low_risk_share is not None else "н/д", "percent":"Досягнуто + низький ризик", "color":"kpi-green"},
            {"key":"high", "title":"Високий + критичний ризик", "count": (_format_summary_number(risk_share) + "%") if risk_share is not None else "н/д", "percent":"Станом на обраний квартал", "color":"kpi-red"},
        ]
        render_kpi_grid(_summary_items, interactive=False)

        st.markdown("</div>", unsafe_allow_html=True)

# Статуси виконання моментного зрізу.
if snapshot_context is not None and snapshot_monitoring_available:
    _activate_dashboard_context(snapshot_context)
    with snapshot_content:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Структура статусів виконання</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-subtitle">Розподіл заходів у зрізі за станом виконання</div>', unsafe_allow_html=True)
        fig_tl = px.pie(
            status_counts,
            names="status_display",
            values="Кількість",
            hole=0.52,
            color="status_display",
            color_discrete_map={
                "Виконано": "#118847", "Частково виконано": "#F4B400",
                "Не виконано": "#DC4A4A", "Не подано": "#B42318",
                "Не настав час": "#8A96A8", "Втратило актуальність": "#5b21b6",
                "Не визначено": "#61708A",
            },
            labels={
                "status_display": "Статус виконання",
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

# Виконання за стратегічними цілями та завданнями — multi-period Average/Latest/Change.
if breakdown_context is not None:
    _activate_dashboard_context(breakdown_context)
    with breakdown_content:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Виконання за стратегічними цілями</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-subtitle">Основне значення — середнє за вибрані квартали. '
            'Tooltip показує останнє значення та зміну від першого порівнюваного кварталу.</div>',
            unsafe_allow_html=True,
        )
        goals_cmp = goal_comparison.copy()
        if goals_cmp.empty:
            render_no_chart_data()
        else:
            goals_cmp["_sort"] = goals_cmp["goal_code"].apply(code_sort_key)
            goals_cmp = goals_cmp.sort_values("_sort")
            goals_cmp["label"] = goals_cmp.apply(
                lambda r: f"{r['goal_code']} — {_short_summary_label(r.get('goal_name',''), 55)}", axis=1
            )
            fig_goals = go.Figure()
            for label, avg_col, latest_col, change_col, color in [
                ("За заходами", "average_by_measures", "latest_by_measures", "change_by_measures", "#005BBB"),
                ("За завданнями", "average_by_tasks", "latest_by_tasks", "change_by_tasks", "#4D8DFF"),
            ]:
                fig_goals.add_trace(go.Bar(
                    name=label, orientation="h", y=goals_cmp["label"], x=goals_cmp[avg_col],
                    marker_color=color,
                    customdata=list(zip(goals_cmp[latest_col], goals_cmp[change_col])),
                    hovertemplate=(
                        f"<b>{label}</b><br>Середнє: %{{x:.1f}}%<br>"
                        "Останнє: %{customdata[0]:.1f}%<br>Зміна: %{customdata[1]:+.1f} в.п.<extra></extra>"
                    ),
                ))
            fig_goals.update_layout(**CHART_LAYOUT, barmode="group",
                                    height=max(300, len(goals_cmp) * 62 + 80),
                                    xaxis=dict(range=[0, 105], ticksuffix="%", showgrid=True, gridcolor="#F7F9FC"),
                                    yaxis=dict(title=None, autorange="reversed"), legend_title_text="Методика")
            apply_safe_plotly_layout(fig_goals, has_legend=True)
            render_plotly_chart(fig_goals, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Виконання завдань</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-subtitle">Середнє, останнє значення та зміна за вибраний період</div>', unsafe_allow_html=True)
        tasks_cmp = task_comparison.copy()
        if tasks_cmp.empty:
            render_no_chart_data()
        else:
            tasks_cmp["_sort"] = tasks_cmp["task_code"].apply(code_sort_key)
            tasks_cmp = tasks_cmp.sort_values("_sort")
            tasks_cmp["label"] = tasks_cmp.apply(
                lambda r: f"{r['task_code']} — {_short_summary_label(r.get('task_name',''), 58)}", axis=1
            )
            fig_tasks = go.Figure(go.Bar(
                orientation="h", y=tasks_cmp["label"], x=tasks_cmp["average_execution"],
                marker_color="#00A8A8",
                customdata=list(zip(tasks_cmp["latest_execution"], tasks_cmp["change_execution"])),
                hovertemplate=(
                    "Середнє: %{x:.1f}%<br>Останнє: %{customdata[0]:.1f}%<br>"
                    "Зміна: %{customdata[1]:+.1f} в.п.<extra></extra>"
                ),
            ))
            fig_tasks.update_layout(**CHART_LAYOUT, height=max(320, len(tasks_cmp) * 32 + 80),
                                    xaxis=dict(range=[0,105], ticksuffix="%", showgrid=True, gridcolor="#F7F9FC"),
                                    yaxis=dict(title=None, autorange="reversed"), showlegend=False)
            render_plotly_chart(fig_tasks, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# Рейтинги й виконання за ССП та заступниками Міністра.
if breakdown_context is not None:
    _activate_dashboard_context(breakdown_context)
    with breakdown_content:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Рейтинг самостійних структурних підрозділів</div>', unsafe_allow_html=True)
        ssp_cmp = ssp_comparison.copy()
        if ssp_cmp.empty:
            render_no_chart_data()
        else:
            ssp_cmp = ssp_cmp.sort_values("average", ascending=False, na_position="last").reset_index(drop=True)
            ssp_cmp["Місце"] = range(1, len(ssp_cmp)+1)
            rank_display = ssp_cmp.rename(columns={
                "ssp": "Самостійний структурний підрозділ", "average": "Середнє виконання, %",
                "latest": "Останнє виконання, %", "change": "Зміна, в.п.",
                "average_coverage": "Середнє покриття, %", "latest_coverage": "Останнє покриття, %",
                "risk_high_critical_latest": "Високий + критичний ризик, %",
            })
            render_dashboard_table(
                rank_display[["Місце", "Самостійний структурний підрозділ", "Середнє виконання, %",
                              "Останнє виконання, %", "Зміна, в.п.", "Середнє покриття, %",
                              "Останнє покриття, %", "Високий + критичний ризик, %"]],
                hide_index=True,
            )
            st.caption("Ризик у рейтингу — станом на останній вибраний звітний квартал; між кварталами він не усереднюється.")

            ssp_plot = ssp_cmp.copy(); ssp_plot["ssp"] = ssp_plot["ssp"].astype(str)
            fig_ssp = go.Figure()
            fig_ssp.add_trace(go.Bar(x=ssp_plot["ssp"], y=ssp_plot["average"], name="Середнє", marker_color="#005BBB",
                                     customdata=ssp_plot["change"],
                                     hovertemplate="Середнє: %{y:.1f}%<br>Зміна: %{customdata:+.1f} в.п.<extra></extra>"))
            fig_ssp.add_trace(go.Scatter(x=ssp_plot["ssp"], y=ssp_plot["latest"], name="Останнє",
                                         mode="markers", marker=dict(size=10, symbol="diamond", color="#F4B400"),
                                         hovertemplate="Останнє: %{y:.1f}%<extra></extra>"))
            fig_ssp.update_layout(**CHART_LAYOUT, height=390, xaxis=dict(tickangle=-35),
                                  yaxis=dict(range=[0,105], ticksuffix="%", showgrid=True, gridcolor="#F7F9FC"))
            apply_safe_plotly_layout(fig_ssp, has_legend=True)
            render_plotly_chart(fig_ssp, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Виконання за Заступниками Міністра</div>', unsafe_allow_html=True)
        dep_cmp = deputy_comparison.copy()
        if dep_cmp.empty:
            render_no_chart_data()
        else:
            dep_display = dep_cmp.rename(columns={
                "deputy":"Заступник Міністра", "average":"Середнє виконання, %", "latest":"Останнє виконання, %",
                "change":"Зміна, в.п.", "average_coverage":"Середнє покриття, %", "latest_coverage":"Останнє покриття, %",
                "risk_high_critical_latest":"Високий + критичний ризик, %",
            })
            render_dashboard_table(dep_display[["Заступник Міністра","Середнє виконання, %","Останнє виконання, %",
                                                  "Зміна, в.п.","Середнє покриття, %","Останнє покриття, %",
                                                  "Високий + критичний ризик, %"]], hide_index=True)
            dep_plot = dep_cmp.copy(); dep_plot["short"] = dep_plot["deputy"].astype(str).str[:32]
            fig_deputy = go.Figure()
            fig_deputy.add_trace(go.Bar(x=dep_plot["short"], y=dep_plot["average"], name="Середнє", marker_color="#00A8A8",
                                        customdata=dep_plot["change"], hovertemplate="Середнє: %{y:.1f}%<br>Зміна: %{customdata:+.1f} в.п.<extra></extra>"))
            fig_deputy.add_trace(go.Scatter(x=dep_plot["short"], y=dep_plot["latest"], name="Останнє", mode="markers",
                                            marker=dict(size=10, symbol="diamond", color="#F4B400")))
            fig_deputy.update_layout(**CHART_LAYOUT, height=370, xaxis=dict(tickangle=-30),
                                     yaxis=dict(range=[0,105], ticksuffix="%", showgrid=True, gridcolor="#F7F9FC"))
            apply_safe_plotly_layout(fig_deputy, has_legend=True)
            render_plotly_chart(fig_deputy, use_container_width=True)
            st.caption("Ризик — станом на останній вибраний квартал.")
        st.markdown("</div>", unsafe_allow_html=True)

# ============================================================
# РИЗИКИ: КРУГОВА І МАТРИЦЯ — МОМЕНТНИЙ ЗРІЗ; СТРУКТУРА — ЗА РОЗРІЗОМ
# ============================================================

# Кругова автоматична оцінка ризиків.
if snapshot_context is not None and snapshot_monitoring_available:
    _activate_dashboard_context(snapshot_context)
    with snapshot_content:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        if quarter_to_roman(snapshot_quarters[0]) == "IV":
            st.markdown('<div class="section-title">Підсумок року</div>', unsafe_allow_html=True)
            st.info("У IV кварталі прогнозний ризик не розраховується. Оцінка базується на фактичному річному результаті.")
        else:
            st.markdown('<div class="section-title">Автоматична оцінка ризиків</div>', unsafe_allow_html=True)
            if risk_counts.empty:
                st.info("Недостатньо даних для прогнозної оцінки ризику.")
            else:
                fig_risk_pie = px.pie(
                    risk_counts, names="auto_risk", values="Кількість", hole=0.52,
                    color="auto_risk", color_discrete_map=RISK_COLORS,
                    labels={"auto_risk":"Рівень ризику","Кількість":"Кількість заходів"},
                )
                fig_risk_pie.update_traces(textfont_size=12, marker=dict(line=dict(color="#ffffff", width=2)))
                fig_risk_pie.update_layout(**CHART_LAYOUT, height=320, showlegend=True)
                apply_safe_plotly_layout(fig_risk_pie, has_legend=True)
                render_plotly_chart(fig_risk_pie, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# Структура ризиків за ССП.
if breakdown_context is not None:
    _activate_dashboard_context(breakdown_context)
    with breakdown_content:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title" style="margin-top:0;">Структура ризиків за самостійними структурними підрозділами</div>', unsafe_allow_html=True)
        stacked = dep_active.groupby(["ssp_department", "auto_risk"]).size().reset_index(name="Кількість") if not dep_active.empty else pd.DataFrame()
        stacked_vis = stacked[stacked["auto_risk"] != "Не оцінюється"].copy() if not stacked.empty else pd.DataFrame()
        if stacked_vis.empty:
            st.info("Для останнього вибраного кварталу прогнозний ризик не оцінюється або недостатньо даних.")
        else:
            stacked_vis["_ssp_sort"] = stacked_vis["ssp_department"].apply(ssp_sort_value)
            stacked_vis = stacked_vis.sort_values("_ssp_sort")
            fig_risk_bar = px.bar(
                stacked_vis, x="ssp_department", y="Кількість", color="auto_risk",
                color_discrete_map=RISK_COLORS, barmode="stack",
                labels={"ssp_department":"Самостійний структурний підрозділ","auto_risk":"Ризик","Кількість":"Кількість заходів"},
            )
            fig_risk_bar.update_layout(**CHART_LAYOUT, height=310,
                                       xaxis=dict(tickangle=-35,tickfont=dict(size=9),showgrid=False,
                                                  categoryorder="array",categoryarray=stacked_vis["ssp_department"].drop_duplicates().tolist()),
                                       yaxis=dict(showgrid=True,gridcolor="#F7F9FC"))
            apply_safe_plotly_layout(fig_risk_bar, has_legend=True)
            render_plotly_chart(fig_risk_bar, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# Матриця виконання × прогнозоване досягнення річного плану.
if snapshot_context is not None and snapshot_monitoring_available:
    _activate_dashboard_context(snapshot_context)
    with snapshot_content:
        st.markdown("<hr class='vis-separator'>", unsafe_allow_html=True)
        st.markdown('<div class="section-title" style="margin-top:0;">Матриця виконання × прогноз</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-subtitle">X — виконання річного плану; Y — прогнозоване досягнення річного плану. '
            'Колір — рівень ризику; розмір — кількість заходів. Горизонтальна лінія Y=100% позначає прогнозоване досягнення плану.</div>',
            unsafe_allow_html=True,
        )
        matrix_df = execution_forecast_matrix.copy()
        if quarter_to_roman(snapshot_quarters[0]) == "IV":
            st.info("IV квартал — підсумок року. Прогнозна матриця більше не застосовується.")
        elif matrix_df.empty:
            st.info("Недостатньо валідних числових прогнозних даних для побудови матриці.")
        else:
            fig_matrix = px.scatter(
                matrix_df,
                x="execution", y="forecast_attainment", size="group_size", color="risk_level",
                text="group",
                color_discrete_map={
                    "Низький ризик":"#118847", "Середній ризик":"#F4B400",
                    "Високий ризик":"#FF7A45", "Критичний ризик":"#DC4A4A",
                    "Не оцінюється":"#8A96A8",
                },
                labels={"execution":"Виконання річного плану, %",
                        "forecast_attainment":"Прогнозоване досягнення річного плану, %",
                        "risk_level":"Ризик", "group_size":"Заходів", "group":"ССП"},
                hover_data={"execution": ":.1f", "forecast_attainment": ":.1f", "group_size":True, "preliminary":True},
            )
            fig_matrix.add_hline(y=100, line_dash="dash", line_color="#61708A", annotation_text="Річний план 100%")
            fig_matrix.update_traces(textposition="top center")
            fig_matrix.update_layout(**CHART_LAYOUT, height=540,
                                     xaxis=dict(range=[0,105], ticksuffix="%", showgrid=True, gridcolor="#F7F9FC"),
                                     yaxis=dict(ticksuffix="%", showgrid=True, gridcolor="#F7F9FC"))
            apply_safe_plotly_layout(fig_matrix, has_legend=True)
            render_plotly_chart(fig_matrix, use_container_width=True)
            if quarter_to_roman(snapshot_quarters[0]) == "I":
                st.caption("Попередній прогноз: сформовано лише за одним квартальним спостереженням.")


# ============================================================
# СЕКЦІЯ: ДИНАМІКА
# ============================================================

# Лінія динаміки з тих самих shared quarter snapshots.
if not presentation_mode and dynamics_context is not None:
    _activate_dashboard_context(dynamics_context)
    with dynamics_content:
        trend_long = dynamics_shared.copy()
        _render_section_summary(
            "Куди рухаємось",
            "Динаміка побудована з тих самих квартальних snapshot, що й поточні KPI; квартали без моніторингу залишаються пропусками.",
            tone="neutral",
        )
        st.markdown('<div class="section-title">Динаміка виконання</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle">{dynamics_label}</div>', unsafe_allow_html=True)
        if trend_long.empty:
            render_no_chart_data()
        else:
            fig_trend = px.line(
                trend_long, x="period", y="value", color="series", markers=True,
                color_discrete_map={
                    "Виконання за заходами":"#005BBB",
                    "Виконання за стратегічними цілями":"#4D8DFF",
                    "Покриття":"#00A8A8",
                },
                labels={"period":"Період","value":"Значення, %","series":"Показник"},
            )
            fig_trend.update_traces(line_width=2.5, marker_size=7, connectgaps=False)
            fig_trend.update_layout(**CHART_LAYOUT, height=360,
                                    xaxis=dict(showgrid=False, tickangle=-20),
                                    yaxis=dict(showgrid=True, gridcolor="#F7F9FC", ticksuffix="%"),
                                    legend_title_text="Показник")
            apply_safe_plotly_layout(fig_trend, has_legend=True)
            render_plotly_chart(fig_trend, use_container_width=True)

        st.markdown("<hr class='vis-separator'>", unsafe_allow_html=True)
        st.markdown('<div class="section-title" style="margin-top:0;">Зміна виконання стратегічних цілей</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-subtitle">Останній порівнюваний квартал мінус перший; без нормативу 25/50/75/100.</div>', unsafe_allow_html=True)
        goals_change = goal_comparison.copy()
        if goals_change.empty or not goals_change["change_by_tasks"].notna().any():
            render_no_chart_data()
        else:
            goals_change = goals_change[goals_change["change_by_tasks"].notna()].copy()
            goals_change["label"] = goals_change["goal_code"].astype(str)
            fig_change = px.bar(
                goals_change, x="change_by_tasks", y="label", orientation="h",
                color="change_by_tasks", color_continuous_scale=["#DC4A4A","#F7F9FC","#118847"],
                color_continuous_midpoint=0,
                text=goals_change["change_by_tasks"].apply(lambda v: f"{v:+.1f} в.п."),
                hover_data={"goal_name":True,"latest_by_tasks":":.1f","average_by_tasks":":.1f"},
                labels={"change_by_tasks":"Зміна, в.п.","label":"Стратегічна ціль"},
            )
            fig_change.update_layout(**CHART_LAYOUT, coloraxis_showscale=False,
                                     xaxis=dict(zeroline=True, zerolinecolor="#61708A"),
                                     yaxis=dict(title=None), height=max(280,len(goals_change)*38+80))
            render_plotly_chart(fig_change, use_container_width=True)

# Heatmap ССП × квартал — shared snapshots; valid 0% remains 0.
if dynamics_context is not None:
    _activate_dashboard_context(dynamics_context)
    with dynamics_content:
        st.markdown('<div class="section-title">Heatmap: самостійний структурний підрозділ × квартал</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle">{dynamics_label}</div>', unsafe_allow_html=True)
        heat_rows = []
        for (year, quarter), item in period_results.items():
            snap = item.get("snapshot", pd.DataFrame())
            if snap.empty or not bool(snap.get("monitoring_conducted", pd.Series([True])).iloc[0]):
                continue
            expanded = dashboard_filters_v2.expand_ssp_rows(snap, selected_department_indices or None)
            if expanded.empty:
                continue
            for ssp, group in expanded.groupby("ssp"):
                values = pd.to_numeric(group["execution_score"], errors="coerce").dropna()
                if values.empty:
                    continue
                heat_rows.append({
                    "Самостійний структурний підрозділ": str(ssp),
                    "Період": f"{year} {quarter}",
                    "Виконання": float(values.mean()),
                })
        heat_df = pd.DataFrame(heat_rows)
        if heat_df.empty:
            render_no_chart_data()
        else:
            pivot = heat_df.pivot_table(
                index="Самостійний структурний підрозділ", columns="Період",
                values="Виконання", aggfunc="mean"
            )
            pivot = pivot.loc[sorted(pivot.index, key=ssp_sort_value)]
            fig_heat = px.imshow(
                pivot, color_continuous_scale=["#FBE5E5", "#FDF3D8", "#E4F5EC"],
                zmin=0, zmax=100, aspect="auto", text_auto=".0f",
                labels=dict(x="Період", y="Підрозділ", color="Виконання, %"),
            )
            fig_heat.update_layout(**CHART_LAYOUT, height=max(300, len(pivot)*22+80),
                                   coloraxis_colorbar=dict(title="Викон., %", ticksuffix="%"),
                                   xaxis=dict(side="top", tickfont=dict(size=10)),
                                   yaxis=dict(tickfont=dict(size=9)), margin=dict(l=10,r=60,t=60,b=10))
            render_plotly_chart(fig_heat, use_container_width=True)

# Таймлайн дедлайнів.
if dynamics_context is not None:
    _activate_dashboard_context(dynamics_context)
    with dynamics_content:
        st.markdown('<div class="section-title">Таймлайн дедлайнів</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-subtitle">{snapshot_label} · Кількість заходів із дедлайном у кожному кварталі · розбивка за статусом виконання</div>',
            unsafe_allow_html=True,
        )

        # Стан кожного заходу беремо саме у кварталі його дедлайну, а не
        # лише з останнього snapshot. Так multi-period фільтр не губить III/IV.
        timeline_data = active_period_rows.copy()
        if "period_number" not in timeline_data.columns:
            timeline_data["period_number"] = timeline_data.apply(
                lambda row: core_period_number(
                    row.get("period_year"), row.get("period_quarter")
                ),
                axis=1,
            )
        timeline_data["end_num"] = timeline_data["end_period"].apply(parse_period)
        timeline_data["period_number"] = pd.to_numeric(
            timeline_data["period_number"], errors="coerce"
        )
        timeline_data["end_num"] = pd.to_numeric(
            timeline_data["end_num"], errors="coerce"
        )

        q_num_map = {"I": 1, "II": 2, "III": 3, "IV": 4}
        selected_deadline_periods = sorted({
            int(year) * 10 + q_num_map[quarter]
            for year in dynamics_years
            for quarter in dynamics_quarters
            if quarter in q_num_map
        })

        def end_num_to_label(n):
            y = int(n) // 10
            q_map = {1: "I", 2: "II", 3: "III", 4: "IV"}
            q = q_map.get(int(n) % 10, "?")
            return f"{y} {q}"

        deadline_order = [
            end_num_to_label(period) for period in selected_deadline_periods
        ]

        timeline_data = timeline_data[
            timeline_data["end_num"].isin(selected_deadline_periods)
            & (timeline_data["period_number"] == timeline_data["end_num"])
        ].copy()

        if selected_deadline_periods:
            def _tl_status(row):
                status = clean(row.get("status_display", ""))
                return (
                    status if status in core_statuses.MODEL_STATUSES
                    else core_statuses.ST_NOTDONE
                )

            if not timeline_data.empty:
                sort_cols = [
                    column for column in
                    ["code", "end_num", "request_submitted_at", "request_id"]
                    if column in timeline_data.columns
                ]
                if sort_cols:
                    timeline_data = timeline_data.sort_values(sort_cols)
                timeline_data = timeline_data.drop_duplicates(
                    subset=["code", "end_num"], keep="last"
                )
                timeline_data["deadline_label"] = timeline_data["end_num"].apply(
                    end_num_to_label
                )
                timeline_data["tl_status"] = timeline_data.apply(_tl_status, axis=1)
                tl_grouped = (
                    timeline_data
                    .groupby(["deadline_label", "tl_status"])
                    .size()
                    .reset_index(name="Кількість")
                )
            else:
                tl_grouped = pd.DataFrame(
                    columns=["deadline_label", "tl_status", "Кількість"]
                )

            tl_status_order = list(core_statuses.MODEL_STATUSES)
            full_index = pd.MultiIndex.from_product(
                [deadline_order, tl_status_order],
                names=["deadline_label", "tl_status"],
            )
            tl_grouped = (
                tl_grouped
                .set_index(["deadline_label", "tl_status"])
                .reindex(full_index, fill_value=0)
                .reset_index()
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
                category_orders={
                    "deadline_label": deadline_order,
                    "tl_status": tl_status_order,
                },
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
if finance_context is not None:
    _activate_dashboard_context(finance_context)
    with finance_content:
        finance_year = _finance_selected_year(finance_years)
        fin_measures = _prepare_dashboard_finance_measures(
            active,
            active_period_rows,
            finance_year,
        )
        fin_total = len(fin_measures)
        fin_db_rows = _finance_group_rows(fin_measures, "state")
        fin_mtd_rows = _finance_group_rows(fin_measures, "mtd")
        fin_other_rows = _finance_group_rows(fin_measures, "other")
        fin_no_rows = _finance_group_rows(fin_measures, "none")
        fin_budget_rows = _finance_group_rows(fin_measures, "budget")

        fin_db_count = len(fin_db_rows)
        fin_mtd_count = len(fin_mtd_rows)
        fin_other_count = len(fin_other_rows)
        fin_no_count = len(fin_no_rows)
        fin_budget_values = pd.to_numeric(
            fin_budget_rows.get("_finance_plan_bln", pd.Series(dtype=float)),
            errors="coerce",
        ).dropna()
        fin_budget_sum = float(fin_budget_values.sum()) if not fin_budget_values.empty else None
        fin_budget_count = len(fin_budget_rows)
        finance_year_note = (
            f"Для фінансових сум використано останній обраний рік — {finance_year}."
            if False
            else f"Фінансові суми наведено за {finance_year} рік."
        )

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">💰 Фінансування заходів</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-subtitle">{snapshot_label} · {finance_year_note} '
            'Планові обсяги — зі стратегічної матриці; фактичне освоєння — з єдиного фінансового модуля.</div>',
            unsafe_allow_html=True,
        )

        finance_detail_state_key = "dashboard_finance_detail_v1"
        st.session_state.setdefault(finance_detail_state_key, "")
        valid_finance_details = {"state", "mtd", "other", "none", "budget"}
        try:
            requested_finance_detail = str(st.query_params.get("finance_kpi", "") or "")
        except Exception:
            requested_finance_detail = ""
        if requested_finance_detail in valid_finance_details:
            st.session_state[finance_detail_state_key] = requested_finance_detail
        selected_finance_detail = st.session_state.get(finance_detail_state_key, "")

        render_kpi_grid(
            [
                {"key": "state", "title": "Заходів з Держбюджетом", "count": fin_db_count,
                 "percent": pct_value(fin_db_count, fin_total), "color": "kpi-blue"},
                {"key": "mtd", "title": "Заходів з МТД / партнерами", "count": fin_mtd_count,
                 "percent": pct_value(fin_mtd_count, fin_total), "color": "kpi-green"},
                {"key": "other", "title": "Небюджетні / інші джерела", "count": fin_other_count,
                 "percent": pct_value(fin_other_count, fin_total), "color": "kpi-yellow"},
                {"key": "none", "title": "Без фінансування", "count": fin_no_count,
                 "percent": pct_value(fin_no_count, fin_total), "color": "kpi-gray"},
                {"key": "budget", "title": f"Бюджет ДБ {finance_year} (млрд грн)",
                 "count": _finance_amount_text(fin_budget_sum) if fin_budget_sum is not None else "—",
                 "percent": f"{fin_budget_count} з {fin_total} заходів мають числовий план", "color": "kpi-blue"},
            ],
            interactive=True,
            query_key="finance_kpi",
        )

        if selected_finance_detail in valid_finance_details:
            detail_labels = {
                "state": "Заходи з державним бюджетом",
                "mtd": "Заходи з МТД / коштами партнерів",
                "other": "Заходи з небюджетними / іншими джерелами",
                "none": "Заходи без визначеного фінансування",
                "budget": f"Заходи з числовим планом державного бюджету за {finance_year} рік",
            }
            detail_rows = _finance_group_rows(fin_measures, selected_finance_detail)
            st.markdown(
                f'<div class="section-title" style="margin-top:18px;">{detail_labels[selected_finance_detail]}</div>',
                unsafe_allow_html=True,
            )
            if detail_rows.empty:
                st.info("Заходів у цій категорії за обраними параметрами немає.")
            else:
                render_dashboard_table(
                    _finance_detail_display(detail_rows, finance_year),
                    hide_index=True,
                )
                detail_plan_values = pd.to_numeric(
                    detail_rows["_finance_plan_bln"], errors="coerce"
                ).dropna()
                detail_fact_values = pd.to_numeric(
                    detail_rows["_finance_fact_bln"], errors="coerce"
                ).dropna()
                detail_plan_sum = float(detail_plan_values.sum()) if not detail_plan_values.empty else None
                detail_fact_sum = float(detail_fact_values.sum()) if not detail_fact_values.empty else None
                st.caption(
                    f"Унікальних заходів: {detail_rows['code'].nunique()}. "
                    f"Сума плану: {_finance_amount_text(detail_plan_sum)} млрд грн; "
                    f"сума факту: {_finance_amount_text(detail_fact_sum)} млрд грн. "
                    "Суми обчислено до форматування рядків."
                )
            if st.button(
                "← Повернутися",
                key="dashboard_finance_detail_back_v1",
            ):
                st.session_state[finance_detail_state_key] = ""
                try:
                    if "finance_kpi" in st.query_params:
                        del st.query_params["finance_kpi"]
                except Exception as exc:
                    log_cosmetic_error("Скидання деталізації фінансових KPI", exc)
                pass  # no explicit rerun: the triggering user action completes in this run

        st.markdown('<div style="margin-top:18px;"></div>', unsafe_allow_html=True)

        fin_col1, fin_col2 = st.columns([1, 1.5])
        with fin_col1:
            fin_donut_data = pd.DataFrame({
                "Тип": ["Державний бюджет", "МТД / кошти партнерів", "Небюджетні / інші", "Без фінансування"],
                "Кількість": [fin_db_count, fin_mtd_count, fin_other_count, fin_no_count],
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
                    labels={"Тип": "Джерело фінансування", "Кількість": "Кількість заходів"},
                )
                fig_donut.update_traces(
                    textfont_size=11,
                    textposition="outside",
                    texttemplate="%{label}: %{percent:.1%}",
                    marker=dict(line=dict(color="#ffffff", width=2)),
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
            goal_budget_source = fin_measures[
                pd.to_numeric(fin_measures["_finance_plan_bln"], errors="coerce") > 0
            ].copy() if not fin_measures.empty else pd.DataFrame()
            if not goal_budget_source.empty and "goal_code" in goal_budget_source.columns:
                goal_budget = (
                    goal_budget_source
                    .groupby("goal_code", dropna=False)
                    .agg(
                        Бюджет=("_finance_plan_bln", "sum"),
                        Заходів=("code", "nunique"),
                    )
                    .reset_index()
                )
                goal_budget["_sort"] = goal_budget["goal_code"].apply(code_sort_key)
                goal_budget = goal_budget.sort_values("_sort")
                goal_budget["label"] = goal_budget["goal_code"].astype(str)
                fig_budget_bar = px.bar(
                    goal_budget,
                    x="label",
                    y="Бюджет",
                    text=goal_budget["Бюджет"].apply(lambda value: _finance_amount_text(value, 3)),
                    hover_data={"Заходів": True},
                    color="Бюджет",
                    color_continuous_scale=["#BFD3F2", "#005BBB"],
                    labels={"label": "Стратегічна ціль", "Бюджет": "млрд грн"},
                )
                fig_budget_bar.update_traces(textposition="outside", textfont_size=10, marker_line_width=0)
                fig_budget_bar.update_layout(
                    **CHART_LAYOUT,
                    title=dict(
                        text=f"Бюджет ДБ {finance_year} за стратегічними цілями (млрд грн)",
                        font=dict(size=14, color="#032A63"),
                        x=0,
                    ),
                    height=300,
                    xaxis=dict(showgrid=False, tickangle=0),
                    yaxis=dict(showgrid=True, gridcolor="#F7F9FC", title="млрд грн"),
                    coloraxis_showscale=False,
                    margin=dict(l=10, r=10, t=40, b=40),
                )
                render_plotly_chart(fig_budget_bar, use_container_width=True)
                st.caption("Лише унікальні заходи з наявним числовим планом бюджету.")
            else:
                st.info(f"Числових даних про бюджет ДБ {finance_year} за обраними фільтрами немає.")

        st.markdown("<hr class='vis-separator'>", unsafe_allow_html=True)

        elasticity_source = fin_measures.copy()
        if not elasticity_source.empty:
            elasticity_source["_elasticity_num"] = pd.to_numeric(
                elasticity_source["_finance_elasticity"], errors="coerce"
            )
            elasticity_source = elasticity_source.dropna(subset=["_elasticity_num"])
        if elasticity_source.empty:
            st.info(
                "Дані про еластичність з'являться після внесення фактичного освоєння бюджету "
                "(наразі відсутнє)."
            )
        else:
            elasticity_by_goal = (
                elasticity_source
                .groupby(["goal_code", "strategic_goal"], dropna=False)
                .agg(
                    Середній_коефіцієнт=("_elasticity_num", "mean"),
                    Заходів=("code", "nunique"),
                )
                .reset_index()
            )
            elasticity_by_goal["_sort"] = elasticity_by_goal["goal_code"].apply(code_sort_key)
            elasticity_by_goal = elasticity_by_goal.sort_values("_sort")
            elasticity_by_goal["label"] = elasticity_by_goal["goal_code"].astype(str)
            fig_elasticity = px.bar(
                elasticity_by_goal,
                x="label",
                y="Середній_коефіцієнт",
                text=elasticity_by_goal["Середній_коефіцієнт"].apply(lambda value: f"{value:.2f}"),
                hover_data={"strategic_goal": True, "Заходів": True},
                labels={
                    "label": "Стратегічна ціль",
                    "Середній_коефіцієнт": "Середній коефіцієнт еластичності",
                    "strategic_goal": "Назва стратегічної цілі",
                },
                color="Середній_коефіцієнт",
                color_continuous_scale=["#BFD3F2", "#005BBB"],
            )
            fig_elasticity.update_traces(textposition="outside", marker_line_width=0)
            fig_elasticity.add_hline(
                y=1.0,
                line_dash="dash",
                line_color="#F4B400",
                annotation_text="Баланс 1,0",
                annotation_position="top left",
            )
            fig_elasticity.update_layout(
                **CHART_LAYOUT,
                title=dict(
                    text=f"Коефіцієнт еластичності за стратегічними цілями · {finance_year}",
                    font=dict(size=14, color="#032A63"),
                    x=0,
                ),
                height=340,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#F7F9FC", title="Коефіцієнт"),
                coloraxis_showscale=False,
                margin=dict(l=10, r=10, t=50, b=40),
            )
            render_plotly_chart(fig_elasticity, use_container_width=True)
            st.caption(
                "1,0 — фінансування відповідає результату; понад 1,0 — освоєння випереджає "
                "результат; менше 1,0 — результат випереджає витрати."
            )

        st.markdown("<hr class='vis-separator'>", unsafe_allow_html=True)

        kpkvk_source = fin_measures[
            fin_measures["_finance_kpkvk"].astype(str).str.strip() != ""
        ].copy() if not fin_measures.empty else pd.DataFrame()
        if not kpkvk_source.empty:
            kpkvk_table = (
                kpkvk_source
                .groupby("_finance_kpkvk", dropna=False)
                .agg(
                    Заходів=("code", "nunique"),
                    План=("_finance_plan_bln", lambda values: values.dropna().sum() if values.notna().any() else None),
                    Факт=("_finance_fact_bln", lambda values: values.dropna().sum() if values.notna().any() else None),
                )
                .reset_index()
                .rename(columns={"_finance_kpkvk": "КПКВК"})
                .sort_values("Заходів", ascending=False)
                .reset_index(drop=True)
            )
            kpkvk_table.index = kpkvk_table.index + 1
            kpkvk_display = kpkvk_table.copy()
            kpkvk_display[f"План {finance_year} (млрд грн)"] = kpkvk_display["План"].apply(_finance_amount_text)
            kpkvk_display[f"Факт {finance_year} (млрд грн)"] = kpkvk_display["Факт"].apply(_finance_amount_text)
            st.markdown(
                '<div class="section-title" style="margin-top:0;">Топ КПКВК за кількістю заходів</div>',
                unsafe_allow_html=True,
            )
            render_dashboard_table(
                kpkvk_display[[
                    "КПКВК",
                    "Заходів",
                    f"План {finance_year} (млрд грн)",
                    f"Факт {finance_year} (млрд грн)",
                ]],
                hide_index=False,
                table_width="99%",
            )
            st.caption(
                "Кожен захід у межах КПКВК враховано один раз; суми обчислено за числовими значеннями."
            )
        else:
            st.info("КПКВК за обраними параметрами не визначено.")

        st.markdown("</div>", unsafe_allow_html=True)

# Таблиця фінансових даних.
if finance_context is not None:
    _activate_dashboard_context(finance_context)
    with finance_content:
        finance_year = _finance_selected_year(finance_years)
        fin_measures = _prepare_dashboard_finance_measures(
            active,
            active_period_rows,
            finance_year,
        )
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Таблиця заходів: фінансові дані</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-subtitle">Фінансові відомості за {finance_year} рік; '
            'факт та еластичність з’являються після внесення файлу фактичного освоєння.</div>',
            unsafe_allow_html=True,
        )
        financed_table_rows = fin_measures[
            fin_measures["_finance_types"].apply(
                lambda values: isinstance(values, list)
                and any(value != "Без фінансування" for value in values)
            )
        ].copy() if not fin_measures.empty else pd.DataFrame()

        render_dashboard_table(
            _finance_detail_display(financed_table_rows, finance_year),
            hide_index=True,
            empty_message="За обраними параметрами заходів із фінансуванням немає.",
            max_cell_height=72,
            table_width="fit-columns",
            column_widths={
                "Код": 72,
                "Захід": 180,
                "Головний ССП": 105,
                "Статус виконання": 120,
                "КПКВК": 90,
                "Інше джерело": 160,
                f"План {finance_year}, млрд грн": 125,
                f"Факт {finance_year}, млрд грн": 125,
                "% фінансового виконання": 135,
                "Стан виконання заходу, %": 145,
                "Коефіцієнт еластичності": 135,
            },
            scroll_columns={"Захід"},
        )
        st.caption(
            "План — стратегічні дані за обраний рік; факт — єдиний індекс core.finance."
        )
        st.markdown("</div>", unsafe_allow_html=True)

# Проблемні заходи — v2 attention signals, not an execution <75 threshold.
if breakdown_context is not None:
    _activate_dashboard_context(breakdown_context)
    with breakdown_content:
        with st.expander("Проблемні заходи", expanded=False):
            problem_mask = dashboard_risk_v2.attention_mask(active)
            risk_table = active.loc[problem_mask].copy()
            if risk_table.empty:
                st.success("Заходів із суттєвими v2 attention signals за обраний період не виявлено.")
            else:
                def _attention_reason(row):
                    parts = []
                    if row.get("risk_level") in dashboard_risk_v2.RISKY_LEVELS:
                        parts.append(clean(row.get("risk_reason")) or clean(row.get("risk_explanation")))
                    if bool(row.get("missing_required_submission")):
                        parts.append("Відсутнє обов’язкове подання за активний квартал.")
                    if bool(row.get("final_missing_result")):
                        parts.append("Захід завершився без валідного фінального результату.")
                    if bool(row.get("data_quality_conflict")):
                        parts.append(clean(row.get("data_quality_message")) or "Конфлікт даних.")
                    if clean(row.get("forecast_kind")) == "final" and not bool(row.get("result_achieved")):
                        parts.append("Фінальний результат не досягнуто.")
                    return " ".join(dict.fromkeys(p for p in parts if p))
                risk_table["Причина / пояснення"] = risk_table.apply(_attention_reason, axis=1)
                problem_display = risk_table.rename(columns={
                    "period_label":"Період", "code":"Код", "name":"Захід", "indicator":"Індикатор",
                    "department":"Головний ССП", "status_display":"Статус", "execution_score":"Виконання, %",
                    "forecast_attainment_pct":"Прогнозоване досягнення, %", "pace_sufficiency_pct":"Достатність темпу, %",
                    "risk_level":"Ризик", "data_quality_conflict":"Data-quality conflict",
                })
                render_dashboard_table(
                    problem_display[["Період","Код","Захід","Індикатор","Головний ССП","Статус",
                                     "Виконання, %","Прогнозоване досягнення, %","Достатність темпу, %",
                                     "Ризик","Причина / пояснення","Data-quality conflict"]],
                    hide_index=True, max_cell_height=76, table_width="fit-columns",
                    scroll_columns={"Захід","Індикатор","Причина / пояснення"},
                )
                st.caption("Для I кварталу прогнозні risk signals є попередніми; для IV кварталу показуються фінальні результати, а не прогнозний ризик.")

# Повна таблиця заходів у зрізі — shared v2 fields.
if breakdown_context is not None:
    _activate_dashboard_context(breakdown_context)
    with breakdown_content:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Повна таблиця заходів у зрізі</div>', unsafe_allow_html=True)
        full = active.copy()
        full["Причина / пояснення"] = full.apply(
            lambda row: clean(row.get("risk_reason")) or clean(row.get("data_quality_message")) or clean(row.get("final_outcome")),
            axis=1,
        )
        full = full.rename(columns={
            "period_label":"Період", "code":"Код", "name":"Захід", "indicator":"Індикатор",
            "unit":"Одиниця виміру", "product_type":"Тип продукту", "department":"Головний ССП",
            "source_national":"Джерело даних", "start_period":"Початок", "end_period":"Кінець",
            "annual_target":"Річний план", "actual":"Факт", "status_display":"Статус",
            "execution_score":"Виконання, %", "raw_attainment_pct":"Raw attainment, %",
            "forecast_attainment_pct":"Прогнозоване досягнення, %", "pace_sufficiency_pct":"Достатність темпу, %",
            "risk_level":"Ризик", "data_quality_conflict":"Data-quality conflict",
        })
        columns = ["Період","Код","Захід","Індикатор","Одиниця виміру","Тип продукту","Головний ССП",
                   "Джерело даних","Початок","Кінець","Річний план","Факт","Статус","Виконання, %",
                   "Raw attainment, %","Прогнозоване досягнення, %","Достатність темпу, %","Ризик",
                   "Причина / пояснення","Data-quality conflict"]
        render_dashboard_table(
            full[columns], hide_index=True, max_cell_height=76, table_width="fit-columns",
            column_widths={"Період":82,"Код":72,"Захід":190,"Індикатор":190,"Одиниця виміру":105,
                           "Тип продукту":105,"Головний ССП":100,"Джерело даних":120,"Початок":90,"Кінець":90,
                           "Річний план":110,"Факт":110,"Статус":120,"Виконання, %":110,"Raw attainment, %":115,
                           "Прогнозоване досягнення, %":145,"Достатність темпу, %":130,"Ризик":115,
                           "Причина / пояснення":210,"Data-quality conflict":120},
            scroll_columns={"Захід","Індикатор","Причина / пояснення"},
        )
        st.markdown("</div>", unsafe_allow_html=True)

# ============================================================
# МЕТОДОЛОГІЯ ТА ТЕСТОВИЙ АВТОМАТИЧНИЙ ВИСНОВОК
# ============================================================

with st.expander("Методологія розрахунку"):
    st.markdown("""
    <div class="methodology-box">
    <strong>Quarter snapshot</strong> є єдиним джерелом розрахунків Dashboard. Майбутні заходи не входять у population; активні використовують тільки дані поточного кварталу; завершені можуть переносити останній валідний погоджений результат. Якщо період застосовності визначити неможливо, захід має explicit state <em>unknown period</em> і не отримує автоматично 0%.<br><br>

    <strong>Виконання заходу.</strong> Для числових plan/fact використовується факт / річний план × 100 зі стелею 100% для execution score; raw attainment зберігається окремо. Для якісних результатів: «Виконано» = 100%, «Частково виконано» = 75%, «Не виконано» = 0%; «Не настав час» та «Втратило актуальність» виключаються. Активний захід без обов'язкового поточного подання отримує 0%, але coverage показується окремо. Завершений захід без жодного валідного фінального результату також отримує 0% та окремий data-quality signal.<br><br>

    <strong>Дві оцінки Стратегічного плану.</strong> «За заходами» — середнє execution score оцінених заходів. «За стратегічними цілями» — ієрархічна оцінка measure → task → goal → plan. Для кожної стратегічної цілі Dashboard окремо показує оцінку за заходами та за завданнями.<br><br>

    <strong>Прогноз і темп</strong> застосовуються лише там, де є достатня числова історія. У I кварталі прогноз є попереднім. У II–III кварталах використовується безпосередньо попередній валідний квартал; locked / monitoring-not-conducted observation повністю виключається з history. Від'ємний приріст зберігається як signal, але прогноз річного факту не може бути нижчим за 0. У IV кварталі прогнозний ризик не розраховується — показується підсумок року за фактичним результатом.<br><br>

    <strong>Ризик</strong> визначається за прогнозованим досягненням річного плану: понад 85% — низький; 51–85% — середній; 20–менше 51% — високий; менше 20% — критичний. Ризик у multi-period розрізах показується станом на останній вибраний квартал і не усереднюється між кварталами.<br><br>

    <strong>Порівняння результатів.</strong> Average — середнє готових квартальних KPI з однаковою вагою кварталів; Latest — останній валідний вибраний квартал; Change — Latest мінус earliest comparable. Якщо використано status filter, cohort фіксується за останнім вибраним кварталом і той самий набір кодів використовується для попередніх кварталів, average та change.<br><br>

    <strong>Період без моніторингу</strong> не перетворюється на 0% і не використовується як previous fact, у прогнозі, темпі чи risk trajectory. У динаміці він залишається пропуском.
    </div>
    """, unsafe_allow_html=True)


if snapshot_context is not None and snapshot_monitoring_available:
    _activate_dashboard_context(snapshot_context)

def _trajectory_number(value):
    text = clean(value).replace("\u00a0", " ").replace(" ", "").replace(",", ".")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _geometric_path(start_year, start_value, end_year, end_value):
    """Year-by-year geometric path, matching the annual-rate idea used by MіО."""
    try:
        start_year, end_year = int(start_year), int(end_year)
        start_value, end_value = float(start_value), float(end_value)
    except (TypeError, ValueError):
        return {}
    years = end_year - start_year
    if years <= 0 or start_value <= 0 or end_value <= 0:
        return {}
    rate = (end_value / start_value) ** (1.0 / years)
    return {year: start_value * (rate ** (year - start_year)) for year in range(start_year, end_year + 1)}


def _indicator_trajectory_rows():
    """Індикатори для графіків із урахуванням поточної сукупності фільтрів.

    ССП/Ціль/Завдання застосовуються безпосередньо до індикаторів. Фільтри,
    які існують лише на рівні заходів (тип продукту, статус, фінансування,
    КПКВК, заступник), звужують індикатори до Цілей/Завдань, що реально
    залишилися у відфільтрованому наборі Dashboard.
    """
    indicators = strat_df[
        strat_df["object_type"].isin(["goal_indicator", "task_indicator"])
    ].copy()
    if indicators.empty:
        return indicators

    indicators = indicators[
        indicators["indicator"].astype(str).str.strip().ne("")
    ].copy()

    if selected_department_indices:
        wanted = {str(x) for x in selected_department_indices}
        indicators = indicators[indicators.apply(
            lambda row: bool(
                wanted.intersection(
                    set(split_department_indices(row.get("resp_main", "")))
                    | set(split_department_indices(row.get("resp_co_1", "")))
                    | set(split_department_indices(row.get("resp_co_2", "")))
                )
            ),
            axis=1,
        )]

    if selected_goals:
        wanted_goals = {str(v).strip() for v in selected_goals}
        indicators = indicators[
            indicators["parent_goal_code"].astype(str).str.strip().isin(wanted_goals)
        ]

    if selected_tasks:
        wanted_tasks = {str(v).strip() for v in selected_tasks}
        indicators = indicators[
            indicators["parent_task_code"].astype(str).str.strip().isin(wanted_tasks)
        ]

    measure_only_filters = any([
        bool(selected_product_types),
        bool(selected_deputies),
        bool(selected_statuses),
        bool(selected_financing),
        bool(selected_kpkvk),
    ])
    if measure_only_filters and not indicators.empty:
        active_goal_codes = set()
        active_task_codes = set()
        if isinstance(active, pd.DataFrame) and not active.empty:
            if "goal_code" in active.columns:
                active_goal_codes = set(active["goal_code"].astype(str).str.strip())
            if "task_code" in active.columns:
                active_task_codes = set(active["task_code"].astype(str).str.strip())
        indicators = indicators[indicators.apply(
            lambda row: (
                (clean(row.get("object_type")) == "goal_indicator"
                 and clean(row.get("parent_goal_code")) in active_goal_codes)
                or
                (clean(row.get("object_type")) == "task_indicator"
                 and clean(row.get("parent_task_code")) in active_task_codes)
            ),
            axis=1,
        )]

    if indicators.empty:
        return indicators

    indicators["_sort_code"] = indicators["code"].apply(code_sort_key)
    indicators["_sort_indicator"] = indicators["indicator"].astype(str).str.casefold()
    return indicators.sort_values(
        ["_sort_code", "_sort_indicator"], kind="stable"
    ).drop(columns=["_sort_code", "_sort_indicator"]).copy()


def _build_indicator_trajectory(row):
    code = clean(row.get("code"))
    indicator_name = clean(row.get("indicator"))
    code_key, indicator_key = monitoring_data.indicator_identity_key(code, indicator_name)

    actual = {}
    for year, col in [(2021, "base_2021"), (2024, "fact_2024"), (2025, "fact_2025")]:
        value = _trajectory_number(row.get(col))
        if value is not None:
            actual[year] = value

    req = _indicator_requests_effective.copy()
    if not req.empty:
        req = req[req.apply(
            lambda item: monitoring_data.indicator_identity_key(
                item.get("strat_code", ""), item.get("indicator_name", "")
            ) == (code_key, indicator_key),
            axis=1,
        )].copy()
        if not req.empty:
            req["_year"] = pd.to_numeric(req.get("year"), errors="coerce")
            req["_value"] = req.apply(
                lambda r: _trajectory_number(r.get("numeric_value"))
                if _trajectory_number(r.get("numeric_value")) is not None
                else _trajectory_number(r.get("value_text")),
                axis=1,
            )
            req["_date"] = pd.to_datetime(req.get("as_of_date"), errors="coerce")
            req["_submitted"] = pd.to_datetime(
                req.get("submitted_at"), errors="coerce", utc=True
            )
            req["_id"] = pd.to_numeric(req.get("id"), errors="coerce").fillna(-1)
            req = req[req["_year"].notna() & req["_value"].notna()].copy()
            if not req.empty:
                latest = (
                    req.sort_values(
                        ["_year", "_date", "_submitted", "_id"],
                        na_position="first",
                    )
                    .groupby("_year", as_index=False, sort=False)
                    .tail(1)
                )
                for _, item in latest.iterrows():
                    actual[int(item["_year"])] = float(item["_value"])

    target_2028 = _trajectory_number(row.get("strategic_target_2028"))
    target_2034 = _trajectory_number(row.get("strategic_target_2034"))

    numeric_actuals = sorted(
        (int(year), float(value))
        for year, value in actual.items()
        if value is not None
    )
    positive_actuals = [
        (year, value) for year, value in numeric_actuals if value > 0
    ]
    anchor_year = numeric_actuals[-1][0] if numeric_actuals else None
    anchor_value = numeric_actuals[-1][1] if numeric_actuals else None

    # Необхідна траєкторія завжди починається від ОСТАННЬОГО факту.
    required = {}
    required_rates = []
    if anchor_year is not None and anchor_value is not None and anchor_value > 0:
        if anchor_year < 2028 and target_2028 is not None and target_2028 > 0:
            segment = _geometric_path(
                anchor_year, anchor_value, 2028, target_2028
            )
            required.update(segment)
            if segment:
                required_rates.append((
                    anchor_year,
                    2028,
                    (target_2028 / anchor_value) ** (1 / (2028 - anchor_year)) - 1,
                ))
            if target_2034 is not None and target_2034 > 0:
                segment_2034 = _geometric_path(
                    2028, target_2028, 2034, target_2034
                )
                required.update(segment_2034)
                if segment_2034:
                    required_rates.append((
                        2028,
                        2034,
                        (target_2034 / target_2028) ** (1 / 6) - 1,
                    ))
        elif anchor_year < 2034 and target_2034 is not None and target_2034 > 0:
            segment = _geometric_path(
                anchor_year, anchor_value, 2034, target_2034
            )
            required.update(segment)
            if segment:
                required_rates.append((
                    anchor_year,
                    2034,
                    (target_2034 / anchor_value) ** (1 / (2034 - anchor_year)) - 1,
                ))
        elif anchor_year < 2028 and target_2034 is not None and target_2034 > 0:
            segment = _geometric_path(
                anchor_year, anchor_value, 2034, target_2034
            )
            required.update(segment)
            if segment:
                required_rates.append((
                    anchor_year,
                    2034,
                    (target_2034 / anchor_value) ** (1 / (2034 - anchor_year)) - 1,
                ))

    # Червоний прогноз: геометричний темп між ДВОМА ОСТАННІМИ
    # позитивними фактичними значеннями.
    forecast = {}
    current_rate = None
    if len(positive_actuals) >= 2:
        previous_year, previous_value = positive_actuals[-2]
        latest_year, latest_value = positive_actuals[-1]
        years_elapsed = latest_year - previous_year
        if years_elapsed > 0:
            current_rate = (
                latest_value / previous_value
            ) ** (1.0 / years_elapsed)
            horizon_year = (
                2034 if target_2034 is not None
                else (2028 if target_2028 is not None else latest_year + 5)
            )
            if horizon_year >= latest_year:
                forecast = {
                    year: latest_value * (
                        current_rate ** (year - latest_year)
                    )
                    for year in range(latest_year, int(horizon_year) + 1)
                }

    return (
        actual,
        required,
        forecast,
        required_rates,
        current_rate,
        target_2028,
        target_2034,
        anchor_year,
        anchor_value,
    )


def _trajectory_value_label(value):
    try:
        return f"{float(value):.2f}".replace(".", ",")
    except (TypeError, ValueError):
        return ""


def _trajectory_marker_sizes(values, *, base=28, maximum=40):
    """Compact circles that still keep a two-decimal value readable inside."""
    sizes = []
    for value in values:
        label = _trajectory_value_label(value)
        sizes.append(min(maximum, max(base, 12 + len(label) * 3.5)))
    return sizes


def _render_indicator_trajectory_section():
    indicators = _indicator_trajectory_rows()
    st.markdown(
        '<div class="section-title">Траєкторія індикаторів стратегічних цілей і завдань</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="section-subtitle">Синя лінія — фактичні значення. '
        'Помаранчева — необхідна траєкторія від останнього факту до орієнтирів '
        '2028/2034. Червоний пунктир — прогноз за фактичним середньорічним '
        'темпом. Поява нового факту автоматично переносить точку старту обох '
        'прогнозних ліній.</div>',
        unsafe_allow_html=True,
    )
    if indicators.empty:
        st.info(
            "За застосованими фільтрами індикаторів Цілей/Завдань не знайдено."
        )
        return

    indicators = indicators.reset_index(drop=True)
    labels = [
        f"{clean(r.get('code'))} — {clean(r.get('indicator'))}"
        for _, r in indicators.iterrows()
    ]
    chosen = st.selectbox(
        "Індикатор для графіка",
        list(range(len(indicators))),
        format_func=lambda i: labels[i],
        key="dashboard_indicator_trajectory_choice",
    )
    row = indicators.iloc[int(chosen)]
    (
        actual,
        required,
        forecast,
        required_rates,
        current_rate,
        t28,
        t34,
        anchor_year,
        anchor_value,
    ) = _build_indicator_trajectory(row)

    if not actual and t28 is None and t34 is None:
        st.info(
            "Для цього індикатора немає числових даних, які можна коректно "
            "побудувати на лінійному графіку."
        )
        return

    fact_color = "#005BBB"
    required_color = "#E66A00"
    forecast_color = "#DC2626"
    target_border = "#8F3A00"

    fig = go.Figure()

    if actual:
        years = sorted(actual)
        values = [actual[y] for y in years]
        fig.add_trace(go.Scatter(
            x=years,
            y=values,
            mode="lines+markers+text",
            name="Фактичні значення",
            line=dict(color=fact_color, width=3),
            marker=dict(
                color=fact_color,
                size=_trajectory_marker_sizes(values),
                symbol="circle",
                line=dict(color="#FFFFFF", width=2),
            ),
            text=[_trajectory_value_label(value) for value in values],
            textposition="middle center",
            textfont=dict(color="#FFFFFF", size=7, family="Arial Black"),
            hovertemplate="Факт %{x}: %{y:.2f}<extra></extra>",
        ))

    if required:
        years = sorted(required)
        values = [required[y] for y in years]
        fig.add_trace(go.Scatter(
            x=years,
            y=values,
            mode="lines+markers+text",
            name="Необхідна траєкторія",
            line=dict(color=required_color, width=3),
            marker=dict(
                color=required_color,
                size=[
                    0 if anchor_year is not None and y == anchor_year
                    else _trajectory_marker_sizes(
                        [required[y]], base=26, maximum=38
                    )[0]
                    for y in years
                ],
                symbol="circle",
                line=dict(color="#FFFFFF", width=2),
            ),
            text=[
                "" if anchor_year is not None and y == anchor_year
                else _trajectory_value_label(required[y])
                for y in years
            ],
            textposition="middle center",
            textfont=dict(color="#FFFFFF", size=7, family="Arial Black"),
            hovertemplate="Необхідно %{x}: %{y:.2f}<extra></extra>",
        ))

    if forecast:
        years = sorted(forecast)
        values = [forecast[y] for y in years]
        fig.add_trace(go.Scatter(
            x=years,
            y=values,
            mode="lines+markers+text",
            name="Прогноз за нинішнім темпом",
            line=dict(color=forecast_color, width=3, dash="dash"),
            marker=dict(
                color=forecast_color,
                size=[
                    0 if anchor_year is not None and y == anchor_year
                    else _trajectory_marker_sizes(
                        [forecast[y]], base=26, maximum=38
                    )[0]
                    for y in years
                ],
                symbol="circle",
                line=dict(color="#FFFFFF", width=2),
            ),
            text=[
                "" if anchor_year is not None and y == anchor_year
                else _trajectory_value_label(forecast[y])
                for y in years
            ],
            textposition="middle center",
            textfont=dict(color="#FFFFFF", size=7, family="Arial Black"),
            hovertemplate="Прогноз %{x}: %{y:.2f}<extra></extra>",
        ))

    if t28 is not None:
        target_label = _trajectory_value_label(t28)
        fig.add_trace(go.Scatter(
            x=[2028],
            y=[t28],
            mode="markers+text",
            marker=dict(
                size=min(44, max(36, 14 + len(target_label) * 3.5)),
                symbol="circle",
                color=required_color,
                line=dict(color=target_border, width=3),
            ),
            text=[target_label],
            textposition="middle center",
            textfont=dict(color="#FFFFFF", size=8, family="Arial Black"),
            name="Орієнтир 2028",
            hovertemplate="Орієнтир 2028: %{y:.2f}<extra></extra>",
        ))
    if t34 is not None:
        target_label = _trajectory_value_label(t34)
        fig.add_trace(go.Scatter(
            x=[2034],
            y=[t34],
            mode="markers+text",
            marker=dict(
                size=min(44, max(36, 14 + len(target_label) * 3.5)),
                symbol="circle",
                color=required_color,
                line=dict(color=target_border, width=3),
            ),
            text=[target_label],
            textposition="middle center",
            textfont=dict(color="#FFFFFF", size=8, family="Arial Black"),
            name="Орієнтир 2034",
            hovertemplate="Орієнтир 2034: %{y:.2f}<extra></extra>",
        ))

    fig.update_layout(
        height=470,
        xaxis=dict(title="Рік", dtick=1),
        yaxis=dict(title=clean(row.get("unit")) or "Значення"),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.03, xanchor="left", x=0
        ),
        margin=dict(l=55, r=25, t=55, b=50),
    )
    render_plotly_chart(fig, use_container_width=True)

    rate_bits = []
    for sy, ey, rate in required_rates:
        rate_bits.append(
            f"потрібний середньорічний темп {sy}–{ey}: {rate*100:+.2f}%"
        )
    if current_rate is not None:
        rate_bits.append(
            f"фактичний середньорічний темп: {(current_rate-1)*100:+.2f}%"
        )
    if anchor_year is not None and anchor_value is not None:
        rate_bits.insert(
            0,
            f"точка перебудови: факт {anchor_year} = "
            f"{_trajectory_value_label(anchor_value)}",
        )
    if rate_bits:
        st.caption(" · ".join(rate_bits))


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

        _filtered_strat = dashboard_filters_v2.filter_measures(
            measures_all,
            ssp=selected_department_indices, goals=selected_goals, tasks=selected_tasks,
            measure_codes=selected_measures, product_types=selected_product_types,
            deputies=selected_deputies, sources=selected_sources, financing=selected_financing,
            kpkvk=selected_kpkvk,
        )
        _summary_pairs = [(_py, _pq), (_cy, _cq)]
        _summary_results = dashboard_breakdowns_v2.build_period_results(
            _filtered_strat, requests_df, _summary_pairs, stable_statuses=selected_statuses,
            period_sources=_build_period_source_overrides(_summary_pairs),
        )
        _prev = _summary_results.get((_py, _pq), {}).get("snapshot", pd.DataFrame())
        _current_for_summary = _summary_results.get((_cy, _cq), {}).get("snapshot", active)

        def _counts(df):
            if df is None or df.empty or "status" not in df.columns:
                return {}
            return df["status"].astype(str).value_counts().to_dict()

        _cur_c, _prev_c = _counts(_current_for_summary), _counts(_prev)
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
            (_current_for_summary["status"].astype(str).isin(["", "Не подано"])).sum()
        ) if "status" in _current_for_summary.columns else 0
        _not_yet = int(
            (_current_for_summary["status"].astype(str) == "Не настав час").sum()
        ) if "status" in _current_for_summary.columns else 0

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


# Окремий керівний блок індикаторів Цілей/Завдань. Він використовує
# фактичні подання та довгострокові орієнтири, але не змінює формули МіО.
# Блок вставляється саме в секцію «Динаміка», а не в кінець сторінки.
if dynamics_context is not None:
    _activate_dashboard_context(dynamics_context)
    with dynamics_content:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        _render_indicator_trajectory_section()
        st.markdown('</div>', unsafe_allow_html=True)

if snapshot_context is not None and snapshot_monitoring_available:
    _render_dash_auto_summary()

render_footer()
