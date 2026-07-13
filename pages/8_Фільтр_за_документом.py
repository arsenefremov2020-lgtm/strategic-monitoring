# ============================================================
# ФІЛЬТР ЗА ДОКУМЕНТОМ (НПА) — DEMO 1.9, перероблено 09.07.2026 (п.7)
# ============================================================
#
# Єдиний стиль системи: фільтри у стандартній «коробці» з кнопками
# «Застосувати/Скинути», стандартні інформаційні блочки, результат —
# охайна таблиця зі закріпленою шапкою і скролінгом (як на Головній).
#
# Довідник документів — config/npa_documents.py (наданий власником список
# за замовчуванням, без зірочок і зайвих лапок). У випадному списку
# показуються ЛИШЕ документи довідника, які реально присутні у матриці;
# нові з'являються автоматично після оновлення матриці.

import re
from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

from core.page_setup import page_setup, render_footer
from core.strategic_data import load_strat_matrix, strip_leading_code
from core import monitoring_data
from core import periods as core_periods
from core.access import filter_actions_for_user
from core.ui import render_scope_toggle, render_auto_refresh_notice, load_css
from core.statuses import legend_badge
from core.closeouts import load_manual_closeouts
from core import exports as core_exports
from core.errors import log_cosmetic_error
from config.npa_documents import (
    CANONICAL_NPA_DOCUMENTS, PPDU_2026_LABEL, normalize_for_match,
)

PAGE_KEY = "Фільтр за документом"

current_user = page_setup(PAGE_KEY, page_name=PAGE_KEY)
load_css()
render_auto_refresh_notice(PAGE_KEY, minutes=5, show_note=False)

st.markdown(
    '<div class="card">'
    '<div class="card-title">Фільтр заходів за НПА / стратегічним документом</div>'
    '<div class="card-subtitle">Сторінка показує заходи, де обраний документ '
    'прямо зазначено у колонках «Глобальний рівень» або «Національний '
    'рівень». Дані моніторингу підтягуються як останні відомості за обраними '
    'параметрами. Дані автоматично оновлюються кожні 5 хвилин; фільтри '
    'спрацьовують тільки після кнопки «Застосувати обрані параметри».</div>'
    '</div>',
    unsafe_allow_html=True,
)


