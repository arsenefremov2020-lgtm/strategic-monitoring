import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime, timezone
from io import BytesIO
import re

st.set_page_config(page_title="Контроль якості даних", layout="wide")

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

.header-box, .card {
    background: rgba(255,255,255,0.94);
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 18px;
    box-shadow: 0 8px 24px rgba(15,23,42,0.06);
}

.header-title {
    font-size: 32px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 8px;
}

.header-subtitle, .card-subtitle {
    font-size: 15px;
    color: #475569;
    line-height: 1.55;
}

.card-title {
    font-size: 21px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 8px;
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

.alert-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin: 14px 0;
}

.alert-card {
    border-radius: 14px;
    padding: 16px;
    border: 1px solid #d8dee9;
    background: white;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

.alert-title {
    font-size: 13px;
    color: #64748b;
    font-weight: 800;
}

.alert-value {
    font-size: 28px;
    color: #0f172a;
    font-weight: 950;
    margin-top: 4px;
}

.alert-red {
    background: #fee2e2;
    border-color: #fecaca;
}

.alert-yellow {
    background: #fef9c3;
    border-color: #fde68a;
}

.alert-green {
    background: #dcfce7;
    border-color: #bbf7d0;
}

.alert-blue {
    background: #dbeafe;
    border-color: #bfdbfe;
}

.issue-card {
    border-radius: 14px;
    border: 1px solid #d8dee9;
    background: #ffffff;
    padding: 16px 18px;
    margin: 10px 0;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

.issue-critical {
    border-left: 7px solid #dc2626;
}

.issue-warning {
    border-left: 7px solid #f59e0b;
}

.issue-info {
    border-left: 7px solid #2563eb;
}

.issue-ok {
    border-left: 7px solid #16a34a;
}

.issue-title {
    font-size: 16px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 5px;
}

.issue-text {
    color: #475569;
    font-size: 14px;
    line-height: 1.5;
}

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.9);
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

div.stDownloadButton > button {
    border-radius: 12px;
    padding: 12px 18px;
    font-weight: 850;
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


def clean(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value)


def has_value(value):
    return clean(value).strip() != ""


def parse_period(value):
    text = str(value).lower().strip()

    if text in ["", "nan", "none", "н.д."]:
        return None

    q = None
    year = None

    if "1 квартал" in text or "i квартал" in text:
        q = 1
    elif "2 квартал" in text or "ii квартал" in text:
        q = 2
    elif "3 квартал" in text or "iii квартал" in text:
        q = 3
    elif "4 квартал" in text or "iv квартал" in text:
        q = 4

    year_match = re.search(r"20\\d{2}", text)

    if year_match:
        year = int(year_match.group())

    if year and q:
        return year * 10 + q

    return None


def quarter_to_number(q):
    return {"I": 1, "II": 2, "III": 3, "IV": 4}.get(str(q), 1)


def get_goal_code(code):
    parts = str(code).split(".")
    return parts[0] + "." if parts else ""


def get_task_code(code):
    parts = str(code).split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}."
    return ""


def valid_email(value):
    text = clean(value).strip()
    if not text:
        return False
    return re.match(r"^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", text) is not None


def to_datetime(value):
    text = clean(value).strip()

    if not text:
        return None

    try:
        dt = pd.to_datetime(text, errors="coerce", utc=True)
        if pd.isna(dt):
            return None
        return dt.to_pydatetime()
    except Exception:
        return None


def days_waiting(value):
    dt = to_datetime(value)
    if not dt:
        return None
    now = datetime.now(timezone.utc)
    return (now - dt).days


def to_number(value):
    text = str(value).replace(",", ".").strip()

    if text.lower() in ["", "nan", "none", "н.д.", "x", "х", "так", "ні", "да", "нет"]:
        return None

    match = re.search(r"-?\\d+(\\.\\d+)?", text)

    if match:
        try:
            return float(match.group())
        except Exception:
            return None

    return None


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
        .order("submitted_at", desc=True)
        .execute()
    )

    return pd.DataFrame(response.data or [])


def make_issue_table(issue_type, severity, df, explanation):
    if df.empty:
        return pd.DataFrame(columns=[
            "issue_type", "severity", "explanation"
        ])

    out = df.copy()
    out.insert(0, "issue_type", issue_type)
    out.insert(1, "severity", severity)
    out.insert(2, "explanation", explanation)
    return out


