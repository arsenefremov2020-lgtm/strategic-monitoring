import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
import re

st.set_page_config(page_title="Оцінка МіО", layout="wide")

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
.ua-line {
    height: 7px;
    border-radius: 999px;
    background: linear-gradient(90deg, #005BBB 0%, #005BBB 50%, #FFD500 50%, #FFD500 100%);
    margin-bottom: 14px;
}
.header-box, .method-box, .score-box {
    background: rgba(255,255,255,0.94);
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 18px;
    box-shadow: 0 6px 18px rgba(15,23,42,0.045);
}
.header-title {
    font-size: 31px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 7px;
}
.header-subtitle, .score-note {
    font-size: 15px;
    color: #475569;
    line-height: 1.55;
}
div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.90);
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}
.footer {
    text-align: center;
    color: #64748b;
    font-size: 13px;
    margin-top: 50px;
    padding: 22px 0 12px 0;
    border-top: 1px solid #d8dee9;
}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_strat_matrix():
    raw = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=None, engine="openpyxl")
    data = raw.iloc[7:].copy()

    df = pd.DataFrame({
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
        "start_date_plan": data.iloc[:, 22] if data.shape[1] > 22 else "",
        "end_date_plan": data.iloc[:, 23] if data.shape[1] > 23 else "",
    })

    df = df.dropna(subset=["code"]).copy()
    df["code"] = df["code"].astype(str).str.strip()
    df["type_marker"] = df["type_marker"].astype(str).str.strip()

    current_goal_code = ""
    current_goal_name = ""
    current_task_code = ""
    current_task_name = ""
    object_types = []
    parent_goal_codes = []
    parent_goal_names = []
    parent_task_codes = []
    parent_task_names = []

    for _, row in df.iterrows():
        marker = str(row["type_marker"]).lower().strip()
        code = str(row["code"]).strip()
        name = str(row["name"]).strip()
        dots = code.count(".")

        if "стратегічна ціль" in marker:
            object_type = "goal"
            current_goal_code = code
            current_goal_name = name
            current_task_code = ""
            current_task_name = ""
        elif "завдання" in marker:
            object_type = "task"
            current_task_code = code
            current_task_name = name
        elif "заход" in marker or dots >= 3:
            object_type = "measure"
        else:
            if current_task_code:
                object_type = "task_indicator"
            elif current_goal_code:
                object_type = "goal_indicator"
            else:
                object_type = "other"

        object_types.append(object_type)
        parent_goal_codes.append(current_goal_code)
        parent_goal_names.append(current_goal_name)
        parent_task_codes.append(current_task_code)
        parent_task_names.append(current_task_name)

    df["object_type"] = object_types
    df["parent_goal_code"] = parent_goal_codes
    df["parent_goal_name"] = parent_goal_names
    df["parent_task_code"] = parent_task_codes
    df["parent_task_name"] = parent_task_names

    return df


@st.cache_data(ttl=60)
def load_monitoring_requests():
    response = supabase.table("monitoring_requests").select("*").execute()
    if not response.data:
        return pd.DataFrame()
    return pd.DataFrame(response.data)


