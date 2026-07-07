import re
import html
import math
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.page_setup import page_setup, render_footer
from core.strategic_data import load_strat_matrix as core_load_strat_matrix, measure_name_by_code
from core import monitoring_data
from core import statuses as core_statuses
from core.text_utils import names_match, normalize_name
from core.ui import load_css
from core.excel_loader import read_excel_sheet
from core import operational
from core.closeouts import load_manual_closeouts
from core.exports import render_png_download
from core.access import filter_actions_for_user, filter_requests_for_user

current_user = page_setup("Оцінка МіО", page_name="Оцінка МіО")


FILE_PATH = "Під моніторинг СП.xlsx"
SHEET_NAME = "Страт_матриця"

# Окреме джерело бюджетних даних для режиму «МіО Фінансування».
# Файл вноситься окремо (поки може бути відсутнім — режим деградує коректно).
FIN_FILE_PATH = "БП під моніторинг СП.xlsx"

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


def level_color(score):
    if score is None:
        return "#94a3b8"
    if score >= 80:
        return "#16a34a"
    if score >= 50:
        return "#d97706"
    return "#dc2626"


def code_sort_key(value):
    """Natural numeric sort for codes like 1., 1.1., 1.1.1."""
    text = raw_value(value)
    nums = re.findall(r"\d+", text)
    if not nums:
        return (9999, text)
    return tuple(int(x) for x in nums) + tuple([0] * max(0, 5 - len(nums)))


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


def extract_main_ssp_index(value):
    """
    Extracts the main SSP index from the department field.
    Example: "20 Директорат..." → "20".
    """
    match = re.search(r"\d+", raw_value(value))
    return match.group(0) if match else ""


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
    """ЄДИНЕ джерело — core.strategic_data (правка К1)."""
    return core_load_strat_matrix()


def load_monitoring_requests():
    """ЄДИНЕ джерело — core.monitoring_data (правки К2, П2)."""
    return monitoring_data.load_monitoring_requests()


# ============================================================
# SCORING LOGIC
# ============================================================

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
    """ЄДИНА реалізація — core.periods.quarter_key (правка К8)."""
    from core.periods import quarter_key
    return quarter_key(value)

def normalize_period_status(value):
    """Зводить статус із моніторингу до 5 категорій аркуша «М_заходи»
    (ЄДИНА реалізація — core.statuses; правки П1/П5)."""
    return core_statuses.normalize_to_model_status(value)


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


_MIO_NAME_GUARD_EXCLUDED = {"count": 0}


def _approved_monitoring_index(monitoring_df, name_map=None):
    """
    Будує індекс погоджених подань: {(strat_code, year, quarter_key) → останній запис}.
    Останній — за submitted_at (як у Excel: остання погоджена відмітка періоду).

    П8 (захист від повторного використання коду): якщо у поданні збережено
    знімок назви заходу (object_name) і він НЕ відповідає поточній назві
    цього коду в Страт_матриці — подання зберігається в базі, але в оцінку
    НЕ враховується (оцінка — «відповідно до нинішніх», як узгоджено).
    Старі записи без object_name враховуються як раніше.
    """
    index = {}
    _MIO_NAME_GUARD_EXCLUDED["count"] = 0
    if monitoring_df is None or monitoring_df.empty:
        return index
    df = monitoring_df.copy()
    for col in ["approval_status", "strat_code", "year", "quarter",
                "status", "numeric_value", "submitted_at", "risks",
                "object_name", "object_kind", "indicator_name"]:
        if col not in df.columns:
            df[col] = ""
    df = df[df["approval_status"].astype(str).str.strip() == "Погоджено"].copy()
    if df.empty:
        return index
    df["_dt"] = pd.to_datetime(df["submitted_at"], errors="coerce")
    df = df.sort_values("_dt")
    for _, rec in df.iterrows():
        # Індекс ЗАХОДІВ: подання індикаторів сюди не потрапляють
        if raw_value(rec.get("object_kind")).lower() == "indicator":
            continue
        code = raw_value(rec.get("strat_code"))
        if name_map is not None:
            stored_name = raw_value(rec.get("object_name"))
            current_name = name_map.get(code)
            if stored_name and current_name is not None                     and not names_match(stored_name, current_name):
                _MIO_NAME_GUARD_EXCLUDED["count"] += 1
                continue
        key = (code, raw_value(rec.get("year")), _quarter_key(rec.get("quarter")))
        index[key] = rec  # пізніший запис перезаписує ранній
    return index


def _approved_indicator_index(monitoring_df):
    """
    П7: окремий індекс подань ІНДИКАТОРІВ цілей/завдань:
    {(code, year, quarter) → {нормалізована назва показника → останній запис}}.
    Порожня назва (старі подання) зберігається під ключем "" (фолбек).
    """
    index = {}
    if monitoring_df is None or monitoring_df.empty:
        return index
    df = monitoring_df.copy()
    for col in ["approval_status", "strat_code", "year", "quarter",
                "numeric_value", "submitted_at", "object_kind", "indicator_name"]:
        if col not in df.columns:
            df[col] = ""
    df = df[df["approval_status"].astype(str).str.strip() == "Погоджено"].copy()
    if df.empty:
        return index
    df["_dt"] = pd.to_datetime(df["submitted_at"], errors="coerce")
    df = df.sort_values("_dt")
    for _, rec in df.iterrows():
        kind = raw_value(rec.get("object_kind")).lower()
        if kind and kind != "indicator":
            continue
        key = (
            raw_value(rec.get("strat_code")),
            raw_value(rec.get("year")),
            _quarter_key(rec.get("quarter")),
        )
        ind_key = normalize_name(rec.get("indicator_name"))
        index.setdefault(key, {})[ind_key] = rec
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
    mon_index = _approved_monitoring_index(
        monitoring_df, name_map=measure_name_by_code(strat_df))
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


# ============================================================
# РЕЖИМ «РВ (СЦ, Завдання)» — РОЗРАХУНОК ВИКОНАННЯ ЗА ЦІЛЯМИ/ЗАВДАННЯМИ
# ============================================================
# Підв'язується під режим «РВ (Заходи)»: бере бали виконання ЗАХОДІВ
# (0–1 за періодами) і агрегує їх вгору за ієрархією кодів, точно
# відтворюючи формули аркуша «РВ (СЦ, Завд.)_РОЗРАХ».
#
# Формула СТРАТЕГІЧНОЇ ЦІЛІ (ДЛСТР($C8)=2, напр. «1.»):
#   =ЕСЛИ(ДЛСТР($C8)=2;
#       ЕСЛИОШИБКА(СРЗНАЧЕСЛИ($C9:$C52; $C8&"*"; E9:E52); "х"); …)
#   → ціль = СЕРЕДНЄ балів її ЗАВДАНЬ (рядки цього ж аркуша, код яких
#     починається з коду цілі).
#
# Формула ЗАВДАННЯ (ДЛСТР($C9)>=4, напр. «1.1.»):
#   =ЕСЛИ(ДЛСТР($C9)>=4;
#       ЕСЛИОШИБКА(СРЗНАЧЕСЛИ('РВ (Заходи)'!$D$8:$D$300; $C9&"*";
#                  'РВ (Заходи)'!G$8:G$300); "х"); …)
#   → завдання = СЕРЕДНЄ балів його ЗАХОДІВ (аркуш «РВ (Заходи)», код яких
#     починається з коду завдання).
#
# СРЗНАЧЕСЛИ (AVERAGEIF) усереднює ЛИШЕ числові бали, ІГНОРУЮЧИ текст
# «х»/«в/а». Якщо жодного числового бала немає — ЕСЛИОШИБКА повертає «х».
# Це принципово дворівнева агрегація: ціль рахується від уже усереднених
# завдань, а не напряму від заходів (перевірено на еталонній моделі — повний збіг).
#
# Відповідність колонок періодів (СЦ,Завд. ← Заходи):
#   E (I квартал) ← G   ·   F (I півріччя) ← H
#   G (9 місяців) ← I   ·   H (рік)        ← J
#
# Кінцевий результат за РІК (формула колонки I аркуша):
#   =ЕСЛИ(H8=$AM$1; $AL$1;
#      ЕСЛИ(И(H8>$AM$2; H8<$AM$1); $AL$2;
#         ЕСЛИ(H8=$AM$5; $AL$5; $AL$4)))
#   $AM$1=1 (100%) · $AM$2=0.75 (75%) · $AM$5="х"
#   100% → «Виконано»; 75% < … < 100% → «Частково виконано»;
#   «х» → «Не настав час»; інакше → «Не виконано».
# ============================================================

# Періодні колонки балів з режиму «РВ (Заходи)» (у порядку E,F,G,H ← G,H,I,J)
RV_PERIOD_COLS = ["Бал · I кв", "Бал · I пів", "Бал · 9 міс", "Бал · РІК"]


def rv_averageif(values):
    """СРЗНАЧЕСЛИ / AVERAGEIF над набором балів періоду.

    Усереднює лише числові бали (0–1), ігноруючи текстові «х»/«в/а».
    Якщо числових немає — повертає «х» (еквівалент ЕСЛИОШИБКА(…;"х")).
    """
    nums = [v for v in values if isinstance(v, (int, float))]
    if not nums:
        return "х"
    return sum(nums) / len(nums)


def rv_goal_final_result(year_score):
    """Кінцевий результат для СЦ/Завдання за балом РІК (колонка H).

    Відтворює: =ЕСЛИ(H=1;«Виконано»; ЕСЛИ(И(H>0.75;H<1);«Частково виконано»;
                  ЕСЛИ(H="х";«Не настав час»;«Не виконано»)))
    """
    if not isinstance(year_score, (int, float)):    # H = "х"  ($AM$5)
        return ST_NOTYET                             # «Не настав час»
    if year_score >= 1.0 - 1e-9:                     # H = $AM$1 (100%)
        return ST_DONE                               # «Виконано»
    if 0.75 < year_score < 1.0:                      # И(>$AM$2; <$AM$1)
        return ST_PARTIAL                            # «Частково виконано»
    return ST_NOTDONE                                # інакше → «Не виконано»


def build_rv_goals_table(strat_df, monitoring_df, year):
    """Формує ієрархічну таблицю режиму «РВ (СЦ, Завдання)» за один рік.

    Дворівнева агрегація балів виконання з режиму «РВ (Заходи)»:
      • Завдання      = rv_averageif(балів ЗАХОДІВ із цим префіксом коду)
      • Стратег. ціль = rv_averageif(балів ЗАВДАНЬ із цим префіксом коду)

    Повертає DataFrame у порядку «ціль → її завдання» з колонками:
      Тип · Код · Назва · Бал · I кв · Бал · I пів · Бал · 9 міс ·
      Бал · РІК · Кінцевий результат · К-ть заходів · К-ть завдань
    """
    measures_df = build_rv_measures_table(strat_df, monitoring_df, year)

    # 1) Бали ЗАХОДІВ: код заходу → [I кв, I пів, 9 міс, РІК]
    measure_scores = {}
    if not measures_df.empty:
        for _, m in measures_df.iterrows():
            mcode = raw_value(m["Захід"])
            if mcode:
                measure_scores[mcode] = [m[c] for c in RV_PERIOD_COLS]

    # 2) Довідники цілей і завдань з ієрархії Страт_матриці
    goals = strat_df[strat_df["object_type"] == "goal"][["code", "name"]]
    tasks = strat_df[strat_df["object_type"] == "task"][["code", "name"]]

    # 3) Бали ЗАВДАНЬ = AVERAGEIF за заходами (префікс коду завдання)
    task_scores, task_name, task_meas_cnt = {}, {}, {}
    for _, t in tasks.iterrows():
        tcode = raw_value(t["code"])
        if not tcode or tcode in task_scores:
            continue
        children = [sc for mc, sc in measure_scores.items() if mc.startswith(tcode)]
        task_scores[tcode] = [rv_averageif([c[i] for c in children]) for i in range(4)]
        task_name[tcode] = raw_value(t["name"])
        task_meas_cnt[tcode] = len(children)

    # 4) Бали ЦІЛЕЙ = AVERAGEIF за завданнями (префікс коду цілі)
    goal_scores, goal_name, goal_task_cnt, goal_meas_cnt = {}, {}, {}, {}
    for _, g in goals.iterrows():
        gcode = raw_value(g["code"])
        if not gcode or gcode in goal_scores:
            continue
        child_codes = [tc for tc in task_scores if tc.startswith(gcode)]
        children = [task_scores[tc] for tc in child_codes]
        goal_scores[gcode] = [rv_averageif([c[i] for c in children]) for i in range(4)]
        goal_name[gcode] = raw_value(g["name"])
        goal_task_cnt[gcode] = len(child_codes)
        goal_meas_cnt[gcode] = sum(task_meas_cnt.get(tc, 0) for tc in child_codes)

    # 5) Ієрархічне складання рядків: ціль, далі її завдання
    rows = []
    for gcode in sorted(goal_scores, key=code_sort_key):
        gp = goal_scores[gcode]
        rows.append({
            "Тип": "goal", "Код": gcode, "Назва": goal_name.get(gcode, ""),
            "Бал · I кв": gp[0], "Бал · I пів": gp[1],
            "Бал · 9 міс": gp[2], "Бал · РІК": gp[3],
            "Кінцевий результат": rv_goal_final_result(gp[3]),
            "К-ть заходів": goal_meas_cnt.get(gcode, 0),
            "К-ть завдань": goal_task_cnt.get(gcode, 0),
        })
        for tcode in sorted([tc for tc in task_scores if tc.startswith(gcode)], key=code_sort_key):
            tp = task_scores[tcode]
            rows.append({
                "Тип": "task", "Код": tcode, "Назва": task_name.get(tcode, ""),
                "Бал · I кв": tp[0], "Бал · I пів": tp[1],
                "Бал · 9 міс": tp[2], "Бал · РІК": tp[3],
                "Кінцевий результат": rv_goal_final_result(tp[3]),
                "К-ть заходів": task_meas_cnt.get(tcode, 0),
                "К-ть завдань": 0,
            })

    return pd.DataFrame(rows)


# ============================================================
# РЕЖИМ «МіО цілі/завдання» — РУШІЙ ОЦІНКИ ТА БІЛДЕР ТАБЛИЦІ
# ============================================================
# Відтворює методику аркуша «МіО_цілі_завдан» моделі (звірено до 8 знаків
# на реальних даних). Колонки факту/цілі беруться зі «Страт_матриці»:
#   Факт 2021 ← base_2021 · Факт 2024 ← fact_2024 · Факт 2025 ← fact_2025 ·
#   Цільовий орієнтир на кінець 2028 ← target_2028_end.
# Факт 2026/2027/2028 підтягується з погоджених подань (Stream 2), коли є.
#
# «Оцінка прогресу, %» — нормована геометрична траєкторія (тільки для ЦІЛЕЙ,
# LEN(код)=2). Степеневі знаменники = кількості років:
#   чисельник 1/(рік−база), знаменник 1/(2028−база).
#   База = факт попереднього року; якщо за 2025 «н.д.» → база 2024
#   (а через помилку → база 2021). Завдання: Факт/Ціль×100.
# «Зміна до попереднього року, %» = Факт / Факт_попередній × 100.

_MIO_GT_TARGET_YEAR = 2028
_MIO_NA = "н.д."


def _mio_gt_branch(fact, base, target, n1, n2):
    """Одна гілка траєкторної оцінки (повторює структуру формули Excel)."""
    rc = (fact / base) ** (1.0 / n1)       # POWER(Факт/база; 1/n1)
    rt = (target / base) ** (1.0 / n2)     # POWER(Ціль/база; 1/n2)
    if target - base < 0:                  # ціль на зниження
        return (100 + (100 - rc * 100)) / (100 + (100 - rt * 100)) * 100
    return rc / rt * 100                    # ціль на зростання


