import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime
import re

st.set_page_config(page_title="Dashboard", layout="wide")

st.logo(
    "assets/Мінекономіки.png",
    size="large"
)

FILE_PATH = "Під моніторинг СП.xlsx"
SHEET_NAME = "Страт_матриця"

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

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
    background: #f0f4f9;
}

/* Subtle geometric background pattern */
.stApp::before {
    content: "";
    position: fixed;
    inset: 0;
    background-image:
        radial-gradient(circle at 15% 15%, rgba(0,91,187,0.06) 0%, transparent 40%),
        radial-gradient(circle at 85% 80%, rgba(255,213,0,0.06) 0%, transparent 40%),
        radial-gradient(circle at 50% 50%, rgba(0,91,187,0.02) 0%, transparent 60%);
    pointer-events: none;
    z-index: 0;
}

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
    background: linear-gradient(90deg, #005BBB 50%, #FFD700 50%);
    margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(0,91,187,0.15);
}

/* ── Ministry label ── */
.ministry-label {
    text-align: right;
    color: #334155;
    font-size: clamp(11px, 1.1vw, 14px);
    font-weight: 700;
    margin-bottom: 10px;
    letter-spacing: 0.01em;
}

/* ── Header card ── */
.header-card {
    background: linear-gradient(135deg, #ffffff 0%, #f8faff 100%);
    border: 1px solid #dde3ed;
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
    color: #0c1a3a;
    margin: 0 0 6px 0;
    line-height: 1.2;
}

.header-subtitle {
    font-size: clamp(12px, 1.1vw, 14px);
    color: #475569;
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
    background: #eef3fb;
    border: 1px solid #c2d4f0;
    border-radius: 20px;
    padding: 5px 12px;
    font-size: clamp(10px, 0.9vw, 12px);
    color: #1e3a6e;
    font-weight: 600;
    white-space: nowrap;
}

/* ── Section card ── */
.section-card {
    background: #ffffff;
    border: 1px solid #dde3ed;
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
    color: #0c1a3a;
    margin: 0 0 4px 0;
}

.section-subtitle {
    font-size: clamp(11px, 0.95vw, 13px);
    color: #64748b;
    margin: 0 0 14px 0;
}

/* ── Filter panel ── */
.filter-panel {
    background: linear-gradient(135deg, #f8fbff 0%, #eef3fb 100%);
    border: 1px solid #c2d4f0;
    border-radius: 12px;
    padding: clamp(14px, 2vw, 20px) clamp(14px, 2vw, 22px);
    margin-bottom: 20px;
    box-shadow: 0 2px 10px rgba(0,91,187,0.06);
}

.filter-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
}

.filter-title {
    font-size: clamp(14px, 1.3vw, 17px);
    font-weight: 800;
    color: #0c1a3a;
}

.filter-hint {
    font-size: clamp(10px, 0.9vw, 12px);
    color: #64748b;
    background: #e9f0fb;
    border-radius: 6px;
    padding: 3px 8px;
}

.filter-group-label {
    font-size: clamp(10px, 0.85vw, 11.5px);
    font-weight: 700;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 10px 0 6px 2px;
}

/* ── Streamlit widget overrides ── */
div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background-color: #ffffff !important;
    border: 1.5px solid #c2d4f0 !important;
    border-radius: 8px !important;
    min-height: 38px !important;
    font-size: clamp(11px, 1vw, 13px) !important;
}

div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div:focus-within,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within {
    border-color: #005BBB !important;
    box-shadow: 0 0 0 3px rgba(0,91,187,0.12) !important;
}

div[data-testid="stMultiSelect"] label,
div[data-testid="stSelectbox"] label {
    font-weight: 700 !important;
    color: #1e3a6e !important;
    font-size: clamp(11px, 0.95vw, 13px) !important;
}

/* toggle */
div[data-testid="stToggle"] label {
    font-weight: 700 !important;
    color: #1e3a6e !important;
    font-size: clamp(11px, 0.95vw, 13px) !important;
}

/* Reset button */
div[data-testid="stButton"] button {
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: clamp(11px, 0.95vw, 13px) !important;
    padding: 6px 14px !important;
}

/* ── Conclusion block ── */
.conclusion-block {
    border-radius: 10px;
    padding: clamp(12px, 1.5vw, 18px) clamp(14px, 2vw, 22px);
    margin: 8px 0 14px 0;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
}

