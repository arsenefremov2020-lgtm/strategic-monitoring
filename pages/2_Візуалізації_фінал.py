import re
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from supabase import create_client


# ============================================================
# CONFIG
# ============================================================

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

st.markdown(
    """
<style>
:root {
    --bg-1: #eef4ff;
    --bg-2: #f7fafc;
    --ink: #0f172a;
    --muted: #64748b;
    --line: rgba(148, 163, 184, 0.34);
    --card: rgba(255,255,255,0.88);
    --blue: #2563eb;
    --blue-dark: #1e3a8a;
    --green: #16a34a;
    --yellow: #d97706;
    --red: #dc2626;
}

.stApp {
    background:
        radial-gradient(circle at 10% 10%, rgba(37,99,235,0.16), transparent 28%),
        radial-gradient(circle at 92% 12%, rgba(14,165,233,0.15), transparent 24%),
        radial-gradient(circle at 16% 88%, rgba(22,163,74,0.12), transparent 25%),
        linear-gradient(180deg, #f8fbff 0%, #eef4ff 45%, #f8fafc 100%);
}

.main .block-container {
    max-width: 1480px;
    padding-top: 1.25rem;
    padding-bottom: 2rem;
}

.ua-line {
    height: 6px;
    border-radius: 999px;
    background: linear-gradient(90deg, #005BBB 0%, #005BBB 50%, #FFD500 50%, #FFD500 100%);
    margin: 0 0 16px 0;
}

.top-label {
    text-align: right;
    color: var(--muted);
    font-size: 13px;
    font-weight: 750;
    margin-bottom: 8px;
}

.hero {
    background:
        linear-gradient(135deg, rgba(255,255,255,0.95), rgba(239,246,255,0.88)),
        radial-gradient(circle at 85% 25%, rgba(37,99,235,0.12), transparent 28%);
    border: 1px solid rgba(148, 163, 184, 0.32);
    border-radius: 24px;
    padding: 28px 30px;
    margin-bottom: 18px;
    box-shadow: 0 18px 48px rgba(15, 23, 42, 0.08);
}

.hero-title {
    font-size: 34px;
    line-height: 1.12;
    font-weight: 950;
    letter-spacing: -0.03em;
    color: var(--ink);
    margin-bottom: 10px;
}

.hero-subtitle {
    max-width: 980px;
    color: #475569;
    font-size: 15px;
    line-height: 1.62;
}

.pill-row {
    display: flex;
    flex-wrap: wrap;
    gap: 9px;
    margin-top: 16px;
}

.pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255,255,255,0.74);
    color: #334155;
    border: 1px solid rgba(148, 163, 184, 0.35);
    border-radius: 999px;
    padding: 8px 12px;
    font-size: 12.5px;
    font-weight: 720;
}

.panel {
    background: var(--card);
    border: 1px solid rgba(148, 163, 184, 0.32);
    border-radius: 22px;
    padding: 20px 22px;
    margin: 16px 0;
    box-shadow: 0 14px 36px rgba(15, 23, 42, 0.065);
    backdrop-filter: blur(10px);
}

.panel-tight {
    padding: 16px 18px;
}

.panel-title {
    color: var(--ink);
    font-size: 20px;
    font-weight: 920;
    letter-spacing: -0.02em;
    margin-bottom: 5px;
}

.panel-subtitle {
    color: var(--muted);
    font-size: 13.5px;
    line-height: 1.55;
    margin-bottom: 10px;
}

.kpi-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 13px;
    margin: 10px 0 4px 0;
}

.kpi {
    background: rgba(255,255,255,0.72);
    border: 1px solid rgba(148, 163, 184, 0.28);
    border-radius: 18px;
    padding: 15px 16px;
    min-height: 116px;
}

.kpi-label {
    color: #64748b;
    font-size: 12.5px;
    line-height: 1.3;
    font-weight: 820;
    min-height: 32px;
}

.kpi-value {
    color: var(--ink);
    font-size: 29px;
    line-height: 1;
    font-weight: 950;
    margin-top: 8px;
}

.kpi-note {
    color: #64748b;
    font-size: 12px;
    margin-top: 8px;
}

.kpi-blue { background: linear-gradient(180deg, #eff6ff, #ffffff); border-color: #bfdbfe; }
.kpi-green { background: linear-gradient(180deg, #ecfdf5, #ffffff); border-color: #bbf7d0; }
.kpi-yellow { background: linear-gradient(180deg, #fffbeb, #ffffff); border-color: #fde68a; }
.kpi-red { background: linear-gradient(180deg, #fef2f2, #ffffff); border-color: #fecaca; }
.kpi-gray { background: linear-gradient(180deg, #f8fafc, #ffffff); border-color: #e2e8f0; }

.insight-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 12px;
    margin-top: 10px;
}

.insight {
    border-radius: 16px;
    padding: 14px 15px;
    border: 1px solid rgba(148,163,184,0.30);
    background: rgba(255,255,255,0.68);
    color: #334155;
    font-size: 13.5px;
    line-height: 1.45;
}

.insight strong {
    display: block;
    color: var(--ink);
    font-size: 14px;
    margin-bottom: 5px;
}

.badge-risk-high { border-color: #fecaca; background: #fef2f2; }
.badge-risk-mid { border-color: #fed7aa; background: #fff7ed; }
.badge-risk-low { border-color: #bbf7d0; background: #ecfdf5; }

.filter-shell {
    background: rgba(255,255,255,0.72);
    border: 1px solid rgba(148, 163, 184, 0.30);
    border-radius: 22px;
    padding: 16px 18px 8px 18px;
    margin: 16px 0;
    box-shadow: 0 10px 28px rgba(15, 23, 42, 0.055);
}

.filter-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 8px;
}

.filter-title {
    color: var(--ink);
    font-size: 19px;
    font-weight: 920;
    letter-spacing: -0.02em;
}

.filter-hint {
    color: var(--muted);
    font-size: 13px;
    margin-top: 3px;
}

.filter-chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 8px 0 12px 0;
}

.filter-chip {
    background: #eff6ff;
    color: #1d4ed8;
    border: 1px solid #bfdbfe;
    border-radius: 999px;
    padding: 6px 10px;
    font-size: 12px;
    font-weight: 760;
}

div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stTextInput"] input {
    background-color: rgba(255,255,255,0.86) !important;
    border: 1px solid rgba(148, 163, 184, 0.55) !important;
    border-radius: 13px !important;
    min-height: 43px !important;
    box-shadow: none !important;
}

div[data-testid="stMultiSelect"] label,
div[data-testid="stSelectbox"] label,
div[data-testid="stTextInput"] label {
    font-weight: 800 !important;
    color: #1e293b !important;
    font-size: 13px !important;
}

div[data-testid="stTabs"] button p {
    font-weight: 850 !important;
}

.plot-card {
    background: rgba(255,255,255,0.72);
    border: 1px solid rgba(148,163,184,0.30);
    border-radius: 20px;
    padding: 16px 16px 8px 16px;
    margin-bottom: 14px;
}

.table-note {
    color: #64748b;
    font-size: 13px;
    line-height: 1.5;
    margin: 5px 0 12px 0;
}

.footer {
    text-align: center;
    color: #64748b;
    font-size: 13px;
    margin-top: 46px;
    padding: 22px 0 12px 0;
    border-top: 1px solid rgba(148, 163, 184, 0.35);
}

@media (max-width: 1100px) {
    .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .insight-grid { grid-template-columns: 1fr; }
    .hero-title { font-size: 27px; }
}
</style>
""",
    unsafe_allow_html=True
)


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
    if "1 квартал" in text or "i квартал" in text or " і квартал" in text:
        q = 1
    elif "2 квартал" in text or "ii квартал" in text or " іі квартал" in text:
        q = 2
    elif "3 квартал" in text or "iii квартал" in text or " ііі квартал" in text:
        q = 3
    elif "4 квартал" in text or "iv квартал" in text:
        q = 4

    year_match = re.search(r"20\d{2}", text)
    year = int(year_match.group()) if year_match else None
    if year and q:
        return year * 10 + q
    return None


