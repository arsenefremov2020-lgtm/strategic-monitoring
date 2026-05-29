import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Моніторинг виконання",
    layout="wide"
)

st.title("Внесення даних моніторингу виконання Стратегічного плану")

st.info(
    "Одна форма може містити кілька заходів одного департаменту за один квартал."
)

with st.form("monitoring_form"):

    st.subheader("Загальні дані подання")

    col1, col2 = st.columns(2)

    with col1:
        year = st.selectbox("Рік", [2026, 2027, 2028])
        quarter = st.selectbox("Квартал", ["I", "II", "III", "IV"])
        department = st.text_input("Департамент")

    with col2:
        responsible_person = st.text_input("ПІБ відповідальної особи")
        phone = st.text_input("Контактний номер телефону")
        measures_count = st.number_input(
            "Кількість заходів у цьому поданні",
            min_value=1,
            max_value=20,
            value=1,
            step=1
        )

    st.divider()
    st.subheader("Інформація по заходах")

    measures_data = []

    for i in range(int(measures_count)):

        st.markdown(f"### Захід {i + 1}")

        c1, c2 = st.columns(2)

        with c1:
            strat_code = st.text_input(
                "Код заходу зі стратегічного плану",
                key=f"strat_code_{i}"
            )

            status = st.selectbox(
                "Стан виконання",
                [
                    "Не розпочато",
                    "Виконується",
                    "Виконано",
                    "Виконано частково",
                    "Прострочено",
                    "Потребує уваги"
                ],
                key=f"status_{i}"
            )

        with c2:
            numeric_value = st.text_input(
                "Фактичне числове значення показника, якщо є",
                key=f"numeric_value_{i}"
            )

        progress_text = st.text_area(
            "Короткий опис прогресу",
            key=f"progress_text_{i}"
        )

        risks = st.text_area(
            "Ризики / проблеми / пояснення відхилення",
            key=f"risks_{i}"
        )

        measures_data.append({
            "strat_code": strat_code,
            "status": status,
            "numeric_value": numeric_value,
            "progress_text": progress_text,
            "risks": risks
        })

        st.divider()

    submitted = st.form_submit_button(
        "Подати інформацію на погодження"
    )

if submitted:

    rows = []

    for item in measures_data:

        rows.append({
            "year": year,
            "quarter": quarter,
            "department": department,
            "responsible_person": responsible_person,
            "phone": phone,
            "strat_code": item["strat_code"],
            "status": item["status"],
            "progress_text": item["progress_text"],
            "numeric_value": item["numeric_value"],
            "risks": item["risks"],
            "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "approval_status": "Очікує погодження"
        })

    preview = pd.DataFrame(rows)

    st.success("Інформацію подано на погодження адміністратору.")

    st.subheader("Попередній перегляд поданих даних")

    st.dataframe(
        preview,
        use_container_width=True,
        hide_index=True
    )
