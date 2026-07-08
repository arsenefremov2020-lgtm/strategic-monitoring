import streamlit as st
import pandas as pd
from core.db import get_supabase_client
from core.ui import load_css
from datetime import datetime, date, timedelta
from io import BytesIO
import re
from core.page_setup import page_setup, render_footer
from config.users import get_active_users
from config.roles import ROLE_ADMIN, ROLE_SSP, ROLE_SSP_HEAD
from core.access import normalize_ssp_index
from core import exports as core_exports

page_setup("Журнал дій", page_name="Журнал дій")
supabase = get_supabase_client()
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

.parameter-panel {
    background: linear-gradient(180deg, #eef6ff 0%, #f8fbff 100%);
    border: 1px solid #bfdbfe;
    border-radius: 16px;
    padding: 16px;
    margin-top: 14px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.75);
}

.parameter-box {
    background: #ffffff;
    border: 1px solid #bfdbfe;
    border-radius: 14px;
    padding: 12px 12px 8px 12px;
    min-height: 96px;
    box-shadow: 0 4px 14px rgba(37,99,235,0.06);
}

.parameter-label {
    color: #1e3a8a;
    font-size: 13px;
    font-weight: 950;
    margin-bottom: 6px;
}

/* Помітніші поля відбору */
div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stDateInput"] input,
div[data-testid="stTextInput"] input {
    background: #f8fbff !important;
    border: 1px solid #93c5fd !important;
    border-radius: 12px !important;
    box-shadow: 0 3px 10px rgba(37,99,235,0.08) !important;
}

div[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background: #2563eb !important;
    color: #ffffff !important;
    border-radius: 999px !important;
    font-weight: 850 !important;
}

div[data-testid="stDateInput"] input:focus,
div[data-testid="stTextInput"] input:focus {
    border-color: #1d4ed8 !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.15) !important;
}

.status-panel {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    border-radius: 16px;
    padding: 16px;
    margin-top: 10px;
}

.status-title {
    color: #9a3412;
    font-weight: 950;
    font-size: 16px;
    margin-bottom: 6px;
}