def issue_card(title, value, text, level="info"):
    css = {
        "critical": "issue-critical",
        "warning": "issue-warning",
        "info": "issue-info",
        "ok": "issue-ok"
    }.get(level, "issue-info")

    st.markdown(
        f"""
        <div class="issue-card {css}">
            <div class="issue-title">{title}: {value}</div>
            <div class="issue-text">{text}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def prepare_active_measures(strat_df, year, quarter, department):
    measures = strat_df[strat_df["object_type"] == "measure"].copy()
    goals = strat_df[strat_df["object_type"] == "goal"].copy()

    measures["goal_code"] = measures["code"].apply(get_goal_code)
    measures["task_code"] = measures["code"].apply(get_task_code)
    measures["strategic_goal"] = measures["goal_code"].map(goals.set_index("code")["name"].to_dict())

    measures["start_num"] = measures["start_period"].apply(parse_period)
    measures["end_num"] = measures["end_period"].apply(parse_period)

    selected_q_num = quarter_to_number(quarter)
    selected_period_num = int(year) * 10 + selected_q_num

    active = measures[
        (
            measures["start_num"].isna()
            |
            (measures["start_num"] <= selected_period_num)
        )
        &
        (
            measures["end_num"].isna()
            |
            (measures["end_num"] >= selected_period_num)
        )
    ].copy()

    if department != "Усі":
        active = active[active["department"].astype(str) == str(department)]

    return active


def create_quality_excel(tables):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_format = workbook.add_format({
            "bold": True,
            "bg_color": "#D9EAF7",
            "border": 1
        })

        for sheet_name, table in tables.items():
            safe_sheet = sheet_name[:31]
            table.to_excel(writer, sheet_name=safe_sheet, index=False)
            worksheet = writer.sheets[safe_sheet]
            worksheet.freeze_panes(1, 0)

            for col_num, value in enumerate(table.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, 22)

    output.seek(0)
    return output


st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)

st.markdown("""
<div class="ministry-label">
🇺🇦 Міністерство економіки, довкілля та сільського господарства України
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="header-box">
    <div class="header-title">Контроль якості даних</div>
    <div class="header-subtitle">
        Автоматична перевірка якості моніторингових даних: дублікати, пропущені подання,
        некоректні email, заявки без файлів, погоджені записи без факту, довге очікування,
        різні значення за один захід і квартал, департаменти без подання.
    </div>
    <div class="badge-wrap">
        <div class="badge">● Режим: data quality control</div>
        <div class="badge">● Джерело: стратегічна матриця + Supabase</div>
        <div class="badge">● Не змінює дані</div>
        <div class="badge">● Оновлено: {datetime.now().strftime("%d.%m.%Y %H:%M")}</div>
    </div>
</div>
""", unsafe_allow_html=True)

strat_df = load_strat_matrix()
requests_df = load_requests()

if requests_df.empty:
    st.warning("У Supabase поки що немає заявок для перевірки.")
    st.stop()

required_cols = [
    "id", "year", "quarter", "department", "responsible_person", "phone", "email",
    "strat_code", "status", "progress_text", "numeric_value", "risks",
    "submitted_at", "approval_status", "admin_comment", "file_names", "file_urls",
    "start_date", "end_date"
]

for col in required_cols:
    if col not in requests_df.columns:
        requests_df[col] = ""

measures_all = strat_df[strat_df["object_type"] == "measure"].copy()

st.markdown('<div class="card"><div class="card-title">Параметри перевірки</div><div class="card-subtitle">Оберіть період і підрозділ для контролю якості даних.</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)

with c1:
    selected_year = st.selectbox("Рік", [2026, 2027, 2028])

with c2:
    selected_quarter = st.selectbox("Квартал", ["I", "II", "III", "IV"])

with c3:
    departments = sorted(measures_all["department"].dropna().astype(str).unique().tolist())
    selected_department = st.selectbox("Департамент", ["Усі"] + departments)

with c4:
    waiting_threshold = st.number_input(
        "Поріг довгого очікування, днів",
        min_value=1,
        max_value=60,
        value=7,
        step=1
    )

st.markdown('</div>', unsafe_allow_html=True)

active = prepare_active_measures(
    strat_df,
    selected_year,
    selected_quarter,
    selected_department
)

period_requests = requests_df[
    (requests_df["year"].astype(str) == str(selected_year)) &
    (requests_df["quarter"].astype(str) == str(selected_quarter))
].copy()

if selected_department != "Усі":
    period_requests = period_requests[
        period_requests["department"].astype(str) == str(selected_department)
    ].copy()

approved_requests = period_requests[
    period_requests["approval_status"].astype(str) == "Погоджено"
].copy()

waiting_requests = period_requests[
    period_requests["approval_status"].astype(str) == "Очікує погодження"
].copy()

returned_requests = period_requests[
    period_requests["approval_status"].astype(str) == "Повернуто на доопрацювання"
].copy()

# 1. Дублікати заявок по одному заходу / кварталу / департаменту
duplicate_keys = ["year", "quarter", "department", "strat_code"]
duplicates = (
    period_requests
    .groupby(duplicate_keys, dropna=False)
    .size()
    .reset_index(name="count")
)
duplicates = duplicates[duplicates["count"] > 1]

if not duplicates.empty:
    duplicates_detail = period_requests.merge(
        duplicates[duplicate_keys],
        on=duplicate_keys,
        how="inner"
    ).sort_values(["strat_code", "submitted_at"])
else:
    duplicates_detail = pd.DataFrame()

# 2. Погоджені заявки без файлів
approved_without_files = approved_requests[
    approved_requests["file_urls"].fillna("").astype(str).str.strip() == ""
].copy()

# 3. Погоджені заявки без фактичного значення
approved_without_fact = approved_requests[
    approved_requests["numeric_value"].fillna("").astype(str).str.strip() == ""
].copy()

# 4. Заявки без email / некоректний email
email_issues = period_requests[
    ~period_requests["email"].apply(valid_email)
].copy()

# 5. Активні заходи без подання
submitted_codes = set(period_requests["strat_code"].dropna().astype(str).str.strip().tolist())
approved_codes = set(approved_requests["strat_code"].dropna().astype(str).str.strip().tolist())

active_without_submission = active[
    ~active["code"].astype(str).str.strip().isin(submitted_codes)
].copy()

active_without_approved = active[
    ~active["code"].astype(str).str.strip().isin(approved_codes)
].copy()

# 6. Департаменти, які не подали нічого
active_by_dep = active.groupby("department").size().reset_index(name="active_measures")
submitted_by_dep = period_requests.groupby("department").size().reset_index(name="submitted_requests")

dep_submission = active_by_dep.merge(
    submitted_by_dep,
    on="department",
    how="left"
)

dep_submission["submitted_requests"] = dep_submission["submitted_requests"].fillna(0).astype(int)
departments_without_submission = dep_submission[
    dep_submission["submitted_requests"] == 0
].copy()

# 7. Різні значення по одному заходу за один квартал
value_conflicts = (
    period_requests
    .groupby(duplicate_keys, dropna=False)["numeric_value"]
    .nunique()
    .reset_index(name="unique_values")
)
value_conflicts = value_conflicts[value_conflicts["unique_values"] > 1]

if not value_conflicts.empty:
    value_conflicts_detail = period_requests.merge(
        value_conflicts[duplicate_keys],
        on=duplicate_keys,
        how="inner"
    ).sort_values(["strat_code", "submitted_at"])
else:
    value_conflicts_detail = pd.DataFrame()

# 8. Заявки з ризиками
requests_with_risks = period_requests[
    period_requests["risks"].fillna("").astype(str).str.strip() != ""
].copy()

# 9. Заявки, які довго очікують погодження
waiting_requests["days_waiting"] = waiting_requests["submitted_at"].apply(days_waiting)
long_waiting = waiting_requests[
    waiting_requests["days_waiting"].fillna(0) >= int(waiting_threshold)
].copy()

# 10. Статус "Виконано", але факт виглядає як ні / 0
bad_completed = period_requests[
    (period_requests["status"].astype(str) == "Виконано") &
    (
        period_requests["numeric_value"].astype(str).str.lower().str.strip().isin(["0", "ні", "нi", "no"])
    )
].copy()

# 11. Статус "Виконано", але немає файлів
completed_without_files = period_requests[
    (period_requests["status"].astype(str) == "Виконано") &
    (period_requests["file_urls"].fillna("").astype(str).str.strip() == "")
].copy()

# 12. Подання по неактивних у кварталі заходах
active_codes = set(active["code"].dropna().astype(str).str.strip().tolist())
submitted_inactive = period_requests[
    ~period_requests["strat_code"].astype(str).str.strip().isin(active_codes)
].copy()

issue_tables = {
    "Дублікати заявок": make_issue_table(
        "Дублікати заявок",
        "Критично",
        duplicates_detail,
        "Більше однієї заявки за одним заходом, департаментом, роком і кварталом."
    ),
    "Погоджені без файлів": make_issue_table(
        "Погоджені без файлів",
        "Попередження",
        approved_without_files,
        "Погоджена заявка не має підтвердних файлів."
    ),
    "Погоджені без факту": make_issue_table(
        "Погоджені без факту",
        "Критично",
        approved_without_fact,
        "Погоджена заявка не має фактичного значення."
    ),
    "Email проблеми": make_issue_table(
        "Email проблеми",
        "Попередження",
        email_issues,
        "Email відсутній або має некоректний формат."
    ),
    "Активні без подання": make_issue_table(
        "Активні без подання",
        "Критично",
        active_without_submission,
        "Захід активний у вибраному кварталі, але по ньому немає поданої заявки."
    ),
    "Активні без погоджених даних": make_issue_table(
        "Активні без погоджених даних",
        "Критично",
        active_without_approved,
        "Захід активний у вибраному кварталі, але по ньому немає погоджених даних."
    ),
    "Департаменти без подання": make_issue_table(
        "Департаменти без подання",
        "Критично",
        departments_without_submission,
        "Департамент має активні заходи, але не подав жодної заявки за період."
    ),
    "Різні значення": make_issue_table(
        "Різні значення",
        "Критично",
        value_conflicts_detail,
        "За одним заходом у межах кварталу подано різні фактичні значення."
    ),
    "Заявки з ризиками": make_issue_table(
        "Заявки з ризиками",
        "Інформаційно",
        requests_with_risks,
        "У заявці зазначено ризики, проблеми або відхилення."
    ),
    "Довге очікування": make_issue_table(
        "Довге очікування",
        "Попередження",
        long_waiting,
        f"Заявка очікує погодження {waiting_threshold} або більше днів."
    ),
    "Виконано але факт 0": make_issue_table(
        "Виконано але факт 0",
        "Критично",
        bad_completed,
        "Статус виконання — виконано, але фактичне значення дорівнює 0 або ні."
    ),
    "Виконано без файлів": make_issue_table(
        "Виконано без файлів",
        "Попередження",
        completed_without_files,
        "Заявка має статус виконано, але не містить підтвердних файлів."
    ),
    "Подання по неактивних": make_issue_table(
        "Подання по неактивних",
        "Попередження",
        submitted_inactive,
        "Подано заявку по заходу, який не є активним у вибраному кварталі."
    )
}

critical_count = (
    len(duplicates_detail)
    + len(approved_without_fact)
    + len(active_without_submission)
    + len(active_without_approved)
    + len(departments_without_submission)
    + len(value_conflicts_detail)
    + len(bad_completed)
)

warning_count = (
    len(approved_without_files)
    + len(email_issues)
    + len(long_waiting)
    + len(completed_without_files)
    + len(submitted_inactive)
)

info_count = len(requests_with_risks)

total_issues = critical_count + warning_count + info_count

quality_score = max(0, 100 - min(100, critical_count * 5 + warning_count * 2 + info_count * 0.5))
quality_score = round(quality_score, 1)

st.markdown(f"""
<div class="alert-grid">
    <div class="alert-card alert-blue">
        <div class="alert-title">Quality score</div>
        <div class="alert-value">{quality_score}%</div>
    </div>
    <div class="alert-card alert-red">
        <div class="alert-title">Критичних проблем</div>
        <div class="alert-value">{critical_count}</div>
    </div>
    <div class="alert-card alert-yellow">
        <div class="alert-title">Попереджень</div>
        <div class="alert-value">{warning_count}</div>
    </div>
    <div class="alert-card alert-green">
        <div class="alert-title">Перевірено заявок</div>
        <div class="alert-value">{len(period_requests)}</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Висновок системи</div>', unsafe_allow_html=True)

if critical_count == 0 and warning_count == 0:
    issue_card(
        "Стан якості даних",
        "Без суттєвих проблем",
        "Система не виявила критичних помилок або попереджень за обраний період.",
        "ok"
    )
elif critical_count == 0:
    issue_card(
        "Стан якості даних",
        "Потрібна точкова перевірка",
        "Критичних помилок не виявлено, але є попередження, які бажано переглянути перед формуванням підсумкового звіту.",
        "warning"
    )
else:
    issue_card(
        "Стан якості даних",
        "Потрібне доопрацювання",
        "Виявлено критичні проблеми, які можуть вплинути на коректність оцінки виконання стратегічного плану.",
        "critical"
    )

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Карта проблем</div><div class="card-subtitle">Автоматично сформований перелік перевірок.</div>', unsafe_allow_html=True)

issue_summary = pd.DataFrame([
    ["Дублікати заявок", len(duplicates_detail), "Критично"],
    ["Погоджені заявки без файлів", len(approved_without_files), "Попередження"],
    ["Погоджені заявки без факту", len(approved_without_fact), "Критично"],
    ["Некоректний або відсутній email", len(email_issues), "Попередження"],
    ["Активні заходи без подання", len(active_without_submission), "Критично"],
    ["Активні заходи без погоджених даних", len(active_without_approved), "Критично"],
    ["Департаменти без подання", len(departments_without_submission), "Критично"],
    ["Різні значення по одному заходу", len(value_conflicts_detail), "Критично"],
    ["Заявки з ризиками", len(requests_with_risks), "Інформаційно"],
    ["Довге очікування погодження", len(long_waiting), "Попередження"],
    ["Виконано, але факт 0 / ні", len(bad_completed), "Критично"],
    ["Виконано без файлів", len(completed_without_files), "Попередження"],
    ["Подання по неактивних заходах", len(submitted_inactive), "Попередження"],
], columns=["Перевірка", "Кількість", "Рівень"])

s1, s2 = st.columns([1, 1])

with s1:
    st.dataframe(issue_summary, use_container_width=True, hide_index=True)

with s2:
    fig = px.bar(
        issue_summary,
        x="Перевірка",
        y="Кількість",
        color="Рівень",
        text="Кількість",
        title="Проблеми за типами"
    )
    fig.update_layout(xaxis_tickangle=-35)
    st.plotly_chart(fig, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Детальні перевірки</div><div class="card-subtitle">Відкрийте потрібну вкладку, щоб переглянути конкретні записи.</div>', unsafe_allow_html=True)

tabs = st.tabs(list(issue_tables.keys()))

for tab, (name, table) in zip(tabs, issue_tables.items()):
    with tab:
        if table.empty:
            st.success("Проблем не виявлено.")
        else:
            st.dataframe(table, use_container_width=True, hide_index=True)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Проблеми за департаментами</div>', unsafe_allow_html=True)

dept_problem_rows = []

for dept in sorted(active["department"].dropna().astype(str).unique().tolist()):
    dept_active = active[active["department"].astype(str) == dept]
    dept_period = period_requests[period_requests["department"].astype(str) == dept]

    dept_problem_rows.append({
        "Департамент": dept,
        "Активних заходів": len(dept_active),
        "Подано заявок": len(dept_period),
        "Погоджено": len(dept_period[dept_period["approval_status"] == "Погоджено"]),
        "Очікує": len(dept_period[dept_period["approval_status"] == "Очікує погодження"]),
        "Повернуто": len(dept_period[dept_period["approval_status"] == "Повернуто на доопрацювання"]),
        "Без файлів": len(dept_period[dept_period["file_urls"].fillna("").astype(str).str.strip() == ""]),
        "Із ризиками": len(dept_period[dept_period["risks"].fillna("").astype(str).str.strip() != ""]),
        "Без email": len(dept_period[~dept_period["email"].apply(valid_email)])
    })

dept_quality = pd.DataFrame(dept_problem_rows)

if dept_quality.empty:
    st.info("Немає даних для департаментів.")
else:
    st.dataframe(dept_quality, use_container_width=True, hide_index=True)

    fig = px.bar(
        dept_quality,
        x="Департамент",
        y=["Активних заходів", "Подано заявок", "Погоджено"],
        barmode="group",
        title="Покриття поданням за департаментами"
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Експорт результатів перевірки</div>', unsafe_allow_html=True)

export_tables = {
    "Карта проблем": issue_summary,
    "Департаменти": dept_quality,
}

for key, value in issue_tables.items():
    export_tables[key] = value

quality_excel = create_quality_excel(export_tables)

st.download_button(
    "Завантажити Excel-звіт контролю якості",
    data=quality_excel,
    file_name=f"data_quality_check_{selected_year}_{selected_quarter}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
<div class="footer">
    Міністерство економіки, довкілля та сільського господарства України<br>
    Розроблено департаментом стратегічного планування та макроекономічного прогнозування<br>
    Версія DEMO 1.0 | Контроль якості моніторингових даних
</div>
""", unsafe_allow_html=True)
