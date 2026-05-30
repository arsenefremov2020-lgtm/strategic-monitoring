import streamlit as st
import pandas as pd
from supabase import create_client
from html import escape

st.set_page_config(page_title="Стратегічний план", layout="wide")

FILE_PATH = "Під моніторинг СП.xlsx"
SHEET_NAME = "Страт_матриця"

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

st.markdown("""
<style>
.stApp {
    background: linear-gradient(180deg, #f6f8fb 0%, #eef2f7 100%);
}

.main .block-container {
    max-width: 1550px;
    padding-top: 1.2rem;
}

.ministry-label {
    text-align: right;
    color: #475569;
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 8px;
}

.header-box {
    background: white;
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 18px;
    box-shadow: 0 4px 14px rgba(15,23,42,0.05);
}

.header-title {
    font-size: 30px;
    font-weight: 850;
    color: #0f172a;
    margin-bottom: 8px;
}

.header-subtitle {
    font-size: 15px;
    color: #475569;
    line-height: 1.5;
}

.cta-box {
    background: linear-gradient(90deg, #15803d, #16a34a);
    color: white;
    border-radius: 14px;
    padding: 20px 24px;
    margin: 12px 0 22px 0;
    box-shadow: 0 6px 18px rgba(22,163,74,0.22);
}

.cta-title {
    font-size: 22px;
    font-weight: 850;
    margin-bottom: 6px;
}

.cta-text {
    font-size: 15px;
    opacity: 0.96;
}

div[data-testid="stPageLink"] a {
    background: linear-gradient(90deg, #15803d, #16a34a) !important;
    color: white !important;
    border-radius: 12px !important;
    padding: 14px 18px !important;
    font-weight: 800 !important;
    text-decoration: none !important;
    border: none !important;
    width: 100%;
    justify-content: center;
}

.info-grid {
    display: grid;
    grid-template-columns: 1.2fr 1fr;
    gap: 14px;
    margin-bottom: 20px;
}

.info-card {
    background: white;
    border: 1px solid #d8dee9;
    border-radius: 12px;
    padding: 16px 18px;
    color: #1f2937;
    box-shadow: 0 3px 10px rgba(15,23,42,0.04);
}

.info-card-title {
    font-size: 16px;
    font-weight: 850;
    margin-bottom: 8px;
    color: #0f172a;
}

.legend-item {
    margin-bottom: 6px;
    font-size: 14px;
}

div[data-testid="stExpander"] {
    border: none;
    margin-bottom: 14px;
}

div[data-testid="stExpander"] > details > summary {
    background: linear-gradient(90deg, #1d4ed8, #0f55e8) !important;
    color: white !important;
    border-radius: 12px !important;
    padding: 18px 22px !important;
    font-weight: 800 !important;
    box-shadow: 0 6px 16px rgba(29,78,216,0.18);
}

div[data-testid="stExpander"] > details > summary p {
    color: white !important;
    font-size: 16px !important;
    font-weight: 800 !important;
}

div[data-testid="stExpander"] div[data-testid="stExpander"] > details > summary {
    background: linear-gradient(90deg, #1f2937, #374151) !important;
    color: white !important;
    border-radius: 10px !important;
    padding: 15px 18px !important;
    font-weight: 750 !important;
    box-shadow: none;
}

div[data-testid="stExpander"] div[data-testid="stExpander"] > details > summary p {
    color: white !important;
    font-size: 15px !important;
    font-weight: 750 !important;
}

.section-title {
    font-size: 16px;
    font-weight: 800;
    color: #111827;
    margin: 18px 0 12px 0;
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
    min-width: 2200px;
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

td.pending-cell {
    background-color: #fff3cd !important;
    font-weight: 800;
    color: #7a4d00;
}

.col-code { width: 95px; }
.col-name { width: 360px; }
.col-indicator { width: 360px; }
.col-unit { width: 170px; }
.col-year { width: 130px; }
.col-quarter { width: 130px; }
.col-department { width: 130px; }

.note-box {
    border: 1px solid #d6dce8;
    border-radius: 8px;
    padding: 12px 16px;
    background: #ffffff;
    color: #374151;
    margin-top: 18px;
    font-size: 14px;
}

.footer {
    text-align: center;
    color: #64748b;
    font-size: 13px;
    margin-top: 50px;
    padding: 20px 0 10px 0;
    border-top: 1px solid #d8dee9;
}
</style>
""", unsafe_allow_html=True)


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
    response = supabase.table("monitoring_requests").select("*").execute()
    if not response.data:
        return pd.DataFrame()
    return pd.DataFrame(response.data)


