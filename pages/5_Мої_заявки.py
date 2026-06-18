import streamlit as st
import pandas as pd
from core.db import get_supabase_client
from core.ui import load_css
from core.notifications import render_notifications_panel
from core.chat_widget import render_bird_chat
from core.config import FILE_PATH, SHEET_NAME
from datetime import datetime
from html import escape
import re
from core.auth import init_auth_state, render_login_form
from core.navigation import require_page_access, render_role_page_links

from core.access import (
    filter_requests_for_user,
    get_available_ssp_options_for_user,
    get_prefilled_user_contacts,
    should_lock_ssp_fields,
    user_has_all_ssp_access,
)

st.set_page_config(page_title="Мої заявки", layout="wide")

init_auth_state()
current_user = render_login_form()
render_role_page_links()

if not require_page_access("Мої заявки"):
    st.stop()

st.logo(
    "assets/Мінекономіки.png",
    size="large"
)


supabase = get_supabase_client()
load_css()
render_bird_chat("Мої заявки", sender="ССП")
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
    if status == "Направлено на підпис":
        return "badge-blue"
    if status == "Очікує погодження":
        return "badge-yellow"
    return "badge-gray"


ACTIVE_APPROVAL_STATUSES = [
    "Очікує погодження",
    "Повернуто на доопрацювання",
    "Направлено на підпис",
]

APPROVAL_FILTER_OPTIONS = [
    "Активні до розгляду",
    "Усі",
    "Очікує погодження",
    "Повернуто на доопрацювання",
    "Направлено на підпис",
    "Погоджено",
]


# ============================================================
# DATA LOADING
# ============================================================

@st.cache_data
def load_strat_matrix():
    df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=None, engine="openpyxl")
    data = df.iloc[7:].copy()

    result = pd.DataFrame({
        "type_marker": data.iloc[:, 1],
        "code": data.iloc[:, 2],
        "name": data.iloc[:, 3],
        "indicator": data.iloc[:, 5],
        "unit": data.iloc[:, 6],
        "base_2021": data.iloc[:, 7],
        "fact_2024": data.iloc[:, 8],
        "expected_2025": data.iloc[:, 9],
        "target_2026": data.iloc[:, 10],
        "target_2027": data.iloc[:, 11],
        "target_2028": data.iloc[:, 12],
        "department": data.iloc[:, 17],
        "start_date_plan": data.iloc[:, 22],
        "end_date_plan": data.iloc[:, 23],
    })

    result = result.dropna(subset=["code"])
    result["code"] = result["code"].astype(str).str.strip()
    return result


def load_requests():
    response = (
        supabase
        .table("monitoring_requests")
        .select("*")
        .order("submitted_at", desc=True)
        .execute()
    )
    return pd.DataFrame(response.data or [])


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


def write_log(request_id, action, old_status, new_status, admin_comment):
    supabase.table("monitoring_logs").insert({
        "request_id": int(request_id),
        "action": action,
        "old_status": old_status,
        "new_status": new_status,
        "admin_comment": admin_comment,
        "changed_by": "ССП"
    }).execute()


