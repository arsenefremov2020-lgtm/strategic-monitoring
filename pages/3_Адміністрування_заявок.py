import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(
    page_title="Адміністрування заявок",
    layout="wide"
)

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

st.title("Адміністрування заявок моніторингу")

response = (
    supabase
    .table("monitoring_requests")
    .select("*")
    .order("id", desc=True)
    .execute()
)

data = response.data

if not data:
    st.warning("Поки що немає поданих заявок.")

else:
    df = pd.DataFrame(data)

    st.subheader("Усі подані заявки")

    status_filter = st.selectbox(
        "Фільтр за статусом погодження",
        ["Усі"] + sorted(df["approval_status"].dropna().unique().tolist())
    )

    filtered = df.copy()

    if status_filter != "Усі":
        filtered = filtered[
            filtered["approval_status"] == status_filter
        ]

    st.dataframe(
        filtered,
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    st.subheader("Погодження заявки")

    df["selection"] = (
        "ID "
        + df["id"].astype(str)
        + " | "
        + df["department"].astype(str)
        + " | "
        + df["strat_code"].astype(str)
        + " | "
        + df["responsible_person"].astype(str)
        + " | "
        + df["year"].astype(str)
        + " "
        + df["quarter"].astype(str)
    )

    selected_item = st.selectbox(
        "Оберіть заявку",
        df["selection"].tolist()
    )

    selected_row = df[
        df["selection"] == selected_item
    ].iloc[0]

    selected_id = int(selected_row["id"])

    new_status = st.selectbox(
        "Новий статус",
        [
            "Очікує погодження",
            "Погоджено",
            "Повернуто на доопрацювання"
        ]
    )

    admin_comment = st.text_area(
        "Коментар адміністратора"
    )

    if st.button("Оновити статус заявки"):

        supabase.table("monitoring_requests").update({
            "approval_status": new_status,
            "admin_comment": admin_comment
        }).eq("id", selected_id).execute()

        st.success("Статус заявки оновлено.")
        st.rerun()
