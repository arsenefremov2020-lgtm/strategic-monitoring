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
.stApp {
    background:
        radial-gradient(circle at top right, rgba(37,99,235,0.08), transparent 28%),
        radial-gradient(circle at bottom left, rgba(22,163,74,0.07), transparent 30%),
        linear-gradient(180deg, #f6f8fb 0%, #eef2f7 100%);
}

.stApp::before {
    content: "";
    position: fixed;
    top: -160px;
    right: -120px;
    width: 460px;
    height: 460px;
    border-radius: 50%;
    background: rgba(37, 99, 235, 0.045);
    z-index: 0;
}

.stApp::after {
    content: "";
    position: fixed;
    bottom: -180px;
    left: -120px;
    width: 390px;
    height: 390px;
    border-radius: 50%;
    background: rgba(22, 163, 74, 0.045);
    z-index: 0;
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

.header-box {
    background: rgba(255,255,255,0.94);
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 24px 28px;
    margin-bottom: 18px;
    box-shadow: 0 8px 24px rgba(15,23,42,0.06);
}

.header-title {
    font-size: 32px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 8px;
}

.header-subtitle {
    font-size: 15px;
    color: #475569;
    line-height: 1.55;
}

.status-pill-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 14px;
}

.status-pill {
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 999px;
    padding: 8px 12px;
    font-size: 13px;
    color: #334155;
}

.card {
    background: rgba(255,255,255,0.94);
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 20px 22px;
    margin: 18px 0;
    box-shadow: 0 6px 18px rgba(15,23,42,0.045);
}

.card-title {
    font-size: 20px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 8px;
}

.card-subtitle {
    color: #64748b;
    font-size: 14px;
    margin-bottom: 12px;
}

.filter-card {
    background: rgba(255,255,255,0.96);
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 20px 22px;
    margin: 18px 0;
    box-shadow: 0 6px 18px rgba(15,23,42,0.045);
}

.alert-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 14px;
    margin: 14px 0;
}

.alert-card {
    border-radius: 14px;
    padding: 16px;
    border: 1px solid #d8dee9;
    background: white;
}

.alert-title {
    font-size: 13px;
    color: #64748b;
    font-weight: 800;
    min-height: 34px;
}

.alert-value {
    font-size: 28px;
    color: #0f172a;
    font-weight: 950;
    margin-top: 4px;
}

.alert-red {
    background: #fee2e2;
    border-color: #fecaca;
}

.alert-yellow {
    background: #fef9c3;
    border-color: #fde68a;
}

.alert-green {
    background: #dcfce7;
    border-color: #bbf7d0;
}

.alert-blue {
    background: #dbeafe;
    border-color: #bfdbfe;
}

.alert-neutral {
    background: #f8fafc;
    border-color: #d8dee9;
}

.badge-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 10px 0 16px 0;
}

.badge {
    background: #eef6ff;
    border: 1px solid #bfdbfe;
    color: #1d4ed8;
    border-radius: 999px;
    padding: 7px 11px;
    font-size: 13px;
    font-weight: 700;
}

.risk-high {
    background: #fee2e2;
    border: 1px solid #fecaca;
    color: #991b1b;
}

.risk-medium {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    color: #9a3412;
}

.risk-low {
    background: #dcfce7;
    border: 1px solid #bbf7d0;
    color: #166534;
}

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.88);
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background-color: #d7eaff !important;
    border: 1px solid #8fb3df !important;
    border-radius: 10px !important;
    min-height: 42px !important;
}

div[data-testid="stMultiSelect"] label,
div[data-testid="stSelectbox"] label {
    font-weight: 800 !important;
    color: #1e293b !important;
}

.methodology-box {
    background: #ffffff;
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 18px 20px;
    color: #334155;
    font-size: 14px;
    line-height: 1.6;
    margin-top: 20px;
}

.footer {
    text-align: center;
    color: #64748b;
    font-size: 13px;
    margin-top: 50px;
    padding: 22px 0 12px 0;
    border-top: 1px solid #d8dee9;
}

