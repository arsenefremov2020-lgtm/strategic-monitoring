import streamlit as st
import pandas as pd
from core.db import get_supabase_client
from core.ui import load_css
from core.errors import log_exception
from core.notifications import render_notifications_panel
from core.config import FILE_PATH, SHEET_NAME
from datetime import datetime
from html import escape
import re
from core.auth import init_auth_state, render_login_form
from core.navigation import require_page_access, render_role_page_links

from core.access import (
    filter_requests_for_user,
    get_available_ssp_options_for_user,
    should_lock_ssp_fields,
    user_has_all_ssp_access,
)

st.set_page_config(page_title="Мій кабінет", layout="wide")

init_auth_state()
current_user = render_login_form()
render_role_page_links()

if not require_page_access("Мій кабінет"):
    st.stop()

st.logo(
    "assets/Мінекономіки.png",
    size="large"
)


supabase = get_supabase_client()
load_css()
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

/* ── Таб підписання ── */
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
/* Кнопка підписати — зелена */
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
    if status == "Направлено на підпис":
        return "badge-purple"
    if status == "Очікує погодження":
        return "badge-yellow"
    return "badge-gray"


APPROVAL_FILTER_OPTIONS = [
    "На підпис",
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


def write_log(request_id, action, old_status, new_status, comment, changed_by="Керівник ССП"):
    supabase.table("monitoring_logs").insert({
        "request_id": int(request_id),
        "action": action,
        "old_status": old_status,
        "new_status": new_status,
        "admin_comment": comment,
        "changed_by": changed_by
    }).execute()



# ============================================================
# MAIN DATA
# ============================================================

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

st.markdown("""
<div class="header-box">
    <div class="header-title">Мій кабінет</div>
    <div class="header-subtitle">
        Кабінет керівника самостійного структурного підрозділу. Тут відображаються заявки,
        надіслані на підпис, а також усі інші відомості вашого ССП. Керівник може підписати
        заявку, повернути на доопрацювання в межах ССП або повернути координатору.
    </div>
    <div class="badge-wrap">
        <div class="badge badge-purple">● Роль: Керівник ССП</div>
        <div class="badge">● Дія: підписання / повернення</div>
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

        allowed_indexes = current_user.get("allowed_ssp_indexes", [])
        available_departments = [
            department
            for department in departments
            if any(str(index) in str(department) for index in allowed_indexes)
        ] or available_departments

    if not available_departments:
        st.warning("Для цього користувача немає доступних ССП.")
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
    search = st.text_input("Пошук за ID або кодом заходу")

filtered = df[df["department"].astype(str) == str(selected_department)].copy()

if selected_year != "Усі":
    filtered = filtered[filtered["year"].astype(str) == str(selected_year)]

if selected_status == "На підпис":
    filtered = filtered[filtered["approval_status"].astype(str) == "Направлено на підпис"]
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
to_sign = len(filtered[filtered["approval_status"] == "Направлено на підпис"])
approved = len(filtered[filtered["approval_status"] == "Погоджено"])
waiting = len(filtered[filtered["approval_status"] == "Очікує погодження"])
returned = len(filtered[filtered["approval_status"] == "Повернуто на доопрацювання"])

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Усього відомостей", total)
m2.metric("🟣 На підпис", to_sign)
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

st.markdown('<div class="card"><div class="card-title">Детальний перегляд та підписання</div>', unsafe_allow_html=True)

options = []
for _, row in filtered.iterrows():
    prefix = "🟣 " if row["approval_status"] == "Направлено на підпис" else ""
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

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# SIGN PANEL — доступний лише для "Направлено на підпис"
# ============================================================

if approval == "Направлено на підпис":
    st.markdown("""
    <div class="sign-panel">
        <div class="sign-panel-title">✍️ Дії керівника ССП</div>
        <div class="sign-panel-sub">
            Ознайомтесь із відомостями вище та оберіть одну з дій. При поверненні —
            обов'язково залиште коментар.
        </div>
    </div>
    """, unsafe_allow_html=True)

    leader_comment = st.text_area(
        "Коментар керівника (обов'язковий при поверненні)",
        height=90,
        placeholder="Вкажіть причину повернення або зауваження...",
        key=f"leader_comment_{selected_id}"
    )

    btn_col1, btn_col2, btn_col3 = st.columns(3)

    with btn_col1:
        sign_btn = st.button("✅ Підписати", use_container_width=True,
                             key=f"sign_{selected_id}")
    with btn_col2:
        return_ssp_btn = st.button("↩️ На доопрацювання в межах ССП",
                                   use_container_width=True, key=f"ret_ssp_{selected_id}")
    with btn_col3:
        return_coord_btn = st.button("🔄 На доопрацювання координатору",
                                     use_container_width=True, key=f"ret_coord_{selected_id}")

    # ── Підписати ────────────────────────────────────────────
    if sign_btn:
        try:
            supabase.table("monitoring_requests").update({
                "approval_status": "Погоджено",
                "admin_comment": clean(leader_comment) or "Підписано керівником ССП",
            }).eq("id", selected_id).execute()

            write_log(
                selected_id,
                "Підписання керівником ССП",
                "Направлено на підпис",
                "Погоджено",
                clean(leader_comment) or "Підписано керівником ССП"
            )
            st.success("✅ Заявку підписано. Статус змінено на «Погоджено».")
            st.rerun()
        except Exception as e:
            st.error("Помилка при підписанні.")
            st.exception(e)

    # ── На доопрацювання в межах ССП ─────────────────────────
    if return_ssp_btn:
        if not clean(leader_comment):
            st.error("Вкажіть коментар перед поверненням на доопрацювання.")
        else:
            try:
                supabase.table("monitoring_requests").update({
                    "approval_status": "Повернуто на доопрацювання",
                    "admin_comment": leader_comment,
                }).eq("id", selected_id).execute()

                write_log(
                    selected_id,
                    "Повернення на доопрацювання в межах ССП",
                    "Направлено на підпис",
                    "Повернуто на доопрацювання",
                    leader_comment
                )
                st.warning("↩️ Заявку повернуто відповідальному на доопрацювання в межах ССП.")
                st.rerun()
            except Exception as e:
                st.error("Помилка при поверненні.")
                st.exception(e)

    # ── На доопрацювання координатору ───────────────────────
    if return_coord_btn:
        if not clean(leader_comment):
            st.error("Вкажіть коментар перед поверненням координатору.")
        else:
            try:
                supabase.table("monitoring_requests").update({
                    "approval_status": "Очікує погодження",
                    "admin_comment": leader_comment,
                }).eq("id", selected_id).execute()

                write_log(
                    selected_id,
                    "Повернення координатору на доопрацювання",
                    "Направлено на підпис",
                    "Очікує погодження",
                    leader_comment
                )
                st.info("🔄 Заявку повернуто координатору. Статус змінено на «Очікує погодження».")
                st.rerun()
            except Exception as e:
                st.error("Помилка при поверненні координатору.")
                st.exception(e)

else:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    if approval == "Погоджено":
        st.success("✅ Заявку вже підписано. Жодних дій не потрібно.")
    elif approval == "Очікує погодження":
        st.info("🕐 Заявка ще не надійшла на підпис — очікує погодження координатором.")
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
if logs_df.empty:
    st.info("Історії змін для цієї заявки поки що немає.")
else:
    logs_show = logs_df.rename(columns={
        "changed_at": "Дата", "action": "Дія",
        "old_status": "Попередній статус", "new_status": "Новий статус",
        "admin_comment": "Коментар", "changed_by": "Ким змінено"
    })
    cols = ["Дата", "Дія", "Попередній статус", "Новий статус", "Коментар", "Ким змінено"]
    st.dataframe(logs_show[[c for c in cols if c in logs_show.columns]],
                 use_container_width=True, hide_index=True)
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