.conclusion-risk-high {
    background: linear-gradient(135deg, #fff1f1 0%, #fee2e2 100%);
    border-left: 5px solid #dc2626;
    border: 1px solid #fecaca;
    border-left: 5px solid #dc2626;
}

.conclusion-risk-medium {
    background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
    border: 1px solid #fde68a;
    border-left: 5px solid #d97706;
}

.conclusion-risk-low {
    background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    border: 1px solid #bbf7d0;
    border-left: 5px solid #16a34a;
}

.conclusion-badge {
    font-size: clamp(13px, 1.2vw, 16px);
    font-weight: 900;
    padding: 6px 14px;
    border-radius: 8px;
    white-space: nowrap;
}

.badge-red { background: #dc2626; color: #fff; }
.badge-yellow { background: #d97706; color: #fff; }
.badge-green { background: #16a34a; color: #fff; }

.conclusion-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.meta-chip {
    background: rgba(255,255,255,0.7);
    border: 1px solid rgba(0,0,0,0.1);
    border-radius: 20px;
    padding: 4px 11px;
    font-size: clamp(10px, 0.9vw, 12px);
    font-weight: 600;
    color: #334155;
}

.conclusion-text {
    font-size: clamp(12px, 1vw, 14px);
    color: #475569;
    margin-top: 6px;
    width: 100%;
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
    color: #475569;
    min-height: 28px;
    line-height: 1.3;
}

.kpi-value {
    font-size: clamp(22px, 2.5vw, 32px);
    font-weight: 900;
    color: #0c1a3a;
    line-height: 1;
    margin-top: 2px;
}

.kpi-pct {
    font-size: clamp(11px, 0.95vw, 13px);
    font-weight: 700;
    color: #64748b;
    margin-top: 4px;
}

.kpi-blue  { background: #eff6ff; border-color: #bfdbfe; }
.kpi-green { background: #f0fdf4; border-color: #bbf7d0; }
.kpi-red   { background: #fef2f2; border-color: #fecaca; }
.kpi-yellow{ background: #fffbeb; border-color: #fde68a; }
.kpi-gray  { background: #f8fafc; border-color: #e2e8f0; }

/* ── Insight items ── */
.insight-item {
    background: #f8fafc;
    border-left: 4px solid #005BBB;
    border-radius: 0 8px 8px 0;
    padding: clamp(8px, 1vw, 12px) clamp(12px, 1.5vw, 16px);
    margin-bottom: 8px;
    font-size: clamp(12px, 1vw, 14px);
    color: #1e293b;
    line-height: 1.5;
}

.insight-item.warn { border-left-color: #d97706; background: #fffbeb; }
.insight-item.danger { border-left-color: #dc2626; background: #fef2f2; }
.insight-item.info { border-left-color: #0891b2; background: #ecfeff; }

/* ── Linear indicator rows ── */
.indicator-row {
    margin-bottom: 10px;
}

.indicator-label {
    display: flex;
    justify-content: space-between;
    font-size: clamp(11px, 0.95vw, 13px);
    font-weight: 600;
    color: #334155;
    margin-bottom: 4px;
}

.indicator-bar-bg {
    background: #e2e8f0;
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
    border: 1px solid #e9eef5;
    border-radius: 10px;
    padding: clamp(10px, 1.5vw, 16px);
    margin-bottom: 10px;
}

.chart-title {
    font-size: clamp(12px, 1.1vw, 15px);
    font-weight: 800;
    color: #0c1a3a;
    margin-bottom: 6px;
}

/* ── Rank table ── */
div[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #dde3ed !important;
}

/* ── Methodology ── */
.methodology-box {
    background: #f8fafc;
    border: 1px solid #dde3ed;
    border-radius: 10px;
    padding: 16px 20px;
    font-size: clamp(11px, 0.95vw, 13px);
    color: #334155;
    line-height: 1.7;
}

/* ── Footer ── */
.footer {
    text-align: center;
    color: #94a3b8;
    font-size: clamp(10px, 0.9vw, 12px);
    margin-top: 40px;
    padding: 18px 0 10px;
    border-top: 1px solid #e2e8f0;
}

/* ── Separator ── */
.vis-separator {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 22px 0;
}

/* ══════════════════════════════════════════════
   PRESENTATION MODE — PowerPoint-like design
   ══════════════════════════════════════════════ */

.pres-overlay {
    position: fixed;
    inset: 0;
    background: #0a0f1e;
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
    background: #FFD700;
    width: 24px;
    border-radius: 4px;
}

.pres-ua-bar {
    height: 3px;
    background: linear-gradient(90deg, #005BBB 50%, #FFD700 50%);
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
    background: radial-gradient(ellipse at 20% 50%, rgba(0,91,187,0.25) 0%, transparent 60%),
                radial-gradient(ellipse at 80% 30%, rgba(255,215,0,0.1) 0%, transparent 50%),
                #0a0f1e;
}

.pres-title-eyebrow {
    font-size: 11px;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #FFD700;
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
    background: radial-gradient(ellipse at 80% 20%, rgba(220,38,38,0.15) 0%, transparent 50%),
                #0d1117;
}

.pres-slide-conclusion.ok {
    background: radial-gradient(ellipse at 80% 20%, rgba(22,163,74,0.12) 0%, transparent 50%),
                #0d1117;
}

.pres-slide-conclusion.medium {
    background: radial-gradient(ellipse at 80% 20%, rgba(217,119,6,0.12) 0%, transparent 50%),
                #0d1117;
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

.pres-verdict-badge.high { background: rgba(220,38,38,0.2); border: 1.5px solid #dc2626; color: #fca5a5; }
.pres-verdict-badge.medium { background: rgba(217,119,6,0.2); border: 1.5px solid #d97706; color: #fde68a; }
.pres-verdict-badge.low { background: rgba(22,163,74,0.2); border: 1.5px solid #16a34a; color: #86efac; }

.pres-verdict-text {
    font-size: clamp(13px, 1.2vw, 16px);
    color: rgba(255,255,255,0.55);
    max-width: 680px;
    line-height: 1.7;
    margin-bottom: 40px;
}

/* Slide 3 — KPI Metrics */
.pres-slide-kpis {
    background: #0d1117;
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

.pres-kpi-card.blue::before { background: #005BBB; }
.pres-kpi-card.green::before { background: #16a34a; }
.pres-kpi-card.red::before { background: #dc2626; }
.pres-kpi-card.yellow::before { background: #d97706; }
.pres-kpi-card.gray::before { background: #475569; }

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
    background: linear-gradient(160deg, #0d1117 60%, rgba(0,91,187,0.06) 100%);
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
    background: #0d1117;
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
.pres-risk-card.high .pres-risk-label { color: #fca5a5; }
.pres-risk-card.medium .pres-risk-label { color: #fde68a; }
.pres-risk-card.low .pres-risk-label { color: #86efac; }

.pres-risk-val {
    font-size: clamp(40px, 5vw, 64px);
    font-weight: 900;
    line-height: 1;
}
.pres-risk-card.high .pres-risk-val { color: #f87171; }
.pres-risk-card.medium .pres-risk-val { color: #fbbf24; }
.pres-risk-card.low .pres-risk-val { color: #4ade80; }

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
    df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=None, engine="openpyxl")
    data = df.iloc[7:].copy()

    def safe_col(index):
        if index < data.shape[1]:
            return data.iloc[:, index]
        return pd.Series([""] * len(data), index=data.index)

    result = pd.DataFrame({
        "type_marker": safe_col(1),
        "code": safe_col(2),
        "name": safe_col(3),
        "product_type": safe_col(4),
        "indicator": safe_col(5),
        "unit": safe_col(6),
        "base_2021": safe_col(7),
        "fact_2024": safe_col(8),
        "expected_2025": safe_col(9),
        "target_2026": safe_col(10),
        "target_2027": safe_col(11),
        "target_2028": safe_col(12),
        "source_national": safe_col(16),
        "department": safe_col(17),
        "department_co_1": safe_col(18),
        "department_co_2": safe_col(19),
        "deputy_minister": safe_col(20),
        "start_period": safe_col(22),
        "end_period": safe_col(23),
    })

    result = result.dropna(subset=["code"])
    result["code"] = result["code"].astype(str).str.strip()
    result["type_marker"] = result["type_marker"].astype(str).str.strip()

    def classify(row):
        marker = str(row["type_marker"]).lower()
        code = str(row["code"]).strip()
        if "стратегічна ціль" in marker:
            return "goal"
        if "завдання" in marker:
            return "task"
        if code.count(".") >= 3:
            return "measure"
        return "other"

    result["object_type"] = result.apply(classify, axis=1)
    return result


@st.cache_data(ttl=60)
def load_requests():
    response = supabase.table("monitoring_requests").select("*").execute()
    if not response.data:
        return pd.DataFrame()
    return pd.DataFrame(response.data)


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
    text = str(value).lower().strip()
    if text in ["", "nan", "none", "н.д.", "нд"]:
        return None
    q = None
    year = None
    if "1 квартал" in text or "i квартал" in text or " і квартал" in text:
        q = 1
    elif "2 квартал" in text or "ii квартал" in text or " іі квартал" in text:
        q = 2
    elif "3 квартал" in text or "iii квартал" in text or " ііі квартал" in text:
        q = 3
    elif "4 квартал" in text or "iv квартал" in text:
        q = 4
    year_match = re.search(r"20\d{2}", text)
    if year_match:
        year = int(year_match.group())
    if year and q:
        return year * 10 + q
    return None


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


def department_matches_indices(row, selected_indices):
    if not selected_indices:
        return True
    found = set()
    for value in get_all_department_values(row):
        found.update(split_department_indices(value))
    return bool(found.intersection(set(selected_indices)))


DEPUTY_MINISTER_BY_SSP = {
    "20": "ПИВОВАРОВ Андрій Андрійович",
    "21": "ПИВОВАРОВ Андрій Андрійович",
    "22": "ПИВОВАРОВ Андрій Андрійович",
    "23": "ЦИБОРТ Олександр Сергійович",
    "24": "ПИВОВАРОВ Андрій Андрійович",
    "25": "СОБОЛЕВ Олексій Дмитрович",
    "26": "БЕЗКАРАВАЙНИЙ Ігор Володимирович",
    "27": "КІНДРАТІВ Віталій Зіновійович",
    "28": "АРТЕМЕНКО Анна Ігорівна",
    "29": "КІНДРАТІВ Віталій Зіновійович",
    "30": "МАРЧАК Дарія Миколаївна",
    "31": "ПЕРЕЛИГІН Єгор Євгенович",
    "32": "МАРЧАК Дарія Миколаївна",
    "33": "АРТЕМЕНКО Анна Ігорівна",
    "34": "ПЕТРУК Віталій Вікторович",
    "35": "АРТЕМЕНКО Анна Ігорівна",
    "36": "ЦИБОРТ Олександр Сергійович",
    "37": "МАРЧАК Дарія Миколаївна",
    "38": "КІНДРАТІВ Віталій Зіновійович",
    "39": "ПЕРЕЛИГІН Єгор Євгенович",
    "40": "ЦИБОРТ Олександр Сергійович",
    "41": "ПЕТРУК Віталій Вікторович",
    "42": "АРТЕМЕНКО Анна Ігорівна",
    "43": "МАРЧАК Дарія Миколаївна",
    "44": "КІНДРАТІВ Віталій Зіновійович",
    "45": "ПИВОВАРОВ Андрій Андрійович",
    "46": "КІНДРАТІВ Віталій Зіновійович",
    "47": "МАРЧАК Дарія Миколаївна",
    "48": "МАРЧАК Дарія Миколаївна",
    "49": "АРТЕМЕНКО Анна Ігорівна",
    "50": "СОБОЛЕВ Олексій Дмитрович",
    "51": "ПИВОВАРОВ Андрій Андрійович",
    "52": "БЕЗКАРАВАЙНИЙ Ігор Володимирович",
    "54": "ПИВОВАРОВ Андрій Андрійович",
    "55": "ПИВОВАРОВ Андрій Андрійович",
    "56": "КРАСНОЛУЦЬКИЙ Олександр Васильович",
    "57": "ПИВОВАРОВ Андрій Андрійович",
    "58": "ПИВОВАРОВ Андрій Андрійович",
    "59": "СОБОЛЕВ Олексій Дмитрович",
    "60": "КРАСНОЛУЦЬКИЙ Олександр Васильович",
    "61": "КІНДРАТІВ Віталій Зіновійович",
    "62": "ПЕРЕЛИГІН Єгор Євгенович",
    "63": "КРАСНОЛУЦЬКИЙ Олександр Васильович",
    "64": "КРАСНОЛУЦЬКИЙ Олександр Васильович",
    "65": "КРАСНОЛУЦЬКИЙ Олександр Васильович",
    "67": "КРАСНОЛУЦЬКИЙ Олександр Васильович",
    "68": "КРАСНОЛУЦЬКИЙ Олександр Васильович",
    "69": "ВИСОЦЬКИЙ Тарас Миколайович",
    "70": "ВИСОЦЬКИЙ Тарас Миколайович",
    "71": "БАШЛИК Денис Олександрович",
    "72": "ВИСОЦЬКИЙ Тарас Миколайович",
    "73": "БАШЛИК Денис Олександрович",
    "74": "ОВЧАРЕНКО Ірина Іванівна",
    "75": "ПИВОВАРОВ Андрій Андрійович",
    "76": "ПИВОВАРОВ Андрій Андрійович",
    "77": "МАРЧАК Дарія Миколаївна",
    "78": "",
    "79": "",
    "80": "ВИСОЦЬКИЙ Тарас Миколайович",
}


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
    status = clean(status)
    mapping = {
        "Виконано": "Виконано",
        "Виконано частково": "Частково виконано",
        "Частково виконано": "Частково виконано",
        "Не виконано": "Не виконано",
        "Прострочено": "Не виконано",
        "Не розпочато": "Не виконано",
        "Потребує уваги": "Не виконано",
        "Не подано": "Не виконано",
        "Виконується": "Виконується",
        "Не настав час": "Термін не настав",
        "Термін не настав": "Термін не настав",
        "Втратило актуальність": "Втратив актуальність",
        "Втратив актуальність": "Втратив актуальність",
    }
    return mapping.get(status, status if status else "Не виконано")


def is_excluded_status(status):
    return status_display(status) in ["Термін не настав", "Втратив актуальність"]


def status_score(status):
    status = clean(status)
    if status == "Виконано":
        return 100
    if status in ["Виконано частково", "Частково виконано"]:
        return 75
    if status == "Виконується":
        return 50
    if status in ["Потребує уваги", "Прострочено", "Не розпочато", "Не подано", "Не виконано"]:
        return 0
    if status in ["Не настав час", "Термін не настав", "Втратило актуальність", "Втратив актуальність"]:
        return None
    return 0


def plan_fact_percent(actual, target):
    actual_num = to_number(actual)
    target_num = to_number(target)
    actual_text = normalize_text(actual)
    target_text = normalize_text(target)
    if actual_num is not None and target_num is not None and target_num != 0:
        return round(min((actual_num / target_num) * 100, 150), 1)
    if target_text in ["так", "yes"] or actual_text in ["так", "ні", "yes", "no"]:
        if actual_text in ["так", "yes"]:
            return 100
        if actual_text in ["ні", "no"]:
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


def risk_level_from_score(score):
    if score is None or pd.isna(score):
        return "Не оцінюється"
    if score >= 70:
        return "Критичний ризик"
    if score >= 35:
        return "Середній ризик"
    return "Низький ризик"


def risk_score_calc(row, selected_quarter_num, selected_period_num):
    status = clean(row.get("status", "Не подано"))
    display_status = status_display(status)
    actual = row.get("numeric_value", "")
    target = row.get("selected_target", "")
    end_num = row.get("end_num", None)
    score = 0
    reasons = []

    if display_status in ["Термін не настав", "Втратив актуальність"]:
        return 0, "захід не включається до ризикової оцінки за поточним статусом"

    pf = plan_fact_percent(actual, target)

    if status == "Не подано":
        score += 45
        reasons.append("за активним заходом не подано моніторингові дані")

    if pf is not None:
        if pf >= 100:
            score += 0
            reasons.append("фактичне значення досягло або перевищило планове")
        elif pf >= 75:
            score += 25
            reasons.append("фактичне значення становить від 75% до 99% плану")
        else:
            score += 45
            reasons.append("значне відставання фактичного значення від планового")
    else:
        if display_status == "Виконано":
            score += 0
            reasons.append("захід позначено як виконаний")
        elif display_status == "Частково виконано":
            score += 25
            reasons.append("захід позначено як частково виконаний")
        elif display_status == "Виконується":
            score += 30
            reasons.append("захід перебуває у виконанні")
        elif display_status == "Не виконано":
            score += 45
            reasons.append("захід не виконано або відсутнє підтвердження виконання")

    if pd.notna(end_num) and end_num < selected_period_num and display_status != "Виконано":
        score += 45
        reasons.append("строк виконання минув, захід не виконано")

    score = min(score, 100)
    if not reasons:
        reasons.append("критичних відхилень не виявлено")

    return score, "; ".join(reasons)


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


def deviation_for_period(completion):
    return round(completion - 100, 1)


def gauge_chart(value, title):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": "%", "font": {"size": 28, "color": "#0c1a3a"}},
        title={"text": title, "font": {"size": 14, "color": "#475569"}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#94a3b8", "tickfont": {"size": 11}},
            "bar": {"color": "#005BBB", "thickness": 0.3},
            "bgcolor": "white",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 35], "color": "#fee2e2"},
                {"range": [35, 70], "color": "#fef3c7"},
                {"range": [70, 100], "color": "#dcfce7"},
            ],
            "threshold": {
                "line": {"color": "#0c1a3a", "width": 3},
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


def pct_value(count, total):
    if total == 0:
        return "0.0%"
    return f"{round(count / total * 100, 1)}%"


def render_kpi_grid(items):
    cards_html = "".join([
        f'<div class="kpi-card {item["color"]}">'
        f'<div class="kpi-title">{item["title"]}</div>'
        f'<div class="kpi-value">{item["count"]}</div>'
        f'<div class="kpi-pct">{item["percent"]}</div>'
        f'</div>'
        for item in items
    ])

    st.markdown(
        f'<div class="kpi-grid">{cards_html}</div>',
        unsafe_allow_html=True
    )


def render_insight(text, kind="default"):
    css_class = "insight-item"
    if kind == "warn":
        css_class += " warn"
    elif kind == "danger":
        css_class += " danger"
    elif kind == "info":
        css_class += " info"
    st.markdown(f'<div class="{css_class}">{text}</div>', unsafe_allow_html=True)


def render_indicator_bar(label, value, max_val=100, color="#005BBB"):
    pct = min(max(value / max_val * 100, 0), 100)
    st.markdown(f"""
    <div class="indicator-row">
        <div class="indicator-label">
            <span>{label}</span>
            <span style="color:{color};font-weight:800;">{value}{'%' if max_val == 100 else ''}</span>
        </div>
        <div class="indicator-bar-bg">
            <div class="indicator-bar-fill" style="width:{pct}%;background:{color};"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def reset_filters():
    keys = [
        "dash_years", "dash_quarters", "dash_department_indices",
        "dash_goals", "dash_tasks", "dash_measures",
        "dash_product_types", "dash_deputies", "dash_statuses",
        "dash_financing", "dash_sources", "dash_view_mode", "dash_presentation_mode"
    ]
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]


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
    selected_period_num = int(year) * 10 + selected_q_num

    active = measures[
        (measures["start_num"].isna() | (measures["start_num"] <= selected_period_num)) &
        (measures["end_num"].isna() | (measures["end_num"] >= selected_period_num))
    ].copy()

    if department != "Усі":
        active = active[active["department"].astype(str) == str(department)]

    if requests_df.empty:
        requests_df = pd.DataFrame(columns=[
            "year", "quarter", "strat_code", "status", "numeric_value",
            "risks", "progress_text", "approval_status", "submitted_at"
        ])

    required_cols = [
        "year", "quarter", "strat_code", "status", "numeric_value",
        "risks", "progress_text", "approval_status", "submitted_at"
    ]
    for col in required_cols:
        if col not in requests_df.columns:
            requests_df[col] = ""

    approved_requests = requests_df[requests_df["approval_status"].astype(str) == "Погоджено"].copy()

    if approved_requests.empty:
        period_requests = pd.DataFrame(columns=[
            "strat_code", "status", "numeric_value", "risks", "progress_text", "submitted_at"
        ])
    else:
        quarter_num = str(quarter_to_number(quarter))
        quarter_roman = quarter_to_roman(quarter)

        period_requests = approved_requests[
            (approved_requests["year"].astype(str) == str(year)) &
            (
                (approved_requests["quarter"].astype(str) == str(quarter)) |
                (approved_requests["quarter"].astype(str) == quarter_num) |
                (approved_requests["quarter"].astype(str) == quarter_roman)
            )
        ].copy()

        if not period_requests.empty:
            period_requests = (
                period_requests
                .sort_values("submitted_at")
                .groupby("strat_code")
                .tail(1)
            )

    active = active.merge(
        period_requests[["strat_code", "status", "numeric_value", "risks", "progress_text"]],
        left_on="code",
        right_on="strat_code",
        how="left"
    )

    active["status"] = active["status"].fillna("Не подано")
    active["numeric_value"] = active["numeric_value"].fillna("")
    active["risks"] = active["risks"].fillna("")
    active["progress_text"] = active["progress_text"].fillna("")
    active["selected_target"] = active[f"target_{year}"] if f"target_{year}" in active.columns else ""

    active["status_display"] = active["status"].apply(status_display)
    active["status_score"] = active["status"].apply(status_score)
    active["plan_fact_percent"] = active.apply(
        lambda r: plan_fact_percent(r["numeric_value"], r["selected_target"]), axis=1
    )
    active["is_quantitative_pf"] = active.apply(is_quantitative_plan_fact, axis=1)
    active["performance_score"] = active.apply(
        lambda r: r["plan_fact_percent"] if pd.notna(r["plan_fact_percent"]) else r["status_score"],
        axis=1
    )
    active["included_in_assessment"] = ~active["status_display"].isin([
        "Термін не настав", "Втратив актуальність"
    ])

    risk_results = active.apply(
        lambda r: risk_score_calc(r, selected_q_num, selected_period_num), axis=1
    )
    active["risk_score"] = [x[0] for x in risk_results]
    active["risk_reason"] = [x[1] for x in risk_results]
    active["auto_risk"] = active["risk_score"].apply(risk_level_from_score)
    active.loc[~active["included_in_assessment"], "auto_risk"] = "Не оцінюється"

    active["traffic_light"] = active["performance_score"].apply(traffic_light)
    active.loc[~active["included_in_assessment"], "traffic_light"] = "⚪ Не оцінюється"

    active["period_year"] = int(year)
    active["period_quarter"] = quarter_to_roman(quarter)
    active["period_label"] = active["period_year"].astype(str) + " " + active["period_quarter"].astype(str)

    # Заступник Міністра визначається не з Excel-колонки, а за головним Індексом ССП.
    active = add_deputy_by_ssp_column(active)

    return active


def build_period_data(strat_df, requests_df, years, quarters):
    frames = []
    for year in years:
        for quarter in quarters:
            temp = prepare_period_data(strat_df, requests_df, year, quarter, "Усі")
            if not temp.empty:
                frames.append(temp)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def apply_dashboard_filters(active, department_indices, goals, tasks, measures, product_types, deputies, statuses, sources):
    data = active.copy()
    if department_indices:
        data = data[data.apply(lambda row: department_matches_indices(row, department_indices), axis=1)]
    if goals:
        data = data[data["goal_code"].isin(goals)]
    if tasks:
        data = data[data["task_code"].isin(tasks)]
    if measures:
        data = data[data["code"].isin(measures)]
    if product_types:
        data = data[data["product_type"].isin(product_types)]
    if deputies:
        data = data[data.apply(lambda row: deputy_matches(row, deputies), axis=1)]
    if statuses:
        data = data[data["status_display"].isin(statuses)]
    if sources:
        data = data[data["source_national"].isin(sources)]
    return data.copy()


def assessment_subset(active):
    if active.empty:
        return active
    return active[active["included_in_assessment"] == True].copy()


def mean_completion(active):
    assessed = assessment_subset(active)
    if assessed.empty:
        return 0
    return round(assessed["performance_score"].fillna(0).mean(), 1)


def calc_coverage(active):
    if active.empty:
        return 0
    submitted = len(active[active["status"] != "Не подано"])
    return round(submitted / len(active) * 100, 1)


def calc_submitted(active):
    if active.empty:
        return 0
    return len(active[active["status"] != "Не подано"])


def calc_risk_share(active):
    assessed = assessment_subset(active)
    if assessed.empty:
        return 0
    risk_count = len(assessed[assessed["auto_risk"].isin(["Критичний ризик", "Середній ризик"])])
    return round(risk_count / len(assessed) * 100, 1)


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
    grouped["Виконання"] = grouped["Виконання"].fillna(0).round(1)
    grouped["Ризик"] = grouped["Ризик"].fillna(0).round(1)
    grouped["Вага_невиконання"] = grouped["Вага_невиконання"].fillna(0).round(1)
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


def style_rank_table(row, total_rows):
    place = row["Місце"]
    if place <= 3:
        return ["background-color: #dcfce7; color: #14532d; font-weight: 800; text-align: center"] * len(row)
    if place <= 10:
        return ["background-color: #e0f2fe; color: #0c4a6e; text-align: center"] * len(row)
    if place > max(total_rows - 7, 10):
        return ["background-color: #fee2e2; color: #7f1d1d; text-align: center"] * len(row)
    return ["background-color: #f8fafc; color: #334155; text-align: center"] * len(row)


def collapse_to_latest_measure_rows(df):
    if df.empty:
        return df
    data = df.copy()
    data["_period_sort"] = (
        data["period_year"].astype(int) * 10
        + data["period_quarter"].apply(quarter_to_number)
    )
    data = (
        data
        .sort_values(["code", "_period_sort"])
        .groupby("code", as_index=False)
        .tail(1)
        .drop(columns=["_period_sort"])
    )
    return data


# ─── Plotly theme helper ───────────────────────────────────────────────────────
CHART_COLORS = ["#005BBB", "#FFD700", "#0891b2", "#16a34a", "#d97706", "#9333ea", "#dc2626", "#64748b"]

RISK_COLORS = {
    "Критичний ризик": "#dc2626",
    "Середній ризик": "#d97706",
    "Низький ризик": "#16a34a",
    "Не оцінюється": "#94a3b8"
}

TRAFFIC_COLORS = {
    "🟢 У графіку": "#16a34a",
    "🟡 Часткове виконання": "#d97706",
    "🔴 Відстає": "#dc2626",
    "⚪ Не оцінюється": "#94a3b8"
}

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Helvetica Neue, Arial, sans-serif", size=12, color="#334155")
)


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
    <div class="header-pills">
        <div class="pill">📋 Dashboard</div>
        <div class="pill">🗄 Excel + Supabase</div>
        <div class="pill">✅ Погоджені заявки</div>
        <div class="pill">🕐 {datetime.now().strftime("%d.%m.%Y %H:%M")}</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================
# LOAD DATA
# ============================================================

strat_df = load_strat_matrix()
requests_df = load_requests()

if requests_df.empty:
    requests_df = pd.DataFrame(columns=[
        "year", "quarter", "department", "strat_code", "status", "numeric_value",
        "risks", "progress_text", "approval_status", "submitted_at"
    ])

measures_all = strat_df[strat_df["object_type"] == "measure"].copy()
goals_all = strat_df[strat_df["object_type"] == "goal"].copy()
tasks_all = strat_df[strat_df["object_type"] == "task"].copy()

measures_all["goal_code"] = measures_all["code"].apply(get_goal_code)
measures_all["task_code"] = measures_all["code"].apply(get_task_code)
measures_all["strategic_goal"] = measures_all["goal_code"].map(goals_all.set_index("code")["name"].to_dict())
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
    key=lambda x: int(x) if x.isdigit() else 9999
)

goal_options = sorted(measures_all["goal_code"].dropna().astype(str).unique().tolist(), key=code_sort_key)
task_options = sorted(measures_all["task_code"].dropna().astype(str).unique().tolist(), key=code_sort_key)
measure_options = sorted(measures_all["code"].dropna().astype(str).unique().tolist(), key=code_sort_key)

goal_name_map = goals_all.set_index("code")["name"].to_dict()
task_name_map = tasks_all.set_index("code")["name"].to_dict()
measure_name_map = measures_all.set_index("code")["name"].to_dict()

product_type_options = unique_clean_values(measures_all["product_type"])
deputy_options = unique_clean_values(measures_all["deputy_minister_by_ssp"])
source_options = unique_clean_values(measures_all["source_national"])

status_options = [
    "Виконано", "Частково виконано", "Не виконано",
    "Термін не настав", "Втратив актуальність", "Виконується"
]


# ============================================================
# FILTERS PANEL
# ============================================================

with st.container():
    st.markdown("""
    <div class="filter-panel">
        <div class="filter-header">
            <span class="filter-title">🔍 Параметри відбору</span>
            <span class="filter-hint">Оберіть необхідні параметри: період, індекс ССП та режим перегляду даних</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Рядок 1: Ключові фільтри + режим
    fa, fb, fc, fd, fe = st.columns([1, 1, 2, 1.5, 1])

    with fa:
        selected_years = st.multiselect(
            "📅 Рік",
            years_options,
            default=[],
            key="dash_years",
            placeholder="Усі роки"
        )

    with fb:
        selected_quarters = st.multiselect(
            "🗓 Квартал",
            quarters_options,
            default=[],
            key="dash_quarters",
            placeholder="Усі квартали"
        )

    with fc:
        selected_department_indices = st.multiselect(
            "🏢 Індекс самостійного струкутрного підрозділу",
            department_indices_options,
            key="dash_department_indices",
            placeholder="Усі підрозділи"
        )

    with fd:
        view_mode = st.selectbox(
            "📊 Режим перегляду даних",
            [
                "Усі візуалізації",
                "Стратегічні цілі",
                "Самостійні структурні підрозділи",
                "Ризики",
                "Динаміка",
                "Heatmap",
                "Таблиці"
            ],
            key="dash_view_mode"
        )

    with fe:
        presentation_mode = st.toggle(
            "🖥 Presentation mode",
            value=False,
            key="dash_presentation_mode",
            help="Спрощений вигляд: висновок, ключові індикатори та основні графіки."
        )

    # Рядок 2: Деталізовані фільтри (у розгорнутому вигляді)
    with st.expander("⚙️ Додаткові фільтри (ціль, завдання, захід, тип, заступник, статус, джерело)"):
        g1, g2, g3 = st.columns(3)
        with g1:
            selected_goals = st.multiselect(
                "Стратегічна ціль",
                goal_options,
                format_func=lambda x: f"{x} — {strip_code_from_name(x, goal_name_map.get(x, ''))}",
                key="dash_goals"
            )
        with g2:
            selected_tasks = st.multiselect(
                "Завдання",
                task_options,
                format_func=lambda x: f"{x} — {strip_code_from_name(x, task_name_map.get(x, ''))}",
                key="dash_tasks"
            )
        with g3:
            selected_measures = st.multiselect(
                "Захід",
                measure_options,
                format_func=lambda x: f"{x} — {strip_code_from_name(x, measure_name_map.get(x, ''))}",
                key="dash_measures"
            )

        h1, h2, h3 = st.columns(3)
        with h1:
            selected_product_types = st.multiselect(
                "Тип продукту",
                product_type_options,
                key="dash_product_types"
            )
        with h2:
            selected_deputies = st.multiselect(
                "Заступник Міністра",
                deputy_options,
                key="dash_deputies",
                help="Фільтр працює за відповідністю Індексу головного ССП до заступника Міністра."
            )
        with h3:
            selected_statuses = st.multiselect(
                "Статус виконання",
                status_options,
                key="dash_statuses"
            )

        j1, j2, j3 = st.columns(3)
        with j1:
            selected_financing = st.multiselect(
                "Фінансування",
                [],
                key="dash_financing",
                help="Дані про фінансування поки не додані. Фільтр залишено як технічну заготовку."
            )
        with j2:
            selected_sources = st.multiselect(
                "Джерело даних: національний рівень",
                source_options,
                key="dash_sources"
            )
        with j3:
            st.write("")
            st.write("")
            if st.button("↺ Скинути фільтри", use_container_width=True):
                reset_filters()
                st.rerun()

    # Кнопка скидання поза expander (завжди доступна)
    col_reset, _ = st.columns([1, 5])
    with col_reset:
        if st.button("Скинути фільтри", use_container_width=True, key="reset_main"):
            reset_filters()
            st.rerun()


# ============================================================
# BUILD ACTIVE DATA
# ============================================================

years_for_calc = selected_years if selected_years else years_options
quarters_for_calc = selected_quarters if selected_quarters else quarters_options

active_raw = build_period_data(strat_df, requests_df, years_for_calc, quarters_for_calc)

if active_raw.empty:
    st.warning("Для обраного періоду активних заходів не знайдено.")
    st.stop()

active = apply_dashboard_filters(
    active_raw,
    selected_department_indices,
    selected_goals if "dash_goals" in st.session_state else [],
    selected_tasks if "dash_tasks" in st.session_state else [],
    selected_measures if "dash_measures" in st.session_state else [],
    selected_product_types if "dash_product_types" in st.session_state else [],
    selected_deputies if "dash_deputies" in st.session_state else [],
    selected_statuses if "dash_statuses" in st.session_state else [],
    selected_sources if "dash_sources" in st.session_state else []
)

if active.empty:
    st.warning("За обраними параметрами відбору даних не знайдено.")
    st.stop()

active_period_rows = active.copy()
active = collapse_to_latest_measure_rows(active)


# ============================================================
# MAIN METRICS
# ============================================================

total_active = len(active)
submitted_count = calc_submitted(active)
coverage = calc_coverage(active)
completion = mean_completion(active)
deviation_current = deviation_for_period(completion)

risk_count = len(assessment_subset(active)[assessment_subset(active)["auto_risk"].isin(["Критичний ризик", "Середній ризик"])])
critical_count = len(assessment_subset(active)[assessment_subset(active)["auto_risk"] == "Критичний ризик"])
risk_share = calc_risk_share(active)
without_data = len(active[active["status"] == "Не подано"])

completed_count = len(active[active["status_display"] == "Виконано"])
partly_count = len(active[active["status_display"] == "Частково виконано"])
not_done_count = len(active[active["status_display"] == "Не виконано"])
obsolete_count = len(active[active["status_display"] == "Втратив актуальність"])
not_time_count = len(active[active["status_display"] == "Термін не настав"])
in_progress_count = len(active[active["status_display"] == "Виконується"])

approved_requests_count = submitted_count
review_count = 0
not_counted_count = len(active[active["status"] == "Не подано"])

conclusion_title, conclusion_text, conclusion_badge = dashboard_conclusion(completion, risk_share, coverage)

period_year_label = (
    ", ".join([f"{y} рік" for y in selected_years]) if selected_years else "усі роки"
)
period_quarter_label = (
    ", ".join([f"{q} квартал" for q in selected_quarters]) if selected_quarters else "усі квартали"
)
period_label = f"{period_year_label} | {period_quarter_label}"

# Conclusion badge mapping
badge_css = {"risk-high": "badge-red", "risk-medium": "badge-yellow", "risk-low": "badge-green"}
block_css = {"risk-high": "conclusion-risk-high", "risk-medium": "conclusion-risk-medium", "risk-low": "conclusion-risk-low"}


# goal_progress — обчислюється тут, бо використовується в presentation_mode нижче
goal_progress = (
    active
    .groupby(["goal_code", "strategic_goal"])
    .agg(
        Активних_заходів=("code", "count"),
        Виконання=("performance_score", "mean"),
        Покриття=("status", lambda x: (x != "Не подано").sum()),
        Ризикових=("auto_risk", lambda x: x.isin(["Критичний ризик", "Середній ризик"]).sum()),
        Середній_ризик=("risk_score", "mean")
    )
    .reset_index()
)
goal_progress["Виконання"] = goal_progress["Виконання"].fillna(0).round(1)
goal_progress["Покриття_%"] = (goal_progress["Покриття"] / goal_progress["Активних_заходів"] * 100).round(1)
goal_progress["Середній_ризик"] = goal_progress["Середній_ризик"].fillna(0).round(1)

# ============================================================
# PRESENTATION MODE — PowerPoint-style slides
# ============================================================

if presentation_mode:
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
            pct = min(max(float(gr["Виконання"]), 0), 100)
            if pct >= 70:
                bar_color = "#16a34a"
            elif pct >= 35:
                bar_color = "#d97706"
            else:
                bar_color = "#dc2626"
            short_name = str(gr["strategic_goal"])[:45] + ("…" if len(str(gr["strategic_goal"])) > 45 else "")
            goal_rows_html += f"""
            <div class="pres-goal-row">
                <div class="pres-goal-code">{gr['goal_code']}</div>
                <div class="pres-goal-name" title="{gr['strategic_goal']}">{short_name}</div>
                <div class="pres-goal-bar-bg">
                    <div class="pres-goal-bar-fill" style="width:{pct}%;background:{bar_color};"></div>
                </div>
                <div class="pres-goal-pct">{pct:.0f}%</div>
            </div>"""

    # risk counts for slide
    risk_map = active.groupby("auto_risk").size().to_dict()
    count_high = risk_map.get("Критичний ризик", 0)
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

    # ── топ-5 проблемних заходів для слайду 6 ─────────────────
    top5_html = ""
    top5_data = active[
        (active["auto_risk"].isin(["Критичний ризик", "Середній ризик"]) |
         (active["status"] == "Не подано")) &
        (active["included_in_assessment"] == True)
    ].copy()
    top5_data = top5_data.sort_values("risk_score", ascending=False).head(5)

    for _, tr in top5_data.iterrows():
        risk_color = "#f87171" if tr["auto_risk"] == "Критичний ризик" else "#fbbf24"
        dep_short = str(tr.get("department", ""))[:12]
        name_short = str(tr.get("name", ""))[:70] + ("…" if len(str(tr.get("name", ""))) > 70 else "")
        top5_html += (
            f'<div style="display:flex;align-items:flex-start;gap:14px;padding:14px 0;'
            f'border-bottom:1px solid rgba(255,255,255,0.06);">'
            f'<div style="background:{risk_color};color:#0a0f1e;font-size:10px;font-weight:900;'
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
    body { background: #0a0f1e; font-family: 'Helvetica Neue', Arial, sans-serif; overflow-x: hidden; }
    .pres-overlay { min-height: 100vh; background: #0a0f1e; overflow-y: auto; }
    .pres-ua-bar { height: 3px; background: linear-gradient(90deg,#005BBB 50%,#FFD700 50%); width: 100%; }
    .pres-nav { position: sticky; top: 0; z-index: 100; background: rgba(10,15,30,0.95); backdrop-filter: blur(12px); border-bottom: 1px solid rgba(255,255,255,0.08); display: flex; align-items: center; justify-content: space-between; padding: 10px 32px; }
    .pres-nav-title { color: rgba(255,255,255,0.5); font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; font-weight: 600; }
    .pres-nav-dots { display: flex; gap: 8px; align-items: center; }
    .pres-dot { width: 8px; height: 8px; border-radius: 50%; background: rgba(255,255,255,0.2); }
    .pres-dot.active { background: #FFD700; width: 24px; border-radius: 4px; }
    .pres-slide { min-height: 100vh; display: flex; flex-direction: column; justify-content: center; padding: 48px 64px; position: relative; border-bottom: 1px solid rgba(255,255,255,0.04); }
    .pres-slide:last-child { border-bottom: none; }
    .pres-slide-num { position: absolute; top: 24px; right: 40px; font-size: 11px; color: rgba(255,255,255,0.2); letter-spacing: 0.1em; font-weight: 600; }
    .pres-slide-title { background: radial-gradient(ellipse at 20% 50%, rgba(0,91,187,0.25) 0%, transparent 60%), radial-gradient(ellipse at 80% 30%, rgba(255,215,0,0.1) 0%, transparent 50%), #0a0f1e; }
    .pres-title-eyebrow { font-size: 11px; letter-spacing: 0.2em; text-transform: uppercase; color: #FFD700; font-weight: 700; margin-bottom: 20px; }
    .pres-title-h1 { font-size: clamp(32px,4vw,56px); font-weight: 900; color: #fff; line-height: 1.1; margin-bottom: 16px; max-width: 800px; }
    .pres-title-sub { font-size: clamp(14px,1.4vw,18px); color: rgba(255,255,255,0.5); max-width: 600px; line-height: 1.6; margin-bottom: 40px; }
    .pres-filter-pills { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }
    .pres-filter-pill { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12); border-radius: 20px; padding: 6px 16px; font-size: 12px; color: rgba(255,255,255,0.7); font-weight: 600; }
    .pres-slide-conclusion { background: radial-gradient(ellipse at 80% 20%, rgba(220,38,38,0.15) 0%, transparent 50%), #0d1117; }
    .pres-slide-conclusion.ok { background: radial-gradient(ellipse at 80% 20%, rgba(22,163,74,0.12) 0%, transparent 50%), #0d1117; }
    .pres-slide-conclusion.medium { background: radial-gradient(ellipse at 80% 20%, rgba(217,119,6,0.12) 0%, transparent 50%), #0d1117; }
    .pres-section-label { font-size: 11px; letter-spacing: 0.18em; text-transform: uppercase; color: rgba(255,255,255,0.35); font-weight: 700; margin-bottom: 24px; }
    .pres-verdict-badge { display: inline-flex; align-items: center; gap: 10px; padding: 10px 24px; border-radius: 10px; font-size: clamp(18px,2vw,26px); font-weight: 900; margin-bottom: 20px; }
    .pres-verdict-badge.high { background: rgba(220,38,38,0.2); border: 1.5px solid #dc2626; color: #fca5a5; }
    .pres-verdict-badge.medium { background: rgba(217,119,6,0.2); border: 1.5px solid #d97706; color: #fde68a; }
    .pres-verdict-badge.low { background: rgba(22,163,74,0.2); border: 1.5px solid #16a34a; color: #86efac; }
    .pres-verdict-text { font-size: clamp(13px,1.2vw,16px); color: rgba(255,255,255,0.55); max-width: 680px; line-height: 1.7; margin-bottom: 40px; }
    .pres-slide-kpis { background: #0d1117; }
    .pres-kpi-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 20px; margin-top: 32px; }
    .pres-kpi-card { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 28px 24px; display: flex; flex-direction: column; gap: 6px; position: relative; overflow: hidden; }
    .pres-kpi-card::before { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px; border-radius: 14px 14px 0 0; }
    .pres-kpi-card.blue::before { background: #005BBB; }
    .pres-kpi-card.green::before { background: #16a34a; }
    .pres-kpi-card.red::before { background: #dc2626; }
    .pres-kpi-card.yellow::before { background: #d97706; }
    .pres-kpi-card.gray::before { background: #475569; }
    .pres-kpi-label { font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: rgba(255,255,255,0.4); }
    .pres-kpi-value { font-size: clamp(36px,4vw,56px); font-weight: 900; color: #fff; line-height: 1; }
    .pres-kpi-sub { font-size: 13px; color: rgba(255,255,255,0.35); font-weight: 600; }
    .pres-slide-goals { background: linear-gradient(160deg,#0d1117 60%,rgba(0,91,187,0.06) 100%); }
    .pres-goal-bar-wrap { margin-top: 28px; display: flex; flex-direction: column; gap: 14px; }
    .pres-goal-row { display: flex; align-items: center; gap: 16px; }
    .pres-goal-code { font-size: 11px; font-weight: 800; color: rgba(255,255,255,0.4); min-width: 36px; text-align: right; }
    .pres-goal-name { font-size: 13px; color: rgba(255,255,255,0.7); flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 320px; }
    .pres-goal-bar-bg { flex: 2; background: rgba(255,255,255,0.06); border-radius: 99px; height: 10px; overflow: hidden; }
    .pres-goal-bar-fill { height: 100%; border-radius: 99px; }
    .pres-goal-pct { font-size: 13px; font-weight: 800; color: #fff; min-width: 44px; text-align: right; }
    .pres-slide-risks { background: #0d1117; }
    .pres-risk-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 20px; margin-top: 32px; }
    .pres-risk-card { border-radius: 14px; padding: 28px 24px; display: flex; flex-direction: column; gap: 8px; }
    .pres-risk-card.high { background: rgba(220,38,38,0.12); border: 1.5px solid rgba(220,38,38,0.3); }
    .pres-risk-card.medium { background: rgba(217,119,6,0.1); border: 1.5px solid rgba(217,119,6,0.25); }
    .pres-risk-card.low { background: rgba(22,163,74,0.1); border: 1.5px solid rgba(22,163,74,0.25); }
    .pres-risk-label { font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; }
    .pres-risk-card.high .pres-risk-label { color: #fca5a5; }
    .pres-risk-card.medium .pres-risk-label { color: #fde68a; }
    .pres-risk-card.low .pres-risk-label { color: #86efac; }
    .pres-risk-val { font-size: clamp(40px,5vw,64px); font-weight: 900; line-height: 1; }
    .pres-risk-card.high .pres-risk-val { color: #f87171; }
    .pres-risk-card.medium .pres-risk-val { color: #fbbf24; }
    .pres-risk-card.low .pres-risk-val { color: #4ade80; }
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
            </div>
            <div style="font-size:11px;color:rgba(255,255,255,0.3);letter-spacing:.08em;">
                ⬆ прокрутіть для перегляду слайдів
            </div>
        </div>

        <!-- ══ SLIDE 1 — TITLE ══ -->
        <div class="pres-slide pres-slide-title">
            <div class="pres-slide-num">01 / 06</div>
            <div class="pres-title-eyebrow">🇺🇦 Міністерство економіки, довкілля та сільського господарства України</div>
            <div class="pres-title-h1">Аналітичний дашборд результативності стратегічного плану</div>
            <div class="pres-title-sub">
                Комплексна панель моніторингу та оцінювання стратегічних результатів —
                в розрізі стратегічних цілей, завдань та самостійних структурних підрозділів.
            </div>
            <div class="pres-filter-pills">
                {filter_pills_html}
                <span class="pres-filter-pill">📌 {total_active} активних заходів</span>
                <span class="pres-filter-pill">🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}</span>
            </div>
        </div>

        <!-- ══ SLIDE 2 — VERDICT ══ -->
        <div class="pres-slide pres-slide-conclusion {verdict_class}">
            <div class="pres-slide-num">02 / 06</div>
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
                    <div style="font-size:44px;font-weight:900;color:{'#f87171' if deviation_current < 0 else '#4ade80'};line-height:1;">{deviation_current:+.1f}</div>
                    <div style="font-size:12px;color:rgba(255,255,255,.35);margin-top:4px;">В.п. від планового рівня</div>
                </div>
            </div>
        </div>

        <!-- ══ SLIDE 3 — KEY METRICS ══ -->
        <div class="pres-slide pres-slide-kpis">
            <div class="pres-slide-num">03 / 06</div>
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
                <div class="pres-kpi-card blue">
                    <div class="pres-kpi-label">Виконується</div>
                    <div class="pres-kpi-value">{in_progress_count}</div>
                    <div class="pres-kpi-sub">{pct_value(in_progress_count, total_active)}</div>
                </div>
                <div class="pres-kpi-card gray">
                    <div class="pres-kpi-label">Термін не настав</div>
                    <div class="pres-kpi-value">{not_time_count}</div>
                    <div class="pres-kpi-sub">{pct_value(not_time_count, total_active)}</div>
                </div>
            </div>

            <div class="pres-metric-rows" style="max-width:680px;margin-top:40px;">
                {pres_bar('Виконання СП', completion, '#005BBB')}
                {pres_bar('Покриття моніторингом', coverage, '#0891b2')}
                {pres_bar('Частка без ризику', round(100 - risk_share, 1), '#16a34a')}
            </div>
        </div>

        <!-- ══ SLIDE 4 — STRATEGIC GOALS ══ -->
        <div class="pres-slide pres-slide-goals">
            <div class="pres-slide-num">04 / 06</div>
            <div class="pres-section-label">Стратегічні цілі</div>
            <div class="pres-slide-h2">Виконання за стратегічними цілями</div>
            <div class="pres-slide-hsub">Відсоток виконання по кожній стратегічній цілі · {period_label}</div>
            <div class="pres-goal-bar-wrap">
                {goal_rows_html if goal_rows_html else '<div style="color:rgba(255,255,255,0.3);margin-top:24px;">Дані відсутні за обраними фільтрами</div>'}
            </div>
        </div>

        <!-- ══ SLIDE 5 — RISKS ══ -->
        <div class="pres-slide pres-slide-risks">
            <div class="pres-slide-num">05 / 06</div>
            <div class="pres-section-label">Автоматична оцінка ризиків</div>
            <div class="pres-slide-h2">Розподіл ризиків недосягнення</div>
            <div class="pres-slide-hsub">{total_active} активних заходів · {period_label}</div>

            <div class="pres-risk-grid">
                <div class="pres-risk-card high">
                    <div class="pres-risk-label">🔴 Критичний ризик</div>
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
        <div class="pres-slide" style="background:#0d1117;">
            <div class="pres-slide-num">06 / 06</div>
            <div class="pres-section-label">Увага керівництва</div>
            <div class="pres-slide-h2">Топ-5 критичних заходів</div>
            <div class="pres-slide-hsub">Заходи з найвищим ризиком недосягнення · {period_label}</div>
            <div style="margin-top:28px;max-width:860px;">
                {top5_html}
            </div>
        </div>

    </div>
</body></html>""", height=600, scrolling=True)
    st.stop()




st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">Прогрес виконання: висновок системи</div>', unsafe_allow_html=True)

st.markdown(f"""
<div class="conclusion-block {block_css[conclusion_badge]}">
    <span class="conclusion-badge {badge_css[conclusion_badge]}">{conclusion_title}</span>
    <div class="conclusion-meta">
        <span class="meta-chip">📅 {period_label}</span>
        <span class="meta-chip">📌 {total_active} активних заходів</span>
        <span class="meta-chip">📉 Відхилення: {deviation_current} в.п.</span>
        <span class="meta-chip">📊 Виконання: {completion}%</span>
        <span class="meta-chip">📋 Покриття: {coverage}%</span>
    </div>
    <div class="conclusion-text">{conclusion_text}</div>
</div>
""", unsafe_allow_html=True)

render_kpi_grid([
    {"title": "Заходів", "count": total_active, "percent": "100.0%", "color": "kpi-blue"},
    {"title": "Виконано", "count": completed_count, "percent": pct_value(completed_count, total_active), "color": "kpi-green"},
    {"title": "Погоджено", "count": approved_requests_count, "percent": pct_value(approved_requests_count, total_active), "color": "kpi-green"},
    {"title": "На розгляді", "count": review_count, "percent": pct_value(review_count, total_active), "color": "kpi-yellow"},
    {"title": "Не враховано", "count": not_counted_count, "percent": pct_value(not_counted_count, total_active), "color": "kpi-red"},
    {"title": "Не виконано", "count": not_done_count, "percent": pct_value(not_done_count, total_active), "color": "kpi-red"},
    {"title": "Втратив актуальність", "count": obsolete_count, "percent": pct_value(obsolete_count, total_active), "color": "kpi-gray"},
    {"title": "Термін не настав", "count": not_time_count, "percent": pct_value(not_time_count, total_active), "color": "kpi-gray"},
    {"title": "Частково виконано", "count": partly_count, "percent": pct_value(partly_count, total_active), "color": "kpi-yellow"},
    {"title": "Виконується", "count": in_progress_count, "percent": pct_value(in_progress_count, total_active), "color": "kpi-blue"},
])


# ============================================================
# АВТОМАТИЧНІ ІНСАЙТИ
# ============================================================

if not presentation_mode:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Автоматичні інсайти</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">Система автоматично виявляє відхилення та концентрації ризиків</div>', unsafe_allow_html=True)

    goal_failure = weighted_failure_group(active, ["goal_code", "strategic_goal"])
    dep_exploded_for_insights = explode_departments(active)
    dep_failure = weighted_failure_group(dep_exploded_for_insights, ["ssp_department"])

    if without_data > 0:
        render_insight(f"⚠️ {without_data} активних заходів не мають поданого погодженого моніторингу.", "warn")
    if critical_count > 0:
        render_insight(f"🔴 {critical_count} заходів мають критичний ризик недосягнення.", "danger")
    if not goal_failure.empty:
        row = goal_failure.iloc[0]
        render_insight(
            f"📉 Найбільша концентрація невиконаних заходів у СЦ {row['goal_code']} — "
            f"{int(row['Невиконаних'])} із {int(row['Активних_заходів'])}; "
            f"вага в обраному портфелі — {row['Вага_невиконання']}%.",
            "warn"
        )
    if not dep_failure.empty:
        row = dep_failure.iloc[0]
        render_insight(
            f"🏢 Самостійний структурний підрозділ із найвищою концентрацією невиконання: "
            f"{row['ssp_department']} — {int(row['Невиконаних'])} із {int(row['Активних_заходів'])}; "
            f"вага в обраному портфелі — {row['Вага_невиконання']}%.",
            "info"
        )
    render_insight(f"📌 Відхилення за звітний період: {deviation_current} в.п. від планового рівня.")

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# ПОКАЗНИКИ ВИКОНАННЯ СТРАТЕГІЧНОГО ПЛАНУ
# ============================================================

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">Показники виконання стратегічного плану</div>', unsafe_allow_html=True)

ind_col1, ind_col2 = st.columns([1, 1.3])

with ind_col1:
    st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
    fig_gauge = gauge_chart(completion, "Виконання СП")
    st.plotly_chart(fig_gauge, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with ind_col2:
    st.markdown('<div class="chart-wrap" style="height:100%;padding-top:20px;">', unsafe_allow_html=True)
    render_indicator_bar("Виконання СП", completion, 100, "#005BBB")
    render_indicator_bar("Покриття моніторингом", coverage, 100, "#0891b2")
    dev_display = round(100 + deviation_current, 1)
    render_indicator_bar("Відхилення за звітний період", round(100 + deviation_current, 1), 100, "#d97706")
    render_indicator_bar("Частка заходів без ризику", round(100 - risk_share, 1), 100, "#16a34a")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# AGGREGATIONS
# ============================================================

status_counts = active.groupby("status_display").size().reset_index(name="Кількість")
risk_counts = active.groupby("auto_risk").size().reset_index(name="Кількість")
traffic_counts = active.groupby("traffic_light").size().reset_index(name="Кількість")

goal_progress = (
    active
    .groupby(["goal_code", "strategic_goal"])
    .agg(
        Активних_заходів=("code", "count"),
        Виконання=("performance_score", "mean"),
        Покриття=("status", lambda x: (x != "Не подано").sum()),
        Ризикових=("auto_risk", lambda x: x.isin(["Критичний ризик", "Середній ризик"]).sum()),
        Середній_ризик=("risk_score", "mean")
    )
    .reset_index()
)
goal_progress["Виконання"] = goal_progress["Виконання"].fillna(0).round(1)
goal_progress["Покриття_%"] = (goal_progress["Покриття"] / goal_progress["Активних_заходів"] * 100).round(1)
goal_progress["Середній_ризик"] = goal_progress["Середній_ризик"].fillna(0).round(1)

dep_active = explode_departments(active)
dep_progress = (
    dep_active
    .groupby("ssp_department")
    .agg(
        Активних_заходів=("code", "count"),
        Виконання=("performance_score", "mean"),
        Подано=("status", lambda x: (x != "Не подано").sum()),
        Ризикових=("auto_risk", lambda x: x.isin(["Критичний ризик", "Середній ризик"]).sum()),
        Критичних=("auto_risk", lambda x: (x == "Критичний ризик").sum()),
        Середній_ризик=("risk_score", "mean")
    )
    .reset_index()
)
dep_progress["Виконання"] = dep_progress["Виконання"].fillna(0).round(1)
dep_progress["Покриття_%"] = (dep_progress["Подано"] / dep_progress["Активних_заходів"] * 100).round(1)
dep_progress["Середній_ризик"] = dep_progress["Середній_ризик"].fillna(0).round(1)


# ============================================================
# VISUALIZATIONS: СТРАТЕГІЧНІ ЦІЛІ (Статуси + Цілі)
# ============================================================

if view_mode in ["Усі візуалізації", "Стратегічні цілі"] or presentation_mode:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)

    sc1, gap_col, sc2 = st.columns([1, 0.18, 1.6])

    with sc1:
        st.markdown('<div class="section-title">Статуси виконання за принципом світлофора</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-subtitle">Розподіл активних заходів за станом виконання</div>', unsafe_allow_html=True)
        fig_tl = px.pie(
            traffic_counts,
            names="traffic_light",
            values="Кількість",
            hole=0.52,
            color="traffic_light",
            color_discrete_map=TRAFFIC_COLORS
        )
        fig_tl.update_traces(
            textfont_size=13,
            marker=dict(line=dict(color="#ffffff", width=2))
        )
        fig_tl.update_layout(
            **CHART_LAYOUT,
            height=300,
            showlegend=True,
            legend=dict(orientation="v", x=1, y=0.5),
            margin=dict(l=10, r=10, t=10, b=10)
        )
        st.plotly_chart(fig_tl, use_container_width=True)

    with sc2:
        st.markdown('<div class="section-title">Виконання за стратегічними цілями</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-subtitle">Відсоток виконання по кожній стратегічній цілі</div>', unsafe_allow_html=True)

    goal_sorted = goal_progress.copy()
    goal_sorted["_goal_sort"] = goal_sorted["goal_code"].apply(code_sort_key)
    goal_sorted = goal_sorted.sort_values("_goal_sort")
    goal_sorted["label"] = (
        goal_sorted["goal_code"].astype(str)
        + " "
        + goal_sorted["strategic_goal"].astype(str).str[:40]
    )

    fig_goals = px.bar(
        goal_sorted,
        x="Виконання",
        y="label",
        orientation="h",
        text=goal_sorted["Виконання"].apply(lambda x: f"{x:.1f}%"),
        hover_data={"Активних_заходів": True, "Покриття_%": True, "Ризикових": True},
        color="Виконання",
        color_continuous_scale=["#dc2626", "#fef08a", "#16a34a"],
        range_color=[0, 100],
    )
    fig_goals.update_traces(
        textposition="outside",
        textfont_size=11,
        marker_line_width=0
     )
    fig_goals.update_layout(
        **CHART_LAYOUT,
        height=max(200, len(goal_sorted) * 38 + 40),
        xaxis=dict(range=[0, 115], showgrid=True, gridcolor="#f1f5f9", ticksuffix="%"),
        yaxis=dict(showgrid=False, categoryorder="array", categoryarray=goal_sorted["label"].tolist()[::-1]),
        coloraxis_showscale=False,
        margin=dict(l=10, r=60, t=10, b=10)
    )
    st.plotly_chart(fig_goals, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# VISUALIZATIONS: САМОСТІЙНІ СТРУКТУРНІ ПІДРОЗДІЛИ
# ============================================================

if not presentation_mode and view_mode in ["Усі візуалізації", "Самостійні структурні підрозділи"]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Рейтинг самостійних структурних підрозділів</div>', unsafe_allow_html=True)

    rank_df = dep_progress.sort_values("Виконання", ascending=False).copy()
    rank_df["Місце"] = range(1, len(rank_df) + 1)

    rank_display = rank_df[[
        "Місце", "ssp_department", "Виконання", "Покриття_%",
        "Ризикових", "Критичних", "Активних_заходів"
    ]].rename(columns={
        "ssp_department": "Самостійний структурний підрозділ",
        "Покриття_%": "Покриття, %",
        "Активних_заходів": "Активних заходів"
    })

    styled_rank = (
        rank_display.style
        .apply(lambda row: style_rank_table(row, len(rank_display)), axis=1)
        .set_properties(**{"text-align": "center"})
        .set_table_styles([{
            "selector": "th",
            "props": [
                ("text-align", "center"), ("background-color", "#e9eef7"),
                ("color", "#111827"), ("font-weight", "900"), ("border", "1px solid #d8dee9")
            ]
        }])
    )

    st.dataframe(styled_rank, use_container_width=True, hide_index=True)

    st.markdown("<hr class='vis-separator'>", unsafe_allow_html=True)

    # Chart: top 20 departments for readability
    top_n = min(30, len(rank_df))
    top_deps = rank_df.head(top_n)

    st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="chart-title">Виконання за самостійними структурними підрозділами</div>', unsafe_allow_html=True)

    fig_dep = px.bar(
        top_deps,
        x="ssp_department",
        y="Виконання",
        text=top_deps["Виконання"].apply(lambda x: f"{x:.1f}%"),
        hover_data={"Активних_заходів": True, "Покриття_%": True, "Ризикових": True, "Критичних": True},
        color="Виконання",
        color_continuous_scale=["#dc2626", "#fef08a", "#16a34a"],
        range_color=[0, 100],
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
            tickangle=-35,
            tickfont=dict(size=10),
            showgrid=False
        ),
        yaxis=dict(
            range=[0, 115],
            showgrid=True,
            gridcolor="#f1f5f9",
            ticksuffix="%"
        ),
        coloraxis_showscale=False,
        margin=dict(l=10, r=10, t=30, b=100)
    )
    st.plotly_chart(fig_dep, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

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
            Ризикових=("auto_risk", lambda x: x.isin(["Критичний ризик", "Середній ризик"]).sum())
        )
        .reset_index()
        .rename(columns={"deputy_minister_by_ssp": "Заступник_Міністра"})
    )
    deputy_progress["Виконання"] = deputy_progress["Виконання"].fillna(0).round(1)
    deputy_progress["Покриття_%"] = (
        deputy_progress["Покриття"] / deputy_progress["Активних_заходів"] * 100
    ).fillna(0).round(1)
    deputy_progress["Dep_short"] = deputy_progress["Заступник_Міністра"].str[:30]
    deputy_progress_sorted = deputy_progress.sort_values("Виконання", ascending=False)

    st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="chart-title">Виконання за Заступниками Міністра</div>', unsafe_allow_html=True)

    fig_dep2 = px.bar(
        deputy_progress_sorted,
        x="Dep_short",
        y="Виконання",
        text=deputy_progress_sorted["Виконання"].apply(lambda x: f"{x:.1f}%"),
        hover_data={"Активних_заходів": True, "Покриття_%": True, "Ризикових": True},
        color="Виконання",
        color_continuous_scale=["#dc2626", "#fef08a", "#16a34a"],
        range_color=[0, 100],
        custom_data=["Заступник_Міністра", "Активних_заходів", "Покриття_%", "Ризикових"]
    )
    fig_dep2.update_traces(
        textposition="outside",
        textfont_size=10,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Виконання: %{y:.1f}%<br>"
            "Активних заходів: %{customdata[1]}<br>"
            "Покриття: %{customdata[2]:.1f}%<br>"
            "Ризикових: %{customdata[3]}"
            "<extra></extra>"
        ),
        marker_line_width=0
    )
    fig_dep2.update_layout(
        **CHART_LAYOUT,
        height=360,
        xaxis=dict(
            tickangle=-30,
            tickfont=dict(size=9),
            showgrid=False
        ),
        yaxis=dict(
            range=[0, 115],
            showgrid=True,
            gridcolor="#f1f5f9",
            ticksuffix="%"
        ),
        coloraxis_showscale=False,
        margin=dict(l=10, r=10, t=30, b=120)
    )
    st.plotly_chart(fig_dep2, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# VISUALIZATIONS: РИЗИКИ
# ============================================================

if not presentation_mode and view_mode in ["Усі візуалізації", "Ризики"]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Автоматична оцінка ризиків</div>', unsafe_allow_html=True)

    r1, r2 = st.columns([1, 1.6])

    with r1:
        st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="chart-title">Рівень ризику недосягнення</div>', unsafe_allow_html=True)

        fig_risk_pie = px.pie(
            risk_counts,
            names="auto_risk",
            values="Кількість",
            hole=0.52,
            color="auto_risk",
            color_discrete_map=RISK_COLORS
        )
        fig_risk_pie.update_traces(
            textfont_size=12,
            marker=dict(line=dict(color="#ffffff", width=2))
        )
        fig_risk_pie.update_layout(
            **CHART_LAYOUT,
            height=280,
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=True,
            legend=dict(orientation="v", x=1, y=0.5)
        )
        st.plotly_chart(fig_risk_pie, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with r2:
        st.markdown('<div class="section-title" style="margin-top:0;">Структура ризиків за самостійними структурними підрозділами</div>', unsafe_allow_html=True)
        st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="chart-title">Ризики за самостійними структурними підрозділами</div>', unsafe_allow_html=True)

        stacked = dep_active.groupby(["ssp_department", "auto_risk"]).size().reset_index(name="Кількість")
        # Filter out "Не оцінюється" for cleaner view
        stacked_vis = stacked[stacked["auto_risk"] != "Не оцінюється"].copy()

        fig_risk_bar = px.bar(
            stacked_vis,
            x="ssp_department",
            y="Кількість",
            color="auto_risk",
            color_discrete_map=RISK_COLORS,
            barmode="stack",
            labels={
                "ssp_department": "Самостійний структурний підрозділ",
                "auto_risk": "Ризик"
            }
        )
        fig_risk_bar.update_layout(
            **CHART_LAYOUT,
            height=310,
            xaxis=dict(tickangle=-35, tickfont=dict(size=9), showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="#f1f5f9"),
            legend=dict(orientation="h", x=0, y=-0.25),
            margin=dict(l=10, r=10, t=10, b=80)
        )
        st.plotly_chart(fig_risk_bar, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── SCATTER: Ризик × Виконання по ССП ────────────────────
    st.markdown("<hr class='vis-separator'>", unsafe_allow_html=True)
    st.markdown('<div class="section-title" style="margin-top:0;">Матриця ризик × виконання (по ССП)</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">Розмір бульбашки — кількість заходів; червоний квадрант — низьке виконання + високий ризик</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)

    scatter_df = dep_progress[dep_progress["Активних_заходів"] >= 1].copy()
    scatter_df["Частка_ризик"] = (scatter_df["Ризикових"] / scatter_df["Активних_заходів"] * 100).round(1)
    scatter_df["dep_short"] = scatter_df["ssp_department"].str[:18]

    if not scatter_df.empty:
        fig_scatter = go.Figure()
        # Квадранти фону
        fig_scatter.add_shape(type="rect", x0=0, x1=50, y0=50, y1=100,
            fillcolor="rgba(220,38,38,0.06)", line_width=0, layer="below")
        fig_scatter.add_shape(type="rect", x0=50, x1=100, y0=0, y1=50,
            fillcolor="rgba(217,119,6,0.05)", line_width=0, layer="below")
        fig_scatter.add_shape(type="rect", x0=50, x1=100, y0=50, y1=100,
            fillcolor="rgba(22,163,74,0.05)", line_width=0, layer="below")
        # Лінії розподілу
        fig_scatter.add_shape(type="line", x0=50, x1=50, y0=0, y1=100,
            line=dict(color="#cbd5e1", dash="dot", width=1))
        fig_scatter.add_shape(type="line", x0=0, x1=100, y0=50, y1=50,
            line=dict(color="#cbd5e1", dash="dot", width=1))

        for _, row in scatter_df.iterrows():
            pct_risk = row["Частка_ризик"]
            perf = row["Виконання"]
            cnt = row["Активних_заходів"]
            if pct_risk >= 50 and perf < 50:
                color = "#dc2626"
            elif pct_risk < 50 and perf >= 50:
                color = "#16a34a"
            else:
                color = "#d97706"
            fig_scatter.add_trace(go.Scatter(
                x=[perf], y=[pct_risk],
                mode="markers+text",
                marker=dict(size=max(10, min(cnt * 3, 50)), color=color, opacity=0.75,
                            line=dict(color="white", width=1.5)),
                text=[row["dep_short"]],
                textposition="top center",
                textfont=dict(size=9, color="#334155"),
                hovertemplate=(
                    f"<b>{row['ssp_department']}</b><br>"
                    f"Виконання: {perf:.1f}%<br>"
                    f"Частка ризикових: {pct_risk:.1f}%<br>"
                    f"Активних заходів: {cnt}<extra></extra>"
                ),
                showlegend=False
            ))

        fig_scatter.update_layout(
            **CHART_LAYOUT,
            height=420,
            xaxis=dict(title="Виконання, %", range=[-5, 110], showgrid=True, gridcolor="#f1f5f9", ticksuffix="%"),
            yaxis=dict(title="Частка ризикових заходів, %", range=[-5, 105], showgrid=True, gridcolor="#f1f5f9", ticksuffix="%"),
            margin=dict(l=60, r=20, t=20, b=60)
        )
        # Підписи квадрантів
        for txt, x, y, col in [
            ("🔴 Критична зона", 25, 95, "#dc2626"),
            ("🟡 Увага", 75, 25, "#d97706"),
            ("🟢 Норма", 75, 95, "#16a34a"),
        ]:
            fig_scatter.add_annotation(x=x, y=y, text=txt, showarrow=False,
                font=dict(size=10, color=col), xanchor="center")

        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("Недостатньо даних для побудови матриці.")

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
# ============================================================

if not presentation_mode and view_mode in ["Усі візуалізації", "Динаміка"]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Динаміка виконання</div>', unsafe_allow_html=True)

    trend_rows = []

    for y in years_for_calc:
        for q in quarters_for_calc:
            temp_raw = build_period_data(strat_df, requests_df, [y], [q])
            temp = apply_dashboard_filters(
                temp_raw,
                selected_department_indices,
                selected_goals if "dash_goals" in st.session_state else [],
                selected_tasks if "dash_tasks" in st.session_state else [],
                selected_measures if "dash_measures" in st.session_state else [],
                selected_product_types if "dash_product_types" in st.session_state else [],
                selected_deputies if "dash_deputies" in st.session_state else [],
                selected_statuses if "dash_statuses" in st.session_state else [],
                selected_sources if "dash_sources" in st.session_state else []
            )

            if temp.empty:
                value, cov, dev = 0, 0, -100
            else:
                value = mean_completion(temp)
                cov = calc_coverage(temp)
                dev = deviation_for_period(value)

            trend_rows.append({
                "Період": f"{y} {q}",
                "Рік": y,
                "Квартал": q,
                "Виконання": value,
                "Покриття": cov,
                "Відхилення за звітний період": dev
            })

    trend_df = pd.DataFrame(trend_rows)

    st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="chart-title">Тренд виконання, покриття і відхилення</div>', unsafe_allow_html=True)

    fig_trend = px.line(
        trend_df,
        x="Період",
        y=["Виконання", "Покриття", "Відхилення за звітний період"],
        markers=True,
        color_discrete_map={
            "Виконання": "#005BBB",
            "Покриття": "#0891b2",
            "Відхилення за звітний період": "#dc2626"
        }
    )
    fig_trend.update_traces(line_width=2.5, marker_size=7)
    fig_trend.update_layout(
        **CHART_LAYOUT,
        height=340,
        xaxis=dict(showgrid=False, tickangle=-20),
        yaxis=dict(showgrid=True, gridcolor="#f1f5f9", ticksuffix="%"),
        legend=dict(orientation="h", x=0, y=1.12),
        margin=dict(l=10, r=10, t=40, b=30)
    )
    st.plotly_chart(fig_trend, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ── WATERFALL: внесок кожної стратегічної цілі у відхилення ──
    st.markdown("<hr class='vis-separator'>", unsafe_allow_html=True)
    st.markdown('<div class="section-title" style="margin-top:0;">Водоспад відхилень за стратегічними цілями</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">Внесок кожної стратегічної цілі у загальне відхилення від планового рівня виконання</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)

    if not goal_progress.empty:
        wf_df = goal_progress.copy()
        wf_df["Відхилення"] = (wf_df["Виконання"] - 100).round(1)
        wf_df["label"] = wf_df["goal_code"].astype(str) + " " + wf_df["strategic_goal"].astype(str).str[:30]
        wf_df = wf_df.sort_values("Відхилення", ascending=True)

        colors_wf = ["#dc2626" if v < 0 else "#16a34a" for v in wf_df["Відхилення"]]

        fig_wf = go.Figure(go.Waterfall(
            name="Відхилення",
            orientation="h",
            measure=["relative"] * len(wf_df) + ["total"],
            y=list(wf_df["label"]) + ["Загальне відхилення"],
            x=list(wf_df["Відхилення"]) + [deviation_current],
            text=[f"{v:+.1f}%" for v in wf_df["Відхилення"]] + [f"{deviation_current:+.1f}%"],
            textposition="outside",
            connector=dict(line=dict(color="#e2e8f0", width=1)),
            increasing=dict(marker=dict(color="#16a34a")),
            decreasing=dict(marker=dict(color="#dc2626")),
            totals=dict(marker=dict(color="#005BBB")),
        ))
        fig_wf.update_layout(
            **CHART_LAYOUT,
            height=max(260, len(wf_df) * 36 + 80),
            xaxis=dict(title="Відхилення, в.п.", showgrid=True, gridcolor="#f1f5f9", ticksuffix="%",
                       zeroline=True, zerolinecolor="#94a3b8", zerolinewidth=1.5),
            yaxis=dict(showgrid=False),
            margin=dict(l=10, r=80, t=10, b=30),
            showlegend=False
        )
        st.plotly_chart(fig_wf, use_container_width=True)
    else:
        st.info("Недостатньо даних для побудови водоспаду.")

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
# ============================================================

if not presentation_mode and view_mode in ["Усі візуалізації", "Heatmap"]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Heatmap: самостійний структурний підрозділ × квартал</div>', unsafe_allow_html=True)

    heat_rows = []

    for y in years_for_calc:
        for q in quarters_for_calc:
            temp_raw = build_period_data(strat_df, requests_df, [y], [q])
            temp = apply_dashboard_filters(
                temp_raw,
                selected_department_indices,
                selected_goals if "dash_goals" in st.session_state else [],
                selected_tasks if "dash_tasks" in st.session_state else [],
                selected_measures if "dash_measures" in st.session_state else [],
                selected_product_types if "dash_product_types" in st.session_state else [],
                selected_deputies if "dash_deputies" in st.session_state else [],
                selected_statuses if "dash_statuses" in st.session_state else [],
                selected_sources if "dash_sources" in st.session_state else []
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
        st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="chart-title">Теплова карта виконання</div>', unsafe_allow_html=True)

        pivot = heat_df.pivot_table(
            index="Самостійний структурний підрозділ",
            columns="Період",
            values="Виконання",
            aggfunc="mean"
        ).fillna(0)

        fig_heat = px.imshow(
            pivot,
            color_continuous_scale=["#fee2e2", "#fef9c3", "#dcfce7"],
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
        st.plotly_chart(fig_heat, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("Недостатньо даних для побудови теплової карти.")

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# VISUALIZATIONS: ТАЙМЛАЙН ДЕДЛАЙНІВ
# ============================================================

if not presentation_mode and view_mode in ["Усі візуалізації", "Динаміка"]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Таймлайн дедлайнів</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">Кількість заходів із дедлайном у кожному кварталі · розбивка за статусом виконання</div>', unsafe_allow_html=True)

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
            s = row.get("status_display", "")
            if s == "Виконано":
                return "Виконано"
            if s in ["Частково виконано", "Виконується"]:
                return "В процесі"
            if row.get("status", "") == "Не подано":
                return "Без даних"
            return "Не виконано / ризик"

        timeline_data["tl_status"] = timeline_data.apply(_tl_status, axis=1)

        tl_grouped = (
            timeline_data
            .groupby(["deadline_label", "end_num", "tl_status"])
            .size()
            .reset_index(name="Кількість")
            .sort_values("end_num")
        )

        tl_color_map = {
            "Виконано": "#16a34a",
            "В процесі": "#d97706",
            "Без даних": "#94a3b8",
            "Не виконано / ризик": "#dc2626"
        }

        st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
        fig_tl2 = px.bar(
            tl_grouped,
            x="deadline_label",
            y="Кількість",
            color="tl_status",
            color_discrete_map=tl_color_map,
            barmode="stack",
            labels={"deadline_label": "Квартал дедлайну", "tl_status": "Статус"},
            text_auto=True,
        )
        fig_tl2.update_traces(textfont_size=10, textposition="inside")
        fig_tl2.update_layout(
            **CHART_LAYOUT,
            height=320,
            xaxis=dict(showgrid=False, tickangle=-20),
            yaxis=dict(showgrid=True, gridcolor="#f1f5f9"),
            legend=dict(orientation="h", x=0, y=1.1),
            margin=dict(l=10, r=10, t=40, b=40)
        )
        st.plotly_chart(fig_tl2, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("Дані про терміни виконання заходів відсутні.")

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# PROBLEM MEASURES
# ============================================================

if not presentation_mode:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Проблемні заходи</div>', unsafe_allow_html=True)

    risk_table = active[
        (
            active["auto_risk"].isin(["Критичний ризик", "Середній ризик"]) |
            (active["status"] == "Не подано") |
            (active["performance_score"].fillna(0) < 75)
        )
        & (active["included_in_assessment"] == True)
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

        st.dataframe(
            risk_table[[
                "Період", "Код", "Захід", "Індикатор", "Головний ССП",
                "Статус виконання", "Планове значення", "Фактичне значення",
                "Traffic light", "Рівень ризику", "Risk score", "Причина ризику", "Опис прогресу"
            ]],
            use_container_width=True,
            hide_index=True
        )

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# FULL TABLE
# ============================================================

if not presentation_mode and view_mode == "Таблиці":
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

    st.dataframe(
        full[[
            "Період", "Код", "Захід", "Індикатор", "Одиниця виміру", "Тип продукту",
            "Головний ССП", "Джерело даних", "Початок", "Кінець",
            "Планове значення", "Фактичне значення", "Статус виконання",
            "Оцінка виконання, %", "Traffic light", "Ризик", "Risk score", "Причина ризику"
        ]],
        use_container_width=True,
        hide_index=True
    )

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# METHODOLOGY
# ============================================================

if not presentation_mode:
    with st.expander("Методологія розрахунку"):
        st.markdown("""
        <div class="methodology-box">
        <strong>Активні заходи</strong> — заходи, період виконання яких охоплює обраний рік і квартал.<br><br>

        <strong>Виконання СП</strong> рахується як середня оцінка виконання активних заходів:
        <ul>
            <li>якщо є планове та фактичне значення — використовується співвідношення факт / план;</li>
            <li>якщо план / факт не можна порахувати числово — використовується статус виконання;</li>
            <li>«Виконано» = 100%; «Частково виконано» = 75%; «Виконується» = 50%;</li>
            <li>«Не виконано», «Не подано», «Не розпочато», «Прострочено», «Потребує уваги» = 0%;</li>
            <li>«Термін не настав» та «Втратив актуальність» не включаються до оцінки ризику.</li>
        </ul>

        <strong>Risk score</strong> визначається автоматично на основі стану виконання:
        відсутність погоджених даних, відставання від плану, прострочення строку, проблемний статус.<br><br>

        <strong>Traffic light:</strong>
        🟢 100%+ — у графіку | 🟡 75–99% — часткове | 🔴 &lt;75% — відставання | ⚪ не оцінюється.<br><br>

        <strong>Відхилення за звітний період</strong> = середній відсоток виконання мінус 100%.
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# FOOTER
# ============================================================

st.markdown("""
<div class="footer">
    <strong>Розроблено департаментом стратегічного планування та макроекономічного прогнозування</strong><br>
    Версія DEMO 1.4 | 2026 | Внутрішня система моніторингу стратегічного плану
</div>
""", unsafe_allow_html=True)
