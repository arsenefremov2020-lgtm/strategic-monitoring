import streamlit as st
import pandas as pd
import os

st.set_page_config(
    page_title="Адміністрування заявок",
    layout="wide"
)

SAVE_FILE = "monitoring_requests.csv"

st.title("Адміністрування заявок моніторингу")

if not os.path.exists(SAVE_FILE):
    st.warning("Поки що немає поданих заявок.")
else:
    df = pd.read_csv(SAVE_FILE)

    st.subheader("Усі подані заявки")

    status_filter = st.selectbox(
        "Фільтр за статусом погодження",
        ["Усі"] + sorted(df["approval_status"].dropna().unique().tolist())
    )

    filtered = df.copy()

    if status_filter != "Усі":
        filtered = filtered[filtered["approval_status"] == status_filter]

    st.dataframe(
        filtered,
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    st.subheader("Демо-блок погодження")

    selected_index = st.number_input(
        "Номер рядка заявки для зміни статусу",
        min_value=0,
        max_value=len(df) - 1,
        value=0,
        step=1
    )

    new_status = st.selectbox(
        "Новий статус",
        [
            "Очікує погодження",
            "Погоджено",
            "Повернуто на доопрацювання"
        ]
    )

    admin_comment = st.text_area("Коментар адміністратора")

    if st.button("Оновити статус заявки"):

        df.loc[selected_index, "approval_status"] = new_status
        df.loc[selected_index, "admin_comment"] = admin_comment

        df.to_csv(SAVE_FILE, index=False)

        st.success("Статус заявки оновлено.")
        st.rerun()
