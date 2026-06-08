import re
import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime, timezone

st.set_page_config(
    page_title="Адміністрування",
    layout="wide"
)

FILE_PATH = "Під моніторинг СП.xlsx"
SHEET_NAME = "Страт_матриця"

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

st.markdown("""
<style>
/* ─── ADMIN CABINET BACKGROUND ─── */
.stApp {
    background:
        radial-gradient(ellipse at 0% 0%, rgba(15,23,80,0.92) 0%, transparent 55%),
        radial-gradient(ellipse at 100% 100%, rgba(10,40,60,0.85) 0%, transparent 55%),
        linear-gradient(135deg, #0a0f2e 0%, #0d1a3a 35%, #0a2240 65%, #091830 100%);
    min-height: 100vh;
}

.stApp::before {
    content: "";
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background-image:
        radial-gradient(circle at 20% 30%, rgba(37,99,235,0.07) 0%, transparent 30%),
        radial-gradient(circle at 80% 70%, rgba(6,182,212,0.06) 0%, transparent 30%),
        repeating-linear-gradient(
            0deg,
            transparent,
            transparent 60px,
            rgba(37,99,235,0.025) 60px,
            rgba(37,99,235,0.025) 61px
        ),
        repeating-linear-gradient(
            90deg,
            transparent,
            transparent 80px,
            rgba(37,99,235,0.02) 80px,
            rgba(37,99,235,0.02) 81px
        );
    pointer-events: none;
    z-index: 0;
}

.main .block-container {
    max-width: 1580px;
    padding-top: 1.2rem;
    position: relative;
    z-index: 1;
}

/* ─── UA LINE ─── */
.ua-line {
    height: 6px;
    border-radius: 999px;
    background: linear-gradient(90deg, #005BBB 0%, #005BBB 50%, #FFD500 50%, #FFD500 100%);
    margin-bottom: 12px;
    box-shadow: 0 2px 8px rgba(0,91,187,0.4);
}

.ministry-label {
    text-align: right;
    color: #94a3b8;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 8px;
    letter-spacing: 0.02em;
}

/* ─── HEADER ─── */
.header-box {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 16px;
    padding: 22px 28px;
    margin-bottom: 16px;
    backdrop-filter: blur(12px);
    box-shadow: 0 8px 32px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.08);
}

.header-title {
    font-size: 30px;
    font-weight: 900;
    color: #f1f5f9;
    margin-bottom: 6px;
    letter-spacing: -0.01em;
}

.header-subtitle {
    font-size: 14px;
    color: #94a3b8;
    line-height: 1.55;
}

.status-pill-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 12px;
}

.status-pill {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 999px;
    padding: 6px 12px;
    font-size: 12px;
    color: #cbd5e1;
}

/* ─── CARDS ─── */
.card {
    background: rgba(255,255,255,0.055);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 18px 22px;
    margin: 14px 0;
    backdrop-filter: blur(10px);
    box-shadow: 0 4px 20px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.06);
}

.card-title {
    font-size: 18px;
    font-weight: 900;
    color: #e2e8f0;
    margin-bottom: 6px;
}

.card-subtitle {
    color: #64748b;
    font-size: 13px;
    margin-bottom: 10px;
}

/* ─── FLOW BOX ─── */
.flow-box {
    background: rgba(37,99,235,0.08);
    border: 1px solid rgba(37,99,235,0.22);
    border-radius: 14px;
    padding: 14px 18px;
    margin: 14px 0;
}

.flow-title {
    font-weight: 900;
    color: #93c5fd;
    margin-bottom: 10px;
    font-size: 14px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.flow-steps {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.flow-step {
    padding: 7px 13px;
    border-radius: 999px;
    background: rgba(37,99,235,0.15);
    border: 1px solid rgba(37,99,235,0.3);
    color: #bfdbfe;
    font-size: 13px;
    font-weight: 600;
}

/* ─── BADGES ─── */
.badge-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 10px 0 14px 0;
}

.badge {
    background: rgba(37,99,235,0.2);
    border: 1px solid rgba(37,99,235,0.4);
    color: #93c5fd;
    border-radius: 999px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 700;
}

.badge-green {
    background: rgba(22,163,74,0.2);
    border: 1px solid rgba(22,163,74,0.4);
    color: #86efac;
}

.badge-yellow {
    background: rgba(202,138,4,0.2);
    border: 1px solid rgba(202,138,4,0.4);
    color: #fde047;
}

.badge-red {
    background: rgba(185,28,28,0.2);
    border: 1px solid rgba(185,28,28,0.4);
    color: #fca5a5;
}

/* ─── ATTENTION GRID ─── */
.attention-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 10px;
    margin: 10px 0;
}

.attention-card {
    border-radius: 12px;
    padding: 12px 14px;
    border: 1px solid rgba(255,255,255,0.1);
}

.attention-title {
    color: #94a3b8;
    font-size: 11px;
    font-weight: 800;
    margin-bottom: 6px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.attention-value {
    font-size: 28px;
    font-weight: 950;
    line-height: 1.1;
}

.attention-note {
    color: #64748b;
    font-size: 11px;
    margin-top: 4px;
    line-height: 1.25;
}

.att-red    { background: rgba(185,28,28,0.18); border-color: rgba(248,113,113,0.3); }
.att-red .attention-value    { color: #f87171; }
.att-yellow { background: rgba(161,98,7,0.18); border-color: rgba(253,224,71,0.3); }
.att-yellow .attention-value { color: #fde047; }
.att-blue   { background: rgba(37,99,235,0.18); border-color: rgba(147,197,253,0.3); }
.att-blue .attention-value   { color: #93c5fd; }
.att-green  { background: rgba(22,163,74,0.18); border-color: rgba(134,239,172,0.3); }
.att-green .attention-value  { color: #86efac; }

/* ─── KPI CARDS ─── */
.admin-kpi-card {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 12px;
    padding: 12px 14px;
    min-height: 90px;
}

.admin-kpi-label {
    color: #64748b;
    font-size: 12px;
    font-weight: 700;
    margin-bottom: 6px;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}

.admin-kpi-value {
    color: #e2e8f0;
    font-size: 20px;
    font-weight: 850;
    line-height: 1.2;
    word-break: break-word;
}

/* ─── QUALITY CARDS ─── */
.quality-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    padding: 10px 12px;
    min-height: 80px;
}

.quality-good { border-left: 4px solid #22c55e; }
.quality-warn { border-left: 4px solid #f59e0b; }

.quality-label {
    color: #64748b;
    font-size: 11px;
    font-weight: 700;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}

.quality-value {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    color: #e2e8f0;
    font-size: 14px;
    font-weight: 750;
    line-height: 1.3;
}

/* ─── REVIEW BOX ─── */
.review-box {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    padding: 14px 16px;
    margin: 10px 0;
    color: #cbd5e1;
    font-size: 14px;
    line-height: 1.6;
}

.review-title {
    font-size: 15px;
    font-weight: 900;
    color: #e2e8f0;
    margin-bottom: 8px;
}

/* ─── RESOLUTION ─── */
.resolution-box {
    background: rgba(37,99,235,0.08);
    border: 1px solid rgba(37,99,235,0.25);
    border-left: 5px solid #3b82f6;
    border-radius: 12px;
    padding: 14px 16px;
    margin: 10px 0;
}

.resolution-title {
    font-size: 15px;
    font-weight: 900;
    color: #93c5fd;
    margin-bottom: 8px;
}

.resolution-text {
    color: #cbd5e1;
    font-size: 14px;
    line-height: 1.65;
}

/* ─── DECISION BOX ─── */
.decision-box {
    background: rgba(37,99,235,0.12);
    border: 1px solid rgba(37,99,235,0.3);
    border-radius: 10px;
    padding: 12px 16px;
    margin: 10px 0;
    color: #93c5fd;
    font-size: 14px;
    font-weight: 700;
}

/* ─── PROGRESS / INFO BOXES ─── */
.progress-risk-box {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    padding: 14px 16px;
    min-height: 120px;
}

.progress-risk-label {
    color: #64748b;
    font-size: 11px;
    font-weight: 700;
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.progress-risk-value {
    color: #cbd5e1;
    font-size: 14px;
    line-height: 1.6;
    white-space: pre-wrap;
}

/* ─── PERSON BOX ─── */
.person-box {
    background: rgba(37,99,235,0.08);
    border: 1px solid rgba(37,99,235,0.2);
    border-radius: 12px;
    padding: 14px 18px;
    display: flex;
    gap: 28px;
    flex-wrap: wrap;
    align-items: center;
}

.person-field {
    display: flex;
    flex-direction: column;
    gap: 3px;
}

.person-field-label {
    color: #64748b;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.person-field-value {
    color: #93c5fd;
    font-size: 14px;
    font-weight: 700;
}

/* ─── SELECTBOX / INPUTS OVERRIDE ─── */
div[data-testid="stSelectbox"] > div > div,
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    background: rgba(255,255,255,0.08) !important;
    border: 1px solid rgba(255,255,255,0.18) !important;
    color: #e2e8f0 !important;
    border-radius: 10px !important;
}

div[data-testid="stSelectbox"] label,
div[data-testid="stTextInput"] label,
div[data-testid="stTextArea"] label {
    color: #94a3b8 !important;
    font-size: 13px !important;
    font-weight: 600 !important;
}

div[data-testid="stSelectbox"] > div > div:hover {
    border-color: rgba(99,179,237,0.5) !important;
}

/* Radio buttons */
div[data-testid="stRadio"] label {
    color: #cbd5e1 !important;
}

div[data-testid="stRadio"] > div {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    padding: 12px 16px;
}

/* Checkbox */
div[data-testid="stCheckbox"] label {
    color: #94a3b8 !important;
}

/* Tabs */
button[data-baseweb="tab"] {
    color: #94a3b8 !important;
    background: transparent !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #93c5fd !important;
    border-bottom: 2px solid #3b82f6 !important;
}

/* Metric widgets */
div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 12px;
    padding: 12px 14px;
}

div[data-testid="stMetric"] label {
    color: #64748b !important;
}

div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: #e2e8f0 !important;
}

/* Buttons */
div.stButton > button {
    border-radius: 10px;
    padding: 10px 18px;
    font-weight: 800;
    background: rgba(37,99,235,0.2);
    border: 1px solid rgba(37,99,235,0.4);
    color: #93c5fd;
    transition: all 0.2s;
}

div.stButton > button:hover {
    background: rgba(37,99,235,0.35);
    border-color: rgba(99,179,237,0.6);
}

div[data-testid="stFormSubmitButton"] button {
    border-radius: 12px;
    padding: 12px 18px;
    font-weight: 900;
    background: linear-gradient(135deg, #1d4ed8, #2563eb);
    border: none;
    color: white;
    box-shadow: 0 4px 14px rgba(37,99,235,0.5);
    transition: all 0.2s;
}

div[data-testid="stFormSubmitButton"] button:hover {
    background: linear-gradient(135deg, #2563eb, #3b82f6);
    box-shadow: 0 6px 20px rgba(37,99,235,0.7);
}

/* Expander */
div[data-testid="stExpander"] {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
}

div[data-testid="stExpander"] summary {
    color: #93c5fd !important;
    font-weight: 700;
}

/* Dataframe */
div[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
}

/* Warnings/Info */
div[data-testid="stWarning"] {
    background: rgba(161,98,7,0.15);
    border: 1px solid rgba(253,224,71,0.3);
    border-radius: 10px;
    color: #fde047;
}

div[data-testid="stInfo"] {
    background: rgba(37,99,235,0.12);
    border: 1px solid rgba(147,197,253,0.3);
    border-radius: 10px;
    color: #93c5fd;
}

div[data-testid="stSuccess"] {
    background: rgba(22,163,74,0.15);
    border: 1px solid rgba(134,239,172,0.3);
    border-radius: 10px;
    color: #86efac;
}

/* Caption */
div[data-testid="stCaptionContainer"] {
    color: #64748b !important;
}

/* Progress bar */
div[data-testid="stProgressBar"] > div {
    background: rgba(255,255,255,0.08);
    border-radius: 999px;
}

div[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, #2563eb, #06b6d4);
    border-radius: 999px;
}

/* Footer */
.footer {
    text-align: center;
    color: #475569;
    font-size: 12px;
    margin-top: 50px;
    padding: 20px 0 12px 0;
    border-top: 1px solid rgba(255,255,255,0.08);
}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def clean(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value)


def has_value(value):
    return clean(value).strip() != ""


def to_datetime(value):
    text = clean(value).strip()
    if not text:
        return None
    try:
        dt = pd.to_datetime(text, errors="coerce", utc=True)
        if pd.isna(dt):
            return None
        return dt.to_pydatetime()
    except Exception:
        return None


def days_waiting(value):
    dt = to_datetime(value)
    if not dt:
        return None
    now = datetime.now(timezone.utc)
    return (now - dt).days


def split_ssp_values(value):
    text = clean(value).strip()
    if not text:
        return []
    return re.findall(r"\d+", text)


def admin_kpi_card(label, value):
    value = "" if value is None else str(value)
    st.markdown(
        f"""
        <div class="admin-kpi-card">
            <div class="admin-kpi-label">{label}</div>
            <div class="admin-kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def quality_card(label, status, good=True):
    icon = "✅" if good else "⚠️"
    css_class = "quality-good" if good else "quality-warn"
    st.markdown(
        f"""
        <div class="quality-card {css_class}">
            <div class="quality-label">{label}</div>
            <div class="quality-value">
                <span>{icon}</span>
                <span>{status}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def attention_card(title, value, note, css_class):
    st.markdown(
        f"""
        <div class="attention-card {css_class}">
            <div class="attention-title">{title}</div>
            <div class="attention-value">{value}</div>
            <div class="attention-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


# ──────────────────────────────────────────────
# DATA LOADING
# ──────────────────────────────────────────────

@st.cache_data
def load_strat_matrix():
    df = pd.read_excel(
        FILE_PATH,
        sheet_name=SHEET_NAME,
        header=None,
        engine="openpyxl"
    )

    data = df.iloc[7:].copy()

    def safe_col(idx):
        if idx < data.shape[1]:
            return data.iloc[:, idx]
        return pd.Series([""] * len(data))

    result = pd.DataFrame({
        "type_marker":    safe_col(1),
        "code":           safe_col(2),
        "name":           safe_col(3),
        "product_type":   safe_col(4),
        "indicator":      safe_col(5),
        "unit":           safe_col(6),
        "base_2021":      safe_col(7),
        "fact_2024":      safe_col(8),
        "expected_2025":  safe_col(9),
        "target_2026":    safe_col(10),
        "target_2027":    safe_col(11),
        "target_2028":    safe_col(12),
        "resp_main":      safe_col(17),
        "resp_co_1":      safe_col(18),
        "resp_co_2":      safe_col(19),
        "start_date_plan": safe_col(22),
        "end_date_plan":   safe_col(23),
    })

    result = result.dropna(subset=["code"])
    result["code"] = result["code"].astype(str).str.strip()

    return result


def load_requests():
    response = (
        supabase
        .table("monitoring_requests")
        .select("*")
        .order("id", desc=True)
        .execute()
    )
    if not response.data:
        return pd.DataFrame()
    return pd.DataFrame(response.data)


def load_logs(request_id):
    response = (
        supabase
        .table("monitoring_logs")
        .select("*")
        .eq("request_id", int(request_id))
        .order("changed_at", desc=True)
        .execute()
    )
    if not response.data:
        return pd.DataFrame()
    return pd.DataFrame(response.data)


def write_log(request_id, action, old_status, new_status, admin_comment):
    supabase.table("monitoring_logs").insert({
        "request_id": int(request_id),
        "action": action,
        "old_status": old_status,
        "new_status": new_status,
        "admin_comment": admin_comment,
        "changed_by": "Адміністратор"
    }).execute()


# ──────────────────────────────────────────────
# QUALITY ASSESSMENT  (без файлів — п.19)
# ──────────────────────────────────────────────

def quality_assessment(row):
    checks = []
    score = 0

    if has_value(row.get("numeric_value", "")):
        checks.append(("Фактичне значення", "Заповнено", True))
        score += 1
    else:
        checks.append(("Фактичне значення", "Не заповнено", False))

    if has_value(row.get("progress_text", "")):
        checks.append(("Опис прогресу", "Заповнено", True))
        score += 1
    else:
        checks.append(("Опис прогресу", "Не заповнено", False))

    if has_value(row.get("responsible_person", "")):
        checks.append(("Відповідальна особа", "Заповнено", True))
        score += 1
    else:
        checks.append(("Відповідальна особа", "Не заповнено", False))

    if has_value(row.get("phone", "")):
        checks.append(("Телефон", "Заповнено", True))
        score += 1
    else:
        checks.append(("Телефон", "Не заповнено", False))

    if has_value(row.get("email", "")):
        checks.append(("Email", "Заповнено", True))
        score += 1
    else:
        checks.append(("Email", "Не заповнено", False))

    if has_value(row.get("status", "")):
        checks.append(("Статус заходу", "Заповнено", True))
        score += 1
    else:
        checks.append(("Статус заходу", "Не заповнено", False))

    if has_value(row.get("start_date", "")):
        checks.append(("Початок виконання", "Заповнено", True))
        score += 1
    else:
        checks.append(("Початок виконання", "Не заповнено", False))

    if has_value(row.get("end_date", "")):
        checks.append(("Кінець виконання", "Заповнено", True))
        score += 1
    else:
        checks.append(("Кінець виконання", "Не заповнено", False))

    if has_value(row.get("risks", "")):
        checks.append(("Ризики", "Є запис", False))
    else:
        checks.append(("Ризики", "Не зазначено", True))
        score += 1

    total_fields = 9
    if score >= 8 and not has_value(row.get("risks", "")):
        recommendation = "Можна направляти на підпис"
        badge = "badge-green"
    elif score >= 6:
        recommendation = "Потребує перевірки"
        badge = "badge-yellow"
    else:
        recommendation = "Краще повернути на доопрацювання"
        badge = "badge-red"

    return checks, recommendation, badge, score, total_fields


# ──────────────────────────────────────────────
# RESOLUTION GENERATOR  (п.13 — якісна, без файлів)
# ──────────────────────────────────────────────

def generate_resolution(row, recommendation, quality_score, total_fields):
    request_id  = clean(row.get("id", ""))
    code        = clean(row.get("strat_code", ""))
    year        = clean(row.get("year", ""))
    quarter     = clean(row.get("quarter", ""))
    department  = clean(row.get("department", ""))
    status      = clean(row.get("status", ""))
    fact        = clean(row.get("numeric_value", ""))
    progress    = clean(row.get("progress_text", ""))
    risks       = clean(row.get("risks", ""))
    person      = clean(row.get("responsible_person", ""))
    phone       = clean(row.get("phone", ""))
    email       = clean(row.get("email", ""))
    start_date  = clean(row.get("start_date", ""))
    end_date    = clean(row.get("end_date", ""))

    missing = []
    if not has_value(fact):        missing.append("фактичне значення показника")
    if not has_value(progress):    missing.append("опис прогресу виконання")
    if not has_value(email):       missing.append("електронна пошта")
    if not has_value(phone):       missing.append("контактний телефон")
    if not has_value(status):      missing.append("статус виконання заходу")
    if not has_value(start_date):  missing.append("дата початку виконання")
    if not has_value(end_date):    missing.append("дата завершення виконання")

    completeness = round(quality_score / total_fields * 100, 1)
    date_info = ""
    if has_value(start_date) and has_value(end_date):
        date_info = f"Заявлений термін виконання: {start_date} — {end_date}. "

    if recommendation == "Можна направляти на підпис":
        risks_note = ""
        if risks:
            risks_note = (
                f" Разом із тим, у заявці зафіксовані ризики / відхилення: «{risks}», "
                f"що потребує врахування при підписанні."
            )
        return (
            f"ПРОЄКТ РЕЗОЛЮЦІЇ\n\n"
            f"Заявка ID {request_id} — ССП «{department}», захід {code}, "
            f"{quarter} квартал {year} року.\n\n"
            f"Системний аналіз підтвердив достатній рівень заповнення відомостей "
            f"(заповненість: {completeness}%). "
            f"Відповідальна особа: {person} (тел.: {phone}, e-mail: {email}). "
            f"Фактичне значення показника — «{fact}», статус виконання — «{status}». "
            f"{date_info}"
            f"Опис прогресу: «{progress}».{risks_note}\n\n"
            f"Рекомендація: НАПРАВИТИ НА ПІДПИС КЕРІВНИКУ ССП. "
            f"Підстава — дані відповідають вимогам моніторингу, ознак критичної неповноти не виявлено."
        )

    if recommendation == "Потребує перевірки":
        details = []
        if risks:
            details.append(f"у заявці задокументовано ризики / проблеми: «{risks}»")
        if missing:
            details.append("не заповнені обов'язкові поля: " + ", ".join(missing))

        detail_text = "; ".join(details) if details else "окремі елементи потребують додаткової перевірки"

        return (
            f"ПРОЄКТ РЕЗОЛЮЦІЇ\n\n"
            f"Заявка ID {request_id} — ССП «{department}», захід {code}, "
            f"{quarter} квартал {year} року.\n\n"
            f"Попередній системний аналіз виявив, що {detail_text}. "
            f"Заповненість ключових полів становить {completeness}%. "
            f"Фактичне значення: «{fact}», статус: «{status}». "
            f"{date_info}"
            f"Відповідальна особа: {person}.\n\n"
            f"Рекомендація: ДОДАТКОВА ПЕРЕВІРКА ПЕРЕД НАПРАВЛЕННЯМ НА ПІДПИС. "
            f"Рекомендовано уточнити зміст поданих відомостей та усунути виявлені недоліки."
        )

    missing_text = ", ".join(missing) if missing else "ключові поля заявки заповнені неповністю"

    return (
        f"ПРОЄКТ РЕЗОЛЮЦІЇ\n\n"
        f"Заявка ID {request_id} — ССП «{department}», захід {code}, "
        f"{quarter} квартал {year} року.\n\n"
        f"Система визначила критичну неповноту поданих відомостей "
        f"(заповненість: {completeness}%). "
        f"Відсутні обов'язкові елементи: {missing_text}. "
        f"Фактичне значення: «{fact}», статус: «{status}». "
        f"{date_info}\n\n"
        f"Рекомендація: ПОВЕРНУТИ НА ДООПРАЦЮВАННЯ. "
        f"До повторного подання необхідно усунути зазначені недоліки "
        f"відповідно до вимог системи моніторингу стратегічного плану."
    )


# ──────────────────────────────────────────────
# ATTENTION SUMMARY  (п.4 — нові блоки, без файлів)
# ──────────────────────────────────────────────

def build_attention_summary(df):
    data = df.copy()

    if data.empty:
        return {
            "long_waiting": pd.DataFrame(),
            "with_risks":   pd.DataFrame(),
            "returned":     pd.DataFrame(),
            "waiting":      pd.DataFrame(),
            "not_counted":  pd.DataFrame(),
            "approved":     pd.DataFrame(),
        }

    data["days_waiting"] = data["submitted_at"].apply(days_waiting)

    long_waiting = data[
        (data["approval_status"].astype(str) == "Очікує погодження") &
        (data["days_waiting"].fillna(0) >= 5)
    ].copy()

    waiting = data[
        data["approval_status"].astype(str) == "Очікує погодження"
    ].copy()

    not_counted = data[
        ~data["approval_status"].astype(str).isin(["Погоджено"])
    ].copy()

    with_risks = data[
        data["risks"].fillna("").astype(str).str.strip() != ""
    ].copy()

    returned = data[
        data["approval_status"].astype(str) == "Повернуто на доопрацювання"
    ].copy()

    approved = data[
        data["approval_status"].astype(str) == "Погоджено"
    ].copy()

    return {
        "long_waiting": long_waiting,
        "waiting":      waiting,
        "not_counted":  not_counted,
        "with_risks":   with_risks,
        "returned":     returned,
        "approved":     approved,
    }


# ──────────────────────────────────────────────
# PAGE HEADER
# ──────────────────────────────────────────────

st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="ministry-label">
    🇺🇦 Міністерство економіки, довкілля та сільського господарства України
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="header-box">
        <div class="header-title">Адміністрування</div>
        <div class="header-subtitle">
            Кабінет адміністратора використовується для розгляду, перевірки та погодження
            поданих відомостей та відстеження історії змін.
        </div>
        <div class="status-pill-wrap">
            <div class="status-pill">● Режим: адміністрування</div>
            <div class="status-pill">● Дані: Supabase</div>
            <div class="status-pill">● Журнал змін: активний</div>
            <div class="status-pill">● Резолюція: автоматична</div>
            <div class="status-pill">● Оновлено: {datetime.now().strftime("%d.%m.%Y %H:%M")}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="flow-box">
        <div class="flow-title">Маршрут адміністратора</div>
        <div class="flow-steps">
            <div class="flow-step">1. Перегляд системних параметрів</div>
            <div class="flow-step">2. Вибір параметрів</div>
            <div class="flow-step">3. Перевірка</div>
            <div class="flow-step">4. Вибір рішення</div>
            <div class="flow-step">5. Підтвердження</div>
            <div class="flow-step">6. Погодження</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# ──────────────────────────────────────────────
# LOAD DATA
# ──────────────────────────────────────────────

df = load_requests()
strat_df = load_strat_matrix()

if df.empty:
    st.warning("Поки що немає поданих заявок.")
    st.stop()

required_cols = [
    "id", "department", "year", "quarter",
    "approval_status", "status", "strat_code",
    "responsible_person", "phone", "email",
    "numeric_value", "progress_text", "risks",
    "file_names", "file_urls", "admin_comment",
    "start_date", "end_date", "submitted_at"
]

for col in required_cols:
    if col not in df.columns:
        df[col] = ""

attention = build_attention_summary(df)

# ──────────────────────────────────────────────
# СИСТЕМНИЙ АНАЛІЗ  (п.4)
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card"><div class="card-title">Системний аналіз</div>'
    '<div class="card-subtitle">Автоматичний контроль усіх поданих відомостей</div>',
    unsafe_allow_html=True
)

st.markdown('<div class="attention-grid">', unsafe_allow_html=True)

attention_card(
    "На розгляді понад 5 днів",
    len(attention["long_waiting"]),
    "Заявки довго перебувають без рішення.",
    "att-red" if len(attention["long_waiting"]) else "att-green"
)

attention_card(
    "На розгляді",
    len(attention["waiting"]),
    "Заявки, що очікують рішення адміністратора.",
    "att-yellow" if len(attention["waiting"]) else "att-green"
)

attention_card(
    "Не враховано",
    len(attention["not_counted"]),
    "Заявки, що ще не отримали статус «Погоджено».",
    "att-red" if len(attention["not_counted"]) else "att-green"
)

attention_card(
    "На доопрацюванні",
    len(attention["returned"]),
    "Повернуті для виправлення та повторного подання.",
    "att-blue" if len(attention["returned"]) else "att-green"
)

attention_card(
    "Погоджено",
    len(attention["approved"]),
    "Відомості погоджені адміністратором.",
    "att-green"
)

st.markdown('</div>', unsafe_allow_html=True)

# Expander з записами — сортування ССП за числовим індексом (п.4)
with st.expander("Перегляд записів"):
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "На розгляді понад 5 днів",
        "На розгляді",
        "Не враховано",
        "На доопрацюванні",
        "Погоджено"
    ])

    def sort_ssp(frame):
        if frame.empty or "department" not in frame.columns:
            return frame
        frame = frame.copy()
        frame["_ssp_sort"] = pd.to_numeric(
            frame["department"].astype(str).str.extract(r"(\d+)")[0], errors="coerce"
        )
        frame = frame.sort_values("_ssp_sort").drop(columns=["_ssp_sort"])
        return frame

    PRIORITY_COLS = [
        "id", "department", "status", "strat_code",
        "start_date", "end_date", "year", "quarter",
    ]

    def show_sorted_table(frame, key):
        if frame.empty:
            st.info("Записів немає.")
            return
        frame = sort_ssp(frame)
        all_cols = list(frame.columns)
        priority = [c for c in PRIORITY_COLS if c in all_cols]
        rest = [c for c in all_cols if c not in priority]
        frame = frame[priority + rest]
        rename_map = {
            "id": "ID",
            "department": "Самостійний структурний підрозділ",
            "status": "Статус заходу",
            "strat_code": "Код заходу",
            "year": "Рік",
            "quarter": "Квартал",
            "approval_status": "Статус погодження",
            "responsible_person": "Відповідальна особа",
            "submitted_at": "Дата подання",
            "start_date": "Початок виконання",
            "end_date": "Кінець виконання",
            "numeric_value": "Факт. значення",
            "progress_text": "Опис прогресу",
            "risks": "Ризики",
            "admin_comment": "Коментар адміністратора",
        }
        frame = frame.rename(columns={k: v for k, v in rename_map.items() if k in frame.columns})
        st.dataframe(frame, use_container_width=True, hide_index=True)

    with tab1:
        show_sorted_table(attention["long_waiting"], "lw")
    with tab2:
        show_sorted_table(attention["waiting"], "wt")
    with tab3:
        show_sorted_table(attention["not_counted"], "nc")
    with tab4:
        show_sorted_table(attention["returned"], "ret")
    with tab5:
        show_sorted_table(attention["approved"], "appr")

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ІНФОГРАФІКА  (п.5 — кругова діаграма)
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card"><div class="card-title">Інфографіка</div>',
    unsafe_allow_html=True
)

