import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime
import re

st.set_page_config(page_title="Dashboard", layout="wide")

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
@import url('https://fonts.googleapis.com/css2?family=e-Ukraine:wght@300;400;500;700&display=swap');

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Helvetica Neue', 'Arial', sans-serif;
}

.stApp {
    background: #f0f4f9;
}

/* Subtle geometric background pattern */
.stApp::before {
    content: "";
    position: fixed;
    inset: 0;
    background-image:
        radial-gradient(circle at 15% 15%, rgba(0,91,187,0.06) 0%, transparent 40%),
        radial-gradient(circle at 85% 80%, rgba(255,213,0,0.06) 0%, transparent 40%),
        radial-gradient(circle at 50% 50%, rgba(0,91,187,0.02) 0%, transparent 60%);
    pointer-events: none;
    z-index: 0;
}

.main .block-container {
    max-width: min(1500px, 98vw);
    padding: clamp(0.5rem, 2vw, 1.5rem) clamp(0.5rem, 2vw, 2rem);
    position: relative;
    z-index: 1;
}

/* ── UA accent stripe ── */
.ua-stripe {
    height: 5px;
    border-radius: 0 0 6px 6px;
    background: linear-gradient(90deg, #005BBB 50%, #FFD700 50%);
    margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(0,91,187,0.15);
}

/* ── Ministry label ── */
.ministry-label {
    text-align: right;
    color: #334155;
    font-size: clamp(11px, 1.1vw, 14px);
    font-weight: 700;
    margin-bottom: 10px;
    letter-spacing: 0.01em;
}

/* ── Header card ── */
.header-card {
    background: linear-gradient(135deg, #ffffff 0%, #f8faff 100%);
    border: 1px solid #dde3ed;
    border-left: 5px solid #005BBB;
    border-radius: 12px;
    padding: clamp(16px, 2.5vw, 28px) clamp(16px, 2.5vw, 32px);
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(0,91,187,0.08), 0 1px 4px rgba(0,0,0,0.04);
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 16px;
}

.header-main {
    flex: 1 1 60%;
    min-width: 200px;
}

.header-title {
    font-size: clamp(20px, 2.5vw, 30px);
    font-weight: 900;
    color: #0c1a3a;
    margin: 0 0 6px 0;
    line-height: 1.2;
}

.header-subtitle {
    font-size: clamp(12px, 1.1vw, 14px);
    color: #475569;
    line-height: 1.6;
    max-width: 680px;
}

.header-pills {
    flex: 0 1 auto;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: flex-start;
    padding-top: 4px;
}

.pill {
    background: #eef3fb;
    border: 1px solid #c2d4f0;
    border-radius: 20px;
    padding: 5px 12px;
    font-size: clamp(10px, 0.9vw, 12px);
    color: #1e3a6e;
    font-weight: 600;
    white-space: nowrap;
}

/* ── Section card ── */
.section-card {
    background: #ffffff;
    border: 1px solid #dde3ed;
    border-radius: 12px;
    padding: clamp(14px, 2vw, 22px) clamp(14px, 2vw, 24px);
    margin-bottom: 18px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}

.section-title {
    font-size: clamp(15px, 1.4vw, 19px);
    font-weight: 800;
    color: #0c1a3a;
    margin: 0 0 4px 0;
}

.section-subtitle {
    font-size: clamp(11px, 0.95vw, 13px);
    color: #64748b;
    margin: 0 0 14px 0;
}

/* ── Filter panel ── */
.filter-panel {
    background: linear-gradient(135deg, #f8fbff 0%, #eef3fb 100%);
    border: 1px solid #c2d4f0;
    border-radius: 12px;
    padding: clamp(14px, 2vw, 20px) clamp(14px, 2vw, 22px);
    margin-bottom: 20px;
    box-shadow: 0 2px 10px rgba(0,91,187,0.06);
}

.filter-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
}

.filter-title {
    font-size: clamp(14px, 1.3vw, 17px);
    font-weight: 800;
    color: #0c1a3a;
}

.filter-hint {
    font-size: clamp(10px, 0.9vw, 12px);
    color: #64748b;
    background: #e9f0fb;
    border-radius: 6px;
    padding: 3px 8px;
}

.filter-group-label {
    font-size: clamp(10px, 0.85vw, 11.5px);
    font-weight: 700;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 10px 0 6px 2px;
}

/* ── Streamlit widget overrides ── */
div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background-color: #ffffff !important;
    border: 1.5px solid #c2d4f0 !important;
    border-radius: 8px !important;
    min-height: 38px !important;
    font-size: clamp(11px, 1vw, 13px) !important;
}

div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div:focus-within,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within {
    border-color: #005BBB !important;
    box-shadow: 0 0 0 3px rgba(0,91,187,0.12) !important;
}

div[data-testid="stMultiSelect"] label,
div[data-testid="stSelectbox"] label {
    font-weight: 700 !important;
    color: #1e3a6e !important;
    font-size: clamp(11px, 0.95vw, 13px) !important;
}

/* toggle */
div[data-testid="stToggle"] label {
    font-weight: 700 !important;
    color: #1e3a6e !important;
    font-size: clamp(11px, 0.95vw, 13px) !important;
}

/* Reset button */
div[data-testid="stButton"] button {
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: clamp(11px, 0.95vw, 13px) !important;
    padding: 6px 14px !important;
}

/* ── Conclusion block ── */
.conclusion-block {
    border-radius: 10px;
    padding: clamp(12px, 1.5vw, 18px) clamp(14px, 2vw, 22px);
    margin: 8px 0 14px 0;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
}

.conclusion-risk-high {
    background: linear-gradient(135deg, #fff1f1 0%, #fee2e2 100%);
    border-left: 5px solid #dc2626;
    border: 1px solid #fecaca;
    border-left: 5px solid #dc2626;
}

.conclusion-risk-medium {
    background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
    border: 1px solid #fde68a;
    border-left: 5px solid #d97706;
}

.conclusion-risk-low {
    background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    border: 1px solid #bbf7d0;
    border-left: 5px solid #16a34a;
}

.conclusion-badge {
    font-size: clamp(13px, 1.2vw, 16px);
    font-weight: 900;
    padding: 6px 14px;
    border-radius: 8px;
    white-space: nowrap;
}

.badge-red { background: #dc2626; color: #fff; }
.badge-yellow { background: #d97706; color: #fff; }
.badge-green { background: #16a34a; color: #fff; }

.conclusion-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.meta-chip {
    background: rgba(255,255,255,0.7);
    border: 1px solid rgba(0,0,0,0.1);
    border-radius: 20px;
    padding: 4px 11px;
    font-size: clamp(10px, 0.9vw, 12px);
    font-weight: 600;
    color: #334155;
}

.conclusion-text {
    font-size: clamp(12px, 1vw, 14px);
    color: #475569;
    margin-top: 6px;
    width: 100%;
}

/* ── KPI status grid ── */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(150px, 100%), 1fr));
    gap: clamp(8px, 1.2vw, 14px);
    margin: 6px 0 4px 0;
}

.kpi-card {
    border-radius: 10px;
    padding: clamp(10px, 1.4vw, 16px);
    border: 1px solid transparent;
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.kpi-title {
    font-size: clamp(10px, 0.85vw, 12px);
    font-weight: 700;
    color: #475569;
    min-height: 28px;
    line-height: 1.3;
}

.kpi-value {
    font-size: clamp(22px, 2.5vw, 32px);
    font-weight: 900;
    color: #0c1a3a;
    line-height: 1;
    margin-top: 2px;
}

.kpi-pct {
    font-size: clamp(11px, 0.95vw, 13px);
    font-weight: 700;
    color: #64748b;
    margin-top: 4px;
}

.kpi-blue  { background: #eff6ff; border-color: #bfdbfe; }
.kpi-green { background: #f0fdf4; border-color: #bbf7d0; }
.kpi-red   { background: #fef2f2; border-color: #fecaca; }
.kpi-yellow{ background: #fffbeb; border-color: #fde68a; }
.kpi-gray  { background: #f8fafc; border-color: #e2e8f0; }

/* ── Insight items ── */
.insight-item {
    background: #f8fafc;
    border-left: 4px solid #005BBB;
    border-radius: 0 8px 8px 0;
    padding: clamp(8px, 1vw, 12px) clamp(12px, 1.5vw, 16px);
    margin-bottom: 8px;
    font-size: clamp(12px, 1vw, 14px);
    color: #1e293b;
    line-height: 1.5;
}

.insight-item.warn { border-left-color: #d97706; background: #fffbeb; }
.insight-item.danger { border-left-color: #dc2626; background: #fef2f2; }
.insight-item.info { border-left-color: #0891b2; background: #ecfeff; }

/* ── Linear indicator rows ── */
.indicator-row {
    margin-bottom: 10px;
}

.indicator-label {
    display: flex;
    justify-content: space-between;
    font-size: clamp(11px, 0.95vw, 13px);
    font-weight: 600;
    color: #334155;
    margin-bottom: 4px;
}

.indicator-bar-bg {
    background: #e2e8f0;
    border-radius: 99px;
    height: 8px;
    overflow: hidden;
}

.indicator-bar-fill {
    height: 100%;
    border-radius: 99px;
    transition: width 0.4s ease;
}

/* ── Chart container ── */
.chart-wrap {
    background: #ffffff;
    border: 1px solid #e9eef5;
    border-radius: 10px;
    padding: clamp(10px, 1.5vw, 16px);
    margin-bottom: 10px;
}

.chart-title {
    font-size: clamp(12px, 1.1vw, 15px);
    font-weight: 800;
    color: #0c1a3a;
    margin-bottom: 6px;
}

/* ── Rank table ── */
div[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #dde3ed !important;
}

/* ── Methodology ── */
.methodology-box {
    background: #f8fafc;
    border: 1px solid #dde3ed;
    border-radius: 10px;
    padding: 16px 20px;
    font-size: clamp(11px, 0.95vw, 13px);
    color: #334155;
    line-height: 1.7;
}

/* ── Footer ── */
.footer {
    text-align: center;
    color: #94a3b8;
    font-size: clamp(10px, 0.9vw, 12px);
    margin-top: 40px;
    padding: 18px 0 10px;
    border-top: 1px solid #e2e8f0;
}

/* ── Separator ── */
.vis-separator {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 22px 0;
}

/* ── Responsive: narrow screens ── */
@media (max-width: 900px) {
    .header-card { flex-direction: column; }
    .header-pills { flex-direction: row; }
    .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 600px) {
    .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# DATA LOAD
# ============================================================

@st.cache_data
def load_strat_matrix():
    df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=None, engine="openpyxl")
    data = df.iloc[7:].copy()

    def safe_col(index):
        if index < data.shape[1]:
            return data.iloc[:, index]
        return pd.Series([""] * len(data), index=data.index)

    result = pd.DataFrame({
        "type_marker": safe_col(1),
        "code": safe_col(2),
        "name": safe_col(3),
        "product_type": safe_col(4),
        "indicator": safe_col(5),
        "unit": safe_col(6),
        "base_2021": safe_col(7),
        "fact_2024": safe_col(8),
        "expected_2025": safe_col(9),
        "target_2026": safe_col(10),
        "target_2027": safe_col(11),
        "target_2028": safe_col(12),
        "source_national": safe_col(16),
        "department": safe_col(17),
        "department_co_1": safe_col(18),
        "department_co_2": safe_col(19),
        "deputy_minister": safe_col(20),
        "start_period": safe_col(22),
        "end_period": safe_col(23),
    })

    result = result.dropna(subset=["code"])
    result["code"] = result["code"].astype(str).str.strip()
    result["type_marker"] = result["type_marker"].astype(str).str.strip()

    def classify(row):
        marker = str(row["type_marker"]).lower()
        code = str(row["code"]).strip()
        if "стратегічна ціль" in marker:
            return "goal"
        if "завдання" in marker:
            return "task"
        if code.count(".") >= 3:
            return "measure"
        return "other"

    result["object_type"] = result.apply(classify, axis=1)
    return result


@st.cache_data(ttl=60)
def load_requests():
    response = supabase.table("monitoring_requests").select("*").execute()
    if not response.data:
        return pd.DataFrame()
    return pd.DataFrame(response.data)


# ============================================================
# HELPERS
# ============================================================

def clean(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value).strip()


def normalize_text(value):
    return str(value).strip().lower().replace("і", "i")


def to_number(value):
    text = str(value).replace(",", ".").replace("%", "").strip()
    if text.lower() in ["", "nan", "none", "н.д.", "нд", "x", "х", "так", "ні", "да", "нет", "-", "—"]:
        return None
    match = re.search(r"-?\d+(\.\d+)?", text)
    if match:
        try:
            return float(match.group())
        except Exception:
            return None
    return None


def parse_period(value):
    text = str(value).lower().strip()
    if text in ["", "nan", "none", "н.д.", "нд"]:
        return None
    q = None
    year = None
    if "1 квартал" in text or "i квартал" in text or " і квартал" in text:
        q = 1
    elif "2 квартал" in text or "ii квартал" in text or " іі квартал" in text:
        q = 2
    elif "3 квартал" in text or "iii квартал" in text or " ііі квартал" in text:
        q = 3
    elif "4 квартал" in text or "iv квартал" in text:
        q = 4
    year_match = re.search(r"20\d{2}", text)
    if year_match:
        year = int(year_match.group())
    if year and q:
        return year * 10 + q
    return None


def quarter_to_number(q):
    q = str(q).strip()
    mapping = {"I": 1, "II": 2, "III": 3, "IV": 4, "1": 1, "2": 2, "3": 3, "4": 4}
    return mapping.get(q, 1)


def quarter_to_roman(q):
    q = str(q).strip()
    mapping = {"1": "I", "2": "II", "3": "III", "4": "IV", "I": "I", "II": "II", "III": "III", "IV": "IV"}
    return mapping.get(q, "I")


def get_goal_code(code):
    parts = str(code).split(".")
    return parts[0] + "." if parts else ""


def get_task_code(code):
    parts = str(code).split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}."
    return ""


def code_sort_key(code):
    parts = re.findall(r"\d+", str(code))
    return tuple(int(p) for p in parts) if parts else (9999,)


def strip_code_from_name(code, name):
    code = clean(code)
    name = clean(name)
    if code and name.startswith(code):
        return name[len(code):].lstrip(" .—-–|:")
    return name


def unique_clean_values(series):
    if series is None:
        return []
    values = []
    for item in series.dropna().astype(str).tolist():
        item = item.strip()
        if item and item.lower() not in ["nan", "none", "н.д.", "нд", "-", "—"]:
            values.append(item)
    return sorted(set(values))


def get_all_department_values(row):
    values = []
    for col in ["department", "department_co_1", "department_co_2"]:
        value = clean(row.get(col, ""))
        if value:
            values.append(value)
    return values


def split_department_indices(value):
    return re.findall(r"\d+", clean(value))


def department_matches_indices(row, selected_indices):
    if not selected_indices:
        return True
    found = set()
    for value in get_all_department_values(row):
        found.update(split_department_indices(value))
    return bool(found.intersection(set(selected_indices)))


def status_display(status):
    status = clean(status)
    mapping = {
        "Виконано": "Виконано",
        "Виконано частково": "Частково виконано",
        "Частково виконано": "Частково виконано",
        "Не виконано": "Не виконано",
        "Прострочено": "Не виконано",
        "Не розпочато": "Не виконано",
        "Потребує уваги": "Не виконано",
        "Не подано": "Не виконано",
        "Виконується": "Виконується",
        "Не настав час": "Термін не настав",
        "Термін не настав": "Термін не настав",
        "Втратило актуальність": "Втратив актуальність",
        "Втратив актуальність": "Втратив актуальність",
    }
    return mapping.get(status, status if status else "Не виконано")


def is_excluded_status(status):
    return status_display(status) in ["Термін не настав", "Втратив актуальність"]


def status_score(status):
    status = clean(status)
    if status == "Виконано":
        return 100
    if status in ["Виконано частково", "Частково виконано"]:
        return 75
    if status == "Виконується":
        return 50
    if status in ["Потребує уваги", "Прострочено", "Не розпочато", "Не подано", "Не виконано"]:
        return 0
    if status in ["Не настав час", "Термін не настав", "Втратило актуальність", "Втратив актуальність"]:
        return None
    return 0


def plan_fact_percent(actual, target):
    actual_num = to_number(actual)
    target_num = to_number(target)
    actual_text = normalize_text(actual)
    target_text = normalize_text(target)
    if actual_num is not None and target_num is not None and target_num != 0:
        return round(min((actual_num / target_num) * 100, 150), 1)
    if target_text in ["так", "yes"] or actual_text in ["так", "ні", "yes", "no"]:
        if actual_text in ["так", "yes"]:
            return 100
        if actual_text in ["ні", "no"]:
            return 0
    return None


def is_quantitative_plan_fact(row):
    actual_num = to_number(row.get("numeric_value", ""))
    target_num = to_number(row.get("selected_target", ""))
    return actual_num is not None and target_num is not None and target_num != 0


def traffic_light(score):
    if score is None or pd.isna(score):
        return "⚪ Не оцінюється"
    if score >= 100:
        return "🟢 У графіку"
    if score >= 75:
        return "🟡 Часткове виконання"
    return "🔴 Відстає"


def risk_level_from_score(score):
    if score is None or pd.isna(score):
        return "Не оцінюється"
    if score >= 70:
        return "Критичний ризик"
    if score >= 35:
        return "Середній ризик"
    return "Низький ризик"


def risk_score_calc(row, selected_quarter_num, selected_period_num):
    status = clean(row.get("status", "Не подано"))
    display_status = status_display(status)
    actual = row.get("numeric_value", "")
    target = row.get("selected_target", "")
    end_num = row.get("end_num", None)
    score = 0
    reasons = []

    if display_status in ["Термін не настав", "Втратив актуальність"]:
        return 0, "захід не включається до ризикової оцінки за поточним статусом"

    pf = plan_fact_percent(actual, target)

    if status == "Не подано":
        score += 45
        reasons.append("за активним заходом не подано моніторингові дані")

    if pf is not None:
        if pf >= 100:
            score += 0
            reasons.append("фактичне значення досягло або перевищило планове")
        elif pf >= 75:
            score += 25
            reasons.append("фактичне значення становить від 75% до 99% плану")
        else:
            score += 45
            reasons.append("значне відставання фактичного значення від планового")
    else:
        if display_status == "Виконано":
            score += 0
            reasons.append("захід позначено як виконаний")
        elif display_status == "Частково виконано":
            score += 25
            reasons.append("захід позначено як частково виконаний")
        elif display_status == "Виконується":
            score += 30
            reasons.append("захід перебуває у виконанні")
        elif display_status == "Не виконано":
            score += 45
            reasons.append("захід не виконано або відсутнє підтвердження виконання")

    if pd.notna(end_num) and end_num < selected_period_num and display_status != "Виконано":
        score += 45
        reasons.append("строк виконання минув, захід не виконано")

    score = min(score, 100)
    if not reasons:
        reasons.append("критичних відхилень не виявлено")

    return score, "; ".join(reasons)


def dashboard_conclusion(completion, risk_share, coverage):
    if completion >= 75 and risk_share <= 15 and coverage >= 70:
        return "План переважно виконується", "Поточний стан виконання виглядає контрольованим.", "risk-low"
    if completion >= 45 and risk_share <= 35:
        return "Є помірні відхилення", "Потрібна увага до окремих заходів, самостійних структурних підрозділів або стратегічних цілей.", "risk-medium"
    return (
        "Високий ризик невиконання",
        "Поточні дані вказують на недостатній рівень подання та погодження відомостей або на суттєві відхилення від планових показників.",
        "risk-high"
    )


def deviation_for_period(completion):
    return round(completion - 100, 1)


def gauge_chart(value, title):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": "%", "font": {"size": 28, "color": "#0c1a3a"}},
        title={"text": title, "font": {"size": 14, "color": "#475569"}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#94a3b8", "tickfont": {"size": 11}},
            "bar": {"color": "#005BBB", "thickness": 0.3},
            "bgcolor": "white",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 35], "color": "#fee2e2"},
                {"range": [35, 70], "color": "#fef3c7"},
                {"range": [70, 100], "color": "#dcfce7"},
            ],
            "threshold": {
                "line": {"color": "#0c1a3a", "width": 3},
                "thickness": 0.75,
                "value": value
            }
        }
    ))
    fig.update_layout(
        height=260,
        margin=dict(l=20, r=20, t=50, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    return fig


def pct_value(count, total):
    if total == 0:
        return "0.0%"
    return f"{round(count / total * 100, 1)}%"


def render_kpi_grid(items):
    cards_html = "".join([
        f'<div class="kpi-card {item["color"]}">'
        f'<div class="kpi-title">{item["title"]}</div>'
        f'<div class="kpi-value">{item["count"]}</div>'
        f'<div class="kpi-pct">{item["percent"]}</div>'
        f'</div>'
        for item in items
    ])

    st.markdown(
        f'<div class="kpi-grid">{cards_html}</div>',
        unsafe_allow_html=True
    )


def render_insight(text, kind="default"):
    css_class = "insight-item"
    if kind == "warn":
        css_class += " warn"
    elif kind == "danger":
        css_class += " danger"
    elif kind == "info":
        css_class += " info"
    st.markdown(f'<div class="{css_class}">{text}</div>', unsafe_allow_html=True)


def render_indicator_bar(label, value, max_val=100, color="#005BBB"):
    pct = min(max(value / max_val * 100, 0), 100)
    st.markdown(f"""
    <div class="indicator-row">
        <div class="indicator-label">
            <span>{label}</span>
            <span style="color:{color};font-weight:800;">{value}{'%' if max_val == 100 else ''}</span>
        </div>
        <div class="indicator-bar-bg">
            <div class="indicator-bar-fill" style="width:{pct}%;background:{color};"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def reset_filters():
    keys = [
        "dash_years", "dash_quarters", "dash_department_indices",
        "dash_goals", "dash_tasks", "dash_measures",
        "dash_product_types", "dash_deputies", "dash_statuses",
        "dash_financing", "dash_sources", "dash_view_mode", "dash_presentation_mode"
    ]
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]


# ============================================================
# CORE DATA FUNCTIONS
# ============================================================

def prepare_period_data(strat_df, requests_df, year, quarter, department="Усі"):
    measures = strat_df[strat_df["object_type"] == "measure"].copy()
    goals = strat_df[strat_df["object_type"] == "goal"].copy()

    measures["goal_code"] = measures["code"].apply(get_goal_code)
    measures["task_code"] = measures["code"].apply(get_task_code)
    measures["strategic_goal"] = measures["goal_code"].map(goals.set_index("code")["name"].to_dict())

    measures["start_num"] = measures["start_period"].apply(parse_period)
    measures["end_num"] = measures["end_period"].apply(parse_period)

    selected_q_num = quarter_to_number(quarter)
    selected_period_num = int(year) * 10 + selected_q_num

    active = measures[
        (measures["start_num"].isna() | (measures["start_num"] <= selected_period_num)) &
        (measures["end_num"].isna() | (measures["end_num"] >= selected_period_num))
    ].copy()

    if department != "Усі":
        active = active[active["department"].astype(str) == str(department)]

    if requests_df.empty:
        requests_df = pd.DataFrame(columns=[
            "year", "quarter", "strat_code", "status", "numeric_value",
            "risks", "progress_text", "approval_status", "submitted_at"
        ])

    required_cols = [
        "year", "quarter", "strat_code", "status", "numeric_value",
        "risks", "progress_text", "approval_status", "submitted_at"
    ]
    for col in required_cols:
        if col not in requests_df.columns:
            requests_df[col] = ""

    approved_requests = requests_df[requests_df["approval_status"].astype(str) == "Погоджено"].copy()

    if approved_requests.empty:
        period_requests = pd.DataFrame(columns=[
            "strat_code", "status", "numeric_value", "risks", "progress_text", "submitted_at"
        ])
    else:
        quarter_num = str(quarter_to_number(quarter))
        quarter_roman = quarter_to_roman(quarter)

        period_requests = approved_requests[
            (approved_requests["year"].astype(str) == str(year)) &
            (
                (approved_requests["quarter"].astype(str) == str(quarter)) |
                (approved_requests["quarter"].astype(str) == quarter_num) |
                (approved_requests["quarter"].astype(str) == quarter_roman)
            )
        ].copy()

        if not period_requests.empty:
            period_requests = (
                period_requests
                .sort_values("submitted_at")
                .groupby("strat_code")
                .tail(1)
            )

    active = active.merge(
        period_requests[["strat_code", "status", "numeric_value", "risks", "progress_text"]],
        left_on="code",
        right_on="strat_code",
        how="left"
    )

    active["status"] = active["status"].fillna("Не подано")
    active["numeric_value"] = active["numeric_value"].fillna("")
    active["risks"] = active["risks"].fillna("")
    active["progress_text"] = active["progress_text"].fillna("")
    active["selected_target"] = active[f"target_{year}"] if f"target_{year}" in active.columns else ""

    active["status_display"] = active["status"].apply(status_display)
    active["status_score"] = active["status"].apply(status_score)
    active["plan_fact_percent"] = active.apply(
        lambda r: plan_fact_percent(r["numeric_value"], r["selected_target"]), axis=1
    )
    active["is_quantitative_pf"] = active.apply(is_quantitative_plan_fact, axis=1)
    active["performance_score"] = active.apply(
        lambda r: r["plan_fact_percent"] if pd.notna(r["plan_fact_percent"]) else r["status_score"],
        axis=1
    )
    active["included_in_assessment"] = ~active["status_display"].isin([
        "Термін не настав", "Втратив актуальність"
    ])

    risk_results = active.apply(
        lambda r: risk_score_calc(r, selected_q_num, selected_period_num), axis=1
    )
    active["risk_score"] = [x[0] for x in risk_results]
    active["risk_reason"] = [x[1] for x in risk_results]
    active["auto_risk"] = active["risk_score"].apply(risk_level_from_score)
    active.loc[~active["included_in_assessment"], "auto_risk"] = "Не оцінюється"

    active["traffic_light"] = active["performance_score"].apply(traffic_light)
    active.loc[~active["included_in_assessment"], "traffic_light"] = "⚪ Не оцінюється"

    active["period_year"] = int(year)
    active["period_quarter"] = quarter_to_roman(quarter)
    active["period_label"] = active["period_year"].astype(str) + " " + active["period_quarter"].astype(str)

    return active


def build_period_data(strat_df, requests_df, years, quarters):
    frames = []
    for year in years:
        for quarter in quarters:
            temp = prepare_period_data(strat_df, requests_df, year, quarter, "Усі")
            if not temp.empty:
                frames.append(temp)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def apply_dashboard_filters(active, department_indices, goals, tasks, measures, product_types, deputies, statuses, sources):
    data = active.copy()
    if department_indices:
        data = data[data.apply(lambda row: department_matches_indices(row, department_indices), axis=1)]
    if goals:
        data = data[data["goal_code"].isin(goals)]
    if tasks:
        data = data[data["task_code"].isin(tasks)]
    if measures:
        data = data[data["code"].isin(measures)]
    if product_types:
        data = data[data["product_type"].isin(product_types)]
    if deputies:
        data = data[data["deputy_minister"].fillna("").astype(str).isin(deputies)]
    if statuses:
        data = data[data["status_display"].isin(statuses)]
    if sources:
        data = data[data["source_national"].isin(sources)]
    return data.copy()


def assessment_subset(active):
    if active.empty:
        return active
    return active[active["included_in_assessment"] == True].copy()


def mean_completion(active):
    assessed = assessment_subset(active)
    if assessed.empty:
        return 0
    return round(assessed["performance_score"].fillna(0).mean(), 1)


def calc_coverage(active):
    if active.empty:
        return 0
    submitted = len(active[active["status"] != "Не подано"])
    return round(submitted / len(active) * 100, 1)


def calc_submitted(active):
    if active.empty:
        return 0
    return len(active[active["status"] != "Не подано"])


def calc_risk_share(active):
    assessed = assessment_subset(active)
    if assessed.empty:
        return 0
    risk_count = len(assessed[assessed["auto_risk"].isin(["Критичний ризик", "Середній ризик"])])
    return round(risk_count / len(assessed) * 100, 1)


def is_failed_for_weight(row):
    if not row.get("included_in_assessment", True):
        return False
    if row.get("status", "") == "Не подано":
        return True
    if row.get("status_display", "") == "Не виконано":
        return True
    score = row.get("performance_score", 0)
    if pd.isna(score):
        score = 0
    return score < 75


def weighted_failure_group(active, group_cols):
    if active.empty:
        return pd.DataFrame()
    data = active.copy()
    data = data[data["included_in_assessment"] == True].copy()
    if data.empty:
        return pd.DataFrame()
    data["failed_weight_flag"] = data.apply(is_failed_for_weight, axis=1)
    grouped = (
        data
        .groupby(group_cols, dropna=False)
        .agg(
            Активних_заходів=("code", "count"),
            Невиконаних=("failed_weight_flag", "sum"),
            Виконання=("performance_score", "mean"),
            Ризик=("risk_score", "mean")
        )
        .reset_index()
    )
    grouped["Вага_невиконання"] = grouped["Невиконаних"] / len(data) * 100
    grouped["Виконання"] = grouped["Виконання"].fillna(0).round(1)
    grouped["Ризик"] = grouped["Ризик"].fillna(0).round(1)
    grouped["Вага_невиконання"] = grouped["Вага_невиконання"].fillna(0).round(1)
    return grouped.sort_values(
        ["Вага_невиконання", "Невиконаних", "Активних_заходів"],
        ascending=[False, False, False]
    )


def explode_departments(active):
    rows = []
    for _, row in active.iterrows():
        departments = get_all_department_values(row)
        if not departments:
            departments = ["Не визначено"]
        for dep in departments:
            item = row.to_dict()
            item["ssp_department"] = dep
            rows.append(item)
    return pd.DataFrame(rows)


def style_rank_table(row, total_rows):
    place = row["Місце"]
    if place <= 3:
        return ["background-color: #dcfce7; color: #14532d; font-weight: 800; text-align: center"] * len(row)
    if place <= 10:
        return ["background-color: #e0f2fe; color: #0c4a6e; text-align: center"] * len(row)
    if place > max(total_rows - 7, 10):
        return ["background-color: #fee2e2; color: #7f1d1d; text-align: center"] * len(row)
    return ["background-color: #f8fafc; color: #334155; text-align: center"] * len(row)


def collapse_to_latest_measure_rows(df):
    if df.empty:
        return df
    data = df.copy()
    data["_period_sort"] = (
        data["period_year"].astype(int) * 10
        + data["period_quarter"].apply(quarter_to_number)
    )
    data = (
        data
        .sort_values(["code", "_period_sort"])
        .groupby("code", as_index=False)
        .tail(1)
        .drop(columns=["_period_sort"])
    )
    return data


# ─── Plotly theme helper ───────────────────────────────────────────────────────
CHART_COLORS = ["#005BBB", "#FFD700", "#0891b2", "#16a34a", "#d97706", "#9333ea", "#dc2626", "#64748b"]

RISK_COLORS = {
    "Критичний ризик": "#dc2626",
    "Середній ризик": "#d97706",
    "Низький ризик": "#16a34a",
    "Не оцінюється": "#94a3b8"
}

TRAFFIC_COLORS = {
    "🟢 У графіку": "#16a34a",
    "🟡 Часткове виконання": "#d97706",
    "🔴 Відстає": "#dc2626",
    "⚪ Не оцінюється": "#94a3b8"
}

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Helvetica Neue, Arial, sans-serif", size=12, color="#334155")
)


def make_chart_frame(title, subtitle=""):
    st.markdown(
        f'<div class="chart-wrap"><div class="chart-title">{title}</div>'
        + (f'<div class="section-subtitle">{subtitle}</div>' if subtitle else ""),
        unsafe_allow_html=True
    )


def close_chart_frame():
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# HEADER
# ============================================================

st.markdown('<div class="ua-stripe"></div>', unsafe_allow_html=True)
st.markdown("""
<div class="ministry-label">
🇺🇦 Міністерство економіки, довкілля та сільського господарства України
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="header-card">
    <div class="header-main">
        <div class="header-title">Аналітичний дашборд результативності стратегічного плану</div>
        <div class="header-subtitle">
            Комплексна панель моніторингу та оцінювання стратегічних результатів — по кожному
            самостійному структурному підрозділу та в розрізі стратегічних цілей і завдань.
        </div>
    </div>
    <div class="header-pills">
        <div class="pill">📋 Dashboard</div>
        <div class="pill">🗄 Excel + Supabase</div>
        <div class="pill">✅ Погоджені заявки</div>
        <div class="pill">🕐 {datetime.now().strftime("%d.%m.%Y %H:%M")}</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================
# LOAD DATA
# ============================================================

strat_df = load_strat_matrix()
requests_df = load_requests()

if requests_df.empty:
    requests_df = pd.DataFrame(columns=[
        "year", "quarter", "department", "strat_code", "status", "numeric_value",
        "risks", "progress_text", "approval_status", "submitted_at"
    ])

measures_all = strat_df[strat_df["object_type"] == "measure"].copy()
goals_all = strat_df[strat_df["object_type"] == "goal"].copy()
tasks_all = strat_df[strat_df["object_type"] == "task"].copy()

measures_all["goal_code"] = measures_all["code"].apply(get_goal_code)
measures_all["task_code"] = measures_all["code"].apply(get_task_code)
measures_all["strategic_goal"] = measures_all["goal_code"].map(goals_all.set_index("code")["name"].to_dict())

years_options = [2026, 2027, 2028]
quarters_options = ["I", "II", "III", "IV"]

department_indices_options = sorted(
    set(
        re.findall(
            r"\d+",
            " | ".join(
                measures_all[["department", "department_co_1", "department_co_2"]]
                .fillna("").astype(str).agg(" | ".join, axis=1).tolist()
            )
        )
    ),
    key=lambda x: int(x) if x.isdigit() else 9999
)

goal_options = sorted(measures_all["goal_code"].dropna().astype(str).unique().tolist(), key=code_sort_key)
task_options = sorted(measures_all["task_code"].dropna().astype(str).unique().tolist(), key=code_sort_key)
measure_options = sorted(measures_all["code"].dropna().astype(str).unique().tolist(), key=code_sort_key)

goal_name_map = goals_all.set_index("code")["name"].to_dict()
task_name_map = tasks_all.set_index("code")["name"].to_dict()
measure_name_map = measures_all.set_index("code")["name"].to_dict()

product_type_options = unique_clean_values(measures_all["product_type"])
deputy_options = unique_clean_values(measures_all["deputy_minister"])
source_options = unique_clean_values(measures_all["source_national"])

status_options = [
    "Виконано", "Частково виконано", "Не виконано",
    "Термін не настав", "Втратив актуальність", "Виконується"
]


# ============================================================
# FILTERS PANEL
# ============================================================

with st.container():
    st.markdown("""
    <div class="filter-panel">
        <div class="filter-header">
            <span class="filter-title">🔍 Параметри відбору</span>
            <span class="filter-hint">Оберіть фільтри — дашборд перерахується автоматично</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Рядок 1: Ключові фільтри + режим
    fa, fb, fc, fd, fe = st.columns([1, 1, 2, 1.5, 1])

    with fa:
        selected_years = st.multiselect(
            "📅 Рік",
            years_options,
            default=[],
            key="dash_years",
            placeholder="Усі роки"
        )

    with fb:
        selected_quarters = st.multiselect(
            "🗓 Квартал",
            quarters_options,
            default=[],
            key="dash_quarters",
            placeholder="Усі квартали"
        )

    with fc:
        selected_department_indices = st.multiselect(
            "🏢 Індекс ССП",
            department_indices_options,
            key="dash_department_indices",
            placeholder="Усі підрозділи"
        )

    with fd:
        view_mode = st.selectbox(
            "📊 Режим перегляду",
            [
                "Усі візуалізації",
                "Стратегічні цілі",
                "Самостійні структурні підрозділи",
                "Ризики",
                "Динаміка",
                "Heatmap",
                "Таблиці"
            ],
            key="dash_view_mode"
        )

    with fe:
        presentation_mode = st.toggle(
            "🖥 Презентаційний режим",
            value=False,
            key="dash_presentation_mode",
            help="Спрощений вигляд: висновок, ключові індикатори та основні графіки."
        )

    # Рядок 2: Деталізовані фільтри (у розгорнутому вигляді)
    with st.expander("⚙️ Додаткові фільтри (ціль, завдання, захід, тип, заступник, статус, джерело)"):
        g1, g2, g3 = st.columns(3)
        with g1:
            selected_goals = st.multiselect(
                "Стратегічна ціль",
                goal_options,
                format_func=lambda x: f"{x} — {strip_code_from_name(x, goal_name_map.get(x, ''))}",
                key="dash_goals"
            )
        with g2:
            selected_tasks = st.multiselect(
                "Завдання",
                task_options,
                format_func=lambda x: f"{x} — {strip_code_from_name(x, task_name_map.get(x, ''))}",
                key="dash_tasks"
            )
        with g3:
            selected_measures = st.multiselect(
                "Захід",
                measure_options,
                format_func=lambda x: f"{x} — {strip_code_from_name(x, measure_name_map.get(x, ''))}",
                key="dash_measures"
            )

        h1, h2, h3 = st.columns(3)
        with h1:
            selected_product_types = st.multiselect(
                "Тип продукту",
                product_type_options,
                key="dash_product_types"
            )
        with h2:
            selected_deputies = st.multiselect(
                "Заступник Міністра",
                deputy_options,
                key="dash_deputies",
                help="Фільтр підготовлено. Повноцінно запрацює після прив'язки заступників до заходів."
            )
        with h3:
            selected_statuses = st.multiselect(
                "Статус виконання",
                status_options,
                key="dash_statuses"
            )

        j1, j2, j3 = st.columns(3)
        with j1:
            selected_financing = st.multiselect(
                "Фінансування",
                [],
                key="dash_financing",
                help="Дані про фінансування поки не додані. Фільтр залишено як технічну заготовку."
            )
        with j2:
            selected_sources = st.multiselect(
                "Джерело даних: національний рівень",
                source_options,
                key="dash_sources"
            )
        with j3:
            st.write("")
            st.write("")
            if st.button("↺ Скинути фільтри", use_container_width=True):
                reset_filters()
                st.rerun()

    # Кнопка скидання поза expander (завжди доступна)
    col_reset, _ = st.columns([1, 5])
    with col_reset:
        if st.button("Скинути фільтри", use_container_width=True, key="reset_main"):
            reset_filters()
            st.rerun()


# ============================================================
# BUILD ACTIVE DATA
# ============================================================

years_for_calc = selected_years if selected_years else years_options
quarters_for_calc = selected_quarters if selected_quarters else quarters_options

active_raw = build_period_data(strat_df, requests_df, years_for_calc, quarters_for_calc)

if active_raw.empty:
    st.warning("Для обраного періоду активних заходів не знайдено.")
    st.stop()

active = apply_dashboard_filters(
    active_raw,
    selected_department_indices,
    selected_goals if "dash_goals" in st.session_state else [],
    selected_tasks if "dash_tasks" in st.session_state else [],
    selected_measures if "dash_measures" in st.session_state else [],
    selected_product_types if "dash_product_types" in st.session_state else [],
    selected_deputies if "dash_deputies" in st.session_state else [],
    selected_statuses if "dash_statuses" in st.session_state else [],
    selected_sources if "dash_sources" in st.session_state else []
)

if active.empty:
    st.warning("За обраними параметрами відбору даних не знайдено.")
    st.stop()

active_period_rows = active.copy()
active = collapse_to_latest_measure_rows(active)


# ============================================================
# MAIN METRICS
# ============================================================

total_active = len(active)
submitted_count = calc_submitted(active)
coverage = calc_coverage(active)
completion = mean_completion(active)
deviation_current = deviation_for_period(completion)

risk_count = len(assessment_subset(active)[assessment_subset(active)["auto_risk"].isin(["Критичний ризик", "Середній ризик"])])
critical_count = len(assessment_subset(active)[assessment_subset(active)["auto_risk"] == "Критичний ризик"])
risk_share = calc_risk_share(active)
without_data = len(active[active["status"] == "Не подано"])

completed_count = len(active[active["status_display"] == "Виконано"])
partly_count = len(active[active["status_display"] == "Частково виконано"])
not_done_count = len(active[active["status_display"] == "Не виконано"])
obsolete_count = len(active[active["status_display"] == "Втратив актуальність"])
not_time_count = len(active[active["status_display"] == "Термін не настав"])
in_progress_count = len(active[active["status_display"] == "Виконується"])

approved_requests_count = submitted_count
review_count = 0
not_counted_count = len(active[active["status"] == "Не подано"])

conclusion_title, conclusion_text, conclusion_badge = dashboard_conclusion(completion, risk_share, coverage)

period_year_label = (
    ", ".join([f"{y} рік" for y in selected_years]) if selected_years else "усі роки"
)
period_quarter_label = (
    ", ".join([f"{q} квартал" for q in selected_quarters]) if selected_quarters else "усі квартали"
)
period_label = f"{period_year_label} | {period_quarter_label}"

# Conclusion badge mapping
badge_css = {"risk-high": "badge-red", "risk-medium": "badge-yellow", "risk-low": "badge-green"}
block_css = {"risk-high": "conclusion-risk-high", "risk-medium": "conclusion-risk-medium", "risk-low": "conclusion-risk-low"}


# ============================================================
# ПРОГРЕС ВИКОНАННЯ: ВИСНОВОК СИСТЕМИ
# ============================================================

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">Прогрес виконання: висновок системи</div>', unsafe_allow_html=True)

st.markdown(f"""
<div class="conclusion-block {block_css[conclusion_badge]}">
    <span class="conclusion-badge {badge_css[conclusion_badge]}">{conclusion_title}</span>
    <div class="conclusion-meta">
        <span class="meta-chip">📅 {period_label}</span>
        <span class="meta-chip">📌 {total_active} активних заходів</span>
        <span class="meta-chip">📉 Відхилення: {deviation_current} в.п.</span>
        <span class="meta-chip">📊 Виконання: {completion}%</span>
        <span class="meta-chip">📋 Покриття: {coverage}%</span>
    </div>
    <div class="conclusion-text">{conclusion_text}</div>
</div>
""", unsafe_allow_html=True)

render_kpi_grid([
    {"title": "Заходів", "count": total_active, "percent": "100.0%", "color": "kpi-blue"},
    {"title": "Виконано", "count": completed_count, "percent": pct_value(completed_count, total_active), "color": "kpi-green"},
    {"title": "Погоджено", "count": approved_requests_count, "percent": pct_value(approved_requests_count, total_active), "color": "kpi-green"},
    {"title": "На розгляді", "count": review_count, "percent": pct_value(review_count, total_active), "color": "kpi-yellow"},
    {"title": "Не враховано", "count": not_counted_count, "percent": pct_value(not_counted_count, total_active), "color": "kpi-red"},
    {"title": "Не виконано", "count": not_done_count, "percent": pct_value(not_done_count, total_active), "color": "kpi-red"},
    {"title": "Втратив актуальність", "count": obsolete_count, "percent": pct_value(obsolete_count, total_active), "color": "kpi-gray"},
    {"title": "Термін не настав", "count": not_time_count, "percent": pct_value(not_time_count, total_active), "color": "kpi-gray"},
    {"title": "Частково виконано", "count": partly_count, "percent": pct_value(partly_count, total_active), "color": "kpi-yellow"},
    {"title": "Виконується", "count": in_progress_count, "percent": pct_value(in_progress_count, total_active), "color": "kpi-blue"},
])

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# АВТОМАТИЧНІ ІНСАЙТИ
# ============================================================

if not presentation_mode:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Автоматичні інсайти</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">Система автоматично виявляє відхилення та концентрації ризиків</div>', unsafe_allow_html=True)

    goal_failure = weighted_failure_group(active, ["goal_code", "strategic_goal"])
    dep_exploded_for_insights = explode_departments(active)
    dep_failure = weighted_failure_group(dep_exploded_for_insights, ["ssp_department"])

    if without_data > 0:
        render_insight(f"⚠️ {without_data} активних заходів не мають поданого погодженого моніторингу.", "warn")
    if critical_count > 0:
        render_insight(f"🔴 {critical_count} заходів мають критичний ризик недосягнення.", "danger")
    if not goal_failure.empty:
        row = goal_failure.iloc[0]
        render_insight(
            f"📉 Найбільша концентрація невиконаних заходів у СЦ {row['goal_code']} — "
            f"{int(row['Невиконаних'])} із {int(row['Активних_заходів'])}; "
            f"вага в обраному портфелі — {row['Вага_невиконання']}%.",
            "warn"
        )
    if not dep_failure.empty:
        row = dep_failure.iloc[0]
        render_insight(
            f"🏢 Самостійний структурний підрозділ із найвищою концентрацією невиконання: "
            f"{row['ssp_department']} — {int(row['Невиконаних'])} із {int(row['Активних_заходів'])}; "
            f"вага в обраному портфелі — {row['Вага_невиконання']}%.",
            "info"
        )
    render_insight(f"📌 Відхилення за звітний період: {deviation_current} в.п. від планового рівня.")

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# ПОКАЗНИКИ ВИКОНАННЯ СТРАТЕГІЧНОГО ПЛАНУ
# ============================================================

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">Показники виконання стратегічного плану</div>', unsafe_allow_html=True)

ind_col1, ind_col2 = st.columns([1, 1.3])

with ind_col1:
    st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
    fig_gauge = gauge_chart(completion, "Виконання СП")
    st.plotly_chart(fig_gauge, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with ind_col2:
    st.markdown('<div class="chart-wrap" style="height:100%;padding-top:20px;">', unsafe_allow_html=True)
    render_indicator_bar("Виконання СП", completion, 100, "#005BBB")
    render_indicator_bar("Покриття моніторингом", coverage, 100, "#0891b2")
    dev_display = round(100 + deviation_current, 1)
    render_indicator_bar("Відхилення за звітний період", round(100 + deviation_current, 1), 100, "#d97706")
    render_indicator_bar("Частка заходів без ризику", round(100 - risk_share, 1), 100, "#16a34a")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# AGGREGATIONS
# ============================================================

status_counts = active.groupby("status_display").size().reset_index(name="Кількість")
risk_counts = active.groupby("auto_risk").size().reset_index(name="Кількість")
traffic_counts = active.groupby("traffic_light").size().reset_index(name="Кількість")

goal_progress = (
    active
    .groupby(["goal_code", "strategic_goal"])
    .agg(
        Активних_заходів=("code", "count"),
        Виконання=("performance_score", "mean"),
        Покриття=("status", lambda x: (x != "Не подано").sum()),
        Ризикових=("auto_risk", lambda x: x.isin(["Критичний ризик", "Середній ризик"]).sum()),
        Середній_ризик=("risk_score", "mean")
    )
    .reset_index()
)
goal_progress["Виконання"] = goal_progress["Виконання"].fillna(0).round(1)
goal_progress["Покриття_%"] = (goal_progress["Покриття"] / goal_progress["Активних_заходів"] * 100).round(1)
goal_progress["Середній_ризик"] = goal_progress["Середній_ризик"].fillna(0).round(1)

dep_active = explode_departments(active)
dep_progress = (
    dep_active
    .groupby("ssp_department")
    .agg(
        Активних_заходів=("code", "count"),
        Виконання=("performance_score", "mean"),
        Подано=("status", lambda x: (x != "Не подано").sum()),
        Ризикових=("auto_risk", lambda x: x.isin(["Критичний ризик", "Середній ризик"]).sum()),
        Критичних=("auto_risk", lambda x: (x == "Критичний ризик").sum()),
        Середній_ризик=("risk_score", "mean")
    )
    .reset_index()
)
dep_progress["Виконання"] = dep_progress["Виконання"].fillna(0).round(1)
dep_progress["Покриття_%"] = (dep_progress["Подано"] / dep_progress["Активних_заходів"] * 100).round(1)
dep_progress["Середній_ризик"] = dep_progress["Середній_ризик"].fillna(0).round(1)


# ============================================================
# VISUALIZATIONS: СТРАТЕГІЧНІ ЦІЛІ (Статуси + Цілі)
# ============================================================

if view_mode in ["Усі візуалізації", "Стратегічні цілі"] or presentation_mode:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Статуси виконання за принципом світлофора</div>', unsafe_allow_html=True)

    sc1, sc2 = st.columns([1, 1.6])

    with sc1:
        st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="chart-title">Розподіл активних заходів за станом виконання</div>', unsafe_allow_html=True)
        fig_tl = px.pie(
            traffic_counts,
            names="traffic_light",
            values="Кількість",
            hole=0.52,
            color="traffic_light",
            color_discrete_map=TRAFFIC_COLORS
        )
        fig_tl.update_traces(
            textfont_size=13,
            marker=dict(line=dict(color="#ffffff", width=2))
        )
        fig_tl.update_layout(
            **CHART_LAYOUT,
            height=300,
            showlegend=True,
            legend=dict(orientation="v", x=1, y=0.5),
            margin=dict(l=10, r=10, t=10, b=10)
        )
        st.plotly_chart(fig_tl, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with sc2:
        st.markdown('<div class="section-title" style="margin-top:0">Виконання за стратегічними цілями</div>', unsafe_allow_html=True)
        st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="chart-title">Відсоток виконання по кожній стратегічній цілі</div>', unsafe_allow_html=True)

        goal_sorted = goal_progress.sort_values("Виконання", ascending=True)
        goal_sorted["label"] = goal_sorted["goal_code"].astype(str) + " " + goal_sorted["strategic_goal"].astype(str).str[:40]

        fig_goals = px.bar(
            goal_sorted,
            x="Виконання",
            y="label",
            orientation="h",
            text=goal_sorted["Виконання"].apply(lambda x: f"{x:.1f}%"),
            hover_data={"Активних_заходів": True, "Покриття_%": True, "Ризикових": True},
            color="Виконання",
            color_continuous_scale=["#dc2626", "#fef08a", "#16a34a"],
            range_color=[0, 100],
        )
        fig_goals.update_traces(
            textposition="outside",
            textfont_size=11,
            marker_line_width=0
        )
        fig_goals.update_layout(
            **CHART_LAYOUT,
            height=max(200, len(goal_sorted) * 38 + 40),
            xaxis=dict(range=[0, 115], showgrid=True, gridcolor="#f1f5f9", ticksuffix="%"),
            yaxis=dict(showgrid=False),
            coloraxis_showscale=False,
            margin=dict(l=10, r=60, t=10, b=10)
        )
        st.plotly_chart(fig_goals, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# VISUALIZATIONS: САМОСТІЙНІ СТРУКТУРНІ ПІДРОЗДІЛИ
# ============================================================

if not presentation_mode and view_mode in ["Усі візуалізації", "Самостійні структурні підрозділи"]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Рейтинг самостійних структурних підрозділів</div>', unsafe_allow_html=True)

    rank_df = dep_progress.sort_values("Виконання", ascending=False).copy()
    rank_df["Місце"] = range(1, len(rank_df) + 1)

    rank_display = rank_df[[
        "Місце", "ssp_department", "Виконання", "Покриття_%",
        "Ризикових", "Критичних", "Активних_заходів"
    ]].rename(columns={
        "ssp_department": "Самостійний структурний підрозділ",
        "Покриття_%": "Покриття, %",
        "Активних_заходів": "Активних заходів"
    })

    styled_rank = (
        rank_display.style
        .apply(lambda row: style_rank_table(row, len(rank_display)), axis=1)
        .set_properties(**{"text-align": "center"})
        .set_table_styles([{
            "selector": "th",
            "props": [
                ("text-align", "center"), ("background-color", "#e9eef7"),
                ("color", "#111827"), ("font-weight", "900"), ("border", "1px solid #d8dee9")
            ]
        }])
    )

    st.dataframe(styled_rank, use_container_width=True, hide_index=True)

    st.markdown("<hr class='vis-separator'>", unsafe_allow_html=True)

    # Chart: top 20 departments for readability
    top_n = min(30, len(rank_df))
    top_deps = rank_df.head(top_n)

    st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="chart-title">Виконання за самостійними структурними підрозділами</div>', unsafe_allow_html=True)

    fig_dep = px.bar(
        top_deps,
        x="ssp_department",
        y="Виконання",
        text=top_deps["Виконання"].apply(lambda x: f"{x:.1f}%"),
        hover_data={"Активних_заходів": True, "Покриття_%": True, "Ризикових": True, "Критичних": True},
        color="Виконання",
        color_continuous_scale=["#dc2626", "#fef08a", "#16a34a"],
        range_color=[0, 100],
    )
    fig_dep.update_traces(
        textposition="outside",
        textfont_size=10,
        marker_line_width=0
    )
    fig_dep.update_layout(
        **CHART_LAYOUT,
        height=380,
        xaxis=dict(
            tickangle=-35,
            tickfont=dict(size=10),
            showgrid=False
        ),
        yaxis=dict(
            range=[0, 115],
            showgrid=True,
            gridcolor="#f1f5f9",
            ticksuffix="%"
        ),
        coloraxis_showscale=False,
        margin=dict(l=10, r=10, t=30, b=100)
    )
    st.plotly_chart(fig_dep, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr class='vis-separator'>", unsafe_allow_html=True)

    # Виконання за Заступниками Міністра
    st.markdown('<div class="section-title">Виконання за Заступниками Міністра</div>', unsafe_allow_html=True)

    deputy_data = active.copy()
    deputy_data["deputy_minister"] = (
        deputy_data["deputy_minister"].fillna("").astype(str)
        .replace("", "Не визначено")
    )

    deputy_progress = (
        deputy_data
        .groupby("deputy_minister")
        .agg(Активних_заходів=("code", "count"), Виконання=("performance_score", "mean"))
        .reset_index()
    )
    deputy_progress["Виконання"] = deputy_progress["Виконання"].fillna(0).round(1)
    deputy_progress["Dep_short"] = deputy_progress["deputy_minister"].str[:30]

    st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="chart-title">Виконання за Заступниками Міністра</div>', unsafe_allow_html=True)

    fig_dep2 = px.bar(
        deputy_progress.sort_values("Виконання", ascending=False),
        x="Dep_short",
        y="Виконання",
        text=deputy_progress.sort_values("Виконання", ascending=False)["Виконання"].apply(lambda x: f"{x:.1f}%"),
        hover_data={"Активних_заходів": True},
        color="Виконання",
        color_continuous_scale=["#dc2626", "#fef08a", "#16a34a"],
        range_color=[0, 100],
        custom_data=["deputy_minister"]
    )
    fig_dep2.update_traces(
        textposition="outside",
        textfont_size=10,
        hovertemplate="<b>%{customdata[0]}</b><br>Виконання: %{y:.1f}%<br>Активних заходів: %{customdata}<extra></extra>",
        marker_line_width=0
    )
    fig_dep2.update_layout(
        **CHART_LAYOUT,
        height=360,
        xaxis=dict(
            tickangle=-30,
            tickfont=dict(size=9),
            showgrid=False
        ),
        yaxis=dict(
            range=[0, 115],
            showgrid=True,
            gridcolor="#f1f5f9",
            ticksuffix="%"
        ),
        coloraxis_showscale=False,
        margin=dict(l=10, r=10, t=30, b=120)
    )
    st.plotly_chart(fig_dep2, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# VISUALIZATIONS: РИЗИКИ
# ============================================================

if not presentation_mode and view_mode in ["Усі візуалізації", "Ризики"]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Автоматична оцінка ризиків</div>', unsafe_allow_html=True)

    r1, r2 = st.columns([1, 1.6])

    with r1:
        st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="chart-title">Рівень ризику недосягнення</div>', unsafe_allow_html=True)

        fig_risk_pie = px.pie(
            risk_counts,
            names="auto_risk",
            values="Кількість",
            hole=0.52,
            color="auto_risk",
            color_discrete_map=RISK_COLORS
        )
        fig_risk_pie.update_traces(
            textfont_size=12,
            marker=dict(line=dict(color="#ffffff", width=2))
        )
        fig_risk_pie.update_layout(
            **CHART_LAYOUT,
            height=280,
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=True,
            legend=dict(orientation="v", x=1, y=0.5)
        )
        st.plotly_chart(fig_risk_pie, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with r2:
        st.markdown('<div class="section-title" style="margin-top:0;">Структура ризиків за самостійними структурними підрозділами</div>', unsafe_allow_html=True)
        st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="chart-title">Ризики за самостійними структурними підрозділами</div>', unsafe_allow_html=True)

        stacked = dep_active.groupby(["ssp_department", "auto_risk"]).size().reset_index(name="Кількість")
        # Filter out "Не оцінюється" for cleaner view
        stacked_vis = stacked[stacked["auto_risk"] != "Не оцінюється"].copy()

        fig_risk_bar = px.bar(
            stacked_vis,
            x="ssp_department",
            y="Кількість",
            color="auto_risk",
            color_discrete_map=RISK_COLORS,
            barmode="stack",
            labels={
                "ssp_department": "Самостійний структурний підрозділ",
                "auto_risk": "Ризик"
            }
        )
        fig_risk_bar.update_layout(
            **CHART_LAYOUT,
            height=310,
            xaxis=dict(tickangle=-35, tickfont=dict(size=9), showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="#f1f5f9"),
            legend=dict(orientation="h", x=0, y=-0.25),
            margin=dict(l=10, r=10, t=10, b=80)
        )
        st.plotly_chart(fig_risk_bar, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# VISUALIZATIONS: ДИНАМІКА
# ============================================================

if not presentation_mode and view_mode in ["Усі візуалізації", "Динаміка"]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Динаміка виконання</div>', unsafe_allow_html=True)

    trend_rows = []

    for y in years_for_calc:
        for q in quarters_for_calc:
            temp_raw = build_period_data(strat_df, requests_df, [y], [q])
            temp = apply_dashboard_filters(
                temp_raw,
                selected_department_indices,
                selected_goals if "dash_goals" in st.session_state else [],
                selected_tasks if "dash_tasks" in st.session_state else [],
                selected_measures if "dash_measures" in st.session_state else [],
                selected_product_types if "dash_product_types" in st.session_state else [],
                selected_deputies if "dash_deputies" in st.session_state else [],
                selected_statuses if "dash_statuses" in st.session_state else [],
                selected_sources if "dash_sources" in st.session_state else []
            )

            if temp.empty:
                value, cov, dev = 0, 0, -100
            else:
                value = mean_completion(temp)
                cov = calc_coverage(temp)
                dev = deviation_for_period(value)

            trend_rows.append({
                "Період": f"{y} {q}",
                "Рік": y,
                "Квартал": q,
                "Виконання": value,
                "Покриття": cov,
                "Відхилення за звітний період": dev
            })

    trend_df = pd.DataFrame(trend_rows)

    st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="chart-title">Тренд виконання, покриття і відхилення</div>', unsafe_allow_html=True)

    fig_trend = px.line(
        trend_df,
        x="Період",
        y=["Виконання", "Покриття", "Відхилення за звітний період"],
        markers=True,
        color_discrete_map={
            "Виконання": "#005BBB",
            "Покриття": "#0891b2",
            "Відхилення за звітний період": "#dc2626"
        }
    )
    fig_trend.update_traces(line_width=2.5, marker_size=7)
    fig_trend.update_layout(
        **CHART_LAYOUT,
        height=340,
        xaxis=dict(showgrid=False, tickangle=-20),
        yaxis=dict(showgrid=True, gridcolor="#f1f5f9", ticksuffix="%"),
        legend=dict(orientation="h", x=0, y=1.12),
        margin=dict(l=10, r=10, t=40, b=30)
    )
    st.plotly_chart(fig_trend, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# VISUALIZATIONS: HEATMAP
# ============================================================

if not presentation_mode and view_mode in ["Усі візуалізації", "Heatmap"]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Heatmap: самостійний структурний підрозділ × квартал</div>', unsafe_allow_html=True)

    heat_rows = []

    for y in years_for_calc:
        for q in quarters_for_calc:
            temp_raw = build_period_data(strat_df, requests_df, [y], [q])
            temp = apply_dashboard_filters(
                temp_raw,
                selected_department_indices,
                selected_goals if "dash_goals" in st.session_state else [],
                selected_tasks if "dash_tasks" in st.session_state else [],
                selected_measures if "dash_measures" in st.session_state else [],
                selected_product_types if "dash_product_types" in st.session_state else [],
                selected_deputies if "dash_deputies" in st.session_state else [],
                selected_statuses if "dash_statuses" in st.session_state else [],
                selected_sources if "dash_sources" in st.session_state else []
            )

            if temp.empty:
                continue

            temp_dep = explode_departments(temp)
            dep_heat = temp_dep.groupby("ssp_department").agg(
                Виконання=("performance_score", "mean")
            ).reset_index()

            for _, row in dep_heat.iterrows():
                heat_rows.append({
                    "Самостійний структурний підрозділ": row["ssp_department"],
                    "Період": f"{y} {q}",
                    "Виконання": round(row["Виконання"], 1) if pd.notna(row["Виконання"]) else 0
                })

    heat_df = pd.DataFrame(heat_rows)

    if not heat_df.empty:
        st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="chart-title">Теплова карта виконання</div>', unsafe_allow_html=True)

        pivot = heat_df.pivot_table(
            index="Самостійний структурний підрозділ",
            columns="Період",
            values="Виконання",
            aggfunc="mean"
        ).fillna(0)

        fig_heat = px.imshow(
            pivot,
            color_continuous_scale=["#fee2e2", "#fef9c3", "#dcfce7"],
            zmin=0, zmax=100,
            aspect="auto",
            text_auto=".0f",
            labels=dict(x="Період", y="Підрозділ", color="Виконання, %")
        )
        fig_heat.update_layout(
            **CHART_LAYOUT,
            height=max(300, len(pivot) * 22 + 80),
            coloraxis_colorbar=dict(title="Викон., %", ticksuffix="%"),
            xaxis=dict(side="top", tickfont=dict(size=10)),
            yaxis=dict(tickfont=dict(size=9)),
            margin=dict(l=10, r=60, t=60, b=10)
        )
        st.plotly_chart(fig_heat, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("Недостатньо даних для побудови теплової карти.")

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# PROBLEM MEASURES
# ============================================================

if not presentation_mode:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Проблемні заходи</div>', unsafe_allow_html=True)

    risk_table = active[
        (
            active["auto_risk"].isin(["Критичний ризик", "Середній ризик"]) |
            (active["status"] == "Не подано") |
            (active["performance_score"].fillna(0) < 75)
        )
        & (active["included_in_assessment"] == True)
    ].copy()

    if risk_table.empty:
        st.success("Ризикових заходів за обраний період не виявлено.")
    else:
        risk_table = risk_table.rename(columns={
            "code": "Код",
            "name": "Захід",
            "indicator": "Індикатор",
            "department": "Головний ССП",
            "status_display": "Статус виконання",
            "selected_target": "Планове значення",
            "numeric_value": "Фактичне значення",
            "auto_risk": "Рівень ризику",
            "risk_score": "Risk score",
            "traffic_light": "Traffic light",
            "risk_reason": "Причина ризику",
            "progress_text": "Опис прогресу",
            "period_label": "Період"
        })

        st.dataframe(
            risk_table[[
                "Період", "Код", "Захід", "Індикатор", "Головний ССП",
                "Статус виконання", "Планове значення", "Фактичне значення",
                "Traffic light", "Рівень ризику", "Risk score", "Причина ризику", "Опис прогресу"
            ]],
            use_container_width=True,
            hide_index=True
        )

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# FULL TABLE
# ============================================================

if not presentation_mode and view_mode == "Таблиці":
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Повна таблиця активних заходів</div>', unsafe_allow_html=True)

    full = active.rename(columns={
        "period_label": "Період",
        "code": "Код",
        "name": "Захід",
        "indicator": "Індикатор",
        "unit": "Одиниця виміру",
        "department": "Головний ССП",
        "product_type": "Тип продукту",
        "source_national": "Джерело даних",
        "start_period": "Початок",
        "end_period": "Кінець",
        "selected_target": "Планове значення",
        "numeric_value": "Фактичне значення",
        "status_display": "Статус виконання",
        "performance_score": "Оцінка виконання, %",
        "auto_risk": "Ризик",
        "risk_score": "Risk score",
        "traffic_light": "Traffic light",
        "risk_reason": "Причина ризику"
    })

    st.dataframe(
        full[[
            "Період", "Код", "Захід", "Індикатор", "Одиниця виміру", "Тип продукту",
            "Головний ССП", "Джерело даних", "Початок", "Кінець",
            "Планове значення", "Фактичне значення", "Статус виконання",
            "Оцінка виконання, %", "Traffic light", "Ризик", "Risk score", "Причина ризику"
        ]],
        use_container_width=True,
        hide_index=True
    )

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# METHODOLOGY
# ============================================================

if not presentation_mode:
    with st.expander("Методологія розрахунку"):
        st.markdown("""
        <div class="methodology-box">
        <strong>Активні заходи</strong> — заходи, період виконання яких охоплює обраний рік і квартал.<br><br>

        <strong>Виконання СП</strong> рахується як середня оцінка виконання активних заходів:
        <ul>
            <li>якщо є планове та фактичне значення — використовується співвідношення факт / план;</li>
            <li>якщо план / факт не можна порахувати числово — використовується статус виконання;</li>
            <li>«Виконано» = 100%; «Частково виконано» = 75%; «Виконується» = 50%;</li>
            <li>«Не виконано», «Не подано», «Не розпочато», «Прострочено», «Потребує уваги» = 0%;</li>
            <li>«Термін не настав» та «Втратив актуальність» не включаються до оцінки ризику.</li>
        </ul>

        <strong>Risk score</strong> визначається автоматично на основі стану виконання:
        відсутність погоджених даних, відставання від плану, прострочення строку, проблемний статус.<br><br>

        <strong>Traffic light:</strong>
        🟢 100%+ — у графіку | 🟡 75–99% — часткове | 🔴 &lt;75% — відставання | ⚪ не оцінюється.<br><br>

        <strong>Відхилення за звітний період</strong> = середній відсоток виконання мінус 100%.
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# FOOTER
# ============================================================

st.markdown("""
<div class="footer">
    <strong>Розроблено департаментом стратегічного планування та макроекономічного прогнозування</strong><br>
    Версія DEMO 1.4 | 2026 | Внутрішня система моніторингу стратегічного плану
</div>
""", unsafe_allow_html=True)
