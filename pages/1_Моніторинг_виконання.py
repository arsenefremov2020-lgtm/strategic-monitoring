import re
from datetime import datetime, timezone
from html import escape

import pandas as pd
import streamlit as st
from core.data_types import prepare_monitoring_payload
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
from core import statuses as core_statuses
from core.period_locks import is_period_locked
from core import approval_schemes as schemes
from core import notify_events
from core.validation import (
    is_x_value,
    status_value_conflict,
    validate_fact_value,
    validate_fact_value_for_target,
)
from core.errors import show_incident, show_warning
from core import periods as core_periods
from core.submission_ui import render_submission_notice, set_submission_notice
from core.transitions import TransitionRejected, submit_request

# Спільна для обох таблиць (заходи + індикатори) висота видимої області
# редактора (~2 рядки + шапка).
TABLE_VISIBLE_HEIGHT_PX = 280

# ВИПРАВЛЕННЯ (спроба 5, скориговано за фідбеком): 60px, потім 80px —
# попередні +100px не гарантували клікабельність останнього canvas-рядка;
# додаємо повний додатковий буфер під редактором.
TABLE_CONTAINER_HEIGHT_PX = TABLE_VISIBLE_HEIGHT_PX + 200


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
    background: #F7F9FC;
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
    color: #61708A;
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
    border: 1px solid #DCE4F0;
    box-shadow: 0 6px 18px rgba(15,23,42,0.045);
}

.status-row {
    max-width: 1280px;
    margin: 12px auto 8px auto;
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
    background: #E4F5EC;
    color: #0C713A;
    border-color: #1E9E57;
}

.status-green .status-dot {
    background: #118847;
}

.status-blue {
    background: #E3EDFF;
    color: #032A63;
    border-color: #BFD3F2;
}

.status-blue .status-dot {
    background: #005BBB;
}

.status-orange {
    background: #FDF3D8;
    color: #FF7A45;
    border-color: #FF7A45;
}

.status-orange .status-dot {
    background: #FF7A45;
}

@media (max-width: 1100px) {
    .status-row {
        grid-template-columns: 1fr;
    }
}

/* Картка перемикача типу подання: візуально узгоджена з flow-box. */
.st-key-submission_mode_card {
    background: rgba(255,255,255,0.94);
    border: 1px solid #DCE4F0;
    border-radius: 16px;
    box-shadow: 0 6px 18px rgba(15,23,42,0.045);
    padding: 12px 16px 8px 16px;
    margin: 10px 0 14px 0;
}
.st-key-submission_mode_card [data-testid="stRadio"] > label p,
.st-key-submission_mode_card [data-testid="stRadio"] label p {
    color: #132238 !important;
    font-weight: 800 !important;
}

.header-box {
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 8px;
    backdrop-filter: blur(8px);
}

.header-title {
    font-size: 32px;
    font-weight: 900;
    color: #132238;
    margin-bottom: 8px;
}

.header-subtitle {
    font-size: 15px;
    color: #61708A;
    line-height: 1.55;
}

.user-box {
    border-radius: 18px;
    padding: 22px 26px 24px 26px;
    margin: 18px 0 18px 0;
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    box-shadow: 0 10px 24px rgba(15,23,42,0.07);
}

.user-title,
.flow-title,
.summary-title,
.filter-title,
.table-title {
    color: #132238;
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
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    color: #132238;
    font-size: 13px;
    font-weight: 900;
    line-height: 1.25;
}

