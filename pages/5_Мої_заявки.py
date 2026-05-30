import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(
    page_title="Мої заявки",
    layout="wide"
)

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)


def clean(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value)


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


st.title("Мої заявки")

df = load_requests()

if df.empty:
    st.warning("Поки що немає поданих заявок.")
    st.stop()

required_cols = [
    "id",
    "department",
    "year",
    "quarter",
    "strat_code",
    "status",
    "numeric_value",
    "approval_status",
    "responsible_person",
    "phone",
    "progress_text",
    "risks",
    "file_names",
    "file_urls",
    "admin_comment",
    "submitted_at"
]

for col in required_cols:
    if col not in df.columns:
        df[col] = ""

st.info(
    "На цій сторінці департамент може переглянути свої подані заявки, "
    "їхній статус погодження, коментар адміністратора та підтвердні файли."
)

st.subheader("Фільтри")

f1, f2, f3 = st.columns(3)

with f1:
    departments = sorted(df["department"].dropna().astype(str).unique().tolist())
    selected_department = st.selectbox("Департамент", departments)

with f2:
    years = sorted(df["year"].dropna().astype(int).unique().tolist())
    selected_year = st.selectbox("Рік", ["Усі"] + years)

with f3:
    statuses = [
        "Усі",
        "Очікує погодження",
        "Погоджено",
        "Повернуто на доопрацювання"
    ]
    selected_status = st.selectbox("Статус погодження", statuses)

filtered = df[
    df["department"].astype(str) == str(selected_department)
].copy()

if selected_year != "Усі":
    filtered = filtered[
        filtered["year"].astype(int) == int(selected_year)
    ]

if selected_status != "Усі":
    filtered = filtered[
        filtered["approval_status"].astype(str) == str(selected_status)
    ]

st.caption(f"Знайдено заявок: {len(filtered)}")

if filtered.empty:
    st.info("За обраними фільтрами заявок не знайдено.")
    st.stop()

st.divider()

summary = (
    filtered
    .groupby("approval_status")
    .size()
    .reset_index(name="Кількість")
)

s1, s2, s3, s4 = st.columns(4)

s1.metric("Усього заявок", len(filtered))
s2.metric("Погоджено", len(filtered[filtered["approval_status"] == "Погоджено"]))
s3.metric("Очікує погодження", len(filtered[filtered["approval_status"] == "Очікує погодження"]))
s4.metric("Повернуто", len(filtered[filtered["approval_status"] == "Повернуто на доопрацювання"]))

st.divider()

st.subheader("Перелік заявок")

table_cols = [
    "id",
    "year",
    "quarter",
    "strat_code",
    "status",
    "numeric_value",
    "approval_status",
    "responsible_person",
    "submitted_at",
    "admin_comment"
]

available_cols = [col for col in table_cols if col in filtered.columns]

st.dataframe(
    filtered[available_cols],
    use_container_width=True,
    hide_index=True
)

st.divider()

st.subheader("Детальний перегляд заявки")

options = []

for _, row in filtered.iterrows():
    option = (
        f"ID {row['id']} | "
        f"{row['strat_code']} | "
        f"{row['year']} {row['quarter']} квартал | "
        f"{row['approval_status']}"
    )
    options.append(option)

selected_request = st.selectbox(
    "Оберіть заявку",
    options
)

selected_id = int(selected_request.split("|")[0].replace("ID", "").strip())

selected_row = filtered[
    filtered["id"].astype(int) == selected_id
].iloc[0]

approval_status = clean(selected_row["approval_status"])

if approval_status == "Погоджено":
    st.success("Статус: погоджено")
elif approval_status == "Повернуто на доопрацювання":
    st.error("Статус: повернуто на доопрацювання")
else:
    st.warning("Статус: очікує погодження")

c1, c2, c3 = st.columns(3)

with c1:
    st.metric("Код заходу", clean(selected_row["strat_code"]))
    st.metric("Рік", clean(selected_row["year"]))

with c2:
    st.metric("Квартал", clean(selected_row["quarter"]))
    st.metric("Статус виконання", clean(selected_row["status"]))

with c3:
    st.metric("Фактичне значення", clean(selected_row["numeric_value"]))
    st.metric("Департамент", clean(selected_row["department"]))

st.markdown("### Опис прогресу")

st.text_area(
    "Опис прогресу",
    value=clean(selected_row["progress_text"]),
    disabled=True,
    height=120
)

st.markdown("### Ризики / проблеми / відхилення")

st.text_area(
    "Ризики / проблеми / відхилення",
    value=clean(selected_row["risks"]),
    disabled=True,
    height=120
)

st.markdown("### Коментар адміністратора")

st.text_area(
    "Коментар адміністратора",
    value=clean(selected_row["admin_comment"]),
    disabled=True,
    height=100
)

st.markdown("### Підтвердні файли")

file_names = clean(selected_row["file_names"])
file_urls = clean(selected_row["file_urls"])

if not file_urls:
    st.info("Файлів до заявки не додано.")
else:
    urls = [u.strip() for u in file_urls.split(",") if u.strip()]
    names = [n.strip() for n in file_names.split(",") if n.strip()]

    for i, url in enumerate(urls):
        label = names[i] if i < len(names) else f"Файл {i + 1}"
        st.markdown(f"[{label}]({url})")

st.divider()

st.subheader("Історія зміни статусу")

logs_df = load_logs(selected_id)

if logs_df.empty:
    st.info("Історії змін для цієї заявки поки що немає.")
else:
    show_cols = [
        "changed_at",
        "action",
        "old_status",
        "new_status",
        "admin_comment",
        "changed_by"
    ]

    available_log_cols = [col for col in show_cols if col in logs_df.columns]

    st.dataframe(
        logs_df[available_log_cols],
        use_container_width=True,
        hide_index=True
    )
