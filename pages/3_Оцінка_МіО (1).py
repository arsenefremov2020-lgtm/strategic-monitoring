import re
import math
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Оцінка МіО", layout="wide")

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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', 'Helvetica Neue', 'Arial', sans-serif;
}

.stApp {
    background: #f0f4f9;
}

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

/* ── UA stripe ── */
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

.header-main { flex: 1 1 60%; min-width: 200px; }

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
    max-width: 700px;
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
    font-size: clamp(14px, 1.3vw, 17px);
    font-weight: 800;
    color: #0c1a3a;
    margin: 0 0 14px 0;
}

.section-subtitle {
    font-size: clamp(11px, 0.95vw, 13px);
    color: #64748b;
    margin: 0 0 12px 0;
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

.filter-title {
    font-size: clamp(14px, 1.3vw, 17px);
    font-weight: 800;
    color: #0c1a3a;
    margin-bottom: 12px;
}

/* ── Streamlit widget overrides ── */
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
    background-color: #d7eaff !important;
    border: 1px solid #8fb3df !important;
    border-radius: 10px !important;
    min-height: 40px !important;
}

div[data-testid="stSelectbox"] label,
div[data-testid="stMultiSelect"] label {
    font-weight: 750 !important;
    color: #1e293b !important;
}

/* ── KPI grid ── */
.kpi-grid {
    display: grid;
    gap: clamp(8px, 1.2vw, 14px);
    margin: 6px 0 4px 0;
}

.kpi-grid-4 { grid-template-columns: repeat(4, 1fr); }
.kpi-grid-5 { grid-template-columns: repeat(5, 1fr); }
.kpi-grid-6 { grid-template-columns: repeat(6, 1fr); }
.kpi-grid-8 { grid-template-columns: repeat(4, 1fr); }

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

