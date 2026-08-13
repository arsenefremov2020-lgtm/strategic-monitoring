from __future__ import annotations

import re
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.roles import (
    ENABLE_PERSONAL_CABINETS,
    ROLE_ADMIN,
    ROLE_SSP,
    ROLE_SSP_DEPUTY,
    ROLE_SSP_HEAD,
    ROLE_SUPER_ADMIN,
    ROLE_UNIT_HEAD,
)
from core import approval_schemes as schemes
from core import dashboard_breakdowns as dashboard_breakdowns_v3
from core import dashboard_periods as dashboard_periods_v3
from core import dashboard_sources as dashboard_sources_v3
from core import monitoring_data, operational
from core.access import filter_actions_for_user, filter_requests_for_user
from core.closeouts import append_confirmed_closeout_facts, load_manual_closeouts
from core.config import FILE_PATH
from core.dashboard_execution import to_number
from core.dashboard_filters import main_ssp_deputy
from core.db import fetch_all
from core.errors import log_cosmetic_error, log_exception
from core.excel_loader import read_excel_sheet
from core.measure_card import build_card_view, quarter_card_view
from core.page_setup import page_setup, render_footer
from core.period_locks import is_period_locked, load_locked_periods
from core.stage4 import (
    build_measure_card_pdf,
    format_kyiv_datetime,
    get_card_target,
    human_versions_table,
    quarter_to_roman,
    render_copy_card_link,
    render_version_comparison,
    style_status_columns,
)
from core.strategic_data import load_strat_matrix as core_load_strat_matrix
from core.timeutils import now_kyiv
from core.ui import render_readonly_table, render_request_timeline, render_scope_toggle
from core.versioning import load_versions


# -----------------------------------------------------------------------------
# Page/access setup. Stage 2 deliberately preserves the existing permissions.
# -----------------------------------------------------------------------------
current_user = page_setup("Картка заходу", page_name="Картка заходу")
card_target = get_card_target()
current_role = current_user.get("role")
can_view_submission_history = (
    not ENABLE_PERSONAL_CABINETS or current_role in [ROLE_ADMIN, ROLE_SUPER_ADMIN]
)
can_submit_monitoring_data = (
    not ENABLE_PERSONAL_CABINETS
    or current_role in [ROLE_SSP, ROLE_SSP_HEAD, ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY]
)


