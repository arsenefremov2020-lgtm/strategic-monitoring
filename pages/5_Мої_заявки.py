import streamlit as st
import pandas as pd
from core.period_locks import is_period_locked
from core.data_types import prepare_monitoring_payload
from core.db import fetch_all, get_supabase_client
from core.errors import log_cosmetic_error, show_incident, show_warning
from core.notifications import render_notifications_panel
from core.config import FILE_PATH, SHEET_NAME
from core.excel_loader import read_excel_sheet
from datetime import datetime, timezone
from html import escape
import re
from core.page_setup import page_setup, render_footer
from core.timeutils import now_kyiv
from core.ui import render_request_timeline
from core.stage4 import (
    format_kyiv_datetime,
    human_versions_table,
    render_version_comparison,
    style_status_columns,
)
from core.strategic_data import load_strat_matrix as core_load_strat_matrix
from core import monitoring_data
from core import notify_events
from core.statuses import SUBMISSION_STATUS_OPTIONS

from core import approval_schemes as schemes
from core.transitions import (
    TransitionRejected,
    resubmit_request,
    withdraw_request as atomic_withdraw_request,
)
from core.drafts import (
    clear_draft_recovery,
    editor_generation,
    forget_draft_state,
    load_drafts_for_keys,
    make_draft_key,
    queue_draft,
    render_draft_autosave_worker,
    render_draft_recovery,
    save_draft_now,
)
from core.submission_ui import render_submission_notice, set_submission_notice
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
    background: #F7F9FC;
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
    color: #61708A;
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 8px;
}

.header-box, .card {
    background: rgba(255,255,255,0.94);
    border: 1px solid #DCE4F0;
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 18px;
    box-shadow: 0 8px 24px rgba(15,23,42,0.06);
}

.header-title {
    font-size: 32px;
    font-weight: 900;
    color: #132238;
    margin-bottom: 8px;
}

.header-subtitle, .card-subtitle {
    font-size: 15px;
    color: #61708A;
    line-height: 1.55;
}

.card-title {
    font-size: 21px;
    font-weight: 900;
    color: #132238;
    margin-bottom: 8px;
}

.filter-panel {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-radius: 18px;
    padding: 18px 20px 10px 20px;
    margin-top: 12px;
    box-shadow: 0 10px 24px rgba(15,23,42,0.07);
}

[data-testid="stMain"] div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stMain"] div[data-testid="stTextInput"] input,
[data-testid="stMain"] div[data-testid="stTextArea"] textarea {
    background-color: #EAF1FF !important;
    border: 1px solid #BFD3F2 !important;
    border-radius: 10px !important;
    box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.08) !important;
}

[data-testid="stMain"] div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stMain"] div[data-testid="stTextInput"] input {
    min-height: 43px !important;
}

[data-testid="stMain"] div[data-testid="stSelectbox"] label,
[data-testid="stMain"] div[data-testid="stTextInput"] label,
[data-testid="stMain"] div[data-testid="stTextArea"] label {
    font-weight: 750 !important;
    color: #132238 !important;
}

.badge-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 12px 0;
}

.badge {
    background: #EAF1FF;
    border: 1px solid #BFD3F2;
    color: #005BBB;
    border-radius: 999px;
    padding: 7px 11px;
    font-size: 13px;
    font-weight: 800;
}

