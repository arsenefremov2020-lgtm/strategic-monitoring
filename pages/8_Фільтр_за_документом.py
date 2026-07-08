import re
from datetime import datetime

import pandas as pd
import streamlit as st

from core.page_setup import page_setup, render_footer
from core.strategic_data import load_strat_matrix, strip_leading_code
from core import monitoring_data
from core.access import filter_actions_for_user
from core.ui import render_scope_toggle, render_auto_refresh_notice
from core import exports as core_exports


PAGE_KEY = "Фільтр за документом"
PPDU_2026_LABEL = "Програма пріоритетних дій Уряду-2026"
PPDU_ALIASES = {
    PPDU_2026_LABEL.lower(),
    "програма пріоритетних дій уряду",
    "програма пріоритетних дій уряду 2026",
    "ппду",
    "ппду-2026",
}

current_user = page_setup(PAGE_KEY, page_name=PAGE_KEY)
render_auto_refresh_notice(PAGE_KEY, minutes=5, show_note=False)

st.markdown('<div class="section-title">Фільтр заходів за НПА / стратегічним документом</div>', unsafe_allow_html=True)
st.caption(
    "Сторінка показує заходи, де обраний документ прямо зазначено у колонках "
    "«Глобальний рівень» або «Національний рівень». Дані моніторингу підтягуються "
    "як останні відомості за обраними параметрами."
)
st.info("Дані автоматично оновлюються кожні 5 хвилин. Фільтри спрацьовують тільки після кнопки «Застосувати обрані параметри».")