# -----------------------------------------------------------------------------
# Styling: the Card remains a compact single-measure profile. The gauge stays
# the primary analytical visual; the old 35/75 progress zones are intentionally
# absent because analytical colour now comes from the shared v3 state.
# -----------------------------------------------------------------------------
st.markdown(
    """
<style>
header[data-testid="stHeader"] { background: transparent !important; }
.stApp { background: #F7F9FC; }
.main .block-container { max-width: 1550px; padding-top: 1.2rem; }
.ua-line { height:7px; border-radius:999px; background:linear-gradient(90deg,#005BBB 0%,#005BBB 50%,#FFD500 50%,#FFD500 100%); margin-bottom:14px; }
.top-grid { display:grid; grid-template-columns:1.4fr .8fr; gap:16px; margin-bottom:18px; }
.hero-card,.ministry-card,.card { background:rgba(255,255,255,.95); border:1px solid #DCE4F0; border-radius:18px; box-shadow:0 8px 24px rgba(15,23,42,.06); }
.hero-card { padding:26px 30px; }
.ministry-card { padding:22px 24px; background:#F7F9FC; }
.card { padding:20px 22px; margin:18px 0; }
.hero-kicker { font-size:13px; font-weight:800; color:#005BBB; text-transform:uppercase; letter-spacing:.04em; margin-bottom:8px; }
.hero-title { font-size:34px; font-weight:950; color:#132238; line-height:1.15; margin-bottom:10px; }
.hero-subtitle,.card-subtitle,.ministry-line { color:#61708A; line-height:1.55; }
.ministry-title,.card-title { color:#132238; font-weight:900; }
.ministry-title { font-size:16px; margin-bottom:8px; }
.card-title { font-size:20px; margin-bottom:8px; }
.card-subtitle { font-size:14px; margin-bottom:12px; }
.status-pill-wrap,.badge-wrap { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
.status-pill,.badge { border-radius:999px; padding:7px 11px; font-size:13px; font-weight:750; border:1px solid #DCE4F0; color:#61708A; background:#F7F9FC; }
.badge-blue { color:#005BBB; border-color:#BFD3F2; background:#EAF1FF; }
.badge-green { color:#0C713A; border-color:#1E9E57; background:#E4F5EC; }
.badge-yellow { color:#8A6400; border-color:#F4B400; background:#FDF3D8; }
.badge-red { color:#A52525; border-color:#DC4A4A; background:#FBE5E5; }
.filter-panel {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-radius: 18px;
    padding: 18px 20px 10px 20px;
    margin-top: 12px;
    box-shadow: 0 10px 24px rgba(15,23,42,0.07);
}
[data-testid="stMain"] div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stMain"] div[data-testid="stTextInput"] input {
    background-color: #EAF1FF !important;
    border: 1px solid #BFD3F2 !important;
    border-radius: 10px !important;
    min-height: 43px !important;
    box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.08) !important;
}
[data-testid="stMain"] div[data-testid="stSelectbox"] label,
[data-testid="stMain"] div[data-testid="stTextInput"] label {
    font-weight: 750 !important;
    color: #132238 !important;
}
.passport-grid { display:grid; grid-template-columns:repeat(12,minmax(0,1fr)); gap:14px; margin-top:12px; }
.col-2{grid-column:span 2}.col-4{grid-column:span 4}.col-6{grid-column:span 6}.col-8{grid-column:span 8}.col-12{grid-column:span 12}
.passport-cell { background:#F7F9FC; border:1px solid #DCE4F0; border-radius:14px; padding:14px 16px; min-height:86px; overflow-wrap:anywhere; }
.passport-label { color:#61708A; font-size:12px; margin-bottom:6px; text-transform:uppercase; letter-spacing:.03em; font-weight:650; }
.passport-value { color:#132238; font-size:15px; font-weight:800; line-height:1.35; }
.passport-muted { color:#61708A; font-size:13px; line-height:1.45; margin-top:4px; }
.plan-chips { display:flex; gap:10px; flex-wrap:wrap; margin-top:8px; }
.plan-chip { background:#EAF1FF; border:1px solid #BFD3F2; border-radius:12px; padding:8px 14px; min-width:90px; text-align:center; }
.plan-chip-year { font-size:11px; color:#61708A; font-weight:700; }
.plan-chip-val { font-size:18px; font-weight:900; color:#005BBB; }
.finance-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:8px; }
.finance-block,.finance-block-alt,.finance-single { border-radius:12px; padding:12px 14px; }
.finance-block,.finance-single { background:#F7F9FC; border:1px solid #1E9E57; }
.finance-block-alt { background:#FDF3D8; border:1px solid #F4B400; }
.finance-source { font-size:11px; color:#61708A; font-weight:700; text-transform:uppercase; }
.finance-kpkvk { font-size:15px; font-weight:900; color:#0C713A; }
.finance-amount { font-size:12px; color:#61708A; margin-top:4px; }
.notice { border-radius:12px; padding:12px 16px; margin:10px 0; font-weight:650; line-height:1.45; }
.notice-blue { background:#EAF1FF; border:1px solid #BFD3F2; color:#032A63; }
.notice-yellow { background:#FDF3D8; border:1px solid #F4B400; color:#6A5200; }
.notice-purple { background:#F3E8FF; border:1px solid #C4B5FD; color:#5B21B6; }
.quarter-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-top:10px; }
.quarter-card { border-radius:16px; border:2px solid #DCE4F0; padding:16px; background:#fff; min-height:174px; overflow-wrap:anywhere; }
.quarter-title { font-size:16px; font-weight:950; color:#132238; margin-bottom:8px; }
.quarter-value { font-size:23px; font-weight:950; color:#132238; margin-bottom:6px; }
.quarter-line { font-size:12.5px; color:#61708A; line-height:1.45; margin-top:4px; }
.quarter-badge { margin-top:10px; display:inline-block; border-radius:999px; padding:5px 9px; background:#F7F9FC; border:1px solid #DCE4F0; font-size:12px; font-weight:800; color:#39475B; }
div[data-testid="stMetric"] { background:#fff; border:1px solid #DCE4F0; border-radius:14px; padding:14px 16px; }
div[data-testid="stMetricLabel"] p { white-space:normal !important; line-height:1.25 !important; font-size:12px !important; }

/* Локальні великі page-link кнопки лише в основному контенті.
   Sidebar-навігація стилізується виключно в assets/app.css. */
[data-testid="stMain"] div[data-testid="stPageLink"] {
    width: 100% !important;
    display: block !important;
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}
[data-testid="stMain"] div[data-testid="stPageLink"] a {
    width: 100% !important;
    min-height: 86px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: #005BBB !important;
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
[data-testid="stMain"] div[data-testid="stPageLink"] a p {
    color: #ffffff !important;
    font-size: 18px !important;
    font-weight: 950 !important;
    margin: 0 !important;
}
[data-testid="stMain"] div[data-testid="stPageLink"] a svg {
    color: #ffffff !important;
    fill: #ffffff !important;
}
[data-testid="stMain"] div[data-testid="stPageLink"] a:hover {
    filter: brightness(1.05);
    transform: translateY(-1px);
}
@media(max-width:1100px){.top-grid,.quarter-grid,.finance-grid{grid-template-columns:1fr}.col-2,.col-4,.col-6,.col-8{grid-column:span 12}}
</style>
""",
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# Pure UI/passport helpers. No execution/risk/forecast calculations live here.
# -----------------------------------------------------------------------------
def render_html(html: str) -> None:
    st.markdown("\n".join(line.lstrip() for line in str(html).splitlines() if line.strip()), unsafe_allow_html=True)


def clean(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in {"none", "nan", "nat", "null"} else text


def display_value(value, fallback="—") -> str:
    text = clean(value)
    return escape(text) if text else fallback

def _query_param_text(name: str) -> str:
    """Read an explicit URL query value without falling back to session navigation."""
    try:
        value = st.query_params.get(name, "")
    except Exception:
        return ""
    if isinstance(value, list):
        value = value[0] if value else ""
    return clean(value)


def strip_leading_code(text, code) -> str:
    value, code_value = clean(text), clean(code)
    if code_value and value.startswith(code_value):
        value = value[len(code_value):].lstrip(" .—-–|:")
    return value


def get_goal_code(code) -> str:
    parts = clean(code).split(".")
    return parts[0] + "." if parts and parts[0] else ""


def get_task_code(code) -> str:
    parts = clean(code).split(".")
    return f"{parts[0]}.{parts[1]}." if len(parts) >= 2 else ""


def split_first_executor(value) -> str:
    text = clean(value)
    for sep in ["\n", ";", "|", ","]:
        if sep in text:
            return clean(text.split(sep)[0])
    return text


def get_period_label(raw_val) -> str:
    """Format start/end period properly from Excel values."""
    text = clean(raw_val)
    if not text or text.lower() in ["x", "х", "—", "-", ""]:
        return "х"
    if "квартал" in text.lower():
        return text
    num = to_number(text)
    if num is not None:
        val = int(num)
        if 2020 <= val <= 2035:
            return str(val)
        if 1 <= val <= 4:
            return f"{val} квартал"
    return text


def format_amount_bln(value) -> str:
    text = clean(value)
    number = to_number(text)
    return (f"{number:g} млрд грн" if number is not None else (text or "—"))


def looks_like_kpkvk(value) -> bool:
    return bool(re.search(r"\b\d{7}\b", clean(value)))


def extract_kpkvk_code(row) -> str:
    candidates = [row.get("kpkvk_code_raw", "")] + [row.get(c, "") for c in ["finance_y", "finance_z", "finance_aa", "finance_ab", "finance_ac", "finance_ad", "finance_ae", "finance_af"]]
    for value in candidates:
        match = re.search(r"\b\d{7}\b", clean(value))
        if match:
            return match.group(0)
    return ""


def first_money_value(values) -> str:
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


def financing_html(row, kpkvk_reference=None) -> str:
    """Passport-only finance rendering; Stage 2 does not change its methodology."""
    kpkvk_reference = kpkvk_reference or {}
    values = [clean(row.get(c, "")) for c in ["finance_y", "finance_z", "finance_aa", "finance_ab", "finance_ac", "finance_ad", "finance_ae", "finance_af"]]
    kpkvk_code = extract_kpkvk_code(row)
    if not any(values) and not kpkvk_code:
        return '<div class="passport-value">Відсутнє</div>'
    y, z, aa, ab, ac, ad, ae, af = values
    joined = " ".join(values).casefold()
    has_state = bool(kpkvk_code) or (any([y, z, aa, ab, ac]) and ("держ" in joined or "кпквк" in joined or any([z, aa, ab, ac])))
    has_other = any([ad, ae, af]) or "інш" in joined
    if not has_state and not has_other:
        text = "; ".join(v for v in values if v)
        return f'<div class="finance-single"><div class="finance-source">Фінансування</div><div class="finance-kpkvk">{escape(text)}</div></div>'
    blocks = []
    if has_state:
        name = clean(kpkvk_reference.get(kpkvk_code, ""))
        title = f'<div class="finance-amount">{escape(name)}</div>' if name else ""
        amount = format_amount_bln(first_money_value([aa, ab, ac, z, y]))
        blocks.append(f'<div class="finance-block"><div class="finance-source">Державний бюджет</div><div class="finance-kpkvk">КПКВК {escape(kpkvk_code) if kpkvk_code else "—"}</div>{title}<div class="finance-amount">2026: {escape(amount)}</div></div>')
    if has_other:
        source = next((v for v in [ad, y, z] if v and "держ" not in v.casefold() and "кпквк" not in v.casefold() and not looks_like_kpkvk(v)), "Інші джерела")
        amount = format_amount_bln(first_money_value([ae, af, ad]))
        blocks.append(f'<div class="finance-block-alt"><div class="finance-source">Інші джерела</div><div class="finance-kpkvk">{escape(source)}</div><div class="finance-amount">2026: {escape(amount)}</div></div>')
    return f'<div class="finance-grid">{"".join(blocks)}</div>' if len(blocks) > 1 else blocks[0]


def gauge_chart(gauge: dict) -> go.Figure:
    """Neutral gauge background; bar colour comes from Card analytical state."""
    value = gauge.get("value")
    if value is None:
        fig = go.Figure(go.Indicator(
            mode="gauge",
            value=0,
            title={"text": "Виконання річного плану"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "rgba(0,0,0,0)"},
                "bgcolor": "#EEF2F7",
                "borderwidth": 0,
            },
        ))
        fig.add_annotation(text="—", x=.5, y=.43, showarrow=False, font={"size": 34, "color": "#61708A"})
    else:
        safe_value = max(0.0, min(float(value), 100.0))
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=safe_value,
            number={"suffix": "%"},
            title={"text": "Виконання річного плану"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": gauge.get("color", "#005BBB")},
                "bgcolor": "#EEF2F7",
                "borderwidth": 0,
            },
        ))
    fig.update_layout(height=320, margin=dict(l=20, r=20, t=60, b=20), paper_bgcolor="rgba(0,0,0,0)")
    return fig


