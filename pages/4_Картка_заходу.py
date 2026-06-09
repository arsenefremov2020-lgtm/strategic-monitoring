import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime
import re

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

st.markdown("""
<style>
.stApp {
    background:
        linear-gradient(rgba(15,23,42,0.025) 1px, transparent 1px),
        linear-gradient(90deg, rgba(15,23,42,0.025) 1px, transparent 1px),
        radial-gradient(circle at top right, rgba(37,99,235,0.09), transparent 28%),
        radial-gradient(circle at bottom left, rgba(22,163,74,0.07), transparent 30%),
        linear-gradient(180deg, #f7f9fc 0%, #eef3f8 100%);
    background-size:
        36px 36px,
        36px 36px,
        auto,
        auto,
        auto;
}

.stApp::before {
    content: "";
    position: fixed;
    top: -180px;
    right: -120px;
    width: 520px;
    height: 520px;
    border-radius: 50%;
    background: rgba(37, 99, 235, 0.045);
    z-index: 0;
}

.stApp::after {
    content: "";
    position: fixed;
    bottom: -190px;
    left: -130px;
    width: 420px;
    height: 420px;
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

.top-grid {
    display: grid;
    grid-template-columns: 1.4fr 0.8fr;
    gap: 16px;
    margin-bottom: 18px;
}

.hero-card {
    background: rgba(255,255,255,0.95);
    border: 1px solid #d8dee9;
    border-radius: 18px;
    padding: 26px 30px;
    box-shadow: 0 10px 26px rgba(15,23,42,0.07);
}

.ministry-card {
    background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(248,250,252,0.96));
    border: 1px solid #d8dee9;
    border-radius: 18px;
    padding: 22px 24px;
    box-shadow: 0 10px 26px rgba(15,23,42,0.055);
}

.hero-kicker {
    font-size: 13px;
    font-weight: 800;
    color: #1d4ed8;
    text-transform: uppercase;
    letter-spacing: .04em;
    margin-bottom: 8px;
}

.hero-title {
    font-size: 34px;
    font-weight: 950;
    color: #0f172a;
    line-height: 1.15;
    margin-bottom: 10px;
}

.hero-subtitle {
    color: #475569;
    font-size: 15px;
    line-height: 1.55;
}

.ministry-title {
    color: #0f172a;
    font-weight: 900;
    font-size: 16px;
    margin-bottom: 8px;
}

.ministry-line {
    color: #475569;
    font-size: 13px;
    line-height: 1.5;
}

.status-pill-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 14px;
}

.status-pill {
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 999px;
    padding: 7px 11px;
    font-size: 13px;
    color: #334155;
    font-weight: 700;
}

.card {
    background: rgba(255,255,255,0.94);
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 20px 22px;
    margin: 18px 0;
    box-shadow: 0 6px 18px rgba(15,23,42,0.045);
}

.card-title {
    font-size: 20px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 8px;
}

.card-subtitle {
    color: #64748b;
    font-size: 14px;
    margin-bottom: 12px;
}

.passport-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin-top: 12px;
}

.passport-cell {
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
}

.passport-label {
    color: #64748b;
    font-size: 13px;
    margin-bottom: 5px;
}

.passport-value {
    color: #0f172a;
    font-weight: 850;
    font-size: 16px;
}

.badge-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 12px 0;
}

.badge {
    background: #eef6ff;
    border: 1px solid #bfdbfe;
    color: #1d4ed8;
    border-radius: 999px;
    padding: 7px 11px;
    font-size: 13px;
    font-weight: 800;
}

.badge-green {
    background: #dcfce7;
    border: 1px solid #bbf7d0;
    color: #166534;
}

.badge-yellow {
    background: #fef9c3;
    border: 1px solid #fde68a;
    color: #854d0e;
}

.badge-red {
    background: #fee2e2;
    border: 1px solid #fecaca;
    color: #991b1b;
}

.badge-gray {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    color: #475569;
}

.timeline {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-top: 10px;
}

.timeline-cell {
    border-radius: 14px;
    border: 1px solid #d8dee9;
    padding: 14px;
    background: #f8fafc;
    min-height: 105px;
}

.timeline-title {
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 6px;
}

.timeline-value {
    font-size: 18px;
    font-weight: 900;
    margin-bottom: 4px;
}

.timeline-note {
    font-size: 13px;
    color: #64748b;
}

.q-approved {
    background: #dcfce7;
    border-color: #bbf7d0;
}

.q-waiting {
    background: #fef9c3;
    border-color: #fde68a;
}

.q-returned {
    background: #fee2e2;
    border-color: #fecaca;
}

.q-empty {
    background: #f8fafc;
}

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.9);
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

div[data-testid="stPageLink"] a {
    background: #ffffff !important;
    border: 1px solid #d8dee9 !important;
    border-radius: 12px !important;
    padding: 12px 16px !important;
    font-weight: 800 !important;
    text-decoration: none !important;
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
        "start_period": data.iloc[:, 22],
        "end_period": data.iloc[:, 23],
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


def load_requests():
    response = (
        supabase
        .table("monitoring_requests")
        .select("*")
        .order("submitted_at", desc=True)
        .execute()
    )

    if not response.data:
        return pd.DataFrame()

    return pd.DataFrame(response.data)


def clean(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value)


def to_number(value):
    text = str(value).replace(",", ".").strip()

    if text.lower() in ["", "nan", "none", "н.д.", "x", "х", "так", "ні", "да", "нет"]:
        return None

    match = re.search(r"-?\d+(\.\d+)?", text)

    if match:
        try:
            return float(match.group())
        except Exception:
            return None

    return None


def normalize_text(value):
    return str(value).strip().lower().replace("і", "i")


def get_goal_code(code):
    parts = str(code).split(".")
    return parts[0] + "." if parts else ""


def get_task_code(code):
    parts = str(code).split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}."
    return ""


def plan_fact_percent(actual, target):
    actual_num = to_number(actual)
    target_num = to_number(target)

    actual_text = normalize_text(actual)
    target_text = normalize_text(target)

    if actual_num is not None and target_num is not None and target_num != 0:
        return round(min((actual_num / target_num) * 100, 150), 1)

    if target_text in ["так", "yes"] or actual_text in ["так", "ні", "yes", "no"]:
        if actual_text in ["так", "yes"]:
            return 100
        if actual_text in ["ні", "no"]:
            return 0

    return None


def status_score(status):
    status = str(status)

    if status == "Виконано":
        return 100
    if status == "Виконано частково":
        return 50
    if status == "Виконується":
        return 40
    if status == "Потребує уваги":
        return 25
    if status == "Прострочено":
        return 0
    if status == "Не розпочато":
        return 0

    return 0


def gauge_chart(value, title):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": "%"},
        title={"text": title},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#1d4ed8"},
            "steps": [
                {"range": [0, 35], "color": "#fee2e2"},
                {"range": [35, 70], "color": "#fef3c7"},
                {"range": [70, 100], "color": "#dcfce7"},
            ],
            "threshold": {
                "line": {"color": "#111827", "width": 4},
                "thickness": 0.75,
                "value": value
            }
        }
    ))

    fig.update_layout(height=320, margin=dict(l=20, r=20, t=60, b=20))
    return fig


def risk_assessment(latest_row, progress_percent, has_monitoring):
    if not has_monitoring:
        return "Дані відсутні", "Моніторингові заявки за цим заходом ще не подано.", "badge-gray"

    status = clean(latest_row.get("status", ""))
    risks = clean(latest_row.get("risks", ""))

    if status in ["Прострочено", "Потребує уваги"]:
        return "Високий ризик", "Статус заявки свідчить про проблеми у виконанні.", "badge-red"

    if progress_percent is not None and progress_percent < 35:
        return "Високий ризик", "Фактичне значення суттєво нижче планового.", "badge-red"

    if status == "Виконано частково" or risks.strip():
        return "Помірний ризик", "Є часткове виконання або зазначені ризики.", "badge-yellow"

    if status == "Виконано" or progress_percent >= 70:
        return "Низький ризик", "Критичних відхилень не виявлено.", "badge-green"

    return "Потребує спостереження", "Даних достатньо для моніторингу, але прогрес ще не завершено.", "badge-yellow"


def period_values(row):
    return pd.DataFrame([
        {"Рік": "2021", "Тип": "Базове значення", "Значення": row["base_2021"]},
        {"Рік": "2024", "Тип": "Звіт", "Значення": row["fact_2024"]},
        {"Рік": "2025", "Тип": "Очікуване", "Значення": row["expected_2025"]},
        {"Рік": "2026", "Тип": "План", "Значення": row["target_2026"]},
        {"Рік": "2027", "Тип": "План", "Значення": row["target_2027"]},
        {"Рік": "2028", "Тип": "План", "Значення": row["target_2028"]},
    ])


st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="top-grid">
        <div class="hero-card">
            <div class="hero-kicker">Паспорт стратегічного заходу</div>
            <div class="hero-title">Картка заходу</div>
            <div class="hero-subtitle">
                Сторінка показує повний профіль окремого заходу: місце в стратегічному плані,
                планові значення, квартальний моніторинг, файли, ризики та історію заявок.
            </div>
        </div>
        <div class="ministry-card">
            <div class="ministry-title">🇺🇦 Міністерство економіки, довкілля та сільського господарства України</div>
            <div class="ministry-line">Внутрішня демо-система моніторингу стратегічного плану.</div>
            <div class="status-pill-wrap">
                <div class="status-pill">● Режим: картка заходу</div>
                <div class="status-pill">● Джерело: Excel + Supabase</div>
                <div class="status-pill">● Оновлено: """ + datetime.now().strftime("%d.%m.%Y %H:%M") + """</div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

df = load_strat_matrix()
requests_df = load_requests()

measures = df[df["object_type"] == "measure"].copy()

if measures.empty:
    st.warning("Заходів у стратегічній матриці не знайдено.")
    st.stop()

measure_options = [
    f"{row['code']} — {row['name']}"
    for _, row in measures.iterrows()
]

st.markdown('<div class="card"><div class="card-title">Вибір заходу</div><div class="card-subtitle">Оберіть захід для перегляду паспорта, моніторингу та ризиків.</div>', unsafe_allow_html=True)

selected_option = st.selectbox(
    "Оберіть захід",
    measure_options
)

selected_code = selected_option.split("—")[0].strip()

selected_measure = measures[
    measures["code"].astype(str).str.strip() == selected_code
].iloc[0]

st.markdown('</div>', unsafe_allow_html=True)

goal_code = get_goal_code(selected_code)
task_code = get_task_code(selected_code)

goal_row = df[
    (df["object_type"] == "goal") &
    (df["code"].astype(str).str.strip() == goal_code)
]

task_row = df[
    (df["object_type"] == "task") &
    (df["code"].astype(str).str.strip() == task_code)
]

goal_name = clean(goal_row.iloc[0]["name"]) if not goal_row.empty else ""
task_name = clean(task_row.iloc[0]["name"]) if not task_row.empty else ""

measure_requests = pd.DataFrame()

if not requests_df.empty:
    measure_requests = requests_df[
        requests_df["strat_code"].astype(str).str.strip() == selected_code
    ].copy()

has_monitoring = not measure_requests.empty

approved_requests = pd.DataFrame()

if has_monitoring:
    approved_requests = measure_requests[
        measure_requests["approval_status"].astype(str) == "Погоджено"
    ].copy()

latest_request = None

if has_monitoring:
    latest_request = measure_requests.sort_values("submitted_at", ascending=False).iloc[0]

latest_approved = None

if not approved_requests.empty:
    latest_approved = approved_requests.sort_values("submitted_at", ascending=False).iloc[0]

target_value = selected_measure.get("target_2026", "")
latest_actual = latest_approved.get("numeric_value", "") if latest_approved is not None else ""
progress_percent = plan_fact_percent(latest_actual, target_value)

if progress_percent is None:
    progress_percent = status_score(latest_approved.get("status", "")) if latest_approved is not None else 0

risk_title, risk_reason, risk_badge = risk_assessment(
    latest_approved if latest_approved is not None else {},
    progress_percent,
    has_monitoring
)

st.markdown('<div class="card"><div class="card-title">Паспорт заходу</div>', unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="badge-wrap">
        <div class="badge">Код: {selected_code}</div>
        <div class="badge">Департамент: {clean(selected_measure["department"])}</div>
        <div class="badge {risk_badge}">{risk_title}</div>
        <div class="badge">Моніторингових заявок: {len(measure_requests)}</div>
    </div>
    <div style="font-size:24px;font-weight:900;color:#0f172a;line-height:1.25;margin-top:10px;">
        {clean(selected_measure["name"])}
    </div>
    <div style="color:#475569;margin-top:10px;">
        {risk_reason}
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="passport-grid">
        <div class="passport-cell">
            <div class="passport-label">Стратегічна ціль</div>
            <div class="passport-value">{goal_code}</div>
            <div class="passport-label">{goal_name}</div>
        </div>
        <div class="passport-cell">
            <div class="passport-label">Завдання</div>
            <div class="passport-value">{task_code}</div>
            <div class="passport-label">{task_name}</div>
        </div>
        <div class="passport-cell">
            <div class="passport-label">Головний виконавець</div>
            <div class="passport-value">{clean(selected_measure["department"])}</div>
        </div>
        <div class="passport-cell">
            <div class="passport-label">Початок виконання</div>
            <div class="passport-value">{clean(selected_measure["start_period"])}</div>
        </div>
        <div class="passport-cell">
            <div class="passport-label">Кінець виконання</div>
            <div class="passport-value">{clean(selected_measure["end_period"])}</div>
        </div>
        <div class="passport-cell">
            <div class="passport-label">Одиниця виміру</div>
            <div class="passport-value">{clean(selected_measure["unit"])}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)

total_requests = len(measure_requests)
approved_count = len(measure_requests[measure_requests["approval_status"] == "Погоджено"]) if has_monitoring else 0
returned_count = len(measure_requests[measure_requests["approval_status"] == "Повернуто на доопрацювання"]) if has_monitoring else 0
waiting_count = len(measure_requests[measure_requests["approval_status"] == "Очікує погодження"]) if has_monitoring else 0
files_count = len(measure_requests[measure_requests["file_urls"].fillna("").astype(str).str.strip() != ""]) if has_monitoring and "file_urls" in measure_requests.columns else 0

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("План 2026", clean(selected_measure["target_2026"]))
k2.metric("Останній факт", clean(latest_actual))
k3.metric("Прогрес", f"{round(progress_percent, 1)}%")
k4.metric("Погоджено", approved_count)
k5.metric("Очікує", waiting_count)
k6.metric("Файли", files_count)

st.markdown('<div class="card"><div class="card-title">Аналітичний висновок</div>', unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="badge-wrap">
        <div class="badge {risk_badge}">{risk_title}</div>
        <div class="badge">Прогрес: {round(progress_percent, 1)}%</div>
        <div class="badge">Заявок: {total_requests}</div>
        <div class="badge">Повернень: {returned_count}</div>
    </div>
    <div style="color:#475569;font-size:14px;">{risk_reason}</div>
    """,
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)