def quarter_to_number(q):
    q = str(q).strip()
    return {"I": 1, "II": 2, "III": 3, "IV": 4, "1": 1, "2": 2, "3": 3, "4": 4}.get(q, 1)


def quarter_to_roman(q):
    q = str(q).strip()
    return {"1": "I", "2": "II", "3": "III", "4": "IV", "I": "I", "II": "II", "III": "III", "IV": "IV"}.get(q, "I")


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


def short_label(value, limit=58):
    value = clean(value)
    if len(value) <= limit:
        return value
    return value[:limit - 1].rstrip() + "…"


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
        return "Не оцінюється"
    if score >= 100:
        return "У графіку"
    if score >= 75:
        return "Часткове виконання"
    return "Відстає"


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
        reasons.append("за активним заходом не подано погоджені моніторингові дані")

    if pf is not None:
        if pf >= 100:
            reasons.append("фактичне значення досягло або перевищило планове")
        elif pf >= 75:
            score += 25
            reasons.append("фактичне значення становить 75–99% плану")
        else:
            score += 45
            reasons.append("значне відставання фактичного значення від планового")
    else:
        if display_status == "Виконано":
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
        return "План переважно виконується", "Поточний стан виглядає контрольованим: виконання та покриття моніторингом достатні, частка ризиків низька.", "badge-risk-low"
    if completion >= 45 and risk_share <= 35:
        return "Є помірні відхилення", "Потрібна увага до окремих заходів, структурних підрозділів або стратегічних цілей.", "badge-risk-mid"
    return "Високий ризик невиконання", "Дані вказують на недостатній рівень погодженого моніторингу або суттєві відхилення від планових показників.", "badge-risk-high"


def deviation_for_period(completion):
    return round(completion - 100, 1)


