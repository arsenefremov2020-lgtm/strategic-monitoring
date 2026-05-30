import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client

st.set_page_config(
    page_title="Моніторинг виконання",
    layout="wide"
)

FILE_PATH = "Під моніторинг СП.xlsx"
SHEET_NAME = "Страт_матриця"

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
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


df = load_strat_matrix()
approved_df = load_approved_monitoring()

measures_df = df[df["object_type"] == "measure"].copy()

st.title("Внесення даних моніторингу виконання Стратегічного плану")

st.info(
    "Оберіть департамент і рік звітування. Система автоматично підтягне всі заходи, "
    "за якими цей департамент є головним виконавцем."
)

departments = sorted(
    measures_df["department"]
    .dropna()
    .astype(str)
    .unique()
)

col1, col2, col3 = st.columns(3)

with col1:
    selected_department = st.selectbox(
        "Департамент",
        departments
    )

with col2:
    selected_year = st.selectbox(
        "Рік звітування",
        [2026, 2027, 2028]
    )

with col3:
    selected_quarter = st.selectbox(
        "Квартал звітування",
        ["I", "II", "III", "IV"]
    )

department_measures = measures_df[
    measures_df["department"].astype(str) == str(selected_department)
].copy()

if department_measures.empty:
    st.warning("Для цього департаменту заходів не знайдено.")
    st.stop()

target_col = f"target_{selected_year}"

quarter_values = {}

if not approved_df.empty:
    year_data = approved_df[
        approved_df["year"] == selected_year
    ]

    for _, row in year_data.iterrows():
        code = str(row["strat_code"]).strip()
        quarter = str(row["quarter"]).strip()
        value = row.get("numeric_value", "")

        quarter_values.setdefault(code, {})
        quarter_values[code][quarter] = value

department_measures["2026 I квартал"] = department_measures["code"].apply(
    lambda x: quarter_values.get(str(x).strip(), {}).get("I", "")
)
department_measures["2026 II квартал"] = department_measures["code"].apply(
    lambda x: quarter_values.get(str(x).strip(), {}).get("II", "")
)
department_measures["2026 III квартал"] = department_measures["code"].apply(
    lambda x: quarter_values.get(str(x).strip(), {}).get("III", "")
)
department_measures["2026 IV квартал"] = department_measures["code"].apply(
    lambda x: quarter_values.get(str(x).strip(), {}).get("IV", "")
)

form_df = pd.DataFrame({
    "Подати": False,
    "Код заходу": department_measures["code"],
    "Назва заходу": department_measures["name"],
    "Індикатор": department_measures["indicator"],
    "Одиниця виміру": department_measures["unit"],
    f"Планове значення {selected_year}": department_measures[target_col],
    f"{selected_year} I квартал": department_measures["2026 I квартал"],
    f"{selected_year} II квартал": department_measures["2026 II квартал"],
    f"{selected_year} III квартал": department_measures["2026 III квартал"],
    f"{selected_year} IV квартал": department_measures["2026 IV квартал"],
    "Початкова дата виконання": "",
    "Кінцева дата виконання": "",
    "Статус виконання": "Виконується",
    "Фактичне значення за квартал": "",
    "Опис прогресу": "",
    "Посилання на підтвердні матеріали": "",
    "Ризики / проблеми / відхилення": ""
})

st.subheader("Загальні дані подання")

g1, g2 = st.columns(2)

with g1:
    responsible_person = st.text_input("ПІБ відповідальної особи")

with g2:
    phone = st.text_input("Контактний номер телефону")

st.subheader("Заходи департаменту")