def raw(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def normalize_doc_name(value) -> str:
    text = raw(value)
    if not text:
        return ""
    text = text.replace("\u00a0", " ")
    text = re.sub(r"^[\s\"'«»]*\d+[\.)\-\s]+", "", text)
    text = text.strip(" \t\n\r\"'«».,;:")
    text = re.sub(r"\s+", " ", text)
    return text


def split_docs(value) -> list[str]:
    text = raw(value)
    if not text:
        return []
    # Документи у матриці найчастіше розділені ; або переносом рядка. Коми не
    # дробимо агресивно, бо вони часто є частиною назви НПА.
    parts = re.split(r"[;\n]+", text)
    docs = [normalize_doc_name(p) for p in parts]
    return [d for d in docs if d]


def doc_matches_cell(cell_value, selected: str) -> bool:
    wanted = normalize_doc_name(selected).lower()
    if not wanted:
        return True
    docs = [d.lower() for d in split_docs(cell_value)]
    if wanted in PPDU_ALIASES:
        return any((d in PPDU_ALIASES) or ("програма пріоритетних дій" in d) or ("ппду" in d) for d in docs)
    return any(d == wanted or wanted in d for d in docs)


def period_started(row, year: str, quarter: str) -> bool:
    """True, якщо захід релевантний для обраного періоду."""
    q_month_end = {"I": 3, "II": 6, "III": 9, "IV": 12}.get(str(quarter), 12)
    q_end = pd.Timestamp(year=int(year), month=q_month_end, day=28) + pd.offsets.MonthEnd(0)
    start_raw = raw(row.get("start_date") or row.get("Початкова дата") or row.get("Початкова\nдата"))
    if not start_raw:
        return True
    start = pd.to_datetime(start_raw, errors="coerce", dayfirst=True)
    if pd.isna(start):
        return True
    return start <= q_end


def build_doc_options(measures: pd.DataFrame) -> list[str]:
    values: set[str] = set()
    for col in ("source_global", "source_national"):
        if col in measures.columns:
            for cell in measures[col].dropna().tolist():
                values.update(split_docs(cell))
    values.add(PPDU_2026_LABEL)
    return sorted(values, key=lambda x: x.lower())


def latest_monitoring_for_codes(codes: list[str], selected_year: str, selected_quarters: list[str], official_only: bool) -> pd.DataFrame:
    req = monitoring_data.ensure_monitoring_columns(monitoring_data.load_monitoring_requests())
    if req.empty:
        return pd.DataFrame()
    req = req.copy()
    req["_code"] = req["strat_code"].astype(str).str.strip()
    req = req[req["_code"].isin([str(c).strip() for c in codes])]
    req = req[req["object_kind"].fillna("measure").astype(str).str.lower().ne("indicator")]
    if selected_year != "Усі":
        req = req[req["year"].astype(str).str.strip() == str(selected_year)]
    if selected_quarters:
        req = req[req["quarter"].astype(str).str.strip().isin(selected_quarters)]
    if official_only:
        req = req[req["approval_status"].astype(str).str.strip() == "Погоджено"]
    if req.empty:
        return pd.DataFrame()
    req["_submitted"] = pd.to_datetime(req.get("submitted_at"), errors="coerce")
    req = req.sort_values(["_code", "_submitted", "id"], ascending=[True, False, False])
    return req.drop_duplicates("_code", keep="first")


def merge_latest_monitoring(display_df: pd.DataFrame, requests_df: pd.DataFrame) -> pd.DataFrame:
    if requests_df.empty:
        display_df["Статус виконання"] = ""
        display_df["Статус погодження"] = ""
        display_df["Фактичне значення"] = ""
        display_df["Опис прогресу"] = ""
        display_df["Останнє подання"] = ""
        return display_df
    keep = requests_df[["_code", "status", "approval_status", "numeric_value", "progress_text", "submitted_at"]].copy()
    merged = display_df.merge(keep, left_on="Код", right_on="_code", how="left")
    merged = merged.drop(columns=["_code"], errors="ignore")
    merged = merged.rename(columns={
        "status": "Статус виконання",
        "approval_status": "Статус погодження",
        "numeric_value": "Фактичне значення",
        "progress_text": "Опис прогресу",
        "submitted_at": "Останнє подання",
    })
    return merged


raw_df = load_strat_matrix()
measures_all = raw_df[raw_df["object_type"] == "measure"].copy()
measures_scoped = filter_actions_for_user(measures_all, current_user, page_key=PAGE_KEY)

doc_options = build_doc_options(measures_all)

if "npa_filter_applied" not in st.session_state:
    st.session_state.npa_filter_applied = {
        "doc": "",
        "year": "Усі",
        "quarters": [],
        "active_only": True,
        "official_only": True,
    }

with st.form("npa_filter_form"):
    c0, c1, c2, c3 = st.columns([1.15, 2.5, 1.0, 1.2])
    with c0:
        ppdu_clicked = st.form_submit_button("ППДУ-2026", use_container_width=True)
    with c1:
        chosen_doc = st.selectbox(
            "Документ",
            [""] + doc_options,
            index=0,
            key="npa_doc_pending",
            format_func=lambda x: "Оберіть документ" if not x else x,
        )
    with c2:
        year = st.selectbox("Рік", ["Усі", "2026", "2027", "2028", "2029", "2030", "2031", "2032", "2033", "2034"], key="npa_year_pending")
    with c3:
        official_only = st.toggle("Лише офіційні дані", value=True, key="npa_official_pending")

    c4, c5 = st.columns([1.2, 1.2])
    with c4:
        quarters = st.multiselect("Квартал", ["I", "II", "III", "IV"], key="npa_quarters_pending")
    with c5:
        active_only = st.toggle("Лише активні заходи", value=True, key="npa_active_pending")

    apply_clicked = st.form_submit_button("Застосувати обрані параметри", type="primary", use_container_width=True)

reset_col, scope_col = st.columns([1.1, 1.5])
with reset_col:
    reset_clicked = st.button("Скинути параметри", use_container_width=True, key="npa_reset_filters")
with scope_col:
    render_scope_toggle(PAGE_KEY, current_user)

if ppdu_clicked:
    st.session_state.npa_filter_applied = {
        "doc": PPDU_2026_LABEL,
        "year": st.session_state.get("npa_year_pending", "Усі"),
        "quarters": st.session_state.get("npa_quarters_pending", []),
        "active_only": st.session_state.get("npa_active_pending", True),
        "official_only": st.session_state.get("npa_official_pending", True),
    }
    st.rerun()

if apply_clicked:
    st.session_state.npa_filter_applied = {
        "doc": chosen_doc,
        "year": year,
        "quarters": quarters,
        "active_only": active_only,
        "official_only": official_only,
    }
    st.rerun()

if reset_clicked:
    st.session_state.npa_filter_applied = {
        "doc": "",
        "year": "Усі",
        "quarters": [],
        "active_only": True,
        "official_only": True,
    }
    for key in ["npa_doc_pending", "npa_year_pending", "npa_quarters_pending", "npa_active_pending", "npa_official_pending"]:
        st.session_state.pop(key, None)
    st.rerun()

params = st.session_state.npa_filter_applied
selected_doc = params.get("doc", "")
if not selected_doc:
    st.info("Оберіть документ і натисніть «Застосувати обрані параметри» або кнопку «ППДУ-2026».")
    render_footer()
    st.stop()

matched = measures_scoped[
    measures_scoped.apply(
        lambda r: doc_matches_cell(r.get("source_global", ""), selected_doc)
        or doc_matches_cell(r.get("source_national", ""), selected_doc),
        axis=1,
    )
].copy()

if params.get("active_only") and params.get("year") != "Усі":
    q_for_active = (params.get("quarters") or ["IV"])[-1]
    matched = matched[matched.apply(lambda r: period_started(r, params.get("year"), q_for_active), axis=1)].copy()

cards = st.columns(4)
cards[0].metric("Знайдено заходів", len(matched))
cards[1].metric("Рік", params.get("year") or "Усі")
cards[2].metric("Квартали", ", ".join(params.get("quarters") or ["усі"]))
cards[3].metric("Режим даних", "офіційні" if params.get("official_only") else "оперативні")

if matched.empty:
    st.warning("За обраними параметрами заходів не знайдено.")
    render_footer()
    st.stop()

display_df = matched[[
    "code", "name", "product_type", "indicator", "unit",
    "resp_main", "resp_co_1", "source_global", "source_national",
]].copy()
display_df["name"] = display_df.apply(lambda r: strip_leading_code(r["name"], r["code"]), axis=1)
display_df = display_df.rename(columns={
    "code": "Код",
    "name": "Захід",
    "product_type": "Тип продукту",
    "indicator": "Індикатор",
    "unit": "Одиниці виміру",
    "resp_main": "Головний виконавець",
    "resp_co_1": "Співвиконавець",
    "source_global": "Глобальний рівень",
    "source_national": "Національний рівень",
})

latest_req = latest_monitoring_for_codes(
    display_df["Код"].astype(str).tolist(),
    params.get("year", "Усі"),
    params.get("quarters", []),
    params.get("official_only", True),
)
display_df = merge_latest_monitoring(display_df, latest_req)

st.dataframe(display_df, use_container_width=True, hide_index=True, height=560)

params_df = pd.DataFrame([
    {"Параметр": "Документ", "Значення": selected_doc},
    {"Параметр": "Рік", "Значення": params.get("year")},
    {"Параметр": "Квартали", "Значення": ", ".join(params.get("quarters") or ["усі"])},
    {"Параметр": "Режим", "Значення": "офіційні" if params.get("official_only") else "оперативні"},
    {"Параметр": "Сформовано", "Значення": datetime.now().strftime("%d.%m.%Y %H:%M")},
])

xlsx = core_exports.write_styled_excel({"Заходи за документом": display_df}, extra_sheets_no_style={"Параметри": params_df})
st.download_button(
    "⬇️ Завантажити Excel",
    data=xlsx,
    file_name="filter_by_npa_demo_1_9.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

render_footer()
