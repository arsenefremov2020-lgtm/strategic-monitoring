import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime, timezone

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

.header-box {
    background: rgba(255,255,255,0.94);
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 24px 28px;
    margin-bottom: 18px;
    box-shadow: 0 8px 24px rgba(15,23,42,0.06);
}

.header-title {
    font-size: 32px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 8px;
}

.header-subtitle {
    font-size: 15px;
    color: #475569;
    line-height: 1.55;
}

.status-pill-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 14px;
}

.status-pill {
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 999px;
    padding: 8px 12px;
    font-size: 13px;
    color: #334155;
}

.card {
    background: rgba(255,255,255,0.94);
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 20px 22px;
    margin: 18px 0;
    box-shadow: 0 6px 18px rgba(15,23,42,0.045);
}

.card-title {
    font-size: 20px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 8px;
}

.card-subtitle {
    color: #64748b;
    font-size: 14px;
    margin-bottom: 12px;
}

.flow-box {
    background: white;
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 16px 18px;
    margin: 18px 0;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

.flow-title {
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 10px;
}

.flow-steps {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    color: #334155;
    font-size: 14px;
}

.flow-step {
    padding: 8px 12px;
    border-radius: 999px;
    background: #f1f5f9;
    border: 1px solid #d8dee9;
}

.badge-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 10px 0 16px 0;
}

.badge {
    background: #eef6ff;
    border: 1px solid #bfdbfe;
    color: #1d4ed8;
    border-radius: 999px;
    padding: 7px 11px;
    font-size: 13px;
    font-weight: 700;
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

.review-box {
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 16px 18px;
    margin: 12px 0;
}

.review-title {
    font-size: 16px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 8px;
}

.admin-kpi-card {
    background: rgba(255,255,255,0.96);
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    min-height: 102px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.045);
}

.admin-kpi-label {
    color: #475569;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 8px;
}

.admin-kpi-value {
    color: #0f172a;
    font-size: 24px;
    font-weight: 850;
    line-height: 1.15;
    white-space: normal;
    overflow-wrap: anywhere;
    word-break: break-word;
}

.quality-card {
    background: rgba(255,255,255,0.96);
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 14px 16px;
    min-height: 104px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.045);
}

.quality-good {
    border-left: 5px solid #22c55e;
}

.quality-warn {
    border-left: 5px solid #f59e0b;
}

.quality-label {
    color: #475569;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 8px;
}

.quality-value {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    color: #0f172a;
    font-size: 18px;
    font-weight: 850;
    line-height: 1.18;
    white-space: normal;
    overflow-wrap: anywhere;
    word-break: break-word;
}

.quality-icon {
    flex: 0 0 auto;
}

.attention-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
    margin-top: 12px;
}

.attention-card {
    border-radius: 14px;
    padding: 14px 15px;
    min-height: 100px;
    border: 1px solid #d8dee9;
    box-shadow: 0 4px 12px rgba(15,23,42,0.045);
}

.attention-title {
    color: #475569;
    font-size: 12px;
    font-weight: 800;
    margin-bottom: 8px;
}

.attention-value {
    color: #0f172a;
    font-size: 26px;
    font-weight: 950;
    line-height: 1.1;
}

.attention-note {
    color: #64748b;
    font-size: 12px;
    margin-top: 5px;
    line-height: 1.25;
}

.att-red {
    background: #fee2e2;
    border-color: #fecaca;
}

.att-yellow {
    background: #fef9c3;
    border-color: #fde68a;
}

.att-blue {
    background: #dbeafe;
    border-color: #bfdbfe;
}

.att-green {
    background: #dcfce7;
    border-color: #bbf7d0;
}

.resolution-box {
    background: #ffffff;
    border: 1px solid #d8dee9;
    border-left: 7px solid #2563eb;
    border-radius: 14px;
    padding: 16px 18px;
    margin: 12px 0;
}

.resolution-title {
    font-size: 17px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 8px;
}

.resolution-text {
    color: #334155;
    font-size: 14px;
    line-height: 1.6;
}

.decision-box {
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 14px;
    padding: 16px 18px;
    margin: 12px 0;
}

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.88);
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