status_counts = {
    "На розгляді понад 5 днів": len(attention["long_waiting"]),
    "На розгляді":              len(attention["waiting"]),
    "Не враховано":             len(attention["not_counted"]),
    "На доопрацюванні":         len(attention["returned"]),
    "Погоджено":                len(attention["approved"]),
}

chart_df = pd.DataFrame({
    "Статус": list(status_counts.keys()),
    "Кількість": list(status_counts.values())
})
chart_df = chart_df[chart_df["Кількість"] > 0]

if not chart_df.empty:
    color_map = {
        "На розгляді понад 5 днів": "#f87171",
        "На розгляді":              "#fde047",
        "Не враховано":             "#fb923c",
        "На доопрацюванні":         "#60a5fa",
        "Погоджено":                "#4ade80",
    }
    fig = px.pie(
        chart_df,
        names="Статус",
        values="Кількість",
        hole=0.5,
        title="Розподіл заявок за статусом погодження",
        color="Статус",
        color_discrete_map=color_map
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#cbd5e1",
        title_font_color="#e2e8f0",
        legend=dict(
            font=dict(color="#94a3b8"),
            bgcolor="rgba(0,0,0,0)"
        )
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Даних для відображення поки що немає.")

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ПАРАМЕТРИ ВІДБОРУ  (п.7 — фільтри)
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card"><div class="card-title">Параметри відбору</div>',
    unsafe_allow_html=True
)

