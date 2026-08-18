"""Фільтр за документом — управлінський зріз заходів Стратегічного плану."""
from __future__ import annotations

import re
from html import escape

import pandas as pd
import streamlit as st

from core.page_setup import page_setup, render_footer
from core.strategic_data import load_strat_matrix, strip_leading_code
from core import monitoring_data
from core import dashboard_breakdowns as dashboard_breakdowns_v3
from core import dashboard_periods as dashboard_periods_v3
from core import dashboard_sources as dashboard_sources_v3
from core.access import filter_actions_for_user
from core.ui import render_readonly_table, render_scope_toggle, load_css
from core.excel_loader import read_excel_sheet
from core.timeutils import now_kyiv
from core import exports as core_exports
from core.errors import log_cosmetic_error
from config.npa_documents import (
    CANONICAL_NPA_DOCUMENTS,
    PPDU_2026_LABEL,
    normalize_for_match,
)

PAGE_KEY = "Фільтр за документом"
YEAR_OPTIONS = [2026, 2027, 2028]
QUARTERS = ["I", "II", "III", "IV"]
HISTORICAL_COLUMNS = [
    ("2021 базовий рівень (факт)", "base_2021"),
    ("2024 звіт", "fact_2024"),
    ("2025 факт", "fact_2025"),
]
TABLE_COLUMNS = [
    "Код заходу",
    "Захід",
    "Індикатор",
    "Тип продукту",
    "Головний виконавець",
    "Стан подання",
    "Стан виконання",
    *[label for label, _ in HISTORICAL_COLUMNS],
    "План",
    "Факт",
    "Початок виконання",
    "Кінець виконання",
    "Виконання, %",
]