.small-note {
    color: #64748b;
    font-size: 13px;
    line-height: 1.55;
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
    output = BytesIO(core_exports.write_styled_excel(sheets))
    output.seek(0)
    return output


@st.cache_data(ttl=300)
def load_logs():
    response = (
        supabase
        .table("monitoring_logs")
        .select("*")
        .order("changed_at", desc=True)
        .execute()
    )
    return pd.DataFrame(response.data or [])


@st.cache_data(ttl=300)
def load_requests():
    response = (
        supabase
        .table("monitoring_requests")
        .select("*")
        .execute()
    )
    return pd.DataFrame(response.data or [])


@st.cache_data(ttl=300)
def load_versions():
    response = (
        supabase
        .table("monitoring_request_versions")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return pd.DataFrame(response.data or [])


def clean_text(value):
    if value is None or pd.isna(value):
        return ""

    text = str(value).strip()

    if text.lower() in ["nan", "none", "null"]:
        return ""

    return text


def get_assigned_admin_for_department(department_value):
    """
    Визначає відповідального адміністратора за ССП.

    Логіка:
    - беремо індекс із department, наприклад "деп. 30" -> "30";
    - шукаємо активного користувача з роллю ROLE_ADMIN;
    - якщо цей індекс є в allowed_ssp_indexes адміністратора — повертаємо його ПІБ і телефон.
    """

    department_index = normalize_ssp_index(department_value)

    if not department_index:
        return {
            "admin_name": "",
            "admin_phone": "",
        }

    active_users = get_active_users()
    matched_admins = []

    for _, user in active_users.items():
        if user.get("role") != ROLE_ADMIN:
            continue

        allowed_indexes = user.get("allowed_ssp_indexes", [])

        normalized_allowed_indexes = [
            normalize_ssp_index(index)
            for index in allowed_indexes
            if index != "*"
        ]

        if department_index in normalized_allowed_indexes:
            matched_admins.append({
                "name": clean_text(user.get("full_name")),
                "phone": clean_text(user.get("phone")),
            })

    if not matched_admins:
        return {
            "admin_name": "",
            "admin_phone": "",
        }

    return {
        "admin_name": "; ".join([item["name"] for item in matched_admins if item["name"]]),
        "admin_phone": "; ".join([item["phone"] for item in matched_admins if item["phone"]]),
    }


def resolve_changed_by_user(row):
    """
    Розкладає поле changed_by на:
    - роль;
    - ПІБ;
    - телефон.

    Логіка:
    - якщо changed_by = "Адміністратор" — шукаємо адміна, закріпленого за ССП заявки;
    - якщо changed_by = "Департамент" або "ССП" — беремо відповідальну особу від ССП із заявки;
    - якщо changed_by = "Керівник ССП" — шукаємо керівника ССП за індексом ССП;
    - якщо changed_by містить email або ПІБ — пробуємо знайти користувача в config/users.py.
    """

    raw_value = clean_text(row.get("changed_by"))
    department_value = row.get("department")
    department_index = normalize_ssp_index(department_value)

    if not raw_value:
        return {
            "changed_by_role": "",
            "changed_by_name": "",
            "changed_by_phone": "",
        }

    raw_lower = raw_value.lower()
    active_users = get_active_users()

    # 1. Адміністратор
    if "адміністратор" in raw_lower or raw_lower == "admin":
        assigned_admin = get_assigned_admin_for_department(department_value)

        return {
            "changed_by_role": "Адміністратор",
            "changed_by_name": assigned_admin.get("admin_name", ""),
            "changed_by_phone": assigned_admin.get("admin_phone", ""),
        }

    # 2. Департамент / ССП
    if raw_lower in ["департамент", "ссп", "кабінет ссп"]:
        responsible_name = (
            clean_text(row.get("responsible_person"))
            or clean_text(row.get("responsible_person_request"))
        )

        responsible_phone = (
            clean_text(row.get("phone"))
            or clean_text(row.get("phone_request"))
        )

        return {
            "changed_by_role": "Департамент",
            "changed_by_name": responsible_name,
            "changed_by_phone": responsible_phone,
        }

    # 3. Керівник ССП
    if "керівник" in raw_lower:
        for _, user in active_users.items():
            if user.get("role") != ROLE_SSP_HEAD:
                continue

            allowed_indexes = user.get("allowed_ssp_indexes", [])

            normalized_allowed_indexes = [
                normalize_ssp_index(index)
                for index in allowed_indexes
                if index != "*"
            ]

            if department_index and department_index in normalized_allowed_indexes:
                return {
                    "changed_by_role": "Керівник ССП",
                    "changed_by_name": clean_text(user.get("full_name")),
                    "changed_by_phone": clean_text(user.get("phone")),
                }

        return {
            "changed_by_role": "Керівник ССП",
            "changed_by_name": "",
            "changed_by_phone": "",
        }

    # 4. Якщо changed_by містить email або ПІБ
    for _, user in active_users.items():
        email = clean_text(user.get("email")).lower()
        full_name = clean_text(user.get("full_name")).lower()

        if email and email == raw_lower:
            return {
                "changed_by_role": clean_text(user.get("role_label")),
                "changed_by_name": clean_text(user.get("full_name")),
                "changed_by_phone": clean_text(user.get("phone")),
            }

        if full_name and full_name in raw_lower:
            return {
                "changed_by_role": clean_text(user.get("role_label")),
                "changed_by_name": clean_text(user.get("full_name")),
                "changed_by_phone": clean_text(user.get("phone")),
            }

    # 5. fallback
    return {
        "changed_by_role": raw_value,
        "changed_by_name": "",
        "changed_by_phone": "",
    }


def first_existing_column(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col
    return None


def prepare_requests(requests_df):
    prepared = requests_df.copy()

    if prepared.empty:
        return prepared

    date_col = first_existing_column(prepared, [
        "submitted_at", "created_at", "updated_at", "changed_at"
    ])

    if date_col:
        prepared["request_date_dt"] = prepared[date_col].apply(parse_datetime)
    else:
        prepared["request_date_dt"] = pd.NaT

    if "approval_status" not in prepared.columns:
        prepared["approval_status"] = "Невідомо"

    return prepared


def prepare_versions(versions_df):
    prepared = versions_df.copy()

    if prepared.empty:
        return prepared

    if "created_at" in prepared.columns:
        prepared["created_at_dt"] = prepared["created_at"].apply(parse_datetime)
        prepared = prepared.sort_values("created_at_dt", ascending=False, na_position="last")

    return prepared


def prepare_logs(logs_df, requests_df):
    if logs_df.empty:
        return logs_df

    prepared = logs_df.copy()

    if "changed_at" in prepared.columns:
        prepared["changed_at_dt"] = prepared["changed_at"].apply(parse_datetime)
        prepared = prepared.sort_values("changed_at_dt", ascending=False, na_position="last")
    else:
        prepared["changed_at_dt"] = pd.NaT

    if not requests_df.empty and "request_id" in prepared.columns:
        req_cols = [
            c for c in [
                "id", "department", "strat_code", "year", "quarter",
                "responsible_person", "phone", "email",
                "approval_status", "submitted_at", "created_at"
            ]
            if c in requests_df.columns
        ]

        req = requests_df[req_cols].copy()
        req = req.rename(columns={
            "id": "request_lookup_id",
            "department": "department_request",
            "strat_code": "strat_code_request",
            "year": "year_request",
            "quarter": "quarter_request",
            "responsible_person": "responsible_person_request",
            "phone": "phone_request",
            "email": "email_request",
            "approval_status": "approval_status_request",
            "submitted_at": "submitted_at_request",
            "created_at": "created_at_request"
            
        })

        prepared = prepared.merge(
            req,
            left_on="request_id",
            right_on="request_lookup_id",
            how="left"
        )

        for left_col, right_col in [
            ("department", "department_request"),
            ("strat_code", "strat_code_request"),
            ("year", "year_request"),
            ("quarter", "quarter_request"),
            ("responsible_person", "responsible_person_request"),
            ("phone", "phone_request"),
            ("email", "email_request"),
            ("approval_status", "approval_status_request")
        ]:
            if left_col not in prepared.columns:
                prepared[left_col] = ""
            if right_col in prepared.columns:
                prepared[left_col] = prepared[left_col].where(
                    prepared[left_col].notna() & (prepared[left_col].astype(str) != ""),
                    prepared[right_col]
                )

    return prepared


def normalize_multi_selection(values):
    if not values or "Усі" in values:
        return None
    return [str(v) for v in values]


def apply_common_filters(df, selected_departments, selected_actions, selected_changed_by, selected_years, selected_quarters, search):
    filtered = df.copy()

    deps = normalize_multi_selection(selected_departments)
    if deps is not None and "department" in filtered.columns:
        filtered = filtered[filtered["department"].astype(str).isin(deps)]

    actions = normalize_multi_selection(selected_actions)
    if actions is not None and "action" in filtered.columns:
        filtered = filtered[filtered["action"].astype(str).isin(actions)]

    changed_by = normalize_multi_selection(selected_changed_by)
    if changed_by is not None and "changed_by" in filtered.columns:
        filtered = filtered[filtered["changed_by"].astype(str).isin(changed_by)]

    years = normalize_multi_selection(selected_years)
    if years is not None and "year" in filtered.columns:
        filtered = filtered[filtered["year"].astype(str).isin(years)]

    quarters = normalize_multi_selection(selected_quarters)
    if quarters is not None and "quarter" in filtered.columns:
        filtered = filtered[filtered["quarter"].astype(str).isin(quarters)]

    if search.strip():
        sq = search.strip().lower()
        mask = pd.Series(False, index=filtered.index)

        for col in filtered.columns:
            mask = mask | filtered[col].astype(str).str.lower().str.contains(sq, na=False, regex=False)

        filtered = filtered[mask]

    return filtered


def apply_date_filter(df, dt_col, start_date, end_date):
    if df.empty or dt_col not in df.columns:
        return df

    filtered = df.copy()

    filtered[dt_col] = pd.to_datetime(
        filtered[dt_col],
        errors="coerce",
        utc=True
    )

    filtered = filtered[filtered[dt_col].notna()].copy()

    if filtered.empty:
        return filtered

    start_ts = pd.Timestamp(start_date).tz_localize("UTC")
    end_ts = pd.Timestamp(end_date).tz_localize("UTC") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    filtered = filtered[
        (filtered[dt_col] >= start_ts)
        &
        (filtered[dt_col] <= end_ts)
    ].copy()

    return filtered


def is_not_moderated(value):
    text = str(value).strip().lower()
    if text in ["", "nan", "none", "невідомо"]:
        return True
    return text != "погоджено"


def filter_requests(requests_df, selected_departments, selected_years, selected_quarters, search, start_date, end_date):
    filtered = requests_df.copy()

    filtered = apply_common_filters(
        filtered,
        selected_departments=selected_departments,
        selected_actions=["Усі"],
        selected_changed_by=["Усі"],
        selected_years=selected_years,
        selected_quarters=selected_quarters,
        search=search
    )

    filtered = apply_date_filter(filtered, "request_date_dt", start_date, end_date)

    return filtered


def format_date_range(start_date, end_date):
    return f"{start_date.strftime('%d.%m.%Y')} — {end_date.strftime('%d.%m.%Y')}"


def render_metric_cards(total_logs, unique_requests, unique_actions, total_versions, pending_requests):
    st.markdown(f"""
    <div class="metric-grid">
        <div class="metric-card metric-blue">
            <div class="metric-title">Записів у журналі</div>
            <div class="metric-value">{total_logs}</div>
            <div class="metric-note">За обраними параметрами відбору</div>
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
            <div class="metric-title">Заявок без завершеної модерації</div>
            <div class="metric-value">{pending_requests}</div>
            <div class="metric-note">У вибраному календарному періоді</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def display_logs_table(filtered):
    if filtered.empty:
        st.info("За обраними параметрами відбору записів журналу не знайдено.")
        return pd.DataFrame()

    show = filtered.copy()

    changed_by_data = show.apply(resolve_changed_by_user, axis=1)

    show["changed_by_role"] = changed_by_data.apply(
        lambda item: item.get("changed_by_role", "")
    )
    show["changed_by_name"] = changed_by_data.apply(
        lambda item: item.get("changed_by_name", "")
    )
    show["changed_by_phone"] = changed_by_data.apply(
        lambda item: item.get("changed_by_phone", "")
    )

    rename_map = {
        "id": "ID запису",
        "request_id": "ID заявки",
        "department": "ССП",
        "strat_code": "Код заходу",
        "year": "Рік",
        "quarter": "Квартал",
        "changed_at": "Дата зміни",
        "action": "Дія",
        "old_status": "Попередній статус",
        "new_status": "Новий статус",
        "approval_status": "Статус модерації",
        "admin_comment": "Коментар",
        "changed_by": "Ким змінено",
        "actor_email": "Email виконавця",
        "actor_name": "ПІБ виконавця",
        "actor_role": "Роль виконавця",
        "payload_json": "Службові деталі",
        "changed_by_role": "Роль",
        "changed_by_name": "ПІБ",
        "changed_by_phone": "Номер",
    }

    show = show.rename(columns=rename_map)

    cols = [
        "ID заявки",
        "ССП",
        "Код заходу",
        "Рік",
        "Квартал",
        "Дія",
        "Попередній статус",
        "Новий статус",
        "Статус модерації",
        "Коментар",
        "Роль виконавця",
        "ПІБ виконавця",
        "Email виконавця",
        "Роль",
        "ПІБ",
        "Номер",
        "Службові деталі",
        "Дата зміни",
    ]

    available = [c for c in cols if c in show.columns]

    st.dataframe(show[available], use_container_width=True, hide_index=True)

    return show[available]


def display_requests_table(df):
    if df.empty:
        st.info("За обраними параметрами заявок не знайдено.")
        return pd.DataFrame()

    show = df.copy()

    assigned_admin_data = show["department"].apply(get_assigned_admin_for_department)

    show["assigned_admin_name"] = assigned_admin_data.apply(
        lambda item: item.get("admin_name", "")
    )
    show["assigned_admin_phone"] = assigned_admin_data.apply(
        lambda item: item.get("admin_phone", "")
    )

    rename_map = {
        "id": "ID заявки",
        "department": "Самостійний структурний підрозділ",
        "strat_code": "Код заходу",
        "year": "Рік",
        "quarter": "Квартал",
        "responsible_person": "Відповідальна особа від ССП",
        "phone": "Телефон",
        "email": "Email",
        "approval_status": "Статус модерації",
        "status": "Статус виконання",
        "numeric_value": "Фактичне значення",
        "progress_text": "Опис прогресу",
        "risks": "Ризики",
        "submitted_at": "Дата подання",
        "created_at": "Дата створення",
        "updated_at": "Дата оновлення",
        "admin_comment": "Коментар адміністратора",
        "npa_link": "Посилання на НПА",
        "scheme_label": "Схема погодження",
        "object_kind": "Тип подання",
        "as_of_date": "Станом на дату",
        "assigned_admin_name": "Відповідальний адміністратор",
        "assigned_admin_phone": "Телефон адміністратора",
    }

    show = show.rename(columns=rename_map)

    cols = [
        "ID заявки",
        "Код заходу",
        "Рік",
        "Квартал",
        "Статус модерації",
        "Статус виконання",
        "Фактичне значення",
        "Опис прогресу",
        "Ризики",
        "Посилання на НПА",
        "Схема погодження",
        "Тип подання",
        "Станом на дату",
        "Відповідальний адміністратор",
        "Телефон адміністратора",
        "Коментар адміністратора",
        "Відповідальна особа від ССП",
        "Телефон",
        "Email",
        "Дата подання",
        "Дата створення",
    ]

    available = [c for c in cols if c in show.columns]
    st.dataframe(show[available], use_container_width=True, hide_index=True)

    return show[available]


def display_versions_table(versions_df, selected_departments, selected_years, selected_quarters, search, start_date, end_date):
    if versions_df.empty:
        st.info("Версій заявок поки що немає.")
        return pd.DataFrame()

    filtered_versions = versions_df.copy()

    filtered_versions = apply_common_filters(
        filtered_versions,
        selected_departments=selected_departments,
        selected_actions=["Усі"],
        selected_changed_by=["Усі"],
        selected_years=selected_years,
        selected_quarters=selected_quarters,
        search=search
    )

    if "created_at_dt" in filtered_versions.columns:
        filtered_versions = apply_date_filter(filtered_versions, "created_at_dt", start_date, end_date)

    show = filtered_versions.copy()

    show = show.rename(columns={
        "request_id": "ID заявки",
        "version_number": "Версія",
        "created_at": "Дата версії",
        "created_by": "Ким створено",
        "department": "Самостійний структурний підрозділ",
        "strat_code": "Код заходу",
        "year": "Рік",
        "quarter": "Квартал",
        "approval_status": "Статус модерації",
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
        "Самостійний структурний підрозділ",
        "Код заходу",
        "Рік",
        "Квартал",
        "Статус модерації",
        "Статус виконання",
        "Фактичне значення",
        "Опис прогресу",
        "Ризики"
    ]

    available = [c for c in version_cols if c in show.columns]

    if show.empty:
        st.info("За обраними параметрами версій заявок не знайдено.")
        return pd.DataFrame()

    st.dataframe(show[available], use_container_width=True, hide_index=True)
    return show[available]


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
        <div class="badge badge-yellow">● Заявки на модерації</div>
        <div class="badge">● Оновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}</div>
    </div>
</div>
""", unsafe_allow_html=True)

logs_df = load_logs()
requests_df = prepare_requests(load_requests())
versions_df = prepare_versions(load_versions())

if logs_df.empty and requests_df.empty:
    st.warning("Журнал дій і реєстр заявок поки що порожні.")
    st.stop()

logs_df = prepare_logs(logs_df, requests_df)

all_dates = []
if "changed_at_dt" in logs_df.columns and not logs_df.empty:
    all_dates += logs_df["changed_at_dt"].dropna().dt.date.tolist()
if "request_date_dt" in requests_df.columns and not requests_df.empty:
    all_dates += requests_df["request_date_dt"].dropna().dt.date.tolist()

if all_dates:
    min_available_date = min(all_dates)
    max_available_date = max(all_dates)
else:
    min_available_date = date.today() - timedelta(days=30)
    max_available_date = date.today()

default_start = min_available_date
default_end = max_available_date

st.markdown("""
<div class="card">
    <div class="card-title">Параметри відбору</div>
    <div class="card-subtitle">
        Оберіть календарний період та додаткові параметри для перегляду дій і заявок.
        Період застосовується до дати зміни в журналі, дати подання заявки та дати створення версії.
    </div>
    <div class="parameter-panel">
""", unsafe_allow_html=True)

p1, p2, p3 = st.columns(3)

with p1:
    st.markdown('<div class="parameter-box"><div class="parameter-label">Початкова дата</div>', unsafe_allow_html=True)
    selected_start_date = st.date_input(
        "Початкова дата",
        value=default_start,
        min_value=min_available_date,
        max_value=max_available_date,
        format="DD.MM.YYYY",
        label_visibility="collapsed"
    )
    st.markdown('</div>', unsafe_allow_html=True)

with p2:
    st.markdown('<div class="parameter-box"><div class="parameter-label">Кінцева дата</div>', unsafe_allow_html=True)
    selected_end_date = st.date_input(
        "Кінцева дата",
        value=default_end,
        min_value=min_available_date,
        max_value=max_available_date,
        format="DD.MM.YYYY",
        label_visibility="collapsed"
    )
    st.markdown('</div>', unsafe_allow_html=True)

with p3:
    st.markdown('<div class="parameter-box"><div class="parameter-label">Пошук</div>', unsafe_allow_html=True)
    search = st.text_input(
        "Пошук",
        placeholder="ID, код заходу, статус, коментар, відповідальна особа...",
        label_visibility="collapsed"
    )
    st.markdown('</div>', unsafe_allow_html=True)

if selected_start_date > selected_end_date:
    st.error("Початкова дата не може бути пізнішою за кінцеву дату.")
    st.stop()

p4, p5, p6 = st.columns(3)

with p4:
    st.markdown('<div class="parameter-box"><div class="parameter-label">Самостійний структурний підрозділ</div>', unsafe_allow_html=True)
    departments = ["Усі"]
    dep_sources = []
    for df in [logs_df, requests_df, versions_df]:
        if "department" in df.columns:
            dep_sources += df["department"].dropna().astype(str).tolist()
    departments += sorted(list(set([d for d in dep_sources if d and d.lower() != "nan"])), key=natural_sort_key)
    selected_departments = st.multiselect("Самостійний структурний підрозділ", departments, default=["Усі"], label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

with p5:
    st.markdown('<div class="parameter-box"><div class="parameter-label">Рік</div>', unsafe_allow_html=True)
    years = ["Усі"]
    year_sources = []
    for df in [logs_df, requests_df, versions_df]:
        if "year" in df.columns:
            year_sources += df["year"].dropna().astype(str).tolist()
    years += sorted(list(set([y for y in year_sources if y and y.lower() != "nan"])), key=natural_sort_key)
    selected_years = st.multiselect("Рік", years, default=["Усі"], label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

with p6:
    st.markdown('<div class="parameter-box"><div class="parameter-label">Квартал</div>', unsafe_allow_html=True)
    quarter_order = {"I": 1, "II": 2, "III": 3, "IV": 4}
    quarters = ["Усі"]
    quarter_sources = []
    for df in [logs_df, requests_df, versions_df]:
        if "quarter" in df.columns:
            quarter_sources += df["quarter"].dropna().astype(str).tolist()
    quarters += sorted(list(set([q for q in quarter_sources if q and q.lower() != "nan"])), key=lambda x: quarter_order.get(str(x), 99))
    selected_quarters = st.multiselect("Квартал", quarters, default=["Усі"], label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

p7, p8, p9 = st.columns(3)

with p7:
    st.markdown('<div class="parameter-box"><div class="parameter-label">Дія в журналі</div>', unsafe_allow_html=True)
    actions = ["Усі"]
    if "action" in logs_df.columns:
        actions += sorted(logs_df["action"].dropna().astype(str).unique().tolist())
    selected_actions = st.multiselect("Дія в журналі", actions, default=["Усі"], label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

with p8:
    st.markdown('<div class="parameter-box"><div class="parameter-label">Ким змінено</div>', unsafe_allow_html=True)
    changed_by_values = ["Усі"]
    if "changed_by" in logs_df.columns:
        changed_by_values += sorted(logs_df["changed_by"].dropna().astype(str).unique().tolist())
    selected_changed_by = st.multiselect("Ким змінено", changed_by_values, default=["Усі"], label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

with p9:
    st.markdown('<div class="parameter-box"><div class="parameter-label">Статус модерації заявок</div>', unsafe_allow_html=True)
    approval_statuses = ["Усі"]
    if "approval_status" in requests_df.columns:
        approval_statuses += sorted(requests_df["approval_status"].fillna("Невідомо").astype(str).unique().tolist())
    selected_approval_statuses = st.multiselect(
        "Статус модерації заявок",
        approval_statuses,
        default=["Усі"],
        label_visibility="collapsed"
    )
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
    </div>
</div>
""", unsafe_allow_html=True)

filtered_logs = apply_common_filters(
    logs_df,
    selected_departments=selected_departments,
    selected_actions=selected_actions,
    selected_changed_by=selected_changed_by,
    selected_years=selected_years,
    selected_quarters=selected_quarters,
    search=search
)
filtered_logs = apply_date_filter(filtered_logs, "changed_at_dt", selected_start_date, selected_end_date)

filtered_requests = filter_requests(
    requests_df,
    selected_departments=selected_departments,
    selected_years=selected_years,
    selected_quarters=selected_quarters,
    search=search,
    start_date=selected_start_date,
    end_date=selected_end_date
)

approval_selection = normalize_multi_selection(selected_approval_statuses)
if approval_selection is not None and "approval_status" in filtered_requests.columns:
    filtered_requests = filtered_requests[filtered_requests["approval_status"].fillna("Невідомо").astype(str).isin(approval_selection)]

not_moderated_requests = filtered_requests[
    filtered_requests["approval_status"].apply(is_not_moderated)
].copy() if "approval_status" in filtered_requests.columns else filtered_requests.copy()

unique_request_ids_from_logs = filtered_logs["request_id"].nunique() if "request_id" in filtered_logs.columns and not filtered_logs.empty else 0
unique_actions = filtered_logs["action"].nunique() if "action" in filtered_logs.columns and not filtered_logs.empty else 0

st.markdown('<div class="card"><div class="card-title">Ключові показники журналу</div><div class="card-subtitle">Зведення за обраним календарним періодом і параметрами відбору.</div>', unsafe_allow_html=True)

render_metric_cards(
    total_logs=len(filtered_logs),
    unique_requests=unique_request_ids_from_logs,
    unique_actions=unique_actions,
    total_versions=len(versions_df),
    pending_requests=len(not_moderated_requests)
)

st.markdown(f"""
<div class="badge-wrap">
    <div class="badge">● Період: {format_date_range(selected_start_date, selected_end_date)}</div>
    <div class="badge badge-green">● Заявок у періоді: {len(filtered_requests)}</div>
    <div class="badge badge-yellow">● Не пройшли модерацію: {len(not_moderated_requests)}</div>
    <div class="badge">● Записів журналу: {len(filtered_logs)}</div>
</div>
""", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
<div class="card">
    <div class="card-title">Заявки за обраний період</div>
    <div class="card-subtitle">
        Окремо винесено заявки, які ще не мають завершеної модерації. Це дозволяє швидко бачити подання, що очікують погодження, повернуті або перебувають у проміжному статусі.
    </div>
""", unsafe_allow_html=True)

tab_pending, tab_all_requests = st.tabs(["Не пройшли модерацію", "Усі заявки за період"])

with tab_pending:
    st.markdown(f"""
    <div class="status-panel">
        <div class="status-title">Заявки без завершеної модерації: {len(not_moderated_requests)}</div>
        <div class="small-note">Вибірка формується за правилом: статус модерації не дорівнює «Погоджено» або статус відсутній.</div>
    </div>
    """, unsafe_allow_html=True)
    pending_export = display_requests_table(not_moderated_requests)

with tab_all_requests:
    # Перемикач типу об'єкта подання: заходи чи індикатори СЦ/завдань
    if "object_kind" in filtered_requests.columns:
        _kind_choice = st.radio(
            "Тип подань",
            ["📊 Заходи", "🎯 Індикатори СЦ та завдань", "Усі"],
            horizontal=True,
            key="journal_kind_toggle",
        )
        if _kind_choice.startswith("📊"):
            filtered_requests = filtered_requests[
                filtered_requests["object_kind"].fillna("measure").astype(str) != "indicator"
            ]
        elif _kind_choice.startswith("🎯"):
            filtered_requests = filtered_requests[
                filtered_requests["object_kind"].astype(str) == "indicator"
            ]

    all_requests_export = display_requests_table(filtered_requests)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Повний журнал дій</div><div class="card-subtitle">Детальний перелік системних подій за обраними параметрами відбору. Графіки з цієї сторінки прибрано, щоб залишити лише контрольні таблиці та календарний відбір.</div>', unsafe_allow_html=True)

logs_export = display_logs_table(filtered_logs)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Версії заявок</div><div class="card-subtitle">Попередні та повторно подані версії заявок у межах обраного періоду.</div>', unsafe_allow_html=True)

versions_export = display_versions_table(
    versions_df,
    selected_departments=selected_departments,
    selected_years=selected_years,
    selected_quarters=selected_quarters,
    search=search,
    start_date=selected_start_date,
    end_date=selected_end_date
)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="card-title">Експорт журналу</div><div class="card-subtitle">Завантаження поточного зрізу журналу, заявок без завершеної модерації, усіх заявок за період і версій.</div>', unsafe_allow_html=True)

excel_file = dataframe_to_excel({
    "Журнал дій": logs_export,
    "Не пройшли модерацію": pending_export,
    "Заявки за період": all_requests_export,
    "Версії заявок": versions_export
})

ec1, ec2 = st.columns(2)
with ec1:
    st.download_button(
        "Завантажити журнал і заявки XLSX",
        data=excel_file,
        file_name=f"audit_log_requests_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
with ec2:
    _docx_file = core_exports.dataframes_to_docx_landscape(
        {
            "Журнал дій": logs_export,
            "Не пройшли модерацію": pending_export,
            "Заявки за період": all_requests_export,
            "Версії заявок": versions_export,
        },
        title="Журнал дій системи моніторингу",
        subtitle=f"Період: {format_date_range(selected_start_date, selected_end_date)}",
    )
    if _docx_file is not None:
        st.download_button(
            "Завантажити журнал DOCX (альбомний)",
            data=_docx_file,
            file_name=f"audit_log_requests_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )
    else:
        st.caption("DOCX-експорт недоступний: перевірте пакет python-docx у requirements.txt.")

st.markdown('</div>', unsafe_allow_html=True)

render_footer()