# Числові індекси ССП (без слів), відсортовані числово
all_ssp_raw = sorted(
    {
        idx
        for _, row in df.iterrows()
        for idx in split_ssp_values(row.get("department", ""))
    },
    key=lambda x: int(x) if str(x).isdigit() else 9999
)

f1, f2, f3, f4 = st.columns(4)

with f1:
    selected_ssp = st.selectbox(
        "Самостійний структурний підрозділ",
        ["Усі"] + all_ssp_raw
    )

with f2:
    years = sorted(df["year"].dropna().astype(str).unique().tolist())
    selected_year = st.selectbox("Рік", ["Усі"] + years)

with f3:
    quarters = sorted(df["quarter"].dropna().astype(str).unique().tolist())
    selected_quarter = st.selectbox("Квартал", ["Усі"] + quarters)

with f4:
    selected_approval_status = st.selectbox(
        "Статус погодження",
        [
            "Активні до розгляду",
            "Усі",
            "Очікує погодження",
            "Повернуто на доопрацювання",
            "Направлено на підпис",
            "Погоджено"
        ],
        index=0
    )

q1, q2 = st.columns([1, 2])

with q1:
    quick_filter = st.selectbox(
        "Швидкий фільтр",
        [
            "Усі заявки",
            "Тільки очікують",
            "Повернуті",
            "Із ризиками",
            "Останні подані",
            "На розгляді понад 5 днів",
        ]
    )

