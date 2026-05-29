import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Моніторинг виконання",
    layout="wide"
)

st.title("Внесення даних моніторингу виконання Стратегічного плану")

st.info(
    "На цій сторінці департаменти подають інформацію про стан виконання заходів. "
    "Дані не змінюють стратегічний план напряму, а формують запит на погодження адміністратором."
)

st.subheader("Форма внесення інформації")

with st.form("monitoring_form"):

    col1, col2 = st.columns(2)

    with col1:
        year = st.selectbox("Рік", [2026, 2027, 2028])
        quarter = st.selectbox("Квартал", ["I", "II", "III", "IV"])
        department = st.text_input("Департамент")
        responsible_person = st.text_input("ПІБ відповідальної особи")

    with col2:
        phone = st.text_input("Контактний номер телефону")
        strat_code = st.text_input("Код заходу зі стратегічного плану")
        status = st.selectbox(
            "Стан виконання",
            [
                "Не розпочато",
                "Виконується",
                "Виконано",
                "Виконано частково",
                "Прострочено",
                "Потребує уваги"
            ]
        )

    progress_text = st.text_area("Короткий опис прогресу")
    numeric_value = st.text_input("Фактичне числове значення показника, якщо є")
    risks = st.text_area("Ризики / проблеми / пояснення відхилення")

    submitted = st.form_submit_button("Подати інформацію на погодження")

if submitted:

    st.success("Інформацію подано на погодження адміністратору.")

    st.write("Попередній перегляд поданих даних:")

    preview = pd.DataFrame([{
        "strat_code": strat_code,
        "year": year,
        "quarter": quarter,
        "department": department,
        "responsible_person": responsible_person,
        "phone": phone,
        "status": status,
        "progress_text": progress_text,
        "numeric_value": numeric_value,
        "risks": risks,
        "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "approval_status": "Очікує погодження"
    }])

    st.dataframe(preview, use_container_width=True)