def load_strat_matrix():
    return core_load_strat_matrix()


@st.cache_data
def load_kpkvk_reference():
    """Load КПКВК code→name reference using the current-main bidirectional lookup."""
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
    data = monitoring_data.measures_only(monitoring_data.load_monitoring_requests())
    if not data.empty and "submitted_at" in data.columns:
        data = data.sort_values("submitted_at", ascending=False)
    return data


def load_request_logs(request_ids) -> pd.DataFrame:
    ids = [int(value) for value in request_ids if clean(value)]
    if not ids:
        return pd.DataFrame()
    return pd.DataFrame(fetch_all("monitoring_logs", "*", filters=lambda query: query.in_("request_id", ids), order=("changed_at", False)))


def _request_period_number(row) -> int | None:
    try:
        return dashboard_periods_v3.period_number(row.get("year"), row.get("quarter"))
    except Exception:
        return None


def _snapshot_row(results, year: int, quarter: str):
    item = results.get((int(year), quarter)) or {}
    snapshot = item.get("snapshot")
    if snapshot is None or snapshot.empty:
        return None
    return snapshot.iloc[0]


# -----------------------------------------------------------------------------
# Header and source data
# -----------------------------------------------------------------------------
render_html('<div class="ua-line"></div>')
render_html(f"""
<div class="top-grid">
  <div class="hero-card">
    <div class="hero-kicker">Паспорт стратегічного заходу</div>
    <div class="hero-title">Картка заходу</div>
    <div class="hero-subtitle">Короткий профіль одного заходу за єдиною методологією розрахунку: річне виконання, актуальність даних, прогнозна траєкторія та ризик.</div>
  </div>
  <div class="ministry-card">
    <div class="ministry-title">Міністерство економіки, довкілля та сільського господарства України</div>
    <div class="ministry-line">Внутрішня система моніторингу стратегічного плану.</div>
    <div class="status-pill-wrap"><div class="status-pill">Картка заходу</div><div class="status-pill">Єдина методологія розрахунку</div><div class="status-pill">Оновлено: {now_kyiv().strftime('%d.%m.%Y %H:%M')}</div></div>
  </div>
</div>
""")