with q2:
    search_query = st.text_input(
        "Пошук за ID, назвою заходу, ПІБ або департаментом"
    )

# Фільтрація
filtered = df.copy()

if selected_ssp != "Усі":
    filtered = filtered[
        filtered["department"].astype(str).str.contains(selected_ssp, na=False)
    ]

if selected_year != "Усі":
    filtered = filtered[filtered["year"].astype(str) == str(selected_year)]

if selected_quarter != "Усі":
    filtered = filtered[filtered["quarter"].astype(str) == str(selected_quarter)]

if selected_approval_status == "Активні до розгляду":
    filtered = filtered[
        filtered["approval_status"].astype(str).isin([
            "Очікує погодження",
            "Повернуто на доопрацювання",
            "Направлено на підпис"
        ])
    ]
elif selected_approval_status != "Усі":
    filtered = filtered[
        filtered["approval_status"].astype(str) == str(selected_approval_status)
    ]

if quick_filter == "Тільки очікують":
    filtered = filtered[filtered["approval_status"] == "Очікує погодження"]
elif quick_filter == "Повернуті":
    filtered = filtered[filtered["approval_status"] == "Повернуто на доопрацювання"]
elif quick_filter == "Із ризиками":
    filtered = filtered[filtered["risks"].fillna("").astype(str).str.strip() != ""]