.kpi-blue   { background: #eff6ff; border-color: #bfdbfe; }
.kpi-green  { background: #f0fdf4; border-color: #bbf7d0; }
.kpi-red    { background: #fef2f2; border-color: #fecaca; }
.kpi-yellow { background: #fffbeb; border-color: #fde68a; }
.kpi-gray   { background: #f8fafc; border-color: #e2e8f0; }
.kpi-teal   { background: #f0fdfa; border-color: #99f6e4; }
.kpi-indigo { background: #eef2ff; border-color: #c7d2fe; }

/* ── Integral score block ── */
.integral-block {
    background: linear-gradient(135deg, #0c1a3a 0%, #1e3a6e 100%);
    border-radius: 14px;
    padding: 24px 28px;
    color: white;
    text-align: center;
    box-shadow: 0 8px 24px rgba(0,91,187,0.25);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 200px;
}

.integral-label {
    font-size: clamp(11px, 1vw, 13px);
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
}

.integral-value {
    font-size: clamp(40px, 5vw, 64px);
    font-weight: 900;
    color: #ffffff;
    line-height: 1;
    margin-bottom: 8px;
}

.integral-level {
    font-size: clamp(12px, 1.1vw, 15px);
    font-weight: 700;
    padding: 5px 14px;
    border-radius: 20px;
    margin-top: 6px;
}

/* ── Goal row (like on screenshot) ── */
.goal-row {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    margin-bottom: 10px;
    overflow: hidden;
}

.goal-row-header {
    display: flex;
    align-items: center;
    padding: 12px 16px;
    gap: 12px;
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
}

.goal-code-badge {
    background: #005BBB;
    color: white;
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 800;
    white-space: nowrap;
}

.goal-name-text {
    font-size: clamp(12px, 1.1vw, 14px);
    font-weight: 700;
    color: #0c1a3a;
    flex: 1;
    line-height: 1.35;
}

.goal-score-text {
    font-size: clamp(14px, 1.3vw, 18px);
    font-weight: 900;
    white-space: nowrap;
}

.goal-score-green  { color: #16a34a; }
.goal-score-yellow { color: #d97706; }
.goal-score-red    { color: #dc2626; }

/* ── Progress bar ── */
.prog-bar-bg {
    background: #e2e8f0;
    border-radius: 99px;
    height: 8px;
    overflow: hidden;
    margin: 10px 16px;
}

.prog-bar-fill {
    height: 100%;
    border-radius: 99px;
    transition: width 0.4s;
}

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

.insight-item.warn   { border-left-color: #d97706; background: #fffbeb; }
.insight-item.danger { border-left-color: #dc2626; background: #fef2f2; }
.insight-item.success { border-left-color: #16a34a; background: #f0fdf4; }
.insight-item.info   { border-left-color: #0891b2; background: #ecfeff; }

/* ── Methodology box ── */
.methodology-box {
    background: #f8fafc;
    border: 1px solid #dde3ed;
    border-radius: 10px;
    padding: 16px 20px;
    font-size: clamp(11px, 0.95vw, 14px);
    color: #334155;
    line-height: 1.7;
}

.methodology-box ol {
    padding-left: 20px;
    margin: 10px 0 0 0;
}

.methodology-box li {
    margin-bottom: 6px;
}

/* ── Divider ── */
.vis-separator {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 22px 0;
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

.footer strong { color: #475569; }

@media (max-width: 900px) {
    .kpi-grid-4, .kpi-grid-5, .kpi-grid-6, .kpi-grid-8 {
        grid-template-columns: repeat(2, 1fr);
    }
    .header-card { flex-direction: column; }
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# HELPERS
# ============================================================

def raw_value(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def is_empty(value):
    text = raw_value(value).lower().replace(" ", "")
    return text in ["", "nan", "none", "н.д.", "нд", "-", "—"]


def parse_number(value):
    text = raw_value(value)
    if is_empty(text):
        return None
    text = text.replace("\u00a0", " ").replace("%", "").replace(",", ".")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in ["", ".", "-", "-."]:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def clamp(value, low=0.0, high=120.0):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return max(low, min(high, float(value)))


def is_yes_no_unit(unit):
    text = raw_value(unit).lower()
    return "так/ні" in text or ("так" in text and "ні" in text)


def is_positive_yes(value):
    text = raw_value(value).lower()
    return text in ["так", "yes", "y", "true", "1", "виконано"] or text.startswith("так")


def status_score_val(status):
    text = raw_value(status).lower()
    mapping = {
        "виконано": 100,
        "виконано частково": 60,
        "виконується": 50,
        "потребує уваги": 40,
        "прострочено": 25,
        "не розпочато": 0,
    }
    for key, val in mapping.items():
        if key in text:
            return val
    return None


def score_level(score):
    if score is None or (isinstance(score, float) and math.isnan(score)):
        return "Немає даних"
    if score >= 100:
        return "Виконано"
    if score >= 80:
        return "Високий прогрес"
    if score >= 50:
        return "Частковий прогрес"
    if score > 0:
        return "Критичне відставання"
    return "Не виконано"


def score_risk(level):
    if level in ["Виконано", "Високий прогрес"]:
        return "Низький"
    if level == "Частковий прогрес":
        return "Середній"
    return "Високий"


def level_color(score):
    if score is None:
        return "#94a3b8"
    if score >= 80:
        return "#16a34a"
    if score >= 50:
        return "#d97706"
    return "#dc2626"


def level_bg(score):
    if score is None:
        return "#f1f5f9"
    if score >= 80:
        return "#f0fdf4"
    if score >= 50:
        return "#fffbeb"
    return "#fef2f2"


def level_pill_class(score):
    if score is None:
        return "background:#e2e8f0;color:#475569;"
    if score >= 80:
        return "background:#dcfce7;color:#166534;"
    if score >= 50:
        return "background:#fef3c7;color:#92400e;"
    return "background:#fee2e2;color:#991b1b;"


def goal_score_class(score):
    if score is None:
        return "goal-score-red"
    if score >= 80:
        return "goal-score-green"
    if score >= 50:
        return "goal-score-yellow"
    return "goal-score-red"


# ============================================================
# DATA LOADING
# ============================================================

@st.cache_data
def load_strat_matrix():
    raw = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=None, engine="openpyxl")
    data = raw.iloc[7:].copy()

    def safe_col(idx):
        if idx < data.shape[1]:
            return data.iloc[:, idx]
        return pd.Series([""] * len(data), index=data.index)

    df = pd.DataFrame({
        "type_marker":     safe_col(1),
        "code":            safe_col(2),
        "name":            safe_col(3),
        "product_type":    safe_col(4),
        "indicator":       safe_col(5),
        "unit":            safe_col(6),
        "base_2021":       safe_col(7),
        "fact_2024":       safe_col(8),
        "fact_2025":       safe_col(9),
        "target_2026":     safe_col(10),
        "target_2027":     safe_col(11),
        "target_2028":     safe_col(12),
        "target_2028_end": safe_col(13),
        "target_2034":     safe_col(14),
        "department":      safe_col(17),
        "resp_co_1":       safe_col(18),
        "resp_co_2":       safe_col(19),
    })

    df = df.dropna(subset=["code"]).copy()
    df["code"] = df["code"].astype(str).str.strip()
    df["type_marker"] = df["type_marker"].astype(str).str.strip()

    cur_goal_code, cur_goal_name = "", ""
    cur_task_code, cur_task_name = "", ""
    obj_types, pg_codes, pg_names, pt_codes, pt_names = [], [], [], [], []

    for _, row in df.iterrows():
        marker = raw_value(row["type_marker"]).lower()
        code = raw_value(row["code"])
        name = raw_value(row["name"])
        dots = code.count(".")

        if "стратегічна ціль" in marker:
            obj_type = "goal"
            cur_goal_code, cur_goal_name = code, name
            cur_task_code, cur_task_name = "", ""
        elif "завдання" in marker:
            obj_type = "task"
            cur_task_code, cur_task_name = code, name
        elif "заход" in marker or dots >= 3:
            obj_type = "measure"
        elif cur_task_code:
            obj_type = "task_indicator"
        elif cur_goal_code:
            obj_type = "goal_indicator"
        else:
            obj_type = "other"

        obj_types.append(obj_type)
        pg_codes.append(cur_goal_code)
        pg_names.append(cur_goal_name)
        pt_codes.append(cur_task_code)
        pt_names.append(cur_task_name)

    df["object_type"] = obj_types
    df["parent_goal_code"] = pg_codes
    df["parent_goal_name"] = pg_names
    df["parent_task_code"] = pt_codes
    df["parent_task_name"] = pt_names
    return df


@st.cache_data(ttl=60)
def load_monitoring_requests():
    resp = supabase.table("monitoring_requests").select("*").execute()
    if not resp.data:
        return pd.DataFrame()
    return pd.DataFrame(resp.data)


# ============================================================
# SCORING LOGIC  (based on Excel МіО methodology)
# ============================================================

def filter_monitoring(monitoring_df, selected_year, selected_quarter):
    if monitoring_df.empty:
        return pd.DataFrame()
    df = monitoring_df.copy()
    required = ["year", "quarter", "approval_status", "strat_code",
                "status", "numeric_value", "progress_text", "risks",
                "department", "submitted_at"]
    for col in required:
        if col not in df.columns:
            df[col] = ""

    df = df[df["year"].astype(str).str.strip() == str(selected_year)].copy()
    if selected_quarter != "Усі квартали":
        q = selected_quarter.replace(" квартал", "").strip()
        df = df[df["quarter"].astype(str).str.strip() == q].copy()
    df = df[df["approval_status"].astype(str).str.strip() == "Погоджено"].copy()
    if "submitted_at" in df.columns:
        df["_dt"] = pd.to_datetime(df["submitted_at"], errors="coerce")
        df = df.sort_values("_dt")
    return df


def calculate_measure_score(row, monitoring_records, selected_year):
    """
    Score logic mirrors Excel model:
    - numeric indicator: fact / plan * 100
    - yes/no: 100 or 0
    - status fallback if no numeric
    - risks: -10 penalty
    """
    code = raw_value(row.get("code"))
    target = row.get(f"target_{selected_year}", "")
    target_num = parse_number(target)
    unit = row.get("unit", "")

    records = monitoring_records[
        monitoring_records["strat_code"].astype(str).str.strip() == code
    ].copy()

    empty_result = {
        "fact_value": None, "indicator_score": None, "status_score": None,
        "measure_score": 0.0, "level": "Не виконано",
        "risk_level": "Високий", "has_approved_data": False,
        "has_risks": False, "method_note": "Немає погоджених даних"
    }

    if records.empty:
        return empty_result

    last = records.iloc[-1]
    fact_raw = last.get("numeric_value", "")
    fact_num = parse_number(fact_raw)
    s_score = status_score_val(last.get("status", ""))
    has_risks = raw_value(last.get("risks", "")) != ""

    if is_yes_no_unit(unit):
        ind_score = 100.0 if (is_positive_yes(fact_raw) or
                              raw_value(last.get("status", "")).lower() == "виконано") else 0.0
        method = "Так/Ні: так = 100%, ні = 0%"
    elif fact_num is not None and target_num not in [None, 0]:
        ind_score = clamp((fact_num / target_num) * 100)
        method = "Факт / Планове значення × 100"
    elif fact_num is not None:
        ind_score = None
        method = "Є факт, немає числового плану; використано статус"
    elif s_score is not None:
        ind_score = None
        method = "Немає числового факту; використано статус виконання"
    else:
        ind_score = 0.0
        method = "Немає числового факту і статусу"

    if ind_score is not None and s_score is not None:
        final = ind_score * 0.7 + s_score * 0.3
    elif ind_score is not None:
        final = ind_score
    elif s_score is not None:
        final = float(s_score)
    else:
        final = 0.0

    if has_risks:
        final = max(0.0, final - 10.0)

    final = round(clamp(final), 1)
    level = score_level(final)

    return {
        "fact_value": fact_raw,
        "indicator_score": round(ind_score, 1) if ind_score is not None else None,
        "status_score": s_score,
        "measure_score": final,
        "level": level,
        "risk_level": score_risk(level),
        "has_approved_data": True,
        "has_risks": has_risks,
        "method_note": method,
    }


def build_evaluation_table(strat_df, monitoring_df, selected_year, selected_quarter, selected_department):
    measures = strat_df[strat_df["object_type"] == "measure"].copy()
    if selected_department and selected_department != "Усі":
        measures = measures[measures["department"].astype(str).str.strip() == selected_department].copy()
    plan_col = f"target_{selected_year}"
    measures["_active"] = measures[plan_col].apply(lambda v: not is_empty(v))
    measures = measures[measures["_active"]].copy()

    filtered_mon = filter_monitoring(monitoring_df, selected_year, selected_quarter)

    rows = []
    for _, row in measures.iterrows():
        score = calculate_measure_score(row, filtered_mon, selected_year)
        rows.append({
            "goal_code":        row.get("parent_goal_code", ""),
            "goal_name":        row.get("parent_goal_name", ""),
            "task_code":        row.get("parent_task_code", ""),
            "task_name":        row.get("parent_task_name", ""),
            "measure_code":     row.get("code", ""),
            "measure_name":     row.get("name", ""),
            "indicator":        row.get("indicator", ""),
            "unit":             row.get("unit", ""),
            "plan_value":       row.get(plan_col, ""),
            "fact_value":       score["fact_value"],
            "department":       row.get("department", ""),
            "indicator_score":  score["indicator_score"],
            "status_score":     score["status_score"],
            "measure_score":    score["measure_score"],
            "level":            score["level"],
            "risk_level":       score["risk_level"],
            "has_approved_data": score["has_approved_data"],
            "has_risks":        score["has_risks"],
            "method_note":      score["method_note"],
        })
    return pd.DataFrame(rows)


def aggregate_scores(evaluation_df):
    if evaluation_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    task_scores = (
        evaluation_df
        .groupby(["goal_code", "goal_name", "task_code", "task_name"], dropna=False)
        .agg(
            task_score=("measure_score", "mean"),
            measures_count=("measure_code", "count"),
            approved_count=("has_approved_data", "sum"),
            risk_measures=("has_risks", "sum"),
        )
        .reset_index()
    )
    task_scores["task_score"] = task_scores["task_score"].round(1)
    task_scores["level"] = task_scores["task_score"].apply(score_level)
    task_scores["risk_level"] = task_scores["level"].apply(score_risk)

    goal_scores = (
        task_scores
        .groupby(["goal_code", "goal_name"], dropna=False)
        .agg(
            goal_score=("task_score", "mean"),
            tasks_count=("task_code", "count"),
            measures_count=("measures_count", "sum"),
            approved_count=("approved_count", "sum"),
            risk_measures=("risk_measures", "sum"),
        )
        .reset_index()
    )
    goal_scores["goal_score"] = goal_scores["goal_score"].round(1)
    goal_scores["level"] = goal_scores["goal_score"].apply(score_level)
    goal_scores["risk_level"] = goal_scores["level"].apply(score_risk)
    return task_scores, goal_scores


def build_integral_score(goal_scores, task_scores, evaluation_df):
    """
    Weights mirror Excel Інт_Оцінка:
      Заходи: 0.20, Завдання: 0.30, Прогрес цілей: 0.50
    """
    if evaluation_df.empty:
        return 0.0
    w_measures = float(evaluation_df["measure_score"].mean()) * 0.20
    w_tasks = float(task_scores["task_score"].mean()) * 0.30 if not task_scores.empty else 0.0
    w_goals = float(goal_scores["goal_score"].mean()) * 0.50 if not goal_scores.empty else 0.0
    return round(w_measures + w_tasks + w_goals, 1)


# ============================================================
# HTML helpers
# ============================================================

def kpi_card(label, value, color="gray", pct_label=""):
    pct_html = f'<div class="kpi-pct">{pct_label}</div>' if pct_label else ""
    return (
        f'<div class="kpi-card kpi-{color}">'
        f'<div class="kpi-title">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{pct_html}'
        f'</div>'
    )


def progress_bar_html(pct, color="#005BBB"):
    w = min(100, max(0, pct))
    return (
        f'<div class="prog-bar-bg">'
        f'<div class="prog-bar-fill" style="width:{w}%;background:{color};"></div>'
        f'</div>'
    )


def insight(text, kind=""):
    cls = f"insight-item {kind}".strip()
    return f'<div class="{cls}">{text}</div>'


# ============================================================
# LOAD DATA
# ============================================================

strat_df = load_strat_matrix()
monitoring_df = load_monitoring_requests()

measures_all = strat_df[strat_df["object_type"] == "measure"].copy()
departments_list = sorted([
    d for d in measures_all["department"].dropna().astype(str).str.strip().unique()
    if d and d.lower() not in ["nan", "none", ""]
])

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
        <div class="header-title">Оцінка МіО — Моніторинг і оцінка стратегічних результатів</div>
        <div class="header-subtitle">
            Сторінка для розрахунку інтегральної оцінки виконання Стратегічного плану за логікою: захід → завдання → стратегічна ціль → інтегральна оцінка.
            У розрахунок включаються лише погоджені моніторингові дані. Методологія відповідає моделі МіО стратегічних цілей.
        </div>
    </div>
    <div class="header-pills">
        <div class="pill">📊 Оцінка МіО</div>
        <div class="pill">🗄 Excel + Supabase</div>
        <div class="pill">✅ Погоджені заявки</div>
        <div class="pill">🕐 {datetime.now().strftime("%d.%m.%Y %H:%M")}</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================
# FILTERS
# ============================================================

st.markdown("""
<div class="filter-panel">
    <div class="filter-title">⚙️ Параметри оцінки</div>
</div>
""", unsafe_allow_html=True)

fc1, fc2, fc3, fc4 = st.columns([1, 1, 1, 1.4])
with fc1:
    selected_year = st.selectbox("Рік оцінки", [2026, 2027, 2028], index=0)
with fc2:
    selected_quarter = st.selectbox(
        "Звітний період",
        ["Усі квартали", "I квартал", "II квартал", "III квартал", "IV квартал"]
    )
with fc3:
    selected_department = st.selectbox("Підрозділ", ["Усі"] + departments_list)
with fc4:
    selected_view = st.selectbox(
        "Режим перегляду",
        ["Загальний огляд", "Стратегічні цілі", "Завдання", "Заходи", "Методологія"]
    )

# ============================================================
# COMPUTE
# ============================================================

evaluation_df = build_evaluation_table(
    strat_df, monitoring_df, selected_year, selected_quarter, selected_department
)
task_scores, goal_scores = aggregate_scores(evaluation_df)
integral_score = build_integral_score(goal_scores, task_scores, evaluation_df)

active_measures    = len(evaluation_df)
approved_measures  = int(evaluation_df["has_approved_data"].sum()) if not evaluation_df.empty else 0
without_data       = active_measures - approved_measures
risk_measures_cnt  = int(evaluation_df["has_risks"].sum()) if not evaluation_df.empty else 0
avg_measure_score  = round(float(evaluation_df["measure_score"].mean()), 1) if not evaluation_df.empty else 0.0
avg_task_score     = round(float(task_scores["task_score"].mean()), 1) if not task_scores.empty else 0.0
avg_goal_score     = round(float(goal_scores["goal_score"].mean()), 1) if not goal_scores.empty else 0.0
total_goals        = len(goal_scores)
total_tasks        = len(task_scores)

# ============================================================
# TOP KPI ROW
# ============================================================

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">Зведені показники оцінки</div>', unsafe_allow_html=True)

left_col, right_col = st.columns([1, 2.5])

with left_col:
    # Integral gauge
    gauge_color = "#16a34a" if integral_score >= 80 else "#d97706" if integral_score >= 50 else "#dc2626"
    level_text = score_level(integral_score)
    pill_style = level_pill_class(integral_score)
    st.markdown(f"""
    <div class="integral-block">
        <div class="integral-label">ІНТЕГРАЛЬНА ОЦІНКА</div>
        <div class="integral-value" style="color:{gauge_color};">{integral_score}%</div>
        <div class="integral-level" style="{pill_style}">{level_text}</div>
        <div style="font-size:11px;color:#64748b;margin-top:10px;">
            за {selected_year} рік · {selected_quarter}
        </div>
    </div>
    """, unsafe_allow_html=True)

with right_col:
    kpis_top = "".join([
        kpi_card("Оцінка заходів (вага 20%)", f"{avg_measure_score}%", "blue"),
        kpi_card("Оцінка завдань (вага 30%)", f"{avg_task_score}%", "indigo"),
        kpi_card("Оцінка цілей (вага 50%)", f"{avg_goal_score}%", "teal"),
    ])
    kpis_bot = "".join([
        kpi_card("Активних заходів", active_measures, "gray"),
        kpi_card("Погоджених подань", approved_measures, "green"),
        kpi_card("Без даних", without_data, "red"),
        kpi_card("Із ризиками", risk_measures_cnt, "yellow"),
        kpi_card("Стратегічних цілей", total_goals, "gray"),
        kpi_card("Завдань", total_tasks, "gray"),
    ])
    st.markdown(
        f'<div class="kpi-grid kpi-grid-4" style="grid-template-columns:repeat(3,1fr);margin-bottom:10px;">{kpis_top}</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        f'<div class="kpi-grid kpi-grid-6">{kpis_bot}</div>',
        unsafe_allow_html=True
    )

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# ANALYTICAL NOTE
# ============================================================

if not evaluation_df.empty:
    notes_html = ""
    best_goals = goal_scores.sort_values("goal_score", ascending=False).head(3) if not goal_scores.empty else pd.DataFrame()
    weak_goals = goal_scores.sort_values("goal_score", ascending=True).head(3) if not goal_scores.empty else pd.DataFrame()
    problem_cnt = len(evaluation_df[evaluation_df["measure_score"] < 50])

    notes_html += insight(
        f"Інтегральна оцінка виконання за {selected_year} рік ({selected_quarter}) становить <strong>{integral_score}%</strong>. "
        f"Охоплено <strong>{active_measures}</strong> активних заходів, з яких <strong>{approved_measures}</strong> "
        f"мають погоджені моніторингові дані, а <strong>{without_data}</strong> залишаються без погодженого подання.",
        "info"
    )
    if not best_goals.empty:
        best = "; ".join([f"{r.goal_code} — {r.goal_score}%" for _, r in best_goals.iterrows()])
        notes_html += insight(f"Найкращу динаміку демонструють стратегічні цілі: <strong>{best}</strong>.", "success")
    if not weak_goals.empty:
        weak_vals = [r.goal_score for _, r in weak_goals.iterrows()]
        if weak_vals and min(weak_vals) < 80:
            weak = "; ".join([f"{r.goal_code} — {r.goal_score}%" for _, r in weak_goals.iterrows()])
            notes_html += insight(f"Найбільшої управлінської уваги потребують цілі: <strong>{weak}</strong>.", "warn")
    if risk_measures_cnt > 0:
        notes_html += insight(
            f"У <strong>{risk_measures_cnt}</strong> заходах зазначено ризики — застосовано понижувальну поправку -10 п.п. до оцінки.",
            "danger"
        )
    if problem_cnt > 0:
        notes_html += insight(
            f"Заходів із критичним відставанням або відсутністю погоджених даних: <strong>{problem_cnt}</strong>. "
            "Рекомендується уточнити причини відхилення, строки та відповідальних виконавців.", "warn"
        )

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Автоматична аналітична довідка</div>', unsafe_allow_html=True)
    st.markdown(notes_html, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<hr class="vis-separator">', unsafe_allow_html=True)

# ============================================================
# VIEWS
# ============================================================

if selected_view == "Методологія":
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Методологія розрахунку оцінки МіО</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="methodology-box">
    <strong>Логіка розрахунку відповідає моделі МіО стратегічних цілей (Excel-файл):</strong>
    <ol>
        <li>У розрахунок включаються активні заходи, які мають планове значення на обраний рік.</li>
        <li>Для кожного заходу береться останнє погоджене подання за обраний рік і квартал.</li>
        <li><strong>Числовий індикатор:</strong> оцінка = Факт / Планове значення × 100. Результат обмежується діапазоном 0–120%.</li>
        <li><strong>Індикатор «Так/Ні»:</strong> «Так» = 100%, «Ні» = 0%.</li>
        <li><strong>Відсутній числовий факт:</strong> використовується статус виконання: Виконано = 100%, Виконано частково = 60%, Виконується = 50%, Потребує уваги = 40%, Прострочено = 25%, Не розпочато = 0%.</li>
        <li><strong>Комбінація:</strong> якщо є і числовий факт, і статус — оцінка = числова оцінка × 0.7 + статусна × 0.3.</li>
        <li><strong>Наявність ризиків:</strong> оцінка заходу зменшується на 10 п.п.</li>
        <li><strong>Оцінка завдання</strong> = середнє значення оцінок його заходів.</li>
        <li><strong>Оцінка стратегічної цілі</strong> = середнє значення оцінок її завдань.</li>
        <li><strong>Інтегральна оцінка</strong> = Оцінка заходів × 0.20 + Оцінка завдань × 0.30 + Оцінка цілей × 0.50</li>
    </ol>
    <br>
    <strong>Шкала рівнів виконання:</strong><br>
    ≥ 100% — <span style="color:#16a34a;font-weight:700;">Виконано</span> &nbsp;|&nbsp;
    80–99% — <span style="color:#16a34a;font-weight:700;">Високий прогрес</span> &nbsp;|&nbsp;
    50–79% — <span style="color:#d97706;font-weight:700;">Частковий прогрес</span> &nbsp;|&nbsp;
    1–49% — <span style="color:#dc2626;font-weight:700;">Критичне відставання</span> &nbsp;|&nbsp;
    0% — <span style="color:#dc2626;font-weight:700;">Не виконано</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


elif selected_view == "Загальний огляд":
    # ── Charts row ──
    ch1, ch2 = st.columns([1.4, 1])

    with ch1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Оцінка виконання за стратегічними цілями</div>', unsafe_allow_html=True)
        if not goal_scores.empty:
            chart_df = goal_scores.sort_values("goal_score", ascending=True).copy()
            chart_df["Ціль"] = chart_df["goal_code"].astype(str) + ". " + chart_df["goal_name"].astype(str).str.slice(0, 55)
            colors = [level_color(s) for s in chart_df["goal_score"]]
            fig = go.Figure(go.Bar(
                x=chart_df["goal_score"],
                y=chart_df["Ціль"],
                orientation="h",
                marker_color=colors,
                text=[f"{v}%" for v in chart_df["goal_score"]],
                textposition="outside",
            ))
            fig.add_vline(x=100, line_dash="dot", line_color="#64748b", line_width=1)
            fig.update_layout(
                height=max(380, len(chart_df) * 52),
                xaxis_range=[0, 125],
                xaxis_title="Оцінка, %",
                yaxis_title="",
                plot_bgcolor="white",
                paper_bgcolor="white",
                margin=dict(l=10, r=40, t=10, b=30),
                font=dict(size=12),
                xaxis=dict(gridcolor="#f1f5f9"),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Немає даних для графіка.")
        st.markdown('</div>', unsafe_allow_html=True)

    with ch2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Структура заходів за рівнем виконання</div>', unsafe_allow_html=True)
        if not evaluation_df.empty:
            level_counts = evaluation_df["level"].value_counts().reset_index()
            level_counts.columns = ["Рівень", "Кількість"]
            color_map = {
                "Виконано": "#16a34a",
                "Високий прогрес": "#4ade80",
                "Частковий прогрес": "#d97706",
                "Критичне відставання": "#f87171",
                "Не виконано": "#dc2626",
                "Немає даних": "#94a3b8",
            }
            fig = px.pie(
                level_counts,
                names="Рівень",
                values="Кількість",
                color="Рівень",
                color_discrete_map=color_map,
                hole=0.48,
            )
            fig.update_layout(
                height=320,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="white",
                legend=dict(font=dict(size=11)),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Немає даних.")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Radar + bar row ──
    ch3, ch4 = st.columns(2)

    with ch3:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Радарна діаграма стратегічних цілей</div>', unsafe_allow_html=True)
        if not goal_scores.empty and len(goal_scores) >= 3:
            radar_df = goal_scores.sort_values("goal_code").copy()
            cats = (radar_df["goal_code"].astype(str) + ". " + radar_df["goal_name"].astype(str).str.slice(0, 30)).tolist()
            vals = radar_df["goal_score"].tolist()
            vals_closed = vals + [vals[0]]
            cats_closed = cats + [cats[0]]
            fig = go.Figure(go.Scatterpolar(
                r=vals_closed,
                theta=cats_closed,
                fill="toself",
                fillcolor="rgba(0,91,187,0.12)",
                line=dict(color="#005BBB", width=2),
                name=str(selected_year),
            ))
            fig.add_trace(go.Scatterpolar(
                r=[100] * len(cats_closed),
                theta=cats_closed,
                mode="lines",
                line=dict(color="#e2e8f0", width=1.5, dash="dot"),
                name="100% (план)",
                showlegend=True,
            ))
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 120], tickfont=dict(size=9)),
                    angularaxis=dict(tickfont=dict(size=9)),
                ),
                height=340,
                paper_bgcolor="white",
                margin=dict(l=20, r=20, t=20, b=20),
                legend=dict(font=dict(size=10)),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Потрібно мінімум 3 цілі для радарної діаграми.")
        st.markdown('</div>', unsafe_allow_html=True)

    with ch4:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Розподіл ризиків за цілями</div>', unsafe_allow_html=True)
        if not goal_scores.empty:
            risk_df = goal_scores[["goal_code", "risk_measures"]].copy()
            risk_df = risk_df.sort_values("risk_measures", ascending=False)
            fig = px.bar(
                risk_df,
                x="goal_code",
                y="risk_measures",
                text="risk_measures",
                color="risk_measures",
                color_continuous_scale=["#bbf7d0", "#fde68a", "#fecaca"],
                labels={"goal_code": "Стратегічна ціль", "risk_measures": "Кількість заходів із ризиками"},
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                height=320,
                paper_bgcolor="white",
                plot_bgcolor="white",
                coloraxis_showscale=False,
                xaxis=dict(gridcolor="#f1f5f9"),
                yaxis=dict(gridcolor="#f1f5f9"),
                margin=dict(l=10, r=10, t=10, b=30),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Немає даних.")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Goal rows table-like view ──
    if not goal_scores.empty:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="section-title">Виконання стратегічного плану — {selected_year} рік</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle">Оцінка по кожній стратегічній цілі. 100% — орієнтир плану.</div>', unsafe_allow_html=True)

        for _, g in goal_scores.sort_values("goal_code").iterrows():
            score_v = g["goal_score"]
            bar_color = level_color(score_v)
            score_cls = goal_score_class(score_v)
            g_name = raw_value(g["goal_name"])[:80]
            tasks_c = int(g["tasks_count"])
            meas_c = int(g["measures_count"])
            appr_c = int(g["approved_count"])
            risk_c = int(g["risk_measures"])

            st.markdown(f"""
            <div class="goal-row">
                <div class="goal-row-header">
                    <span class="goal-code-badge">СЦ {raw_value(g['goal_code'])}</span>
                    <span class="goal-name-text">{g_name}</span>
                    <span class="goal-score-text {score_cls}">{score_v}%</span>
                </div>
                {progress_bar_html(score_v, bar_color)}
                <div style="display:flex;gap:20px;padding:6px 16px 10px;font-size:12px;color:#64748b;">
                    <span>📋 Завдань: <strong>{tasks_c}</strong></span>
                    <span>📌 Заходів: <strong>{meas_c}</strong></span>
                    <span>✅ Погоджено: <strong>{appr_c}</strong></span>
                    <span>⚠️ З ризиками: <strong style="color:#dc2626;">{risk_c}</strong></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)


elif selected_view == "Стратегічні цілі":
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Оцінка стратегічних цілей</div>', unsafe_allow_html=True)
    if goal_scores.empty:
        st.info("Дані відсутні.")
    else:
        show = goal_scores.rename(columns={
            "goal_code": "Код СЦ",
            "goal_name": "Стратегічна ціль",
            "goal_score": "Оцінка, %",
            "tasks_count": "Завдань",
            "measures_count": "Заходів",
            "approved_count": "Погоджених подань",
            "risk_measures": "Заходів із ризиками",
            "level": "Рівень виконання",
            "risk_level": "Рівень ризику",
        })
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Завантажити CSV",
            data=show.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"goal_scores_{selected_year}.csv",
            mime="text/csv"
        )

        # Bar
        chart_df = goal_scores.sort_values("goal_score", ascending=True).copy()
        chart_df["Ціль"] = chart_df["goal_code"].astype(str) + ". " + chart_df["goal_name"].astype(str).str.slice(0, 55)
        colors = [level_color(s) for s in chart_df["goal_score"]]
        fig = go.Figure(go.Bar(
            x=chart_df["goal_score"],
            y=chart_df["Ціль"],
            orientation="h",
            marker_color=colors,
            text=[f"{v}%" for v in chart_df["goal_score"]],
            textposition="outside",
        ))
        fig.add_vline(x=100, line_dash="dot", line_color="#64748b", line_width=1)
        fig.update_layout(
            height=max(380, len(chart_df) * 52),
            xaxis_range=[0, 125],
            plot_bgcolor="white",
            paper_bgcolor="white",
            margin=dict(l=10, r=50, t=10, b=30),
            xaxis=dict(gridcolor="#f1f5f9"),
        )
        st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)


elif selected_view == "Завдання":
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Оцінка завдань</div>', unsafe_allow_html=True)
    if task_scores.empty:
        st.info("Дані відсутні.")
    else:
        show = task_scores.rename(columns={
            "goal_code": "Код СЦ",
            "goal_name": "Стратегічна ціль",
            "task_code": "Код завдання",
            "task_name": "Завдання",
            "task_score": "Оцінка, %",
            "measures_count": "Заходів",
            "approved_count": "Погоджених подань",
            "risk_measures": "Заходів із ризиками",
            "level": "Рівень виконання",
            "risk_level": "Рівень ризику",
        })
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Завантажити CSV",
            data=show.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"task_scores_{selected_year}.csv",
            mime="text/csv"
        )

        # horizontal bar for tasks per goal (select goal)
        if not goal_scores.empty:
            goal_sel = st.selectbox(
                "Деталізація за стратегічною ціллю",
                ["— усі —"] + goal_scores["goal_code"].tolist()
            )
            task_chart = task_scores.copy()
            if goal_sel != "— усі —":
                task_chart = task_chart[task_chart["goal_code"] == goal_sel]
            if not task_chart.empty:
                task_chart["Завдання"] = task_chart["task_code"].astype(str) + ". " + task_chart["task_name"].astype(str).str.slice(0, 60)
                colors = [level_color(s) for s in task_chart["task_score"]]
                fig = go.Figure(go.Bar(
                    x=task_chart["task_score"],
                    y=task_chart["Завдання"],
                    orientation="h",
                    marker_color=colors,
                    text=[f"{v}%" for v in task_chart["task_score"]],
                    textposition="outside",
                ))
                fig.add_vline(x=100, line_dash="dot", line_color="#64748b", line_width=1)
                fig.update_layout(
                    height=max(320, len(task_chart) * 46),
                    xaxis_range=[0, 125],
                    plot_bgcolor="white",
                    paper_bgcolor="white",
                    margin=dict(l=10, r=50, t=10, b=30),
                    xaxis=dict(gridcolor="#f1f5f9"),
                )
                st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)


else:  # Заходи
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Оцінка заходів</div>', unsafe_allow_html=True)
    if evaluation_df.empty:
        st.info("Дані відсутні.")
    else:
        search = st.text_input("🔍 Пошук у заходах", "", placeholder="Код, назва, індикатор, підрозділ...")
        show_df = evaluation_df.copy()
        if search.strip():
            sq = search.strip().lower()
            show_df = show_df[
                show_df["measure_code"].astype(str).str.lower().str.contains(sq, na=False)
                | show_df["measure_name"].astype(str).str.lower().str.contains(sq, na=False)
                | show_df["indicator"].astype(str).str.lower().str.contains(sq, na=False)
                | show_df["department"].astype(str).str.lower().str.contains(sq, na=False)
            ].copy()

        show = show_df.rename(columns={
            "goal_code": "Код СЦ",
            "goal_name": "Стратегічна ціль",
            "task_code": "Код завдання",
            "task_name": "Завдання",
            "measure_code": "Код заходу",
            "measure_name": "Захід",
            "indicator": "Індикатор",
            "unit": "Одиниця виміру",
            "plan_value": "Планове значення",
            "fact_value": "Фактичне значення",
            "department": "Підрозділ",
            "indicator_score": "Оцінка індикатора, %",
            "status_score": "Оцінка статусу, %",
            "measure_score": "Оцінка заходу, %",
            "level": "Рівень виконання",
            "risk_level": "Рівень ризику",
            "has_approved_data": "Є погоджені дані",
            "has_risks": "Є ризики",
            "method_note": "Метод розрахунку",
        })
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Завантажити CSV",
            data=show.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"measure_scores_{selected_year}.csv",
            mime="text/csv"
        )

        # scatter: заходи (score vs measure_code)
        if len(show_df) > 0:
            fig = px.scatter(
                show_df,
                x="measure_code",
                y="measure_score",
                color="level",
                hover_data=["measure_name", "indicator", "plan_value", "fact_value", "department"],
                color_discrete_map={
                    "Виконано": "#16a34a",
                    "Високий прогрес": "#4ade80",
                    "Частковий прогрес": "#d97706",
                    "Критичне відставання": "#f87171",
                    "Не виконано": "#dc2626",
                    "Немає даних": "#94a3b8",
                },
                labels={"measure_score": "Оцінка, %", "measure_code": "Код заходу"},
                title=""
            )
            fig.add_hline(y=100, line_dash="dot", line_color="#64748b", line_width=1)
            fig.add_hline(y=80, line_dash="dot", line_color="#d97706", line_width=1, opacity=0.5)
            fig.add_hline(y=50, line_dash="dot", line_color="#dc2626", line_width=1, opacity=0.5)
            fig.update_layout(
                height=360,
                plot_bgcolor="white",
                paper_bgcolor="white",
                margin=dict(l=10, r=10, t=10, b=40),
                xaxis=dict(gridcolor="#f1f5f9", tickangle=45),
                yaxis=dict(gridcolor="#f1f5f9", range=[0, 125]),
            )
            st.plotly_chart(fig, use_container_width=True)
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