df = load_strat_matrix()
kpkvk_reference = load_kpkvk_reference()
requests_df = load_requests()

goals = df[df["object_type"].astype(str).str.strip().eq("goal")].copy()
tasks = df[df["object_type"].astype(str).str.strip().eq("task")].copy()
measures = df[df["object_type"].astype(str).str.strip().eq("measure")].copy()
all_measures_for_access = measures.copy()

# Preserve current access-control semantics; main-SSP analytics does not redefine permissions.
measures = filter_actions_for_user(measures, current_user, page_key="Картка заходу")
requests_df = filter_requests_for_user(requests_df, current_user, ssp_columns=["department"], page_key="Картка заходу")

_target_code = clean(card_target.get("code"))
if _target_code:
    _exists_anywhere = bool(all_measures_for_access["code"].astype(str).str.strip().eq(_target_code).any())
    _exists_in_scope = bool(measures["code"].astype(str).str.strip().eq(_target_code).any())
    if _exists_anywhere and not _exists_in_scope:
        st.error("У вас немає доступу до картки цього заходу.")
        render_footer(); st.stop()
    if not _exists_anywhere:
        st.warning("Захід із посилання не знайдено. Відкрито доступний перелік заходів.")
        card_target = {"code": "", "year": "", "quarter": ""}

if measures.empty:
    st.warning("Заходів у стратегічній матриці не знайдено.")
    render_footer(); st.stop()

measures["goal_code"] = measures["code"].apply(get_goal_code)
measures["task_code"] = measures["code"].apply(get_task_code)
tasks["goal_code"] = tasks["code"].apply(get_goal_code)


# -----------------------------------------------------------------------------
# Measure selection — same access/path concept as the existing Card.
# -----------------------------------------------------------------------------
render_html('<div class="card"><div class="card-title">Вибір заходу</div><div class="card-subtitle">Оберіть стратегічну ціль, завдання та конкретний захід.</div><div class="filter-panel">')
f1, f2, f3, f4, f5 = st.columns([1.1, 1.1, 1.5, 1.05, 1.05])

goal_options = ["Усі стратегічні цілі"] + [f"{row['code']} — {row['name']}" for _, row in goals.iterrows()]
with f1:
    selected_goal_label = st.selectbox("Стратегічна ціль", goal_options, index=0)
if selected_goal_label == "Усі стратегічні цілі":
    filtered_tasks, filtered_measures = tasks.copy(), measures.copy()
else:
    selected_goal_code = selected_goal_label.split("—")[0].strip()
    filtered_tasks = tasks[tasks["goal_code"] == selected_goal_code].copy()
    filtered_measures = measures[measures["goal_code"] == selected_goal_code].copy()

task_options = ["Усі завдання"] + [f"{row['code']} — {row['name']}" for _, row in filtered_tasks.iterrows()]
with f2:
    selected_task_label = st.selectbox("Завдання", task_options, index=0)
if selected_task_label != "Усі завдання":
    selected_task_code_filter = selected_task_label.split("—")[0].strip()
    filtered_measures = filtered_measures[filtered_measures["task_code"] == selected_task_code_filter].copy()

with f4:
    keyword = st.text_input("За ключовими словами", value="", placeholder="Введіть слово або код")
with f5:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    render_scope_toggle("Картка заходу", current_user)

if clean(keyword):
    kw = clean(keyword).casefold()
    mask = (
        filtered_measures["code"].astype(str).str.casefold().str.contains(kw, na=False)
        | filtered_measures["name"].astype(str).str.casefold().str.contains(kw, na=False)
        | filtered_measures.get("indicator", pd.Series("", index=filtered_measures.index)).astype(str).str.casefold().str.contains(kw, na=False)
        | filtered_measures.get("department", pd.Series("", index=filtered_measures.index)).astype(str).str.casefold().str.contains(kw, na=False)
    )
    filtered_measures = filtered_measures[mask].copy()

if filtered_measures.empty:
    render_html("</div></div>"); st.warning("За обраними фільтрами заходів не знайдено."); render_footer(); st.stop()

measure_options = [f"{row['code']} — {row['name']}" for _, row in filtered_measures.iterrows()]
_target_measure_index = next((idx for idx, label in enumerate(measure_options) if label.split("—")[0].strip() == clean(card_target.get("code"))), 0)
with f3:
    selected_option = st.selectbox("Захід", measure_options, index=_target_measure_index)
render_html("</div></div>")

selected_code = selected_option.split("—")[0].strip()
selected_measure = measures[measures["code"].astype(str).str.strip().eq(selected_code)].iloc[0]
goal_code, task_code = get_goal_code(selected_code), get_task_code(selected_code)
goal_row = df[(df["object_type"].astype(str).eq("goal")) & (df["code"].astype(str).str.strip().eq(goal_code))]
task_row = df[(df["object_type"].astype(str).eq("task")) & (df["code"].astype(str).str.strip().eq(task_code))]
goal_name = strip_leading_code(goal_row.iloc[0]["name"], goal_code) if not goal_row.empty else ""
task_name = strip_leading_code(task_row.iloc[0]["name"], task_code) if not task_row.empty else ""


# -----------------------------------------------------------------------------
# Period assessment. Explicit URL year/quarter wins; otherwise use Dashboard v3
# current_reporting_period rather than a hard-coded historical default.
# -----------------------------------------------------------------------------
locked_periods = load_locked_periods()
default_year, default_quarter = dashboard_periods_v3.current_reporting_period(requests_df, locked_periods=locked_periods)
_link_request_rows = requests_df[requests_df["strat_code"].astype(str).str.strip().eq(selected_code)].copy() if not requests_df.empty and "strat_code" in requests_df.columns else pd.DataFrame()