elif quick_filter == "Останні подані":
    filtered = filtered.sort_values("submitted_at", ascending=False).head(10)
elif quick_filter == "На розгляді понад 5 днів":
    filtered = attention["long_waiting"].copy()

if search_query.strip():
    sq = search_query.strip().lower()
    filtered = filtered[
        filtered["id"].astype(str).str.lower().str.contains(sq, na=False)
        | filtered["strat_code"].astype(str).str.lower().str.contains(sq, na=False)
        | filtered["responsible_person"].astype(str).str.lower().str.contains(sq, na=False)
        | filtered["department"].astype(str).str.lower().str.contains(sq, na=False)
        | filtered["progress_text"].astype(str).str.lower().str.contains(sq, na=False)
    ]

st.caption(f"Знайдено заявок: {len(filtered)}")
st.markdown('</div>', unsafe_allow_html=True)

if filtered.empty:
    st.info("За обраними фільтрами заявок не знайдено.")
    st.stop()

# ──────────────────────────────────────────────
# ЧЕРГА НА РОЗГЛЯД  (п.8)
# ──────────────────────────────────────────────

queue_df = filtered[
    filtered["approval_status"].isin(["Очікує погодження", "Направлено на підпис"])
].copy()

if not queue_df.empty:
    st.markdown(
        '<div class="card"><div class="card-title">Черга на розгляд</div>'
        '<div class="card-subtitle">Заявки, що потребують рішення адміністратора.</div>',
        unsafe_allow_html=True
    )

    # Сортуємо ССП числово
    queue_df["_ssp_sort"] = pd.to_numeric(
        queue_df["department"].astype(str).str.extract(r"(\d+)")[0], errors="coerce"
    )
    queue_df = queue_df.sort_values("_ssp_sort").drop(columns=["_ssp_sort"])

    queue_show = queue_df.rename(columns={
        "id": "ID",
        "department": "Самостійний структурний підрозділ",
        "strat_code": "Код заходу",
        "year": "Рік",
        "quarter": "Квартал",
        "status": "Статус заходу",
        "approval_status": "Статус погодження",
        "responsible_person": "Відповідальна особа",
        "submitted_at": "Дата подання"
    })

    display_cols = [c for c in [
        "ID", "Самостійний структурний підрозділ", "Код заходу",
        "Рік", "Квартал", "Статус заходу", "Статус погодження",
        "Відповідальна особа", "Дата подання"
    ] if c in queue_show.columns]

    st.dataframe(queue_show[display_cols], use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ВИБІР ЗАЯВКИ  (п.9 — стильний selectbox)
# ──────────────────────────────────────────────

st.markdown('<div class="card"><div class="card-title">Вибір заявки</div>', unsafe_allow_html=True)

selected_options = []
for _, row in filtered.iterrows():
    option = (
        f"ID {row['id']} | "
        f"ССП {row['department']} | "
        f"{row['strat_code']} | "
        f"{row['year']} {row['quarter']} квартал | "
        f"{row['approval_status']} | "
        f"{clean(row['submitted_at'])}"
    )
    selected_options.append(option)

selected_request = st.selectbox(
    "Оберіть заявку для перегляду та погодження",
    selected_options
)

selected_id = int(selected_request.split("|")[0].replace("ID", "").strip())
selected_row = filtered[filtered["id"].astype(int) == selected_id].iloc[0]

st.markdown('</div>', unsafe_allow_html=True)

approval_status = clean(selected_row["approval_status"])
selected_code   = clean(selected_row["strat_code"])

checks, recommendation, rec_badge, quality_score, total_fields = quality_assessment(selected_row)
auto_resolution = generate_resolution(selected_row, recommendation, quality_score, total_fields)

# ──────────────────────────────────────────────
# КАРТКА ЗАЯВКИ  (п.10)
# ──────────────────────────────────────────────

st.markdown('<div class="card"><div class="card-title">Картка заявки</div>', unsafe_allow_html=True)

if approval_status == "Погоджено":
    status_badge = "badge-green"
elif approval_status == "Повернуто на доопрацювання":
    status_badge = "badge-red"
elif approval_status == "Направлено на підпис":
    status_badge = "badge"
else:
    status_badge = "badge-yellow"

st.markdown(
    f"""
    <div class="badge-wrap">
        <div class="badge {status_badge}">Статус погодження: {approval_status}</div>
        <div class="badge">Заявка ID {clean(selected_row['id'])}</div>
        <div class="badge">Захід {selected_code}</div>
        <div class="badge {rec_badge}">Рекомендація: {recommendation}</div>
    </div>
    """,
    unsafe_allow_html=True
)

k1, k2, k3, k4, k5, k6 = st.columns(6)

with k1:
    admin_kpi_card("Самостійний структурний підрозділ", clean(selected_row.get("department", "")))

with k2:
    admin_kpi_card("Рік", clean(selected_row.get("year", "")))

with k3:
    admin_kpi_card("Квартал", clean(selected_row.get("quarter", "")))

with k4:
    admin_kpi_card("Статус", clean(selected_row.get("status", "")))

with k5:
    # Розбиваємо Факт на два блоки (п.10)
    target_year_val = ""
    year_val = clean(selected_row.get("year", ""))
    if year_val and year_val.isdigit():
        col_name = f"target_{year_val}"
        measure_info_for_fact = strat_df[
            strat_df["code"].astype(str).str.strip() == selected_code
        ]
        if not measure_info_for_fact.empty and col_name in measure_info_for_fact.columns:
            target_year_val = clean(measure_info_for_fact.iloc[0].get(col_name, ""))

    admin_kpi_card(
        f"Планове значення ({year_val})",
        target_year_val if target_year_val else "—"
    )

with k6:
    admin_kpi_card("Фактичне квартальне значення", clean(selected_row.get("numeric_value", "")))

# Ще один рядок — Код заходу
k7, k8 = st.columns([1, 5])
with k7:
    admin_kpi_card("Код заходу", clean(selected_row.get("strat_code", "")))

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# СИСТЕМНА ОЦІНКА ЯКОСТІ  (п.11 — компактно, без файлів)
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card"><div class="card-title">Системна оцінка якості заявки</div>',
    unsafe_allow_html=True
)