def mio_gt_progress_score(is_goal, unit, fact_year, year,
                          f2021, f2024, f2025, target_2028):
    """Значення колонки «Оцінка прогресу у досягненні, %» за один рік.

    Повертає число (%) або рядок «Виконується»/«х»/«» (немає даних).
    """
    # --- бінарний показник «так/ні» ---
    if is_yes_no_unit(unit):
        return "Виконується" if is_positive_yes(fact_year) else "х"

    J = parse_number(fact_year)

    # --- завдання (LEN(код)≠2): простий Факт/Ціль×100 ---
    if not is_goal:
        X = parse_number(target_2028)
        if J is None or X in (None, 0):
            return ""
        return J / X * 100

    # --- ціль (LEN(код)=2): траєкторна формула ---
    if J is None:                          # ЕСЛИ(J="";"")
        return ""
    X = parse_number(target_2028)
    I = parse_number(f2025)
    H = parse_number(f2024)
    G = parse_number(f2021)
    if X in (None, 0):
        return ""

    # I="н.д." (або відсутнє) → база 2024 з фолбеком на 2021 (ЕСЛИОШИБКА)
    if raw_value(f2025).lower() == _MIO_NA or I is None:
        try:
            if H in (None, 0):
                raise ValueError
            return _mio_gt_branch(J, H, X, year - 2024, _MIO_GT_TARGET_YEAR - 2024)
        except (ZeroDivisionError, ValueError, TypeError):
            if G in (None, 0):
                return ""
            return _mio_gt_branch(J, G, X, year - 2021, _MIO_GT_TARGET_YEAR - 2021)

    # звичайний шлях: база = факт 2025 (I). Степені: 1/(рік−2025) та 1/(2028−2025).
    return _mio_gt_branch(J, I, X, year - 2025, _MIO_GT_TARGET_YEAR - 2025)


def mio_gt_change(unit, fact_year, fact_prev):
    """«Зміна до попереднього року, %» = ЕСЛИ(од.=«так/ні»;«х»; Факт/Факт_поп×100)."""
    if is_yes_no_unit(unit):
        return "х"
    f = parse_number(fact_year)
    p = parse_number(fact_prev)
    if f is None or p in (None, 0):
        return ""
    return f / p * 100


def _mio_indicator_year_fact(mon_index, code, year,
                             indicator_name="", ind_index=None):
    """Факт показника за РІК із погоджених подань (Stream 2).

    П7: подання індикаторів тепер зберігають НАЗВУ показника
    (indicator_name), тому для цілей із кількома показниками факт
    підтягується саме до свого показника, а не «розмазується» на всі.
    Старі подання без назви — фолбек на спільний код (як раніше).
    """
    code_v = raw_value(code)
    ind_key = normalize_name(indicator_name)
    # Подані значення індикаторів «станом на дату» лягають у квартал дати
    # подання, тому беремо НАЙНОВІШИЙ доступний квартал року (IV → I).
    for _q in ("IV", "III", "II", "I"):
        if ind_index is not None:
            bucket = ind_index.get((code_v, str(year), _q))
            if bucket:
                rec = bucket.get(ind_key)
                if rec is None and ind_key:
                    rec = bucket.get("")     # старі подання без назви
                if rec is None and not ind_key:
                    if len(bucket) == 1:
                        rec = next(iter(bucket.values()))
                if rec is not None:
                    return raw_value(rec.get("numeric_value"))
        rec = mon_index.get((code_v, str(year), _q))
        if rec is not None:
            # захист: не віддавати факт заходу як факт показника
            kind = raw_value(rec.get("object_kind")).lower()
            if kind in ("", "indicator"):
                return raw_value(rec.get("numeric_value"))
    return ""


_MIO_GT_YEARS = [2026, 2027, 2028]


def build_mio_goals_tasks_table(strat_df, monitoring_df):
    """Формує таблицю режиму «МіО цілі/завдання».

    Один рядок = один показник цілі або завдання (як у «МіО_цілі_завдан»).
    Зберігає ієрархічний порядок «Страт_матриці»: ціль → її показники →
    її завдання → їх показники. Заходи (LEN коду ≥ 5) не входять.
    """
    if strat_df is None or strat_df.empty:
        return pd.DataFrame()

    mon_index = _approved_monitoring_index(monitoring_df)
    ind_index = _approved_indicator_index(monitoring_df)
    goal_types = {"goal", "goal_indicator"}
    task_types = {"task", "task_indicator"}

    rows = []
    for _, r in strat_df.iterrows():
        otype = raw_value(r.get("object_type"))
        if otype not in goal_types and otype not in task_types:
            continue
        indicator = raw_value(r.get("indicator"))
        if not indicator:                  # рядок без показника пропускаємо
            continue

        is_goal = otype in goal_types
        if is_goal:
            code = raw_value(r.get("parent_goal_code")) or raw_value(r.get("code"))
            owner = raw_value(r.get("parent_goal_name"))
        else:
            code = raw_value(r.get("parent_task_code")) or raw_value(r.get("code"))
            owner = raw_value(r.get("parent_task_name"))

        unit = raw_value(r.get("unit")).replace("\n", " ").strip()
        f2021 = raw_value(r.get("base_2021"))
        f2024 = raw_value(r.get("fact_2024"))
        f2025 = raw_value(r.get("fact_2025"))
        target = raw_value(r.get("target_2028_end"))

        entry = {
            "Рівень": "goal" if is_goal else "task",
            "Код": code,
            "Власник": owner,
            "Індикатор": indicator,
            "Од. виміру": unit,
            "Факт 2021": f2021,
            "Факт 2024": f2024,
            "Факт 2025": f2025,
            "Ціль 2028": target,
        }

        prev_fact = f2025                  # попередній для 2026 — факт 2025
        for y in _MIO_GT_YEARS:
            fact_y = _mio_indicator_year_fact(
                mon_index, code, y,
                indicator_name=indicator, ind_index=ind_index)
            entry[f"Факт {y}"] = fact_y
            entry[f"Зміна {y}"] = mio_gt_change(unit, fact_y, prev_fact)
            entry[f"Оцінка {y}"] = mio_gt_progress_score(
                is_goal, unit, fact_y, y, f2021, f2024, f2025, target
            )
            prev_fact = fact_y             # для наступного року попередній — цей факт

        rows.append(entry)

    return pd.DataFrame(rows)



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


def insight(text, kind=""):
    cls = f"insight-item {kind}".strip()
    return f'<div class="{cls}">{text}</div>'


# ============================================================
# LOAD DATA
# ============================================================

strat_df      = load_strat_matrix()
monitoring_df = load_monitoring_requests()

# Пункт 1 нового ТЗ: звужуємо тут лише monitoring_df (подання, без
# ризику для ієрархії цілей/завдань). strat_df навмисно НЕ звужуємо
# на цьому рівні — у ньому перемішані рядки стратегічних цілей,
# завдань і заходів, і "Головний виконавець" для рядків
# цілей/завдань в Excel успадкований через об'єднані комірки (не є
# надійним індикатором власника). Звуження заходів застосовується
# нижче, у кожному режимі сторінки окремо — через ті самі st_filter,
# що вже й керують відбором ССП у цьому режимі.
monitoring_df = filter_requests_for_user(
    monitoring_df, current_user, ssp_columns=["department"], page_key="Оцінка МіО"
)

# ============================================================
# ДЖЕРЕЛО ДАНИХ: ПІДТВЕРДЖЕНІ / ОПЕРАТИВНА ОЦІНКА (правка №6)
# ============================================================
# Усі режими цієї сторінки фільтрують подання за статусом «Погоджено».
# В оперативному режимі до підтверджених додаються подання, які координатор
# уже пропустив далі по схемі; ті з них, де значення ≥ річного орієнтира,
# авто-зараховуються як «Виконано» (⚡). Пріоритет підтверджених — по кожному
# заходу. Ручні закриття (офіційні) враховуються в обох режимах.

mio_data_mode = st.radio(
    "Джерело даних для розрахунків",
    operational.MODE_OPTIONS,
    horizontal=True,
    key="mio_data_source_mode",
    help=operational.MODE_HELP,
)

mio_auto_list = []
if mio_data_mode == operational.MODE_OPERATIONAL and not monitoring_df.empty:
    _mio_targets = operational.build_target_map(load_strat_matrix())
    monitoring_df, mio_auto_list = operational.apply_operational_mode(monitoring_df, _mio_targets)
    _op_n = int(monitoring_df["_operational"].sum()) if "_operational" in monitoring_df.columns else 0
    st.caption(
        f"⚡ Оперативний режим: додатково враховано {_op_n} подань(ня) після координатора, "
        f"з них авто-зараховано як виконані: {len(mio_auto_list)}."
    )
    if mio_auto_list:
        with st.expander(f"⚡ Авто-зараховані заходи: {len(mio_auto_list)} — деталі"):
            st.caption(operational.auto_completed_caption(mio_auto_list))
            st.dataframe(
                pd.DataFrame(mio_auto_list).rename(columns={
                    "code": "Код заходу", "year": "Рік", "quarter": "Квартал",
                    "value": "Подане значення", "target": "Річний орієнтир",
                    "approval_status": "Поточний етап погодження",
                }),
                use_container_width=True, hide_index=True,
            )
else:
    st.caption("✅ Розрахунок лише за заявками, що пройшли всі етапи схеми погодження.")

# 🔒 Ручні закриття — офіційні, в обох режимах: для періодів без запису
# «Погоджено» додається синтетичний запис «Виконано».
_mio_closeouts = load_manual_closeouts()
if _mio_closeouts:
    _mio_keys = set()
    if not monitoring_df.empty:
        _m_ok = monitoring_df[monitoring_df.get("approval_status", pd.Series(dtype=str)).astype(str) == "Погоджено"]
        for _, _r in _m_ok.iterrows():
            _mio_keys.add((
                str(_r.get("strat_code", "")).strip(),
                str(_r.get("year", "")).strip(),
                _quarter_key(_r.get("quarter", "")),
            ))
    _mio_synth = [
        {
            "strat_code": _c, "year": _y, "quarter": _q,
            "approval_status": "Погоджено", "status": "Виконано",
            "numeric_value": "", "progress_text": "Закрито вручну адміністратором",
            "risks": "", "submitted_at": "", "object_kind": "measure",
        }
        for (_c, _y, _q) in _mio_closeouts
        if (_c, _y, _q) not in _mio_keys
    ]
    if _mio_synth:
        monitoring_df = pd.concat([monitoring_df, pd.DataFrame(_mio_synth)], ignore_index=True)
        st.caption(f"🔒 Враховано ручних закриттів заходів (офіційні): {len(_mio_synth)}.")

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
MODE_FINANCING = "💰 МіО Фінансування"
MODE_INFOGR_SC = "📈 Інфограф СЦ"
MODE_INFOGR_SCZZ = "📉 Інфограф_СЦ.З.з"

MIO_MODES = [MODE_MZAHODY, MODE_RV_MEAS, MODE_RV_GOALS, MODE_MIO_GT,
             MODE_INTEGRAL, MODE_FINANCING, MODE_INFOGR_SC, MODE_INFOGR_SCZZ]
