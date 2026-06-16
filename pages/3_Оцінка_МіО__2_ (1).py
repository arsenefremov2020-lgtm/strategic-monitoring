import re
import html
import math
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Оцінка МіО", layout="wide")

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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', 'Helvetica Neue', 'Arial', sans-serif;
}

.stApp {
    background: #f0f4f9;
}

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

/* ── UA stripe ── */
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
    padding: clamp(16px, 2.2vw, 24px) clamp(16px, 2.5vw, 32px);
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(0,91,187,0.08), 0 1px 4px rgba(0,0,0,0.04);
    display: block;
}

.header-main { width: 100%; min-width: 200px; }

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
    line-height: 1.55;
    max-width: none;
    width: 100%;
}

.header-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: flex-start;
    padding-top: 14px;
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
    font-size: clamp(14px, 1.3vw, 17px);
    font-weight: 800;
    color: #0c1a3a;
    margin: 0 0 14px 0;
}

.section-subtitle {
    font-size: clamp(11px, 0.95vw, 13px);
    color: #64748b;
    margin: 0 0 12px 0;
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

.filter-title {
    font-size: clamp(14px, 1.3vw, 17px);
    font-weight: 800;
    color: #0c1a3a;
    margin-bottom: 12px;
}

/* ── Excel-style mode tabs (режими = вкладки) ── */
.mio-modebar {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
    padding: 8px 8px 0 8px;
    margin-bottom: 0;
    border-bottom: 2px solid #c2d4f0;
    background: linear-gradient(180deg, #f8fbff 0%, #eef3fb 100%);
    border-radius: 12px 12px 0 0;
}
.mio-modebar-wrap {
    background: #ffffff;
    border: 1px solid #dde3ed;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0,91,187,0.06);
    margin-bottom: 18px;
    overflow: hidden;
}
.mio-modebar-meta {
    padding: 10px 16px;
    font-size: 12px;
    color: #475569;
    font-weight: 600;
}

/* Перетворюємо горизонтальний st.radio на вкладки Excel */
div[data-testid="stRadio"].mio-tabs > div { gap: 4px !important; }

/* ── Легенда станів ── */
.mio-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 4px 0 14px 0;
}
.mio-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 700;
    padding: 5px 12px;
    border-radius: 20px;
    border: 1px solid transparent;
}
.mio-chip .dot { width: 9px; height: 9px; border-radius: 50%; }
.mio-chip.done     { background:#dcfce7; color:#166534; border-color:#bbf7d0; }
.mio-chip.partial  { background:#fef3c7; color:#92400e; border-color:#fde68a; }
.mio-chip.notdone  { background:#fee2e2; color:#991b1b; border-color:#fecaca; }
.mio-chip.notyet   { background:#e2e8f0; color:#475569; border-color:#cbd5e1; }
.mio-chip.obsolete { background:#ede9fe; color:#5b21b6; border-color:#ddd6fe; }
.mio-chip.done .dot     { background:#16a34a; }
.mio-chip.partial .dot  { background:#d97706; }
.mio-chip.notdone .dot  { background:#dc2626; }
.mio-chip.notyet .dot   { background:#94a3b8; }
.mio-chip.obsolete .dot { background:#7c3aed; }

/* ── Заглушка «у розробці» ── */
.mio-placeholder {
    text-align: center;
    padding: 48px 24px;
    border: 1.5px dashed #c2d4f0;
    border-radius: 14px;
    background: #f8fbff;
    color: #475569;
}
.mio-placeholder .big { font-size: 40px; margin-bottom: 8px; }
.mio-placeholder .ttl { font-size: 18px; font-weight: 800; color: #0c1a3a; margin-bottom: 6px; }

/* ══════════════════════════════════════════════
   Красива таблиця режиму «М_заходи»
   ══════════════════════════════════════════════ */
.mio-tablewrap {
    max-height: 640px;
    overflow: auto;
    border: 1px solid #dbe3ee;
    border-radius: 14px;
    box-shadow: 0 4px 18px rgba(15,30,60,0.06);
    background: #ffffff;
    position: relative;
}
.mio-tablewrap::-webkit-scrollbar { height: 11px; width: 11px; }
.mio-tablewrap::-webkit-scrollbar-thumb {
    background: #c2d0e4; border-radius: 8px; border: 2px solid #ffffff;
}
.mio-tablewrap::-webkit-scrollbar-thumb:hover { background: #9fb4d4; }
.mio-tablewrap::-webkit-scrollbar-track { background: #f1f5fb; }

.mio-table {
    border-collapse: separate;
    border-spacing: 0;
    width: 100%;
    font-size: 12.5px;
    color: #1e293b;
    min-width: 1080px;
}

/* ── Заголовки ── */
.mio-table thead th {
    position: sticky;
    background: #eef3fb;
    font-weight: 800;
    color: #1e3a6e;
    text-align: center;
    padding: 8px 10px;
    border-bottom: 1px solid #d4deec;
    white-space: nowrap;
}
.mio-table thead tr.grp th { top: 0; z-index: 3; font-size: 12px; }
.mio-table thead tr.sub th { top: 35px; z-index: 3; font-weight: 700; font-size: 11px; color: #5b7099; }
.mio-table thead .grp-q    { background: #eef3fb; }
.mio-table thead .grp-year { background: #dceafc; color: #0c2f6e; border-left: 2px solid #b6d2f5; border-right: 2px solid #b6d2f5; }
.mio-table thead .sub-year { background: #dceafc; }
.mio-table thead .grp-plan { background: #f3f0fb; color: #4c1d95; }
.mio-table thead .sub-f { background: #f6f9fe; }
.mio-table thead .sub-s { background: #eef3fb; }

/* ── Комірка-якір (захід), закріплена зліва ── */
.mio-table th.m-anchor, .mio-table td.m-anchor {
    position: sticky;
    left: 0;
    z-index: 2;
    width: 360px;
    min-width: 360px;
    max-width: 360px;
    text-align: left;
    border-right: 2px solid #dbe3ee;
}
.mio-table thead th.m-anchor { z-index: 4; background: #e6edf8; vertical-align: middle; }
.mio-table td.m-anchor { background: #ffffff; padding: 9px 12px; vertical-align: top; }
.mio-table tbody tr:nth-child(even) td.m-anchor { background: #f8fafd; }
.mio-table tbody tr:hover td.m-anchor { background: #eef5ff; }

.m-codeline { display: flex; align-items: center; flex-wrap: wrap; gap: 5px; margin-bottom: 3px; }
.m-code {
    font-weight: 900; color: #0c2f6e; font-size: 12.5px;
    background: #e7f0fd; border: 1px solid #c3d8f5;
    padding: 1px 7px; border-radius: 6px; letter-spacing: .01em;
}
.m-name { font-weight: 700; color: #16233f; line-height: 1.32; font-size: 12.5px; }
.m-ind {
    color: #64748b; font-size: 11px; line-height: 1.3; margin-top: 3px;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden;
}
.tag {
    font-size: 9.5px; font-weight: 800; padding: 1px 6px; border-radius: 20px;
    letter-spacing: .02em; white-space: nowrap;
}
.tag-goal { background: #eef3fb; color: #1e3a6e; border: 1px solid #c9d8ef; }
.tag-task { background: #f0fbf6; color: #0f766e; border: 1px solid #b8e6d7; }
.tag-unit { background: #fbf8ef; color: #92600e; border: 1px solid #ecdcb0; }

/* ── Комірки даних ── */
.mio-table tbody td {
    padding: 7px 8px;
    border-bottom: 1px solid #eef2f8;
    text-align: center;
    vertical-align: middle;
    background: #ffffff;
}
.mio-table tbody tr:nth-child(even) td { background: #f8fafd; }
.mio-table tbody tr:hover td { background: #eef5ff; }
.mio-table tbody tr:last-child td { border-bottom: none; }

.m-fact { font-weight: 700; color: #0f1f3d; font-variant-numeric: tabular-nums; }
.m-empty { color: #cbd5e1; font-weight: 700; }
.m-plan { font-weight: 800; color: #1e293b; font-variant-numeric: tabular-nums;
          background: #fbfaff !important; }
.m-styear { border-left: 1px solid #e6edf8; }

/* ── Чипи стану ── */
.tchip {
    display: inline-block; font-weight: 800; font-size: 10.5px;
    padding: 2px 8px; border-radius: 20px; white-space: nowrap; line-height: 1.5;
    border: 1px solid transparent;
}
.tchip.lg { font-size: 11px; padding: 3px 10px; }
.tchip.done     { background: #dcfce7; color: #166534; border-color: #bbf7d0; }
.tchip.partial  { background: #fef3c7; color: #92400e; border-color: #fde68a; }
.tchip.notdone  { background: #fee2e2; color: #991b1b; border-color: #fecaca; }
.tchip.notyet   { background: #eef2f7; color: #64748b; border-color: #dde5ef; }
.tchip.obsolete { background: #ede9fe; color: #5b21b6; border-color: #ddd6fe; }

/* ── Прогрес-бар «Факт/План» ── */
.m-ratio { min-width: 120px; }
.rbar {
    position: relative; height: 22px; border-radius: 7px; overflow: hidden;
    background: #eef2f8; border: 1px solid #e2e8f0; min-width: 96px;
}
.rfill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 7px 0 0 7px; }
.rbar.done .rfill     { background: linear-gradient(90deg,#34d399,#16a34a); }
.rbar.partial .rfill  { background: linear-gradient(90deg,#fbbf24,#d97706); }
.rbar.notdone .rfill  { background: linear-gradient(90deg,#f87171,#dc2626); }
.rbar.notyet .rfill   { background: #cbd5e1; }
.rlabel {
    position: relative; z-index: 1; display: block; text-align: center;
    line-height: 22px; font-size: 11px; font-weight: 800; color: #0f1f3d;
    font-variant-numeric: tabular-nums; text-shadow: 0 1px 2px rgba(255,255,255,.6);
}

/* ── Streamlit widget overrides ── */
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
    background-color: #d7eaff !important;
    border: 1px solid #8fb3df !important;
    border-radius: 10px !important;
    min-height: 40px !important;
}

div[data-testid="stSelectbox"] label,
div[data-testid="stMultiSelect"] label {
    font-weight: 750 !important;
    color: #1e293b !important;
}

/* ── KPI grid ── */
.kpi-grid {
    display: grid;
    gap: clamp(8px, 1.2vw, 14px);
    margin: 6px 0 4px 0;
}

.kpi-grid-4 { grid-template-columns: repeat(4, 1fr); }
.kpi-grid-5 { grid-template-columns: repeat(5, 1fr); }
.kpi-grid-6 { grid-template-columns: repeat(6, 1fr); }
.kpi-grid-8 { grid-template-columns: repeat(4, 1fr); }

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

.kpi-blue   { background: #eff6ff; border-color: #bfdbfe; }
.kpi-green  { background: #f0fdf4; border-color: #bbf7d0; }
.kpi-red    { background: #fef2f2; border-color: #fecaca; }
.kpi-yellow { background: #fffbeb; border-color: #fde68a; }
.kpi-gray   { background: #f8fafc; border-color: #e2e8f0; }
.kpi-teal   { background: #f0fdfa; border-color: #99f6e4; }
.kpi-indigo { background: #eef2ff; border-color: #c7d2fe; }

/* ── Integral score block ── */
.integral-block {
    background: linear-gradient(135deg, #0c1a3a 0%, #1e3a6e 100%);
    border-radius: 14px;
    padding: 24px 28px;
    color: white;
    text-align: center;
    box-shadow: 0 8px 24px rgba(0,91,187,0.25);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 200px;
}

.integral-label {
    font-size: clamp(11px, 1vw, 13px);
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
}

.integral-value {
    font-size: clamp(40px, 5vw, 64px);
    font-weight: 900;
    color: #ffffff;
    line-height: 1;
    margin-bottom: 8px;
}

.integral-level {
    font-size: clamp(12px, 1.1vw, 15px);
    font-weight: 700;
    padding: 5px 14px;
    border-radius: 20px;
    margin-top: 6px;
}

/* ── Goal row (like on screenshot) ── */
.goal-row {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    margin-bottom: 10px;
    overflow: hidden;
}

.goal-row-header {
    display: flex;
    align-items: center;
    padding: 12px 16px;
    gap: 12px;
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
}

.goal-code-badge {
    background: #005BBB;
    color: white;
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 800;
    white-space: nowrap;
}

.goal-name-text {
    font-size: clamp(12px, 1.1vw, 14px);
    font-weight: 700;
    color: #0c1a3a;
    flex: 1;
    line-height: 1.35;
}

.goal-score-text {
    font-size: clamp(14px, 1.3vw, 18px);
    font-weight: 900;
    white-space: nowrap;
}

.goal-score-green  { color: #16a34a; }
.goal-score-yellow { color: #d97706; }
.goal-score-red    { color: #dc2626; }

/* ── Progress bar ── */
.prog-bar-bg {
    background: #e2e8f0;
    border-radius: 99px;
    height: 8px;
    overflow: hidden;
    margin: 10px 16px;
}

.prog-bar-fill {
    height: 100%;
    border-radius: 99px;
    transition: width 0.4s;
}

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

.insight-item.warn   { border-left-color: #d97706; background: #fffbeb; }
.insight-item.danger { border-left-color: #dc2626; background: #fef2f2; }
.insight-item.success { border-left-color: #16a34a; background: #f0fdf4; }
.insight-item.info   { border-left-color: #0891b2; background: #ecfeff; }

/* ── Methodology box ── */
.methodology-box {
    background: #f8fafc;
    border: 1px solid #dde3ed;
    border-radius: 10px;
    padding: 16px 20px;
    font-size: clamp(11px, 0.95vw, 14px);
    color: #334155;
    line-height: 1.7;
}

.methodology-box ol {
    padding-left: 20px;
    margin: 10px 0 0 0;
}

.methodology-box li {
    margin-bottom: 6px;
}

/* ── Divider ── */
.vis-separator {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 22px 0;
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

.footer strong { color: #475569; }

@media (max-width: 900px) {
    .kpi-grid-4, .kpi-grid-5, .kpi-grid-6, .kpi-grid-8 {
        grid-template-columns: repeat(2, 1fr);
    }
    .header-card { flex-direction: column; }
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# HELPERS
# ============================================================

def raw_value(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def is_empty(value):
    text = raw_value(value).lower().replace(" ", "")
    return text in ["", "nan", "none", "н.д.", "нд", "-", "—"]


def parse_number(value):
    text = raw_value(value)
    if is_empty(text):
        return None
    text = text.replace("\u00a0", " ").replace("%", "").replace(",", ".")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in ["", ".", "-", "-."]:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def clamp(value, low=0.0, high=120.0):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return max(low, min(high, float(value)))


def is_yes_no_unit(unit):
    text = raw_value(unit).lower()
    return "так/ні" in text or ("так" in text and "ні" in text)


def is_positive_yes(value):
    text = raw_value(value).lower()
    return text in ["так", "yes", "y", "true", "1", "виконано"] or text.startswith("так")


def status_score_val(status):
    text = raw_value(status).lower()
    mapping = {
        "виконано": 100,
        "виконано частково": 60,
        "виконується": 50,
        "потребує уваги": 40,
        "прострочено": 25,
        "не розпочато": 0,
    }
    for key, val in mapping.items():
        if key in text:
            return val
    return None


def score_level(score):
    if score is None or (isinstance(score, float) and math.isnan(score)):
        return "Немає даних"
    if score >= 100:
        return "Виконано"
    if score >= 80:
        return "Високий прогрес"
    if score >= 50:
        return "Частковий прогрес"
    if score > 0:
        return "Критичне відставання"
    return "Не виконано"


def score_risk(level):
    if level in ["Виконано", "Високий прогрес"]:
        return "Низький"
    if level == "Частковий прогрес":
        return "Середній"
    return "Високий"


def level_color(score):
    if score is None:
        return "#94a3b8"
    if score >= 80:
        return "#16a34a"
    if score >= 50:
        return "#d97706"
    return "#dc2626"


def level_bg(score):
    if score is None:
        return "#f1f5f9"
    if score >= 80:
        return "#f0fdf4"
    if score >= 50:
        return "#fffbeb"
    return "#fef2f2"


def level_pill_class(score):
    if score is None:
        return "background:#e2e8f0;color:#475569;"
    if score >= 80:
        return "background:#dcfce7;color:#166534;"
    if score >= 50:
        return "background:#fef3c7;color:#92400e;"
    return "background:#fee2e2;color:#991b1b;"


def goal_score_class(score):
    if score is None:
        return "goal-score-red"
    if score >= 80:
        return "goal-score-green"
    if score >= 50:
        return "goal-score-yellow"
    return "goal-score-red"


def code_sort_key(value):
    """Natural numeric sort for codes like 1., 1.1., 1.1.1."""
    text = raw_value(value)
    nums = re.findall(r"\d+", text)
    if not nums:
        return (9999, text)
    return tuple(int(x) for x in nums) + tuple([0] * max(0, 5 - len(nums)))


def department_sort_key(value):
    """Sorts SСП by the first visible number while keeping the full text unchanged."""
    text = raw_value(value)
    match = re.search(r"\d+", text)
    if match:
        return (int(match.group(0)), text.lower())
    return (9999, text.lower())


# ============================================================
# DEPUTY MINISTERS BY MAIN SSP INDEX
# ============================================================
# Джерело логіки: розподіл заступників за Індексом ССП.
# Використовується лише для режиму "За заступниками Міністра".
# Інші розрахунки сторінки не змінює.

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


def short_name(value, limit=70):
    text = raw_value(value)
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def add_order_columns(df, code_col, name_col=None, label_col=None, label_limit=70):
    out = df.copy()
    out["_sort_key"] = out[code_col].apply(code_sort_key)
    out = out.sort_values("_sort_key", ascending=True).copy()
    if label_col and name_col:
        out[label_col] = out[code_col].astype(str).str.strip() + " " + out[name_col].astype(str).apply(lambda x: short_name(x, label_limit))
    return out


def monitoring_status_counts(monitoring_df, selected_year, selected_quarter, active_codes=None):
    """Counts approved / pending / not-approved submissions for the selected period."""
    if monitoring_df.empty:
        return {"approved": 0, "pending": 0, "rejected": 0, "approved_codes": set(), "pending_codes": set(), "rejected_codes": set()}

    df = monitoring_df.copy()
    for col in ["year", "quarter", "approval_status", "strat_code", "submitted_at"]:
        if col not in df.columns:
            df[col] = ""

    df = df[df["year"].astype(str).str.strip() == str(selected_year)].copy()
    if selected_quarter != "Усі квартали":
        q = selected_quarter.replace(" квартал", "").strip()
        df = df[df["quarter"].astype(str).str.strip() == q].copy()

    df["_code"] = df["strat_code"].astype(str).str.strip()
    if active_codes is not None:
        active_codes = {raw_value(c) for c in active_codes}
        df = df[df["_code"].isin(active_codes)].copy()

    if "submitted_at" in df.columns:
        df["_dt"] = pd.to_datetime(df["submitted_at"], errors="coerce")
        df = df.sort_values("_dt").drop_duplicates("_code", keep="last")
    else:
        df = df.drop_duplicates("_code", keep="last")

    status = df["approval_status"].astype(str).str.strip().str.lower()
    approved_mask = status.eq("погоджено")
    pending_mask = status.str.contains("розгляд|очіку|pending|submitted|на погоджен", regex=True, na=False)
    rejected_mask = (~approved_mask) & (~pending_mask)

    return {
        "approved": int(approved_mask.sum()),
        "pending": int(pending_mask.sum()),
        "rejected": int(rejected_mask.sum()),
        "approved_codes": set(df.loc[approved_mask, "_code"]),
        "pending_codes": set(df.loc[pending_mask, "_code"]),
        "rejected_codes": set(df.loc[rejected_mask, "_code"]),
    }


def classify_measure_structure(row):
    """Maps measure status into the requested portfolio structure categories."""
    status = raw_value(row.get("latest_status", "")).lower()
    score = row.get("measure_score", 0)
    has_data = bool(row.get("has_approved_data", False))

    if "не настав" in status or "ще не настав" in status:
        return "Термін виконання не настав"
    if "простроч" in status or "протерм" in status:
        return "Протерміновані"
    if score is not None and score >= 100:
        return "Виконано"
    if has_data:
        return "Виконується"
    return "Протерміновані"


def structure_counts_df(evaluation_df):
    order = ["Виконано", "Виконується", "Термін виконання не настав", "Протерміновані"]
    if evaluation_df.empty:
        return pd.DataFrame({"Статус": order, "Кількість": [0, 0, 0, 0]})
    tmp = evaluation_df.copy()
    tmp["Статус"] = tmp.apply(classify_measure_structure, axis=1)
    counts = tmp["Статус"].value_counts().to_dict()
    return pd.DataFrame({"Статус": order, "Кількість": [int(counts.get(x, 0)) for x in order]})


def goal_portfolio_df(evaluation_df):
    """Shows each strategic goal's weight in the overall portfolio and its problem load."""
    if evaluation_df.empty:
        return pd.DataFrame(columns=[
            "goal_code", "goal_name", "total_measures", "portfolio_share",
            "completed_count", "in_progress_count", "not_due_count", "delayed_count",
            "problem_count", "problem_portfolio_share", "problem_inside_goal_share", "_sort_key"
        ])

    tmp = evaluation_df.copy()
    tmp["Статус"] = tmp.apply(classify_measure_structure, axis=1)
    total_portfolio = max(1, len(tmp))

    rows = []
    for (g_code, g_name), grp in tmp.groupby(["goal_code", "goal_name"], dropna=False):
        total = len(grp)
        completed = int((grp["Статус"] == "Виконано").sum())
        in_progress = int((grp["Статус"] == "Виконується").sum())
        not_due = int((grp["Статус"] == "Термін виконання не настав").sum())
        delayed = int((grp["Статус"] == "Протерміновані").sum())
        problem = delayed
        rows.append({
            "goal_code": raw_value(g_code),
            "goal_name": raw_value(g_name),
            "total_measures": total,
            "portfolio_share": round(total / total_portfolio * 100, 1),
            "completed_count": completed,
            "in_progress_count": in_progress,
            "not_due_count": not_due,
            "delayed_count": delayed,
            "problem_count": problem,
            "problem_portfolio_share": round(problem / total_portfolio * 100, 1),
            "problem_inside_goal_share": round(problem / total * 100, 1) if total else 0.0,
            "_sort_key": code_sort_key(g_code),
        })

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["problem_count", "total_measures", "_sort_key"], ascending=[False, False, True]).copy()
    return out


def extract_main_ssp_index(value):
    """
    Extracts the main SSP index from the department field.
    Example: "20 Директорат..." → "20".
    """
    match = re.search(r"\d+", raw_value(value))
    return match.group(0) if match else ""


def deputy_by_department(value):
    """
    Maps the main SSP index to the corresponding Deputy Minister.
    Empty SSP 78/79 or missing mapping are grouped as "Не визначено".
    """
    ssp_index = extract_main_ssp_index(value)
    deputy = DEPUTY_MINISTER_BY_SSP.get(ssp_index, "")
    return deputy if deputy else "Не визначено"


def deputy_sort_key(value):
    text = raw_value(value)
    if text == "Не визначено":
        return (9999, text.lower())
    return (0, text.lower())


def build_deputy_evaluation_df(evaluation_df):
    """
    Builds Deputy Minister aggregation from the already calculated evaluation_df.
    This does not change measure scoring. It only adds a management grouping:
    main SSP index → Deputy Minister.
    """
    if evaluation_df.empty:
        return pd.DataFrame(columns=[
            "Заступник Міністра", "Кількість заходів", "Погоджено",
            "Без погоджених даних", "Заходів з ризиками", "Середня оцінка, %",
            "Високий ризик", "Частковий прогрес", "Виконано / високий прогрес",
            "_sort_key"
        ])

    df = evaluation_df.copy()
    df["main_ssp_index"] = df["department"].apply(extract_main_ssp_index)
    df["deputy_minister"] = df["department"].apply(deputy_by_department)

    grouped = (
        df
        .groupby("deputy_minister", dropna=False)
        .agg(
            measures_count=("measure_code", "count"),
            approved_count=("has_approved_data", "sum"),
            without_data=("has_approved_data", lambda x: int((~x.astype(bool)).sum())),
            risk_measures=("has_risks", "sum"),
            avg_score=("measure_score", "mean"),
            high_risk=("risk_level", lambda x: int((x == "Високий").sum())),
            partial_progress=("level", lambda x: int((x == "Частковий прогрес").sum())),
            good_progress=("level", lambda x: int(x.isin(["Виконано", "Високий прогрес"]).sum())),
        )
        .reset_index()
    )

    grouped["avg_score"] = grouped["avg_score"].fillna(0).round(1)
    grouped["coverage_share"] = (
        grouped["approved_count"] / grouped["measures_count"].replace(0, pd.NA) * 100
    ).fillna(0).round(1)
    grouped["risk_share"] = (
        grouped["risk_measures"] / grouped["measures_count"].replace(0, pd.NA) * 100
    ).fillna(0).round(1)
    grouped["_sort_key"] = grouped["deputy_minister"].apply(deputy_sort_key)

    grouped = grouped.sort_values(["avg_score", "measures_count"], ascending=[False, False]).copy()

    return grouped.rename(columns={
        "deputy_minister": "Заступник Міністра",
        "measures_count": "Кількість заходів",
        "approved_count": "Погоджено",
        "without_data": "Без погоджених даних",
        "risk_measures": "Заходів з ризиками",
        "avg_score": "Середня оцінка, %",
        "high_risk": "Високий ризик",
        "partial_progress": "Частковий прогрес",
        "good_progress": "Виконано / високий прогрес",
        "coverage_share": "Покриття погодженими, %",
        "risk_share": "Частка ризикових, %",
    })


def build_deputy_measure_detail_df(evaluation_df):
    """
    Builds measure-level details for the Deputy Minister view.
    """
    if evaluation_df.empty:
        return pd.DataFrame()

    df = evaluation_df.copy()
    df["Індекс ССП"] = df["department"].apply(extract_main_ssp_index)
    df["Заступник Міністра"] = df["department"].apply(deputy_by_department)
    df["Самостійний структурний підрозділ"] = df["department"]
    df["Код заходу"] = df["measure_code"]
    df["Захід"] = df["measure_name"].apply(lambda x: short_name(x, 110))
    df["Стратегічна ціль"] = df["goal_code"].astype(str).str.strip() + " " + df["goal_name"].astype(str).apply(lambda x: short_name(x, 70))
    df["Оцінка, %"] = df["measure_score"].round(1)
    df["Рівень"] = df["level"]
    df["Ризик"] = df["risk_level"]
    df["Погоджені дані"] = df["has_approved_data"].apply(lambda x: "Так" if bool(x) else "Ні")
    df["Наявні ризики"] = df["has_risks"].apply(lambda x: "Так" if bool(x) else "Ні")

    return df[[
        "Заступник Міністра", "Індекс ССП", "Самостійний структурний підрозділ",
        "Стратегічна ціль", "Код заходу", "Захід", "Оцінка, %",
        "Рівень", "Ризик", "Погоджені дані", "Наявні ризики"
    ]].sort_values(
        ["Заступник Міністра", "Індекс ССП", "Код заходу"],
        key=lambda col: col.map(lambda x: code_sort_key(x) if col.name in ["Код заходу"] else x)
    )



def department_execution_df(evaluation_df):
    if evaluation_df.empty:
        return pd.DataFrame(columns=["Самостійний структурний підрозділ", "Рівень виконання, %", "_sort_key"])
    df = evaluation_df.copy()
    df["department"] = df["department"].astype(str).str.strip()
    df = df[df["department"].ne("") & df["department"].str.lower().ne("nan")].copy()
    if df.empty:
        return pd.DataFrame(columns=["Самостійний структурний підрозділ", "Рівень виконання, %", "_sort_key"])
    out = df.groupby("department", dropna=False).agg(score=("measure_score", "mean")).reset_index()
    out["Рівень виконання, %"] = out["score"].round(1)
    out["Самостійний структурний підрозділ"] = out["department"]
    out["_sort_key"] = out["department"].apply(department_sort_key)
    out = out.sort_values("_sort_key", ascending=True)
    return out[["Самостійний структурний підрозділ", "Рівень виконання, %", "_sort_key"]]


# ============================================================
# DATA LOADING — DUAL STREAM ARCHITECTURE
# ============================================================
# Stream 1 (Excel): strategic matrix structure and annual plan values
#   Страт_матриця → hierarchy, departments, indicators, targets
# Stream 2 (Supabase): measures execution data (approved submissions)
# ============================================================

MIO_SHEET      = SHEET_NAME  # важливо: оцінка прив’язана до аркуша «Страт_матриця»
MEASURES_SHEET = "РВ (СЦ, Завд.)_РОЗРАХ"

# Optional progress column positions. Для аркуша «Страт_матриця» ці колонки не використовуються.
YEAR_COLS = {
    2026: {"fact": 10, "progress": 13},  # J=fact, M=progress
    2027: {"fact": 14, "progress": 17},  # N=fact, Q=progress
    2028: {"fact": 18, "progress": 23},  # R=fact, W=progress
}
# РВ (СЦ, Завд.)_РОЗРАХ — annual measure score columns (1-indexed, 0–1 scale):
MEASURE_EXEC_COL = {2026: 8, 2027: 15, 2028: 22}  # H, O, V


@st.cache_data
def load_strat_matrix():
    """Loads Страт_матриця: measures list with hierarchy and annual targets."""
    raw = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=None, engine="openpyxl")
    data = raw.iloc[7:].copy()

    def safe_col(idx):
        if idx < data.shape[1]:
            return data.iloc[:, idx]
        return pd.Series([""] * len(data), index=data.index)

    df = pd.DataFrame({
        "type_marker":     safe_col(1),
        "code":            safe_col(2),
        "name":            safe_col(3),
        "product_type":    safe_col(4),
        "indicator":       safe_col(5),
        "unit":            safe_col(6),
        "base_2021":       safe_col(7),
        "fact_2024":       safe_col(8),
        "fact_2025":       safe_col(9),
        "target_2026":     safe_col(10),
        "target_2027":     safe_col(11),
        "target_2028":     safe_col(12),
        "target_2028_end": safe_col(13),
        "target_2034":     safe_col(14),
        "department":      safe_col(17),
        "resp_co_1":       safe_col(18),
        "resp_co_2":       safe_col(19),
    })

    df = df.dropna(subset=["code"]).copy()
    df["code"] = df["code"].astype(str).str.strip()
    df["type_marker"] = df["type_marker"].astype(str).str.strip()

    cur_goal_code, cur_goal_name = "", ""
    cur_task_code, cur_task_name = "", ""
    obj_types, pg_codes, pg_names, pt_codes, pt_names = [], [], [], [], []

    for _, row in df.iterrows():
        marker = raw_value(row["type_marker"]).lower()
        code   = raw_value(row["code"])
        name   = raw_value(row["name"])
        dots   = code.count(".")

        if "стратегічна ціль" in marker:
            obj_type = "goal"
            cur_goal_code, cur_goal_name = code, name
            cur_task_code, cur_task_name = "", ""
        elif "завдання" in marker:
            obj_type = "task"
            cur_task_code, cur_task_name = code, name
        elif "заход" in marker or dots >= 3:
            obj_type = "measure"
        elif cur_task_code:
            obj_type = "task_indicator"
        elif cur_goal_code:
            obj_type = "goal_indicator"
        else:
            obj_type = "other"

        obj_types.append(obj_type)
        pg_codes.append(cur_goal_code)
        pg_names.append(cur_goal_name)
        pt_codes.append(cur_task_code)
        pt_names.append(cur_task_name)

    df["object_type"]     = obj_types
    df["parent_goal_code"] = pg_codes
    df["parent_goal_name"] = pg_names
    df["parent_task_code"] = pt_codes
    df["parent_task_name"] = pt_names
    return df


@st.cache_data
def load_mio_excel():
    """
    STREAM 1a — Excel Страт_матриця.
    Reads pre-computed fact values and progress scores for goals/tasks indicators.
    When the Excel file is updated with new fact data, the progress scores
    recalculate automatically and this function picks them up on next load.
    Returns:
      indicators_df: full row-level DataFrame
      code_progress: dict {code → {year → avg_progress_%}}
        - goals:  average of their direct indicators' progress scores
        - tasks:  average of their indicators' progress scores
    """
    try:
        raw = pd.read_excel(
            FILE_PATH, sheet_name=MIO_SHEET,
            header=None, engine="openpyxl"
        )
    except Exception:
        return pd.DataFrame(), {}

    data = raw.iloc[7:].copy().reset_index(drop=True)

    rows_list = []
    cur_goal, cur_task = "", ""

    for i in range(len(data)):
        def sc(col_1idx):  # safe cell read
            try:
                return data.iloc[i, col_1idx - 1]
            except (IndexError, KeyError):
                return None

        type_m = raw_value(sc(2)).lower()
        code_v = raw_value(sc(3))
        name_v = raw_value(sc(4))

        if "стратегічна ціль" in type_m:
            cur_goal, cur_task, obj_t = code_v, "", "goal"
        elif "завдання" in type_m:
            cur_task, obj_t = code_v, "task"
        elif code_v.count(".") >= 3 or "заход" in type_m:
            obj_t = "measure"
        else:
            obj_t = "indicator"

        entry = {
            "code":        code_v,
            "name":        name_v,
            "indicator":   raw_value(sc(5)),
            "unit":        raw_value(sc(6)),
            "base_2021":   sc(7),
            "obj_type":    obj_t,
            "parent_goal": cur_goal,
            "parent_task": cur_task,
        }
        for yr, cols in YEAR_COLS.items():
            # «Страт_матриця» contains plan values and hierarchy, not pre-calculated progress.
            # Keep fields for backward compatibility, but do not read unrelated columns as progress.
            if MIO_SHEET == SHEET_NAME:
                entry[f"fact_{yr}"] = None
                entry[f"progress_{yr}"] = None
            else:
                entry[f"fact_{yr}"] = sc(cols["fact"])
                entry[f"progress_{yr}"] = sc(cols["progress"])

        rows_list.append(entry)

    df = pd.DataFrame(rows_list)

    # Aggregate average progress per goal/task code
    code_progress = {}
    for yr in [2026, 2027, 2028]:
        prog_col = f"progress_{yr}"
        indic = df[df["obj_type"] == "indicator"].copy()
        indic["_p"] = indic[prog_col].apply(
            lambda v: parse_number(str(v)) if v is not None and str(v) not in ["х", "в/а", "Виконується"] else None
        )
        valid = indic.dropna(subset=["_p"])

        # Goals: indicators with no parent_task
        for g_code, grp in valid[valid["parent_task"] == ""].groupby("parent_goal"):
            if g_code:
                avg = round(float(grp["_p"].mean()), 2)
                code_progress.setdefault(g_code, {})[yr] = avg

        # Tasks: indicators grouped by parent_task
        for t_code, grp in valid[valid["parent_task"] != ""].groupby("parent_task"):
            if t_code:
                avg = round(float(grp["_p"].mean()), 2)
                code_progress.setdefault(t_code, {})[yr] = avg

    return df, code_progress


@st.cache_data
def load_excel_measure_exec_scores():
    """
    STREAM 1b — Excel РВ (СЦ, Завд.)_РОЗРАХ.
    Pre-aggregated measure execution scores per goal/task
    (computed by Excel from М_заходи sheet data — quarterly statuses).
    Values are on a 0–1 scale → converted to % here.
    Returns: dict {code → {year → score_%}}
    NOTE: These are used ONLY if Supabase has no data for a given code.
    """
    try:
        raw = pd.read_excel(
            FILE_PATH, sheet_name=MEASURES_SHEET,
            header=None, engine="openpyxl"
        )
    except Exception:
        return {}

    data = raw.iloc[7:].copy().reset_index(drop=True)
    result = {}

    for i in range(len(data)):
        try:
            code_v = raw_value(data.iloc[i, 2])  # col C
            if not code_v:
                continue
            entry = {}
            for yr, col_1idx in MEASURE_EXEC_COL.items():
                val = data.iloc[i, col_1idx - 1]
                num = parse_number(str(val)) if val is not None else None
                if num is not None:
                    entry[yr] = round(clamp(num * 100, 0, 120), 2)
            if entry:
                result[code_v] = entry
        except (IndexError, KeyError):
            continue
    return result


@st.cache_data(ttl=60)
def load_monitoring_requests():
    """STREAM 2 — Supabase: approved monitoring submissions for measures."""
    resp = supabase.table("monitoring_requests").select("*").execute()
    if not resp.data:
        return pd.DataFrame()
    return pd.DataFrame(resp.data)


# ============================================================
# SCORING LOGIC
# ============================================================

def filter_monitoring(monitoring_df, selected_year, selected_quarter):
    if monitoring_df.empty:
        return pd.DataFrame()
    df = monitoring_df.copy()
    for col in ["year", "quarter", "approval_status", "strat_code",
                "status", "numeric_value", "progress_text", "risks", "submitted_at"]:
        if col not in df.columns:
            df[col] = ""
    df = df[df["year"].astype(str).str.strip() == str(selected_year)].copy()
    if selected_quarter != "Усі квартали":
        q = selected_quarter.replace(" квартал", "").strip()
        df = df[df["quarter"].astype(str).str.strip() == q].copy()
    df = df[df["approval_status"].astype(str).str.strip() == "Погоджено"].copy()
    if "submitted_at" in df.columns:
        df["_dt"] = pd.to_datetime(df["submitted_at"], errors="coerce")
        df = df.sort_values("_dt")
    return df


def calculate_measure_score(row, monitoring_records, selected_year):
    """
    STREAM 2: Score a single measure via Supabase approved submissions.
    Formula: fact/plan×100 | yes/no | status fallback | risk -10 penalty.
    """
    code       = raw_value(row.get("code"))
    target_raw = row.get(f"target_{selected_year}", "")
    target_num = parse_number(target_raw)
    unit       = row.get("unit", "")

    records = monitoring_records[
        monitoring_records["strat_code"].astype(str).str.strip() == code
    ].copy()

    if records.empty:
        return {
            "fact_value": None, "indicator_score": None, "status_score": None,
            "measure_score": 0.0, "level": "Не виконано",
            "risk_level": "Високий", "has_approved_data": False,
            "has_risks": False, "method_note": "Немає погоджених даних (Supabase)",
            "latest_status": "",
        }

    last      = records.iloc[-1]
    fact_raw  = raw_value(last.get("numeric_value", ""))
    fact_num  = parse_number(fact_raw)
    s_score   = status_score_val(last.get("status", ""))
    latest_status = raw_value(last.get("status", ""))
    has_risks = raw_value(last.get("risks", "")) != ""

    if is_yes_no_unit(unit):
        ind_score = 100.0 if (is_positive_yes(fact_raw) or
                              raw_value(last.get("status", "")).lower() == "виконано") else 0.0
        method = "Так/Ні: так=100%, ні=0%"
    elif fact_num is not None and target_num not in [None, 0]:
        ind_score = clamp((fact_num / target_num) * 100)
        method = f"{fact_num} / {target_num} × 100 = {round(ind_score, 1)}%"
    elif fact_num is not None:
        ind_score = None
        method = "Є факт, немає числового плану → статус"
    elif s_score is not None:
        ind_score = None
        method = f"Немає числового факту → статус '{raw_value(last.get('status',''))}' = {s_score}%"
    else:
        ind_score = 0.0
        method = "Немає ні факту, ні статусу → 0%"

    if ind_score is not None and s_score is not None:
        final = ind_score * 0.7 + s_score * 0.3
    elif ind_score is not None:
        final = ind_score
    elif s_score is not None:
        final = float(s_score)
    else:
        final = 0.0

    if has_risks:
        final = max(0.0, final - 10.0)

    final = round(clamp(final), 1)
    return {
        "fact_value": fact_raw,
        "indicator_score": round(ind_score, 1) if ind_score is not None else None,
        "status_score": s_score,
        "measure_score": final,
        "level": score_level(final),
        "risk_level": score_risk(score_level(final)),
        "has_approved_data": True,
        "has_risks": has_risks,
        "method_note": method,
        "latest_status": latest_status,
    }



def calculate_measure_score_debug(row, monitoring_records, selected_year):
    """
    Повна версія розрахунку з детальним журналом кожного кроку.
    Повертає той самий результат + список debug_steps для панелі адміністратора.
    """
    steps = []
    code = raw_value(row.get("code"))
    target = row.get(f"target_{selected_year}", "")
    target_num = parse_number(target)
    unit = raw_value(row.get("unit", ""))
    measure_name = raw_value(row.get("name", ""))[:80]

    steps.append(("📌 Захід", f"{code} — {measure_name}"))
    steps.append(("📅 Рік оцінки", str(selected_year)))
    steps.append(("📐 Одиниця виміру", unit if unit else "—"))
    steps.append(("🎯 Планове значення (target)", f"{raw_value(target)}" + (f" → числове: {target_num}" if target_num is not None else " → числове: не розпізнано")))

    # Пошук погоджених подань
    records = monitoring_records[
        monitoring_records["strat_code"].astype(str).str.strip() == code
    ].copy()

    total_mon = len(monitoring_records)
    found_mon = len(records)
    steps.append(("🗄 Погоджених подань у Supabase (всього у фільтрі)", str(total_mon)))
    steps.append(("🔍 Знайдено подань для цього заходу", str(found_mon)))

    if records.empty:
        steps.append(("❌ Результат пошуку", "Немає погоджених подань — оцінка = 0"))
        result = {
            "fact_value": None, "indicator_score": None, "status_score": None,
            "measure_score": 0.0, "level": "Не виконано",
            "risk_level": "Високий", "has_approved_data": False,
            "has_risks": False, "method_note": "Немає погоджених даних"
        }
        result["debug_steps"] = steps
        return result

    last = records.iloc[-1]
    fact_raw = raw_value(last.get("numeric_value", ""))
    fact_num = parse_number(fact_raw)
    status_raw = raw_value(last.get("status", ""))
    s_score = status_score_val(status_raw)
    risks_raw = raw_value(last.get("risks", ""))
    has_risks = risks_raw != ""
    dept_raw = raw_value(last.get("department", ""))
    submitted_raw = raw_value(last.get("submitted_at", ""))

    steps.append(("✅ Останнє погоджене подання", f"подано: {submitted_raw}, підрозділ: {dept_raw}"))
    steps.append(("🔢 Фактичне значення (numeric_value)", f"'{fact_raw}'" + (f" → числове: {fact_num}" if fact_num is not None else " → числове: не розпізнано")))
    steps.append(("📝 Статус виконання (status)", f"'{status_raw}'" + (f" → балів: {s_score}" if s_score is not None else " → не розпізнано")))
    steps.append(("⚠️ Ризики (risks)", f"'{risks_raw}'" if risks_raw else "—"))

    # Вибір методу розрахунку
    if is_yes_no_unit(unit):
        ind_score = 100.0 if (is_positive_yes(fact_raw) or status_raw.lower() == "виконано") else 0.0
        method = "Так/Ні: так = 100%, ні = 0%"
        steps.append(("⚙️ Метод", "Так/Ні (одиниця виміру містить 'так/ні')"))
        steps.append(("🧮 Розрахунок", f"факт = '{fact_raw}' → оцінка індикатора = {ind_score}%"))
    elif fact_num is not None and target_num not in [None, 0]:
        ind_score = clamp((fact_num / target_num) * 100)
        method = "Факт / Планове значення × 100"
        steps.append(("⚙️ Метод", "Числовий: Факт / Планове × 100"))
        steps.append(("🧮 Розрахунок", f"{fact_num} / {target_num} × 100 = {round((fact_num / target_num) * 100, 2)}% → після clamp(0–120): {ind_score}%"))
    elif fact_num is not None and target_num is None:
        ind_score = None
        method = "Є факт, немає числового плану; використано статус"
        steps.append(("⚙️ Метод", "Є числовий факт, але плану немає → перехід на статус"))
        steps.append(("🧮 Розрахунок", f"ind_score = None, s_score = {s_score}"))
    elif fact_num is not None and target_num == 0:
        ind_score = None
        method = "Планове значення = 0, ділення неможливе; використано статус"
        steps.append(("⚙️ Метод", "Планове значення = 0 → ділення неможливе → перехід на статус"))
    elif s_score is not None:
        ind_score = None
        method = "Немає числового факту; використано статус виконання"
        steps.append(("⚙️ Метод", f"Немає числового факту → використано статус: '{status_raw}' = {s_score}%"))
        steps.append(("🧮 Розрахунок", f"ind_score = None, s_score = {s_score}"))
    else:
        ind_score = 0.0
        method = "Немає числового факту і статусу → 0%"
        steps.append(("⚙️ Метод", "Немає ні числового факту, ні розпізнаного статусу → 0%"))
        steps.append(("🧮 Розрахунок", "ind_score = 0"))

    # Комбінування
    if ind_score is not None and s_score is not None:
        final = ind_score * 0.7 + s_score * 0.3
        steps.append(("🔀 Комбінування", f"ind_score ({ind_score}%) × 0.7 + s_score ({s_score}%) × 0.3 = {round(final, 2)}%"))
    elif ind_score is not None:
        final = ind_score
        steps.append(("🔀 Комбінування", f"Тільки ind_score = {ind_score}%"))
    elif s_score is not None:
        final = float(s_score)
        steps.append(("🔀 Комбінування", f"Тільки s_score = {s_score}%"))
    else:
        final = 0.0
        steps.append(("🔀 Комбінування", "Обидва = None → final = 0%"))

    before_risk = round(final, 2)

    if has_risks:
        final = max(0.0, final - 10.0)
        steps.append(("⚠️ Коригування на ризики", f"Є ризики → {before_risk}% - 10 = {round(final, 2)}% (мін. 0)"))
    else:
        steps.append(("✅ Коригування на ризики", "Ризиків немає → без змін"))

    final = round(clamp(final), 1)
    level = score_level(final)
    steps.append(("🏁 Фінальна оцінка заходу", f"**{final}%** → рівень: {level}"))

    return {
        "fact_value": fact_raw,
        "indicator_score": round(ind_score, 1) if ind_score is not None else None,
        "status_score": s_score,
        "measure_score": final,
        "level": level,
        "risk_level": score_risk(level),
        "has_approved_data": True,
        "has_risks": has_risks,
        "method_note": method,
        "debug_steps": steps,
    }


# ============================================================
# РЕЖИМ «М_заходи» — ВІДТВОРЕННЯ МЕТОДИКИ EXCEL (аркуш «М_заходи»)
# ============================================================
# Стани виконання (довідник $AR$1:$AR$5 в Excel):
#   AR1 «Виконано»               → 100
#   AR2 «Частково виконано»      → 75
#   AR3 «Не виконано»            → (бал не задано)
#   AR4 «Не настав час»          → "х"
#   AR5 «Втратило актуальність»  → (бал не задано)
#
# Стани кварталів (I квартал / I півріччя / 9 місяців) підтягуються з
# моніторингу як є (погоджені дані). Стан за РІК і Співвідношення Факт/План
# обчислюються формулами нижче (точна копія O8 та Q8 з аркуша «М_заходи»).
# ============================================================

ST_DONE     = "Виконано"               # $AR$1
ST_PARTIAL  = "Частково виконано"      # $AR$2
ST_NOTDONE  = "Не виконано"            # $AR$3
ST_NOTYET   = "Не настав час"          # $AR$4
ST_OBSOLETE = "Втратило актуальність"  # $AR$5

# Періоди аркуша «М_заходи» ↔ квартали моніторингу (кумулятивні звіти):
#   I квартал → I,  I півріччя → II,  9 місяців → III,  РІК → IV
MIO_PERIODS = [
    ("I квартал",   "I"),
    ("I півріччя",  "II"),
    ("9 місяців",   "III"),
    ("РІК",         "IV"),
]


def _quarter_key(value):
    """Нормалізує позначення кварталу до I / II / III / IV (лат.), стійко до кирилиці."""
    t = raw_value(value).upper()
    t = t.replace("КВАРТАЛ", "").replace(".", "").strip()
    # кирилиця → латиниця
    t = t.replace("\u0406", "I").replace("\u0407", "I").replace("\u04C0", "I")
    t = t.replace("\u0405", "S")
    if t in ("1", "I"):
        return "I"
    if t in ("2", "II", "ПІВРІЧЧЯ", "ПIВРIЧЧЯ"):
        return "II"
    if t in ("3", "III", "9 МІСЯЦІВ", "9 МIСЯЦIВ"):
        return "III"
    if t in ("4", "IV", "РІК", "РIК"):
        return "IV"
    return t


def normalize_period_status(value):
    """Зводить статус із моніторингу до 5 категорій аркуша «М_заходи»."""
    t = raw_value(value).lower().replace("’", "'")
    if not t or t in ["nan", "none", "-", "—", "н.д.", "нд"]:
        return ""
    if "втрат" in t and "актуальн" in t:
        return ST_OBSOLETE
    if "не настав" in t or "не настало" in t or "не настане" in t:
        return ST_NOTYET
    if "частков" in t:                       # «виконано частково» / «частково виконано»
        return ST_PARTIAL
    if "не викон" in t or "не розпоч" in t or "простроч" in t or t == "ні":
        return ST_NOTDONE
    if t.startswith("викон"):                # «виконано», «виконується» → Виконано
        return ST_DONE
    if t == "так":
        return ST_DONE
    # вже в потрібному словнику?
    canonical = {ST_DONE.lower(): ST_DONE, ST_PARTIAL.lower(): ST_PARTIAL,
                 ST_NOTDONE.lower(): ST_NOTDONE, ST_NOTYET.lower(): ST_NOTYET,
                 ST_OBSOLETE.lower(): ST_OBSOLETE}
    return canonical.get(t, "")


def _plan_is_x(plan):
    return raw_value(plan).strip().lower() == "х"


def mio_fact_plan_ratio(unit, s1, s2, s3, year_fact, plan):
    """
    Точна копія формули Q8 (Співвідношення Факту і Плану, %):

    =ЕСЛИОШИБКА(ЕСЛИ(ИЛИ(I8=$AR$5;K8=$AR$5;M8=$AR$5);"в/а";
       ЕСЛИ(ИЛИ(P8="х";N8="");"х";
          ЕСЛИ($G8="так/ні";ЕСЛИ(И(N8=P8;P8="так");100;0); N8/P8*100)));"х")

    Повертає число (%) або рядок "в/а" / "х".
    """
    try:
        if s1 == ST_OBSOLETE or s2 == ST_OBSOLETE or s3 == ST_OBSOLETE:
            return "в/а"
        if _plan_is_x(plan) or is_empty(year_fact):
            return "х"
        if is_yes_no_unit(unit):
            fact_t = raw_value(year_fact).lower()
            plan_t = raw_value(plan).lower()
            return 100 if (fact_t == plan_t and plan_t == "так") else 0
        fn = parse_number(year_fact)
        pn = parse_number(plan)
        if fn is None or pn in (None, 0):
            return "х"            # IFERROR → "х"
        return fn / pn * 100
    except Exception:
        return "х"


def mio_year_status(unit, s1, s2, s3, year_fact, plan, ratio):
    """
    Точна копія формули O8 (Стан виконання за РІК):

    =ЕСЛИ(ИЛИ(I8=$AR$5;K8=$AR$5;M8=$AR$5);$AR$5;
       ЕСЛИ(ИЛИ(P8="х";N8="");$AR$4;
          ЕСЛИ(G8="так/ні";ЕСЛИ(N8=P8;$AR$1;ЕСЛИ(N8="ні";$AR$3;$AR$4));
             ЕСЛИ(Q8>99,99;$AR$1;ЕСЛИ(И(Q8>74,99;Q8<100);$AR$2;
                ЕСЛИ(Q8=0;$AR$4;$AR$3))))))

    `ratio` — результат mio_fact_plan_ratio() (число або "х"/"в/а").
    """
    if s1 == ST_OBSOLETE or s2 == ST_OBSOLETE or s3 == ST_OBSOLETE:
        return ST_OBSOLETE
    if _plan_is_x(plan) or is_empty(year_fact):
        return ST_NOTYET
    if is_yes_no_unit(unit):
        fact_t = raw_value(year_fact).lower()
        plan_t = raw_value(plan).lower()
        if fact_t == plan_t:
            return ST_DONE
        if fact_t == "ні":
            return ST_NOTDONE
        return ST_NOTYET
    q = ratio
    if not isinstance(q, (int, float)):
        return ST_NOTYET
    if q > 99.99:
        return ST_DONE
    if 74.99 < q < 100:
        return ST_PARTIAL
    if q == 0:
        return ST_NOTYET
    return ST_NOTDONE


def _approved_monitoring_index(monitoring_df):
    """
    Будує індекс погоджених подань: {(strat_code, year, quarter_key) → останній запис}.
    Останній — за submitted_at (як у Excel: остання погоджена відмітка періоду).
    """
    index = {}
    if monitoring_df is None or monitoring_df.empty:
        return index
    df = monitoring_df.copy()
    for col in ["approval_status", "strat_code", "year", "quarter",
                "status", "numeric_value", "submitted_at", "risks"]:
        if col not in df.columns:
            df[col] = ""
    df = df[df["approval_status"].astype(str).str.strip() == "Погоджено"].copy()
    if df.empty:
        return index
    df["_dt"] = pd.to_datetime(df["submitted_at"], errors="coerce")
    df = df.sort_values("_dt")
    for _, rec in df.iterrows():
        key = (
            raw_value(rec.get("strat_code")),
            raw_value(rec.get("year")),
            _quarter_key(rec.get("quarter")),
        )
        index[key] = rec  # пізніший запис перезаписує ранній
    return index


def build_mio_measures_table(strat_df, monitoring_df, year):
    """
    Формує таблицю режиму «М_заходи» за один рік.

    Колонки (як в Excel «М_заходи»):
      Стратегічна ціль · Завдання · Захід · Індикатор · Од. виміру ·
      [I квартал: Факт, Стан] · [I півріччя: Факт, Стан] · [9 місяців: Факт, Стан] ·
      [РІК: Факт, Стан(формула)] · План · Співвідношення Факту і Плану, %(формула)

    Квартальні Факт/Стан підтягуються з погоджених подань моніторингу.
    Стан за РІК і Співвідношення обчислюються формулами Excel.
    """
    measures = strat_df[strat_df["object_type"] == "measure"].copy()
    mon_index = _approved_monitoring_index(monitoring_df)
    plan_col = f"target_{year}"

    rows = []
    for _, m in measures.iterrows():
        code = raw_value(m.get("code"))
        unit = raw_value(m.get("unit"))
        plan = m.get(plan_col, "")

        # Квартальні дані з моніторингу (Факт + нормалізований стан)
        period_fact = {}
        period_status = {}
        for label, qkey in MIO_PERIODS:
            rec = mon_index.get((code, str(year), qkey))
            if rec is not None:
                period_fact[label] = raw_value(rec.get("numeric_value"))
                period_status[label] = normalize_period_status(rec.get("status"))
            else:
                period_fact[label] = ""
                period_status[label] = ""

        s1 = period_status["I квартал"]
        s2 = period_status["I півріччя"]
        s3 = period_status["9 місяців"]
        year_fact = period_fact["РІК"]

        # Формули Excel: спочатку співвідношення (Q8), потім стан за рік (O8)
        ratio = mio_fact_plan_ratio(unit, s1, s2, s3, year_fact, plan)
        year_status = mio_year_status(unit, s1, s2, s3, year_fact, plan, ratio)

        rows.append({
            "Стратегічна ціль": (raw_value(m.get("parent_goal_code")) + " "
                                 + raw_value(m.get("parent_goal_name"))).strip(),
            "Завдання": (raw_value(m.get("parent_task_code")) + " "
                         + raw_value(m.get("parent_task_name"))).strip(),
            "Захід": code,
            "Назва заходу": raw_value(m.get("name")),
            "Індикатор": raw_value(m.get("indicator")),
            "Од. виміру": unit.replace("\n", " ").strip(),
            "Факт · I кв": period_fact["I квартал"],
            "Стан · I кв": s1,
            "Факт · I пів": period_fact["I півріччя"],
            "Стан · I пів": s2,
            "Факт · 9 міс": period_fact["9 місяців"],
            "Стан · 9 міс": s3,
            "Факт · РІК": year_fact,
            "Стан · РІК": year_status,
            "План (ціль. орієнтир)": raw_value(plan),
            "Факт/План, %": ratio,
        })

    return pd.DataFrame(rows)


# ============================================================
# РЕЖИМ «РВ (Заходи)» — РОЗРАХУНОК ВИКОНАННЯ ЗА ЗАХОДАМИ
# ============================================================
# Орієнтується на попередній режим «М_заходи»: переводить стани
# виконання у бали (0–1) за довідниками аркуша «РВ (Заходи)».
#
# Довідник $AD/$AE (стан → бал), рядки 1,2,4,5,6:
#   $AE$1 «Виконано»              → $AD$1 = 1.0
#   $AE$2 «Частково виконано»     → $AD$2 = 0.75
#   $AE$4 «Не виконано»           → $AD$4 = 0.0
#   $AE$5 «Не настав час»         → $AD$5 = "х"
#   $AE$6 «Втратило актуальність» → $AD$6 = "в/а"
#
# Довідник $AK/$AL (бал за рік → кінцевий результат):
#   $AL$1 = 1     → $AK$1 «Виконано»
#   $AL$2 = 0.75  → $AK$2 «Частково виконано»
#   $AK$4         «Не виконано»
#   $AL$5 = "х"   → $AK$5 «Не настав час»
#   $AL$6 = "в/а" → $AK$6 «Втратило актуальність»
# ============================================================

def rv_period_score(status):
    """
    Бал за квартальний період (формули G8/H8/I8 аркуша «РВ (Заходи)»):

    =ЕСЛИ(М_заходи!I8=$AE$1;$AD$1;
       ЕСЛИ(М_заходи!I8=$AE$4;$AD$4;
          ЕСЛИ(М_заходи!I8=$AE$2;$AD$2;
             ЕСЛИ(М_заходи!I8=$AE$6;$AD$6;$AD$5))))

    `status` — нормалізований стан виконання періоду з «М_заходи».
    Повертає число (1.0 / 0.75 / 0.0) або рядок "х" / "в/а".
    """
    if status == ST_DONE:        # $AE$1
        return 1.0               # $AD$1
    if status == ST_NOTDONE:     # $AE$4
        return 0.0               # $AD$4
    if status == ST_PARTIAL:     # $AE$2
        return 0.75              # $AD$2
    if status == ST_OBSOLETE:    # $AE$6
        return "в/а"             # $AD$6
    return "х"                   # $AD$5 (Не настав час / порожньо / інше)


def rv_year_score(ratio):
    """
    Бал за РІК (формула J8 аркуша «РВ (Заходи)»):

    =ЕСЛИ(М_заходи!Q8="х";"х";
       ЕСЛИ(М_заходи!Q8="в/а";"в/а";М_заходи!Q8/100))

    `ratio` — Співвідношення Факту і Плану, % (Q8 з «М_заходи»).
    Повертає число (частка 0–1+) або рядок "х" / "в/а".
    """
    if ratio == "х":
        return "х"
    if ratio == "в/а":
        return "в/а"
    if isinstance(ratio, (int, float)):
        return ratio / 100.0
    return "х"


def rv_final_result(year_score):
    """
    Кінцевий результат (формула K8 аркуша «РВ (Заходи)»):

    =ЕСЛИ(J8=$AL$5;$AK$5;
       ЕСЛИ(J8=$AL$6;$AK$6;
          ЕСЛИ(J8>=$AL$1;$AK$1;
             ЕСЛИ(И(J8>$AL$2;J8<$AL$1);$AK$2;$AK$4))))

    $AL$5="х" · $AL$6="в/а" · $AL$1=1 · $AL$2=0.75
    `year_score` — результат rv_year_score() (J8).
    Повертає назву стану («Виконано» / «Частково виконано» / …).
    """
    if year_score == "х":                       # =$AL$5
        return ST_NOTYET                        # $AK$5 «Не настав час»
    if year_score == "в/а":                     # =$AL$6
        return ST_OBSOLETE                      # $AK$6 «Втратило актуальність»
    if isinstance(year_score, (int, float)):
        if year_score >= 1.0:                   # >=$AL$1
            return ST_DONE                      # $AK$1 «Виконано»
        if 0.75 < year_score < 1.0:             # И(>$AL$2; <$AL$1)
            return ST_PARTIAL                   # $AK$2 «Частково виконано»
        return ST_NOTDONE                       # $AK$4 «Не виконано» (вкл. рівно 0.75)
    return ST_NOTDONE


def build_rv_measures_table(strat_df, monitoring_df, year):
    """
    Формує таблицю режиму «РВ (Заходи)» за один рік.

    Бере стани з режиму «М_заходи» (G8…I8 ← I8/K8/M8, J8 ← Q8) і
    переводить їх у бали виконання (0–1) та кінцевий результат.

    Колонки (як в Excel «РВ (Заходи)», блок року):
      Захід · Бал I кв (G) · Бал I пів (H) · Бал 9 міс (I) ·
      Бал РІК (J) · Кінцевий результат (K)
    """
    base = build_mio_measures_table(strat_df, monitoring_df, year)
    if base.empty:
        return base

    rows = []
    for _, r in base.iterrows():
        g_q1   = rv_period_score(r["Стан · I кв"])
        h_half = rv_period_score(r["Стан · I пів"])
        i_9m   = rv_period_score(r["Стан · 9 міс"])
        j_year = rv_year_score(r["Факт/План, %"])
        k_res  = rv_final_result(j_year)

        rows.append({
            "Стратегічна ціль": r["Стратегічна ціль"],
            "Завдання":         r["Завдання"],
            "Захід":            r["Захід"],
            "Назва заходу":     r["Назва заходу"],
            "Індикатор":        r["Індикатор"],
            "Од. виміру":       r["Од. виміру"],
            "Бал · I кв":       g_q1,
            "Бал · I пів":      h_half,
            "Бал · 9 міс":      i_9m,
            "Бал · РІК":        j_year,
            "Кінцевий результат": k_res,
        })

    return pd.DataFrame(rows)


def build_evaluation_table(strat_df, monitoring_df, selected_year, selected_quarter, selected_department):
    """
    Builds measure-level evaluation table using STREAM 2 (Supabase).
    Each active measure is scored via approved submissions.
    """
    measures = strat_df[strat_df["object_type"] == "measure"].copy()
    if selected_department and selected_department != "Усі":
        measures = measures[measures["department"].astype(str).str.strip() == selected_department].copy()
    plan_col = f"target_{selected_year}"
    measures = measures[measures[plan_col].apply(lambda v: not is_empty(v))].copy()

    filtered_mon = filter_monitoring(monitoring_df, selected_year, selected_quarter)

    rows = []
    for _, row in measures.iterrows():
        score = calculate_measure_score(row, filtered_mon, selected_year)
        rows.append({
            "goal_code":         row.get("parent_goal_code", ""),
            "goal_name":         row.get("parent_goal_name", ""),
            "task_code":         row.get("parent_task_code", ""),
            "task_name":         row.get("parent_task_name", ""),
            "measure_code":      row.get("code", ""),
            "measure_name":      row.get("name", ""),
            "indicator":         row.get("indicator", ""),
            "unit":              row.get("unit", ""),
            "plan_value":        row.get(plan_col, ""),
            "fact_value":        score["fact_value"],
            "department":        row.get("department", ""),
            "indicator_score":   score["indicator_score"],
            "status_score":      score["status_score"],
            "measure_score":     score["measure_score"],
            "level":             score["level"],
            "risk_level":        score["risk_level"],
            "has_approved_data": score["has_approved_data"],
            "has_risks":         score["has_risks"],
            "method_note":       score["method_note"],
            "latest_status":     score.get("latest_status", ""),
            "data_source":       "Supabase",
        })
    return pd.DataFrame(rows)


def aggregate_scores_dual(evaluation_df, code_progress_excel, selected_year):
    """
    DUAL-STREAM aggregation mirroring Excel Інт_Оцінка:

    Per GOAL (code like "1."):
      I  = Зведена оцінка виконання заходів   (Stream 2: Supabase mean of measures)
      J  = Зведена оцінка завдань              (Stream 2: mean of task scores from Supabase)
      K  = Зведена оцінка прогресу індикаторів (Stream 1: Excel МіО progress mean)
      Integral = I×0.20 + J×0.30 + K×0.50

    Per TASK (code like "1.1."):
      measures mean from Supabase
      indicator progress mean from Excel
    """
    if evaluation_df.empty:
        return pd.DataFrame(), pd.DataFrame(), {}

    # --- Task level ---
    task_agg = (
        evaluation_df
        .groupby(["goal_code", "goal_name", "task_code", "task_name"], dropna=False)
        .agg(
            task_measure_score=("measure_score", "mean"),
            measures_count=("measure_code", "count"),
            approved_count=("has_approved_data", "sum"),
            risk_measures=("has_risks", "sum"),
        )
        .reset_index()
    )
    task_agg["task_measure_score"] = task_agg["task_measure_score"].round(2)

    # Attach Excel indicator progress per task
    task_agg["task_indicator_progress"] = task_agg["task_code"].apply(
        lambda c: code_progress_excel.get(raw_value(c), {}).get(selected_year, None)
    )
    # Task final score: if Excel progress available use 70/30 blend, else Supabase only
    def task_final(row):
        ms = row["task_measure_score"]
        ip = row["task_indicator_progress"]
        if ip is not None:
            return round(ms * 0.50 + ip * 0.50, 1)
        return round(ms, 1)

    task_agg["task_score"] = task_agg.apply(task_final, axis=1)
    task_agg["level"] = task_agg["task_score"].apply(score_level)
    task_agg["risk_level"] = task_agg["level"].apply(score_risk)

    # --- Goal level ---
    goal_agg = (
        task_agg
        .groupby(["goal_code", "goal_name"], dropna=False)
        .agg(
            goal_measure_score=("task_measure_score", "mean"),
            goal_task_score=("task_score", "mean"),
            tasks_count=("task_code", "count"),
            measures_count=("measures_count", "sum"),
            approved_count=("approved_count", "sum"),
            risk_measures=("risk_measures", "sum"),
        )
        .reset_index()
    )

    # Attach Excel indicator progress per goal
    goal_agg["goal_indicator_progress"] = goal_agg["goal_code"].apply(
        lambda c: code_progress_excel.get(raw_value(c), {}).get(selected_year, None)
    )

    def goal_integral(row):
        i_measures = row["goal_measure_score"]   # Stream 2 zahodiv
        j_tasks    = row["goal_task_score"]       # Stream 2 zavdan
        k_progress = row["goal_indicator_progress"]  # Stream 1 Excel
        if k_progress is not None:
            return round(i_measures * 0.20 + j_tasks * 0.30 + k_progress * 0.50, 1)
        # No Excel progress data → use Supabase only, weight tasks more
        return round(i_measures * 0.35 + j_tasks * 0.65, 1)

    goal_agg["goal_score"] = goal_agg.apply(goal_integral, axis=1)
    goal_agg["level"] = goal_agg["goal_score"].apply(score_level)
    goal_agg["risk_level"] = goal_agg["level"].apply(score_risk)

    # Sources info for admin panel
    sources = {}
    for _, g in goal_agg.iterrows():
        c = raw_value(g["goal_code"])
        sources[c] = {
            "measure_score":     round(g["goal_measure_score"], 1),
            "task_score":        round(g["goal_task_score"], 1),
            "indicator_progress": g["goal_indicator_progress"],
            "has_excel_progress": g["goal_indicator_progress"] is not None,
            "formula": (
                f"{round(g['goal_measure_score'],1)}×0.20 + "
                f"{round(g['goal_task_score'],1)}×0.30 + "
                f"{round(g['goal_indicator_progress'],1) if g['goal_indicator_progress'] is not None else 'н.д.'}×0.50"
                f" = {g['goal_score']}%"
            )
        }

    return task_agg, goal_agg, sources


# Keep old aggregate_scores as alias for compatibility with debug panel
def aggregate_scores(evaluation_df):
    if evaluation_df.empty:
        return pd.DataFrame(), pd.DataFrame()
    task_scores = (
        evaluation_df
        .groupby(["goal_code", "goal_name", "task_code", "task_name"], dropna=False)
        .agg(
            task_score=("measure_score", "mean"),
            measures_count=("measure_code", "count"),
            approved_count=("has_approved_data", "sum"),
            risk_measures=("has_risks", "sum"),
        ).reset_index()
    )
    task_scores["task_score"] = task_scores["task_score"].round(1)
    task_scores["level"] = task_scores["task_score"].apply(score_level)
    task_scores["risk_level"] = task_scores["level"].apply(score_risk)
    goal_scores = (
        task_scores
        .groupby(["goal_code", "goal_name"], dropna=False)
        .agg(
            goal_score=("task_score", "mean"),
            tasks_count=("task_code", "count"),
            measures_count=("measures_count", "sum"),
            approved_count=("approved_count", "sum"),
            risk_measures=("risk_measures", "sum"),
        ).reset_index()
    )
    goal_scores["goal_score"] = goal_scores["goal_score"].round(1)
    goal_scores["level"] = goal_scores["goal_score"].apply(score_level)
    goal_scores["risk_level"] = goal_scores["level"].apply(score_risk)
    return task_scores, goal_scores


def build_integral_score(goal_scores, task_scores, evaluation_df):
    """Overall integral: weighted average across all goals."""
    if goal_scores.empty:
        return 0.0
    return round(float(goal_scores["goal_score"].mean()), 1)


# ============================================================
# HTML helpers
# ============================================================

def kpi_card(label, value, color="gray", pct_label=""):
    pct_html = f'<div class="kpi-pct">{pct_label}</div>' if pct_label else ""
    return (
        f'<div class="kpi-card kpi-{color}">'
        f'<div class="kpi-title">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{pct_html}'
        f'</div>'
    )


def progress_bar_html(pct, color="#005BBB"):
    w = min(100, max(0, pct))
    return (
        f'<div class="prog-bar-bg">'
        f'<div class="prog-bar-fill" style="width:{w}%;background:{color};"></div>'
        f'</div>'
    )


def insight(text, kind=""):
    cls = f"insight-item {kind}".strip()
    return f'<div class="{cls}">{text}</div>'


# ============================================================
# LOAD DATA
# ============================================================

strat_df      = load_strat_matrix()
monitoring_df = load_monitoring_requests()
mio_df, code_progress_excel = load_mio_excel()

measures_all = strat_df[strat_df["object_type"] == "measure"].copy()
departments_list = sorted(
    [
        d for d in measures_all["department"].dropna().astype(str).str.strip().unique()
        if d and d.lower() not in ["nan", "none", ""]
    ],
    key=department_sort_key
)

# Check if Excel МіО sheet loaded successfully
excel_mio_ok = not mio_df.empty

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
        <div class="header-title">Оцінка стратегічних результатів</div>
        <div class="header-subtitle">
            Сторінка призначена для розрахунку оцінки виконання стратегічного плану за ієрархічною моделлю: захід → завдання → стратегічна ціль → інтегральна оцінка. До розрахунку включаються виключно погоджені результати моніторингу. Дані за непогодженими заявками залишаються доступними для адміністрування, але не враховуються під час формування оцінки.
        </div>
    </div>
    <div class="header-pills">
        <div class="pill">📊 Оцінка стратегічних результатів</div>
        <div class="pill">🗄 Страт_матриця + Supabase</div>
        <div class="pill">✅ Погоджені результати</div>
        <div class="pill">🕐 {datetime.now().strftime("%d.%m.%Y %H:%M")}</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================
# РЕЖИМИ (вкладки Excel) — перемикають увесь вміст сторінки
# ============================================================
# Кожен режим відповідає аркушу методичної моделі Excel. Реалізовується
# поетапно. Перший реалізований режим — «М_заходи».
# ============================================================

MODE_MZAHODY   = "📋 М_заходи"
MODE_RV_MEAS   = "🧮 РВ (Заходи)"
MODE_RV_GOALS  = "🎯 РВ (СЦ, Завдання)"
MODE_MIO_GT    = "📊 МіО цілі/завдання"
MODE_INTEGRAL  = "🏛 Інт_Оцінка"
MODE_LEGACY    = "📈 Зведена аналітика"

MIO_MODES = [MODE_MZAHODY, MODE_RV_MEAS, MODE_RV_GOALS, MODE_MIO_GT, MODE_INTEGRAL, MODE_LEGACY]
IMPLEMENTED_MODES = {MODE_MZAHODY, MODE_RV_MEAS}

st.markdown('<div class="mio-modebar-wrap">', unsafe_allow_html=True)
st.markdown(
    '<div class="mio-modebar-meta">🗂️ Режим (аркуш методики) — перемикає весь вміст сторінки</div>',
    unsafe_allow_html=True
)
if hasattr(st, "segmented_control"):
    active_mode = st.segmented_control(
        "Режим", MIO_MODES, default=MODE_MZAHODY,
        label_visibility="collapsed", key="mio_mode"
    )
else:
    active_mode = st.radio(
        "Режим", MIO_MODES, index=0, horizontal=True,
        label_visibility="collapsed", key="mio_mode"
    )
if not active_mode:
    active_mode = MODE_MZAHODY
st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# ФІЛЬТР ЗА РОКАМИ (для режимів методики; можна обрати кілька)
# ============================================================

def _render_year_filter():
    yc1, yc2 = st.columns([2.2, 3], gap="medium")
    with yc1:
        yrs = st.multiselect(
            "Роки", [2026, 2027, 2028], default=[2026], key="mio_years"
        )
    if not yrs:
        yrs = [2026]
    return sorted(yrs)


# ============================================================
# РЕЖИМ «М_заходи» — РЕНДЕР
# ============================================================

_MIO_STATUS_CLASS = {
    ST_DONE:     "done",
    ST_PARTIAL:  "partial",
    ST_NOTDONE:  "notdone",
    ST_NOTYET:   "notyet",
    ST_OBSOLETE: "obsolete",
}
_MIO_STATUS_SHORT = {
    ST_DONE:     "Вик.",
    ST_PARTIAL:  "Частк.",
    ST_NOTDONE:  "Не вик.",
    ST_NOTYET:   "—",
    ST_OBSOLETE: "В/а",
}


def _esc(value):
    return html.escape(raw_value(value))


def _mio_fmt_ratio(val):
    if isinstance(val, (int, float)):
        return f"{val:.1f}%"
    return str(val)


def _fact_cell_html(val):
    """Числовий факт за період (компактно)."""
    t = raw_value(val)
    if not t or t.lower() in ("nan", "none"):
        return '<td class="m-fact m-empty">·</td>'
    return f'<td class="m-fact">{_esc(t)}</td>'


def _status_cell_html(status, short=True):
    """Кольоровий чип стану виконання."""
    if not status:
        return '<td class="m-st"><span class="m-empty">·</span></td>'
    cls = _MIO_STATUS_CLASS.get(status, "notyet")
    label = _MIO_STATUS_SHORT.get(status, status) if short else status
    return (f'<td class="m-st"><span class="tchip {cls}" title="{_esc(status)}">'
            f'{_esc(label)}</span></td>')


def _year_status_cell_html(status):
    """Стан за РІК — повний чип (ключова колонка)."""
    if not status:
        return '<td class="m-styear"><span class="m-empty">·</span></td>'
    cls = _MIO_STATUS_CLASS.get(status, "notyet")
    return (f'<td class="m-styear"><span class="tchip lg {cls}">'
            f'{_esc(status)}</span></td>')


def _ratio_cell_html(val):
    """Співвідношення Факт/План — прогрес-бар + значення, або чип «х»/«в/а»."""
    if isinstance(val, (int, float)):
        if val > 99.99:
            cls = "done"
        elif val > 74.99:
            cls = "partial"
        elif val == 0:
            cls = "notyet"
        else:
            cls = "notdone"
        width = max(2, min(100, val))
        label = f"{val:.1f}%".replace(".0%", "%")
        return (
            '<td class="m-ratio">'
            f'<div class="rbar {cls}"><div class="rfill" style="width:{width:.0f}%;"></div>'
            f'<span class="rlabel">{label}</span></div></td>'
        )
    if val == "в/а":
        return '<td class="m-ratio"><span class="tchip obsolete" title="Втратило актуальність">в/а</span></td>'
    return '<td class="m-ratio"><span class="tchip notyet" title="Дані відсутні / не настав час">х</span></td>'


def _measure_anchor_html(row):
    """Багаторядкова комірка-якір: код + назва + індикатор + теги (СЦ/завд./од.)."""
    code = _esc(row["Захід"])
    name = _esc(row["Назва заходу"])
    indicator = _esc(row["Індикатор"])
    unit = _esc(row["Од. виміру"])
    goal = _esc(row["Стратегічна ціль"])
    task = _esc(row["Завдання"])
    goal_short = goal.split(".")[0] if goal else ""
    task_code = task.split(" ")[0] if task else ""
    tags = ""
    if goal_short:
        tags += f'<span class="tag tag-goal" title="{goal}">СЦ {goal_short}</span>'
    if task_code:
        tags += f'<span class="tag tag-task" title="{task}">Завд. {_esc(task_code)}</span>'
    if unit:
        tags += f'<span class="tag tag-unit" title="Одиниця виміру">{unit}</span>'
    ind_html = f'<div class="m-ind" title="{indicator}">{indicator}</div>' if indicator else ""
    return (
        '<td class="m-anchor">'
        f'<div class="m-codeline"><span class="m-code">{code}</span>{tags}</div>'
        f'<div class="m-name" title="{name}">{name}</div>'
        f'{ind_html}'
        '</td>'
    )


def _build_mio_table_html(df):
    """Збирає повний HTML красивої таблиці режиму «М_заходи»."""
    head = """
    <div class="mio-tablewrap">
    <table class="mio-table">
      <thead>
        <tr class="grp">
          <th class="m-anchor sticky-h" rowspan="2">Захід</th>
          <th colspan="2" class="grp-q">I квартал</th>
          <th colspan="2" class="grp-q">I півріччя</th>
          <th colspan="2" class="grp-q">9 місяців</th>
          <th colspan="2" class="grp-year">РІК</th>
          <th rowspan="2" class="grp-plan">План</th>
          <th rowspan="2" class="grp-plan">Факт / План</th>
        </tr>
        <tr class="sub">
          <th class="sub-f">Факт</th><th class="sub-s">Стан</th>
          <th class="sub-f">Факт</th><th class="sub-s">Стан</th>
          <th class="sub-f">Факт</th><th class="sub-s">Стан</th>
          <th class="sub-f">Факт</th><th class="sub-s sub-year">Стан</th>
        </tr>
      </thead>
      <tbody>
    """
    rows = []
    for _, r in df.iterrows():
        plan = _esc(r["План (ціль. орієнтир)"]) or "·"
        cells = (
            _measure_anchor_html(r)
            + _fact_cell_html(r["Факт · I кв"]) + _status_cell_html(r["Стан · I кв"])
            + _fact_cell_html(r["Факт · I пів"]) + _status_cell_html(r["Стан · I пів"])
            + _fact_cell_html(r["Факт · 9 міс"]) + _status_cell_html(r["Стан · 9 міс"])
            + _fact_cell_html(r["Факт · РІК"]) + _year_status_cell_html(r["Стан · РІК"])
            + f'<td class="m-plan">{plan}</td>'
            + _ratio_cell_html(r["Факт/План, %"])
        )
        rows.append(f"<tr>{cells}</tr>")
    tail = "</tbody></table></div>"
    return head + "".join(rows) + tail


def _render_mzahody_year(strat_df, monitoring_df, year):
    df_full = build_mio_measures_table(strat_df, monitoring_df, year)
    if df_full.empty:
        st.info("Немає заходів для відображення.")
        return

    # ── KPI за РІК (по всьому портфелю року) ──
    sc = df_full["Стан · РІК"].value_counts().to_dict()
    n_total    = len(df_full)
    kpis = "".join([
        kpi_card("Усього заходів", n_total, "gray"),
        kpi_card("Виконано", sc.get(ST_DONE, 0), "green"),
        kpi_card("Частково виконано", sc.get(ST_PARTIAL, 0), "yellow"),
        kpi_card("Не виконано", sc.get(ST_NOTDONE, 0), "red"),
        kpi_card("Не настав час", sc.get(ST_NOTYET, 0), "blue"),
        kpi_card("Втратило актуальність", sc.get(ST_OBSOLETE, 0), "gray"),
    ])
    st.markdown(
        f'<div class="kpi-grid" style="grid-template-columns:repeat(6,1fr);">{kpis}</div>',
        unsafe_allow_html=True
    )

    # ── Фільтри (пошук / стан / стратегічна ціль) ──
    goals = ["Усі"] + sorted(
        [g for g in df_full["Стратегічна ціль"].unique() if raw_value(g)],
        key=code_sort_key
    )
    fcol = st.columns([3, 2.4, 2.6], gap="medium")
    with fcol[0]:
        query = st.text_input(
            "Пошук", placeholder="🔎 код, назва заходу або індикатор…",
            key=f"mio_q_{year}", label_visibility="collapsed"
        )
    with fcol[1]:
        st_filter = st.multiselect(
            "Стан за РІК",
            [ST_DONE, ST_PARTIAL, ST_NOTDONE, ST_NOTYET, ST_OBSOLETE],
            default=[], key=f"mio_st_{year}", placeholder="Стан за РІК",
            label_visibility="collapsed"
        )
    with fcol[2]:
        goal_sel = st.selectbox(
            "Стратегічна ціль", goals, key=f"mio_goal_{year}",
            label_visibility="collapsed"
        )

    df = df_full.copy()
    if query.strip():
        q = query.strip().lower()
        mask = (
            df["Захід"].astype(str).str.lower().str.contains(q, regex=False)
            | df["Назва заходу"].astype(str).str.lower().str.contains(q, regex=False)
            | df["Індикатор"].astype(str).str.lower().str.contains(q, regex=False)
        )
        df = df[mask]
    if st_filter:
        df = df[df["Стан · РІК"].isin(st_filter)]
    if goal_sel and goal_sel != "Усі":
        df = df[df["Стратегічна ціль"] == goal_sel]

    # ── Легенда + лічильник ──
    st.markdown(f"""
    <div class="mio-legend">
        <span class="mio-chip done"><span class="dot"></span>Виконано (&gt;99.99%)</span>
        <span class="mio-chip partial"><span class="dot"></span>Частково виконано (75–99.99%)</span>
        <span class="mio-chip notdone"><span class="dot"></span>Не виконано (&lt;75%)</span>
        <span class="mio-chip notyet"><span class="dot"></span>Не настав час</span>
        <span class="mio-chip obsolete"><span class="dot"></span>Втратило актуальність</span>
        <span style="margin-left:auto;font-size:12px;color:#64748b;font-weight:700;align-self:center;">
            Показано {len(df)} із {n_total}
        </span>
    </div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.info("За обраними фільтрами заходів не знайдено.")
    else:
        st.markdown(_build_mio_table_html(df), unsafe_allow_html=True)

    # ── Експорт ──
    csv = df_full.copy()
    csv["Факт/План, %"] = csv["Факт/План, %"].map(_mio_fmt_ratio)
    st.download_button(
        f"⬇️ Завантажити таблицю за {year} рік (CSV)",
        data=csv.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"М_заходи_{year}.csv",
        mime="text/csv",
        key=f"mio_dl_{year}",
    )


def render_mode_mzahody(strat_df, monitoring_df, years):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">М_заходи · моніторинг виконання заходів</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        "<div style='font-size:13px;color:#475569;margin-bottom:8px;line-height:1.5;'>"
        "Квартальні значення (Факт + Стан виконання за I квартал, I півріччя, 9 місяців) "
        "підтягуються з погоджених результатів моніторингу. "
        "Стан виконання за <b>РІК</b> та <b>Співвідношення Факту і Плану</b> "
        "обчислюються за формулами методичної моделі (аркуш «М_заходи»)."
        "</div>",
        unsafe_allow_html=True
    )
    if len(years) == 1:
        _render_mzahody_year(strat_df, monitoring_df, years[0])
    else:
        ytabs = st.tabs([f"{y} рік" for y in years])
        for tab, y in zip(ytabs, years):
            with tab:
                _render_mzahody_year(strat_df, monitoring_df, y)
    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# РЕЖИМ «РВ (Заходи)» — РЕНДЕР
# ============================================================

def _rv_fmt_pct(val):
    """Форматує частку 0–1 у відсоток (формат Excel «0%»):
    1 → «100%», 0.75 → «75%», 0.855 → «85,5%», 0 → «0%»."""
    pct = val * 100
    if float(pct).is_integer():
        return f"{int(pct)}%"
    return f"{pct:.1f}".replace(".", ",") + "%"


def _rv_ball_class(val):
    """Колірний клас чипа за балом (узгоджено з порогами кінцевого результату)."""
    if val >= 1.0:
        return "done"
    if val >= 0.75:
        return "partial"
    return "notdone"


def _rv_ball_cell(val):
    """Бал за квартальний період (G/H/I): число 0–1 або чип «х»/«в/а»."""
    if isinstance(val, (int, float)):
        return (f'<td class="m-st"><span class="tchip {_rv_ball_class(val)}">'
                f'{_rv_fmt_pct(val)}</span></td>')
    if val == "в/а":
        return '<td class="m-st"><span class="tchip obsolete" title="Втратило актуальність">в/а</span></td>'
    return '<td class="m-st"><span class="tchip notyet" title="Не настав час / дані відсутні">х</span></td>'


def _rv_year_cell(val):
    """Бал за РІК (J): прогрес-бар + значення 0–1, або чип «х»/«в/а»."""
    if isinstance(val, (int, float)):
        if val >= 1.0:
            cls = "done"
        elif val > 0.75:
            cls = "partial"
        else:
            cls = "notdone"
        width = max(2, min(100, val * 100))
        return (
            '<td class="m-ratio">'
            f'<div class="rbar {cls}"><div class="rfill" style="width:{width:.0f}%;"></div>'
            f'<span class="rlabel">{_rv_fmt_pct(val)}</span></div></td>'
        )
    if val == "в/а":
        return '<td class="m-ratio"><span class="tchip obsolete" title="Втратило актуальність">в/а</span></td>'
    return '<td class="m-ratio"><span class="tchip notyet" title="Не настав час / дані відсутні">х</span></td>'


def _build_rv_table_html(df):
    """Збирає HTML красивої таблиці режиму «РВ (Заходи)»."""
    head = """
    <div class="mio-tablewrap">
    <table class="mio-table">
      <thead>
        <tr class="grp">
          <th class="m-anchor sticky-h" rowspan="2">Захід</th>
          <th colspan="3" class="grp-q">Виконання, % (наростаючим)</th>
          <th rowspan="2" class="grp-year">За РІК, %</th>
          <th rowspan="2" class="grp-plan">Кінцевий результат</th>
        </tr>
        <tr class="sub">
          <th class="sub-s">I квартал</th>
          <th class="sub-s">I півріччя</th>
          <th class="sub-s">9 місяців</th>
        </tr>
      </thead>
      <tbody>
    """
    rows = []
    for _, r in df.iterrows():
        cells = (
            _measure_anchor_html(r)
            + _rv_ball_cell(r["Бал · I кв"])
            + _rv_ball_cell(r["Бал · I пів"])
            + _rv_ball_cell(r["Бал · 9 міс"])
            + _rv_year_cell(r["Бал · РІК"])
            + _year_status_cell_html(r["Кінцевий результат"])
        )
        rows.append(f"<tr>{cells}</tr>")
    tail = "</tbody></table></div>"
    return head + "".join(rows) + tail


def _render_rv_meas_year(strat_df, monitoring_df, year):
    df_full = build_rv_measures_table(strat_df, monitoring_df, year)
    if df_full.empty:
        st.info("Немає заходів для відображення.")
        return

    # ── KPI за кінцевим результатом ──
    rc = df_full["Кінцевий результат"].value_counts().to_dict()
    n_total = len(df_full)
    # Середній відсоток за РІК (лише числові значення)
    num_year = [v for v in df_full["Бал · РІК"] if isinstance(v, (int, float))]
    avg_year = sum(num_year) / len(num_year) if num_year else None

    kpis = "".join([
        kpi_card("Усього заходів", n_total, "gray"),
        kpi_card("Виконано", rc.get(ST_DONE, 0), "green"),
        kpi_card("Частково виконано", rc.get(ST_PARTIAL, 0), "yellow"),
        kpi_card("Не виконано", rc.get(ST_NOTDONE, 0), "red"),
        kpi_card("Не настав час", rc.get(ST_NOTYET, 0), "blue"),
        kpi_card(
            "Середнє за РІК, %",
            _rv_fmt_pct(avg_year) if avg_year is not None else "—",
            "gray"
        ),
    ])
    st.markdown(
        f'<div class="kpi-grid" style="grid-template-columns:repeat(6,1fr);">{kpis}</div>',
        unsafe_allow_html=True
    )

    # ── Фільтри (пошук / кінцевий результат / стратегічна ціль) ──
    goals = ["Усі"] + sorted(
        [g for g in df_full["Стратегічна ціль"].unique() if raw_value(g)],
        key=code_sort_key
    )
    fcol = st.columns([3, 2.4, 2.6], gap="medium")
    with fcol[0]:
        query = st.text_input(
            "Пошук", placeholder="🔎 код, назва заходу або індикатор…",
            key=f"rv_q_{year}", label_visibility="collapsed"
        )
    with fcol[1]:
        st_filter = st.multiselect(
            "Кінцевий результат",
            [ST_DONE, ST_PARTIAL, ST_NOTDONE, ST_NOTYET, ST_OBSOLETE],
            default=[], key=f"rv_st_{year}", placeholder="Кінцевий результат",
            label_visibility="collapsed"
        )
    with fcol[2]:
        goal_sel = st.selectbox(
            "Стратегічна ціль", goals, key=f"rv_goal_{year}",
            label_visibility="collapsed"
        )

    df = df_full.copy()
    if query.strip():
        q = query.strip().lower()
        mask = (
            df["Захід"].astype(str).str.lower().str.contains(q, regex=False)
            | df["Назва заходу"].astype(str).str.lower().str.contains(q, regex=False)
            | df["Індикатор"].astype(str).str.lower().str.contains(q, regex=False)
        )
        df = df[mask]
    if st_filter:
        df = df[df["Кінцевий результат"].isin(st_filter)]
    if goal_sel and goal_sel != "Усі":
        df = df[df["Стратегічна ціль"] == goal_sel]

    # ── Легенда + лічильник ──
    st.markdown(f"""
    <div class="mio-legend">
        <span class="mio-chip done"><span class="dot"></span>Виконано (&ge; 100%)</span>
        <span class="mio-chip partial"><span class="dot"></span>Частково виконано (75% &lt; ... &lt; 100%)</span>
        <span class="mio-chip notdone"><span class="dot"></span>Не виконано (&le; 75%)</span>
        <span class="mio-chip notyet"><span class="dot"></span>Не настав час (х)</span>
        <span class="mio-chip obsolete"><span class="dot"></span>Втратило актуальність (в/а)</span>
        <span style="margin-left:auto;font-size:12px;color:#64748b;font-weight:700;align-self:center;">
            Показано {len(df)} із {n_total}
        </span>
    </div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.info("За обраними фільтрами заходів не знайдено.")
    else:
        st.markdown(_build_rv_table_html(df), unsafe_allow_html=True)

    # ── Експорт ──
    csv = df_full.copy()
    for col in ["Бал · I кв", "Бал · I пів", "Бал · 9 міс", "Бал · РІК"]:
        csv[col] = csv[col].map(lambda v: _rv_fmt_pct(v) if isinstance(v, (int, float)) else v)
    csv = csv.rename(columns={
        "Бал · I кв":  "Виконання I кв, %",
        "Бал · I пів": "Виконання I пів, %",
        "Бал · 9 міс": "Виконання 9 міс, %",
        "Бал · РІК":   "Виконання за РІК, %",
    })
    st.download_button(
        f"⬇️ Завантажити таблицю за {year} рік (CSV)",
        data=csv.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"РВ_Заходи_{year}.csv",
        mime="text/csv",
        key=f"rv_dl_{year}",
    )


def render_mode_rv_meas(strat_df, monitoring_df, years):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">РВ (Заходи) · розрахунок виконання заходів</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        "<div style='font-size:13px;color:#475569;margin-bottom:8px;line-height:1.5;'>"
        "Відсоток виконання переводиться зі станів режиму <b>«М_заходи»</b> за довідником моделі: "
        "<b>Виконано → 100%</b>, <b>Частково виконано → 75%</b>, <b>Не виконано → 0%</b>, "
        "<b>Не настав час → «х»</b>, <b>Втратило актуальність → «в/а»</b>. "
        "Показник за <b>РІК</b> дорівнює співвідношенню Факту і Плану (%), а "
        "<b>Кінцевий результат</b> класифікує його (≥ 100% — виконано; 75–100% — частково; інакше — не виконано)."
        "</div>",
        unsafe_allow_html=True
    )
    if len(years) == 1:
        _render_rv_meas_year(strat_df, monitoring_df, years[0])
    else:
        ytabs = st.tabs([f"{y} рік" for y in years])
        for tab, y in zip(ytabs, years):
            with tab:
                _render_rv_meas_year(strat_df, monitoring_df, y)
    st.markdown('</div>', unsafe_allow_html=True)


def render_mode_placeholder(mode_label):
    sheet_map = {
        MODE_RV_MEAS:  ("РВ (Заходи)", "Розрахунок виконання на рівні заходів."),
        MODE_RV_GOALS: ("РВ (СЦ, Завдання)_РОЗРАХ", "Розрахунок виконання за стратегічними цілями та завданнями."),
        MODE_MIO_GT:   ("МіО_цілі_завдан", "Моніторинг та оцінка індикаторів цілей і завдань."),
        MODE_INTEGRAL: ("Інт_Оцінка", "Інтегральна оцінка (зважена 20/30/50)."),
    }
    name, desc = sheet_map.get(mode_label, (mode_label, ""))
    st.markdown(f"""
    <div class="mio-placeholder">
        <div class="big">🚧</div>
        <div class="ttl">Режим «{name}» — у розробці</div>
        <div>{desc}</div>
        <div style="margin-top:10px;font-size:13px;color:#64748b;">
            Реалізуємо поетапно, за тією ж логікою формул, що й «М_заходи».
        </div>
    </div>
    """, unsafe_allow_html=True)


# Диспетчер режимів: режими методики рендеряться тут і зупиняють сторінку.
# Режим «Зведена аналітика» — це наявний (легасі) контент нижче.
if active_mode in MIO_MODES and active_mode != MODE_LEGACY:
    mio_years = _render_year_filter()
    if active_mode == MODE_MZAHODY:
        render_mode_mzahody(strat_df, monitoring_df, mio_years)
    elif active_mode == MODE_RV_MEAS:
        render_mode_rv_meas(strat_df, monitoring_df, mio_years)
    else:
        render_mode_placeholder(active_mode)
    st.stop()


# ============================================================
# FILTERS
# ============================================================

st.markdown("""
<div class="filter-panel">
    <div class="filter-title">⚙️ Параметри оцінки</div>
</div>
""", unsafe_allow_html=True)

fc1, fc2, fc3, fc4 = st.columns([1.0, 1.0, 2.2, 1.5], gap="medium")
with fc1:
    st.markdown("<div style='font-weight:800;color:#0c1a3a;margin-bottom:4px;'>Звітний період</div>", unsafe_allow_html=True)
    selected_year = st.selectbox("Рік", [2026, 2027, 2028], index=0)
with fc2:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    selected_quarter = st.selectbox(
        "Квартал",
        ["Усі квартали", "I квартал", "II квартал", "III квартал", "IV квартал"]
    )
with fc3:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    selected_department = st.selectbox("Самостійний структурний підрозділ", ["Усі"] + departments_list)
with fc4:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    selected_view = st.selectbox(
        "Режим перегляду",
        ["Загальний огляд", "Стратегічні цілі", "Завдання", "Заходи", "За заступниками Міністра", "Методологія"]
    )


# ============================================================
# COMPUTE
# ============================================================

# STREAM 2: measure scores from Supabase
evaluation_df = build_evaluation_table(
    strat_df, monitoring_df, selected_year, selected_quarter, selected_department
)

# DUAL-STREAM: aggregate with Excel indicator progress (Stream 1) + Supabase measures (Stream 2)
task_scores, goal_scores, goal_sources = aggregate_scores_dual(
    evaluation_df, code_progress_excel, selected_year
)

# Integral score = average of goal-level integral scores (each already weighted 20/30/50)
integral_score = build_integral_score(goal_scores, task_scores, evaluation_df)

active_measures    = len(evaluation_df)
approved_measures  = int(evaluation_df["has_approved_data"].sum()) if not evaluation_df.empty else 0
without_data       = active_measures - approved_measures
risk_measures_cnt  = int(evaluation_df["has_risks"].sum()) if not evaluation_df.empty else 0
avg_measure_score  = round(float(evaluation_df["measure_score"].mean()), 1) if not evaluation_df.empty else 0.0
avg_task_score     = round(float(task_scores["task_score"].mean()), 1) if not task_scores.empty else 0.0
avg_goal_score     = round(float(goal_scores["goal_score"].mean()), 1) if not goal_scores.empty else 0.0
# Excel Stream 1 stats
goals_with_excel_progress = sum(1 for v in goal_sources.values() if v["has_excel_progress"])
total_goals        = len(goal_scores)
total_tasks        = len(task_scores)
active_measure_codes = set(evaluation_df["measure_code"].astype(str).str.strip()) if not evaluation_df.empty else set()
status_counts = monitoring_status_counts(monitoring_df, selected_year, selected_quarter, active_measure_codes)
pending_measures = len(status_counts["pending_codes"] - status_counts["approved_codes"])
unapproved_measures = max(0, active_measures - approved_measures - pending_measures)

# ============================================================
# TOP KPI ROW
# ============================================================

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">Зведені показники оцінки</div>', unsafe_allow_html=True)

left_col, right_col = st.columns([1, 2.5])

with left_col:
    gauge_color = "#16a34a" if integral_score >= 80 else "#d97706" if integral_score >= 50 else "#dc2626"
    level_text = score_level(integral_score)
    pill_style = level_pill_class(integral_score)
    st.markdown(f"""
    <div class="integral-block">
        <div class="integral-label">ІНТЕГРАЛЬНА ОЦІНКА</div>
        <div class="integral-value" style="color:{gauge_color};">{integral_score}%</div>
        <div class="integral-level" style="{pill_style}">{level_text}</div>
        <div style="font-size:11px;color:#64748b;margin-top:10px;">
            за {selected_year} рік · {selected_quarter}
        </div>
    </div>
    """, unsafe_allow_html=True)

with right_col:
    kpis_top = "".join([
        kpi_card("Оцінка стратегічних цілей", f"{avg_goal_score}%", "teal"),
        kpi_card("Оцінка завдань", f"{avg_task_score}%", "indigo"),
        kpi_card("Оцінка заходів", f"{avg_measure_score}%", "blue"),
    ])
    kpis_bot = "".join([
        kpi_card("Погоджено", approved_measures, "green"),
        kpi_card("Непогоджені", unapproved_measures, "red"),
        kpi_card("На розгляді", pending_measures, "yellow"),
    ])
    st.markdown(
        f'<div class="kpi-grid kpi-grid-4" style="grid-template-columns:repeat(3,1fr);margin-bottom:10px;">{kpis_top}</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        f'<div class="kpi-grid kpi-grid-4" style="grid-template-columns:repeat(3,1fr);">{kpis_bot}</div>',
        unsafe_allow_html=True
    )

st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# ANALYTICAL NOTE
# ============================================================

if not evaluation_df.empty:
    notes_html = ""
    best_goals = add_order_columns(goal_scores, "goal_code").sort_values("goal_score", ascending=False).head(3) if not goal_scores.empty else pd.DataFrame()
    structure_df = structure_counts_df(evaluation_df)
    structure_map = dict(zip(structure_df["Статус"], structure_df["Кількість"]))
    portfolio_goals = goal_portfolio_df(evaluation_df)
    attention_goals = portfolio_goals[portfolio_goals["problem_count"] > 0].head(4) if not portfolio_goals.empty else pd.DataFrame()

    approved_share = round(approved_measures / active_measures * 100, 1) if active_measures else 0
    pending_share = round(pending_measures / active_measures * 100, 1) if active_measures else 0
    unapproved_share = round(unapproved_measures / active_measures * 100, 1) if active_measures else 0
    completed_share = round(structure_map.get("Виконано", 0) / active_measures * 100, 1) if active_measures else 0
    delayed_share = round(structure_map.get("Протерміновані", 0) / active_measures * 100, 1) if active_measures else 0
    in_progress_share = round(structure_map.get("Виконується", 0) / active_measures * 100, 1) if active_measures else 0

    notes_html += insight(
        f"Інтегральна оцінка виконання за {selected_year} рік ({selected_quarter}) становить <strong>{integral_score}%</strong>. "
        f"Погодженими результатами охоплено <strong>{approved_share}%</strong> портфеля заходів; "
        f"непогоджені становлять <strong>{unapproved_share}%</strong>, на розгляді — <strong>{pending_share}%</strong>.",
        "info"
    )

    if completed_share >= 50:
        notes_html += insight(f"Найстабільніша зона портфеля — виконані заходи: <strong>{completed_share}%</strong> від загальної кількості.", "success")
    elif in_progress_share > 0:
        notes_html += insight(f"Основний масив роботи перебуває у процесі виконання: <strong>{in_progress_share}%</strong> заходів.", "success")

    if not best_goals.empty:
        best = "; ".join([f"{raw_value(r.goal_code)} — {r.goal_score}%" for _, r in best_goals.iterrows()])
        notes_html += insight(f"Найкращу динаміку демонструють стратегічні цілі: <strong>{best}</strong>.", "success")

    if not attention_goals.empty:
        attention = "; ".join([
            f"{raw_value(r.goal_code)} — {int(r.problem_count)} заходів ({r.problem_portfolio_share}% портфеля)"
            for _, r in attention_goals.iterrows()
        ])
        notes_html += insight(f"Найбільшої управлінської уваги потребують стратегічні цілі: <strong>{attention}</strong>.", "warn")

    if delayed_share > 0:
        notes_html += insight(
            f"Протерміновані заходи формують <strong>{delayed_share}%</strong> портфеля. "
            "Доцільно пріоритезувати уточнення строків, відповідальних виконавців і причин відхилення.",
            "danger" if delayed_share >= 25 else "warn"
        )

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Автоматична аналітична довідка</div>', unsafe_allow_html=True)
    st.markdown(notes_html, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<hr class="vis-separator">', unsafe_allow_html=True)

# ============================================================
# VIEWS
# ============================================================

if selected_view == "Методологія":
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Методологія розрахунку оцінки стратегічних результатів</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="methodology-box">
    <strong>Логіка розрахунку:</strong>
    <ol>
        <li>У розрахунок включаються активні заходи, які мають планове значення на обраний рік.</li>
        <li>Для кожного заходу береться останнє погоджене подання за обраний рік і квартал.</li>
        <li><strong>Числовий індикатор:</strong> оцінка = Факт / Планове значення × 100. Результат обмежується діапазоном 0–120%.</li>
        <li><strong>Індикатор «Так/Ні»:</strong> «Так» = 100%, «Ні» = 0%.</li>
        <li><strong>Відсутній числовий факт:</strong> використовується статус виконання: Виконано = 100%, Виконано частково = 60%, Виконується = 50%, Потребує уваги = 40%, Прострочено = 25%, Не розпочато = 0%.</li>
        <li><strong>Комбінація:</strong> якщо є і числовий факт, і статус — оцінка = числова оцінка × 0.7 + статусна × 0.3.</li>
        <li><strong>Наявність ризиків:</strong> оцінка заходу зменшується на 10 п.п.</li>
        <li><strong>Оцінка завдання</strong> = середнє значення оцінок його заходів.</li>
        <li><strong>Оцінка стратегічної цілі</strong> = агрегована оцінка завдань і заходів у межах відповідної цілі.</li>
        <li><strong>Інтегральна оцінка</strong> формується на рівні стратегічних цілей і агрегується до загального показника.</li>
    </ol>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

elif selected_view == "За заступниками Міністра":
    deputy_df = build_deputy_evaluation_df(evaluation_df)
    deputy_detail_df = build_deputy_measure_detail_df(evaluation_df)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Оцінка виконання за заступниками Міністра</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="section-subtitle">
        Групування здійснюється не за окремою колонкою Excel, а за затвердженою відповідністю:
        <strong>головний Індекс ССП → Заступник Міністра</strong>. Розрахунок оцінок заходів не змінюється;
        цей режим лише агрегує вже сформовану оцінку за управлінською відповідальністю.
    </div>
    """, unsafe_allow_html=True)

    if deputy_df.empty:
        st.info("Немає даних для формування оцінки за заступниками Міністра за обраними параметрами.")
    else:
        best_deputy_row = deputy_df.sort_values("Середня оцінка, %", ascending=False).iloc[0]
        attention_deputy_row = deputy_df.sort_values(
            ["Високий ризик", "Без погоджених даних", "Кількість заходів"],
            ascending=[False, False, False]
        ).iloc[0]

        total_deputies = len(deputy_df)
        avg_deputy_score = round(float(deputy_df["Середня оцінка, %"].mean()), 1)
        total_deputy_risks = int(deputy_df["Заходів з ризиками"].sum())
        total_deputy_without_data = int(deputy_df["Без погоджених даних"].sum())

        kpis = "".join([
            kpi_card("Заступників у вибірці", total_deputies, "blue"),
            kpi_card("Середня оцінка", f"{avg_deputy_score}%", "teal"),
            kpi_card("Заходів з ризиками", total_deputy_risks, "red"),
            kpi_card("Без погоджених даних", total_deputy_without_data, "yellow"),
        ])
        st.markdown(
            f'<div class="kpi-grid kpi-grid-4">{kpis}</div>',
            unsafe_allow_html=True
        )

        notes = ""
        notes += insight(
            f"Найвища середня оцінка у вибірці: <strong>{best_deputy_row['Заступник Міністра']}</strong> — "
            f"<strong>{best_deputy_row['Середня оцінка, %']}%</strong> за "
            f"<strong>{int(best_deputy_row['Кількість заходів'])}</strong> заходами.",
            "success"
        )
        notes += insight(
            f"Найбільшої уваги потребує зона відповідальності: <strong>{attention_deputy_row['Заступник Міністра']}</strong> — "
            f"<strong>{int(attention_deputy_row['Високий ризик'])}</strong> заходів з високим ризиком, "
            f"<strong>{int(attention_deputy_row['Без погоджених даних'])}</strong> без погоджених даних.",
            "warn" if int(attention_deputy_row["Високий ризик"]) > 0 else "info"
        )
        st.markdown(notes, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    if not deputy_df.empty:
        chart_df = deputy_df.copy()
        chart_df = chart_df.sort_values("Середня оцінка, %", ascending=True)

        c1, c2 = st.columns([1.35, 1], gap="medium")

        with c1:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Середня оцінка виконання за заступниками</div>', unsafe_allow_html=True)

            bar_colors = [level_color(v) for v in chart_df["Середня оцінка, %"]]
            fig = go.Figure(go.Bar(
                x=chart_df["Середня оцінка, %"],
                y=chart_df["Заступник Міністра"],
                orientation="h",
                marker=dict(color=bar_colors),
                text=chart_df["Середня оцінка, %"].astype(str) + "%",
                textposition="outside",
                customdata=chart_df[[
                    "Кількість заходів", "Погоджено", "Без погоджених даних",
                    "Заходів з ризиками", "Покриття погодженими, %"
                ]],
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "Середня оцінка: %{x}%<br>"
                    "Кількість заходів: %{customdata[0]}<br>"
                    "Погоджено: %{customdata[1]}<br>"
                    "Без погоджених даних: %{customdata[2]}<br>"
                    "Заходів з ризиками: %{customdata[3]}<br>"
                    "Покриття погодженими: %{customdata[4]}%<extra></extra>"
                )
            ))
            fig.update_layout(
                height=max(430, 34 * len(chart_df) + 120),
                margin=dict(l=20, r=60, t=10, b=30),
                xaxis=dict(range=[0, 120], title="Середня оцінка, %"),
                yaxis=dict(title=""),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(size=12, color="#334155")
            )
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with c2:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Структура портфеля за заступниками</div>', unsafe_allow_html=True)

            stack_df = deputy_df[[
                "Заступник Міністра", "Виконано / високий прогрес",
                "Частковий прогрес", "Високий ризик", "Без погоджених даних"
            ]].copy()
            stack_long = stack_df.melt(
                id_vars="Заступник Міністра",
                var_name="Категорія",
                value_name="Кількість"
            )
            fig_stack = px.bar(
                stack_long,
                x="Кількість",
                y="Заступник Міністра",
                color="Категорія",
                orientation="h",
                text="Кількість",
                color_discrete_map={
                    "Виконано / високий прогрес": "#16a34a",
                    "Частковий прогрес": "#d97706",
                    "Високий ризик": "#dc2626",
                    "Без погоджених даних": "#64748b",
                }
            )
            fig_stack.update_layout(
                height=max(430, 34 * len(deputy_df) + 120),
                margin=dict(l=20, r=20, t=10, b=30),
                xaxis_title="Кількість заходів",
                yaxis_title="",
                legend_title="",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(size=12, color="#334155")
            )
            fig_stack.update_traces(textposition="inside", insidetextanchor="middle")
            st.plotly_chart(fig_stack, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Зведена таблиця за заступниками Міністра</div>', unsafe_allow_html=True)
        table_df = deputy_df[[
            "Заступник Міністра", "Кількість заходів", "Погоджено",
            "Без погоджених даних", "Заходів з ризиками",
            "Покриття погодженими, %", "Частка ризикових, %",
            "Середня оцінка, %"
        ]].copy()
        st.dataframe(
            table_df,
            use_container_width=True,
            hide_index=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Деталізація заходів за заступниками</div>', unsafe_allow_html=True)
        st.dataframe(
            deputy_detail_df,
            use_container_width=True,
            hide_index=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

elif selected_view == "Загальний огляд":
    ch1, ch2 = st.columns([1.4, 1])

    with ch1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Оцінка виконання стратегічних цілей</div>', unsafe_allow_html=True)
        if not goal_scores.empty:
            chart_df = add_order_columns(goal_scores, "goal_code", "goal_name", "Ціль", 55)
            colors = [level_color(s) for s in chart_df["goal_score"]]
            fig = go.Figure(go.Bar(
                x=chart_df["goal_score"],
                y=chart_df["Ціль"],
                orientation="h",
                marker_color=colors,
                text=[f"{v}%" for v in chart_df["goal_score"]],
                textposition="outside",
            ))
            fig.add_vline(x=100, line_dash="dot", line_color="#64748b", line_width=1)
            fig.update_layout(
                height=max(380, len(chart_df) * 52),
                xaxis_range=[0, 125],
                xaxis_title="Оцінка, %",
                yaxis_title="",
                plot_bgcolor="white",
                paper_bgcolor="white",
                margin=dict(l=10, r=40, t=10, b=30),
                font=dict(size=12),
                xaxis=dict(gridcolor="#f1f5f9"),
            )
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Немає даних для графіка.")
        st.markdown('</div>', unsafe_allow_html=True)

    with ch2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Структура заходів за рівнем виконання</div>', unsafe_allow_html=True)
        if not evaluation_df.empty:
            level_counts = structure_counts_df(evaluation_df)
            fig = px.pie(
                level_counts,
                names="Статус",
                values="Кількість",
                color="Статус",
                color_discrete_map={
                    "Виконано": "#16a34a",
                    "Виконується": "#005BBB",
                    "Термін виконання не настав": "#94a3b8",
                    "Протерміновані": "#dc2626",
                },
                hole=0.48,
            )
            fig.update_layout(
                height=320,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="white",
                legend=dict(font=dict(size=11)),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Немає даних.")
        st.markdown('</div>', unsafe_allow_html=True)

    ch3, ch4 = st.columns(2)

    with ch3:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Радарна діаграма стратегічних цілей</div>', unsafe_allow_html=True)
        if not goal_scores.empty and len(goal_scores) >= 3:
            radar_df = add_order_columns(goal_scores, "goal_code")
            cats = (radar_df["goal_code"].astype(str) + " " + radar_df["goal_name"].astype(str).str.slice(0, 30)).tolist()
            vals = radar_df["goal_score"].tolist()
            vals_closed = vals + [vals[0]]
            cats_closed = cats + [cats[0]]
            fig = go.Figure(go.Scatterpolar(
                r=vals_closed,
                theta=cats_closed,
                fill="toself",
                fillcolor="rgba(0,91,187,0.12)",
                line=dict(color="#005BBB", width=2),
                name=str(selected_year),
            ))
            fig.add_trace(go.Scatterpolar(
                r=[100] * len(cats_closed),
                theta=cats_closed,
                mode="lines",
                line=dict(color="#e2e8f0", width=1.5, dash="dot"),
                name="100% (план)",
                showlegend=True,
            ))
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 120], tickfont=dict(size=9)),
                    angularaxis=dict(tickfont=dict(size=9)),
                ),
                height=340,
                paper_bgcolor="white",
                margin=dict(l=20, r=20, t=20, b=20),
                legend=dict(font=dict(size=10)),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Потрібно мінімум 3 цілі для радарної діаграми.")
        st.markdown('</div>', unsafe_allow_html=True)

    with ch4:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Оцінка виконання заходів у розрізі самостійних структурних підрозділів</div>', unsafe_allow_html=True)
        dept_df = department_execution_df(evaluation_df)
        if not dept_df.empty:
            fig = go.Figure(go.Bar(
                x=dept_df["Рівень виконання, %"],
                y=dept_df["Самостійний структурний підрозділ"],
                orientation="h",
                text=[f"{v}%" for v in dept_df["Рівень виконання, %"]],
                textposition="outside",
                marker_color=[level_color(v) for v in dept_df["Рівень виконання, %"]],
            ))
            fig.add_vline(x=100, line_dash="dot", line_color="#64748b", line_width=1)
            fig.update_layout(
                height=max(320, len(dept_df) * 38),
                xaxis_range=[0, 125],
                xaxis_title="Рівень виконання, %",
                yaxis_title="",
                paper_bgcolor="white",
                plot_bgcolor="white",
                xaxis=dict(gridcolor="#f1f5f9"),
                margin=dict(l=10, r=40, t=10, b=30),
            )
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Немає даних для розрізу за ССП.")
        st.markdown('</div>', unsafe_allow_html=True)

    if not goal_scores.empty:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="section-title">Виконання стратегічного плану — {selected_year} рік</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle">Оцінка по кожній стратегічній цілі. 100% — орієнтир плану.</div>', unsafe_allow_html=True)

        for _, g in add_order_columns(goal_scores, "goal_code").iterrows():
            score_v = g["goal_score"]
            bar_color = level_color(score_v)
            score_cls = goal_score_class(score_v)
            g_name = raw_value(g["goal_name"])[:80]
            tasks_c = int(g["tasks_count"])
            meas_c = int(g["measures_count"])
            appr_c = int(g["approved_count"])

            st.markdown(f"""
            <div class="goal-row">
                <div class="goal-row-header">
                    <span class="goal-code-badge">СЦ {raw_value(g['goal_code'])}</span>
                    <span class="goal-name-text">{g_name}</span>
                    <span class="goal-score-text {score_cls}">{score_v}%</span>
                </div>
                {progress_bar_html(score_v, bar_color)}
                <div style="display:flex;gap:20px;padding:6px 16px 10px;font-size:12px;color:#64748b;">
                    <span>📋 Завдань: <strong>{tasks_c}</strong></span>
                    <span>📌 Заходів: <strong>{meas_c}</strong></span>
                    <span>✅ Погоджено: <strong>{appr_c}</strong></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

elif selected_view == "Стратегічні цілі":
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Оцінка виконання стратегічних цілей</div>', unsafe_allow_html=True)
    if goal_scores.empty:
        st.info("Дані відсутні.")
    else:
        chart_df = add_order_columns(goal_scores, "goal_code", "goal_name", "Ціль", 70)
        colors = [level_color(s) for s in chart_df["goal_score"]]
        fig = go.Figure(go.Bar(
            x=chart_df["goal_score"],
            y=chart_df["Ціль"],
            orientation="h",
            marker_color=colors,
            text=[f"{v}%" for v in chart_df["goal_score"]],
            textposition="outside",
        ))
        fig.add_vline(x=100, line_dash="dot", line_color="#64748b", line_width=1)
        fig.update_layout(
            height=max(380, len(chart_df) * 52),
            xaxis_range=[0, 125],
            xaxis_title="Оцінка, %",
            plot_bgcolor="white",
            paper_bgcolor="white",
            margin=dict(l=10, r=50, t=10, b=30),
            xaxis=dict(gridcolor="#f1f5f9"),
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

        show = add_order_columns(goal_scores, "goal_code").rename(columns={
            "goal_code": "Код СЦ",
            "goal_name": "Стратегічна ціль",
            "goal_score": "Оцінка, %",
            "tasks_count": "Завдань",
            "measures_count": "Заходів",
            "approved_count": "Погоджено",
            "level": "Рівень виконання",
            "risk_level": "Рівень ризику",
        }).drop(columns=["_sort_key"], errors="ignore")
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Завантажити CSV",
            data=show.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"goal_scores_{selected_year}.csv",
            mime="text/csv"
        )
    st.markdown('</div>', unsafe_allow_html=True)

elif selected_view == "Завдання":
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Оцінка виконання завдань</div>', unsafe_allow_html=True)
    if task_scores.empty:
        st.info("Дані відсутні.")
    else:
        if not goal_scores.empty:
            goal_options = add_order_columns(goal_scores, "goal_code")["goal_code"].tolist()
            goal_sel = st.selectbox("Деталізація за стратегічною ціллю", ["— усі —"] + goal_options)
        else:
            goal_sel = "— усі —"

        task_chart = task_scores.copy()
        if goal_sel != "— усі —":
            task_chart = task_chart[task_chart["goal_code"] == goal_sel]
        task_chart = add_order_columns(task_chart, "task_code", "task_name", "Завдання", 70)

        if not task_chart.empty:
            colors = [level_color(s) for s in task_chart["task_score"]]
            fig = go.Figure(go.Bar(
                x=task_chart["task_score"],
                y=task_chart["Завдання"],
                orientation="h",
                marker_color=colors,
                text=[f"{v}%" for v in task_chart["task_score"]],
                textposition="outside",
            ))
            fig.add_vline(x=100, line_dash="dot", line_color="#64748b", line_width=1)
            fig.update_layout(
                height=max(320, len(task_chart) * 46),
                xaxis_range=[0, 125],
                xaxis_title="Оцінка, %",
                plot_bgcolor="white",
                paper_bgcolor="white",
                margin=dict(l=10, r=50, t=10, b=30),
                xaxis=dict(gridcolor="#f1f5f9"),
            )
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)

        show = add_order_columns(task_scores, "task_code").rename(columns={
            "goal_code": "Код СЦ",
            "goal_name": "Стратегічна ціль",
            "task_code": "Код завдання",
            "task_name": "Завдання",
            "task_score": "Оцінка, %",
            "measures_count": "Заходів",
            "approved_count": "Погоджено",
            "level": "Рівень виконання",
            "risk_level": "Рівень ризику",
        }).drop(columns=["_sort_key"], errors="ignore")
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Завантажити CSV",
            data=show.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"task_scores_{selected_year}.csv",
            mime="text/csv"
        )
    st.markdown('</div>', unsafe_allow_html=True)

elif selected_view == "Заходи":
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Оцінка виконання заходів</div>', unsafe_allow_html=True)
    if evaluation_df.empty:
        st.info("Дані відсутні.")
    else:
        search = st.text_input("🔍 Пошук у заходах", "", placeholder="Код, назва, індикатор, ССП...")
        show_df = evaluation_df.copy()
        if search.strip():
            sq = search.strip().lower()
            show_df = show_df[
                show_df["measure_code"].astype(str).str.lower().str.contains(sq, na=False)
                | show_df["measure_name"].astype(str).str.lower().str.contains(sq, na=False)
                | show_df["indicator"].astype(str).str.lower().str.contains(sq, na=False)
                | show_df["department"].astype(str).str.lower().str.contains(sq, na=False)
            ].copy()

        show_df = add_order_columns(show_df, "measure_code")
        if len(show_df) > 0:
            fig = px.scatter(
                show_df,
                x="measure_code",
                y="measure_score",
                color="level",
                hover_data=["measure_name", "indicator", "plan_value", "fact_value", "department"],
                color_discrete_map={
                    "Виконано": "#16a34a",
                    "Високий прогрес": "#4ade80",
                    "Частковий прогрес": "#d97706",
                    "Критичне відставання": "#f87171",
                    "Не виконано": "#dc2626",
                    "Немає даних": "#94a3b8",
                },
                labels={"measure_score": "Оцінка, %", "measure_code": "Код заходу"},
                title=""
            )
            fig.add_hline(y=100, line_dash="dot", line_color="#64748b", line_width=1)
            fig.add_hline(y=80, line_dash="dot", line_color="#d97706", line_width=1, opacity=0.5)
            fig.add_hline(y=50, line_dash="dot", line_color="#dc2626", line_width=1, opacity=0.5)
            fig.update_layout(
                height=360,
                plot_bgcolor="white",
                paper_bgcolor="white",
                margin=dict(l=10, r=10, t=10, b=40),
                xaxis=dict(gridcolor="#f1f5f9", tickangle=45, categoryorder="array", categoryarray=show_df["measure_code"].tolist()),
                yaxis=dict(gridcolor="#f1f5f9", range=[0, 125]),
            )
            st.plotly_chart(fig, use_container_width=True)

        show = show_df.rename(columns={
            "goal_code": "Код СЦ",
            "goal_name": "Стратегічна ціль",
            "task_code": "Код завдання",
            "task_name": "Завдання",
            "measure_code": "Код заходу",
            "measure_name": "Захід",
            "indicator": "Індикатор",
            "unit": "Одиниця виміру",
            "plan_value": "Планове значення",
            "fact_value": "Фактичне значення",
            "department": "Самостійний структурний підрозділ",
            "indicator_score": "Оцінка індикатора, %",
            "status_score": "Оцінка статусу, %",
            "measure_score": "Оцінка заходу, %",
            "level": "Рівень виконання",
            "risk_level": "Рівень ризику",
            "has_approved_data": "Є погоджені дані",
            "has_risks": "Є ризики",
            "latest_status": "Статус виконання",
            "method_note": "Метод розрахунку",
        }).drop(columns=["_sort_key"], errors="ignore")
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Завантажити CSV",
            data=show.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"measure_scores_{selected_year}.csv",
            mime="text/csv"
        )
    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# ADMIN PANEL
# ============================================================

st.markdown('<hr class="vis-separator">', unsafe_allow_html=True)

with st.expander("🔧 Панель адміністратора — деталізація всіх розрахунків", expanded=False):

    st.markdown("""
    <div class="section-card" style="margin-bottom:14px;">
        <div class="section-title">📋 Про цю панель</div>
        <div class="methodology-box">
        Ця панель відображає <strong>кожен крок розрахунку</strong> для кожного активного заходу:
        звідки береться числове значення, яка формула застосовується, чи знайдено погоджені подання
        у Supabase, як рахується фінальна оцінка і як вона агрегується до рівня завдань та цілей.
        Дані підтягуються автоматично — із <strong>Excel-файлу</strong> (планові значення, структура)
        та із <strong>Supabase</strong> (погоджені моніторингові подання).
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 1. Джерела даних ──
    st.markdown("### 1. Джерела даних — два потоки")

    active_in_year = len(evaluation_df)
    total_supabase = len(monitoring_df) if not monitoring_df.empty else 0
    filtered_mon_debug = filter_monitoring(monitoring_df, selected_year, selected_quarter)
    total_filtered = len(filtered_mon_debug)
    unique_codes_mon = len(filtered_mon_debug["strat_code"].unique()) if not filtered_mon_debug.empty else 0

    mio_rows = len(mio_df) if not mio_df.empty else 0
    mio_indicators = len(mio_df[mio_df["obj_type"] == "indicator"]) if not mio_df.empty else 0

    st.markdown(
        f"""
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:14px;">
          <div class="section-card" style="margin:0;">
            <div class="section-title">📗 Stream 1a — Excel Страт_матриця</div>
            <div class="methodology-box">
              <strong>Аркуш:</strong> Страт_матриця<br>
              <strong>Статус:</strong> {"✅ завантажено" if excel_mio_ok else "❌ помилка читання"}<br>
              <strong>Рядків зчитано:</strong> {mio_rows}<br>
              <strong>Індикаторів (рядків):</strong> {mio_indicators}<br>
              <strong>Цілей із Excel-прогресом {selected_year}:</strong> {goals_with_excel_progress} з {total_goals}<br>
              <strong>Джерело:</strong> структура, індикатори та планові значення зі Страт_матриці<br>
              <em>↻ Оновлюється при заміні файлу</em>
            </div>
          </div>
          <div class="section-card" style="margin:0;">
            <div class="section-title">📘 Stream 1b — Excel Страт_матриця</div>
            <div class="methodology-box">
              <strong>Аркуш:</strong> {SHEET_NAME}<br>
              <strong>Рядків зчитано:</strong> {len(strat_df)}<br>
              <strong>Цілей / Завдань / Заходів:</strong>
              {len(strat_df[strat_df["object_type"]=="goal"])} /
              {len(strat_df[strat_df["object_type"]=="task"])} /
              {len(strat_df[strat_df["object_type"]=="measure"])}<br>
              <strong>Активних заходів у {selected_year}:</strong> {active_in_year}<br>
              <em>Джерело: планові значення, ієрархія, підрозділи</em>
            </div>
          </div>
          <div class="section-card" style="margin:0;">
            <div class="section-title">🗄 Stream 2 — Supabase (подання ССП)</div>
            <div class="methodology-box">
              <strong>Таблиця:</strong> monitoring_requests<br>
              <strong>Всього записів:</strong> {total_supabase}<br>
              <strong>Фільтр:</strong> рік={selected_year}, {selected_quarter}, Погоджено<br>
              <strong>Після фільтрації:</strong> {total_filtered} записів<br>
              <strong>Унікальних заходів із даними:</strong> {unique_codes_mon}<br>
              <strong>Заходів без даних:</strong> {active_in_year - approved_measures}<br>
              <em>Джерело: факт і статус виконання заходів</em>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        """
        <div class="insight-item info">
        <strong>Формула інтегральної оцінки (відповідає Excel Інт_Оцінка):</strong><br>
        I (виконання заходів, Stream 2) × <strong>0.20</strong> + J (оцінка завдань, Stream 2) × <strong>0.30</strong>
        + K (прогрес індикаторів, Stream 1 Excel) × <strong>0.50</strong> = <strong>Інтегральна оцінка СЦ</strong><br>
        <em>Якщо Excel-прогрес відсутній (н.д.) — ціль рахується лише за Supabase: I×0.35 + J×0.65</em>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ── 2. Структура розрахунку ──
    st.markdown("### 2. Структура агрегації (дерево розрахунку)")

    if not evaluation_df.empty and not task_scores.empty and not goal_scores.empty:
        agg_rows = []
        w_measures = round(float(evaluation_df["measure_score"].mean()), 2)
        w_tasks_val = round(float(task_scores["task_score"].mean()), 2)
        w_goals_val = round(float(goal_scores["goal_score"].mean()), 2)
        excel_goals = goals_with_excel_progress

        agg_rows.append({
            "Рівень": "Захід (Stream 2: Supabase)",
            "Кількість": active_in_year,
            "Середня оцінка, %": w_measures,
            "Вага у формулі цілі": "20%",
            "Внесок в інтегральну": f"{round(w_measures * 0.20, 2)}%",
            "Формула": "Факт/План×100 або статус виконання"
        })
        agg_rows.append({
            "Рівень": "Завдання (Stream 2: Supabase агрег.)",
            "Кількість": len(task_scores),
            "Середня оцінка, %": w_tasks_val,
            "Вага у формулі цілі": "30%",
            "Внесок в інтегральну": f"{round(w_tasks_val * 0.30, 2)}%",
            "Формула": "MEAN(оцінки заходів завдання)"
        })
        agg_rows.append({
            "Рівень": f"Прогрес індикаторів (Stream 1: Excel Страт_матриця) — {excel_goals}/{total_goals} цілей мають дані",
            "Кількість": total_goals,
            "Середня оцінка, %": w_goals_val,
            "Вага у формулі цілі": "50%",
            "Внесок в інтегральну": f"{round(w_goals_val * 0.50, 2)}%",
            "Формула": "MEAN прогресу індикаторів з Excel Страт_матриця, якщо відповідні дані додано"
        })
        agg_rows.append({
            "Рівень": "▶ ІНТЕГРАЛЬНА ОЦІНКА",
            "Кількість": "—",
            "Середня оцінка, %": integral_score,
            "Вага у формулі цілі": "100%",
            "Внесок в інтегральну": f"{integral_score}%",
            "Формула": f"{w_measures}×0.20 + {w_tasks_val}×0.30 + {w_goals_val}×0.50 = {integral_score}%"
        })
        st.dataframe(pd.DataFrame(agg_rows), use_container_width=True, hide_index=True)

        # Per-goal breakdown with formula sources
        if goal_sources:
            st.markdown("**Деталізація формули по кожній стратегічній цілі:**")
            gs_rows = []
            for g_code, src in goal_sources.items():
                gs_rows.append({
                    "Код СЦ": g_code,
                    "Оцінка заходів I (Supabase), %": src["measure_score"],
                    "Оцінка завдань J (Supabase), %": src["task_score"],
                    "Прогрес K (Excel Страт_матриця), %": src["indicator_progress"] if src["indicator_progress"] is not None else "н.д.",
                    "Excel дані є": "✅" if src["has_excel_progress"] else "❌",
                    "Формула": src["formula"],
                })
            st.dataframe(pd.DataFrame(gs_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Немає даних для агрегації.")

    # ── 3. Оцінка по цілях і завданнях ──
    st.markdown("### 3. Деталізація по цілях і завданнях")

    if not goal_scores.empty and not task_scores.empty:
        for _, g in goal_scores.sort_values("goal_code").iterrows():
            g_code = raw_value(g["goal_code"])
            g_name = raw_value(g["goal_name"])[:70]
            g_score = g["goal_score"]
            g_color = level_color(g_score)

            with st.expander(
                f"СЦ {g_code} — {g_name} | Оцінка: {g_score}%",
                expanded=False
            ):
                st.markdown(f"""
                <div class="kpi-grid kpi-grid-4" style="grid-template-columns:repeat(4,1fr);margin-bottom:12px;">
                    {kpi_card("Оцінка цілі", f"{g_score}%", "blue" if g_score >= 80 else "yellow" if g_score >= 50 else "red")}
                    {kpi_card("Завдань", int(g["tasks_count"]), "gray")}
                    {kpi_card("Заходів", int(g["measures_count"]), "gray")}
                    {kpi_card("Із ризиками", int(g["risk_measures"]), "yellow" if g["risk_measures"] > 0 else "green")}
                </div>
                """, unsafe_allow_html=True)

                # Tasks for this goal
                g_tasks = task_scores[task_scores["goal_code"] == g_code].copy()
                task_rows = []
                for _, t in g_tasks.iterrows():
                    t_meas = evaluation_df[evaluation_df["task_code"] == t["task_code"]].copy()
                    task_rows.append({
                        "Код завдання": t["task_code"],
                        "Назва завдання": raw_value(t["task_name"])[:60],
                        "Оцінка завдання, %": t["task_score"],
                        "Заходів": int(t["measures_count"]),
                        "Погоджено": int(t["approved_count"]),
                        "Ризики": int(t["risk_measures"]),
                        "Рівень": t["level"],
                        "Формула агрегації": f"MEAN({[round(s, 1) for s in t_meas['measure_score'].tolist()]}) = {t['task_score']}%"
                    })
                if task_rows:
                    st.dataframe(pd.DataFrame(task_rows), use_container_width=True, hide_index=True)

                st.markdown(f"""
                <div class="insight-item info" style="margin-top:10px;">
                <strong>Формула оцінки цілі:</strong>
                MEAN({[t['task_score'] for _, t in g_tasks.iterrows()]}) = {g_score}%
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Немає даних про цілі/завдання.")

    # ── 4. Покроковий розрахунок кожного заходу ──
    st.markdown("### 4. Покроковий розрахунок по кожному заходу")

    st.markdown("""
    <div class="insight-item info">
    Нижче показаний <strong>повний журнал розрахунку</strong> для кожного активного заходу:
    яке значення взято з Excel, що знайдено у Supabase, яка формула застосована на кожному кроці.
    </div>
    """, unsafe_allow_html=True)

    # Search filter for admin
    admin_search = st.text_input(
        "🔍 Фільтр заходів для деталізації (код або ключове слово)",
        "",
        key="admin_search_measures",
        placeholder="Наприклад: 1.1.1 або кредит"
    )
    admin_goal_filter = st.selectbox(
        "Фільтр за стратегічною ціллю",
        ["— усі —"] + (goal_scores["goal_code"].tolist() if not goal_scores.empty else []),
        key="admin_goal_filter"
    )

    # Build debug table
    measures_for_debug = strat_df[strat_df["object_type"] == "measure"].copy()
    plan_col_debug = f"target_{selected_year}"
    measures_for_debug["_active"] = measures_for_debug[plan_col_debug].apply(lambda v: not is_empty(v))
    measures_for_debug = measures_for_debug[measures_for_debug["_active"]].copy()

    if admin_goal_filter != "— усі —":
        measures_for_debug = measures_for_debug[
            measures_for_debug["parent_goal_code"].astype(str).str.strip() == admin_goal_filter
        ].copy()

    if admin_search.strip():
        sq = admin_search.strip().lower()
        measures_for_debug = measures_for_debug[
            measures_for_debug["code"].astype(str).str.lower().str.contains(sq, na=False)
            | measures_for_debug["name"].astype(str).str.lower().str.contains(sq, na=False)
            | measures_for_debug["indicator"].astype(str).str.lower().str.contains(sq, na=False)
        ].copy()

    filtered_mon_for_debug = filter_monitoring(monitoring_df, selected_year, selected_quarter)

    st.caption(f"Показано {len(measures_for_debug)} заходів (з {active_in_year} активних)")

    if measures_for_debug.empty:
        st.info("Заходів не знайдено за вказаними фільтрами.")
    else:
        # Summary table first
        debug_summary_rows = []
        for _, mrow in measures_for_debug.iterrows():
            dbg = calculate_measure_score_debug(mrow, filtered_mon_for_debug, selected_year)
            plan_val = raw_value(mrow.get(plan_col_debug, ""))
            has_data_icon = "✅" if dbg["has_approved_data"] else "❌"
            risk_icon = "⚠️" if dbg["has_risks"] else "—"
            debug_summary_rows.append({
                "Код":             raw_value(mrow.get("code", "")),
                "Назва заходу":    raw_value(mrow.get("name", ""))[:55],
                "Підрозділ":       raw_value(mrow.get("department", "")),
                "Індикатор":       raw_value(mrow.get("indicator", ""))[:40],
                "Одиниця":         raw_value(mrow.get("unit", "")),
                "План":            plan_val,
                "Факт (Supabase)": raw_value(dbg["fact_value"]) if dbg["fact_value"] else "—",
                "Оцінка індик., %": dbg["indicator_score"] if dbg["indicator_score"] is not None else "—",
                "Оцінка статусу":  dbg["status_score"] if dbg["status_score"] is not None else "—",
                "Ризик -10":       risk_icon,
                "ОЦІНКА ЗАХОДУ, %": dbg["measure_score"],
                "Рівень":          dbg["level"],
                "Дані":            has_data_icon,
                "Метод":           dbg["method_note"],
            })

        st.dataframe(pd.DataFrame(debug_summary_rows), use_container_width=True, hide_index=True)

        st.download_button(
            "⬇️ Завантажити деталізований розрахунок CSV",
            data=pd.DataFrame(debug_summary_rows).to_csv(index=False).encode("utf-8-sig"),
            file_name=f"admin_debug_{selected_year}.csv",
            mime="text/csv",
            key="admin_download"
        )

        # Per-measure step-by-step (only if not too many)
        max_detail = 50
        show_detail = len(measures_for_debug) <= max_detail

        if not show_detail:
            st.info(
                f"Детальний покроковий журнал відображається для ≤ {max_detail} заходів. "
                f"Зараз відібрано {len(measures_for_debug)} — уточніть фільтр або введіть конкретний код."
            )
        else:
            st.markdown("#### Покроковий журнал по кожному заходу")
            for _, mrow in measures_for_debug.iterrows():
                code_d = raw_value(mrow.get("code", ""))
                name_d = raw_value(mrow.get("name", ""))[:70]
                dbg = calculate_measure_score_debug(mrow, filtered_mon_for_debug, selected_year)
                score_d = dbg["measure_score"]
                score_color = level_color(score_d)

                with st.expander(
                    f"{code_d} — {name_d} | Оцінка: {score_d}% ({dbg['level']})",
                    expanded=False
                ):
                    steps_html = ""
                    for step_label, step_value in dbg["debug_steps"]:
                        # Bold final score line
                        is_final = "Фінальна оцінка" in step_label
                        val_style = (
                            f"font-weight:900;font-size:16px;color:{score_color};"
                            if is_final else "color:#1e293b;"
                        )
                        row_bg = "#f0fdf4" if is_final else "transparent"
                        steps_html += f"""
                        <tr style="background:{row_bg};">
                            <td style="padding:7px 12px;border-bottom:1px solid #f1f5f9;
                                       font-size:12px;font-weight:700;color:#475569;
                                       white-space:nowrap;min-width:200px;">{step_label}</td>
                            <td style="padding:7px 12px;border-bottom:1px solid #f1f5f9;
                                       font-size:13px;{val_style}">{step_value}</td>
                        </tr>"""

                    st.markdown(f"""
                    <div style="border:1px solid #e2e8f0;border-radius:10px;
                                overflow:hidden;margin-top:4px;background:white;">
                        <table style="width:100%;border-collapse:collapse;">
                            <thead>
                                <tr style="background:#f8fafc;">
                                    <th style="padding:8px 12px;text-align:left;
                                               font-size:11px;color:#64748b;
                                               border-bottom:2px solid #e2e8f0;">Крок розрахунку</th>
                                    <th style="padding:8px 12px;text-align:left;
                                               font-size:11px;color:#64748b;
                                               border-bottom:2px solid #e2e8f0;">Значення / пояснення</th>
                                </tr>
                            </thead>
                            <tbody>{steps_html}</tbody>
                        </table>
                    </div>
                    """, unsafe_allow_html=True)

    # ── 5. Суппаbase data health ──
    st.markdown("### 5. Перевірка якості даних Supabase")

    if not monitoring_df.empty:
        health_rows = []
        mon_all = monitoring_df.copy()
        for col in ["year", "quarter", "approval_status", "strat_code", "numeric_value", "status", "risks"]:
            if col not in mon_all.columns:
                mon_all[col] = ""
            total = len(mon_all)
            empty_cnt = mon_all[col].apply(lambda v: is_empty(str(v))).sum()
            fill_pct = round((total - empty_cnt) / total * 100, 1) if total > 0 else 0
            health_rows.append({
                "Колонка": col,
                "Всього записів": total,
                "Заповнених": total - empty_cnt,
                "Порожніх": empty_cnt,
                "Заповненість, %": fill_pct
            })
        st.dataframe(pd.DataFrame(health_rows), use_container_width=True, hide_index=True)

        # Breakdown by approval status
        st.markdown("**Розподіл за статусом погодження:**")
        if "approval_status" in monitoring_df.columns:
            status_counts = monitoring_df["approval_status"].value_counts().reset_index()
            status_counts.columns = ["Статус погодження", "Кількість"]
            st.dataframe(status_counts, use_container_width=True, hide_index=True)
    else:
        st.warning("Supabase: таблиця monitoring_requests порожня або недоступна.")

    # ── 6. Перевірка коректності зіставлення кодів ──
    st.markdown("### 6. Зіставлення кодів заходів (Excel ↔ Supabase)")

    if not filtered_mon_for_debug.empty:
        excel_codes = set(measures_for_debug["code"].astype(str).str.strip().tolist())
        supabase_codes = set(filtered_mon_for_debug["strat_code"].astype(str).str.strip().tolist())

        matched = excel_codes & supabase_codes
        only_excel = excel_codes - supabase_codes
        only_supabase = supabase_codes - excel_codes

        match_rows = [
            {"Статус": "✅ Код є і в Excel, і в Supabase",
             "Кількість": len(matched),
             "Коди (перші 10)": ", ".join(sorted(matched)[:10]) + ("..." if len(matched) > 10 else "")},
            {"Статус": "📁 Тільки в Excel (немає погоджених даних)",
             "Кількість": len(only_excel),
             "Коди (перші 10)": ", ".join(sorted(only_excel)[:10]) + ("..." if len(only_excel) > 10 else "")},
            {"Статус": "🗄 Тільки в Supabase (немає в поточному Excel-фільтрі)",
             "Кількість": len(only_supabase),
             "Коди (перші 10)": ", ".join(sorted(only_supabase)[:10]) + ("..." if len(only_supabase) > 10 else "")},
        ]
        st.dataframe(pd.DataFrame(match_rows), use_container_width=True, hide_index=True)
    else:
        st.info(f"Немає погоджених подань у Supabase для {selected_year} р. / {selected_quarter}.")


# ============================================================
# FOOTER
# ============================================================

st.markdown("""
<div class="footer">
    <strong>Розроблено департаментом стратегічного планування та макроекономічного прогнозування</strong><br>
    Версія DEMO 1.4 | 2026 | Внутрішня система моніторингу стратегічного плану
</div>
""", unsafe_allow_html=True)
