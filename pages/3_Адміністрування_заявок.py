import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime
from html import escape

st.set_page_config(
    page_title="Адміністрування заявок",
    layout="wide"
)

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

st.markdown(
    """
    <style>
    .request-card {
        border: 1px solid #d1d5db;
        border-radius: 12px;
        padding: 16px 18px;
        margin-bottom: 16px;
        background: #ffffff;
        box-shadow: 0 4px 12px rgba(15,23,42,0.05);
    }

    .request-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 16px;
        margin-bottom: 12px;
    }

    .request-title {
        font-size: 18px;
        font-weight: 800;
        color: #111827;
        line-height: 1.35;
    }

    .request-meta {
        font-size: 13px;
        color: #4b5563;
        line-height: 1.55;
    }

    .status-badge {
        display: inline-block;
        padding: 6px 10px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 700;
        white-space: nowrap;
    }

    .status-waiting {
        background: #fef3c7;
        color: #92400e;
    }

    .status-approved {
        background: #dcfce7;
        color: #166534;
    }

    .status-returned {
        background: #fee2e2;
        color: #991b1b;
    }

    .mini-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 10px;
        margin: 12px 0;
    }

    .mini-cell {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 10px;
        background: #f8fafc;
    }

    .mini-label {
        font-size: 12px;
        color: #6b7280;
        margin-bottom: 4px;
    }

    .mini-value {
        font-size: 14px;
        font-weight: 700;
        color: #111827;
        white-space: normal;
        overflow-wrap: break-word;
    }

    .text-block {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 10px 12px;
        background: #ffffff;
        margin-top: 10px;
    }

    .text-label {
        font-size: 13px;
        font-weight: 800;
        color: #374151;
        margin-bottom: 6px;
    }

    .text-value {
        font-size: 14px;
        color: #111827;
        line-height: 1.5;
        white-space: pre-wrap;
        overflow-wrap: break-word;
    }
    </style>
    """,
    unsafe_allow_html=True
)


def safe(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return escape(str(value))


def status_class(status):
    if status == "Погоджено":
        return "status-approved"
    if status == "Повернуто на доопрацювання":
        return "status-returned"
    return "status-waiting"


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

if df.empty:
    st.warning("Поки що немає поданих заявок.")
    st.stop()

for col in [
    "department",
    "year",
    "quarter",
    "approval_status",
    "status",
    "strat_code",
    "responsible_person",
    "phone",
    "numeric_value",
    "progress_text",
    "risks",
    "file_names",
    "admin_comment",
    "start_date",
    "end_date"
]:
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
    quarters = ["I", "II", "III", "IV"]
    selected_quarter = st.selectbox("Квартал", ["Усі"] + quarters)

with f4:
    statuses = [
        "Усі",
        "Очікує погодження",
        "Погоджено",
        "Повернуто на доопрацювання"
    ]
    selected_approval_status = st.selectbox("Статус погодження", statuses)

filtered = df.copy()

if selected_department != "Усі":
    filtered = filtered[
        filtered["department"].astype(str) == str(selected_department)
    ]

if selected_year != "Усі":
    filtered = filtered[
        filtered["year"].astype(int) == int(selected_year)
    ]

if selected_quarter != "Усі":
    filtered = filtered[
        filtered["quarter"].astype(str) == str(selected_quarter)
    ]

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

approval_status = str(selected_row["approval_status"])

badge_class = status_class(approval_status)

st.markdown(
    f"""
    <div class="request-card">
        <div class="request-header">
            <div>
                <div class="request-title">
                    Заявка ID {safe(selected_row["id"])} — захід {safe(selected_row["strat_code"])}
                </div>
                <div class="request-meta">
                    Департамент: <b>{safe(selected_row["department"])}</b><br>
                    Період: <b>{safe(selected_row["year"])} рік, {safe(selected_row["quarter"])} квартал</b><br>
                    Подав/подала: <b>{safe(selected_row["responsible_person"])}</b>, тел. {safe(selected_row["phone"])}
                </div>
            </div>
            <div>
                <span class="status-badge {badge_class}">
                    {safe(approval_status)}
                </span>
            </div>
        </div>

        <div class="mini-grid">
            <div class="mini-cell">
                <div class="mini-label">Статус виконання</div>
                <div class="mini-value">{safe(selected_row["status"])}</div>
            </div>
            <div class="mini-cell">
                <div class="mini-label">Фактичне значення</div>
                <div class="mini-value">{safe(selected_row["numeric_value"])}</div>
            </div>
            <div class="mini-cell">
                <div class="mini-label">Початкова дата</div>
                <div class="mini-value">{safe(selected_row["start_date"])}</div>
            </div>
            <div class="mini-cell">
                <div class="mini-label">Кінцева дата</div>
                <div class="mini-value">{safe(selected_row["end_date"])}</div>
            </div>
        </div>

        <div class="text-block">
            <div class="text-label">Опис прогресу</div>
            <div class="text-value">{safe(selected_row["progress_text"])}</div>
        </div>

        <div class="text-block">
            <div class="text-label">Ризики / проблеми / відхилення</div>
            <div class="text-value">{safe(selected_row["risks"])}</div>
        </div>

        <div class="text-block">
            <div class="text-label">Підтвердні файли</div>
            <div class="text-value">{safe(selected_row["file_names"])}</div>
        </div>

        <div class="text-block">
            <div class="text-label">Коментар адміністратора</div>
            <div class="text-value">{safe(selected_row["admin_comment"])}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.subheader("Рішення адміністратора")

admin_comment = st.text_area(
    "Коментар адміністратора",
    value="" if pd.isna(selected_row["admin_comment"]) else str(selected_row["admin_comment"])
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