@media (max-width: 1100px) {
    .alert-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
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
    mapping = {
        "I": 1,
        "II": 2,
        "III": 3,
        "IV": 4,
        "1": 1,
        "2": 2,
        "3": 3,
        "4": 4,
    }
    return mapping.get(q, 1)


def quarter_to_roman(q):
    q = str(q).strip()
    mapping = {
        "1": "I",
        "2": "II",
        "3": "III",
        "4": "IV",
        "I": "I",
        "II": "II",
        "III": "III",
        "IV": "IV",
    }
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


def gauge_chart(value, title):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": "%"},
        title={"text": title},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#1d4ed8"},
            "steps": [
                {"range": [0, 35], "color": "#fee2e2"},
                {"range": [35, 70], "color": "#fef3c7"},
                {"range": [70, 100], "color": "#dcfce7"},
            ],
            "threshold": {
                "line": {"color": "#111827", "width": 4},
                "thickness": 0.75,
                "value": value
            }
        }
    ))

    fig.update_layout(height=350, margin=dict(l=30, r=30, t=60, b=20))
    return fig


def deviation_for_period(completion):
    return round(completion - 100, 1)


def forecast_to_q4(current_completion, selected_quarter):
    qn = quarter_to_number(selected_quarter)
    if qn == 0:
        return current_completion

    forecast = current_completion / qn * 4
    return round(min(forecast, 100), 1)


def render_status_cards(items):
    rows = [items[:5], items[5:]]

    for row in rows:
        cols = st.columns(5)

        for col, item in zip(cols, row):
            title = item["title"]
            count = item["count"]
            percent = item["percent"]
            color_class = item["color"]

            with col:
                st.markdown(
                    f"""
                    <div class="alert-card {color_class}">
                        <div class="alert-title">{title}</div>
                        <div class="alert-value">{count}</div>
                        <div style="font-size:15px;font-weight:850;color:#475569;margin-top:6px;">
                            {percent}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )


def reset_filters():
    keys = [
        "dash_years",
        "dash_quarters",
        "dash_department_indices",
        "dash_goals",
        "dash_tasks",
        "dash_measures",
        "dash_product_types",
        "dash_deputies",
        "dash_statuses",
        "dash_financing",
        "dash_sources",
        "dash_view_mode",
        "dash_presentation_mode"
    ]
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]


# ============================================================
# CORE PREPARE FUNCTION — збережена логіка старої сторінки
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
        (
            measures["start_num"].isna()
            |
            (measures["start_num"] <= selected_period_num)
        )
        &
        (
            measures["end_num"].isna()
            |
            (measures["end_num"] >= selected_period_num)
        )
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

    approved_requests = requests_df[
        requests_df["approval_status"].astype(str) == "Погоджено"
    ].copy()

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
        period_requests[
            ["strat_code", "status", "numeric_value", "risks", "progress_text"]
        ],
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
        lambda r: plan_fact_percent(r["numeric_value"], r["selected_target"]),
        axis=1
    )

    active["is_quantitative_pf"] = active.apply(is_quantitative_plan_fact, axis=1)

    active["performance_score"] = active.apply(
        lambda r: r["plan_fact_percent"]
        if pd.notna(r["plan_fact_percent"])
        else r["status_score"],
        axis=1
    )

    active["included_in_assessment"] = ~active["status_display"].isin([
        "Термін не настав",
        "Втратив актуальність"
    ])

    risk_results = active.apply(
        lambda r: risk_score_calc(r, selected_q_num, selected_period_num),
        axis=1
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


def apply_dashboard_filters(
    active,
    department_indices,
    goals,
    tasks,
    measures,
    product_types,
    deputies,
    statuses,
    sources
):
    data = active.copy()

    if department_indices:
        data = data[
            data.apply(lambda row: department_matches_indices(row, department_indices), axis=1)
        ]

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


# ============================================================
# HEADER
# ============================================================

st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)

st.markdown("""
<div class="ministry-label">
🇺🇦 Міністерство економіки, довкілля та сільського господарства України
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="header-box">
    <div class="header-title">Аналітичний дашборд результативності стратегічного плану</div>
    <div class="header-subtitle">
        Аналітична панель забезпечує комплексне представлення результатів виконання Стратегічного плану.
        Інфографіка та моніторингові звіти формуються за результатами проведення оцінки на основі
        моніторингу й оцінювання стратегічних результатів як у цілому, так і в розрізі кожного
        самостійного структурного підрозділу окремо.
    </div>
    <div class="status-pill-wrap">
        <div class="status-pill">● Сторінка: Dashboard</div>
        <div class="status-pill">● Джерело: Excel + Supabase</div>
        <div class="status-pill">● Факт: погоджені заявки</div>
        <div class="status-pill">● Оновлено: {datetime.now().strftime("%d.%m.%Y %H:%M")}</div>
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
                measures_all[
                    ["department", "department_co_1", "department_co_2"]
                ].fillna("").astype(str).agg(" | ".join, axis=1).tolist()
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
    "Виконано",
    "Частково виконано",
    "Не виконано",
    "Термін не настав",
    "Втратив актуальність",
    "Виконується"
]


