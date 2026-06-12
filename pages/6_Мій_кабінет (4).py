import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime
from html import escape
import re

st.set_page_config(page_title="Мій кабінет", layout="wide")

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

/* ── Floating chat button ── */
.chat-fab {
    position: fixed;
    bottom: 32px;
    right: 32px;
    z-index: 9999;
    width: 62px;
    height: 62px;
    border-radius: 50%;
    background: linear-gradient(135deg, #1e40af, #3b82f6);
    box-shadow: 0 8px 24px rgba(37,99,235,0.40);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 3px solid #fff;
    transition: transform 0.2s, box-shadow 0.2s;
    user-select: none;
}
.chat-fab:hover {
    transform: scale(1.08);
    box-shadow: 0 12px 30px rgba(37,99,235,0.50);
}
.chat-fab svg {
    width: 36px;
    height: 36px;
}
.chat-fab-badge {
    position: absolute;
    top: -2px;
    right: -2px;
    background: #dc2626;
    color: #fff;
    font-size: 10px;
    font-weight: 900;
    border-radius: 99px;
    padding: 2px 5px;
    min-width: 18px;
    text-align: center;
    border: 2px solid #fff;
}

/* ── Chat window ── */
.chat-window {
    position: fixed;
    bottom: 108px;
    right: 32px;
    z-index: 9998;
    width: 380px;
    background: #fff;
    border: 1px solid #d8dee9;
    border-radius: 20px;
    box-shadow: 0 20px 60px rgba(15,23,42,0.18);
    display: flex;
    flex-direction: column;
    overflow: hidden;
}
.chat-header {
    background: linear-gradient(135deg, #1e40af, #3b82f6);
    color: #fff;
    padding: 14px 18px;
    font-weight: 900;
    font-size: 15px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.chat-tabs {
    display: flex;
    border-bottom: 1px solid #e2e8f0;
    background: #f8fafc;
}
.chat-tab {
    flex: 1;
    text-align: center;
    padding: 10px 6px;
    font-size: 12px;
    font-weight: 700;
    color: #64748b;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    transition: all 0.15s;
}
.chat-tab.active {
    color: #1e40af;
    border-bottom-color: #3b82f6;
    background: #fff;
}
.chat-messages {
    height: 260px;
    overflow-y: auto;
    padding: 14px 14px 8px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    background: #f8fafc;
}
.msg-row { display: flex; align-items: flex-end; gap: 8px; }
.msg-row.me { flex-direction: row-reverse; }
.msg-avatar {
    width: 30px; height: 30px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 900;
    flex-shrink: 0;
}
.msg-bubble {
    max-width: 72%;
    padding: 9px 13px;
    border-radius: 14px;
    font-size: 13px;
    line-height: 1.45;
    word-break: break-word;
}
.msg-row.me .msg-bubble {
    background: linear-gradient(135deg, #1e40af, #3b82f6);
    color: #fff;
    border-bottom-right-radius: 4px;
}
.msg-row.other .msg-bubble {
    background: #fff;
    border: 1px solid #e2e8f0;
    color: #1e293b;
    border-bottom-left-radius: 4px;
}
.msg-meta {
    font-size: 10px;
    color: #94a3b8;
    margin-top: 3px;
    white-space: nowrap;
}
.msg-row.me .msg-meta { text-align: right; }
.chat-input-area {
    display: flex;
    gap: 8px;
    padding: 10px 12px;
    border-top: 1px solid #e2e8f0;
    background: #fff;
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


# ── Chat helpers ─────────────────────────────────────────────────────────────

CHAT_CHANNELS = {
    "coordinator": "Координатор",
    "responsible": "Відповідальний від ССП",
    "group": "Груповий чат",
}


def load_chat_messages(channel: str):
    try:
        response = (
            supabase
            .table("chat_messages")
            .select("*")
            .eq("channel", channel)
            .order("created_at", desc=False)
            .limit(100)
            .execute()
        )
        return response.data or []
    except Exception:
        return []


def send_chat_message(channel: str, sender: str, text: str):
    supabase.table("chat_messages").insert({
        "channel": channel,
        "sender": sender,
        "text": text,
        "created_at": datetime.now().isoformat(),
    }).execute()


# ============================================================
# MAIN DATA
# ============================================================

df = load_requests()
strat_df = load_strat_matrix()

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
        <div class="badge">● Суперечки: чат з пташкою →</div>
    </div>
</div>
""", unsafe_allow_html=True)

required_cols = [
    "id", "year", "quarter", "department", "responsible_person", "phone", "email",
    "strat_code", "status", "progress_text", "numeric_value", "risks",
    "submitted_at", "approval_status", "admin_comment", "file_names", "file_urls",
    "start_date", "end_date"
]
for col in required_cols:
    if col not in df.columns:
        df[col] = ""

if df.empty:
    st.warning("Поки що немає поданих відомостей.")
    st.stop()

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
    selected_department = st.selectbox("Самостійний структурний підрозділ", departments)

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
# FLOATING CHAT WITH BIRD
# Рендеримо FAB + чат-вікно через st.markdown (position:fixed
# в головному документі, не в iframe) + JS через components.html
# для прямих викликів Supabase REST без rerun.
# ============================================================

import streamlit.components.v1 as _components

# ── Завантажуємо повідомлення всіх каналів при рендері ──
def _load_all_channels():
    result = {}
    for ch in ["coordinator", "responsible", "group"]:
        try:
            resp = supabase.table("chat_messages").select("*") \
                .eq("channel", ch).order("created_at", desc=False).limit(80).execute()
            result[ch] = resp.data or []
        except Exception:
            result[ch] = []
    return result

_all_msgs = _load_all_channels()

def _msgs_to_js(msgs):
    import json
    safe = []
    for m in msgs:
        safe.append({
            "sender": str(m.get("sender", "")),
            "text":   str(m.get("text", "")),
            "ts":     str(m.get("created_at", ""))[:16].replace("T", " "),
        })
    return json.dumps(safe, ensure_ascii=False)

_msgs_coord = _msgs_to_js(_all_msgs["coordinator"])
_msgs_resp  = _msgs_to_js(_all_msgs["responsible"])
_msgs_group = _msgs_to_js(_all_msgs["group"])

_SUPABASE_URL = st.secrets["SUPABASE_URL"]
_SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# ── FAB + Chat: components.html з iframe-розтяжкою ──
# <script> в st.markdown вирізається React-ом.
# Рішення: components.html (справжній iframe) + CSS хак що розтягує
# цей iframe на весь viewport через st.markdown <style>.

import streamlit.components.v1 as _components

def _load_all_channels():
    result = {}
    for ch in ["coordinator", "responsible", "group"]:
        try:
            resp = supabase.table("chat_messages").select("*") \
                .eq("channel", ch).order("created_at", desc=False).limit(80).execute()
            result[ch] = resp.data or []
        except Exception:
            result[ch] = []
    return result

_all_msgs = _load_all_channels()

def _msgs_to_js(msgs):
    import json
    safe = []
    for m in msgs:
        safe.append({
            "sender": str(m.get("sender", "")),
            "text":   str(m.get("text", "")),
            "ts":     str(m.get("created_at", ""))[:16].replace("T", " "),
        })
    return json.dumps(safe, ensure_ascii=False)

_msgs_coord = _msgs_to_js(_all_msgs["coordinator"])
_msgs_resp  = _msgs_to_js(_all_msgs["responsible"])
_msgs_group = _msgs_to_js(_all_msgs["group"])

_SUPABASE_URL = st.secrets["SUPABASE_URL"]
_SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# Крок 1: CSS через st.markdown — <style> тег НЕ вирізається React-ом.
# Знаходимо iframe що містить наш компонент і розтягуємо його.
# Streamlit рендерить components.html в <iframe> з data-testid="stIframe"
# або просто iframe всередині div.element-container.
st.markdown("""
<style>
/* Розтягуємо iframe чату на весь екран.
   Streamlit вставляє компоненти як iframe без фіксованого title.
   Шукаємо через батьківський div з data-testid="stCustomComponentV1" */
div[data-testid="stCustomComponentV1"] iframe,
div[data-testid="stCustomComponentV1"] > iframe {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
    z-index: 999990 !important;
    pointer-events: none !important;
    border: none !important;
    background: transparent !important;
}
</style>
""", unsafe_allow_html=True)

# Крок 2: сам iframe з усім чатом всередині
_chat_html = f"""<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="utf-8">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{
  background: transparent !important;
  overflow: hidden;
  width: 100%; height: 100%;
  /* body не перехоплює кліки — лише FAB і вікно чату */
  pointer-events: none;
}}
#bird-fab {{
  pointer-events: auto;
  position: fixed;
  bottom: 90px; right: 28px;
  width: 60px; height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg,#1e40af,#3b82f6);
  box-shadow: 0 8px 28px rgba(37,99,235,.5);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  border: 3px solid #fff;
  z-index: 10;
  transition: transform .2s, box-shadow .2s;
}}
#bird-fab:hover {{ transform: scale(1.1); box-shadow: 0 12px 36px rgba(37,99,235,.6); }}
#bird-fab svg {{ width: 36px; height: 36px; }}

#bird-chat {{
  pointer-events: auto;
  position: fixed;
  bottom: 164px; right: 28px;
  width: 370px; max-height: 500px;
  background: #fff;
  border: 1px solid #d8dee9;
  border-radius: 20px;
  box-shadow: 0 20px 60px rgba(15,23,42,.2);
  display: none; flex-direction: column; overflow: hidden;
  z-index: 10;
  font-family: 'Helvetica Neue', Arial, sans-serif;
}}
#bird-chat.open {{ display: flex; }}

