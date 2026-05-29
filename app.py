import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Моніторинг стратегічного плану",
    layout="wide"
)

FILE_PATH = "Під моніторинг СП.xlsx"
SHEET_NAME = "Страт_матриця"

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
        "type_marker": data.iloc[:,1],
        "code": data.iloc[:,2],
        "name": data.iloc[:,3],
        "indicator": data.iloc[:,5],
        "unit": data.iloc[:,6],
        "target_2026": data.iloc[:,10],
        "target_2027": data.iloc[:,11],
        "target_2028": data.iloc[:,12],
        "department": data.iloc[:,17]
    })

    result = result.dropna(subset=["code"])

    result["code"] = result["code"].astype(str)

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

    result["object_type"] = result.apply(
        define_type,
        axis=1
    )

    return result


df = load_strat_matrix()

st.title(
    "Моніторинг виконання стратегічного плану"
)

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

filtered = df.copy()

if selected_dep != "Усі":

    filtered = filtered[
        filtered["department"]
        .astype(str)
        == selected_dep
    ]

goals = filtered[
    filtered["object_type"]
    == "goal"
]

for _, goal in goals.iterrows():

    goal_code = goal["code"]
    goal_name = goal["name"]

    with st.expander(
        f"{goal_code} {goal_name}"
    ):

        goal_rows = filtered[
            filtered["code"]
            .astype(str)
            .str.startswith(goal_code)
        ]

        tasks = goal_rows[
            goal_rows["object_type"]
            == "task"
        ]

        for _, task in tasks.iterrows():

            task_code = task["code"]

            with st.expander(
                f"{task_code} {task['name']}"
            ):

                measures = goal_rows[
                    goal_rows["code"]
                    .astype(str)
                    .str.startswith(task_code)
                ]

                st.dataframe(
                    measures[
                        [
                            "code",
                            "name",
                            "indicator",
                            "department"
                        ]
                    ],
                    use_container_width=True
                )