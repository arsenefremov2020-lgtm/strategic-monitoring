import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client

st.set_page_config(
    page_title="Візуалізації",
    layout="wide"
)

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

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


st.title("Візуалізації моніторингу")

df = load_requests()

if df.empty:
    st.warning("Поки що немає даних для візуалізації.")
    st.stop()

st.subheader("Фільтри")

c1, c2, c3 = st.columns(3)

with c1:
    years = sorted(df["year"].dropna().astype(int).unique().tolist())
    selected_year = st.selectbox("Рік", ["Усі"] + years)

with c2:
    departments = sorted(df["department"].dropna().astype(str).unique().tolist())
    selected_department = st.selectbox("Департамент", ["Усі"] + departments)

with c3:
    statuses = sorted(df["approval_status"].dropna().astype(str).unique().tolist())
    selected_status = st.selectbox("Статус погодження", ["Усі"] + statuses)

filtered = df.copy()

if selected_year != "Усі":
    filtered = filtered[filtered["year"].astype(int) == int(selected_year)]

if selected_department != "Усі":
    filtered = filtered[filtered["department"].astype(str) == selected_department]

if selected_status != "Усі":
    filtered = filtered[filtered["approval_status"].astype(str) == selected_status]

st.divider()

total = len(filtered)
approved = len(filtered[filtered["approval_status"] == "Погоджено"])
waiting = len(filtered[filtered["approval_status"] == "Очікує погодження"])
returned = len(filtered[filtered["approval_status"] == "Повернуто на доопрацювання"])

m1, m2, m3, m4 = st.columns(4)

m1.metric("Усього заявок", total)
m2.metric("Погоджено", approved)
m3.metric("Очікує погодження", waiting)
m4.metric("Повернуто", returned)

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Заявки за статусом погодження")

    status_count = (
        filtered
        .groupby("approval_status")
        .size()
        .reset_index(name="Кількість")
    )

    fig_status = px.bar(
        status_count,
        x="approval_status",
        y="Кількість",
        text="Кількість",
        labels={
            "approval_status": "Статус погодження",
            "Кількість": "Кількість заявок"
        }
    )

    st.plotly_chart(fig_status, use_container_width=True)

with right:
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
            "quarter": "Квартал",
            "Кількість": "Кількість заявок"
        }
    )

    st.plotly_chart(fig_quarter, use_container_width=True)

st.divider()

st.subheader("Заявки за департаментами")

department_count = (
    filtered
    .groupby("department")
    .size()
    .reset_index(name="Кількість")
    .sort_values("Кількість", ascending=False)
)

fig_department = px.bar(
    department_count,
    x="department",
    y="Кількість",
    text="Кількість",
    labels={
        "department": "Департамент",
        "Кількість": "Кількість заявок"
    }
)

st.plotly_chart(fig_department, use_container_width=True)

st.divider()

st.subheader("Таблиця моніторингових даних")

show_cols = [
    "id",
    "year",
    "quarter",
    "department",
    "strat_code",
    "status",
    "numeric_value",
    "approval_status",
    "responsible_person",
    "submitted_at"
]

available_cols = [col for col in show_cols if col in filtered.columns]

st.dataframe(
    filtered[available_cols],
    use_container_width=True,
    hide_index=True
)
