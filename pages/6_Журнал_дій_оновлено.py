import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime
from io import BytesIO
import re

st.set_page_config(page_title="Журнал дій", layout="wide")

st.logo(
    "assets/Мінекономіки.png",
    size="large"
)

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

.stApp::before {
    content: "";
    position: fixed;
    top: -160px;
    right: -120px;
    width: 460px;
    height: 460px;
    border-radius: 50%;
    background: rgba(37, 99, 235, 0.045);
    z-index: 0;
}

.stApp::after {
    content: "";
    position: fixed;
    bottom: -180px;
    left: -120px;
    width: 390px;
    height: 390px;
    border-radius: 50%;
    background: rgba(22, 163, 74, 0.045);
    z-index: 0;
}

.main .block-container {
    max-width: 1550px;
    padding-top: 1.2rem;
    padding-bottom: 2.2rem;
    position: relative;
    z-index: 1;
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
    margin: 12px 0 0 0;
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

.badge-green {
    background: #dcfce7;
    border: 1px solid #bbf7d0;
    color: #166534;
}

.badge-yellow {
    background: #fef9c3;
    border: 1px solid #fde68a;
    color: #854d0e;
}

.badge-red {
    background: #fee2e2;
    border: 1px solid #fecaca;
    color: #991b1b;
}

.metric-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    margin-top: 12px;
}

.metric-card {
    border-radius: 16px;
    padding: 16px 18px;
    border: 1px solid #d8dee9;
    box-shadow: 0 6px 16px rgba(15,23,42,0.045);
}

.metric-title {
    font-size: 13px;
    color: #475569;
    font-weight: 850;
    margin-bottom: 4px;
}

.metric-value {
    font-size: 30px;
    line-height: 1.1;
    color: #0f172a;
    font-weight: 950;
}

.metric-note {
    font-size: 12px;
    color: #64748b;
    margin-top: 5px;
}

.metric-blue {
    background: #dbeafe;
    border-color: #bfdbfe;
}

.metric-green {
    background: #dcfce7;
    border-color: #bbf7d0;
}

.metric-yellow {
    background: #fef9c3;
    border-color: #fde68a;
}

.metric-red {
    background: #fee2e2;
    border-color: #fecaca;
}

.filter-box {
    background: linear-gradient(180deg, #f8fbff 0%, #eef6ff 100%);
    border: 1px solid #bfdbfe;
    border-radius: 14px;
    padding: 14px 14px 8px 14px;
    min-height: 104px;
}

.filter-label {
    color: #1e3a8a;
    font-size: 13px;
    font-weight: 900;
    margin-bottom: 6px;
}

.small-note {
    color: #64748b;
    font-size: 13px;
    line-height: 1.55;
}

.section-divider {
    height: 1px;
    background: #d8dee9;
    margin: 10px 0 16px 0;
}

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.9);
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

div.stButton > button,
div.stDownloadButton > button {
    border-radius: 12px;
    padding: 10px 16px;
    font-weight: 850;
    border: 1px solid #bfdbfe;
}

div[data-testid="stDataFrame"] {
    border-radius: 14px;
    overflow: hidden;
}

.footer {
    text-align: center;
    color: #64748b;
    font-size: 13px;
    margin-top: 50px;
    padding: 22px 0 12px 0;
    border-top: 1px solid #d8dee9;
}

@media (max-width: 1100px) {
    .metric-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}