div[data-testid="stFormSubmitButton"] button {
    border-radius: 12px;
    padding: 12px 18px;
    font-weight: 900;
    background: #2563eb;
    color: white;
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


def to_datetime(value):
    text = clean(value).strip()

    if not text:
        return None

    try:
        dt = pd.to_datetime(text, errors="coerce", utc=True)
        if pd.isna(dt):
            return None
        return dt.to_pydatetime()
    except Exception:
        return None


def days_waiting(value):
    dt = to_datetime(value)
    if not dt:
        return None

    now = datetime.now(timezone.utc)
    return (now - dt).days


def admin_kpi_card(label, value):
    value = "" if value is None else str(value)

    st.markdown(
        f"""
        <div class="admin-kpi-card">
            <div class="admin-kpi-label">{label}</div>
            <div class="admin-kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def quality_card(label, status, good=True):
    icon = "✅" if good else "⚠️"
    css_class = "quality-good" if good else "quality-warn"

    st.markdown(
        f"""
        <div class="quality-card {css_class}">
            <div class="quality-label">{label}</div>
            <div class="quality-value">
                <span class="quality-icon">{icon}</span>
                <span>{status}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def attention_card(title, value, note, css_class):
    st.markdown(
        f"""
        <div class="attention-card {css_class}">
            <div class="attention-title">{title}</div>
            <div class="attention-value">{value}</div>
            <div class="attention-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


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


def load_logs(request_id):
    response = (
        supabase
        .table("monitoring_logs")
        .select("*")
        .eq("request_id", int(request_id))
        .order("changed_at", desc=True)
        .execute()
    )

    if not response.data:
        return pd.DataFrame()

    return pd.DataFrame(response.data)


def write_log(request_id, action, old_status, new_status, admin_comment):
    supabase.table("monitoring_logs").insert({
        "request_id": int(request_id),
        "action": action,
        "old_status": old_status,
        "new_status": new_status,
        "admin_comment": admin_comment,
        "changed_by": "Адміністратор"
    }).execute()


def quality_assessment(row):
    checks = []
    score = 0

    if has_value(row.get("numeric_value", "")):
        checks.append(("Фактичне значення", "Заповнено", True))
        score += 1
    else:
        checks.append(("Фактичне значення", "Не заповнено", False))

    if has_value(row.get("progress_text", "")):
        checks.append(("Опис прогресу", "Заповнено", True))
        score += 1
    else:
        checks.append(("Опис прогресу", "Не заповнено", False))

    if has_value(row.get("file_urls", "")):
        checks.append(("Підтвердні файли", "Додано", True))
        score += 1
    else:
        checks.append(("Підтвердні файли", "Не додано", False))

    if has_value(row.get("responsible_person", "")):
        checks.append(("Відповідальна особа", "Заповнено", True))
        score += 1
    else:
        checks.append(("Відповідальна особа", "Не заповнено", False))

    if has_value(row.get("phone", "")):
        checks.append(("Телефон", "Заповнено", True))
        score += 1
    else:
        checks.append(("Телефон", "Не заповнено", False))

    if has_value(row.get("email", "")):
        checks.append(("Email", "Заповнено", True))
        score += 1
    else:
        checks.append(("Email", "Не заповнено", False))

    if has_value(row.get("risks", "")):
        checks.append(("Ризики", "Є запис", False))
    else:
        checks.append(("Ризики", "Не зазначено", True))

    if score >= 5 and not has_value(row.get("risks", "")):
        recommendation = "Можна погоджувати"
        badge = "badge-green"
    elif score >= 4:
        recommendation = "Потребує перевірки"
        badge = "badge-yellow"
    else:
        recommendation = "Краще повернути на доопрацювання"
        badge = "badge-red"

    return checks, recommendation, badge, score


def generate_resolution(row, recommendation, quality_score):
    request_id = clean(row.get("id", ""))
    code = clean(row.get("strat_code", ""))
    year = clean(row.get("year", ""))
    quarter = clean(row.get("quarter", ""))
    department = clean(row.get("department", ""))
    status = clean(row.get("status", ""))
    fact = clean(row.get("numeric_value", ""))
    progress = clean(row.get("progress_text", ""))
    risks = clean(row.get("risks", ""))
    files = clean(row.get("file_urls", ""))
    person = clean(row.get("responsible_person", ""))

    missing = []

    if not has_value(fact):
        missing.append("фактичне значення")
    if not has_value(progress):
        missing.append("опис прогресу")
    if not has_value(files):
        missing.append("підтвердні файли")
    if not has_value(row.get("email", "")):
        missing.append("електронна пошта")
    if not has_value(row.get("phone", "")):
        missing.append("контактний телефон")

    if recommendation == "Можна погоджувати":
        return (
            f"За результатами розгляду заявки ID {request_id} щодо заходу {code} "
            f"за {quarter} квартал {year} року, поданої підрозділом «{department}», "
            f"моніторингові дані можуть бути погоджені. Заявка містить фактичне значення "
            f"«{fact}», статус виконання «{status}», опис прогресу, контактні дані відповідальної особи "
            f"({person}) та підтвердні матеріали. Ознак критичної неповноти даних системою не виявлено."
        )

    if recommendation == "Потребує перевірки":
        details = []

        if risks:
            details.append("у заявці зазначено ризики / проблеми / відхилення")
        if missing:
            details.append("потребують перевірки такі елементи: " + ", ".join(missing))

        detail_text = "; ".join(details) if details else "окремі елементи заявки потребують додаткової перевірки"

        return (
            f"За результатами попереднього аналізу заявки ID {request_id} щодо заходу {code} "
            f"за {quarter} квартал {year} року, поданої підрозділом «{department}», "
            f"заявка потребує додаткової перевірки перед прийняттям остаточного рішення. "
            f"Система визначила, що {detail_text}. Рекомендовано перевірити зміст поданого фактичного значення, "
            f"опис прогресу та наявність достатнього документального підтвердження."
        )

    missing_text = ", ".join(missing) if missing else "ключові елементи заявки заповнені неповністю"

    return (
        f"Заявку ID {request_id} щодо заходу {code} за {quarter} квартал {year} року, "
        f"подану підрозділом «{department}», доцільно повернути на доопрацювання. "
        f"Підстава: {missing_text}. До повторного подання необхідно уточнити фактичне значення, "
        f"доповнити опис прогресу та/або додати підтвердні матеріали відповідно до вимог моніторингу."
    )


def build_attention_summary(df):
    data = df.copy()

    if data.empty:
        return {
            "long_waiting": pd.DataFrame(),
            "without_files": pd.DataFrame(),
            "with_risks": pd.DataFrame(),
            "returned": pd.DataFrame(),
            "approved_without_fact": pd.DataFrame(),
            "duplicates": pd.DataFrame()
        }

    data["days_waiting"] = data["submitted_at"].apply(days_waiting)

    long_waiting = data[
        (data["approval_status"].astype(str) == "Очікує погодження") &
        (data["days_waiting"].fillna(0) >= 7)
    ].copy()

    without_files = data[
        data["file_urls"].fillna("").astype(str).str.strip() == ""
    ].copy()

    with_risks = data[
        data["risks"].fillna("").astype(str).str.strip() != ""
    ].copy()

    returned = data[
        data["approval_status"].astype(str) == "Повернуто на доопрацювання"
    ].copy()

    approved_without_fact = data[
        (data["approval_status"].astype(str) == "Погоджено") &
        (data["numeric_value"].fillna("").astype(str).str.strip() == "")
    ].copy()

    duplicate_keys = ["year", "quarter", "department", "strat_code"]

    duplicate_groups = (
        data
        .groupby(duplicate_keys, dropna=False)
        .size()
        .reset_index(name="count")
    )

    duplicate_groups = duplicate_groups[duplicate_groups["count"] > 1]

    if not duplicate_groups.empty:
        duplicates = data.merge(
            duplicate_groups[duplicate_keys],
            on=duplicate_keys,
            how="inner"
        ).copy()
    else:
        duplicates = pd.DataFrame()

    return {
        "long_waiting": long_waiting,
        "without_files": without_files,
        "with_risks": with_risks,
        "returned": returned,
        "approved_without_fact": approved_without_fact,
        "duplicates": duplicates
    }


st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="ministry-label">
    🇺🇦 Міністерство економіки, довкілля та сільського господарства України
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="header-box">
        <div class="header-title">Адміністрування заявок моніторингу</div>
        <div class="header-subtitle">
            Робочий кабінет адміністратора для перевірки поданих даних, перегляду підтвердних файлів,
            погодження заявок, повернення на доопрацювання та контролю історії змін.
        </div>
        <div class="status-pill-wrap">
            <div class="status-pill">● Режим: адміністрування</div>
            <div class="status-pill">● Дані: Supabase</div>
            <div class="status-pill">● Журнал змін: активний</div>
            <div class="status-pill">● Резолюція: автоматична</div>
            <div class="status-pill">● Оновлено: {datetime.now().strftime("%d.%m.%Y %H:%M")}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="flow-box">
        <div class="flow-title">Маршрут рішення адміністратора</div>
        <div class="flow-steps">
            <div class="flow-step">1. Відфільтрувати заявки</div>
            <div class="flow-step">2. Переглянути захід</div>
            <div class="flow-step">3. Перевірити факт і файли</div>
            <div class="flow-step">4. Переглянути системну резолюцію</div>
            <div class="flow-step">5. Обрати рішення</div>
            <div class="flow-step">6. Натиснути одну кнопку підтвердження</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

df = load_requests()
strat_df = load_strat_matrix()

if df.empty:
    st.warning("Поки що немає поданих заявок.")
    st.stop()

required_cols = [
    "id",
    "department",
    "year",
    "quarter",
    "approval_status",
    "status",
    "strat_code",
    "responsible_person",
    "phone",
    "email",
    "numeric_value",
    "progress_text",
    "risks",
    "file_names",
    "file_urls",
    "admin_comment",
    "start_date",
    "end_date",
    "submitted_at"
]

for col in required_cols:
    if col not in df.columns:
        df[col] = ""

attention = build_attention_summary(df)

st.markdown(
    '<div class="card"><div class="card-title">Потребує уваги</div><div class="card-subtitle">Автоматичні попередження для адміністратора за всіма заявками.</div>',
    unsafe_allow_html=True
)

st.markdown('<div class="attention-grid">', unsafe_allow_html=True)

attention_card(
    "Очікують понад 7 днів",
    len(attention["long_waiting"]),
    "Заявки довго перебувають без рішення.",
    "att-red" if len(attention["long_waiting"]) else "att-green"
)

attention_card(
    "Без файлів",
    len(attention["without_files"]),
    "Заявки без підтвердних матеріалів.",
    "att-yellow" if len(attention["without_files"]) else "att-green"
)

attention_card(
    "Із ризиками",
    len(attention["with_risks"]),
    "У заявках зазначено ризики або відхилення.",
    "att-yellow" if len(attention["with_risks"]) else "att-green"
)

attention_card(
    "Повернуто",
    len(attention["returned"]),
    "Потребують доопрацювання департаментом.",
    "att-blue" if len(attention["returned"]) else "att-green"
)

attention_card(
    "Погоджено без факту",
    len(attention["approved_without_fact"]),
    "Погоджені записи без фактичного значення.",
    "att-red" if len(attention["approved_without_fact"]) else "att-green"
)

attention_card(
    "Дублікати",
    len(attention["duplicates"]),
    "Кілька заявок по одному заходу/кварталу.",
    "att-red" if len(attention["duplicates"]) else "att-green"
)

st.markdown('</div>', unsafe_allow_html=True)

with st.expander("Переглянути записи, які потребують уваги"):
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Очікують понад 7 днів",
        "Без файлів",
        "Із ризиками",
        "Повернуті",
        "Погоджено без факту",
        "Дублікати"
    ])

    with tab1:
        st.dataframe(attention["long_waiting"], use_container_width=True, hide_index=True)

    with tab2:
        st.dataframe(attention["without_files"], use_container_width=True, hide_index=True)

    with tab3:
        st.dataframe(attention["with_risks"], use_container_width=True, hide_index=True)

    with tab4:
        st.dataframe(attention["returned"], use_container_width=True, hide_index=True)

    with tab5:
        st.dataframe(attention["approved_without_fact"], use_container_width=True, hide_index=True)

    with tab6:
        st.dataframe(attention["duplicates"], use_container_width=True, hide_index=True)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="card"><div class="card-title">Огляд заявок</div><div class="card-subtitle">Короткий стан черги адміністрування.</div>',
    unsafe_allow_html=True
)

total_requests = len(df)
waiting_count = len(df[df["approval_status"] == "Очікує погодження"])
approved_count = len(df[df["approval_status"] == "Погоджено"])
returned_count = len(df[df["approval_status"] == "Повернуто на доопрацювання"])
with_files_count = len(df[df["file_urls"].fillna("").astype(str).str.strip() != ""])
with_risks_count = len(df[df["risks"].fillna("").astype(str).str.strip() != ""])

m1, m2, m3, m4, m5, m6 = st.columns(6)

m1.metric("Усього", total_requests)
m2.metric("Очікують", waiting_count)
m3.metric("Погоджено", approved_count)
m4.metric("Повернуто", returned_count)
m5.metric("Із файлами", with_files_count)
m6.metric("Із ризиками", with_risks_count)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Міні-візуалізація статусів</div>', unsafe_allow_html=True)

chart_df = (
    df["approval_status"]
    .fillna("Невідомо")
    .value_counts()
    .reset_index()
)

chart_df.columns = ["Статус", "Кількість"]

fig = px.pie(
    chart_df,
    names="Статус",
    values="Кількість",
    hole=0.5,
    title="Розподіл заявок за статусом погодження"
)

st.plotly_chart(fig, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Фільтри та пошук</div>', unsafe_allow_html=True)

f1, f2, f3, f4 = st.columns(4)

with f1:
    departments = sorted(df["department"].dropna().astype(str).unique().tolist())
    selected_department = st.selectbox("Департамент", ["Усі"] + departments)

with f2:
    years = sorted(df["year"].dropna().astype(str).unique().tolist())
    selected_year = st.selectbox("Рік", ["Усі"] + years)

with f3:
    quarters = sorted(df["quarter"].dropna().astype(str).unique().tolist())
    selected_quarter = st.selectbox("Квартал", ["Усі"] + quarters)

with f4:
    selected_approval_status = st.selectbox(
        "Статус погодження",
        [
            "Активні до розгляду",
            "Усі",
            "Очікує погодження",
            "Повернуто на доопрацювання",
            "Погоджено"
        ],
        index=0
    )

q1, q2 = st.columns([1, 2])

with q1:
    quick_filter = st.selectbox(
        "Швидкий фільтр",
        [
            "Усі заявки",
            "Тільки очікують",
            "Повернуті",
            "Без файлів",
            "Із ризиками",
            "Останні подані",
            "Очікують понад 7 днів",
            "Дублікати"
        ]
    )

with q2:
    search_query = st.text_input(
        "Пошук за ID, кодом заходу, ПІБ або департаментом"
    )

filtered = df.copy()

if selected_department != "Усі":
    filtered = filtered[
        filtered["department"].astype(str) == str(selected_department)
    ]

if selected_year != "Усі":
    filtered = filtered[
        filtered["year"].astype(str) == str(selected_year)
    ]

if selected_quarter != "Усі":
    filtered = filtered[
        filtered["quarter"].astype(str) == str(selected_quarter)
    ]

if selected_approval_status == "Активні до розгляду":
    filtered = filtered[
        filtered["approval_status"].astype(str).isin([
            "Очікує погодження",
            "Повернуто на доопрацювання"
        ])
    ]

elif selected_approval_status != "Усі":
    filtered = filtered[
        filtered["approval_status"].astype(str) == str(selected_approval_status)
    ]

if quick_filter == "Тільки очікують":
    filtered = filtered[filtered["approval_status"] == "Очікує погодження"]

elif quick_filter == "Повернуті":
    filtered = filtered[filtered["approval_status"] == "Повернуто на доопрацювання"]

elif quick_filter == "Без файлів":
    filtered = filtered[filtered["file_urls"].fillna("").astype(str).str.strip() == ""]

elif quick_filter == "Із ризиками":
    filtered = filtered[filtered["risks"].fillna("").astype(str).str.strip() != ""]

elif quick_filter == "Останні подані":
    filtered = filtered.sort_values("submitted_at", ascending=False).head(10)

elif quick_filter == "Очікують понад 7 днів":
    filtered = attention["long_waiting"].copy()

elif quick_filter == "Дублікати":
    filtered = attention["duplicates"].copy()

if search_query.strip():
    sq = search_query.strip().lower()

    filtered = filtered[
        filtered["id"].astype(str).str.lower().str.contains(sq, na=False)
        |
        filtered["strat_code"].astype(str).str.lower().str.contains(sq, na=False)
        |
        filtered["responsible_person"].astype(str).str.lower().str.contains(sq, na=False)
        |
        filtered["department"].astype(str).str.lower().str.contains(sq, na=False)
    ]

st.caption(f"Знайдено заявок: {len(filtered)}")

st.markdown('</div>', unsafe_allow_html=True)

if filtered.empty:
    st.info("За обраними фільтрами заявок не знайдено.")
    st.stop()

queue_df = filtered[
    filtered["approval_status"] == "Очікує погодження"
].copy()

if not queue_df.empty:
    st.markdown(
        '<div class="card"><div class="card-title">Черга на розгляд</div><div class="card-subtitle">Заявки, які потребують рішення адміністратора.</div>',
        unsafe_allow_html=True
    )

    queue_show = queue_df.rename(columns={
        "id": "ID",
        "department": "Департамент",
        "year": "Рік",
        "quarter": "Квартал",
        "strat_code": "Код заходу",
        "responsible_person": "Відповідальна особа",
        "submitted_at": "Дата подання"
    })

    st.dataframe(
        queue_show[
            [
                "ID",
                "Департамент",
                "Код заходу",
                "Рік",
                "Квартал",
                "Відповідальна особа",
                "Дата подання"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Вибір заявки</div>', unsafe_allow_html=True)

selected_options = []

for _, row in filtered.iterrows():
    option = (
        f"ID {row['id']} | "
        f"{row['department']} | "
        f"{row['strat_code']} | "
        f"{row['year']} {row['quarter']} квартал | "
        f"{row['approval_status']} | "
        f"{clean(row['submitted_at'])}"
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

st.markdown('</div>', unsafe_allow_html=True)

approval_status = clean(selected_row["approval_status"])
selected_code = clean(selected_row["strat_code"])

checks, recommendation, rec_badge, quality_score = quality_assessment(selected_row)
auto_resolution = generate_resolution(selected_row, recommendation, quality_score)

st.markdown('<div class="card"><div class="card-title">Картка заявки</div>', unsafe_allow_html=True)

if approval_status == "Погоджено":
    status_badge = "badge-green"
elif approval_status == "Повернуто на доопрацювання":
    status_badge = "badge-red"
else:
    status_badge = "badge-yellow"

st.markdown(
    f"""
    <div class="badge-wrap">
        <div class="badge {status_badge}">Статус погодження: {approval_status}</div>
        <div class="badge">Заявка ID {clean(selected_row['id'])}</div>
        <div class="badge">Захід {selected_code}</div>
        <div class="badge {rec_badge}">Рекомендація: {recommendation}</div>
    </div>
    """,
    unsafe_allow_html=True
)

k1, k2, k3, k4, k5, k6 = st.columns(6)

with k1:
    admin_kpi_card("Департамент", clean(selected_row.get("department", "")))

with k2:
    admin_kpi_card("Рік", clean(selected_row.get("year", "")))

with k3:
    admin_kpi_card("Квартал", clean(selected_row.get("quarter", "")))

with k4:
    admin_kpi_card("Статус виконання", clean(selected_row.get("status", "")))

with k5:
    admin_kpi_card("Факт", clean(selected_row.get("numeric_value", "")))

with k6:
    admin_kpi_card("Код", clean(selected_row.get("strat_code", "")))

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Автоматична оцінка якості заявки</div>', unsafe_allow_html=True)

qcols = st.columns(len(checks))

for idx, item in enumerate(checks):
    label, value, ok = item
    with qcols[idx]:
        quality_card(label, value, ok)

st.progress(
    min(quality_score / 6, 1.0),
    text=f"Заповненість ключових полів: {round(quality_score / 6 * 100, 1)}%"
)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="card"><div class="card-title">Автоматична службова резолюція</div><div class="card-subtitle">Система формує текст на основі якості заявки, статусу, фактичного значення, файлів і ризиків.</div>',
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="resolution-box">
        <div class="resolution-title">Проєкт резолюції</div>
        <div class="resolution-text">{auto_resolution}</div>
    </div>
    """,
    unsafe_allow_html=True
)

st.text_area(
    "Текст резолюції для копіювання",
    value=auto_resolution,
    height=160,
    key=f"auto_resolution_text_{selected_id}",
    disabled=True
)

use_auto_resolution = st.checkbox(
    "Використати цей текст як коментар адміністратора",
    value=False,
    key=f"use_auto_resolution_{selected_id}"
)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Інформація про захід зі стратегічного плану</div>', unsafe_allow_html=True)

measure_info = strat_df[
    strat_df["code"].astype(str).str.strip() == selected_code
].copy()

if measure_info.empty:
    st.warning("Захід не знайдено у стратегічній матриці.")
else:
    short_info = measure_info.iloc[0]

    st.markdown(
        f"""
        <div class="review-box">
            <div class="review-title">{clean(short_info.get("code", ""))} — {clean(short_info.get("name", ""))}</div>
            <div><b>Індикатор:</b> {clean(short_info.get("indicator", ""))}</div>
            <div><b>Одиниця виміру:</b> {clean(short_info.get("unit", ""))}</div>
            <div><b>Період виконання:</b> {clean(short_info.get("start_date_plan", ""))} — {clean(short_info.get("end_date_plan", ""))}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.expander("Детальна таблиця заходу"):
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

        detail_cols = [
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

        available_detail_cols = [c for c in detail_cols if c in measure_info.columns]

        st.dataframe(
            measure_info[available_detail_cols],
            use_container_width=True,
            hide_index=True
        )

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Дані відповідальної особи</div>', unsafe_allow_html=True)

p1, p2, p3 = st.columns(3)

with p1:
    st.text_input(
        "ПІБ відповідальної особи",
        value=clean(selected_row["responsible_person"]),
        disabled=True,
        key=f"responsible_{selected_id}"
    )

with p2:
    st.text_input(
        "Контактний номер телефону",
        value=clean(selected_row["phone"]),
        disabled=True,
        key=f"phone_{selected_id}"
    )

with p3:
    st.text_input(
        "Електронна пошта",
        value=clean(selected_row["email"]),
        disabled=True,
        key=f"email_{selected_id}"
    )

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Терміни виконання</div>', unsafe_allow_html=True)

d1, d2 = st.columns(2)

with d1:
    st.text_input(
        "Початкова дата виконання",
        value=clean(selected_row["start_date"]),
        disabled=True,
        key=f"start_{selected_id}"
    )

with d2:
    st.text_input(
        "Кінцева дата виконання",
        value=clean(selected_row["end_date"]),
        disabled=True,
        key=f"end_{selected_id}"
    )

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Опис прогресу та ризики</div>', unsafe_allow_html=True)

t1, t2 = st.columns(2)

with t1:
    st.text_area(
        "Опис прогресу",
        value=clean(selected_row["progress_text"]),
        disabled=True,
        height=150,
        key=f"progress_{selected_id}"
    )

with t2:
    st.text_area(
        "Ризики / проблеми / відхилення",
        value=clean(selected_row["risks"]),
        disabled=True,
        height=150,
        key=f"risks_{selected_id}"
    )

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Підтвердні файли</div>', unsafe_allow_html=True)

file_names = clean(selected_row["file_names"])
file_urls = clean(selected_row["file_urls"])

if not file_urls:
    st.warning("Файлів до заявки не додано.")
else:
    urls = [u.strip() for u in file_urls.split(",") if u.strip()]
    names = [n.strip() for n in file_names.split(",") if n.strip()]

    st.caption(f"Додано файлів: {len(urls)}")

    for i, url in enumerate(urls):
        label = names[i] if i < len(names) else f"Файл {i + 1}"
        st.markdown(f"[{label}]({url})")

st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="card"><div class="card-title">Рішення адміністратора</div><div class="card-subtitle">Оберіть рішення та підтвердьте його однією кнопкою. Це прибирає ризик випадкового спрацювання не тієї дії.</div>',
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="badge-wrap">
        <div class="badge {rec_badge}">Системна рекомендація: {recommendation}</div>
        <div class="badge">Заповненість: {round(quality_score / 6 * 100, 1)}%</div>
        <div class="badge {status_badge}">Поточний статус: {approval_status}</div>
    </div>
    """,
    unsafe_allow_html=True
)

default_comment = auto_resolution if use_auto_resolution else clean(selected_row["admin_comment"])

with st.form(key=f"admin_decision_form_{selected_id}"):
    decision = st.radio(
        "Оберіть рішення",
        [
            "Погодити",
            "Повернути на доопрацювання",
            "Залишити в очікуванні"
        ],
        horizontal=True,
        key=f"decision_radio_{selected_id}"
    )

    st.markdown(
        f"""
        <div class="decision-box">
            <b>Буде застосовано рішення:</b> {decision}
        </div>
        """,
        unsafe_allow_html=True
    )

    admin_comment = st.text_area(
        "Коментар адміністратора",
        value=default_comment,
        height=150,
        key=f"admin_comment_form_{selected_id}_{use_auto_resolution}"
    )

    confirm_decision = st.form_submit_button(
        "Застосувати рішення",
        use_container_width=True
    )

if confirm_decision:
    if decision == "Погодити":
        new_status = "Погоджено"
        action_text = "Погодження заявки"
        success_text = "Заявку погоджено."

    elif decision == "Повернути на доопрацювання":
        new_status = "Повернуто на доопрацювання"
        action_text = "Повернення заявки на доопрацювання"
        success_text = "Заявку повернуто на доопрацювання."

    else:
        new_status = "Очікує погодження"
        action_text = "Заявку залишено в очікуванні"
        success_text = "Заявку залишено в очікуванні."

    try:
        supabase.table("monitoring_requests").update({
            "approval_status": new_status,
            "admin_comment": admin_comment
        }).eq("id", int(selected_id)).execute()

        write_log(
            selected_id,
            action_text,
            approval_status,
            new_status,
            admin_comment
        )

        st.success(success_text)
        st.rerun()

    except Exception as e:
        st.error("Не вдалося застосувати рішення.")
        st.exception(e)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Остання дія та історія змін</div>', unsafe_allow_html=True)

logs_df = load_logs(selected_id)

if logs_df.empty:
    st.info("Історії змін для цієї заявки поки що немає.")
else:
    latest_log = logs_df.iloc[0]

    st.markdown(
        f"""
        <div class="review-box">
            <div class="review-title">Остання дія: {clean(latest_log.get("action", ""))}</div>
            <div><b>Статус:</b> {clean(latest_log.get("old_status", ""))} → {clean(latest_log.get("new_status", ""))}</div>
            <div><b>Коментар:</b> {clean(latest_log.get("admin_comment", ""))}</div>
            <div><b>Дата:</b> {clean(latest_log.get("changed_at", ""))}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.expander("Повна історія змін заявки"):
        show_logs = logs_df.rename(columns={
            "changed_at": "Дата зміни",
            "action": "Дія",
            "old_status": "Попередній статус",
            "new_status": "Новий статус",
            "admin_comment": "Коментар адміністратора",
            "changed_by": "Ким змінено"
        })

        show_cols = [
            "Дата зміни",
            "Дія",
            "Попередній статус",
            "Новий статус",
            "Коментар адміністратора",
            "Ким змінено"
        ]

        available_log_cols = [col for col in show_cols if col in show_logs.columns]

        st.dataframe(
            show_logs[available_log_cols],
            use_container_width=True,
            hide_index=True
        )

st.markdown('</div>', unsafe_allow_html=True)

with st.expander("Технічна таблиця заявок"):
    st.dataframe(
        filtered,
        use_container_width=True,
        hide_index=True
    )

st.markdown(
    """
    <div class="footer">
        Розроблено департаментом стратегічного планування та макроекономічного прогнозування<br>
        Версія DEMO 1.3 | Кабінет адміністрування заявок моніторингу
    </div>
    """,
    unsafe_allow_html=True
)
