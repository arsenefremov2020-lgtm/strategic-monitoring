import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime
import re
from html import escape


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

.filter-panel {
    background: linear-gradient(180deg, rgba(239,246,255,0.92), rgba(255,255,255,0.95));
    border: 1px solid #bfdbfe;
    border-radius: 16px;
    padding: 16px 18px 8px 18px;
    margin-top: 12px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.8);
}

div[data-testid="stSelectbox"] > label,
div[data-testid="stTextInput"] > label {
    color: #1e3a8a !important;
    font-weight: 850 !important;
}

div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stTextInput"] input {
    background: #f8fbff !important;
    border: 1px solid #bfdbfe !important;
    border-radius: 12px !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.06) !important;
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
    min-height: 112px;
}

.passport-cell-wide {
    grid-column: span 2;
}

.passport-cell-full {
    grid-column: 1 / -1;
}

.passport-label {
    color: #64748b;
    font-size: 13px;
    margin-bottom: 6px;
}

.passport-value {
    color: #0f172a;
    font-weight: 850;
    font-size: 16px;
    line-height: 1.35;
}

.passport-muted {
    color: #64748b;
    font-size: 13px;
    line-height: 1.45;
    margin-top: 6px;
}

.split-box {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0;
}

.split-box > div:first-child {
    padding-right: 16px;
    border-right: 1px solid #cbd5e1;
}

.split-box > div:last-child {
    padding-left: 16px;
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

.quarter-scale {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-top: 10px;
}

.quarter-card {
    border-radius: 16px;
    border: 1px solid #d8dee9;
    padding: 16px;
    background: #f8fafc;
    min-height: 145px;
}

.quarter-title {
    font-weight: 950;
    color: #0f172a;
    margin-bottom: 8px;
    font-size: 16px;
}

.quarter-value {
    font-size: 23px;
    font-weight: 950;
    color: #0f172a;
    margin-bottom: 5px;
}

.quarter-plan {
    font-size: 13px;
    color: #475569;
    line-height: 1.45;
}

.quarter-status {
    margin-top: 10px;
    font-size: 12px;
    font-weight: 850;
    display: inline-block;
    border-radius: 999px;
    padding: 5px 9px;
}

.q-approved {
    background: #dcfce7;
    border-color: #bbf7d0;
}

.q-approved .quarter-status {
    background: #bbf7d0;
    color: #166534;
}

.q-waiting {
    background: #fef9c3;
    border-color: #fde68a;
}

.q-waiting .quarter-status {
    background: #fde68a;
    color: #854d0e;
}

.q-returned {
    background: #fee2e2;
    border-color: #fecaca;
}

.q-returned .quarter-status {
    background: #fecaca;
    color: #991b1b;
}

.q-empty {
    background: #f8fafc;
}

.q-empty .quarter-status {
    background: #e2e8f0;
    color: #475569;
}

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.9);
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

div[data-testid="stMetricLabel"] {
    min-height: 34px;
}

div[data-testid="stPageLink"] a {
    background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 55%, #16a34a 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 16px !important;
    padding: 16px 18px !important;
    font-weight: 900 !important;
    text-decoration: none !important;
    min-height: 62px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    box-shadow: 0 10px 22px rgba(37,99,235,0.18) !important;
}

div[data-testid="stPageLink"] a:hover {
    filter: brightness(0.97);
    transform: translateY(-1px);
}

.footer {
    text-align: center;
    color: #64748b;
    font-size: 13px;
    margin-top: 50px;
    padding: 22px 0 12px 0;
    border-top: 1px solid #d8dee9;
}

