import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(
    page_title="Стратегічний план",
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
        "base_2021": data.iloc[:, 7],
        "fact_2024": data.iloc[:, 8],
        "expected_2025": data.iloc[:, 9],
        "target_2026": data.iloc[:, 10],
        "target_2027": data.iloc[:, 11],
        "target_2028": data.iloc[:, 12],
        "department": data.iloc[:, 17]
    })

    result = result.dropna(subset=["code"])
    result["code"] = result["code"].astype(str).str.strip()
    result["name"] = result["name"].astype(str).str.strip()

    def define_type(row):
        marker = str(row["type_marker"]).lower()
        code = str(row["code"])

        if "стратегічна ціль" in marker:
            return "goal"
        elif "завдання" in marker:
            return "task"
        elif "заход" in marker:
            return "measure"
        elif code.count(".") >= 3:
            return "measure"
        else:
            return "other"

    result["object_type"] = result.apply(define_type, axis=1)

    return result


def load_monitoring():
    response = (
        supabase
        .table("monitoring_requests")
        .select("*")
        .execute()
    )

    data = response.data

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    return df


df = load_strat_matrix()
monitoring_df = load_monitoring()

st.title("Моніторинг виконання стратегічного плану")

col1, col2 = st.columns([3, 1])

with col2:
    st.page_link(
        "pages/1_Моніторинг_виконання.py",
        label="Внесення даних моніторингу",
        icon="📝"
    )

st.divider()

st.subheader("Фільтри")

f1, f2 = st.columns(2)

with f1:
    departments = sorted(
        df["department"]
        .dropna()
        .astype(str)
        .unique()
    )

    selected_dep = st.selectbox(
        "Департамент",
        ["Усі"] + departments
    )

with f2:
    selected_year = st.selectbox(
        "Рік",
        [2026, 2027, 2028]
    )

filtered = df.copy()

if selected_dep != "Усі":
    filtered = filtered[
        filtered["department"].astype(str) == selected_dep
    ]

approved_monitoring = pd.DataFrame()

if not monitoring_df.empty:
    approved_monitoring = monitoring_df[
        (monitoring_df["approval_status"] == "Погоджено") &
        (monitoring_df["year"] == selected_year)
    ].copy()

    if not approved_monitoring.empty:
        approved_monitoring = (
            approved_monitoring
            .sort_values("submitted_at")
            .groupby("strat_code")
            .tail(1)
        )

st.subheader("Стратегічний план")

goals = df[df["object_type"] == "goal"]

for _, goal in goals.iterrows():

    goal_code = goal["code"]
    goal_name = goal["name"]

    with st.expander(f"{goal_code} {goal_name}"):

        goal_rows = filtered[
            filtered["code"].astype(str).str.startswith(goal_code)
        ]

        tasks = goal_rows[
            goal_rows["object_type"] == "task"
        ]

        for _, task in tasks.iterrows():

            task_code = task["code"]

            with st.expander(f"{task_code} {task['name']}"):

                measures = goal_rows[
                    (goal_rows["object_type"] == "measure") &
                    (goal_rows["code"].astype(str).str.startswith(task_code))
                ].copy()

                if measures.empty:
                    st.info("Заходів за цим завданням не знайдено.")
                    continue

                if not approved_monitoring.empty:
                    measures = measures.merge(
                        approved_monitoring[
                            [
                                "strat_code",
                                "quarter",
                                "status",
                                "progress_text",
                                "numeric_value",
                                "risks",
                                "submitted_at"
                            ]
                        ],
                        left_on="code",
                        right_on="strat_code",
                        how="left"
                    )
                else:
                    measures["quarter"] = ""
                    measures["status"] = ""
                    measures["progress_text"] = ""
                    measures["numeric_value"] = ""
                    measures["risks"] = ""
                    measures["submitted_at"] = ""

                year_col = f"target_{selected_year}"

                show_cols = [
                    "code",
                    "name",
                    "indicator",
                    "unit",
                    year_col,
                    "quarter",
                    "status",
                    "numeric_value",
                    "progress_text",
                    "department"
                ]

                st.dataframe(
                    measures[show_cols],
                    use_container_width=True,
                    hide_index=True
                )