def raw_value(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def is_empty(value):
    text = raw_value(value).lower().replace(" ", "")
    return text in ["", "nan", "none", "н.д.", "нд", "-", "—"]


def parse_number(value):
    text = raw_value(value)
    if is_empty(text):
        return None
    text = text.replace("\u00a0", " ").replace("%", "").replace(",", ".")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in ["", ".", "-", "-."]:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def clamp(value, low=0, high=120):
    if value is None or pd.isna(value):
        return None
    return max(low, min(high, float(value)))


def is_yes_no_unit(unit):
    text = raw_value(unit).lower()
    return "так/ні" in text or ("так" in text and "ні" in text)


def is_positive_yes(value):
    text = raw_value(value).lower()
    return text in ["так", "yes", "y", "true", "1", "виконано"] or text.startswith("так")


def status_score(status):
    text = raw_value(status).lower()
    if text == "виконано частково":
        return 60
    mapping = {
        "виконано": 100,
        "виконано частково": 60,
        "виконується": 50,
        "потребує уваги": 40,
        "прострочено": 25,
        "не розпочато": 0,
    }
    for key, value in mapping.items():
        if key in text:
            return value
    return None


def score_level(score):
    if score is None or pd.isna(score):
        return "Немає даних"
    if score >= 100:
        return "Виконано"
    if score >= 80:
        return "Високий прогрес"
    if score >= 50:
        return "Частковий прогрес"
    if score > 0:
        return "Критичне відставання"
    return "Не виконано / немає погоджених даних"


def score_risk(level):
    if level in ["Виконано", "Високий прогрес"]:
        return "Низький"
    if level == "Частковий прогрес":
        return "Середній"
    if level in ["Критичне відставання", "Не виконано / немає погоджених даних"]:
        return "Високий"
    return "Невизначений"


def filter_monitoring(monitoring_df, selected_year, selected_quarter):
    if monitoring_df.empty:
        return pd.DataFrame()

    df = monitoring_df.copy()
    required_cols = [
        "year", "quarter", "approval_status", "strat_code", "status",
        "numeric_value", "progress_text", "risks", "department", "submitted_at"
    ]
    for col in required_cols:
        if col not in df.columns:
            df[col] = ""

    df = df[df["year"].astype(str).str.strip() == str(selected_year)].copy()

    if selected_quarter != "Усі квартали":
        q = selected_quarter.replace(" квартал", "").strip()
        df = df[df["quarter"].astype(str).str.strip() == q].copy()

    df = df[df["approval_status"].astype(str).str.strip() == "Погоджено"].copy()

    if "submitted_at" in df.columns:
        df["_submitted_at_dt"] = pd.to_datetime(df["submitted_at"], errors="coerce")
        df = df.sort_values("_submitted_at_dt")

    return df


def calculate_measure_score(row, monitoring_records, selected_year):
    code = raw_value(row.get("code"))
    target = row.get(f"target_{selected_year}", "")
    target_num = parse_number(target)
    unit = row.get("unit", "")

    records = monitoring_records[
        monitoring_records["strat_code"].astype(str).str.strip() == code
    ].copy()

    if records.empty:
        return {
            "fact_value": None,
            "indicator_score": None,
            "status_score": None,
            "measure_score": 0.0,
            "level": "Не виконано / немає погоджених даних",
            "risk_level": "Високий",
            "has_approved_data": False,
            "has_risks": False,
            "method_note": "Немає погоджених даних за обраний період",
        }

    last = records.iloc[-1]
    fact_raw = last.get("numeric_value", "")
    fact_num = parse_number(fact_raw)
    s_score = status_score(last.get("status", ""))
    has_risks = raw_value(last.get("risks", "")) != ""

    if is_yes_no_unit(unit):
        indicator_score = 100 if is_positive_yes(fact_raw) or raw_value(last.get("status", "")).lower() == "виконано" else 0
        method_note = "Індикатор так/ні: так = 100%, ні = 0%"
    elif fact_num is not None and target_num not in [None, 0]:
        indicator_score = clamp((fact_num / target_num) * 100)
        method_note = "Факт / планове значення × 100"
    elif fact_num is not None and target_num is None:
        indicator_score = None
        method_note = "Є факт, але немає числового плану; використано статус виконання"
    elif s_score is not None:
        indicator_score = None
        method_note = "Немає числового факту; використано статус виконання"
    else:
        indicator_score = 0
        method_note = "Немає числового факту і статус не дає оцінки"

    if indicator_score is not None and s_score is not None:
        final_score = indicator_score * 0.7 + s_score * 0.3
    elif indicator_score is not None:
        final_score = indicator_score
    elif s_score is not None:
        final_score = s_score
    else:
        final_score = 0

    if has_risks:
        final_score = max(0, final_score - 10)

    final_score = round(clamp(final_score), 1)
    level = score_level(final_score)

    return {
        "fact_value": fact_raw,
        "indicator_score": round(indicator_score, 1) if indicator_score is not None else None,
        "status_score": s_score,
        "measure_score": final_score,
        "level": level,
        "risk_level": score_risk(level),
        "has_approved_data": True,
        "has_risks": has_risks,
        "method_note": method_note,
    }


def build_evaluation_table(strat_df, monitoring_df, selected_year, selected_quarter, selected_department):
    measures = strat_df[strat_df["object_type"] == "measure"].copy()

    if selected_department != "Усі":
        measures = measures[measures["department"].astype(str).str.strip() == selected_department].copy()

    plan_col = f"target_{selected_year}"
    measures["is_active_year"] = measures[plan_col].apply(lambda value: not is_empty(value))
    measures = measures[measures["is_active_year"]].copy()

    filtered_monitoring = filter_monitoring(monitoring_df, selected_year, selected_quarter)

    rows = []
    for _, row in measures.iterrows():
        score = calculate_measure_score(row, filtered_monitoring, selected_year)
        rows.append({
            "goal_code": row.get("parent_goal_code", ""),
            "goal_name": row.get("parent_goal_name", ""),
            "task_code": row.get("parent_task_code", ""),
            "task_name": row.get("parent_task_name", ""),
            "measure_code": row.get("code", ""),
            "measure_name": row.get("name", ""),
            "indicator": row.get("indicator", ""),
            "unit": row.get("unit", ""),
            "plan_value": row.get(plan_col, ""),
            "fact_value": score["fact_value"],
            "department": row.get("department", ""),
            "indicator_score": score["indicator_score"],
            "status_score": score["status_score"],
            "measure_score": score["measure_score"],
            "level": score["level"],
            "risk_level": score["risk_level"],
            "has_approved_data": score["has_approved_data"],
            "has_risks": score["has_risks"],
            "method_note": score["method_note"],
        })

    return pd.DataFrame(rows)


def aggregate_scores(evaluation_df):
    if evaluation_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    task_scores = (
        evaluation_df
        .groupby(["goal_code", "goal_name", "task_code", "task_name"], dropna=False)
        .agg(
            task_score=("measure_score", "mean"),
            measures_count=("measure_code", "count"),
            approved_count=("has_approved_data", "sum"),
            risk_measures=("has_risks", "sum"),
        )
        .reset_index()
    )
    task_scores["task_score"] = task_scores["task_score"].round(1)
    task_scores["level"] = task_scores["task_score"].apply(score_level)
    task_scores["risk_level"] = task_scores["level"].apply(score_risk)

    goal_scores = (
        task_scores
        .groupby(["goal_code", "goal_name"], dropna=False)
        .agg(
            goal_score=("task_score", "mean"),
            tasks_count=("task_code", "count"),
            measures_count=("measures_count", "sum"),
            approved_count=("approved_count", "sum"),
            risk_measures=("risk_measures", "sum"),
        )
        .reset_index()
    )
    goal_scores["goal_score"] = goal_scores["goal_score"].round(1)
    goal_scores["level"] = goal_scores["goal_score"].apply(score_level)
    goal_scores["risk_level"] = goal_scores["level"].apply(score_risk)

    return task_scores, goal_scores


def build_integral_score(goal_scores, task_scores, evaluation_df):
    if evaluation_df.empty:
        return 0.0
    measures_score = evaluation_df["measure_score"].mean()
    tasks_score = task_scores["task_score"].mean() if not task_scores.empty else 0
    goals_score = goal_scores["goal_score"].mean() if not goal_scores.empty else 0
    return round(float(measures_score * 0.45 + tasks_score * 0.35 + goals_score * 0.20), 1)


def build_analytical_note(evaluation_df, task_scores, goal_scores, integral_score):
    if evaluation_df.empty:
        return "За обраними фільтрами немає активних заходів або даних для оцінки."

    total = len(evaluation_df)
    approved = int(evaluation_df["has_approved_data"].sum())
    without_data = total - approved
    risk_count = int(evaluation_df["has_risks"].sum())
    problem_measures = evaluation_df[evaluation_df["measure_score"] < 50].copy()
    best_goals = goal_scores.sort_values("goal_score", ascending=False).head(3)
    weak_goals = goal_scores.sort_values("goal_score", ascending=True).head(3)

    text = []
    text.append(
        f"Інтегральна оцінка виконання за обраним періодом становить {integral_score}%. "
        f"Розрахунок охоплює {total} активних заходів, з яких {approved} мають погоджені моніторингові дані, "
        f"а {without_data} залишаються без погодженого подання."
    )

    if risk_count > 0:
        text.append(f"У {risk_count} заходах зазначено ризики або проблеми, тому для них застосовано понижувальну поправку до оцінки.")

    if not best_goals.empty:
        best = "; ".join([f"{r.goal_code} — {r.goal_score}%" for _, r in best_goals.iterrows()])
        text.append(f"Найкращу динаміку демонструють стратегічні цілі: {best}.")

    if not weak_goals.empty:
        weak = "; ".join([f"{r.goal_code} — {r.goal_score}%" for _, r in weak_goals.iterrows()])
        text.append(f"Найбільшої управлінської уваги потребують стратегічні цілі: {weak}.")

    if not problem_measures.empty:
        text.append(
            f"Кількість заходів із критичним відставанням або відсутністю погоджених даних: {len(problem_measures)}. "
            "Їх доцільно винести в окремий перелік для уточнення причин відхилення, строків і відповідальних виконавців."
        )

    return " ".join(text)


def prepare_download(df):
    return df.to_csv(index=False).encode("utf-8-sig")


st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="header-box">
        <div class="header-title">Оцінка моніторингу та результативності</div>
        <div class="header-subtitle">
            Сторінка для розрахунку оцінки виконання стратегічного плану за логікою: захід → завдання → стратегічна ціль → інтегральна оцінка.
            У розрахунок включаються лише погоджені моніторингові дані. Непогоджені заявки залишаються частиною процесу адміністрування, але не впливають на оцінку.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

strat_df = load_strat_matrix()
monitoring_df = load_monitoring_requests()

measures_all = strat_df[strat_df["object_type"] == "measure"].copy()
departments = sorted([d for d in measures_all["department"].dropna().astype(str).str.strip().unique() if d and d.lower() != "nan"])

f1, f2, f3, f4 = st.columns([1, 1, 1, 1.4])
with f1:
    selected_year = st.selectbox("Рік оцінки", [2026, 2027, 2028], index=0)
with f2:
    selected_quarter = st.selectbox("Період", ["Усі квартали", "I квартал", "II квартал", "III квартал", "IV квартал"])
with f3:
    selected_department = st.selectbox("Департамент", ["Усі"] + departments)
with f4:
    selected_view = st.selectbox("Режим перегляду", ["Загальний дашборд", "Стратегічні цілі", "Завдання", "Заходи", "Методика"])

evaluation_df = build_evaluation_table(strat_df, monitoring_df, selected_year, selected_quarter, selected_department)
task_scores, goal_scores = aggregate_scores(evaluation_df)
integral_score = build_integral_score(goal_scores, task_scores, evaluation_df)
analytical_note = build_analytical_note(evaluation_df, task_scores, goal_scores, integral_score)

active_measures = len(evaluation_df)
approved_measures = int(evaluation_df["has_approved_data"].sum()) if not evaluation_df.empty else 0
without_approved_data = active_measures - approved_measures
risk_measures = int(evaluation_df["has_risks"].sum()) if not evaluation_df.empty else 0
average_measure_score = round(evaluation_df["measure_score"].mean(), 1) if not evaluation_df.empty else 0
average_task_score = round(task_scores["task_score"].mean(), 1) if not task_scores.empty else 0
average_goal_score = round(goal_scores["goal_score"].mean(), 1) if not goal_scores.empty else 0

k1, k2, k3, k4 = st.columns(4)
k1.metric("Інтегральна оцінка", f"{integral_score}%")
k2.metric("Оцінка заходів", f"{average_measure_score}%")
k3.metric("Оцінка завдань", f"{average_task_score}%")
k4.metric("Оцінка цілей", f"{average_goal_score}%")

k5, k6, k7, k8 = st.columns(4)
k5.metric("Активних заходів", active_measures)
k6.metric("З погодженими даними", approved_measures)
k7.metric("Без погоджених даних", without_approved_data)
k8.metric("Із ризиками", risk_measures)

st.markdown(
    f"""
    <div class="score-box">
        <b>Автоматична аналітична довідка</b><br>
        <div class="score-note">{analytical_note}</div>
    </div>
    """,
    unsafe_allow_html=True
)

if selected_view == "Методика":
    st.markdown(
        """
        <div class="method-box">
        <b>Логіка розрахунку</b><br><br>
        1. У розрахунок включаються активні заходи, які мають планове значення на обраний рік.<br>
        2. Для кожного заходу система бере останнє погоджене подання за обраний рік і квартал.<br>
        3. Якщо індикатор числовий, оцінка рахується як факт / план × 100.<br>
        4. Якщо індикатор має формат так/ні, так = 100%, ні = 0%.<br>
        5. Якщо числового факту або плану немає, використовується статус виконання: виконано = 100%, виконано частково = 60%, виконується = 50%, потребує уваги = 40%, прострочено = 25%, не розпочато = 0%.<br>
        6. Якщо за заходом зазначені ризики, оцінка зменшується на 10 пунктів.<br>
        7. Оцінка завдання = середнє значення оцінок його заходів.<br>
        8. Оцінка стратегічної цілі = середнє значення оцінок її завдань.<br>
        9. Інтегральна оцінка = 45% оцінка заходів + 35% оцінка завдань + 20% оцінка стратегічних цілей.<br><br>
        Ця сторінка використовує внутрішню логіку розрахунку на основі стратегічної матриці, погоджених подань і ризиків.
        </div>
        """,
        unsafe_allow_html=True
    )

elif selected_view == "Загальний дашборд":
    c1, c2 = st.columns([1.2, 1])

    with c1:
        if not goal_scores.empty:
            chart_df = goal_scores.sort_values("goal_score", ascending=True).copy()
            chart_df["Ціль"] = chart_df["goal_code"].astype(str) + " " + chart_df["goal_name"].astype(str).str.slice(0, 70)
            fig = px.bar(
                chart_df,
                x="goal_score",
                y="Ціль",
                orientation="h",
                text="goal_score",
                title="Оцінка виконання за стратегічними цілями",
                labels={"goal_score": "Оцінка, %"},
            )
            fig.update_traces(texttemplate="%{text}%", textposition="outside")
            fig.update_layout(height=max(420, len(chart_df) * 55), xaxis_range=[0, 120])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Немає даних для графіка стратегічних цілей.")

    with c2:
        if not evaluation_df.empty:
            level_counts = evaluation_df["level"].value_counts().reset_index()
            level_counts.columns = ["Рівень", "Кількість"]
            fig = px.pie(
                level_counts,
                names="Рівень",
                values="Кількість",
                title="Структура заходів за рівнем виконання",
                hole=0.45,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Немає даних для структури виконання.")

    c3, c4 = st.columns(2)
    with c3:
        if not evaluation_df.empty:
            risk_counts = evaluation_df["risk_level"].value_counts().reset_index()
            risk_counts.columns = ["Рівень ризику", "Кількість"]
            fig = px.bar(
                risk_counts,
                x="Рівень ризику",
                y="Кількість",
                text="Кількість",
                title="Розподіл заходів за рівнем ризику",
            )
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

    with c4:
        if not evaluation_df.empty:
            dep_df = evaluation_df.groupby("department", dropna=False).agg(
                score=("measure_score", "mean"),
                measures=("measure_code", "count"),
                risks=("has_risks", "sum"),
            ).reset_index()
            dep_df["score"] = dep_df["score"].round(1)
            dep_df = dep_df.sort_values("score", ascending=True)
            fig = px.bar(
                dep_df,
                x="score",
                y="department",
                orientation="h",
                text="score",
                title="Середня оцінка за департаментами",
                labels={"score": "Оцінка, %", "department": "Департамент"},
            )
            fig.update_traces(texttemplate="%{text}%", textposition="outside")
            fig.update_layout(height=max(420, len(dep_df) * 35), xaxis_range=[0, 120])
            st.plotly_chart(fig, use_container_width=True)

elif selected_view == "Стратегічні цілі":
    st.subheader("Оцінка стратегічних цілей")
    if goal_scores.empty:
        st.info("Дані відсутні.")
    else:
        show = goal_scores.rename(columns={
            "goal_code": "Код СЦ",
            "goal_name": "Стратегічна ціль",
            "goal_score": "Оцінка, %",
            "tasks_count": "Завдань",
            "measures_count": "Заходів",
            "approved_count": "Погоджених подань",
            "risk_measures": "Заходів із ризиками",
            "level": "Рівень виконання",
            "risk_level": "Рівень ризику",
        })
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.download_button("Завантажити оцінку стратегічних цілей CSV", data=prepare_download(show), file_name=f"goal_scores_{selected_year}.csv", mime="text/csv")

elif selected_view == "Завдання":
    st.subheader("Оцінка завдань")
    if task_scores.empty:
        st.info("Дані відсутні.")
    else:
        show = task_scores.rename(columns={
            "goal_code": "Код СЦ",
            "goal_name": "Стратегічна ціль",
            "task_code": "Код завдання",
            "task_name": "Завдання",
            "task_score": "Оцінка, %",
            "measures_count": "Заходів",
            "approved_count": "Погоджених подань",
            "risk_measures": "Заходів із ризиками",
            "level": "Рівень виконання",
            "risk_level": "Рівень ризику",
        })
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.download_button("Завантажити оцінку завдань CSV", data=prepare_download(show), file_name=f"task_scores_{selected_year}.csv", mime="text/csv")

else:
    st.subheader("Оцінка заходів")
    if evaluation_df.empty:
        st.info("Дані відсутні.")
    else:
        search = st.text_input("Пошук у заходах", "")
        show_df = evaluation_df.copy()
        if search.strip():
            sq = search.strip().lower()
            show_df = show_df[
                show_df["measure_code"].astype(str).str.lower().str.contains(sq, na=False)
                | show_df["measure_name"].astype(str).str.lower().str.contains(sq, na=False)
                | show_df["indicator"].astype(str).str.lower().str.contains(sq, na=False)
                | show_df["department"].astype(str).str.lower().str.contains(sq, na=False)
            ].copy()

        show = show_df.rename(columns={
            "goal_code": "Код СЦ",
            "goal_name": "Стратегічна ціль",
            "task_code": "Код завдання",
            "task_name": "Завдання",
            "measure_code": "Код заходу",
            "measure_name": "Захід",
            "indicator": "Індикатор",
            "unit": "Одиниця виміру",
            "plan_value": "План",
            "fact_value": "Факт",
            "department": "Департамент",
            "indicator_score": "Оцінка індикатора, %",
            "status_score": "Оцінка статусу, %",
            "measure_score": "Оцінка заходу, %",
            "level": "Рівень виконання",
            "risk_level": "Рівень ризику",
            "has_approved_data": "Є погоджені дані",
            "has_risks": "Є ризики",
            "method_note": "Метод розрахунку",
        })
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.download_button("Завантажити оцінку заходів CSV", data=prepare_download(show), file_name=f"measure_scores_{selected_year}.csv", mime="text/csv")

st.markdown(
    """
    <div class="footer">
        Версія DEMO 1.3 | Модуль оцінки МіО | Внутрішня логіка стратегічного моніторингу
    </div>
    """,
    unsafe_allow_html=True
)
