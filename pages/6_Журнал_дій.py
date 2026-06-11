import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime

st.set_page_config(page_title="Журнал дій", layout="wide")

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

st.markdown("""
<style>
header[data-testid="stHeader"] {
    background: transparent !important;
}
.stApp {
    background:
        radial-gradient(circle at top right, rgba(37,99,235,0.08), transparent 28%),
        radial-gradient(circle at bottom left, rgba(22,163,74,0.07), transparent 30%),
        linear-gradient(180deg, #f6f8fb 0%, #eef2f7 100%);
}

.main .block-container {
    max-width: 1550px;
    padding-top: 1.2rem;
}

.ua-line {
    height: 7px;
    border-radius: 999px;
    background: linear-gradient(90deg, #005BBB 0%, #005BBB 50%, #FFD500 50%, #FFD500 100%);
    margin-bottom: 14px;
}

.ministry-label {
    text-align: right;
    color: #475569;
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 8px;
}

.header-box, .card {
    background: rgba(255,255,255,0.94);
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 18px;
    box-shadow: 0 8px 24px rgba(15,23,42,0.06);
}

.header-title {
    font-size: 32px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 8px;
}

.header-subtitle, .card-subtitle {
    font-size: 15px;
    color: #475569;
    line-height: 1.55;
}

.card-title {
    font-size: 21px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 8px;
}

.badge-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 12px 0;
}

.badge {
    background: #eef6ff;
    border: 1px solid #bfdbfe;
    color: #1d4ed8;
    border-radius: 999px;
    padding: 7px 11px;
    font-size: 13px;
    font-weight: 800;
}

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.9);
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

.footer {
    text-align: center;
    color: #64748b;
    font-size: 13px;
    margin-top: 50px;
    padding: 22px 0 12px 0;
    border-top: 1px solid #d8dee9;
}
</style>
""", unsafe_allow_html=True)


def clean(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value)


def load_logs():
    response = (
        supabase
        .table("monitoring_logs")
        .select("*")
        .order("changed_at", desc=True)
        .execute()
    )

    return pd.DataFrame(response.data or [])


def load_requests():
    response = (
        supabase
        .table("monitoring_requests")
        .select("id, department, strat_code, year, quarter, responsible_person")
        .execute()
    )

    return pd.DataFrame(response.data or [])


def load_versions():
    response = (
        supabase
        .table("monitoring_request_versions")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )

    return pd.DataFrame(response.data or [])


st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)

st.markdown("""
<div class="ministry-label">
🇺🇦 Міністерство економіки, довкілля та сільського господарства України
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="header-box">
    <div class="header-title">Журнал дій системи</div>
    <div class="header-subtitle">
        Загальний audit dashboard для перегляду всіх дій із заявками:
        погодження, повернення, повторні подання, зміни статусів і створення версій.
    </div>
    <div class="badge-wrap">
        <div class="badge">● Режим: audit log</div>
        <div class="badge">● Джерело: monitoring_logs + monitoring_request_versions</div>
        <div class="badge">● Оновлено: {datetime.now().strftime("%d.%m.%Y %H:%M")}</div>
    </div>
</div>
""", unsafe_allow_html=True)

logs_df = load_logs()
requests_df = load_requests()
versions_df = load_versions()

if logs_df.empty:
    st.warning("Журнал дій поки що порожній.")
    st.stop()

if not requests_df.empty and "request_id" in logs_df.columns:
    logs_df = logs_df.merge(
        requests_df,
        left_on="request_id",
        right_on="id",
        how="left",
        suffixes=("", "_request")
    )

st.markdown('<div class="card"><div class="card-title">Ключові показники журналу</div>', unsafe_allow_html=True)

total_logs = len(logs_df)
unique_requests = logs_df["request_id"].nunique() if "request_id" in logs_df.columns else 0
unique_actions = logs_df["action"].nunique() if "action" in logs_df.columns else 0
total_versions = len(versions_df)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Записів у журналі", total_logs)
c2.metric("Заявок із діями", unique_requests)
c3.metric("Типів дій", unique_actions)
c4.metric("Версій заявок", total_versions)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Фільтри журналу</div>', unsafe_allow_html=True)

f1, f2, f3, f4 = st.columns(4)

with f1:
    departments = ["Усі"]
    if "department" in logs_df.columns:
        departments += sorted(logs_df["department"].dropna().astype(str).unique().tolist())
    selected_department = st.selectbox("Департамент", departments)

with f2:
    actions = ["Усі"]
    if "action" in logs_df.columns:
        actions += sorted(logs_df["action"].dropna().astype(str).unique().tolist())
    selected_action = st.selectbox("Дія", actions)