IMPLEMENTED_MODES = {MODE_MZAHODY, MODE_RV_MEAS, MODE_RV_GOALS, MODE_MIO_GT,
                     MODE_INTEGRAL, MODE_FINANCING}

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
        return f"{val:.2f}%"
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
        label = f"{val:.2f}%".replace(".0%", "%")
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
    if _MIO_NAME_GUARD_EXCLUDED.get("count"):
        st.caption(
            f"ℹ️ {_MIO_NAME_GUARD_EXCLUDED['count']} подань(ня) не враховано в оцінці: "
            "збережена назва заходу не відповідає поточній назві цього коду "
            "в Страт_матриці (захист після актуалізації плану). "
            "Записи збережені в базі та журналах."
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


# ============================================================
# РЕЖИМ «РВ (СЦ, Завдання)» — РЕНДЕР
# ============================================================

# Локальні стилі ієрархічної таблиці (ціль/завдання)
_RV_GOALS_CSS = """
<style>
.mio-table tr.rv-goal-row > td { background:#eef4fb; border-top:2px solid #cbdcef; }
.mio-table tr.rv-goal-row:hover > td { background:#e6eef9; }
.mio-table td.rv-anchor { padding:9px 12px; }
.mio-table td.rv-anchor .m-code { font-weight:800; }
.mio-table tr.rv-goal-row td.rv-anchor .m-code { color:#0a3d7a; font-size:14px; }
.mio-table tr.rv-goal-row td.rv-anchor .rv-name { font-weight:800; color:#0f2747; text-transform:uppercase; letter-spacing:.2px; font-size:12.5px; }
.mio-table td.rv-anchor.rv-task { padding-left:30px; position:relative; }
.mio-table td.rv-anchor.rv-task::before { content:""; position:absolute; left:14px; top:0; bottom:0; width:3px; background:#dbe6f3; border-radius:2px; }
.mio-table td.rv-anchor.rv-task .rv-name { color:#334155; font-size:12.5px; font-weight:600; }
.rv-badge { display:inline-block; font-size:10px; font-weight:800; padding:1px 7px; border-radius:999px; margin-left:8px; vertical-align:middle; }
.rv-badge.goal { background:#0a3d7a; color:#fff; }
.rv-badge.task { background:#e2ecf8; color:#1d4e89; border:1px solid #cdddf0; }
.rv-cnt { font-size:10.5px; color:#64748b; font-weight:700; margin-left:6px; }
</style>
"""


def _rv_goal_anchor_html(row):
    """Комірка-якір ієрархії: код + назва + бейдж (СЦ/Завд.)."""
    is_goal = row["Тип"] == "goal"
    code = _esc(row["Код"])
    name = _esc(row["Назва"])
    if is_goal:
        cnt = (f'<span class="rv-cnt">{int(row["К-ть завдань"])} завд. · '
               f'{int(row["К-ть заходів"])} зах.</span>')
        return (
            '<td class="m-anchor rv-anchor">'
            f'<div class="m-codeline"><span class="m-code">{code}</span>'
            f'<span class="rv-badge goal">СЦ</span>{cnt}</div>'
            f'<div class="rv-name" title="{name}">{name}</div></td>'
        )
    cnt = f'<span class="rv-cnt">{int(row["К-ть заходів"])} зах.</span>'
    return (
        '<td class="m-anchor rv-anchor rv-task">'
        f'<div class="m-codeline"><span class="m-code">{code}</span>'
        f'<span class="rv-badge task">Завд.</span>{cnt}</div>'
        f'<div class="rv-name" title="{name}">{name}</div></td>'
    )


def _build_rv_goals_table_html(df):
    """Збирає HTML ієрархічної таблиці режиму «РВ (СЦ, Завдання)»."""
    head = """
    <div class="mio-tablewrap">
    <table class="mio-table">
      <thead>
        <tr class="grp">
          <th class="m-anchor sticky-h" rowspan="2">Стратегічна ціль / Завдання</th>
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
        tr_cls = "rv-goal-row" if r["Тип"] == "goal" else "rv-task-row"
        cells = (
            _rv_goal_anchor_html(r)
            + _rv_ball_cell(r["Бал · I кв"])
            + _rv_ball_cell(r["Бал · I пів"])
            + _rv_ball_cell(r["Бал · 9 міс"])
            + _rv_year_cell(r["Бал · РІК"])
            + _year_status_cell_html(r["Кінцевий результат"])
        )
        rows.append(f'<tr class="{tr_cls}">{cells}</tr>')
    tail = "</tbody></table></div>"
    return head + "".join(rows) + tail


def _render_rv_goals_year(strat_df, monitoring_df, year):
    st.markdown(_RV_GOALS_CSS, unsafe_allow_html=True)
    df_full = build_rv_goals_table(strat_df, monitoring_df, year)
    if df_full.empty:
        st.info("Немає стратегічних цілей для відображення.")
        return

    goals_df = df_full[df_full["Тип"] == "goal"]
    tasks_df = df_full[df_full["Тип"] == "task"]

    # ── KPI за кінцевим результатом ЦІЛЕЙ ──
    rc = goals_df["Кінцевий результат"].value_counts().to_dict()
    num_year = [v for v in goals_df["Бал · РІК"] if isinstance(v, (int, float))]
    avg_year = sum(num_year) / len(num_year) if num_year else None

    kpis = "".join([
        kpi_card("Стратегічних цілей", len(goals_df), "gray"),
        kpi_card("Завдань", len(tasks_df), "gray"),
        kpi_card("Виконано", rc.get(ST_DONE, 0), "green"),
        kpi_card("Частково виконано", rc.get(ST_PARTIAL, 0), "yellow"),
        kpi_card("Не виконано", rc.get(ST_NOTDONE, 0), "red"),
        kpi_card("Не настав час", rc.get(ST_NOTYET, 0), "blue"),
        kpi_card(
            "Середнє за РІК (цілі), %",
            _rv_fmt_pct(avg_year) if avg_year is not None else "—",
            "gray"
        ),
    ])
    st.markdown(
        f'<div class="kpi-grid" style="grid-template-columns:repeat(7,1fr);">{kpis}</div>',
        unsafe_allow_html=True
    )

    # ── Фільтри (пошук / кінцевий результат / рівень) ──
    fcol = st.columns([3, 2.4, 2.6], gap="medium")
    with fcol[0]:
        query = st.text_input(
            "Пошук", placeholder="🔎 код або назва цілі / завдання…",
            key=f"rvg_q_{year}", label_visibility="collapsed"
        )
    with fcol[1]:
        st_filter = st.multiselect(
            "Кінцевий результат",
            [ST_DONE, ST_PARTIAL, ST_NOTDONE, ST_NOTYET, ST_OBSOLETE],
            default=[], key=f"rvg_st_{year}", placeholder="Кінцевий результат",
            label_visibility="collapsed"
        )
    with fcol[2]:
        level_sel = st.selectbox(
            "Рівень", ["Цілі + завдання", "Лише стратегічні цілі", "Лише завдання"],
            key=f"rvg_lvl_{year}", label_visibility="collapsed"
        )

    df = df_full.copy()
    if level_sel == "Лише стратегічні цілі":
        df = df[df["Тип"] == "goal"]
    elif level_sel == "Лише завдання":
        df = df[df["Тип"] == "task"]

    if query.strip():
        q = query.strip().lower()
        mask = (
            df["Код"].astype(str).str.lower().str.contains(q, regex=False)
            | df["Назва"].astype(str).str.lower().str.contains(q, regex=False)
        )
        df = df[mask]
    if st_filter:
        df = df[df["Кінцевий результат"].isin(st_filter)]

    # ── Легенда + лічильник ──
    st.markdown(f"""
    <div class="mio-legend">
        <span class="mio-chip done"><span class="dot"></span>Виконано (&ge; 100%)</span>
        <span class="mio-chip partial"><span class="dot"></span>Частково виконано (75% &lt; ... &lt; 100%)</span>
        <span class="mio-chip notdone"><span class="dot"></span>Не виконано (&le; 75%)</span>
        <span class="mio-chip notyet"><span class="dot"></span>Не настав час (х)</span>
        <span style="margin-left:auto;font-size:12px;color:#64748b;font-weight:700;align-self:center;">
            Показано {len(df)} рядків
        </span>
    </div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.info("За обраними фільтрами нічого не знайдено.")
    else:
        st.markdown(_build_rv_goals_table_html(df), unsafe_allow_html=True)

    # ── Експорт ──
    csv = df_full.copy()
    for col in RV_PERIOD_COLS:
        csv[col] = csv[col].map(lambda v: _rv_fmt_pct(v) if isinstance(v, (int, float)) else v)
    csv["Тип"] = csv["Тип"].map({"goal": "Стратегічна ціль", "task": "Завдання"})
    csv = csv.rename(columns={
        "Бал · I кв":  "Виконання I кв, %",
        "Бал · I пів": "Виконання I пів, %",
        "Бал · 9 міс": "Виконання 9 міс, %",
        "Бал · РІК":   "Виконання за РІК, %",
    })
    st.download_button(
        f"⬇️ Завантажити таблицю за {year} рік (CSV)",
        data=csv.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"РВ_СЦ_Завдання_{year}.csv",
        mime="text/csv",
        key=f"rvg_dl_{year}",
    )


def render_mode_rv_goals(strat_df, monitoring_df, years):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">РВ (СЦ, Завдання) · розрахунок виконання за цілями та завданнями</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        "<div style='font-size:13px;color:#475569;margin-bottom:8px;line-height:1.5;'>"
        "Бали виконання агрегуються вгору з режиму <b>«РВ (Заходи)»</b> за ієрархією кодів: "
        "<b>завдання</b> = середнє балів його <b>заходів</b>, <b>стратегічна ціль</b> = середнє балів її "
        "<b>завдань</b> (дворівнева агрегація). Стани <b>«х»</b> (не настав час) і <b>«в/а»</b> "
        "(втратило актуальність) у середнє <u>не входять</u>. "
        "<b>Кінцевий результат</b> класифікує бал за РІК: <b>= 100%</b> — виконано; "
        "<b>75–100%</b> — частково; <b>«х»</b> — не настав час; інакше — не виконано."
        "</div>",
        unsafe_allow_html=True
    )
    if len(years) == 1:
        _render_rv_goals_year(strat_df, monitoring_df, years[0])
    else:
        ytabs = st.tabs([f"{y} рік" for y in years])
        for tab, y in zip(ytabs, years):
            with tab:
                _render_rv_goals_year(strat_df, monitoring_df, y)
    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# РЕЖИМ «МіО цілі/завдання» — РЕНДЕР (надколонки 2026/2027/2028)
# ============================================================

_MIO_GT_CSS = """
<style>
.mgt-score { display:inline-flex; align-items:center; gap:5px; font-weight:800;
  font-variant-numeric:tabular-nums; padding:3px 9px; border-radius:999px;
  font-size:12px; border:1px solid transparent; white-space:nowrap; }
.mgt-score.s-green { background:#e8f7ee; color:#0b7a3b; border-color:#bbf7d0; }
.mgt-score.s-amber { background:#fff7e6; color:#92600e; border-color:#f5e0b0; }
.mgt-score.s-red   { background:#fdecec; color:#b42318; border-color:#fecaca; }
.mgt-score.s-dark  { background:#ecedf2; color:#334155; border-color:#cbd5e1; }
.mgt-score.s-done  { background:#e8f7ee; color:#0b7a3b; border-color:#bbf7d0; }
.mgt-score.s-na    { background:transparent; color:#94a3b8; border:none; font-weight:700; }
.mgt-chg { font-weight:700; font-variant-numeric:tabular-nums; color:#1e293b; }
.mgt-chg.up   { color:#0b7a3b; }
.mgt-chg.down { color:#b42318; }
.mgt-chg.na   { color:#94a3b8; font-weight:600; }
.mio-table td.mgt-plan { font-weight:800; color:#0c2f6e; background:#f3f7fe;
  font-variant-numeric:tabular-nums; }
.mio-table thead .grp-fact { background:#eef3fb; color:#334155; }
.mgt-legend { display:flex; flex-wrap:wrap; gap:14px; margin:4px 0 12px;
  font-size:12px; color:#475569; }
.mgt-legend span b { font-weight:800; }
.mgt-tag-goal { background:#eaf1ff; color:#1d4ed8; border:1px solid #c7dafd; }
.mgt-tag-task { background:#f3eefc; color:#6d28d9; border:1px solid #ddc9f7; }
</style>
"""


def _mio_gt_fmt_pct(val):
    if isinstance(val, (int, float)):
        return f"{val:.1f}".rstrip("0").rstrip(".") + "%"
    return ""


def _mio_gt_score_cell(val):
    """Комірка «Оцінка прогресу, %» зі світлофором (≥90/≥50/≥20)."""
    if isinstance(val, (int, float)):
        if val >= 90:   cls, dot = "s-green", "🟢"
        elif val >= 50: cls, dot = "s-amber", "🟡"
        elif val >= 20: cls, dot = "s-red", "🔴"
        else:           cls, dot = "s-dark", "⚫"
        return f'<td><span class="mgt-score {cls}">{dot} {val:.2f}%</span></td>'
    if val == "Виконується":
        return '<td><span class="mgt-score s-done">🟢 Виконується</span></td>'
    if val == "х":
        return '<td><span class="mgt-score s-dark" title="Дані відсутні / не настав час">х</span></td>'
    return '<td><span class="mgt-score s-na">·</span></td>'


def _mio_gt_change_cell(val):
    """Комірка «Зміна до попереднього року, %»."""
    if isinstance(val, (int, float)):
        cls = "up" if val > 100 else ("down" if val < 100 else "")
        return f'<td><span class="mgt-chg {cls}">{val:.2f}%</span></td>'
    if val == "х":
        return '<td><span class="mgt-chg na">х</span></td>'
    return '<td><span class="mgt-chg na">·</span></td>'


def _mio_gt_fact_cell(val):
    t = raw_value(val)
    if not t or t.lower() in ("nan", "none"):
        return '<td class="m-fact m-empty">·</td>'
    return f'<td class="m-fact">{_esc(t)}</td>'


def _mio_gt_anchor_cell(row):
    code = _esc(row["Код"])
    owner = _esc(row["Власник"])
    indicator = _esc(row["Індикатор"])
    unit = _esc(row["Од. виміру"])
    is_goal = row["Рівень"] == "goal"
    badge_cls = "mgt-tag-goal" if is_goal else "mgt-tag-task"
    badge = "Ціль" if is_goal else "Завд."
    tags = f'<span class="tag {badge_cls}" title="{owner}">{badge} {code}</span>'
    if unit:
        tags += f'<span class="tag tag-unit" title="Одиниця виміру">{unit}</span>'
    owner_html = f'<div class="m-name" title="{owner}">{owner}</div>' if owner else ""
    return (
        '<td class="m-anchor">'
        f'<div class="m-codeline"><span class="m-code">{code}</span>{tags}</div>'
        f'{owner_html}'
        f'<div class="m-ind" title="{indicator}">{indicator}</div>'
        '</td>'
    )


def _build_mio_gt_table_html(df, years):
    yrs = [y for y in _MIO_GT_YEARS if y in years] or [_MIO_GT_YEARS[0]]

    grp = ('<tr class="grp">'
           '<th class="m-anchor sticky-h" rowspan="2">Ціль / Завдання · показник</th>'
           '<th colspan="3" class="grp-fact">Факт (звітні роки)</th>')
    sub = ('<tr class="sub">'
           '<th class="sub-f">2021</th><th class="sub-f">2024</th><th class="sub-f">2025</th>')
    for y in yrs:
        grp += f'<th colspan="3" class="grp-year">{y}</th>'
        sub += ('<th class="sub-f sub-year">Факт</th>'
                '<th class="sub-s sub-year">Зміна, %</th>'
                '<th class="sub-s sub-year">Оцінка, %</th>')
    grp += '<th rowspan="2" class="grp-plan">Ціль на кінець 2028</th></tr>'
    sub += '</tr>'

    head = f'<div class="mio-tablewrap"><table class="mio-table"><thead>{grp}{sub}</thead><tbody>'

    body = []
    for _, r in df.iterrows():
        tr_cls = "rv-goal-row" if r["Рівень"] == "goal" else "rv-task-row"
        cells = _mio_gt_anchor_cell(r)
        cells += _mio_gt_fact_cell(r["Факт 2021"])
        cells += _mio_gt_fact_cell(r["Факт 2024"])
        cells += _mio_gt_fact_cell(r["Факт 2025"])
        for y in yrs:
            cells += _mio_gt_fact_cell(r[f"Факт {y}"])
            cells += _mio_gt_change_cell(r[f"Зміна {y}"])
            cells += _mio_gt_score_cell(r[f"Оцінка {y}"])
        cells += f'<td class="mgt-plan">{_esc(r["Ціль 2028"])}</td>'
        body.append(f'<tr class="{tr_cls}">{cells}</tr>')

    return head + "".join(body) + "</tbody></table></div>"


def render_mode_mio_gt(strat_df, monitoring_df, years):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">МіО цілі/завдання · моніторинг та оцінка індикаторів</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        "<div style='font-size:13px;color:#475569;margin-bottom:8px;line-height:1.5;'>"
        "Для кожного показника цілі/завдання — звітні факти (2021/2024/2025), факт за "
        "роки 2026–2028 (з погоджених подань), <b>зміна до попереднього року</b> та "
        "<b>оцінка прогресу у досягненні цільового орієнтиру на кінець 2028</b>. "
        "Для <b>цілей</b> оцінка рахується нормованою геометричною траєкторією, для "
        "<b>завдань</b> — як Факт/Ціль×100.</div>",
        unsafe_allow_html=True
    )
    st.markdown(_MIO_GT_CSS, unsafe_allow_html=True)

    df = build_mio_goals_tasks_table(strat_df, monitoring_df)
    if df.empty:
        st.info("Немає цілей/завдань з показниками для відображення.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    goals_df = df[df["Рівень"] == "goal"]
    tasks_df = df[df["Рівень"] == "task"]
    n_goals = goals_df["Код"].nunique()
    n_tasks = tasks_df["Код"].nunique()
    primary = sorted([y for y in _MIO_GT_YEARS if y in years]) or [_MIO_GT_YEARS[0]]
    py = primary[0]
    nums = [v for v in df[f"Оцінка {py}"] if isinstance(v, (int, float))]
    avg = sum(nums) / len(nums) if nums else None
    avg_lbl = f"{avg:.2f}%" if avg is not None else "—"

    st.markdown(
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:6px 0 12px;">'
        + kpi_card("Стратегічних цілей", n_goals, "blue")
        + kpi_card("Завдань", n_tasks, "teal")
        + kpi_card("Показників усього", len(df), "gray")
        + kpi_card(f"Середня оцінка · {py}", avg_lbl, "green")
        + '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="mgt-legend">'
        '<span><b>🟢 ≥ 90%</b> — на шляху досягнення</span>'
        '<span><b>🟡 50–89%</b> — потребує прискорення</span>'
        '<span><b>🔴 20–49%</b> — потребує суттєвого прискорення</span>'
        '<span><b>⚫ &lt; 20%</b> — недосяжне за такої динаміки</span>'
        '<span><b>х</b> — дані відсутні / не настав час</span>'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(_build_mio_gt_table_html(df, primary), unsafe_allow_html=True)

    # ── Експорт ──
    csv = df.copy()
    for y in _MIO_GT_YEARS:
        csv[f"Зміна {y}"] = csv[f"Зміна {y}"].map(
            lambda v: _mio_gt_fmt_pct(v) if isinstance(v, (int, float)) else v)
        csv[f"Оцінка {y}"] = csv[f"Оцінка {y}"].map(
            lambda v: _mio_gt_fmt_pct(v) if isinstance(v, (int, float)) else v)
    csv["Рівень"] = csv["Рівень"].map({"goal": "Стратегічна ціль", "task": "Завдання"})
    st.download_button(
        "⬇️ Завантажити таблицю «МіО цілі/завдання» (CSV)",
        data=csv.to_csv(index=False).encode("utf-8-sig"),
        file_name="МіО_цілі_завдання.csv",
        mime="text/csv",
        key="mio_gt_dl",
    )

    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# РЕЖИМ «Інт_Оцінка» — ІНТЕГРАЛЬНА ОЦІНКА ВИКОНАННЯ ЦІЛЕЙ
# ============================================================
# Точне відтворення аркуша «Інт_Оцінка» моделі. Один рядок = один показник
# цілі/завдання (та сама зернистість, що й «МіО_цілі_завдан»), згрупований у
# НАДБЛОКИ по роках (2026/2027/2028). У кожному надблоці — 6 колонок:
#
#   Факт                         ← «МіО_цілі_завдан» (J/N/R)  = mio["Факт {рік}"]
#   Оцінка прогресу у досягненні ← «МіО_цілі_завдан» (M/Q/W)÷100  (Excel H = M/100;
#                                  тут залишаємо у %, бо це лінійно й нагляднiше;
#                                  M=0 або текст → «х», як у формулі)
#   Зведена оцінка викон. ЗАХОДІВ (20%) ← VLOOKUP назви у «РВ (СЦ, Завд.)_РОЗРАХ»,
#                                  бал РІК (Бал · РІК) → ×100. Стоїть у рядку-якорі
#                                  ЦІЛІ (бал цілі) та ЗАВДАННЯ (бал завдання).
#   Зведена оцінка ЗАВДАНЬ по індик. (30%) ← AVERAGEIF(H за показниками завдання);
#                                  стоїть у рядку-якорі ЗАВДАННЯ.  (J)
#   Зведена оцінка прогресу інд. ЦІЛЕЙ (50%) ← AVERAGEIF(H за ВЛАСНИМИ показниками
#                                  цілі); стоїть у рядку-якорі ЦІЛІ.  (K)
#   ІНТЕГРАЛЬНА ОЦІНКА ← лише в рядку-якорі ЦІЛІ:
#        0.20·I(заходи цілі) + 0.30·AVERAGE(J завдань цілі) + 0.50·K(прогрес цілі)
#        Кожен компонент відсутній → 0 (еквівалент ЕСЛИОШИБКА(…;0)); вага завжди 1.0.
#
# Зв'язок з попередніми режимами: Факт і «Оцінка прогресу» беруться з
# build_mio_goals_tasks_table (режим «МіО цілі/завдання»), а бал виконання
# заходів — з build_rv_goals_table (режим «РВ (СЦ, Завдання)»). Жодного
# дублювання методики: Інт_Оцінка лише зважує вже пораховані величини 20/30/50.
# ============================================================

_INT_WEIGHTS = (0.20, 0.30, 0.50)   # I (заходи) · J (завдання) · K (прогрес цілі)


def _int_is_num(v):
    """Справжнє число (не None, не NaN). NaN з DataFrame має проходити як «порожньо»."""
    return isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v))


