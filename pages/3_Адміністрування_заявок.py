import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime

st.set_page_config(
    page_title="Адміністрування заявок",
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
    background: rgba(255,255,255,0.94);
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 24px 28px;
    margin-bottom: 18px;
    box-shadow: 0 8px 24px rgba(15,23,42,0.06);
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

.status-pill-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 14px;
}

.status-pill {
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 999px;
    padding: 8px 12px;
    font-size: 13px;
    color: #334155;
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

.flow-box {
    background: white;
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 16px 18px;
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

.badge-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 10px 0 16px 0;
}

.badge {
    background: #eef6ff;
    border: 1px solid #bfdbfe;
    color: #1d4ed8;
    border-radius: 999px;
    padding: 7px 11px;
    font-size: 13px;
    font-weight: 700;
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

.review-box {
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 16px 18px;
    margin: 12px 0;
}

.review-title {
    font-size: 16px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 8px;
}

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.88);
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

div.stButton > button {
    border-radius: 12px;
    padding: 12px 18px;
    font-weight: 800;
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

    return result


def load_requests():
    response = (
        supabase
        .table("monitoring_requests")
        .select("*")
        .order("id", desc=True)
        .execute()
    )

    if not response.data:
        return pd.DataFrame()

    return pd.DataFrame(response.data)


def load_logs(request_id):
    response = (
        supabase
        .table("monitoring_logs")
        .select("*")
        .eq("request_id", request_id)
        .order("changed_at", desc=True)
        .execute()
    )

    if not response.data:
        return pd.DataFrame()

    return pd.DataFrame(response.data)


def write_log(request_id, action, old_status, new_status, admin_comment):
    supabase.table("monitoring_logs").insert({
        "request_id": int(request_id),
        "action": action,
        "old_status": old_status,
        "new_status": new_status,
        "admin_comment": admin_comment,
        "changed_by": "Адміністратор"
    }).execute()


def quality_assessment(row):
    checks = []
    score = 0

    if has_value(row.get("numeric_value", "")):
        checks.append(("Фактичне значення", "Заповнено", True))
        score += 1
    else:
        checks.append(("Фактичне значення", "Не заповнено", False))

    if has_value(row.get("progress_text", "")):
        checks.append(("Опис прогресу", "Заповнено", True))
        score += 1
    else:
        checks.append(("Опис прогресу", "Не заповнено", False))

    if has_value(row.get("file_urls", "")):
        checks.append(("Підтвердні файли", "Додано", True))
        score += 1
    else:
        checks.append(("Підтвердні файли", "Не додано", False))

    if has_value(row.get("responsible_person", "")):
        checks.append(("Відповідальна особа", "Заповнено", True))
        score += 1
    else:
        checks.append(("Відповідальна особа", "Не заповнено", False))

    if has_value(row.get("phone", "")):
        checks.append(("Телефон", "Заповнено", True))
        score += 1
    else:
        checks.append(("Телефон", "Не заповнено", False))

    if has_value(row.get("email", "")):
        checks.append(("Email", "Заповнено", True))
        score += 1
    else:
        checks.append(("Email", "Не заповнено", False))

    if has_value(row.get("risks", "")):
        checks.append(("Ризики", "Є зазначені ризики", False))
    else:
        checks.append(("Ризики", "Не зазначено", True))

    if score >= 5 and not has_value(row.get("risks", "")):
        recommendation = "Можна погоджувати"
        badge = "badge-green"
    elif score >= 4:
        recommendation = "Потребує перевірки"
        badge = "badge-yellow"
    else:
        recommendation = "Краще повернути на доопрацювання"
        badge = "badge-red"

    return checks, recommendation, badge, score


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
    """
    <div class="header-box">
        <div class="header-title">Адміністрування заявок моніторингу</div>
        <div class="header-subtitle">
            Робочий кабінет адміністратора для перевірки поданих даних, перегляду підтвердних файлів,
            погодження заявок, повернення на доопрацювання та контролю історії змін.
        </div>
        <div class="status-pill-wrap">
            <div class="status-pill">● Режим: адміністрування</div>
            <div class="status-pill">● Дані: Supabase</div>
            <div class="status-pill">● Журнал змін: активний</div>
            <div class="status-pill">● Оновлено: """ + datetime.now().strftime("%d.%m.%Y %H:%M") + """</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="flow-box">
        <div class="flow-title">Маршрут рішення адміністратора</div>
        <div class="flow-steps">
            <div class="flow-step">1. Відфільтрувати заявки</div>
            <div class="flow-step">2. Переглянути захід</div>
            <div class="flow-step">3. Перевірити факт і файли</div>
            <div class="flow-step">4. Додати коментар</div>
            <div class="flow-step">5. Прийняти рішення</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

df = load_requests()
strat_df = load_strat_matrix()

if df.empty:
    st.warning("Поки що немає поданих заявок.")
    st.stop()

required_cols = [
    "id",
    "department",
    "year",
    "quarter",
    "approval_status",
    "status",
    "strat_code",
    "responsible_person",
    "phone",
    "email",
    "numeric_value",
    "progress_text",
    "risks",
    "file_names",
    "file_urls",
    "admin_comment",
    "start_date",
    "end_date",
    "submitted_at"
]

for col in required_cols:
    if col not in df.columns:
        df[col] = ""

st.markdown('<div class="card"><div class="card-title">Огляд заявок</div><div class="card-subtitle">Короткий стан черги адміністрування.</div>', unsafe_allow_html=True)

total_requests = len(df)
waiting_count = len(df[df["approval_status"] == "Очікує погодження"])
approved_count = len(df[df["approval_status"] == "Погоджено"])
returned_count = len(df[df["approval_status"] == "Повернуто на доопрацювання"])
with_files_count = len(df[df["file_urls"].fillna("").astype(str).str.strip() != ""])
with_risks_count = len(df[df["risks"].fillna("").astype(str).str.strip() != ""])

m1, m2, m3, m4, m5, m6 = st.columns(6)

m1.metric("Усього", total_requests)
m2.metric("Очікують", waiting_count)
m3.metric("Погоджено", approved_count)
m4.metric("Повернуто", returned_count)
m5.metric("Із файлами", with_files_count)
m6.metric("Із ризиками", with_risks_count)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Міні-візуалізація статусів</div>', unsafe_allow_html=True)

chart_df = (
    df["approval_status"]
    .fillna("Невідомо")
    .value_counts()
    .reset_index()
)

chart_df.columns = ["Статус", "Кількість"]

fig = px.pie(
    chart_df,
    names="Статус",
    values="Кількість",
    hole=0.5,
    title="Розподіл заявок за статусом погодження"
)

st.plotly_chart(fig, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Фільтри та пошук</div>', unsafe_allow_html=True)

f1, f2, f3, f4 = st.columns(4)

with f1:
    departments = sorted(df["department"].dropna().astype(str).unique().tolist())
    selected_department = st.selectbox("Департамент", ["Усі"] + departments)

with f2:
    years = sorted(df["year"].dropna().astype(str).unique().tolist())
    selected_year = st.selectbox("Рік", ["Усі"] + years)

with f3:
    quarters = sorted(df["quarter"].dropna().astype(str).unique().tolist())
    selected_quarter = st.selectbox("Квартал", ["Усі"] + quarters)

with f4:
    selected_approval_status = st.selectbox(
        "Статус погодження",
        [
            "Усі",
            "Очікує погодження",
            "Погоджено",
            "Повернуто на доопрацювання"
        ]
    )

q1, q2 = st.columns([1, 2])

with q1:
    quick_filter = st.selectbox(
        "Швидкий фільтр",
        [
            "Усі заявки",
            "Тільки очікують",
            "Повернуті",
            "Без файлів",
            "Із ризиками",
            "Останні подані"
        ]
    )

with q2:
    search_query = st.text_input(
        "Пошук за ID, кодом заходу, ПІБ або департаментом"
    )

filtered = df.copy()

if selected_department != "Усі":
    filtered = filtered[
        filtered["department"].astype(str) == str(selected_department)
    ]

if selected_year != "Усі":
    filtered = filtered[
        filtered["year"].astype(str) == str(selected_year)
    ]

if selected_quarter != "Усі":
    filtered = filtered[
        filtered["quarter"].astype(str) == str(selected_quarter)
    ]

if selected_approval_status != "Усі":
    filtered = filtered[
        filtered["approval_status"].astype(str) == str(selected_approval_status)
    ]

if quick_filter == "Тільки очікують":
    filtered = filtered[filtered["approval_status"] == "Очікує погодження"]

elif quick_filter == "Повернуті":
    filtered = filtered[filtered["approval_status"] == "Повернуто на доопрацювання"]

elif quick_filter == "Без файлів":
    filtered = filtered[filtered["file_urls"].fillna("").astype(str).str.strip() == ""]

elif quick_filter == "Із ризиками":
    filtered = filtered[filtered["risks"].fillna("").astype(str).str.strip() != ""]

elif quick_filter == "Останні подані":
    filtered = filtered.sort_values("submitted_at", ascending=False).head(10)

if search_query.strip():
    sq = search_query.strip().lower()

    filtered = filtered[
        filtered["id"].astype(str).str.lower().str.contains(sq, na=False)
        |
        filtered["strat_code"].astype(str).str.lower().str.contains(sq, na=False)
        |
        filtered["responsible_person"].astype(str).str.lower().str.contains(sq, na=False)
        |
        filtered["department"].astype(str).str.lower().str.contains(sq, na=False)
    ]

st.caption(f"Знайдено заявок: {len(filtered)}")

st.markdown('</div>', unsafe_allow_html=True)

if filtered.empty:
    st.info("За обраними фільтрами заявок не знайдено.")
    st.stop()

queue_df = filtered[
    filtered["approval_status"] == "Очікує погодження"
].copy()

if not queue_df.empty:
    st.markdown('<div class="card"><div class="card-title">Черга на розгляд</div><div class="card-subtitle">Заявки, які потребують рішення адміністратора.</div>', unsafe_allow_html=True)

    queue_show = queue_df.rename(columns={
        "id": "ID",
        "department": "Департамент",
        "year": "Рік",
        "quarter": "Квартал",
        "strat_code": "Код заходу",
        "responsible_person": "Відповідальна особа",
        "submitted_at": "Дата подання"
    })

    st.dataframe(
        queue_show[
            [
                "ID",
                "Департамент",
                "Код заходу",
                "Рік",
                "Квартал",
                "Відповідальна особа",
                "Дата подання"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Вибір заявки</div>', unsafe_allow_html=True)

selected_options = []

for _, row in filtered.iterrows():
    option = (
        f"ID {row['id']} | "
        f"{row['department']} | "
        f"{row['strat_code']} | "
        f"{row['year']} {row['quarter']} квартал | "
        f"{row['approval_status']} | "
        f"{clean(row['submitted_at'])}"
    )
    selected_options.append(option)

selected_request = st.selectbox(
    "Оберіть заявку для перегляду та погодження",
    selected_options
)

selected_id = int(selected_request.split("|")[0].replace("ID", "").strip())

selected_row = filtered[
    filtered["id"].astype(int) == selected_id
].iloc[0]

st.markdown('</div>', unsafe_allow_html=True)

approval_status = clean(selected_row["approval_status"])
selected_code = clean(selected_row["strat_code"])

checks, recommendation, rec_badge, quality_score = quality_assessment(selected_row)

st.markdown('<div class="card"><div class="card-title">Картка заявки</div>', unsafe_allow_html=True)

if approval_status == "Погоджено":
    status_badge = "badge-green"
elif approval_status == "Повернуто на доопрацювання":
    status_badge = "badge-red"
else:
    status_badge = "badge-yellow"

st.markdown(
    f"""
    <div class="badge-wrap">
        <div class="badge {status_badge}">Статус погодження: {approval_status}</div>
        <div class="badge">Заявка ID {clean(selected_row['id'])}</div>
        <div class="badge">Захід {selected_code}</div>
        <div class="badge {rec_badge}">Рекомендація: {recommendation}</div>
    </div>
    """,
    unsafe_allow_html=True
)

m1, m2, m3, m4, m5, m6 = st.columns(6)

m1.metric("Департамент", clean(selected_row["department"]))
m2.metric("Рік", clean(selected_row["year"]))
m3.metric("Квартал", clean(selected_row["quarter"]))
m4.metric("Статус виконання", clean(selected_row["status"]))
m5.metric("Факт", clean(selected_row["numeric_value"]))
m6.metric("Код", selected_code)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Автоматична оцінка якості заявки</div>', unsafe_allow_html=True)

qcols = st.columns(len(checks))

for idx, item in enumerate(checks):
    label, value, ok = item
    icon = "✅" if ok else "⚠️"
    qcols[idx].metric(label, f"{icon} {value}")

st.progress(min(quality_score / 6, 1.0), text=f"Заповненість ключових полів: {round(quality_score / 6 * 100, 1)}%")

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Інформація про захід зі стратегічного плану</div>', unsafe_allow_html=True)

measure_info = strat_df[
    strat_df["code"].astype(str).str.strip() == selected_code
].copy()

if measure_info.empty:
    st.warning("Захід не знайдено у стратегічній матриці.")
else:
    short_info = measure_info.iloc[0]

    st.markdown(
        f"""
        <div class="review-box">
            <div class="review-title">{clean(short_info.get("code", ""))} — {clean(short_info.get("name", ""))}</div>
            <div><b>Індикатор:</b> {clean(short_info.get("indicator", ""))}</div>
            <div><b>Одиниця виміру:</b> {clean(short_info.get("unit", ""))}</div>
            <div><b>Період виконання:</b> {clean(short_info.get("start_date_plan", ""))} — {clean(short_info.get("end_date_plan", ""))}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.expander("Детальна таблиця заходу"):
        measure_info = measure_info.rename(columns={
            "code": "Код",
            "name": "Захід",
            "indicator": "Індикатор",
            "unit": "Одиниця виміру",
            "base_2021": "Базове значення 2021",
            "fact_2024": "Звіт 2024",
            "expected_2025": "Очікуване 2025",
            "target_2026": "План 2026",
            "target_2027": "План 2027",
            "target_2028": "План 2028",
            "department": "Департамент",
            "start_date_plan": "Початкова дата зі СП",
            "end_date_plan": "Кінцева дата зі СП"
        })

        detail_cols = [
            "Код",
            "Захід",
            "Індикатор",
            "Одиниця виміру",
            "Базове значення 2021",
            "Звіт 2024",
            "Очікуване 2025",
            "План 2026",
            "План 2027",
            "План 2028",
            "Департамент",
            "Початкова дата зі СП",
            "Кінцева дата зі СП"
        ]

        available_detail_cols = [c for c in detail_cols if c in measure_info.columns]

        st.dataframe(
            measure_info[available_detail_cols],
            use_container_width=True,
            hide_index=True
        )

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Дані відповідальної особи</div>', unsafe_allow_html=True)

p1, p2, p3 = st.columns(3)

with p1:
    st.text_input(
        "ПІБ відповідальної особи",
        value=clean(selected_row["responsible_person"]),
        disabled=True
    )

with p2:
    st.text_input(
        "Контактний номер телефону",
        value=clean(selected_row["phone"]),
        disabled=True
    )

with p3:
    st.text_input(
        "Електронна пошта",
        value=clean(selected_row["email"]),
        disabled=True
    )

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Терміни виконання</div>', unsafe_allow_html=True)

d1, d2 = st.columns(2)

with d1:
    st.text_input(
        "Початкова дата виконання",
        value=clean(selected_row["start_date"]),
        disabled=True
    )

with d2:
    st.text_input(
        "Кінцева дата виконання",
        value=clean(selected_row["end_date"]),
        disabled=True
    )

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Опис прогресу та ризики</div>', unsafe_allow_html=True)

t1, t2 = st.columns(2)

with t1:
    st.text_area(
        "Опис прогресу",
        value=clean(selected_row["progress_text"]),
        disabled=True,
        height=150
    )

with t2:
    st.text_area(
        "Ризики / проблеми / відхилення",
        value=clean(selected_row["risks"]),
        disabled=True,
        height=150
    )

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Підтвердні файли</div>', unsafe_allow_html=True)

file_names = clean(selected_row["file_names"])
file_urls = clean(selected_row["file_urls"])

if not file_urls:
    st.warning("Файлів до заявки не додано.")
else:
    urls = [u.strip() for u in file_urls.split(",") if u.strip()]
    names = [n.strip() for n in file_names.split(",") if n.strip()]

    st.caption(f"Додано файлів: {len(urls)}")

    for i, url in enumerate(urls):
        label = names[i] if i < len(names) else f"Файл {i + 1}"
        st.markdown(f"[{label}]({url})")

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Рішення адміністратора</div><div class="card-subtitle">Додайте коментар і прийміть рішення щодо обраної заявки.</div>', unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="badge-wrap">
        <div class="badge {rec_badge}">Системна рекомендація: {recommendation}</div>
        <div class="badge">Заповненість: {round(quality_score / 6 * 100, 1)}%</div>
    </div>
    """,
    unsafe_allow_html=True
)

admin_comment = st.text_area(
    "Коментар адміністратора",
    value=clean(selected_row["admin_comment"]),
    height=120
)

c1, c2, c3 = st.columns(3)

with c1:
    approve = st.button("Погодити", use_container_width=True)

with c2:
    return_back = st.button("Повернути на доопрацювання", use_container_width=True)

with c3:
    keep_waiting = st.button("Залишити в очікуванні", use_container_width=True)

if approve:
    supabase.table("monitoring_requests").update({
        "approval_status": "Погоджено",
        "admin_comment": admin_comment
    }).eq("id", selected_id).execute()

    write_log(
        selected_id,
        "Погодження заявки",
        approval_status,
        "Погоджено",
        admin_comment
    )

    st.success("Заявку погоджено.")
    st.rerun()

if return_back:
    supabase.table("monitoring_requests").update({
        "approval_status": "Повернуто на доопрацювання",
        "admin_comment": admin_comment
    }).eq("id", selected_id).execute()

    write_log(
        selected_id,
        "Повернення заявки на доопрацювання",
        approval_status,
        "Повернуто на доопрацювання",
        admin_comment
    )

    st.warning("Заявку повернуто на доопрацювання.")
    st.rerun()

if keep_waiting:
    supabase.table("monitoring_requests").update({
        "approval_status": "Очікує погодження",
        "admin_comment": admin_comment
    }).eq("id", selected_id).execute()

    write_log(
        selected_id,
        "Заявку залишено в очікуванні",
        approval_status,
        "Очікує погодження",
        admin_comment
    )

    st.info("Заявку залишено в очікуванні.")
    st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Остання дія та історія змін</div>', unsafe_allow_html=True)

logs_df = load_logs(selected_id)

if logs_df.empty:
    st.info("Історії змін для цієї заявки поки що немає.")
else:
    latest_log = logs_df.iloc[0]

    st.markdown(
        f"""
        <div class="review-box">
            <div class="review-title">Остання дія: {clean(latest_log.get("action", ""))}</div>
            <div><b>Статус:</b> {clean(latest_log.get("old_status", ""))} → {clean(latest_log.get("new_status", ""))}</div>
            <div><b>Коментар:</b> {clean(latest_log.get("admin_comment", ""))}</div>
            <div><b>Дата:</b> {clean(latest_log.get("changed_at", ""))}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.expander("Повна історія змін заявки"):
        show_logs = logs_df.rename(columns={
            "changed_at": "Дата зміни",
            "action": "Дія",
            "old_status": "Попередній статус",
            "new_status": "Новий статус",
            "admin_comment": "Коментар адміністратора",
            "changed_by": "Ким змінено"
        })

        show_cols = [
            "Дата зміни",
            "Дія",
            "Попередній статус",
            "Новий статус",
            "Коментар адміністратора",
            "Ким змінено"
        ]

        available_log_cols = [col for col in show_cols if col in show_logs.columns]

        st.dataframe(
            show_logs[available_log_cols],
            use_container_width=True,
            hide_index=True
        )

st.markdown('</div>', unsafe_allow_html=True)

with st.expander("Технічна таблиця заявок"):
    st.dataframe(
        filtered,
        use_container_width=True,
        hide_index=True
    )

st.markdown(
    """
    <div class="footer">
        Розроблено департаментом стратегічного планування та макроекономічного прогнозування<br>
        Версія DEMO 0.9 | Кабінет адміністрування заявок моніторингу
    </div>
    """,
    unsafe_allow_html=True
)