def raw(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception as exc:
        log_cosmetic_error("Нормалізація значення у фільтрі за документом", exc)
    return str(value).strip()


def _search_text(value) -> str:
    text = raw(value).replace("\u00a0", " ").replace("’", "'").replace("`", "'")
    text = text.replace("«", '"').replace("»", '"').casefold()
    return re.sub(r"\s+", " ", text).strip()


def _document_in_cell(cell_value, document_name: str) -> bool:
    """Deterministic canonical-title containment, not fuzzy similarity matching."""
    wanted = normalize_for_match(document_name)
    cell = normalize_for_match(raw(cell_value))
    return bool(wanted and cell and (cell == wanted or wanted in cell))


def _document_options_from_matrix(measures: pd.DataFrame) -> list[str]:
    if measures is None or measures.empty:
        return []
    cells: list[str] = []
    for column in ("source_global", "source_national"):
        if column in measures.columns:
            cells.extend(measures[column].dropna().astype(str).tolist())
    result = [
        label for label in CANONICAL_NPA_DOCUMENTS
        if any(_document_in_cell(cell, label) for cell in cells)
    ]
    return sorted(dict.fromkeys(result), key=lambda value: value.casefold())


def _load_npa_registry() -> pd.DataFrame:
    """Read C/D/E from the actual NPA registry sheet without mutating cached Excel data."""
    for sheet_name in ("Перелік НПА", "Перелік_НПА"):
        try:
            source = read_excel_sheet(sheet_name=sheet_name, header=None)
        except (ValueError, KeyError):
            continue
        except Exception as exc:
            log_cosmetic_error("Читання аркуша Перелік НПА", exc)
            return pd.DataFrame(columns=["document", "adoption", "link"])
        if source is None or source.empty or source.shape[1] < 5:
            return pd.DataFrame(columns=["document", "adoption", "link"])
        registry = pd.DataFrame({
            "document": source.iloc[:, 2],  # C
            "adoption": source.iloc[:, 3],  # D
            "link": source.iloc[:, 4],      # E
        }).copy()
        registry = registry[registry["document"].map(raw).ne("")].copy()
        registry["_norm"] = registry["document"].map(lambda value: normalize_for_match(raw(value)))
        return registry
    return pd.DataFrame(columns=["document", "adoption", "link", "_norm"])


def _document_details(registry: pd.DataFrame, document_name: str) -> dict | None:
    if registry is None or registry.empty or not document_name:
        return None
    wanted = normalize_for_match(document_name)
    if not wanted:
        return None
    norm = registry.get("_norm")
    if norm is None:
        norm = registry["document"].map(lambda value: normalize_for_match(raw(value)))
    matches = registry[norm.eq(wanted)]
    if matches.empty:
        return None
    row = matches.iloc[0]
    return {
        "document": raw(row.get("document")),
        "adoption": raw(row.get("adoption")),
        "link": raw(row.get("link")),
    }


def _first_http_url(value) -> str:
    match = re.search(r"https?://[^\s<>'\"]+", raw(value), flags=re.I)
    return match.group(0).rstrip(".,;)") if match else ""


def _filter_document_options(options: list[str], query: str, registry: pd.DataFrame) -> list[str]:
    query_text = _search_text(query)
    if not query_text:
        return list(options)
    terms = [term for term in query_text.split(" ") if term]
    result = []
    for option in options:
        details = _document_details(registry, option) or {}
        haystack = _search_text(" ".join([
            option,
            details.get("adoption", ""),
        ]))
        if all(term in haystack for term in terms):
            result.append(option)
    return result


def _period_pairs_for_year(selected_year: int, reporting_year: int, reporting_quarter: str) -> list[tuple[int, str]]:
    """Only periods that can already be reporting periods; never look ahead."""
    selected_year = int(selected_year)
    reporting_year = int(reporting_year)
    if selected_year > reporting_year:
        return []
    if selected_year < reporting_year:
        return [(selected_year, quarter) for quarter in QUARTERS]
    ceiling = {"I": 1, "II": 2, "III": 3, "IV": 4}.get(str(reporting_quarter).strip().upper(), 1)
    return [(selected_year, quarter) for quarter in QUARTERS[:ceiling]]


def _latest_snapshot_by_code(period_results: dict) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for key in sorted(period_results, key=lambda item: item[0] * 10 + {"I": 1, "II": 2, "III": 3, "IV": 4}[item[1]]):
        snapshot = period_results[key].get("snapshot")
        if snapshot is None or snapshot.empty:
            continue
        for _, row in snapshot.iterrows():
            code = raw(row.get("code"))
            if code:
                latest[code] = row.to_dict()
    return latest


def _submission_state(snapshot: dict | None, *, future_year: bool = False) -> str:
    if snapshot is None:
        return "Не настав час" if future_year else "Не подано"
    if raw(snapshot.get("period_state")) in {"future", "not_started"}:
        return "Не настав час"
    if bool(snapshot.get("submitted_current_period")):
        return raw(snapshot.get("approval_status")) or "Погоджено"
    if bool(snapshot.get("missing_required_submission")) or bool(snapshot.get("final_missing_result")):
        return "Не подано"
    if bool(snapshot.get("carry_forward")):
        return "Не подано"
    return "—"


def _execution_state(snapshot: dict | None, *, future_year: bool = False) -> str:
    if snapshot is None:
        return "Не настав час" if future_year else "—"
    if raw(snapshot.get("period_state")) in {"future", "not_started"}:
        return "Не настав час"
    return raw(snapshot.get("effective_result_status")) or raw(snapshot.get("status_display")) or "—"


def _format_number(value, digits: int = 2) -> str:
    if value is None:
        return "—"
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        text = raw(value)
        return text if text else "—"
    return f"{float(number):.{digits}f}".rstrip("0").rstrip(".")


def _format_execution_kpi(value) -> str:
    if value is None:
        return "—"
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "—"
    return f"{_format_number(number, 2)}%"


def _build_display_rows(
    matched: pd.DataFrame,
    snapshots: dict[str, dict],
    selected_year: int,
    reporting_year: int,
) -> tuple[pd.DataFrame, list[dict]]:
    display_rows: list[dict] = []
    export_rows: list[dict] = []
    future_year = int(selected_year) > int(reporting_year)
    for _, measure in matched.iterrows():
        code = raw(measure.get("code"))
        name = strip_leading_code(raw(measure.get("name")), code)
        snapshot = snapshots.get(code)
        plan_value = measure.get(f"target_{int(selected_year)}", "")
        fact_value = snapshot.get("actual") if snapshot else None
        execution_value = snapshot.get("execution_score") if snapshot else None

        row = {
            "Код заходу": code,
            "Захід": name,
            "Індикатор": raw(measure.get("indicator")),
            "Тип продукту": raw(measure.get("product_type")),
            "Головний виконавець": raw(measure.get("resp_main")),
            "Стан подання": _submission_state(snapshot, future_year=future_year),
            "Стан виконання": _execution_state(snapshot, future_year=future_year),
            HISTORICAL_COLUMNS[0][0]: raw(measure.get(HISTORICAL_COLUMNS[0][1])),
            HISTORICAL_COLUMNS[1][0]: raw(measure.get(HISTORICAL_COLUMNS[1][1])),
            HISTORICAL_COLUMNS[2][0]: raw(measure.get(HISTORICAL_COLUMNS[2][1])),
            "План": raw(plan_value) or "—",
            "Факт": _format_number(fact_value, 4) if fact_value is not None else "—",
            "Початок виконання": raw(measure.get("measure_start_date")) or "—",
            "Кінець виконання": raw(measure.get("measure_end_date")) or "—",
            "Виконання, %": _format_number(execution_value, 2) if execution_value is not None else "—",
        }
        display_rows.append(row)

        # Preserve the existing Excel export schema; this stage does not redesign export.
        export_rows.append({
            "Код": code,
            "Захід": name,
            "Тип продукту": raw(measure.get("product_type")),
            "Індикатор": raw(measure.get("indicator")),
            "Одиниці виміру": raw(measure.get("unit")),
            "Головний виконавець": raw(measure.get("resp_main")),
            "Співвиконавець": raw(measure.get("resp_co_1")),
            "Глобальний рівень": raw(measure.get("source_global")),
            "Національний рівень": raw(measure.get("source_national")),
            "Стан подання": row["Стан подання"],
            "Статус виконання": row["Стан виконання"],
            "Фактичне значення": row["Факт"],
            "Опис прогресу": raw(snapshot.get("progress_text")) if snapshot else "",
            "Останнє подання": raw(snapshot.get("request_submitted_at"))[:16].replace("T", " ") if snapshot else "",
        })

    frame = pd.DataFrame(display_rows, columns=TABLE_COLUMNS)
    return frame, export_rows


current_user = page_setup(PAGE_KEY, page_name=PAGE_KEY)
load_css()

# Page shell intentionally mirrors the current Dashboard composition.
# Functional controls and calculations below remain unchanged.
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
    max-width: min(1500px, 98vw);
    padding: clamp(0.5rem, 2vw, 1.5rem) clamp(0.5rem, 2vw, 2rem);
    position: relative;
    z-index: 1;
}

