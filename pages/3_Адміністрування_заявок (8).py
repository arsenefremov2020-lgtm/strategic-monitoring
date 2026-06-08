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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

* { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; }

.stApp { background: #f0f4fb; min-height: 100vh; }

.main .block-container { max-width: 1560px; padding-top: 1rem; }

.ua-line {
    height: 4px; border-radius: 0;
    background: linear-gradient(90deg, #005BBB 0%, #005BBB 50%, #FFD500 50%, #FFD500 100%);
    margin-bottom: 0;
}

.ministry-label {
    text-align: right; color: #6b7a99; font-size: 12px;
    font-weight: 600; margin-bottom: 6px;
}

.header-box {
    background: linear-gradient(135deg, #1a56db 0%, #1e40af 60%, #1d4ed8 100%);
    border-radius: 16px; padding: 22px 28px; margin-bottom: 16px;
    box-shadow: 0 4px 20px rgba(26,86,219,0.3);
    position: relative; overflow: hidden;
}
.header-box::before {
    content: ""; position: absolute; top: -40px; right: -40px;
    width: 160px; height: 160px; border-radius: 50%;
    background: rgba(255,255,255,0.06);
}
.header-title { font-size: 26px; font-weight: 800; color: #ffffff; margin-bottom: 5px; }
.header-subtitle { font-size: 13.5px; color: rgba(255,255,255,0.78); line-height: 1.5; }

.status-pill-wrap { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 12px; }
.status-pill {
    background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25);
    border-radius: 999px; padding: 4px 11px; font-size: 11.5px;
    color: rgba(255,255,255,0.9); font-weight: 600;
}

.flow-box {
    background: #ffffff; border: 1px solid #e2e8f5;
    border-left: 4px solid #1a56db; border-radius: 12px;
    padding: 12px 18px; margin: 12px 0;
    box-shadow: 0 1px 6px rgba(26,86,219,0.07);
}
.flow-title { font-weight: 700; color: #1a56db; margin-bottom: 9px; font-size: 11px; letter-spacing: 0.07em; text-transform: uppercase; }
.flow-steps { display: flex; flex-wrap: wrap; gap: 7px; }
.flow-step { padding: 5px 13px; border-radius: 999px; background: #eff6ff; border: 1px solid #bfdbfe; color: #1d4ed8; font-size: 12.5px; font-weight: 600; }

.card {
    background: #ffffff; border: 1px solid #e2e8f5;
    border-radius: 14px; padding: 18px 22px; margin: 12px 0;
    box-shadow: 0 2px 10px rgba(15,30,80,0.06);
}
.card-title {
    font-size: 16px; font-weight: 700; color: #111827; margin-bottom: 4px;
    display: flex; align-items: center; gap: 8px;
}
.card-title::before {
    content: ""; display: inline-block; width: 4px; height: 18px;
    background: linear-gradient(180deg, #1a56db, #60a5fa);
    border-radius: 2px; flex-shrink: 0;
}
.card-subtitle { color: #6b7a99; font-size: 13px; margin-bottom: 12px; padding-left: 12px; }

.badge-wrap { display: flex; flex-wrap: wrap; gap: 7px; margin: 8px 0 13px 0; }
.badge { background: #eff6ff; border: 1.5px solid #bfdbfe; color: #1d4ed8; border-radius: 8px; padding: 4px 11px; font-size: 12px; font-weight: 600; }
.badge-green { background: #f0fdf4; border-color: #86efac; color: #15803d; }
.badge-yellow { background: #fefce8; border-color: #fde68a; color: #92400e; }
.badge-red { background: #fef2f2; border-color: #fca5a5; color: #b91c1c; }

.attention-grid {
    display: grid; grid-template-columns: repeat(5, 1fr);
    gap: 12px; margin: 12px 0;
}
.attention-card {
    border-radius: 14px; padding: 16px 18px; border: none;
    position: relative; overflow: hidden;
    box-shadow: 0 3px 14px rgba(0,0,0,0.09);
    transition: transform 0.15s, box-shadow 0.15s;
}
.attention-card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.13); }
.attention-card::after {
    content: ""; position: absolute; bottom: -18px; right: -18px;
    width: 72px; height: 72px; border-radius: 50%; background: rgba(255,255,255,0.12);
}
.attention-title { font-size: 11px; font-weight: 700; margin-bottom: 8px; letter-spacing: 0.05em; text-transform: uppercase; color: rgba(255,255,255,0.88); }
.attention-value { font-size: 36px; font-weight: 800; line-height: 1; color: #ffffff; }
.attention-note { font-size: 11px; margin-top: 5px; color: rgba(255,255,255,0.75); line-height: 1.3; }
.att-red    { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); }
.att-yellow { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); }
.att-blue   { background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); }
.att-green  { background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); }

.admin-kpi-card {
    background: #ffffff; border: 1px solid #e2e8f5;
    border-radius: 12px; padding: 13px 15px; min-height: 86px;
    box-shadow: 0 2px 8px rgba(15,30,80,0.05);
    transition: box-shadow 0.15s;
}
.admin-kpi-card:hover { box-shadow: 0 4px 14px rgba(26,86,219,0.1); }
.admin-kpi-label { color: #6b7a99; font-size: 11px; font-weight: 600; margin-bottom: 6px; letter-spacing: 0.04em; text-transform: uppercase; }
.admin-kpi-value { color: #111827; font-size: 18px; font-weight: 700; line-height: 1.2; word-break: break-word; }

.quality-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 9px; margin-bottom: 10px; }
.quality-card { background: #f8fafc; border: 1.5px solid #e2e8f5; border-radius: 10px; padding: 10px 12px; min-height: 66px; }
.quality-good { border-left: 4px solid #22c55e; background: #f0fdf4; border-color: #86efac; }
.quality-warn { border-left: 4px solid #f59e0b; background: #fffbeb; border-color: #fde68a; }
.quality-label { color: #6b7a99; font-size: 10px; font-weight: 700; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 0.04em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.quality-value { display: flex; align-items: center; gap: 5px; font-size: 13px; font-weight: 700; color: #111827; line-height: 1.25; }

.quality-conclusion {
    background: linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%);
    border: 1.5px solid #bfdbfe; border-left: 5px solid #1a56db;
    border-radius: 10px; padding: 11px 16px; margin-top: 6px;
    display: flex; align-items: center; gap: 12px;
}
.quality-conclusion-label { color: #6b7a99; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; min-width: 110px; }
.quality-conclusion-value { font-size: 14px; font-weight: 800; }
.quality-conclusion-pct { font-size: 13px; color: #475569; font-weight: 600; margin-left: auto; background: #e0e7ff; padding: 3px 10px; border-radius: 999px; }

.review-box { background: #f8fafc; border: 1px solid #e2e8f5; border-radius: 11px; padding: 14px 17px; margin: 9px 0; color: #374151; font-size: 14px; line-height: 1.65; }
.review-title { font-size: 14px; font-weight: 700; color: #111827; margin-bottom: 8px; }

.resolution-box {
    background: linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%);
    border: 1.5px solid #93c5fd; border-left: 5px solid #1a56db;
    border-radius: 12px; padding: 18px 22px; margin: 10px 0;
    box-shadow: 0 2px 10px rgba(26,86,219,0.08);
}
.resolution-title { font-size: 11px; font-weight: 800; color: #1a56db; margin-bottom: 10px; letter-spacing: 0.07em; text-transform: uppercase; display: flex; align-items: center; gap: 7px; }
.resolution-title::before { content: "📋"; font-size: 14px; }
.resolution-text { color: #1e293b; font-size: 14px; line-height: 1.75; }

.decision-box { background: linear-gradient(135deg, #eff6ff, #e0f2fe); border: 1.5px solid #93c5fd; border-radius: 10px; padding: 12px 16px; margin: 9px 0; color: #1d4ed8; font-size: 14px; font-weight: 600; }

.progress-risk-box { background: #ffffff; border: 1.5px solid #e2e8f5; border-radius: 12px; padding: 14px 16px; min-height: 110px; box-shadow: 0 1px 6px rgba(15,30,80,0.05); }
.progress-risk-label { color: #6b7a99; font-size: 11px; font-weight: 700; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em; }
.progress-risk-value { color: #1e293b; font-size: 14px; line-height: 1.65; white-space: pre-wrap; }

.person-box { background: linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%); border: 1.5px solid #bfdbfe; border-radius: 12px; padding: 14px 20px; display: flex; gap: 36px; flex-wrap: wrap; align-items: center; box-shadow: 0 1px 6px rgba(26,86,219,0.07); }
.person-field { display: flex; flex-direction: column; gap: 3px; }
.person-field-label { color: #6b7a99; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
.person-field-value { color: #1a56db; font-size: 14px; font-weight: 700; }

.comment-header { background: linear-gradient(135deg, #eff6ff, #e0f2fe); border: 1.5px solid #93c5fd; border-radius: 9px; padding: 9px 14px; margin-bottom: 6px; color: #1d4ed8; font-size: 11px; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; }

div[data-testid="stSelectbox"] > div > div,
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    background: #ffffff !important; border: 1.5px solid #d1daf0 !important;
    color: #111827 !important; border-radius: 9px !important; font-size: 14px !important;
}
div[data-testid="stSelectbox"] label,
div[data-testid="stTextInput"] label,
div[data-testid="stTextArea"] label { color: #374151 !important; font-size: 13px !important; font-weight: 600 !important; }

div[data-testid="stRadio"] label { color: #374151 !important; font-size: 14px !important; font-weight: 500 !important; }
div[data-testid="stRadio"] > div { background: #ffffff; border: 1.5px solid #e2e8f5; border-radius: 12px; padding: 12px 16px; box-shadow: 0 1px 5px rgba(15,30,80,0.05); }

div[data-testid="stCheckbox"] label { color: #374151 !important; }

button[data-baseweb="tab"] { color: #6b7a99 !important; font-weight: 600 !important; font-size: 13px !important; }
button[data-baseweb="tab"][aria-selected="true"] { color: #1a56db !important; border-bottom: 2px solid #1a56db !important; font-weight: 700 !important; }

div[data-testid="stMetric"] { background: #ffffff; border: 1px solid #e2e8f5; border-radius: 12px; padding: 12px 14px; box-shadow: 0 1px 6px rgba(15,30,80,0.05); }
div[data-testid="stMetric"] label { color: #6b7a99 !important; font-size: 12px !important; }
div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #111827 !important; font-weight: 700 !important; }

div.stButton > button { border-radius: 9px; padding: 9px 18px; font-weight: 600; font-size: 13.5px; background: #ffffff; border: 1.5px solid #d1daf0; color: #1a56db; transition: all 0.15s; box-shadow: 0 1px 4px rgba(15,30,80,0.07); }
div.stButton > button:hover { background: #eff6ff; border-color: #93c5fd; box-shadow: 0 3px 10px rgba(26,86,219,0.15); }

div[data-testid="stFormSubmitButton"] button { border-radius: 10px; padding: 12px 20px; font-weight: 700; font-size: 14px; background: linear-gradient(135deg, #1a56db 0%, #2563eb 100%); border: none; color: #ffffff; box-shadow: 0 4px 14px rgba(26,86,219,0.35); transition: all 0.15s; }
div[data-testid="stFormSubmitButton"] button:hover { background: linear-gradient(135deg, #1e40af 0%, #1a56db 100%); box-shadow: 0 6px 20px rgba(26,86,219,0.5); }

div[data-testid="stExpander"] { background: #ffffff; border: 1px solid #e2e8f5; border-radius: 12px; box-shadow: 0 1px 5px rgba(15,30,80,0.05); }
div[data-testid="stExpander"] summary { color: #1a56db !important; font-weight: 700; font-size: 14px !important; }

div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; border: 1px solid #e2e8f5; }

div[data-testid="stWarning"] { background: #fffbeb; border: 1px solid #fde68a; border-left: 4px solid #f59e0b; border-radius: 10px; color: #78350f; font-weight: 500; }
div[data-testid="stInfo"] { background: #eff6ff; border: 1px solid #bfdbfe; border-left: 4px solid #3b82f6; border-radius: 10px; color: #1e40af; font-weight: 500; }
div[data-testid="stSuccess"] { background: #f0fdf4; border: 1px solid #86efac; border-left: 4px solid #22c55e; border-radius: 10px; color: #14532d; font-weight: 500; }

div[data-testid="stCaptionContainer"] { color: #6b7a99 !important; font-size: 12px !important; }

div[data-testid="stProgressBar"] > div { background: #e2e8f5; border-radius: 999px; }
div[data-testid="stProgressBar"] > div > div { background: linear-gradient(90deg, #1a56db, #3b82f6); border-radius: 999px; }

.footer { text-align: center; color: #9ca3af; font-size: 12px; margin-top: 48px; padding: 18px 0 10px 0; border-top: 1px solid #e2e8f5; }
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
# СТАТУС — автоматична перевірка відповідності
# Пороги: <75% → Виконується | 75-99% → Частково виконано | ≥100% → Виконано
# ──────────────────────────────────────────────

def compute_execution_pct(fact_str, plan_str):
    """Повертає (float_pct або None, fact_float або None, plan_float або None)."""
    try:
        f = float(str(fact_str).replace(",", ".").strip())
        p = float(str(plan_str).replace(",", ".").strip())
        if p == 0:
            return None, f, p
        return round(f / p * 100, 1), f, p
    except Exception:
        return None, None, None


def expected_status(exec_pct):
    """Повертає очікуваний статус за відсотком виконання."""
    if exec_pct is None:
        return None
    if exec_pct >= 100:
        return "Виконано"
    if exec_pct >= 75:
        return "Частково виконано"
    return "Виконується"


def analyze_request(row, plan_val_str):
    """
    Повний аналіз заявки. Повертає dict з усіма знахідками.
    plan_val_str — рядок планового значення з стратматриці.
    """
    fact_str   = clean(row.get("numeric_value", ""))
    status     = clean(row.get("status", ""))
    progress   = clean(row.get("progress_text", ""))
    risks      = clean(row.get("risks", ""))
    start_d    = clean(row.get("start_date", ""))
    end_d      = clean(row.get("end_date", ""))

    issues   = []   # критичні — треба повертати
    warnings = []   # застереження — для погодження з приміткою

    # 1. Відсутні обов'язкові поля
    missing_fields = []
    field_map = {
        "numeric_value":      "фактичне значення показника",
        "progress_text":      "опис прогресу виконання",
        "status":             "статус виконання заходу",
        "start_date":         "дата початку виконання",
        "end_date":           "дата завершення виконання",
        "responsible_person": "відповідальна особа",
        "phone":              "контактний телефон",
        "email":              "електронна пошта",
    }
    for field, label in field_map.items():
        if not has_value(row.get(field, "")):
            missing_fields.append(label)

    if missing_fields:
        issues.append({
            "type": "missing_fields",
            "fields": missing_fields,
            "text": f"не заповнені обов'язкові поля: {', '.join(missing_fields)}"
        })

    # 2. Перевірка відповідності статусу плановому значенню
    status_mismatch = None
    exec_pct, fact_num, plan_num = compute_execution_pct(fact_str, plan_val_str)
    exp_status = expected_status(exec_pct)

    if exec_pct is not None and exp_status is not None and has_value(status):
        if status.strip() != exp_status:
            status_mismatch = {
                "type":        "status_mismatch",
                "fact":        fact_num,
                "fact_num":    fact_num,
                "plan":        plan_num,
                "plan_num":    plan_num,
                "exec_pct":    exec_pct,
                "submitted":   status,
                "expected":    exp_status,
                "text": (
                    f"невідповідність статусу: подано «{status}», "
                    f"однак при виконанні {exec_pct}% від планового значення "
                    f"({fact_num} з {plan_num}) коректний статус — «{exp_status}»"
                )
            }
            issues.append(status_mismatch)

    # 3. Термін виконання минув, а статус не закритий
    deadline_overdue = False
    if has_value(end_d):
        try:
            end_dt = pd.to_datetime(end_d, errors="coerce")
            if not pd.isna(end_dt):
                if end_dt < pd.Timestamp.now():
                    closed = {"Виконано", "Втратило актуальність"}
                    if status not in closed:
                        deadline_overdue = True
                        issues.append({
                            "type": "deadline_overdue",
                            "text": (
                                f"термін виконання заходу ({end_d}) минув, "
                                f"однак статус не закрито — зазначено «{status}»"
                            )
                        })
        except Exception:
            pass

    # 4. Ризики при статусі «Виконано»
    if risks and status == "Виконано":
        warnings.append({
            "type": "risks_with_done",
            "text": (
                f"зафіксовано ризики/відхилення при статусі «Виконано» — "
                f"це потребує пояснення: {risks}"
            )
        })

    # 5. Опис прогресу є, але факт відсутній
    if has_value(progress) and not has_value(fact_str):
        warnings.append({
            "type": "progress_no_fact",
            "text": "опис прогресу надано, але фактичне числове значення відсутнє"
        })

    # 6. Факт є, але прогрес відсутній
    if has_value(fact_str) and not has_value(progress):
        warnings.append({
            "type": "fact_no_progress",
            "text": "фактичне значення вказано, але опис прогресу виконання відсутній"
        })

    # 7. Нульове фактичне значення при статусі, що не «Виконується» / «Термін не настав»
    if fact_num == 0.0 and status not in ("Виконується", "Термін не настав", ""):
        warnings.append({
            "type": "zero_fact",
            "text": (
                f"фактичне значення дорівнює нулю при статусі «{status}» — "
                f"можлива помилка або дійсно нульовий результат"
            )
        })

    # 8. Ризики зафіксовані — завжди як застереження
    if risks and status != "Виконано":
        warnings.append({
            "type": "has_risks",
            "text": f"зафіксовано ризики/проблеми/відхилення: {risks}"
        })

    return {
        "issues":          issues,
        "warnings":        warnings,
        "missing_fields":  missing_fields,
        "status_mismatch": status_mismatch,
        "exec_pct":        exec_pct,
        "fact_num":        fact_num,
        "plan_num":        plan_num,
        "exp_status":      exp_status,
        "deadline_overdue": deadline_overdue,
    }


# ──────────────────────────────────────────────
# RESOLUTION GENERATOR — готовий до копіювання текст
# ──────────────────────────────────────────────

def generate_resolution(row, recommendation, plan_val_str):
    code      = clean(row.get("strat_code", ""))
    year      = clean(row.get("year", ""))
    quarter   = clean(row.get("quarter", ""))
    dept      = clean(row.get("department", ""))
    status    = clean(row.get("status", ""))
    fact      = clean(row.get("numeric_value", ""))
    progress  = clean(row.get("progress_text", ""))
    risks     = clean(row.get("risks", ""))
    person    = clean(row.get("responsible_person", ""))
    phone     = clean(row.get("phone", ""))
    email     = clean(row.get("email", ""))
    end_d     = clean(row.get("end_date", ""))

    analysis = analyze_request(row, plan_val_str)
    exec_pct  = analysis["exec_pct"]
    fact_num  = analysis["fact_num"]
    plan_num  = analysis["plan_num"]
    sm        = analysis["status_mismatch"]

    # Форматуємо план/факт рядки
    plan_str = str(plan_val_str).strip() if has_value(plan_val_str) else None
    fact_str = fact if has_value(fact) else None

    pf_clause = ""
    if plan_str and fact_str and exec_pct is not None:
        pf_clause = (
            f"Планове значення показника на {year} рік — {plan_str}, "
            f"фактичне значення за {quarter} квартал — {fact_str} "
            f"({exec_pct}% від річного плану). "
        )
    elif fact_str:
        pf_clause = f"Фактичне значення за {quarter} квартал — {fact_str}. "
    elif plan_str:
        pf_clause = f"Планове значення на {year} рік — {plan_str}. Фактичне значення не вказано. "

    header = (
        f"Відомості щодо заходу {code} за {quarter} квартал {year} року "
        f"від підрозділу {dept} (відповідальна особа: {person}"
        + (f", тел.: {phone}" if has_value(phone) else "")
        + (f", e-mail: {email}" if has_value(email) else "")
        + ") розглянуто. "
    )

    # ── ПОГОДЖЕННЯ ──
    if recommendation == "Можна направляти на підпис":
        warn_texts = [w["text"] for w in analysis["warnings"]]
        warn_clause = ""
        if warn_texts:
            warn_clause = (
                f" Разом із тим, звертаємо увагу на таке: {'; '.join(warn_texts)}. "
                f"Це підлягає врахуванню при підписанні та подальшому моніторингу."
            )
        return (
            header
            + pf_clause
            + f"Статус виконання — «{status}». "
            + (f"Прогрес: {progress}. " if has_value(progress) else "")
            + "Подані відомості визнано достатніми для погодження."
            + warn_clause
            + " Направляємо на підпис керівнику підрозділу."
        )

    # ── ПОВЕРНЕННЯ — невідповідність статусу ──
    if sm is not None and len(analysis["issues"]) == 1:
        # Єдина проблема — тільки статус не той
        fact_v = sm.get("fact") or sm.get("fact_num") or "—"
        plan_v = sm.get("plan") or sm.get("plan_num") or "—"
        return (
            header
            + pf_clause
            + f"Зазначений статус виконання — «{sm['submitted']}». "
            f"Однак при виконанні {sm['exec_pct']}% від річного планового значення "
            f"({fact_v} з {plan_v}) відповідно до методології моніторингу "
            f"коректний статус — «{sm['expected']}». "
            f"Відомості повертаються на доопрацювання. "
            f"Просимо виправити статус виконання на «{sm['expected']}» та подати відомості повторно."
        )

    # ── ПОВЕРНЕННЯ — загальне (кілька проблем) ──
    issue_parts = []

    if analysis["missing_fields"]:
        issue_parts.append(
            f"не заповнені обов'язкові поля: {', '.join(analysis['missing_fields'])}"
        )

    if sm is not None:
        fact_v = sm.get("fact") or sm.get("fact_num") or "—"
        plan_v = sm.get("plan") or sm.get("plan_num") or "—"
        issue_parts.append(
            f"невідповідність статусу: подано «{sm['submitted']}», "
            f"при виконанні {sm['exec_pct']}% ({fact_v} з {plan_v}) коректний статус — «{sm['expected']}»"
        )

    if analysis["deadline_overdue"]:
        issue_parts.append(
            f"термін виконання ({end_d}) минув, але статус не закрито"
        )

    # Додаємо застереження що стають причиною повернення
    for w in analysis["warnings"]:
        if w["type"] in ("progress_no_fact", "fact_no_progress"):
            issue_parts.append(w["text"])

    issues_text = "; ".join(issue_parts) if issue_parts else "виявлено невідповідності у поданих відомостях"

    # Формуємо інструкцію що виправити
    fix_parts = []
    if analysis["missing_fields"]:
        fix_parts.append(f"заповнити відсутні поля ({', '.join(analysis['missing_fields'])})")
    if sm is not None:
        fix_parts.append(f"змінити статус виконання на «{sm['expected']}»")
    if analysis["deadline_overdue"]:
        fix_parts.append("закрити або пояснити статус заходу з урахуванням минулого терміну")
    for w in analysis["warnings"]:
        if w["type"] == "progress_no_fact":
            fix_parts.append("внести числове фактичне значення показника")
        if w["type"] == "fact_no_progress":
            fix_parts.append("додати опис прогресу виконання заходу")

    fix_text = "; ".join(fix_parts) if fix_parts else "усунути зазначені розбіжності"

    return (
        header
        + pf_clause
        + f"Статус виконання — «{status if status else 'не вказано'}». "
        + f"За результатами перевірки встановлено: {issues_text}. "
        + f"Відомості повертаються на доопрацювання. "
        + f"Для повторного подання необхідно: {fix_text}."
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

# Планове значення — обчислюємо тут, щоб передати в резолюцію
target_year_val = ""
year_val = clean(selected_row.get("year", ""))
if year_val and year_val.isdigit():
    m_info_for_plan = strat_df[strat_df["code"].astype(str).str.strip() == selected_code]
    col_name = f"target_{year_val}"
    if not m_info_for_plan.empty and col_name in m_info_for_plan.columns:
        v = clean(m_info_for_plan.iloc[0].get(col_name, ""))
        if v:
            target_year_val = v

checks, recommendation, rec_badge, quality_score, total_fields, completeness_pct = quality_assessment(selected_row)
auto_resolution = generate_resolution(selected_row, recommendation, target_year_val)

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

with k4:
    display_plan = target_year_val if target_year_val else "—"
    admin_kpi_card(f"Планове значення ({year_val})", display_plan)
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