#bch {{
  background: linear-gradient(135deg,#1e40af,#3b82f6);
  color: #fff; padding: 12px 16px;
  font-weight: 900; font-size: 14px;
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0;
}}
#bcx {{ cursor: pointer; font-size: 18px; opacity: .75; padding: 2px 6px; border-radius: 4px; }}
#bcx:hover {{ opacity: 1; background: rgba(255,255,255,.2); }}

#bctabs {{
  display: flex; border-bottom: 1px solid #e2e8f0;
  background: #f8fafc; flex-shrink: 0;
}}
.bctab {{
  flex: 1; text-align: center; padding: 9px 4px;
  font-size: 11px; font-weight: 700; color: #64748b;
  cursor: pointer; border-bottom: 2px solid transparent;
  white-space: nowrap;
}}
.bctab.active {{ color: #1e40af; border-bottom-color: #3b82f6; background: #fff; }}

#bcmsgs {{
  flex: 1; overflow-y: auto; padding: 12px;
  display: flex; flex-direction: column; gap: 8px;
  background: #f8fafc; min-height: 0;
}}
.bmw {{ display: flex; flex-direction: column; }}
.bmw.me {{ align-items: flex-end; }}
.bmw.other {{ align-items: flex-start; }}
.bmr {{ display: flex; align-items: flex-end; gap: 7px; }}
.bmw.me .bmr {{ flex-direction: row-reverse; }}
.bav {{
  width: 27px; height: 27px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 900; color: #fff; flex-shrink: 0;
}}
.bbl {{
  max-width: 74%; padding: 8px 12px; border-radius: 14px;
  font-size: 13px; line-height: 1.45; word-break: break-word;
}}
.bmw.me .bbl {{
  background: linear-gradient(135deg,#1e40af,#3b82f6);
  color: #fff; border-bottom-right-radius: 4px;
}}
.bmw.other .bbl {{
  background: #fff; border: 1px solid #e2e8f0; color: #1e293b;
  border-bottom-left-radius: 4px; box-shadow: 0 1px 4px rgba(0,0,0,.06);
}}
.bmt {{ font-size: 10px; color: #94a3b8; margin-top: 3px; }}
.bmw.me .bmt {{ text-align: right; }}
.bemp {{ color: #94a3b8; font-size: 13px; text-align: center; margin: auto; padding: 24px; }}

#bcinp {{
  display: flex; gap: 8px; padding: 10px 12px;
  border-top: 1px solid #e2e8f0; background: #fff; flex-shrink: 0;
}}
#bcinp input {{
  flex: 1; border: 1.5px solid #bfdbfe; border-radius: 10px;
  padding: 8px 12px; font-size: 13px; outline: none; background: #f0f9ff;
  font-family: inherit;
}}
#bcinp input:focus {{ border-color: #3b82f6; background: #fff; }}
#bcinp button {{
  background: linear-gradient(135deg,#1e40af,#3b82f6);
  color: #fff; border: none; border-radius: 10px;
  padding: 8px 14px; font-size: 16px; font-weight: 700; cursor: pointer;
}}
#bcinp button:hover {{ filter: brightness(1.1); }}
</style>
</head>
<body>

