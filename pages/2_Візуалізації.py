import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client

st.set_page_config(
    page_title="Візуалізації",
    layout="wide"
)

FILE_PATH = "Під моніторинг СП.xlsx"
SHEET_NAME = "Страт_матриця"

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)


@st.cache_data
def load_strat_matrix():
    df = pd.read_excel(
        FILE_PATH,
        sheet_name=SHEET_NAME,
        header=None,
        engine="openpyxl"
    )

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
        "department": data.iloc[:, 17]
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
        .execute()
    )

    if not response.data:
        return pd.DataFrame()

    return pd.DataFrame(response.data)


def get_goal_code(code):
    parts = str(code).split(".")
    if len(parts) >= 1:
        return parts[0] + "."
    return ""


def get_task_code(code):
    parts = str(code).split(".")
    if len(parts) >= 2:
        return parts[0] + "." + parts[1] + "."
    return ""


def traffic_light(status):
    if status == "Виконано":
        return "🟢 Виконано"
    if status == "Виконано частково":
        return "🟡 Частково"
    if status == "Виконується":
        return "🔵 Виконується"
    if status == "Потребує уваги":
        return "🟠 Потребує уваги"
    if status == "Прострочено":
        return "🔴 Прострочено"
    return "⚪ Не розпочато"


st.title("Візуалізації виконання стратегічного плану")

strat_df = load_strat_matrix()
requests_df = load_requests()

measures_df = strat_df[strat_df["object_type"] == "measure"].copy()
goals_df = strat_df[strat_df["object_type"] == "goal"].copy()
tasks_df = strat_df[strat_df["object_type"] == "task"].copy()

if requests_df.empty:
    st.warning("Поки що немає даних моніторингу.")
    st.stop()

for col in [
    "year",
    "quarter",
    "department",
    "strat_code",
    "status",
    "numeric_value",
    "approval_status",
    "risks",
    "progress_text"
]:
    if col not in requests_df.columns:
        requests_df[col] = ""

requests_df["goal_code"] = requests_df["strat_code"].apply(get_goal_code)
requests_df["task_code"] = requests_df["strat_code"].apply(get_task_code)

goal_map = goals_df.set_index("code")["name"].to_dict()
task_map = tasks_df.set_index("code")["name"].to_dict()

requests_df["strategic_goal"] = requests_df["goal_code"].map(goal_map)
requests_df["strategic_task"] = requests_df["task_code"].map(task_map)

st.subheader("Фільтри")

f1, f2, f3, f4 = st.columns(4)

with f1:
    years = sorted(requests_df["year"].dropna().astype(int).unique().tolist())
    selected_year = st.selectbox("Рік", ["Усі"] + years)

with f2:
    departments = sorted(requests_df["department"].dropna().astype(str).unique().tolist())
    selected_department = st.selectbox("Департамент", ["Усі"] + departments)

with f3:
    quarters = ["I", "II", "III", "IV"]
    selected_quarter = st.selectbox("Квартал", ["Усі"] + quarters)

with f4:
    approval_statuses = [
        "Усі",
        "Очікує погодження",
        "Погоджено",
        "Повернуто на доопрацювання"
    ]
    selected_approval = st.selectbox("Статус погодження", approval_statuses)

filtered = requests_df.copy()

if selected_year != "Усі":
    filtered = filtered[filtered["year"].astype(int) == int(selected_year)]

if selected_department != "Усі":
    filtered = filtered[filtered["department"].astype(str) == str(selected_department)]

if selected_quarter != "Усі":
    filtered = filtered[filtered["quarter"].astype(str) == str(selected_quarter)]

if selected_approval != "Усі":
    filtered = filtered[filtered["approval_status"].astype(str) == str(selected_approval)]

approved = filtered[filtered["approval_status"] == "Погоджено"].copy()

st.divider()

total_measures = len(measures_df)
monitored_measures = filtered["strat_code"].nunique()
approved_measures = approved["strat_code"].nunique()
coverage = round((approved_measures / total_measures) * 100, 1) if total_measures > 0 else 0

pending = len(filtered[filtered["approval_status"] == "Очікує погодження"])
returned = len(filtered[filtered["approval_status"] == "Повернуто на доопрацювання"])

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Усього заходів у СП", total_measures)
k2.metric("Заходів із заявками", monitored_measures)
k3.metric("Погоджених заходів", approved_measures)
k4.metric("Покриття моніторингом", f"{coverage}%")
k5.metric("Очікують погодження", pending)

st.caption(f"Повернуто на доопрацювання: {returned}")

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Покриття моніторингом за стратегічними цілями")

    goal_total = (
        measures_df
        .assign(goal_code=measures_df["code"].apply(get_goal_code))
        .groupby("goal_code")
        .size()
        .reset_index(name="Усього заходів")
    )

    goal_approved = (
        approved
        .groupby("goal_code")["strat_code"]
        .nunique()
        .reset_index(name="Погоджено заходів")
    )

    goal_progress = goal_total.merge(goal_approved, on="goal_code", how="left")
    goal_progress["Погоджено заходів"] = goal_progress["Погоджено заходів"].fillna(0)
    goal_progress["Покриття, %"] = round(
        goal_progress["Погоджено заходів"] / goal_progress["Усього заходів"] * 100,
        1
    )
    goal_progress["Стратегічна ціль"] = goal_progress["goal_code"].map(goal_map)

    fig_goal = px.bar(
        goal_progress,
        x="Стратегічна ціль",
        y="Покриття, %",
        text="Покриття, %",
        hover_data=["Усього заходів", "Погоджено заходів"]
    )

    fig_goal.update_layout(xaxis_tickangle=-25)

    st.plotly_chart(fig_goal, use_container_width=True)