@media (max-width: 700px) {
    .metric-grid {
        grid-template-columns: 1fr;
    }
}
</style>
""", unsafe_allow_html=True)


def clean(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value)


def parse_datetime(value):
    if value is None or pd.isna(value):
        return pd.NaT
    return pd.to_datetime(value, errors="coerce")


def natural_sort_key(value):
    text = str(value)
    nums = re.findall(r"\d+", text)
    if nums:
        return [int(n) for n in nums]
    return [10**9, text.lower()]


def dataframe_to_excel(sheets):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for sheet_name, df in sheets.items():
            safe_name = str(sheet_name)[:31]
            df.to_excel(writer, sheet_name=safe_name, index=False)

            worksheet = writer.sheets[safe_name]
            workbook = writer.book

            header_format = workbook.add_format({
                "bold": True,
                "bg_color": "#D9EAF7",
                "border": 1,
                "text_wrap": True,
                "valign": "top"
            })

            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, 18)

            worksheet.freeze_panes(1, 0)

    output.seek(0)
    return output


@st.cache_data(ttl=60)
def load_logs():
    response = (
        supabase
        .table("monitoring_logs")
        .select("*")
        .order("changed_at", desc=True)
        .execute()
    )

    return pd.DataFrame(response.data or [])


@st.cache_data(ttl=60)
def load_requests():
    response = (
        supabase
        .table("monitoring_requests")
        .select("id, department, strat_code, year, quarter, responsible_person")
        .execute()
    )

    return pd.DataFrame(response.data or [])


@st.cache_data(ttl=60)
def load_versions():
    response = (
        supabase
        .table("monitoring_request_versions")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )

    return pd.DataFrame(response.data or [])


def prepare_logs(logs_df, requests_df):
    if logs_df.empty:
        return logs_df

    prepared = logs_df.copy()

    if "changed_at" in prepared.columns:
        prepared["changed_at_dt"] = prepared["changed_at"].apply(parse_datetime)
        prepared = prepared.sort_values("changed_at_dt", ascending=False, na_position="last")

    if not requests_df.empty and "request_id" in prepared.columns:
        req = requests_df.copy()
        req = req.rename(columns={
            "department": "department_request",
            "strat_code": "strat_code_request",
            "year": "year_request",
            "quarter": "quarter_request",
            "responsible_person": "responsible_person_request"
        })

        prepared = prepared.merge(
            req,
            left_on="request_id",
            right_on="id",
            how="left",
            suffixes=("", "_request_join")
        )

        for left_col, right_col in [
            ("department", "department_request"),
            ("strat_code", "strat_code_request"),
            ("year", "year_request"),
            ("quarter", "quarter_request"),
            ("responsible_person", "responsible_person_request")
        ]:
            if left_col not in prepared.columns:
                prepared[left_col] = ""
            if right_col in prepared.columns:
                prepared[left_col] = prepared[left_col].where(
                    prepared[left_col].notna() & (prepared[left_col].astype(str) != ""),
                    prepared[right_col]
                )

    return prepared


def apply_filters(df, selected_departments, selected_actions, selected_changed_by, selected_years, selected_quarters, search):
    filtered = df.copy()

    if selected_departments and "Усі" not in selected_departments and "department" in filtered.columns:
        filtered = filtered[filtered["department"].astype(str).isin(selected_departments)]

    if selected_actions and "Усі" not in selected_actions and "action" in filtered.columns:
        filtered = filtered[filtered["action"].astype(str).isin(selected_actions)]

    if selected_changed_by and "Усі" not in selected_changed_by and "changed_by" in filtered.columns:
        filtered = filtered[filtered["changed_by"].astype(str).isin(selected_changed_by)]

    if selected_years and "Усі" not in selected_years and "year" in filtered.columns:
        filtered = filtered[filtered["year"].astype(str).isin([str(y) for y in selected_years])]

    if selected_quarters and "Усі" not in selected_quarters and "quarter" in filtered.columns:
        filtered = filtered[filtered["quarter"].astype(str).isin([str(q) for q in selected_quarters])]

    if search.strip():
        sq = search.strip().lower()
        mask = pd.Series(False, index=filtered.index)

        for col in filtered.columns:
            mask = mask | filtered[col].astype(str).str.lower().str.contains(sq, na=False, regex=False)

        filtered = filtered[mask]

    return filtered


def render_metric_cards(total_logs, unique_requests, unique_actions, total_versions, filtered_count=None):
    filtered_note = ""
    if filtered_count is not None and filtered_count != total_logs:
        filtered_note = f"Після фільтрів: {filtered_count}"

    st.markdown(f"""
    <div class="metric-grid">
        <div class="metric-card metric-blue">
            <div class="metric-title">Записів у журналі</div>
            <div class="metric-value">{total_logs}</div>
            <div class="metric-note">{filtered_note if filtered_note else "Усі зафіксовані системні дії"}</div>
        </div>
        <div class="metric-card metric-green">
            <div class="metric-title">Заявок із діями</div>
            <div class="metric-value">{unique_requests}</div>
            <div class="metric-note">Унікальні заявки, за якими є події</div>
        </div>
        <div class="metric-card metric-yellow">
            <div class="metric-title">Типів дій</div>
            <div class="metric-value">{unique_actions}</div>
            <div class="metric-note">Погодження, повернення, повторне подання тощо</div>
        </div>
        <div class="metric-card metric-red">
            <div class="metric-title">Версій заявок</div>
            <div class="metric-value">{total_versions}</div>
            <div class="metric-note">Історія повторних або змінених подань</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


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
        Сторінка призначена для перегляду історії роботи із заявками моніторингу:
        створення записів, погодження, повернення на доопрацювання, повторні подання,
        зміни статусів і формування версій заявок.
    </div>
    <div class="badge-wrap">
        <div class="badge">● Audit dashboard</div>
        <div class="badge badge-green">● Журнал дій</div>
        <div class="badge badge-yellow">● Версійність заявок</div>
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

