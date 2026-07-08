import streamlit as st
import pandas as pd
from core.db import get_supabase_client
from core.notifications import render_notifications_panel
from core.config import FILE_PATH, SHEET_NAME
from core.excel_loader import read_excel_sheet
from datetime import datetime, timezone
from html import escape
import re
from core.page_setup import page_setup, render_footer
from core.strategic_data import load_strat_matrix as core_load_strat_matrix
from core import monitoring_data
from core import notify_events
from core.statuses import SUBMISSION_STATUS_OPTIONS

from core import approval_schemes as schemes
from core.access import (
    filter_requests_for_user,
    get_available_ssp_options_for_user,
    get_prefilled_user_contacts,
    should_lock_ssp_fields,
    user_has_all_ssp_access,
)

current_user = page_setup("Мої заявки", page_name="Мої заявки")
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
    box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.08) !important;
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

.badge-green {
    background: #dcfce7;
    border: 1px solid #bbf7d0;
    color: #166534;
}

.badge-yellow {
    background: #fef9c3;
    border: 1px solid #fde68a;
    color: #854d0e;
}

.badge-red {
    background: #fee2e2;
    border: 1px solid #fecaca;
    color: #991b1b;
}

.badge-gray {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    color: #475569;
}

.badge-blue {
    background: #dbeafe;
    border: 1px solid #93c5fd;
    color: #1e40af;
}

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

.info-card-blue {
    background: #eef6ff;
    border-color: #bfdbfe;
}

.info-card-green {
    background: #dcfce7;
    border-color: #bbf7d0;
}

.info-card-yellow {
    background: #fef9c3;
    border-color: #fde68a;
}

.info-card-red {
    background: #fee2e2;
    border-color: #fecaca;
}

.info-card-gray {
    background: #f8fafc;
    border-color: #cbd5e1;
}

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

.version-box {
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    margin: 10px 0;
}

.version-title {
    color: #0f172a;
    font-weight: 900;
    font-size: 15px;
    margin-bottom: 6px;
}

.version-text {
    color: #475569;
    font-size: 13px;
    line-height: 1.45;
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


def valid_email(email):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(email).strip()) is not None


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
        return "badge-blue"
    if status == "Очікує погодження":
        return "badge-yellow"
    return "badge-gray"


ACTIVE_APPROVAL_STATUSES = [
    "Очікує погодження",
    "Повернуто на доопрацювання",
    "Очікує: Керівник ССП",
]

APPROVAL_FILTER_OPTIONS = [
    "Активні до розгляду",
    "Усі",
    "Очікує погодження",
    "Повернуто на доопрацювання",
    "Очікує: Керівник ССП",
    "Погоджено",
]


# ============================================================
# DATA LOADING
# ============================================================

@st.cache_data
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

def write_log(request_id, action, old_status, new_status, admin_comment):
    supabase.table("monitoring_logs").insert({
        "request_id": int(request_id),
        "action": action,
        "old_status": old_status,
        "new_status": new_status,
        "admin_comment": admin_comment,
        # Аудит: конкретний користувач, а не лише роль
        "changed_by": _actor_identity("ССП")
    }).execute()


# Спільна логіка версіювання винесена в core/versioning.py (пункт 3 ТЗ:
# та сама логіка тепер потрібна і в 1_Мій_кабінет.py, і в
# 3_Адміністрування.py для коригування супер-адміном закритих заявок).
from core.versioning import (
    get_next_version_number,
    save_request_version,
    load_versions,
)


# ============================================================
# MAIN DATA
# ============================================================

df = load_requests()
strat_df = load_strat_matrix()

df = filter_requests_for_user(
    df,
    current_user,
    ssp_columns=["department"]
)

prefilled_contacts = get_prefilled_user_contacts(current_user)

st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)

