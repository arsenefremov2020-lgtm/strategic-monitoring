import streamlit as st
import pandas as pd
from supabase import create_client
from html import escape

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

st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 1.5rem;
        max-width: 1500px;
    }

    div[data-testid="stExpander"] {
        border: none;
        box-shadow: none;
        background: transparent;
        margin-bottom: 14px;
    }

    div[data-testid="stExpander"] details {
        border: none;
    }

    div[data-testid="stExpander"] summary {
        padding: 0 !important;
        background: transparent !important;
        border: none !important;
    }

    div[data-testid="stExpander"] summary p {
        display: none;
    }

    .goal-card {
        background: linear-gradient(90deg, #1d4ed8, #0f55e8);
        color: white;
        padding: 18px 22px;
        border-radius: 12px;
        font-weight: 800;
        margin: 10px 0 12px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 20px;
        box-shadow: 0 6px 16px rgba(29,78,216,0.18);
    }

    .goal-title {
        font-size: 17px;
        line-height: 1.35;
    }

    .goal-meta {
        font-size: 14px;
        line-height: 1.55;
        text-align: right;
        min-width: 130px;
    }

    .task-card {
        background: linear-gradient(90deg, #1f2937, #374151);
        color: white;
        padding: 15px 18px;
        border-radius: 10px 10px 0 0;
        font-weight: 750;
        margin-top: 16px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 18px;
    }

    .task-title {
        font-size: 15px;
        line-height: 1.4;
    }

    .task-meta {
        font-size: 14px;
        min-width: 110px;
        text-align: right;
    }

    .section-box {
        border: 1px solid #d6dce8;
        border-top: none;
        border-radius: 0 0 10px 10px;
        padding: 16px 16px 18px 16px;
        margin-bottom: 18px;
        background: white;
    }

    .section-title {
        font-size: 16px;
        font-weight: 800;
        color: #111827;
        margin: 12px 0 12px 0;
    }

    .table-scroll {
        overflow-x: auto;
        width: 100%;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        margin-bottom: 18px;
        background: white;
    }

    table.custom-table {
        min-width: 1850px;
        border-collapse: collapse;
        table-layout: fixed;
        font-size: 13px;
    }

    table.custom-table th {
        background-color: #e9eef7;
        color: #111827;
        padding: 10px;
        border: 1px solid #d1d5db;
        text-align: left;
        vertical-align: top;
        white-space: normal;
        word-wrap: break-word;
        font-weight: 800;
    }

    table.custom-table td {
        padding: 10px;
        border: 1px solid #d1d5db;
        vertical-align: top;
        white-space: normal;
        word-wrap: break-word;
        overflow-wrap: break-word;
        line-height: 1.45;
    }

    table.custom-table tr:nth-child(even) {
        background-color: #f8fafc;
    }

    table.custom-table tr:nth-child(odd) {
        background-color: #ffffff;
    }

    .col-code { width: 95px; }
    .col-name { width: 330px; }
    .col-indicator { width: 330px; }
    .col-unit { width: 170px; }
    .col-year { width: 125px; }
    .col-quarter { width: 125px; }
    .col-department { width: 130px; }

    .note-box {
        border: 1px solid #d6dce8;
        border-radius: 8px;
        padding: 12px 16px;
        background: #f8fafc;
        color: #374151;
        margin-top: 18px;
        font-size: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True
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
    response = (
        supabase
        .table("monitoring_requests")
        .select("*")
        .execute()
    )

    if not response.data:
        return pd.DataFrame()

    return pd.DataFrame(response.data)


def clean_value(value):
    if pd.isna(value) or str(value) == "None":
        return ""
    return escape(str(value))


def render_table(df, min_width=1850):
    if df.empty:
        st.info("Дані відсутні.")
        return

    html = f"""
    <div class="table-scroll">
    <table class="custom-table" style="min-width:{min_width}px;">
    <thead>
    <tr>
    """

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

        html += f"<th class='{css_class}'>{escape(str(col))}</th>"

    html += "</tr></thead><tbody>"

    for _, row in df.iterrows():
        html += "<tr>"
        for col in df.columns:
            html += f"<td>{clean_value(row[col])}</td>"
        html += "</tr>"

    html += "</tbody></table></div>"

    st.markdown(html, unsafe_allow_html=True)


def indicator_table(data):
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

    show_cols = [
        "Індикатор",
        "Одиниця виміру",
        "Базове значення 2021",
        "Звіт 2024",
        "Очікуване 2025",
        "План 2026",
        "План 2027",
        "План 2028"
    ]

    render_table(renamed[show_cols], min_width=1300)


df = load_strat_matrix()
monitoring_df = load_monitoring()

approved = pd.DataFrame()

selected_year = 2026

if not monitoring_df.empty:
    approved = monitoring_df[
        (monitoring_df["approval_status"] == "Погоджено")
    ].copy()

quarter_data = {}

if not approved.empty:
    for _, row in approved.iterrows():
        key = str(row["strat_code"]).strip()
        year = str(row["year"]).strip()
        q = str(row["quarter"]).strip()

        quarter_data.setdefault(key, {})
        quarter_data[key][f"{year}_{q}"] = row["numeric_value"]


st.title("Стратегічний план")

top_left, top_right = st.columns([3, 1])

with top_right:
    st.page_link(
        "pages/1_Моніторинг_виконання.py",
        label="Внесення даних моніторингу",
        icon="🖊️"
    )

f1, f2 = st.columns(2)

departments = sorted(df["department"].dropna().astype(str).unique())

with f1:
    selected_dep = st.selectbox("Департамент", ["Усі"] + departments)

with f2:
    selected_year = st.selectbox("Рік моніторингу", [2026, 2027, 2028])

st.markdown("")

goals = df[df["object_type"] == "goal"]

for _, goal in goals.iterrows():
    goal_code = str(goal["code"])
    goal_name = str(goal["name"])

    goal_rows = df[df["code"].astype(str).str.startswith(goal_code)]

    tasks = goal_rows[goal_rows["object_type"] == "task"].copy()
    measures_all = goal_rows[goal_rows["object_type"] == "measure"].copy()

    tasks_count = len(tasks)
    measures_count = len(measures_all)

    goal_label = (
        f"🔽 {goal_code} {goal_name}     "
        f"Завдань — {tasks_count} | Заходів — {measures_count}"
    )

    with st.expander(goal_label, expanded=False):

        st.markdown(
            f"""
            <div class="goal-card">
                <div class="goal-title">{escape(goal_code)} {escape(goal_name)}</div>
                <div class="goal-meta">
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
            st.markdown('<div class="section-title">Індикатори досягнення стратегічної цілі</div>', unsafe_allow_html=True)
            indicator_table(goal_indicators)

        for _, task in tasks.iterrows():
            task_code = str(task["code"])
            task_name = str(task["name"])

            task_rows = df[df["code"].astype(str).str.startswith(task_code)]
            task_measures = task_rows[task_rows["object_type"] == "measure"].copy()

            if selected_dep != "Усі":
                task_measures_for_count = task_measures[
                    task_measures["department"].astype(str) == selected_dep
                ]
            else:
                task_measures_for_count = task_measures

            task_measures_count = len(task_measures_for_count)

            task_label = f"▶ {task_code} {task_name}     Заходів — {task_measures_count}"

            with st.expander(task_label, expanded=False):

                st.markdown(
                    f"""
                    <div class="task-card">
                        <div class="task-title">{escape(task_code)} {escape(task_name)}</div>
                        <div class="task-meta">Заходів — {task_measures_count}</div>
                    </div>
                    <div class="section-box">
                    """,
                    unsafe_allow_html=True
                )

                task_indicators = df[
                    (df["object_type"] == "task_indicator") &
                    (df["code"].astype(str) == task_code)
                ].copy()

                if not task_indicators.empty:
                    st.markdown('<div class="section-title">Індикатори досягнення завдання</div>', unsafe_allow_html=True)
                    indicator_table(task_indicators)

                measures = task_measures.copy()

                if selected_dep != "Усі":
                    measures = measures[
                        measures["department"].astype(str) == selected_dep
                    ]

                if not measures.empty:
                    for q in ["I", "II", "III", "IV"]:
                        measures[f"{selected_year}_{q}"] = measures["code"].apply(
                            lambda x: quarter_data.get(str(x).strip(), {}).get(f"{selected_year}_{q}", "")
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
                        f"{selected_year}_I": f"{selected_year} I квартал",
                        f"{selected_year}_II": f"{selected_year} II квартал",
                        f"{selected_year}_III": f"{selected_year} III квартал",
                        f"{selected_year}_IV": f"{selected_year} IV квартал",
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

                    st.markdown('<div class="section-title">Заходи</div>', unsafe_allow_html=True)
                    render_table(measures[show_cols], min_width=2100)
                else:
                    st.info("Заходів за цим завданням не знайдено.")

                st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
    """
    <div class="note-box">
        У квартальних колонках відображаються фактичні значення з моніторингу, якщо заявка погоджена адміністратором.
    </div>
    """,
    unsafe_allow_html=True
)