logs_df = prepare_logs(logs_df, requests_df)

st.markdown('<div class="card"><div class="card-title">Ключові показники журналу</div><div class="card-subtitle">Зведення щодо кількості подій, заявок і версій у системі.</div>', unsafe_allow_html=True)

total_logs = len(logs_df)
unique_requests = logs_df["request_id"].nunique() if "request_id" in logs_df.columns else 0
unique_actions = logs_df["action"].nunique() if "action" in logs_df.columns else 0
total_versions = len(versions_df)

render_metric_cards(total_logs, unique_requests, unique_actions, total_versions)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
<div class="card">
    <div class="card-title">Фільтри журналу</div>
    <div class="card-subtitle">
        Оберіть один або кілька параметрів для перегляду потрібного зрізу дій.
        Якщо значення не обрано або обрано «Усі», фільтр не обмежує вибірку.
    </div>
""", unsafe_allow_html=True)

f1, f2, f3 = st.columns(3)

with f1:
    st.markdown('<div class="filter-label">Департамент</div>', unsafe_allow_html=True)
    departments = ["Усі"]
    if "department" in logs_df.columns:
        deps = logs_df["department"].dropna().astype(str).unique().tolist()
        departments += sorted([d for d in deps if d and d.lower() != "nan"], key=natural_sort_key)
    selected_departments = st.multiselect("Департамент", departments, default=["Усі"], label_visibility="collapsed")

with f2:
    st.markdown('<div class="filter-label">Дія</div>', unsafe_allow_html=True)
    actions = ["Усі"]
    if "action" in logs_df.columns:
        actions += sorted(logs_df["action"].dropna().astype(str).unique().tolist())
    selected_actions = st.multiselect("Дія", actions, default=["Усі"], label_visibility="collapsed")

with f3:
    st.markdown('<div class="filter-label">Ким змінено</div>', unsafe_allow_html=True)
    changed_by_values = ["Усі"]
    if "changed_by" in logs_df.columns:
        changed_by_values += sorted(logs_df["changed_by"].dropna().astype(str).unique().tolist())
    selected_changed_by = st.multiselect("Ким змінено", changed_by_values, default=["Усі"], label_visibility="collapsed")

f4, f5, f6 = st.columns(3)

with f4:
    st.markdown('<div class="filter-label">Рік</div>', unsafe_allow_html=True)
    years = ["Усі"]
    if "year" in logs_df.columns:
        year_values = logs_df["year"].dropna().astype(str).unique().tolist()
        years += sorted([y for y in year_values if y and y.lower() != "nan"], key=natural_sort_key)
    selected_years = st.multiselect("Рік", years, default=["Усі"], label_visibility="collapsed")

with f5:
    st.markdown('<div class="filter-label">Квартал</div>', unsafe_allow_html=True)
    quarter_order = {"I": 1, "II": 2, "III": 3, "IV": 4}
    quarters = ["Усі"]
    if "quarter" in logs_df.columns:
        q_values = logs_df["quarter"].dropna().astype(str).unique().tolist()
        quarters += sorted([q for q in q_values if q and q.lower() != "nan"], key=lambda x: quarter_order.get(str(x), 99))
    selected_quarters = st.multiselect("Квартал", quarters, default=["Усі"], label_visibility="collapsed")

with f6:
    st.markdown('<div class="filter-label">Пошук</div>', unsafe_allow_html=True)
    search = st.text_input("Пошук за ID / кодом / текстом", placeholder="Введіть ID, код заходу, статус, коментар...", label_visibility="collapsed")

filtered = apply_filters(
    logs_df,
    selected_departments,
    selected_actions,
    selected_changed_by,
    selected_years,
    selected_quarters,
    search
)

st.markdown(f"""
<div class="badge-wrap">
    <div class="badge">● Знайдено записів: {len(filtered)}</div>
    <div class="badge badge-green">● Унікальних заявок у вибірці: {filtered["request_id"].nunique() if "request_id" in filtered.columns and not filtered.empty else 0}</div>
    <div class="badge badge-yellow">● Типів дій у вибірці: {filtered["action"].nunique() if "action" in filtered.columns and not filtered.empty else 0}</div>
