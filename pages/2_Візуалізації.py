import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime
import re

st.set_page_config(page_title="Візуалізації", layout="wide")

FILE_PATH = "Під моніторинг СП.xlsx"
SHEET_NAME = "Страт_матриця"

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

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

.footer {
    text-align: center;
    color: #64748b;
    font-size: 13px;
    margin-top: 50px;
    padding: 22px 0 12px 0;
    border-top: 1px solid #d8dee9;
}
</style>
""", unsafe_allow_html=True)


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
        "start_period": data.iloc[:, 22],
        "end_period": data.iloc[:, 23],
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


def load_requests():
    response = supabase.table("monitoring_requests").select("*").execute()

    if not response.data:
        return pd.DataFrame()

    return pd.DataFrame(response.data)


def parse_period(value):
    text = str(value).lower().strip()

    if text in ["", "nan", "none", "н.д."]:
        return None

    q = None
    year = None

    if "1 квартал" in text or "i квартал" in text:
        q = 1
    elif "2 квартал" in text or "ii квартал" in text:
        q = 2
    elif "3 квартал" in text or "iii квартал" in text:
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
    return {"I": 1, "II": 2, "III": 3, "IV": 4}.get(str(q), 1)


def get_goal_code(code):
    parts = str(code).split(".")
    return parts[0] + "." if parts else ""


def get_task_code(code):
    parts = str(code).split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}."
    return ""


def to_number(value):
    text = str(value).replace(",", ".").strip()

    if text.lower() in ["", "nan", "none", "н.д.", "x", "х", "так", "ні", "да", "нет"]:
        return None

    match = re.search(r"-?\d+(\.\d+)?", text)

    if match:
        try:
            return float(match.group())
        except Exception:
            return None

    return None


def normalize_text(value):
    return str(value).strip().lower().replace("і", "i")


def status_score(status):
    status = str(status)

    if status == "Виконано":
        return 100
    if status == "Виконано частково":
        return 50
    if status == "Виконується":
        return 40
    if status == "Потребує уваги":
        return 25
    if status == "Прострочено":
        return 0
    if status == "Не розпочато":
        return 0
    if status == "Не подано":
        return 0

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


def risk_assessment(row, selected_period_num, selected_quarter_num):
    status = str(row.get("status", "Не подано"))
    actual = row.get("numeric_value", "")
    target = row.get("selected_target", "")
    risks_text = str(row.get("risks", "")).strip()

    expected_progress = selected_quarter_num * 25
    pf = plan_fact_percent(actual, target)

    if status == "Не подано":
        return "Критичний ризик", "За активним заходом не подано моніторингові дані."

    if status == "Прострочено":
        return "Критичний ризик", "Статус заходу — прострочено."

    if status == "Потребує уваги":
        return "Помірний ризик", "Статус заходу потребує уваги."

    if status == "Виконано частково":
        return "Помірний ризик", "Захід виконано частково."

    if pf is not None:
        if pf < max(expected_progress - 25, 0):
            return "Критичний ризик", f"Факт суттєво нижчий за очікуваний прогрес кварталу ({expected_progress}%)."
        if pf < expected_progress:
            return "Помірний ризик", f"Факт нижчий за очікуваний прогрес кварталу ({expected_progress}%)."

    if risks_text:
        return "Помірний ризик", "У заявці зазначені ризики / проблеми / відхилення."

    if status == "Виконано":
        return "Низький ризик", "Захід позначено як виконаний."

    if status == "Виконується":
        return "Низький ризик", "Захід виконується без критичних відхилень."

    return "Низький ризик", "Критичних відхилень не виявлено."


def dashboard_conclusion(completion, risk_share, coverage):
    if completion >= 75 and risk_share <= 15 and coverage >= 70:
        return "План переважно виконується", "Поточний стан виконання виглядає контрольованим."
    if completion >= 45 and risk_share <= 35:
        return "Є помірні відхилення", "Потрібна увага до окремих заходів, департаментів або стратегічних цілей."
    return "Високий ризик невиконання", "Поточні дані свідчать про суттєві ризики або недостатнє покриття моніторингом."


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


def prepare_period_data(strat_df, requests_df, year, quarter, department):
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

    approved_requests = requests_df[
        requests_df["approval_status"].astype(str) == "Погоджено"
    ].copy()

    if approved_requests.empty:
        period_requests = pd.DataFrame(columns=[
            "strat_code", "status", "numeric_value", "risks", "progress_text", "submitted_at"
        ])
    else:
        period_requests = approved_requests[
            (approved_requests["year"].astype(str) == str(year)) &
            (approved_requests["quarter"].astype(str) == str(quarter))
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

    active["status_score"] = active["status"].apply(status_score)
    active["plan_fact_percent"] = active.apply(
        lambda r: plan_fact_percent(r["numeric_value"], r["selected_target"]),
        axis=1
    )

    active["performance_score"] = active.apply(
        lambda r: r["plan_fact_percent"] if pd.notna(r["plan_fact_percent"]) else r["status_score"],
        axis=1
    )

    risk_results = active.apply(
        lambda r: risk_assessment(r, selected_period_num, selected_q_num),
        axis=1
    )

    active["auto_risk"] = [x[0] for x in risk_results]
    active["risk_reason"] = [x[1] for x in risk_results]

    return active


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
    """
    <div class="header-box">
        <div class="header-title">Аналітична панель виконання стратегічного плану</div>
        <div class="header-subtitle">
            Dashboard показує не лише кількість заявок, а реальний стан виконання заходів:
            прогрес, відхилення від плану, ризики недосягнення, активні заходи за квартал,
            проблемні департаменти та стратегічні цілі.
        </div>
        <div class="status-pill-wrap">
            <div class="status-pill">● Режим: dashboard</div>
            <div class="status-pill">● Джерело: Excel + Supabase</div>
            <div class="status-pill">● Факт: погоджені заявки</div>
            <div class="status-pill">● Оновлено: """ + datetime.now().strftime("%d.%m.%Y %H:%M") + """</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