with f3:
    changed_by_values = ["Усі"]
    if "changed_by" in logs_df.columns:
        changed_by_values += sorted(logs_df["changed_by"].dropna().astype(str).unique().tolist())
    selected_changed_by = st.selectbox("Ким змінено", changed_by_values)

with f4:
    search = st.text_input("Пошук за ID / кодом / текстом")

filtered = logs_df.copy()

if selected_department != "Усі" and "department" in filtered.columns:
    filtered = filtered[filtered["department"].astype(str) == selected_department]

if selected_action != "Усі" and "action" in filtered.columns:
    filtered = filtered[filtered["action"].astype(str) == selected_action]

if selected_changed_by != "Усі" and "changed_by" in filtered.columns:
    filtered = filtered[filtered["changed_by"].astype(str) == selected_changed_by]

if search.strip():
    sq = search.strip().lower()
    mask = pd.Series(False, index=filtered.index)

    for col in filtered.columns:
        mask = mask | filtered[col].astype(str).str.lower().str.contains(sq, na=False)

    filtered = filtered[mask]

st.caption(f"Знайдено записів: {len(filtered)}")

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Аналітика журналу</div>', unsafe_allow_html=True)

a1, a2 = st.columns(2)

with a1:
    if "action" in filtered.columns and not filtered.empty:
        action_chart = filtered["action"].fillna("Невідомо").value_counts().reset_index()
        action_chart.columns = ["Дія", "Кількість"]

        fig = px.bar(
            action_chart,
            x="Дія",
            y="Кількість",
            text="Кількість",
            title="Кількість дій за типами"
        )
        fig.update_layout(xaxis_tickangle=-25)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Немає даних для графіка дій.")

with a2:
    if "changed_by" in filtered.columns and not filtered.empty:
        user_chart = filtered["changed_by"].fillna("Невідомо").value_counts().reset_index()
        user_chart.columns = ["Ким змінено", "Кількість"]

        fig = px.pie(
            user_chart,
            names="Ким змінено",
            values="Кількість",
            hole=0.45,
            title="Розподіл дій за виконавцем"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Немає даних для графіка виконавців.")

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Повний журнал дій</div>', unsafe_allow_html=True)

show = filtered.copy()

rename_map = {
    "id": "ID запису",
    "request_id": "ID заявки",
    "department": "Департамент",
    "strat_code": "Код заходу",
    "year": "Рік",
    "quarter": "Квартал",
    "responsible_person": "Відповідальна особа",
    "changed_at": "Дата зміни",
    "action": "Дія",
    "old_status": "Попередній статус",
    "new_status": "Новий статус",
    "admin_comment": "Коментар",
    "changed_by": "Ким змінено"
}

show = show.rename(columns=rename_map)

cols = [
    "Дата зміни",
    "ID заявки",
    "Департамент",
    "Код заходу",
    "Рік",
    "Квартал",
    "Дія",
    "Попередній статус",
    "Новий статус",
    "Коментар",
    "Ким змінено",
    "Відповідальна особа"
]

available = [c for c in cols if c in show.columns]

st.dataframe(
    show[available],
    use_container_width=True,
    hide_index=True
)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Версії заявок</div><div class="card-subtitle">Тут зберігаються попередні та повторно подані версії заявок.</div>', unsafe_allow_html=True)

if versions_df.empty:
    st.info("Версій заявок поки що немає.")
else:
    versions_show = versions_df.rename(columns={
        "request_id": "ID заявки",
        "version_number": "Версія",
        "created_at": "Дата версії",
        "created_by": "Ким створено",
        "department": "Департамент",
        "strat_code": "Код заходу",
        "year": "Рік",
        "quarter": "Квартал",
        "approval_status": "Статус погодження",
        "status": "Статус виконання",
        "numeric_value": "Фактичне значення",
        "progress_text": "Опис прогресу",
        "risks": "Ризики"
    })

    version_cols = [
        "Дата версії",
        "ID заявки",
        "Версія",
        "Ким створено",
        "Департамент",
        "Код заходу",
        "Рік",
        "Квартал",
        "Статус погодження",
        "Статус виконання",
        "Фактичне значення",
        "Опис прогресу",
        "Ризики"
    ]

    version_available = [c for c in version_cols if c in versions_show.columns]

    st.dataframe(
        versions_show[version_available],
        use_container_width=True,
        hide_index=True
    )

st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
<div class="footer">
    Міністерство економіки, довкілля та сільського господарства України<br>
    Розроблено департаментом стратегічного планування та макроекономічного прогнозування<br>
    Версія DEMO 1.0 | Журнал дій та версійність заявок
</div>
""", unsafe_allow_html=True)
