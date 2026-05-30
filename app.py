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
        "department": data.iloc[:, 17]
    })

    result = result.dropna(subset=["code"])
    result["code"] = result["code"].astype(str).str.strip()
    result["type_marker"] = result["type_marker"].astype(str).str.strip()

    def classify(row):
        marker = str(row["type_marker"]).lower()
        code = str(row["code"]).strip()
        dots = code.count(".")

        if "стратегічна ціль" in marker:
            return "goal"
        if "завдання" in marker:
            return "task"
        if dots == 1:
            return "goal_indicator"
        if dots == 2:
            return "task_indicator"
        if dots >= 3:
            return "measure"
        return "other"

    result["object_type"] = result.apply(classify, axis=1)
    return result


def load_monitoring():
    response = supabase.table("monitoring_requests").select("*").execute()
    if not response.data:
        return pd.DataFrame()
    return pd.DataFrame(response.data)


def render_table(df):
    if df.empty:
        st.info("Дані відсутні.")
        return

    html = """
    <style>
    .table-scroll {
        overflow-x: auto;
        width: 100%;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        margin-bottom: 16px;
    }

    table.custom-table {
        min-width: 1800px;
        border-collapse: collapse;
        table-layout: fixed;
        font-size: 13px;
    }

    table.custom-table th {
        background-color: #e9eef7;
        color: #1f2937;
        padding: 8px;
        border: 1px solid #d1d5db;
        text-align: left;
        vertical-align: top;
        white-space: normal;
        word-wrap: break-word;
    }

    table.custom-table td {
        padding: 8px;
        border: 1px solid #d1d5db;
        vertical-align: top;
        white-space: normal;
        word-wrap: break-word;
        overflow-wrap: break-word;
    }

    table.custom-table tr:nth-child(even) {
        background-color: #f8fafc;
    }

    table.custom-table tr:nth-child(odd) {
        background-color: #ffffff;
    }

    .col-code { width: 90px; }
    .col-name { width: 360px; }
    .col-indicator { width: 360px; }
    .col-unit { width: 170px; }
    .col-year { width: 130px; }
    .col-quarter { width: 130px; }
    .col-department { width: 130px; }
    </style>
    """

    html += "<div class='table-scroll'>"
    html += "<table class='custom-table'><thead><tr>"

    for col in df.columns:
        css_class = "col-year"

        if col == "Код":
            css_class = "col-code"
        elif col == "Захід":
            css_class = "col-name"
        elif col == "Індикатор":
            css_class = "col-indicator"
        elif col == "Одиниця виміру":
            css_class = "col-unit"
        elif "квартал" in col:
            css_class = "col-quarter"
        elif "Департамент" in col:
            css_class = "col-department"

        html += f"<th class='{css_class}'>{col}</th>"

    html += "</tr></thead><tbody>"

    for _, row in df.iterrows():
        html += "<tr>"
        for col in df.columns:
            value = row[col]
            if pd.isna(value) or value == "None":
                value = ""
            html += f"<td>{value}</td>"
        html += "</tr>"

    html += "</tbody></table></div>"
    st.markdown(html, unsafe_allow_html=True)


def ua_indicator_table(data):
    renamed = data.rename(columns={
        "indicator": "Індикатор",
        "unit": "Одиниця виміру",
        "base_2021": "Базове значення 2021",
        "fact_2024": "Звіт 2024",
        "expected_2025": "Очікуване 2025",
        "target_2026": "План 2026",
        "target_2027": "План 2027",
        "target_2028": "План 2028"
    })

    render_table(renamed[
        [
            "Індикатор",
            "Одиниця виміру",
            "Базове значення 2021",
            "Звіт 2024",
            "Очікуване 2025",
            "План 2026",
            "План 2027",
            "План 2028"
        ]
    ])


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

departments = sorted(df["department"].dropna().astype(str).unique())

f1, f2 = st.columns(2)

with f1:
    selected_dep = st.selectbox("Департамент", ["Усі"] + departments)

with f2:
    selected_year = st.selectbox("Рік моніторингу", [2026, 2027, 2028])

approved = pd.DataFrame()

if not monitoring_df.empty:
    approved = monitoring_df[
        (monitoring_df["approval_status"] == "Погоджено") &
        (monitoring_df["year"] == selected_year)
    ].copy()

quarter_data = {}

