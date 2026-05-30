import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client
import re

st.set_page_config(page_title="Моніторинг виконання", layout="wide")

FILE_PATH = "Під моніторинг СП.xlsx"
SHEET_NAME = "Страт_матриця"
BUCKET_NAME = "monitoring-files"

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)


def safe_filename(name):
    name = re.sub(r"[^A-Za-zА-Яа-яІіЇїЄєҐґ0-9._-]", "_", name)
    return name


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


def upload_files(files, code):
    urls = []
    names = []

    for file in files:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = safe_filename(file.name)
        path = f"{code}/{timestamp}_{filename}"

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


df = load_strat_matrix()
approved_df = load_approved_monitoring()

measures_df = df[df["object_type"] == "measure"].copy()

st.title("Внесення даних моніторингу виконання Стратегічного плану")

st.info(
    "Оберіть департамент і рік звітування. Система автоматично підтягне всі заходи, "
    "за якими обраний департамент є головним виконавцем."
)

departments = sorted(measures_df["department"].dropna().astype(str).unique())

col1, col2 = st.columns(2)

with col1:
    selected_department = st.selectbox("Департамент", departments)

with col2:
    selected_year = st.selectbox("Рік звітування", [2026, 2027, 2028])

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

st.subheader("Загальні дані подання")

g1, g2 = st.columns(2)

with g1:
    responsible_person = st.text_input("ПІБ відповідальної особи")

with g2:
    phone = st.text_input("Контактний номер телефону")

st.subheader("Заходи департаменту")

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

st.subheader("Підтвердні файли")

file_map = {}

if selected_rows.empty:
    st.info("Позначте хоча б один захід у таблиці, щоб додати файли.")
else:
    for _, row in selected_rows.iterrows():
        code = str(row["Код заходу"])
        files = st.file_uploader(
            f"Файли для заходу {code}",
            accept_multiple_files=True,
            key=f"files_{code}"
        )
        file_map[code] = files

submit = st.button("Подати інформацію на погодження")

if submit:
    errors = []

    if not responsible_person.strip():
        errors.append("Заповніть ПІБ відповідальної особи.")

    if not phone.strip():
        errors.append("Заповніть контактний номер телефону.")

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

        quarters_filled = []

        for quarter, col_name in quarter_columns.items():
            value = row[col_name]

            if pd.notna(value) and str(value).strip() != "":
                quarters_filled.append((quarter, str(value).strip()))

        if not quarters_filled:
            errors.append(f"Для заходу {code} потрібно заповнити хоча б одну квартальну колонку.")
            continue

        uploaded_names = ""
        uploaded_urls = ""

        try:
            uploaded_names, uploaded_urls = upload_files(file_map.get(code, []), code)
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
                "strat_code": code,
                "status": str(row["Статус виконання"]),
                "progress_text": str(row["Опис прогресу"]),
                "numeric_value": value,
                "risks": str(row["Ризики / проблеми / відхилення"]),
                "submitted_at": datetime.now().isoformat(),
                "approval_status": "Очікує погодження",
                "start_date": str(row["Початкова дата виконання"]) if pd.notna(row["Початкова дата виконання"]) else None,
                "end_date": str(row["Кінцева дата виконання"]) if pd.notna(row["Кінцева дата виконання"]) else None,
                "evidence_links": "",
                "file_names": uploaded_names,
                "file_urls": uploaded_urls
            })

    if errors:
        for error in errors:
            st.error(error)
        st.stop()

    try:
        supabase.table("monitoring_requests").insert(rows_to_insert).execute()

        st.success("Інформацію подано на погодження адміністратору.")

        st.subheader("Попередній перегляд поданих даних")

        st.dataframe(
            pd.DataFrame(rows_to_insert),
            use_container_width=True,
            hide_index=True
        )

    except Exception as e:
        st.error("Не вдалося зберегти дані в Supabase.")
        st.exception(e)