<div id="bird-fab" title="Чат">
  <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
    <ellipse cx="32" cy="38" rx="16" ry="13" fill="#60a5fa"/>
    <circle cx="32" cy="22" r="11" fill="#3b82f6"/>
    <circle cx="28" cy="20" r="3" fill="white"/>
    <circle cx="36" cy="20" r="3" fill="white"/>
    <circle cx="28.8" cy="20" r="1.4" fill="#1e3a8a"/>
    <circle cx="36.8" cy="20" r="1.4" fill="#1e3a8a"/>
    <path d="M30 25 L32 29 L34 25 Q32 23 30 25Z" fill="#fbbf24"/>
    <ellipse cx="17" cy="36" rx="7" ry="10" fill="#2563eb" transform="rotate(-20 17 36)"/>
    <ellipse cx="47" cy="36" rx="7" ry="10" fill="#2563eb" transform="rotate(20 47 36)"/>
    <path d="M24 49 Q32 56 40 49 Q36 52 32 51 Q28 52 24 49Z" fill="#1d4ed8"/>
    <path d="M29 12 Q32 6 35 12" stroke="#93c5fd" stroke-width="2" fill="none" stroke-linecap="round"/>
    <path d="M32 10 Q32 4 32 10" stroke="#bfdbfe" stroke-width="1.5" fill="none" stroke-linecap="round"/>
  </svg>