def _int_h_value(progress):
    """H-величина за показником = «Оцінка прогресу, %» (M).

    Відтворює Excel H = IFERROR(IF(OR(M="";M=0);"х";M/100);"х"):
    числове ≠ 0 → саме значення (у %); 0, порожнє чи текст («Виконується»/«х»)
    → None (виключається із середніх AVERAGEIF, як текст «х»).
    Масштаб лишаємо у %, бо інтеграл — лінійна зважена сума (×100 наприкінці).
    """
    if _int_is_num(progress) and progress != 0:
        return float(progress)
    return None


def _int_avg(values):
    """AVERAGEIF над H-величинами: лише числа; якщо жодного — None."""
    nums = [v for v in values if _int_is_num(v)]
    return sum(nums) / len(nums) if nums else None


def build_integral_table(strat_df, monitoring_df):
    """Будує дані режиму «Інт_Оцінка».

    Повертає (rows_df, goals_df):
      • rows_df — показникова таблиця (як «МіО_цілі_завдан») з прапорцями-якорями
        та поколонковими значеннями по роках: fact/h/i/j/k/int (None де комірка
        має бути порожньою — тобто не на рядку-якорі);
      • goals_df — зведення по цілях × роки (Інтеграл + компоненти I/J/K) для KPI,
        короткого підсумку й експорту.
    """
    mio = build_mio_goals_tasks_table(strat_df, monitoring_df)
    if mio is None or mio.empty:
        return pd.DataFrame(), pd.DataFrame()

    # 1) Бал РІК виконання заходів по роках (з «РВ (СЦ, Завдання)») → {рік: {код: бал}}
    rv_score = {}
    for y in _MIO_GT_YEARS:
        rvg = build_rv_goals_table(strat_df, monitoring_df, y)
        d = {}
        if rvg is not None and not rvg.empty:
            for _, rr in rvg.iterrows():
                d[raw_value(rr["Код"])] = rr["Бал · РІК"]
        rv_score[y] = d

    goal_rows = mio[mio["Рівень"] == "goal"]
    task_rows = mio[mio["Рівень"] == "task"]
    goal_codes = list(dict.fromkeys(goal_rows["Код"].map(raw_value)))
    task_codes = list(dict.fromkeys(task_rows["Код"].map(raw_value)))

    # 2) Поколонкові агрегати по роках
    goal_K, task_J = {}, {}          # K цілі (власні показники) · J завдання
    goal_I, task_I = {}, {}          # I заходів (бал РІК ×100)
    goal_Jcomp, goal_int = {}, {}    # середнє J завдань цілі · інтеграл
    wI, wJ, wK = _INT_WEIGHTS

    for y in _MIO_GT_YEARS:
        gK, tJ, gI, tI, gJc, gInt = {}, {}, {}, {}, {}, {}

        for tcode in task_codes:
            vals = [_int_h_value(v) for v in
                    task_rows[task_rows["Код"].map(raw_value) == tcode][f"Оцінка {y}"]]
            tJ[tcode] = _int_avg(vals)
            bal = rv_score[y].get(tcode)
            tI[tcode] = bal * 100 if isinstance(bal, (int, float)) else None

        for gcode in goal_codes:
            vals = [_int_h_value(v) for v in
                    goal_rows[goal_rows["Код"].map(raw_value) == gcode][f"Оцінка {y}"]]
            gK[gcode] = _int_avg(vals)
            bal = rv_score[y].get(gcode)
            gI[gcode] = bal * 100 if isinstance(bal, (int, float)) else None
            # середнє J завдань цілі (префікс коду; лише числові J)
            jts = [tJ[tc] for tc in task_codes
                   if tc.startswith(gcode) and isinstance(tJ.get(tc), (int, float))]
            gJc[gcode] = sum(jts) / len(jts) if jts else None
            gInt[gcode] = (wI * (gI[gcode] or 0)
                           + wJ * (gJc[gcode] or 0)
                           + wK * (gK[gcode] or 0))

        goal_K[y], task_J[y] = gK, tJ
        goal_I[y], task_I[y] = gI, tI
        goal_Jcomp[y], goal_int[y] = gJc, gInt

    # 3) Показникові рядки + прапорці-якорі (перший рядок цілі / завдання)
    seen_goal, seen_task = set(), set()
    rows = []
    for _, r in mio.iterrows():
        is_goal = r["Рівень"] == "goal"
        code = raw_value(r["Код"])
        g_anchor = is_goal and code not in seen_goal
        t_anchor = (not is_goal) and code not in seen_task
        if g_anchor:
            seen_goal.add(code)
        if t_anchor:
            seen_task.add(code)

        entry = {
            "Рівень": r["Рівень"], "Код": code, "Власник": r["Власник"],
            "Індикатор": r["Індикатор"], "Од. виміру": r["Од. виміру"],
            "is_goal_anchor": g_anchor, "is_task_anchor": t_anchor,
        }
        for y in _MIO_GT_YEARS:
            entry[f"fact_{y}"] = r[f"Факт {y}"]
            entry[f"h_{y}"] = r[f"Оцінка {y}"]            # відображаємо як прогрес, %
            # I — бал заходів цілі (на якорі цілі) або завдання (на якорі завдання)
            if g_anchor:
                entry[f"i_{y}"] = goal_I[y].get(code)
            elif t_anchor:
                entry[f"i_{y}"] = task_I[y].get(code)
            else:
                entry[f"i_{y}"] = None
            entry[f"j_{y}"] = task_J[y].get(code) if t_anchor else None
            entry[f"k_{y}"] = goal_K[y].get(code) if g_anchor else None
            entry[f"int_{y}"] = goal_int[y].get(code) if g_anchor else None
        rows.append(entry)
    rows_df = pd.DataFrame(rows)

    # 4) Зведення по цілях × роки
    gsum = []
    goal_name = {raw_value(r["Код"]): raw_value(r["Власник"])
                 for _, r in goal_rows.iterrows()}
    for gcode in goal_codes:
        rec = {"Код": gcode, "Ціль": goal_name.get(gcode, "")}
        for y in _MIO_GT_YEARS:
            rec[f"Заходи {y}"] = goal_I[y].get(gcode)
            rec[f"Завдання {y}"] = goal_Jcomp[y].get(gcode)
            rec[f"Прогрес {y}"] = goal_K[y].get(gcode)
            rec[f"Інтеграл {y}"] = goal_int[y].get(gcode)
        gsum.append(rec)
    goals_df = pd.DataFrame(gsum)
    return rows_df, goals_df


# ── Форматери комірок ──

def _int_fmt_pct(val):
    if _int_is_num(val):
        return f"{val:.2f}%"
    return ""


def _int_level(val):
    """Світлофор інтеграла: ≥80 🟢 · 50–79 🟡 · 20–49 🔴 · <20 ⚫."""
    if val >= 80:   return "s-green", "🟢"
    if val >= 50:   return "s-amber", "🟡"
    if val >= 20:   return "s-red", "🔴"
    return "s-dark", "⚫"


def _int_fact_cell(val):
    t = raw_value(val)
    if not t or t.lower() in ("nan", "none"):
        return '<td class="int-fact int-empty">·</td>'
    return f'<td class="int-fact">{_esc(t)}</td>'


def _int_h_cell(val):
    """Комірка «Оцінка прогресу, %» (Excel H). 0/текст → «х»."""
    hv = _int_h_value(val)
    if hv is not None:
        cls, dot = _int_level(hv)
        return f'<td><span class="int-pill {cls}">{dot} {hv:.2f}%</span></td>'
    if val == "Виконується":
        return '<td><span class="int-pill s-green">🟢 Викон.</span></td>'
    return '<td><span class="int-pill s-na" title="Дані відсутні / 0 / не настав час">х</span></td>'


def _int_comp_cell(val, css):
    """Комірка компонента (заходи/завдання/прогрес цілі) — без світлофора."""
    if _int_is_num(val):
        return f'<td><span class="int-comp {css}">{val:.2f}%</span></td>'
    return '<td><span class="int-comp int-na">·</span></td>'


def _int_integral_cell(val):
    if _int_is_num(val):
        cls, dot = _int_level(val)
        return f'<td class="int-final-td"><span class="int-final {cls}">{dot} {val:.2f}%</span></td>'
    return '<td class="int-final-td"><span class="int-final int-na">·</span></td>'


def _int_anchor_cell(row):
    code = _esc(row["Код"])
    owner = _esc(row["Власник"])
    indicator = _esc(row["Індикатор"])
    unit = _esc(row["Од. виміру"])
    is_goal = row["Рівень"] == "goal"
    badge_cls = "mgt-tag-goal" if is_goal else "mgt-tag-task"
    badge = "Ціль" if is_goal else "Завд."
    tags = f'<span class="tag {badge_cls}" title="{owner}">{badge} {code}</span>'
    if unit:
        tags += f'<span class="tag tag-unit" title="Одиниця виміру">{unit}</span>'
    owner_html = f'<div class="m-name" title="{owner}">{owner}</div>' if owner else ""
    return (
        '<td class="m-anchor">'
        f'<div class="m-codeline"><span class="m-code">{code}</span>{tags}</div>'
        f'{owner_html}'
        f'<div class="m-ind" title="{indicator}">{indicator}</div>'
        '</td>'
    )


_INT_CSS = """
<style>
.int-pill { display:inline-flex; align-items:center; gap:5px; font-weight:800;
  font-variant-numeric:tabular-nums; padding:3px 9px; border-radius:999px;
  font-size:12px; border:1px solid transparent; white-space:nowrap; }
.int-pill.s-green { background:#e8f7ee; color:#0b7a3b; border-color:#bbf7d0; }
.int-pill.s-amber { background:#fff7e6; color:#92600e; border-color:#f5e0b0; }
.int-pill.s-red   { background:#fdecec; color:#b42318; border-color:#fecaca; }
.int-pill.s-dark  { background:#ecedf2; color:#334155; border-color:#cbd5e1; }
.int-pill.s-na    { background:transparent; color:#94a3b8; border:none; font-weight:700; }
.int-comp { font-weight:700; font-variant-numeric:tabular-nums; font-size:12px;
  padding:2px 7px; border-radius:6px; white-space:nowrap; }
.int-comp.c-i { color:#0c5db5; background:#eef4fc; }
.int-comp.c-j { color:#6d28d9; background:#f5eefd; }
.int-comp.c-k { color:#0b7a3b; background:#ecfaf1; }
.int-comp.int-na { color:#94a3b8; background:transparent; font-weight:600; }
.int-final { display:inline-flex; align-items:center; gap:5px; font-weight:900;
  font-variant-numeric:tabular-nums; padding:4px 11px; border-radius:999px;
  font-size:13px; border:1px solid transparent; white-space:nowrap; }
.int-final.s-green { background:#dcfce7; color:#166534; border-color:#86efac; }
.int-final.s-amber { background:#fef3c7; color:#92400e; border-color:#fcd34d; }
.int-final.s-red   { background:#fee2e2; color:#991b1b; border-color:#fca5a5; }
.int-final.s-dark  { background:#e2e8f0; color:#334155; border-color:#cbd5e1; }
.int-final.int-na  { background:transparent; color:#94a3b8; border:none; }
.mio-table td.int-fact { font-variant-numeric:tabular-nums; font-weight:700; color:#1e293b; }
.mio-table td.int-empty { color:#cbd5e1; font-weight:600; }
.mio-table td.int-final-td { background:#f6f9ff; }
.mio-table thead .grp-int { background:#0c2f6e; color:#fff; }
.mio-table thead .sub-int { background:#eef3fb; color:#334155; font-size:10.5px; }
.mio-table thead .sub-int.col-final { background:#dde8fb; font-weight:800; color:#0c2f6e; }
.int-weights { display:flex; flex-wrap:wrap; gap:14px; margin:4px 0 12px;
  font-size:12px; color:#475569; }
.int-weights b { font-weight:800; }
.int-formula { font-size:12.5px; color:#0c2f6e; background:#eef4fc; border:1px solid #cfe0fa;
  border-radius:8px; padding:8px 12px; margin:2px 0 12px; font-variant-numeric:tabular-nums; }
</style>
"""


def _build_int_table_html(rows_df, years):
    yrs = [y for y in _MIO_GT_YEARS if y in years] or [_MIO_GT_YEARS[0]]

    grp = ('<tr class="grp">'
           '<th class="m-anchor sticky-h" rowspan="2">Ціль / Завдання · показник</th>')
    sub = '<tr class="sub">'
    for y in yrs:
        grp += f'<th colspan="6" class="grp-int">{y} рік</th>'
        sub += ('<th class="sub-int">Факт</th>'
                '<th class="sub-int">Прогрес,&nbsp;%</th>'
                '<th class="sub-int">Заходи 20%</th>'
                '<th class="sub-int">Завдання 30%</th>'
                '<th class="sub-int">Прогрес&nbsp;Цілі 50%</th>'
                '<th class="sub-int col-final">ІНТЕГРАЛ</th>')
    grp += '</tr>'
    sub += '</tr>'

    head = f'<div class="mio-tablewrap"><table class="mio-table"><thead>{grp}{sub}</thead><tbody>'

    body = []
    for _, r in rows_df.iterrows():
        tr_cls = "rv-goal-row" if r["Рівень"] == "goal" else "rv-task-row"
        cells = _int_anchor_cell(r)
        for y in yrs:
            cells += _int_fact_cell(r[f"fact_{y}"])
            cells += _int_h_cell(r[f"h_{y}"])
            cells += _int_comp_cell(r[f"i_{y}"], "c-i")
            cells += _int_comp_cell(r[f"j_{y}"], "c-j")
            cells += _int_comp_cell(r[f"k_{y}"], "c-k")
            cells += _int_integral_cell(r[f"int_{y}"])
        body.append(f'<tr class="{tr_cls}">{cells}</tr>')

    return head + "".join(body) + "</tbody></table></div>"


