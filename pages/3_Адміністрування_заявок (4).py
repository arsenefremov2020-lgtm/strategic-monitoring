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
/* ─── BACKGROUND — м'який нейтральний ─── */
.stApp {
    background: linear-gradient(160deg, #f0f4f8 0%, #e8edf5 40%, #edf1f8 100%);
    min-height: 100vh;
}

.main .block-container {
    max-width: 1560px;
    padding-top: 1.2rem;
    position: relative;
}

/* ─── UA LINE ─── */
.ua-line {
    height: 5px;
    border-radius: 999px;
    background: linear-gradient(90deg, #005BBB 0%, #005BBB 50%, #FFD500 50%, #FFD500 100%);
    margin-bottom: 10px;
}

.ministry-label {
    text-align: right;
    color: #64748b;
    font-size: 12.5px;
    font-weight: 700;
    margin-bottom: 6px;
    letter-spacing: 0.02em;
}

/* ─── HEADER ─── */
.header-box {
    background: #ffffff;
    border: 1px solid #dde3ef;
    border-radius: 14px;
    padding: 20px 26px;
    margin-bottom: 14px;
    box-shadow: 0 2px 12px rgba(30,50,100,0.07);
}

.header-title {
    font-size: 28px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 5px;
    letter-spacing: -0.01em;
}

.header-subtitle {
    font-size: 14px;
    color: #64748b;
    line-height: 1.5;
}

.status-pill-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin-top: 11px;
}

.status-pill {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 999px;
    padding: 5px 11px;
    font-size: 12px;
    color: #475569;
    font-weight: 600;
}

/* ─── CARDS ─── */
.card {
    background: #ffffff;
    border: 1px solid #dde3ef;
    border-radius: 14px;
    padding: 18px 22px;
    margin: 12px 0;
    box-shadow: 0 2px 10px rgba(30,50,100,0.055);
}

.card-title {
    font-size: 17px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 5px;
}

.card-subtitle {
    color: #64748b;
    font-size: 13px;
    margin-bottom: 10px;
}

/* ─── FLOW BOX ─── */
.flow-box {
    background: #f8faff;
    border: 1px solid #c7d7f5;
    border-left: 4px solid #3b82f6;
    border-radius: 12px;
    padding: 13px 18px;
    margin: 12px 0;
}

.flow-title {
    font-weight: 800;
    color: #1e40af;
    margin-bottom: 9px;
    font-size: 12px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

.flow-steps {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
}

.flow-step {
    padding: 6px 12px;
    border-radius: 999px;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    color: #1d4ed8;
    font-size: 13px;
    font-weight: 600;
}

/* ─── BADGES ─── */
.badge-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin: 9px 0 13px 0;
}

.badge {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    color: #1d4ed8;
    border-radius: 999px;
    padding: 5px 11px;
    font-size: 12px;
    font-weight: 700;
}

.badge-green {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    color: #15803d;
}

.badge-yellow {
    background: #fefce8;
    border: 1px solid #fde68a;
    color: #92400e;
}

.badge-red {
    background: #fef2f2;
    border: 1px solid #fecaca;
    color: #b91c1c;
}

/* ─── ATTENTION GRID — 5 блоків в один рядок ─── */
.attention-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 10px;
    margin: 10px 0;
}

.attention-card {
    border-radius: 11px;
    padding: 13px 15px;
    border: 1px solid transparent;
}

