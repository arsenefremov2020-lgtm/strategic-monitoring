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

   df["selection"] = (
    df["department"].astype(str)
    + " | "
    + df["strat_code"].astype(str)
    + " | "
    + df["responsible_person"].astype(str)
)

selected_item = st.selectbox(
    "Оберіть заявку",
    df["selection"].tolist()
)

selected_index = df[
    df["selection"] == selected_item
].index[0]

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