# ============================================================
# FILTERS
# ============================================================

st.markdown("""
<div class="filter-card">
    <div class="card-title">Параметри відбору</div>
    <div class="card-subtitle">
        Оберіть необхідні параметри: період, індекс ССП та режим перегляду даних.
    </div>
</div>
""", unsafe_allow_html=True)

f1, f2, f3, f4 = st.columns([1, 1, 1.5, 1.2])

with f1:
    selected_years = st.multiselect(
        "Звітний період: рік",
        years_options,
        default=[],
        key="dash_years",
        placeholder="Усі роки"
    )

with f2:
    selected_quarters = st.multiselect(
        "Звітний період: квартал",
        quarters_options,
        default=[],
        key="dash_quarters",
        placeholder="Усі квартали"
    )

with f3:
    selected_department_indices = st.multiselect(
        "Індекс самостійного структурного підрозділу",
        department_indices_options,
        key="dash_department_indices"
    )

with f4:
    presentation_mode = st.toggle(
        "Presentation mode",
        value=False,
        key="dash_presentation_mode",
        help="Показує скорочену презентаційну версію: висновок, ключові індикатори та основні графіки."
    )

f5, f6, f7 = st.columns(3)

with f5:
    selected_goals = st.multiselect(
        "Стратегічна ціль",
        goal_options,
        format_func=lambda x: f"{x} — {strip_code_from_name(x, goal_name_map.get(x, ''))}",
        key="dash_goals"
    )

with f6:
    selected_tasks = st.multiselect(
        "Завдання",
        task_options,
        format_func=lambda x: f"{x} — {strip_code_from_name(x, task_name_map.get(x, ''))}",
        key="dash_tasks"
    )

with f7:
    selected_measures = st.multiselect(
        "Захід",
        measure_options,
        format_func=lambda x: f"{x} — {strip_code_from_name(x, measure_name_map.get(x, ''))}",
        key="dash_measures"
    )

f8, f9, f10 = st.columns(3)

with f8:
    selected_product_types = st.multiselect(
        "Тип продукту",
        product_type_options,
        key="dash_product_types"
    )

with f9:
    selected_deputies = st.multiselect(
        "Заступник Міністра",
        deputy_options,
        key="dash_deputies",
        help="Фільтр підготовлено. Повноцінно запрацює після прив’язки заступників до заходів."
    )

with f10:
    selected_statuses = st.multiselect(
        "Статус виконання",
        status_options,
        key="dash_statuses"
    )

f11, f12, f13 = st.columns([1, 1.5, 1])

with f11:
    selected_financing = st.multiselect(
        "Фінансування",
        [],
        key="dash_financing",
        help="Дані про фінансування поки не додані. Фільтр залишено як технічну заготовку."
    )

with f12:
    selected_sources = st.multiselect(
        "Джерело даних: національний рівень",
        source_options,
        key="dash_sources"
    )

