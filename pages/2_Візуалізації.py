import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
import re

st.set_page_config(page_title="Візуалізації", layout="wide")

FILE_PATH = "Під моніторинг СП.xlsx"
SHEET_NAME = "Страт_матриця"

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

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
    response = (
        supabase
        .table("monitoring_requests")
        .select("*")
        .eq("approval_status", "Погоджено")
        .execute()
    )

    if not response.data:
        return pd.DataFrame()

    return pd.DataFrame(response.data)


def get_goal_code(code):
    parts = str(code).split(".")
    return parts[0] + "." if len(parts) >= 1 else ""


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
    mapping = {
        "I": 1,
        "II": 2,
        "III": 3,
        "IV": 4
    }
    return mapping.get(str(q), 1)


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

    return 0


st.title("Виконання стратегічного плану")

strat_df = load_strat_matrix()
requests_df = load_requests()

measures = strat_df[strat_df["object_type"] == "measure"].copy()
goals = strat_df[strat_df["object_type"] == "goal"].copy()

if measures.empty:
    st.warning("У стратегічній матриці не знайдено заходів.")
    st.stop()

measures["goal_code"] = measures["code"].apply(get_goal_code)

goal_map = goals.set_index("code")["name"].to_dict()
measures["strategic_goal"] = measures["goal_code"].map(goal_map)

measures["start_num"] = measures["start_period"].apply(parse_period)
measures["end_num"] = measures["end_period"].apply(parse_period)

st.subheader("Фільтри періоду")

f1, f2, f3 = st.columns(3)

with f1:
    selected_year = st.selectbox("Рік", [2026, 2027, 2028])

with f2:
    selected_quarter = st.selectbox("Квартал", ["I", "II", "III", "IV"])

with f3:
    departments = sorted(measures["department"].dropna().astype(str).unique().tolist())
    selected_department = st.selectbox("Департамент", ["Усі"] + departments)

selected_period_num = selected_year * 10 + quarter_to_number(selected_quarter)

active_measures = measures.copy()

active_measures = active_measures[
    (
        active_measures["start_num"].isna()
        |
        (active_measures["start_num"] <= selected_period_num)
    )
    &
    (
        active_measures["end_num"].isna()
        |
        (active_measures["end_num"] >= selected_period_num)
    )
].copy()

if selected_department != "Усі":
    active_measures = active_measures[
        active_measures["department"].astype(str) == selected_department
    ]

if active_measures.empty:
    st.warning("Для обраного періоду активних заходів не знайдено.")
    st.stop()

if requests_df.empty:
    requests_df = pd.DataFrame(columns=[
        "year", "quarter", "strat_code", "status", "numeric_value", "risks", "progress_text"
    ])

period_requests = requests_df[
    (requests_df["year"].astype(int) == int(selected_year)) &
    (requests_df["quarter"].astype(str) == str(selected_quarter))
].copy()

period_requests = (
    period_requests
    .sort_values("submitted_at")
    .groupby("strat_code")
    .tail(1)
)

active_measures = active_measures.merge(
    period_requests[
        [
            "strat_code",
            "status",
            "numeric_value",
            "risks",
            "progress_text"
        ]
    ],
    left_on="code",
    right_on="strat_code",
    how="left"
)

active_measures["status"] = active_measures["status"].fillna("Не подано")
active_measures["score"] = active_measures["status"].apply(status_score)

total_active = len(active_measures)
submitted_count = len(active_measures[active_measures["status"] != "Не подано"])
completed_count = len(active_measures[active_measures["status"] == "Виконано"])
problem_count = len(active_measures[
    active_measures["status"].isin(["Прострочено", "Потребує уваги", "Виконано частково"])
])

completion_percent = round(active_measures["score"].mean(), 1)
submission_coverage = round(submitted_count / total_active * 100, 1)

st.divider()

st.subheader("Ключові показники виконання СП за обраний квартал")

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Активних заходів", total_active)
k2.metric("Подано моніторинг", submitted_count)
k3.metric("Покриття поданням", f"{submission_coverage}%")
k4.metric("Виконання СП", f"{completion_percent}%")
k5.metric("Проблемних заходів", problem_count)