def raw(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception as exc:
        log_cosmetic_error("Нормалізація значення у фільтрі за документом", exc)
    return str(value).strip()


def split_docs(value) -> list[str]:
    text = raw(value)
    if not text:
        return []
    return [p for p in (normalize_for_match(x) for x in re.split(r"[;\n]+", text)) if p]


def doc_in_cell(cell_value, wanted_norm: str) -> bool:
    if not wanted_norm:
        return False
    for d in split_docs(cell_value):
        if d == wanted_norm:
            return True
        if len(d) > 25 and len(wanted_norm) > 25 and (wanted_norm in d or d in wanted_norm):
            return True
    return False


# ------------------------------------------------------------
# Дані
# ------------------------------------------------------------

raw_df = load_strat_matrix()
measures_all = raw_df[raw_df["object_type"] == "measure"].copy()
measures_scoped = filter_actions_for_user(measures_all, current_user, page_key=PAGE_KEY)
manual_closeouts = load_manual_closeouts()

# Документи довідника, які РЕАЛЬНО присутні у матриці
_matrix_docs: set[str] = set()
for col in ("source_global", "source_national"):
    if col in measures_all.columns:
        for cell in measures_all[col].dropna().astype(str):
            _matrix_docs.update(split_docs(cell))

doc_options = []
for d in CANONICAL_NPA_DOCUMENTS:
    n = normalize_for_match(d)
    if n in _matrix_docs or any(
        len(c) > 25 and len(n) > 25 and (n in c or c in n) for c in _matrix_docs
    ):
        doc_options.append(d)
doc_options = sorted(set(doc_options), key=lambda x: x.lower())

# ------------------------------------------------------------
# Фільтри (єдиний стандарт)
# ------------------------------------------------------------

_defaults = {"doc": "", "year": "Усі", "quarters": [],
             "active_only": True, "official_only": True}
if "npa_filter_applied" not in st.session_state:
    st.session_state.npa_filter_applied = dict(_defaults)

st.markdown('<div class="card"><div class="card-title">Параметри відбору</div>', unsafe_allow_html=True)

with st.form("npa_filter_form"):
    r1c1, r1c2, r1c3 = st.columns([3.2, 1.0, 1.4])
    with r1c1:
        chosen_doc = st.selectbox(
            "Документ",
            [""] + doc_options,
            index=0,
            key="npa_doc_pending",
            format_func=lambda x: "Оберіть документ" if not x else x,
        )
    with r1c2:
        year = st.selectbox(
            "Рік",
            ["Усі", "2026", "2027", "2028", "2029", "2030",
             "2031", "2032", "2033", "2034"],
            key="npa_year_pending",
        )
    with r1c3:
        quarters = st.multiselect("Квартал", ["I", "II", "III", "IV"],
                                  key="npa_quarters_pending")

    r2c1, r2c2, _sp = st.columns([1.3, 1.3, 3.0])
    with r2c1:
        official_only = st.toggle("Лише офіційні дані", value=True,
                                  key="npa_official_pending")
    with r2c2:
        active_only = st.toggle("Лише активні заходи", value=True,
                                key="npa_active_pending")

    r3c1, r3c2 = st.columns([1.2, 3.0])
    with r3c1:
        ppdu_clicked = st.form_submit_button(
            "🎯 ППДУ-2026", use_container_width=True,
            help=PPDU_2026_LABEL,
        )
    with r3c2:
        apply_clicked = st.form_submit_button(
            "Застосувати обрані параметри", type="primary",
            use_container_width=True,
        )

rr1, rr2 = st.columns([1.2, 3.0])
with rr1:
    reset_clicked = st.button("Скинути параметри", use_container_width=True,
                              key="npa_reset_filters")
with rr2:
    render_scope_toggle(PAGE_KEY, current_user)

st.markdown('</div>', unsafe_allow_html=True)

if ppdu_clicked or apply_clicked:
    st.session_state.npa_filter_applied = {
        "doc": PPDU_2026_LABEL if ppdu_clicked else chosen_doc,
        "year": st.session_state.get("npa_year_pending", "Усі"),
        "quarters": list(st.session_state.get("npa_quarters_pending", []) or []),
        "active_only": st.session_state.get("npa_active_pending", True),
        "official_only": st.session_state.get("npa_official_pending", True),
    }
    st.rerun()

if reset_clicked:
    st.session_state.npa_filter_applied = dict(_defaults)
    for key in ["npa_doc_pending", "npa_year_pending", "npa_quarters_pending",
                "npa_active_pending", "npa_official_pending"]:
        st.session_state.pop(key, None)
    st.rerun()

params = st.session_state.npa_filter_applied
selected_doc = params.get("doc", "")
if not selected_doc:
    st.info("Оберіть документ і натисніть «Застосувати обрані параметри» "
            "або кнопку «🎯 ППДУ-2026».")
    render_footer()
    st.stop()

# ------------------------------------------------------------
# Відбір заходів
# ------------------------------------------------------------

_wanted = normalize_for_match(selected_doc)
matched = measures_scoped[
    measures_scoped.apply(
        lambda r: doc_in_cell(r.get("source_global", ""), _wanted)
        or doc_in_cell(r.get("source_national", ""), _wanted),
        axis=1,
    )
].copy()

sel_year = params.get("year", "Усі")
sel_quarters = list(params.get("quarters") or [])

# «Лише активні»: період заходу вже настав для обраного року/кварталу
if params.get("active_only") and sel_year != "Усі":
    _q_last = (sel_quarters or ["IV"])[-1]
    _sel_period = int(sel_year) * 10 + core_periods.quarter_to_number(_q_last)
    matched = matched[~matched["measure_start_date"].map(
        lambda v: core_periods.is_measure_not_started(
            core_periods.parse_period(v), _sel_period)
    )].copy()

# Останні моніторингові відомості по кодах
codes = matched["code"].astype(str).str.strip().tolist()
req = monitoring_data.load_monitoring_requests()
latest = pd.DataFrame()
if not req.empty and codes:
    req = req.copy()
    req["_code"] = req["strat_code"].astype(str).str.strip()
    req = req[req["_code"].isin(codes)]
    req = req[req["object_kind"].fillna("measure").astype(str)
              .str.lower().ne("indicator")]
    if sel_year != "Усі":
        req = req[req["year"].astype(str).str.strip() == str(sel_year)]
    if sel_quarters:
        req = req[req["quarter"].astype(str).str.strip().isin(sel_quarters)]
    if params.get("official_only"):
        req = req[req["approval_status"].astype(str).str.strip() == "Погоджено"]
    if not req.empty:
        req["_submitted"] = pd.to_datetime(req.get("submitted_at"), errors="coerce")
        req = req.sort_values(["_code", "_submitted", "id"],
                              ascending=[True, False, False])
        latest = req.drop_duplicates("_code", keep="first").set_index("_code")


def _submission_state(code: str, start_raw) -> tuple[str, dict]:
    """(бейдж стану подання, останні відомості) — за єдиною легендою."""
    if not latest.empty and code in latest.index:
        row = latest.loc[code]
        ap = raw(row.get("approval_status"))
        if ap == "Погоджено":
            b = legend_badge("Погоджено")
        elif ap == "Повернуто на доопрацювання":
            b = legend_badge("На доопрацюванні")
        else:
            b = legend_badge("На розгляді")
        return b, {
            "status": raw(row.get("status")),
            "fact": raw(row.get("numeric_value")),
            "progress": raw(row.get("progress_text")),
            "submitted": raw(row.get("submitted_at"))[:16].replace("T", " "),
        }
    if sel_year != "Усі":
        _quarters = sel_quarters or ["IV"]
        if any((code, str(sel_year), q) in manual_closeouts for q in _quarters):
            return legend_badge("Закрито адміністратором"), {}
        _q_last = _quarters[-1]
        _sel_period = int(sel_year) * 10 + core_periods.quarter_to_number(_q_last)
        if core_periods.is_measure_not_started(
                core_periods.parse_period(start_raw), _sel_period):
            return legend_badge("Не настав час"), {}
        return legend_badge("Не враховано"), {}
    return '<span style="color:#94a3b8;">—</span>', {}


# ------------------------------------------------------------
# Стандартні інформаційні блочки
# ------------------------------------------------------------

_states = [_submission_state(raw(r.get("code")), r.get("measure_start_date"))
           for _, r in matched.iterrows()]
_n_submitted = sum(1 for b, _ in _states if "Погоджено" in b or "розгляді" in b
                   or "доопрацюванні" in b or "адміністратором" in b)
_n_approved = sum(1 for b, _ in _states
                  if "Погоджено" in b or "адміністратором" in b)
_n_notyet = sum(1 for b, _ in _states if "Не настав час" in b)

_kpis = [
    ("Знайдено заходів", len(matched)),
    ("З поданими відомостями", _n_submitted),
    ("Погоджено / закрито", _n_approved),
    ("Не настав час", _n_notyet),
]
st.markdown(
    '<div class="card"><div style="display:flex;flex-wrap:wrap;gap:10px;">'
    + "".join(
        f'<div class="admin-kpi-card" style="min-width:170px;">'
        f'<div class="admin-kpi-label">{k}</div>'
        f'<div class="admin-kpi-value">{v}</div></div>'
        for k, v in _kpis
    )
    + '</div>'
    f'<div style="font-size:12px;color:#64748b;margin-top:8px;">Документ: '
    f'<b>{escape(selected_doc)}</b> · Рік: {escape(str(sel_year))} · '
    f'Квартали: {escape(", ".join(sel_quarters) if sel_quarters else "усі")} · '
    f'Режим: {"офіційні" if params.get("official_only") else "оперативні"} '
    f'дані</div></div>',
    unsafe_allow_html=True,
)

if matched.empty:
    st.warning("За обраними параметрами заходів не знайдено.")
    render_footer()
    st.stop()

# ------------------------------------------------------------
# Результат — таблиця зі закріпленою шапкою (стиль Головної)
# ------------------------------------------------------------

st.markdown(
    '<div class="card"><div class="card-title">Заходи за документом</div>',
    unsafe_allow_html=True,
)

_rows_html = []
export_rows = []
for (_, m), (badge, info) in zip(matched.iterrows(), _states):
    code = raw(m.get("code"))
    name = strip_leading_code(raw(m.get("name")), code)
    _rows_html.append(
        "<tr>"
        f'<td style="white-space:nowrap;font-weight:700;">{escape(code)}</td>'
        f'<td style="min-width:280px;">{escape(name)}</td>'
        f'<td style="min-width:120px;">{escape(raw(m.get("product_type")))}</td>'
        f'<td style="min-width:200px;">{escape(raw(m.get("indicator")))}</td>'
        f'<td style="min-width:130px;">{escape(raw(m.get("resp_main")))}</td>'
        f'<td style="text-align:center;white-space:nowrap;">{badge}</td>'
        f'<td>{escape(info.get("status", ""))}</td>'
        f'<td style="text-align:center;">{escape(info.get("fact", ""))}</td>'
        f'<td style="white-space:nowrap;font-size:11px;color:#64748b;">'
        f'{escape(info.get("submitted", ""))}</td>'
        "</tr>"
    )
    export_rows.append({
        "Код": code, "Захід": name,
        "Тип продукту": raw(m.get("product_type")),
        "Індикатор": raw(m.get("indicator")),
        "Одиниці виміру": raw(m.get("unit")),
        "Головний виконавець": raw(m.get("resp_main")),
        "Співвиконавець": raw(m.get("resp_co_1")),
        "Глобальний рівень": raw(m.get("source_global")),
        "Національний рівень": raw(m.get("source_national")),
        "Стан подання": re.sub(r"<[^>]+>", "", badge),
        "Статус виконання": info.get("status", ""),
        "Фактичне значення": info.get("fact", ""),
        "Опис прогресу": info.get("progress", ""),
        "Останнє подання": info.get("submitted", ""),
    })

_head = (
    "<tr>"
    '<th style="text-align:left;">Код</th>'
    '<th style="text-align:left;">Захід</th>'
    '<th style="text-align:left;">Тип продукту</th>'
    '<th style="text-align:left;">Індикатор</th>'
    '<th style="text-align:left;">Головний виконавець</th>'
    "<th>Стан подання</th>"
    '<th style="text-align:left;">Статус виконання</th>'
    "<th>Факт</th>"
    "<th>Останнє подання</th>"
    "</tr>"
)
st.markdown(
    '<div style="max-height:560px;overflow:auto;border:1px solid #e2e8f0;'
    'border-radius:10px;">'
    '<table style="width:100%;border-collapse:collapse;font-size:12.5px;">'
    '<thead style="position:sticky;top:0;z-index:2;background:#0f172a;'
    'color:#fff;">'
    f"{_head}</thead><tbody>"
    + "".join(_rows_html)
    + "</tbody></table></div>",
    unsafe_allow_html=True,
)
st.markdown('</div>', unsafe_allow_html=True)

# ------------------------------------------------------------
# Експорт (єдиний стандарт охайного Excel)
# ------------------------------------------------------------

params_df = pd.DataFrame([
    {"Параметр": "Документ", "Значення": selected_doc},
    {"Параметр": "Рік", "Значення": sel_year},
    {"Параметр": "Квартали",
     "Значення": ", ".join(sel_quarters) if sel_quarters else "усі"},
    {"Параметр": "Режим",
     "Значення": "офіційні" if params.get("official_only") else "оперативні"},
    {"Параметр": "Сформовано",
     "Значення": datetime.now().strftime("%d.%m.%Y %H:%M")},
])
xlsx = core_exports.write_styled_excel(
    {"Заходи за документом": pd.DataFrame(export_rows)},
    extra_sheets_no_style={"Параметри": params_df},
)
st.download_button(
    "⬇️ Завантажити Excel",
    data=xlsx,
    file_name="Фільтр_за_документом_DEMO_1_9.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

render_footer()