with right:
    st.subheader("Розподіл заявок за статусом погодження")

    status_count = (
        filtered
        .groupby("approval_status")
        .size()
        .reset_index(name="Кількість")
    )

    fig_status = px.pie(
        status_count,
        names="approval_status",
        values="Кількість",
        hole=0.45
    )

    st.plotly_chart(fig_status, use_container_width=True)

st.divider()

left2, right2 = st.columns(2)

with left2:
    st.subheader("Виконання за статусами заходів")

    status_exec = (
        approved
        .groupby("status")
        .size()
        .reset_index(name="Кількість")
    )

    if status_exec.empty:
        st.info("Немає погоджених даних для цього фільтра.")
    else:
        fig_exec = px.bar(
            status_exec,
            x="status",
            y="Кількість",
            text="Кількість",
            labels={
                "status": "Статус виконання"
            }
        )

        st.plotly_chart(fig_exec, use_container_width=True)

with right2:
    st.subheader("Заявки за кварталами")

    quarter_count = (
        filtered
        .groupby("quarter")
        .size()
        .reset_index(name="Кількість")
    )

    quarter_order = ["I", "II", "III", "IV"]

    quarter_count["quarter"] = pd.Categorical(
        quarter_count["quarter"],
        categories=quarter_order,
        ordered=True
    )

    quarter_count = quarter_count.sort_values("quarter")

    fig_quarter = px.bar(
        quarter_count,
        x="quarter",
        y="Кількість",
        text="Кількість",
        labels={
            "quarter": "Квартал"
        }
    )

    st.plotly_chart(fig_quarter, use_container_width=True)

st.divider()

st.subheader("Heatmap: департаменти × стратегічні цілі")

heatmap_data = (
    approved
    .groupby(["department", "goal_code"])["strat_code"]
    .nunique()
    .reset_index(name="Кількість погоджених заходів")
)

if heatmap_data.empty:
    st.info("Немає погоджених даних для heatmap.")
else:
    heatmap_data["Стратегічна ціль"] = heatmap_data["goal_code"].map(goal_map)

    heatmap_pivot = heatmap_data.pivot_table(
        index="department",
        columns="Стратегічна ціль",
        values="Кількість погоджених заходів",
        fill_value=0
    )

    fig_heatmap = px.imshow(
        heatmap_pivot,
        text_auto=True,
        aspect="auto",
        labels=dict(
            x="Стратегічна ціль",
            y="Департамент",
            color="Кількість"
        )
    )

    st.plotly_chart(fig_heatmap, use_container_width=True)

st.divider()

st.subheader("Світлофор проблемних заходів")

latest_approved = approved.copy()

if latest_approved.empty:
    st.info("Немає погоджених заявок.")
else:
    latest_approved = latest_approved.sort_values("submitted_at").groupby("strat_code").tail(1)

    latest_approved["Світлофор"] = latest_approved["status"].apply(traffic_light)

    problem_statuses = [
        "Прострочено",
        "Потребує уваги",
        "Виконано частково"
    ]

    problem_df = latest_approved[
        latest_approved["status"].isin(problem_statuses)
    ].copy()

    if problem_df.empty:
        st.success("Проблемних заходів за обраними фільтрами не виявлено.")
    else:
        show_cols = [
            "Світлофор",
            "year",
            "quarter",
            "department",
            "strat_code",
            "status",
            "numeric_value",
            "risks",
            "progress_text"
        ]

        st.dataframe(
            problem_df[show_cols],
            use_container_width=True,
            hide_index=True
        )

st.divider()

st.subheader("Рейтинг департаментів за погодженими заходами")

ranking = (
    approved
    .groupby("department")["strat_code"]
    .nunique()
    .reset_index(name="Погоджених заходів")
    .sort_values("Погоджених заходів", ascending=False)
)

if ranking.empty:
    st.info("Немає погоджених даних для рейтингу.")
else:
    fig_rank = px.bar(
        ranking,
        x="department",
        y="Погоджених заходів",
        text="Погоджених заходів",
        labels={
            "department": "Департамент"
        }
    )

    st.plotly_chart(fig_rank, use_container_width=True)

st.divider()

st.subheader("Таблиця моніторингових даних")

table_cols = [
    "year",
    "quarter",
    "department",
    "goal_code",
    "strategic_goal",
    "task_code",
    "strategic_task",
    "strat_code",
    "status",
    "numeric_value",
    "approval_status",
    "risks",
    "progress_text"
]

available_cols = [col for col in table_cols if col in filtered.columns]

st.dataframe(
    filtered[available_cols],
    use_container_width=True,
    hide_index=True
)
