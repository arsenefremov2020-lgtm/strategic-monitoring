import streamlit as st
import pandas as pd
from core.data_types import normalise_closeout_frame, prepare_monitoring_payload
from core.db import fetch_all, get_supabase_client
from core.ui import load_css, prepare_human_log_table, render_request_timeline
from core.errors import log_cosmetic_error, show_incident, show_warning
from core.config import FILE_PATH, SHEET_NAME
from core.excel_loader import read_excel_sheet
from datetime import datetime, timezone
from html import escape
import re
from core.page_setup import page_setup, render_footer
from core.period_locks import is_period_locked
from core.stage4 import format_kyiv_datetime, quarter_to_roman
from core.strategic_data import load_strat_matrix as core_load_strat_matrix
from core import monitoring_data
from core.statuses import SUBMISSION_STATUS_OPTIONS
from core.validation import (
    cumulative_quarter_decrease_error,
    status_value_conflict,
    validate_fact_value_for_target,
)
from core.versioning import coordinator_stage_index
from core.transitions import (
    TransitionRejected,
    approve_request_step,
    resubmit_request,
    return_request as atomic_return_request,
)
from core.submission_ui import NOTICE_KEY, set_submission_notice

from core.access import (
    filter_requests_for_user,
    get_available_ssp_options_for_user,
    should_lock_ssp_fields,
    user_has_all_ssp_access,
)
from core import approval_schemes as schemes
from core import notify_events
from config.roles import ROLE_SSP_HEAD, ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY

