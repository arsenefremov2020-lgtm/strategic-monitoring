import streamlit as st
import pandas as pd
from core.db import get_supabase_client
from core.ui import load_css, render_request_timeline
from core.errors import log_exception
from core.notifications import render_notifications_panel
from core.config import FILE_PATH, SHEET_NAME
from core.excel_loader import read_excel_sheet
from datetime import datetime, timezone
from html import escape
import re
from core.page_setup import page_setup, render_footer
from core.strategic_data import load_strat_matrix as core_load_strat_matrix
from core import monitoring_data
from core.statuses import SUBMISSION_STATUS_OPTIONS
from core.versioning import save_request_version, coordinator_stage_index

from core.access import (
    filter_requests_for_user,
    get_available_ssp_options_for_user,
    should_lock_ssp_fields,
    user_has_all_ssp_access,
)
from core import approval_schemes as schemes
from core import notify_events
from config.roles import ROLE_SSP_HEAD, ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY

current_user = page_setup("Мій кабінет", page_name="Мій кабінет")
supabase = get_supabase_client()
# ============================================================
# STYLE
# ============================================================

st.markdown("""
<style>
header[data-testid="stHeader"] {
    background: transparent !important;
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
.ministry-label {
    text-align: right;
    color: #475569;
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 8px;
}
.header-box, .card {
    background: rgba(255,255,255,0.94);
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 18px;
    box-shadow: 0 8px 24px rgba(15,23,42,0.06);
}
.header-title {
    font-size: 32px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 8px;
}
.header-subtitle, .card-subtitle {
    font-size: 15px;
    color: #475569;
    line-height: 1.55;
}
.card-title {
    font-size: 21px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 8px;
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
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    background-color: #d7eaff !important;
    border: 1px solid #8fb3df !important;
    border-radius: 10px !important;
    box-shadow: inset 0 1px 2px rgba(15,23,42,0.08) !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stTextInput"] input {
    min-height: 43px !important;
}
div[data-testid="stSelectbox"] label,
div[data-testid="stTextInput"] label,
div[data-testid="stTextArea"] label {
    font-weight: 750 !important;
    color: #1e293b !important;
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
.badge-green { background: #dcfce7; border: 1px solid #bbf7d0; color: #166534; }
.badge-yellow { background: #fef9c3; border: 1px solid #fde68a; color: #854d0e; }
.badge-red { background: #fee2e2; border: 1px solid #fecaca; color: #991b1b; }
.badge-gray { background: #f1f5f9; border: 1px solid #cbd5e1; color: #475569; }
.badge-blue { background: #dbeafe; border: 1px solid #93c5fd; color: #1e40af; }
.badge-purple { background: #f3e8ff; border: 1px solid #d8b4fe; color: #6b21a8; }

.info-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    margin-top: 14px;
}
.info-card {
    border-radius: 14px;
    padding: 16px 18px;
    min-height: 105px;
    border: 1px solid #d8dee9;
    overflow-wrap: anywhere;
}
.info-card-blue { background: #eef6ff; border-color: #bfdbfe; }
.info-card-green { background: #dcfce7; border-color: #bbf7d0; }
.info-card-yellow { background: #fef9c3; border-color: #fde68a; }
.info-card-red { background: #fee2e2; border-color: #fecaca; }
.info-card-gray { background: #f8fafc; border-color: #cbd5e1; }
.info-label {
    color: #64748b;
    font-size: 12px;
    margin-bottom: 7px;
    line-height: 1.35;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    font-weight: 750;
}
.info-value {
    color: #0f172a;
    font-weight: 900;
    font-size: 15px;
    line-height: 1.4;
}
.step-box {
    background: #eef6ff;
    border: 1px solid #bfdbfe;
    border-radius: 14px;
    padding: 14px 16px;
    margin: 10px 0;
}
.comment-box {
    background: linear-gradient(135deg, #fff7ed, #fef3c7);
    border: 1px solid #f59e0b;
    color: #78350f;
    border-radius: 16px;
    padding: 18px 20px;
    margin: 18px 0 6px 0;
    box-shadow: 0 8px 20px rgba(245,158,11,0.12);
}
.comment-title {
    font-size: 14px;
    font-weight: 950;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    margin-bottom: 8px;
}
.comment-text {
    font-size: 15px;
    line-height: 1.6;
    font-weight: 750;
}

/* ── Таб підтвердження ── */
.sign-panel {
    background: linear-gradient(135deg, #f0fdf4, #dcfce7);
    border: 2px solid #16a34a;
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 14px;
}
.sign-panel-title {
    font-size: 18px;
    font-weight: 900;
    color: #14532d;
    margin-bottom: 6px;
}
.sign-panel-sub {
    font-size: 14px;
    color: #166534;
    margin-bottom: 16px;
}
/* Кнопка підтвердити — зелена */
div[data-testid="stButton"].sign-btn > button {
    background: linear-gradient(135deg, #16a34a, #15803d) !important;
    color: #fff !important;
    border: none !important;
    font-size: 16px !important;
    padding: 14px 22px !important;
}
div[data-testid="stButton"].return-ssp-btn > button {
    background: linear-gradient(135deg, #fef9c3, #fde68a) !important;
    color: #854d0e !important;
    border: 1px solid #fbbf24 !important;
}
div[data-testid="stButton"].return-coord-btn > button {
    background: linear-gradient(135deg, #fee2e2, #fecaca) !important;
    color: #991b1b !important;
    border: 1px solid #fca5a5 !important;
}

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.9);
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

div.stButton > button {
    border-radius: 14px;
    padding: 12px 18px;
    font-weight: 900;
    border: 1px solid #bfdbfe;
    background: linear-gradient(135deg, #eff6ff, #e0f2fe) !important;
    color: #1d4ed8 !important;
    box-shadow: 0 8px 18px rgba(37,99,235,0.10);
}
div.stButton > button:hover {
    filter: brightness(1.03);
    transform: translateY(-1px);
    border-color: #93c5fd;
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
    .info-grid { grid-template-columns: 1fr; }
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# HELPERS
# ============================================================

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


def has_value(value):
    return clean(value).strip() != ""


def display_text(value, fallback="—"):
    text = clean(value)
    return escape(text) if text else fallback


def status_badge_class(status):
    status = clean(status)
    if status == "Погоджено":
        return "badge-green"
    if status == "Повернуто на доопрацювання":
        return "badge-red"
    if status == "Очікує: Керівник ССП":
        return "badge-purple"
    if status == "Очікує: Керівник управління":
        return "badge-blue"
    if status == "Очікує: Заступник керівника ССП":
        return "badge-blue"
    if status == "Очікує погодження":
        return "badge-yellow"
    return "badge-gray"


APPROVAL_FILTER_OPTIONS = [
    "Активні до розгляду",
    "Усі",
    "Очікує погодження",
    "Очікує: Керівник управління",
    "Очікує: Заступник керівника ССП",
    "Очікує: Керівник ССП",
    "Повернуто на доопрацювання",
    "Погоджено",
]


# ============================================================
# DATA LOADING
# ============================================================

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
    response = (
        supabase
        .table("monitoring_logs")
        .select("*")
        .eq("request_id", int(request_id))
        .order("changed_at", desc=True)
        .execute()
    )
    return pd.DataFrame(response.data or [])



def _actor_identity(role_label):
    """Повний підпис дії для журналу: роль + ПІБ + email поточного користувача."""
    try:
        name = str((current_user or {}).get("full_name", "")).strip()
        email = str((current_user or {}).get("email", "")).strip()
    except Exception:
        name, email = "", ""
    parts = [p for p in (role_label, name, f"<{email}>" if email else "") if p]
    return " · ".join(parts) if parts else role_label

def write_log(request_id, action, old_status, new_status, comment, changed_by="Керівник ССП"):
    supabase.table("monitoring_logs").insert({
        "request_id": int(request_id),
        "action": action,
        "old_status": old_status,
        "new_status": new_status,
        "admin_comment": comment,
        # Аудит: роль ланки + конкретний користувач
        "changed_by": _actor_identity(changed_by)
    }).execute()



# ============================================================
# MAIN DATA
# ============================================================

_refresh_col1, _refresh_col2 = st.columns([4, 1])
with _refresh_col2:
    if st.button("🔄 Оновити зараз", use_container_width=True, key="cabinet_refresh"):
        monitoring_data.invalidate_monitoring_cache()
        st.rerun()
with _refresh_col1:
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    _kyiv_now = _dt.now(_tz(_td(hours=3)))
    st.caption(
        f"🕓 Дані оновлено о {_kyiv_now.strftime('%H:%M:%S')} (Київ). "
        "Список оновлюється автоматично; кнопкою можна оновити миттєво."
    )

df = load_requests()
strat_df = load_strat_matrix()

required_cols = [
    "id", "year", "quarter", "department", "responsible_person", "phone", "email",
    "strat_code", "status", "progress_text", "numeric_value", "risks",
    "submitted_at", "approval_status", "admin_comment", "file_names", "file_urls",
    "start_date", "end_date"
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
    st.warning("Для цього користувача немає доступних відомостей за закріпленим ССП.")
    st.stop()

st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)
st.markdown("""
<div class="ministry-label">
🇺🇦 Міністерство економіки, довкілля та сільського господарства України
</div>
""", unsafe_allow_html=True)

role_label = current_user.get("role_label") or "Керівник ССП"

st.markdown(f"""
<div class="header-box">
    <div class="header-title">Мій кабінет</div>
    <div class="header-subtitle">
        Кабінет погодження вашого самостійного структурного підрозділу. Тут відображаються
        заявки вашого ССП; коли заявка перебуває на вашій ланці схеми погодження — доступні
        дії: погодити та передати далі або повернути на доопрацювання (подавачу чи на
        будь-яку попередню ланку).
    </div>
    <div class="badge-wrap">
        <div class="badge badge-purple">● Роль: {role_label}</div>
        <div class="badge">● Дія: погодження / повернення</div>
    </div>
</div>
""", unsafe_allow_html=True)

render_notifications_panel(df, mode="cabinet")

# ============================================================
# FILTERS
# ============================================================

st.markdown(
    '<div class="card"><div class="card-title">Параметри відбору</div>'
    '<div class="card-subtitle">Оберіть самостійний структурний підрозділ та статус погодження.</div>'
    '<div class="filter-panel">',
    unsafe_allow_html=True
)

if "cabinet_filters_applied_v19" not in st.session_state:
    st.session_state["cabinet_filters_applied_v19"] = {"department": None, "year": "Усі", "status": "Усі", "search": ""}

c1, c2, c3, c4 = st.columns(4)
with c1:
    departments = sorted(df["department"].dropna().astype(str).unique().tolist())
    if user_has_all_ssp_access(current_user):
        available_departments = departments
    else:
        available_departments = get_available_ssp_options_for_user(current_user, all_options=departments)
        allowed_indexes = current_user.get("allowed_ssp_indexes", [])
        available_departments = [d for d in departments if any(str(index) in str(d) for index in allowed_indexes)] or available_departments
    if not available_departments:
        st.warning("Для цього користувача немає доступних ССП.")
        st.stop()
    current_dep = st.session_state["cabinet_filters_applied_v19"].get("department") or available_departments[0]
    dep_index = available_departments.index(current_dep) if current_dep in available_departments else 0
    selected_department_pending = st.selectbox(
        "Самостійний структурний підрозділ", available_departments, index=dep_index,
        disabled=should_lock_ssp_fields(current_user), key="cabinet_department_pending"
    )
with c2:
    years = ["Усі"] + sorted(df["year"].dropna().astype(str).unique().tolist())
    _cur_year = st.session_state["cabinet_filters_applied_v19"].get("year", "Усі")
    selected_year_pending = st.selectbox("Рік", years, index=years.index(_cur_year) if _cur_year in years else 0, key="cabinet_year_pending")
with c3:
    _cur_status = st.session_state["cabinet_filters_applied_v19"].get("status", "Усі")
    selected_status_pending = st.selectbox("Статус погодження", APPROVAL_FILTER_OPTIONS, index=APPROVAL_FILTER_OPTIONS.index(_cur_status) if _cur_status in APPROVAL_FILTER_OPTIONS else 0, key="cabinet_status_pending")
with c4:
    search_pending = st.text_input("Пошук за ID або кодом заходу", value=st.session_state["cabinet_filters_applied_v19"].get("search", ""), key="cabinet_search_pending")

ba, bb, bc = st.columns([1, 1, 1.2])
with ba:
    if st.button("Застосувати обрані параметри", type="primary", use_container_width=True, key="cabinet_apply_filters_v19"):
        st.session_state["cabinet_filters_applied_v19"] = {"department": selected_department_pending, "year": selected_year_pending, "status": selected_status_pending, "search": search_pending}
        st.rerun()
with bb:
    if st.button("Скинути параметри", use_container_width=True, key="cabinet_reset_filters_v19"):
        st.session_state["cabinet_filters_applied_v19"] = {"department": available_departments[0], "year": "Усі", "status": "Усі", "search": ""}
        st.rerun()
with bc:
    st.caption("Заявки фільтруються тільки після застосування параметрів.")

_applied_cab = st.session_state["cabinet_filters_applied_v19"]
selected_department = _applied_cab.get("department") or available_departments[0]
selected_year = _applied_cab.get("year", "Усі")
selected_status = _applied_cab.get("status", "Усі")
search = str(_applied_cab.get("search", "") or "")

filtered = df[df["department"].astype(str) == str(selected_department)].copy()
if selected_year != "Усі":
    filtered = filtered[filtered["year"].astype(str) == str(selected_year)]
if selected_status == "Активні до розгляду":
    filtered = filtered[filtered["approval_status"].astype(str).isin(schemes.ALL_WAITING_STATUSES)]
elif selected_status != "Усі":
    filtered = filtered[filtered["approval_status"].astype(str) == selected_status]
if search.strip():
    sq = search.strip().lower()
    filtered = filtered[
        filtered["id"].astype(str).str.lower().str.contains(sq, na=False)
        | filtered["strat_code"].astype(str).str.lower().str.contains(sq, na=False)
    ]

st.caption(f"Знайдено відомостей: {len(filtered)}")
st.markdown('</div></div>', unsafe_allow_html=True)

if filtered.empty:
    st.info("За обраними параметрами відбору відомостей не знайдено.")
    st.stop()

# ============================================================
# METRICS
# ============================================================

total = len(filtered)
to_sign = len(filtered[filtered["approval_status"] == "Очікує: Керівник ССП"])
approved = len(filtered[filtered["approval_status"] == "Погоджено"])
waiting = len(filtered[filtered["approval_status"] == "Очікує погодження"])
returned = len(filtered[filtered["approval_status"] == "Повернуто на доопрацювання"])

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Усього відомостей", total)
m2.metric("🟣 На підтвердженні", to_sign)
m3.metric("🟡 Очікує", waiting)
m4.metric("🔴 Повернуто", returned)
m5.metric("🟢 Погоджено", approved)

# ============================================================
# REQUEST LIST
# ============================================================

st.markdown('<div class="card"><div class="card-title">Перелік відомостей</div>', unsafe_allow_html=True)

show_df = filtered.rename(columns={
    "id": "ID",
    "year": "Рік",
    "quarter": "Квартал",
    "strat_code": "Код заходу",
    "status": "Статус виконання",
    "numeric_value": "Фактичне значення",
    "approval_status": "Статус погодження",
    "responsible_person": "Відповідальна особа",
    "submitted_at": "Дата подання",
    "admin_comment": "Коментар координатора"
})

show_cols = [
    "ID", "Рік", "Квартал", "Код заходу", "Статус виконання",
    "Фактичне значення", "Статус погодження", "Відповідальна особа",
    "Дата подання", "Коментар координатора"
]
available_show_cols = [c for c in show_cols if c in show_df.columns]
st.dataframe(show_df[available_show_cols], use_container_width=True, hide_index=True)
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# DETAILED VIEW
# ============================================================

if st.session_state.get("cab_last_decision_notice"):
    st.warning(st.session_state["cab_last_decision_notice"], icon="⚠️")
    if st.button("Зрозуміло, приховати це повідомлення", key="cab_dismiss_decision_notice"):
        st.session_state.pop("cab_last_decision_notice", None)
        st.rerun()

st.markdown('<div class="card"><div class="card-title">Детальний перегляд та підтвердження</div>', unsafe_allow_html=True)

options = []
for _, row in filtered.iterrows():
    prefix = "🟣 " if row["approval_status"] == "Очікує: Керівник ССП" else ""
    options.append(
        f"{prefix}ID {row['id']} | {row['strat_code']} | {row['year']} {row['quarter']} квартал | {row['approval_status']}"
    )

selected = st.selectbox("Оберіть заявку", options)

raw_id = selected.replace("🟣 ", "").split("|")[0].replace("ID", "").strip()
selected_id = int(raw_id)
selected_row = filtered[filtered["id"].astype(int) == selected_id].iloc[0]

approval = clean(selected_row["approval_status"])
code = clean(selected_row["strat_code"])
badge_class = status_badge_class(approval)

st.markdown(f"""
<div class="badge-wrap">
    <div class="badge {badge_class}">Статус: {display_text(approval)}</div>
    <div class="badge">ID {selected_id}</div>
    <div class="badge">Захід {display_text(code)}</div>
    <div class="badge">Рік: {display_text(selected_row["year"])}</div>
    <div class="badge">Квартал: {display_text(selected_row["quarter"])}</div>
</div>
""", unsafe_allow_html=True)

measure_info = strat_df[strat_df["code"].astype(str).str.strip() == code].copy()
if not measure_info.empty:
    mi = measure_info.iloc[0]
    st.markdown(f"""
    <div class="step-box">
        <b>{display_text(code)} — {display_text(mi["name"])}</b><br>
        <span style="color:#475569;">Індикатор: {display_text(mi["indicator"])}</span><br>
        <span style="color:#475569;">Одиниця виміру: {display_text(mi["unit"])}</span><br>
        <span style="color:#475569;">Терміни: {display_text(mi["start_date_plan"])} — {display_text(mi["end_date_plan"])}</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown(f"""
<div class="info-grid">
    <div class="info-card info-card-blue">
        <div class="info-label">Статус виконання</div>
        <div class="info-value">{display_text(selected_row["status"])}</div>
    </div>
    <div class="info-card info-card-green">
        <div class="info-label">Фактичне значення</div>
        <div class="info-value">{display_text(selected_row["numeric_value"])}</div>
    </div>
    <div class="info-card info-card-yellow">
        <div class="info-label">ССП</div>
        <div class="info-value">{display_text(selected_row["department"])}</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ── Поля лише для читання ────────────────────────────────────────────────────
st.markdown('<div class="card">', unsafe_allow_html=True)

p1, p2, p3 = st.columns(3)
with p1:
    st.text_input("ПІБ відповідальної особи", value=clean(selected_row["responsible_person"]),
                  disabled=True, key=f"v_resp_{selected_id}")
with p2:
    st.text_input("Телефон", value=clean(selected_row["phone"]),
                  disabled=True, key=f"v_phone_{selected_id}")
with p3:
    st.text_input("Email", value=clean(selected_row["email"]),
                  disabled=True, key=f"v_email_{selected_id}")

st.text_area("Опис прогресу", value=clean(selected_row["progress_text"]),
             disabled=True, height=120, key=f"v_prog_{selected_id}")
st.text_area("Ризики / проблеми / відхилення", value=clean(selected_row["risks"]),
             disabled=True, height=100, key=f"v_risks_{selected_id}")

if has_value(selected_row["admin_comment"]):
    st.markdown(f"""
    <div class="comment-box">
        <div class="comment-title">Коментар координатора</div>
        <div class="comment-text">{display_text(selected_row["admin_comment"])}</div>
    </div>
    """, unsafe_allow_html=True)

# ── Посилання на НПА (клікабельні; може бути декілька) ──
_npa_raw = clean(selected_row.get("npa_link", "")) if "npa_link" in selected_row.index else ""
if _npa_raw:
    _links_html = "".join(
        f'<div>🔗 <a href="{escape(u.strip())}" target="_blank">{escape(u.strip())}</a></div>'
        for u in re.split(r"[\n;,]+", _npa_raw) if u.strip()
    )
    st.markdown(f"""
    <div class="comment-box">
        <div class="comment-title">Посилання на НПА / підтвердні документи</div>
        <div class="comment-text">{_links_html}</div>
    </div>
    """, unsafe_allow_html=True)

# ── Маршрут погодження (схема + прогрес) ──
_chain = schemes.parse_chain(selected_row.get("approval_chain")) if "approval_chain" in selected_row.index else []
_stage_idx = schemes.parse_stage(selected_row.get("chain_stage")) if "chain_stage" in selected_row.index else 0
if _chain:
    _scheme_lbl = clean(selected_row.get("scheme_label", "")) if "scheme_label" in selected_row.index else ""
    st.markdown(f"""
    <div class="comment-box">
        <div class="comment-title">Схема погодження{(" · " + escape(_scheme_lbl)) if _scheme_lbl else ""}</div>
        <div class="comment-text">
            {escape(schemes.chain_route_text(_chain))}<br>
            <b>{escape(schemes.chain_progress_text(_chain, _stage_idx, approval))}</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# ACTION PANEL — панель дій поточної ланки схеми погодження
# ============================================================
# Заявка з ланцюгом: дії доступні, коли ПОТОЧНА ланка — це саме цей
# користувач (за email; якщо email у ланці не вказано — за роллю).
# Успадковані заявки без ланцюга: стара поведінка — керівник ССП
# діє за статусу «Очікує: Керівник ССП».

_my_email = str(current_user.get("email") or "").strip().lower()
_my_role = current_user.get("role")

_waiting_statuses = set(schemes.ALL_WAITING_STATUSES)

if _chain:
    _stage = schemes.current_stage(_chain, _stage_idx)
    is_my_turn = (
        approval in _waiting_statuses
        and _stage is not None
        and (
            (_stage.get("email") and _stage.get("email") == _my_email)
            or (not _stage.get("email") and _stage.get("role") == _my_role)
        )
    )
    _stage_label = _stage.get("label", "") if _stage else ""
else:
    is_my_turn = (approval == "Очікує: Керівник ССП" and _my_role == ROLE_SSP_HEAD)
    _stage_label = "Керівник ССП"

if is_my_turn:
    st.markdown(f"""
    <div class="sign-panel">
        <div class="sign-panel-title">✍️ Дії ланки «{escape(_stage_label)}»</div>
        <div class="sign-panel-sub">
            Ознайомтесь із відомостями вище та оберіть одну з дій. При поверненні —
            обов'язково залиште коментар та оберіть, кому саме повертається заявка.
        </div>
    </div>
    """, unsafe_allow_html=True)

    leader_comment = st.text_area(
        "Коментар (обов'язковий при поверненні)",
        height=90,
        placeholder="Вкажіть причину повернення або зауваження...",
        key=f"leader_comment_{selected_id}"
    )

    # ТЗ 3.16: користувач має розуміти наслідок дії ЩЕ ДО натискання кнопки —
    # показуємо, кому саме перейде заявка після погодження.
    _preview_next = schemes.current_stage(_chain, _stage_idx + 1) if _chain else None
    if _preview_next is not None:
        _next_who = clean(_preview_next.get("name", "") or _preview_next.get("email", ""))
        _next_note = (
            f"➡️ Після погодження заявка перейде наступній ланці: "
            f"«{clean(_preview_next.get('label', ''))}»"
            + (f" — {_next_who}" if _next_who else "")
        )
    else:
        _next_note = (
            "➡️ Наступної наперед визначеної ланки немає — після погодження ви "
            "зможете завершити погодження або передати вище."
        )
    # ТЗ 3.17: попередження про незворотність.
    st.markdown(
        f'<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:10px;'
        f'padding:8px 12px;margin-bottom:8px;font-size:13px;color:#92400e;">'
        f'<div style="font-weight:800;">{escape(_next_note)}</div>'
        f'<div style="margin-top:2px;">⚠️ Після погодження ви більше не зможете '
        f'змінити своє рішення — заявка повернеться до вас лише в разі '
        f'повернення на доопрацювання наступними ланками.</div></div>',
        unsafe_allow_html=True,
    )

    # Адресати повернення: подавач + усі попередні ланки
    if _chain:
        _targets = schemes.return_targets(_chain, _stage_idx)
    else:
        _targets = [
            {"key": "submitter", "label": "Подавачу (відповідальній особі ССП)",
             "status": "Повернуто на доопрацювання", "new_stage": 0},
            {"key": "legacy_admin", "label": "Координатору",
             "status": "Очікує погодження", "new_stage": 0},
        ]

    btn_col1, btn_col2 = st.columns([1, 1.6])

    with btn_col1:
        sign_btn = st.button("✅ Погодити та передати далі", use_container_width=True,
                             key=f"sign_{selected_id}")
    with btn_col2:
        rc1, rc2 = st.columns([1.7, 1])
        with rc1:
            _target_labels = [t["label"] for t in _targets]
            _picked_target_label = st.selectbox(
                "Кому повернути", _target_labels,
                key=f"return_target_{selected_id}", label_visibility="collapsed",
            )
        with rc2:
            return_btn = st.button("↩️ Повернути", use_container_width=True,
                                   key=f"ret_{selected_id}")

    _picked_target = _targets[_target_labels.index(_picked_target_label)]

    # ── Динамічний вибір наступної ланки (пункт "схеми погодження мають
    # бути різні для кожної ланки"): якщо в ланцюга вже НЕМАЄ наперед
    # визначеної наступної ланки, саме ЦЯ ланка (а не подавач і не
    # координатор заздалегідь) вирішує — завершити заявку на собі, чи
    # передати вище (лише вище — керівнику ССП; спуститися "нижче себе"
    # чи повернутися до вже пройденого рівня не можна). Для керівника
    # ССП варіантів немає — він завжди найвища ланка.
    _next_after_me = schemes.current_stage(_chain, _stage_idx + 1) if _chain else None
    _my_next_role_options = []
    if _chain and not _next_after_me:
        _my_next_role_options = schemes.next_stage_role_options(_my_role)

    _my_chosen_next_role = None
    _my_chosen_next_person = None
    if _my_next_role_options:
        _my_req_dept_nums = re.findall(r"\d+", clean(selected_row.get("department", "")))
        _my_req_dept_idx = _my_req_dept_nums[0] if _my_req_dept_nums else ""
        _my_next_choice_labels = [f"Завершити на «{_stage_label}» (без додаткової ланки)"] + [
            f"Передати ланці «{schemes.STAGE_LABELS[r]}»" for r in _my_next_role_options
        ]
        _my_next_choice = st.selectbox(
            "Що далі після вашого рішення",
            _my_next_choice_labels,
            key=f"cab_next_stage_choice_{selected_id}",
        )
        if _my_next_choice != _my_next_choice_labels[0]:
            _my_chosen_next_role = _my_next_role_options[_my_next_choice_labels.index(_my_next_choice) - 1]
            _my_next_candidates = schemes.stage_candidates(_my_chosen_next_role, _my_req_dept_idx)
            if len(_my_next_candidates) > 1:
                _my_cand_labels = [schemes.candidate_label(c) for c in _my_next_candidates]
                _my_picked_cand_label = st.selectbox(
                    f"Хто саме — {schemes.STAGE_LABELS[_my_chosen_next_role]}",
                    _my_cand_labels,
                    key=f"cab_next_stage_person_{selected_id}",
                )
                _my_chosen_next_person = _my_next_candidates[_my_cand_labels.index(_my_picked_cand_label)]
            elif _my_next_candidates:
                _my_chosen_next_person = _my_next_candidates[0]
                st.caption(f"→ {schemes.candidate_label(_my_chosen_next_person)}")
            else:
                st.error(
                    f"Немає користувача ролі «{schemes.STAGE_LABELS[_my_chosen_next_role]}» "
                    f"для цього ССП. Оберіть «Завершити» або зверніться до супер-адміна."
                )

    # ── Погодити та передати далі ───────────────────────────
    if sign_btn:
        _sign_blocked = False
        if _chain and _next_after_me:
            # ЗАСТАРІЛИЙ ланцюг: наступна ланка вже наперед відома.
            new_status, new_stage = schemes.status_after_approve(_chain, _stage_idx)
            _final_chain_for_notify = _chain
        elif _chain and _my_chosen_next_role:
            if not _my_chosen_next_person:
                st.error("Оберіть конкретну особу для наступної ланки.")
                _sign_blocked = True
                new_status, new_stage, _final_chain_for_notify = approval, _stage_idx, _chain
            else:
                _new_chain, new_status, new_stage = schemes.advance_with_new_stage(
                    _chain, _stage_idx, _my_chosen_next_role, _my_req_dept_idx, _my_chosen_next_person
                )
                if _new_chain is None:
                    st.error("Не вдалося призначити наступну ланку.")
                    _sign_blocked = True
                    new_status, new_stage, _final_chain_for_notify = approval, _stage_idx, _chain
                else:
                    _chain = _new_chain
                    _final_chain_for_notify = _new_chain
        elif _chain:
            new_status, new_stage = schemes.finalize_here(_stage_idx)
            _final_chain_for_notify = _chain
        else:
            new_status, new_stage = "Погоджено", _stage_idx + 1
            _final_chain_for_notify = _chain

        if _sign_blocked:
            st.stop()

        update_data = {
            "approval_status": new_status,
            "admin_comment": clean(leader_comment) or f"Погоджено ланкою «{_stage_label}»",
        }
        if _chain and "chain_stage" in selected_row.index:
            update_data["chain_stage"] = int(new_stage)
        if _chain and "approval_chain" in selected_row.index:
            update_data["approval_chain"] = schemes.chain_to_json(_chain)
        update_data = schemes.finalize_update_payload(update_data, new_status)

        try:
            supabase.table("monitoring_requests").update(update_data).eq("id", selected_id).execute()
            write_log(
                selected_id,
                f"Погодження ланкою «{_stage_label}»",
                approval, new_status,
                clean(leader_comment) or f"Погоджено ланкою «{_stage_label}»",
                changed_by=role_label,
            )

            # Миттєві сповіщення
            try:
                if new_status == "Погоджено":
                    notify_events.notify_approved(
                        clean(selected_row.get("email", "")),
                        clean(selected_row.get("responsible_person", "")),
                        code, clean(selected_row.get("year", "")), clean(selected_row.get("quarter", "")),
                    )
                elif _final_chain_for_notify:
                    _next = schemes.current_stage(_final_chain_for_notify, new_stage)
                    if _next:
                        notify_events.notify_stage_assigned(
                            _next.get("email", ""), _next.get("name", ""), _next.get("label", ""),
                            code, clean(selected_row.get("year", "")), clean(selected_row.get("quarter", "")),
                            submitter=clean(selected_row.get("responsible_person", "")),
                        )
            except Exception:
                pass

            if new_status == "Погоджено":
                st.success("✅ Заявка пройшла всі етапи схеми. Статус: «Погоджено».")
            else:
                _next = schemes.current_stage(_final_chain_for_notify, new_stage) if _final_chain_for_notify else None
                if _next:
                    _who = _next.get("name") or _next.get("email") or _next.get("label")
                    st.success(
                        f"✅ Підтверджено. Заявка одразу надійшла наступній ланці — "
                        f"**{_next.get('label','')}** ({_who}). "
                        f"Вона вже бачить її у своєму кабінеті у списку «Активні до розгляду»."
                    )
                else:
                    st.success(f"✅ Підтверджено. Новий статус: «{new_status}».")
            st.session_state["cab_last_decision_notice"] = (
                "Рішення застосовано. Якщо в черзі є ще заявки — систему щойно "
                "переключило на НАСТУПНУ заявку. Це не помилка: перегляньте її "
                "дані з самого початку, перш ніж ухвалювати рішення."
            )
            monitoring_data.invalidate_monitoring_cache()
            st.rerun()
        except Exception as e:
            st.error("Помилка під час погодження.")
            st.exception(e)

    # ── Повернути на доопрацювання ──────────────────────────
    if return_btn:
        if not clean(leader_comment):
            st.error("Вкажіть коментар перед поверненням на доопрацювання.")
        else:
            update_data = {
                "approval_status": _picked_target["status"],
                "admin_comment": leader_comment,
            }
            if _chain and "chain_stage" in selected_row.index:
                update_data["chain_stage"] = int(_picked_target["new_stage"])
            try:
                supabase.table("monitoring_requests").update(update_data).eq("id", selected_id).execute()
                write_log(
                    selected_id,
                    f"Повернення на доопрацювання: {_picked_target['label']}",
                    approval, _picked_target["status"],
                    leader_comment,
                    changed_by=role_label,
                )
                try:
                    if _picked_target["key"] == "submitter":
                        notify_events.notify_returned(
                            clean(selected_row.get("email", "")),
                            clean(selected_row.get("responsible_person", "")),
                            code, clean(selected_row.get("year", "")), clean(selected_row.get("quarter", "")),
                            by_label=_stage_label, comment=clean(leader_comment),
                        )
                    elif _picked_target["key"].startswith("stage:") and _chain:
                        _tstage = _chain[_picked_target["new_stage"]]
                        notify_events.notify_returned(
                            _tstage.get("email", ""), _tstage.get("name", ""),
                            code, clean(selected_row.get("year", "")), clean(selected_row.get("quarter", "")),
                            by_label=_stage_label, comment=clean(leader_comment),
                        )
                except Exception:
                    pass
                st.warning(f"↩️ Заявку повернуто: {_picked_target['label']}.")
                st.session_state["cab_last_decision_notice"] = (
                    "Рішення застосовано. Якщо в черзі є ще заявки — систему щойно "
                    "переключило на НАСТУПНУ заявку. Це не помилка: перегляньте її "
                    "дані з самого початку, перш ніж ухвалювати рішення."
                )
                monitoring_data.invalidate_monitoring_cache()
                st.rerun()
            except Exception as e:
                st.error("Помилка при поверненні.")
                st.exception(e)

    # ── Редагувати дані напряму (пункт 3 нового ТЗ) ──────────
    # Замість того, щоб повертати заявку на доопрацювання (і чекати,
    # доки подавач сам відредагує), ця ланка може виправити дані сама.
    # Відредаговані дані завжди повертаються саме координатору —
    # незалежно від того, на якій ланці зараз перебуває ланка, що
    # редагує (координатор повторно перевіряє й далі заявка йде
    # рештою маршруту як зазвичай).
    if not schemes.is_final_locked(selected_row):
        with st.expander(f"✏️ Редагувати дані заявки (від імені ланки «{_stage_label}»)"):
            st.caption(
                "Використовуйте, якщо простіше виправити дані самостійно, ніж "
                "повертати заявку відповідальній особі. Попередню версію буде "
                "збережено в історії; заявка повернеться на розгляд координатору."
            )

            _cab_status_options = list(SUBMISSION_STATUS_OPTIONS)
            _cab_current_status = clean(selected_row["status"])
            _cab_status_index = (
                _cab_status_options.index(_cab_current_status)
                if _cab_current_status in _cab_status_options else 0
            )

            cab_new_status = st.selectbox(
                "Статус виконання", _cab_status_options, index=_cab_status_index,
                key=f"cab_edit_status_{selected_id}",
            )
            cab_new_value = st.text_input(
                "Фактичне значення", value=clean(selected_row["numeric_value"]),
                key=f"cab_edit_value_{selected_id}",
            )
            cab_new_progress = st.text_area(
                "Опис прогресу", value=clean(selected_row["progress_text"]),
                height=110, key=f"cab_edit_progress_{selected_id}",
            )
            cab_new_risks = st.text_area(
                "Ризики / проблеми / відхилення", value=clean(selected_row["risks"]),
                height=110, key=f"cab_edit_risks_{selected_id}",
            )

            cab_edit_submit = st.button(
                "💾 Зберегти й надіслати координатору",
                use_container_width=True,
                key=f"cab_edit_submit_{selected_id}",
            )

            if cab_edit_submit:
                if not has_value(cab_new_value) or not has_value(cab_new_progress):
                    st.error("Заповніть фактичне значення та опис прогресу.")
                else:
                    try:
                        _cab_old_version = save_request_version(
                            selected_id, selected_row.to_dict(),
                            created_by=f"{role_label} / до редагування",
                        )

                        if _chain:
                            _cab_coord_idx = coordinator_stage_index(_chain)
                            _cab_new_status = schemes.waiting_status_for_stage(_chain[_cab_coord_idx])
                        else:
                            _cab_coord_idx = 0
                            _cab_new_status = "Очікує погодження"

                        _cab_update = {
                            "status": cab_new_status,
                            "numeric_value": cab_new_value,
                            "progress_text": cab_new_progress,
                            "risks": cab_new_risks,
                            "approval_status": _cab_new_status,
                            "chain_stage": int(_cab_coord_idx),
                            "admin_comment": "",
                        }

                        supabase.table("monitoring_requests").update(_cab_update).eq(
                            "id", selected_id
                        ).execute()

                        if _chain:
                            _cab_coord_stage = _chain[_cab_coord_idx]
                            try:
                                notify_events.notify_stage_assigned(
                                    _cab_coord_stage.get("email", ""), _cab_coord_stage.get("name", ""),
                                    _cab_coord_stage.get("label", ""),
                                    code, clean(selected_row.get("year", "")), clean(selected_row.get("quarter", "")),
                                    submitter=clean(selected_row.get("responsible_person", "")),
                                    kind=clean(selected_row.get("object_kind", "")) or "measure",
                                )
                            except Exception:
                                pass

                        _cab_new_version_data = selected_row.to_dict()
                        _cab_new_version_data.update(_cab_update)
                        _cab_new_version = save_request_version(
                            selected_id, _cab_new_version_data,
                            created_by=f"{role_label} / редагування",
                        )

                        write_log(
                            selected_id,
                            f"Редагування ланкою «{_stage_label}»: версія "
                            f"{_cab_old_version} → {_cab_new_version}",
                            approval, _cab_new_status,
                            "Відредаговано ланкою погодження; надіслано координатору повторно.",
                            changed_by=role_label,
                        )

                        st.success(
                            "Зміни збережено. Заявку повторно надіслано координатору на розгляд."
                        )
                        monitoring_data.invalidate_monitoring_cache()
                        st.rerun()
                    except Exception as e:
                        st.error("Не вдалося зберегти зміни.")
                        st.exception(e)

else:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    if approval == "Погоджено":
        st.success("✅ Заявку вже підтверджено. Жодних дій не потрібно.")
    elif approval in _waiting_statuses:
        if _chain:
            st.info(f"🕐 Зараз не ваша ланка. {schemes.chain_progress_text(_chain, _stage_idx, approval)}")
        else:
            st.info("🕐 Заявка ще не надійшла на ваш етап погодження.")
    elif approval == "Повернуто на доопрацювання":
        st.warning("↩️ Заявку повернуто відповідальному на доопрацювання.")
    else:
        st.info("Для цього статусу дій не передбачено.")
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# LOG HISTORY
# ============================================================

logs_df = load_logs(selected_id)
st.markdown('<div class="card"><div class="card-title">Історія зміни статусу</div>', unsafe_allow_html=True)
# ЄДИНИЙ компонент таймлайну для всієї системи (core/ui.py, ТЗ 16.13)
render_request_timeline(logs_df)
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# РУЧНІ ЗАКРИТТЯ ЗАХОДІВ — реакція керівника ССП
# ============================================================
# Після підтвердження супер-адміном закриття направляється керівнику
# ССП «до відома»: він може не заперечити або заперечити з коментарем.
# Заперечення НЕ блокує закриття автоматично — його розглядає
# супер-адмін і, за потреби, скасовує закриття.

if _my_role == ROLE_SSP_HEAD:
    try:
        _co_resp = (
            supabase.table("closeout_requests")
            .select("*")
            .eq("approval_status", "Підтверджено")
            .execute()
        )
        _co_df = pd.DataFrame(_co_resp.data) if _co_resp.data else pd.DataFrame()
    except Exception:
        _co_df = pd.DataFrame()

    if not _co_df.empty:
        for _col in ("head_status", "head_comment", "strat_code",
                     "period_year", "period_quarter", "reason", "npa_links", "scope"):
            if _col not in _co_df.columns:
                _co_df[_col] = ""

        _my_ssp = str(current_user.get("ssp_index") or "")
        _my_allowed = [str(a) for a in (current_user.get("allowed_ssp_indexes") or [])]

        def _closeout_is_mine(co_row):
            # Закриття прив'язуємо до ССП через головного виконавця заходу
            _code = clean(co_row.get("strat_code"))
            try:
                _m = df_matrix[df_matrix["code"].astype(str).str.strip() == _code]
            except Exception:
                return "*" in _my_allowed
            if _m.empty:
                return "*" in _my_allowed
            _dept = str(_m.iloc[0].get("department", ""))
            _idx = re.findall(r"\d+", _dept)
            _idx = _idx[0] if _idx else ""
            return "*" in _my_allowed or (_idx and (_idx == _my_ssp or _idx in _my_allowed))

        try:
            df_matrix = load_strat_matrix()
        except Exception:
            df_matrix = pd.DataFrame(columns=["code", "department"])

        _pending_ack = _co_df[
            _co_df.apply(_closeout_is_mine, axis=1)
            & (~_co_df["head_status"].astype(str).isin(["Не заперечує", "Заперечує", "Оскаржено"]))
        ]

        if not _pending_ack.empty:
            st.markdown(
                '<div class="card"><div class="card-title">🔒 Ручні закриття заходів вашого ССП — потрібна ваша реакція</div>',
                unsafe_allow_html=True,
            )
            st.caption(
                "Ці заходи закрито адміністратором на підставі внутрішньої інформації та "
                "підтверджено супер-адміном. Ознайомтесь: якщо ви не згодні — "
                "заперечте з коментарем, і рішення перегляне супер-адміністратор."
            )
            for _, _co in _pending_ack.iterrows():
                _co_id = int(_co.get("id"))
                _links_html = " ".join(
                    f'<a href="{escape(u.strip())}" target="_blank">🔗 посилання</a>'
                    for u in re.split(r"[\n;,]+", clean(_co.get("npa_links"))) if u.strip()
                )
                st.markdown(
                    f"""<div class="comment-box">
                        <div class="comment-title">Захід {escape(clean(_co.get("strat_code")))} ·
                            {escape(clean(_co.get("period_quarter")))} · {escape(clean(_co.get("period_year")))}
                            ({escape(clean(_co.get("scope")) or "Квартал")})</div>
                        <div class="comment-text">Підстава: {escape(clean(_co.get("reason")))} {_links_html}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
                _ack_comment = st.text_input(
                    "Коментар (обов'язковий при запереченні)",
                    key=f"co_ack_comment_{_co_id}",
                )
                _a1, _a2 = st.columns(2)
                with _a1:
                    _ok_btn = st.button("✅ Не заперечую", key=f"co_ok_{_co_id}", use_container_width=True)
                with _a2:
                    _obj_btn = st.button("⛔ Оскаржити", key=f"co_obj_{_co_id}", use_container_width=True)

                if _ok_btn or _obj_btn:
                    if _obj_btn and not clean(_ack_comment):
                        st.error("Вкажіть коментар до заперечення.")
                    else:
                        _new_head_status = "Оскаржено" if _obj_btn else "Не заперечує"
                        try:
                            supabase.table("closeout_requests").update({
                                "head_status": _new_head_status,
                                "head_comment": clean(_ack_comment),
                                "head_email": _my_email,
                            }).eq("id", _co_id).execute()
                            write_log(
                                _co_id,
                                f"Реакція керівника ССП на ручне закриття: {_new_head_status}",
                                "Підтверджено", "Підтверджено",
                                clean(_ack_comment), changed_by=role_label,
                            )
                            st.success(f"Вашу реакцію зафіксовано: {_new_head_status}.")
                            monitoring_data.invalidate_monitoring_cache()
                            st.rerun()
                        except Exception as e:
                            st.error("Не вдалося зберегти реакцію.")
                            st.exception(e)
            st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# FOOTER
# ============================================================

render_footer()