</div>
""", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Аналітика журналу</div><div class="card-subtitle">Графіки будуються за відфільтрованою вибіркою.</div>', unsafe_allow_html=True)

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
        fig.update_traces(textposition="outside")
        fig.update_layout(
            xaxis_tickangle=-25,
            yaxis_title="Кількість",
            xaxis_title="Дія",
            margin=dict(l=10, r=10, t=55, b=80)
        )
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
        fig.update_layout(margin=dict(l=10, r=10, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Немає даних для графіка виконавців.")

a3, a4 = st.columns(2)

with a3:
    if "department" in filtered.columns and not filtered.empty:
        department_chart = filtered["department"].fillna("Невідомо").value_counts().reset_index()
        department_chart.columns = ["Департамент", "Кількість"]

        fig = px.bar(
            department_chart,
            x="Департамент",
            y="Кількість",
            text="Кількість",
            title="Кількість дій за департаментами"
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            xaxis_tickangle=-25,
            yaxis_title="Кількість",
            xaxis_title="Департамент",
            margin=dict(l=10, r=10, t=55, b=100)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Немає даних для графіка департаментів.")

with a4:
    if "changed_at_dt" in filtered.columns and not filtered.empty:
        timeline = filtered.copy()
        timeline["Дата"] = timeline["changed_at_dt"].dt.date
        timeline = timeline.dropna(subset=["Дата"])

        if not timeline.empty:
            timeline_chart = timeline.groupby("Дата").size().reset_index(name="Кількість")

            fig = px.line(
                timeline_chart,
                x="Дата",
                y="Кількість",
                markers=True,
                title="Динаміка дій у часі"
            )
            fig.update_layout(
                yaxis_title="Кількість",
                xaxis_title="Дата",
                margin=dict(l=10, r=10, t=55, b=40)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Немає валідних дат для побудови динаміки.")
    else:
        st.info("Немає даних для графіка динаміки.")

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Повний журнал дій</div><div class="card-subtitle">Детальний перелік системних подій за обраними фільтрами.</div>', unsafe_allow_html=True)

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

if filtered.empty:
    st.info("За обраними фільтрами записів не знайдено.")
else:
    st.dataframe(
        show[available],
        use_container_width=True,
        hide_index=True
    )

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Версії заявок</div><div class="card-subtitle">Попередні та повторно подані версії заявок. Блок зберігає наявний механізм версійності.</div>', unsafe_allow_html=True)

if versions_df.empty:
    st.info("Версій заявок поки що немає.")
else:
    versions_show = versions_df.copy()

    if "created_at" in versions_show.columns:
        versions_show["created_at_dt"] = versions_show["created_at"].apply(parse_datetime)
        versions_show = versions_show.sort_values("created_at_dt", ascending=False, na_position="last")

    versions_show = versions_show.rename(columns={
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

st.markdown('<div class="card"><div class="card-title">Експорт журналу</div><div class="card-subtitle">Завантаження поточного зрізу журналу та повного реєстру версій.</div>', unsafe_allow_html=True)

export_logs = show[available] if not filtered.empty and available else pd.DataFrame()
export_versions = versions_show[version_available] if not versions_df.empty and version_available else pd.DataFrame()

excel_file = dataframe_to_excel({
    "Журнал дій": export_logs,
    "Версії заявок": export_versions
})

st.download_button(
    "Завантажити журнал дій та версії XLSX",
    data=excel_file,
    file_name=f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
<div class="footer">
    Розроблено департаментом стратегічного планування та макроекономічного прогнозування<br>
    Версія DEMO 1.4 | 2026 | Внутрішня система моніторингу стратегічного плану
</div>
""", unsafe_allow_html=True)