strat_df = load_strat_matrix()
requests_df = load_requests()

if requests_df.empty:
    requests_df = pd.DataFrame(columns=[
        "year", "quarter", "department", "strat_code", "status", "numeric_value",
        "risks", "progress_text", "approval_status", "submitted_at"
    ])

measures_all = strat_df[strat_df["object_type"] == "measure"].copy()

st.markdown('<div class="card"><div class="card-title">Фільтри аналітики</div><div class="card-subtitle">Оберіть період і зріз аналізу.</div>', unsafe_allow_html=True)

f1, f2, f3, f4 = st.columns(4)

with f1:
    selected_year = st.selectbox("Рік", [2026, 2027, 2028])

with f2:
    selected_quarter = st.selectbox("Квартал", ["I", "II", "III", "IV"])

with f3:
    departments = sorted(measures_all["department"].dropna().astype(str).unique().tolist())
    selected_department = st.selectbox("Департамент", ["Усі"] + departments)

with f4:
    view_mode = st.selectbox(
        "Режим перегляду",
        [
            "Огляд",
            "Стратегічні цілі",
            "Департаменти",
            "Ризики",
            "Динаміка",
            "План / факт",
            "Таблиці"
        ]
    )

st.markdown('</div>', unsafe_allow_html=True)

active = prepare_period_data(
    strat_df,
    requests_df,
    selected_year,
    selected_quarter,
    selected_department
)

if active.empty:
    st.warning("Для обраного періоду активних заходів не знайдено.")
    st.stop()

total_active = len(active)
submitted_count = len(active[active["status"] != "Не подано"])
coverage = round(submitted_count / total_active * 100, 1) if total_active else 0
completion = round(active["performance_score"].mean(), 1) if total_active else 0
risk_count = len(active[active["auto_risk"].isin(["Критичний ризик", "Помірний ризик"])])
critical_count = len(active[active["auto_risk"] == "Критичний ризик"])
risk_share = round(risk_count / total_active * 100, 1) if total_active else 0
without_data = len(active[active["status"] == "Не подано"])

conclusion_title, conclusion_text = dashboard_conclusion(completion, risk_share, coverage)

st.markdown('<div class="card"><div class="card-title">Чи йдемо за планом?</div>', unsafe_allow_html=True)

badge_class = "risk-low"

if "помірні" in conclusion_title.lower():
    badge_class = "risk-medium"
elif "високий" in conclusion_title.lower():
    badge_class = "risk-high"