.flow-steps.flow-steps-5 {
    grid-template-columns: repeat(5, minmax(0, 1fr));
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
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-radius: 13px;
    padding: 14px 15px;
    min-height: 96px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.summary-label {
    color: #61708A;
    font-size: 12px;
    font-weight: 800;
    line-height: 1.35;
    min-height: 34px;
    margin-bottom: 8px;
}

.summary-value {
    color: #132238;
    font-size: 24px;
    line-height: 1;
    font-weight: 950;
}

.filter-box {
    border-radius: 18px;
    padding: 24px 26px 26px 26px;
    margin: 18px 0 24px 0;
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    box-shadow: 0 10px 24px rgba(15,23,42,0.07);
}

.filter-title {
    font-size: 22px;
    margin-bottom: 10px;
}

.filter-legend {
    color: #61708A;
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
    color: #032A63;
    line-height: 1.55;
}

.info-card-title {
    color: #132238;
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
    color: #032A63;
    font-size: 14px;
    margin: 12px 0 18px 0;
}

.table-title {
    font-size: 20px;
    margin: 24px auto 12px auto;
    max-width: 1280px;
}

.measure-table-title {
    margin-top: 8px !important;
}

div[data-testid="stRadio"] > label p,
div[data-testid="stRadio"] [role="radiogroup"] label p {
    color: #132238 !important;
    font-weight: 900 !important;
}

/* Центрування всієї таблиці.
   ВАЖЛИВО (виправлення після тестування, липень 2026 — спроба 4):
   попередні спроби покладались ЛИШЕ на Python-параметр height=
   st.data_editor(), сподіваючись, що він і визначає фактичну висоту
   обгортки в пікселях. На практиці цього виявилось не досить: коробка
   іноді "переливалася" за межі заявленої висоти (накладання на текст
   під таблицею), а спроба виправити це ЗОВНІШНІМ st.container(height=)
   давала другий, зайвий скрол. Тому тут — пряме форсування height/
   max-height через CSS з !important, синхронізоване з тим самим
   числом (TABLE_VISIBLE_HEIGHT_PX) у Python-коді сторінки. CSS має
   останнє слово незалежно від того, що вважає сам компонент. */
div[data-testid="stDataEditor"] {
    max-width: 1280px !important;
    height: 280px !important;
    max-height: 280px !important;
    margin-left: auto !important;
    margin-right: auto !important;
    border-radius: 14px !important;
    overflow: hidden !important;
    border: 1px solid #DCE4F0 !important;
    box-shadow: 0 8px 22px rgba(15,23,42,0.06) !important;
}

/* Внутрішній скрол-контейнер самого grid (Glide Data Grid) — саме тут
   реально відбувається горизонтальна/вертикальна прокрутка. На відміну
   від зовнішньої обгортки вище, тут overflow навмисно лишається
   керованим самим компонентом (auto), а не примусово ламається. */
div[data-testid="stDataEditor"] [class*="dvn-scroll"] {
    border-radius: 0 0 14px 14px;
}

/* Вища шапка таблиці + перенос тексту в шапці */
div[data-testid="stDataEditor"] div[role="columnheader"] {
    min-height: 96px !important;
    height: 96px !important;
    background: #EAF1FF !important;
    border-bottom: 1px solid #DCE4F0 !important;
    font-weight: 900 !important;
    color: #132238 !important;
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

[data-testid="stMain"] div[data-testid="stButton"] > button {
    width: 100%;
    min-height: 68px;
    background: #FF7A45 !important;
    color: #ffffff !important;
    border: 0 !important;
    border-radius: 18px !important;
    font-size: 20px !important;
    font-weight: 950 !important;
    letter-spacing: 0.3px !important;
    box-shadow: 0 18px 34px rgba(249,115,22,0.34), inset 0 1px 0 rgba(255,255,255,0.25) !important;
}

[data-testid="stMain"] div[data-testid="stButton"] > button:hover {
    filter: brightness(1.05);
    transform: translateY(-1px);
}

.final-footer {
    text-align: center;
    color: #61708A;
    font-size: 13px;
    margin-top: 48px;
    padding-top: 24px;
    border-top: 1px solid #DCE4F0;
    line-height: 1.7;
}

.final-footer-main {
    font-weight: 700;
    color: #61708A;
}

.final-footer-sub {
    color: #61708A;
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
    """A target marked «х» is still an active reporting row."""
    col = f"target_{year}"
    if col not in row:
        return True
    value = row.get(col, "")
    if is_x_value(value):
        return True
    return not is_empty_or_nd(value)


def future_targets_for_row(row, year):
    """Return later annual targets used to infer the input type for a current «х»."""
    targets = []
    for future_year in range(int(year) + 1, 2035):
        col = f"target_{future_year}"
        if col in row:
            targets.append(row.get(col, ""))
    return targets


get_record_visual_status = core_statuses.get_record_visual_status


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

_submit_warning = st.session_state.pop("monitoring_submit_warning", None)
if _submit_warning:
    st.warning(_submit_warning)

prefilled_contacts = get_prefilled_user_contacts(current_user)
contact_fields_disabled = should_prefill_contact_fields(current_user)

# ------------------------------------------------------------
# User info fields
# ------------------------------------------------------------

with st.expander("Контактна інформація відповідальної особи", expanded=False):
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


# ------------------------------------------------------------
# Схема погодження — спільний блок для заходів та індикаторів
# ------------------------------------------------------------

def render_scheme_picker(ssp_index, key_prefix):
    """Вибір повного маршруту погодження подавачем.

    DEMO 1.9 повертає логіку вибору маршруту на етап подання, але залишає
    обмеження: координатор обов'язковий, координатор не може бути останнім
    (крім подання керівником ССП), а ланки нижче ролі подавача недоступні.
    """
    st.markdown(
        '<div class="table-title" style="margin-top:14px;">Схема погодження</div>',
        unsafe_allow_html=True,
    )
    submitter_role = str(current_user.get("role") or "")
    available_schemes = schemes.scheme_options_for_submitter(submitter_role)

    if not available_schemes:
        st.error("Для вашої ролі не знайдено доступної схеми погодження.")
        return "", [], False

    default_index = 0
    if schemes.DEFAULT_SCHEME in available_schemes:
        default_index = available_schemes.index(schemes.DEFAULT_SCHEME)

    scheme_name = st.selectbox(
        "Схема погодження",
        available_schemes,
        index=default_index,
        key=f"{key_prefix}_approval_scheme_select",
        label_visibility="collapsed",
    )

    roles = schemes.APPROVAL_SCHEMES.get(scheme_name, [])
    persons: dict[str, dict] = {}
    ready = True

    for i, role in enumerate(roles, start=1):
        candidates = schemes.stage_candidates(role, ssp_index)
        label = schemes.STAGE_LABELS.get(role, role)
        if not candidates:
            ready = False
            st.error(
                f"Для ССП {ssp_index} не знайдено користувача для ланки «{label}». "
                f"Без цього подання за обраною схемою неможливе."
            )
            continue

        if len(candidates) == 1:
            chosen = candidates[0]
            st.markdown(
                f'<div style="background:#F7F9FC;border:1px solid #DCE4F0;'
                f'border-radius:10px;padding:8px 12px;margin-bottom:6px;">'
                f'<div style="font-size:10px;font-weight:800;letter-spacing:.04em;'
                f'text-transform:uppercase;color:#61708A;">{i}. {escape(label)}</div>'
                f'<div style="font-size:13px;font-weight:700;color:#132238;">'
                f'{escape(chosen.get("name") or chosen.get("email") or "")}</div></div>',
                unsafe_allow_html=True,
            )
        else:
            chosen_label = st.selectbox(
                f"{i}. {label}",
                [schemes.candidate_label(c) for c in candidates],
                key=f"{key_prefix}_stage_{i}_{role}",
            )
            chosen = candidates[[schemes.candidate_label(c) for c in candidates].index(chosen_label)]
        persons[role] = chosen

    chain = schemes.build_chain(scheme_name, persons) if ready else []
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
    except Exception as exc:
        show_warning(
            "Заявку подано, але email першій ланці не надіслано.",
            exc,
            "Сповіщення першої ланки після подання заявки",
        )


# ------------------------------------------------------------
# Перемикач: що подаємо — заходи чи індикатори СЦ/завдань
# ------------------------------------------------------------

_submission_mode_labels = {
    "measures": "📋 Заходи",
    "indicators": "📊 Індикатори стратегічних цілей та завдань",
}
with st.container(border=True, key="submission_mode_card"):
    submission_mode = st.radio(
        "**Що подаєте (оберіть потрібний для Вас варіант)**",
        list(_submission_mode_labels),
        format_func=lambda value: _submission_mode_labels[value],
        horizontal=True,
        key="submission_mode_toggle",
    )

if submission_mode == "indicators":
    # ========================================================
    # ПОДАННЯ ДАНИХ ДЛЯ ІНДИКАТОРІВ СТРАТЕГІЧНИХ ЦІЛЕЙ ТА ЗАВДАНЬ
    # ========================================================
    st.markdown(
        """
        <div class="flow-box">
            <div class="flow-title">Подання значень індикаторів стратегічних цілей та завдань</div>
            <div class="flow-steps flow-steps-5">
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
        "нова інформація — подається оновлене значення. Вся історія подань зберігається."
    )

    ic1, ic2, ic3, ic4 = st.columns([1.25, 0.7, 0.9, 1.4])
    with ic1:
        if available_ssp_indices:
            ind_ssp_index = st.selectbox(
                "Індекс самостійного структурного підрозділу",
                available_ssp_indices,
                index=0,
                key="ind_ssp_filter",
                disabled=ssp_select_disabled,
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
            key="ind_search_filter",
            placeholder="Наприклад: 1.2",
        )

    full_matrix = load_full_strat_matrix()
    indicator_rows = full_matrix[
        full_matrix["object_type"].isin(["goal_indicator", "task_indicator"])
    ].copy()

    indicator_rows = filter_actions_for_user(
        indicator_rows,
        current_user,
        executor_columns=["resp_main"],
    )

    if ind_ssp_index:
        _pat = re.compile(rf"(?<!\d){re.escape(str(ind_ssp_index))}(?!\d)")
        _mask = indicator_rows.apply(
            lambda r: bool(_pat.search(str(r.get("resp_main", "")))),
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

    # Останні подання індикаторів: ключ = (код + назва індикатора).
    # Один strat_code може належати кільком індикаторам, тому матчинг лише
    # за кодом заборонений. Старі записи без indicator_name використовуємо
    # тільки якщо в матриці за цим кодом існує рівно один індикатор.
    waiting_statuses = set(schemes.ALL_WAITING_STATUSES)
    ind_submitted, ind_submitted_legacy = monitoring_data.latest_indicator_submissions(
        monitoring_df,
        year=ind_year,
    )

    _indicator_names_by_code = {}
    for _, _row in indicator_rows.iterrows():
        _code = raw_value(_row.get("code", ""))
        _name_key = monitoring_data.indicator_identity_key(
            _code, _row.get("indicator", "")
        )[1]
        if _code and _name_key:
            _indicator_names_by_code.setdefault(_code, set()).add(_name_key)

    value_col = "Значення\nіндикатора"
    fact_col = f"{ind_year} Факт"

    ind_table_rows = []
    for _, row in indicator_rows.iterrows():
        code = raw_value(row.get("code", ""))
        indicator_name = raw_value(row.get("indicator", ""))
        identity_key = monitoring_data.indicator_identity_key(code, indicator_name)
        last = ind_submitted.get(identity_key)
        if last is None and len(_indicator_names_by_code.get(code, set())) == 1:
            last = ind_submitted_legacy.get(code)
        in_progress = (
            last is not None
            and raw_value(last.get("approval_status")) in waiting_statuses
        )
        last_badge = ""
        if last is not None:
            last_value = (
                raw_value(last.get("numeric_value"))
                or raw_value(last.get("value_text"))
            )
            if last_value:
                last_badge = core_statuses.legend_badge_image_uri(
                    core_statuses.get_record_visual_status(last),
                    display_value=last_value,
                )
        ind_table_rows.append({
            "Подати": False,
            "Код": code,
            "СЦ / Завдання": strip_leading_code(row.get("name", ""), code),
            "Індикатор": indicator_name,
            "Одиниці\nвиміру": raw_value(row.get("unit", "")),
            "2021\n(базовий)": raw_value(row.get("base_2021", "")),
            f"{ind_year}\n(цільовий орієнтир)": raw_value(row.get(ind_target_col, "")),
            fact_col: last_badge,
            value_col: "",
            "Опис\nпрогресу": "",
            "Ризики / проблеми /\nвідхилення": "",
            "Посилання\nна НПА": "",
            "_locked": in_progress,
        })

    ind_required_cols = [value_col, "Опис\nпрогресу"]
    st.markdown(
        f"""
        <div class="note-box" style="background:#F7F9FC;border:1px solid #DCE4F0;">
            <b>Легенда обов'язковості полів:</b>
            <span style="background:#FBE5E5;border:1px solid #DC4A4A;border-radius:8px;
                  padding:2px 10px;margin:0 6px;font-weight:800;color:#DC4A4A;">🔴 Обов'язкове</span>
            «Значення індикатора», «Опис прогресу»
            <span style="background:#FDF3D8;border:1px solid #F4B400;border-radius:8px;
                  padding:2px 10px;margin:0 6px;font-weight:800;color:#8A6400;">🟡 Необов'язкове</span>
            «Ризики», «Посилання на НПА»
        </div>
        """,
        unsafe_allow_html=True,
    )

    ind_df_table = pd.DataFrame(ind_table_rows)
    if ind_df_table.empty:
        st.info("За обраними параметрами індикаторів не знайдено.")
        render_footer()
        st.stop()

    quarter_roman = {1: "I", 2: "II", 3: "III", 4: "IV"}[
        (ind_as_of.month - 1) // 3 + 1
    ]

    ind_locked_count = int(ind_df_table["_locked"].sum())
    if ind_locked_count:
        st.markdown(
            f'<div class="note-box" style="background:#FDF3D8;border:1px solid #F4B400;color:#8A6400;">'
            f'За {ind_locked_count} індикатором(ами) подання за {ind_year} рік уже перебуває '
            f'в процесі погодження — повторне подання стане доступним після завершення процесу.</div>',
            unsafe_allow_html=True,
        )

    ind_display_cols = [c for c in ind_df_table.columns if not c.startswith("_")]
    _ind_visible_height = TABLE_VISIBLE_HEIGHT_PX

    with st.container(height=TABLE_CONTAINER_HEIGHT_PX):
        ind_edited = st.data_editor(
            ind_df_table,
            key=(
                f"indicator_editor_{normalize_key(ind_ssp_index)}_{ind_year}_"
                f"{ind_as_of.isoformat()}"
            ),
            use_container_width=True,
            hide_index=True,
            height=_ind_visible_height,
            row_height=72,
            num_rows="fixed",
            column_order=ind_display_cols,
            disabled=[
                "Код",
                "СЦ / Завдання",
                "Індикатор",
                "Одиниці\nвиміру",
                "2021\n(базовий)",
                f"{ind_year}\n(цільовий орієнтир)",
                fact_col,
            ],
            column_config={
                "Подати": st.column_config.CheckboxColumn("Подати", width=80),
                fact_col: st.column_config.ImageColumn(
                    fact_col,
                    help="Останнє подане значення цього індикатора за обраний рік",
                    width=130,
                ),
                value_col: st.column_config.TextColumn(
                    f"🔴 {value_col}",
                    width=150,
                    help="Обов'язкове поле. Фактичне значення індикатора станом на обрану дату",
                ),
                "Опис\nпрогресу": st.column_config.TextColumn(
                    "🔴 Опис\nпрогресу",
                    width=280,
                    help="Обов'язкове поле",
                ),
                "Ризики / проблеми /\nвідхилення": st.column_config.TextColumn(
                    "🟡 Ризики / проблеми /\nвідхилення",
                    width=280,
                    help="Необов'язкове поле",
                ),
                "Посилання\nна НПА": st.column_config.TextColumn(
                    "🟡 Посилання\nна НПА",
                    width=220,
                    help="Необов'язкове. Кілька посилань — через кому або крапку з комою",
                ),
                "_locked": st.column_config.CheckboxColumn("_locked", width=1),
            },
        )

    # Успішне подання показується саме між таблицею і схемою погодження.
    render_submission_notice(dismissible=False, consume=True)

    _ind_scheme_prefix = (
        f"ind_{normalize_key(ind_ssp_index)}_{ind_year}_{ind_as_of.isoformat()}"
    )
    ind_scheme_name, ind_chain, ind_scheme_ready = render_scheme_picker(
        ind_ssp_index,
        _ind_scheme_prefix,
    )

    if st.button(
        "Подати значення індикаторів на розгляд",
        use_container_width=True,
        key="ind_submit",
    ):
        ind_errors = []
        if not ind_scheme_ready:
            ind_errors.append(
                "Схема погодження неповна: для однієї з ланок не знайдено користувача"
            )

        ind_selected = ind_edited[
            (ind_edited["Подати"] == True) & (ind_edited["_locked"] == False)
        ].copy()
        if ind_selected.empty:
            ind_errors.append("Позначте хоча б один індикатор для подання")
        else:
            for _, r in ind_selected.iterrows():
                code = raw_value(r.get("Код"))
                unit = raw_value(r.get("Одиниці\nвиміру", ""))
                fact_value = raw_value(r.get(value_col, ""))
                for field in ind_required_cols:
                    if not raw_value(r.get(field, "")):
                        ind_errors.append(
                            f"У індикаторі {code} не заповнено обов'язкове поле "
                            f"«{field.replace(chr(10), ' ')}»."
                        )
                ok, msg = validate_fact_value(fact_value, unit)
                if fact_value and not ok:
                    ind_errors.append(f"У індикаторі {code}: {msg}.")

        if ind_errors:
            for error in ind_errors:
                st.error(error)
        else:
            submitted_at = datetime.now(timezone.utc).isoformat()
            successful_codes = []
            rejected_messages = []
            first_stage_label = (
                ind_chain[0].get("label", "Координатор")
                if ind_chain
                else "Координатор"
            )

            for _, row in ind_selected.iterrows():
                code = raw_value(row.get("Код"))
                item = {
                    "object_name": raw_value(row.get("СЦ / Завдання", "")),
                    "indicator_name": raw_value(row.get("Індикатор", "")),
                    "department": raw_value(ind_ssp_index),
                    "year": str(ind_year),
                    "quarter": quarter_roman,
                    "status": "",
                    "strat_code": code,
                    "responsible_person": raw_value(responsible_person),
                    "phone": raw_value(responsible_phone),
                    "email": raw_value(responsible_email),
                    "numeric_value": raw_value(row.get(value_col, "")),
                    "progress_text": raw_value(row.get("Опис\nпрогресу", "")),
                    "risks": raw_value(row.get("Ризики / проблеми /\nвідхилення", "")),
                    "npa_link": raw_value(row.get("Посилання\nна НПА", "")),
                    "object_kind": "indicator",
                    "as_of_date": ind_as_of.isoformat(),
                    "approval_chain": schemes.chain_to_json(ind_chain),
                    "chain_stage": 0,
                    "scheme_label": ind_scheme_name,
                    "file_names": "",
                    "file_urls": "",
                    "admin_comment": "",
                    "start_date": "",
                    "end_date": "",
                    "submitted_at": submitted_at,
                }
                prepared = prepare_monitoring_payload(item)
                try:
                    result = submit_request(
                        payload=prepared,
                        action="Подання значення індикатора",
                        user=current_user,
                        created_by="Подавач / первинне подання індикатора",
                        draft_email="",
                        draft_key="",
                    )
                    successful_codes.append(code)
                    first_stage_label = (
                        result.data.get("first_stage_label") or first_stage_label
                    )
                except TransitionRejected as exc:
                    rejected_messages.append(f"{code}: {exc.message}")
                except Exception as exc:
                    show_incident(exc, context=f"Атомарне подання індикатора {code}")

            if successful_codes:
                monitoring_data.invalidate_monitoring_cache()
                notify_first_stage(
                    ind_chain,
                    successful_codes,
                    str(ind_year),
                    f"станом на {ind_as_of.strftime('%d.%m.%Y')}",
                    kind="indicator",
                )
                set_submission_notice(
                    first_stage_label=first_stage_label,
                    codes=successful_codes,
                )
                if rejected_messages:
                    st.session_state["monitoring_submit_warning"] = (
                        "Частину індикаторів не подано: "
                        + " | ".join(rejected_messages)
                    )
                st.rerun()
            elif rejected_messages:
                st.error("Подання відхилено: " + " | ".join(rejected_messages))

    render_footer()
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
            Оберіть звітний період. Система автоматично відобразить лише ті заходи, 
            за якими самостійний структурний підрозділ визначений головним виконавцем, 
            і лише ті, період виконання яких уже настав для обраного року та кварталу.
        </div>
        <div class="info-grid">
            <div class="info-card">
                <div class="info-card-title">Інструкція користувача</div>
                <div class="instruction-item">1. Позначте у першій колонці таблиці «Подати» заходи, за якими подається інформація</div>
                <div class="instruction-item">2. Внесіть фактичні звітні відомості (показники, стан виконання, короткий опис прогресу та інформацію щодо ризиків)</div>
                <div class="instruction-item">3. Натисніть «Подати на розгляд»</div>
                <div class="instruction-item">4. Оберіть схему погодження відповідно до внутрішнього розподілу з випадного списку.</div>
                <div class="instruction-item">5. Відстежуйте статус погодження — відомості проходять усі ланки обраної схеми до кінцевого погодження.</div>
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

if is_period_locked(selected_year, selected_quarter):
    st.info("Не настав час — моніторинг за цей період не проводиться")
    render_footer()
    st.stop()


# ------------------------------------------------------------
# Filtering
# ------------------------------------------------------------

# ТЗ-правка (09.07.2026, п.1): у таблиці подання відомостей показуються
# ЛИШЕ заходи, де ССП визначено ГОЛОВНИМ виконавцем. Заходи, де ССП є
# співвиконавцем, у подання не потрапляють — їхній стан можна переглянути
# у «Паспорті ССП» через перемикач співвиконавця.
filtered_measures = filter_actions_for_user(
    all_measures,
    current_user,
    executor_columns=["resp_main"],
)

if selected_ssp_index:
    filtered_measures = filtered_measures[
        filtered_measures.apply(
            lambda row: (
                value_contains_ssp(row.get("resp_main", ""), selected_ssp_index)
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
            monitoring_selected["visual_status"].isin(["Погоджено", "На доопрацюванні"])
        ]
    )

    waiting_count = unique_measure_count(
        monitoring_selected[
            monitoring_selected["visual_status"] == "На розгляді"
        ]
    )

    returned_count = unique_measure_count(
        monitoring_selected[
            monitoring_selected["visual_status"] == "На доопрацюванні"
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

# Пункт 6 нового ТЗ: картковий режим подання прибрано за рішенням
# Арсена — лишається виключно табличний спосіб подання (нижче).

# ------------------------------------------------------------
# One editable table
# ------------------------------------------------------------

quarter_label = f"{quarter_to_q_label(selected_quarter)} {selected_year}"
target_col = f"target_{selected_year}"

if target_col not in filtered_measures.columns:
    filtered_measures[target_col] = ""

future_targets_by_code = {
    raw_value(row.get("code", "")): future_targets_for_row(row, selected_year)
    for _, row in filtered_measures.iterrows()
}

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

# Номер обраного звітного періоду (рік*10 + квартал) для перевірки
# «Не настав час» — ТЗ 10.18: система має правильно зчитувати, коли
# саме починається захід, і не давати подавати відомості раніше.
_selected_period_num = (
    int(str(selected_year)) * 10
    + core_periods.quarter_to_number(selected_quarter)
)
_not_started_hidden = 0

table_rows = []
locked_cols_per_row = {}   # code -> list of column names that must be disabled

for _, row in filtered_measures.iterrows():
    code = raw_value(row.get("code", ""))
    deputy = get_deputy_for_ssp(extract_ssp_index(row.get("resp_main", "")))

    # Чи є вже подана заявка? Автоуспадковане «так/Виконано» є лише
    # підстановкою для відображення та розрахунків: воно НЕ блокує реальне
    # подання наступного кварталу і перекривається ним.
    existing = submitted_map.get(code)
    is_auto_inherited = (
        existing is not None
        and bool(existing.get("_auto_inherited", False))
    )
    is_locked = existing is not None and not is_auto_inherited
    is_approved = (
        is_locked
        and raw_value(existing.get("approval_status", "")) == "Погоджено"
    )
    is_manually_closed = (
        code,
        str(selected_year),
        str(selected_quarter),
    ) in manual_closeouts

    if is_manually_closed:
        is_locked = True

    # ТЗ 10.18: якщо період виконання заходу ще НЕ НАСТАВ у обраному
    # звітному періоді — подання відомостей неможливе в принципі.
    # Заходи без розпізнаваної початкової дати вважаються щорічними
    # (виконуються постійно) і НЕ блокуються.
    # ТЗ-правка (09.07.2026, п.2): захід, період якого ще НЕ НАСТАВ для
    # обраного року/кварталу, у таблицю подання НЕ потрапляє взагалі —
    # рядок з'явиться автоматично, щойно настане його період. Якщо по
    # заходу вже існує заявка чи ручне закриття — рядок показується.
    is_not_started = core_periods.is_measure_not_started(
        core_periods.parse_period(row.get("measure_start_date", "")),
        _selected_period_num,
    )
    if is_not_started and not is_locked:
        _not_started_hidden += 1
        continue

    if existing is not None:
        q_fact_val = raw_value(existing.get("numeric_value", ""))
        status_val = raw_value(existing.get("status", ""))
        progress_val = raw_value(existing.get("progress_text", ""))
        risks_val = raw_value(existing.get("risks", ""))
        npa_link_val = raw_value(existing.get("npa_link", ""))
        if is_manually_closed:
            lock_label = "🔒 Закрито вручну"
        elif is_auto_inherited:
            lock_label = ""
        else:
            lock_label = "✅ Погоджено" if is_approved else "⏳ На розгляді"
    else:
        q_fact_val = status_val = progress_val = risks_val = npa_link_val = ""
        lock_label = ""

    table_rows.append({
        "Подати":      False,   # виправлення: за замовчуванням НІЧОГО не позначено —
                                  # людина сама обирає, які заходи подає цього разу
                                  # (раніше було "not is_locked" — позначало ВСІ незакриті
                                  # рядки одразу, навіть якщо даних по них ще не вносили).
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

if _not_started_hidden:
    st.caption(
        f"⬜ {_not_started_hidden} захід(ів) вашого ССП не показані в таблиці, "
        f"бо їхній період виконання ще не настав для обраного року/кварталу — "
        f"вони з'являться автоматично з початком свого періоду."
    )

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

st.markdown('<div class="table-title measure-table-title">Заходи для внесення відомостей</div>', unsafe_allow_html=True)

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
            f'''<div class="note-box" style="background:#FDF3D8;border:1px solid #F4B400;color:#8A6400;">
                За {locked_count} заходом(заходами) у {quarter_label} відомості вже подано: {", ".join(parts)}.
                Поля цих заходів заповнені поданими даними та <strong>заблоковані</strong> для редагування.
            </div>''',
            unsafe_allow_html=True
        )

    # Виправлення (спроба 5): CSS-форсування виявилось ненадійним —
    # повертаємо зовнішній st.container() як єдиний надійний спосіб
    # обрізати вміст (він не дає накладання). Щоб уникнути повторного
    # "другого скролу", контейнер тепер ПОМІТНО вищий за саму таблицю
    # (TABLE_CONTAINER_HEIGHT_PX), а не точно дорівнює їй.
    _row_h = 80
    _header_h = 110
    _visible_rows = 2
    _visible_height = TABLE_VISIBLE_HEIGHT_PX

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
            help="Необов'язкове. Посилання на НПА / підтвердний документ.",
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
        <div class="note-box" style="background:#F7F9FC;border:1px solid #DCE4F0;">
            <b>Легенда обов'язковості полів:</b>
            <span style="background:#FBE5E5;border:1px solid #DC4A4A;border-radius:8px;
                  padding:2px 10px;margin:0 6px;font-weight:800;color:#DC4A4A;">🔴 Обов'язкові</span>
            «{quarter_label}» (квартальне значення), «Статус виконання», «Опис прогресу» — без них подання не пройде
            <span style="background:#FDF3D8;border:1px solid #F4B400;border-radius:8px;
                  padding:2px 10px;margin:0 6px;font-weight:800;color:#8A6400;">🟡 Необов'язкові</span>
            «Ризики / проблеми / відхилення», «Посилання на НПА»
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(height=TABLE_CONTAINER_HEIGHT_PX):
        edited_df = st.data_editor(
            table_df,
            key=(
                f"monitoring_editor_{normalize_key(selected_ssp_index)}_{selected_year}_"
                f"{selected_quarter}_{normalize_key(search_query)}"
            ),
            use_container_width=True,
            hide_index=True,
            height=_visible_height,
            row_height=80,
            num_rows="fixed",
            column_config=col_config,
            column_order=display_cols,   # приховуємо _locked/_lock_label
            disabled=always_disabled,
        )

# Успішне подання показується саме між таблицею і схемою погодження.
render_submission_notice(dismissible=False, consume=True)


# ------------------------------------------------------------
# Submission validation and submit
# ------------------------------------------------------------

def validate_submission():
    errors = []

    # Контактні дані підтягуються з таблиці доступів; ручну валідацію не застосовуємо.

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
        # Контрольна перевірка ТЗ 10.18 (додатково до блокування рядка):
        # захід, період якого ще не настав, подати неможливо.
        if core_periods.is_measure_not_started(
            core_periods.parse_period(row.get("Початкова\nдата", "")),
            _selected_period_num,
        ):
            errors.append(
                f"Захід {code} має статус «Не настав час» для обраного періоду — "
                "подання відомостей за ним неможливе."
            )
            continue
        fact_value = raw_value(row.get(quarter_label, ""))
        target_value = raw_value(row.get(col_target, ""))
        unit = raw_value(row.get("Одиниці\nвиміру", ""))
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
        future_targets = future_targets_by_code.get(code, [])
        if fact_value:
            ok, msg = validate_fact_value_for_target(
                fact_value,
                unit,
                target_value,
                future_targets,
            )
            if not ok:
                errors.append(f"У заході {code}: {msg}.")
        status_msg = status_value_conflict(
            row.get("Статус\nвиконання", ""),
            fact_value,
            target_value,
            unit,
            code,
            future_targets,
        )
        if status_msg:
            errors.append(status_msg)

    return errors


# ------------------------------------------------------------
# Схема погодження для подання заходів
# ------------------------------------------------------------

_meas_scheme_prefix = (
    f"meas_{normalize_key(selected_ssp_index)}_{selected_year}_{selected_quarter}"
)
measures_scheme_name, measures_chain, measures_scheme_ready = render_scheme_picker(
    selected_ssp_index,
    _meas_scheme_prefix,
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

        successful_codes = []
        rejected_messages = []
        first_stage_label = (
            measures_chain[0].get("label", "Координатор")
            if measures_chain else "Координатор"
        )

        for _, row in selected_rows.iterrows():
            code = raw_value(row.get("Код", ""))
            item = {
                "object_name": raw_value(row.get("Захід", "")),
                "department": raw_value(selected_ssp_index),
                "year": str(selected_year),
                "quarter": raw_value(selected_quarter),
                "status": raw_value(row.get("Статус\nвиконання", "")),
                "strat_code": code,
                "responsible_person": raw_value(responsible_person),
                "phone": raw_value(responsible_phone),
                "email": raw_value(responsible_email),
                "numeric_value": raw_value(row.get(quarter_label, "")),
                "progress_text": raw_value(row.get("Опис\nпрогресу", "")),
                "risks": raw_value(row.get("Ризики / проблеми /\nвідхилення", "")),
                "npa_link": raw_value(row.get("Посилання\nна НПА", "")),
                "object_kind": "measure",
                "approval_chain": schemes.chain_to_json(measures_chain),
                "chain_stage": 0,
                "scheme_label": measures_scheme_name,
                "file_names": "",
                "file_urls": "",
                "admin_comment": "",
                "start_date": raw_value(row.get("Початкова\nдата", "")),
                "end_date": raw_value(row.get("Кінцева\nдата", "")),
                "submitted_at": submitted_at,
            }
            prepared = prepare_monitoring_payload(item)
            try:
                result = submit_request(
                    payload=prepared,
                    action="Подання моніторингових відомостей",
                    user=current_user,
                    created_by="Подавач / первинне подання",
                    draft_email="",
                    draft_key="",
                )
                successful_codes.append(code)
                first_stage_label = result.data.get("first_stage_label") or first_stage_label
            except TransitionRejected as exc:
                rejected_messages.append(f"{code}: {exc.message}")
            except Exception as exc:
                show_incident(exc, context=f"Атомарне подання заходу {code}")

        if successful_codes:
            monitoring_data.invalidate_monitoring_cache()
            notify_first_stage(
                measures_chain, successful_codes, str(selected_year),
                raw_value(selected_quarter),
            )
            set_submission_notice(
                first_stage_label=first_stage_label, codes=successful_codes
            )
            if rejected_messages:
                st.session_state["monitoring_submit_warning"] = (
                    "Частину заходів не подано: " + " | ".join(rejected_messages)
                )
            st.rerun()
        elif rejected_messages:
            st.error("Подання відхилено: " + " | ".join(rejected_messages))


# ------------------------------------------------------------
# Footer
# ------------------------------------------------------------

render_footer()
