import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime
import re

st.set_page_config(page_title="Мої заявки", layout="wide")

FILE_PATH = "Під моніторинг СП.xlsx"
SHEET_NAME = "Страт_матриця"
BUCKET_NAME = "monitoring-files"

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

st.markdown("""
<style>
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

.badge-gray {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    color: #475569;
}

.step-box {
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    margin: 10px 0;
}

.version-box {
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    margin: 10px 0;
}

.version-title {
    color: #0f172a;
    font-weight: 900;
    font-size: 15px;
    margin-bottom: 6px;
}

.version-text {
    color: #475569;
    font-size: 13px;
    line-height: 1.45;
}

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.9);
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

div.stButton > button {
    border-radius: 12px;
    padding: 12px 18px;
    font-weight: 800;
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


def has_value(value):
    return clean(value).strip() != ""


def safe_filename(name):
    name = str(name).replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_")


def valid_email(email):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(email).strip()) is not None


def upload_files(files, code):
    urls = []
    names = []
    safe_code = safe_filename(str(code)).replace(".", "_")

    for file in files:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = safe_filename(file.name)
        path = f"{safe_code}/{timestamp}_{filename}"

        supabase.storage.from_(BUCKET_NAME).upload(
            path,
            file.getvalue(),
            file_options={
                "content-type": file.type,
                "upsert": "true"
            }
        )

        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(path)
        urls.append(public_url)
        names.append(file.name)

    return ", ".join(names), ", ".join(urls)


@st.cache_data
def load_strat_matrix():
    df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=None, engine="openpyxl")
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
        .order("submitted_at", desc=True)
        .execute()
    )

    return pd.DataFrame(response.data or [])


def load_logs(request_id):
    response = (
        supabase
        .table("monitoring_logs")
        .select("*")
        .eq("request_id", int(request_id))
        .order("changed_at", desc=True)
        .execute()
    )

    return pd.DataFrame(response.data or [])


def write_log(request_id, action, old_status, new_status, admin_comment):
    supabase.table("monitoring_logs").insert({
        "request_id": int(request_id),
        "action": action,
        "old_status": old_status,
        "new_status": new_status,
        "admin_comment": admin_comment,
        "changed_by": "Департамент"
    }).execute()


def get_next_version_number(request_id):
    response = (
        supabase
        .table("monitoring_request_versions")
        .select("version_number")
        .eq("request_id", int(request_id))
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        return 1

    return int(response.data[0].get("version_number", 0)) + 1


def save_request_version(request_id, row_data, created_by="Департамент"):
    version_number = get_next_version_number(request_id)

    payload = {
        "request_id": int(request_id),
        "version_number": version_number,
        "year": clean(row_data.get("year", "")),
        "quarter": clean(row_data.get("quarter", "")),
        "department": clean(row_data.get("department", "")),
        "responsible_person": clean(row_data.get("responsible_person", "")),
        "phone": clean(row_data.get("phone", "")),
        "email": clean(row_data.get("email", "")),
        "strat_code": clean(row_data.get("strat_code", "")),
        "status": clean(row_data.get("status", "")),
        "progress_text": clean(row_data.get("progress_text", "")),
        "numeric_value": clean(row_data.get("numeric_value", "")),
        "risks": clean(row_data.get("risks", "")),
        "file_names": clean(row_data.get("file_names", "")),
        "file_urls": clean(row_data.get("file_urls", "")),
        "approval_status": clean(row_data.get("approval_status", "")),
        "admin_comment": clean(row_data.get("admin_comment", "")),
        "start_date": clean(row_data.get("start_date", "")),
        "end_date": clean(row_data.get("end_date", "")),
        "created_by": created_by
    }

    supabase.table("monitoring_request_versions").insert(payload).execute()

    return version_number


def load_versions(request_id):
    response = (
        supabase
        .table("monitoring_request_versions")
        .select("*")
        .eq("request_id", int(request_id))
        .order("version_number", desc=False)
        .execute()
    )

    return pd.DataFrame(response.data or [])


df = load_requests()
strat_df = load_strat_matrix()

st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)

st.markdown("""
<div class="ministry-label">
🇺🇦 Міністерство економіки, довкілля та сільського господарства України
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-box">
    <div class="header-title">Мої заявки</div>
    <div class="header-subtitle">
        Кабінет департаменту для перегляду поданих заявок, статусу погодження,
        коментарів адміністратора, підтвердних файлів, історії версій і повторного подання після доопрацювання.
    </div>
    <div class="badge-wrap">
        <div class="badge">● Режим: перегляд заявок</div>
        <div class="badge">● Доступ: департамент</div>
        <div class="badge">● Версійність: активна</div>
        <div class="badge">● Повторне подання: доступне для повернутих заявок</div>
    </div>
</div>
""", unsafe_allow_html=True)

if df.empty:
    st.warning("Поки що немає поданих заявок.")
    st.stop()

required_cols = [
    "id", "year", "quarter", "department", "responsible_person", "phone", "email",
    "strat_code", "status", "progress_text", "numeric_value", "risks",
    "submitted_at", "approval_status", "admin_comment", "file_names", "file_urls",
    "start_date", "end_date"
]

for col in required_cols:
    if col not in df.columns:
        df[col] = ""

st.markdown('<div class="card"><div class="card-title">Фільтри</div><div class="card-subtitle">Оберіть департамент, рік і статус погодження.</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)

with c1:
    departments = sorted(df["department"].dropna().astype(str).unique().tolist())
    selected_department = st.selectbox("Департамент", departments)

with c2:
    years = ["Усі"] + sorted(df["year"].dropna().astype(str).unique().tolist())
    selected_year = st.selectbox("Рік", years)

with c3:
    approval_statuses = [
        "Усі",
        "Очікує погодження",
        "Погоджено",
        "Повернуто на доопрацювання"
    ]
    selected_status = st.selectbox("Статус погодження", approval_statuses)

with c4:
    search = st.text_input("Пошук за кодом / ID / ПІБ")

filtered = df[df["department"].astype(str) == str(selected_department)].copy()

if selected_year != "Усі":
    filtered = filtered[filtered["year"].astype(str) == str(selected_year)]

if selected_status != "Усі":
    filtered = filtered[filtered["approval_status"].astype(str) == selected_status]

if search.strip():
    sq = search.strip().lower()
    filtered = filtered[
        filtered["id"].astype(str).str.lower().str.contains(sq, na=False)
        |
        filtered["strat_code"].astype(str).str.lower().str.contains(sq, na=False)
        |
        filtered["responsible_person"].astype(str).str.lower().str.contains(sq, na=False)
    ]

st.caption(f"Знайдено заявок: {len(filtered)}")

st.markdown('</div>', unsafe_allow_html=True)

if filtered.empty:
    st.info("За обраними фільтрами заявок не знайдено.")
    st.stop()

total = len(filtered)
approved = len(filtered[filtered["approval_status"] == "Погоджено"])
waiting = len(filtered[filtered["approval_status"] == "Очікує погодження"])
returned = len(filtered[filtered["approval_status"] == "Повернуто на доопрацювання"])
with_files = len(filtered[filtered["file_urls"].fillna("").astype(str).str.strip() != ""])

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Усього заявок", total)
m2.metric("Погоджено", approved)
m3.metric("Очікує", waiting)
m4.metric("Повернуто", returned)
m5.metric("Із файлами", with_files)

st.markdown('<div class="card"><div class="card-title">Перелік заявок</div>', unsafe_allow_html=True)

show_df = filtered.rename(columns={
    "id": "ID",
    "year": "Рік",
    "quarter": "Квартал",
    "strat_code": "Код заходу",
    "status": "Статус виконання",
    "numeric_value": "Фактичне значення",
    "approval_status": "Статус погодження",
    "responsible_person": "Відповідальна особа",
    "submitted_at": "Дата подання",
    "admin_comment": "Коментар адміністратора"
})

show_cols = [
    "ID", "Рік", "Квартал", "Код заходу", "Статус виконання",
    "Фактичне значення", "Статус погодження", "Відповідальна особа",
    "Дата подання", "Коментар адміністратора"
]

st.dataframe(show_df[show_cols], use_container_width=True, hide_index=True)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Детальний перегляд заявки</div>', unsafe_allow_html=True)

options = []

for _, row in filtered.iterrows():
    options.append(
        f"ID {row['id']} | {row['strat_code']} | {row['year']} {row['quarter']} квартал | {row['approval_status']}"
    )

selected = st.selectbox("Оберіть заявку", options)

selected_id = int(selected.split("|")[0].replace("ID", "").strip())
selected_row = filtered[filtered["id"].astype(int) == selected_id].iloc[0]

approval = clean(selected_row["approval_status"])
code = clean(selected_row["strat_code"])

badge_class = "badge-yellow"
if approval == "Погоджено":
    badge_class = "badge-green"
elif approval == "Повернуто на доопрацювання":
    badge_class = "badge-red"

st.markdown(f"""
<div class="badge-wrap">
    <div class="badge {badge_class}">Статус: {approval}</div>
    <div class="badge">Заявка ID {selected_id}</div>
    <div class="badge">Захід {code}</div>
    <div class="badge">Рік: {clean(selected_row["year"])}</div>
    <div class="badge">Квартал: {clean(selected_row["quarter"])}</div>
</div>
""", unsafe_allow_html=True)

measure_info = strat_df[strat_df["code"].astype(str).str.strip() == code].copy()

if not measure_info.empty:
    mi = measure_info.iloc[0]
    st.markdown(f"""
    <div class="step-box">
        <b>{code} — {clean(mi["name"])}</b><br>
        <span style="color:#475569;">Індикатор: {clean(mi["indicator"])}</span><br>
        <span style="color:#475569;">Одиниця виміру: {clean(mi["unit"])}</span><br>
        <span style="color:#475569;">Терміни: {clean(mi["start_date_plan"])} — {clean(mi["end_date_plan"])}</span>
    </div>
    """, unsafe_allow_html=True)

a1, a2, a3, a4, a5, a6 = st.columns(6)
a1.metric("Код", code)
a2.metric("Рік", clean(selected_row["year"]))
a3.metric("Квартал", clean(selected_row["quarter"]))
a4.metric("Статус виконання", clean(selected_row["status"]))
a5.metric("Факт", clean(selected_row["numeric_value"]))
a6.metric("Департамент", clean(selected_row["department"]))

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Дані заявки</div>', unsafe_allow_html=True)

p1, p2, p3 = st.columns(3)

with p1:
    st.text_input(
        "ПІБ відповідальної особи",
        value=clean(selected_row["responsible_person"]),
        disabled=True,
        key=f"view_responsible_{selected_id}"
    )

with p2:
    st.text_input(
        "Телефон",
        value=clean(selected_row["phone"]),
        disabled=True,
        key=f"view_phone_{selected_id}"
    )

with p3:
    st.text_input(
        "Email",
        value=clean(selected_row["email"]),
        disabled=True,
        key=f"view_email_{selected_id}"
    )

d1, d2 = st.columns(2)

with d1:
    st.text_input(
        "Початкова дата виконання",
        value=clean(selected_row["start_date"]),
        disabled=True,
        key=f"view_start_{selected_id}"
    )

with d2:
    st.text_input(
        "Кінцева дата виконання",
        value=clean(selected_row["end_date"]),
        disabled=True,
        key=f"view_end_{selected_id}"
    )

st.text_area(
    "Опис прогресу",
    value=clean(selected_row["progress_text"]),
    disabled=True,
    height=130,
    key=f"view_progress_{selected_id}"
)

st.text_area(
    "Ризики / проблеми / відхилення",
    value=clean(selected_row["risks"]),
    disabled=True,
    height=130,
    key=f"view_risks_{selected_id}"
)

if has_value(selected_row["admin_comment"]):
    st.warning(f"Коментар адміністратора: {clean(selected_row['admin_comment'])}")

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Підтвердні файли</div>', unsafe_allow_html=True)

file_urls = clean(selected_row["file_urls"])
file_names = clean(selected_row["file_names"])

if not file_urls:
    st.info("Файлів до заявки не додано.")
else:
    urls = [u.strip() for u in file_urls.split(",") if u.strip()]
    names = [n.strip() for n in file_names.split(",") if n.strip()]

    for i, url in enumerate(urls):
        label = names[i] if i < len(names) else f"Файл {i + 1}"
        st.markdown(f"- [{label}]({url})")

st.markdown('</div>', unsafe_allow_html=True)

logs_df = load_logs(selected_id)

st.markdown('<div class="card"><div class="card-title">Історія зміни статусу</div>', unsafe_allow_html=True)

if logs_df.empty:
    st.info("Історії змін для цієї заявки поки що немає.")
else:
    logs_show = logs_df.rename(columns={
        "changed_at": "Дата",
        "action": "Дія",
        "old_status": "Попередній статус",
        "new_status": "Новий статус",
        "admin_comment": "Коментар",
        "changed_by": "Ким змінено"
    })

    cols = ["Дата", "Дія", "Попередній статус", "Новий статус", "Коментар", "Ким змінено"]
    available = [c for c in cols if c in logs_show.columns]

    st.dataframe(logs_show[available], use_container_width=True, hide_index=True)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Історія версій заявки</div>', unsafe_allow_html=True)

versions_df = load_versions(selected_id)

if versions_df.empty:
    st.info("Версій для цієї заявки поки що немає.")
else:
    latest_version = versions_df.sort_values("version_number", ascending=False).iloc[0]

    st.markdown(f"""
    <div class="version-box">
        <div class="version-title">Остання збережена версія: №{clean(latest_version.get("version_number", ""))}</div>
        <div class="version-text">
            Створено: {clean(latest_version.get("created_at", ""))}<br>
            Ким створено: {clean(latest_version.get("created_by", ""))}<br>
            Статус погодження: {clean(latest_version.get("approval_status", ""))}<br>
            Статус виконання: {clean(latest_version.get("status", ""))}<br>
            Фактичне значення: {clean(latest_version.get("numeric_value", ""))}
        </div>
    </div>
    """, unsafe_allow_html=True)

    versions_show = versions_df.rename(columns={
        "version_number": "Версія",
        "created_at": "Дата створення версії",
        "created_by": "Ким створено",
        "approval_status": "Статус погодження",
        "status": "Статус виконання",
        "numeric_value": "Фактичне значення",
        "progress_text": "Опис прогресу",
        "risks": "Ризики / проблеми",
        "file_names": "Файли"
    })

    cols = [
        "Версія",
        "Дата створення версії",
        "Ким створено",
        "Статус погодження",
        "Статус виконання",
        "Фактичне значення",
        "Опис прогресу",
        "Ризики / проблеми",
        "Файли"
    ]

    available = [c for c in cols if c in versions_show.columns]

    st.dataframe(
        versions_show[available],
        use_container_width=True,
        hide_index=True
    )

st.markdown('</div>', unsafe_allow_html=True)

if approval == "Повернуто на доопрацювання":
    st.markdown('<div class="card"><div class="card-title">Редагування та повторне подання</div><div class="card-subtitle">Цей блок доступний тільки для заявок, повернутих на доопрацювання.</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="step-box">
        1. Перегляньте коментар адміністратора.<br>
        2. Виправте фактичне значення, опис прогресу або ризики.<br>
        3. За потреби додайте нові підтвердні файли.<br>
        4. Після повторного подання система збереже стару і нову версію заявки.<br>
        5. Натисніть «Повторно подати на погодження».
    </div>
    """, unsafe_allow_html=True)

    status_options = [
        "Не розпочато",
        "Виконується",
        "Виконано",
        "Виконано частково",
        "Прострочено",
        "Потребує уваги"
    ]

    current_status = clean(selected_row["status"])
    default_status_index = status_options.index(current_status) if current_status in status_options else 1

    new_status = st.selectbox(
        "Статус виконання",
        status_options,
        index=default_status_index,
        key=f"edit_status_{selected_id}"
    )

    new_value = st.text_input(
        "Фактичне значення",
        value=clean(selected_row["numeric_value"]),
        key=f"edit_value_{selected_id}"
    )

    new_progress = st.text_area(
        "Опис прогресу",
        value=clean(selected_row["progress_text"]),
        height=140,
        key=f"edit_progress_{selected_id}"
    )

    new_risks = st.text_area(
        "Ризики / проблеми / відхилення",
        value=clean(selected_row["risks"]),
        height=140,
        key=f"edit_risks_{selected_id}"
    )

    e1, e2, e3 = st.columns(3)

    with e1:
        new_responsible = st.text_input(
            "ПІБ відповідальної особи",
            value=clean(selected_row["responsible_person"]),
            key=f"edit_responsible_{selected_id}"
        )

    with e2:
        new_phone = st.text_input(
            "Телефон",
            value=clean(selected_row["phone"]),
            key=f"edit_phone_{selected_id}"
        )

    with e3:
        new_email = st.text_input(
            "Email",
            value=clean(selected_row["email"]),
            key=f"edit_email_{selected_id}"
        )

    new_files = st.file_uploader(
        "Додати нові підтвердні файли",
        accept_multiple_files=True,
        key=f"edit_files_{selected_id}"
    )

    st.markdown("**Перед повторним поданням система перевірить:**")
    st.write("- фактичне значення;")
    st.write("- опис прогресу;")
    st.write("- ПІБ, телефон, email;")
    st.write("- коректність email;")
    st.write("- логічну відповідність статусу і фактичного значення;")
    st.write("- підтвердні файли, якщо статус «Виконано».")

    resubmit = st.button(
        "Повторно подати на погодження",
        use_container_width=True,
        key=f"resubmit_{selected_id}"
    )

    if resubmit:
        errors = []

        if not has_value(new_value):
            errors.append("Заповніть фактичне значення.")

        if not has_value(new_progress):
            errors.append("Заповніть опис прогресу.")

        if not has_value(new_responsible):
            errors.append("Заповніть ПІБ відповідальної особи.")

        if not has_value(new_phone):
            errors.append("Заповніть телефон.")

        if not has_value(new_email):
            errors.append("Заповніть email.")
        elif not valid_email(new_email):
            errors.append("Email має некоректний формат.")

        normalize_value = str(new_value).strip().lower()

        if new_status == "Виконано" and normalize_value in ["0", "ні", "нi", "no"]:
            errors.append("Статус «Виконано» не узгоджується з фактичним значенням 0 / ні.")

        if new_status == "Виконано" and not new_files and not has_value(selected_row["file_urls"]):
            errors.append("Для статусу «Виконано» бажано додати підтвердний файл.")

        if errors:
            st.error("Повторне подання не виконано:")
            for e in errors:
                st.error(e)
            st.stop()

        added_names = ""
        added_urls = ""

        if new_files:
            try:
                added_names, added_urls = upload_files(new_files, code)
            except Exception as e:
                st.error(f"Не вдалося завантажити файли: {e}")
                st.stop()

        old_file_names = clean(selected_row["file_names"])
        old_file_urls = clean(selected_row["file_urls"])

        combined_names = old_file_names
        combined_urls = old_file_urls

        if added_names:
            combined_names = ", ".join([x for x in [old_file_names, added_names] if x])
            combined_urls = ", ".join([x for x in [old_file_urls, added_urls] if x])

        try:
            old_version_data = selected_row.to_dict()
            old_version_number = save_request_version(
                selected_id,
                old_version_data,
                created_by="Департамент / до редагування"
            )

            update_payload = {
                "status": new_status,
                "numeric_value": new_value,
                "progress_text": new_progress,
                "risks": new_risks,
                "responsible_person": new_responsible,
                "phone": new_phone,
                "email": new_email,
                "file_names": combined_names,
                "file_urls": combined_urls,
                "approval_status": "Очікує погодження",
                "submitted_at": datetime.now().isoformat(),
                "admin_comment": ""
            }

            supabase.table("monitoring_requests").update(update_payload).eq("id", int(selected_id)).execute()

            new_version_data = selected_row.to_dict()
            new_version_data.update(update_payload)

            new_version_number = save_request_version(
                selected_id,
                new_version_data,
                created_by="Департамент / повторне подання"
            )

            write_log(
                selected_id,
                f"Повторне подання після доопрацювання: версія {old_version_number} → {new_version_number}",
                "Повернуто на доопрацювання",
                "Очікує погодження",
                "Заявку повторно подано департаментом"
            )

            st.success("Заявку повторно подано на погодження. Попередню і нову версію збережено.")
            st.rerun()

        except Exception as e:
            st.error("Не вдалося повторно подати заявку.")
            st.exception(e)

    st.markdown('</div>', unsafe_allow_html=True)

else:
    st.markdown('<div class="card"><div class="card-title">Редагування недоступне</div>', unsafe_allow_html=True)

    if approval == "Погоджено":
        st.success("Заявку погоджено. Редагування недоступне.")
    elif approval == "Очікує погодження":
        st.info("Заявка очікує погодження. Редагування буде доступне, якщо адміністратор поверне її на доопрацювання.")
    else:
        st.info("Редагування для цього статусу недоступне.")

    st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="footer">
        Міністерство економіки, довкілля та сільського господарства України<br>
        Розроблено департаментом стратегічного планування та макроекономічного прогнозування<br>
        Версія DEMO 1.1 | Кабінет департаменту з версійністю заявок
    </div>
    """,
    unsafe_allow_html=True
)