.badge-green {
    background: #E4F5EC;
    border: 1px solid #1E9E57;
    color: #0C713A;
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

.badge-gray {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    color: #61708A;
}

.badge-blue {
    background: #E3EDFF;
    border: 1px solid #BFD3F2;
    color: #032A63;
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
    border: 1px solid #DCE4F0;
    overflow-wrap: anywhere;
}

.info-card-blue {
    background: #EAF1FF;
    border-color: #BFD3F2;
}

.info-card-green {
    background: #E4F5EC;
    border-color: #1E9E57;
}

.info-card-yellow {
    background: #FDF3D8;
    border-color: #F4B400;
}

.info-card-red {
    background: #FBE5E5;
    border-color: #DC4A4A;
}

.info-card-gray {
    background: #F7F9FC;
    border-color: #DCE4F0;
}

.info-label {
    color: #61708A;
    font-size: 12px;
    margin-bottom: 7px;
    line-height: 1.35;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    font-weight: 750;
}

.info-value {
    color: #132238;
    font-weight: 900;
    font-size: 15px;
    line-height: 1.4;
}

.step-box {
    background: #EAF1FF;
    border: 1px solid #BFD3F2;
    border-radius: 14px;
    padding: 14px 16px;
    margin: 10px 0;
}

.version-box {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-radius: 14px;
    padding: 14px 16px;
    margin: 10px 0;
}

.version-title {
    color: #132238;
    font-weight: 900;
    font-size: 15px;
    margin-bottom: 6px;
}

.version-text {
    color: #61708A;
    font-size: 13px;
    line-height: 1.45;
}

.comment-box {
    background: #FDF3D8;
    border: 1px solid #FF7A45;
    color: #FF7A45;
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
    border: 1px solid #DCE4F0;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

[data-testid="stMain"] div.stButton > button {
    border-radius: 14px;
    padding: 12px 18px;
    font-weight: 900;
    border: 1px solid #BFD3F2;
    background: #EAF1FF !important;
    color: #005BBB !important;
    box-shadow: 0 8px 18px rgba(37,99,235,0.10);
}

[data-testid="stMain"] div.stButton > button:hover {
    filter: brightness(1.03);
    transform: translateY(-1px);
    border-color: #BFD3F2;
}

.footer {
    text-align: center;
    color: #8A96A8;
    font-size: clamp(10px, 0.9vw, 12px);
    margin-top: 40px;
    padding: 18px 0 10px;
    border-top: 1px solid #DCE4F0;
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
    except Exception as exc:
        log_cosmetic_error("Нормалізація значення у Мої заявки", exc)
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
    rows = fetch_all(
        "monitoring_logs",
        "*",
        filters=[("eq", "request_id", int(request_id))],
        order=("changed_at", True),
    )
    return pd.DataFrame(rows)



def _actor_identity(role_label):
    """Повний підпис дії для журналу: роль + ПІБ + email поточного користувача."""
    try:
        name = str((current_user or {}).get("full_name", "")).strip()
        email = str((current_user or {}).get("email", "")).strip()
    except Exception as exc:
        log_cosmetic_error("Формування підпису користувача у Мої заявки", exc)
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


def _apply_widget_draft_once(context_key, content, mapping):
    marker_key = f"draft_widgets_applied::{context_key}"
    if not content or st.session_state.get(marker_key):
        return
    for content_key, widget_key in mapping.items():
        if content_key in content:
            st.session_state[widget_key] = content[content_key]
    st.session_state[marker_key] = True


def _clear_widget_draft_marker(context_key):
    st.session_state.pop(f"draft_widgets_applied::{context_key}", None)


# Спільна логіка версіювання винесена в core/versioning.py (пункт 3 ТЗ:
# та сама логіка тепер потрібна і в 1_Мій_кабінет.py, і в
# 3_Адміністрування.py для коригування супер-адміном закритих заявок).
from core.versioning import coordinator_stage_index, load_versions


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

render_submission_notice()

if df.empty:
    st.warning("Поки що немає поданих відомостей.")
    render_footer()
    st.stop()

required_cols = [
    "id", "year", "quarter", "department", "responsible_person", "phone", "email",
    "strat_code", "status", "progress_text", "numeric_value", "risks",
    "submitted_at", "approval_status", "admin_comment", "file_names", "file_urls",
    "start_date", "end_date", "updated_at"
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

filtered["_visual_status"] = filtered.apply(
    lambda row: "Не настав час" if is_period_locked(row.get("year"), row.get("quarter")) else row.get("status", ""),
    axis=1,
)

st.caption(f"Знайдено відомостей: {len(filtered)}")
st.markdown('</div></div>', unsafe_allow_html=True)

if filtered.empty:
    st.info("За обраними параметрами відбору відомостей не знайдено.")
    render_footer()
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
    "_visual_status": "Статус виконання",
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
        <span style="color:#61708A;">Індикатор: {display_text(mi["indicator"])}</span><br>
        <span style="color:#61708A;">Одиниця виміру: {display_text(mi["unit"])}</span><br>
        <span style="color:#61708A;">Терміни: {display_text(mi["start_date_plan"])} — {display_text(mi["end_date_plan"])}</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown(f"""
<div class="info-grid">
    <div class="info-card info-card-blue">
        <div class="info-label">Статус виконання</div>
        <div class="info-value">{display_text(selected_row["_visual_status"])}</div>
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
    _now = now_kyiv()

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
        _action = ("✅ Дій від вас не потрібно", "#E4F5EC", "#1E9E57", "#0C713A")
    elif approval == "Повернуто на доопрацювання":
        _holder = "Заявка у вас (повернута на доопрацювання)"
        _action = ("✍️ Потребує вашої дії — виправте дані та подайте повторно",
                   "#FDF3D8", "#FF7A45", "#FF7A45")
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
                   "#EAF1FF", "#BFD3F2", "#032A63")
    else:
        _holder = "На розгляді координатора"
        _action = ("⏳ На розгляді — дій від вас не потрібно",
                   "#EAF1FF", "#BFD3F2", "#032A63")

    st.markdown(
        f'<div style="display:flex;flex-wrap:wrap;gap:10px;margin:6px 0 10px 0;">'
        f'<div style="background:#F7F9FC;border:1px solid #DCE4F0;border-radius:10px;'
        f'padding:8px 12px;font-size:13px;font-weight:700;color:#132238;">'
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
# ЄДИНИЙ компонент таймлайну для всієї системи (core/ui.py, ТЗ 16.13)
render_request_timeline(logs_df)
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

    _latest_numeric = clean(latest_version.get("numeric_value", ""))
    _latest_textual = clean(latest_version.get("value_text", ""))
    _latest_fact = _latest_numeric or _latest_textual or "—"
    st.markdown(f"""
    <div class="version-box">
        <div class="version-title">Остання збережена версія: №{display_text(latest_version.get("version_number", ""))}</div>
        <div class="version-text">
            Створено: {format_kyiv_datetime(latest_version.get("created_at", ""))}<br>
            Ким створено: {display_text(latest_version.get("created_by", ""))}<br>
            Статус погодження: {display_text(latest_version.get("approval_status", ""))}<br>
            Статус виконання: {display_text(latest_version.get("status", ""))}<br>
            Фактичне значення: {display_text(_latest_fact)}
        </div>
    </div>
    """, unsafe_allow_html=True)

    versions_show = human_versions_table(versions_df)
    st.dataframe(
        style_status_columns(
            versions_show,
            ["Статус погодження", "Статус виконання"],
        ),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Порівняти дві версії заявки", expanded=False):
        render_version_comparison(
            versions_df,
            key_prefix=f"my_requests_versions_{selected_id}",
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

        _de_chain = schemes.parse_chain(selected_row.get("approval_chain"))
        _de_coord_idx = (
            min(coordinator_stage_index(_de_chain), _request_stage_idx)
            if _de_chain else 0
        )
        _de_draft_context = f"direct_edit::{selected_id}"
        _de_draft_key = make_draft_key(
            clean(selected_row.get("object_kind")) or "measure",
            selected_row.get("strat_code"), selected_row.get("year"),
            selected_row.get("quarter"), mode="direct_edit", request_id=int(selected_id),
        )
        _de_draft_rows = load_drafts_for_keys(
            clean(current_user.get("email")), [_de_draft_key]
        )
        _de_restored_map = render_draft_recovery(
            context_key=_de_draft_context,
            user_email=clean(current_user.get("email")),
            draft_rows=_de_draft_rows,
        )
        _de_restored = _de_restored_map.get(_de_draft_key, {})

        _de_generation = editor_generation(_de_draft_context)
        _de_status_key = f"direct_edit_status_{selected_id}_{_de_generation}"
        _de_value_key = f"direct_edit_value_{selected_id}_{_de_generation}"
        _de_progress_key = f"direct_edit_progress_{selected_id}_{_de_generation}"
        _de_risks_key = f"direct_edit_risks_{selected_id}_{_de_generation}"
        _apply_widget_draft_once(
            _de_draft_context, _de_restored,
            {
                "status": _de_status_key,
                "numeric_value": _de_value_key,
                "progress_text": _de_progress_key,
                "risks": _de_risks_key,
            },
        )

        _de_status_options = list(SUBMISSION_STATUS_OPTIONS)
        _de_current_status = clean(selected_row["status"])
        _de_status_index = (
            _de_status_options.index(_de_current_status)
            if _de_current_status in _de_status_options else 0
        )

        de_new_status = st.selectbox(
            "Статус виконання", _de_status_options, index=_de_status_index,
            key=_de_status_key,
        )
        de_new_value = st.text_input(
            "Фактичне значення", value=clean(selected_row["numeric_value"]),
            key=_de_value_key,
        )
        de_new_progress = st.text_area(
            "Опис прогресу", value=clean(selected_row["progress_text"]),
            height=120, key=_de_progress_key,
        )
        de_new_risks = st.text_area(
            "Ризики / проблеми / відхилення", value=clean(selected_row["risks"]),
            height=120, key=_de_risks_key,
        )

        _de_draft_content = {
            "status": de_new_status,
            "numeric_value": de_new_value,
            "progress_text": de_new_progress,
            "risks": de_new_risks,
        }
        _de_has_changes = (
            de_new_status != clean(selected_row.get("status"))
            or clean(de_new_value) != clean(selected_row.get("numeric_value"))
            or clean(de_new_progress) != clean(selected_row.get("progress_text"))
            or clean(de_new_risks) != clean(selected_row.get("risks"))
        )
        if (not _de_draft_rows or _de_restored_map) and (_de_has_changes or _de_restored_map):
            queue_draft(
                clean(current_user.get("email")), _de_draft_key, _de_draft_content
            )
        render_draft_autosave_worker()

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
                for error in de_errors:
                    st.error(error)
            else:
                update_payload = prepare_monitoring_payload({
                    "status": de_new_status,
                    "numeric_value": de_new_value,
                    "progress_text": de_new_progress,
                    "risks": de_new_risks,
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                    "admin_comment": "",
                    "log_comment": (
                        "Відредаговано без повернення на доопрацювання; "
                        "надіслано координатору повторно."
                    ),
                })
                try:
                    result = resubmit_request(
                        request_id=int(selected_id),
                        expected_updated_at=clean(selected_row.get("updated_at")),
                        expected_status=approval,
                        expected_chain_stage=int(_request_stage_idx),
                        target_chain_stage=int(_de_coord_idx),
                        payload=update_payload,
                        mode="stage_edit",
                        action="Пряме редагування поданих даних",
                        user=current_user,
                        created_by_before="ССП / до прямого редагування",
                        created_by_after="ССП / пряме редагування",
                        draft_email=clean(current_user.get("email")),
                        draft_key=_de_draft_key,
                    )
                    forget_draft_state([_de_draft_key])

                    if _de_chain:
                        _de_coord_stage = _de_chain[_de_coord_idx]
                        try:
                            notify_events.notify_stage_assigned(
                                _de_coord_stage.get("email", ""),
                                _de_coord_stage.get("name", ""),
                                _de_coord_stage.get("label", ""),
                                clean(selected_row.get("strat_code", "")),
                                clean(selected_row.get("year", "")),
                                clean(selected_row.get("quarter", "")),
                                submitter=clean(selected_row.get("responsible_person", "")),
                                kind=clean(selected_row.get("object_kind", "")) or "measure",
                            )
                        except Exception as notify_exc:
                            show_warning(
                                "Зміни збережено, але координатору не відправлено миттєвий лист.",
                                notify_exc,
                                "Email після прямого редагування подавачем",
                            )

                    clear_draft_recovery(_de_draft_context)
                    _clear_widget_draft_marker(_de_draft_context)
                    set_submission_notice(
                        first_stage_label=(
                            result.data.get("first_stage_label")
                            or (_de_chain[_de_coord_idx].get("label") if _de_chain else "Координатор")
                        ),
                        codes=[clean(selected_row.get("strat_code"))],
                        repeated=True,
                    )
                    monitoring_data.invalidate_monitoring_cache()
                    st.rerun()
                except TransitionRejected as exc:
                    if exc.code in {"concurrent_change", "state_changed"}:
                        try:
                            save_draft_now(
                                clean(current_user.get("email")),
                                _de_draft_key,
                                _de_draft_content,
                            )
                        except Exception as draft_exc:
                            show_warning(
                                "Чернетку змін не вдалося зберегти.",
                                draft_exc,
                                "Чернетка після конфлікту прямого редагування",
                            )
                    st.error(exc.message)
                except Exception as exc:
                    try:
                        save_draft_now(
                            clean(current_user.get("email")),
                            _de_draft_key,
                            _de_draft_content,
                        )
                    except Exception as draft_exc:
                        show_warning(
                            "Чернетку змін не вдалося зберегти.",
                            draft_exc,
                            "Чернетка після помилки прямого редагування",
                        )
                    show_incident(exc, context="Атомарне пряме редагування заявки подавачем")
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
                # Атомарне м’яке відкликання: рядок, версія та журнал
                # зберігаються, а заявка зникає лише з робочих вибірок.
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
                atomic_withdraw_request(
                    request_id=int(selected_id),
                    expected_status=approval,
                    expected_chain_stage=int(_request_stage_idx),
                    comment=_wd_snapshot,
                    user=current_user,
                )

                monitoring_data.invalidate_monitoring_cache()
                st.success(
                    "Заявку відкликано. Захід знову доступний для подання у "
                    "вкладці «Моніторинг виконання»."
                )
                st.rerun()
            except TransitionRejected as exc:
                st.error(exc.message)
            except Exception as exc:
                show_incident(exc, context="Атомарне відкликання заявки")

# ============================================================
# RESUBMIT
# ============================================================

if approval == "Повернуто на доопрацювання":
    st.markdown(
        '<div class="card"><div class="card-title">Редагування та повторне подання</div>'
        '<div class="card-subtitle">Цей блок доступний тільки для заявок, повернутих на доопрацювання.</div>',
        unsafe_allow_html=True
    )

    _resubmit_chain = schemes.parse_chain(selected_row.get("approval_chain"))
    _resubmit_draft_context = f"resubmit::{selected_id}"
    _resubmit_draft_key = make_draft_key(
        clean(selected_row.get("object_kind")) or "measure",
        selected_row.get("strat_code"), selected_row.get("year"),
        selected_row.get("quarter"), mode="resubmit", request_id=int(selected_id),
    )
    _resubmit_draft_rows = load_drafts_for_keys(
        clean(current_user.get("email")), [_resubmit_draft_key]
    )
    _resubmit_restored_map = render_draft_recovery(
        context_key=_resubmit_draft_context,
        user_email=clean(current_user.get("email")),
        draft_rows=_resubmit_draft_rows,
    )
    _resubmit_restored = _resubmit_restored_map.get(_resubmit_draft_key, {})

    _resubmit_generation = editor_generation(_resubmit_draft_context)
    _resubmit_widget_keys = {
        "status": f"edit_status_{selected_id}_{_resubmit_generation}",
        "numeric_value": f"edit_value_{selected_id}_{_resubmit_generation}",
        "progress_text": f"edit_progress_{selected_id}_{_resubmit_generation}",
        "risks": f"edit_risks_{selected_id}_{_resubmit_generation}",
        "responsible_person": f"edit_responsible_{selected_id}_{_resubmit_generation}",
        "phone": f"edit_phone_{selected_id}_{_resubmit_generation}",
        "email": f"edit_email_{selected_id}_{_resubmit_generation}",
    }
    _apply_widget_draft_once(
        _resubmit_draft_context, _resubmit_restored, _resubmit_widget_keys
    )

    status_options = list(SUBMISSION_STATUS_OPTIONS)
    current_status = clean(selected_row["status"])
    default_status_index = status_options.index(current_status) if current_status in status_options else 0

    new_status = st.selectbox(
        "Статус виконання", status_options, index=default_status_index,
        key=_resubmit_widget_keys["status"]
    )
    new_value = st.text_input(
        "Фактичне значення", value=clean(selected_row["numeric_value"]),
        key=_resubmit_widget_keys["numeric_value"]
    )
    new_progress = st.text_area(
        "Опис прогресу", value=clean(selected_row["progress_text"]), height=140,
        key=_resubmit_widget_keys["progress_text"]
    )
    new_risks = st.text_area(
        "Ризики / проблеми / відхилення", value=clean(selected_row["risks"]), height=140,
        key=_resubmit_widget_keys["risks"]
    )

    e1, e2, e3 = st.columns(3)
    with e1:
        new_responsible = st.text_input(
            "ПІБ відповідальної особи",
            value=prefilled_contacts.get("full_name") or clean(selected_row["responsible_person"]),
            key=_resubmit_widget_keys["responsible_person"], disabled=True,
        )
    with e2:
        new_phone = st.text_input(
            "Телефон", value=prefilled_contacts.get("phone") or clean(selected_row["phone"]),
            key=_resubmit_widget_keys["phone"], disabled=True,
        )
    with e3:
        new_email = st.text_input(
            "Email", value=prefilled_contacts.get("email") or clean(selected_row["email"]),
            key=_resubmit_widget_keys["email"], disabled=True,
        )

    _resubmit_draft_content = {
        "status": new_status,
        "numeric_value": new_value,
        "progress_text": new_progress,
        "risks": new_risks,
        "responsible_person": new_responsible,
        "phone": new_phone,
        "email": new_email,
    }
    _resubmit_has_changes = (
        new_status != clean(selected_row.get("status"))
        or clean(new_value) != clean(selected_row.get("numeric_value"))
        or clean(new_progress) != clean(selected_row.get("progress_text"))
        or clean(new_risks) != clean(selected_row.get("risks"))
        or clean(new_responsible) != clean(selected_row.get("responsible_person"))
        or clean(new_phone) != clean(selected_row.get("phone"))
        or clean(new_email).lower() != clean(selected_row.get("email")).lower()
    )
    if (not _resubmit_draft_rows or _resubmit_restored_map) and (
        _resubmit_has_changes or _resubmit_restored_map
    ):
        queue_draft(
            clean(current_user.get("email")),
            _resubmit_draft_key,
            _resubmit_draft_content,
        )
    render_draft_autosave_worker()

    resubmit = st.button(
        "Повторно подати на погодження", use_container_width=True,
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
            for error in errors:
                st.error(error)
        else:
            update_payload = prepare_monitoring_payload({
                "status": new_status,
                "numeric_value": new_value,
                "progress_text": new_progress,
                "risks": new_risks,
                "responsible_person": new_responsible,
                "phone": new_phone,
                "email": new_email,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "admin_comment": "",
                "log_comment": "Заявку повторно подано ССП",
            })
            try:
                result = resubmit_request(
                    request_id=int(selected_id),
                    expected_updated_at=clean(selected_row.get("updated_at")),
                    expected_status="Повернуто на доопрацювання",
                    expected_chain_stage=int(_request_stage_idx),
                    target_chain_stage=0,
                    payload=update_payload,
                    mode="returned",
                    action="Повторне подання після доопрацювання",
                    user=current_user,
                    created_by_before="ССП / до повторного подання",
                    created_by_after="ССП / повторне подання",
                    draft_email=clean(current_user.get("email")),
                    draft_key=_resubmit_draft_key,
                )
                forget_draft_state([_resubmit_draft_key])

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
                except Exception as notify_exc:
                    show_warning(
                        "Заявку повторно подано, але першій ланці не відправлено миттєвий лист.",
                        notify_exc,
                        "Email після повторного подання заявки",
                    )

                clear_draft_recovery(_resubmit_draft_context)
                _clear_widget_draft_marker(_resubmit_draft_context)
                set_submission_notice(
                    first_stage_label=(
                        result.data.get("first_stage_label")
                        or (_resubmit_chain[0].get("label") if _resubmit_chain else "Координатор")
                    ),
                    codes=[clean(selected_row.get("strat_code"))],
                    repeated=True,
                )
                monitoring_data.invalidate_monitoring_cache()
                st.rerun()
            except TransitionRejected as exc:
                if exc.code in {"concurrent_change", "state_changed"}:
                    try:
                        save_draft_now(
                            clean(current_user.get("email")),
                            _resubmit_draft_key,
                            _resubmit_draft_content,
                        )
                    except Exception as draft_exc:
                        show_warning(
                            "Чернетку змін не вдалося зберегти.",
                            draft_exc,
                            "Чернетка після конфлікту повторного подання",
                        )
                st.error(exc.message)
            except Exception as exc:
                try:
                    save_draft_now(
                        clean(current_user.get("email")),
                        _resubmit_draft_key,
                        _resubmit_draft_content,
                    )
                except Exception as draft_exc:
                    show_warning(
                        "Чернетку змін не вдалося зберегти.",
                        draft_exc,
                        "Чернетка після помилки повторного подання",
                    )
                show_incident(exc, context="Атомарне повторне подання заявки після доопрацювання")

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