# Відображаємо компактно — по 4-5 у рядку
per_row = 5
rows_chunks = [checks[i:i+per_row] for i in range(0, len(checks), per_row)]

for chunk in rows_chunks:
    qcols = st.columns(len(chunk))
    for idx, item in enumerate(chunk):
        label, value, ok = item
        with qcols[idx]:
            quality_card(label, value, ok)

completeness_pct = round(quality_score / total_fields * 100, 1)
st.progress(
    min(quality_score / total_fields, 1.0),
    text=f"Заповненість ключових полів: {completeness_pct}%"
)

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# АВТОМАТИЧНА СЛУЖБОВА РЕЗОЛЮЦІЯ  (п.12, п.13, п.14)
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card"><div class="card-title">Автоматична службова резолюція</div>'
    '<div class="card-subtitle">Система формує текст на основі якості заявки, статусу, фактичного значення та ризиків.</div>',
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="resolution-box">
        <div class="resolution-title">Проєкт резолюції</div>
        <div class="resolution-text">{auto_resolution.replace(chr(10), "<br>")}</div>
    </div>
    """,
    unsafe_allow_html=True
)

use_auto_resolution = st.checkbox(
    "Використати цей текст як коментар адміністратора",
    value=False,
    key=f"use_auto_resolution_{selected_id}"
)

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ІНФОРМАЦІЯ ПРО ЗАХІД  (п.15)
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card"><div class="card-title">Інформація про захід зі стратегічного плану</div>',
    unsafe_allow_html=True
)

measure_info = strat_df[
    strat_df["code"].astype(str).str.strip() == selected_code
].copy()

if measure_info.empty:
    st.warning("Захід не знайдено у стратегічній матриці.")
else:
    short_info = measure_info.iloc[0]

    st.markdown(
        f"""
        <div class="review-box">
            <div class="review-title">
                {clean(short_info.get("code", ""))} — {clean(short_info.get("name", ""))}
            </div>
            <div><b>Тип продукту:</b> {clean(short_info.get("product_type", ""))}</div>
            <div><b>Індикатор:</b> {clean(short_info.get("indicator", ""))}</div>
            <div><b>Одиниця виміру:</b> {clean(short_info.get("unit", ""))}</div>
            <div><b>Відповідальний ССП (головний):</b> {clean(short_info.get("resp_main", ""))}</div>
            <div><b>Співвиконавець 1:</b> {clean(short_info.get("resp_co_1", ""))}</div>
            <div><b>Співвиконавець 2:</b> {clean(short_info.get("resp_co_2", ""))}</div>
            <div><b>Період виконання:</b>
                {clean(short_info.get("start_date_plan", ""))} — {clean(short_info.get("end_date_plan", ""))}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.expander("Детальна таблиця заходу"):
        measure_display = measure_info.rename(columns={
            "type_marker":   "Тип маркера",
            "code":          "Код заходу",
            "name":          "Назва заходу",
            "product_type":  "Тип продукту",
            "indicator":     "Індикатор",
            "unit":          "Одиниця виміру",
            "base_2021":     "Базове значення 2021",
            "fact_2024":     "Звіт 2024",
            "expected_2025": "Очікуване 2025",
            "target_2026":   "План 2026",
            "target_2027":   "План 2027",
            "target_2028":   "План 2028",
            "resp_main":     "Відповідальні ССП\nГоловний",
            "resp_co_1":     "Відповідальні ССП\nСпіввиконавець 1",
            "resp_co_2":     "Відповідальні ССП\nСпіввиконавець 2",
            "start_date_plan": "Початкова дата зі СП",
            "end_date_plan":   "Кінцева дата зі СП",
        })

        detail_cols = [
            "Тип маркера", "Код заходу", "Назва заходу", "Тип продукту",
            "Індикатор", "Одиниця виміру",
            "Базове значення 2021", "Звіт 2024", "Очікуване 2025",
            "План 2026", "План 2027", "План 2028",
            "Відповідальні ССП\nГоловний",
            "Відповідальні ССП\nСпіввиконавець 1",
            "Відповідальні ССП\nСпіввиконавець 2",
            "Початкова дата зі СП", "Кінцева дата зі СП",
        ]

        available_cols = [c for c in detail_cols if c in measure_display.columns]
        st.dataframe(measure_display[available_cols], use_container_width=True, hide_index=True)

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ДАНІ ВІДПОВІДАЛЬНОЇ ОСОБИ  (п.16 — компактно)
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card"><div class="card-title">Дані відповідальної особи</div>',
    unsafe_allow_html=True
)