edited_df = st.data_editor(
    form_df,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    column_config={
        "Подати": st.column_config.CheckboxColumn(
            "Подати",
            help="Позначте заходи, за якими подається моніторингова інформація"
        ),
        "Код заходу": st.column_config.TextColumn(
            "Код заходу",
            disabled=True,
            width="small"
        ),
        "Назва заходу": st.column_config.TextColumn(
            "Назва заходу",
            disabled=True,
            width="large"
        ),
        "Індикатор": st.column_config.TextColumn(
            "Індикатор",
            disabled=True,
            width="large"
        ),
        "Одиниця виміру": st.column_config.TextColumn(
            "Одиниця виміру",
            disabled=True,
            width="medium"
        ),
        f"Планове значення {selected_year}": st.column_config.TextColumn(
            f"Планове значення {selected_year}",
            disabled=True,
            width="medium"
        ),
        f"{selected_year} I квартал": st.column_config.TextColumn(
            f"{selected_year} I квартал",
            disabled=True,
            width="medium"
        ),
        f"{selected_year} II квартал": st.column_config.TextColumn(
            f"{selected_year} II квартал",
            disabled=True,
            width="medium"
        ),
        f"{selected_year} III квартал": st.column_config.TextColumn(
            f"{selected_year} III квартал",
            disabled=True,
            width="medium"
        ),
        f"{selected_year} IV квартал": st.column_config.TextColumn(
            f"{selected_year} IV квартал",
            disabled=True,
            width="medium"
        ),
        "Початкова дата виконання": st.column_config.DateColumn(
            "Початкова дата виконання"
        ),
        "Кінцева дата виконання": st.column_config.DateColumn(
            "Кінцева дата виконання"
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
            required=True
        ),
        "Фактичне значення за квартал": st.column_config.TextColumn(
            "Фактичне значення за квартал"
        ),
        "Опис прогресу": st.column_config.TextColumn(
            "Опис прогресу",
            width="large"
        ),
        "Посилання на підтвердні матеріали": st.column_config.TextColumn(
            "Посилання на підтвердні матеріали",
            width="large"
        ),
        "Ризики / проблеми / відхилення": st.column_config.TextColumn(
            "Ризики / проблеми / відхилення",
            width="large"
        )
    }
)

selected_rows = edited_df[edited_df["Подати"] == True].copy()

st.subheader("Підтвердні файли")

st.caption(
    "На цьому етапі файли не зберігаються в Supabase Storage, але їхні назви записуються в заявку. "
    "Для повноцінного зберігання файлів пізніше додамо окремий bucket у Supabase."
)

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

        file_map[code] = ", ".join([file.name for file in files]) if files else ""

submit = st.button("Подати інформацію на погодження")

if submit:
    errors = []

    if not responsible_person.strip():
        errors.append("Заповніть ПІБ відповідальної особи.")

    if not phone.strip():
        errors.append("Заповніть контактний номер телефону.")

    if selected_rows.empty:
        errors.append("Позначте хоча б один захід для подання.")

    for _, row in selected_rows.iterrows():
        if not str(row["Статус виконання"]).strip():
            errors.append(f"Не заповнено статус для заходу {row['Код заходу']}.")

    if errors:
        for error in errors:
            st.error(error)
        st.stop()

    rows_to_insert = []

    for _, row in selected_rows.iterrows():
        code = str(row["Код заходу"])

        start_date = row["Початкова дата виконання"]
        end_date = row["Кінцева дата виконання"]

        rows_to_insert.append({
            "year": int(selected_year),
            "quarter": selected_quarter,
            "department": str(selected_department),
            "responsible_person": responsible_person,
            "phone": phone,
            "strat_code": code,
            "status": str(row["Статус виконання"]),
            "progress_text": str(row["Опис прогресу"]),
            "numeric_value": str(row["Фактичне значення за квартал"]),
            "risks": str(row["Ризики / проблеми / відхилення"]),
            "submitted_at": datetime.now().isoformat(),
            "approval_status": "Очікує погодження",
            "start_date": str(start_date) if pd.notna(start_date) else None,
            "end_date": str(end_date) if pd.notna(end_date) else None,
            "evidence_links": str(row["Посилання на підтвердні матеріали"]),
            "file_names": file_map.get(code, "")
        })

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
