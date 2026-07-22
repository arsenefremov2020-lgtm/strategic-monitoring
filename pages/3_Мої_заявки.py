import streamlit as st
import pandas as pd
from core.period_locks import is_period_locked
from core.data_types import prepare_monitoring_payload
from core.db import fetch_all
from core.errors import log_cosmetic_error, show_incident, show_warning
from datetime import datetime, timezone
from html import escape
import re
from core.page_setup import page_setup, render_footer
from core.timeutils import now_kyiv
from core.ui import render_request_timeline
from core.stage4 import format_kyiv_datetime, quarter_to_roman, style_status_columns
from core.strategic_data import load_strat_matrix as core_load_strat_matrix
from core import monitoring_data
from core import notify_events
from core.statuses import SUBMISSION_STATUS_OPTIONS

from core import approval_schemes as schemes
from core.transitions import (
    TransitionRejected,
    resubmit_request,
    withdraw_request as atomic_withdraw_request,
)
from core.submission_ui import render_submission_notice, set_submission_notice
from core.access import filter_requests_for_user, get_prefilled_user_contacts
from core.operational import build_target_map
from config.users import get_user_by_email

current_user = page_setup("Мої заявки", page_name="Мої заявки")
# ============================================================
# STYLE
# ============================================================

st.markdown("""
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

.header-box, .card {
    background: rgba(255,255,255,0.94);
    border: 1px solid #DCE4F0;
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 18px;
    box-shadow: 0 8px 24px rgba(15,23,42,0.06);
}

.header-title {
    font-size: 32px;
    font-weight: 900;
    color: #132238;
    margin-bottom: 8px;
}

.header-subtitle, .card-subtitle {
    font-size: 15px;
    color: #61708A;
    line-height: 1.55;
}

.card-title {
    font-size: 21px;
    font-weight: 900;
    color: #132238;
    margin-bottom: 8px;
}

.filter-panel {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-radius: 18px;
    padding: 18px 20px 10px 20px;
    margin-top: 12px;
    box-shadow: 0 10px 24px rgba(15,23,42,0.07);
}


.badge-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 12px 0;
}

.badge {
    background: #EAF1FF;
    border: 1px solid #BFD3F2;
    color: #005BBB;
    border-radius: 999px;
    padding: 7px 11px;
    font-size: 13px;
    font-weight: 800;
}

.badge-green {
    background: #E4F5EC;
    border: 1px solid #1E9E57;
    color: #0C713A;
}

.badge-yellow {
    background: #FDF3D8;
    border: 1px solid #F4B400;
    color: #8A6400;
}

.badge-red {
    background: #FBE5E5;
    border: 1px solid #DC4A4A;
    color: #DC4A4A;
}

.badge-gray {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    color: #61708A;
}

.badge-blue {
    background: #E3EDFF;
    border: 1px solid #BFD3F2;
    color: #032A63;
}

.info-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    margin-top: 14px;
}

.info-card {
    border-radius: 14px;
    padding: 10px 14px;
    min-height: 72px;
    border: 1px solid #DCE4F0;
    overflow-wrap: anywhere;
}

.info-card-blue {
    background: #EAF1FF;
    border-color: #BFD3F2;
}

.info-card-green {
    background: #E4F5EC;
    border-color: #1E9E57;
}

.info-card-yellow {
    background: #FDF3D8;
    border-color: #F4B400;
}

.info-card-red {
    background: #FBE5E5;
    border-color: #DC4A4A;
}

.info-card-gray {
    background: #F7F9FC;
    border-color: #DCE4F0;
}

.info-label {
    color: #61708A;
    font-size: 12px;
    margin-bottom: 7px;
    line-height: 1.35;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    font-weight: 750;
}

.info-value {
    color: #132238;
    font-weight: 900;
    font-size: 15px;
    line-height: 1.4;
}

.step-box {
    background: #EAF1FF;
    border: 1px solid #BFD3F2;
    border-radius: 14px;
    padding: 14px 16px;
    margin: 10px 0;
}

.version-box {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-radius: 14px;
    padding: 14px 16px;
    margin: 10px 0;
}

.version-title {
    color: #132238;
    font-weight: 900;
    font-size: 15px;
    margin-bottom: 6px;
}

.version-text {
    color: #61708A;
    font-size: 13px;
    line-height: 1.45;
}

.comment-box {
    background: #FDF3D8;
    border: 1px solid #FF7A45;
    color: #FF7A45;
    border-radius: 16px;
    padding: 18px 20px;
    margin: 18px 0 6px 0;
    box-shadow: 0 8px 20px rgba(245,158,11,0.12);
}

.comment-title {
    font-size: 14px;
    font-weight: 950;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    margin-bottom: 8px;
}

.comment-text {
    font-size: 15px;
    line-height: 1.6;
    font-weight: 750;
}

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.9);
    border: 1px solid #DCE4F0;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}


.footer {
    text-align: center;
    color: #8A96A8;
    font-size: clamp(10px, 0.9vw, 12px);
    margin-top: 40px;
    padding: 18px 0 10px;
    border-top: 1px solid #DCE4F0;
}

@media (max-width: 1100px) {
    .info-grid { grid-template-columns: 1fr; }
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# HELPERS
# ============================================================

def clean(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception as exc:
        log_cosmetic_error("Нормалізація значення у Мої заявки", exc)
    text = str(value).strip()
    if text.lower() in ["none", "nan", "nat"]:
        return ""
    return text


def has_value(value):
    return clean(value).strip() != ""


def valid_email(email):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(email).strip()) is not None


def display_text(value, fallback="—"):
    text = clean(value)
    return escape(text) if text else fallback


def status_badge_class(status):
    status = clean(status)
    if status == "Погоджено":
        return "badge-green"
    if status == "Повернуто на доопрацювання":
        return "badge-red"
    if status == "Очікує: Керівник ССП":
        return "badge-blue"
    if status == "Очікує погодження":
        return "badge-yellow"
    return "badge-gray"


ACTIVE_APPROVAL_STATUSES = list(dict.fromkeys([
    *schemes.ALL_WAITING_STATUSES,
    "Повернуто на доопрацювання",
]))

APPROVAL_FILTER_OPTIONS = [
    "Активні до розгляду",
    "Усі",
    *schemes.ALL_WAITING_STATUSES,
    "Повернуто на доопрацювання",
    "Погоджено",
]


# ============================================================
# DATA LOADING
# ============================================================

@st.cache_data
def load_strat_matrix():
    """ЄДИНЕ джерело — core.strategic_data (правка К1)."""
    return core_load_strat_matrix()


def load_requests():
    """ЄДИНЕ джерело — core.monitoring_data (правки К2, П2)."""
    df = monitoring_data.load_monitoring_requests_live()
    if not df.empty and "submitted_at" in df.columns:
        df = df.sort_values("submitted_at", ascending=False)
    return df


def load_logs(request_id):
    rows = fetch_all(
        "monitoring_logs",
        "*",
        filters=[("eq", "request_id", int(request_id))],
        order=("changed_at", True),
    )
    return pd.DataFrame(rows)




# Спільна логіка версіювання винесена в core/versioning.py (пункт 3 ТЗ:
# та сама логіка тепер потрібна і в 1_Мій_кабінет.py, і в
# 3_Адміністрування.py для коригування супер-адміном закритих заявок).
from core.versioning import load_versions



# ============================================================
# MAIN DATA
# ============================================================

df = load_requests()
strat_df = load_strat_matrix()

df = filter_requests_for_user(
    df,
    current_user,
    ssp_columns=["department"]
)

prefilled_contacts = get_prefilled_user_contacts(current_user)

required_cols = [
    "id", "year", "quarter", "department", "responsible_person", "phone", "email",
    "strat_code", "status", "progress_text", "numeric_value", "value_text", "risks",
    "submitted_at", "approval_status", "admin_comment", "file_names", "file_urls",
    "start_date", "end_date", "updated_at", "npa_link", "approval_chain", "chain_stage",
    "scheme_label", "object_kind", "indicator_name",
]
for col in required_cols:
    if col not in df.columns:
        df[col] = ""

# «Мої заявки» показує лише заявки, створені поточним користувачем.
_current_email = str((current_user or {}).get("email") or "").strip().lower()
if _current_email and "email" in df.columns:
    df = df[df["email"].astype(str).str.strip().str.lower() == _current_email].copy()

_target_by_code_year = build_target_map(strat_df)
_indicator_target_by_key = {}
for _, _srow in strat_df.iterrows():
    _scode = clean(_srow.get("code"))
    _iname = clean(_srow.get("indicator"))
    if not _scode or not _iname:
        continue
    for _year in range(2026, 2035):
        _col = f"target_{_year}"
        if _col in strat_df.columns:
            _indicator_target_by_key[(_scode, _iname.casefold(), str(_year))] = clean(_srow.get(_col))


def _target_for_record(record) -> str:
    code = clean(record.get("strat_code"))
    year = clean(record.get("year"))
    kind = clean(record.get("object_kind"))
    indicator_name = clean(record.get("indicator_name"))
    if kind == "indicator" and indicator_name:
        value = _indicator_target_by_key.get((code, indicator_name.casefold(), year), "")
        if value:
            return value
    return clean(_target_by_code_year.get((code, year), "")) or "—"


def _fact_for_record(record) -> str:
    return clean(record.get("numeric_value")) or clean(record.get("value_text")) or "—"


def _strategic_object_name_by_code(code) -> str:
    """Повертає назву стратегічного об'єкта за кодом, віддаючи пріоритет рядку цілі/завдання/заходу."""
    code_value = clean(code).strip()
    if not code_value or strat_df.empty or "code" not in strat_df.columns:
        return ""

    code_key = code_value.rstrip(".")
    candidates = strat_df[
        strat_df["code"].astype(str).str.strip().str.rstrip(".") == code_key
    ].copy()
    if candidates.empty:
        return ""

    if "object_type" in candidates.columns:
        priority = {"goal": 0, "task": 1, "measure": 2}
        candidates["_object_priority"] = (
            candidates["object_type"].astype(str).map(priority).fillna(99)
        )
        candidates = candidates.sort_values("_object_priority")

    for _, candidate in candidates.iterrows():
        name = clean(candidate.get("name"))
        if not name:
            continue
        if name.startswith(code_value):
            name = name[len(code_value):].lstrip(" .—-–|:")
        return name
    return ""


def _period_label(year, quarter) -> str:
    roman = quarter_to_roman(quarter)
    qnum = {"I": "1", "II": "2", "III": "3", "IV": "4"}.get(roman, clean(quarter))
    qnum = str(qnum).upper().removeprefix("Q")
    return f"{clean(year)} Q{qnum}" if clean(year) else f"Q{qnum}"


def _coordinator_details(record) -> tuple[str, str]:
    chain = schemes.parse_chain(record.get("approval_chain"))
    stage = next((item for item in chain if clean(item.get("role")) == "admin"), {})
    email = clean(stage.get("email")).lower()
    directory_user = get_user_by_email(email) if email else {}
    name = clean(stage.get("name")) or clean(directory_user.get("full_name")) or email or "—"
    phone = clean(directory_user.get("phone")) or "—"
    return name, phone


def _auto_textarea_height(value, min_height=68, max_height=260) -> int:
    text = clean(value)
    logical_lines = text.splitlines() or [""]
    visual_lines = sum(max(1, (len(line) // 90) + 1) for line in logical_lines)
    return min(max_height, max(min_height, 44 + visual_lines * 22))


def _next_stage_has_acted(logs: pd.DataFrame, chain: list[dict]) -> bool:
    """True, якщо перша після подавача ланка вже зробила будь-яку дію."""
    if not chain or logs is None or logs.empty:
        return False

    first_stage = chain[0] or {}
    stage_email = clean(first_stage.get("email")).lower()
    stage_name = clean(first_stage.get("name")).casefold()
    stage_role = clean(first_stage.get("role")).casefold()

    for _, log_row in logs.iterrows():
        actor_email = clean(log_row.get("actor_email")).lower()
        actor_name = clean(log_row.get("actor_name")).casefold()
        actor_role = clean(log_row.get("actor_role")).casefold()
        changed_by = clean(log_row.get("changed_by")).casefold()

        if stage_email and (actor_email == stage_email or stage_email in changed_by):
            return True
        if stage_name and actor_name == stage_name:
            return True
        if stage_role and actor_role == stage_role:
            return True
    return False


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
        Кабінет самостійного структурного підрозділу призначений для перегляду поданих відомостей,
        відстеження статусу погодження, історії змін та повторного подання відомостей після доопрацювання.
    </div>
</div>
""", unsafe_allow_html=True)

render_submission_notice()

if df.empty:
    st.warning("Поки що немає поданих відомостей.")
    render_footer()
    st.stop()


# ============================================================
# FILTERS
# ============================================================

if "my_requests_filters_applied" not in st.session_state:
    st.session_state.my_requests_filters_applied = {
        "year": "Усі",
        "status": "Усі",
        "search": "",
    }

_applied_defaults = st.session_state.my_requests_filters_applied
st.session_state.setdefault("my_req_year_pending", _applied_defaults.get("year", "Усі"))
st.session_state.setdefault("my_req_status_pending", _applied_defaults.get("status", "Усі"))
st.session_state.setdefault("my_req_search_pending", _applied_defaults.get("search", ""))


def _apply_my_requests_filters():
    st.session_state.my_requests_filters_applied = {
        "year": st.session_state.get("my_req_year_pending", "Усі"),
        "status": st.session_state.get("my_req_status_pending", "Усі"),
        "search": st.session_state.get("my_req_search_pending", ""),
    }


def _reset_my_requests_filters():
    st.session_state.my_requests_filters_applied = {"year": "Усі", "status": "Усі", "search": ""}
    st.session_state.my_req_year_pending = "Усі"
    st.session_state.my_req_status_pending = "Усі"
    st.session_state.my_req_search_pending = ""


years = ["Усі"] + sorted(df["year"].dropna().astype(str).unique().tolist())

with st.form("my_requests_filters_form"):
    st.markdown('<div class="filter-title">Параметри відбору</div>', unsafe_allow_html=True)
    f1, f2, f3 = st.columns([0.85, 1.2, 1.7])
    with f1:
        st.markdown('<div class="filter-field-label">Рік</div>', unsafe_allow_html=True)
        st.selectbox(
            "Рік", years, key="my_req_year_pending",
            label_visibility="collapsed",
        )
    with f2:
        st.markdown('<div class="filter-field-label">Статус погодження</div>', unsafe_allow_html=True)
        st.selectbox(
            "Статус погодження", APPROVAL_FILTER_OPTIONS,
            key="my_req_status_pending", label_visibility="collapsed",
        )
    with f3:
        st.markdown(
            '<div class="filter-field-label">Пошук за ID або кодом заходу</div>',
            unsafe_allow_html=True,
        )
        st.text_input(
            "Пошук за ID або кодом заходу",
            key="my_req_search_pending",
            label_visibility="collapsed",
            placeholder="Введіть ID або код",
        )

    b1, b2 = st.columns([1, 1])
    with b1:
        st.form_submit_button(
            "Застосувати обрані параметри",
            use_container_width=True,
            on_click=_apply_my_requests_filters,
        )
    with b2:
        st.form_submit_button(
            "Скинути параметри",
            use_container_width=True,
            on_click=_reset_my_requests_filters,
        )

_applied = st.session_state.my_requests_filters_applied
filtered = df.copy()

selected_year = _applied.get("year", "Усі")
selected_status = _applied.get("status", "Усі")
search = str(_applied.get("search", "") or "")

if selected_year != "Усі":
    filtered = filtered[filtered["year"].astype(str) == str(selected_year)]

if selected_status == "Активні до розгляду":
    filtered = filtered[filtered["approval_status"].astype(str).isin(ACTIVE_APPROVAL_STATUSES)]
elif selected_status != "Усі":
    filtered = filtered[filtered["approval_status"].astype(str) == selected_status]

if search.strip():
    sq = search.strip().lower()
    filtered = filtered[
        filtered["id"].astype(str).str.lower().str.contains(sq, na=False)
        | filtered["strat_code"].astype(str).str.lower().str.contains(sq, na=False)
    ]

if not filtered.empty:
    filtered["_returned_rank"] = (
        filtered["approval_status"].astype(str) != "Повернуто на доопрацювання"
    ).astype(int)
    filtered["_submitted_sort"] = pd.to_datetime(filtered["submitted_at"], errors="coerce")
    filtered = (
        filtered.sort_values(
            ["_returned_rank", "_submitted_sort"], ascending=[True, False]
        )
        .drop(columns=["_returned_rank", "_submitted_sort"], errors="ignore")
    )

filtered["_visual_status"] = filtered.apply(
    lambda row: "Не настав час"
    if is_period_locked(row.get("year"), row.get("quarter"))
    else row.get("status", ""),
    axis=1,
)

st.caption(f"Знайдено відомостей: {len(filtered)}")

if filtered.empty:
    st.info("За обраними параметрами відбору відомостей не знайдено.")
    render_footer()
    st.stop()


# ============================================================
# METRICS
# ============================================================

total = len(filtered)
_approval_series = filtered["approval_status"].fillna("").astype(str).str.strip()
_waiting_statuses = set(schemes.ALL_WAITING_STATUSES)
_returned_mask = _approval_series.eq("Повернуто на доопрацювання")
_approved_mask = _approval_series.eq("Погоджено")
_waiting_mask = _approval_series.isin(_waiting_statuses)
# Невідомий або новий статус не губиться з математичного підсумку: доки він
# не є «Повернуто» чи «Погоджено», відносимо його до укрупненої «На розгляді».
_other_open_mask = ~(_returned_mask | _approved_mask | _waiting_mask)

approved = int(_approved_mask.sum())
returned = int(_returned_mask.sum())
on_review = int((_waiting_mask | _other_open_mask).sum())

m1, m2, m3, m4 = st.columns(4)
m1.metric("Усього відомостей", total)
m2.metric("На розгляді", on_review)
m3.metric("Повернуто на доопрацювання", returned)
m4.metric("Погоджено", approved)


# ============================================================
# REQUEST LIST — HTML TABLE
# ============================================================

st.markdown(
    '<div class="myreq-section-header"><div class="myreq-section-title">'
    'Перелік поданих відомостей</div></div>',
    unsafe_allow_html=True,
)

_table_rows = []
for _, _row in filtered.iterrows():
    _coord_name, _coord_phone = _coordinator_details(_row)
    _table_rows.append(
        "<tr>"
        f"<td>{display_text(_row.get('id'))}</td>"
        f"<td>{display_text(_period_label(_row.get('year'), _row.get('quarter')))}</td>"
        f"<td>{display_text(_target_for_record(_row))}</td>"
        f"<td>{display_text(_fact_for_record(_row))}</td>"
        f"<td>{display_text(_row.get('_visual_status'))}</td>"
        f"<td>{display_text(_row.get('approval_status'))}</td>"
        f"<td>{display_text(_coord_name)}</td>"
        f"<td>{display_text(_coord_phone)}</td>"
        f"<td>{display_text(_row.get('admin_comment'))}</td>"
        f"<td>{display_text(format_kyiv_datetime(_row.get('submitted_at')))}</td>"
        "</tr>"
    )

st.markdown(
    """
    <div class="myreq-table-scroll">
      <table class="myreq-html-table">
        <thead>
          <tr>
            <th>ID заявки</th>
            <th>Звітний період</th>
            <th>Цільовий орієнтир</th>
            <th>Фактичне значення</th>
            <th>Статус виконання</th>
            <th>Статус погодження</th>
            <th>Координатор</th>
            <th>Номер телефону координатора</th>
            <th>Коментар координатора</th>
            <th>Дата подання</th>
          </tr>
        </thead>
        <tbody>
    """
    + "".join(_table_rows)
    + """
        </tbody>
      </table>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DETAILED VIEW
# ============================================================

st.markdown(
    '<div class="myreq-section-header"><div class="myreq-section-title">'
    'Детальний перегляд заявки</div></div>',
    unsafe_allow_html=True,
)

options = [
    f"ID {row['id']} | {row['strat_code']} | {row['year']} {row['quarter']} квартал | {row['approval_status']}"
    for _, row in filtered.iterrows()
]
selected = st.selectbox("Оберіть заявку", options)

selected_id = int(selected.split("|")[0].replace("ID", "").strip())
selected_row = filtered[filtered["id"].astype(int) == selected_id].iloc[0]

approval = clean(selected_row["approval_status"])
code = clean(selected_row["strat_code"])
badge_class = status_badge_class(approval)
selected_target = _target_for_record(selected_row)
selected_fact = _fact_for_record(selected_row)

st.markdown(f"""
<div class="badge-wrap">
    <div class="badge {badge_class}">Статус погодження: {display_text(approval)}</div>
    <div class="badge">Заявка ID {selected_id}</div>
    <div class="badge">Код {display_text(code)}</div>
    <div class="badge">{display_text(_period_label(selected_row["year"], selected_row["quarter"]))}</div>
</div>
""", unsafe_allow_html=True)

_kind = clean(selected_row.get("object_kind"))
_indicator_name = clean(selected_row.get("indicator_name"))
measure_info = strat_df[
    strat_df["code"].astype(str).str.strip().str.rstrip(".") == code.rstrip(".")
].copy()
if _kind == "indicator" and _indicator_name and "indicator" in measure_info.columns:
    _matched_indicator = measure_info[
        measure_info["indicator"].astype(str).str.strip().str.casefold()
        == _indicator_name.casefold()
    ]
    if not _matched_indicator.empty:
        measure_info = _matched_indicator

if not measure_info.empty:
    mi = measure_info.iloc[0]
    st.markdown(f"""
    <div class="step-box">
        <b>{display_text(code)} {display_text(_strategic_object_name_by_code(code), fallback="")}</b><br>
        <span style="color:#61708A;">Індикатор: {display_text(mi.get("indicator"))}</span><br>
        <span style="color:#61708A;">Одиниця виміру: {display_text(mi.get("unit"))}</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown(f"""
<div class="info-grid">
    <div class="info-card info-card-blue">
        <div class="info-label">Статус виконання</div>
        <div class="info-value">{display_text(selected_row["_visual_status"])}</div>
    </div>
    <div class="info-card info-card-yellow">
        <div class="info-label">Цільовий орієнтир</div>
        <div class="info-value">{display_text(selected_target)}</div>
    </div>
    <div class="info-card info-card-green">
        <div class="info-label">Фактичне значення</div>
        <div class="info-value">{display_text(selected_fact)}</div>
    </div>
</div>
""", unsafe_allow_html=True)

d1, d2 = st.columns(2)
with d1:
    st.text_input(
        "Початкова дата виконання",
        value=clean(selected_row["start_date"]),
        disabled=True,
        key=f"view_start_{selected_id}",
    )
with d2:
    st.text_input(
        "Кінцева дата виконання",
        value=clean(selected_row["end_date"]),
        disabled=True,
        key=f"view_end_{selected_id}",
    )

st.markdown(
    f'<div class="myreq-detail-field"><div class="myreq-detail-label">Опис прогресу</div>'
    f'<div class="myreq-detail-value">{display_text(selected_row.get("progress_text"))}</div></div>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<div class="myreq-detail-field"><div class="myreq-detail-label">Ризики / проблеми / відхилення</div>'
    f'<div class="myreq-detail-value">{display_text(selected_row.get("risks"))}</div></div>',
    unsafe_allow_html=True,
)

if has_value(selected_row.get("admin_comment")):
    st.markdown(f"""
    <div class="comment-box">
        <div class="comment-title">Коментар координатора</div>
        <div class="comment-text">{display_text(selected_row.get("admin_comment"))}</div>
    </div>
    """, unsafe_allow_html=True)

_npa_raw = clean(selected_row.get("npa_link"))
if _npa_raw:
    _links_html = "".join(
        f'<div>🔗 <a href="{escape(u.strip())}" target="_blank">{escape(u.strip())}</a></div>'
        for u in re.split(r"[\n;,]+", _npa_raw)
        if u.strip()
    )
    st.markdown(
        f'<div class="myreq-detail-field"><div class="myreq-detail-label">Посилання на НПА</div>'
        f'<div class="myreq-detail-value">{_links_html}</div></div>',
        unsafe_allow_html=True,
    )

_chain = schemes.parse_chain(selected_row.get("approval_chain"))
_request_stage_idx = schemes.parse_stage(selected_row.get("chain_stage"))
logs_df = load_logs(selected_id)

if _chain:
    _scheme_lbl = clean(selected_row.get("scheme_label"))
    st.markdown(f"""
    <div class="myreq-scheme-box">
        <div class="myreq-scheme-title">Схема погодження{(" · " + escape(_scheme_lbl)) if _scheme_lbl else ""}</div>
        <div class="myreq-scheme-text">
            {escape(schemes.chain_route_text(_chain))}<br>
            <b>{escape(schemes.chain_progress_text(_chain, _request_stage_idx, approval))}</b>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── У кого зараз заявка та чи потрібна ваша дія ──
def _render_holder_strip():
    _now = now_kyiv()
    _last_ts = None
    if not logs_df.empty and "changed_at" in logs_df.columns:
        _last_ts = pd.to_datetime(logs_df["changed_at"], errors="coerce", utc=True).max()
    if _last_ts is None or pd.isna(_last_ts):
        _last_ts = pd.to_datetime(
            clean(selected_row.get("submitted_at", "")), errors="coerce", utc=True
        )

    _days_txt = ""
    if _last_ts is not None and not pd.isna(_last_ts):
        _days = max(0, (_now - _last_ts.to_pydatetime()).days)
        _days_txt = f" · на цьому кроці {_days} дн."

    if approval == "Погоджено":
        _holder = "Погодження завершено"
        _action = ("✅ Дій від вас не потрібно", "#E4F5EC", "#1E9E57", "#0C713A")
    elif approval == "Повернуто на доопрацювання":
        _holder = "Заявка у вас (повернута на доопрацювання)"
        _action = (
            "✍️ Потребує вашої дії — виправте дані та подайте повторно",
            "#FDF3D8", "#FF7A45", "#8A6400",
        )
    elif _chain:
        _st = schemes.current_stage(_chain, _request_stage_idx)
        _holder = (
            f"Зараз у: {clean((_st or {}).get('label', ''))} — "
            f"{clean((_st or {}).get('name', '') or (_st or {}).get('email', ''))}"
        )
        _action = ("⏳ На розгляді — дій від вас не потрібно", "#EAF1FF", "#BFD3F2", "#032A63")
    else:
        _holder = "На розгляді"
        _action = ("⏳ На розгляді — дій від вас не потрібно", "#EAF1FF", "#BFD3F2", "#032A63")

    st.markdown(
        f'<div style="display:flex;flex-wrap:wrap;gap:10px;margin:6px 0 10px 0;">'
        f'<div style="background:#F7F9FC;border:1px solid #DCE4F0;border-radius:10px;'
        f'padding:8px 12px;font-size:13px;font-weight:700;color:#132238;">'
        f'📍 {escape(_holder)}{escape(_days_txt)}</div>'
        f'<div style="background:{_action[1]};border:1px solid {_action[2]};'
        f'border-radius:10px;padding:8px 12px;font-size:13px;font-weight:700;'
        f'color:{_action[3]};">{_action[0]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


_render_holder_strip()


# ============================================================
# EARLY EDIT / WITHDRAW — until the first approval stage acts
# ============================================================

_first_stage_waiting = schemes.waiting_status_for_stage(_chain[0]) if _chain else ""
_next_stage_acted = _next_stage_has_acted(logs_df, _chain)
_can_early_modify = bool(
    _chain
    and approval in set(schemes.ALL_WAITING_STATUSES)
    and approval == _first_stage_waiting
    and _request_stage_idx == 0
    and not _next_stage_acted
    and not schemes.is_final_locked(selected_row)
)

if _can_early_modify:
    with st.expander("✏️ Редагувати подану інформацію (без очікування повернення)"):
        st.caption(
            "Оновлені дані буде збережено, а заявка залишиться на поточній ланці "
            "схеми погодження. Факт редагування та нова версія зафіксуються в історії. "
            "Маршрут погодження не перезапускається і не повертається до координатора."
        )

        _de_status_options = list(SUBMISSION_STATUS_OPTIONS)
        _de_current_status = clean(selected_row["status"])
        _de_status_index = (
            _de_status_options.index(_de_current_status)
            if _de_current_status in _de_status_options else 0
        )

        de_new_status = st.selectbox(
            "Статус виконання",
            _de_status_options,
            index=_de_status_index,
            key=f"direct_edit_status_{selected_id}",
        )
        de_new_value = st.text_input(
            "Фактичне значення",
            value=clean(selected_row["numeric_value"]) or clean(selected_row.get("value_text")),
            key=f"direct_edit_value_{selected_id}",
        )
        de_new_progress = st.text_area(
            "Опис прогресу",
            value=clean(selected_row["progress_text"]),
            height=_auto_textarea_height(selected_row["progress_text"]),
            key=f"direct_edit_progress_{selected_id}",
        )
        de_new_risks = st.text_area(
            "Ризики / проблеми / відхилення",
            value=clean(selected_row["risks"]),
            height=_auto_textarea_height(selected_row["risks"]),
            key=f"direct_edit_risks_{selected_id}",
        )
        de_new_npa = st.text_area(
            "Посилання на НПА",
            value=clean(selected_row.get("npa_link")),
            height=_auto_textarea_height(selected_row.get("npa_link")),
            key=f"direct_edit_npa_{selected_id}",
        )

        de_submit = st.button(
            "💾 Зберегти відредаговані відомості",
            use_container_width=True,
            key=f"direct_edit_submit_{selected_id}",
        )

        if de_submit:
            de_errors = []
            if not has_value(de_new_value):
                de_errors.append("Заповніть фактичне значення.")
            if not has_value(de_new_progress):
                de_errors.append("Заповніть опис прогресу.")

            if de_errors:
                for error in de_errors:
                    st.error(error)
            else:
                update_payload = prepare_monitoring_payload({
                    "status": de_new_status,
                    "numeric_value": de_new_value,
                    "progress_text": de_new_progress,
                    "risks": de_new_risks,
                    "npa_link": de_new_npa,
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                    "log_comment": (
                        "Подавач відредагував подані відомості до першої дії "
                        "наступної ланки; маршрут і поточна ланка не змінені."
                    ),
                })
                try:
                    resubmit_request(
                        request_id=int(selected_id),
                        expected_updated_at=clean(selected_row.get("updated_at")),
                        expected_status=approval,
                        expected_chain_stage=int(_request_stage_idx),
                        target_chain_stage=int(_request_stage_idx),
                        payload=update_payload,
                        mode="stage_edit",
                        action="Редагування поданих відомостей подавачем",
                        user=current_user,
                        created_by_before="ССП / до редагування",
                        created_by_after="ССП / відредаговані відомості",
                        draft_email="",
                        draft_key="",
                    )
                    st.session_state["my_requests_edit_notice"] = (
                        "Відредаговані відомості збережено. Заявка залишилася "
                        "на поточній ланці схеми погодження."
                    )
                    st.session_state["my_requests_edit_notice_ts"] = now_kyiv().isoformat()
                    monitoring_data.invalidate_monitoring_cache()
                    st.rerun()
                except TransitionRejected as exc:
                    st.error(exc.message)
                except Exception as exc:
                    show_incident(exc, context="Атомарне редагування заявки подавачем")

    with st.expander("↩️ Відкликати заявку"):
        st.warning(
            "Відкликання повністю знімає заявку з розгляду. Після цього ви "
            "зможете подати за цим об’єктом нову заявку у вкладці "
            "«Моніторинг (внесення відомостей)». Запис про відкликання та "
            "всі подані дані залишаться в журналі дій."
        )
        _wd_confirm = st.checkbox(
            "Підтверджую, що хочу відкликати цю заявку",
            key=f"withdraw_confirm_{selected_id}",
        )
        _wd_click = st.button(
            "Відкликати заявку",
            use_container_width=True,
            disabled=not _wd_confirm,
            key=f"withdraw_btn_{selected_id}",
        )
        if _wd_click:
            try:
                _wd_snapshot = (
                    f"Відкликано подавачем. Дані на момент відкликання: "
                    f"код {clean(selected_row.get('strat_code', ''))}; "
                    f"період {clean(selected_row.get('year', ''))}, "
                    f"{clean(selected_row.get('quarter', ''))} квартал; "
                    f"статус виконання «{clean(selected_row.get('status', ''))}»; "
                    f"фактичне значення «{_fact_for_record(selected_row)}»; "
                    f"опис прогресу «{clean(selected_row.get('progress_text', ''))}»; "
                    f"ризики «{clean(selected_row.get('risks', ''))}»."
                )
                atomic_withdraw_request(
                    request_id=int(selected_id),
                    expected_status=approval,
                    expected_chain_stage=int(_request_stage_idx),
                    comment=_wd_snapshot,
                    user=current_user,
                )
                monitoring_data.invalidate_monitoring_cache()
                st.success("Заявку відкликано.")
                st.rerun()
            except TransitionRejected as exc:
                st.error(exc.message)
            except Exception as exc:
                show_incident(exc, context="Атомарне відкликання заявки")


# ── Тимчасове підтвердження успішного редагування ──
_edit_notice = st.session_state.get("my_requests_edit_notice", "")
_edit_notice_ts_raw = st.session_state.get("my_requests_edit_notice_ts", "")
_edit_notice_active = False
_edit_notice_remaining_ms = 0

if _edit_notice and _edit_notice_ts_raw:
    try:
        _edit_notice_ts = (
            _edit_notice_ts_raw
            if isinstance(_edit_notice_ts_raw, datetime)
            else datetime.fromisoformat(str(_edit_notice_ts_raw))
        )
        _edit_notice_age = max(0.0, (now_kyiv() - _edit_notice_ts).total_seconds())
        if _edit_notice_age < 60:
            _edit_notice_active = True
            _edit_notice_remaining_ms = max(1000, int((60 - _edit_notice_age) * 1000) + 250)
        else:
            st.session_state.pop("my_requests_edit_notice", None)
            st.session_state.pop("my_requests_edit_notice_ts", None)
    except (TypeError, ValueError):
        st.session_state.pop("my_requests_edit_notice", None)
        st.session_state.pop("my_requests_edit_notice_ts", None)

if _edit_notice_active:
    st.success(_edit_notice)
    import streamlit.components.v1 as components

    components.html(
        f"""
        <script>
        setTimeout(function() {{ window.parent.location.reload(); }}, {_edit_notice_remaining_ms});
        </script>
        """,
        height=0,
    )


# ============================================================
# STATUS HISTORY
# ============================================================

st.markdown(
    '<div class="myreq-section-header"><div class="myreq-section-title">'
    'Історія зміни статусу</div></div>',
    unsafe_allow_html=True,
)
render_request_timeline(logs_df, with_table_expander=False)


# ============================================================
# VERSION HISTORY — expandable table only
# ============================================================

versions_df = load_versions(selected_id)
with st.expander("Історія версій заявки", expanded=False):
    if versions_df.empty:
        st.info("Версій для цієї заявки поки що немає.")
    else:
        _version_rows = []
        for _, version_row in versions_df.sort_values("version_number", ascending=False).iterrows():
            _version_rows.append({
                "Версія заявки": clean(version_row.get("version_number")) or "—",
                "Дата створення": format_kyiv_datetime(version_row.get("created_at")),
                "Ким створено": clean(version_row.get("created_by")) or "система",
                "Статус погодження": clean(version_row.get("approval_status")) or "—",
                "Цільовий орієнтир": _target_for_record(version_row),
                "Фактичне значення": _fact_for_record(version_row),
                "Статус виконання": clean(version_row.get("status")) or "—",
                "Опис прогресу": clean(version_row.get("progress_text")) or "—",
                "Ризики/проблеми/відхилення": clean(version_row.get("risks")) or "—",
                "Посилання на НПА": clean(version_row.get("npa_link")) or "—",
            })
        versions_show = pd.DataFrame(_version_rows)
        st.dataframe(
            style_status_columns(
                versions_show,
                ["Статус погодження", "Статус виконання"],
            ),
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# RESUBMIT AFTER RETURN
# ============================================================

if approval == "Повернуто на доопрацювання":
    st.markdown(
        '<div class="myreq-section-header"><div class="myreq-section-title">'
        'Редагування та повторне подання</div></div>',
        unsafe_allow_html=True,
    )
    st.caption("Цей блок доступний для заявки, повернутої на доопрацювання.")

    _resubmit_chain = schemes.parse_chain(selected_row.get("approval_chain"))
    _status_options = list(SUBMISSION_STATUS_OPTIONS)
    current_status = clean(selected_row["status"])
    default_status_index = _status_options.index(current_status) if current_status in _status_options else 0

    new_status = st.selectbox(
        "Статус виконання",
        _status_options,
        index=default_status_index,
        key=f"edit_status_{selected_id}",
    )
    new_value = st.text_input(
        "Фактичне значення",
        value=clean(selected_row["numeric_value"]) or clean(selected_row.get("value_text")),
        key=f"edit_value_{selected_id}",
    )
    new_progress = st.text_area(
        "Опис прогресу",
        value=clean(selected_row["progress_text"]),
        height=_auto_textarea_height(selected_row["progress_text"]),
        key=f"edit_progress_{selected_id}",
    )
    new_risks = st.text_area(
        "Ризики / проблеми / відхилення",
        value=clean(selected_row["risks"]),
        height=_auto_textarea_height(selected_row["risks"]),
        key=f"edit_risks_{selected_id}",
    )
    new_npa = st.text_area(
        "Посилання на НПА",
        value=clean(selected_row.get("npa_link")),
        height=_auto_textarea_height(selected_row.get("npa_link")),
        key=f"edit_npa_{selected_id}",
    )

    e1, e2, e3 = st.columns(3)
    with e1:
        new_responsible = st.text_input(
            "ПІБ відповідальної особи",
            value=prefilled_contacts.get("full_name") or clean(selected_row["responsible_person"]),
            key=f"edit_responsible_{selected_id}",
            disabled=True,
        )
    with e2:
        new_phone = st.text_input(
            "Телефон",
            value=prefilled_contacts.get("phone") or clean(selected_row["phone"]),
            key=f"edit_phone_{selected_id}",
            disabled=True,
        )
    with e3:
        new_email = st.text_input(
            "Email",
            value=prefilled_contacts.get("email") or clean(selected_row["email"]),
            key=f"edit_email_{selected_id}",
            disabled=True,
        )

    resubmit = st.button(
        "Повторно подати на погодження",
        use_container_width=True,
        key=f"resubmit_{selected_id}",
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

        if errors:
            st.error("Повторне подання не виконано:")
            for error in errors:
                st.error(error)
        else:
            update_payload = prepare_monitoring_payload({
                "status": new_status,
                "numeric_value": new_value,
                "progress_text": new_progress,
                "risks": new_risks,
                "npa_link": new_npa,
                "responsible_person": new_responsible,
                "phone": new_phone,
                "email": new_email,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "admin_comment": "",
                "log_comment": "Заявку повторно подано ССП",
            })
            try:
                result = resubmit_request(
                    request_id=int(selected_id),
                    expected_updated_at=clean(selected_row.get("updated_at")),
                    expected_status="Повернуто на доопрацювання",
                    expected_chain_stage=int(_request_stage_idx),
                    target_chain_stage=0,
                    payload=update_payload,
                    mode="returned",
                    action="Повторне подання після доопрацювання",
                    user=current_user,
                    created_by_before="ССП / до повторного подання",
                    created_by_after="ССП / повторне подання",
                    draft_email="",
                    draft_key="",
                )

                try:
                    if _resubmit_chain:
                        _first = _resubmit_chain[0]
                        notify_events.notify_stage_assigned(
                            _first.get("email", ""),
                            _first.get("name", ""),
                            _first.get("label", ""),
                            clean(selected_row.get("strat_code", "")),
                            clean(selected_row.get("year", "")),
                            clean(selected_row.get("quarter", "")),
                            submitter=clean(new_responsible),
                            kind=clean(selected_row.get("object_kind", "")) or "measure",
                        )
                except Exception as notify_exc:
                    show_warning(
                        "Заявку повторно подано, але першій ланці не відправлено миттєвий лист.",
                        notify_exc,
                        "Email після повторного подання заявки",
                    )

                set_submission_notice(
                    first_stage_label=(
                        result.data.get("first_stage_label")
                        or (_resubmit_chain[0].get("label") if _resubmit_chain else "Перша ланка")
                    ),
                    codes=[clean(selected_row.get("strat_code"))],
                    repeated=True,
                )
                monitoring_data.invalidate_monitoring_cache()
                st.rerun()
            except TransitionRejected as exc:
                st.error(exc.message)
            except Exception as exc:
                show_incident(exc, context="Атомарне повторне подання заявки після доопрацювання")


# ============================================================
# FOOTER
# ============================================================

render_footer()