year_options = {2026, 2027, 2028, int(default_year)}
if not _link_request_rows.empty and "year" in _link_request_rows.columns:
    for value in _link_request_rows["year"].tolist():
        try: year_options.add(int(float(value)))
        except (TypeError, ValueError): pass
url_code = _query_param_text("code")
url_year = _query_param_text("year")
url_quarter = quarter_to_roman(_query_param_text("quarter"))
explicit_url_period = bool(url_code == selected_code and url_year and url_quarter in ["I", "II", "III", "IV"])
try:
    explicit_url_year = int(float(url_year)) if explicit_url_period else None
except (TypeError, ValueError):
    explicit_url_year = None
    explicit_url_period = False

fallback_year = clean(card_target.get("year"))
try:
    selected_default_year = explicit_url_year if explicit_url_period else (int(float(fallback_year)) if fallback_year else int(default_year))
except (TypeError, ValueError):
    selected_default_year = int(default_year)
year_options.add(selected_default_year)
year_options = sorted(year_options)
fallback_quarter = quarter_to_roman(card_target.get("quarter"))
selected_default_quarter = url_quarter if explicit_url_period else (fallback_quarter or default_quarter)
quarter_options = ["I", "II", "III", "IV"]

year_widget_key = f"card_year_{selected_code}"
quarter_widget_key = f"card_quarter_{selected_code}"
if explicit_url_period:
    # Streamlit widget state otherwise wins over a newly opened explicit URL in
    # the same session. Synchronise before widget creation so URL parameters win.
    st.session_state[year_widget_key] = selected_default_year
    st.session_state[quarter_widget_key] = selected_default_quarter

render_html('<div class="card"><div class="card-title">Період оцінки</div><div class="card-subtitle">Рік, квартал і джерело даних визначають аналітичний зріз. Пряме посилання зберігає обраний захід і період.</div>')
p1, p2, p3, p4 = st.columns([.8, .8, 1.6, 1.5])
with p1:
    card_link_year = st.selectbox("Рік", year_options, index=year_options.index(selected_default_year), key=year_widget_key)
with p2:
    card_link_quarter = st.selectbox("Квартал", quarter_options, index=quarter_options.index(selected_default_quarter), key=quarter_widget_key)
with p3:
    card_data_mode = st.radio("Джерело даних", operational.MODE_OPTIONS, horizontal=True, key=f"card_data_source_mode_{selected_code}", help=operational.MODE_HELP)
with p4:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    render_copy_card_link(selected_code, card_link_year, card_link_quarter, key=f"copy_card_{selected_code}_{card_link_year}_{card_link_quarter}")
render_html('</div>')

if explicit_url_period:
    st.info(f"Картку відкрито за прямим посиланням: {card_link_quarter} квартал {card_link_year} року.")


# -----------------------------------------------------------------------------
# Raw/process history and analytical requests are intentionally separate.
# Only the analytical copy gets operational reconstruction and official closeouts.
# -----------------------------------------------------------------------------
raw_measure_requests = _link_request_rows.copy()
request_ids = pd.to_numeric(raw_measure_requests.get("id"), errors="coerce").dropna().astype(int).tolist() if not raw_measure_requests.empty and "id" in raw_measure_requests.columns else []
measure_logs = load_request_logs(request_ids)

_focus_rows = raw_measure_requests.copy()
if not _focus_rows.empty:
    _focus_rows = _focus_rows[
        _focus_rows["year"].astype(str).eq(str(card_link_year))
        & _focus_rows["quarter"].apply(quarter_to_roman).eq(card_link_quarter)
    ]
    if _focus_rows.empty:
        _focus_rows = raw_measure_requests.copy()
    if "submitted_at" in _focus_rows.columns:
        _focus_rows["_submitted"] = pd.to_datetime(_focus_rows["submitted_at"], errors="coerce", utc=True)
        _focus_rows = _focus_rows.sort_values("_submitted", ascending=False)
focused_request = _focus_rows.iloc[0] if not _focus_rows.empty else None
try: focused_request_id = int(float(clean(focused_request.get("id")))) if focused_request is not None and clean(focused_request.get("id")) else None
except (TypeError, ValueError): focused_request_id = None
focused_versions = load_versions(focused_request_id) if focused_request_id is not None else pd.DataFrame()

analytical_requests = raw_measure_requests.copy()
operational_extension_used = False
if card_data_mode == operational.MODE_OPERATIONAL and not analytical_requests.empty:
    target_map = {(selected_code, str(year)): clean(selected_measure.get(f"target_{year}", "")) for year in year_options}
    analytical_requests, _legacy_auto_list = operational.apply_operational_mode(analytical_requests, target_map)
    operational_extension_used = bool(analytical_requests.get("_operational", pd.Series(False, index=analytical_requests.index)).fillna(False).astype(bool).any())

# Official closeouts are analytical facts; they do not alter raw submission history.
analytical_requests = append_confirmed_closeout_facts(analytical_requests, include_incomplete=True)
_card_closeouts = load_manual_closeouts()
card_closed_periods = sorted(
    f"{q} кв. {y}" for (code, y, q) in _card_closeouts
    if code == selected_code and not is_period_locked(y, q, locked_periods)
)

if operational_extension_used:
    render_html('<div class="notice notice-blue"><b>Оперативна оцінка:</b> використано версію подання, яка підтверджено пройшла координатора. Подані фактичні значення та статус виконання не змінюються автоматично.</div>')
if card_closed_periods:
    render_html(f'<div class="notice notice-purple"><b>Підтверджене ручне закриття.</b> Для аналітичної оцінки використовується зафіксований у рішенні фактичний результат; система не підміняє його автоматичним статусом. Періоди: {escape(", ".join(card_closed_periods))}. Підстава та НПА залишаються в «Адмініструванні».</div>')


