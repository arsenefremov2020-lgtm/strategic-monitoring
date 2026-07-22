# ============================================================
# ЦЕНТР ЗАДАЧ — ТЕСТОВИЙ РЕЖИМ (ТЗ 16.2)
# ============================================================
#
# Погоджено як окремий ТЕСТОВИЙ режим: одна сторінка, яка для КОЖНОЇ ролі
# показує рівно те, що потребує дії саме зараз, з переходом одразу на
# потрібну вкладку. Нічого не змінює в даних — тільки читає.
#
# Логіка за ролями:
#   • Відповідальний від ССП  → повернуті заявки; заходи без поданих
#     відомостей за обраний період (крім «не настав час» і закритих вручну).
#   • Керівник управління / Заступник / Керівник ССП → заявки, що очікують
#     саме їхнього рішення; власні повернуті подання; для керівника ССП —
#     ручні закриття, що очікують його реакції.
#   • Адміністратор (координатор) → заявки на ланці координатора по своїх
#     ССП; заявки, що очікують понад 5 робочих днів; конфлікти закриттів.
#   • Супер-адмін → ручні закриття на підтвердженні; спори; заявки, де його
#     додано в ланцюг і зараз його ланка.

import re
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from core.page_setup import page_setup, render_footer
from core.ui import load_css, render_own_ssp_badge
from core.db import get_supabase_client
from core import monitoring_data
from core import approval_schemes as schemes
from core import periods as core_periods
from core.access import (
    filter_requests_for_user,
    get_user_allowed_ssp_indexes,
    user_has_all_ssp_access,
)
from core.strategic_data import load_strat_matrix
from core.closeouts import load_manual_closeouts
from config.roles import (
    ROLE_SSP, ROLE_SSP_HEAD, ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY,
    ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_GUEST,
)

current_user = page_setup("Центр задач", page_name="Центр задач")
load_css()

supabase = get_supabase_client()


