import streamlit as st
import pandas as pd
from supabase import create_client

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


def clean(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value)


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


st.title("Адміністрування заявок моніторингу")

df = load_requests()
strat_df = load_strat_matrix()

if df.empty:
    st.warning("Поки що немає поданих заявок.")
    st.stop()

required_cols = [
    "id", "department", "year", "quarter", "approval_status", "status",
    "strat_code", "responsible_person", "phone", "numeric_value",
    "progress_text", "risks", "file_names", "admin_comment",
    "start_date", "end_date", "file_urls"
]

for col in required_cols:
    if col not in df.columns:
        df[col] = ""

st.subheader("Фільтри")

f1, f2, f3, f4 = st.columns(4)

with f1:
    departments = sorted(df["department"].dropna().astype(str).unique().tolist())
    selected_department = st.selectbox("Департамент", ["Усі"] + departments)

with f2:
    years = sorted(df["year"].dropna().astype(int).unique().tolist())
    selected_year = st.selectbox("Рік", ["Усі"] + years)

with f3:
    selected_quarter = st.selectbox("Квартал", ["Усі", "I", "II", "III", "IV"])

with f4:
    selected_approval_status = st.selectbox(
        "Статус погодження",
        ["Усі", "Очікує погодження", "Погоджено", "Повернуто на доопрацювання"]
    )

filtered = df.copy()

if selected_department != "Усі":
    filtered = filtered[filtered["department"].astype(str) == str(selected_department)]

if selected_year != "Усі":
    filtered = filtered[filtered["year"].astype(int) == int(selected_year)]

if selected_quarter != "Усі":
    filtered = filtered[filtered["quarter"].astype(str) == str(selected_quarter)]

if selected_approval_status != "Усі":
    filtered = filtered[
        filtered["approval_status"].astype(str) == str(selected_approval_status)
    ]

st.caption(f"Знайдено заявок: {len(filtered)}")

if filtered.empty:
    st.info("За обраними фільтрами заявок не знайдено.")
    st.stop()

st.divider()

selected_options = []

for _, row in filtered.iterrows():
    option = (
        f"ID {row['id']} | "
        f"{row['department']} | "
        f"{row['strat_code']} | "
        f"{row['year']} {row['quarter']} квартал | "
        f"{row['approval_status']}"
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

approval_status = clean(selected_row["approval_status"])
selected_code = clean(selected_row["strat_code"])

st.subheader(f"Заявка ID {clean(selected_row['id'])} — захід {selected_code}")

if approval_status == "Погоджено":
    st.success("Статус погодження: Погоджено")
elif approval_status == "Повернуто на доопрацювання":
    st.error("Статус погодження: Повернуто на доопрацювання")
else:
    st.warning("Статус погодження: Очікує погодження")

st.markdown("### Інформація про захід зі стратегічного плану")

measure_info = strat_df[
    strat_df["code"].astype(str).str.strip() == selected_code
].copy()

if measure_info.empty:
    st.warning("Захід не знайдено у стратегічній матриці.")
else:
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

    st.dataframe(
        measure_info[
            [
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
        ],
        use_container_width=True,
        hide_index=True
    )

st.markdown("### Дані заявки")

m1, m2, m3 = st.columns(3)

with m1:
    st.metric("Департамент", clean(selected_row["department"]))
    st.metric("Рік", clean(selected_row["year"]))

with m2:
    st.metric("Квартал", clean(selected_row["quarter"]))
    st.metric("Статус виконання", clean(selected_row["status"]))

with m3:
    st.metric("Фактичне значення", clean(selected_row["numeric_value"]))
    st.metric("Код заходу", selected_code)

st.markdown("### Дані відповідальної особи")

p1, p2 = st.columns(2)

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

st.markdown("### Терміни виконання")

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

st.subheader("Рішення адміністратора")

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

    st.success("Заявку погоджено.")
    st.rerun()

if return_back:
    supabase.table("monitoring_requests").update({
        "approval_status": "Повернуто на доопрацювання",
        "admin_comment": admin_comment
    }).eq("id", selected_id).execute()

    st.warning("Заявку повернуто на доопрацювання.")
    st.rerun()

if keep_waiting:
    supabase.table("monitoring_requests").update({
        "approval_status": "Очікує погодження",
        "admin_comment": admin_comment
    }).eq("id", selected_id).execute()

    st.info("Заявку залишено в очікуванні.")
    st.rerun()

st.divider()

st.subheader("Технічна таблиця заявок")

st.dataframe(
    filtered,
    use_container_width=True,
    hide_index=True
)