/* Dashboard-identical branded shell, scoped to this page. */
.ua-stripe {
    height: 5px;
    border-radius: 0 0 6px 6px;
    background: linear-gradient(90deg, #005BBB 50%, #FFD500 50%);
    margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(0,91,187,0.15);
}
.ministry-label {
    text-align: right;
    color: #61708A;
    font-size: clamp(11px, 1.1vw, 14px);
    font-weight: 700;
    margin-bottom: 10px;
    letter-spacing: 0.01em;
}
.header-card {
    background: #F7F9FC;
    border: 1px solid #DCE4F0;
    border-left: 5px solid #005BBB;
    border-radius: 12px;
    padding: clamp(16px, 2.5vw, 28px) clamp(16px, 2.5vw, 32px);
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(0,91,187,0.08), 0 1px 4px rgba(0,0,0,0.04);
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 16px;
}
.header-main {
    flex: 1 1 100%;
    width: 100%;
    min-width: 200px;
}
.header-title {
    font-size: clamp(20px, 2.5vw, 30px);
    font-weight: 900;
    color: #032A63;
    margin: 0 0 6px 0;
    line-height: 1.2;
}
.header-subtitle {
    font-size: clamp(12px, 1.1vw, 14px);
    color: #61708A;
    line-height: 1.6;
    max-width: none;
    width: 100%;
}

/* Dashboard section-card tokens reused for the document information card. */
.section-card {
    background: #FFFFFF;
    border: 1px solid #DCE4F0;
    border-radius: 12px;
    padding: clamp(14px, 2vw, 22px) clamp(14px, 2vw, 24px);
    margin-bottom: 18px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.section-title {
    font-size: clamp(15px, 1.4vw, 19px);
    font-weight: 800;
    color: #032A63;
    margin: 0 0 4px 0;
}

/* Reactive control panel: visual equivalent of Dashboard filter card, without st.form. */
.st-key-npa_filter_panel {
    background: #FFFFFF;
    border: 1px solid #DCE4F0;
    border-radius: 12px;
    padding: clamp(14px, 2vw, 22px) clamp(14px, 2vw, 24px);
    margin-bottom: 18px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.st-key-npa_filter_panel .npa-filter-subtitle {
    margin-top: 0 !important;
}

.npa-kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 12px;
    margin: 0 0 20px 0;
}
.npa-document-name {
    font-size: 20px;
    font-weight: 750;
    color: #132238;
    margin: 8px 0 12px;
}
.npa-document-meta {
    font-size: 13px;
    color: #61708A;
}
.npa-document-meta b { color: #132238; }
.npa-document-link {
    display: inline-block;
    margin-top: 12px;
    color: #005BBB !important;
    font-weight: 700;
    text-decoration: none !important;
}
</style>
<div class="ua-stripe"></div>
<div class="ministry-label">
🇺🇦 Міністерство економіки, довкілля та сільського господарства України
</div>
<div class="header-card">
    <div class="header-main">
        <div class="header-title">Фільтр за документом</div>
        <div class="header-subtitle">
            Перегляд усіх заходів та показників, пов’язаних з обраним документом.
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

raw_df = load_strat_matrix()
measures_all = raw_df[raw_df["object_type"].astype(str).str.strip().eq("measure")].copy()
measures_scoped = filter_actions_for_user(measures_all, current_user, page_key=PAGE_KEY)
requests_all = monitoring_data.load_monitoring_requests()
measure_requests = monitoring_data.measures_only(requests_all)
registry = _load_npa_registry()
doc_options = _document_options_from_matrix(measures_all)

try:
    reporting_year, reporting_quarter = dashboard_periods_v3.current_reporting_period(measure_requests)
except Exception as exc:
    log_cosmetic_error("Визначення поточного звітного періоду", exc)
    reporting_year, reporting_quarter = 2026, "I"
default_year = reporting_year if reporting_year in YEAR_OPTIONS else YEAR_OPTIONS[0]

st.session_state.setdefault("npa_doc_search", "")
st.session_state.setdefault("npa_doc_selected", "")
st.session_state.setdefault("npa_year_selected", default_year)


def _choose_ppdu():
    st.session_state["npa_doc_search"] = ""
    st.session_state["npa_doc_selected"] = PPDU_2026_LABEL if PPDU_2026_LABEL in doc_options else ""


with st.container(key="npa_filter_panel"):
    st.markdown(
        '<div class="filter-title">Параметри відбору</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="filter-subtitle npa-filter-subtitle">Документ і період</div>',
        unsafe_allow_html=True,
    )
    search_query = st.text_input(
        "Пошук за назвою / номером",
        key="npa_doc_search",
        placeholder="Введіть частину назви, номер або характерне слово",
    )
    filtered_options = _filter_document_options(doc_options, search_query, registry)
    current_selection = raw(st.session_state.get("npa_doc_selected"))
    if current_selection not in filtered_options:
        if search_query and len(filtered_options) == 1:
            st.session_state["npa_doc_selected"] = filtered_options[0]
        elif search_query:
            st.session_state["npa_doc_selected"] = ""
        elif current_selection not in doc_options:
            st.session_state["npa_doc_selected"] = ""

    c_doc, c_year, c_ppdu = st.columns([4.5, 1.2, 1.4])
    with c_doc:
        selected_doc = st.selectbox(
            "Оберіть документ",
            [""] + filtered_options,
            key="npa_doc_selected",
            format_func=lambda value: "Оберіть документ" if not value else value,
        )
    with c_year:
        selected_year = st.selectbox("Рік", YEAR_OPTIONS, key="npa_year_selected")
    with c_ppdu:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        st.button(
            "🎯 ППДУ-2026",
            use_container_width=True,
            help=PPDU_2026_LABEL,
            on_click=_choose_ppdu,
        )
    render_scope_toggle(PAGE_KEY, current_user)

if not selected_doc:
    st.info("Оберіть документ, щоб переглянути пов’язану з ним інформацію.")
    render_footer()
    st.stop()

wanted_norm = normalize_for_match(selected_doc)
matched = measures_scoped[
    measures_scoped.apply(
        lambda row: _document_in_cell(row.get("source_global", ""), selected_doc)
        or _document_in_cell(row.get("source_national", ""), selected_doc),
        axis=1,
    )
].copy()
matched = matched.drop_duplicates(subset=["code"], keep="first").copy()

# Document card: exact normalized C -> D/E matching only.
details = _document_details(registry, selected_doc)
if details:
    adopted = details.get("adoption") or "—"
    link = _first_http_url(details.get("link"))
    link_html = (
        f'<a href="{escape(link, quote=True)}" target="_blank" rel="noopener noreferrer" '
        'class="npa-document-link">'
        'Відкрити документ ↗</a>'
        if link else ""
    )
    st.markdown(
        '<div class="section-card">'
        '<div class="section-title">Обраний документ</div>'
        f'<div class="npa-document-name">{escape(selected_doc)}</div>'
        f'<div class="npa-document-meta"><b>Прийнято:</b> {escape(adopted)}</div>'
        f'{link_html}'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="section-card">'
        '<div class="section-title">Обраний документ</div>'
        f'<div class="npa-document-name">{escape(selected_doc)}</div>'
        '<div class="npa-document-meta">Реквізити документа не знайдено у «Переліку НПА».</div>'
        '</div>',
        unsafe_allow_html=True,
    )

codes = matched["code"].astype(str).str.strip().tolist() if not matched.empty else []
pairs = _period_pairs_for_year(selected_year, reporting_year, reporting_quarter)
period_results = {}
if codes and pairs:
    period_sources = dashboard_sources_v3.build_period_source_overrides(
        pairs,
        measure_codes=codes,
    )
    period_results = dashboard_breakdowns_v3.build_period_results(
        matched,
        measure_requests,
        pairs,
        period_sources=period_sources,
    )

snapshots = _latest_snapshot_by_code(period_results)
plan_summary = dashboard_breakdowns_v3.aggregate_plan(period_results) if period_results else {}
execution_kpi = plan_summary.get("execution_by_measures_latest")
completed_count = sum(bool(snapshots.get(code, {}).get("result_achieved")) for code in codes)
main_executors = {
    raw(value) for value in matched.get("resp_main", pd.Series(dtype=object)).tolist() if raw(value)
}

kpi_items = [
    {
        "label": "Заходів",
        "value": str(len(matched)),
        "background": "#EAF1FF",
        "border": "#BFD3F2",
        "accent": "#005BBB",
    },
    {
        "label": "Головних виконавців",
        "value": str(len(main_executors)),
        "background": "#F5F8FD",
        "border": "#DCE4F0",
        "accent": "#032A63",
    },
    {
        "label": "Виконано заходів",
        "value": f"{completed_count} із {len(matched)}",
        "background": "#E4F5EC",
        "border": "#BFE7CF",
        "accent": "#118847",
    },
    {
        "label": f"Виконання за {selected_year} рік",
        "value": _format_execution_kpi(execution_kpi),
        "background": "#F3F7FD",
        "border": "#BFD3F2",
        "accent": "#005BBB",
    },
]
st.markdown(
    '<div class="npa-kpi-grid">'
    + "".join(
        '<div class="admin-kpi-card" '
        f'style="background:{item["background"]};border:1px solid {item["border"]};'
        f'border-top:3px solid {item["accent"]};box-shadow:0 4px 14px rgba(15,23,42,.035);">'
        f'<div class="admin-kpi-value" style="color:{item["accent"]};">{escape(item["value"])}</div>'
        f'<div class="admin-kpi-label" style="color:#61708A;">{escape(item["label"])}</div>'
        '</div>'
        for item in kpi_items
    )
    + '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div style="display:flex;align-items:baseline;justify-content:space-between;gap:16px;margin-top:6px;">'
    '<div style="font-size:18px;font-weight:750;color:#032A63;">Інформація за документом</div>'
    f'<div style="font-size:12px;color:#61708A;">{len(matched)} записів</div>'
    '</div>',
    unsafe_allow_html=True,
)

if matched.empty:
    st.info("За обраним документом у доступному вам переліку заходів записів не знайдено.")
    display_rows = pd.DataFrame(columns=TABLE_COLUMNS)
    export_rows: list[dict] = []
else:
    display_rows, export_rows = _build_display_rows(
        matched,
        snapshots,
        selected_year,
        reporting_year,
    )
    render_readonly_table(
        display_rows,
        height=350,
        min_width=2785,
        empty_message="За обраним документом немає заходів.",
        visual_style="signal",
        variant="wide",
        show_index=False,
        table_width="fit-columns",
        column_widths={
            "Код заходу": 90,
            "Захід": 360,
            "Індикатор": 430,
            "Тип продукту": 170,
            "Головний виконавець": 210,
            "Стан подання": 160,
            "Стан виконання": 160,
            "2021 базовий рівень (факт)": 130,
            "2024 звіт": 130,
            "2025 факт": 130,
            "План": 130,
            "Факт": 130,
            "Початок виконання": 130,
            "Кінець виконання": 130,
            "Виконання, %": 130,
        },
        scroll_columns={"Захід", "Індикатор"},
        status_columns={"Стан подання", "Стан виконання"},
        metric_columns={"Виконання, %": "blue"},
        column_alignments={
            "Тип продукту": "center",
            "Головний виконавець": "center",
            "2021 базовий рівень (факт)": "center",
            "2024 звіт": "center",
            "2025 факт": "center",
            "План": "center",
            "Факт": "center",
            "Початок виконання": "center",
            "Кінець виконання": "center",
            "Виконання, %": "center",
        },
        enforce_column_widths=True,
    )

# Existing export is deliberately preserved; no new export functionality in this stage.
params_df = pd.DataFrame([
    {"Параметр": "Документ", "Значення": selected_doc},
    {"Параметр": "Рік", "Значення": selected_year},
    {"Параметр": "Квартали", "Значення": "усі"},
    {"Параметр": "Режим", "Значення": "офіційні"},
    {"Параметр": "Сформовано", "Значення": now_kyiv().strftime("%d.%m.%Y %H:%M")},
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