def clean(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def extract_ssp_index(value) -> str:
    m = re.search(r"№?\s*(\d+)", clean(value))
    return m.group(1) if m else ""


# ------------------------------------------------------------
# Заголовок
# ------------------------------------------------------------

st.markdown(
    """
<div class="card">
    <div class="card-title">🧪 Центр задач <span style="font-size:12px;
        background:#fef3c7;border:1px solid #fcd34d;color:#92400e;
        border-radius:8px;padding:2px 8px;vertical-align:middle;">тестовий
        режим</span></div>
    <div class="card-subtitle">Персональний список того, що потребує вашої дії
    саме зараз, — без пошуку по вкладках. Сторінка нічого не змінює в даних:
    усі дії виконуються на своїх звичних вкладках, сюди виводяться лише
    посилання на них.</div>
</div>
""",
    unsafe_allow_html=True,
)

role = clean(current_user.get("role")) or ROLE_GUEST
my_email = clean(current_user.get("email")).lower()

if role == ROLE_GUEST:
    st.info("Центр задач доступний лише авторизованим користувачам.")
    render_footer()
    st.stop()

render_own_ssp_badge(current_user)

# ------------------------------------------------------------
# Дані
# ------------------------------------------------------------

requests_df = monitoring_data.load_monitoring_requests_live()
strat_df = load_strat_matrix()
manual_closeouts = load_manual_closeouts()

_now = datetime.now(timezone.utc)
_current_year = _now.year
_current_quarter_num = (_now.month - 1) // 3 + 1
_current_quarter_roman = {1: "I", 2: "II", 3: "III", 4: "IV"}[_current_quarter_num]
_current_period_num = _current_year * 10 + _current_quarter_num

st.caption(
    f"Поточний звітний період: {_current_quarter_roman} квартал "
    f"{_current_year} року · станом на {_now.strftime('%d.%m.%Y %H:%M')} (UTC)"
)


def _days_since(value) -> int | None:
    ts = pd.to_datetime(clean(value), errors="coerce", utc=True)
    if ts is None or pd.isna(ts):
        return None
    return max(0, (_now - ts.to_pydatetime()).days)


def _task_section(icon: str, title: str, rows: list[str], page: str,
                  page_label: str, empty_text: str) -> None:
    """Єдиний вигляд секції задач: заголовок, список, кнопка переходу."""
    st.markdown(
        f'<div class="card"><div class="card-title">{icon} {title} '
        f'<span style="font-size:12px;background:#e2e8f0;border-radius:8px;'
        f'padding:2px 8px;color:#334155;vertical-align:middle;">{len(rows)}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if not rows:
        st.markdown(
            f'<div style="background:#f0fdf4;border:1px solid #86efac;'
            f'border-radius:10px;padding:8px 12px;font-size:13px;'
            f'font-weight:700;color:#166534;">✅ {empty_text}</div>',
            unsafe_allow_html=True,
        )
    else:
        items = "".join(
            f'<li style="margin-bottom:4px;">{r}</li>' for r in rows[:15]
        )
        more = (
            f'<div style="font-size:12px;color:#64748b;margin-top:4px;">'
            f'…і ще {len(rows) - 15} позицій — повний перелік на вкладці '
            f'«{page_label}».</div>'
            if len(rows) > 15 else ""
        )
        st.markdown(
            f'<ul style="font-size:13px;color:#0f172a;line-height:1.5;'
            f'padding-left:18px;margin:4px 0;">{items}</ul>{more}',
            unsafe_allow_html=True,
        )
        st.page_link(page, label=f"Перейти: {page_label}", icon="➡️")
    st.markdown("</div>", unsafe_allow_html=True)


# Мої власні подання (для будь-якої ролі, що подає)
my_requests = requests_df[
    requests_df.get("email", pd.Series(dtype=str)).astype(str)
    .str.strip().str.lower() == my_email
] if not requests_df.empty else pd.DataFrame()

total_tasks = 0

# ------------------------------------------------------------
# 1) ПОВЕРНУТІ НА ДООПРАЦЮВАННЯ (усі ролі, що подають)
# ------------------------------------------------------------

if role in (ROLE_SSP, ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY, ROLE_SSP_HEAD):
    returned_rows = []
    if not my_requests.empty:
        _ret = my_requests[
            my_requests["approval_status"].astype(str).str.strip()
            == "Повернуто на доопрацювання"
        ]
        for _, r in _ret.iterrows():
            d = _days_since(r.get("submitted_at"))
            returned_rows.append(
                f"Заявка № {clean(r.get('id'))} — захід "
                f"<b>{clean(r.get('strat_code'))}</b> "
                f"({clean(r.get('quarter'))} кв. {clean(r.get('year'))})"
                + (f" · повернута, у роботі {d} дн." if d is not None else "")
                + (f"<br><span style='color:#9a3412;'>💬 "
                   f"{clean(r.get('admin_comment'))[:160]}</span>"
                   if clean(r.get("admin_comment")) else "")
            )
    total_tasks += len(returned_rows)
    _task_section(
        "✍️", "Повернуті на доопрацювання", returned_rows,
        "pages/3_Мої_заявки.py", "Мої заявки",
        "Повернутих заявок немає.",
    )

# ------------------------------------------------------------
# 2) НЕ ПОДАНІ ЗАХОДИ ЗА ПОТОЧНИЙ ПЕРІОД (ролі ССП)
# ------------------------------------------------------------

if role in (ROLE_SSP, ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY, ROLE_SSP_HEAD):
    my_ssp_indexes = {
        str(i) for i in (get_user_allowed_ssp_indexes(current_user) or [])
    }
    measures = strat_df[strat_df["object_type"].astype(str) == "measure"].copy()
    measures["_ssp"] = measures["resp_main"].map(extract_ssp_index)
    measures = measures[measures["_ssp"].isin(my_ssp_indexes)]

    submitted_codes = set()
    if not requests_df.empty:
        _cur = requests_df[
            (requests_df["year"].astype(str) == str(_current_year))
            & (requests_df["quarter"].astype(str).map(core_periods.quarter_to_number)
               == _current_quarter_num)
        ]
        submitted_codes = {
            clean(c) for c in _cur.get("strat_code", pd.Series(dtype=str))
        }

    not_submitted = []
    for _, m in measures.iterrows():
        code = clean(m.get("code"))
        if not code or code in submitted_codes:
            continue
        if core_periods.is_measure_not_started(
            core_periods.parse_period(m.get("measure_start_date", "")),
            _current_period_num,
        ):
            continue  # «не настав час» — задачею не є
        if (code, str(_current_year), _current_quarter_roman) in manual_closeouts:
            continue  # закрито вручну
        not_submitted.append(
            f"<b>{code}</b> — {clean(m.get('name'))[:110]}"
        )
    total_tasks += len(not_submitted)
    _task_section(
        "📝",
        f"Не подані відомості за {_current_quarter_roman} квартал {_current_year}",
        not_submitted,
        "pages/1_Моніторинг_виконання.py", "Моніторинг виконання",
        "За всіма активними заходами вашого ССП відомості за поточний період "
        "уже подано.",
    )

# ------------------------------------------------------------
# 3) ЗАЯВКИ, ЩО ОЧІКУЮТЬ САМЕ ВАШОГО РІШЕННЯ (ланки погодження)
# ------------------------------------------------------------

if role in (ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY, ROLE_SSP_HEAD):
    waiting_rows = []
    scoped = filter_requests_for_user(
        requests_df, current_user, ssp_columns=["department"]
    )
    if scoped is not None and not scoped.empty:
        waiting_set = set(schemes.ALL_WAITING_STATUSES)
        for _, r in scoped.iterrows():
            approval = clean(r.get("approval_status"))
            if approval not in waiting_set:
                continue
            chain = schemes.parse_chain(r.get("approval_chain"))
            stage_idx = schemes.parse_stage(r.get("chain_stage"))
            stage = schemes.current_stage(chain, stage_idx) if chain else None
            mine = False
            if stage is not None:
                s_email = clean(stage.get("email")).lower()
                mine = (s_email and s_email == my_email) or (
                    not s_email and clean(stage.get("role")) == role
                )
            elif approval == "Очікує: Керівник ССП" and role == ROLE_SSP_HEAD:
                mine = True
            if mine:
                d = _days_since(r.get("submitted_at"))
                waiting_rows.append(
                    f"Заявка № {clean(r.get('id'))} — захід "
                    f"<b>{clean(r.get('strat_code'))}</b> "
                    f"({clean(r.get('quarter'))} кв. {clean(r.get('year'))})"
                    + (f" · очікує {d} дн." if d is not None else "")
                )
    total_tasks += len(waiting_rows)
    _task_section(
        "🖊️", "Очікують вашого рішення", waiting_rows,
        "pages/1_Мій_кабінет.py", "Мій кабінет",
        "Заявок на вашій ланці немає.",
    )

# ------------------------------------------------------------
# 4) РУЧНІ ЗАКРИТТЯ, ЩО ОЧІКУЮТЬ РЕАКЦІЇ КЕРІВНИКА ССП
# ------------------------------------------------------------

if role == ROLE_SSP_HEAD:
    head_rows = []
    try:
        _co = (
            supabase.table("closeout_requests")
            .select("id, strat_code, year, quarter, head_status")
            .execute()
        )
        _co_df = pd.DataFrame(_co.data or [])
        if not _co_df.empty:
            my_ssp_indexes = {
                str(i) for i in (get_user_allowed_ssp_indexes(current_user) or [])
            }
            _meas = strat_df[strat_df["object_type"].astype(str) == "measure"]
            _code_to_ssp = {
                clean(m.get("code")): extract_ssp_index(m.get("resp_main"))
                for _, m in _meas.iterrows()
            }
            for _, c in _co_df.iterrows():
                # Реакції очікують закриття, за якими керівник ССП ще НЕ
                # зафіксував рішення (ті самі значення, що в «Моєму кабінеті»).
                if clean(c.get("head_status")) in ("Не заперечує", "Заперечує", "Оскаржено"):
                    continue
                if _code_to_ssp.get(clean(c.get("strat_code")), "") not in my_ssp_indexes:
                    continue
                head_rows.append(
                    f"Ручне закриття № {clean(c.get('id'))} — захід "
                    f"<b>{clean(c.get('strat_code'))}</b> "
                    f"({clean(c.get('quarter'))} кв. {clean(c.get('year'))}) — "
                    f"підтвердити або оскаржити"
                )
    except Exception:
        pass
    total_tasks += len(head_rows)
    _task_section(
        "🔏", "Ручні закриття — очікують вашої реакції", head_rows,
        "pages/1_Мій_кабінет.py", "Мій кабінет",
        "Ручних закриттів, що очікують вашої реакції, немає.",
    )

# ------------------------------------------------------------
# 5) АДМІНІСТРАТОР (КООРДИНАТОР)
# ------------------------------------------------------------

if role == ROLE_ADMIN:
    scoped = filter_requests_for_user(
        requests_df, current_user, ssp_columns=["department"]
    )
    admin_waiting, admin_stale = [], []
    if scoped is not None and not scoped.empty:
        for _, r in scoped.iterrows():
            approval = clean(r.get("approval_status"))
            if approval == "Очікує погодження":
                d = _days_since(r.get("submitted_at"))
                line = (
                    f"Заявка № {clean(r.get('id'))} — захід "
                    f"<b>{clean(r.get('strat_code'))}</b> "
                    f"(ССП №{clean(r.get('department'))}, "
                    f"{clean(r.get('quarter'))} кв. {clean(r.get('year'))})"
                    + (f" · очікує {d} дн." if d is not None else "")
                )
                admin_waiting.append(line)
                if d is not None and d > 5:
                    admin_stale.append(line)
    total_tasks += len(admin_waiting)
    _task_section(
        "🖊️", "На ланці координатора", admin_waiting,
        "pages/3_Адміністрування.py", "Адміністрування",
        "Заявок, що очікують координатора, немає.",
    )
    _task_section(
        "⏰", "Очікують понад 5 днів", admin_stale,
        "pages/3_Адміністрування.py", "Адміністрування",
        "Прострочених очікувань немає.",
    )

# ------------------------------------------------------------
# 6) СУПЕР-АДМІН
# ------------------------------------------------------------

if role == ROLE_SUPER_ADMIN:
    sa_close, sa_disputes = [], []
    try:
        _co = (
            supabase.table("closeout_requests")
            .select("id, strat_code, year, quarter, approval_status, "
                    "dispute_status, admin_email")
            .execute()
        )
        _co_df = pd.DataFrame(_co.data or [])
        for _, c in _co_df.iterrows():
            if clean(c.get("approval_status")) == "Очікує підтвердження":
                sa_close.append(
                    f"Закриття № {clean(c.get('id'))} — захід "
                    f"<b>{clean(c.get('strat_code'))}</b> "
                    f"({clean(c.get('quarter'))} кв. {clean(c.get('year'))}) "
                    f"від {clean(c.get('admin_email'))}"
                )
            if clean(c.get("dispute_status")) == "На розгляді":
                sa_disputes.append(
                    f"Спір по закриттю № {clean(c.get('id'))} — захід "
                    f"<b>{clean(c.get('strat_code'))}</b> — остаточне рішення "
                    f"за супер-адміном"
                )
    except Exception:
        pass

    sa_waiting = []
    if not requests_df.empty:
        for _, r in requests_df.iterrows():
            approval = clean(r.get("approval_status"))
            if approval not in set(schemes.ALL_WAITING_STATUSES):
                continue
            chain = schemes.parse_chain(r.get("approval_chain"))
            stage_idx = schemes.parse_stage(r.get("chain_stage"))
            stage = schemes.current_stage(chain, stage_idx) if chain else None
            if stage is None:
                continue
            s_email = clean(stage.get("email")).lower()
            if (s_email and s_email == my_email) or (
                not s_email and clean(stage.get("role")) == ROLE_SUPER_ADMIN
            ):
                sa_waiting.append(
                    f"Заявка № {clean(r.get('id'))} — захід "
                    f"<b>{clean(r.get('strat_code'))}</b> — направлена "
                    f"на розгляд супер-адміну"
                )
    total_tasks += len(sa_close) + len(sa_disputes) + len(sa_waiting)
    _task_section(
        "🔏", "Ручні закриття на підтвердженні", sa_close,
        "pages/3_Адміністрування.py", "Адміністрування",
        "Закриттів на підтвердженні немає.",
    )
    _task_section(
        "⚖️", "Спори щодо ручних закриттів", sa_disputes,
        "pages/3_Адміністрування.py", "Адміністрування",
        "Активних спорів немає.",
    )
    _task_section(
        "🖊️", "Заявки, направлені супер-адміну", sa_waiting,
        "pages/3_Адміністрування.py", "Адміністрування",
        "Заявок на вашій ланці немає.",
    )

# ------------------------------------------------------------
# Підсумок
# ------------------------------------------------------------

if total_tasks == 0:
    st.markdown(
        '<div class="card" style="text-align:center;">'
        '<div style="font-size:28px;">🎉</div>'
        '<div style="font-size:15px;font-weight:800;color:#166534;">'
        'Усі задачі опрацьовано — дій від вас зараз не потрібно.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

st.caption(
    "🧪 Тестовий режим: перелік задач формується автоматично з поточних даних "
    "системи і не є офіційним дорученням. Зауваження та пропозиції щодо цього "
    "режиму передавайте власнику системи."
)

render_footer()