st.caption(
    "Розрахунок виконання: Виконано = 100%, Виконано частково = 50%, "
    "Виконується = 40%, Потребує уваги = 25%, Прострочено / Не розпочато / Не подано = 0%."
)

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Статуси активних заходів")

    status_count = (
        active_measures
        .groupby("status")
        .size()
        .reset_index(name="Кількість")
    )

    fig_status = px.pie(
        status_count,
        names="status",
        values="Кількість",
        hole=0.45
    )

    st.plotly_chart(fig_status, use_container_width=True)

with right:
    st.subheader("Виконання за стратегічними цілями")

    goal_progress = (
        active_measures
        .groupby(["goal_code", "strategic_goal"])
        .agg(
            Активних_заходів=("code", "count"),
            Середній_прогрес=("score", "mean"),
            Подано=("status", lambda x: (x != "Не подано").sum())
        )
        .reset_index()
    )

    goal_progress["Середній_прогрес"] = goal_progress["Середній_прогрес"].round(1)

    fig_goal = px.bar(
        goal_progress,
        x="strategic_goal",
        y="Середній_прогрес",
        text="Середній_прогрес",
        hover_data=["Активних_заходів", "Подано"],
        labels={
            "strategic_goal": "Стратегічна ціль",
            "Середній_прогрес": "Виконання, %"
        }
    )

    fig_goal.update_layout(xaxis_tickangle=-25)

    st.plotly_chart(fig_goal, use_container_width=True)

st.divider()

st.subheader("Виконання за департаментами")

dep_progress = (
    active_measures
    .groupby("department")
    .agg(
        Активних_заходів=("code", "count"),
        Подано=("status", lambda x: (x != "Не подано").sum()),
        Виконання=("score", "mean"),
        Проблемних=("status", lambda x: x.isin(["Прострочено", "Потребує уваги", "Виконано частково"]).sum())
    )
    .reset_index()
)

dep_progress["Виконання"] = dep_progress["Виконання"].round(1)

fig_dep = px.bar(
    dep_progress.sort_values("Виконання", ascending=False),
    x="department",
    y="Виконання",
    text="Виконання",
    hover_data=["Активних_заходів", "Подано", "Проблемних"],
    labels={
        "department": "Департамент",
        "Виконання": "Виконання, %"
    }
)

st.plotly_chart(fig_dep, use_container_width=True)

st.divider()

st.subheader("Проблемні або неподані заходи")

problem_table = active_measures[
    (active_measures["status"] == "Не подано")
    |
    (active_measures["status"].isin(["Прострочено", "Потребує уваги", "Виконано частково"]))
].copy()

if problem_table.empty:
    st.success("Проблемних або неподаних заходів за обраний період немає.")
else:
    problem_table = problem_table.rename(columns={
        "code": "Код",
        "name": "Захід",
        "indicator": "Індикатор",
        "department": "Департамент",
        "status": "Статус",
        "numeric_value": "Факт за квартал",
        "risks": "Ризики / проблеми",
        "progress_text": "Опис прогресу",
        "start_period": "Початок",
        "end_period": "Кінець"
    })

    st.dataframe(
        problem_table[
            [
                "Код",
                "Захід",
                "Індикатор",
                "Департамент",
                "Початок",
                "Кінець",
                "Статус",
                "Факт за квартал",
                "Ризики / проблеми",
                "Опис прогресу"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

st.divider()

st.subheader("Повна таблиця активних заходів за обраний квартал")

full_table = active_measures.rename(columns={
    "code": "Код",
    "name": "Захід",
    "indicator": "Індикатор",
    "unit": "Одиниця виміру",
    "department": "Департамент",
    "start_period": "Початок виконання",
    "end_period": "Кінець виконання",
    "target_2026": "План 2026",
    "target_2027": "План 2027",
    "target_2028": "План 2028",
    "status": "Статус",
    "numeric_value": "Факт за квартал",
    "score": "Оцінка виконання, %"
})

st.dataframe(
    full_table[
        [
            "Код",
            "Захід",
            "Індикатор",
            "Одиниця виміру",
            "Департамент",
            "Початок виконання",
            "Кінець виконання",
            "План 2026",
            "План 2027",
            "План 2028",
            "Статус",
            "Факт за квартал",
            "Оцінка виконання, %"
        ]
    ],
    use_container_width=True,
    hide_index=True
)