if not approved.empty:
    for _, row in approved.iterrows():
        key = str(row["strat_code"]).strip()
        q = str(row["quarter"]).strip()
        quarter_data.setdefault(key, {})
        quarter_data[key][q] = row["numeric_value"]

st.subheader("Стратегічний план")

goals = df[df["object_type"] == "goal"]

for _, goal in goals.iterrows():
    goal_code = str(goal["code"])
    goal_name = str(goal["name"])

    goal_rows = df[df["code"].astype(str).str.startswith(goal_code)]

    tasks_count = goal_rows[goal_rows["object_type"] == "task"].shape[0]
    measures_count = goal_rows[goal_rows["object_type"] == "measure"].shape[0]

    with st.expander(f"{goal_code}", expanded=False):

        st.markdown(
            f"""
            <div style="
                background-color:#1d4ed8;
                color:white;
                padding:14px 18px;
                border-radius:10px;
                font-weight:700;
                margin-bottom:12px;
                display:flex;
                justify-content:space-between;
                align-items:center;">
                <div>{goal_code} {goal_name}</div>
                <div style="text-align:right; font-size:13px; line-height:1.5;">
                    <div>Завдань — {tasks_count}</div>
                    <div>Заходів — {measures_count}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        goal_indicators = df[
            (df["object_type"] == "goal_indicator") &
            (df["code"].astype(str) == goal_code)
        ].copy()

        if not goal_indicators.empty:
            st.markdown("**Індикатори досягнення стратегічної цілі**")
            ua_indicator_table(goal_indicators)

        tasks = goal_rows[goal_rows["object_type"] == "task"]

        for _, task in tasks.iterrows():
            task_code = str(task["code"])
            task_name = str(task["name"])

            task_rows = df[df["code"].astype(str).str.startswith(task_code)]
            task_measures_count = task_rows[task_rows["object_type"] == "measure"].shape[0]

            with st.expander(f"{task_code}", expanded=False):

                st.markdown(
                    f"""
                    <div style="
                        background-color:#374151;
                        color:white;
                        padding:12px 16px;
                        border-radius:8px;
                        font-weight:600;
                        margin-bottom:12px;
                        display:flex;
                        justify-content:space-between;
                        align-items:center;">
                        <div>{task_code} {task_name}</div>
                        <div style="text-align:right; font-size:13px;">
                            Заходів — {task_measures_count}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                task_indicators = df[
                    (df["object_type"] == "task_indicator") &
                    (df["code"].astype(str) == task_code)
                ].copy()

                if not task_indicators.empty:
                    st.markdown("**Індикатори досягнення завдання**")
                    ua_indicator_table(task_indicators)

                measures = df[
                    (df["object_type"] == "measure") &
                    (df["code"].astype(str).str.startswith(task_code))
                ].copy()

                if selected_dep != "Усі":
                    measures = measures[
                        measures["department"].astype(str) == selected_dep
                    ]

                if measures.empty:
                    st.info("Заходів за цим завданням не знайдено.")
                    continue

                for q in ["I", "II", "III", "IV"]:
                    measures[f"{selected_year} Q{q}"] = measures["code"].apply(
                        lambda x: quarter_data.get(str(x).strip(), {}).get(q, "")
                    )

                measures = measures.rename(columns={
                    "code": "Код",
                    "name": "Захід",
                    "indicator": "Індикатор",
                    "unit": "Одиниця виміру",
                    "base_2021": "Базове значення 2021",
                    "fact_2024": "Звіт 2024",
                    "expected_2025": "Очікуване 2025",
                    "target_2026": "План 2026",
                    f"{selected_year} QI": f"{selected_year} I квартал",
                    f"{selected_year} QII": f"{selected_year} II квартал",
                    f"{selected_year} QIII": f"{selected_year} III квартал",
                    f"{selected_year} QIV": f"{selected_year} IV квартал",
                    "target_2027": "План 2027",
                    "target_2028": "План 2028",
                    "department": "Департамент"
                })

                show_cols = [
                    "Код",
                    "Захід",
                    "Індикатор",
                    "Одиниця виміру",
                    "Базове значення 2021",
                    "Звіт 2024",
                    "Очікуване 2025",
                    "План 2026",
                    f"{selected_year} I квартал",
                    f"{selected_year} II квартал",
                    f"{selected_year} III квартал",
                    f"{selected_year} IV квартал",
                    "План 2027",
                    "План 2028",
                    "Департамент"
                ]

                st.markdown("**Заходи**")
                render_table(measures[show_cols])