@media (max-width: 980px) {
    .top-grid,
    .passport-grid,
    .quarter-scale,
    .split-box {
        grid-template-columns: 1fr;
    }

    .passport-cell-wide {
        grid-column: auto;
    }

    .split-box > div:first-child {
        border-right: none;
        border-bottom: 1px solid #cbd5e1;
        padding-right: 0;
        padding-bottom: 12px;
        margin-bottom: 12px;
    }

    .split-box > div:last-child {
        padding-left: 0;
    }
}
</style>
""", unsafe_allow_html=True)


def clean(value):
    if value is None or pd.isna(value) or str(value).strip().lower() in ["none", "nan"]:
        return ""
    return str(value).strip()


def display_value(value, fallback="—"):
    text = clean(value)
    return escape(text) if text else fallback


def safe_col(data, idx):
    if idx < data.shape[1]:
        return data.iloc[:, idx]
    return ""


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
        "type_marker": safe_col(data, 1),
        "code": safe_col(data, 2),
        "name": safe_col(data, 3),
        "indicator": safe_col(data, 5),
        "unit": safe_col(data, 6),
        "base_2021": safe_col(data, 7),
        "fact_2024": safe_col(data, 8),
        "expected_2025": safe_col(data, 9),
        "target_2026": safe_col(data, 10),
        "target_2027": safe_col(data, 11),
        "target_2028": safe_col(data, 12),

        # За потреби ці індекси можна точково підлаштувати під фактичну структуру Excel.
        "department": safe_col(data, 17),
        "co_executor": safe_col(data, 18),
        "product_type": safe_col(data, 19),
        "year": safe_col(data, 20),
        "deputy_minister": safe_col(data, 21),

        "start_period": safe_col(data, 22),
        "end_period": safe_col(data, 23),

        # Фінансування: колонки Y-AF.
        "finance_y": safe_col(data, 24),
        "finance_z": safe_col(data, 25),
        "finance_aa": safe_col(data, 26),
        "finance_ab": safe_col(data, 27),
        "finance_ac": safe_col(data, 28),
        "finance_ad": safe_col(data, 29),
        "finance_ae": safe_col(data, 30),
        "finance_af": safe_col(data, 31),
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


def split_first_executor(value):
    text = clean(value)

    if not text:
        return ""

    for sep in ["\n", ";", "|"]:
        if sep in text:
            return clean(text.split(sep)[0])

    return text


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


def format_amount_bln(value):
    text = clean(value)
    number = to_number(text)

    if number is None:
        return text if text else "—"

    return f"{number:g} млрд грн"


def first_numeric_value(values):
    for value in values:
        number = to_number(value)
        if number is not None:
            return value
    return ""


def financing_html(row):
    finance_values = [
        row.get("finance_y", ""),
        row.get("finance_z", ""),
        row.get("finance_aa", ""),
        row.get("finance_ab", ""),
        row.get("finance_ac", ""),
        row.get("finance_ad", ""),
        row.get("finance_ae", ""),
        row.get("finance_af", ""),
    ]

    if all(clean(v) == "" for v in finance_values):
        return '<div class="passport-value">Відсутнє</div>'

    y = clean(row.get("finance_y", ""))
    z = clean(row.get("finance_z", ""))
    aa = clean(row.get("finance_aa", ""))
    ab = clean(row.get("finance_ab", ""))
    ac = clean(row.get("finance_ac", ""))

    ad = clean(row.get("finance_ad", ""))
    ae = clean(row.get("finance_ae", ""))
    af = clean(row.get("finance_af", ""))

    state_budget_parts = [y, z, aa, ab, ac]
    other_parts = [ad, ae, af]

    has_state_budget = any(v for v in state_budget_parts)
    has_other = any(v for v in other_parts)

    state_amount_2026 = first_numeric_value([aa, ab, ac])
    other_amount_2026 = first_numeric_value([ae, af])

    state_html = ""
    other_html = ""

    if has_state_budget:
        kpkvk = z if z else y
        state_html = f"""
        <div>
            <div class="passport-label">Державний бюджет</div>
            <div class="passport-value">КПКВК {escape(kpkvk) if kpkvk else "—"}</div>
            <div class="passport-muted">2026 рік: {escape(format_amount_bln(state_amount_2026))}</div>
        </div>
        """

    if has_other:
        source = ad if ad else "Інші джерела"
        other_html = f"""
        <div>
            <div class="passport-label">Інші джерела</div>
            <div class="passport-value">{escape(source)}</div>
            <div class="passport-muted">2026 рік: {escape(format_amount_bln(other_amount_2026))}</div>
        </div>
        """

    if has_state_budget and has_other:
        return f'<div class="split-box">{state_html}{other_html}</div>'

    return state_html or other_html or '<div class="passport-value">Відсутнє</div>'


def period_plan_text(row):
    values = [
        f"2026: {clean(row.get('target_2026', ''))}",
        f"2027: {clean(row.get('target_2027', ''))}",
        f"2028: {clean(row.get('target_2028', ''))}",
    ]

    return " | ".join([v for v in values if not v.endswith(": ")])


def get_quarter_css(approval):
    if approval == "Погоджено":
        return "q-approved"
    if approval == "Очікує погодження":
        return "q-waiting"
    if approval == "Повернуто на доопрацювання":
        return "q-returned"
    return "q-empty"


def get_measure_label(row):
    return f"{row['code']} — {row['name']}"


def get_goal_label(row):
    return f"{row['code']} — {row['name']}"


def get_task_label(row):
    return f"{row['code']} — {row['name']}"


st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="top-grid">
        <div class="hero-card">
            <div class="hero-kicker">Паспорт стратегічного заходу</div>
            <div class="hero-title">Картка заходу</div>
            <div class="hero-subtitle">
                Сторінка відображає повний профіль окремого заходу: його місце у Стратегічному плані,
                планові показники, результати квартального моніторингу, інформацію щодо ризиків та
                історію подання відомостей.
            </div>
        </div>
        <div class="ministry-card">
            <div class="ministry-title">🇺🇦 Міністерство економіки, довкілля та сільського господарства України</div>
            <div class="ministry-line">Внутрішня демо-система моніторингу стратегічного плану.</div>
            <div class="status-pill-wrap">
                <div class="status-pill">● Режим: картка заходу</div>
                <div class="status-pill">● Джерело: Excel + Supabase</div>
                <div class="status-pill">● Оновлено: {datetime.now().strftime("%d.%m.%Y %H:%M")}</div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

df = load_strat_matrix()
requests_df = load_requests()

goals = df[df["object_type"] == "goal"].copy()
tasks = df[df["object_type"] == "task"].copy()
measures = df[df["object_type"] == "measure"].copy()

if measures.empty:
    st.warning("Заходів у стратегічній матриці не знайдено.")
    st.stop()

measures["goal_code"] = measures["code"].apply(get_goal_code)
measures["task_code"] = measures["code"].apply(get_task_code)
tasks["goal_code"] = tasks["code"].apply(get_goal_code)

st.markdown(
    """
    <div class="card">
        <div class="card-title">Вибір заходу</div>
        <div class="card-subtitle">
            Спочатку оберіть стратегічну ціль, потім завдання, після цього — конкретний захід.
            Пошук за ключовими словами додатково звужує перелік заходів.
        </div>
        <div class="filter-panel">
    """,
    unsafe_allow_html=True
)

f1, f2, f3, f4 = st.columns([1.15, 1.15, 1.6, 1.1])

goal_options = ["Усі стратегічні цілі"] + [
    get_goal_label(row) for _, row in goals.iterrows()
]

with f1:
    selected_goal_label = st.selectbox(
        "Стратегічна ціль",
        goal_options,
        index=0
    )

if selected_goal_label == "Усі стратегічні цілі":
    selected_goal_code = ""
    filtered_tasks = tasks.copy()
    filtered_measures_by_goal = measures.copy()
else:
    selected_goal_code = selected_goal_label.split("—")[0].strip()
    filtered_tasks = tasks[tasks["goal_code"] == selected_goal_code].copy()
    filtered_measures_by_goal = measures[measures["goal_code"] == selected_goal_code].copy()

task_options = ["Усі завдання"] + [
    get_task_label(row) for _, row in filtered_tasks.iterrows()
]

with f2:
    selected_task_label = st.selectbox(
        "Завдання",
        task_options,
        index=0
    )

if selected_task_label == "Усі завдання":
    selected_task_code_filter = ""
    filtered_measures_by_task = filtered_measures_by_goal.copy()
else:
    selected_task_code_filter = selected_task_label.split("—")[0].strip()
    filtered_measures_by_task = filtered_measures_by_goal[
        filtered_measures_by_goal["task_code"] == selected_task_code_filter
    ].copy()

with f4:
    keyword = st.text_input(
        "За ключовими словами",
        value="",
        placeholder="Введіть слово або код"
    )

if clean(keyword):
    kw = clean(keyword).lower()
    filtered_measures_by_task = filtered_measures_by_task[
        filtered_measures_by_task["code"].astype(str).str.lower().str.contains(kw, na=False) |
        filtered_measures_by_task["name"].astype(str).str.lower().str.contains(kw, na=False) |
        filtered_measures_by_task["indicator"].astype(str).str.lower().str.contains(kw, na=False) |
        filtered_measures_by_task["department"].astype(str).str.lower().str.contains(kw, na=False)
    ].copy()

if filtered_measures_by_task.empty:
    st.markdown("</div></div>", unsafe_allow_html=True)
    st.warning("За обраними фільтрами заходів не знайдено.")
    st.stop()

measure_options = [
    get_measure_label(row)
    for _, row in filtered_measures_by_task.iterrows()
]

with f3:
    selected_option = st.selectbox(
        "Захід",
        measure_options,
        index=0
    )

st.markdown("</div></div>", unsafe_allow_html=True)

selected_code = selected_option.split("—")[0].strip()

selected_measure = measures[
    measures["code"].astype(str).str.strip() == selected_code
].iloc[0]

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

if not requests_df.empty and "strat_code" in requests_df.columns:
    measure_requests = requests_df[
        requests_df["strat_code"].astype(str).str.strip() == selected_code
    ].copy()

has_monitoring = not measure_requests.empty

approved_requests = pd.DataFrame()

if has_monitoring and "approval_status" in measure_requests.columns:
    approved_requests = measure_requests[
        measure_requests["approval_status"].astype(str) == "Погоджено"
    ].copy()

latest_request = None

if has_monitoring and "submitted_at" in measure_requests.columns:
    latest_request = measure_requests.sort_values("submitted_at", ascending=False).iloc[0]
elif has_monitoring:
    latest_request = measure_requests.iloc[0]

latest_approved = None

if not approved_requests.empty and "submitted_at" in approved_requests.columns:
    latest_approved = approved_requests.sort_values("submitted_at", ascending=False).iloc[0]
elif not approved_requests.empty:
    latest_approved = approved_requests.iloc[0]

target_value = selected_measure.get("target_2026", "")
latest_actual = latest_approved.get("numeric_value", "") if latest_approved is not None else ""
progress_percent = plan_fact_percent(latest_actual, target_value)

if progress_percent is None:
    progress_percent = status_score(latest_approved.get("status", "")) if latest_approved is not None else 0

total_requests = len(measure_requests)
approved_count = len(measure_requests[measure_requests["approval_status"] == "Погоджено"]) if has_monitoring and "approval_status" in measure_requests.columns else 0
returned_count = len(measure_requests[measure_requests["approval_status"] == "Повернуто на доопрацювання"]) if has_monitoring and "approval_status" in measure_requests.columns else 0
waiting_count = len(measure_requests[measure_requests["approval_status"] == "Очікує погодження"]) if has_monitoring and "approval_status" in measure_requests.columns else 0

co_executor_first = split_first_executor(selected_measure.get("co_executor", ""))
deputy_minister = clean(selected_measure.get("deputy_minister", "")) or "ПЕТРЕНКО Петро Петрович"
selected_year = clean(selected_measure.get("year", ""))

if not selected_year and latest_request is not None:
    selected_year = clean(latest_request.get("year", ""))

if not selected_year:
    selected_year = "2026"

st.markdown('<div class="card"><div class="card-title">Паспорт заходу</div>', unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="badge-wrap">
        <div class="badge">Код: {display_value(selected_code)}</div>
        <div class="badge">Департамент: {display_value(selected_measure.get("department", ""))}</div>
        <div class="badge">Моніторингових заявок: {total_requests}</div>
    </div>
    <div style="font-size:24px;font-weight:900;color:#0f172a;line-height:1.25;margin-top:10px;">
        {display_value(selected_measure.get("name", ""))}
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="passport-grid">
        <div class="passport-cell">
            <div class="passport-label">Стратегічна ціль</div>
            <div class="passport-value">{display_value(goal_code)}</div>
            <div class="passport-muted">{display_value(goal_name)}</div>
        </div>

        <div class="passport-cell">
            <div class="passport-label">Завдання</div>
            <div class="passport-value">{display_value(task_code)}</div>
            <div class="passport-muted">{display_value(task_name)}</div>
        </div>

        <div class="passport-cell">
            <div class="split-box">
                <div>
                    <div class="passport-label">Головний виконавець</div>
                    <div class="passport-value">{display_value(selected_measure.get("department", ""))}</div>
                </div>
                <div>
                    <div class="passport-label">Співвиконавець</div>
                    <div class="passport-value">{display_value(co_executor_first)}</div>
                </div>
            </div>
        </div>

        <div class="passport-cell">
            <div class="passport-label">Замміністра</div>
            <div class="passport-value">{display_value(deputy_minister)}</div>
        </div>

        <div class="passport-cell">
            <div class="passport-label">Тип продукту</div>
            <div class="passport-value">{display_value(selected_measure.get("product_type", ""))}</div>
        </div>

        <div class="passport-cell">
            <div class="passport-label">Рік</div>
            <div class="passport-value">{display_value(selected_year)}</div>
        </div>

        <div class="passport-cell">
            <div class="passport-label">Початок виконання</div>
            <div class="passport-value">{display_value(selected_measure.get("start_period", ""))}</div>
        </div>

        <div class="passport-cell">
            <div class="passport-label">Кінець виконання</div>
            <div class="passport-value">{display_value(selected_measure.get("end_period", ""))}</div>
        </div>

        <div class="passport-cell">
            <div class="passport-label">Одиниця виміру</div>
            <div class="passport-value">{display_value(selected_measure.get("unit", ""))}</div>
        </div>

        <div class="passport-cell passport-cell-wide">
            <div class="passport-label">Індикатор</div>
            <div class="passport-value">{display_value(selected_measure.get("indicator", ""))}</div>
        </div>

        <div class="passport-cell">
            <div class="passport-label">Планові показники</div>
            <div class="passport-value">{display_value(period_plan_text(selected_measure))}</div>
        </div>

        <div class="passport-cell passport-cell-full">
            <div class="passport-label">Фінансування</div>
            {financing_html(selected_measure)}
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("План 2026", clean(selected_measure.get("target_2026", "")) or "—")
k2.metric("Останнє фактичне значення, подане ССП", clean(latest_actual) or "—")
k3.metric("Прогрес", f"{round(progress_percent, 1)}%")
k4.metric("Погоджено", approved_count)
k5.metric("Очікує", waiting_count)

st.markdown('<div class="card"><div class="card-title">Аналітичний висновок</div>', unsafe_allow_html=True)

if total_requests == 0:
    conclusion = (
        "За цим заходом ще не зафіксовано погоджених квартальних даних. "
        "Поточна оцінка прогресу базується на наявності або відсутності поданих ССП відомостей."
    )
elif progress_percent >= 70:
    conclusion = (
        "Захід має достатній рівень підтвердженого прогресу за наявними погодженими даними. "
        "Критичних ознак відставання за поточним показником не виявлено."
    )
elif progress_percent >= 35:
    conclusion = (
        "Захід перебуває у проміжному стані виконання. "
        "Потрібне подальше квартальне оновлення фактичних значень для точнішої оцінки динаміки."
    )
else:
    conclusion = (
        "Поточний прогрес заходу є низьким або недостатньо підтвердженим погодженими даними. "
        "Доцільно перевірити актуальність поданих ССП відомостей і планове значення на відповідний рік."
    )

st.markdown(
    f"""
    <div class="badge-wrap">
        <div class="badge">Прогрес: {round(progress_percent, 1)}%</div>
        <div class="badge">Заявок: {total_requests}</div>
        <div class="badge">Погоджено: {approved_count}</div>
        <div class="badge">Повернень: {returned_count}</div>
    </div>
    <div style="color:#475569;font-size:14px;line-height:1.55;">{escape(conclusion)}</div>
    """,
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)

view_mode = st.selectbox(
    "Тип візуалізації",
    [
        "Огляд",
        "Індикатор прогресу",
        "Квартальна динаміка",
        "Статуси заявок",
        "Історія подання відомостей"
    ]
)

if view_mode in ["Огляд", "Індикатор прогресу"]:
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
            "Якщо є числовий план і факт — рахується співвідношення фактичного значення до планового. "
            "Якщо показник має формат так/ні — значення «так» відповідає 100%, «ні» відповідає 0%. "
            "Якщо погоджених даних немає — прогрес відображається як 0%."
        )
        st.progress(min(progress_percent / 100, 1.0), text=f"Прогрес: {round(progress_percent, 1)}%")

    st.markdown('</div>', unsafe_allow_html=True)

if view_mode in ["Огляд", "Квартальна динаміка"]:
    st.markdown(
        '<div class="card"><div class="card-title">Динаміка планових і звітних даних за кварталами</div>'
        '<div class="card-subtitle">Шкала показує подані ССП фактичні значення та статус погодження за кожним кварталом.</div>',
        unsafe_allow_html=True
    )

    quarters = ["I", "II", "III", "IV"]
    quarter_html = ['<div class="quarter-scale">']

    for q in quarters:
        q_data = pd.DataFrame()

        if has_monitoring and "quarter" in measure_requests.columns:
            q_data = measure_requests[
                measure_requests["quarter"].astype(str) == q
            ].copy()

        if q_data.empty:
            css = "q-empty"
            value = "—"
            approval = "Не подано"
            status = ""
            submitted = ""
        else:
            if "submitted_at" in q_data.columns:
                latest_q = q_data.sort_values("submitted_at", ascending=False).iloc[0]
            else:
                latest_q = q_data.iloc[0]

            approval = clean(latest_q.get("approval_status", ""))
            value = clean(latest_q.get("numeric_value", ""))
            status = clean(latest_q.get("status", ""))
            submitted = clean(latest_q.get("submitted_at", ""))
            css = get_quarter_css(approval)

        quarter_html.append(
            f"""
            <div class="quarter-card {css}">
                <div class="quarter-title">{q} квартал</div>
                <div class="quarter-value">{escape(value) if value else "—"}</div>
                <div class="quarter-plan">План 2026: {display_value(selected_measure.get("target_2026", ""))}</div>
                <div class="quarter-plan">Статус виконання: {escape(status) if status else "—"}</div>
                <div class="quarter-plan">Дата подання: {escape(submitted) if submitted else "—"}</div>
                <div class="quarter-status">{escape(approval) if approval else "Не подано"}</div>
            </div>
            """
        )

    quarter_html.append("</div>")
    st.markdown("".join(quarter_html), unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

if view_mode in ["Огляд", "Статуси заявок"]:
    st.markdown('<div class="card"><div class="card-title">Статуси заявок за заходом</div>', unsafe_allow_html=True)

    if measure_requests.empty or "approval_status" not in measure_requests.columns:
        st.info("Заявок за цим заходом немає.")
    else:
        status_df = (
            measure_requests["approval_status"]
            .fillna("Невідомо")
            .value_counts()
            .reset_index()
        )

        status_df.columns = ["Статус погодження", "Кількість"]

        fig = go.Figure(
            data=[
                go.Bar(
                    x=status_df["Статус погодження"],
                    y=status_df["Кількість"],
                    text=status_df["Кількість"],
                    textposition="auto"
                )
            ]
        )

        fig.update_layout(
            title="Кількість заявок за статусами",
            height=360,
            margin=dict(l=20, r=20, t=60, b=40),
            xaxis_title="Статус погодження",
            yaxis_title="Кількість"
        )

        st.plotly_chart(fig, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

if view_mode in ["Огляд", "Історія подання відомостей"]:
    st.markdown('<div class="card"><div class="card-title">Історія подання відомостей</div>', unsafe_allow_html=True)

    if measure_requests.empty:
        st.info("Для цього заходу ще немає поданих відомостей.")
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

st.markdown('<div class="card"><div class="card-title">Швидкі переходи</div>', unsafe_allow_html=True)

n1, n2 = st.columns(2)

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

st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="footer">
        Міністерство економіки, довкілля та сільського господарства України<br>
        Розроблено департаментом стратегічного планування та макроекономічного прогнозування<br>
        Версія DEMO 1.4 | Паспорт стратегічного заходу
    </div>
    """,
    unsafe_allow_html=True
)