person_name  = clean(selected_row["responsible_person"])
person_phone = clean(selected_row["phone"])
person_email = clean(selected_row["email"])

st.markdown(
    f"""
    <div class="person-box">
        <div class="person-field">
            <span class="person-field-label">ПІБ</span>
            <span class="person-field-value">{person_name if person_name else "—"}</span>
        </div>
        <div class="person-field">
            <span class="person-field-label">Телефон</span>
            <span class="person-field-value">{person_phone if person_phone else "—"}</span>
        </div>
        <div class="person-field">
            <span class="person-field-label">Email</span>
            <span class="person-field-value">{person_email if person_email else "—"}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ОПИС ПРОГРЕСУ ТА РИЗИКИ  (п.18 — компактно)
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card"><div class="card-title">Опис прогресу та ризики</div>',
    unsafe_allow_html=True
)

pr1, pr2 = st.columns(2)

progress_val = clean(selected_row["progress_text"])
risks_val    = clean(selected_row["risks"])

with pr1:
    st.markdown(
        f"""
        <div class="progress-risk-box">
            <div class="progress-risk-label">Опис прогресу виконання</div>
            <div class="progress-risk-value">{progress_val if progress_val else "—"}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with pr2:
    risks_color = "#f87171" if risks_val else "#64748b"
    st.markdown(
        f"""
        <div class="progress-risk-box" style="border-left: 4px solid {risks_color};">
            <div class="progress-risk-label">Ризики / проблеми / відхилення</div>
            <div class="progress-risk-value" style="color: {'#fca5a5' if risks_val else '#64748b'};">
                {risks_val if risks_val else "Не зазначено"}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# РІШЕННЯ АДМІНІСТРАТОРА  (п.20, п.21)
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card"><div class="card-title">Рішення адміністратора</div>'
    '<div class="card-subtitle">Оберіть рішення та підтвердьте його однією кнопкою.</div>',
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="badge-wrap">
        <div class="badge {rec_badge}">Системна рекомендація: {recommendation}</div>
        <div class="badge">Заповненість: {completeness_pct}%</div>
        <div class="badge {status_badge}">Поточний статус: {approval_status}</div>
    </div>
    """,
    unsafe_allow_html=True
)

default_comment = auto_resolution if use_auto_resolution else clean(selected_row["admin_comment"])

with st.form(key=f"admin_decision_form_{selected_id}"):
    decision = st.radio(
        "Оберіть рішення",
        [
            "Направити на підпис керівнику ССП",
            "Повернути на доопрацювання",
            "Залишити в очікуванні"
        ],
        horizontal=True,
        key=f"decision_radio_{selected_id}"
    )

    decision_labels = {
        "Направити на підпис керівнику ССП": "🖊 Направлено на підпис керівнику ССП — після підпису дані будуть підтверджені",
        "Повернути на доопрацювання": "↩ Повернено на доопрацювання — відповідальна особа отримає сповіщення",
        "Залишити в очікуванні": "⏳ Залишено в очікуванні — без змін статусу",
    }

    st.markdown(
        f"""
        <div class="decision-box">
            {decision_labels.get(decision, decision)}
        </div>
        """,
        unsafe_allow_html=True
    )

    # Яскравий блок для коментаря (п.20)
    st.markdown(
        """
        <div style="
            background: rgba(37,99,235,0.12);
            border: 1px solid rgba(37,99,235,0.35);
            border-radius: 10px;
            padding: 10px 14px;
            margin-bottom: 6px;
            color: #93c5fd;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        ">✏ Коментар адміністратора</div>
        """,
        unsafe_allow_html=True
    )

    admin_comment = st.text_area(
        "Введіть коментар або обґрунтування рішення",
        value=default_comment,
        height=150,
        key=f"admin_comment_form_{selected_id}_{use_auto_resolution}",
        label_visibility="collapsed"
    )

    confirm_decision = st.form_submit_button(
        "Застосувати рішення",
        use_container_width=True
    )

if confirm_decision:
    if decision == "Направити на підпис керівнику ССП":
        # п.21 — новий статус "Направлено на підпис"
        new_status  = "Направлено на підпис"
        action_text = "Направлення на підпис керівнику ССП"
        success_text = (
            "✅ Заявку направлено на підпис керівнику ССП. "
            "Після підпису дані будуть підтверджені на головній сторінці."
        )
    elif decision == "Повернути на доопрацювання":
        new_status  = "Повернуто на доопрацювання"
        action_text = "Повернення заявки на доопрацювання"
        success_text = "↩ Заявку повернуто на доопрацювання."
    else:
        new_status  = "Очікує погодження"
        action_text = "Заявку залишено в очікуванні"
        success_text = "⏳ Заявку залишено в очікуванні."

    try:
        supabase.table("monitoring_requests").update({
            "approval_status": new_status,
            "admin_comment":   admin_comment
        }).eq("id", int(selected_id)).execute()

        write_log(selected_id, action_text, approval_status, new_status, admin_comment)

        st.success(success_text)
        st.rerun()

    except Exception as e:
        st.error("Не вдалося застосувати рішення.")
        st.exception(e)

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ОСТАННЯ ДІЯ ТА ІСТОРІЯ ЗМІН
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card"><div class="card-title">Остання дія та історія змін</div>',
    unsafe_allow_html=True
)

