# ============================================================
# ПАСПОРТ ССП — ТЕСТОВИЙ РЕЖИМ (ТЗ 16.10)
# ============================================================
#
# Погоджено як окремий ТЕСТОВИЙ режим: повний «паспорт» одного самостійного
# структурного підрозділу на одному екрані — команда, всі заходи, стан подань
# по кварталах, ручні закриття, зависання, — плюс охайний Excel-експорт.
#
# Сторінка нічого не змінює в даних — тільки читає, використовуючи ті самі
# спільні модулі, що й решта системи (статуси, періоди, доступи, експорти).

import re
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from core.page_setup import page_setup, render_footer
from core.ui import load_css, render_own_ssp_badge, apply_reset_buttons, render_scope_toggle, render_readonly_table
from core.db import get_supabase_client
from core import monitoring_data
from core import approval_schemes as schemes
from core import periods as core_periods
from core.statuses import legend_badge
from core.access import (
    get_user_allowed_ssp_indexes,
    user_has_all_ssp_access,
)
from core.strategic_data import load_strat_matrix
from core.closeouts import load_manual_closeouts
from core.deputies import get_deputy_for_ssp
from core.exports import write_styled_excel
from config.users import get_users_by_ssp_index
from config.roles import (
    ROLE_SSP, ROLE_SSP_HEAD, ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY,
    ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_GUEST, ROLE_LABELS,
)

current_user = page_setup("Паспорт ССП", page_name="Паспорт ССП")
load_css()

supabase = get_supabase_client()

QUARTERS = ["I", "II", "III", "IV"]


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
    <div class="card-title">🧪 Паспорт ССП <span style="font-size:12px;
        background:#fef3c7;border:1px solid #fcd34d;color:#92400e;
        border-radius:8px;padding:2px 8px;vertical-align:middle;">тестовий
        режим</span></div>
    <div class="card-subtitle">Повна картка одного самостійного структурного
    підрозділу: команда та ланки погодження, всі заходи з їхнім станом,
    подання по кварталах, ручні закриття та зависання. Дані відповідають
    офіційним (погодженим) відомостям системи.</div>