.attention-title {
    font-size: 11px;
    font-weight: 800;
    margin-bottom: 5px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

.attention-value {
    font-size: 32px;
    font-weight: 950;
    line-height: 1.05;
}

.attention-note {
    font-size: 11px;
    margin-top: 4px;
    line-height: 1.3;
    opacity: 0.75;
}

.att-red    { background: #fef2f2; border-color: #fecaca; }
.att-red .attention-title  { color: #b91c1c; }
.att-red .attention-value  { color: #dc2626; }
.att-red .attention-note   { color: #991b1b; }

.att-yellow { background: #fefce8; border-color: #fde68a; }
.att-yellow .attention-title { color: #92400e; }
.att-yellow .attention-value { color: #d97706; }
.att-yellow .attention-note  { color: #78350f; }

.att-blue   { background: #eff6ff; border-color: #bfdbfe; }
.att-blue .attention-title { color: #1e40af; }
.att-blue .attention-value { color: #2563eb; }
.att-blue .attention-note  { color: #1e3a8a; }

.att-green  { background: #f0fdf4; border-color: #bbf7d0; }
.att-green .attention-title { color: #14532d; }
.att-green .attention-value { color: #16a34a; }
.att-green .attention-note  { color: #166534; }

/* ─── KPI CARDS ─── */
.admin-kpi-card {
    background: #f8fafc;
    border: 1px solid #dde3ef;
    border-radius: 11px;
    padding: 11px 13px;
    min-height: 82px;
}

.admin-kpi-label {
    color: #64748b;
    font-size: 11px;
    font-weight: 700;
    margin-bottom: 5px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.admin-kpi-value {
    color: #0f172a;
    font-size: 19px;
    font-weight: 850;
    line-height: 1.2;
    word-break: break-word;
}

/* ─── QUALITY GRID ─── */
.quality-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 8px;
    margin-bottom: 12px;
}

.quality-card {
    background: #f8fafc;
    border: 1px solid #dde3ef;
    border-radius: 10px;
    padding: 9px 11px;
    min-height: 64px;
}

.quality-good { border-left: 3px solid #22c55e; background: #f0fdf4; border-color: #bbf7d0; }
.quality-warn { border-left: 3px solid #f59e0b; background: #fefce8; border-color: #fde68a; }

.quality-label {
    color: #64748b;
    font-size: 10px;
    font-weight: 700;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.quality-value {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 13px;
    font-weight: 700;
    line-height: 1.25;
    color: #0f172a;
}

/* ─── CONCLUSION BOX ─── */
.quality-conclusion {
    background: #f8faff;
    border: 1px solid #c7d7f5;
    border-left: 4px solid #3b82f6;
    border-radius: 10px;
    padding: 11px 16px;
    margin-top: 4px;
    display: flex;
    align-items: center;
    gap: 12px;
}

.quality-conclusion-label {
    color: #64748b;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    min-width: 110px;
}

.quality-conclusion-value {
    font-size: 14px;
    font-weight: 800;
    color: #1e40af;
}

.quality-conclusion-pct {
    font-size: 13px;
    color: #475569;
    font-weight: 600;
    margin-left: auto;
}

/* ─── REVIEW BOX ─── */
.review-box {
    background: #f8fafc;
    border: 1px solid #dde3ef;
    border-radius: 11px;
    padding: 13px 16px;
    margin: 9px 0;
    color: #334155;
    font-size: 14px;
    line-height: 1.6;
}

.review-title {
    font-size: 14px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 7px;
}

/* ─── RESOLUTION ─── */
.resolution-box {
    background: #f8faff;
    border: 1px solid #c7d7f5;
    border-left: 5px solid #3b82f6;
    border-radius: 11px;
    padding: 16px 20px;
    margin: 10px 0;
}

.resolution-title {
    font-size: 13px;
    font-weight: 800;
    color: #1e40af;
    margin-bottom: 9px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.resolution-text {
    color: #1e293b;
    font-size: 14px;
    line-height: 1.7;
}

/* ─── DECISION BOX ─── */
.decision-box {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 10px;
    padding: 11px 15px;
    margin: 9px 0;
    color: #1d4ed8;
    font-size: 14px;
    font-weight: 700;
}

/* ─── PROGRESS / RISK BOXES ─── */
.progress-risk-box {
    background: #f8fafc;
    border: 1px solid #dde3ef;
    border-radius: 11px;
    padding: 13px 15px;
    min-height: 110px;
}

.progress-risk-label {
    color: #64748b;
    font-size: 11px;
    font-weight: 700;
    margin-bottom: 7px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.progress-risk-value {
    color: #1e293b;
    font-size: 14px;
    line-height: 1.6;
    white-space: pre-wrap;
}

/* ─── PERSON BOX ─── */
.person-box {
    background: #f0f7ff;
    border: 1px solid #bfdbfe;
    border-radius: 11px;
    padding: 14px 18px;
    display: flex;
    gap: 32px;
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
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.person-field-value {
    color: #1d4ed8;
    font-size: 14px;
    font-weight: 700;
}

/* ─── COMMENT HEADER ─── */
.comment-header {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 9px;
    padding: 9px 14px;
    margin-bottom: 6px;
    color: #1d4ed8;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

/* ─── SELECTBOX / INPUTS ─── */
div[data-testid="stSelectbox"] > div > div,
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    background: #ffffff !important;
    border: 1.5px solid #c7d4e8 !important;
    color: #0f172a !important;
    border-radius: 9px !important;
}

div[data-testid="stSelectbox"] > div > div:hover,
div[data-testid="stTextInput"] input:hover,
div[data-testid="stTextArea"] textarea:hover {
    border-color: #3b82f6 !important;
}

div[data-testid="stSelectbox"] label,
div[data-testid="stTextInput"] label,
div[data-testid="stTextArea"] label {
    color: #475569 !important;
    font-size: 13px !important;
    font-weight: 600 !important;
}

/* Radio */
div[data-testid="stRadio"] label {
    color: #334155 !important;
    font-size: 14px !important;
}

div[data-testid="stRadio"] > div {
    background: #f8fafc;
    border: 1.5px solid #dde3ef;
    border-radius: 11px;
    padding: 11px 15px;
}

/* Checkbox */
div[data-testid="stCheckbox"] label {
    color: #475569 !important;
}

/* Tabs */
button[data-baseweb="tab"] {
    color: #64748b !important;
    background: transparent !important;
    font-weight: 600 !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #1d4ed8 !important;
    border-bottom: 2px solid #3b82f6 !important;
}

/* Metric widgets */
div[data-testid="stMetric"] {
    background: #f8fafc;
    border: 1px solid #dde3ef;
    border-radius: 11px;
    padding: 11px 13px;
}

div[data-testid="stMetric"] label {
    color: #64748b !important;
}

div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: #0f172a !important;
}

/* Buttons */
div.stButton > button {
    border-radius: 9px;
    padding: 9px 16px;
    font-weight: 700;
    background: #eff6ff;
    border: 1.5px solid #bfdbfe;
    color: #1d4ed8;
    transition: all 0.15s;
}

div.stButton > button:hover {
    background: #dbeafe;
    border-color: #93c5fd;
}

div[data-testid="stFormSubmitButton"] button {
    border-radius: 11px;
    padding: 12px 18px;
    font-weight: 900;
    background: linear-gradient(135deg, #1d4ed8, #2563eb);
    border: none;
    color: white;
    box-shadow: 0 3px 12px rgba(37,99,235,0.35);
    transition: all 0.15s;
}

div[data-testid="stFormSubmitButton"] button:hover {
    background: linear-gradient(135deg, #2563eb, #3b82f6);
    box-shadow: 0 5px 18px rgba(37,99,235,0.5);
}

/* Expander */
div[data-testid="stExpander"] {
    background: #f8fafc;
    border: 1px solid #dde3ef;
    border-radius: 11px;
}

div[data-testid="stExpander"] summary {
    color: #1d4ed8 !important;
    font-weight: 700;
}

/* Dataframe */
div[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
}

/* Alerts */
div[data-testid="stWarning"] {
    background: #fefce8;
    border: 1px solid #fde68a;
    border-radius: 9px;
    color: #92400e;
}

div[data-testid="stInfo"] {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 9px;
    color: #1e40af;
}

div[data-testid="stSuccess"] {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 9px;
    color: #14532d;
}

div[data-testid="stCaptionContainer"] {
    color: #64748b !important;
}

/* Progress bar */
div[data-testid="stProgressBar"] > div {
    background: #e2e8f0;
    border-radius: 999px;
}

div[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, #2563eb, #06b6d4);
    border-radius: 999px;
}

/* Footer */
.footer {
    text-align: center;
    color: #94a3b8;
    font-size: 12px;
    margin-top: 48px;
    padding: 18px 0 10px 0;
    border-top: 1px solid #e2e8f0;
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
    return (datetime.now(timezone.utc) - dt).days


def split_ssp_values(value):
    text = clean(value).strip()
    if not text:
        return []
    return re.findall(r"\d+", text)


def admin_kpi_card(label, value):
    value = "" if value is None else str(value)
    st.markdown(
        f'<div class="admin-kpi-card">'
        f'<div class="admin-kpi-label">{label}</div>'
        f'<div class="admin-kpi-value">{value}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


def attention_card(title, value, note, css_class):
    st.markdown(
        f'<div class="attention-card {css_class}">'
        f'<div class="attention-title">{title}</div>'
        f'<div class="attention-value">{value}</div>'
        f'<div class="attention-note">{note}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


# ──────────────────────────────────────────────
# DATA LOADING
# ──────────────────────────────────────────────

@st.cache_data
def load_strat_matrix():
    df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=None, engine="openpyxl")
    data = df.iloc[7:].copy()

    def safe_col(idx):
        return data.iloc[:, idx] if idx < data.shape[1] else pd.Series([""] * len(data))

    result = pd.DataFrame({
        "type_marker":     safe_col(1),
        "code":            safe_col(2),
        "name":            safe_col(3),
        "product_type":    safe_col(4),
        "indicator":       safe_col(5),
        "unit":            safe_col(6),
        "base_2021":       safe_col(7),
        "fact_2024":       safe_col(8),
        "expected_2025":   safe_col(9),
        "target_2026":     safe_col(10),
        "target_2027":     safe_col(11),
        "target_2028":     safe_col(12),
        "resp_main":       safe_col(17),
        "resp_co_1":       safe_col(18),
        "resp_co_2":       safe_col(19),
        "start_date_plan": safe_col(22),
        "end_date_plan":   safe_col(23),
    })

    result = result.dropna(subset=["code"])
    result["code"] = result["code"].astype(str).str.strip()
    return result


def load_requests():
    resp = supabase.table("monitoring_requests").select("*").order("id", desc=True).execute()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()


def load_logs(request_id):
    resp = (
        supabase.table("monitoring_logs")
        .select("*")
        .eq("request_id", int(request_id))
        .order("changed_at", desc=True)
        .execute()
    )
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()


def write_log(request_id, action, old_status, new_status, admin_comment):
    supabase.table("monitoring_logs").insert({
        "request_id":    int(request_id),
        "action":        action,
        "old_status":    old_status,
        "new_status":    new_status,
        "admin_comment": admin_comment,
        "changed_by":    "Адміністратор"
    }).execute()


# ──────────────────────────────────────────────
# QUALITY ASSESSMENT
# ──────────────────────────────────────────────

def quality_assessment(row):
    checks = []
    score = 0

    fields = [
        ("numeric_value",      "Фактичне значення"),
        ("progress_text",      "Опис прогресу"),
        ("responsible_person", "Відповідальна особа"),
        ("phone",              "Телефон"),
        ("email",              "Email"),
        ("status",             "Статус заходу"),
        ("start_date",         "Початок виконання"),
        ("end_date",           "Кінець виконання"),
    ]

    for field, label in fields:
        ok = has_value(row.get(field, ""))
        checks.append((label, "Заповнено" if ok else "Відсутнє", ok))
        if ok:
            score += 1

    # Ризики — інверсія: добре якщо немає
    has_risks = has_value(row.get("risks", ""))
    checks.append(("Ризики / відхилення", "Є запис ⚠" if has_risks else "Не зазначено", not has_risks))
    if not has_risks:
        score += 1

    total_fields = 9
    pct = round(score / total_fields * 100, 1)

    if score >= 8 and not has_risks:
        recommendation = "Можна направляти на підпис"
        badge = "badge-green"
    elif score >= 6:
        recommendation = "Потребує перевірки"
        badge = "badge-yellow"
    else:
        recommendation = "Краще повернути на доопрацювання"
        badge = "badge-red"

    return checks, recommendation, badge, score, total_fields, pct


# ──────────────────────────────────────────────
# RESOLUTION GENERATOR — один абзац, готовий до копіювання
# ──────────────────────────────────────────────

def generate_resolution(row, recommendation, quality_score, total_fields, pct):
    request_id = clean(row.get("id", ""))
    code       = clean(row.get("strat_code", ""))
    year       = clean(row.get("year", ""))
    quarter    = clean(row.get("quarter", ""))
    dept       = clean(row.get("department", ""))
    status     = clean(row.get("status", ""))
    fact       = clean(row.get("numeric_value", ""))
    progress   = clean(row.get("progress_text", ""))
    risks      = clean(row.get("risks", ""))
    person     = clean(row.get("responsible_person", ""))
    phone      = clean(row.get("phone", ""))
    email      = clean(row.get("email", ""))
    start_d    = clean(row.get("start_date", ""))
    end_d      = clean(row.get("end_date", ""))

    # Формуємо перелік відсутніх полів
    missing_map = {
        "numeric_value":      "фактичне значення показника",
        "progress_text":      "опис прогресу виконання",
        "email":              "електронна пошта відповідальної особи",
        "phone":              "контактний телефон відповідальної особи",
        "status":             "статус виконання заходу",
        "start_date":         "дата початку виконання",
        "end_date":           "дата завершення виконання",
    }
    missing = [label for field, label in missing_map.items() if not has_value(row.get(field, ""))]

    date_range = f"{start_d} — {end_d}" if (has_value(start_d) and has_value(end_d)) else "не вказано"
    person_info = person
    if has_value(phone):
        person_info += f", тел.: {phone}"
    if has_value(email):
        person_info += f", e-mail: {email}"

    # ── ПОГОДЖЕННЯ ──
    if recommendation == "Можна направляти на підпис":
        risks_clause = ""
        if risks:
            risks_clause = (
                f" Додатково зазначаємо: у заявці задокументовано ризики та відхилення — {risks}; "
                f"це підлягає врахуванню при підписанні та подальшому моніторингу."
            )
        return (
            f"За результатами системного аналізу заявки ID {request_id} від ССП «{dept}» "
            f"щодо заходу {code} за {quarter} квартал {year} року (заповненість: {pct}%) "
            f"встановлено, що подані відомості відповідають вимогам моніторингу стратегічного плану. "
            f"Фактичне значення показника — {fact if fact else 'не вказано'}, "
            f"статус виконання — «{status if status else 'не вказано'}», "
            f"термін виконання — {date_range}. "
            f"Відповідальна особа: {person_info}. "
            f"Зміст прогресу: {progress if progress else 'не заповнено'}.{risks_clause} "
            f"Підстава для направлення на підпис: усі обов'язкові поля заповнені, "
            f"критичних відхилень не виявлено. Рекомендується НАПРАВИТИ НА ПІДПИС КЕРІВНИКУ ССП."
        )

    # ── ПЕРЕВІРКА ──
    if recommendation == "Потребує перевірки":
        issues = []
        if risks:
            issues.append(f"зафіксовано ризики / проблеми / відхилення: «{risks}»")
        if missing:
            issues.append(f"не заповнені поля: {', '.join(missing)}")
        issues_text = "; ".join(issues) if issues else "виявлено окремі невідповідності"

        return (
            f"За результатами системного аналізу заявки ID {request_id} від ССП «{dept}» "
            f"щодо заходу {code} за {quarter} квартал {year} року (заповненість: {pct}%) "
            f"встановлено, що {issues_text}. "
            f"Наявні дані: фактичне значення — {fact if fact else 'відсутнє'}, "
            f"статус виконання — «{status if status else 'не вказано'}», "
            f"термін — {date_range}. "
            f"Відповідальна особа: {person_info}. "
            f"До прийняття остаточного рішення рекомендується провести додаткову перевірку "
            f"поданих відомостей та уточнити виявлені розбіжності."
        )

    # ── ПОВЕРНЕННЯ ──
    missing_text = ", ".join(missing) if missing else "ключові поля заявки не заповнені належним чином"
    what_to_fix = []
    if not has_value(fact):
        what_to_fix.append("внести фактичне значення показника за звітний квартал")
    if not has_value(progress):
        what_to_fix.append("заповнити опис прогресу виконання заходу")
    if not has_value(status):
        what_to_fix.append("вказати статус виконання заходу")
    if not has_value(phone) or not has_value(email):
        what_to_fix.append("уточнити контактні дані відповідальної особи")
    if not has_value(start_d) or not has_value(end_d):
        what_to_fix.append("вказати терміни виконання заходу")

    fix_text = "; ".join(what_to_fix) if what_to_fix else "усунути виявлені недоліки"

    return (
        f"За результатами системного аналізу заявки ID {request_id} від ССП «{dept}» "
        f"щодо заходу {code} за {quarter} квартал {year} року (заповненість: {pct}%) "
        f"виявлено критичну неповноту поданих відомостей: {missing_text}. "
        f"Наявні дані: фактичне значення — {fact if fact else 'відсутнє'}, "
        f"статус — «{status if status else 'не вказано'}». "
        f"Відповідальна особа: {person_info}. "
        f"Для усунення виявлених недоліків необхідно: {fix_text}. "
        f"Заявку слід ПОВЕРНУТИ НА ДООПРАЦЮВАННЯ з обов'язковим повторним поданням "
        f"після виправлення всіх зазначених розбіжностей."
    )


# ──────────────────────────────────────────────
# ATTENTION SUMMARY
# ──────────────────────────────────────────────

def build_attention_summary(df):
    data = df.copy()
    if data.empty:
        return {k: pd.DataFrame() for k in
                ["long_waiting", "waiting", "not_counted", "returned", "approved"]}

    data["days_waiting"] = data["submitted_at"].apply(days_waiting)

    return {
        "long_waiting": data[
            (data["approval_status"].astype(str) == "Очікує погодження") &
            (data["days_waiting"].fillna(0) >= 5)
        ].copy(),
        "waiting": data[
            data["approval_status"].astype(str) == "Очікує погодження"
        ].copy(),
        "not_counted": data[
            ~data["approval_status"].astype(str).isin(["Погоджено"])
        ].copy(),
        "returned": data[
            data["approval_status"].astype(str) == "Повернуто на доопрацювання"
        ].copy(),
        "approved": data[
            data["approval_status"].astype(str) == "Погоджено"
        ].copy(),
    }


# ══════════════════════════════════════════════
# PAGE
# ══════════════════════════════════════════════

st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)
st.markdown(
    '<div class="ministry-label">🇺🇦 Міністерство економіки, довкілля та сільського господарства України</div>',
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
    "id", "department", "year", "quarter", "approval_status", "status",
    "strat_code", "responsible_person", "phone", "email",
    "numeric_value", "progress_text", "risks",
    "file_names", "file_urls", "admin_comment",
    "start_date", "end_date", "submitted_at"
]
for col in required_cols:
    if col not in df.columns:
        df[col] = ""

attention = build_attention_summary(df)

# ──────────────────────────────────────────────
# СИСТЕМНИЙ АНАЛІЗ
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card">'
    '<div class="card-title">Системний аналіз</div>'
    '<div class="card-subtitle">Автоматичний контроль усіх поданих відомостей</div>',
    unsafe_allow_html=True
)

def _att(title, value, note, css):
    return (
        f'<div class="attention-card {css}">'
        f'<div class="attention-title">{title}</div>'
        f'<div class="attention-value">{value}</div>'
        f'<div class="attention-note">{note}</div>'
        f'</div>'
    )

_lw  = len(attention["long_waiting"])
_wt  = len(attention["waiting"])
_nc  = len(attention["not_counted"])
_ret = len(attention["returned"])
_appr= len(attention["approved"])

st.markdown(
    '<div class="attention-grid">'
    + _att("На розгляді понад 5 днів", _lw,   "Без рішення тривалий час",            "att-red"    if _lw   else "att-green")
    + _att("На розгляді",              _wt,   "Очікують рішення адміністратора",     "att-yellow" if _wt   else "att-green")
    + _att("Не враховано",             _nc,   "Не отримали статус «Погоджено»",      "att-red"    if _nc   else "att-green")
    + _att("На доопрацюванні",         _ret,  "Повернуті для виправлення",           "att-blue"   if _ret  else "att-green")
    + _att("Погоджено",                _appr, "Відомості погоджені адміністратором", "att-green")
    + '</div>',
    unsafe_allow_html=True
)

# Expander — таблиці з вкладками
RENAME_MAP = {
    "id":                 "ID",
    "department":         "ССП",
    "status":             "Статус заходу",
    "strat_code":         "Код заходу",
    "year":               "Рік",
    "quarter":            "Квартал",
    "approval_status":    "Статус погодження",
    "responsible_person": "Відповідальна особа",
    "submitted_at":       "Дата подання",
    "start_date":         "Початок виконання",
    "end_date":           "Кінець виконання",
    "numeric_value":      "Факт. значення",
    "progress_text":      "Опис прогресу",
    "risks":              "Ризики",
    "admin_comment":      "Коментар адміністратора",
}

PRIORITY_COLS_KEYS = [
    "id", "department", "status", "strat_code",
    "start_date", "end_date", "year", "quarter",
]

def sort_and_show(frame):
    if frame.empty:
        st.info("Записів немає.")
        return
    frame = frame.copy()
    frame["_s"] = pd.to_numeric(
        frame["department"].astype(str).str.extract(r"(\d+)")[0], errors="coerce"
    )
    frame = frame.sort_values("_s").drop(columns=["_s"])
    all_cols = list(frame.columns)
    priority = [c for c in PRIORITY_COLS_KEYS if c in all_cols]
    rest = [c for c in all_cols if c not in priority]
    frame = frame[priority + rest].rename(
        columns={k: v for k, v in RENAME_MAP.items() if k in frame.columns}
    )
    st.dataframe(frame, use_container_width=True, hide_index=True)

with st.expander("Перегляд записів"):
    t1, t2, t3, t4, t5 = st.tabs([
        "На розгляді понад 5 днів",
        "На розгляді",
        "Не враховано",
        "На доопрацюванні",
        "Погоджено"
    ])
    with t1: sort_and_show(attention["long_waiting"])
    with t2: sort_and_show(attention["waiting"])
    with t3: sort_and_show(attention["not_counted"])
    with t4: sort_and_show(attention["returned"])
    with t5: sort_and_show(attention["approved"])

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ІНФОГРАФІКА
# ──────────────────────────────────────────────

st.markdown('<div class="card"><div class="card-title">Інфографіка</div>', unsafe_allow_html=True)

status_counts = {
    "На розгляді понад 5 днів": len(attention["long_waiting"]),
    "На розгляді":              len(attention["waiting"]),
    "Не враховано":             len(attention["not_counted"]),
    "На доопрацюванні":         len(attention["returned"]),
    "Погоджено":                len(attention["approved"]),
}

chart_df = pd.DataFrame({
    "Статус":    list(status_counts.keys()),
    "Кількість": list(status_counts.values())
})
chart_df = chart_df[chart_df["Кількість"] > 0]

if not chart_df.empty:
    color_map = {
        "На розгляді понад 5 днів": "#ef4444",
        "На розгляді":              "#f59e0b",
        "Не враховано":             "#f97316",
        "На доопрацюванні":         "#3b82f6",
        "Погоджено":                "#22c55e",
    }
    fig = px.pie(
        chart_df, names="Статус", values="Кількість", hole=0.48,
        title="Розподіл заявок за статусом погодження",
        color="Статус", color_discrete_map=color_map
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#334155",
        title_font_color="#0f172a",
        legend=dict(font=dict(color="#475569"), bgcolor="rgba(0,0,0,0)")
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Даних для відображення немає.")

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ПАРАМЕТРИ ВІДБОРУ
# ──────────────────────────────────────────────

st.markdown('<div class="card"><div class="card-title">Параметри відбору</div>', unsafe_allow_html=True)

all_ssp_raw = sorted(
    {idx for _, row in df.iterrows() for idx in split_ssp_values(row.get("department", ""))},
    key=lambda x: int(x) if str(x).isdigit() else 9999
)

f1, f2, f3, f4 = st.columns(4)
with f1:
    selected_ssp = st.selectbox("Самостійний структурний підрозділ", ["Усі"] + all_ssp_raw)
with f2:
    years = sorted(df["year"].dropna().astype(str).unique().tolist())
    selected_year = st.selectbox("Рік", ["Усі"] + years)
with f3:
    quarters = sorted(df["quarter"].dropna().astype(str).unique().tolist())
    selected_quarter = st.selectbox("Квартал", ["Усі"] + quarters)
with f4:
    selected_approval_status = st.selectbox(
        "Статус погодження",
        ["Активні до розгляду", "Усі", "Очікує погодження",
         "Повернуто на доопрацювання", "Направлено на підпис", "Погоджено"],
        index=0
    )

q1, q2 = st.columns([1, 2])
with q1:
    quick_filter = st.selectbox(
        "Швидкий фільтр",
        ["Усі заявки", "Тільки очікують", "Повернуті",
         "Із ризиками", "Останні подані", "На розгляді понад 5 днів"]
    )
with q2:
    search_query = st.text_input("Пошук за ID, назвою заходу, ПІБ або департаментом")

# ── фільтрація ──
filtered = df.copy()

if selected_ssp != "Усі":
    filtered = filtered[filtered["department"].astype(str).str.contains(selected_ssp, na=False)]
if selected_year != "Усі":
    filtered = filtered[filtered["year"].astype(str) == str(selected_year)]
if selected_quarter != "Усі":
    filtered = filtered[filtered["quarter"].astype(str) == str(selected_quarter)]

if selected_approval_status == "Активні до розгляду":
    filtered = filtered[filtered["approval_status"].astype(str).isin(
        ["Очікує погодження", "Повернуто на доопрацювання", "Направлено на підпис"]
    )]
elif selected_approval_status != "Усі":
    filtered = filtered[filtered["approval_status"].astype(str) == str(selected_approval_status)]

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
# ЧЕРГА НА РОЗГЛЯД
# ──────────────────────────────────────────────

queue_df = filtered[
    filtered["approval_status"].isin(["Очікує погодження", "Направлено на підпис"])
].copy()

if not queue_df.empty:
    st.markdown(
        '<div class="card">'
        '<div class="card-title">Черга на розгляд</div>'
        '<div class="card-subtitle">Заявки, що потребують рішення адміністратора.</div>',
        unsafe_allow_html=True
    )

    queue_df["_s"] = pd.to_numeric(
        queue_df["department"].astype(str).str.extract(r"(\d+)")[0], errors="coerce"
    )
    queue_df = queue_df.sort_values("_s").drop(columns=["_s"])

    queue_show = queue_df.rename(columns={
        "id":                 "ID",
        "department":         "Самостійний структурний підрозділ",
        "strat_code":         "Код заходу",
        "year":               "Рік",
        "quarter":            "Квартал",
        "status":             "Статус заходу",
        "approval_status":    "Статус погодження",
        "responsible_person": "Відповідальна особа",
        "submitted_at":       "Дата подання"
    })

    display_cols = [c for c in [
        "ID", "Самостійний структурний підрозділ", "Код заходу",
        "Рік", "Квартал", "Статус заходу", "Статус погодження",
        "Відповідальна особа", "Дата подання"
    ] if c in queue_show.columns]

    st.dataframe(queue_show[display_cols], use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ВИБІР ЗАЯВКИ
# ──────────────────────────────────────────────

st.markdown('<div class="card"><div class="card-title">Вибір заявки</div>', unsafe_allow_html=True)

selected_options = [
    f"ID {row['id']} | ССП {row['department']} | {row['strat_code']} | "
    f"{row['year']} {row['quarter']} квартал | {row['approval_status']} | "
    f"{clean(row['submitted_at'])}"
    for _, row in filtered.iterrows()
]

selected_request = st.selectbox("Оберіть заявку для перегляду та погодження", selected_options)
selected_id  = int(selected_request.split("|")[0].replace("ID", "").strip())
selected_row = filtered[filtered["id"].astype(int) == selected_id].iloc[0]

st.markdown('</div>', unsafe_allow_html=True)

approval_status = clean(selected_row["approval_status"])
selected_code   = clean(selected_row["strat_code"])

checks, recommendation, rec_badge, quality_score, total_fields, completeness_pct = quality_assessment(selected_row)
auto_resolution = generate_resolution(selected_row, recommendation, quality_score, total_fields, completeness_pct)

# ──────────────────────────────────────────────
# КАРТКА ЗАЯВКИ  (без "Код заходу" — він у заголовку)
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
        <div class="badge {status_badge}">Статус: {approval_status}</div>
        <div class="badge">Захід № {selected_code}</div>
        <div class="badge">ID {clean(selected_row['id'])}</div>
        <div class="badge {rec_badge}">Рекомендація: {recommendation}</div>
    </div>
    """,
    unsafe_allow_html=True
)

k1, k2, k3, k4, k5 = st.columns(5)

with k1:
    admin_kpi_card("Самостійний структурний підрозділ", clean(selected_row.get("department", "")))
with k2:
    admin_kpi_card("Рік / Квартал", f"{clean(selected_row.get('year', ''))} / {clean(selected_row.get('quarter', ''))}")
with k3:
    admin_kpi_card("Статус", clean(selected_row.get("status", "")))

# Планове значення з матриці
target_year_val = "—"
year_val = clean(selected_row.get("year", ""))
if year_val and year_val.isdigit():
    m_info = strat_df[strat_df["code"].astype(str).str.strip() == selected_code]
    col_name = f"target_{year_val}"
    if not m_info.empty and col_name in m_info.columns:
        v = clean(m_info.iloc[0].get(col_name, ""))
        if v:
            target_year_val = v

with k4:
    admin_kpi_card(f"Планове значення ({year_val})", target_year_val)
with k5:
    admin_kpi_card("Фактичне квартальне значення", clean(selected_row.get("numeric_value", "")))

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# СИСТЕМНА ОЦІНКА ЯКОСТІ — grid 5+4, висновок окремо
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card"><div class="card-title">Системна оцінка якості заявки</div>',
    unsafe_allow_html=True
)

# Рендеримо картки HTML-гридом, 5 per row
row1 = checks[:5]
row2 = checks[5:]

def render_quality_row(items):
    cols_html = ""
    for label, value, ok in items:
        css = "quality-good" if ok else "quality-warn"
        icon = "✅" if ok else "⚠️"
        cols_html += (
            f'<div class="quality-card {css}">'
            f'<div class="quality-label">{label}</div>'
            f'<div class="quality-value"><span>{icon}</span><span>{value}</span></div>'
            f'</div>'
        )
    st.markdown(f'<div class="quality-grid">{cols_html}</div>', unsafe_allow_html=True)

render_quality_row(row1)
if row2:
    render_quality_row(row2)

# Висновок системи
if recommendation == "Можна направляти на підпис":
    concl_color = "#15803d"
    concl_icon  = "✅"
elif recommendation == "Потребує перевірки":
    concl_color = "#92400e"
    concl_icon  = "⚠️"
else:
    concl_color = "#b91c1c"
    concl_icon  = "❌"

st.markdown(
    f"""
    <div class="quality-conclusion">
        <span class="quality-conclusion-label">Висновок системи</span>
        <span class="quality-conclusion-value" style="color:{concl_color};">
            {concl_icon} {recommendation}
        </span>
        <span class="quality-conclusion-pct">Заповненість: {completeness_pct}%</span>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# АВТОМАТИЧНА СЛУЖБОВА РЕЗОЛЮЦІЯ
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card">'
    '<div class="card-title">Автоматична службова резолюція</div>'
    '<div class="card-subtitle">Система формує текст на основі якості заявки, статусу, фактичного значення та ризиків.</div>',
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="resolution-box">
        <div class="resolution-title">Проєкт резолюції — готовий до копіювання</div>
        <div class="resolution-text">{auto_resolution}</div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ІНФОРМАЦІЯ ПРО ЗАХІД
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card"><div class="card-title">Інформація про захід зі стратегічного плану</div>',
    unsafe_allow_html=True
)

measure_info = strat_df[strat_df["code"].astype(str).str.strip() == selected_code].copy()

if measure_info.empty:
    st.warning("Захід не знайдено у стратегічній матриці.")
else:
    si = measure_info.iloc[0]
    st.markdown(
        f"""
        <div class="review-box">
            <div class="review-title">{clean(si.get("code",""))} — {clean(si.get("name",""))}</div>
            <div><b>Тип продукту:</b> {clean(si.get("product_type",""))}</div>
            <div><b>Індикатор:</b> {clean(si.get("indicator",""))}</div>
            <div><b>Одиниця виміру:</b> {clean(si.get("unit",""))}</div>
            <div><b>Відповідальний ССП:</b> {clean(si.get("resp_main",""))} &nbsp;|&nbsp;
                 Спів. 1: {clean(si.get("resp_co_1",""))} &nbsp;|&nbsp;
                 Спів. 2: {clean(si.get("resp_co_2",""))}</div>
            <div><b>Термін:</b> {clean(si.get("start_date_plan",""))} — {clean(si.get("end_date_plan",""))}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.expander("Детальна таблиця заходу"):
        measure_display = measure_info.rename(columns={
            "type_marker":     "Тип маркера",
            "code":            "Код заходу",
            "name":            "Назва заходу",
            "product_type":    "Тип продукту",
            "indicator":       "Індикатор",
            "unit":            "Одиниця виміру",
            "base_2021":       "Базове 2021",
            "fact_2024":       "Звіт 2024",
            "expected_2025":   "Очікуване 2025",
            "target_2026":     "План 2026",
            "target_2027":     "План 2027",
            "target_2028":     "План 2028",
            "resp_main":       "ССП Головний",
            "resp_co_1":       "ССП Спів. 1",
            "resp_co_2":       "ССП Спів. 2",
            "start_date_plan": "Початок (СП)",
            "end_date_plan":   "Кінець (СП)",
        })
        detail_cols = [
            "Тип маркера","Код заходу","Назва заходу","Тип продукту",
            "Індикатор","Одиниця виміру",
            "Базове 2021","Звіт 2024","Очікуване 2025",
            "План 2026","План 2027","План 2028",
            "ССП Головний","ССП Спів. 1","ССП Спів. 2",
            "Початок (СП)","Кінець (СП)",
        ]
        available = [c for c in detail_cols if c in measure_display.columns]
        st.dataframe(measure_display[available], use_container_width=True, hide_index=True)

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ДАНІ ВІДПОВІДАЛЬНОЇ ОСОБИ
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
            <span class="person-field-value">{person_name or "—"}</span>
        </div>
        <div class="person-field">
            <span class="person-field-label">Телефон</span>
            <span class="person-field-value">{person_phone or "—"}</span>
        </div>
        <div class="person-field">
            <span class="person-field-label">Email</span>
            <span class="person-field-value">{person_email or "—"}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ОПИС ПРОГРЕСУ ТА РИЗИКИ
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
        f'<div class="progress-risk-box">'
        f'<div class="progress-risk-label">Опис прогресу виконання</div>'
        f'<div class="progress-risk-value">{progress_val or "—"}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

with pr2:
    r_color = "#dc2626" if risks_val else "#64748b"
    r_text_color = "#b91c1c" if risks_val else "#94a3b8"
    st.markdown(
        f'<div class="progress-risk-box" style="border-left: 3px solid {r_color};">'
        f'<div class="progress-risk-label">Ризики / проблеми / відхилення</div>'
        f'<div class="progress-risk-value" style="color:{r_text_color};">'
        f'{risks_val or "Не зазначено"}'
        f'</div></div>',
        unsafe_allow_html=True
    )

st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# РІШЕННЯ АДМІНІСТРАТОРА
# ──────────────────────────────────────────────

st.markdown(
    '<div class="card">'
    '<div class="card-title">Рішення адміністратора</div>'
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

default_comment = clean(selected_row["admin_comment"])

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
        "Направити на підпис керівнику ССП":
            "🖊 Направлено на підпис керівнику ССП — після підпису дані будуть підтверджені",
        "Повернути на доопрацювання":
            "↩ Повернено на доопрацювання — відповідальна особа отримає сповіщення",
        "Залишити в очікуванні":
            "⏳ Залишено в очікуванні — без змін статусу",
    }

    st.markdown(
        f'<div class="decision-box">{decision_labels.get(decision, decision)}</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="comment-header">✏ Коментар адміністратора</div>',
        unsafe_allow_html=True
    )

    admin_comment = st.text_area(
        "Введіть коментар або обґрунтування рішення",
        value=default_comment,
        height=130,
        key=f"admin_comment_form_{selected_id}",
        label_visibility="collapsed"
    )

    confirm_decision = st.form_submit_button(
        "Застосувати рішення",
        use_container_width=True
    )

if confirm_decision:
    if decision == "Направити на підпис керівнику ССП":
        new_status   = "Направлено на підпис"
        action_text  = "Направлення на підпис керівнику ССП"
        success_text = "✅ Заявку направлено на підпис керівнику ССП. Після підпису дані будуть підтверджені на головній сторінці."
    elif decision == "Повернути на доопрацювання":
        new_status   = "Повернуто на доопрацювання"
        action_text  = "Повернення заявки на доопрацювання"
        success_text = "↩ Заявку повернуто на доопрацювання."
    else:
        new_status   = "Очікує погодження"
        action_text  = "Заявку залишено в очікуванні"
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
            <div class="review-title">Остання дія: {clean(latest_log.get("action",""))}</div>
            <div><b>Статус:</b>
                {clean(latest_log.get("old_status",""))} → {clean(latest_log.get("new_status",""))}
            </div>
            <div><b>Коментар:</b> {clean(latest_log.get("admin_comment",""))}</div>
            <div><b>Дата:</b> {clean(latest_log.get("changed_at",""))}</div>
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
        show_cols = ["Дата зміни","Дія","Попередній статус",
                     "Новий статус","Коментар адміністратора","Ким змінено"]
        st.dataframe(
            show_logs[[c for c in show_cols if c in show_logs.columns]],
            use_container_width=True, hide_index=True
        )

st.markdown('</div>', unsafe_allow_html=True)

with st.expander("Технічна таблиця заявок"):
    st.dataframe(filtered, use_container_width=True, hide_index=True)

st.markdown(
    """
    <div class="footer">
        Розроблено департаментом стратегічного планування та макроекономічного прогнозування<br>
        Версія DEMO 1.4 | 2026 | Внутрішня система моніторингу стратегічного плану
    </div>
    """,
    unsafe_allow_html=True
)