st.markdown(
    f"""
    <div class="badge-wrap">
        <div class="badge {badge_class}">{conclusion_title}</div>
        <div class="badge">Період: {selected_year} рік, {selected_quarter} квартал</div>
        <div class="badge">Активних заходів: {total_active}</div>
        <div class="badge">Покриття моніторингом: {coverage}%</div>
    </div>
    <div style="color:#475569;font-size:14px;">{conclusion_text}</div>
    """,
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Активних заходів", total_active)
k2.metric("Подано моніторинг", submitted_count)
k3.metric("Покриття", f"{coverage}%")
k4.metric("Виконання СП", f"{completion}%")
k5.metric("Заходів у ризику", risk_count)

k6, k7, k8 = st.columns(3)
k6.metric("Критичні ризики", critical_count)
k7.metric("Без подання", without_data)
k8.metric("Середнє відхилення", f"{round(100 - completion, 1)}%")

st.markdown('<div class="card"><div class="card-title">Головні індикатори</div>', unsafe_allow_html=True)

g1, g2 = st.columns([1, 1])

with g1:
    st.plotly_chart(
        gauge_chart(completion, "Виконання СП"),
        use_container_width=True
    )

with g2:
    st.markdown("**Бар-індикатори стану**")
    st.caption("Ці індикатори показують не кількість заявок, а стан виконання активних заходів.")

    st.progress(min(completion / 100, 1.0), text=f"Виконання СП: {completion}%")
    st.progress(min(coverage / 100, 1.0), text=f"Покриття моніторингом: {coverage}%")
    st.progress(min((100 - risk_share) / 100, 1.0), text=f"Безризиковість портфеля: {round(100 - risk_share, 1)}%")
    st.progress(min((100 - (without_data / total_active * 100)) / 100, 1.0), text=f"Заходи з даними: {round(100 - (without_data / total_active * 100), 1)}%")

st.markdown('</div>', unsafe_allow_html=True)

chart_mode = st.selectbox(
    "Оберіть тип візуалізації",
    [
        "Автоматичний огляд",
        "Gauge",
        "Кругова діаграма",
        "Стовпчаста діаграма",
        "Stacked bar",
        "Лінія тренду",
        "Heatmap",
        "Treemap"
    ]
)

status_counts = active.groupby("status").size().reset_index(name="Кількість")
risk_counts = active.groupby("auto_risk").size().reset_index(name="Кількість")

goal_progress = (
    active
    .groupby(["goal_code", "strategic_goal"])
    .agg(
        Активних_заходів=("code", "count"),
        Виконання=("performance_score", "mean"),
        Покриття=("status", lambda x: (x != "Не подано").sum()),
        Ризикових=("auto_risk", lambda x: x.isin(["Критичний ризик", "Помірний ризик"]).sum())
    )
    .reset_index()
)

goal_progress["Виконання"] = goal_progress["Виконання"].round(1)
goal_progress["Покриття_%"] = (goal_progress["Покриття"] / goal_progress["Активних_заходів"] * 100).round(1)

dep_progress = (
    active
    .groupby("department")
    .agg(
        Активних_заходів=("code", "count"),
        Виконання=("performance_score", "mean"),
        Подано=("status", lambda x: (x != "Не подано").sum()),
        Ризикових=("auto_risk", lambda x: x.isin(["Критичний ризик", "Помірний ризик"]).sum()),
        Критичних=("auto_risk", lambda x: (x == "Критичний ризик").sum())
    )
    .reset_index()
)

dep_progress["Виконання"] = dep_progress["Виконання"].round(1)
dep_progress["Покриття_%"] = (dep_progress["Подано"] / dep_progress["Активних_заходів"] * 100).round(1)

if view_mode in ["Огляд", "Стратегічні цілі"] or chart_mode in ["Автоматичний огляд", "Стовпчаста діаграма"]:
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Статуси активних заходів")

        fig = px.pie(
            status_counts,
            names="status",
            values="Кількість",
            hole=0.45,
            title="Розподіл статусів"
        )

        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Виконання за стратегічними цілями")

        fig = px.bar(
            goal_progress.sort_values("Виконання", ascending=False),
            x="strategic_goal",
            y="Виконання",
            text="Виконання",
            hover_data=["Активних_заходів", "Покриття_%", "Ризикових"],
            labels={
                "strategic_goal": "Стратегічна ціль",
                "Виконання": "Виконання, %"
            }
        )

        fig.update_layout(xaxis_tickangle=-25)
        st.plotly_chart(fig, use_container_width=True)

if view_mode in ["Огляд", "Департаменти"] or chart_mode in ["Автоматичний огляд", "Stacked bar"]:
    st.subheader("Виконання за департаментами")

    fig = px.bar(
        dep_progress.sort_values("Виконання", ascending=False),
        x="department",
        y="Виконання",
        text="Виконання",
        hover_data=["Активних_заходів", "Покриття_%", "Ризикових", "Критичних"],
        labels={
            "department": "Департамент",
            "Виконання": "Виконання, %"
        }
    )

    st.plotly_chart(fig, use_container_width=True)

    stacked = (
        active
        .groupby(["department", "auto_risk"])
        .size()
        .reset_index(name="Кількість")
    )

    fig = px.bar(
        stacked,
        x="department",
        y="Кількість",
        color="auto_risk",
        title="Структура ризиків за департаментами",
        labels={"department": "Департамент", "auto_risk": "Ризик"}
    )

    st.plotly_chart(fig, use_container_width=True)

if view_mode in ["Огляд", "Ризики"] or chart_mode in ["Автоматичний огляд", "Кругова діаграма"]:
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
        st.subheader("Treemap ризиків")

        tree_df = active.copy()
        tree_df["strategic_goal"] = tree_df["strategic_goal"].fillna("Без стратегічної цілі")

        fig = px.treemap(
            tree_df,
            path=["auto_risk", "department", "code"],
            values=[1] * len(tree_df),
            title="Структура ризиків: ризик → департамент → захід"
        )

        st.plotly_chart(fig, use_container_width=True)

if view_mode in ["Огляд", "Динаміка"] or chart_mode in ["Автоматичний огляд", "Лінія тренду"]:
    st.subheader("Динаміка виконання за кварталами")

    trend_rows = []

    for y in [2026, 2027, 2028]:
        for q in ["I", "II", "III", "IV"]:
            temp = prepare_period_data(strat_df, requests_df, y, q, selected_department)

            if temp.empty:
                value = 0
                cov = 0
                risks = 0
            else:
                value = round(temp["performance_score"].mean(), 1)
                cov = round(len(temp[temp["status"] != "Не подано"]) / len(temp) * 100, 1)
                risks = len(temp[temp["auto_risk"].isin(["Критичний ризик", "Помірний ризик"])])

            trend_rows.append({
                "Період": f"{y} {q}",
                "Рік": y,
                "Квартал": q,
                "Виконання": value,
                "Покриття": cov,
                "Ризикових заходів": risks
            })

    trend_df = pd.DataFrame(trend_rows)

    fig = px.line(
        trend_df,
        x="Період",
        y=["Виконання", "Покриття"],
        markers=True,
        title="Тренд виконання та покриття моніторингом"
    )

    st.plotly_chart(fig, use_container_width=True)

    fig = px.bar(
        trend_df,
        x="Період",
        y="Ризикових заходів",
        title="Динаміка кількості ризикових заходів"
    )

    st.plotly_chart(fig, use_container_width=True)

if view_mode in ["Огляд", "Стратегічні цілі"] or chart_mode in ["Автоматичний огляд", "Heatmap"]:
    st.subheader("Heatmap: стратегічна ціль × квартал")

    heat_rows = []

    for y in [2026, 2027, 2028]:
        for q in ["I", "II", "III", "IV"]:
            temp = prepare_period_data(strat_df, requests_df, y, q, selected_department)

            if temp.empty:
                continue

            gp = (
                temp
                .groupby("goal_code")
                .agg(Виконання=("performance_score", "mean"))
                .reset_index()
            )

            for _, row in gp.iterrows():
                heat_rows.append({
                    "Стратегічна ціль": row["goal_code"],
                    "Період": f"{y} {q}",
                    "Виконання": round(row["Виконання"], 1)
                })

    heat_df = pd.DataFrame(heat_rows)

    if not heat_df.empty:
        fig = px.density_heatmap(
            heat_df,
            x="Період",
            y="Стратегічна ціль",
            z="Виконання",
            histfunc="avg",
            title="Теплова карта виконання"
        )

        st.plotly_chart(fig, use_container_width=True)

if view_mode in ["План / факт", "Огляд"] or chart_mode in ["Автоматичний огляд"]:
    st.subheader("Порівняння план / факт")

    pf_table = active.copy()
    pf_table = pf_table[
        pf_table["plan_fact_percent"].notna()
    ].copy()

    if pf_table.empty:
        st.info("Для обраного періоду немає числових або бінарних показників для порівняння план / факт.")
    else:
        pf_table["Відхилення від плану, %"] = (pf_table["plan_fact_percent"] - 100).round(1)

        fig = px.bar(
            pf_table.sort_values("plan_fact_percent").head(25),
            x="code",
            y="plan_fact_percent",
            hover_data=["name", "indicator", "department", "selected_target", "numeric_value"],
            title="ТОП-25 заходів з найнижчим виконанням планового показника",
            labels={
                "code": "Код заходу",
                "plan_fact_percent": "План / факт, %"
            }
        )

        st.plotly_chart(fig, use_container_width=True)

if view_mode in ["Ризики", "Огляд"]:
    st.subheader("Проблемні та ризикові заходи")

    risk_table = active[
        active["auto_risk"].isin(["Критичний ризик", "Помірний ризик"])
    ].copy()

    if risk_table.empty:
        st.success("Ризикових заходів за обраний період не виявлено.")
    else:
        risk_table = risk_table.rename(columns={
            "code": "Код",
            "name": "Захід",
            "indicator": "Індикатор",
            "department": "Департамент",
            "status": "Статус",
            "selected_target": "Планове значення",
            "numeric_value": "Фактичне значення",
            "auto_risk": "Рівень ризику",
            "risk_reason": "Причина ризику",
            "progress_text": "Опис прогресу"
        })

        st.dataframe(
            risk_table[
                [
                    "Код",
                    "Захід",
                    "Індикатор",
                    "Департамент",
                    "Статус",
                    "Планове значення",
                    "Фактичне значення",
                    "Рівень ризику",
                    "Причина ризику",
                    "Опис прогресу"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

if view_mode == "Таблиці":
    st.subheader("Повна таблиця активних заходів")

    full = active.rename(columns={
        "code": "Код",
        "name": "Захід",
        "indicator": "Індикатор",
        "unit": "Одиниця виміру",
        "department": "Департамент",
        "start_period": "Початок",
        "end_period": "Кінець",
        "selected_target": "Планове значення",
        "numeric_value": "Фактичне значення",
        "status": "Статус",
        "performance_score": "Оцінка виконання, %",
        "auto_risk": "Ризик",
        "risk_reason": "Причина ризику"
    })

    st.dataframe(
        full[
            [
                "Код",
                "Захід",
                "Індикатор",
                "Одиниця виміру",
                "Департамент",
                "Початок",
                "Кінець",
                "Планове значення",
                "Фактичне значення",
                "Статус",
                "Оцінка виконання, %",
                "Ризик",
                "Причина ризику"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

with st.expander("Методологія розрахунку"):
    st.markdown(
        """
        **Активні заходи** — заходи, період виконання яких охоплює обраний рік і квартал.

        **Виконання СП** рахується як середня оцінка виконання активних заходів:
        - якщо є планове та фактичне значення — використовується співвідношення факт / план;
        - якщо план / факт не можна порахувати числово — використовується статус виконання;
        - «Виконано» = 100%;
        - «Виконано частково» = 50%;
        - «Виконується» = 40%;
        - «Потребує уваги» = 25%;
        - «Прострочено», «Не розпочато», «Не подано» = 0%.

        **Ризик недосягнення** визначається автоматично:
        - якщо активний захід не має поданих даних;
        - якщо статус проблемний;
        - якщо фактичне значення нижче очікуваного прогресу кварталу;
        - якщо зазначені ризики / проблеми / відхилення.
        """
    )

st.markdown(
    """
    <div class="footer">
        Розроблено департаментом стратегічного планування та макроекономічного прогнозування<br>
        Версія DEMO 0.9 | Аналітична панель виконання стратегічного плану
    </div>
    """,
    unsafe_allow_html=True
)