with f13:
    view_mode = st.selectbox(
        "Режим перегляду",
        [
            "Усі візуалізації",
            "Стратегічні цілі",
            "Самостійні структурні підрозділи",
            "Ризики",
            "Динаміка",
            "План / факт",
            "Heatmap",
            "Таблиці"
        ],
        key="dash_view_mode"
    )

r1, r2 = st.columns([1, 5])
with r1:
    if st.button("Скинути фільтри", use_container_width=True):
        reset_filters()
        st.rerun()


# ============================================================
# BUILD ACTIVE DATA
# ============================================================

years_for_calc = selected_years if selected_years else years_options
quarters_for_calc = selected_quarters if selected_quarters else quarters_options

active_raw = build_period_data(
    strat_df,
    requests_df,
    years_for_calc,
    quarters_for_calc
)

if active_raw.empty:
    st.warning("Для обраного періоду активних заходів не знайдено.")
    st.stop()

active = apply_dashboard_filters(
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

if active.empty:
    st.warning("За обраними параметрами відбору даних не знайдено.")
    st.stop()


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
overdue_count = len(active[(active["end_num"].notna()) & (active["status_display"] != "Виконано") & (active["included_in_assessment"] == True)])

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
    ", ".join([f"{y} рік" for y in selected_years])
    if selected_years
    else "усі роки"
)

period_quarter_label = (
    ", ".join([f"{q} квартал" for q in selected_quarters])
    if selected_quarters
    else "усі квартали"
)

period_label = f"{period_year_label} | {period_quarter_label}"

st.markdown('<div class="card"><div class="card-title">Прогрес виконання: висновок системи</div>', unsafe_allow_html=True)