</div>
""",
    unsafe_allow_html=True,
)

role = clean(current_user.get("role")) or ROLE_GUEST
if role == ROLE_GUEST:
    st.info("Паспорт ССП доступний лише авторизованим користувачам.")
    render_footer()
    st.stop()

render_own_ssp_badge(current_user)

# ------------------------------------------------------------
# Дані
# ------------------------------------------------------------

strat_df = load_strat_matrix()
requests_df = monitoring_data.load_monitoring_requests()
manual_closeouts = load_manual_closeouts()

measures_all = strat_df[strat_df["object_type"].astype(str) == "measure"].copy()
measures_all["_ssp"] = measures_all["resp_main"].map(extract_ssp_index)

_all_ssp_indexes = sorted(
    {i for i in measures_all["_ssp"] if i}, key=lambda v: int(v)
)
_ssp_labels = {}
for _, m in measures_all.iterrows():
    idx = m["_ssp"]
    if idx and idx not in _ssp_labels:
        _ssp_labels[idx] = clean(m.get("resp_main"))

# Доступні ССП: свої — за замовчуванням; повний перелік — для ролей із
# повним доступом або після стандартної кнопки «Переглянути загальну
# інформацію» (той самий механізм, що на інших вкладках).
_scope_all = render_scope_toggle("Паспорт ССП", current_user)
if user_has_all_ssp_access(current_user) or _scope_all:
    available_ssp = list(_all_ssp_indexes)
else:
    _allowed = {
        str(i) for i in (get_user_allowed_ssp_indexes(current_user) or [])
    }
    available_ssp = [i for i in _all_ssp_indexes if i in _allowed]
if not available_ssp:
    st.warning("За вашим профілем не знайдено жодного доступного ССП.")
    render_footer()
    st.stop()

# ------------------------------------------------------------
# Параметри (єдиний стандарт: «Застосувати» / «Скинути»)
# ------------------------------------------------------------

_now = datetime.now(timezone.utc)
_years = ["2026", "2027", "2028"]

with st.container():
    c1, c2 = st.columns([2, 1])
    with c1:
        sel_ssp = st.selectbox(
            "Самостійний структурний підрозділ",
            available_ssp,
            key="passport_ssp_select",
            format_func=lambda v: _ssp_labels.get(str(v), f"ССП №{v}"),
        )
    with c2:
        sel_year = st.selectbox(
            "Рік", _years,
            index=_years.index(str(_now.year)) if str(_now.year) in _years else 0,
            key="passport_year_select",
        )
    applied, reset = apply_reset_buttons(
        "passport_apply", "passport_reset"
    )

if reset:
    for k in ("passport_ssp_select", "passport_year_select",
              "passport_params_applied"):
        st.session_state.pop(k, None)
    pass  # no explicit rerun: the triggering user action completes in this run

if applied:
    st.session_state["passport_params_applied"] = {
        "ssp": str(sel_ssp), "year": str(sel_year),
    }

_params = st.session_state.get("passport_params_applied")
if not _params:
    st.info(
        "Оберіть ССП і рік та натисніть «Застосувати обрані параметри», "
        "щоб сформувати паспорт."
    )
    render_footer()
    st.stop()

ssp_index = _params["ssp"]
year = _params["year"]
ssp_label = _ssp_labels.get(ssp_index, f"ССП №{ssp_index}")

# ------------------------------------------------------------
# 1) КОМАНДА ТА ЛАНКИ ПОГОДЖЕННЯ
# ------------------------------------------------------------

st.markdown(
    f'<div class="card"><div class="card-title">👥 {ssp_label}</div>'
    f'<div class="card-subtitle">Команда підрозділу та ланки схеми '
    f'погодження</div>',
    unsafe_allow_html=True,
)

_deputy_minister = clean(get_deputy_for_ssp(ssp_index))
_coordinators = schemes.stage_candidates(ROLE_ADMIN, ssp_index)
_team_rows = []
if _deputy_minister:
    _team_rows.append(("Заступник Міністра (координація)", _deputy_minister, ""))
for c in _coordinators:
    _team_rows.append(("Координатор (адміністратор)",
                       clean(c.get("name")), clean(c.get("email"))))
_ssp_users = get_users_by_ssp_index(ssp_index) or {}
_role_order = [ROLE_SSP_HEAD, ROLE_SSP_DEPUTY, ROLE_UNIT_HEAD, ROLE_SSP]
for r in _role_order:
    for u in _ssp_users.values():
        if clean(u.get("role")) != r:
            continue
        _team_rows.append((
            ROLE_LABELS.get(r, r),
            clean(u.get("full_name")) or clean(u.get("email")),
            clean(u.get("email")),
        ))

if _team_rows:
    team_df = pd.DataFrame(_team_rows, columns=["Роль", "ПІБ", "Email"])
    render_readonly_table(team_df, height=260, compact=True)
else:
    st.info("Для цього ССП поки що не знайдено користувачів у таблиці доступів.")
st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------
# 2) ЗВЕДЕННЯ ПО ЗАХОДАХ
# ------------------------------------------------------------

measures = measures_all[measures_all["_ssp"] == ssp_index].copy()

ssp_requests = pd.DataFrame()
if not requests_df.empty:
    ssp_requests = requests_df[
        (requests_df["department"].astype(str).str.strip() == ssp_index)
        & (requests_df["year"].astype(str).str.strip() == year)
    ].copy()
    if not ssp_requests.empty:
        ssp_requests["_qnum"] = ssp_requests["quarter"].map(
            core_periods.quarter_to_number
        )

_now_period = _now.year * 10 + ((_now.month - 1) // 3 + 1)


def _measure_state_cells(code: str, start_raw, end_raw) -> list[str]:
    """HTML-комірки I–IV кварталу для одного заходу за єдиною легендою."""
    cells = []
    for qn, q_roman in enumerate(QUARTERS, start=1):
        # Ручне закриття — фіолетовий, як у легенді (🔒)
        if (code, year, q_roman) in manual_closeouts:
            cells.append(legend_badge("Закрито адміністратором"))
            continue
        row = None
        if not ssp_requests.empty:
            hit = ssp_requests[
                (ssp_requests["strat_code"].astype(str).str.strip() == code)
                & (ssp_requests["_qnum"] == qn)
            ]
            if not hit.empty:
                _sort_cols = [c for c in ("updated_at", "submitted_at", "id") if c in hit.columns]
                if _sort_cols:
                    hit = hit.sort_values(_sort_cols, ascending=False, na_position="last")
                row = hit.iloc[0]
        if row is not None:
            approval = clean(row.get("approval_status"))
            if approval == "Погоджено":
                cells.append(legend_badge("Погоджено"))
            elif schemes.is_returned(approval):
                cells.append(legend_badge("На доопрацюванні"))
            else:
                cells.append(legend_badge("На розгляді"))
            continue
        # Немає подання: «не настав час» чи просто не подано?
        period_num = int(year) * 10 + qn
        if core_periods.is_measure_not_started(
            core_periods.parse_period(start_raw), period_num
        ):
            cells.append(legend_badge("Не настав час"))
        else:
            cells.append(legend_badge("Не враховано"))
    return cells


_summary = {
    "заходів усього": len(measures),
    "подано (рік)": 0, "погоджено": 0,
    "повернуто": 0, "закрито вручну": 0,
}
if not ssp_requests.empty:
    _summary["подано (рік)"] = int(ssp_requests["strat_code"].nunique())
    _summary["погоджено"] = int(
        ssp_requests.loc[
            ssp_requests["approval_status"].astype(str).str.strip() == schemes.APPROVED_STATUS,
            "strat_code",
        ].astype(str).str.strip().nunique()
    )
    _summary["повернуто"] = int(
        ssp_requests.loc[
            ssp_requests["approval_status"].map(schemes.is_returned),
            "strat_code",
        ].astype(str).str.strip().nunique()
    )
_summary["закрито вручну"] = sum(
    1 for (c, y, q) in manual_closeouts if y == year and
    c in set(measures["code"].astype(str).str.strip())
)

st.markdown(
    '<div class="card"><div class="card-title">📊 Зведення за '
    f'{year} рік</div>',
    unsafe_allow_html=True,
)
_kpi_cells = "".join(
    f'<div class="admin-kpi-card" style="min-width:140px;">'
    f'<div class="admin-kpi-label">{k}</div>'
    f'<div class="admin-kpi-value">{v}</div></div>'
    for k, v in _summary.items()
)
st.markdown(
    f'<div style="display:flex;flex-wrap:wrap;gap:10px;">{_kpi_cells}</div>'
    '</div>',
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# 3) ВСІ ЗАХОДИ ССП ЗІ СТАНОМ ПО КВАРТАЛАХ (єдина легенда кольорів)
# ------------------------------------------------------------

st.markdown(
    '<div class="card"><div class="card-title">📋 Заходи та стан подань '
    'по кварталах</div>'
    '<div class="card-subtitle">Кольори відповідають єдиній легенді системи: '
    'зелений — погоджено, синій — на розгляді, жовтий — на доопрацюванні, '
    'сірий — не настав час, червоний — не подано, фіолетовий — закрито '
    'вручну.</div>',
    unsafe_allow_html=True,
)

export_rows = []
if measures.empty:
    st.info("За стратегічною матрицею у цього ССП немає заходів.")
else:
    _display_rows = []
    for _, m in measures.iterrows():
        code = clean(m.get("code"))
        name = clean(m.get("name"))
        cells = _measure_state_cells(
            code, m.get("measure_start_date"), m.get("measure_end_date")
        )
        quarter_values = {
            f"{q} квартал": re.sub(r"<[^>]+>", "", c)
            for q, c in zip(QUARTERS, cells)
        }
        _display_rows.append({"Код": code, "Захід": name, **quarter_values})
        export_rows.append({"Код": code, "Захід": name, **quarter_values})
    render_readonly_table(
        pd.DataFrame(_display_rows),
        height=480,
        min_width=1250,
        empty_message="Заходів немає.",
    )
st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------
# 4) ЗАВИСАННЯ ТА РУЧНІ ЗАКРИТТЯ
# ------------------------------------------------------------

col_a, col_b = st.columns(2)

with col_a:
    st.markdown(
        '<div class="card"><div class="card-title">⏰ Очікують понад '
        '5 днів</div>',
        unsafe_allow_html=True,
    )
    stale_rows = []
    if not ssp_requests.empty:
        waiting = ssp_requests[
            ssp_requests["approval_status"].astype(str).isin(
                list(schemes.ALL_WAITING_STATUSES)
            )
        ]
        for _, r in waiting.iterrows():
            ts = pd.to_datetime(clean(r.get("submitted_at")),
                                errors="coerce", utc=True)
            if ts is None or pd.isna(ts):
                continue
            d = (_now - ts.to_pydatetime()).days
            if d > 5:
                stale_rows.append(
                    f"Заявка № {clean(r.get('id'))} — захід "
                    f"<b>{clean(r.get('strat_code'))}</b> · {d} дн. · "
                    f"{clean(r.get('approval_status'))}"
                )
    if stale_rows:
        st.markdown(
            '<ul style="font-size:13px;padding-left:18px;">'
            + "".join(f"<li>{r}</li>" for r in stale_rows)
            + "</ul>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="background:#f0fdf4;border:1px solid #86efac;'
            'border-radius:10px;padding:8px 12px;font-size:13px;'
            'font-weight:700;color:#166534;">✅ Зависань немає.</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with col_b:
    st.markdown(
        '<div class="card"><div class="card-title">🔒 Ручні закриття '
        f'({year} рік)</div>',
        unsafe_allow_html=True,
    )
    _codes = set(measures["code"].astype(str).str.strip())
    closed_rows = [
        f"Захід <b>{c}</b> — {q} квартал {y} року"
        for (c, y, q) in sorted(manual_closeouts)
        if y == year and c in _codes
    ]
    if closed_rows:
        st.markdown(
            '<ul style="font-size:13px;padding-left:18px;">'
            + "".join(f"<li>{r}</li>" for r in closed_rows)
            + "</ul>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="background:#f8fafc;border:1px solid #cbd5e1;'
            'border-radius:10px;padding:8px 12px;font-size:13px;'
            'color:#334155;">Ручних закриттів за цей рік немає.</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------
# 5) ЗАХОДИ, ДЕ ВАШ ССП — СПІВВИКОНАВЕЦЬ (ТЗ-правка 09.07.2026, п.1)
# ------------------------------------------------------------

_co_toggle = st.toggle(
    "Переглянути стан заходів, де Ваш ССП є співвиконавцем",
    key="passport_co_exec_toggle",
)
if _co_toggle:
    st.markdown(
        '<div class="card"><div class="card-title">🤝 Заходи, де '
        f'{ssp_label} — співвиконавець</div>'
        '<div class="card-subtitle">Відомості за цими заходами подає '
        'головний виконавець. Нижче — стан кожного заходу та контакти '
        'відповідальної особи головного виконавця.</div>',
        unsafe_allow_html=True,
    )
    _co_measures = measures_all[
        measures_all.apply(
            lambda r: ssp_index in (
                extract_ssp_index(r.get("resp_co_1")),
                extract_ssp_index(r.get("resp_co_2")),
            ),
            axis=1,
        )
    ].copy() if not measures_all.empty else pd.DataFrame()

    if _co_measures.empty:
        st.info("Заходів, де ваш ССП визначено співвиконавцем, не знайдено.")
    else:
        _co_display_rows = []
        for _, m in _co_measures.iterrows():
            code = clean(m.get("code"))
            name = clean(m.get("name"))
            _main_idx = extract_ssp_index(m.get("resp_main"))
            _main_label = _ssp_labels.get(_main_idx, f"ССП №{_main_idx}")
            _contacts = []
            for u in (get_users_by_ssp_index(_main_idx) or {}).values():
                if clean(u.get("role")) == ROLE_SSP:
                    _nm = clean(u.get("full_name")) or clean(u.get("email"))
                    _em = clean(u.get("email"))
                    _contacts.append(f"{_nm}" + (f" · {_em}" if _em else ""))
            _contact_txt = "\n".join(_contacts) if _contacts else "—"
            cells = _measure_state_cells(
                code, m.get("measure_start_date"), m.get("measure_end_date")
            )
            _co_display_rows.append({
                "Код": code,
                "Захід": name,
                "Головний виконавець": _main_label,
                "Відповідальна особа (контакти)": _contact_txt,
                **{f"{q} квартал": re.sub(r"<[^>]+>", "", c) for q, c in zip(QUARTERS, cells)},
            })
        render_readonly_table(
            pd.DataFrame(_co_display_rows),
            height=420,
            min_width=1550,
            empty_message="Заходів немає.",
        )
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------
# 6) ЕКСПОРТ (єдиний стандарт охайного Excel)
# ------------------------------------------------------------

if export_rows:
    _sheets = {"Заходи ССП": pd.DataFrame(export_rows)}
    if _team_rows:
        _sheets["Команда"] = pd.DataFrame(
            _team_rows, columns=["Роль", "ПІБ", "Email"]
        )
    _sheets["Зведення"] = pd.DataFrame(
        [{"Показник": k, "Значення": v} for k, v in _summary.items()]
    )
    try:
        _xlsx = write_styled_excel(_sheets, freeze_first_col=1)
        st.download_button(
            "⬇️ Завантажити паспорт ССП (Excel)",
            data=_xlsx,
            file_name=f"Паспорт_ССП_{ssp_index}_{year}.xlsx",
            mime="application/vnd.openxmlformats-officedocument."
                 "spreadsheetml.sheet",
            use_container_width=True,
            key="passport_export_xlsx",
        )
    except Exception as e:
        st.error("Не вдалося сформувати Excel-файл паспорта.")
        st.exception(e)

st.caption(
    "🧪 Тестовий режим: сторінка формується автоматично зі стратегічної "
    "матриці, таблиці доступів і заявок моніторингу. Зауваження та "
    "пропозиції щодо цього режиму передавайте власнику системи."
)

render_footer()