def clean_value(value):
    if pd.isna(value) or str(value) == "None":
        return ""
    return escape(str(value))


def render_table(df, pending_cells=None, min_width=2200):
    if df.empty:
        st.info("Дані відсутні.")
        return

    if pending_cells is None:
        pending_cells = set()

    html = f"""
    <div class="table-scroll">
    <table class="custom-table" style="min-width:{min_width}px;">
    <thead><tr>
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
        code = str(row.get("Код", "")).strip()
        html += "<tr>"

        for col in df.columns:
            value = clean_value(row[col])
            cell_class = ""

            if (code, col) in pending_cells:
                cell_class = "pending-cell"

            html += f"<td class='{cell_class}'>{value}</td>"

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

    render_table(renamed[show_cols], min_width=1350)


df = load_strat_matrix()
monitoring_df = load_monitoring()

quarter_data = {}
pending_cells_global = set()

if not monitoring_df.empty:
    visible_monitoring = monitoring_df[
        monitoring_df["approval_status"].isin(["Погоджено", "Очікує погодження"])
    ].copy()

    if not visible_monitoring.empty:
        visible_monitoring = visible_monitoring.sort_values("submitted_at")

        for _, row in visible_monitoring.iterrows():
            key = str(row["strat_code"]).strip()
            year = str(row["year"]).strip()
            q = str(row["quarter"]).strip()
            approval = str(row["approval_status"]).strip()

            quarter_key = f"{year}_{q}"

            quarter_data.setdefault(key, {})
            quarter_data[key][quarter_key] = {
                "value": row["numeric_value"],
                "approval": approval
            }


total_measures = len(df[df["object_type"] == "measure"])
submitted_count = 0
approved_count = 0
waiting_count = 0

if not monitoring_df.empty:
    submitted_count = len(monitoring_df)
    approved_count = len(monitoring_df[monitoring_df["approval_status"] == "Погоджено"])
    waiting_count = len(monitoring_df[monitoring_df["approval_status"] == "Очікує погодження"])


st.markdown(
    """
    <div class="ministry-label">
    Міністерство економіки, довкілля та сільського господарства України
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="header-box">
        <div class="header-title">Моніторинг виконання стратегічного плану</div>
        <div class="header-subtitle">
            Інтерактивна демо-версія системи для перегляду стратегічного плану, внесення квартального моніторингу,
            погодження даних та аналізу прогресу виконання.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="cta-box">
        <div class="cta-title">Внесення даних моніторингу виконання Стратегічного плану</div>
        <div class="cta-text">
            Подайте квартальні дані щодо заходів свого департаменту, додайте опис прогресу, ризики та підтвердні файли.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.page_link(
    "pages/1_Моніторинг_виконання.py",
    label="Перейти до внесення моніторингових даних",
    icon="🖊️"
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Заходів у стратегічному плані", total_measures)
k2.metric("Поданих заявок", submitted_count)
k3.metric("Погоджено", approved_count)
k4.metric("Очікує погодження", waiting_count)

st.markdown(
    """
    <div class="info-grid">
        <div class="info-card">
            <div class="info-card-title">Як працювати з головною сторінкою</div>
            <div>
                1. Оберіть департамент і рік моніторингу.<br>
                2. Натисніть на синій блок стратегічної цілі.<br>
                3. Відкрийте темно-сірий блок завдання.<br>
                4. Перегляньте індикатори, заходи, планові та квартальні значення.<br>
                5. Для внесення нових даних перейдіть за зеленою кнопкою вище.
            </div>
        </div>
        <div class="info-card">
            <div class="info-card-title">Легенда квартальних даних</div>
            <div class="legend-item">🟨 Жовта комірка — дані подані, але ще очікують погодження адміністратора.</div>
            <div class="legend-item">⚪ Звичайна комірка — дані погоджені та враховані в моніторингу.</div>
            <div class="legend-item">🔴 Повернуті на доопрацювання дані не відображаються у стратегічному плані.</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

f1, f2 = st.columns(2)

departments = sorted(df["department"].dropna().astype(str).unique())

with f1:
    selected_dep = st.selectbox("Департамент", ["Усі"] + departments)

with f2:
    selected_year = st.selectbox("Рік моніторингу", [2026, 2027, 2028])

st.subheader("Стратегічний план")

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
        f"{goal_code} {goal_name}     "
        f"｜ Завдань — {tasks_count} ｜ Заходів — {measures_count}"
    )

    with st.expander(goal_label, expanded=False):

        goal_indicators = df[
            (df["object_type"] == "goal_indicator") &
            (df["code"].astype(str) == goal_code)
        ].copy()

        if not goal_indicators.empty:
            st.markdown(
                '<div class="section-title">Індикатори досягнення стратегічної цілі</div>',
                unsafe_allow_html=True
            )
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

            task_label = (
                f"{task_code} {task_name}     "
                f"｜ Заходів — {task_measures_count}"
            )

            with st.expander(task_label, expanded=False):

                task_indicators = df[
                    (df["object_type"] == "task_indicator") &
                    (df["code"].astype(str) == task_code)
                ].copy()

                if not task_indicators.empty:
                    st.markdown(
                        '<div class="section-title">Індикатори досягнення завдання</div>',
                        unsafe_allow_html=True
                    )
                    indicator_table(task_indicators)

                measures = task_measures.copy()

                if selected_dep != "Усі":
                    measures = measures[
                        measures["department"].astype(str) == selected_dep
                    ]

                if measures.empty:
                    st.info("Заходів за цим завданням не знайдено.")
                    continue

                pending_cells = set()

                for q in ["I", "II", "III", "IV"]:
                    col_key = f"{selected_year}_{q}"
                    col_name = f"{selected_year} {q} квартал"

                    def get_q_value(code):
                        code = str(code).strip()
                        item = quarter_data.get(code, {}).get(col_key, None)

                        if item is None:
                            return ""

                        if item["approval"] == "Очікує погодження":
                            return item["value"]

                        if item["approval"] == "Погоджено":
                            return item["value"]

                        return ""

                    measures[col_key] = measures["code"].apply(get_q_value)

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

                for _, measure_row in measures.iterrows():
                    code = str(measure_row["Код"]).strip()

                    for q in ["I", "II", "III", "IV"]:
                        col_key = f"{selected_year}_{q}"
                        col_name = f"{selected_year} {q} квартал"

                        item = quarter_data.get(code, {}).get(col_key, None)

                        if item is not None and item["approval"] == "Очікує погодження":
                            pending_cells.add((code, col_name))

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

                st.markdown(
                    '<div class="section-title">Заходи</div>',
                    unsafe_allow_html=True
                )

                render_table(
                    measures[show_cols],
                    pending_cells=pending_cells,
                    min_width=2200
                )

st.markdown(
    """
    <div class="note-box">
        У квартальних колонках відображаються погоджені значення моніторингу. 
        Значення, які очікують погодження, підсвічуються жовтим кольором. 
        Дані, повернуті на доопрацювання, не відображаються в основному стратегічному плані.
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="footer">
        Розроблено департаментом стратегічного планування та макроекономічного прогнозування
    </div>
    """,
    unsafe_allow_html=True
)
