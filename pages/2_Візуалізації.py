import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from supabase import create_client

st.set_page_config(
    page_title="Візуалізації",
    layout="wide"
)

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

st.title("Візуалізація моніторингу виконання")

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


df = load_requests()

if df.empty:
    st.warning("Ще немає даних для візуалізації.")
    st.stop()

for col in [
    "approval_status",
    "department",
    "quarter",
    "status",
    "numeric_value",
    "year",
    "risks"
]:
    if col not in df.columns:
        df[col] = ""

df["numeric_value"] = pd.to_numeric(
    df["numeric_value"],
    errors="coerce"
)

st.sidebar.header("Фільтри")

selected_year = st.sidebar.selectbox(
    "Рік",
    ["Усі"] + sorted(
        df["year"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
)

selected_department = st.sidebar.selectbox(
    "Департамент",
    ["Усі"] + sorted(
        df["department"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
)

filtered = df.copy()

if selected_year != "Усі":
    filtered = filtered[
        filtered["year"].astype(str)
        == selected_year
    ]

if selected_department != "Усі":
    filtered = filtered[
        filtered["department"].astype(str)
        == selected_department
    ]

st.subheader("Ключові показники")

k1, k2, k3, k4 = st.columns(4)

with k1:
    st.metric(
        "Усього заявок",
        len(filtered)
    )

with k2:
    st.metric(
        "Погоджено",
        len(
            filtered[
                filtered["approval_status"]
                == "Погоджено"
            ]
        )
    )

with k3:
    st.metric(
        "Очікує погодження",
        len(
            filtered[
                filtered["approval_status"]
                == "Очікує погодження"
            ]
        )
    )

with k4:
    st.metric(
        "Повернуто",
        len(
            filtered[
                filtered["approval_status"]
                == "Повернуто на доопрацювання"
            ]
        )
    )

st.divider()

left, right = st.columns(2)

with left:

    st.subheader("Статуси погодження")

    status_counts = (
        filtered["approval_status"]
        .fillna("Невідомо")
        .value_counts()
    )

    fig, ax = plt.subplots()

    ax.pie(
        status_counts,
        labels=status_counts.index,
        autopct="%1.0f%%"
    )

    st.pyplot(fig)

with right:

    st.subheader("Заявки по департаментах")

    dep_counts = (
        filtered["department"]
        .astype(str)
        .value_counts()
        .sort_values()
    )

    fig, ax = plt.subplots()

    ax.barh(
        dep_counts.index,
        dep_counts.values
    )

    st.pyplot(fig)

st.divider()

c1, c2 = st.columns(2)

with c1:

    st.subheader("Подання по кварталах")

    quarter_counts = (
        filtered["quarter"]
        .fillna("Невідомо")
        .value_counts()
    )

    fig, ax = plt.subplots()

    ax.bar(
        quarter_counts.index,
        quarter_counts.values
    )

    st.pyplot(fig)

with c2:

    st.subheader("Статуси виконання")

    exec_counts = (
        filtered["status"]
        .fillna("Невідомо")
        .value_counts()
    )

    fig, ax = plt.subplots()

    ax.bar(
        exec_counts.index,
        exec_counts.values
    )

    plt.xticks(rotation=20)

    st.pyplot(fig)

st.divider()

st.subheader("Середні фактичні значення по департаментах")

numeric_df = filtered.dropna(
    subset=["numeric_value"]
)

if not numeric_df.empty:

    avg_values = (
        numeric_df
        .groupby("department")["numeric_value"]
        .mean()
        .sort_values()
    )

    fig, ax = plt.subplots()

    ax.barh(
        avg_values.index.astype(str),
        avg_values.values
    )

    st.pyplot(fig)

else:

    st.info(
        "Немає числових даних."
    )

st.divider()

st.subheader("Проблемні заявки")

problem_df = filtered[
    (
        filtered["approval_status"]
        == "Повернуто на доопрацювання"
    )
    |
    (
        filtered["risks"]
        .fillna("")
        .astype(str)
        .str.len()
        > 0
    )
]

if problem_df.empty:

    st.success(
        "Проблемних заявок не знайдено."
    )

else:

    show_cols = [
        "id",
        "department",
        "strat_code",
        "approval_status",
        "status",
        "risks"
    ]

    available = [
        c for c in show_cols
        if c in problem_df.columns
    ]

    st.dataframe(
        problem_df[available],
        use_container_width=True,
        hide_index=True
    )