# -----------------------------------------------------------------------------
# One canonical shared v3 calculation path for the selected measure.
# -----------------------------------------------------------------------------
analysis_measure = selected_measure.to_dict()
analysis_measure.update({
    "object_type": "measure",
    "code": selected_code,
    "resp_main": clean(selected_measure.get("resp_main")) or clean(selected_measure.get("department")),
    "measure_start_date": selected_measure.get("measure_start_date", selected_measure.get("start_period", "")),
    "measure_end_date": selected_measure.get("measure_end_date", selected_measure.get("end_period", "")),
    "parent_goal_code": goal_code,
    "parent_goal_name": goal_name,
    "parent_task_code": task_code,
    "parent_task_name": task_name,
})
analysis_strat = pd.DataFrame([analysis_measure])

start_num = dashboard_periods_v3.parse_measure_period(analysis_measure.get("measure_start_date"), end=False)
end_num = dashboard_periods_v3.parse_measure_period(analysis_measure.get("measure_end_date"), end=True)
selected_period_num = dashboard_periods_v3.period_number(card_link_year, card_link_quarter)
selected_period_state = dashboard_periods_v3.period_state(start_num, end_num, selected_period_num)
selected_is_future = selected_period_state == "future"
selected_q_index = quarter_options.index(card_link_quarter)
analysis_pairs = [(int(card_link_year), q) for q in quarter_options[: selected_q_index + 1]]
period_sources = dashboard_sources_v3.build_period_source_overrides(
    analysis_pairs,
    operational_mode=card_data_mode == operational.MODE_OPERATIONAL,
    measure_codes=[selected_code],
)
period_results = dashboard_breakdowns_v3.build_period_results(
    analysis_strat,
    analytical_requests,
    analysis_pairs,
    locked_periods=locked_periods,
    period_sources=period_sources,
)
selected_row = None if selected_is_future else _snapshot_row(period_results, card_link_year, card_link_quarter)

if selected_is_future:
    selected_view_source = {
        "year": int(card_link_year), "quarter": card_link_quarter,
        "annual_target": selected_measure.get(f"target_{card_link_year}", ""),
        "period_state": "future", "monitoring_conducted": True,
    }
    card_view = build_card_view(selected_view_source, future=True)
else:
    selected_view_source = selected_row.to_dict() if selected_row is not None else None
    card_view = build_card_view(selected_view_source)


# -----------------------------------------------------------------------------
# Passport. Deputy is derived from the same main-SSP helper as Dashboard v3;
# coexecutor remains passport information only.
# -----------------------------------------------------------------------------
deputy_minister = main_ssp_deputy(analysis_measure)
co_executor_first = split_first_executor(selected_measure.get("co_executor", selected_measure.get("resp_co_1", "")))
start_period_display = get_period_label(selected_measure.get("measure_start_date", selected_measure.get("start_period", "")))
end_period_display = get_period_label(selected_measure.get("measure_end_date", selected_measure.get("end_period", "")))

plan_chips = []
for y in [2026, 2027, 2028]:
    target = clean(selected_measure.get(f"target_{y}", ""))
    if target and not (y == 2028 and target.casefold() in {"x", "х"}):
        plan_chips.append(f'<div class="plan-chip"><div class="plan-chip-year">{y}</div><div class="plan-chip-val">{escape(target)}</div></div>')

render_html(f"""
<div class="card"><div class="card-title">Паспорт заходу</div>
<div class="badge-wrap"><div class="badge badge-blue">Код: {display_value(selected_code)}</div><div class="badge">Головний ССП: {display_value(selected_measure.get('department',''))}</div></div>
<div style="font-size:24px;font-weight:900;color:#132238;line-height:1.25;margin:12px 0 16px;">{display_value(selected_measure.get('name',''))}</div>
<div class="passport-grid">
  <div class="passport-cell col-4"><div class="passport-label">Стратегічна ціль</div><div class="passport-value">{display_value(goal_code)}</div><div class="passport-muted">{display_value(goal_name)}</div></div>
  <div class="passport-cell col-4"><div class="passport-label">Завдання</div><div class="passport-value">{display_value(task_code)}</div><div class="passport-muted">{display_value(task_name)}</div></div>
  <div class="passport-cell col-4"><div class="passport-label">Головний виконавець</div><div class="passport-value">{display_value(selected_measure.get('department',''))}</div><div class="passport-muted">Співвиконавець: {display_value(co_executor_first)}</div></div>
  <div class="passport-cell col-4"><div class="passport-label">Заступник Міністра</div><div class="passport-value">{display_value(deputy_minister)}</div></div>
  <div class="passport-cell col-2"><div class="passport-label">Тип продукту</div><div class="passport-value">{display_value(selected_measure.get('product_type',''))}</div></div>
  <div class="passport-cell col-2"><div class="passport-label">Одиниця виміру</div><div class="passport-value">{display_value(selected_measure.get('unit',''))}</div></div>
  <div class="passport-cell col-2"><div class="passport-label">Початок</div><div class="passport-value">{escape(start_period_display)}</div></div>
  <div class="passport-cell col-2"><div class="passport-label">Кінець</div><div class="passport-value">{escape(end_period_display)}</div></div>
  <div class="passport-cell col-8"><div class="passport-label">Індикатор</div><div class="passport-value">{display_value(selected_measure.get('indicator',''))}</div></div>
  <div class="passport-cell col-4"><div class="passport-label">Планові показники</div><div class="plan-chips">{''.join(plan_chips) or '—'}</div></div>
  <div class="passport-cell col-12"><div class="passport-label">Фінансування</div>{financing_html(selected_measure, kpkvk_reference)}</div>
</div></div>
""")