st.markdown(f"""
<div class="badge-wrap">
    <div class="badge {conclusion_badge}">{conclusion_title}</div>
    <div class="badge">Період: {period_label}</div>
    <div class="badge">Активних заходів: {total_active}</div>
    <div class="badge">Відхилення за звітний період: {deviation_current} в.п.</div>
</div>
<div style="color:#475569;font-size:14px;">{conclusion_text}</div>
""", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

def pct_value(count, total):
    if total == 0:
        return "0.0%"
    return f"{round(count / total * 100, 1)}%"


render_status_cards([
    {
        "title": "Заходів",
        "count": total_active,
        "percent": "100.0%" if total_active else "0.0%",
        "color": "alert-blue"
    },
    {
        "title": "Виконано",
        "count": completed_count,
        "percent": pct_value(completed_count, total_active),
        "color": "alert-green"
    },
    {
        "title": "Погоджено",
        "count": approved_requests_count,
        "percent": pct_value(approved_requests_count, total_active),
        "color": "alert-green"
    },
    {
        "title": "На розгляді",
        "count": review_count,
        "percent": pct_value(review_count, total_active),
        "color": "alert-yellow"
    },
    {
        "title": "Не враховано",
        "count": not_counted_count,
        "percent": pct_value(not_counted_count, total_active),
        "color": "alert-red"
    },
    {
        "title": "Не виконано",
        "count": not_done_count,
        "percent": pct_value(not_done_count, total_active),
        "color": "alert-red"
    },
    {
        "title": "Втратив актуальність",
        "count": obsolete_count,
        "percent": pct_value(obsolete_count, total_active),
        "color": "alert-neutral"
    },
    {
        "title": "Термін не настав",
        "count": not_time_count,
        "percent": pct_value(not_time_count, total_active),
        "color": "alert-neutral"
    },
    {
        "title": "Частково виконано",
        "count": partly_count,
        "percent": pct_value(partly_count, total_active),
        "color": "alert-yellow"
    },
    {
        "title": "Виконується",
        "count": in_progress_count,
        "percent": pct_value(in_progress_count, total_active),
        "color": "alert-blue"
    },
])


# ============================================================
# INSIGHTS
# ============================================================

if not presentation_mode:
    st.markdown('<div class="card"><div class="card-title">Автоматичні інсайти</div>', unsafe_allow_html=True)

    goal_failure = weighted_failure_group(active, ["goal_code", "strategic_goal"])

    dep_exploded_for_insights = explode_departments(active)
    dep_failure = weighted_failure_group(dep_exploded_for_insights, ["ssp_department"])

    insights = []

    if without_data > 0:
        insights.append(f"⚠️ {without_data} активних заходів не мають поданого погодженого моніторингу.")

    if critical_count > 0:
        insights.append(f"🔴 {critical_count} заходів мають критичний ризик недосягнення.")

    if not goal_failure.empty:
        row = goal_failure.iloc[0]
        insights.append(
            f"📉 Найбільша концентрація невиконаних заходів у СЦ {row['goal_code']} — "
            f"{int(row['Невиконаних'])} із {int(row['Активних_заходів'])}; "
            f"вага в обраному портфелі — {row['Вага_невиконання']}%."
        )

    if not dep_failure.empty:
        row = dep_failure.iloc[0]
        insights.append(
            f"🏢 Самостійний структурний підрозділ із найвищою концентрацією невиконання: "
            f"{row['ssp_department']} — {int(row['Невиконаних'])} із {int(row['Активних_заходів'])}; "
            f"вага в обраному портфелі — {row['Вага_невиконання']}%."
        )

    insights.append(f"📌 Відхилення за звітний період: {deviation_current} в.п. від планового рівня.")

    if not insights:
        insights.append("✅ Система не виявила критичних відхилень за обраним періодом.")

    for insight in insights:
        st.write(insight)

    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# MAIN INDICATORS
# ============================================================

st.markdown('<div class="card"><div class="card-title">Показники виконання стратегічного плану</div>', unsafe_allow_html=True)

g1, g2 = st.columns([1, 1])

with g1:
    st.plotly_chart(gauge_chart(completion, "Виконання СП"), use_container_width=True)

with g2:
    st.markdown("**Лінійні індикатори стану**")
    st.progress(min(completion / 100, 1.0), text=f"Виконання СП: {completion}%")
    st.progress(min(coverage / 100, 1.0), text=f"Покриття моніторингом: {coverage}%")
    st.progress(min(max(100 + deviation_current, 0) / 100, 1.0), text=f"Відхилення за звітний період: {deviation_current} в.п.")
    st.progress(min((100 - risk_share) / 100, 1.0), text=f"Частка заходів без автоматично визначеного ризику: {round(100 - risk_share, 1)}%")

st.markdown('</div>', unsafe_allow_html=True)


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
# VISUALIZATIONS
# ============================================================

show_all = view_mode == "Усі візуалізації" or presentation_mode

if view_mode in ["Усі візуалізації", "Стратегічні цілі"] or presentation_mode:
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Статуси виконання за принципом світлофора")
        fig = px.pie(
            traffic_counts,
            names="traffic_light",
            values="Кількість",
            hole=0.45,
            title="Розподіл активних заходів за станом виконання"
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Виконання за стратегічними цілями")
        fig = px.bar(
            goal_progress.sort_values("Виконання", ascending=False),
            x="strategic_goal",
            y="Виконання",
            text="Виконання",
            hover_data=["Активних_заходів", "Покриття_%", "Ризикових", "Середній_ризик"],
            labels={"strategic_goal": "Стратегічна ціль", "Виконання": "Виконання, %"}
        )
        fig.update_layout(xaxis_tickangle=-25, yaxis_range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)


if not presentation_mode and view_mode in ["Усі візуалізації", "Самостійні структурні підрозділи"]:
    st.subheader("Рейтинг самостійних структурних підрозділів")

    rank_df = dep_progress.sort_values("Виконання", ascending=False).copy()
    rank_df["Місце"] = range(1, len(rank_df) + 1)

    rank_display = rank_df[[
        "Місце",
        "ssp_department",
        "Виконання",
        "Покриття_%",
        "Ризикових",
        "Критичних",
        "Активних_заходів"
    ]].rename(columns={
        "ssp_department": "Самостійний структурний підрозділ",
        "Покриття_%": "Покриття, %",
        "Активних_заходів": "Активних заходів"
    })

    styled_rank = (
        rank_display
        .style
        .apply(lambda row: style_rank_table(row, len(rank_display)), axis=1)
        .set_properties(**{"text-align": "center"})
        .set_table_styles([
            {
                "selector": "th",
                "props": [
                    ("text-align", "center"),
                    ("background-color", "#e9eef7"),
                    ("color", "#111827"),
                    ("font-weight", "900"),
                    ("border", "1px solid #d8dee9")
                ]
            }
        ])
    )

    st.dataframe(styled_rank, use_container_width=True, hide_index=True)

    fig = px.bar(
        rank_df,
        x="ssp_department",
        y="Виконання",
        text="Виконання",
        hover_data=["Активних_заходів", "Покриття_%", "Ризикових", "Критичних"],
        labels={"ssp_department": "Самостійний структурний підрозділ", "Виконання": "Виконання, %"},
        title="Виконання за самостійними структурними підрозділами"
    )
    fig.update_layout(xaxis_tickangle=-25, yaxis_range=[0, 100])
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Виконання за Заступниками Міністра")

    deputy_data = active.copy()
    deputy_data["deputy_minister"] = deputy_data["deputy_minister"].fillna("").astype(str).replace("", "Не визначено")

    deputy_progress = (
        deputy_data
        .groupby("deputy_minister")
        .agg(
            Активних_заходів=("code", "count"),
            Виконання=("performance_score", "mean")
        )
        .reset_index()
    )

    deputy_progress["Виконання"] = deputy_progress["Виконання"].fillna(0).round(1)

    fig = px.bar(
        deputy_progress,
        x="deputy_minister",
        y="Виконання",
        text="Виконання",
        hover_data=["Активних_заходів"],
        labels={"deputy_minister": "Заступник Міністра", "Виконання": "Виконання, %"},
        title="Виконання за Заступниками Міністра"
    )
    fig.update_layout(xaxis_tickangle=-25, yaxis_range=[0, 100])
    st.plotly_chart(fig, use_container_width=True)


if not presentation_mode and view_mode in ["Усі візуалізації", "Ризики"]:
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Автоматична оцінка ризиків")
        fig = px.pie(
            risk_counts,
            names="auto_risk",
            values="Кількість",
            hole=0.45,
            title="Рівень ризику недосягнення"
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Структура ризиків за самостійними структурними підрозділами")
        stacked = dep_active.groupby(["ssp_department", "auto_risk"]).size().reset_index(name="Кількість")
        fig = px.bar(
            stacked,
            x="ssp_department",
            y="Кількість",
            color="auto_risk",
            title="Ризики за самостійними структурними підрозділами",
            labels={"ssp_department": "Самостійний структурний підрозділ", "auto_risk": "Ризик"}
        )
        fig.update_layout(xaxis_tickangle=-25)
        st.plotly_chart(fig, use_container_width=True)


if not presentation_mode and view_mode in ["Усі візуалізації", "Динаміка"]:
    st.subheader("Динаміка виконання")

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
                value = 0
                cov = 0
                dev = -100
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

    fig = px.line(
        trend_df,
        x="Період",
        y=["Виконання", "Покриття", "Відхилення за звітний період"],
        markers=True,
        title="Тренд виконання, покриття і відхилення"
    )
    st.plotly_chart(fig, use_container_width=True)


if not presentation_mode and view_mode in ["Усі візуалізації", "Heatmap"]:
    st.subheader("Heatmap: самостійний структурний підрозділ × квартал")

    heat_rows = []

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

            dep_heat = temp_dep.groupby("ssp_department").agg(
                Виконання=("performance_score", "mean"),
                Ризик=("risk_score", "mean")
            ).reset_index()

            for _, row in dep_heat.iterrows():
                heat_rows.append({
                    "Самостійний структурний підрозділ": row["ssp_department"],
                    "Період": f"{y} {q}",
                    "Виконання": round(row["Виконання"], 1) if pd.notna(row["Виконання"]) else 0,
                    "Ризик": round(row["Ризик"], 1) if pd.notna(row["Ризик"]) else 0
                })

    heat_df = pd.DataFrame(heat_rows)

    if not heat_df.empty:
        fig = px.density_heatmap(
            heat_df,
            x="Період",
            y="Самостійний структурний підрозділ",
            z="Виконання",
            histfunc="avg",
            title="Теплова карта виконання",
            color_continuous_scale="Blues"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Недостатньо даних для побудови теплової карти.")


if not presentation_mode and view_mode in ["Усі візуалізації", "План / факт"]:
    st.subheader("Порівняння план / факт")

    pf_table = active[
        (active["plan_fact_percent"].notna()) &
        (active["is_quantitative_pf"] == True)
    ].copy()

    if pf_table.empty:
        st.info("Для обраного періоду немає кількісних показників для порівняння план / факт.")
    else:
        pf_table["Відхилення від плану, %"] = (pf_table["plan_fact_percent"] - 100).round(1)

        fig = px.bar(
            pf_table.sort_values("plan_fact_percent").head(25),
            x="code",
            y="plan_fact_percent",
            hover_data=["name", "indicator", "department", "selected_target", "numeric_value"],
            title="ТОП-25 заходів із найнижчим виконанням планового показника",
            labels={"code": "Код заходу", "plan_fact_percent": "План / факт, %"}
        )
        fig.update_layout(yaxis_range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)


# ============================================================
# PROBLEM MEASURES
# ============================================================

if not presentation_mode:
    st.subheader("Проблемні заходи")

    risk_table = active[
        (
            active["auto_risk"].isin(["Критичний ризик", "Середній ризик"])
            |
            (active["status"] == "Не подано")
            |
            (active["performance_score"].fillna(0) < 75)
        )
        &
        (active["included_in_assessment"] == True)
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
            risk_table[
                [
                    "Період",
                    "Код",
                    "Захід",
                    "Індикатор",
                    "Головний ССП",
                    "Статус виконання",
                    "Планове значення",
                    "Фактичне значення",
                    "Traffic light",
                    "Рівень ризику",
                    "Risk score",
                    "Причина ризику",
                    "Опис прогресу"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# FULL TABLE
# ============================================================

if not presentation_mode and view_mode == "Таблиці":
    st.subheader("Повна таблиця активних заходів")

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
        full[
            [
                "Період",
                "Код",
                "Захід",
                "Індикатор",
                "Одиниця виміру",
                "Тип продукту",
                "Головний ССП",
                "Джерело даних",
                "Початок",
                "Кінець",
                "Планове значення",
                "Фактичне значення",
                "Статус виконання",
                "Оцінка виконання, %",
                "Traffic light",
                "Ризик",
                "Risk score",
                "Причина ризику"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# METHODOLOGY
# ============================================================

if not presentation_mode:
    with st.expander("Методологія розрахунку"):
        st.markdown(
            """
            **Активні заходи** — заходи, період виконання яких охоплює обраний рік і квартал.

            **Виконання СП** рахується як середня оцінка виконання активних заходів:
            - якщо є планове та фактичне значення — використовується співвідношення факт / план;
            - якщо план / факт не можна порахувати числово — використовується статус виконання;
            - «Виконано» = 100%;
            - «Частково виконано» = 75%;
            - «Виконується» = 50%;
            - «Не виконано», «Не подано», «Не розпочато», «Прострочено», «Потребує уваги» = 0%;
            - «Термін не настав» та «Втратив актуальність» не включаються до оцінки ризику.

            **Risk score** визначається автоматично на основі стану виконання:
            - відсутність погоджених моніторингових даних за активним заходом;
            - значне відставання фактичного значення від планового;
            - прострочення строку виконання;
            - проблемний статус виконання.

            Поле «ризики» у заявці є довідковим для адміністраторів і не є основою автоматичного розрахунку ризику.

            **Traffic light**:
            - 🟢 100% і більше — у графіку;
            - 🟡 75–99% — часткове виконання;
            - 🔴 нижче 75% — відставання;
            - ⚪ не оцінюється — термін не настав або захід втратив актуальність.

            **Відхилення за звітний період** = середній відсоток виконання мінус 100%.
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