st.markdown("""
<div class="ministry-label">
🇺🇦 Міністерство економіки, довкілля та сільського господарства України
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-box">
    <div class="header-title">Мої заявки</div>
    <div class="header-subtitle">
        Кабінет самостійного структурного підрозділу призначений для перегляду поданих відомостей,
        відстеження статусу погодження, перегляду коментарів координатора, історії змін та повторного
        подання відомостей після доопрацювання.
    </div>
    <div class="badge-wrap">
        <div class="badge">● Режим: перегляд відомостей</div>
        <div class="badge">● Доступ: ССП</div>
        <div class="badge">● Версійність: активна</div>
        <div class="badge">● Повторне подання: доступне для повернутих відомостей</div>
    </div>
</div>
""", unsafe_allow_html=True)

if df.empty:
    st.warning("Поки що немає поданих відомостей.")
    st.stop()

required_cols = [
    "id", "year", "quarter", "department", "responsible_person", "phone", "email",
    "strat_code", "status", "progress_text", "numeric_value", "risks",
    "submitted_at", "approval_status", "admin_comment", "file_names", "file_urls",
    "start_date", "end_date"
]

for col in required_cols:
    if col not in df.columns:
        df[col] = ""

# DEMO 1.9: «Мої заявки» показує тільки заявки, створені поточним користувачем,
# а не всі заявки ССП. Основний ключ — email подавача.
_current_email = str((current_user or {}).get("email") or "").strip().lower()
if _current_email and "email" in df.columns:
    df = df[df["email"].astype(str).str.strip().str.lower() == _current_email].copy()

render_notifications_panel(df, mode="cabinet")

# ============================================================
# FILTERS
# ============================================================

st.markdown(
    '<div class="card"><div class="card-title">Параметри відбору</div>'
    '<div class="card-subtitle">Фільтри застосовуються тільки після натискання кнопки. У кабінеті показуються лише заявки, створені поточним користувачем.</div>'
    '<div class="filter-panel">',
    unsafe_allow_html=True
)

if "my_requests_filters_applied" not in st.session_state:
    st.session_state.my_requests_filters_applied = {
        "year": "Усі",
        "status": "Усі",
        "search": "",
    }

f1, f2, f3 = st.columns([0.75, 1.15, 1.5])
with f1:
    years = ["Усі"] + sorted(df["year"].dropna().astype(str).unique().tolist())
    st.selectbox("Рік", years, key="my_req_year_pending")
with f2:
    st.selectbox("Статус погодження", APPROVAL_FILTER_OPTIONS, index=0, key="my_req_status_pending")
with f3:
    st.text_input("Пошук за ID або кодом заходу", key="my_req_search_pending")

b1, b2 = st.columns([1, 1])
with b1:
    if st.button("Застосувати обрані параметри", type="primary", use_container_width=True, key="my_req_apply_filters"):
        st.session_state.my_requests_filters_applied = {
            "year": st.session_state.get("my_req_year_pending", "Усі"),
            "status": st.session_state.get("my_req_status_pending", "Усі"),
            "search": st.session_state.get("my_req_search_pending", ""),
        }
        st.rerun()
with b2:
    if st.button("Скинути параметри", use_container_width=True, key="my_req_reset_filters"):
        st.session_state.my_requests_filters_applied = {"year": "Усі", "status": "Усі", "search": ""}
        for _k in ("my_req_year_pending", "my_req_status_pending", "my_req_search_pending"):
            st.session_state.pop(_k, None)
        st.rerun()

_applied = st.session_state.my_requests_filters_applied
filtered = df.copy()

selected_year = _applied.get("year", "Усі")
selected_status = _applied.get("status", "Усі")
search = str(_applied.get("search", "") or "")

if selected_year != "Усі":
    filtered = filtered[filtered["year"].astype(str) == str(selected_year)]

if selected_status == "Активні до розгляду":
    filtered = filtered[filtered["approval_status"].astype(str).isin(ACTIVE_APPROVAL_STATUSES)]
elif selected_status != "Усі":
    filtered = filtered[filtered["approval_status"].astype(str) == selected_status]

if search.strip():
    sq = search.strip().lower()
    filtered = filtered[
        filtered["id"].astype(str).str.lower().str.contains(sq, na=False)
        | filtered["strat_code"].astype(str).str.lower().str.contains(sq, na=False)
        | filtered["responsible_person"].astype(str).str.lower().str.contains(sq, na=False)
    ]

