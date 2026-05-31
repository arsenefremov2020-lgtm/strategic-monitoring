import streamlit as st
import pandas as pd
from supabase import create_client
from html import escape
from datetime import datetime

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
    background:
        radial-gradient(circle at top right, rgba(37,99,235,0.08), transparent 28%),
        radial-gradient(circle at bottom left, rgba(22,163,74,0.07), transparent 30%),
        linear-gradient(180deg, #f6f8fb 0%, #eef2f7 100%);
}

.stApp::before {
    content: "";
    position: fixed;
    top: -160px;
    right: -120px;
    width: 460px;
    height: 460px;
    border-radius: 50%;
    background: rgba(37, 99, 235, 0.045);
    z-index: 0;
}

.stApp::after {
    content: "";
    position: fixed;
    bottom: -180px;
    left: -120px;
    width: 390px;
    height: 390px;
    border-radius: 50%;
    background: rgba(22, 163, 74, 0.045);
    z-index: 0;
}

.main .block-container {
    max-width: 1550px;
    padding-top: 1.2rem;
    position: relative;
    z-index: 1;
}

.ua-line {
    height: 7px;
    border-radius: 999px;
    background: linear-gradient(90deg, #005BBB 0%, #005BBB 50%, #FFD500 50%, #FFD500 100%);
    margin-bottom: 14px;
}

.ministry-label {
    text-align: right;
    color: #475569;
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 8px;
}

.header-box {
    background: rgba(255,255,255,0.92);
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 18px;
    box-shadow: 0 8px 24px rgba(15,23,42,0.06);
    backdrop-filter: blur(8px);
}

.header-title {
    font-size: 32px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 8px;
}

.header-subtitle {
    font-size: 15px;
    color: #475569;
    line-height: 1.55;
}

.system-status {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-top: 14px;
}

.status-pill {
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 10px;
    padding: 10px 12px;
    font-size: 13px;
    color: #334155;
}

.cta-box {
    background: linear-gradient(90deg, #15803d, #16a34a);
    color: white;
    border-radius: 16px;
    padding: 22px 26px;
    margin: 14px 0 18px 0;
    box-shadow: 0 10px 24px rgba(22,163,74,0.25);
}

.cta-title {
    font-size: 23px;
    font-weight: 900;
    margin-bottom: 6px;
}

.cta-text {
    font-size: 15px;
    opacity: 0.97;
}

div[data-testid="stPageLink"] a {
    background: linear-gradient(90deg, #15803d, #16a34a) !important;
    color: white !important;
    border-radius: 12px !important;
    padding: 15px 20px !important;
    font-weight: 850 !important;
    text-decoration: none !important;
    border: none !important;
    width: 100%;
    justify-content: center;
    box-shadow: 0 6px 14px rgba(22,163,74,0.20);
}

.flow-box {
    background: white;
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 18px;
    margin: 18px 0;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

.flow-title {
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 10px;
}

.flow-steps {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    color: #334155;
    font-size: 14px;
}

.flow-step {
    padding: 8px 12px;
    border-radius: 999px;
    background: #f1f5f9;
    border: 1px solid #d8dee9;
}

.info-grid {
    display: grid;
    grid-template-columns: 1.2fr 1fr;
    gap: 14px;
    margin-bottom: 20px;
}

.info-card {
    background: rgba(255,255,255,0.92);
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 17px 19px;
    color: #1f2937;
    box-shadow: 0 4px 14px rgba(15,23,42,0.045);
}

.info-card-title {
    font-size: 16px;
    font-weight: 900;
    margin-bottom: 8px;
    color: #0f172a;
}

.legend-item {
    margin-bottom: 6px;
    font-size: 14px;
}

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.85);
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

div[data-testid="stExpander"] {
    border: none;
    margin-bottom: 14px;
}

div[data-testid="stExpander"] > details > summary {
    background: linear-gradient(90deg, #1d4ed8, #0f55e8) !important;
    color: white !important;
    border-radius: 13px !important;
    padding: 18px 22px !important;
    font-weight: 850 !important;
    box-shadow: 0 7px 18px rgba(29,78,216,0.20);
}

div[data-testid="stExpander"] > details > summary p {
    color: white !important;
    font-size: 16px !important;
    font-weight: 850 !important;
}

div[data-testid="stExpander"] div[data-testid="stExpander"] > details > summary {
    background: linear-gradient(90deg, #1f2937, #374151) !important;
    color: white !important;
    border-radius: 11px !important;
    padding: 15px 18px !important;
    font-weight: 800 !important;
    box-shadow: none;
}

div[data-testid="stExpander"] div[data-testid="stExpander"] > details > summary p {
    color: white !important;
    font-size: 15px !important;
    font-weight: 800 !important;
}

.section-title {
    font-size: 16px;
    font-weight: 850;
    color: #111827;
    margin: 18px 0 12px 0;
}

.table-scroll {
    overflow-x: auto;
    width: 100%;
    border: 1px solid #d1d5db;
    border-radius: 9px;
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
    font-weight: 850;
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
    font-weight: 850;
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
    border-radius: 10px;
    padding: 13px 17px;
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
    padding: 22px 0 12px 0;
    border-top: 1px solid #d8dee9;
}

.footer strong {
    color: #334155;
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


def get_goal_completion(goal_measures, selected_year, quarter_data):
    if goal_measures.empty:
        return 0

    total = len(goal_measures)
    approved_measures = 0

    for _, row in goal_measures.iterrows():
        code = str(row["code"]).strip()
        has_approved = False

        for q in ["I", "II", "III", "IV"]:
            item = quarter_data.get(code, {}).get(f"{selected_year}_{q}", None)
            if item is not None and item["approval"] == "Погоджено":
                has_approved = True

        if has_approved:
            approved_measures += 1

    return round((approved_measures / total) * 100, 1) if total else 0


df = load_strat_matrix()
monitoring_df = load_monitoring()

quarter_data = {}

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
returned_count = 0
risk_count = 0
last_update = datetime.now().strftime("%d.%m.%Y %H:%M")

if not monitoring_df.empty:
    submitted_count = len(monitoring_df)
    approved_count = len(monitoring_df[monitoring_df["approval_status"] == "Погоджено"])
    waiting_count = len(monitoring_df[monitoring_df["approval_status"] == "Очікує погодження"])
    returned_count = len(monitoring_df[monitoring_df["approval_status"] == "Повернуто на доопрацювання"])

    if "risks" in monitoring_df.columns:
        risk_count = len(
            monitoring_df[
                monitoring_df["risks"].fillna("").astype(str).str.strip() != ""
            ]
        )

    if "submitted_at" in monitoring_df.columns:
        try:
            last_update_value = pd.to_datetime(monitoring_df["submitted_at"], errors="coerce").max()
            if pd.notna(last_update_value):
                last_update = last_update_value.strftime("%d.%m.%Y %H:%M")
        except Exception:
            pass

approved_share = round((approved_count / submitted_count) * 100, 1) if submitted_count else 0
without_monitoring = max(total_measures - len(set(monitoring_df["strat_code"].astype(str))) if not monitoring_df.empty else total_measures, 0)


st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="ministry-label">
    🇺🇦 Міністерство економіки, довкілля та сільського господарства України
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="header-box">
        <div class="header-title">Моніторинг виконання стратегічного плану</div>
        <div class="header-subtitle">
            Інтерактивна демо-версія системи для перегляду стратегічного плану, внесення квартального моніторингу,
            погодження даних та аналізу прогресу виконання.
        </div>
        <div class="system-status">
            <div class="status-pill">● Supabase: активний</div>
            <div class="status-pill">● Моніторинг: працює</div>
            <div class="status-pill">● Статус системи: стабільний</div>
            <div class="status-pill">● Оновлено: {last_update}</div>
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

st.markdown(
    """
    <div class="flow-box">
        <div class="flow-title">Маршрут моніторингових даних</div>
        <div class="flow-steps">
            <div class="flow-step">📝 Подання департаментом</div>
            <div class="flow-step">🔎 Перевірка адміністратором</div>
            <div class="flow-step">✅ Погодження</div>
            <div class="flow-step">📊 Відображення у стратегічному плані</div>
            <div class="flow-step">📈 Аналітика виконання</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Заходів у СП", total_measures)
k2.metric("Поданих заявок", submitted_count)
k3.metric("Погоджено", approved_count)
k4.metric("Погоджено, %", f"{approved_share}%")
k5.metric("Без моніторингу", without_monitoring)

k6, k7, k8 = st.columns(3)
k6.metric("Очікує погодження", waiting_count)
k7.metric("Повернуто", returned_count)
k8.metric("Заявок із ризиками", risk_count)

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

f1, f2, f3 = st.columns([1, 1, 1.2])

departments = sorted(df["department"].dropna().astype(str).unique())
goals = df[df["object_type"] == "goal"].copy()
goal_options = ["Усі стратегічні цілі"] + [
    f"{row['code']} {row['name']}" for _, row in goals.iterrows()
]

with f1:
    selected_dep = st.selectbox("Департамент", ["Усі"] + departments)

with f2:
    selected_year = st.selectbox("Рік моніторингу", [2026, 2027, 2028])

with f3:
    selected_goal_nav = st.selectbox("Швидкий перехід до стратегічної цілі", goal_options)

st.subheader("Стратегічний план")

selected_goal_code = None

if selected_goal_nav != "Усі стратегічні цілі":
    selected_goal_code = selected_goal_nav.split(" ")[0].strip()

for _, goal in goals.iterrows():
    goal_code = str(goal["code"])
    goal_name = str(goal["name"])

    if selected_goal_code and goal_code != selected_goal_code:
        continue

    goal_rows = df[df["code"].astype(str).str.startswith(goal_code)]

    tasks = goal_rows[goal_rows["object_type"] == "task"].copy()
    measures_all = goal_rows[goal_rows["object_type"] == "measure"].copy()

    if selected_dep != "Усі":
        measures_for_progress = measures_all[
            measures_all["department"].astype(str) == selected_dep
        ].copy()
    else:
        measures_for_progress = measures_all.copy()

    tasks_count = len(tasks)
    measures_count = len(measures_all)
    goal_percent = get_goal_completion(measures_for_progress, selected_year, quarter_data)

    goal_label = (
        f"{goal_code} {goal_name}  |  "
        f"Завдань — {tasks_count}  |  Заходів — {measures_count}  |  Виконання — {goal_percent}%"
    )

    expand_goal = selected_goal_code == goal_code

    with st.expander(goal_label, expanded=expand_goal):
        st.progress(min(goal_percent / 100, 1.0))

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
                f"{task_code} {task_name}  |  "
                f"Заходів — {task_measures_count}"
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

                    def get_q_value(code):
                        code = str(code).strip()
                        item = quarter_data.get(code, {}).get(col_key, None)

                        if item is None:
                            return ""

                        if item["approval"] in ["Очікує погодження", "Погоджено"]:
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
        <strong>Розроблено департаментом стратегічного планування та макроекономічного прогнозування</strong><br>
        Версія DEMO 0.9 | 2026 | Внутрішня система моніторингу стратегічного плану
    </div>
    """,
    unsafe_allow_html=True
)