def render_mode_integral(strat_df, monitoring_df, years):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">Інт_Оцінка · інтегральна оцінка виконання цілей стратплану</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        "<div style='font-size:13px;color:#475569;margin-bottom:8px;line-height:1.5;'>"
        "Зважена оцінка <b>20/30/50</b>, що зводить три попередні режими докупи на рівні "
        "<b>стратегічної цілі</b>. Кожен рядок — показник цілі/завдання; надблок — рік. "
        "<b>Факт</b> і <b>оцінка прогресу</b> підтягуються з «<b>МіО цілі/завдання</b>», "
        "<b>оцінка виконання заходів</b> — з «<b>РВ (СЦ, Завдання)</b>» (бал за РІК). "
        "Компоненти стоять на рядку-якорі відповідного рівня; інтеграл — лише на цілі."
        "</div>",
        unsafe_allow_html=True
    )
    st.markdown(_MIO_GT_CSS, unsafe_allow_html=True)
    st.markdown(_INT_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="int-formula">Інтегральна оцінка цілі = '
        '<b>0.20</b>·(зведена оцінка виконання заходів) + '
        '<b>0.30</b>·(середня оцінка виконання завдань по індикаторах) + '
        '<b>0.50</b>·(оцінка прогресу по індикаторах цілі)</div>',
        unsafe_allow_html=True
    )

    rows_df, goals_df = build_integral_table(strat_df, monitoring_df)
    if rows_df.empty:
        st.info("Немає цілей/завдань з показниками для інтегральної оцінки.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    primary = sorted([y for y in _MIO_GT_YEARS if y in years]) or [_MIO_GT_YEARS[0]]
    py = primary[0]
    n_goals = goals_df["Код"].nunique()
    n_tasks = rows_df[rows_df["Рівень"] == "task"]["Код"].nunique()
    int_vals = [v for v in goals_df[f"Інтеграл {py}"] if isinstance(v, (int, float))]
    avg_int = sum(int_vals) / len(int_vals) if int_vals else None
    on_track = sum(1 for v in int_vals if v >= 80)

    st.markdown(
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:6px 0 12px;">'
        + kpi_card("Стратегічних цілей", n_goals, "blue")
        + kpi_card("Завдань", n_tasks, "teal")
        + kpi_card(f"Середній інтеграл · {py}",
                   _int_fmt_pct(avg_int) if avg_int is not None else "—", "green")
        + kpi_card(f"Цілей 🟢 ≥80% · {py}", f"{on_track} / {n_goals}", "gray")
        + '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="int-weights">'
        '<span><b>Факт</b> — фактичне значення показника (з МіО)</span>'
        '<span><b>Прогрес, %</b> — оцінка прогресу у досягненні (0 / «—» → «х»)</span>'
        '<span><b>🟢 ≥80%</b> · <b>🟡 50–79%</b> · <b>🔴 20–49%</b> · <b>⚫ &lt;20%</b></span>'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(_build_int_table_html(rows_df, primary), unsafe_allow_html=True)

    # ── Підсумок по цілях (компактно, для всіх обраних років) ──
    with st.expander("📊 Підсумок по стратегічних цілях (інтеграл і компоненти)", expanded=False):
        view = goals_df.copy()
        cols = ["Код", "Ціль"]
        for y in primary:
            for pref in (f"Заходи {y}", f"Завдання {y}", f"Прогрес {y}", f"Інтеграл {y}"):
                view[pref] = view[pref].map(_int_fmt_pct)
                cols.append(pref)
        st.dataframe(view[cols], use_container_width=True, hide_index=True)

    # ── Експорт ──
    csv = rows_df.copy()
    for y in _MIO_GT_YEARS:
        for pref in (f"h_{y}", f"i_{y}", f"j_{y}", f"k_{y}", f"int_{y}"):
            csv[pref] = csv[pref].map(lambda v: _int_fmt_pct(v) if isinstance(v, (int, float)) else "")
    csv["Рівень"] = csv["Рівень"].map({"goal": "Стратегічна ціль", "task": "Завдання"})
    csv = csv.drop(columns=["is_goal_anchor", "is_task_anchor"])
    rename = {}
    for y in _MIO_GT_YEARS:
        rename.update({
            f"fact_{y}": f"Факт {y}", f"h_{y}": f"Прогрес {y}, %",
            f"i_{y}": f"Заходи {y} (20%)", f"j_{y}": f"Завдання {y} (30%)",
            f"k_{y}": f"Прогрес цілі {y} (50%)", f"int_{y}": f"ІНТЕГРАЛ {y}",
        })
    csv = csv.rename(columns=rename)
    st.download_button(
        "⬇️ Завантажити «Інт_Оцінка» (CSV)",
        data=csv.to_csv(index=False).encode("utf-8-sig"),
        file_name="Інтегральна_оцінка.csv",
        mime="text/csv",
        key="int_dl",
    )

    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# РЕЖИМ «МіО Фінансування» — ФІНАНСОВЕ ВИКОНАННЯ ЗАХОДІВ
# ============================================================
# Відтворює методику аркуша «МіО Фінансування» еталонної моделі:
# шапка «Державний бюджет України» → КПКВК + по три річні блоки
# (2026/2027/2028), у кожному: план (млрд грн) · факт (млрд грн) ·
# % виконання · стан виконання заходу, % · К еластичності.
# Додатково (за вимогою) лишаємо колонку «Інше джерело фінансування».
#
# Звідки беруться дані:
#   • Перелік заходів і «Стан виконання заходу, %» — з режиму
#     «РВ (Заходи)» (build_rv_measures_table → «Бал · РІК», тобто
#     VLOOKUP у 'РВ (Заходи)' за моделлю: I=стовпець 7/14/21 для
#     2026/2027/2028). Бал РІК — частка 0–1 (або «х»/«в/а»).
#   • Бюджетний ПЛАН (млрд грн), КПКВК та інше джерело — з даних app
#     (Страт_матриця: Y=КПКВК, Z/AA/AB=план 2026/2027/2028, AC=інше джерело).
#   • Бюджетний ФАКТ (млрд грн) — з ОКРЕМОГО Excel «БП під моніторинг СП.xlsx»
#     (FIN_FILE_PATH), keyed за кодом заходу (+ роком). Файл вноситься окремо;
#     поки його немає — факт показується прочерком, % виконання й
#     еластичність не рахуються, а план і стан виконання вже відображаються.
#
# Формули (точно як у моделі — частки, формат «%»):
#   % виконання              = Факт, млрд / План, млрд          (H = G/F)
#   стан виконання заходу     = Бал РІК заходу з «РВ (Заходи)»    (I = VLOOKUP)
#   К еластичності            = % виконання / стан виконання      (J = H/I)
#     (≈1 — фінансування пропорційне результату; >1 — витрат більше,
#      ніж фізичного результату; <1 — результат випереджає витрати).
# ============================================================

# Очікувана структура «БП під моніторинг СП.xlsx» (ФАКТ виконання бюджету).
# План/КПКВК/інше джерело беруться з app (Страт_матриця); цей файл дає ФАКТ.
# Підтримуються ДВА формати (визначається автоматично за заголовками):
#
#  A) ДОВГИЙ (по рядку на захід+рік):
#     Код заходу | Рік | Факт (млрд грн)
#     (за бажання — також КПКВК / Інше джерело / План, якщо їх немає в app)
#
#  B) ШИРОКИЙ (по рядку на захід, роки в колонках):
#     Код заходу | Факт 2026 | Факт 2027 | Факт 2028
#     (опціонально також План 2026/2027/2028, КПКВК, Інше джерело)
#
# Розпізнавання назв колонок — гнучке (без врахування регістру).
FIN_SHEET_CANDIDATES = ["МіО Фінансування", "Фінансування", "БП", "Sheet1", "Аркуш1"]
FIN_CODE_KEYS   = ["код заходу", "код", "захід", "strat_code", "measure_code", "code", "кпкв код"]
FIN_YEAR_KEYS   = ["рік", "year", "звітний рік"]
FIN_KPKVK_KEYS  = ["кпквк", "kpkvk", "kpkv", "код кпквк", "бюджетна програма"]
FIN_SOURCE_KEYS = ["інше джерело фінансування", "інше джерело", "джерело фінансування",
                   "other_source", "fin_source", "джерело"]
FIN_PLAN_KEYS   = ["план (млрд грн)", "план, млрд грн", "план млрд грн", "план млрд",
                   "план", "plan", "fin_plan", "fin_plan_bln"]
FIN_FACT_KEYS   = ["факт (млрд грн)", "факт, млрд грн", "факт млрд грн", "факт млрд",
                   "факт", "fact", "fin_fact", "fin_fact_bln"]


def _fin_norm_header(value):
    """Нормалізує заголовок колонки: нижній регістр, без зайвих пробілів/переносів."""
    t = raw_value(value).lower().replace("\n", " ").replace("\xa0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _fin_match_col(columns, candidates):
    """Шукає колонку, чий нормалізований заголовок збігається/містить кандидата."""
    norm = {_fin_norm_header(c): c for c in columns}
    for cand in candidates:                      # точний збіг
        if cand in norm:
            return norm[cand]
    for cand in candidates:                      # частковий збіг (план/факт + рік)
        for nk, orig in norm.items():
            if nk.startswith(cand) or cand in nk:
                return orig
    return None


def _fin_year_columns(columns):
    """Для широкого формату: знаходить пари (рік → колонка плану/факту)."""
    plan_by_year, fact_by_year = {}, {}
    for c in columns:
        nk = _fin_norm_header(c)
        m = re.search(r"(20\d{2})", nk)
        if not m:
            continue
        yr = m.group(1)
        if nk.startswith("план") or "план" in nk:
            plan_by_year[yr] = c
        elif nk.startswith("факт") or "факт" in nk:
            fact_by_year[yr] = c
    return plan_by_year, fact_by_year


@st.cache_data(show_spinner=False, ttl=300)
def load_financing_data():
    """
    Зчитує бюджетні дані заходів із окремого Excel «БП під моніторинг СП.xlsx»
    у вигляді індексу:
        {(code, year_str): {kpkvk, other_source, plan_bln, fact_bln}}

    Автовизначення довгого/широкого формату. Якщо файлу немає або він
    нечитабельний — повертає порожній індекс (режим працює, бюджетні
    колонки — прочерками).
    """
    index = {}
    try:
        xls = pd.ExcelFile(FIN_FILE_PATH, engine="openpyxl")
    except Exception:
        return index  # файл ще не внесено — тиха коректна деградація

    # Вибір аркуша: відомий за назвою, інакше перший.
    sheet = next((s for s in FIN_SHEET_CANDIDATES if s in xls.sheet_names),
                 xls.sheet_names[0] if xls.sheet_names else None)
    if sheet is None:
        return index

    try:
        df = xls.parse(sheet)
    except Exception:
        return index
    if df is None or df.empty:
        return index

    cols = list(df.columns)
    k_code  = _fin_match_col(cols, FIN_CODE_KEYS)
    k_year  = _fin_match_col(cols, FIN_YEAR_KEYS)
    k_kpkvk = _fin_match_col(cols, FIN_KPKVK_KEYS)
    k_src   = _fin_match_col(cols, FIN_SOURCE_KEYS)
    if not k_code:
        return index

    plan_by_year, fact_by_year = _fin_year_columns(cols)
    wide = (not k_year) and (plan_by_year or fact_by_year)

    if wide:
        # ── ШИРОКИЙ формат: роки в колонках ──
        for _, rec in df.iterrows():
            code = raw_value(rec.get(k_code))
            if not code:
                continue
            kpkvk = raw_value(rec.get(k_kpkvk)) if k_kpkvk else ""
            src   = raw_value(rec.get(k_src)) if k_src else ""
            years = set(plan_by_year) | set(fact_by_year)
            for yr in years:
                plan = parse_number(rec.get(plan_by_year[yr])) if yr in plan_by_year else None
                fact = parse_number(rec.get(fact_by_year[yr])) if yr in fact_by_year else None
                index[(code, yr)] = {
                    "kpkvk": kpkvk, "other_source": src,
                    "plan_bln": plan, "fact_bln": fact,
                }
    else:
        # ── ДОВГИЙ формат: рядок на захід+рік ──
        k_plan = _fin_match_col(cols, FIN_PLAN_KEYS)
        k_fact = _fin_match_col(cols, FIN_FACT_KEYS)
        for _, rec in df.iterrows():
            code = raw_value(rec.get(k_code))
            if not code:
                continue
            year = raw_value(rec.get(k_year)) if k_year else ""
            # Рік на кшталт «2026.0» → «2026»
            ym = re.search(r"(20\d{2})", year)
            year = ym.group(1) if ym else year
            index[(code, year)] = {
                "kpkvk": raw_value(rec.get(k_kpkvk)) if k_kpkvk else "",
                "other_source": raw_value(rec.get(k_src)) if k_src else "",
                "plan_bln": parse_number(rec.get(k_plan)) if k_plan else None,
                "fact_bln": parse_number(rec.get(k_fact)) if k_fact else None,
            }
    return index


def _fin_lookup(fin_index, code, year):
    """Бере бюджетний запис за (код, рік); якщо немає — пробує без року."""
    return (fin_index.get((code, str(year)))
            or fin_index.get((code, ""))
            or {})


def build_financing_table(strat_df, monitoring_df, fin_index, year):
    """
    Формує таблицю режиму «МіО Фінансування» за один рік.

    Колонки:
      Захід (якір: код+назва) · КПКВК · Інше джерело фінансування ·
      План, млрд грн · Факт, млрд грн · % виконання (фін.) ·
      Стан виконання заходу, % · Коефіцієнт еластичності.
    """
    base = build_mio_measures_table(strat_df, monitoring_df, year)
    if base.empty:
        return base

    # Стан виконання заходу = «Бал · РІК» з «РВ (Заходи)» (модель: VLOOKUP,
    # стовпець 7/14/21 для 2026/2027/2028). Бал РІК — частка 0–1 / «х» / «в/а».
    rv = build_rv_measures_table(strat_df, monitoring_df, year)
    rv_year_by_code = {}
    if not rv.empty:
        for _, rr in rv.iterrows():
            rv_year_by_code[rr["Захід"]] = rr["Бал · РІК"]

    # Плановий бюджет, КПКВК та інше джерело — зі Страт_матриці (дані app):
    #   Y=КПКВК · Z/AA/AB=план 2026/2027/2028 · AC=інше джерело.
    plan_col = f"fin_plan_{year}"
    strat_fin = {}
    for _, m in strat_df[strat_df["object_type"] == "measure"].iterrows():
        strat_fin[raw_value(m.get("code"))] = {
            "kpkvk": raw_value(m.get("kpkvk")),
            "other_source": raw_value(m.get("fin_other_source")),
            "plan_bln": parse_number(m.get(plan_col)) if plan_col in m else None,
        }

    rows = []
    for _, r in base.iterrows():
        code = r["Захід"]
        sfin = strat_fin.get(code, {})
        fin = _fin_lookup(fin_index, code, year)   # окремий Excel (факт)

        kpkvk     = sfin.get("kpkvk", "") or fin.get("kpkvk", "")
        other_src = sfin.get("other_source", "") or fin.get("other_source", "")
        # План — пріоритетно зі Страт_матриці; якщо немає, з окремого Excel.
        plan_bln  = sfin.get("plan_bln", None)
        if plan_bln is None:
            plan_bln = fin.get("plan_bln", None)
        # Факт — з окремого Excel «БП під моніторинг СП».
        fact_bln  = fin.get("fact_bln", None)

        # ── Показуємо ЛИШЕ заходи, що мають фінансування ──
        # за держбюджетом (КПКВК або плановий обсяг) АБО за іншим джерелом.
        has_state_budget = bool(kpkvk) or (plan_bln is not None)
        has_other_source = bool(other_src)
        if not (has_state_budget or has_other_source or fact_bln is not None):
            continue  # фінансування немає — захід не відображається

        # % виконання (фін.) = Факт / План (модель: H = G/F). У відсотках (×100).
        if plan_bln not in (None, 0) and fact_bln is not None:
            fin_pct = fact_bln / plan_bln * 100.0
        else:
            fin_pct = None

        # Стан виконання заходу, % = Бал РІК заходу × 100 (частка 0–1 → %).
        rv_year = rv_year_by_code.get(code, "х")
        if isinstance(rv_year, (int, float)):
            state_pct = rv_year * 100.0
        else:
            state_pct = rv_year  # "х" / "в/а"

        # К еластичності = % виконання / стан виконання (модель: J = H/I).
        # IFERROR(IF(H/I; H/I; ""): порожньо при нульовому факті/стані або помилці.
        if (fin_pct not in (None, 0, 0.0)
                and isinstance(state_pct, (int, float)) and state_pct not in (0, 0.0)):
            elasticity = fin_pct / state_pct
        else:
            elasticity = None

        rows.append({
            "Стратегічна ціль": r["Стратегічна ціль"],
            "Завдання":         r["Завдання"],
            "Захід":            code,
            "Назва заходу":     r["Назва заходу"],
            "Індикатор":        r["Індикатор"],
            "Од. виміру":       r["Од. виміру"],
            "КПКВК":            kpkvk,
            "Інше джерело фінансування": other_src,
            "План, млрд грн":   plan_bln,
            "Факт, млрд грн":   fact_bln,
            "% виконання":      fin_pct,
            "Стан виконання заходу, %": state_pct,
            "Коефіцієнт еластичності":  elasticity,
        })

    return pd.DataFrame(rows)


def _fin_bln_cell(val):
    """Сума у млрд грн (3 знаки) або прочерк."""
    if isinstance(val, (int, float)):
        txt = f"{val:.3f}".rstrip("0").rstrip(".").replace(".", ",")
        return f'<td class="m-fact" style="text-align:right;font-variant-numeric:tabular-nums;">{txt}</td>'
    return '<td class="m-fact m-empty" style="text-align:right;">·</td>'


def _fin_text_cell(val, align="left"):
    t = raw_value(val)
    if not t:
        return '<td class="m-fact m-empty">·</td>'
    return f'<td class="m-fact" style="text-align:{align};">{_esc(t)}</td>'


def _fin_pct_cell(val):
    """Відсоток фінансового виконання — прогрес-бар (формат «0%»)."""
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
        label = f"{val:.1f}".replace(".0", "").replace(".", ",") + "%"
        return (
            '<td class="m-ratio">'
            f'<div class="rbar {cls}"><div class="rfill" style="width:{width:.0f}%;"></div>'
            f'<span class="rlabel">{label}</span></div></td>'
        )
    return '<td class="m-ratio"><span class="m-empty">·</span></td>'


def _fin_state_cell(val):
    """Стан виконання заходу, % (фізичний) — той самий вигляд, що Факт/План."""
    return _ratio_cell_html(val)


def _fin_elast_cell(val):
    """
    Коефіцієнт еластичності (% виконання фін. / стан виконання, %).
    Колір: ~1 — збалансовано (зелений), >1 — витрат більше за результат
    (жовтий/червоний), <1 — результат випереджає витрати (синій).
    """
    if not isinstance(val, (int, float)):
        return '<td class="m-st"><span class="m-empty" title="Недостатньо даних (немає фін. виконання або стан = 0)">·</span></td>'
    if 0.9 <= val <= 1.1:
        cls = "done"
    elif val < 0.9:
        cls = "notyet"          # синій: результат випереджає витрати
    elif val <= 1.5:
        cls = "partial"         # жовтий: помірний перевитрат на результат
    else:
        cls = "notdone"         # червоний: витрат значно більше за результат
    txt = f"{val:.2f}".replace(".", ",")
    return (f'<td class="m-st"><span class="tchip {cls}" '
            f'title="% фін. виконання ÷ стан виконання заходу, %">{txt}</span></td>')


def _build_financing_table_html(df):
    """Збирає HTML таблиці режиму «МіО Фінансування»."""
    head = """
    <div class="mio-tablewrap">
    <table class="mio-table">
      <thead>
        <tr class="grp">
          <th class="m-anchor sticky-h" rowspan="2">Захід</th>
          <th rowspan="2">КПКВК</th>
          <th rowspan="2">Інше джерело<br>фінансування</th>
          <th colspan="3" class="grp-q">Фінансування</th>
          <th rowspan="2" class="grp-year">Стан виконання<br>заходу, %</th>
          <th rowspan="2" class="grp-plan">Коефіцієнт<br>еластичності</th>
        </tr>
        <tr class="sub">
          <th class="sub-s">План, млрд грн</th>
          <th class="sub-s">Факт, млрд грн</th>
          <th class="sub-s">% виконання</th>
        </tr>
      </thead>
      <tbody>
    """
    rows = []
    for _, r in df.iterrows():
        cells = (
            _measure_anchor_html(r)
            + _fin_text_cell(r["КПКВК"], align="center")
            + _fin_text_cell(r["Інше джерело фінансування"])
            + _fin_bln_cell(r["План, млрд грн"])
            + _fin_bln_cell(r["Факт, млрд грн"])
            + _fin_pct_cell(r["% виконання"])
            + _fin_state_cell(r["Стан виконання заходу, %"])
            + _fin_elast_cell(r["Коефіцієнт еластичності"])
        )
        rows.append(f"<tr>{cells}</tr>")
    tail = "</tbody></table></div>"
    return head + "".join(rows) + tail


def _render_financing_year(strat_df, monitoring_df, fin_index, year):
    df_full = build_financing_table(strat_df, monitoring_df, fin_index, year)
    n_measures_all = int((strat_df["object_type"] == "measure").sum()) if strat_df is not None else 0
    if df_full.empty:
        st.info(
            f"Жоден із {n_measures_all} заходів не має фінансування "
            "(ні за держбюджетом — КПКВК/план, ні за іншим джерелом). "
            "Показувати нічого."
        )
        return

    has_plan = df_full["План, млрд грн"].notna().any()
    has_fact = df_full["Факт, млрд грн"].notna().any()
    st.caption(
        f"💰 Показано лише заходи з фінансуванням: {len(df_full)} із {n_measures_all}. "
        "Заходи без бюджету (держбюджет або інше джерело) приховано."
    )

    # ── KPI ──
    n_total = len(df_full)
    plan_sum = df_full["План, млрд грн"].dropna().sum()
    fact_sum = df_full["Факт, млрд грн"].dropna().sum()
    fin_pct_total = (fact_sum / plan_sum * 100.0) if plan_sum else None
    elast_vals = [v for v in df_full["Коефіцієнт еластичності"] if isinstance(v, (int, float))]
    elast_avg = sum(elast_vals) / len(elast_vals) if elast_vals else None

    kpis = "".join([
        kpi_card("Усього заходів", n_total, "gray"),
        kpi_card("План, млрд грн", f"{plan_sum:.2f}".replace(".", ",") if plan_sum else "—", "blue"),
        kpi_card("Факт, млрд грн", f"{fact_sum:.2f}".replace(".", ",") if fact_sum else "—", "green"),
        kpi_card("% виконання (фін.)",
                 f"{fin_pct_total:.2f}%".replace(".", ",") if fin_pct_total is not None else "—",
                 "yellow"),
        kpi_card("Сер. коеф. еластичності",
                 f"{elast_avg:.2f}".replace(".", ",") if elast_avg is not None else "—",
                 "gray"),
    ])
    st.markdown(
        f'<div class="kpi-grid" style="grid-template-columns:repeat(5,1fr);">{kpis}</div>',
        unsafe_allow_html=True
    )

    if not has_fact:
        st.warning(
            "⚠️ Фактичних бюджетних значень не знайдено. План, КПКВК і стан виконання "
            "вже відображаються (з даних app), але **% виконання** та **К еластичності** "
            "не рахуються без факту. Додайте файл **«БП під моніторинг СП.xlsx»** поряд "
            "із застосунком. Очікувані колонки (довгий формат): `Код заходу`, `Рік`, "
            "`Факт (млрд грн)`; або широкий формат: `Код заходу`, `Факт 2026`, "
            "`Факт 2027`, `Факт 2028`."
        )
    elif not has_plan:
        st.info(
            "ℹ️ Планові бюджетні значення відсутні у Страт_матриці (колонки Z/AA/AB — "
            "«затверджено/прогноз, млрд грн»). Перевірте їх заповнення у джерелі app."
        )

    # ── Фільтри ──
    goals = ["Усі"] + sorted(
        [g for g in df_full["Стратегічна ціль"].unique() if raw_value(g)],
        key=code_sort_key
    )
    fcol = st.columns([3, 2.4, 2.6], gap="medium")
    with fcol[0]:
        query = st.text_input(
            "Пошук", placeholder="🔎 код, назва заходу, КПКВК…",
            key=f"fin_q_{year}", label_visibility="collapsed"
        )
    with fcol[1]:
        only_fin = st.checkbox(
            "Лише з бюджетними даними", value=False, key=f"fin_only_{year}"
        )
    with fcol[2]:
        goal_sel = st.selectbox(
            "Стратегічна ціль", goals, key=f"fin_goal_{year}",
            label_visibility="collapsed"
        )

    df = df_full.copy()
    if query.strip():
        q = query.strip().lower()
        mask = (
            df["Захід"].astype(str).str.lower().str.contains(q, regex=False)
            | df["Назва заходу"].astype(str).str.lower().str.contains(q, regex=False)
            | df["КПКВК"].astype(str).str.lower().str.contains(q, regex=False)
        )
        df = df[mask]
    if only_fin:
        df = df[df["План, млрд грн"].notna() | df["Факт, млрд грн"].notna()]
    if goal_sel and goal_sel != "Усі":
        df = df[df["Стратегічна ціль"] == goal_sel]

    # ── Легенда коефіцієнта еластичності + лічильник ──
    st.markdown(f"""
    <div class="mio-legend">
        <span class="mio-chip done"><span class="dot"></span>Еластичність ≈ 1 (фінансування ∝ результату)</span>
        <span class="mio-chip notyet"><span class="dot"></span>&lt; 0,9 (результат випереджає витрати)</span>
        <span class="mio-chip partial"><span class="dot"></span>1–1,5 (помірний перевитрат)</span>
        <span class="mio-chip notdone"><span class="dot"></span>&gt; 1,5 (витрат значно більше за результат)</span>
        <span style="margin-left:auto;font-size:12px;color:#64748b;font-weight:700;align-self:center;">
            Показано {len(df)} із {n_total}
        </span>
    </div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.info("За обраними фільтрами заходів не знайдено.")
    else:
        st.markdown(_build_financing_table_html(df), unsafe_allow_html=True)

    # ── Експорт ──
    csv = df_full.copy()
    csv["% виконання"] = csv["% виконання"].map(
        lambda v: f"{v:.1f}".replace(".", ",") + "%" if isinstance(v, (int, float)) else ""
    )
    csv["Стан виконання заходу, %"] = csv["Стан виконання заходу, %"].map(
        lambda v: f"{v:.1f}".replace(".", ",") + "%" if isinstance(v, (int, float)) else str(v)
    )
    csv["Коефіцієнт еластичності"] = csv["Коефіцієнт еластичності"].map(
        lambda v: f"{v:.2f}".replace(".", ",") if isinstance(v, (int, float)) else ""
    )
    csv = csv[["Захід", "Назва заходу", "КПКВК", "Інше джерело фінансування",
               "План, млрд грн", "Факт, млрд грн", "% виконання",
               "Стан виконання заходу, %", "Коефіцієнт еластичності"]]
    st.download_button(
        f"⬇️ Завантажити фінансування за {year} рік (CSV)",
        data=csv.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"МіО_Фінансування_{year}.csv",
        mime="text/csv",
        key=f"fin_dl_{year}",
    )


def render_mode_financing(strat_df, monitoring_df, years):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">МіО Фінансування · фінансове виконання заходів</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        "<div style='font-size:13px;color:#475569;margin-bottom:8px;line-height:1.5;'>"
        "До кожного року — бюджетний розріз заходів за методикою аркуша "
        "«МіО Фінансування»: <b>КПКВК</b>, <b>інше джерело фінансування</b>, "
        "<b>План</b> і <b>Факт</b> у млрд грн. "
        "<b>% виконання</b> = Факт ÷ План. "
        "<b>Стан виконання заходу, %</b> — бал виконання заходу за РІК із режиму "
        "«РВ (Заходи)». "
        "<b>Коефіцієнт еластичності</b> = % виконання ÷ Стан виконання заходу "
        "(≈1 — фінансування пропорційне результату). "
        "<b>План</b>, КПКВК та джерело беруться з даних app (Страт_матриця), "
        "<b>Факт</b> — з окремого файлу <b>«БП під моніторинг СП.xlsx»</b>."
        "</div>",
        unsafe_allow_html=True
    )
    fin_index = load_financing_data()
    if len(years) == 1:
        _render_financing_year(strat_df, monitoring_df, fin_index, years[0])
    else:
        ytabs = st.tabs([f"{y} рік" for y in years])
        for tab, y in zip(ytabs, years):
            with tab:
                _render_financing_year(strat_df, monitoring_df, fin_index, y)
    st.markdown('</div>', unsafe_allow_html=True)


_INFOGR_CSS = """
<style>
.infogr-header { background:linear-gradient(135deg,#1c3f63,#15314f); border-bottom:4px solid #d4a017;
  border-radius:10px 10px 0 0; padding:14px 22px; display:flex; justify-content:space-between;
  align-items:center; gap:16px; }
.infogr-header .ih-title { color:#fff; font-size:13px; font-weight:800; line-height:1.45; }
.infogr-header .ih-subtitle { color:#f3c95a; font-size:13px; font-weight:800; white-space:nowrap; }
.infogr-planned-wrap { display:flex; align-items:center; gap:22px; background:#fff;
  border:1px solid #d8dee9; border-top:none; border-radius:0 0 10px 10px; padding:18px 22px; }
.ip-icon { font-size:42px; line-height:1; }
.infogr-planned-label { font-weight:800; color:#0f172a; font-size:13px; white-space:nowrap; }
.ip-bars { flex:2; display:flex; flex-direction:column; gap:7px; min-width:0; }
.ip-row { display:flex; align-items:center; gap:8px; }
.ip-label { width:74px; font-size:11px; font-weight:800; color:#334155; text-align:right; flex-shrink:0; }
.ip-bar { height:28px; border-radius:4px; display:flex; align-items:center; justify-content:flex-end;
  padding-right:12px; color:#fff; font-weight:900; font-size:16px; }
.infogr-stat { text-align:center; flex-shrink:0; min-width:90px; }
.infogr-stat .is-icon { font-size:36px; line-height:1; }
.infogr-stat .is-val { font-size:19px; font-weight:900; color:#0f172a; margin-top:2px; }
.infogr-stat .is-lbl { font-size:10.5px; font-weight:800; color:#475569; letter-spacing:.2px; }
.infogr-year-wrap { text-align:right; flex-shrink:0; }
.infogr-year-wrap .iy-lbl { font-size:11px; font-weight:800; color:#475569; margin-bottom:2px; }
.infogr-donut-title { font-weight:800; font-size:12.5px; color:#0f172a; text-align:center;
  text-transform:uppercase; margin-bottom:2px; }
.infogr-target-mark { text-align:center; font-size:11px; font-weight:800; color:#0f172a;
  border-top:2px solid #0f172a; padding-top:4px; margin-top:46px; }
.infogr-radar-title { font-weight:800; font-size:13px; color:#0f172a; text-transform:uppercase; }
.infogr-radar-sub { font-size:11px; font-weight:800; color:#c2860b; }
.infogr-axis-row { display:flex; align-items:center; gap:8px; margin-bottom:5px; }
.infogr-axis-label { width:42px; font-size:11px; font-weight:800; color:#334155; flex-shrink:0; }
.infogr-axis-pct { width:50px; font-size:11.5px; font-weight:800; flex-shrink:0; }
.infogr-axis-bar-bg { flex:1; height:9px; background:#f1f5f9; border-radius:5px; position:relative; min-width:0; }
.infogr-axis-bar-fill { height:100%; border-radius:5px; }
.infogr-axis-flag { width:54px; font-size:11px; font-weight:700; color:#64748b; flex-shrink:0; }
.infogr-goal-row { display:grid; grid-template-columns:38px 2.3fr 0.7fr 1.1fr 1.3fr 0.9fr;
  align-items:center; gap:8px; padding:9px 10px; border-bottom:1px solid #e2e8f0; }
.infogr-goal-row.head { font-size:10.5px; font-weight:800; color:#64748b; text-transform:uppercase;
  border-bottom:2px solid #0f172a; text-align:center; }
.infogr-goal-row.head .igr-name { text-align:left; }
.infogr-goal-icon { font-size:22px; text-align:center; }
.infogr-goal-name { font-weight:800; font-size:12px; color:#0f172a; }
.infogr-goal-num { text-align:center; font-weight:800; font-size:13.5px; color:#0f172a; }
.infogr-goal-meas-bar { height:7px; border-radius:4px; background:#e2e8f0; margin-top:3px; }
.infogr-goal-meas-fill { height:100%; border-radius:4px; background:#0c5db5; }

/* ── Інфограф_СЦ.З.з ── */
.iz-goaltitle { font-weight:800; font-size:14px; color:#0f172a; text-transform:uppercase;
  padding:10px 4px 4px; }
.iz-kpi-row { display:flex; align-items:center; gap:26px; background:#fff; border:1px solid #d8dee9;
  border-radius:0 0 10px 10px; padding:16px 22px; flex-wrap:wrap; }
.iz-kpi { text-align:center; min-width:90px; }
.iz-kpi .kl { font-size:11px; font-weight:800; color:#475569; }
.iz-kpi .kv { font-size:24px; font-weight:900; color:#0f172a; }
.iz-ind-table { width:100%; border-collapse:collapse; margin-top:8px; font-size:12px; }
.iz-ind-table th { background:#1c3f63; color:#fff; font-size:10.5px; font-weight:800;
  text-transform:uppercase; padding:6px 8px; text-align:center; }
.iz-ind-table th.iz-left { text-align:left; }
.iz-ind-table td { padding:6px 8px; border-bottom:1px solid #e2e8f0; text-align:center; }
.iz-ind-table td.iz-left { text-align:left; font-weight:600; color:#0f172a; }
.iz-task-card { background:#fff; border:1px solid #d8dee9; border-radius:8px; padding:14px;
  margin-bottom:14px; }
.iz-task-title { font-weight:800; font-size:12.5px; color:#1c3f63; text-transform:uppercase; }
.iz-task-name { font-size:11.5px; color:#475569; margin-bottom:8px; }
.iz-task-score-bar { height:18px; border-radius:4px; background:#e2e8f0; position:relative;
  margin-bottom:10px; }
.iz-task-score-fill { height:100%; border-radius:4px; display:flex; align-items:center;
  justify-content:flex-end; padding-right:8px; color:#fff; font-weight:800; font-size:11px; }
.iz-status-row { display:flex; justify-content:space-between; gap:6px; flex-wrap:wrap;
  margin-top:6px; font-size:11px; }
.iz-status-chip { padding:3px 8px; border-radius:12px; font-weight:700; white-space:nowrap; }
</style>
"""


def render_mode_infogr_sc(strat_df, monitoring_df, years):
    """Режим «Інфограф СЦ» — зведена візуалізація прогресу за стратегічними цілями.

    Підв'язаний до всіх попередніх режимів: жодних власних обчислень —
    лише агрегація вже готових даних з build_integral_table (Інтеграл),
    build_rv_measures_table (стан заходів), build_financing_table/
    load_financing_data (фінансування) і load_strat_matrix (ієрархія).
    Дизайн відтворює аркуш «Інфограф_СЦ» еталонної моделі МіО.
    """
    st.markdown(_INFOGR_CSS, unsafe_allow_html=True)

    year_options = [2026, 2027, 2028]
    default_year = years[0] if years else year_options[0]
    sel_idx = year_options.index(default_year) if default_year in year_options else 0

    goals = strat_df[strat_df["object_type"] == "goal"].copy()
    tasks = strat_df[strat_df["object_type"] == "task"].copy()
    measures_all = strat_df[strat_df["object_type"] == "measure"].copy()
    goals["__code"] = goals["code"].map(raw_value)
    tasks["__code"] = tasks["code"].map(raw_value)
    measures_all["__code"] = measures_all["code"].map(raw_value)
    goal_codes_sorted = sorted(goals["__code"].unique(), key=code_sort_key)
    goal_name_by_code = {raw_value(r["code"]): raw_value(r["name"]) for _, r in goals.iterrows()}
    goal_icons = ["🏭", "⚙️", "🛡️", "💡", "👥", "📈", "🌐", "🇪🇺"]

    n_goals = len(goal_codes_sorted)
    n_tasks = tasks["__code"].nunique()

    # ── Шапка (як на еталонному аркуші «Інфограф_СЦ») ──
    st.markdown(
        '<div class="infogr-header">'
        '<div class="ih-title">СТРАТЕГІЧНИЙ ПЛАН ДІЯЛЬНОСТІ МІНІСТЕРСТВА ЕКОНОМІКИ,<br>'
        'ДОВКІЛЛЯ ТА СІЛЬСЬКОГО ГОСПОДАРСТВА УКРАЇНИ НА 2026-2028 РОКИ</div>'
        '<div class="ih-subtitle">ІНФОГРАФІКА СТРАТЕГІЧНИХ ЦІЛЕЙ</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    def _bar_width(value, vmax):
        if vmax <= 0:
            return 25
        return int(25 + 67 * (math.sqrt(value) / math.sqrt(vmax)))

    head_l, head_r = st.columns([6, 1])
    with head_r:
        sel_year = st.selectbox("Рік", year_options, index=sel_idx, key="infogr_sc_year",
                                 label_visibility="collapsed")

    # ── Заходи, «активні» в обраному році — мають ціль/орієнтир (target_{рік})
    # на цей рік. Заходи, що стартують пізніше або вже завершили дію раніше,
    # не входять до підрахунку «Заходів» саме цього року.
    def _target_active(v):
        t = raw_value(v).strip().lower()
        return t not in ("", "х")

    target_col = f"target_{sel_year}"
    active_mask = measures_all[target_col].map(_target_active)
    measures = measures_all[active_mask].copy()
    n_measures = measures["__code"].nunique()
    kpkvk_clean = measures["kpkvk"].map(raw_value)
    n_budget_progs = kpkvk_clean[kpkvk_clean.str.strip() != ""].nunique()

    vmax = max(n_goals, n_tasks, n_measures, 1)

    active_codes = set(measures["__code"])
    fin_index = load_financing_data()
    fin_df = build_financing_table(strat_df, monitoring_df, fin_index, sel_year)
    if not fin_df.empty:
        fin_df = fin_df[fin_df["Захід"].map(raw_value).isin(active_codes)]
    total_plan_bln = fin_df["План, млрд грн"].dropna().sum() if not fin_df.empty else 0.0
    total_fact_bln = fin_df["Факт, млрд грн"].dropna().sum() if not fin_df.empty else 0.0
    budget_mln = total_plan_bln * 1000.0

    with head_l:
        st.markdown(
            '<div class="infogr-planned-wrap">'
            '<div class="ip-icon">📋</div>'
            '<div class="infogr-planned-label">ЗАПЛАНОВАНО:</div>'
            '<div class="ip-bars">'
            f'<div class="ip-row"><span class="ip-label">ЦІЛЕЙ</span>'
            f'<div class="ip-bar" style="width:{_bar_width(n_goals, vmax)}%;background:#aed1e8;">{n_goals}</div></div>'
            f'<div class="ip-row"><span class="ip-label">ЗАВДАННЯ</span>'
            f'<div class="ip-bar" style="width:{_bar_width(n_tasks, vmax)}%;background:#5a93b8;">{n_tasks}</div></div>'
            f'<div class="ip-row"><span class="ip-label">ЗАХОДІВ</span>'
            f'<div class="ip-bar" style="width:{_bar_width(n_measures, vmax)}%;background:#1c3f63;">{n_measures}</div></div>'
            '</div>'
            '<div class="infogr-stat"><div class="is-icon">🗄️</div>'
            f'<div class="is-val">{n_budget_progs}</div><div class="is-lbl">БЮДЖЕТНИХ<br>ПРОГРАМ</div></div>'
            '<div class="infogr-stat"><div class="is-icon">💰</div>'
            f'<div class="is-val">{budget_mln:,.0f} млн грн</div><div class="is-lbl">БЮДЖЕТНІ<br>КОШТИ</div></div>'
            '</div>'.replace(",", " "),
            unsafe_allow_html=True,
        )

    rv_df = build_rv_measures_table(strat_df, monitoring_df, sel_year)
    done_by_goal = {}
    if not rv_df.empty:
        rv_df = rv_df[rv_df["Захід"].map(raw_value).isin(active_codes)].copy()
        rv_df["__goal_code"] = rv_df["Захід"].map(
            lambda c: next((g for g in goal_codes_sorted if raw_value(c).startswith(g)), "")
        )
        for gcode, grp in rv_df.groupby("__goal_code"):
            done_by_goal[gcode] = int((grp["Кінцевий результат"] == "Виконано").sum())

    def _num0(v):
        """0.0 для None/NaN/тексту («х», «в/а») — лише скінченні числа лишаються як є."""
        if isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v)):
            return float(v)
        return 0.0

    def _is_finite_num(v):
        return isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v))

    _, goals_int_df = build_integral_table(strat_df, monitoring_df)
    int_col = f"Інтеграл {sel_year}"
    int_by_goal = {}
    if not goals_int_df.empty and int_col in goals_int_df.columns:
        for _, r in goals_int_df.iterrows():
            int_by_goal[raw_value(r["Код"])] = r[int_col]

    finite_vals = [v for v in int_by_goal.values() if _is_finite_num(v)]
    avg_progress = (sum(finite_vals) / len(finite_vals)) if finite_vals else 0.0
    fin_pct = _num0(total_fact_bln / total_plan_bln * 100.0) if total_plan_bln else 0.0

    # ── Два донати: загальний прогрес і фінансування ──
    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
    col1, col2 = st.columns(2, gap="large")

    def _render_donut(container, title, pct, color):
        with container:
            st.markdown(f'<div class="infogr-donut-title">{title}</div>', unsafe_allow_html=True)
            cA, cB = st.columns([4, 1])
            with cA:
                donut_df = pd.DataFrame({
                    "Статус": ["Виконано", "Залишок"],
                    "Значення": [pct, max(0.0, 100.0 - pct)],
                })
                fig = px.pie(
                    donut_df, names="Статус", values="Значення", color="Статус",
                    color_discrete_map={"Виконано": color, "Залишок": "#dbe6ee"},
                    hole=0.68,
                )
                fig.update_traces(textinfo="none", sort=False)
                fig.add_annotation(text=f"{pct:.2f}%", showarrow=False,
                                    font=dict(size=22, color="#0f172a", family="Inter"))
                fig.update_layout(height=230, margin=dict(l=6, r=6, t=6, b=6),
                                   paper_bgcolor="white", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            with cB:
                st.markdown(
                    '<div class="infogr-target-mark">🎯<br>100%</div>',
                    unsafe_allow_html=True,
                )

    _render_donut(col1, "ЗАГАЛЬНИЙ ПРОГРЕС<br>ВИКОНАННЯ СТРАТПЛАНУ", avg_progress, "#1c3f63")
    _render_donut(col2, "ФІНАНСУВАННЯ<br>ВИКОНАННЯ БЮДЖЕТНИХ ПРОГРАМ", fin_pct, "#16a34a")

    # ── Радар: інтегральна оцінка за два суміжні роки ──
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
    prev_year = sel_year - 1 if (sel_year - 1) in year_options else None
    radar_years = [y for y in [prev_year, sel_year] if y is not None]
    years_label = f"{radar_years[0]}-{radar_years[-1]}" if len(radar_years) > 1 else str(sel_year)
    st.markdown(
        f'<div class="infogr-radar-title">ІНТЕГРАЛЬНА ОЦІНКА '
        f'<span class="infogr-radar-sub">за {years_label} роки</span></div>',
        unsafe_allow_html=True,
    )

    rcol1, rcol2 = st.columns([1.3, 1], gap="large")
    cats = [f"СЦ{i+1}" for i in range(len(goal_codes_sorted))]
    radar_colors = {radar_years[0]: "#9fc4dd"} if len(radar_years) > 1 else {}
    radar_colors[sel_year] = "#1c3f63"

    int_by_goal_year = {}
    for y in radar_years:
        if y == sel_year:
            int_by_goal_year[y] = int_by_goal
        else:
            _, gdf_y = build_integral_table(strat_df, monitoring_df)
            col_y = f"Інтеграл {y}"
            d = {}
            if not gdf_y.empty and col_y in gdf_y.columns:
                for _, r in gdf_y.iterrows():
                    d[raw_value(r["Код"])] = r[col_y]
            int_by_goal_year[y] = d

    with rcol1:
        if cats:
            fig = go.Figure()
            for y in radar_years:
                vals = [_num0(int_by_goal_year[y].get(g)) for g in goal_codes_sorted]
                cats_closed = cats + [cats[0]]
                vals_closed = vals + [vals[0]]
                fig.add_trace(go.Scatterpolar(
                    r=vals_closed, theta=cats_closed, fill="toself",
                    fillcolor=f"rgba(28,63,99,{0.10 if y == sel_year else 0.06})",
                    line=dict(color=radar_colors[y], width=2), name=str(y),
                ))
            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=9),
                                            ticksuffix="%"),
                           angularaxis=dict(tickfont=dict(size=10))),
                height=330, paper_bgcolor="white", margin=dict(l=20, r=20, t=10, b=10),
                legend=dict(orientation="h", font=dict(size=11), x=0.5, xanchor="center", y=1.08),
            )
            st.plotly_chart(fig, use_container_width=True)

    with rcol2:
        st.markdown(
            '<div style="font-size:11px;font-weight:800;color:#c2860b;text-align:right;'
            'margin-bottom:4px;">за звітний рік</div>',
            unsafe_allow_html=True,
        )
        for g, c in zip(goal_codes_sorted, cats):
            v = _num0(int_by_goal.get(g))
            color = "#16a34a" if v >= 80 else "#dc2626"
            st.markdown(
                '<div class="infogr-axis-row">'
                f'<span class="infogr-axis-label">{c.lower()}</span>'
                f'<span class="infogr-axis-pct" style="color:{color};">{v:.2f}%</span>'
                f'<div class="infogr-axis-bar-bg"><div class="infogr-axis-bar-fill" '
                f'style="width:{min(100, v):.2f}%;background:{color};"></div></div>'
                '<span class="infogr-axis-flag">🚩 100%</span>'
                '</div>',
                unsafe_allow_html=True,
            )

    # ── Таблиця стратегічних цілей ──
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-weight:800;font-size:13px;color:#0f172a;'>{sel_year} РІК</div>",
                unsafe_allow_html=True)
    st.markdown(
        '<div class="infogr-goal-row head">'
        '<span></span><span class="igr-name">Стратегічна ціль</span>'
        '<span>Завдань</span><span>Заходів<br>всього</span>'
        '<span>з них<br>виконано</span><span>Бюджетних<br>програм</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    for i, g in enumerate(goal_codes_sorted):
        n_g_tasks = tasks[tasks["__code"].str.startswith(g)]["__code"].nunique()
        n_g_measures = measures[measures["__code"].str.startswith(g)]["__code"].nunique()
        n_g_done = done_by_goal.get(g, 0)
        kpkvk_g = kpkvk_clean[measures["__code"].str.startswith(g)]
        n_g_budget = kpkvk_g[kpkvk_g.str.strip() != ""].nunique()
        done_pct = (n_g_done / n_g_measures * 100.0) if n_g_measures else 0.0
        icon = goal_icons[i % len(goal_icons)]
        st.markdown(
            '<div class="infogr-goal-row">'
            f'<span class="infogr-goal-icon">{icon}</span>'
            f'<span class="infogr-goal-name">{g} {goal_name_by_code.get(g, "").upper()}</span>'
            f'<span class="infogr-goal-num">{n_g_tasks}</span>'
            f'<span class="infogr-goal-num">{n_g_measures}</span>'
            f'<span class="infogr-goal-num">{n_g_done} з {n_g_measures}'
            f'<div class="infogr-goal-meas-bar"><div class="infogr-goal-meas-fill" '
            f'style="width:{done_pct:.0f}%;"></div></div></span>'
            f'<span class="infogr-goal-num">{n_g_budget}</span>'
            '</div>',
            unsafe_allow_html=True,
        )


def render_mode_infogr_sczz(strat_df, monitoring_df, years):
    """Режим «Інфограф_СЦ.З.з» — деталізація стратегічної цілі за завданнями.

    Підв'язаний до тих самих джерел, що й «Інфограф СЦ»: build_mio_goals_tasks_table/
    build_integral_table (показники й інтеграл цілі/завдань), build_rv_measures_table
    (стан виконання заходів), load_strat_matrix (ієрархія). Дизайн відтворює аркуш
    «Інфограф_СЦ.З.з» еталонної моделі МіО — у розрізі завдань обраної стратегічної цілі.
    """
    st.markdown(_INFOGR_CSS, unsafe_allow_html=True)

    year_options = [2026, 2027, 2028]
    default_year = years[0] if years else year_options[0]
    sel_idx = year_options.index(default_year) if default_year in year_options else 0

    goals = strat_df[strat_df["object_type"] == "goal"].copy()
    tasks = strat_df[strat_df["object_type"] == "task"].copy()
    measures_all = strat_df[strat_df["object_type"] == "measure"].copy()
    goals["__code"] = goals["code"].map(raw_value)
    tasks["__code"] = tasks["code"].map(raw_value)
    measures_all["__code"] = measures_all["code"].map(raw_value)
    goal_codes_sorted = sorted(goals["__code"].unique(), key=code_sort_key)
    goal_name_by_code = {raw_value(r["code"]): raw_value(r["name"]) for _, r in goals.iterrows()}

    if not goal_codes_sorted:
        st.info("Немає даних стратегічних цілей.")
        return

    st.markdown(
        '<div class="infogr-header">'
        '<div class="ih-title">СТРАТЕГІЧНИЙ ПЛАН ДІЯЛЬНОСТІ МІНІСТЕРСТВА ЕКОНОМІКИ,<br>'
        'ДОВКІЛЛЯ ТА СІЛЬСЬКОГО ГОСПОДАРСТВА УКРАЇНИ НА 2026-2028 РОКИ</div>'
        '<div class="ih-subtitle">ІНФОРГАФІКА СТРАТЕГІЧНИХ ЗАВДАНЬ</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    head_l, head_m, head_r = st.columns([2.2, 4.4, 1])
    with head_l:
        gsel_idx = st.selectbox(
            "Стратегічна ціль", list(range(len(goal_codes_sorted))), index=0,
            format_func=lambda i: f"Стратегічна ціль {goal_codes_sorted[i].rstrip('.')}",
            key="infogr_sczz_goal", label_visibility="collapsed",
        )
    sel_goal = goal_codes_sorted[gsel_idx]
    with head_m:
        st.markdown(
            f'<div class="iz-goaltitle">{goal_name_by_code.get(sel_goal, "")}</div>',
            unsafe_allow_html=True,
        )
    with head_r:
        sel_year = st.selectbox("Рік", year_options, index=sel_idx, key="infogr_sczz_year",
                                 label_visibility="collapsed")

    def _target_active(v):
        t = raw_value(v).strip().lower()
        return t not in ("", "х")

    target_col = f"target_{sel_year}"
    active_mask = measures_all[target_col].map(_target_active)
    measures_active = measures_all[active_mask].copy()
    g_measures = measures_active[measures_active["__code"].str.startswith(sel_goal)].copy()
    g_tasks = tasks[tasks["__code"].str.startswith(sel_goal)].copy()

    n_measures = g_measures["__code"].nunique()
    depts = g_measures["department"].map(raw_value)
    n_depts = depts[depts.str.strip() != ""].nunique()

    rv_df_goal = build_rv_measures_table(strat_df, monitoring_df, sel_year)
    if not rv_df_goal.empty:
        rv_df_goal = rv_df_goal[rv_df_goal["Захід"].map(raw_value).isin(set(g_measures["__code"]))]

    _, goals_int_df = build_integral_table(strat_df, monitoring_df)
    int_col = f"Інтеграл {sel_year}"
    int_val = None
    if not goals_int_df.empty and int_col in goals_int_df.columns:
        match = goals_int_df[goals_int_df["Код"].map(raw_value) == sel_goal]
        if not match.empty:
            int_val = match.iloc[0][int_col]

    def _num0(v):
        if isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v)):
            return float(v)
        return 0.0

    int_pct = _num0(int_val)

    measures_score_pct = None
    if not rv_df_goal.empty:
        nums = [v for v in rv_df_goal["Бал · РІК"] if isinstance(v, (int, float))]
        if nums:
            measures_score_pct = sum(nums) / len(nums) * 100.0
    measures_score_pct = _num0(measures_score_pct)

    mio_table = build_mio_goals_tasks_table(strat_df, monitoring_df)
    goal_ind_rows = pd.DataFrame()
    if not mio_table.empty:
        goal_ind_rows = mio_table[(mio_table["Рівень"] == "goal")
                                   & (mio_table["Код"].map(raw_value) == sel_goal)]
    ind_scores = []
    if not goal_ind_rows.empty and f"Оцінка {sel_year}" in goal_ind_rows.columns:
        ind_scores = [v for v in goal_ind_rows[f"Оцінка {sel_year}"] if isinstance(v, (int, float))]
    indicators_score_pct = _num0(sum(ind_scores) / len(ind_scores)) if ind_scores else 0.0

    st.markdown(
        '<div class="iz-kpi-row">'
        f'<div class="iz-kpi"><div class="kv">{n_measures}</div><div class="kl">ЗАПЛАНОВАНО<br>ЗАХОДІВ</div></div>'
        f'<div class="iz-kpi"><div class="kv">{n_depts}</div><div class="kl">ЗАЛУЧЕНО<br>СТРУКТУРНИХ ПІДРОЗДІЛІВ</div></div>'
        f'<div class="iz-kpi"><div class="kv">{measures_score_pct:.0f}%</div>'
        '<div class="kl">ЗВЕДЕНА ОЦІНКА<br>ВИКОНАННЯ ЗАХОДІВ</div></div>'
        f'<div class="iz-kpi"><div class="kv">{indicators_score_pct:.0f}%</div>'
        '<div class="kl">ЗВЕДЕНА ОЦІНКА ПРОГРЕСУ<br>ПО ІНДИКАТОРАХ ЦІЛІ</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    gcol1, gcol2 = st.columns([2, 1])
    with gcol1:
        if not goal_ind_rows.empty:
            head = ("<tr><th class='iz-left'>Індикатор</th>"
                    f"<th>Факт {sel_year}</th><th>Оцінка прогресу, %</th><th>Ціль 2028</th></tr>")
            body = ""
            for _, r in goal_ind_rows.iterrows():
                fact_y = r.get(f"Факт {sel_year}", "")
                score_y = r.get(f"Оцінка {sel_year}", "")
                score_str = f"{score_y:.1f}" if isinstance(score_y, (int, float)) else raw_value(score_y)
                body += (f"<tr><td class='iz-left'>{raw_value(r['Індикатор'])}</td>"
                         f"<td>{raw_value(fact_y)}</td><td>{score_str}</td>"
                         f"<td>{raw_value(r['Ціль 2028'])}</td></tr>")
            st.markdown(f"<table class='iz-ind-table'>{head}{body}</table>", unsafe_allow_html=True)
        else:
            st.info("Немає показників цілі.")
    with gcol2:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=int_pct,
            number={"suffix": "%", "font": {"size": 26}},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#1c3f63"},
                "steps": [
                    {"range": [0, 50], "color": "#fca5a5"},
                    {"range": [50, 90], "color": "#fde68a"},
                    {"range": [90, 100], "color": "#86efac"},
                ],
            },
            title={"text": "ІНТЕГРАЛЬНА<br>ОЦІНКА", "font": {"size": 12}},
        ))
        fig.update_layout(height=190, margin=dict(l=18, r=18, t=40, b=4), paper_bgcolor="white")
        st.plotly_chart(fig, use_container_width=True)

    # ── Картки завдань ──
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
    task_codes_sorted = sorted(g_tasks["__code"].unique(), key=code_sort_key)
    task_name_by_code = {raw_value(r["code"]): raw_value(r["name"]) for _, r in g_tasks.iterrows()}

    cols_per_row = 2
    for start in range(0, len(task_codes_sorted), cols_per_row):
        row_codes = task_codes_sorted[start:start + cols_per_row]
        row_cols = st.columns(cols_per_row, gap="large")
        for col, tcode in zip(row_cols, row_codes):
            with col:
                t_measures = g_measures[g_measures["__code"].str.startswith(tcode)].copy()
                t_rv = rv_df_goal[rv_df_goal["Захід"].map(raw_value).isin(set(t_measures["__code"]))] \
                    if not rv_df_goal.empty else pd.DataFrame()

                t_score = None
                if not t_rv.empty:
                    nums = [v for v in t_rv["Бал · РІК"] if isinstance(v, (int, float))]
                    if nums:
                        t_score = sum(nums) / len(nums) * 100.0
                t_score = _num0(t_score)
                t_color = "#16a34a" if t_score >= 80 else ("#f59e0b" if t_score >= 50 else "#dc2626")

                t_ind_rows = pd.DataFrame()
                if not mio_table.empty:
                    t_ind_rows = mio_table[(mio_table["Рівень"] == "task")
                                            & (mio_table["Код"].map(raw_value) == tcode)]

                ind_html = ""
                if not t_ind_rows.empty:
                    for _, r in t_ind_rows.iterrows():
                        fact_y = r.get(f"Факт {sel_year}", "")
                        score_y = r.get(f"Оцінка {sel_year}", "")
                        score_str = f"{score_y:.0f}%" if isinstance(score_y, (int, float)) else raw_value(score_y)
                        ind_html += (
                            '<div style="display:flex;justify-content:space-between;font-size:11px;'
                            'padding:4px 0;border-bottom:1px solid #f1f5f9;">'
                            f'<span style="color:#334155;">{raw_value(r["Індикатор"])}</span>'
                            f'<span style="font-weight:800;color:#0f172a;white-space:nowrap;'
                            f'padding-left:10px;">{raw_value(fact_y)} · {score_str}</span></div>'
                        )

                n_t_measures = t_measures["__code"].nunique()
                st.markdown(
                    '<div class="iz-task-card">'
                    f'<div class="iz-task-title">ЗАВДАННЯ {tcode.rstrip(".")}</div>'
                    f'<div class="iz-task-name">{task_name_by_code.get(tcode, "")} '
                    f'· {n_t_measures} заходів</div>'
                    '<div class="iz-task-score-bar">'
                    f'<div class="iz-task-score-fill" style="width:{min(100, t_score):.0f}%;'
                    f'background:{t_color};">{t_score:.0f}%</div></div>'
                    f'{ind_html}'
                    '</div>',
                    unsafe_allow_html=True,
                )

    # ── Стан виконання заходів по завданнях ──
    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
    for tcode in task_codes_sorted:
        t_measures = g_measures[g_measures["__code"].str.startswith(tcode)].copy()
        n_t_measures = t_measures["__code"].nunique()
        if n_t_measures == 0:
            continue
        t_rv = rv_df_goal[rv_df_goal["Захід"].map(raw_value).isin(set(t_measures["__code"]))] \
            if not rv_df_goal.empty else pd.DataFrame()

        t_score = None
        if not t_rv.empty:
            nums = [v for v in t_rv["Бал · РІК"] if isinstance(v, (int, float))]
            if nums:
                t_score = sum(nums) / len(nums) * 100.0
        t_score = _num0(t_score)

        result_counts = {ST_DONE: 0, ST_PARTIAL: 0, ST_NOTDONE: 0, ST_NOTYET: 0}
        bucket_counts = {">=90%": 0, "50-90%": 0, "<50%": 0, '"в/а"/"х"': 0}
        if not t_rv.empty:
            for _, rr in t_rv.iterrows():
                res = rr["Кінцевий результат"]
                if res in result_counts:
                    result_counts[res] += 1
                bal = rr["Бал · РІК"]
                if isinstance(bal, (int, float)):
                    pct = bal * 100.0
                    if pct >= 90:
                        bucket_counts[">=90%"] += 1
                    elif pct >= 50:
                        bucket_counts["50-90%"] += 1
                    else:
                        bucket_counts["<50%"] += 1
                else:
                    bucket_counts['"в/а"/"х"'] += 1

        st.markdown(
            f"<div style='font-weight:800;font-size:12.5px;color:#1c3f63;margin-top:10px;'>"
            f"СТАН ВИКОНАННЯ ЗАХОДІВ ЗАВДАННЯ {tcode.rstrip('.')}</div>",
            unsafe_allow_html=True,
        )
        scol1, scol2 = st.columns([2, 1.4])
        with scol1:
            st.markdown(
                f"<div style='font-size:12px;color:#334155;margin-bottom:4px;'>"
                f"Заплановано: <b>{n_t_measures}</b> заходів &nbsp;·&nbsp; "
                f"Зведена оцінка виконання заходів: <b>{t_score:.0f}%</b></div>",
                unsafe_allow_html=True,
            )
            chips = "".join(
                f'<span class="iz-status-chip" style="background:#eef2f7;color:#0f172a;">'
                f'{label} {cnt} з {n_t_measures}</span>'
                for label, cnt in result_counts.items()
            )
            st.markdown(f"<div class='iz-status-row'>{chips}</div>", unsafe_allow_html=True)
        with scol2:
            bucket_str = " · ".join(f"{k}: {v}" for k, v in bucket_counts.items())
            st.markdown(
                f"<div style='font-size:11px;color:#475569;'>Розподіл заходів за оцінкою "
                f"виконання:<br>{bucket_str}</div>",
                unsafe_allow_html=True,
            )


def render_mode_placeholder(mode_label):
    sheet_map = {
        MODE_RV_MEAS:  ("РВ (Заходи)", "Розрахунок виконання на рівні заходів."),
        MODE_RV_GOALS: ("РВ (СЦ, Завдання)_РОЗРАХ", "Розрахунок виконання за стратегічними цілями та завданнями."),
        MODE_MIO_GT:   ("МіО_цілі_завдан", "Моніторинг та оцінка індикаторів цілей і завдань."),
        MODE_INTEGRAL: ("Інт_Оцінка", "Інтегральна оцінка (зважена 20/30/50)."),
        MODE_INFOGR_SCZZ: ("Інфограф_СЦ.З.з",
                           "Інфографіка за стратегічними цілями, завданнями та заходами (деталізований розріз)."),
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


# Диспетчер режимів: кожен режим сторінки відповідає аркушу
# методичної моделі Excel і рендериться тут.
if active_mode in MIO_MODES:
    mio_years = _render_year_filter()
    if active_mode == MODE_MZAHODY:
        render_mode_mzahody(strat_df, monitoring_df, mio_years)
    elif active_mode == MODE_RV_MEAS:
        render_mode_rv_meas(strat_df, monitoring_df, mio_years)
    elif active_mode == MODE_RV_GOALS:
        render_mode_rv_goals(strat_df, monitoring_df, mio_years)
    elif active_mode == MODE_MIO_GT:
        render_mode_mio_gt(strat_df, monitoring_df, mio_years)
    elif active_mode == MODE_INTEGRAL:
        render_mode_integral(strat_df, monitoring_df, mio_years)
    elif active_mode == MODE_FINANCING:
        render_mode_financing(strat_df, monitoring_df, mio_years)
    elif active_mode == MODE_INFOGR_SC:
        render_mode_infogr_sc(strat_df, monitoring_df, mio_years)
    elif active_mode == MODE_INFOGR_SCZZ:
        render_mode_infogr_sczz(strat_df, monitoring_df, mio_years)
    else:
        render_mode_placeholder(active_mode)
    st.stop()


render_footer()