# Повернуті заявки піднімаємо вгору.
if not filtered.empty:
    filtered["_returned_rank"] = (filtered["approval_status"].astype(str) != "Повернуто на доопрацювання").astype(int)
    filtered["_submitted_sort"] = pd.to_datetime(filtered["submitted_at"], errors="coerce")
    filtered = filtered.sort_values(["_returned_rank", "_submitted_sort"], ascending=[True, False]).drop(columns=["_returned_rank", "_submitted_sort"], errors="ignore")

st.caption(f"Знайдено відомостей: {len(filtered)}")
st.markdown('</div></div>', unsafe_allow_html=True)

if filtered.empty:
    st.info("За обраними параметрами відбору відомостей не знайдено.")
    st.stop()

# ============================================================
# METRICS
# ============================================================

total = len(filtered)
approved = len(filtered[filtered["approval_status"] == "Погоджено"])
waiting = len(filtered[filtered["approval_status"] == "Очікує погодження"])
returned = len(filtered[filtered["approval_status"] == "Повернуто на доопрацювання"])
sent_to_sign = len(filtered[filtered["approval_status"] == "Очікує: Керівник ССП"])

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Усього відомостей", total)
m2.metric("Очікує", waiting)
m3.metric("Повернуто", returned)
m4.metric("Очікує: Керівник ССП", sent_to_sign)
m5.metric("Погоджено", approved)

# ============================================================
# REQUEST LIST
# ============================================================

st.markdown('<div class="card"><div class="card-title">Перелік поданих відомостей</div>', unsafe_allow_html=True)

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

st.markdown('<div class="card"><div class="card-title">Детальний перегляд заявки</div>', unsafe_allow_html=True)

options = []
for _, row in filtered.iterrows():
    options.append(
        f"ID {row['id']} | {row['strat_code']} | {row['year']} {row['quarter']} квартал | {row['approval_status']}"
    )

selected = st.selectbox("Оберіть заявку", options)

selected_id = int(selected.split("|")[0].replace("ID", "").strip())
selected_row = filtered[filtered["id"].astype(int) == selected_id].iloc[0]

approval = clean(selected_row["approval_status"])
code = clean(selected_row["strat_code"])
badge_class = status_badge_class(approval)