def get_next_version_number(request_id):
    response = (
        supabase
        .table("monitoring_request_versions")
        .select("version_number")
        .eq("request_id", int(request_id))
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        return 1

    return int(response.data[0].get("version_number", 0)) + 1


def save_request_version(request_id, row_data, created_by="ССП"):
    version_number = get_next_version_number(request_id)

    payload = {
        "request_id": int(request_id),
        "version_number": version_number,
        "year": clean(row_data.get("year", "")),
        "quarter": clean(row_data.get("quarter", "")),
        "department": clean(row_data.get("department", "")),
        "responsible_person": clean(row_data.get("responsible_person", "")),
        "phone": clean(row_data.get("phone", "")),
        "email": clean(row_data.get("email", "")),
        "strat_code": clean(row_data.get("strat_code", "")),
        "status": clean(row_data.get("status", "")),
        "progress_text": clean(row_data.get("progress_text", "")),
        "numeric_value": clean(row_data.get("numeric_value", "")),
        "risks": clean(row_data.get("risks", "")),
        "file_names": clean(row_data.get("file_names", "")),
        "file_urls": clean(row_data.get("file_urls", "")),
        "approval_status": clean(row_data.get("approval_status", "")),
        "admin_comment": clean(row_data.get("admin_comment", "")),
        "start_date": clean(row_data.get("start_date", "")),
        "end_date": clean(row_data.get("end_date", "")),
        "created_by": created_by
    }

    supabase.table("monitoring_request_versions").insert(payload).execute()
    return version_number


def load_versions(request_id):
    response = (
        supabase
        .table("monitoring_request_versions")
        .select("*")
        .eq("request_id", int(request_id))
        .order("version_number", desc=False)
        .execute()
    )
    return pd.DataFrame(response.data or [])


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

render_notifications_panel(df, mode="cabinet")

# ============================================================
# FILTERS
# ============================================================

st.markdown(
    '<div class="card"><div class="card-title">Параметри відбору</div>'
    '<div class="card-subtitle">Оберіть самостійний структурний підрозділ, рік і статус погодження.</div>'
    '<div class="filter-panel">',
    unsafe_allow_html=True
)

c1, c2, c3, c4 = st.columns(4)

with c1:
    departments = sorted(df["department"].dropna().astype(str).unique().tolist())

    if user_has_all_ssp_access(current_user):
        available_departments = departments
    else:
        available_departments = get_available_ssp_options_for_user(
            current_user,
            all_options=departments
        )

        # Для випадку, коли в заявках department записаний просто як "30",
        # а в профілі користувача label стоїть як "деп. 30".
        allowed_indexes = current_user.get("allowed_ssp_indexes", [])
        available_departments = [
            department
            for department in departments
            if any(str(index) in str(department) for index in allowed_indexes)
        ] or available_departments

    if not available_departments:
        st.warning("Для цього користувача немає доступних заявок за ССП.")
        st.stop()

    selected_department = st.selectbox(
        "Самостійний структурний підрозділ",
        available_departments,
        index=0,
        disabled=should_lock_ssp_fields(current_user),
    )

with c2:
    years = ["Усі"] + sorted(df["year"].dropna().astype(str).unique().tolist())
    selected_year = st.selectbox("Рік", years)

with c3:
    selected_status = st.selectbox("Статус погодження", APPROVAL_FILTER_OPTIONS, index=0)

with c4:
    search = st.text_input("Пошук за ID або назвою заходу")

filtered = df[df["department"].astype(str) == str(selected_department)].copy()

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
        |
        filtered["strat_code"].astype(str).str.lower().str.contains(sq, na=False)
        |
        filtered["responsible_person"].astype(str).str.lower().str.contains(sq, na=False)
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
approved = len(filtered[filtered["approval_status"] == "Погоджено"])
waiting = len(filtered[filtered["approval_status"] == "Очікує погодження"])
returned = len(filtered[filtered["approval_status"] == "Повернуто на доопрацювання"])
sent_to_sign = len(filtered[filtered["approval_status"] == "Направлено на підпис"])

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Усього відомостей", total)
m2.metric("Очікує", waiting)
m3.metric("Повернуто", returned)
m4.metric("Направлено на підпис", sent_to_sign)
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

st.markdown('</div>', unsafe_allow_html=True)

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
# RESUBMIT
# ============================================================

if approval == "Повернуто на доопрацювання":
    st.markdown(
        '<div class="card"><div class="card-title">Редагування та повторне подання</div>'
        '<div class="card-subtitle">Цей блок доступний тільки для заявок, повернутих на доопрацювання.</div>',
        unsafe_allow_html=True
    )

    status_options = [
        "Не розпочато",
        "Виконується",
        "Виконано",
        "Виконано частково",
        "Прострочено",
        "Потребує уваги"
    ]

    current_status = clean(selected_row["status"])
    default_status_index = status_options.index(current_status) if current_status in status_options else 1

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

            update_payload = {
                "status": new_status,
                "numeric_value": new_value,
                "progress_text": new_progress,
                "risks": new_risks,
                "responsible_person": new_responsible,
                "phone": new_phone,
                "email": new_email,
                "approval_status": "Очікує погодження",
                "submitted_at": datetime.now().isoformat(),
                "admin_comment": ""
            }

            supabase.table("monitoring_requests").update(update_payload).eq("id", int(selected_id)).execute()

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
                "Очікує погодження",
                "Заявку повторно подано ССП"
            )

            st.success("Заявку повторно подано на погодження. Попередню і нову версію збережено.")
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
    elif approval == "Направлено на підпис":
        st.info("Заявку направлено на підпис. Редагування недоступне.")
    else:
        st.info("Редагування для цього статусу недоступне.")

    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# FOOTER
# ============================================================

st.markdown("""
<div class="footer">
    <strong>Розроблено департаментом стратегічного планування та макроекономічного прогнозування</strong><br>
    Версія DEMO 1.4 | 2026 | Внутрішня система моніторингу стратегічного плану
</div>
""", unsafe_allow_html=True)
