import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client

st.set_page_config(
    page_title="Картка заходу",
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
        "department": data.iloc[:, 17],
        "start_date_plan": data.iloc[:, 22],
        "end_date_plan": data.iloc[:, 23],
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


def clean(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value)


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


st.title("Картка заходу")

strat_df = load_strat_matrix()
requests_df = load_requests()

measures_df = strat_df[strat_df["object_type"] == "measure"].copy()
goals_df = strat_df[strat_df["object_type"] == "goal"].copy()
tasks_df = strat_df[strat_df["object_type"] == "task"].copy()

goal_map = goals_df.set_index("code")["name"].to_dict()
task_map = tasks_df.set_index("code")["name"].to_dict()

if measures_df.empty:
    st.warning("Заходів у стратегічній матриці не знайдено.")
    st.stop()

measures_df["label"] = (
    measures_df["code"].astype(str)
    + " — "
    + measures_df["name"].astype(str)
)

selected_label = st.selectbox(
    "Оберіть захід",
    measures_df["label"].tolist()
)

selected_code = selected_label.split(" — ")[0].strip()

measure = measures_df[
    measures_df["code"].astype(str).str.strip() == selected_code
].iloc[0]

goal_code = get_goal_code(selected_code)
task_code = get_task_code(selected_code)

st.subheader(f"{selected_code} — {clean(measure['name'])}")

m1, m2, m3 = st.columns(3)

with m1:
    st.metric("Стратегічна ціль", goal_code)
    st.caption(clean(goal_map.get(goal_code, "")))

with m2:
    st.metric("Завдання", task_code)
    st.caption(clean(task_map.get(task_code, "")))

with m3:
    st.metric("Департамент", clean(measure["department"]))

st.divider()

st.subheader("Паспорт заходу")

passport = pd.DataFrame([{
    "Код заходу": clean(measure["code"]),
    "Назва заходу": clean(measure["name"]),
    "Індикатор": clean(measure["indicator"]),
    "Одиниця виміру": clean(measure["unit"]),
    "Базове значення 2021": clean(measure["base_2021"]),
    "Звіт 2024": clean(measure["fact_2024"]),
    "Очікуване 2025": clean(measure["expected_2025"]),
    "План 2026": clean(measure["target_2026"]),
    "План 2027": clean(measure["target_2027"]),
    "План 2028": clean(measure["target_2028"]),
    "Початкова дата виконання": clean(measure["start_date_plan"]),
    "Кінцева дата виконання": clean(measure["end_date_plan"]),
    "Департамент": clean(measure["department"])
}])

st.dataframe(
    passport,
    use_container_width=True,
    hide_index=True
)

st.divider()

st.subheader("Планові та звітні значення за роками")

annual_df = pd.DataFrame({
    "Рік": ["2021", "2024", "2025", "2026", "2027", "2028"],
    "Тип": [
        "Базове значення",
        "Звіт",
        "Очікуване",
        "План",
        "План",
        "План"
    ],
    "Значення": [
        clean(measure["base_2021"]),
        clean(measure["fact_2024"]),
        clean(measure["expected_2025"]),
        clean(measure["target_2026"]),
        clean(measure["target_2027"]),
        clean(measure["target_2028"])
    ]
})

st.dataframe(
    annual_df,
    use_container_width=True,
    hide_index=True
)

chart_df = annual_df.copy()
chart_df["Числове значення"] = pd.to_numeric(
    chart_df["Значення"],
    errors="coerce"
)

if chart_df["Числове значення"].notna().sum() > 0:
    fig_annual = px.line(
        chart_df.dropna(subset=["Числове значення"]),
        x="Рік",
        y="Числове значення",
        markers=True,
        text="Числове значення",
        title="Динаміка планових/звітних значень"
    )

    st.plotly_chart(
        fig_annual,
        use_container_width=True
    )
else:
    st.info("Для цього заходу немає числових річних значень для побудови графіка.")

st.divider()

st.subheader("Квартальний моніторинг")

if requests_df.empty:
    st.info("Для цього заходу ще немає моніторингових заявок.")
    st.stop()

for col in [
    "year",
    "quarter",
    "department",
    "strat_code",
    "status",
    "numeric_value",
    "approval_status",
    "progress_text",
    "risks",
    "responsible_person",
    "submitted_at",
    "admin_comment",
    "file_names"
]:
    if col not in requests_df.columns:
        requests_df[col] = ""

measure_requests = requests_df[
    requests_df["strat_code"].astype(str).str.strip() == selected_code
].copy()

if measure_requests.empty:
    st.info("Для цього заходу ще немає моніторингових заявок.")
    st.stop()

f1, f2 = st.columns(2)

with f1:
    years = sorted(measure_requests["year"].dropna().astype(int).unique().tolist())
    selected_year = st.selectbox("Рік моніторингу", ["Усі"] + years)

with f2:
    selected_approval = st.selectbox(
        "Статус погодження",
        [
            "Усі",
            "Очікує погодження",
            "Погоджено",
            "Повернуто на доопрацювання"
        ]
    )

filtered_requests = measure_requests.copy()

if selected_year != "Усі":
    filtered_requests = filtered_requests[
        filtered_requests["year"].astype(int) == int(selected_year)
    ]

if selected_approval != "Усі":
    filtered_requests = filtered_requests[
        filtered_requests["approval_status"].astype(str) == str(selected_approval)
    ]

st.dataframe(
    filtered_requests[
        [
            "year",
            "quarter",
            "numeric_value",
            "status",
            "approval_status",
            "progress_text",
            "risks",
            "responsible_person",
            "submitted_at",
            "admin_comment",
            "file_names"
        ]
    ],
    use_container_width=True,
    hide_index=True
)

approved = filtered_requests[
    filtered_requests["approval_status"] == "Погоджено"
].copy()

if approved.empty:
    st.info("Погоджених квартальних даних для графіка ще немає.")
else:
    quarter_order = ["I", "II", "III", "IV"]

    approved["quarter"] = pd.Categorical(
        approved["quarter"],
        categories=quarter_order,
        ordered=True
    )

    approved["numeric_value_num"] = pd.to_numeric(
        approved["numeric_value"],
        errors="coerce"
    )

    chart_quarter = approved.dropna(subset=["numeric_value_num"]).copy()

    if chart_quarter.empty:
        st.info("Погоджені квартальні значення не є числовими, тому графік не побудовано.")
    else:
        chart_quarter = chart_quarter.sort_values(["year", "quarter"])

        chart_quarter["Період"] = (
            chart_quarter["year"].astype(str)
            + " "
            + chart_quarter["quarter"].astype(str)
            + " квартал"
        )

        fig_quarter = px.line(
            chart_quarter,
            x="Період",
            y="numeric_value_num",
            markers=True,
            text="numeric_value_num",
            title="Динаміка погоджених квартальних значень"
        )

        st.plotly_chart(
            fig_quarter,
            use_container_width=True
        )

st.divider()

st.subheader("Останній погоджений статус")

latest = requests_df[
    (requests_df["strat_code"].astype(str).str.strip() == selected_code) &
    (requests_df["approval_status"] == "Погоджено")
].copy()

if latest.empty:
    st.warning("Погодженого статусу для цього заходу ще немає.")
else:
    latest = latest.sort_values("submitted_at").tail(1).iloc[0]

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Рік", clean(latest["year"]))

    with c2:
        st.metric("Квартал", clean(latest["quarter"]))

    with c3:
        st.metric("Статус виконання", clean(latest["status"]))

    st.text_area(
        "Останній опис прогресу",
        value=clean(latest["progress_text"]),
        disabled=True,
        height=100
    )

    st.text_area(
        "Останні ризики / проблеми / відхилення",
        value=clean(latest["risks"]),
        disabled=True,
        height=100
    )