</div>

<div id="bird-chat">
  <div id="bch">
    <span>🐦 Чат</span>
    <span id="bcx">✕</span>
  </div>
  <div id="bctabs">
    <div class="bctab active" data-ch="coordinator">📋 Координатор</div>
    <div class="bctab"        data-ch="responsible">👤 ССП</div>
    <div class="bctab"        data-ch="group">👥 Груп</div>
  </div>
  <div id="bcmsgs"></div>
  <div id="bcinp">
    <input id="bci" type="text" placeholder="Напишіть повідомлення..."/>
    <button id="bcsend">➤</button>
  </div>
</div>

<script>
(function(){{
  var SU  = "{_SUPABASE_URL}";
  var SK  = "{_SUPABASE_KEY}";
  var ME  = "Керівник ССП";
  var COL = {{"Керівник ССП":"#3b82f6","Координатор":"#16a34a"}};
  var LET = {{"Керівник ССП":"К","Координатор":"⚙"}};
  var cache = {{
    coordinator:{_msgs_coord},
    responsible:{_msgs_resp},
    group:{_msgs_group}
  }};
  var cur="coordinator", poll=null;

  function esc(s){{
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;")
      .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }}

  function toggle(){{
    var w=document.getElementById("bird-chat");
    var open=w.classList.toggle("open");
    if(open){{render(cache[cur]);sb();startPoll();
      setTimeout(function(){{document.getElementById("bci").focus();}},100);
    }}else stopPoll();
  }}

  function switchTab(ch){{
    cur=ch;
    document.querySelectorAll(".bctab").forEach(function(t){{
      t.classList.toggle("active",t.dataset.ch===ch);
    }});
    render(cache[ch]);sb();fetch_();
  }}

  function render(msgs){{
    var b=document.getElementById("bcmsgs");
    if(!msgs||!msgs.length){{
      b.innerHTML='<div class="bemp">Повідомлень поки немає.<br>Напишіть першим 👇</div>';
      return;
    }}
    b.innerHTML=msgs.slice(-60).map(function(m){{
      var me=m.sender===ME;
      var c=COL[m.sender]||"#d97706";
      var l=LET[m.sender]||"В";
      return '<div class="bmw '+(me?"me":"other")+'">'
        +'<div class="bmr">'
        +'<div class="bav" style="background:'+c+'">'+esc(l)+'</div>'
        +'<div class="bbl">'+esc(m.text)+'</div>'
        +'</div>'
        +'<div class="bmt">'+esc(m.sender)+' · '+esc(m.ts)+'</div>'
        +'</div>';
    }}).join("");
  }}

  function sb(){{var b=document.getElementById("bcmsgs");b.scrollTop=b.scrollHeight;}}

  function fetch_(){{
    fetch(SU+"/rest/v1/chat_messages?channel=eq."+encodeURIComponent(cur)
      +"&order=created_at.asc&limit=80",
      {{headers:{{"apikey":SK,"Authorization":"Bearer "+SK}}}}
    ).then(function(r){{return r.json();}})
     .then(function(d){{
       var m=d.map(function(x){{return{{sender:x.sender,text:x.text,
         ts:(x.created_at||"").slice(0,16).replace("T"," ")}};  }});
       cache[cur]=m;render(m);sb();
     }}).catch(function(){{}});
  }}

  function send(){{
    var inp=document.getElementById("bci");
    var txt=inp.value.trim();
    if(!txt)return;
    inp.value="";inp.disabled=true;
    fetch(SU+"/rest/v1/chat_messages",{{
      method:"POST",
      headers:{{"apikey":SK,"Authorization":"Bearer "+SK,
        "Content-Type":"application/json","Prefer":"return=minimal"}},
      body:JSON.stringify({{channel:cur,sender:ME,text:txt}})
    }}).then(function(){{return fetch_();}})
      .catch(function(e){{alert("Помилка: "+e.message);}})
      .finally(function(){{inp.disabled=false;inp.focus();}});
  }}

  function startPoll(){{stopPoll();poll=setInterval(fetch_,8000);}}
  function stopPoll(){{if(poll){{clearInterval(poll);poll=null;}}}}

  // Прив'язка подій
  document.getElementById("bird-fab").addEventListener("click",toggle);
  document.getElementById("bcx").addEventListener("click",toggle);
  document.getElementById("bcsend").addEventListener("click",send);
  document.getElementById("bci").addEventListener("keydown",function(e){{
    if(e.key==="Enter")send();
  }});
  document.querySelectorAll(".bctab").forEach(function(t){{
    t.addEventListener("click",function(){{switchTab(t.dataset.ch);}});
  }});

  render(cache[cur]);
}})();
</script>
</body>
</html>"""

_components.html(_chat_html, height=600, scrolling=False)


# ============================================================
# FOOTER
# ============================================================

st.markdown("""
<div class="footer">
    <strong>Розроблено департаментом стратегічного планування та макроекономічного прогнозування</strong><br>
    Версія DEMO 1.4 | 2026 | Внутрішня система моніторингу стратегічного плану
</div>
""", unsafe_allow_html=True)