def reset_filters():
    keys = [
        "dash_years", "dash_quarters", "dash_department_indices",
        "dash_goals", "dash_tasks", "dash_measures", "dash_product_types",
        "dash_deputies", "dash_statuses", "dash_sources", "dash_focus",
        "dash_presentation_mode"
    ]
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]


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
        ((measures["start_num"].isna()) | (measures["start_num"] <= selected_period_num))
        & ((measures["end_num"].isna()) | (measures["end_num"] >= selected_period_num))
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
        period_requests = pd.DataFrame(columns=["strat_code", "status", "numeric_value", "risks", "progress_text", "submitted_at"])
    else:
        quarter_num = str(quarter_to_number(quarter))
        quarter_roman = quarter_to_roman(quarter)
        period_requests = approved_requests[
            (approved_requests["year"].astype(str) == str(year))
            & (
                (approved_requests["quarter"].astype(str) == str(quarter))
                | (approved_requests["quarter"].astype(str) == quarter_num)
                | (approved_requests["quarter"].astype(str) == quarter_roman)
            )
        ].copy()
        if not period_requests.empty:
            period_requests = period_requests.sort_values("submitted_at").groupby("strat_code").tail(1)

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
    active["plan_fact_percent"] = active.apply(lambda r: plan_fact_percent(r["numeric_value"], r["selected_target"]), axis=1)
    active["is_quantitative_pf"] = active.apply(is_quantitative_plan_fact, axis=1)
    active["performance_score"] = active.apply(
        lambda r: r["plan_fact_percent"] if pd.notna(r["plan_fact_percent"]) else r["status_score"],
        axis=1
    )
    active["included_in_assessment"] = ~active["status_display"].isin(["Термін не настав", "Втратив актуальність"])

    risk_results = active.apply(lambda r: risk_score_calc(r, selected_q_num, selected_period_num), axis=1)
    active["risk_score"] = [x[0] for x in risk_results]
    active["risk_reason"] = [x[1] for x in risk_results]
    active["auto_risk"] = active["risk_score"].apply(risk_level_from_score)
    active.loc[~active["included_in_assessment"], "auto_risk"] = "Не оцінюється"
    active["traffic_light"] = active["performance_score"].apply(traffic_light)
    active.loc[~active["included_in_assessment"], "traffic_light"] = "Не оцінюється"

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
        data = data[data["status"].isin(statuses) | data["status_display"].isin(statuses)]
    if sources:
        data = data[data["source_national"].isin(sources)]
    return data.copy()


def collapse_to_latest_measure_rows(df):
    if df.empty:
        return df
    data = df.copy()
    data["_period_sort"] = data["period_year"].astype(int) * 10 + data["period_quarter"].apply(quarter_to_number)
    data = data.sort_values(["code", "_period_sort"]).groupby("code", as_index=False).tail(1).drop(columns=["_period_sort"])
    return data


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


def calc_approval_counts(requests_df, active_codes, years, quarters):
    result = {"Погоджено": 0, "На розгляді": 0, "Не враховано": 0}
    if requests_df is None or requests_df.empty or not active_codes:
        return result
    required = ["year", "quarter", "strat_code", "approval_status", "submitted_at"]
    data = requests_df.copy()
    for col in required:
        if col not in data.columns:
            data[col] = ""
    q_values = set()
    for q in quarters:
        q_values.add(str(q))
        q_values.add(str(quarter_to_number(q)))
        q_values.add(quarter_to_roman(q))
    data = data[
        data["strat_code"].astype(str).isin(set(map(str, active_codes)))
        & data["year"].astype(str).isin(set(map(str, years)))
        & data["quarter"].astype(str).isin(q_values)
    ].copy()
    if data.empty:
        return result
    data = data.sort_values("submitted_at").groupby("strat_code", as_index=False).tail(1)
    counts = data["approval_status"].fillna("").astype(str).value_counts().to_dict()
    for key in result:
        result[key] = int(counts.get(key, 0))
    return result


def calc_risk_share(active):
    assessed = assessment_subset(active)
    if assessed.empty:
        return 0
    risk_count = len(assessed[assessed["auto_risk"].isin(["Критичний ризик", "Середній ризик"])])
    return round(risk_count / len(assessed) * 100, 1)


def pct_value(count, total):
    if total == 0:
        return "0.0%"
    return f"{round(count / total * 100, 1)}%"


def kpi_card(label, value, note, color="kpi-gray"):
    return f"""
    <div class="kpi {color}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-note">{note}</div>
    </div>
    """


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
    data = active[active["included_in_assessment"] == True].copy()
    if data.empty:
        return pd.DataFrame()
    data["failed_weight_flag"] = data.apply(is_failed_for_weight, axis=1)
    grouped = (
        data.groupby(group_cols, dropna=False)
        .agg(
            Активних_заходів=("code", "count"),
            Невиконаних=("failed_weight_flag", "sum"),
            Виконання=("performance_score", "mean"),
            Ризик=("risk_score", "mean")
        )
        .reset_index()
    )
    grouped["Вага_невиконання"] = grouped["Невиконаних"] / len(data) * 100
    for col in ["Виконання", "Ризик", "Вага_невиконання"]:
        grouped[col] = grouped[col].fillna(0).round(1)
    return grouped.sort_values(["Вага_невиконання", "Невиконаних", "Активних_заходів"], ascending=[False, False, False])


def apply_plot_theme(fig, height=390, legend_orientation="h"):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=42, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Arial", size=12, color="#334155"),
        title=dict(font=dict(size=15, color="#0f172a"), x=0.02, xanchor="left"),
        legend=dict(orientation=legend_orientation, yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(148,163,184,0.24)", zeroline=False)
    return fig


def status_color_map():
    return {
        "Виконано": "#16a34a",
        "Частково виконано": "#d97706",
        "Виконується": "#2563eb",
        "Не виконано": "#dc2626",
        "Термін не настав": "#94a3b8",
        "Втратив актуальність": "#64748b",
        "У графіку": "#16a34a",
        "Відстає": "#dc2626",
        "Не оцінюється": "#94a3b8",
        "Критичний ризик": "#dc2626",
        "Середній ризик": "#d97706",
        "Низький ризик": "#16a34a",
    }


# ============================================================
# HEADER
# ============================================================

st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)
st.markdown('<div class="top-label">🇺🇦 Міністерство економіки, довкілля та сільського господарства України</div>', unsafe_allow_html=True)

last_update = datetime.now().strftime("%d.%m.%Y %H:%M")