# -----------------------------------------------------------------------------
# Compact analytical headline. Process counters are deliberately not headline
# metrics; they stay with raw history below.
# -----------------------------------------------------------------------------
kpis = card_view["headline_kpis"]
metric_cols = st.columns(len(kpis)) if kpis else []
for col, item in zip(metric_cols, kpis):
    col.metric(item["label"], item["value"])

if card_view.get("warning"):
    render_html(f'<div class="notice notice-yellow">{escape(card_view["warning"])}</div>')

if selected_row is not None:
    reporting_status = clean(selected_row.get("status")) or "—"
    effective_status = clean(selected_row.get("effective_result_status")) or "—"
    if reporting_status != effective_status:
        render_html(f'<div class="badge-wrap"><div class="badge badge-yellow">Поточний статус звітності: {escape(reporting_status)}</div><div class="badge badge-blue">Статус результату-джерела: {escape(effective_status)}</div></div>')

render_html('<div class="card"><div class="card-title">Аналітичний висновок</div>')
render_html(f'<div style="color:#39475B;font-size:14px;line-height:1.6;">{escape(card_view["conclusion"])}</div>')
render_html('</div>')


# -----------------------------------------------------------------------------
# Analytical views. Gauge remains primary visual, sourced directly from shared
# execution_score. Quarterly cards use shared snapshots; raw rows never drive
# analytical quarter dynamics.
# -----------------------------------------------------------------------------
view_mode_options = ["Огляд", "Індикатор прогресу", "Квартальна динаміка"]
if can_view_submission_history:
    view_mode_options.append("Історія подання відомостей")
view_mode = st.selectbox("Тип візуалізації", view_mode_options)

if view_mode in ["Огляд", "Індикатор прогресу"]:
    render_html('<div class="card"><div class="card-title">Виконання річного плану</div><div class="card-subtitle">Значення та колір індикатора відповідають аналітичному зрізу за обраним періодом. Перевиконання відображається окремо, а gauge обмежений 100%.</div>')
    gc1, gc2 = st.columns([1, 1])
    with gc1:
        st.plotly_chart(gauge_chart(card_view["gauge"]), use_container_width=True)
    with gc2:
        gauge = card_view["gauge"]
        render_html(f'<div class="badge-wrap"><div class="badge" style="border-color:{gauge["color"]};color:{gauge["color"]}">{escape(gauge["label"])}</div></div>')
        if selected_row is not None:
            raw = to_number(selected_row.get("raw_attainment_pct"))
            execution = to_number(selected_row.get("execution_score"))
            if raw is not None:
                st.write(f"Фактичне досягнення: **{raw:.1f}%**")
            st.write("Виконання для оцінки: **—**" if execution is None else f"Виконання для оцінки: **{min(execution,100):.1f}%**")
            if execution is not None:
                st.progress(max(0.0, min(execution / 100.0, 1.0)), text=f"Виконання річного плану: {execution:.1f}%")
        else:
            st.write("Оцінка виконання для обраного періоду не формується.")
    render_html('</div>')