st.markdown(f"""
<div class="badge-wrap">
    <div class="badge {badge_class}">Статус погодження: {display_text(approval)}</div>
    <div class="badge">Заявка ID {selected_id}</div>
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

# ============================================================
# REQUEST DATA WITHOUT TITLE
# ============================================================

st.markdown('<div class="card">', unsafe_allow_html=True)

p1, p2, p3 = st.columns(3)

with p1:
    st.text_input(
        "ПІБ відповідальної особи",
        value=clean(selected_row["responsible_person"]),
        disabled=True,
        key=f"view_responsible_{selected_id}"
    )

with p2:
    st.text_input(
        "Телефон",
        value=clean(selected_row["phone"]),
        disabled=True,
        key=f"view_phone_{selected_id}"
    )

with p3:
    st.text_input(
        "Email",
        value=clean(selected_row["email"]),
        disabled=True,
        key=f"view_email_{selected_id}"
    )

d1, d2 = st.columns(2)

with d1:
    st.text_input(
        "Початкова дата виконання",
        value=clean(selected_row["start_date"]),
        disabled=True,
        key=f"view_start_{selected_id}"
    )

with d2:
    st.text_input(
        "Кінцева дата виконання",
        value=clean(selected_row["end_date"]),
        disabled=True,
        key=f"view_end_{selected_id}"
    )

st.text_area(
    "Опис прогресу",
    value=clean(selected_row["progress_text"]),
    disabled=True,
    height=130,
    key=f"view_progress_{selected_id}"
)

st.text_area(
    "Ризики / проблеми / відхилення",
    value=clean(selected_row["risks"]),
    disabled=True,
    height=130,
    key=f"view_risks_{selected_id}"
)

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

# ── Маршрут погодження заявки ──
_chain = schemes.parse_chain(selected_row.get("approval_chain")) if "approval_chain" in selected_row.index else []
if _chain:
    _stage_idx = schemes.parse_stage(selected_row.get("chain_stage")) if "chain_stage" in selected_row.index else 0
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

# ── У кого зараз заявка та чи потрібна ваша дія (ТЗ 8.14 / 8.17) ──
def _render_holder_strip():
    _now = datetime.now(timezone.utc)

    # Скільки днів заявка на поточному кроці: від останньої дії в журналі,
    # а якщо дій ще не було — від моменту подання.
    _last_ts = None
    try:
        _hl = load_logs(selected_id)
        if not _hl.empty and "changed_at" in _hl.columns:
            _last_ts = pd.to_datetime(_hl["changed_at"], errors="coerce", utc=True).max()
    except Exception:
        _last_ts = None
    if _last_ts is None or pd.isna(_last_ts):
        _last_ts = pd.to_datetime(
            clean(selected_row.get("submitted_at", "")), errors="coerce", utc=True
        )
    _days_txt = ""
    if _last_ts is not None and not pd.isna(_last_ts):
        _days = max(0, (_now - _last_ts.to_pydatetime()).days)
        _days_txt = f" · на цьому кроці {_days} дн."

    if approval == "Погоджено":
        _holder = "Погодження завершено"
        _action = ("✅ Дій від вас не потрібно", "#f0fdf4", "#86efac", "#166534")
    elif approval == "Повернуто на доопрацювання":
        _holder = "Заявка у вас (повернута на доопрацювання)"
        _action = ("✍️ Потребує вашої дії — виправте дані та подайте повторно",
                   "#fff7ed", "#fdba74", "#9a3412")
    elif _chain:
        _hs_idx = (
            schemes.parse_stage(selected_row.get("chain_stage"))
            if "chain_stage" in selected_row.index else 0
        )
        _st = schemes.current_stage(_chain, _hs_idx)
        _holder = (
            f"Зараз у: {clean((_st or {}).get('label', ''))} — "
            f"{clean((_st or {}).get('name', '') or (_st or {}).get('email', ''))}"
        )
        _action = ("⏳ На розгляді — дій від вас не потрібно",
                   "#eff6ff", "#93c5fd", "#1e40af")
    else:
        _holder = "На розгляді координатора"
        _action = ("⏳ На розгляді — дій від вас не потрібно",
                   "#eff6ff", "#93c5fd", "#1e40af")

    st.markdown(
        f'<div style="display:flex;flex-wrap:wrap;gap:10px;margin:6px 0 10px 0;">'
        f'<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:10px;'
        f'padding:8px 12px;font-size:13px;font-weight:700;color:#0f172a;">'
        f'📍 {escape(_holder)}{escape(_days_txt)}</div>'
        f'<div style="background:{_action[1]};border:1px solid {_action[2]};'
        f'border-radius:10px;padding:8px 12px;font-size:13px;font-weight:700;'
        f'color:{_action[3]};">{_action[0]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

_render_holder_strip()

# ============================================================
# STATUS HISTORY
# ============================================================

logs_df = load_logs(selected_id)

st.markdown('<div class="card"><div class="card-title">Історія зміни статусу</div>', unsafe_allow_html=True)

if logs_df.empty:
    st.info("Історії змін для цієї заявки поки що немає.")
else:
    logs_show = logs_df.rename(columns={
        "changed_at": "Дата",
        "action": "Дія",
        "old_status": "Попередній статус",
        "new_status": "Новий статус",
        "admin_comment": "Коментар",
        "changed_by": "Ким змінено"
    })

    cols = ["Дата", "Дія", "Попередній статус", "Новий статус", "Коментар", "Ким змінено"]
    available = [c for c in cols if c in logs_show.columns]
    st.dataframe(logs_show[available], use_container_width=True, hide_index=True)

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# VERSION HISTORY
# ============================================================

st.markdown('<div class="card"><div class="card-title">Історія версій заявки</div>', unsafe_allow_html=True)

versions_df = load_versions(selected_id)

if versions_df.empty:
    st.info("Версій для цієї заявки поки що немає.")
else:
    latest_version = versions_df.sort_values("version_number", ascending=False).iloc[0]

    st.markdown(f"""
    <div class="version-box">
        <div class="version-title">Остання збережена версія: №{display_text(latest_version.get("version_number", ""))}</div>
        <div class="version-text">
            Створено: {display_text(latest_version.get("created_at", ""))}<br>
            Ким створено: {display_text(latest_version.get("created_by", ""))}<br>
            Статус погодження: {display_text(latest_version.get("approval_status", ""))}<br>
            Статус виконання: {display_text(latest_version.get("status", ""))}<br>
            Фактичне значення: {display_text(latest_version.get("numeric_value", ""))}
        </div>
    </div>
    """, unsafe_allow_html=True)

    versions_show = versions_df.rename(columns={
        "version_number": "Версія",
        "created_at": "Дата створення версії",
        "created_by": "Ким створено",
        "approval_status": "Статус погодження",
        "status": "Статус виконання",
        "numeric_value": "Фактичне значення",
        "progress_text": "Опис прогресу",
        "risks": "Ризики / проблеми"
    })

    cols = [
        "Версія",
        "Дата створення версії",
        "Ким створено",
        "Статус погодження",
        "Статус виконання",
        "Фактичне значення",
        "Опис прогресу",
        "Ризики / проблеми"
    ]

    available = [c for c in cols if c in versions_show.columns]

    st.dataframe(
        versions_show[available],
        use_container_width=True,
        hide_index=True
    )

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# ПРЯМЕ РЕДАГУВАННЯ (пункт 3 нового ТЗ)
# ============================================================
#
# На відміну від блоку "RESUBMIT" нижче (він доступний лише коли
# координатор/ланка явно повернули заявку на доопрацювання і запускає
# ВЕСЬ маршрут погодження заново), цей блок дозволяє подавачу
# відредагувати дані ПРЯМО ЗАРАЗ, поки заявка ще десь у процесі
# погодження (не повернута і ще не погоджена остаточно) — без
# додаткового кроку "надіслати на доопрацювання". Обов'язкова умова:
# відредаговані дані завжди повертаються саме на ланку координатора
# (а не на початок схеми і не туди, де заявка щойно була) — координатор
# повторно перевіряє зміни, після чого заявка як і раніше рухається
# рештою ланок схеми.
_direct_edit_statuses = set(schemes.ALL_WAITING_STATUSES) - {"Повернуто на доопрацювання"}

# ТЗ 2.10 / 8.7 / 8.8 / 8.11: пряме редагування доступне подавачу ЛИШЕ доти,
# доки жодна ланка схеми (насамперед координатор) не здійснила дій із
# заявкою: заявка стоїть на ПЕРШІЙ ланці у статусі очікування. Щойно
# координатор (або перша ланка) погодив/повернув — редагування блокується,
# і зміни можливі тільки через повернення на доопрацювання.
_first_stage_waiting = (
    schemes.waiting_status_for_stage(_chain[0]) if _chain else "Очікує погодження"
)
_request_stage_idx = (
    schemes.parse_stage(selected_row.get("chain_stage"))
    if "chain_stage" in selected_row.index else 0
)
_no_action_yet = (approval == _first_stage_waiting and _request_stage_idx == 0)

if (
    approval in _direct_edit_statuses
    and _no_action_yet
    and not schemes.is_final_locked(selected_row)
):
    with st.expander("✏️ Редагувати подану інформацію (без очікування повернення)"):
        st.caption(
            "Зміните дані нижче й натисніть «Зберегти й надіслати координатору». "
            "Попередню версію буде збережено в історії. Заявка повернеться на "
            "розгляд координатору (ланці «Координатор»), після чого — далі за "
            "звичайним маршрутом схеми погодження."
        )

        _de_status_options = list(SUBMISSION_STATUS_OPTIONS)
        _de_current_status = clean(selected_row["status"])
        _de_status_index = (
            _de_status_options.index(_de_current_status)
            if _de_current_status in _de_status_options else 0
        )

        de_new_status = st.selectbox(
            "Статус виконання", _de_status_options, index=_de_status_index,
            key=f"direct_edit_status_{selected_id}",
        )
        de_new_value = st.text_input(
            "Фактичне значення", value=clean(selected_row["numeric_value"]),
            key=f"direct_edit_value_{selected_id}",
        )
        de_new_progress = st.text_area(
            "Опис прогресу", value=clean(selected_row["progress_text"]),
            height=120, key=f"direct_edit_progress_{selected_id}",
        )
        de_new_risks = st.text_area(
            "Ризики / проблеми / відхилення", value=clean(selected_row["risks"]),
            height=120, key=f"direct_edit_risks_{selected_id}",
        )

        de_submit = st.button(
            "💾 Зберегти й надіслати координатору",
            use_container_width=True,
            key=f"direct_edit_submit_{selected_id}",
        )

        if de_submit:
            de_errors = []
            if not has_value(de_new_value):
                de_errors.append("Заповніть фактичне значення.")
            if not has_value(de_new_progress):
                de_errors.append("Заповніть опис прогресу.")

            if de_errors:
                for e in de_errors:
                    st.error(e)
                st.stop()

            try:
                _de_old_data = selected_row.to_dict()
                _de_old_version = save_request_version(
                    selected_id, _de_old_data, created_by="ССП / до редагування"
                )

                _de_chain = schemes.parse_chain(selected_row.get("approval_chain"))
                if _de_chain:
                    from core.versioning import coordinator_stage_index
                    # Якщо заявка ще НЕ дійшла до координатора (перша ланка —
                    # інша), редагування не «перестрибує» чергу: заявка
                    # залишається на поточній (першій) ланці. Якщо ж перша
                    # ланка — координатор, вона й отримує заявку повторно.
                    _de_coord_idx = min(
                        coordinator_stage_index(_de_chain), _request_stage_idx
                    )
                    _de_new_status = schemes.waiting_status_for_stage(_de_chain[_de_coord_idx])
                else:
                    _de_coord_idx = 0
                    _de_new_status = "Очікує погодження"

                _de_update = {
                    "status": de_new_status,
                    "numeric_value": de_new_value,
                    "progress_text": de_new_progress,
                    "risks": de_new_risks,
                    "approval_status": _de_new_status,
                    "chain_stage": int(_de_coord_idx),
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                    "admin_comment": "",
                }

                supabase.table("monitoring_requests").update(_de_update).eq(
                    "id", int(selected_id)
                ).execute()

                if _de_chain:
                    _de_coord_stage = _de_chain[_de_coord_idx]
                    try:
                        notify_events.notify_stage_assigned(
                            _de_coord_stage.get("email", ""), _de_coord_stage.get("name", ""),
                            _de_coord_stage.get("label", ""),
                            clean(selected_row.get("strat_code", "")),
                            clean(selected_row.get("year", "")),
                            clean(selected_row.get("quarter", "")),
                            submitter=clean(selected_row.get("responsible_person", "")),
                            kind=clean(selected_row.get("object_kind", "")) or "measure",
                        )
                    except Exception:
                        pass

                _de_new_version_data = selected_row.to_dict()
                _de_new_version_data.update(_de_update)
                _de_new_version = save_request_version(
                    selected_id, _de_new_version_data, created_by="ССП / пряме редагування"
                )

                write_log(
                    selected_id,
                    f"Пряме редагування поданих даних: версія {_de_old_version} → {_de_new_version}",
                    approval, _de_new_status,
                    "Відредаговано без повернення на доопрацювання; надіслано координатору повторно.",
                )

                st.success(
                    "Зміни збережено. Заявку повторно надіслано координатору на розгляд."
                )
                monitoring_data.invalidate_monitoring_cache()
                st.rerun()
            except Exception as e:
                st.error("Не вдалося зберегти зміни.")
                st.exception(e)

# ============================================================
# ВІДКЛИКАННЯ ЗАЯВКИ (ТЗ 8.18–8.19 / 15.12)
# ============================================================
#
# Подавач може ВІДКЛИКАТИ власну заявку, але лише доти, доки координатор
# (перша ланка схеми) не здійснив із нею жодних дій. Заявка при цьому
# видаляється з розгляду (зникає з кабінетів усіх ланок), захід знову
# стає доступним для подання, а в журналі дій назавжди залишається
# повний запис про відкликання з усіма поданими даними.

if _no_action_yet and not schemes.is_final_locked(selected_row):
    with st.expander("↩️ Відкликати заявку"):
        st.warning(
            "Відкликання повністю знімає заявку з розгляду. Після цього ви "
            "зможете подати за цим заходом нову заявку у вкладці "
            "«Моніторинг виконання». Запис про відкликання та всі подані "
            "дані назавжди зберігаються в журналі дій."
        )
        _wd_confirm = st.checkbox(
            "Підтверджую, що хочу відкликати цю заявку",
            key=f"withdraw_confirm_{selected_id}",
        )
        _wd_click = st.button(
            "Відкликати заявку",
            use_container_width=True,
            disabled=not _wd_confirm,
            key=f"withdraw_btn_{selected_id}",
        )
        if _wd_click:
            try:
                # 1) Спершу — запис у журнал (він переживає видалення заявки,
                #    бо журнал не має жорсткої прив'язки до рядка заявки).
                _wd_snapshot = (
                    f"Відкликано подавачем. Дані на момент відкликання: "
                    f"код {clean(selected_row.get('strat_code', ''))}; "
                    f"період {clean(selected_row.get('year', ''))}, "
                    f"{clean(selected_row.get('quarter', ''))} квартал; "
                    f"статус виконання «{clean(selected_row.get('status', ''))}»; "
                    f"фактичне значення «{clean(selected_row.get('numeric_value', ''))}»; "
                    f"опис прогресу «{clean(selected_row.get('progress_text', ''))}»; "
                    f"ризики «{clean(selected_row.get('risks', ''))}»."
                )
                write_log(
                    selected_id,
                    "Відкликання заявки подавачем",
                    approval,
                    "Відкликано",
                    _wd_snapshot,
                )
                # 2) Потім — видалення самої заявки.
                supabase.table("monitoring_requests").delete().eq(
                    "id", int(selected_id)
                ).execute()

                monitoring_data.invalidate_monitoring_cache()
                st.success(
                    "Заявку відкликано. Захід знову доступний для подання у "
                    "вкладці «Моніторинг виконання»."
                )
                st.rerun()
            except Exception as e:
                st.error("Не вдалося відкликати заявку.")
                st.exception(e)

# ============================================================
# RESUBMIT
# ============================================================

if approval == "Повернуто на доопрацювання":
    st.markdown(
        '<div class="card"><div class="card-title">Редагування та повторне подання</div>'
        '<div class="card-subtitle">Цей блок доступний тільки для заявок, повернутих на доопрацювання.</div>',
        unsafe_allow_html=True
    )

    # ЄДИНА шкала статусів моделі «Оцінка МіО» (правка П5)
    status_options = list(SUBMISSION_STATUS_OPTIONS)

    current_status = clean(selected_row["status"])
    default_status_index = status_options.index(current_status) if current_status in status_options else 0

    new_status = st.selectbox(
        "Статус виконання",
        status_options,
        index=default_status_index,
        key=f"edit_status_{selected_id}"
    )

    new_value = st.text_input(
        "Фактичне значення",
        value=clean(selected_row["numeric_value"]),
        key=f"edit_value_{selected_id}"
    )

    new_progress = st.text_area(
        "Опис прогресу",
        value=clean(selected_row["progress_text"]),
        height=140,
        key=f"edit_progress_{selected_id}"
    )

    new_risks = st.text_area(
        "Ризики / проблеми / відхилення",
        value=clean(selected_row["risks"]),
        height=140,
        key=f"edit_risks_{selected_id}"
    )

    e1, e2, e3 = st.columns(3)

    with e1:
        new_responsible = st.text_input(
            "ПІБ відповідальної особи",
            value=prefilled_contacts.get("full_name") or clean(selected_row["responsible_person"]),
            key=f"edit_responsible_{selected_id}",
            disabled=True,
        )

    with e2:
        new_phone = st.text_input(
            "Телефон",
            value=prefilled_contacts.get("phone") or clean(selected_row["phone"]),
            key=f"edit_phone_{selected_id}",
            disabled=True,
        )

    with e3:
        new_email = st.text_input(
            "Email",
            value=prefilled_contacts.get("email") or clean(selected_row["email"]),
            key=f"edit_email_{selected_id}",
            disabled=True,
        )

    resubmit = st.button(
        "Повторно подати на погодження",
        use_container_width=True,
        key=f"resubmit_{selected_id}"
    )

    if resubmit:
        errors = []

        if not has_value(new_value):
            errors.append("Заповніть фактичне значення.")

        if not has_value(new_progress):
            errors.append("Заповніть опис прогресу.")

        if not has_value(new_responsible):
            errors.append("Заповніть ПІБ відповідальної особи.")

        if not has_value(new_phone):
            errors.append("Заповніть телефон.")

        if not has_value(new_email):
            errors.append("Заповніть email.")
        elif not valid_email(new_email):
            errors.append("Email має некоректний формат.")

        normalize_value = str(new_value).strip().lower()

        if new_status == "Виконано" and normalize_value in ["0", "ні", "нi", "no"]:
            errors.append("Статус «Виконано» не узгоджується з фактичним значенням 0 / ні.")

        if errors:
            st.error("Повторне подання не виконано:")
            for e in errors:
                st.error(e)
            st.stop()

        try:
            old_version_data = selected_row.to_dict()
            old_version_number = save_request_version(
                selected_id,
                old_version_data,
                created_by="ССП / до редагування"
            )

            # П3: статус першої ланки БЕРЕТЬСЯ ЗІ СХЕМИ заявки, а не жорстко
            # «Очікує погодження» (інакше для схем, де перша ланка не
            # координатор, заявка «зависала» — її не бачив жоден кабінет).
            _resubmit_chain = schemes.parse_chain(selected_row.get("approval_chain"))
            if _resubmit_chain:
                _first_status = schemes.waiting_status_for_stage(_resubmit_chain[0])
            else:
                _first_status = "Очікує погодження"

            update_payload = {
                "status": new_status,
                "numeric_value": new_value,
                "progress_text": new_progress,
                "risks": new_risks,
                "responsible_person": new_responsible,
                "phone": new_phone,
                "email": new_email,
                "approval_status": _first_status,
                "chain_stage": 0,
                # П4: єдиний стандарт часу — UTC
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "admin_comment": ""
            }

            supabase.table("monitoring_requests").update(update_payload).eq("id", int(selected_id)).execute()

            # Миттєве сповіщення першій ланці (як при первинному поданні)
            try:
                if _resubmit_chain:
                    _first = _resubmit_chain[0]
                    notify_events.notify_stage_assigned(
                        _first.get("email", ""), _first.get("name", ""),
                        _first.get("label", ""),
                        clean(selected_row.get("strat_code", "")),
                        clean(selected_row.get("year", "")),
                        clean(selected_row.get("quarter", "")),
                        submitter=clean(new_responsible),
                        kind=clean(selected_row.get("object_kind", "")) or "measure",
                    )
            except Exception:
                pass

            new_version_data = selected_row.to_dict()
            new_version_data.update(update_payload)

            new_version_number = save_request_version(
                selected_id,
                new_version_data,
                created_by="ССП / повторне подання"
            )

            write_log(
                selected_id,
                f"Повторне подання після доопрацювання: версія {old_version_number} → {new_version_number}",
                "Повернуто на доопрацювання",
                _first_status,
                "Заявку повторно подано ССП"
            )

            st.success("Заявку повторно подано на погодження. Попередню і нову версію збережено.")
            monitoring_data.invalidate_monitoring_cache()
            st.rerun()

        except Exception as e:
            st.error("Не вдалося повторно подати заявку.")
            st.exception(e)

    st.markdown('</div>', unsafe_allow_html=True)

else:
    st.markdown('<div class="card"><div class="card-title">Редагування недоступне</div>', unsafe_allow_html=True)

    if approval == "Погоджено":
        st.success("Заявку погоджено. Редагування недоступне.")
    elif approval == "Очікує погодження":
        st.info("Заявка очікує погодження. Редагування буде доступне, якщо її повернуть на доопрацювання.")
    elif approval == "Очікує: Керівник ССП":
        st.info("Заявку передано на підтвердження. Редагування недоступне.")
    else:
        st.info("Редагування для цього статусу недоступне.")

    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# FOOTER
# ============================================================

render_footer()
