import re
from datetime import datetime, timezone
from html import escape

import pandas as pd
import streamlit as st
from core.db import get_supabase_client
from core.deputies import DEPUTY_MINISTER_BY_SSP
from core.ui import load_css
from core.config import FILE_PATH, SHEET_NAME
from core.excel_loader import read_excel_sheet

from core.page_setup import page_setup, render_footer

from core.access import (
    filter_actions_for_user,
    get_prefilled_user_contacts,
    get_user_allowed_ssp_indexes,
    should_lock_ssp_fields,
    should_prefill_contact_fields,
    user_has_all_ssp_access,
)
from core.closeouts import load_manual_closeouts
from core.strategic_data import load_strat_matrix as load_full_strat_matrix
from core import monitoring_data
from core import approval_schemes as schemes
from core import notify_events


# ------------------------------------------------------------
# Page config
# ------------------------------------------------------------

current_user = page_setup("Моніторинг (внесення відомостей)",
                          page_name="Моніторинг виконання")
supabase = get_supabase_client()
# ------------------------------------------------------------
# CSS
# ------------------------------------------------------------

st.markdown(
    """
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

.header-box,
.flow-box,
.summary-box,
.filter-box,
.info-card,
.note-box {
    background: rgba(255,255,255,0.94);
    border: 1px solid #d8dee9;
    box-shadow: 0 6px 18px rgba(15,23,42,0.045);
}

.status-row {
    max-width: 1280px;
    margin: 12px auto 22px auto;
    display: grid;
    grid-template-columns: 1fr 1fr 1.45fr;
    gap: 12px;
    align-items: stretch;
}

.status-pill {
    min-height: 58px;
    border-radius: 14px;
    padding: 12px 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    font-size: 13px;
    font-weight: 850;
    line-height: 1.3;
    text-align: center;
    border: 1px solid transparent;
    box-shadow: 0 6px 16px rgba(15,23,42,0.05);
}

.status-dot {
    width: 10px;
    height: 10px;
    min-width: 10px;
    border-radius: 999px;
    display: inline-block;
}

.status-green {
    background: #dcfce7;
    color: #166534;
    border-color: #86efac;
}

.status-green .status-dot {
    background: #16a34a;
}

.status-blue {
    background: #dbeafe;
    color: #1e40af;
    border-color: #93c5fd;
}

.status-blue .status-dot {
    background: #2563eb;
}

.status-orange {
    background: #ffedd5;
    color: #9a3412;
    border-color: #fdba74;
}

.status-orange .status-dot {
    background: #f97316;
}

@media (max-width: 1100px) {
    .status-row {
        grid-template-columns: 1fr;
    }
}

.header-box {
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 18px;
    backdrop-filter: blur(8px);
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

.user-box {
    border-radius: 18px;
    padding: 22px 26px 24px 26px;
    margin: 18px 0 18px 0;
    background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(241,246,253,0.98));
    border: 1px solid #cbd8ea;
    box-shadow: 0 10px 24px rgba(15,23,42,0.07);
}

.user-title,
.flow-title,
.summary-title,
.filter-title,
.table-title {
    color: #0f172a;
    font-weight: 900;
}

.user-title {
    font-size: 20px;
    margin-bottom: 14px;
}

.flow-box {
    border-radius: 16px;
    padding: 18px 20px;
    margin: 18px 0;
}

.flow-title {
    font-size: 17px;
    margin-bottom: 12px;
}

.flow-steps {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 10px;
}

.flow-step {
    min-height: 58px;
    padding: 10px 12px;
    border-radius: 14px;
    background: linear-gradient(180deg, #f8fafc 0%, #eef4fb 100%);
    border: 1px solid #d8dee9;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    color: #334155;
    font-size: 13px;
    font-weight: 800;
    line-height: 1.25;
}

.summary-box {
    border-radius: 16px;
    padding: 18px 20px;
    margin: 18px 0;
}

.summary-title {
    font-size: 20px;
    margin-bottom: 12px;
}

.summary-grid {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 12px;
    align-items: stretch;
}

.summary-card {
    background: #f8fafc;
    border: 1px solid #d8dee9;
    border-radius: 13px;
    padding: 14px 15px;
    min-height: 96px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.summary-label {
    color: #64748b;
    font-size: 12px;
    font-weight: 800;
    line-height: 1.35;
    min-height: 34px;
    margin-bottom: 8px;
}

.summary-value {
    color: #0f172a;
    font-size: 24px;
    line-height: 1;
    font-weight: 950;
}

.filter-box {
    border-radius: 18px;
    padding: 24px 26px 26px 26px;
    margin: 18px 0 24px 0;
    background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(241,246,253,0.98));
    border: 1px solid #cbd8ea;
    box-shadow: 0 10px 24px rgba(15,23,42,0.07);
}

.filter-title {
    font-size: 22px;
    margin-bottom: 10px;
}

.filter-legend {
    color: #475569;
    font-size: 14px;
    line-height: 1.55;
    margin-bottom: 16px;
}

.info-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 14px;
    margin-bottom: 20px;
}

.info-card {
    border-radius: 14px;
    padding: 17px 19px;
    color: #1f2937;
    line-height: 1.55;
}

.info-card-title {
    color: #0f172a;
    font-size: 16px;
    font-weight: 900;
    margin-bottom: 8px;
}

.instruction-item {
    margin-bottom: 7px;
    font-size: 14px;
}

.note-box {
    border-radius: 10px;
    padding: 13px 17px;
    color: #374151;
    font-size: 14px;
    margin: 12px 0 18px 0;
}

.table-title {
    font-size: 20px;
    margin: 24px auto 12px auto;
    max-width: 1280px;
}

div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    background-color: #d7eaff !important;
    border: 1px solid #8fb3df !important;
    border-radius: 10px !important;
    min-height: 43px !important;
    box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.08) !important;
}

div[data-testid="stSelectbox"] label,
div[data-testid="stTextInput"] label,
div[data-testid="stTextArea"] label {
    font-weight: 750 !important;
    color: #1e293b !important;
}

/* Центрування всієї таблиці */
div[data-testid="stDataEditor"] {
    max-width: 1280px !important;
    margin-left: auto !important;
    margin-right: auto !important;
    border-radius: 14px !important;
    overflow: hidden !important;
    border: 1px solid #cbd5e1 !important;
    box-shadow: 0 8px 22px rgba(15,23,42,0.06) !important;
}

/* Вища шапка таблиці + перенос тексту в шапці */
div[data-testid="stDataEditor"] div[role="columnheader"] {
    min-height: 96px !important;
    height: 96px !important;
    background: #e8eef7 !important;
    border-bottom: 1px solid #cbd5e1 !important;
    font-weight: 900 !important;
    color: #0f172a !important;
    line-height: 1.2 !important;
    white-space: normal !important;
    overflow: visible !important;
}

/* Реальний текстовий контейнер у шапці data_editor */
div[data-testid="stDataEditor"] div[role="columnheader"] div,
div[data-testid="stDataEditor"] div[role="columnheader"] span,
div[data-testid="stDataEditor"] div[role="columnheader"] p {
    white-space: pre-line !important;
    word-break: normal !important;
    overflow-wrap: anywhere !important;
    text-align: center !important;
    line-height: 1.2 !important;
    max-height: none !important;
    overflow: visible !important;
    text-overflow: clip !important;
}

/* Забирає обрізання назв колонок */
div[data-testid="stDataEditor"] div[role="columnheader"] [title] {
    white-space: pre-line !important;
    overflow: visible !important;
    text-overflow: clip !important;
}

/* Центрування тексту в шапці і клітинках */
div[data-testid="stDataEditor"] div[role="gridcell"],
div[data-testid="stDataEditor"] div[role="columnheader"],
div[data-testid="stDataEditor"] div[role="gridcell"] div,
div[data-testid="stDataEditor"] div[role="columnheader"] div,
div[data-testid="stDataEditor"] div[role="gridcell"] p,
div[data-testid="stDataEditor"] div[role="columnheader"] p,
div[data-testid="stDataEditor"] div[role="gridcell"] span,
div[data-testid="stDataEditor"] div[role="columnheader"] span {
    text-align: center !important;
    justify-content: center !important;
    align-items: center !important;
}

/* Перенос саме в рядках таблиці */
div[data-testid="stDataEditor"] div[role="gridcell"] div,
div[data-testid="stDataEditor"] div[role="gridcell"] p,
div[data-testid="stDataEditor"] div[role="gridcell"] span {
    white-space: normal !important;
    overflow-wrap: break-word !important;
}

div[data-testid="stDataEditor"] textarea,
div[data-testid="stDataEditor"] input {
    text-align: center !important;
}

div[data-testid="stDataEditor"] [data-testid="stCheckbox"] {
    display: flex !important;
    justify-content: center !important;
}

div[data-testid="stButton"] > button {
    width: 100%;
    min-height: 68px;
    background: linear-gradient(135deg, #dc2626 0%, #f97316 52%, #facc15 100%) !important;
    color: #ffffff !important;
    border: 0 !important;
    border-radius: 18px !important;
    font-size: 20px !important;
    font-weight: 950 !important;
    letter-spacing: 0.3px !important;
    box-shadow: 0 18px 34px rgba(249,115,22,0.34), inset 0 1px 0 rgba(255,255,255,0.25) !important;
}

div[data-testid="stButton"] > button:hover {
    filter: brightness(1.05);
    transform: translateY(-1px);
}

.final-footer {
    text-align: center;
    color: #475569;
    font-size: 13px;
    margin-top: 48px;
    padding-top: 24px;
    border-top: 1px solid #cbd5e1;
    line-height: 1.7;
}

.final-footer-main {
    font-weight: 700;
    color: #334155;
}

.final-footer-sub {
    color: #64748b;
    font-size: 12px;
}

@media (max-width: 1100px) {
    .summary-grid,
    .flow-steps {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}
</style>
""",
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def raw_value(value):
    if value is None or pd.isna(value) or str(value) == "None":
        return ""
    return str(value).strip()


def clean_value(value):
    return escape(raw_value(value))


def is_empty_or_nd(value):
    text = raw_value(value).lower().replace(" ", "")
    return text in {"", "н.д.", "нд", "nan", "none", "-", "—"}


def strip_leading_code(text, code):
    value = raw_value(text)
    code_value = raw_value(code)

    if code_value and value.startswith(code_value):
        value = value[len(code_value):].lstrip(" .—-–|:")

    return value


def split_ssp_values(value):
    text = raw_value(value)
    if not text:
        return []
    return re.findall(r"\d+", text)


def value_contains_ssp(value, selected_index):
    if not selected_index:
        return True
    return selected_index in split_ssp_values(value)

def extract_ssp_index(value):
    text = raw_value(value)
    if not text:
        return ""
    match = re.search(r"\d+", text)
    return match.group(0) if match else ""


def get_deputy_for_ssp(ssp_index):
    return DEPUTY_MINISTER_BY_SSP.get(str(ssp_index), "")




def make_summary_card(label, value):
    return (
        f'<div class="summary-card">'
        f'<div class="summary-label">{escape(str(label))}</div>'
        f'<div class="summary-value">{escape(str(value))}</div>'
        f'</div>'
    )


def normalize_key(text):
    """Стислий безпечний суфікс для st.session_state-ключів."""
    return re.sub(r"[^0-9a-zA-Zа-яА-ЯіїєґІЇЄҐ]+", "_", str(text))[:60]


def quarter_to_q_label(quarter):
    mapping = {
        "I": "Q1",
        "II": "Q2",
        "III": "Q3",
        "IV": "Q4"
    }
    return mapping.get(raw_value(quarter), raw_value(quarter))


def row_matches_search(row, search_query):
    query = raw_value(search_query).lower()

    if not query:
        return True

    values = [
        row.get("code", ""),
        row.get("name", ""),
        row.get("indicator", ""),
        row.get("product_type", ""),
        row.get("resp_main", ""),
        row.get("resp_co_1", ""),
        row.get("resp_co_2", "")
    ]

    return any(query in raw_value(value).lower() for value in values)


def has_target_for_year(row, year):
    col = f"target_{year}"
    if col not in row:
        return True
    return not is_empty_or_nd(row.get(col, ""))


def get_record_visual_status(row):
    approval = raw_value(row.get("approval_status", ""))

    if approval == "Погоджено":
        return "Погоджено"

    if approval == "Повернуто на доопрацювання":
        return "Повернуто на доопрацювання"

    if approval in {"Очікує погодження", "На розгляді", "Очікує розгляду"}:
        return "Очікує розгляду"

    return "Не враховано"


def subset_monitoring_for_selection(monitoring_df, selected_codes, selected_year, selected_quarter):
    if monitoring_df.empty:
        return pd.DataFrame()

    data = monitoring_df.copy()
    data["strat_code_clean"] = data["strat_code"].astype(str).str.strip()
    data["year_clean"] = data["year"].astype(str).str.strip()
    data["quarter_clean"] = data["quarter"].astype(str).str.strip()

    return data[
        data["strat_code_clean"].isin([str(code).strip() for code in selected_codes])
        & (data["year_clean"] == str(selected_year))
        & (data["quarter_clean"] == str(selected_quarter))
    ].copy()


def unique_measure_count(data):
    if data.empty or "strat_code" not in data.columns:
        return 0
    return data["strat_code"].astype(str).str.strip().replace("", pd.NA).dropna().nunique()


# ------------------------------------------------------------
# Data loading
# ------------------------------------------------------------

def load_strat_matrix():
    """ЄДИНЕ джерело — core.strategic_data (правка К1)."""
    return load_full_strat_matrix()


def load_monitoring():
    """ЄДИНЕ джерело — core.monitoring_data (правки К2, П2)."""
    return monitoring_data.load_monitoring_requests()


def ensure_monitoring_columns(monitoring_df):
    return monitoring_data.ensure_monitoring_columns(monitoring_df)



# ------------------------------------------------------------
# Load data
# ------------------------------------------------------------

df = load_strat_matrix()
_raw_monitoring_df = load_monitoring()
# П2: наявність колонок таблиці зафіксована константами (core.monitoring_data),
# а не визначається за завантаженими рядками — інакше після очищення бази
# перше подання йшло БЕЗ схеми погодження, НПА та позначки захід/індикатор.
npa_link_column_exists = monitoring_data.HAS_NPA_LINK_COLUMN
chain_columns_exist = monitoring_data.HAS_CHAIN_COLUMNS
kind_column_exists = monitoring_data.HAS_OBJECT_KIND_COLUMN
monitoring_df = ensure_monitoring_columns(_raw_monitoring_df)

all_measures = df[df["object_type"] == "measure"].copy()

all_ssp_indices = sorted(
    {
        index
        for _, row in all_measures.iterrows()
        for column in ["resp_main", "resp_co_1"]
        for index in split_ssp_values(row.get(column, ""))
    },
    key=lambda x: int(x) if str(x).isdigit() else 9999
)

user_allowed_ssp_indexes = get_user_allowed_ssp_indexes(current_user)

if user_has_all_ssp_access(current_user):
    available_ssp_indices = all_ssp_indices
else:
    available_ssp_indices = [
        index
        for index in user_allowed_ssp_indexes
        if index in all_ssp_indices
    ]

    # Якщо в матриці поки не знайдено цей індекс, але він прописаний користувачу,
    # все одно показуємо його, щоб форма не падала.
    if not available_ssp_indices:
        available_ssp_indices = user_allowed_ssp_indexes

ssp_select_disabled = should_lock_ssp_fields(current_user)

year_options = list(range(2026, 2035))
quarter_options = ["I", "II", "III", "IV"]

execution_status_options = [
    "Виконано",
    "Частково виконано",
    "Не виконано",
    "Не настав час",
    "Втратило актуальність"
]


# ------------------------------------------------------------
# Header
# ------------------------------------------------------------

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
    """
    <div class="header-box">
        <div class="header-title">Моніторинг стратегічних результатів</div>
        <div class="header-subtitle">
            Кабінет користувача призначений для щоквартального внесення відомостей 
            (до 15 числа місяця, наступного за звітним кварталом) з метою формування 
            результатів моніторингу виконання заходів, оцінки прогресу досягнення 
            стратегічних цілей, контролю статусу виконання заходів, своєчасного 
            виявлення відхилень і ризиків, формування коригувальних дій, а також 
            створення моніторингових звітів та інфографічних матеріалів.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

prefilled_contacts = get_prefilled_user_contacts(current_user)
contact_fields_disabled = should_prefill_contact_fields(current_user)

# ------------------------------------------------------------
# User info fields
# ------------------------------------------------------------

st.markdown(
    """
    <div class="user-box">
        <div class="user-title">Контактна інформація відповідальної особи</div>
    """,
    unsafe_allow_html=True
)

u1, u2, u3 = st.columns([1.2, 0.85, 1.1])

with u1:
    responsible_person = st.text_input(
        "ПІБ відповідальної особи",
        value=prefilled_contacts.get("full_name", ""),
        key="responsible_person_input",
        placeholder="Введіть ПІБ",
        disabled=contact_fields_disabled,
    )

with u2:
    responsible_phone = st.text_input(
        "Контактний номер телефону",
        value=prefilled_contacts.get("phone", ""),
        key="responsible_phone_input",
        placeholder="+380...",
        disabled=contact_fields_disabled,
    )

with u3:
    responsible_email = st.text_input(
        "Електронна пошта відповідальної особи",
        value=prefilled_contacts.get("email", ""),
        key="responsible_email_input",
        placeholder="name@me.gov.ua",
        disabled=contact_fields_disabled,
    )

st.markdown("</div>", unsafe_allow_html=True)


# ------------------------------------------------------------
# Схема погодження — спільний блок для заходів та індикаторів
# ------------------------------------------------------------

def render_scheme_picker(ssp_index, key_prefix):
    """
    Виводить вибір схеми погодження і конкретних осіб для кожної ланки.

    Повертає (scheme_name, chain, ready):
    - chain — список ланок для approval_chain;
    - ready=False, якщо для якоїсь ланки не знайдено/не обрано особу.
    """
    st.markdown(
        '<div class="table-title" style="margin-top:14px;">Схема погодження</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Оберіть маршрут погодження цієї подачі та конкретних осіб на кожній ланці. "
        "Координатор — обов'язкова ланка кожної схеми. Адміністратор може "
        "підтвердити або змінити обрану схему (зміна фіксується в журналі дій)."
    )

    scheme_name = st.selectbox(
        "Маршрут погодження",
        schemes.scheme_options(),
        index=schemes.scheme_options().index(schemes.DEFAULT_SCHEME),
        key=f"{key_prefix}_scheme",
    )

    roles_in_scheme = schemes.APPROVAL_SCHEMES[scheme_name]
    persons = {}
    ready = True

    cols = st.columns(len(roles_in_scheme))
    for i, role in enumerate(roles_in_scheme):
        with cols[i]:
            candidates = schemes.stage_candidates(role, ssp_index)
            label = schemes.STAGE_LABELS.get(role, role)
            if not candidates:
                if role == schemes.ROLE_ADMIN:
                    st.error(
                        f"Для ССП {ssp_index} не закріплено координатора "
                        f"(адміністратора). Зверніться до супер-адміністратора, "
                        f"щоб призначити відповідального адміністратора цьому ССП."
                    )
                else:
                    st.warning(
                        f"Ланка «{label}»: у системі немає користувача цієї ролі "
                        f"для ССП {ssp_index}."
                    )
                ready = False
                continue
            # Координатор закріплений за ССП однозначно — без вибору:
            # показуємо єдину особу, зафіксовану автоматично.
            if role == schemes.ROLE_ADMIN or len(candidates) == 1:
                chosen = candidates[0]
                st.markdown(
                    f'<div style="background:#eef2f9;border:1px solid #d8dee9;'
                    f'border-radius:10px;padding:8px 12px;">'
                    f'<div style="font-size:10px;font-weight:800;letter-spacing:.04em;'
                    f'text-transform:uppercase;color:#64748b;">{i + 1}. {label}</div>'
                    f'<div style="font-size:13px;font-weight:700;color:#0f172a;">'
                    f'{escape(schemes.candidate_label(chosen))}</div></div>',
                    unsafe_allow_html=True,
                )
                persons[role] = {"email": chosen["email"], "name": chosen["name"]}
                continue
            options = [schemes.candidate_label(c) for c in candidates]
            picked = st.selectbox(
                f"{i + 1}. {label}",
                options,
                key=f"{key_prefix}_stage_{role}",
            )
            chosen = candidates[options.index(picked)]
            persons[role] = {"email": chosen["email"], "name": chosen["name"]}

    chain = schemes.build_chain(scheme_name, persons) if ready else []
    if ready:
        st.markdown(
            f'<div class="note-box" style="background:#eff6ff;border:1px solid #bfdbfe;color:#1e3a8a;">'
            f'Маршрут: <b>{schemes.chain_route_text(chain)}</b></div>',
            unsafe_allow_html=True,
        )
    return scheme_name, chain, ready


def notify_first_stage(chain, codes, year_str, quarter_str, kind="measure"):
    """Одне миттєве сповіщення першій ланці про подання (без спаму по кожному коду)."""
    if not chain:
        return
    stage = chain[0]
    codes_text = ", ".join(codes[:5]) + ("…" if len(codes) > 5 else "")
    try:
        notify_events.notify_stage_assigned(
            stage.get("email", ""), stage.get("name", ""), stage.get("label", ""),
            codes_text, year_str, quarter_str,
            submitter=raw_value(responsible_person), kind=kind,
        )
    except Exception:
        pass


# ------------------------------------------------------------
# Перемикач: що подаємо — заходи чи індикатори СЦ/завдань
# ------------------------------------------------------------

submission_mode = st.radio(
    "Що подаєте",
    ["📊 Заходи", "🎯 Індикатори СЦ та стратегічних завдань"],
    horizontal=True,
    key="submission_mode_toggle",
)

if submission_mode.startswith("🎯"):
    # ========================================================
    # ПОДАННЯ ДАНИХ ДЛЯ ІНДИКАТОРІВ СЦ ТА ЗАВДАНЬ
    # ========================================================
    st.markdown(
        """
        <div class="flow-box">
            <div class="flow-title">Подання значень індикаторів СЦ та стратегічних завдань</div>
            <div class="flow-steps">
                <div class="flow-step">1. Вибір ССП і року</div>
                <div class="flow-step">2. Дата «станом на»</div>
                <div class="flow-step">3. Заповнення значень</div>
                <div class="flow-step">4. Схема погодження</div>
                <div class="flow-step">5. Відправлення</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Значення індикаторів подаються «станом на дату»: щойно у ССП з'являється "
        "нова інформація — подається оновлене значення. Для розрахунків оцінки "
        "прогресу (режим «МіО цілі/завдання») використовуються найновіші погоджені "
        "дані; вся історія подань зберігається."
    )

    ic1, ic2, ic3, ic4 = st.columns([1.25, 0.7, 0.9, 1.4])
    with ic1:
        if available_ssp_indices:
            ind_ssp_index = st.selectbox(
                "Індекс самостійного структурного підрозділу",
                available_ssp_indices, index=0,
                key="ind_ssp_filter", disabled=ssp_select_disabled,
            )
        else:
            ind_ssp_index = ""
            st.warning("Для цього користувача не визначено доступний індекс ССП.")
    with ic2:
        ind_year = st.selectbox("Рік", [2026, 2027, 2028], index=0, key="ind_year_filter")
    with ic3:
        ind_as_of = st.date_input("Станом на дату", key="ind_as_of_date")
    with ic4:
        ind_search = st.text_input(
            "Пошук (код СЦ/завдання, ключові слова)",
            key="ind_search_filter", placeholder="Наприклад: 1.2",
        )

    full_matrix = load_full_strat_matrix()
    indicator_rows = full_matrix[
        full_matrix["object_type"].isin(["goal_indicator", "task_indicator"])
    ].copy()

    indicator_rows = filter_actions_for_user(
        indicator_rows, current_user, executor_columns=["resp_main", "resp_co_1"],
    )

    if ind_ssp_index:
        _pat = re.compile(rf"(?<!\d){re.escape(str(ind_ssp_index))}(?!\d)")
        _mask = indicator_rows.apply(
            lambda r: bool(_pat.search(str(r.get("resp_main", "")))) or bool(_pat.search(str(r.get("resp_co_1", "")))),
            axis=1,
        )
        indicator_rows = indicator_rows[_mask]

    if raw_value(ind_search):
        _q = raw_value(ind_search).lower()
        indicator_rows = indicator_rows[indicator_rows.apply(
            lambda r: _q in str(r.get("code", "")).lower()
            or _q in str(r.get("name", "")).lower()
            or _q in str(r.get("indicator", "")).lower(),
            axis=1,
        )]

    ind_target_col = f"target_{ind_year}"
    if ind_target_col not in indicator_rows.columns:
        indicator_rows[ind_target_col] = ""

    # Останні подання індикаторів (у процесі → блокуємо новий дубль у черзі)
    waiting_statuses = set(schemes.ALL_WAITING_STATUSES)
    ind_submitted = {}
    if kind_column_exists and not monitoring_df.empty and "object_kind" in monitoring_df.columns:
        _ind_df = monitoring_df[
            (monitoring_df["object_kind"].astype(str) == "indicator")
            & (monitoring_df["year"].astype(str).str.strip() == str(ind_year))
        ]
        for _, mrow in _ind_df.sort_values("submitted_at").iterrows():
            ind_submitted[raw_value(mrow.get("strat_code"))] = mrow

    value_col = f"Значення станом\nна {ind_as_of.strftime('%d.%m.%Y')}"

    ind_table_rows = []
    for _, row in indicator_rows.iterrows():
        code = raw_value(row.get("code", ""))
        last = ind_submitted.get(code)
        in_progress = last is not None and raw_value(last.get("approval_status")) in waiting_statuses
        last_info = ""
        if last is not None:
            last_info = (
                f"{raw_value(last.get('numeric_value'))} "
                f"(станом на {raw_value(last.get('as_of_date')) or raw_value(last.get('submitted_at'))[:10]}, "
                f"{raw_value(last.get('approval_status'))})"
            )
        ind_table_rows.append({
            "Подати": not in_progress,
            "Код": code,
            "СЦ / Завдання": strip_leading_code(row.get("name", ""), code),
            "Індикатор": raw_value(row.get("indicator", "")),
            "Одиниці\nвиміру": raw_value(row.get("unit", "")),
            "2021\n(базовий)": raw_value(row.get("base_2021", "")),
            f"{ind_year}\n(цільовий орієнтир)": raw_value(row.get(ind_target_col, "")),
            "Останнє подане\nзначення": last_info,
            value_col: "",
            "Статус\nвиконання": "",
            "Опис\nпрогресу": "",
            "Ризики / проблеми /\nвідхилення": "",
            "Посилання\nна НПА": "",
            "_locked": in_progress,
        })

    ind_required_cols = [value_col, "Статус\nвиконання"]
    st.markdown(
        f"""
        <div class="note-box" style="background:#f8fafc;border:1px solid #d8dee9;">
            <b>Легенда обов'язковості полів:</b>
            <span style="background:#fde8e8;border:1px solid #fca5a5;border-radius:8px;
                  padding:2px 10px;margin:0 6px;font-weight:800;color:#991b1b;">🔴 Обов'язкове</span>
            «{value_col.replace(chr(10), ' ')}», «Статус виконання»
            <span style="background:#fef6e0;border:1px solid #fde68a;border-radius:8px;
                  padding:2px 10px;margin:0 6px;font-weight:800;color:#92400e;">🟡 Необов'язкове</span>
            «Опис прогресу», «Ризики», «Посилання на НПА»
        </div>
        """,
        unsafe_allow_html=True,
    )

    ind_df_table = pd.DataFrame(ind_table_rows)
    if ind_df_table.empty:
        st.info("За обраними параметрами індикаторів не знайдено.")
        st.stop()

    # ── Формат подання індикаторів: картка або таблиця ──
    ind_view_mode = st.radio(
        "Формат подання",
        ["🗂 Карткове подання (як у Картці заходу)", "🧾 Табличне подання"],
        horizontal=True,
        key="indicators_form_view_mode",
    )

    if ind_view_mode.startswith("🗂"):
        def _ind_option_label(r):
            mark = " · ⏳ у процесі погодження" if r["_locked"] else ""
            return f"{r['Код']} — {str(r['Індикатор'])[:80]}{mark}"

        ind_card_labels = [_ind_option_label(r) for _, r in ind_df_table.iterrows()]
        ind_pick = st.selectbox(
            "Показник для подання",
            ind_card_labels,
            key=f"ind_card_pick_{ind_ssp_index}_{ind_year}",
        )
        icr = ind_df_table.iloc[ind_card_labels.index(ind_pick)]

        def _ipcell(label, value):
            v = clean_value(value) or "—"
            return (f'<div style="background:#f8fafc;border:1px solid #e2e8f0;'
                    f'border-radius:12px;padding:10px 12px;">'
                    f'<div style="font-size:10px;font-weight:800;letter-spacing:.05em;'
                    f'text-transform:uppercase;color:#64748b;margin-bottom:4px;">{label}</div>'
                    f'<div style="font-size:13px;font-weight:700;color:#0f172a;'
                    f'line-height:1.35;">{v}</div></div>')

        st.markdown(
            f'''
            <div style="background:#ffffff;border:1px solid #d8dee9;border-radius:16px;
                        padding:18px 20px;margin:14px 0 8px 0;">
              <div style="font-size:11px;font-weight:900;letter-spacing:.08em;color:#1d4ed8;
                          text-transform:uppercase;margin-bottom:6px;">Паспорт показника · {clean_value(icr["Код"])}</div>
              <div style="font-size:17px;font-weight:900;color:#0f172a;line-height:1.35;
                          margin-bottom:14px;">{clean_value(icr["Індикатор"])}</div>
              <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;">
                {_ipcell("СЦ / Завдання", icr["СЦ / Завдання"])}
                {_ipcell("Одиниці виміру", icr["Одиниці" + chr(10) + "виміру"])}
                {_ipcell("2021 (базовий)", icr["2021" + chr(10) + "(базовий)"])}
                {_ipcell(f"{ind_year} (цільовий орієнтир)", icr[f"{ind_year}" + chr(10) + "(цільовий орієнтир)"])}
                {_ipcell("Останнє подане значення", icr["Останнє подане" + chr(10) + "значення"])}
              </div>
            </div>
            ''',
            unsafe_allow_html=True,
        )

        if bool(icr["_locked"]):
            st.info("За цим показником подання вже перебуває в процесі погодження — "
                    "повторне подання стане доступним після завершення процесу.")
        else:
            def _iblock_open(title, required=True):
                color = "#fda4a5" if required else "#fde68a"
                bg = "#fff7f7" if required else "#fffdf3"
                mark = "🔴" if required else "🟡"
                st.markdown(
                    f'<div style="border:2px solid {color};background:{bg};border-radius:14px;'
                    f'padding:12px 14px 4px 14px;margin:10px 0 4px 0;">'
                    f'<div style="font-size:12px;font-weight:900;color:#0f172a;'
                    f'margin-bottom:4px;">{mark} {title}</div>',
                    unsafe_allow_html=True,
                )

            _ind_key_sfx = f"{ind_ssp_index}_{ind_year}_{raw_value(icr['Код'])}_{normalize_key(raw_value(icr['Індикатор']))}"

            _iblock_open(f"Значення станом на {ind_as_of.strftime('%d.%m.%Y')}", required=True)
            ind_card_value = st.text_input(
                "Фактичне значення показника", key=f"indcard_value_{_ind_key_sfx}",
            )
            st.markdown('</div>', unsafe_allow_html=True)

            _iblock_open("Статус виконання", required=True)
            ind_card_status = st.selectbox(
                "Статус виконання", execution_status_options,
                key=f"indcard_status_{_ind_key_sfx}",
            )
            st.markdown('</div>', unsafe_allow_html=True)

            _iblock_open("Опис прогресу", required=False)
            ind_card_progress = st.text_area(
                "Короткий опис прогресу", height=100, key=f"indcard_progress_{_ind_key_sfx}",
            )
            st.markdown('</div>', unsafe_allow_html=True)

            _iblock_open("Ризики / проблеми / відхилення", required=False)
            ind_card_risks = st.text_area(
                "Ризики / проблеми (за наявності)", height=90, key=f"indcard_risks_{_ind_key_sfx}",
            )
            st.markdown('</div>', unsafe_allow_html=True)

            _iblock_open("Посилання на НПА / джерела", required=False)
            ind_card_npa = st.text_area(
                "Посилання (по одному в рядку)", height=80, key=f"indcard_npa_{_ind_key_sfx}",
            )
            st.markdown('</div>', unsafe_allow_html=True)

            ind_card_scheme, ind_card_chain, ind_card_ready = render_scheme_picker(
                ind_ssp_index, "indcard"
            )

            if st.button("Подати значення показника на розгляд",
                         use_container_width=True, key=f"indcard_submit_{_ind_key_sfx}"):
                _errs = []
                if not raw_value(responsible_person):
                    _errs.append("Заповніть ПІБ відповідальної особи")
                if not raw_value(responsible_email):
                    _errs.append("Заповніть електронну пошту відповідальної особи")
                if not raw_value(ind_card_value):
                    _errs.append("Заповніть обов'язковий блок зі значенням показника")
                if not raw_value(ind_card_status):
                    _errs.append("Заповніть обов'язковий блок «Статус виконання»")
                if not ind_card_ready:
                    _errs.append("Схема погодження неповна: для однієї з ланок не знайдено користувача")
                if _errs:
                    for e in _errs:
                        st.error(e)
                else:
                    as_of_iso = ind_as_of.isoformat()
                    quarter_roman = {1: "I", 2: "II", 3: "III", 4: "IV"}[(ind_as_of.month - 1) // 3 + 1]
                    item = {
                        "object_name": raw_value(icr["СЦ / Завдання"]),
                        "indicator_name": raw_value(icr["Індикатор"]),
                        "department": raw_value(ind_ssp_index),
                        "year": str(ind_year),
                        "quarter": quarter_roman,
                        "approval_status": (
                            schemes.waiting_status_for_stage(ind_card_chain[0])
                            if ind_card_chain else "Очікує погодження"
                        ),
                        "status": raw_value(ind_card_status),
                        "strat_code": raw_value(icr["Код"]),
                        "responsible_person": raw_value(responsible_person),
                        "phone": raw_value(responsible_phone),
                        "email": raw_value(responsible_email),
                        "numeric_value": raw_value(ind_card_value),
                        "progress_text": raw_value(ind_card_progress),
                        "risks": raw_value(ind_card_risks),
                        "file_names": "", "file_urls": "", "admin_comment": "",
                        "start_date": "", "end_date": "",
                        "submitted_at": datetime.now(timezone.utc).isoformat(),
                    }
                    if npa_link_column_exists:
                        item["npa_link"] = "\n".join(
                            [u.strip() for u in raw_value(ind_card_npa).splitlines() if u.strip()]
                        )
                    if kind_column_exists:
                        item["object_kind"] = "indicator"
                        item["as_of_date"] = as_of_iso
                    if ind_card_chain:
                        item["approval_chain"] = schemes.chain_to_json(ind_card_chain)
                        item["chain_stage"] = 0
                        item["scheme_label"] = ind_card_scheme
                    try:
                        supabase.table("monitoring_requests").insert(item).execute()
                        st.cache_data.clear()
                        notify_first_stage(
                            ind_card_chain, [item["strat_code"]],
                            str(ind_year),
                            f"станом на {ind_as_of.strftime('%d.%m.%Y')}",
                            kind="indicator",
                        )
                        st.success("Значення показника подано на розгляд.")
                        st.rerun()
                    except Exception as error:
                        st.error(f"Не вдалося подати значення. Технічна помилка: {error}")

        render_footer()
        st.stop()

    ind_locked_count = int(ind_df_table["_locked"].sum())
    if ind_locked_count:
        st.markdown(
            f'<div class="note-box" style="background:#fef9c3;border:1px solid #fde047;color:#713f12;">'
            f'За {ind_locked_count} індикатором(ами) подання за {ind_year} рік уже перебуває '
            f'в процесі погодження — повторне подання стане доступним після завершення процесу.</div>',
            unsafe_allow_html=True,
        )

    ind_display_cols = [c for c in ind_df_table.columns if not c.startswith("_")]
    ind_edited = st.data_editor(
        ind_df_table,
        key=f"indicator_editor_{ind_ssp_index}_{ind_year}",
        use_container_width=True, hide_index=True,
        height=min(760, max(220, 110 + len(ind_df_table) * 72)),
        row_height=72, num_rows="fixed",
        column_order=ind_display_cols,
        disabled=[
            "Код", "СЦ / Завдання", "Індикатор", "Одиниці\nвиміру",
            "2021\n(базовий)", f"{ind_year}\n(цільовий орієнтир)", "Останнє подане\nзначення",
        ],
        column_config={
            "Подати": st.column_config.CheckboxColumn("Подати", width=80),
            value_col: st.column_config.TextColumn(f"🔴 {value_col}", width=150,
                help="Обов'язкове поле. Фактичне значення індикатора станом на обрану дату"),
            "Статус\nвиконання": st.column_config.SelectboxColumn(
                "🔴 Статус\nвиконання", options=execution_status_options, width=180,
                help="Обов'язкове поле"),
            "Опис\nпрогресу": st.column_config.TextColumn("🟡 Опис\nпрогресу", width=280,
                help="Необов'язкове поле"),
            "Ризики / проблеми /\nвідхилення": st.column_config.TextColumn(
                "🟡 Ризики / проблеми /\nвідхилення", width=280, help="Необов'язкове поле"),
            "Посилання\nна НПА": st.column_config.TextColumn(
                "🟡 Посилання\nна НПА", width=220,
                help="Необов'язкове. Кілька посилань — через кому або крапку з комою"),
            "_locked": st.column_config.CheckboxColumn("_locked", width=1),
        },
    )

    ind_scheme_name, ind_chain, ind_scheme_ready = render_scheme_picker(ind_ssp_index, "ind")

    if st.button("Подати значення індикаторів на розгляд", use_container_width=True, key="ind_submit"):
        ind_errors = []
        if not raw_value(responsible_person):
            ind_errors.append("Заповніть ПІБ відповідальної особи")
        if not raw_value(responsible_email):
            ind_errors.append("Заповніть електронну пошту відповідальної особи")
        if not ind_scheme_ready:
            ind_errors.append("Схема погодження неповна: для однієї з ланок не знайдено користувача")

        ind_selected = ind_edited[(ind_edited["Подати"] == True) & (ind_edited["_locked"] == False)].copy()
        if ind_selected.empty:
            ind_errors.append("Позначте хоча б один індикатор для подання")
        else:
            for _, r in ind_selected.iterrows():
                for field in ind_required_cols:
                    if not raw_value(r.get(field, "")):
                        ind_errors.append(
                            f"У індикаторі {raw_value(r.get('Код'))} не заповнено обов'язкове поле "
                            f"«{field.replace(chr(10), ' ')}»."
                        )

        if ind_errors:
            for e in ind_errors:
                st.error(e)
        else:
            as_of_iso = ind_as_of.isoformat()
            quarter_roman = {1: "I", 2: "II", 3: "III", 4: "IV"}[(ind_as_of.month - 1) // 3 + 1]
            submitted_at = datetime.now(timezone.utc).isoformat()
            first_status = schemes.waiting_status_for_stage(ind_chain[0]) if ind_chain else "Очікує погодження"

            ind_payload = []
            for _, r in ind_selected.iterrows():
                item = {
                    # П7/П8: знімки назв на момент подання
                    "object_name": raw_value(r.get("СЦ / Завдання", "")),
                    "indicator_name": raw_value(r.get("Індикатор", "")),
                    "department": raw_value(ind_ssp_index),
                    "year": str(ind_year),
                    "quarter": quarter_roman,
                    "approval_status": first_status,
                    "status": raw_value(r.get("Статус\nвиконання", "")),
                    "strat_code": raw_value(r.get("Код", "")),
                    "responsible_person": raw_value(responsible_person),
                    "phone": raw_value(responsible_phone),
                    "email": raw_value(responsible_email),
                    "numeric_value": raw_value(r.get(value_col, "")),
                    "progress_text": raw_value(r.get("Опис\nпрогресу", "")),
                    "risks": raw_value(r.get("Ризики / проблеми /\nвідхилення", "")),
                    "file_names": "", "file_urls": "", "admin_comment": "",
                    "start_date": "", "end_date": "",
                    "submitted_at": submitted_at,
                }
                if npa_link_column_exists:
                    item["npa_link"] = raw_value(r.get("Посилання\nна НПА", ""))
                if kind_column_exists:
                    item["object_kind"] = "indicator"
                    item["as_of_date"] = as_of_iso
                if chain_columns_exist and ind_chain:
                    item["approval_chain"] = schemes.chain_to_json(ind_chain)
                    item["chain_stage"] = 0
                    item["scheme_label"] = ind_scheme_name
                ind_payload.append(item)

            try:
                supabase.table("monitoring_requests").insert(ind_payload).execute()
                st.cache_data.clear()
                notify_first_stage(
                    ind_chain, [p["strat_code"] for p in ind_payload],
                    str(ind_year), f"станом на {ind_as_of.strftime('%d.%m.%Y')}", kind="indicator",
                )
                st.success("Значення індикаторів успішно подано на розгляд за обраною схемою погодження.")
            except Exception as error:
                st.error(f"Не вдалося подати значення індикаторів. Технічна помилка: {error}")

    st.stop()


# ------------------------------------------------------------
# Flow block
# ------------------------------------------------------------

st.markdown(
    """
    <div class="flow-box">
        <div class="flow-title">Маршрут подання відомостей</div>
        <div class="flow-steps">
            <div class="flow-step">1. Вибір параметрів</div>
            <div class="flow-step">2. Перегляд</div>
            <div class="flow-step">3. Позначення заходу</div>
            <div class="flow-step">4. Заповнення</div>
            <div class="flow-step">5. Відправлення на розгляд</div>
            <div class="flow-step">6. Погодження</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# User guide / filters
# ------------------------------------------------------------

st.markdown(
    """
    <div class="filter-box">
        <div class="filter-title">Гід користувача</div>
        <div class="filter-legend">
            Оберіть індекс самостійного структурнго підрозділу та звітний період. 
            Система автоматично відобразить лише ті заходи, за якими самостійний 
            структурний підрозділ, визначений головним виконавцем або співвиконавцем.
        </div>
        <div class="info-grid">
            <div class="info-card">
                <div class="info-card-title">Інструкція користувача</div>
                <div class="instruction-item">1. Позначте у першій колонці таблиці «Подати» заходи, за якими подається інформація</div>
                <div class="instruction-item">2. Внесіть фактичні звітні відомості (показники, стан виконання, короткий опис прогресу та інформацію щодо ризиків)</div>
                <div class="instruction-item">3. Натисніть «Подати на розгляд»</div>
                <div class="instruction-item">4. Після розгляду відомостей, координатор направить інформацію на погодження (відповідальний виконавець, керівник ССП)</div>
            </div>
        </div>
    """,
    unsafe_allow_html=True
)

f1, f2, f3, f4 = st.columns([1.25, 0.7, 0.7, 1.6])

with f1:
    if available_ssp_indices:
        selected_ssp_index = st.selectbox(
            "Індекс самостійного структурного підрозділу",
            available_ssp_indices,
            index=0,
            key="ssp_submit_filter",
            placeholder="Оберіть індекс ССП",
            disabled=ssp_select_disabled,
        )
    else:
        selected_ssp_index = ""
        st.warning("Для цього користувача не визначено доступний індекс ССП.")

with f2:
    selected_year = st.selectbox(
        "Рік",
        year_options,
        index=0,
        key="year_submit_filter"
    )

with f3:
    selected_quarter = st.selectbox(
        "Квартал",
        quarter_options,
        index=0,
        key="quarter_submit_filter"
    )

with f4:
    search_query = st.text_input(
        "Додаткові параметри пошуку (код завдання, заходу, ключові слова)",
        key="search_submit_filter",
        placeholder="Введіть код, назву або ключове слово"
    )

st.markdown("</div>", unsafe_allow_html=True)


# ------------------------------------------------------------
# Filtering
# ------------------------------------------------------------

filtered_measures = filter_actions_for_user(
    all_measures,
    current_user,
    executor_columns=["resp_main", "resp_co_1"],
)

if selected_ssp_index:
    filtered_measures = filtered_measures[
        filtered_measures.apply(
            lambda row: (
                value_contains_ssp(row.get("resp_main", ""), selected_ssp_index)
                or value_contains_ssp(row.get("resp_co_1", ""), selected_ssp_index)
            ),
            axis=1,
        )
    ]

filtered_measures = filtered_measures[
    filtered_measures.apply(lambda row: row_matches_search(row, search_query), axis=1)
]

filtered_measures = filtered_measures[
    filtered_measures.apply(lambda row: has_target_for_year(row, selected_year), axis=1)
]

filtered_codes = filtered_measures["code"].astype(str).str.strip().tolist()
monitoring_selected = subset_monitoring_for_selection(
    monitoring_df,
    filtered_codes,
    selected_year,
    selected_quarter
)


# ------------------------------------------------------------
# Selection parameters summary
# ------------------------------------------------------------

total_count = len(filtered_measures)
submitted_count = unique_measure_count(monitoring_selected)

if monitoring_selected.empty:
    reviewed_count = 0
    waiting_count = 0
    returned_count = 0
    approved_count = 0
else:
    monitoring_selected["visual_status"] = monitoring_selected.apply(get_record_visual_status, axis=1)

    reviewed_count = unique_measure_count(
        monitoring_selected[
            monitoring_selected["visual_status"].isin(["Погоджено", "Повернуто на доопрацювання"])
        ]
    )

    waiting_count = unique_measure_count(
        monitoring_selected[
            monitoring_selected["visual_status"] == "Очікує розгляду"
        ]
    )

    returned_count = unique_measure_count(
        monitoring_selected[
            monitoring_selected["visual_status"] == "Повернуто на доопрацювання"
        ]
    )

    approved_count = unique_measure_count(
        monitoring_selected[
            monitoring_selected["visual_status"] == "Погоджено"
        ]
    )

summary_cards = "".join([
    make_summary_card("Заходів усього", total_count),
    make_summary_card("Поданих відомостей за заходами", submitted_count),
    make_summary_card("Розглянуто", reviewed_count),
    make_summary_card("Очікує розгляду", waiting_count),
    make_summary_card("Повернуто на доопрацювання", returned_count),
    make_summary_card("Погоджено", approved_count)
])

st.markdown(
    f"""
    <div class="summary-box">
        <div class="summary-title">Параметри відбору</div>
        <div class="summary-grid">{summary_cards}</div>
    </div>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# Status notes
# ------------------------------------------------------------

st.markdown(
    """
    <div class="status-row">
        <div class="status-pill status-green">
            <span class="status-dot"></span>
            Редагування звітних даних активне
        </div>
        <div class="status-pill status-blue">
            <span class="status-dot"></span>
            Відомості відображаються автоматично
        </div>
        <div class="status-pill status-orange">
            <span class="status-dot"></span>
            Перед поданням система виконає перевірку коректності та повноти даних
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="info-card" style="margin-bottom:14px;">
        <div class="info-card-title">Легенда обов'язковості полів</div>
        <div class="legend-item">🟥 Обов'язкове поле для заповнення (квартальне значення, статус виконання, опис прогресу)</div>
        <div class="legend-item">🟨 Опційне поле, не обов'язкове (ризики/проблеми/відхилення, посилання на НПА)</div>
    </div>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# Формат подання: таблиця або картка (нове)
# ------------------------------------------------------------

form_view_mode = st.radio(
    "Формат подання",
    ["🗂 Карткове подання (як у Картці заходу)", "🧾 Табличне подання"],
    horizontal=True,
    key="measures_form_view_mode",
)

if form_view_mode.startswith("🗂"):
    # ========================================================
    # КАРТКОВЕ ПОДАННЯ: один захід за раз, паспорт + кольорові блоки
    # ========================================================
    quarter_label = f"{quarter_to_q_label(selected_quarter)} {selected_year}"
    card_target_col = f"target_{selected_year}"
    if card_target_col not in filtered_measures.columns:
        filtered_measures[card_target_col] = ""

    if filtered_measures.empty:
        st.info("За обраними параметрами немає заходів, доступних для подання.")
        render_footer()
        st.stop()

    # Індекс уже поданих заявок цього періоду (лок, як у таблиці)
    card_submitted_map = {}
    if not monitoring_df.empty:
        _cmask = (
            (monitoring_df["year"].astype(str).str.strip() == str(selected_year))
            & (monitoring_df["quarter"].astype(str).str.strip() == str(selected_quarter))
        )
        for _, _mrow in monitoring_df[_cmask].iterrows():
            if raw_value(_mrow.get("object_kind", "")).lower() == "indicator":
                continue
            _ck = raw_value(_mrow.get("strat_code", ""))
            if _ck and _ck not in card_submitted_map:
                card_submitted_map[_ck] = _mrow
    card_closeouts = load_manual_closeouts()

    def _card_option_label(r):
        c = raw_value(r.get("code", ""))
        nm = strip_leading_code(r.get("name", ""), c)
        mark = ""
        ex = card_submitted_map.get(c)
        if (c, str(selected_year), str(selected_quarter)) in card_closeouts:
            mark = " · 🔒 закрито вручну"
        elif ex is not None:
            mark = (" · ✅ погоджено"
                    if raw_value(ex.get("approval_status")) == "Погоджено"
                    else " · ⏳ на розгляді")
        return f"{c} — {nm[:90]}{mark}"

    card_measures = filtered_measures.reset_index(drop=True)
    card_labels = [_card_option_label(r) for _, r in card_measures.iterrows()]
    picked_label = st.selectbox(
        f"Захід ССП {selected_ssp_index} для подання",
        card_labels,
        key="card_measure_pick",
    )
    card_row = card_measures.iloc[card_labels.index(picked_label)]
    card_code = raw_value(card_row.get("code", ""))
    card_name = strip_leading_code(card_row.get("name", ""), card_code)

    _existing = card_submitted_map.get(card_code)
    _closed = (card_code, str(selected_year), str(selected_quarter)) in card_closeouts
    _locked = _closed or (_existing is not None)

    # ── Паспорт заходу (як у Картці заходу) ──
    def _pcell(label, value):
        v = clean_value(value) or "—"
        return (f'<div style="background:#f8fafc;border:1px solid #e2e8f0;'
                f'border-radius:12px;padding:10px 12px;">'
                f'<div style="font-size:10px;font-weight:800;letter-spacing:.05em;'
                f'text-transform:uppercase;color:#64748b;margin-bottom:4px;">{label}</div>'
                f'<div style="font-size:13px;font-weight:700;color:#0f172a;'
                f'line-height:1.35;">{v}</div></div>')

    st.markdown(
        f'''
        <div style="background:#ffffff;border:1px solid #d8dee9;border-radius:16px;
                    padding:18px 20px;margin:14px 0 8px 0;">
          <div style="font-size:11px;font-weight:900;letter-spacing:.08em;color:#1d4ed8;
                      text-transform:uppercase;margin-bottom:6px;">Паспорт заходу · {card_code}</div>
          <div style="font-size:19px;font-weight:900;color:#0f172a;line-height:1.3;
                      margin-bottom:14px;">{clean_value(card_name)}</div>
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;">
            {_pcell("Тип продукту", card_row.get("product_type"))}
            {_pcell("Індикатор", card_row.get("indicator"))}
            {_pcell("Одиниці виміру", card_row.get("unit"))}
            {_pcell("Головний виконавець", card_row.get("resp_main"))}
            {_pcell("Співвиконавець", card_row.get("resp_co_1"))}
            {_pcell(f"Цільовий орієнтир {selected_year}", card_row.get(card_target_col))}
            {_pcell("2021 (базовий)", card_row.get("base_2021"))}
            {_pcell("2024 (звіт)", card_row.get("fact_2024"))}
            {_pcell("Початок виконання", card_row.get("measure_start_date"))}
            {_pcell("Кінець виконання", card_row.get("measure_end_date"))}
          </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    if _locked:
        if _closed:
            st.info("🔒 Захід закрито вручну адміністратором за цей період — подання недоступне.")
        else:
            _ap = raw_value(_existing.get("approval_status"))
            st.info(f"За цей період уже є заявка (статус погодження: «{_ap}»). "
                    "Повторне подання можливе після повернення на доопрацювання "
                    "у вкладці «Мої заявки».")
    else:
        # ── Кольорові блоки подання: 🔴 обовʼязкові · 🟡 необовʼязкові ──
        st.markdown(
            '''<div class="note-box" style="background:#f8fafc;border:1px solid #d8dee9;">
            <b>Легенда:</b>
            <span style="background:#fde8e8;border:1px solid #fca5a5;border-radius:8px;
                  padding:2px 10px;margin:0 6px;font-weight:800;color:#991b1b;">🔴 Обов'язковий блок</span>
            <span style="background:#fef6e0;border:1px solid #fde68a;border-radius:8px;
                  padding:2px 10px;margin:0 6px;font-weight:800;color:#92400e;">🟡 Необов'язковий блок</span>
            </div>''',
            unsafe_allow_html=True,
        )

        def _block_open(title, required=True):
            color = ("#fda4a5" if required else "#fde68a")
            bg = ("#fff7f7" if required else "#fffdf3")
            mark = "🔴" if required else "🟡"
            st.markdown(
                f'<div style="border:2px solid {color};background:{bg};border-radius:14px;'
                f'padding:12px 14px 4px 14px;margin:10px 0 4px 0;">'
                f'<div style="font-size:12px;font-weight:900;color:#0f172a;'
                f'margin-bottom:4px;">{mark} {title}</div>',
                unsafe_allow_html=True,
            )

        def _block_close():
            st.markdown('</div>', unsafe_allow_html=True)

        _block_open(f"Квартальні дані · {quarter_label}", required=True)
        card_value = st.text_input(
            f"Фактичне значення за {quarter_label}",
            key=f"card_value_{card_code}_{selected_year}_{selected_quarter}",
            placeholder="Наприклад: 120 або так/ні",
        )
        _block_close()

        _block_open("Статус виконання", required=True)
        card_status = st.selectbox(
            "Статус виконання заходу",
            execution_status_options,
            key=f"card_status_{card_code}_{selected_year}_{selected_quarter}",
        )
        _block_close()

        _block_open("Опис прогресу", required=True)
        card_progress = st.text_area(
            "Короткий опис прогресу виконання",
            height=110,
            key=f"card_progress_{card_code}_{selected_year}_{selected_quarter}",
        )
        _block_close()

        _block_open("Ризики / проблеми / відхилення", required=False)
        card_risks = st.text_area(
            "Ризики, проблеми або відхилення (за наявності)",
            height=90,
            key=f"card_risks_{card_code}_{selected_year}_{selected_quarter}",
        )
        _block_close()

        _block_open("Посилання на НПА / джерела", required=False)
        card_npa = st.text_area(
            "Посилання (по одному в рядку)",
            height=80,
            key=f"card_npa_{card_code}_{selected_year}_{selected_quarter}",
            placeholder="https://zakon.rada.gov.ua/…",
        )
        _block_close()

        # ── Схема погодження (та сама, що в табличному режимі) ──
        card_scheme_name, card_chain, card_scheme_ready = render_scheme_picker(
            selected_ssp_index, "card"
        )

        if st.button("Подати відомості на розгляд", use_container_width=True,
                     key=f"card_submit_{card_code}"):
            card_errors = []
            if not raw_value(responsible_person):
                card_errors.append("Заповніть ПІБ відповідальної особи")
            if not raw_value(responsible_phone):
                card_errors.append("Заповніть контактний номер телефону")
            if not raw_value(responsible_email):
                card_errors.append("Заповніть електронну пошту відповідальної особи")
            if not raw_value(card_value):
                card_errors.append(f"Заповніть обов'язковий блок «Квартальні дані · {quarter_label}»")
            if not raw_value(card_status):
                card_errors.append("Заповніть обов'язковий блок «Статус виконання»")
            if not raw_value(card_progress):
                card_errors.append("Заповніть обов'язковий блок «Опис прогресу»")
            if chain_columns_exist and not card_scheme_ready:
                card_errors.append("Схема погодження неповна: для однієї з ланок не знайдено користувача")

            if card_errors:
                for e in card_errors:
                    st.error(e)
            else:
                submitted_at = datetime.now(timezone.utc).isoformat()
                first_stage_status = (
                    schemes.waiting_status_for_stage(card_chain[0])
                    if (chain_columns_exist and card_chain)
                    else "Очікує погодження"
                )
                card_payload = {
                    "object_name":        raw_value(card_name),
                    "department":         raw_value(selected_ssp_index),
                    "year":               str(selected_year),
                    "quarter":            raw_value(selected_quarter),
                    "approval_status":    first_stage_status,
                    "status":             raw_value(card_status),
                    "strat_code":         card_code,
                    "responsible_person": raw_value(responsible_person),
                    "phone":              raw_value(responsible_phone),
                    "email":              raw_value(responsible_email),
                    "numeric_value":      raw_value(card_value),
                    "progress_text":      raw_value(card_progress),
                    "risks":              raw_value(card_risks),
                    "file_names": "", "file_urls": "", "admin_comment": "",
                    # Дати виконання — зі стратегічної матриці (як у таблиці)
                    "start_date": raw_value(card_row.get("measure_start_date", "")),
                    "end_date":   raw_value(card_row.get("measure_end_date", "")),
                    "submitted_at":       submitted_at,
                }
                if npa_link_column_exists:
                    card_payload["npa_link"] = "\n".join(
                        [u.strip() for u in raw_value(card_npa).splitlines() if u.strip()]
                    )
                if kind_column_exists:
                    card_payload["object_kind"] = "measure"
                if chain_columns_exist and card_chain:
                    card_payload["approval_chain"] = schemes.chain_to_json(card_chain)
                    card_payload["chain_stage"] = 0
                    card_payload["scheme_label"] = card_scheme_name
                try:
                    supabase.table("monitoring_requests").insert(card_payload).execute()
                    st.cache_data.clear()
                    notify_first_stage(
                        card_chain, [card_code],
                        str(selected_year), raw_value(selected_quarter), kind="measure",
                    )
                    st.success(
                        f"Відомості щодо заходу {card_code} подано на розгляд "
                        f"за схемою «{card_scheme_name}»."
                    )
                    st.rerun()
                except Exception as error:
                    st.error(f"Не вдалося подати відомості. Технічна помилка: {error}")

    render_footer()
    st.stop()


# ------------------------------------------------------------
# One editable table
# ------------------------------------------------------------

quarter_label = f"{quarter_to_q_label(selected_quarter)} {selected_year}"
target_col = f"target_{selected_year}"

if target_col not in filtered_measures.columns:
    filtered_measures[target_col] = ""

# Динамічні назви колонок для років
def year_col_label(year, role):
    """role: 'fact' | 'report' | 'target'"""
    labels = {"fact": "факт", "report": "звіт", "target": "цільовий орієнтир"}
    return f"{year}\n({labels.get(role, role)})"

col_2021  = year_col_label(2021, "fact")
col_2024  = year_col_label(2024, "report")
col_2025  = year_col_label(2025, "fact")
col_target = year_col_label(selected_year, "target")

# Індекс підтягнутих заявок із Supabase для цього кварталу
# key: strat_code → рядок моніторингу (перший знайдений)
submitted_map = {}
if not monitoring_df.empty:
    mask = (
        (monitoring_df["year"].astype(str).str.strip()    == str(selected_year))
        & (monitoring_df["quarter"].astype(str).str.strip() == str(selected_quarter))
    )
    period_df = monitoring_df[mask].copy()
    for _, mrow in period_df.iterrows():
        if raw_value(mrow.get("object_kind", "")).lower() == "indicator":
            continue
        code_key = raw_value(mrow.get("strat_code", ""))
        if code_key and code_key not in submitted_map:
            submitted_map[code_key] = mrow

manual_closeouts = load_manual_closeouts()

table_rows = []
locked_cols_per_row = {}   # code -> list of column names that must be disabled

for _, row in filtered_measures.iterrows():
    code = raw_value(row.get("code", ""))
    deputy = get_deputy_for_ssp(extract_ssp_index(row.get("resp_main", "")))

    # Чи є вже подана заявка?
    existing = submitted_map.get(code)
    is_locked = existing is not None
    is_approved = is_locked and raw_value(existing.get("approval_status", "")) == "Погоджено"
    is_manually_closed = (code, str(selected_year), str(selected_quarter)) in manual_closeouts

    if is_manually_closed:
        is_locked = True

    if is_locked:
        q_fact_val   = raw_value(existing.get("numeric_value", "")) if existing is not None else ""
        status_val   = raw_value(existing.get("status", "")) if existing is not None else ""
        progress_val = raw_value(existing.get("progress_text", "")) if existing is not None else ""
        risks_val    = raw_value(existing.get("risks", "")) if existing is not None else ""
        npa_link_val = raw_value(existing.get("npa_link", "")) if existing is not None else ""
        if is_manually_closed:
            lock_label = "🔒 Закрито вручну"
        else:
            lock_label = "✅ Погоджено" if is_approved else "⏳ На розгляді"
    else:
        q_fact_val = status_val = progress_val = risks_val = npa_link_val = ""
        lock_label = ""

    table_rows.append({
        "Подати":      not is_locked,   # checkbox: True тільки для нових
        "Код":         code,
        "Захід":       strip_leading_code(row.get("name", ""), code),
        "Тип\nпродукту":   raw_value(row.get("product_type", "")),
        "Індикатор":   raw_value(row.get("indicator", "")),
        "Одиниці\nвиміру": raw_value(row.get("unit", "")),

        col_2021:   raw_value(row.get("base_2021", "")),
        col_2024:   raw_value(row.get("fact_2024", "")),
        col_2025:   raw_value(row.get("fact_2025", "")),
        col_target: raw_value(row.get(target_col, "")),
        quarter_label: q_fact_val,

        "Глобальний\nрівень":    raw_value(row.get("source_global", "")),
        "Національний\nрівень":  raw_value(row.get("source_national", "")),

        "Головний\nвиконавець":  raw_value(row.get("resp_main", "")),
        "Співвиконавець":       raw_value(row.get("resp_co_1", "")),

        "Початкова\nдата":  raw_value(row.get("measure_start_date", "")),
        "Кінцева\nдата":    raw_value(row.get("measure_end_date", "")),
        "Заступник\nМіністра": deputy,

        "Статус\nвиконання":               status_val,
        "Опис\nпрогресу":                  progress_val,
        "Ризики / проблеми /\nвідхилення": risks_val,
        "Посилання\nна НПА":               npa_link_val,
        "_locked": is_locked,
        "_lock_label": lock_label,
    })

table_df = pd.DataFrame(table_rows)

# Колонки які завжди disabled (інформаційні)
always_disabled = [
    "Код", "Захід", "Тип\nпродукту", "Індикатор", "Одиниці\nвиміру",
    col_2021, col_2024, col_2025, col_target,
    "Глобальний\nрівень", "Національний\nрівень",
    "Головний\nвиконавець", "Співвиконавець",
    "Початкова\nдата", "Кінцева\nдата", "Заступник\nМіністра",
]

# Колонки для редагування
editable_cols = [
    quarter_label, "Статус\nвиконання", "Опис\nпрогресу",
    "Ризики / проблеми /\nвідхилення", "Посилання\nна НПА",
]
# Обов'язкові редаговані поля (опційні — не блокують подання)
# Уніфіковано з картковим режимом та адмін-перевіркою якості:
# «Опис прогресу» — обовʼязкове поле в ОБОХ режимах подання заходів.
required_editable_cols = [quarter_label, "Статус\nвиконання", "Опис\nпрогресу"]
optional_editable_cols = ["Опис\nпрогресу", "Ризики / проблеми /\nвідхилення", "Посилання\nна НПА"]

# Для рядків із поданими заявками — теж блокуємо редаговані колонки
# Робимо це через окремий DataFrame: locked і free рядки
locked_mask  = table_df["_locked"] == True
free_mask    = ~locked_mask

# Прихований ознаковий стовпець (_locked, _lock_label) не показуємо
display_cols = [c for c in table_df.columns if not c.startswith("_")]
# Але залишаємо _locked у даних для логіки submit — просто ховаємо через column_config

st.markdown('<div class="table-title">Заходи для внесення відомостей</div>', unsafe_allow_html=True)

if table_df.empty:
    st.info("За обраними параметрами заходів не знайдено.")
    edited_df = pd.DataFrame()
else:
    # Якщо є заблоковані рядки — показати інфо-банер
    locked_count = int(locked_mask.sum())
    if locked_count:
        approved_count_lock = int((table_df["_lock_label"].str.contains("Погоджено")).sum())
        pending_count_lock  = locked_count - approved_count_lock
        parts = []
        if pending_count_lock:
            parts.append(f"<strong>{pending_count_lock}</strong> ⏳ на розгляді")
        if approved_count_lock:
            parts.append(f"<strong>{approved_count_lock}</strong> ✅ погоджено")
        st.markdown(
            f'''<div class="note-box" style="background:#fef9c3;border:1px solid #fde047;color:#713f12;">
                За {locked_count} заходом(заходами) у {quarter_label} відомості вже подано: {", ".join(parts)}.
                Поля цих заходів заповнені поданими даними та <strong>заблоковані</strong> для редагування.
            </div>''',
            unsafe_allow_html=True
        )

    dynamic_height = min(820, max(220, 110 + len(table_df) * 80))

    # Всі колонки disabled для заблокованих рядків —
    # st.data_editor не підтримує per-row disabled, тому ділимо на два editor-и
    # АБО: передаємо disabled_rows через обхід — рядки locked підставляємо pre-filled
    # Найчистіший підхід: один editor, locked рядки мають ті ж значення що були,
    # а в validate_submission ми ігноруємо їх зміни

    # Колонки що завжди disabled + для locked рядків також editable_cols
    # Обхід: робимо locked рядки в окремому display, а редагований editor — тільки free рядки
    # Але тоді індекси не збігатимуться. Простіше — один editor з pre-filled locked значеннями
    # і валідація відкидає locked. Checkbox "Подати" для locked = False і disabled через initial value.

    col_config = {
        "Подати": st.column_config.CheckboxColumn(
            "Подати",
            help="Позначте незаблоковані заходи для подання",
            width=80,
        ),
        "Код": st.column_config.TextColumn("Код", disabled=True, width=80),
        "Захід": st.column_config.TextColumn("Захід", disabled=True, width=360),
        "Тип\nпродукту": st.column_config.TextColumn("Тип\nпродукту", disabled=True, width=160),
        "Індикатор": st.column_config.TextColumn("Індикатор", disabled=True, width=340),
        "Одиниці\nвиміру": st.column_config.TextColumn("Одиниці\nвиміру", disabled=True, width=100),

        col_2021:   st.column_config.TextColumn(col_2021,   disabled=True, width=120),
        col_2024:   st.column_config.TextColumn(col_2024,   disabled=True, width=120),
        col_2025:   st.column_config.TextColumn(col_2025,   disabled=True, width=120),
        col_target: st.column_config.TextColumn(col_target, disabled=True, width=140),
        quarter_label: st.column_config.TextColumn(
            f"🔴 {quarter_label}",
            help="Обов'язкове поле. Фактичне значення за обраний квартал",
            width=140,
        ),

        "Глобальний\nрівень":   st.column_config.TextColumn("Глобальний\nрівень",   disabled=True, width=270),
        "Національний\nрівень": st.column_config.TextColumn("Національний\nрівень", disabled=True, width=270),

        "Головний\nвиконавець": st.column_config.TextColumn("Головний\nвиконавець", disabled=True, width=180),
        "Співвиконавець":      st.column_config.TextColumn("Співвиконавець",      disabled=True, width=160),

        "Початкова\nдата":  st.column_config.TextColumn("Початкова\nдата",  disabled=True, width=120),
        "Кінцева\nдата":    st.column_config.TextColumn("Кінцева\nдата",    disabled=True, width=120),
        "Заступник\nМіністра": st.column_config.TextColumn("Заступник\nМіністра", disabled=True, width=200),

        "Статус\nвиконання": st.column_config.SelectboxColumn(
            "🔴 Статус\nвиконання",
            help="Обов'язкове поле",
            options=execution_status_options,
            required=False,
            width=190,
        ),
        "Опис\nпрогресу": st.column_config.TextColumn(
            "🔴 Опис\nпрогресу",
            help="Обов'язкове поле. Коротко опишіть фактичний прогрес за звітний квартал",
            width=300,
        ),
        "Ризики / проблеми /\nвідхилення": st.column_config.TextColumn(
            "🟡 Ризики / проблеми /\nвідхилення",
            help="Необов'язкове поле. Якщо ризиків немає, зазначте: відсутні",
            width=300,
        ),
        "Посилання\nна НПА": st.column_config.TextColumn(
            "🟡 Посилання\nна НПА",
            help="Необов'язкове. Основне посилання на НПА; додаткові — у блоці «➕ Додаткові посилання» під таблицею",
            width=220,
        ),
        # Приховані службові колонки
        "_locked":     st.column_config.CheckboxColumn("_locked",     width=1),
        "_lock_label": st.column_config.TextColumn("_lock_label", width=1),
    }

    # Редактор Streamlit малює таблицю на canvas, тому CSS-підсвітка клітинок
    # неможлива технічно. Обов'язковість позначаємо маркерами 🔴/🟡 просто
    # в заголовках колонок + кольоровою легендою перед таблицею.
    st.markdown(
        f"""
        <div class="note-box" style="background:#f8fafc;border:1px solid #d8dee9;">
            <b>Легенда обов'язковості полів:</b>
            <span style="background:#fde8e8;border:1px solid #fca5a5;border-radius:8px;
                  padding:2px 10px;margin:0 6px;font-weight:800;color:#991b1b;">🔴 Обов'язкові</span>
            «{quarter_label}» (квартальне значення), «Статус виконання», «Опис прогресу» — без них подання не пройде
            <span style="background:#fef6e0;border:1px solid #fde68a;border-radius:8px;
                  padding:2px 10px;margin:0 6px;font-weight:800;color:#92400e;">🟡 Необов'язкові</span>
            «Ризики / проблеми / відхилення», «Посилання на НПА»
        </div>
        """,
        unsafe_allow_html=True,
    )

    edited_df = st.data_editor(
        table_df,
        key=f"monitoring_editor_{selected_ssp_index}_{selected_year}_{selected_quarter}_{search_query}",
        use_container_width=True,
        hide_index=True,
        height=dynamic_height,
        row_height=80,
        num_rows="fixed",
        column_config=col_config,
        column_order=display_cols,   # приховуємо _locked/_lock_label
        disabled=always_disabled,
    )


# ------------------------------------------------------------
# Submission validation and submit
# ------------------------------------------------------------

def validate_submission():
    errors = []

    if not raw_value(responsible_person):
        errors.append("Заповніть ПІБ відповідальної особи")
    if not raw_value(responsible_phone):
        errors.append("Заповніть контактний номер телефону")
    if not raw_value(responsible_email):
        errors.append("Заповніть електронну пошту відповідальної особи")

    if chain_columns_exist and not measures_scheme_ready:
        errors.append("Схема погодження неповна: для однієї з ланок не знайдено користувача")

    if edited_df.empty:
        errors.append("Позначте хоча б один захід для подання")
        return errors

    # Беремо тільки рядки де Подати=True І захід НЕ заблокований
    selected_rows = edited_df[
        (edited_df["Подати"] == True) & (edited_df["_locked"] == False)
    ].copy()

    if selected_rows.empty:
        # Перевіримо чи взагалі щось позначено
        any_checked = edited_df[edited_df["Подати"] == True]
        if any_checked.empty:
            errors.append("Позначте хоча б один захід для подання")
        else:
            errors.append("Усі позначені заходи вже подані у цьому звітному періоді")
        return errors

    for _, row in selected_rows.iterrows():
        code = raw_value(row.get("Код", ""))
        missing_fields = [
            field for field in required_editable_cols
            if not raw_value(row.get(field, ""))
        ]
        for field_name in missing_fields:
            field_label = field_name.replace("\n", " ")
            errors.append(
                f"У заході {code} не заповнено поле «{field_label}». "
                "Виправте це та спробуйте подати інформацію ще раз."
            )

    return errors


# ------------------------------------------------------------
# Додаткові посилання на НПА («плюсик» до основної клітинки)
# ------------------------------------------------------------

_extra_npa_state_key = f"extra_npa_{selected_ssp_index}_{selected_year}_{selected_quarter}"
if _extra_npa_state_key not in st.session_state:
    st.session_state[_extra_npa_state_key] = {}   # code -> [url, url, ...]

extra_npa_links = st.session_state[_extra_npa_state_key]

if npa_link_column_exists and not table_df.empty:
    _free_codes = table_df.loc[table_df["_locked"] == False, "Код"].tolist()
    with st.expander("➕ Додаткові посилання на НПА (якщо їх декілька для одного заходу)"):
        st.caption(
            "Основне посилання вноситься в колонку «🟡 Посилання на НПА» таблиці. "
            "Тут можна додати до заходу будь-яку кількість додаткових посилань — "
            "усі вони збережуться в заявці та відображатимуться клікабельними "
            "в кабінетах і журналі дій."
        )
        if _free_codes:
            add_c1, add_c2, add_c3 = st.columns([1, 2.4, 0.7])
            with add_c1:
                _npa_code = st.selectbox("Захід", _free_codes, key=f"{_extra_npa_state_key}_code")
            with add_c2:
                _npa_url = st.text_input(
                    "Посилання (НПА, документ, гугл-док тощо)",
                    key=f"{_extra_npa_state_key}_url",
                    placeholder="https://zakon.rada.gov.ua/…",
                )
            with add_c3:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("➕ Додати", key=f"{_extra_npa_state_key}_add", use_container_width=True):
                    url_clean = raw_value(_npa_url)
                    if url_clean:
                        extra_npa_links.setdefault(_npa_code, [])
                        if url_clean not in extra_npa_links[_npa_code]:
                            extra_npa_links[_npa_code].append(url_clean)
                        st.rerun()

            for _c, _links in list(extra_npa_links.items()):
                for _j, _u in enumerate(_links):
                    l1, l2 = st.columns([5, 0.6])
                    with l1:
                        st.markdown(f"• **{_c}** → {_u}")
                    with l2:
                        if st.button("🗑", key=f"{_extra_npa_state_key}_del_{_c}_{_j}"):
                            extra_npa_links[_c].pop(_j)
                            if not extra_npa_links[_c]:
                                extra_npa_links.pop(_c)
                            st.rerun()
        else:
            st.info("Немає заходів, доступних для подання в цьому періоді.")


# ------------------------------------------------------------
# Схема погодження для подання заходів
# ------------------------------------------------------------

measures_scheme_name, measures_chain, measures_scheme_ready = render_scheme_picker(
    selected_ssp_index, "meas"
)

submit_clicked = st.button("Подати на розгляд", use_container_width=True)

if submit_clicked:
    validation_errors = validate_submission()

    if validation_errors:
        for error in validation_errors:
            st.error(error)
    else:
        selected_rows = edited_df[
            (edited_df["Подати"] == True) & (edited_df["_locked"] == False)
        ].copy()
        submitted_at = datetime.now(timezone.utc).isoformat()

        first_stage_status = (
            schemes.waiting_status_for_stage(measures_chain[0])
            if (chain_columns_exist and measures_chain)
            else "Очікує погодження"
        )

        payload = []
        for _, row in selected_rows.iterrows():
            code = raw_value(row.get("Код", ""))
            payload.append({
                # П8: знімок назви заходу на момент подання (захист від
                # повторного використання коду після актуалізації плану)
                "object_name":        raw_value(row.get("Захід", "")),
                "department":         raw_value(selected_ssp_index),
                "year":               str(selected_year),
                "quarter":            raw_value(selected_quarter),
                "approval_status":    first_stage_status,
                "status":             raw_value(row.get("Статус\nвиконання", "")),
                "strat_code":         code,
                "responsible_person": raw_value(responsible_person),
                "phone":              raw_value(responsible_phone),
                "email":              raw_value(responsible_email),
                "numeric_value":      raw_value(row.get(quarter_label, "")),
                "progress_text":      raw_value(row.get("Опис\nпрогресу", "")),
                "risks":              raw_value(row.get("Ризики / проблеми /\nвідхилення", "")),
                **(
                    {"npa_link": "\n".join(
                        [u for u in [raw_value(row.get("Посилання\nна НПА", ""))] if u]
                        + extra_npa_links.get(code, [])
                    )}
                    if npa_link_column_exists else {}
                ),
                **(
                    {"object_kind": "measure"}
                    if kind_column_exists else {}
                ),
                **(
                    {
                        "approval_chain": schemes.chain_to_json(measures_chain),
                        "chain_stage": 0,
                        "scheme_label": measures_scheme_name,
                    }
                    if (chain_columns_exist and measures_chain) else {}
                ),
                "file_names":         "",
                "file_urls":          "",
                "admin_comment":      "",
                "start_date":         raw_value(row.get("Початкова\nдата", "")),
                "end_date":           raw_value(row.get("Кінцева\nдата", "")),
                "submitted_at":       submitted_at,
            })

        try:
            supabase.table("monitoring_requests").insert(payload).execute()
            st.cache_data.clear()
            st.session_state[_extra_npa_state_key] = {}
            if chain_columns_exist and measures_chain:
                notify_first_stage(
                    measures_chain,
                    [p["strat_code"] for p in payload],
                    str(selected_year), raw_value(selected_quarter),
                )
            st.success("Відомості успішно подано на розгляд")
            st.info(
                "Відомості опрацьовуються координатором. "
                "Інформація про подальший статус відобразиться в особистому кабінеті."
            )
        except Exception as error:
            st.error(f"Не вдалося подати відомості. Технічна помилка: {error}")


# ------------------------------------------------------------
# Footer
# ------------------------------------------------------------

render_footer()