view_mode = st.selectbox(
    "Тип візуалізації",
    [
        "Огляд",
        "Динаміка планових значень",
        "Квартальний моніторинг",
        "План / факт",
        "Статуси заявок",
        "Ризики та відхилення",
        "Файли та історія"
    ]
)

if view_mode in ["Огляд", "План / факт"]:
    st.markdown('<div class="card"><div class="card-title">Індикатор прогресу заходу</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])

    with c1:
        st.plotly_chart(
            gauge_chart(progress_percent, "Прогрес заходу"),
            use_container_width=True
        )

    with c2:
        st.markdown("**Метод оцінки:**")
        st.write(
            "Якщо є числовий план і факт — рахується факт / план. "
            "Якщо показник має формат так/ні — так = 100%, ні = 0%. "
            "Якщо погоджених даних немає — прогрес вважається нульовим."
        )
        st.progress(min(progress_percent / 100, 1.0), text=f"Прогрес: {round(progress_percent, 1)}%")

    st.markdown('</div>', unsafe_allow_html=True)

if view_mode in ["Огляд", "Динаміка планових значень"]:
    st.markdown('<div class="card"><div class="card-title">Планові та звітні значення за роками</div>', unsafe_allow_html=True)

    values_df = period_values(selected_measure)

    st.dataframe(
        values_df,
        use_container_width=True,
        hide_index=True
    )

    values_df["Числове значення"] = values_df["Значення"].apply(to_number)
    numeric_values = values_df.dropna(subset=["Числове значення"]).copy()

    if numeric_values.empty:
        st.info("Для цього заходу значення не є числовими. Графік динаміки не будується.")
    else:
        fig = px.line(
            numeric_values,
            x="Рік",
            y="Числове значення",
            markers=True,
            text="Числове значення",
            title="Динаміка планових / звітних значень"
        )

        fig.update_xaxes(type="category")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

if view_mode in ["Огляд", "Квартальний моніторинг"]:
    st.markdown('<div class="card"><div class="card-title">Квартальна шкала моніторингу</div><div class="card-subtitle">Колір показує статус погодження даних у відповідному кварталі.</div>', unsafe_allow_html=True)

    quarters = ["I", "II", "III", "IV"]

    timeline_parts = ['<div class="timeline">']

    for q in quarters:
        q_data = pd.DataFrame()

        if has_monitoring:
            q_data = measure_requests[
                measure_requests["quarter"].astype(str) == q
            ].copy()

        if q_data.empty:
            css = "q-empty"
            value = "—"
            approval = "Дані не подано"
            status = ""
        else:
            latest_q = q_data.sort_values("submitted_at", ascending=False).iloc[0]
            approval = clean(latest_q.get("approval_status", ""))
            value = clean(latest_q.get("numeric_value", ""))
            status = clean(latest_q.get("status", ""))

            if approval == "Погоджено":
                css = "q-approved"
            elif approval == "Очікує погодження":
                css = "q-waiting"
            elif approval == "Повернуто на доопрацювання":
                css = "q-returned"
            else:
                css = "q-empty"

        timeline_parts.append(
            f'<div class="timeline-cell {css}">'
            f'<div class="timeline-title">{q} квартал</div>'
            f'<div class="timeline-value">{value}</div>'
            f'<div class="timeline-note">{approval}</div>'
            f'<div class="timeline-note">{status}</div>'
            f'</div>'
        )

    timeline_parts.append("</div>")

    timeline_html = "".join(timeline_parts)

    st.markdown(timeline_html, unsafe_allow_html=True)

    if not has_monitoring:
        st.info(
            f"Для цього заходу ще немає моніторингових заявок. "
            f"Очікуваний період виконання: {clean(selected_measure['start_period'])} — {clean(selected_measure['end_period'])}. "
            f"Головний виконавець: {clean(selected_measure['department'])}."
        )

    st.markdown('</div>', unsafe_allow_html=True)

if view_mode in ["Огляд", "Статуси заявок"]:
    st.markdown('<div class="card"><div class="card-title">Статуси заявок за заходом</div>', unsafe_allow_html=True)

    if measure_requests.empty:
        st.info("Заявок за цим заходом немає.")
    else:
        status_df = (
            measure_requests["approval_status"]
            .fillna("Невідомо")
            .value_counts()
            .reset_index()
        )

        status_df.columns = ["Статус погодження", "Кількість"]

        c1, c2 = st.columns(2)

        with c1:
            fig = px.pie(
                status_df,
                names="Статус погодження",
                values="Кількість",
                hole=0.5,
                title="Розподіл заявок за статусом"
            )
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            fig = px.bar(
                status_df,
                x="Статус погодження",
                y="Кількість",
                text="Кількість",
                title="Кількість заявок за статусами"
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

if view_mode in ["Огляд", "Ризики та відхилення"]:
    st.markdown('<div class="card"><div class="card-title">Ризики та відхилення</div>', unsafe_allow_html=True)

    if measure_requests.empty:
        st.info("Ризики не зафіксовано, оскільки заявок за заходом ще немає.")
    else:
        risk_rows = measure_requests[
            measure_requests["risks"].fillna("").astype(str).str.strip() != ""
        ].copy()

        if risk_rows.empty:
            st.success("У поданих заявках ризики / проблеми / відхилення не зазначені.")
        else:
            risk_show = risk_rows.rename(columns={
                "id": "ID",
                "year": "Рік",
                "quarter": "Квартал",
                "approval_status": "Статус погодження",
                "risks": "Ризики / проблеми / відхилення",
                "submitted_at": "Дата подання"
            })

            st.dataframe(
                risk_show[
                    [
                        "ID",
                        "Рік",
                        "Квартал",
                        "Статус погодження",
                        "Ризики / проблеми / відхилення",
                        "Дата подання"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )

    st.markdown('</div>', unsafe_allow_html=True)

if view_mode in ["Огляд", "Файли та історія"]:
    st.markdown('<div class="card"><div class="card-title">Файли по заходу</div>', unsafe_allow_html=True)

    if measure_requests.empty:
        st.info("Файлів по цьому заходу немає.")
    else:
        files_found = False

        for _, row in measure_requests.iterrows():
            urls = [u.strip() for u in clean(row.get("file_urls", "")).split(",") if u.strip()]
            names = [n.strip() for n in clean(row.get("file_names", "")).split(",") if n.strip()]

            for i, url in enumerate(urls):
                files_found = True
                label = names[i] if i < len(names) else f"Файл {i + 1}"
                st.markdown(
                    f"- Заявка ID {clean(row.get('id', ''))}: [{label}]({url})"
                )

        if not files_found:
            st.info("Файлів по цьому заходу не додано.")

    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Паспорт заходу — повна таблиця</div>', unsafe_allow_html=True)

passport_df = pd.DataFrame([{
    "Код заходу": clean(selected_measure["code"]),
    "Назва заходу": clean(selected_measure["name"]),
    "Індикатор": clean(selected_measure["indicator"]),
    "Одиниця виміру": clean(selected_measure["unit"]),
    "Базове значення 2021": clean(selected_measure["base_2021"]),
    "Звіт 2024": clean(selected_measure["fact_2024"]),
    "Очікуване 2025": clean(selected_measure["expected_2025"]),
    "План 2026": clean(selected_measure["target_2026"]),
    "План 2027": clean(selected_measure["target_2027"]),
    "План 2028": clean(selected_measure["target_2028"]),
    "Департамент": clean(selected_measure["department"]),
    "Початок виконання": clean(selected_measure["start_period"]),
    "Кінець виконання": clean(selected_measure["end_period"]),
}])

with st.expander("Розгорнути повний паспорт заходу"):
    st.dataframe(
        passport_df,
        use_container_width=True,
        hide_index=True
    )

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Історія заявок по заходу</div>', unsafe_allow_html=True)

if measure_requests.empty:
    st.info("Для цього заходу ще немає моніторингових заявок.")
else:
    history_df = measure_requests.rename(columns={
        "id": "ID",
        "year": "Рік",
        "quarter": "Квартал",
        "status": "Статус виконання",
        "approval_status": "Статус погодження",
        "numeric_value": "Фактичне значення",
        "responsible_person": "Відповідальна особа",
        "submitted_at": "Дата подання",
        "admin_comment": "Коментар адміністратора"
    })

    show_cols = [
        "ID",
        "Рік",
        "Квартал",
        "Статус виконання",
        "Статус погодження",
        "Фактичне значення",
        "Відповідальна особа",
        "Дата подання",
        "Коментар адміністратора"
    ]

    available = [c for c in show_cols if c in history_df.columns]

    st.dataframe(
        history_df[available],
        use_container_width=True,
        hide_index=True
    )

st.markdown('</div>', unsafe_allow_html=True)

task_measures = measures[
    measures["code"].astype(str).str.startswith(task_code)
].copy()

task_request_codes = set()

if not requests_df.empty:
    task_request_codes = set(
        requests_df["strat_code"]
        .dropna()
        .astype(str)
        .str.strip()
        .tolist()
    )

task_measures["Є моніторинг"] = task_measures["code"].apply(
    lambda x: "Так" if str(x).strip() in task_request_codes else "Ні"
)

st.markdown('<div class="card"><div class="card-title">Порівняння з іншими заходами завдання</div>', unsafe_allow_html=True)

p1, p2, p3 = st.columns(3)
p1.metric("Заходів у завданні", len(task_measures))
p2.metric("Мають моніторинг", len(task_measures[task_measures["Є моніторинг"] == "Так"]))
p3.metric("Без моніторингу", len(task_measures[task_measures["Є моніторинг"] == "Ні"]))

with st.expander("Переглянути заходи цього завдання"):
    compare_df = task_measures.rename(columns={
        "code": "Код",
        "name": "Захід",
        "indicator": "Індикатор",
        "department": "Департамент"
    })

    st.dataframe(
        compare_df[
            [
                "Код",
                "Захід",
                "Індикатор",
                "Департамент",
                "Є моніторинг"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Швидкі переходи</div>', unsafe_allow_html=True)

n1, n2, n3 = st.columns(3)

with n1:
    st.page_link(
        "pages/1_Моніторинг_виконання.py",
        label="Перейти до внесення моніторингу",
        icon="🖊️"
    )

with n2:
    st.page_link(
        "pages/2_Dashboard.py",
        label="Перейти до аналітики",
        icon="📊"
    )

with n3:
    st.page_link(
        "pages/3_Адміністрування.py",
        label="Перейти до адмінки",
        icon="✅"
    )

st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="footer">
        Міністерство економіки, довкілля та сільського господарства України<br>
        Розроблено департаментом стратегічного планування та макроекономічного прогнозування<br>
        Версія DEMO 0.9 | Паспорт стратегічного заходу
    </div>
    """,
    unsafe_allow_html=True
)
