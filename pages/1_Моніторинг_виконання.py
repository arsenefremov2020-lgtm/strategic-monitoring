import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client
import re

st.set_page_config(
    page_title="Моніторинг виконання",
    layout="wide"
)

FILE_PATH = "Під моніторинг СП.xlsx"
SHEET_NAME = "Страт_матриця"
BUCKET_NAME = "monitoring-files"

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

.warn-badge {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    color: #9a3412;
}

.success-box {
    background: linear-gradient(90deg, #15803d, #16a34a);
    color: white;
    border-radius: 16px;
    padding: 20px 24px;
    margin: 18px 0;
    box-shadow: 0 10px 24px rgba(22,163,74,0.22);
}

.success-title {
    font-size: 22px;
    font-weight: 900;
    margin-bottom: 6px;
}

.submit-zone {
    background: white;
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 18px 22px;
    margin: 18px 0;
    box-shadow: 0 6px 18px rgba(15,23,42,0.045);
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


def safe_filename(name):
    name = str(name)
    name = name.replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_")


def valid_email(email):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()) is not None


def quarter_to_num(q):
    mapping = {
        "I": 1,
        "II": 2,
        "III": 3,
        "IV": 4
    }
    return mapping.get(str(q), None)


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

    year_match = re.search(r"20\d{2}", text)

    if year_match:
        year = int(year_match.group())

    if year and q:
        return year * 10 + q

    return None


def upload_files(files, code):
    urls = []
    names = []

    safe_code = safe_filename(str(code)).replace(".", "_")

    for file in files:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = safe_filename(file.name)

        if not filename:
            filename = f"file_{timestamp}"

        path = f"{safe_code}/{timestamp}_{filename}"

        supabase.storage.from_(BUCKET_NAME).upload(
            path,
            file.getvalue(),
            file_options={
                "content-type": file.type,
                "upsert": "true"
            }
        )

        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(path)

        urls.append(public_url)
        names.append(file.name)

    return ", ".join(names), ", ".join(urls)


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


def load_approved_monitoring():
    response = (
        supabase
        .table("monitoring_requests")
        .select("*")
        .eq("approval_status", "Погоджено")
        .execute()
    )

    if not response.data:
        return pd.DataFrame()

    return pd.DataFrame(response.data)


def load_all_monitoring():
    response = (
        supabase
        .table("monitoring_requests")
        .select("*")
        .execute()
    )

    if not response.data:
        return pd.DataFrame()

    return pd.DataFrame(response.data)


df = load_strat_matrix()
approved_df = load_approved_monitoring()
all_monitoring_df = load_all_monitoring()

measures_df = df[df["object_type"] == "measure"].copy()

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
        <div class="header-title">Внесення даних моніторингу виконання Стратегічного плану</div>
        <div class="header-subtitle">
            Кабінет департаменту для квартального подання інформації про виконання заходів,
            додавання підтвердних файлів і передачі даних адміністратору на погодження.
        </div>
        <div class="status-pill-wrap">
            <div class="status-pill">● Режим: подання даних</div>
            <div class="status-pill">● Supabase: активний</div>
            <div class="status-pill">● Файли: Storage підключено</div>
            <div class="status-pill">● Статус: DEMO</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="flow-box">
        <div class="flow-title">Маршрут подання</div>
        <div class="flow-steps">
            <div class="flow-step">1. Обрати департамент</div>
            <div class="flow-step">2. Позначити заходи</div>
            <div class="flow-step">3. Заповнити квартали</div>
            <div class="flow-step">4. Додати файли</div>
            <div class="flow-step">5. Подати на погодження</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

departments = sorted(measures_df["department"].dropna().astype(str).unique())

st.markdown('<div class="card"><div class="card-title">Параметри подання</div><div class="card-subtitle">Оберіть департамент і рік звітування. Система підтягне тільки ті заходи, за якими департамент є головним виконавцем.</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    selected_department = st.selectbox("Департамент", departments)

with col2:
    selected_year = st.selectbox("Рік звітування", [2026, 2027, 2028])

st.markdown('</div>', unsafe_allow_html=True)

department_measures = measures_df[
    measures_df["department"].astype(str) == str(selected_department)
].copy()

if department_measures.empty:
    st.warning("Для цього департаменту заходів не знайдено.")
    st.stop()

target_col = f"target_{selected_year}"

quarter_values = {}

if not approved_df.empty:
    year_data = approved_df[approved_df["year"] == selected_year]

    for _, row in year_data.iterrows():
        code = str(row["strat_code"]).strip()
        quarter = str(row["quarter"]).strip()
        value = row.get("numeric_value", "")

        quarter_values.setdefault(code, {})
        quarter_values[quarter] = value

for q in ["I", "II", "III", "IV"]:
    department_measures[f"{selected_year} {q} квартал"] = department_measures["code"].apply(
        lambda x: quarter_values.get(str(x).strip(), {}).get(q, "")
    )

form_df = pd.DataFrame({
    "Подати": False,
    "Код заходу": department_measures["code"],
    "Назва заходу": department_measures["name"],
    "Індикатор": department_measures["indicator"],
    "Одиниця виміру": department_measures["unit"],
    f"Планове значення {selected_year}": department_measures[target_col],
    f"{selected_year} I квартал": department_measures[f"{selected_year} I квартал"],
    f"{selected_year} II квартал": department_measures[f"{selected_year} II квартал"],
    f"{selected_year} III квартал": department_measures[f"{selected_year} III квартал"],
    f"{selected_year} IV квартал": department_measures[f"{selected_year} IV квартал"],
    "Початкова дата виконання": department_measures["start_date_plan"],
    "Кінцева дата виконання": department_measures["end_date_plan"],
    "Статус виконання": "Виконується",
    "Опис прогресу": "",
    "Ризики / проблеми / відхилення": ""
})

dept_all = pd.DataFrame()

if not all_monitoring_df.empty:
    dept_all = all_monitoring_df[
        (all_monitoring_df["department"].astype(str) == str(selected_department)) &
        (all_monitoring_df["year"].astype(str) == str(selected_year))
    ].copy()

dept_approved = len(dept_all[dept_all["approval_status"] == "Погоджено"]) if not dept_all.empty else 0
dept_waiting = len(dept_all[dept_all["approval_status"] == "Очікує погодження"]) if not dept_all.empty else 0
dept_risks = len(dept_all[dept_all["risks"].fillna("").astype(str).str.strip() != ""]) if not dept_all.empty and "risks" in dept_all.columns else 0
dept_without = max(len(department_measures) - dept_all["strat_code"].nunique(), 0) if not dept_all.empty else len(department_measures)

st.markdown('<div class="card"><div class="card-title">Поточний стан обраного департаменту</div>', unsafe_allow_html=True)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Заходів департаменту", len(department_measures))
k2.metric("Погоджено заявок", dept_approved)
k3.metric("Очікує погодження", dept_waiting)
k4.metric("Без подання", dept_without)
k5.metric("Із ризиками", dept_risks)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Загальні дані подання</div><div class="card-subtitle">Ці дані будуть застосовані до всіх заходів, які ви позначите у таблиці.</div>', unsafe_allow_html=True)

g1, g2, g3 = st.columns(3)

with g1:
    responsible_person = st.text_input("ПІБ відповідальної особи *")

with g2:
    phone = st.text_input("Контактний номер телефону *")

with g3:
    email = st.text_input("Електронна пошта відповідальної особи *")

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Заходи департаменту</div><div class="card-subtitle">Позначте заходи для подання. Редагуються квартальні значення, статус виконання, опис прогресу та ризики.</div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="badge-wrap">
        <div class="badge">Редагування квартальних значень активне</div>
        <div class="badge">Погоджені дані підтягнуто автоматично</div>
        <div class="badge">Файли додаються після вибору заходів</div>
        <div class="badge warn-badge">Перед поданням система виконає перевірку якості даних</div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    **Як працювати з таблицею:**

    1. Поставте галочку у колонці **«Подати»** біля заходів, за якими подаєте інформацію.
    2. У квартальних колонках внесіть фактичні значення виконання.
    3. Якщо дані вже були погоджені раніше, вони підтягнуться автоматично.
    4. Терміни виконання підтягуються зі стратегічної матриці.
    5. Заповніть статус, опис прогресу та ризики/проблеми/відхилення.
    6. Нижче завантажте підтвердні файли для обраних заходів.
    7. Натисніть **«Подати інформацію на погодження»**.
    """
)

edited_df = st.data_editor(
    form_df,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    height=580,
    row_height=95,
    column_config={
        "Подати": st.column_config.CheckboxColumn("Подати", width="small"),
        "Код заходу": st.column_config.TextColumn("Код заходу", disabled=True, width="small"),
        "Назва заходу": st.column_config.TextColumn("Назва заходу", disabled=True, width="large"),
        "Індикатор": st.column_config.TextColumn("Індикатор", disabled=True, width="large"),
        "Одиниця виміру": st.column_config.TextColumn("Одиниця виміру", disabled=True, width="medium"),
        f"Планове значення {selected_year}": st.column_config.TextColumn(
            f"Планове значення {selected_year}",
            disabled=True,
            width="medium"
        ),
        f"{selected_year} I квартал": st.column_config.TextColumn(f"{selected_year} I квартал", width="medium"),
        f"{selected_year} II квартал": st.column_config.TextColumn(f"{selected_year} II квартал", width="medium"),
        f"{selected_year} III квартал": st.column_config.TextColumn(f"{selected_year} III квартал", width="medium"),
        f"{selected_year} IV квартал": st.column_config.TextColumn(f"{selected_year} IV квартал", width="medium"),
        "Початкова дата виконання": st.column_config.TextColumn(
            "Початкова дата виконання",
            disabled=True,
            width="medium"
        ),
        "Кінцева дата виконання": st.column_config.TextColumn(
            "Кінцева дата виконання",
            disabled=True,
            width="medium"
        ),
        "Статус виконання": st.column_config.SelectboxColumn(
            "Статус виконання",
            options=[
                "Не розпочато",
                "Виконується",
                "Виконано",
                "Виконано частково",
                "Прострочено",
                "Потребує уваги"
            ],
            required=True,
            width="medium"
        ),
        "Опис прогресу": st.column_config.TextColumn("Опис прогресу", width="large"),
        "Ризики / проблеми / відхилення": st.column_config.TextColumn(
            "Ризики / проблеми / відхилення",
            width="large"
        )
    }
)

selected_rows = edited_df[edited_df["Подати"] == True].copy()

selected_count = len(selected_rows)
filled_count = 0

quarter_columns_tmp = [
    f"{selected_year} I квартал",
    f"{selected_year} II квартал",
    f"{selected_year} III квартал",
    f"{selected_year} IV квартал"
]

if selected_count > 0:
    for _, row in selected_rows.iterrows():
        has_value = any(
            pd.notna(row[col]) and str(row[col]).strip() != ""
            for col in quarter_columns_tmp
        )

        if has_value:
            filled_count += 1

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Прогрес заповнення</div>', unsafe_allow_html=True)

p1, p2, p3 = st.columns(3)
p1.metric("Позначено заходів", selected_count)
p2.metric("З квартальними значеннями", filled_count)
p3.metric("Очікують файлів", selected_count)

if selected_count > 0:
    st.progress(min(filled_count / selected_count, 1.0))
else:
    st.progress(0)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Підтвердні файли</div><div class="card-subtitle">Додайте наказ, звіт, скан, таблицю або інший підтвердний документ для обраних заходів.</div>', unsafe_allow_html=True)

file_map = {}

if selected_rows.empty:
    st.info("Позначте хоча б один захід у таблиці, щоб додати файли.")
else:
    for _, row in selected_rows.iterrows():
        code = str(row["Код заходу"])

        with st.expander(f"Файли для заходу {code}", expanded=True):
            files = st.file_uploader(
                "Завантажте підтвердні документи",
                accept_multiple_files=True,
                key=f"files_{code}"
            )
            file_map[code] = files

st.markdown('</div>', unsafe_allow_html=True)

files_count = sum(1 for files in file_map.values() if files)

st.markdown('<div class="submit-zone">', unsafe_allow_html=True)

st.markdown(
    """
    **Перед поданням система перевірить:**
    - ПІБ відповідальної особи;
    - контактний номер телефону;
    - електронну пошту;
    - наявність фактичних квартальних значень;
    - статус виконання;
    - строки виконання;
    - наявність підтвердних файлів.
    """
)

s1, s2, s3 = st.columns(3)
s1.metric("Позначено заходів", selected_count)
s2.metric("Мають квартальні значення", filled_count)
s3.metric("Мають файли", files_count)

submit = st.button("Подати інформацію на погодження", use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)

if submit:
    errors = []
    warnings = []

    if not responsible_person.strip():
        errors.append("Заповніть ПІБ відповідальної особи.")

    if not phone.strip():
        errors.append("Заповніть контактний номер телефону.")

    if not email.strip():
        errors.append("Заповніть електронну пошту відповідальної особи.")
    elif not valid_email(email):
        errors.append("Електронна пошта має некоректний формат.")

    if selected_rows.empty:
        errors.append("Позначте хоча б один захід для подання.")

    rows_to_insert = []

    quarter_columns = {
        "I": f"{selected_year} I квартал",
        "II": f"{selected_year} II квартал",
        "III": f"{selected_year} III квартал",
        "IV": f"{selected_year} IV квартал"
    }

    for _, row in selected_rows.iterrows():
        code = str(row["Код заходу"])
        status = str(row["Статус виконання"]).strip()
        risks = str(row["Ризики / проблеми / відхилення"]).strip()
        progress = str(row["Опис прогресу"]).strip()
        files = file_map.get(code, [])

        start_period_num = parse_period(row["Початкова дата виконання"])
        end_period_num = parse_period(row["Кінцева дата виконання"])

        quarters_filled = []

        for quarter, col_name in quarter_columns.items():
            value = row[col_name]

            if pd.notna(value) and str(value).strip() != "":
                quarters_filled.append((quarter, str(value).strip()))

        if not quarters_filled:
            errors.append(f"Для заходу {code} потрібно заповнити хоча б одну квартальну колонку.")
            continue

        if status == "Виконано" and not quarters_filled:
            errors.append(f"Для заходу {code} статус «Виконано» неможливий без фактичного значення.")

        if not progress:
            warnings.append(f"Для заходу {code} не заповнено опис прогресу.")

        if status == "Виконано" and risks:
            warnings.append(
                f"Для заходу {code} статус «Виконано», але заповнено ризики/проблеми. Перевірте коректність."
            )

        if not files:
            warnings.append(f"Для заходу {code} не додано підтвердні файли.")

        for quarter, value in quarters_filled:
            current_period_num = selected_year * 10 + quarter_to_num(quarter)

            if start_period_num is not None and current_period_num < start_period_num:
                warnings.append(
                    f"Для заходу {code} подається інформація за {quarter} квартал {selected_year}, "
                    f"але період виконання ще не настав."
                )

            if end_period_num is not None and current_period_num > end_period_num:
                warnings.append(
                    f"Для заходу {code} подається інформація за {quarter} квартал {selected_year}, "
                    f"але період виконання вже завершився."
                )

        uploaded_names = ""
        uploaded_urls = ""

        try:
            uploaded_names, uploaded_urls = upload_files(files, code)
        except Exception as e:
            errors.append(f"Не вдалося завантажити файл для заходу {code}: {e}")
            continue

        for quarter, value in quarters_filled:
            rows_to_insert.append({
                "year": int(selected_year),
                "quarter": quarter,
                "department": str(selected_department),
                "responsible_person": responsible_person,
                "phone": phone,
                "email": email,
                "strat_code": code,
                "status": status,
                "progress_text": progress,
                "numeric_value": value,
                "risks": risks,
                "submitted_at": datetime.now().isoformat(),
                "approval_status": "Очікує погодження",
                "start_date": str(row["Початкова дата виконання"]) if pd.notna(row["Початкова дата виконання"]) else None,
                "end_date": str(row["Кінцева дата виконання"]) if pd.notna(row["Кінцева дата виконання"]) else None,
                "evidence_links": "",
                "file_names": uploaded_names,
                "file_urls": uploaded_urls
            })

    if errors:
        st.error("Подання не виконано. Виправте помилки:")
        for error in errors:
            st.error(error)
        st.stop()

    if warnings:
        st.warning("Система виявила попередження. Дані все одно можна подати:")
        for warning in warnings:
            st.warning(warning)

    try:
        supabase.table("monitoring_requests").insert(rows_to_insert).execute()

        st.markdown(
            """
            <div class="success-box">
                <div class="success-title">Подання прийнято</div>
                <div>Статус: очікує погодження адміністратора. Дані передано до системи моніторингу.</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.subheader("Попередній перегляд поданих даних")

        st.dataframe(
            pd.DataFrame(rows_to_insert),
            use_container_width=True,
            hide_index=True
        )

    except Exception as e:
        st.error("Не вдалося зберегти дані в Supabase.")
        st.exception(e)

st.markdown(
    """
    <div class="footer">
        Розроблено департаментом стратегічного планування та макроекономічного прогнозування<br>
        Версія DEMO 0.9 | Внутрішня система моніторингу стратегічного плану
    </div>
    """,
    unsafe_allow_html=True
)