st.markdown(
    f"""
<div class="hero">
    <div class="hero-title">Аналітичний дашборд результативності стратегічного плану</div>
    <div class="hero-subtitle">
        Аналітична панель забезпечує комплексне представлення результатів виконання Стратегічного плану. Інфографіка та моніторинговий звіт формуються за результатами
        проведення оцінки на основі моніторингу й оцінювання стратегічних результатів як у цілому, так і в розрізі кожного самостійного структурного підрозділу окремо.
    </div>
    <div class="pill-row">
        <div class="pill">• Сторінка: Dashboard</div>
        <div class="pill">• Джерело: Excel + Supabase</div>
        <div class="pill">• Факт: погоджені заявки</div>
        <div class="pill">• Оновлено: {last_update}</div>
    </div>
</div>
""",
    unsafe_allow_html=True
)


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
    set(re.findall(r"\d+", " | ".join(measures_all[["department", "department_co_1", "department_co_2"]].fillna("").astype(str).agg(" | ".join, axis=1).tolist()))),
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

raw_status_options = unique_clean_values(requests_df["status"]) if (not requests_df.empty and "status" in requests_df.columns) else []
base_status_options = [
    "Виконано", "Виконано частково", "Частково виконано", "Виконується",
    "Не виконано", "Не розпочато", "Прострочено", "Потребує уваги",
    "Не подано", "Термін не настав", "Не настав час",
    "Втратив актуальність", "Втратило актуальність"
]
status_rank = {name: i for i, name in enumerate(base_status_options)}
status_options = sorted(set(raw_status_options + base_status_options), key=lambda x: status_rank.get(x, 999))


# ============================================================
# FILTERS
# ============================================================