current_user = page_setup("Мій кабінет", page_name="Мій кабінет")
supabase = get_supabase_client()
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
    margin-bottom: 18px;
    box-shadow: 0 8px 24px rgba(15,23,42,0.06);
}
.header-box {
    padding: 16px 22px;
}
.card {
    padding: 22px 26px;
}
.cabinet-section-card {
    padding: 12px 18px;
    margin-bottom: 10px;
}
.cabinet-section-card .card-title {
    margin-bottom: 0;
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
[data-testid="stMain"] div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stMain"] div[data-testid="stTextInput"] input,
[data-testid="stMain"] div[data-testid="stTextArea"] textarea {
    background-color: #EAF1FF !important;
    border: 1px solid #BFD3F2 !important;
    border-radius: 10px !important;
    box-shadow: inset 0 1px 2px rgba(15,23,42,0.08) !important;
}
[data-testid="stMain"] div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stMain"] div[data-testid="stTextInput"] input {
    min-height: 43px !important;
}
[data-testid="stMain"] div[data-testid="stSelectbox"] label,
[data-testid="stMain"] div[data-testid="stTextInput"] label,
[data-testid="stMain"] div[data-testid="stTextArea"] label {
    font-weight: 750 !important;
    color: #132238 !important;
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
.badge-green { background: #E4F5EC; border: 1px solid #1E9E57; color: #0C713A; }
.badge-yellow { background: #FDF3D8; border: 1px solid #F4B400; color: #8A6400; }
.badge-red { background: #FBE5E5; border: 1px solid #DC4A4A; color: #DC4A4A; }
.badge-gray { background: #F7F9FC; border: 1px solid #DCE4F0; color: #61708A; }
.badge-blue { background: #E3EDFF; border: 1px solid #BFD3F2; color: #032A63; }
.badge-purple { background: #f3e8ff; border: 1px solid #d8b4fe; color: #6b21a8; }

.info-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    margin-top: 14px;
}
.info-card {
    border-radius: 14px;
    padding: 16px 18px;
    min-height: 105px;
    border: 1px solid #DCE4F0;
    overflow-wrap: anywhere;
}
.info-card-blue { background: #EAF1FF; border-color: #BFD3F2; }
.info-card-green { background: #E4F5EC; border-color: #1E9E57; }
.info-card-yellow { background: #FDF3D8; border-color: #F4B400; }
.info-card-red { background: #FBE5E5; border-color: #DC4A4A; }
.info-card-gray { background: #F7F9FC; border-color: #DCE4F0; }
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
.comment-box {
    background: #FDF3D8;
    border: 1px solid #FF7A45;
    color: #FF7A45;
    border-radius: 16px;
    padding: 18px 20px;
    margin: 18px 0 6px 0;
    box-shadow: 0 8px 20px rgba(245,158,11,0.12);
}
.comment-box.cabinet-muted-box {
    background: #FFF8E8;
    border: 1px solid #E5C66B;
    color: #5E4A18;
    border-radius: 14px;
    padding: 14px 16px;
    margin: 14px 0 6px 0;
    box-shadow: 0 4px 12px rgba(138,100,0,0.08);
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

.cabinet-readonly-block {
    background: #EAF1FF;
    border: 1px solid #BFD3F2;
    border-radius: 12px;
    padding: 12px 14px;
    margin: 10px 0;
}
.cabinet-readonly-label {
    color: #132238;
    font-size: 12px;
    font-weight: 900;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.cabinet-readonly-value {
    color: #132238;
    font-size: 15px;
    font-weight: 850;
    line-height: 1.6;
    overflow-wrap: anywhere;
    white-space: pre-wrap;
}
.cabinet-readonly-value a {
    color: #005BBB;
    font-weight: 850;
    text-decoration: underline;
    text-underline-offset: 2px;
}
.cabinet-route-caption {
    color: #5E4A18;
    font-size: 12px;
    font-weight: 850;
    margin-bottom: 8px;
}
.cabinet-route-row {
    display: flex;
    flex-wrap: nowrap;
    align-items: stretch;
    gap: 7px;
    overflow-x: auto;
    padding: 2px 0 6px;
    scrollbar-width: thin;
}
.cabinet-route-node {
    flex: 0 0 auto;
    min-width: 150px;
    max-width: 250px;
    background: #EAF1FF;
    border: 1px solid #BFD3F2;
    border-radius: 10px;
    padding: 8px 10px;
    color: #132238;
    font-size: 12px;
    font-weight: 800;
    line-height: 1.4;
}
.cabinet-route-node.current {
    background: #FFF4ED;
    border: 2px solid #FF7A45;
    box-shadow: 0 0 0 2px rgba(255,122,69,0.10);
}
.cabinet-route-role {
    display: block;
    color: #132238;
    font-size: 11px;
    font-weight: 900;
    margin-bottom: 3px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.cabinet-route-arrow {
    flex: 0 0 auto;
    align-self: center;
    color: #61708A;
    font-size: 18px;
    font-weight: 900;
}
[data-testid="stMain"] div[data-testid="stForm"]:has(.cabinet-filter-form-marker) div[data-testid="stFormSubmitButton"] button {
    background: #FFFFFF !important;
    border: 1.5px solid #BFD3F2 !important;
    color: #132238 !important;
    box-shadow: none !important;
}
[data-testid="stMain"] div[data-testid="stForm"]:has(.cabinet-filter-form-marker) div[data-testid="stFormSubmitButton"] button:hover {
    background: #F7F9FC !important;
    border-color: #9FBCE8 !important;
    color: #132238 !important;
    box-shadow: none !important;
}

/* ── Панель рішення ланки: той самий спокійний підхід, що й в адмінці ── */
.sign-panel {
    background: #FFFFFF;
    border: 1px solid #DCE4F0;
    border-left: 4px solid #4D8DFF;
    border-radius: 12px;
    padding: 11px 15px;
    margin: 10px 0 8px 0;
    box-shadow: 0 3px 10px rgba(15,23,42,0.045);
}
.sign-panel-title {
    font-size: 17px;
    font-weight: 900;
    color: #132238;
    margin-bottom: 3px;
}
.sign-panel-sub {
    font-size: 13px;
    color: #61708A;
    line-height: 1.45;
    margin-bottom: 0;
}
.cabinet-decision-card {
    background: #FFFFFF;
    border: 1px solid #DCE4F0;
    border-radius: 12px;
    padding: 13px 17px;
    margin: 8px 0 10px 0;
}
.cabinet-decision-guidance {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-left: 4px solid #4D8DFF;
    border-radius: 10px;
    padding: 10px 13px;
    margin: 7px 0 10px 0;
    color: #132238;
    font-size: 13px;
    font-weight: 650;
    line-height: 1.55;
}
.cabinet-decision-guidance p {
    margin: 0 0 7px 0;
}
.cabinet-decision-guidance p:last-child {
    margin-bottom: 0;
}
.cabinet-control-label,
.cabinet-comment-header {
    color: #132238;
    font-size: 14px;
    font-weight: 900;
    line-height: 1.35;
    margin: 7px 0 6px 0;
}
.cabinet-decision-box {
    background: #EAF1FF;
    border: 1px solid #BFD3F2;
    border-radius: 10px;
    color: #132238;
    font-size: 13px;
    font-weight: 800;
    line-height: 1.45;
    padding: 9px 12px;
    margin: 8px 0 10px 0;
}
/* Кнопка підтвердити — зелена */
div[data-testid="stButton"].sign-btn > button {
    background: #118847 !important;
    color: #fff !important;
    border: none !important;
    font-size: 16px !important;
    padding: 14px 22px !important;
}
div[data-testid="stButton"].return-ssp-btn > button {
    background: #FDF3D8 !important;
    color: #8A6400 !important;
    border: 1px solid #F4B400 !important;
}
div[data-testid="stButton"].return-coord-btn > button {
    background: #FBE5E5 !important;
    color: #DC4A4A !important;
    border: 1px solid #DC4A4A !important;
}

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.9);
    border: 1px solid #DCE4F0;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
}

[data-testid="stMain"] div.stButton > button {
    border-radius: 14px;
    padding: 12px 18px;
    font-weight: 900;
    border: 1px solid #BFD3F2;
    background: #EAF1FF !important;
    color: #005BBB !important;
    box-shadow: 0 8px 18px rgba(37,99,235,0.10);
}
[data-testid="stMain"] div.stButton > button:hover {
    filter: brightness(1.03);
    transform: translateY(-1px);
    border-color: #BFD3F2;
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
        log_cosmetic_error("Нормалізація значення у Мій кабінет", exc)
    text = str(value).strip()
    if text.lower() in ["none", "nan", "nat"]:
        return ""
    return text


def has_value(value):
    return clean(value).strip() != ""


def display_text(value, fallback="—"):
    text = clean(value)
    return escape(text) if text else fallback


def _html_cell(value):
    """Безпечне HTML-представлення значення комірки."""
    value_text = clean(value).strip()
    return escape(value_text).replace("\n", "<br>") if value_text else "—"


def _render_html_table(headers, rows, empty_message="Записів немає."):
    """Єдиний HTML-рендер через глобальні класи таблиць системи."""
    if not rows:
        st.info(empty_message)
        return
    header_html = "".join(f"<th>{escape(str(header))}</th>" for header in headers)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{_html_cell(value)}</td>" for value in row) + "</tr>"
        for row in rows
    )
    st.markdown(
        '<div class="myreq-table-scroll"><table class="myreq-html-table">'
        f"<thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody>"
        "</table></div>",
        unsafe_allow_html=True,
    )


def _period_label(year, quarter):
    roman = quarter_to_roman(quarter)
    qnum = {"I": "1", "II": "2", "III": "3", "IV": "4"}.get(
        roman,
        clean(quarter),
    )
    qnum = str(qnum).upper().removeprefix("Q")
    return f"{clean(year)} Q{qnum}" if clean(year) else f"Q{qnum}"


def _request_fact(row):
    return clean(row.get("numeric_value")) or clean(row.get("value_text")) or "—"


def _request_is_my_turn(row):
    approval_status = clean(row.get("approval_status"))
    chain = schemes.parse_chain(row.get("approval_chain"))
    stage_index = schemes.parse_stage(row.get("chain_stage"))
    my_email = clean(current_user.get("email")).lower()
    my_role = current_user.get("role")

    if chain:
        stage = schemes.current_stage(chain, stage_index)
        if approval_status not in set(schemes.ALL_WAITING_STATUSES) or stage is None:
            return False
        stage_email = clean(stage.get("email")).lower()
        return (
            bool(stage_email and stage_email == my_email)
            or (not stage_email and stage.get("role") == my_role)
        )

    return approval_status == schemes.STATUS_MANAGER_REVIEW and my_role == ROLE_SSP_HEAD


def _build_strat_lookup(frame):
    if frame is None or frame.empty or "code" not in frame.columns:
        return {}
    lookup = {}
    for _, row in frame.iterrows():
        code_key = clean(row.get("code")).rstrip(".")
        if code_key and code_key not in lookup:
            lookup[code_key] = row
    return lookup


@st.cache_data(show_spinner=False)
def load_initial_submitters(request_ids):
    """Один масовий запит найперших версій для таблиць кабінету."""
    ids = sorted({int(request_id) for request_id in request_ids if request_id is not None})
    if not ids:
        return {}
    try:
        rows = fetch_all(
            "monitoring_request_versions",
            "request_id,version_number,created_at,responsible_person",
            filters=[("in_", "request_id", ids)],
            order=[("request_id", False), ("version_number", False), ("created_at", False)],
        )
    except Exception as exc:
        log_cosmetic_error("Масове завантаження перших версій у Мій кабінет", exc)
        return {}

    versions = pd.DataFrame(rows)
    if versions.empty or "request_id" not in versions.columns:
        return {}
    versions["_request_id"] = pd.to_numeric(versions["request_id"], errors="coerce")
    versions["_version_number"] = pd.to_numeric(
        versions.get("version_number"),
        errors="coerce",
    )
    versions["_created_at"] = pd.to_datetime(
        versions.get("created_at"),
        errors="coerce",
        utc=True,
    )
    versions = versions.dropna(subset=["_request_id"]).sort_values(
        ["_request_id", "_version_number", "_created_at"],
        ascending=[True, True, True],
        na_position="last",
    )
    first_rows = versions.groupby("_request_id", sort=False).head(1)
    return {
        int(row["_request_id"]): clean(row.get("responsible_person"))
        for _, row in first_rows.iterrows()
    }


def _request_table_rows(frame, strat_lookup, initial_submitters):
    rows = []
    if frame is None or frame.empty:
        return rows
    for _, row in frame.iterrows():
        try:
            request_id = int(float(str(row.get("id"))))
        except (TypeError, ValueError):
            request_id = clean(row.get("id"))
        code = clean(row.get("strat_code"))
        strat_row = strat_lookup.get(code.rstrip("."))
        try:
            year_number = int(float(str(row.get("year"))))
        except (TypeError, ValueError):
            year_number = None
        target = (
            clean(strat_row.get(f"target_{year_number}"))
            if strat_row is not None and year_number is not None
            else ""
        )
        first_submitter = initial_submitters.get(request_id, "") if isinstance(request_id, int) else ""
        rows.append([
            request_id,
            code or "—",
            _period_label(row.get("year"), row.get("quarter")),
            target or "—",
            _request_fact(row),
            clean(row.get("approval_status")) or "—",
            clean(row.get("scheme_label")) or "—",
            first_submitter or clean(row.get("responsible_person")) or "—",
            format_kyiv_datetime(row.get("submitted_at")) or "—",
        ])
    return rows


def status_badge_class(status):
    status = clean(status)
    if status == schemes.APPROVED_STATUS:
        return "badge-green"
    if status in schemes.ALL_RETURNED_STATUSES:
        return "badge-yellow"
    if status == schemes.STATUS_MANAGER_REVIEW:
        return "badge-purple"
    if status in schemes.ALL_WAITING_STATUSES:
        return "badge-blue"
    return "badge-gray"


APPROVAL_FILTER_OPTIONS = [
    "Активні до розгляду",
    "Усі",
    *schemes.ALL_WAITING_STATUSES,
    *schemes.ALL_RETURNED_STATUSES,
    schemes.APPROVED_STATUS,
]


# ============================================================
# DATA LOADING
# ============================================================

def load_strat_matrix():
    """ЄДИНЕ джерело — core.strategic_data (правка К1)."""
    return core_load_strat_matrix()


def load_requests():
    """ЄДИНЕ джерело — core.monitoring_data (правки К2, П2)."""
    df = monitoring_data.load_monitoring_requests_live()
    if not df.empty and "submitted_at" in df.columns:
        df = df.sort_values("submitted_at", ascending=False)
    return df


def load_request_live(request_id):
    """Пряме читання однієї заявки без кешу перед показом дій."""
    try:
        rows = fetch_all(
            "monitoring_requests",
            "*",
            filters=[("eq", "id", int(request_id))],
        )
    except Exception as exc:
        log_cosmetic_error("Актуальна перевірка заявки у Мій кабінет", exc)
        return None
    return dict(rows[0]) if rows else None


def _queue_cabinet_selection_reset(request_id):
    """На наступному rerun обрати іншу актуальну заявку або порожній стан."""
    st.session_state["cab_selection_reset_pending"] = True
    st.session_state["cab_processed_request_id"] = int(request_id)


def _render_cabinet_decision_notices():
    """Стабільні зелені повідомлення після rerun — унизу панелі дій."""
    success_text = clean(st.session_state.get("cab_action_success_notice"))
    switch_text = clean(st.session_state.get("cab_last_decision_notice"))
    if success_text:
        st.success(success_text)
    if switch_text:
        st.success(switch_text)
    if success_text or switch_text:
        if st.button(
            "Зрозуміло, приховати це повідомлення",
            key="cab_dismiss_decision_notice",
        ):
            st.session_state.pop("cab_action_success_notice", None)
            st.session_state.pop("cab_last_decision_notice", None)
            st.rerun()


def _render_cabinet_submission_notice():
    """Одноразове стандартне зелене повідомлення внизу робочої зони."""
    notice = st.session_state.pop(NOTICE_KEY, None)
    if not isinstance(notice, dict):
        return
    repeated = bool(notice.get("repeated"))
    codes = [clean(code) for code in notice.get("codes") or [] if clean(code)]
    stage = clean(notice.get("first_stage_label")) or "Координатор"
    if len(codes) > 1:
        heading = "Заявки повторно подано" if repeated else "Заявки подано"
        detail = f"Вони очікують на розгляд: {stage}."
    else:
        heading = "Заявку повторно подано" if repeated else "Заявку подано"
        detail = f"Вона очікує на розгляд: {stage}."
    code_text = f" Код: {', '.join(codes)}." if codes else ""
    st.success(f"{heading}. {detail}{code_text}")


def load_logs(request_id):
    rows = fetch_all(
        "monitoring_logs",
        "*",
        filters=[("eq", "request_id", int(request_id))],
        order=("changed_at", True),
    )
    return pd.DataFrame(rows)


def load_versions(request_id):
    rows = fetch_all(
        "monitoring_request_versions",
        "*",
        filters=[("eq", "request_id", int(request_id))],
        order=("created_at", True),
    )
    return pd.DataFrame(rows)



def _actor_identity(role_label):
    """Повний підпис дії для журналу: роль + ПІБ + email поточного користувача."""
    try:
        name = str((current_user or {}).get("full_name", "")).strip()
        email = str((current_user or {}).get("email", "")).strip()
    except Exception:
        name, email = "", ""
    parts = [p for p in (role_label, name, f"<{email}>" if email else "") if p]
    return " · ".join(parts) if parts else role_label

def write_log(request_id, action, old_status, new_status, comment, changed_by="Керівник ССП"):
    supabase.table("monitoring_logs").insert({
        "request_id": int(request_id),
        "action": action,
        "old_status": old_status,
        "new_status": new_status,
        "admin_comment": comment,
        # Аудит: роль ланки + конкретний користувач
        "changed_by": _actor_identity(changed_by)
    }).execute()



# ============================================================
# MAIN DATA
# ============================================================

df = load_requests()
strat_df = load_strat_matrix()

required_cols = [
    "id", "year", "quarter", "department", "responsible_person", "phone", "email",
    "strat_code", "status", "progress_text", "numeric_value", "value_text", "risks",
    "submitted_at", "approval_status", "admin_comment", "file_names", "file_urls",
    "start_date", "end_date", "updated_at", "npa_link", "scheme_label",
    "approval_chain", "chain_stage"
]
for col in required_cols:
    if col not in df.columns:
        df[col] = ""

df = filter_requests_for_user(
    df,
    current_user,
    ssp_columns=["department"]
)

if df.empty:
    st.warning("Для цього користувача немає доступних відомостей за закріпленим ССП.")
    _render_cabinet_submission_notice()
    render_footer()
    st.stop()

st.markdown('<div class="ua-line"></div>', unsafe_allow_html=True)
st.markdown("""
<div class="ministry-label">
🇺🇦 Міністерство економіки, довкілля та сільського господарства України
</div>
""", unsafe_allow_html=True)

role_label = current_user.get("role_label") or "Керівник ССП"

st.markdown(f"""
<div class="header-box">
    <div class="header-title">Мій кабінет</div>
    <div class="header-subtitle">
        Кабінет погодження вашого самостійного структурного підрозділу. Тут відображаються
        заявки вашого ССП; коли заявка перебуває на вашій ланці схеми погодження — доступні
        дії: погодити та передати далі або повернути на доопрацювання (подавачу чи на
        будь-яку попередню ланку).
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================
# FILTERS
# ============================================================

if "cabinet_filters_applied_v19" not in st.session_state:
    st.session_state["cabinet_filters_applied_v19"] = {
        "department": None,
        "year": "Усі",
        "status": "Усі",
        "search": "",
    }

departments = sorted(df["department"].dropna().astype(str).unique().tolist())
if user_has_all_ssp_access(current_user):
    available_departments = departments
else:
    available_departments = get_available_ssp_options_for_user(
        current_user,
        all_options=departments,
    )
    allowed_indexes = current_user.get("allowed_ssp_indexes", [])
    available_departments = [
        department
        for department in departments
        if any(str(index) in str(department) for index in allowed_indexes)
    ] or available_departments

if not available_departments:
    st.warning("Для цього користувача немає доступних ССП.")
    _render_cabinet_submission_notice()
    render_footer()
    st.stop()

_filter_defaults = {
    "department": available_departments[0],
    "year": "Усі",
    "status": "Усі",
    "search": "",
}
_pending_filter_keys = {
    "department": "cabinet_department_pending",
    "year": "cabinet_year_pending",
    "status": "cabinet_status_pending",
    "search": "cabinet_search_pending",
}
for _filter_name, _widget_key in _pending_filter_keys.items():
    st.session_state.setdefault(
        _widget_key,
        st.session_state["cabinet_filters_applied_v19"].get(
            _filter_name,
            _filter_defaults[_filter_name],
        ) or _filter_defaults[_filter_name],
    )

years = ["Усі"] + sorted(df["year"].dropna().astype(str).unique().tolist())
_valid_filter_options = {
    "department": available_departments,
    "year": years,
    "status": APPROVAL_FILTER_OPTIONS,
}
for _filter_name, _options in _valid_filter_options.items():
    _widget_key = _pending_filter_keys[_filter_name]
    if st.session_state.get(_widget_key) not in _options:
        st.session_state[_widget_key] = _filter_defaults[_filter_name]


def _apply_cabinet_filters_v19():
    st.session_state["cabinet_filters_applied_v19"] = {
        name: st.session_state.get(widget_key, _filter_defaults[name])
        for name, widget_key in _pending_filter_keys.items()
    }


def _reset_cabinet_filters_v19():
    st.session_state["cabinet_filters_applied_v19"] = _filter_defaults.copy()
    for name, widget_key in _pending_filter_keys.items():
        st.session_state[widget_key] = _filter_defaults[name]


with st.form("cabinet_filters_form_v19"):
    st.markdown(
        '<span class="cabinet-filter-form-marker" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="filter-title">Параметри відбору</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown('<div class="filter-field-label">ССП</div>', unsafe_allow_html=True)
        st.selectbox(
            "Самостійний структурний підрозділ",
            available_departments,
            key=_pending_filter_keys["department"],
            disabled=should_lock_ssp_fields(current_user),
            label_visibility="collapsed",
        )
    with c2:
        st.markdown('<div class="filter-field-label">Рік</div>', unsafe_allow_html=True)
        st.selectbox(
            "Рік",
            years,
            key=_pending_filter_keys["year"],
            label_visibility="collapsed",
        )
    with c3:
        st.markdown('<div class="filter-field-label">Статус погодження</div>', unsafe_allow_html=True)
        st.selectbox(
            "Статус погодження",
            APPROVAL_FILTER_OPTIONS,
            key=_pending_filter_keys["status"],
            label_visibility="collapsed",
        )
    with c4:
        st.markdown('<div class="filter-field-label">Пошук за ID або кодом заходу</div>', unsafe_allow_html=True)
        st.text_input(
            "Пошук за ID або кодом заходу",
            key=_pending_filter_keys["search"],
            label_visibility="collapsed",
        )

    ba, bb = st.columns([2, 1])
    with ba:
        st.form_submit_button(
            "Застосувати обрані параметри",
            use_container_width=True,
            on_click=_apply_cabinet_filters_v19,
        )
    with bb:
        st.form_submit_button(
            "Скинути параметри",
            use_container_width=True,
            on_click=_reset_cabinet_filters_v19,
        )

_applied_cab = st.session_state["cabinet_filters_applied_v19"]
selected_department = _applied_cab.get("department") or available_departments[0]
selected_year = _applied_cab.get("year", "Усі")
selected_status = _applied_cab.get("status", "Усі")
search = str(_applied_cab.get("search", "") or "")

filtered = df[df["department"].astype(str) == str(selected_department)].copy()
if selected_year != "Усі":
    filtered = filtered[filtered["year"].astype(str) == str(selected_year)]
if selected_status == "Активні до розгляду":
    filtered = filtered[
        filtered["approval_status"].astype(str).isin(schemes.ALL_WAITING_STATUSES)
    ]
elif selected_status != "Усі":
    filtered = filtered[filtered["approval_status"].astype(str) == selected_status]
if search.strip():
    sq = search.strip().lower()
    filtered = filtered[
        filtered["id"].astype(str).str.lower().str.contains(sq, na=False)
        | filtered["strat_code"].astype(str).str.lower().str.contains(sq, na=False)
    ]

st.caption(f"Знайдено відомостей: {len(filtered)}")

if filtered.empty:
    st.info("За обраними параметрами відбору відомостей не знайдено.")
    _render_cabinet_decision_notices()
    _render_cabinet_submission_notice()
    render_footer()
    st.stop()

# ============================================================
# METRICS
# ============================================================

total = len(filtered)
to_sign = len(filtered[filtered["approval_status"] == schemes.STATUS_MANAGER_REVIEW])
approved = len(filtered[filtered["approval_status"] == schemes.APPROVED_STATUS])
waiting = len(filtered[filtered["approval_status"] == schemes.STATUS_COORDINATOR_REVIEW])
returned = len(filtered[filtered["approval_status"].isin(schemes.ALL_RETURNED_STATUSES)])

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Усього відомостей", total)
m2.metric("🟣 На підтвердженні", to_sign)
m3.metric("🟡 Очікує", waiting)
m4.metric("🔴 Повернуто", returned)
m5.metric("🟢 Погоджено", approved)

# ============================================================
# REQUEST LISTS
# ============================================================

_table_headers = [
    "ID",
    "Код заходу",
    "Звітний період",
    "Цільовий орієнтир",
    "Фактичне значення",
    "Статус погодження",
    "Застосована схема погодження",
    "Особа, яка подала заявку",
    "Дата подання",
]
_strat_lookup = _build_strat_lookup(strat_df)
_request_ids = tuple(
    int(value)
    for value in pd.to_numeric(filtered.get("id"), errors="coerce").dropna().tolist()
)
_initial_submitters = load_initial_submitters(_request_ids)

_cabinet_ssp_number = clean(current_user.get("ssp_index"))
if not _cabinet_ssp_number:
    _ssp_numbers = re.findall(r"\d+", clean(selected_department))
    _cabinet_ssp_number = _ssp_numbers[0] if _ssp_numbers else "—"

with st.expander(
    f"Перелік поданих відомостей від ССП №{_cabinet_ssp_number}",
    expanded=False,
):
    _render_html_table(
        _table_headers,
        _request_table_rows(filtered, _strat_lookup, _initial_submitters),
        empty_message="Доступних відомостей за обраними параметрами немає.",
    )

st.markdown(
    '<div class="myreq-section-header">'
    '<div class="myreq-section-title">Перелік заявок на погодженні</div>'
    '</div>',
    unsafe_allow_html=True,
)
_pending_for_me = filtered[filtered.apply(_request_is_my_turn, axis=1)].copy()
_render_html_table(
    _table_headers,
    _request_table_rows(_pending_for_me, _strat_lookup, _initial_submitters),
    empty_message="Заявок, що зараз очікують вашого рішення, немає.",
)

# ============================================================
# DETAILED VIEW
# ============================================================

st.markdown(
    '<div class="card cabinet-section-card">'
    '<div class="card-title">Детальний перегляд та підтвердження</div>'
    '</div>',
    unsafe_allow_html=True,
)

_my_email = str(current_user.get("email") or "").strip().lower()
_my_role = current_user.get("role")

_CAB_REQUEST_PLACEHOLDER = "— Оберіть заявку —"
_CAB_REQUEST_SELECTOR_KEY = "cabinet_request_selector"

options = [_CAB_REQUEST_PLACEHOLDER]
_option_by_id = {}
for _, row in _pending_for_me.iterrows():
    option_label = (
        f"ID {row['id']} | {row['strat_code']} | "
        f"{row['year']} {row['quarter']} квартал | {row['approval_status']}"
    )
    options.append(option_label)
    try:
        _option_by_id[int(float(str(row["id"])))] = option_label
    except (TypeError, ValueError):
        pass

if st.session_state.pop("cab_selection_reset_pending", False):
    _processed_id = st.session_state.pop("cab_processed_request_id", None)
    _next_pending_ids = []
    for _value in pd.to_numeric(_pending_for_me.get("id"), errors="coerce").dropna().tolist():
        _candidate_id = int(_value)
        if _candidate_id != _processed_id and _candidate_id in _option_by_id:
            _next_pending_ids.append(_candidate_id)
    st.session_state[_CAB_REQUEST_SELECTOR_KEY] = (
        _option_by_id[_next_pending_ids[0]]
        if _next_pending_ids
        else _CAB_REQUEST_PLACEHOLDER
    )
elif st.session_state.get(_CAB_REQUEST_SELECTOR_KEY) not in options:
    _current_pending_ids = [
        int(value)
        for value in pd.to_numeric(_pending_for_me.get("id"), errors="coerce").dropna().tolist()
        if int(value) in _option_by_id
    ]
    st.session_state[_CAB_REQUEST_SELECTOR_KEY] = (
        _option_by_id[_current_pending_ids[0]]
        if _current_pending_ids
        else _CAB_REQUEST_PLACEHOLDER
    )

selected = st.selectbox(
    "Оберіть заявку",
    options,
    key=_CAB_REQUEST_SELECTOR_KEY,
)

if selected == _CAB_REQUEST_PLACEHOLDER:
    st.info(
        "Оберіть заявку, що зараз перебуває на вашій ланці погодження. "
        "Інші відомості ССП доступні лише в оглядовій таблиці вище."
    )
    _render_cabinet_decision_notices()
else:
    raw_id = selected.split("|")[0].replace("ID", "").strip()
    selected_id = int(raw_id)
    selected_row = _pending_for_me[_pending_for_me["id"].astype(int) == selected_id].iloc[0].copy()

    _live_request = load_request_live(selected_id)
    _live_request_verified = _live_request is not None
    if _live_request_verified:
        for _live_key, _live_value in _live_request.items():
            selected_row[_live_key] = _live_value

    approval = clean(selected_row["approval_status"])
    code = clean(selected_row["strat_code"])
    badge_class = status_badge_class(approval)

    st.markdown(f"""
    <div class="badge-wrap">
        <div class="badge {badge_class}">Статус: {display_text(approval)}</div>
        <div class="badge">ID {selected_id}</div>
        <div class="badge">Захід {display_text(code)}</div>
        <div class="badge">Рік: {display_text(selected_row["year"])}</div>
        <div class="badge">Квартал: {display_text(selected_row["quarter"])}</div>
    </div>
    """, unsafe_allow_html=True)

    mi = _strat_lookup.get(code.rstrip("."))
    if mi is not None:
        st.markdown(f"""
        <div class="step-box">
            <b>{display_text(code)} — {display_text(mi.get("name"))}</b><br>
            <span style="color:#132238;font-weight:750;">Індикатор: {display_text(mi.get("indicator"))}</span><br>
            <span style="color:#132238;font-weight:750;">Одиниця виміру: {display_text(mi.get("unit"))}</span><br>
            <span style="color:#132238;font-weight:750;">Терміни: {display_text(mi.get("start_date_plan"))} — {display_text(mi.get("end_date_plan"))}</span>
        </div>
        """, unsafe_allow_html=True)

    try:
        _cab_record_year = int(str(selected_row.get("year") or "").strip())
    except (TypeError, ValueError):
        _cab_record_year = None

    _cab_selected_target = (
        clean(mi.get(f"target_{_cab_record_year}", ""))
        if mi is not None and _cab_record_year is not None
        else ""
    )
    _cab_future_targets = (
        [mi.get(f"target_{year}", "") for year in range(_cab_record_year + 1, 2035)]
        if mi is not None and _cab_record_year is not None
        else []
    )

    st.markdown(f"""
    <div class="info-grid">
        <div class="info-card info-card-blue">
            <div class="info-label">Статус виконання</div>
            <div class="info-value">{display_text("Не настав час" if is_period_locked(selected_row.get("year"), selected_row.get("quarter")) else selected_row["status"])}</div>
        </div>
        <div class="info-card info-card-green">
            <div class="info-label">Фактичне значення</div>
            <div class="info-value">{display_text(_request_fact(selected_row))}</div>
        </div>
        <div class="info-card info-card-yellow">
            <div class="info-label">ССП</div>
            <div class="info-value">{display_text(selected_row["department"])}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Поля лише для читання ────────────────────────────────────────────────────
    p1, p2, p3 = st.columns(3)
    with p1:
        st.text_input(
            "ПІБ подавача заявки",
            value=clean(selected_row["responsible_person"]),
            disabled=True,
            key=f"v_resp_{selected_id}",
        )
    with p2:
        st.text_input(
            "Телефон",
            value=clean(selected_row["phone"]),
            disabled=True,
            key=f"v_phone_{selected_id}",
        )
    with p3:
        st.text_input(
            "Email",
            value=clean(selected_row["email"]),
            disabled=True,
            key=f"v_email_{selected_id}",
        )

    _progress_html = _html_cell(selected_row.get("progress_text"))
    _risks_html = _html_cell(selected_row.get("risks"))
    st.markdown(
        '<div class="cabinet-readonly-block">'
        '<div class="cabinet-readonly-label">Опис прогресу</div>'
        f'<div class="cabinet-readonly-value">{_progress_html}</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="cabinet-readonly-block">'
        '<div class="cabinet-readonly-label">Ризики / проблеми / відхилення</div>'
        f'<div class="cabinet-readonly-value">{_risks_html}</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if has_value(selected_row["admin_comment"]):
        st.markdown(f"""
        <div class="comment-box cabinet-muted-box">
            <div class="comment-title">Коментар координатора</div>
            <div class="comment-text">{display_text(selected_row["admin_comment"])}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Посилання на НПА: рядок відображається завжди ──
    _npa_raw = clean(selected_row.get("npa_link", ""))
    if _npa_raw:
        _links_html = "".join(
            f'<div>🔗 <a href="{escape(url.strip())}" target="_blank">{escape(url.strip())}</a></div>'
            for url in re.split(r"[\n;,]+", _npa_raw)
            if url.strip()
        )
    else:
        _links_html = "—"
    st.markdown(
        '<div class="cabinet-readonly-block">'
        '<div class="cabinet-readonly-label">Посилання на НПА</div>'
        f'<div class="cabinet-readonly-value">{_links_html}</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Маршрут погодження: візуальний ланцюжок + підпис прогресу ──
    _chain = schemes.parse_chain(selected_row.get("approval_chain"))
    _stage_idx = schemes.parse_stage(selected_row.get("chain_stage"))
    if _chain:
        _scheme_lbl = clean(selected_row.get("scheme_label"))
        _route_nodes = [
            '<div class="cabinet-route-node">'
            '<span class="cabinet-route-role">Подавач</span>'
            f'{escape(clean(selected_row.get("responsible_person")) or clean(selected_row.get("email")) or "—")}'
            '</div>'
        ]
        for _route_index, _route_stage in enumerate(_chain):
            _route_label = clean(_route_stage.get("label")) or schemes.STAGE_LABELS.get(
                clean(_route_stage.get("role")),
                "Ланка",
            )
            _route_person = (
                clean(_route_stage.get("name"))
                or clean(_route_stage.get("email"))
                or "—"
            )
            _current_class = " current" if _route_index == _stage_idx and approval in schemes.ALL_WAITING_STATUSES else ""
            _route_nodes.append(
                f'<div class="cabinet-route-node{_current_class}">'
                f'<span class="cabinet-route-role">{escape(_route_label)}</span>'
                f'{escape(_route_person)}</div>'
            )
        _route_html = '<span class="cabinet-route-arrow">→</span>'.join(_route_nodes)
        _progress_text = schemes.chain_progress_text(_chain, _stage_idx, approval)
        st.markdown(
            '<div class="comment-box cabinet-muted-box">'
            f'<div class="comment-title">Схема погодження{(" · " + escape(_scheme_lbl)) if _scheme_lbl else ""}</div>'
            f'<div class="cabinet-route-row">{_route_html}</div>'
            f'<div class="cabinet-route-caption">{escape(_progress_text)}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    # ============================================================
    # ACTION PANEL — панель дій поточної ланки схеми погодження
    # ============================================================

    _waiting_statuses = set(schemes.ALL_WAITING_STATUSES)

    if _chain:
        _stage = schemes.current_stage(_chain, _stage_idx)
        _stage_label = clean(_stage.get("label")) if _stage else ""
    else:
        _stage = None
        _stage_label = "Керівник ССП"
    is_my_turn = bool(
        _live_request_verified
        and _request_is_my_turn(selected_row)
    )

    if is_my_turn:
        st.markdown(
            f'<div class="sign-panel">'
            f'<div class="sign-panel-title">Дії ланки «{escape(_stage_label)}»</div>'
            '<div class="sign-panel-sub">Оберіть рішення після перевірки даних заявки.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="cabinet-decision-card">'
            '<div class="cabinet-decision-guidance">'
            '<p>Якщо зауважень немає, погодьте заявку: вона перейде наступній ланці схеми або отримає статус «Погоджено», якщо маршрут завершено.</p>'
            '<p>Якщо дані потребують виправлення, поверніть заявку подавачу або на попередню ланку та обов’язково зазначте причину.</p>'
            '<p>Після застосування рішення попередня заявка буде прибрана з активного перегляду, а кабінет переключиться на наступну актуальну заявку.</p>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        _next_after_me = schemes.current_stage(_chain, _stage_idx + 1) if _chain else None
        _approve_option = "Погодити та передати далі" if _next_after_me else "Погодити"

        st.markdown('<div class="cabinet-control-label">Оберіть рішення</div>', unsafe_allow_html=True)
        decision = st.radio(
            "Оберіть рішення",
            [_approve_option, "Повернути на доопрацювання"],
            horizontal=True,
            key=f"cab_decision_radio_{selected_id}",
            label_visibility="collapsed",
        )

        # Адресати повернення: подавач + усі попередні ланки.
        if _chain:
            _targets = schemes.return_targets(_chain, _stage_idx)
        else:
            _targets = [
                {"key": "submitter", "label": "Подавачу (відповідальній особі ССП)",
                 "status": schemes.STATUS_RETURNED_BY_MANAGER, "new_stage": 0},
                {"key": "legacy_admin", "label": "Координатору",
                 "status": schemes.STATUS_COORDINATOR_REVIEW, "new_stage": 0},
            ]
        _target_labels = [target["label"] for target in _targets]
        _picked_target = None
        if decision == "Повернути на доопрацювання":
            st.markdown('<div class="cabinet-control-label">Кому повернути</div>', unsafe_allow_html=True)
            _picked_target_label = st.selectbox(
                "Кому повернути",
                _target_labels,
                key=f"return_target_{selected_id}",
                label_visibility="collapsed",
            )
            _picked_target = _targets[_target_labels.index(_picked_target_label)]

        # Формування верхньої частини динамічного маршруту реалізується
        # окремо у Частині 2. У цій частині нові ланки тут не додаються.
        _my_next_role_options = []

        _my_chosen_next_role = None
        _my_chosen_next_person = None
        _my_req_dept_idx = ""
        if _my_next_role_options:
            _my_req_dept_nums = re.findall(r"\d+", clean(selected_row.get("department", "")))
            _my_req_dept_idx = _my_req_dept_nums[0] if _my_req_dept_nums else ""
            _my_next_choice_labels = [
                f"Завершити на «{_stage_label}» (без додаткової ланки)"
            ] + [
                f"Передати ланці «{schemes.STAGE_LABELS[role]}»"
                for role in _my_next_role_options
            ]
            st.markdown('<div class="cabinet-control-label">Наступна ланка</div>', unsafe_allow_html=True)
            _my_next_choice = st.selectbox(
                "Наступна ланка",
                _my_next_choice_labels,
                key=f"cab_next_stage_choice_{selected_id}",
                label_visibility="collapsed",
            )
            if _my_next_choice != _my_next_choice_labels[0]:
                _my_chosen_next_role = _my_next_role_options[
                    _my_next_choice_labels.index(_my_next_choice) - 1
                ]
                _my_next_candidates = schemes.stage_candidates(
                    _my_chosen_next_role,
                    _my_req_dept_idx,
                )
                if len(_my_next_candidates) > 1:
                    _my_cand_labels = [
                        schemes.candidate_label(candidate)
                        for candidate in _my_next_candidates
                    ]
                    _my_picked_cand_label = st.selectbox(
                        f"Хто саме — {schemes.STAGE_LABELS[_my_chosen_next_role]}",
                        _my_cand_labels,
                        key=f"cab_next_stage_person_{selected_id}",
                    )
                    _my_chosen_next_person = _my_next_candidates[
                        _my_cand_labels.index(_my_picked_cand_label)
                    ]
                elif _my_next_candidates:
                    _my_chosen_next_person = _my_next_candidates[0]
                    st.caption(f"→ {schemes.candidate_label(_my_chosen_next_person)}")
                else:
                    st.error(
                        f"Немає користувача ролі «{schemes.STAGE_LABELS[_my_chosen_next_role]}» "
                        f"для цього ССП. Оберіть завершення погодження або зверніться до супер-адміна."
                    )

        if decision == _approve_option:
            if _next_after_me is not None:
                _next_who = clean(_next_after_me.get("name")) or clean(_next_after_me.get("email"))
                _decision_hint = (
                    f"Заявку буде передано ланці «{clean(_next_after_me.get('label'))}»"
                    + (f" — {_next_who}" if _next_who else "")
                )
            elif _my_chosen_next_role:
                _decision_hint = f"Заявку буде передано ланці «{schemes.STAGE_LABELS[_my_chosen_next_role]}»"
            else:
                _decision_hint = "Заявка завершить поточну схему погодження й отримає статус «Погоджено»."
        else:
            _decision_hint = (
                f"Заявку буде повернуто: {_picked_target['label']}."
                if _picked_target is not None
                else "Оберіть адресата повернення."
            )
        if decision == _approve_option and not _my_next_role_options:
            st.markdown(
                '<div class="cabinet-control-label">Наступна ланка</div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            f'<div class="cabinet-decision-box">{escape(_decision_hint)}</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="cabinet-comment-header">Коментар до рішення</div>', unsafe_allow_html=True)
        leader_comment = st.text_area(
            "Коментар до рішення",
            height=110,
            placeholder=(
                "Вкажіть причину повернення або зауваження..."
                if decision == "Повернути на доопрацювання"
                else "За потреби додайте коментар до погодження..."
            ),
            key=f"leader_comment_{selected_id}",
            label_visibility="collapsed",
        )

        apply_decision_btn = st.button(
            "Застосувати рішення",
            use_container_width=True,
            key=f"cab_apply_decision_{selected_id}",
        )

        if apply_decision_btn and decision == _approve_option:
            _sign_blocked = False
            if _chain and _next_after_me:
                new_status, new_stage = schemes.status_after_approve(_chain, _stage_idx)
                _final_chain_for_notify = _chain
            elif _chain and _my_chosen_next_role:
                if not _my_chosen_next_person:
                    st.error("Оберіть конкретну особу для наступної ланки.")
                    _sign_blocked = True
                    new_status, new_stage, _final_chain_for_notify = approval, _stage_idx, _chain
                else:
                    _new_chain, new_status, new_stage = schemes.advance_with_new_stage(
                        _chain,
                        _stage_idx,
                        _my_chosen_next_role,
                        _my_req_dept_idx,
                        _my_chosen_next_person,
                    )
                    if _new_chain is None:
                        st.error("Не вдалося призначити наступну ланку.")
                        _sign_blocked = True
                        new_status, new_stage, _final_chain_for_notify = approval, _stage_idx, _chain
                    else:
                        _chain = _new_chain
                        _final_chain_for_notify = _new_chain
            elif _chain:
                new_status, new_stage = schemes.finalize_here(_stage_idx)
                _final_chain_for_notify = _chain
            else:
                new_status, new_stage = "Погоджено", _stage_idx + 1
                _final_chain_for_notify = _chain

            if not _sign_blocked:
                _approval_comment = clean(leader_comment) or f"Погоджено ланкою «{_stage_label}»"
                try:
                    approve_request_step(
                        request_id=int(selected_id),
                        expected_status=approval,
                        expected_chain_stage=int(_stage_idx),
                        new_status=new_status,
                        new_chain_stage=int(new_stage),
                        approval_chain=(schemes.chain_to_json(_chain) if _chain else None),
                        comment=_approval_comment,
                        action=f"Погодження ланкою «{_stage_label}»",
                        user=current_user,
                        created_by=f"{role_label} / погодження",
                    )

                    try:
                        if new_status == "Погоджено":
                            notify_events.notify_approved(
                                clean(selected_row.get("email")),
                                clean(selected_row.get("responsible_person")),
                                code,
                                clean(selected_row.get("year")),
                                clean(selected_row.get("quarter")),
                            )
                        elif _final_chain_for_notify:
                            _next = schemes.current_stage(_final_chain_for_notify, new_stage)
                            if _next:
                                notify_events.notify_stage_assigned(
                                    _next.get("email", ""),
                                    _next.get("name", ""),
                                    _next.get("label", ""),
                                    code,
                                    clean(selected_row.get("year")),
                                    clean(selected_row.get("quarter")),
                                    submitter=clean(selected_row.get("responsible_person")),
                                )
                    except Exception as notify_exc:
                        show_warning(
                            "Рішення збережено, але миттєве email-сповіщення не відправлено.",
                            notify_exc,
                            "Email після погодження у Мій кабінет",
                        )

                    if new_status == "Погоджено":
                        _success_notice = "Заявка пройшла всі етапи схеми. Статус: «Погоджено»."
                    else:
                        _next = (
                            schemes.current_stage(_final_chain_for_notify, new_stage)
                            if _final_chain_for_notify
                            else None
                        )
                        if _next:
                            _who = _next.get("name") or _next.get("email") or _next.get("label")
                            _success_notice = (
                                f"Підтверджено. Заявка надійшла наступній ланці — "
                                f"«{_next.get('label', '')}» ({_who})."
                            )
                        else:
                            _success_notice = f"Підтверджено. Новий статус: «{new_status}»."
                    st.session_state["cab_action_success_notice"] = _success_notice
                    st.session_state["cab_last_decision_notice"] = (
                        "Рішення застосовано. Якщо в черзі є ще заявки — систему переключено "
                        "на наступну заявку. Перевірте її дані з початку перед новим рішенням."
                    )
                    _queue_cabinet_selection_reset(selected_id)
                    monitoring_data.invalidate_monitoring_cache()
                    st.rerun()
                except TransitionRejected as exc:
                    st.error(exc.message)
                except Exception as exc:
                    show_incident(exc, context="Атомарне погодження заявки у Мій кабінет")

        if apply_decision_btn and decision == "Повернути на доопрацювання":
            if not clean(leader_comment):
                st.error("Вкажіть коментар перед поверненням на доопрацювання.")
            elif _picked_target is None:
                st.error("Оберіть адресата повернення.")
            else:
                try:
                    atomic_return_request(
                        request_id=int(selected_id),
                        expected_status=approval,
                        expected_chain_stage=int(_stage_idx),
                        new_status=_picked_target["status"],
                        new_chain_stage=int(_picked_target["new_stage"]),
                        comment=clean(leader_comment),
                        action=f"Повернення на доопрацювання: {_picked_target['label']}",
                        user=current_user,
                        created_by=f"{role_label} / повернення",
                    )
                    try:
                        if _picked_target["key"] == "submitter":
                            notify_events.notify_returned(
                                clean(selected_row.get("email")),
                                clean(selected_row.get("responsible_person")),
                                code,
                                clean(selected_row.get("year")),
                                clean(selected_row.get("quarter")),
                                by_label=_stage_label,
                                comment=clean(leader_comment),
                            )
                        elif _picked_target["key"].startswith("stage:") and _chain:
                            _target_stage = _chain[_picked_target["new_stage"]]
                            notify_events.notify_returned(
                                _target_stage.get("email", ""),
                                _target_stage.get("name", ""),
                                code,
                                clean(selected_row.get("year")),
                                clean(selected_row.get("quarter")),
                                by_label=_stage_label,
                                comment=clean(leader_comment),
                            )
                    except Exception as notify_exc:
                        show_warning(
                            "Заявку повернуто, але миттєве email-сповіщення не відправлено.",
                            notify_exc,
                            "Email після повернення у Мій кабінет",
                        )
                    st.session_state["cab_action_success_notice"] = (
                        f"Заявку повернуто: {_picked_target['label']}."
                    )
                    st.session_state["cab_last_decision_notice"] = (
                        "Рішення застосовано. Якщо в черзі є ще заявки — систему переключено "
                        "на наступну заявку. Перевірте її дані з початку перед новим рішенням."
                    )
                    _queue_cabinet_selection_reset(selected_id)
                    monitoring_data.invalidate_monitoring_cache()
                    st.rerun()
                except TransitionRejected as exc:
                    st.error(exc.message)
                except Exception as exc:
                    show_incident(exc, context="Атомарне повернення заявки у Мій кабінет")

        _render_cabinet_decision_notices()

        # Ланка може виправити дані напряму. Механізм чернеток і відновлення
        # незбереженого стану видалено; зберігається лише явна дія користувача.
        if not schemes.is_final_locked(selected_row):
            with st.expander(f"Редагувати дані заявки (від імені ланки «{_stage_label}»)"):
                st.caption(
                    "Використовуйте, якщо простіше виправити дані самостійно, ніж "
                    "повертати заявку відповідальній особі. Попередню версію буде "
                    "збережено в історії; заявка повернеться на розгляд координатору."
                )
                _cab_coord_idx = coordinator_stage_index(_chain) if _chain else 0
                _cab_status_key = f"cab_edit_status_{selected_id}_{_stage_idx}"
                _cab_value_key = f"cab_edit_value_{selected_id}_{_stage_idx}"
                _cab_progress_key = f"cab_edit_progress_{selected_id}_{_stage_idx}"
                _cab_risks_key = f"cab_edit_risks_{selected_id}_{_stage_idx}"

                _cab_status_options = list(SUBMISSION_STATUS_OPTIONS)
                _cab_current_status = clean(selected_row.get("status"))
                _cab_status_index = (
                    _cab_status_options.index(_cab_current_status)
                    if _cab_current_status in _cab_status_options
                    else 0
                )
                cab_new_status = st.selectbox(
                    "Статус виконання",
                    _cab_status_options,
                    index=_cab_status_index,
                    key=_cab_status_key,
                )
                cab_new_value = st.text_input(
                    "Фактичне значення",
                    value=clean(selected_row.get("numeric_value")) or clean(selected_row.get("value_text")),
                    key=_cab_value_key,
                )
                cab_new_progress = st.text_area(
                    "Опис прогресу",
                    value=clean(selected_row.get("progress_text")),
                    height=110,
                    key=_cab_progress_key,
                )
                cab_new_risks = st.text_area(
                    "Ризики / проблеми / відхилення",
                    value=clean(selected_row.get("risks")),
                    height=110,
                    key=_cab_risks_key,
                )
                cab_edit_submit = st.button(
                    "Зберегти й надіслати координатору",
                    use_container_width=True,
                    key=f"cab_edit_submit_{selected_id}",
                )

                if cab_edit_submit:
                    cab_edit_errors = []
                    if not has_value(cab_new_value):
                        cab_edit_errors.append("Заповніть фактичне значення.")

                    cab_unit = clean(mi.get("unit")) if mi is not None else ""
                    cab_decrease_error = cumulative_quarter_decrease_error(
                        df,
                        code=code,
                        year=selected_row.get("year"),
                        quarter=selected_row.get("quarter"),
                        value=cab_new_value,
                        progress_text=cab_new_progress,
                        unit=cab_unit,
                        department=selected_row.get("department"),
                        object_kind=selected_row.get("object_kind") or "measure",
                    )
                    if not has_value(cab_new_progress):
                        cab_edit_errors.append(
                            cab_decrease_error or "Заповніть опис прогресу."
                        )

                    _cab_chain_for_edit = _chain
                    _cab_target_stage = _cab_coord_idx
                    if has_value(cab_new_value):
                        cab_value_ok, cab_value_error = validate_fact_value_for_target(
                            cab_new_value,
                            cab_unit,
                            _cab_selected_target,
                            _cab_future_targets,
                        )
                        if not cab_value_ok:
                            cab_edit_errors.append(cab_value_error)

                    cab_conflict_error = status_value_conflict(
                        cab_new_status,
                        cab_new_value,
                        _cab_selected_target,
                        cab_unit,
                        code,
                        _cab_future_targets,
                    )
                    if cab_conflict_error:
                        cab_edit_errors.append(cab_conflict_error)

                    if cab_edit_errors:
                        for cab_error in cab_edit_errors:
                            st.error(cab_error)
                    else:
                        _cab_update = prepare_monitoring_payload({
                            "status": cab_new_status,
                            "numeric_value": cab_new_value,
                            "progress_text": cab_new_progress,
                            "risks": cab_new_risks,
                            "admin_comment": "",
                            "submitted_at": datetime.now(timezone.utc).isoformat(),
                            "log_comment": (
                                f"Відредаговано ланкою «{_stage_label}»; "
                                "надіслано на наявну ланку координатора повторно."
                            ),
                        })
                        try:
                            result = resubmit_request(
                                request_id=int(selected_id),
                                expected_updated_at=clean(selected_row.get("updated_at")),
                                expected_status=approval,
                                expected_chain_stage=int(_stage_idx),
                                target_chain_stage=int(_cab_target_stage),
                                payload=_cab_update,
                                mode="stage_edit",
                                action=f"Редагування ланкою «{_stage_label}»",
                                user=current_user,
                                created_by_before=f"{role_label} / до редагування",
                                created_by_after=f"{role_label} / редагування",
                            )

                            if _cab_chain_for_edit:
                                _cab_coord_stage = _cab_chain_for_edit[_cab_target_stage]
                                try:
                                    notify_events.notify_stage_assigned(
                                        _cab_coord_stage.get("email", ""),
                                        _cab_coord_stage.get("name", ""),
                                        _cab_coord_stage.get("label", ""),
                                        code,
                                        clean(selected_row.get("year")),
                                        clean(selected_row.get("quarter")),
                                        submitter=clean(selected_row.get("responsible_person")),
                                        kind=clean(selected_row.get("object_kind")) or "measure",
                                    )
                                except Exception as notify_exc:
                                    show_warning(
                                        "Зміни збережено, але координатору не відправлено миттєвий лист.",
                                        notify_exc,
                                        "Email після редагування ланкою погодження",
                                    )

                            set_submission_notice(
                                first_stage_label=(
                                    result.data.get("first_stage_label")
                                    or (_cab_chain_for_edit[_cab_target_stage].get("label") if _cab_chain_for_edit else "Координатор")
                                ),
                                codes=[code],
                                repeated=True,
                            )
                            _queue_cabinet_selection_reset(selected_id)
                            monitoring_data.invalidate_monitoring_cache()
                            st.rerun()
                        except TransitionRejected as exc:
                            st.error(exc.message)
                        except Exception as exc:
                            show_incident(
                                exc,
                                context="Атомарне редагування заявки ланкою погодження",
                            )
    else:
        if not _live_request_verified:
            st.info(
                "Не вдалося підтвердити актуальний стан заявки в базі. "
                "Кнопки рішення вимкнено; оновіть сторінку й повторіть перевірку."
            )
        elif approval == schemes.APPROVED_STATUS:
            st.info("Заявку вже опрацьовано й погоджено. Додаткові дії не потрібні.")
        elif approval in _waiting_statuses:
            if _chain:
                st.info(
                    "Заявка вже не перебуває на вашій ланці. "
                    f"{schemes.chain_progress_text(_chain, _stage_idx, approval)}"
                )
            else:
                st.info("Заявка вже не перебуває на вашому етапі погодження.")
        elif approval in schemes.ALL_RETURNED_STATUSES:
            st.info("Заявку вже повернуто на доопрацювання. Дії цієї ланки не потрібні.")
        else:
            st.info("Заявку вже опрацьовано; для поточного стану дій цієї ланки немає.")
        _render_cabinet_decision_notices()

    # ============================================================
    # LOG HISTORY
    # ============================================================

    logs_df = load_logs(selected_id)
    st.markdown(
        '<div class="card cabinet-section-card">'
        '<div class="card-title">Історія зміни статусу</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    # ЄДИНИЙ компонент таймлайну для всієї системи (core/ui.py, ТЗ 16.13)
    render_request_timeline(logs_df, with_table_expander=False)

    _history_logs = logs_df.copy()
    _versions_df = load_versions(selected_id)
    _log_timestamps = pd.to_datetime(
        _history_logs["changed_at"]
        if "changed_at" in _history_logs.columns
        else pd.Series([], dtype="object"),
        errors="coerce",
        utc=True,
    )
    _history_facts = []
    _history_progress = []
    if not _versions_df.empty and "created_at" in _versions_df.columns:
        _versions_df = _versions_df.copy()
        _versions_df["_ts"] = pd.to_datetime(
            _versions_df["created_at"],
            errors="coerce",
            utc=True,
        )
        _versions_df = _versions_df.sort_values("_ts")
        for _timestamp in _log_timestamps:
            _snapshot = (
                _versions_df[_versions_df["_ts"] <= _timestamp]
                if pd.notna(_timestamp)
                else _versions_df.iloc[0:0]
            )
            _version_row = _snapshot.iloc[-1] if not _snapshot.empty else None
            if _version_row is not None:
                _history_facts.append(_request_fact(_version_row))
                _history_progress.append(clean(_version_row.get("progress_text")) or "—")
            else:
                _history_facts.append(_request_fact(selected_row))
                _history_progress.append(clean(selected_row.get("progress_text")) or "—")
    else:
        _history_facts = [_request_fact(selected_row)] * len(_history_logs)
        _history_progress = [clean(selected_row.get("progress_text")) or "—"] * len(_history_logs)

    if not _history_logs.empty:
        _history_logs["Фактичне значення"] = _history_facts
        _history_logs["Опис прогресу"] = _history_progress

    _history_table = prepare_human_log_table(
        _history_logs,
        extra_columns=["Фактичне значення", "Опис прогресу"],
    )
    with st.expander("Повна історія змін заявки (табличний вигляд)"):
        _render_html_table(
            list(_history_table.columns),
            [list(row) for row in _history_table.itertuples(index=False, name=None)],
            empty_message="Історії змін для цієї заявки поки що немає.",
        )

_render_cabinet_submission_notice()

# ============================================================
# РУЧНІ ЗАКРИТТЯ ЗАХОДІВ — реакція керівника ССП
# ============================================================
# Після підтвердження супер-адміном закриття направляється керівнику
# ССП «до відома»: він може не заперечити або заперечити з коментарем.
# Заперечення НЕ блокує закриття автоматично — його розглядає
# супер-адмін і, за потреби, скасовує закриття.

if _my_role == ROLE_SSP_HEAD:
    try:
        _co_df = normalise_closeout_frame(pd.DataFrame(fetch_all(
            "closeout_requests",
            "*",
            filters=[("eq", "approval_status", "Підтверджено")],
            order=("id", False),
        )))
    except Exception:
        _co_df = pd.DataFrame()

    if not _co_df.empty:
        for _col in ("head_status", "head_comment", "strat_code",
                     "period_year", "period_quarter", "reason", "npa_links", "scope"):
            if _col not in _co_df.columns:
                _co_df[_col] = ""

        _my_ssp = str(current_user.get("ssp_index") or "")
        _my_allowed = [str(a) for a in (current_user.get("allowed_ssp_indexes") or [])]

        def _closeout_is_mine(co_row):
            # Закриття прив'язуємо до ССП через головного виконавця заходу
            _code = clean(co_row.get("strat_code"))
            try:
                _m = df_matrix[df_matrix["code"].astype(str).str.strip() == _code]
            except Exception:
                return "*" in _my_allowed
            if _m.empty:
                return "*" in _my_allowed
            _dept = str(_m.iloc[0].get("department", ""))
            _idx = re.findall(r"\d+", _dept)
            _idx = _idx[0] if _idx else ""
            return "*" in _my_allowed or (_idx and (_idx == _my_ssp or _idx in _my_allowed))

        try:
            df_matrix = load_strat_matrix()
        except Exception:
            df_matrix = pd.DataFrame(columns=["code", "department"])

        _pending_ack = _co_df[
            _co_df.apply(_closeout_is_mine, axis=1)
            & (~_co_df["head_status"].astype(str).isin(["Не заперечує", "Заперечує", "Оскаржено"]))
        ]

        if not _pending_ack.empty:
            st.markdown(
                '<div class="card"><div class="card-title">🔒 Ручні закриття заходів вашого ССП — потрібна ваша реакція</div>',
                unsafe_allow_html=True,
            )
            st.caption(
                "Ці заходи закрито адміністратором на підставі внутрішньої інформації та "
                "підтверджено супер-адміном. Ознайомтесь: якщо ви не згодні — "
                "заперечте з коментарем, і рішення перегляне супер-адміністратор."
            )
            for _, _co in _pending_ack.iterrows():
                _co_id = int(_co.get("id"))
                _links_html = " ".join(
                    f'<a href="{escape(u.strip())}" target="_blank">🔗 посилання</a>'
                    for u in re.split(r"[\n;,]+", clean(_co.get("npa_links"))) if u.strip()
                )
                st.markdown(
                    f"""<div class="comment-box">
                        <div class="comment-title">Захід {escape(clean(_co.get("strat_code")))} ·
                            {escape(clean(_co.get("period_quarter")))} · {escape(clean(_co.get("period_year")))}
                            ({escape(clean(_co.get("scope")) or "Квартал")})</div>
                        <div class="comment-text">Підстава: {escape(clean(_co.get("reason")))} {_links_html}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
                _ack_comment = st.text_input(
                    "Коментар (обов'язковий при запереченні)",
                    key=f"co_ack_comment_{_co_id}",
                )
                _a1, _a2 = st.columns(2)
                with _a1:
                    _ok_btn = st.button("✅ Не заперечую", key=f"co_ok_{_co_id}", use_container_width=True)
                with _a2:
                    _obj_btn = st.button("⛔ Оскаржити", key=f"co_obj_{_co_id}", use_container_width=True)

                if _ok_btn or _obj_btn:
                    if _obj_btn and not clean(_ack_comment):
                        st.error("Вкажіть коментар до заперечення.")
                    else:
                        _new_head_status = "Оскаржено" if _obj_btn else "Не заперечує"
                        try:
                            supabase.table("closeout_requests").update({
                                "head_status": _new_head_status,
                                "head_comment": clean(_ack_comment),
                                "head_email": _my_email,
                            }).eq("id", _co_id).execute()
                            write_log(
                                _co_id,
                                f"Реакція керівника ССП на ручне закриття: {_new_head_status}",
                                "Підтверджено", "Підтверджено",
                                clean(_ack_comment), changed_by=role_label,
                            )
                            st.success(f"Вашу реакцію зафіксовано: {_new_head_status}.")
                            monitoring_data.invalidate_monitoring_cache()
                            st.rerun()
                        except Exception as exc:
                            show_incident(
                                exc,
                                context="Збереження реакції керівника ССП на ручне закриття",
                            )
            st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# FOOTER
# ============================================================

render_footer()