if view_mode in ["Огляд", "Квартальна динаміка"]:
    render_html('<div class="card"><div class="card-title">Квартальна динаміка</div><div class="card-subtitle">Квартальні картки побудовано за єдиною методологією розрахунку. Майбутні квартали відносно обраного зрізу не використовують фактичні подання.</div>')
    cards = []
    actual_points = []
    for idx, q in enumerate(quarter_options):
        if idx > selected_q_index:
            q_view = quarter_card_view(None, quarter=q, future_relative=True)
        else:
            q_period_num = dashboard_periods_v3.period_number(card_link_year, q)
            q_state = dashboard_periods_v3.period_state(start_num, end_num, q_period_num)
            if q_state == "future":
                q_view = quarter_card_view(None, quarter=q, future_measure=True)
            else:
                q_row = _snapshot_row(period_results, card_link_year, q)
                q_view = quarter_card_view(q_row.to_dict() if q_row is not None else None, quarter=q)
        cards.append(q_view)
        actual_points.append(q_view.get("actual_observation"))

    html = ['<div class="quarter-grid">']
    for item in cards:
        lines = "".join(f'<div class="quarter-line">{escape(str(line))}</div>' for line in item.get("lines", []))
        html.append(f'<div class="quarter-card" style="border-color:{item["color"]}"><div class="quarter-title">{item["quarter"]} квартал</div><div class="quarter-value">{escape(str(item["value"]))}</div>{lines}<div class="quarter-badge">{escape(str(item["badge"]))}</div></div>')
    html.append('</div>')
    render_html("".join(html))

    # One compact numeric chart only when shared snapshots contain real numeric observations.
    if any(point is not None for point in actual_points):
        plan_num = to_number(selected_measure.get(f"target_{card_link_year}", ""))
        fig = go.Figure()
        if plan_num is not None:
            fig.add_trace(go.Scatter(x=[f"{q} кв." for q in quarter_options], y=[plan_num] * 4, mode="lines", name=f"Річний план {card_link_year}", line=dict(width=2, dash="dash"), connectgaps=False))
        fig.add_trace(go.Scatter(x=[f"{q} кв." for q in quarter_options], y=actual_points, mode="lines+markers", name="Фактичне спостереження", line=dict(width=3), connectgaps=False))
        fig.update_layout(title="Фактична динаміка та річний план", height=340, margin=dict(l=20,r=20,t=55,b=30), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", yaxis=dict(gridcolor="#DCE4F0", rangemode="tozero"), xaxis=dict(showgrid=False), legend=dict(orientation="h", y=-.22))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("Числовий line chart не застосовується: у доступному зрізі немає реальних current-quarter numeric observations.")
    render_html('</div>')


# -----------------------------------------------------------------------------
# Raw process/history section: unchanged analytical separation. It intentionally
# uses real user submissions, not synthetic closeout/operational analytical rows.
# -----------------------------------------------------------------------------
if can_view_submission_history and view_mode in ["Огляд", "Історія подання відомостей"]:
    render_html('<div class="card"><div class="card-title">Історія подання відомостей</div><div class="card-subtitle">Процесна історія реальних monitoring submissions. Вона не є джерелом квартальної аналітичної динаміки Card.</div>')

    selected_period = dashboard_periods_v3.period_number(card_link_year, card_link_quarter)
    process_rows = raw_measure_requests.copy()
    if not process_rows.empty:
        process_rows["_period"] = process_rows.apply(_request_period_number, axis=1)
        process_rows = process_rows[pd.to_numeric(process_rows["_period"], errors="coerce").le(selected_period)].copy()
    approved_count = int(process_rows.get("approval_status", pd.Series("", index=process_rows.index)).map(schemes.is_approved).sum()) if not process_rows.empty else 0
    waiting_count = int(process_rows.get("approval_status", pd.Series("", index=process_rows.index)).map(schemes.is_waiting).sum()) if not process_rows.empty else 0
    returned_count = int(process_rows.get("approval_status", pd.Series("", index=process_rows.index)).map(schemes.is_returned).sum()) if not process_rows.empty else 0
    render_html(f'<div class="badge-wrap"><div class="badge badge-green">Погоджено: {approved_count}</div><div class="badge badge-yellow">Очікує: {waiting_count}</div><div class="badge badge-red">Повернено: {returned_count}</div></div>')

    if raw_measure_requests.empty:
        st.info("Для цього заходу ще немає поданих відомостей.")
    else:
        history = raw_measure_requests.copy()
        history["Рік"] = history.get("year", "").apply(lambda v: clean(v) or "—")
        history["Квартал"] = history.get("quarter", "").apply(lambda v: quarter_to_roman(v) or "—")
        history["Статус виконання"] = history.get("status", "").apply(lambda v: clean(v) or "—")
        history["Статус погодження"] = history.get("approval_status", "").apply(lambda v: clean(v) or "—")
        numeric = history.get("numeric_value", pd.Series("", index=history.index)).apply(clean)
        textual = history.get("value_text", pd.Series("", index=history.index)).apply(clean)
        history["Фактичне значення"] = [n or t or "—" for n, t in zip(numeric, textual)]
        history["Відповідальна особа"] = history.get("responsible_person", pd.Series("", index=history.index)).apply(lambda v: clean(v) or "—")
        history["Дата подання"] = history.get("submitted_at", pd.Series("", index=history.index)).apply(format_kyiv_datetime)
        history["Коментар"] = history.get("admin_comment", pd.Series("", index=history.index)).apply(lambda v: clean(v) or "—")
        human_history = history[["Рік", "Квартал", "Статус виконання", "Статус погодження", "Фактичне значення", "Відповідальна особа", "Дата подання", "Коментар"]]
        render_readonly_table(style_status_columns(human_history, ["Статус виконання", "Статус погодження"]))
        if not measure_logs.empty:
            with st.expander("Історія погодження заходу"):
                render_request_timeline(measure_logs)
        if focused_request_id is not None:
            st.markdown(f"**Версії заявки за періодом:** ID {focused_request_id} · {card_link_quarter} квартал {card_link_year} року")
            if focused_versions.empty:
                st.info("Для цієї заявки збережених версій поки що немає.")
            else:
                render_readonly_table(style_status_columns(human_versions_table(focused_versions), ["Статус виконання", "Статус погодження"]))
                with st.expander("Порівняти дві версії заявки", expanded=False):
                    render_version_comparison(focused_versions, key_prefix=f"card_versions_{focused_request_id}")
    render_html('</div>')


# -----------------------------------------------------------------------------
# Existing PDF implementation is deliberately untouched in Stage 2.
# -----------------------------------------------------------------------------
render_html('<div class="card"><div class="card-title">Друк картки заходу <span style="font-size:11px;color:#8A6400;background:#FDF3D8;border:1px solid #F4B400;border-radius:999px;padding:3px 8px;">тест</span></div><div class="card-subtitle">PDF залишається на чинній реалізації; його адаптація — окремий етап.</div>')
try:
    _card_pdf = build_measure_card_pdf(
        measure=selected_measure.to_dict(),
        goal_name=goal_name,
        task_name=task_name,
        requests_df=raw_measure_requests,
        logs_df=measure_logs,
        focus_year=card_link_year,
        focus_quarter=card_link_quarter,
        closed_periods=card_closed_periods,
    )
    st.download_button("Завантажити картку в PDF · тест", data=_card_pdf, file_name=f"картка_заходу_{selected_code}_{card_link_year}_{card_link_quarter}.pdf", mime="application/pdf", use_container_width=True, key=f"download_card_pdf_{selected_code}_{card_link_year}_{card_link_quarter}")
except Exception as exc:
    log_exception("build_measure_card_pdf", exc)
    st.error("Не вдалося сформувати PDF картки. Причину записано в технічний лог.")
render_html('</div>')


# -----------------------------------------------------------------------------
# Existing navigation/actions.
# -----------------------------------------------------------------------------
render_html('<div class="card"><div class="card-title">Швидкі переходи</div>')
if can_submit_monitoring_data:
    n1, _, n2 = st.columns([1, 1.5, 1], gap="large")
    with n1:
        st.page_link("pages/1_Моніторинг_виконання.py", label="Подати відомості", icon="🖊️")
    with n2:
        st.page_link("pages/2_Dashboard.py", label="Dashboard", icon="📊")
else:
    _, n2, _ = st.columns([1, 1, 1], gap="large")
    with n2:
        st.page_link("pages/2_Dashboard.py", label="Dashboard", icon="📊")
render_html('</div>')
render_footer()