st.markdown(
    """
<div class="filter-shell">
    <div class="filter-header">
        <div>
            <div class="filter-title">Параметри відбору</div>
            <div class="filter-hint">Оберіть необхідні параметри: період, індекс ССП та режим перегляду даних.</div>
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True
)

f1, f2, f3, f4 = st.columns([1.05, 1.05, 1.55, 1.2])
with f1:
    selected_years = st.multiselect("Рік", years_options, default=[], key="dash_years", placeholder="Усі роки")
with f2:
    selected_quarters = st.multiselect("Квартал", quarters_options, default=[], key="dash_quarters", placeholder="Усі квартали")
with f3:
    selected_department_indices = st.multiselect("Індекс ССП", department_indices_options, key="dash_department_indices", placeholder="Усі підрозділи")
with f4:
    focus_mode = st.selectbox(
        "Фокус сторінки",
        ["Огляд", "Ризики", "Самостійні структурні підрозділи", "Стратегічні цілі", "Динаміка", "Таблиці"],
        key="dash_focus"
    )

with st.expander("Додаткові фільтри", expanded=False):
    a1, a2, a3 = st.columns(3)
    with a1:
        selected_goals = st.multiselect(
            "Стратегічна ціль",
            goal_options,
            format_func=lambda x: f"{x} — {short_label(strip_code_from_name(x, goal_name_map.get(x, '')), 70)}",
            key="dash_goals"
        )
    with a2:
        selected_tasks = st.multiselect(
            "Завдання",
            task_options,
            format_func=lambda x: f"{x} — {short_label(strip_code_from_name(x, task_name_map.get(x, '')), 70)}",
            key="dash_tasks"
        )
    with a3:
        selected_measures = st.multiselect(
            "Захід",
            measure_options,
            format_func=lambda x: f"{x} — {short_label(strip_code_from_name(x, measure_name_map.get(x, '')), 70)}",
            key="dash_measures"
        )

    b1, b2, b3 = st.columns(3)
    with b1:
        selected_product_types = st.multiselect("Тип продукту", product_type_options, key="dash_product_types")
    with b2:
        selected_deputies = st.multiselect("Заступник Міністра", deputy_options, key="dash_deputies")
    with b3:
        selected_statuses = st.multiselect("Статус виконання", status_options, key="dash_statuses")

    c1, c2 = st.columns([2, 1])
    with c1:
        selected_sources = st.multiselect("Джерело даних: національний рівень", source_options, key="dash_sources")
    with c2:
        presentation_mode = st.toggle("Presentation mode", value=False, key="dash_presentation_mode")

r1, r2 = st.columns([1, 5])
with r1:
    if st.button("Скинути фільтри", use_container_width=True):
        reset_filters()
        st.rerun()

selected_labels = []
selected_labels.append("роки: " + (", ".join(map(str, selected_years)) if selected_years else "усі"))
selected_labels.append("квартали: " + (", ".join(selected_quarters) if selected_quarters else "усі"))
selected_labels.append("ССП: " + (", ".join(selected_department_indices) if selected_department_indices else "усі"))
selected_labels.append("фокус: " + focus_mode)
st.markdown(
    '<div class="filter-chip-row">' + ''.join([f'<div class="filter-chip">{x}</div>' for x in selected_labels]) + '</div>',
    unsafe_allow_html=True
)


# ============================================================
# BUILD ACTIVE DATA
# ============================================================

years_for_calc = selected_years if selected_years else years_options
quarters_for_calc = selected_quarters if selected_quarters else quarters_options

active_raw = build_period_data(strat_df, requests_df, years_for_calc, quarters_for_calc)

if active_raw.empty:
    st.warning("Для обраного періоду активних заходів не знайдено.")
    st.stop()

active_filtered_period_rows = apply_dashboard_filters(
    active_raw,
    selected_department_indices,
    selected_goals,
    selected_tasks,
    selected_measures,
    selected_product_types,
    selected_deputies,
    selected_statuses,
    selected_sources
)

if active_filtered_period_rows.empty:
    st.warning("За обраними параметрами відбору даних не знайдено.")
    st.stop()

active = collapse_to_latest_measure_rows(active_filtered_period_rows)


# ============================================================
# METRICS AND AGGREGATIONS
# ============================================================

total_active = len(active)
submitted_count = calc_submitted(active)
coverage = calc_coverage(active)
completion = mean_completion(active)
deviation_current = deviation_for_period(completion)
risk_share = calc_risk_share(active)

assessed = assessment_subset(active)
critical_count = len(assessed[assessed["auto_risk"] == "Критичний ризик"])
medium_count = len(assessed[assessed["auto_risk"] == "Середній ризик"])
without_data = len(active[active["status"] == "Не подано"])
completed_count = len(active[active["status_display"] == "Виконано"])
partly_count = len(active[active["status_display"] == "Частково виконано"])
in_progress_count = len(active[active["status_display"] == "Виконується"])
not_done_count = len(active[active["status_display"] == "Не виконано"])
not_time_count = len(active[active["status_display"] == "Термін не настав"])
obsolete_count = len(active[active["status_display"] == "Втратив актуальність"])
approval_counts = calc_approval_counts(requests_df, active["code"].astype(str).tolist(), years_for_calc, quarters_for_calc)
approved_count = approval_counts.get("Погоджено", submitted_count)
on_review_count = approval_counts.get("На розгляді", 0)
not_counted_count = approval_counts.get("Не враховано", 0)

conclusion_title, conclusion_text, conclusion_badge = dashboard_conclusion(completion, risk_share, coverage)

dep_active = explode_departments(active)

status_counts = active.groupby("status_display").size().reset_index(name="Кількість")
risk_counts = active.groupby("auto_risk").size().reset_index(name="Кількість")
traffic_counts = active.groupby("traffic_light").size().reset_index(name="Кількість")

goal_progress = (
    active.groupby(["goal_code", "strategic_goal"])
    .agg(
        Активних_заходів=("code", "count"),
        Виконання=("performance_score", "mean"),
        Погоджено=("status", lambda x: (x != "Не подано").sum()),
        Ризикових=("auto_risk", lambda x: x.isin(["Критичний ризик", "Середній ризик"]).sum()),
        Критичних=("auto_risk", lambda x: (x == "Критичний ризик").sum()),
        Середній_ризик=("risk_score", "mean")
    )
    .reset_index()
)

goal_progress["Виконання"] = goal_progress["Виконання"].fillna(0).round(1)
goal_progress["Покриття_%"] = (goal_progress["Погоджено"] / goal_progress["Активних_заходів"] * 100).round(1)
goal_progress["Середній_ризик"] = goal_progress["Середній_ризик"].fillna(0).round(1)
goal_progress["Відхилення"] = (goal_progress["Виконання"] - 100).round(1)
goal_progress["Ціль"] = goal_progress.apply(lambda r: f"СЦ {r['goal_code']} — {short_label(strip_code_from_name(r['goal_code'], r['strategic_goal']), 72)}", axis=1)

dep_progress = (
    dep_active.groupby("ssp_department")
    .agg(
        Активних_заходів=("code", "count"),
        Виконання=("performance_score", "mean"),
        Погоджено=("status", lambda x: (x != "Не подано").sum()),
        Ризикових=("auto_risk", lambda x: x.isin(["Критичний ризик", "Середній ризик"]).sum()),
        Критичних=("auto_risk", lambda x: (x == "Критичний ризик").sum()),
        Середній_ризик=("risk_score", "mean")
    )
    .reset_index()
)

dep_progress["Виконання"] = dep_progress["Виконання"].fillna(0).round(1)
dep_progress["Покриття_%"] = (dep_progress["Погоджено"] / dep_progress["Активних_заходів"] * 100).round(1)
dep_progress["Середній_ризик"] = dep_progress["Середній_ризик"].fillna(0).round(1)
dep_progress["Підрозділ"] = dep_progress["ssp_department"].apply(lambda x: short_label(x, 44))

goal_failure = weighted_failure_group(active, ["goal_code", "strategic_goal"])
dep_failure = weighted_failure_group(dep_active, ["ssp_department"])


# ============================================================
# EXECUTIVE SUMMARY
# ============================================================

period_text = f"Період: {'/'.join(map(str, selected_years)) if selected_years else 'усі роки'} | {', '.join(selected_quarters) if selected_quarters else 'усі квартали'}"

st.markdown(
    f"""
<div class="panel">
    <div class="panel-title">Прогрес виконання: висновок системи</div>
    <div class="pill-row">
        <div class="pill {conclusion_badge}">{conclusion_title}</div>
        <div class="pill">{period_text}</div>
        <div class="pill">Активних заходів: {total_active}</div>
        <div class="pill">Відхилення за звітний період: {deviation_current} в.п.</div>
    </div>
    <div style="color:#475569;font-size:14px;line-height:1.55;margin-top:10px;">{conclusion_text}</div>
</div>
""",
    unsafe_allow_html=True
)

kpi_html = "".join([
    kpi_card("Заходів", total_active, "100.0%", "kpi-blue"),
    kpi_card("Виконано", completed_count, pct_value(completed_count, total_active), "kpi-green"),
    kpi_card("Погоджено", approved_count, pct_value(approved_count, total_active), "kpi-green"),
    kpi_card("На розгляді", on_review_count, pct_value(on_review_count, total_active), "kpi-yellow"),
    kpi_card("Не враховано", not_counted_count, pct_value(not_counted_count, total_active), "kpi-red"),
    kpi_card("Не виконано", not_done_count, pct_value(not_done_count, total_active), "kpi-red"),
    kpi_card("Втратили актуальність", obsolete_count, pct_value(obsolete_count, total_active), "kpi-gray"),
    kpi_card("Термін не настав", not_time_count, pct_value(not_time_count, total_active), "kpi-gray"),
    kpi_card("Частково виконано", partly_count, pct_value(partly_count, total_active), "kpi-yellow"),
    kpi_card("Виконується", in_progress_count, pct_value(in_progress_count, total_active), "kpi-blue"),
])
st.markdown(f'<div class="kpi-grid">{kpi_html}</div>', unsafe_allow_html=True)

insight_lines = []
insight_lines.append(f"⚠️ {without_data} активних заходів не мають поданого погодженого моніторингу.")
insight_lines.append(f"🔴 {critical_count} заходів мають критичний ризик недосягнення.")
if not goal_failure.empty:
    row = goal_failure.iloc[0]
    insight_lines.append(f"📉 Найбільша концентрація невиконаних заходів у СЦ {row['goal_code']} — {int(row['Невиконаних'])} із {int(row['Активних_заходів'])}; вага в обраному портфелі — {row['Вага_невиконання']}%.")
if not dep_failure.empty:
    row = dep_failure.iloc[0]
    insight_lines.append(f"🏢 Самостійний структурний підрозділ із найвищою концентрацією невиконання: {row['ssp_department']} — {int(row['Невиконаних'])} із {int(row['Активних_заходів'])}; вага в обраному портфелі — {row['Вага_невиконання']}%.")
insight_lines.append(f"📌 Відхилення за звітний період: {deviation_current} в.п. від планового рівня.")

st.markdown('<div class="panel"><div class="panel-title">Автоматичні інсайти</div>', unsafe_allow_html=True)
for line in insight_lines:
    st.markdown(line)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="panel"><div class="panel-title">Показники виконання стратегічного плану</div>', unsafe_allow_html=True)
g1, g2 = st.columns([1, 1])
with g1:
    gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=completion,
        number={"suffix": "%", "font": {"size": 54, "color": "#0f172a"}},
        title={"text": "Виконання СП", "font": {"size": 20}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#64748b"},
            "bar": {"color": "#0f172a", "thickness": 0.22},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 1,
            "bordercolor": "#cbd5e1",
            "steps": [
                {"range": [0, 30], "color": "#fee2e2"},
                {"range": [30, 70], "color": "#fef3c7"},
                {"range": [70, 100], "color": "#dcfce7"},
            ],
            "threshold": {"line": {"color": "#111827", "width": 4}, "thickness": 0.75, "value": completion},
        },
    ))
    gauge.update_layout(height=390, margin=dict(l=10, r=10, t=45, b=10), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(gauge, use_container_width=True)
with g2:
    st.markdown("**Лінійні індикатори стану**")
    st.markdown(f"Виконання СП: {completion}%")
    st.progress(min(max(completion / 100, 0), 1))
    st.markdown(f"Покриття моніторингом: {coverage}%")
    st.progress(min(max(coverage / 100, 0), 1))
    st.markdown(f"Відхилення за звітний період: {deviation_current} в.п.")
    st.progress(min(max((deviation_current + 100) / 100, 0), 1))
    auto_share = round((1 - calc_risk_share(active) / 100), 3) * 100 if total_active else 0
    st.markdown(f"Частка заходів без автоматично визначеного ризику: {auto_share:.1f}%")
    st.progress(min(max(auto_share / 100, 0), 1))
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# CHART TABS
# ============================================================

show_overview = focus_mode == "Огляд" or presentation_mode
show_risks = focus_mode in ["Огляд", "Ризики"] and not presentation_mode
show_departments = focus_mode in ["Огляд", "Самостійні структурні підрозділи"] and not presentation_mode
show_goals = focus_mode in ["Огляд", "Стратегічні цілі"] or presentation_mode
show_dynamics = focus_mode in ["Огляд", "Динаміка"] and not presentation_mode
show_tables = focus_mode == "Таблиці" and not presentation_mode

if show_overview or show_goals:
    st.markdown('<div class="panel"><div class="panel-title">Ключова картина виконання</div><div class="panel-subtitle">Менше графіків, але більше управлінського змісту: статуси, цілі та основні джерела відхилення.</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([0.9, 1.35])

    with c1:
        status_chart = active.copy()
        status_chart["Статус"] = status_chart["status"].apply(lambda x: clean(x) if clean(x) else "Не подано")
        status_counts_full = status_chart.groupby("Статус").size().reset_index(name="Кількість")
        status_counts_full["sort"] = status_counts_full["Статус"].apply(lambda x: status_rank.get(x, 999))
        status_counts_full = status_counts_full.sort_values(["sort", "Статус"]).drop(columns="sort")
        fig = px.bar(
            status_counts_full,
            x="Кількість",
            y="Статус",
            orientation="h",
            text="Кількість",
            color="Статус",
            color_discrete_map=status_color_map(),
            title="Розподіл заходів за статусом",
            labels={"Статус": "Статус", "Кількість": "Кількість"}
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(apply_plot_theme(fig, height=360), use_container_width=True)

    with c2:
        goal_for_chart = goal_progress.sort_values(["Відхилення", "Активних_заходів"], ascending=[True, False]).copy()
        fig = px.bar(
            goal_for_chart,
            x="Виконання",
            y="Ціль",
            orientation="h",
            text="Виконання",
            color="Відхилення",
            color_continuous_scale="RdYlGn",
            hover_data=["Активних_заходів", "Покриття_%", "Відхилення", "Ризикових", "Критичних"],
            title="Стратегічні цілі: виконання і відхилення",
            labels={"Виконання": "Виконання, %", "Ціль": "Стратегічна ціль", "Відхилення": "Відхилення, в.п."}
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_range=[0, 100])
        st.plotly_chart(apply_plot_theme(fig, height=420), use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

if show_risks:
    st.markdown('<div class="panel"><div class="panel-title">Автоматична оцінка ризиків</div><div class="panel-subtitle">Блок показує рівень ризику недосягнення та структуру ризиків за самостійними структурними підрозділами.</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([0.8, 1.2])

    with c1:
        risk_order = ["Критичний ризик", "Середній ризик", "Низький ризик", "Не оцінюється"]
        risk_counts["auto_risk"] = pd.Categorical(risk_counts["auto_risk"], categories=risk_order, ordered=True)
        risk_counts = risk_counts.sort_values("auto_risk")
        fig = px.bar(
            risk_counts,
            x="Кількість",
            y="auto_risk",
            orientation="h",
            text="Кількість",
            color="auto_risk",
            color_discrete_map=status_color_map(),
            title="Рівень ризику недосягнення",
            labels={"auto_risk": "Ризик"}
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(apply_plot_theme(fig, height=330), use_container_width=True)

    with c2:
        dep_risk = dep_progress.sort_values(["Критичних", "Ризикових", "Активних_заходів"], ascending=[False, False, False]).head(15)
        fig = px.scatter(
            dep_risk,
            x="Виконання",
            y="Середній_ризик",
            size="Активних_заходів",
            color="Критичних",
            hover_name="ssp_department",
            hover_data=["Покриття_%", "Ризикових", "Критичних", "Активних_заходів"],
            color_continuous_scale="Reds",
            title="Ризики за самостійними структурними підрозділами",
            labels={"Виконання": "Виконання, %", "Середній_ризик": "Risk score", "ssp_department": "Самостійний структурний підрозділ"}
        )
        fig.update_layout(xaxis_range=[0, 100], yaxis_range=[0, 100])
        st.plotly_chart(apply_plot_theme(fig, height=390), use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

if show_departments:
    st.markdown('<div class="panel"><div class="panel-title">Самостійні структурні підрозділи</div><div class="panel-subtitle">Рейтинг показує не тільки виконання, а й покриття погодженими даними та ризиковість.</div>', unsafe_allow_html=True)

    rank_df = dep_progress.sort_values(["Виконання", "Покриття_%", "Активних_заходів"], ascending=[False, False, False]).copy()
    rank_df["Місце"] = range(1, len(rank_df) + 1)
    rank_display = rank_df[["Місце", "ssp_department", "Виконання", "Покриття_%", "Ризикових", "Критичних", "Активних_заходів"]].rename(columns={
        "ssp_department": "Самостійний структурний підрозділ",
        "Покриття_%": "Покриття, %",
        "Активних_заходів": "Активних заходів"
    })
    st.dataframe(rank_display, use_container_width=True, hide_index=True, height=360)

    top_dep = rank_df.sort_values(["Ризикових", "Активних_заходів"], ascending=[False, False]).head(18)
    fig = px.bar(
        top_dep,
        x="Ризикових",
        y="Підрозділ",
        orientation="h",
        text="Ризикових",
        color="Виконання",
        color_continuous_scale="Blues",
        hover_data=["Активних_заходів", "Покриття_%", "Критичних", "Середній_ризик"],
        title="Підрозділи з найбільшою кількістю ризикових заходів",
        labels={"Підрозділ": "Підрозділ", "Ризикових": "Ризикові заходи"}
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(apply_plot_theme(fig, height=470), use_container_width=True)

    perf_dep = rank_df.sort_values("Виконання", ascending=False).copy()
    fig = px.bar(
        perf_dep,
        x="Підрозділ",
        y="Виконання",
        text="Виконання",
        title="Виконання за самостійними структурними підрозділами",
        labels={"Підрозділ": "Самостійний структурний підрозділ", "Виконання": "Виконання, %"}
    )
    fig.update_layout(xaxis_tickangle=-35, yaxis_range=[0, 100])
    st.plotly_chart(apply_plot_theme(fig, height=470), use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

if show_dynamics:
    st.markdown('<div class="panel"><div class="panel-title">Динаміка</div><div class="panel-subtitle">Динаміка очищена від зайвого шуму: показуються лише періоди, де є активні заходи після фільтрів.</div>', unsafe_allow_html=True)

    trend_rows = []
    for y in years_for_calc:
        for q in quarters_for_calc:
            temp_raw = build_period_data(strat_df, requests_df, [y], [q])
            temp = apply_dashboard_filters(
                temp_raw,
                selected_department_indices,
                selected_goals,
                selected_tasks,
                selected_measures,
                selected_product_types,
                selected_deputies,
                selected_statuses,
                selected_sources
            )
            if temp.empty:
                continue
            trend_rows.append({
                "Період": f"{y} {q}",
                "Виконання": mean_completion(temp),
                "Покриття погодженими даними": calc_coverage(temp),
                "Відхилення за звітний період": deviation_for_period(mean_completion(temp))
            })

    trend_df = pd.DataFrame(trend_rows)
    if not trend_df.empty:
        fig = px.line(
            trend_df,
            x="Період",
            y=["Виконання", "Покриття погодженими даними", "Відхилення за звітний період"],
            markers=True,
            title="Тренд виконання, покриття та відхилення",
            labels={"value": "Значення, %", "variable": "Показник"}
        )
        fig.update_yaxes(range=[-100, 100])
        st.plotly_chart(apply_plot_theme(fig, height=400), use_container_width=True)

        heat_source = []
        for y in years_for_calc:
            for q in quarters_for_calc:
                temp_raw = build_period_data(strat_df, requests_df, [y], [q])
                temp = apply_dashboard_filters(
                    temp_raw,
                    selected_department_indices,
                    selected_goals,
                    selected_tasks,
                    selected_measures,
                    selected_product_types,
                    selected_deputies,
                    selected_statuses,
                    selected_sources
                )
                if temp.empty:
                    continue
                temp_dep = explode_departments(temp)
                dep_heat = temp_dep.groupby("ssp_department").agg(Виконання=("performance_score", "mean"), Активних=("code", "count")).reset_index()
                for _, row in dep_heat.iterrows():
                    heat_source.append({
                        "Самостійний структурний підрозділ": row["ssp_department"],
                        "Період": f"{y} {q}",
                        "Виконання": round(row["Виконання"], 1) if pd.notna(row["Виконання"]) else 0,
                        "Активних": int(row["Активних"])
                    })

        heat_df = pd.DataFrame(heat_source)
        if not heat_df.empty:
            top_heat_deps = dep_progress.sort_values("Активних_заходів", ascending=False).head(18)["ssp_department"].tolist()
            heat_df = heat_df[heat_df["Самостійний структурний підрозділ"].isin(top_heat_deps)]
            fig = px.density_heatmap(
                heat_df,
                x="Період",
                y="Самостійний структурний підрозділ",
                z="Виконання",
                histfunc="avg",
                color_continuous_scale="Blues",
                title="Теплова карта виконання: топ підрозділів за кількістю активних заходів"
            )
            st.plotly_chart(apply_plot_theme(fig, height=520), use_container_width=True)
    else:
        st.info("Недостатньо даних для побудови динаміки.")

    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# PROBLEM MEASURES
# ============================================================

if not presentation_mode and focus_mode in ["Огляд", "Ризики", "Таблиці"]:
    st.markdown('<div class="panel"><div class="panel-title">Проблемні заходи</div><div class="panel-subtitle">Тут залишені тільки ті заходи, які реально потребують уваги: немає погоджених даних, низьке виконання або середній/критичний ризик.</div>', unsafe_allow_html=True)

    risk_table = active[
        (
            active["auto_risk"].isin(["Критичний ризик", "Середній ризик"])
            | (active["status"] == "Не подано")
            | (active["performance_score"].fillna(0) < 75)
        )
        & (active["included_in_assessment"] == True)
    ].copy()

    if risk_table.empty:
        st.success("Ризикових заходів за обраний період не виявлено.")
    else:
        risk_table["Захід"] = risk_table["name"].apply(lambda x: short_label(x, 130))
        risk_table = risk_table.rename(columns={
            "period_label": "Період",
            "code": "Код",
            "indicator": "Індикатор",
            "department": "Головний ССП",
            "status_display": "Статус виконання",
            "selected_target": "Планове значення",
            "numeric_value": "Фактичне значення",
            "auto_risk": "Рівень ризику",
            "risk_score": "Risk score",
            "risk_reason": "Причина ризику",
            "progress_text": "Опис прогресу"
        })
        st.dataframe(
            risk_table[["Період", "Код", "Захід", "Індикатор", "Головний ССП", "Статус виконання", "Планове значення", "Фактичне значення", "Рівень ризику", "Risk score", "Причина ризику", "Опис прогресу"]],
            use_container_width=True,
            hide_index=True,
            height=430
        )

    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# FULL TABLE
# ============================================================

if show_tables:
    st.markdown('<div class="panel"><div class="panel-title">Повна таблиця активних заходів</div><div class="panel-subtitle">Детальна таблиця для перевірки даних та експорту.</div>', unsafe_allow_html=True)

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

    table_cols = [
        "Період", "Код", "Захід", "Індикатор", "Одиниця виміру", "Тип продукту",
        "Головний ССП", "Джерело даних", "Початок", "Кінець", "Планове значення",
        "Фактичне значення", "Статус виконання", "Оцінка виконання, %", "Traffic light",
        "Ризик", "Risk score", "Причина ризику"
    ]
    st.dataframe(full[table_cols], use_container_width=True, hide_index=True, height=600)
    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# METHODOLOGY
# ============================================================

if not presentation_mode:
    with st.expander("Методологія розрахунку", expanded=False):
        st.markdown(
            """
            **Активні заходи** — заходи, період виконання яких охоплює обраний рік і квартал.

            **Погоджені дані** — дані із Supabase, де `approval_status = "Погоджено"`. Саме вони включаються до фактичної оцінки виконання.

            **Виконання СП** рахується як середня оцінка активних заходів:
            - якщо є числовий план і факт — використовується співвідношення факт / план;
            - якщо числове співвідношення неможливе — використовується статус;
            - «Виконано» = 100%;
            - «Частково виконано» = 75%;
            - «Виконується» = 50%;
            - «Не виконано», «Не подано», «Не розпочато», «Прострочено», «Потребує уваги» = 0%;
            - «Термін не настав» і «Втратив актуальність» не включаються до ризикової оцінки.

            **Risk score** визначається автоматично за відсутністю погоджених даних, відставанням факт/план, проблемним статусом і простроченням строку.
            """
        )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
<div class="footer">
    <strong>Розроблено департаментом стратегічного планування та макроекономічного прогнозування</strong><br>
    Версія DEMO 1.4 | 2026 | Внутрішня система моніторингу стратегічного плану
</div>
""",
    unsafe_allow_html=True
)