logs_df = load_logs(selected_id)

if logs_df.empty:
    st.info("Історії змін для цієї заявки поки що немає.")
else:
    latest_log = logs_df.iloc[0]

    st.markdown(
        f"""
        <div class="review-box">
            <div class="review-title">Остання дія: {clean(latest_log.get("action", ""))}</div>
            <div><b>Статус:</b>
                {clean(latest_log.get("old_status", ""))} →
                {clean(latest_log.get("new_status", ""))}
            </div>
            <div><b>Коментар:</b> {clean(latest_log.get("admin_comment", ""))}</div>
            <div><b>Дата:</b> {clean(latest_log.get("changed_at", ""))}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.expander("Повна історія змін заявки"):
        show_logs = logs_df.rename(columns={
            "changed_at":    "Дата зміни",
            "action":        "Дія",
            "old_status":    "Попередній статус",
            "new_status":    "Новий статус",
            "admin_comment": "Коментар адміністратора",
            "changed_by":    "Ким змінено"
        })

        show_cols = [
            "Дата зміни", "Дія", "Попередній статус",
            "Новий статус", "Коментар адміністратора", "Ким змінено"
        ]
        available_log_cols = [c for c in show_cols if c in show_logs.columns]
        st.dataframe(show_logs[available_log_cols], use_container_width=True, hide_index=True)

st.markdown('</div>', unsafe_allow_html=True)

with st.expander("Технічна таблиця заявок"):
    st.dataframe(filtered, use_container_width=True, hide_index=True)

# ──────────────────────────────────────────────
# FOOTER  (п.23)
# ──────────────────────────────────────────────

st.markdown(
    """
    <div class="footer">
        Розроблено департаментом стратегічного планування та макроекономічного прогнозування<br>
        Версія DEMO 1.4 | 2026 | Внутрішня система моніторингу стратегічного плану
    </div>
    """,
    unsafe_allow_html=True
)
