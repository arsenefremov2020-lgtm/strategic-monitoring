"""Regression contracts for the Filter by Document production page."""
from __future__ import annotations

import ast
import io
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.npa_documents import normalize_for_match

PAGE = ROOT / "pages" / "8_Фільтр_за_документом.py"
HOME = ROOT / "app.py"
SRC = PAGE.read_text(encoding="utf-8")
HOME_SRC = HOME.read_text(encoding="utf-8")
TREE = ast.parse(SRC)


def _helper_namespace(read_excel_sheet=None):
    ns = {
        "pd": pd,
        "io": io,
        "re": re,
        "normalize_for_match": normalize_for_match,
        "log_cosmetic_error": lambda *args, **kwargs: None,
        "read_excel_sheet": read_excel_sheet or (lambda **kwargs: pd.DataFrame()),
        "strip_leading_code": lambda name, code: str(name).replace(str(code), "", 1).strip(" ."),
        "CANONICAL_NPA_DOCUMENTS": [],
    }
    for node in TREE.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = []
            if isinstance(node, ast.Assign):
                targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            elif isinstance(node.target, ast.Name):
                targets = [node.target.id]
            if any(name in {
                "YEAR_OPTIONS", "QUARTERS", "HISTORICAL_COLUMNS", "TABLE_COLUMNS",
                "EXCEL_COLUMN_WIDTHS_PX", "EXCEL_CENTER_COLUMNS", "EXCEL_WRAP_COLUMNS",
            } for name in targets):
                exec(compile(ast.Module(body=[node], type_ignores=[]), str(PAGE), "exec"), ns)
        elif isinstance(node, ast.FunctionDef):
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(PAGE), "exec"), ns)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        else:
            # All UI/runtime code starts after helper definitions.
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "current_user" for target in node.targets
            ):
                break
    return ns


def test_historical_columns_match_home_contract():
    ns = _helper_namespace()
    assert ns["HISTORICAL_COLUMNS"] == [
        ("2021 базовий рівень (факт)", "base_2021"),
        ("2024 звіт", "fact_2024"),
        ("2025 факт", "fact_2025"),
    ]


def test_table_column_order_is_fixed():
    ns = _helper_namespace()
    assert ns["TABLE_COLUMNS"] == [
        "Код заходу", "Захід", "Індикатор", "Тип продукту", "Головний виконавець",
        "Стан подання", "Стан виконання", "2021 базовий рівень (факт)", "2024 звіт",
        "2025 факт", "План", "Факт", "Початок виконання", "Кінець виконання", "Виконання, %",
    ]


def test_npa_registry_reads_c_d_e_and_exact_match():
    source = pd.DataFrame([[None] * 5 for _ in range(7)])
    source.iloc[5, 2] = "План України"
    source.iloc[5, 3] = "Розпорядження № 244"
    source.iloc[5, 4] = "https://example.org/244"
    source.iloc[6, 2] = "Інший документ"
    source.iloc[6, 3] = "Інший НПА"
    source.iloc[6, 4] = "https://example.org/other"

    calls = []
    def reader(**kwargs):
        calls.append(kwargs.get("sheet_name"))
        if kwargs.get("sheet_name") == "Перелік НПА":
            raise ValueError("actual workbook uses underscore")
        return source

    ns = _helper_namespace(read_excel_sheet=reader)
    registry = ns["_load_npa_registry"]()
    assert calls == ["Перелік НПА", "Перелік_НПА"]
    details = ns["_document_details"](registry, "  ПЛАН УКРАЇНИ ")
    assert details == {
        "document": "План України",
        "adoption": "Розпорядження № 244",
        "link": "https://example.org/244",
    }
    assert ns["_document_details"](registry, "План України додатковий") is None


def test_search_uses_same_options_and_supports_number():
    source = pd.DataFrame([[None] * 5 for _ in range(6)])
    source.iloc[5, 2] = "План України"
    source.iloc[5, 3] = "Розпорядження Кабінету Міністрів України № 244"
    source.iloc[5, 4] = "https://example.org/244"
    ns = _helper_namespace(read_excel_sheet=lambda **kwargs: source)
    registry = ns["_load_npa_registry"]()
    options = ["План України", "Інший документ"]
    assert ns["_filter_document_options"](options, "244", registry) == ["План України"]
    assert ns["_filter_document_options"](options, "план укра", registry) == ["План України"]


def test_period_pairs_never_look_ahead():
    ns = _helper_namespace()
    fn = ns["_period_pairs_for_year"]
    assert fn(2026, 2026, "III") == [(2026, "I"), (2026, "II"), (2026, "III")]
    assert fn(2027, 2026, "III") == []
    assert fn(2026, 2027, "II") == [(2026, "I"), (2026, "II"), (2026, "III"), (2026, "IV")]


def test_dynamic_plan_fact_only_selected_year():
    ns = _helper_namespace()
    matched = pd.DataFrame([{
        "code": "1.1.1.", "name": "1.1.1. Тестовий захід", "indicator": "Індикатор",
        "product_type": "НПА", "resp_main": "ССП 10", "base_2021": "10", "fact_2024": "20",
        "fact_2025": "30", "target_2026": "40", "target_2027": "50", "target_2028": "60",
        "measure_start_date": "I квартал 2026", "measure_end_date": "IV квартал 2028",
        "unit": "%", "resp_co_1": "", "source_global": "", "source_national": "",
    }])
    snapshots = {"1.1.1.": {
        "actual": 45.0, "execution_score": 90.0, "result_achieved": False,
        "period_state": "active", "submitted_current_period": True, "approval_status": "Погоджено",
        "effective_result_status": "В процесі", "progress_text": "", "request_submitted_at": "2027-06-01",
    }}
    frame, _ = ns["_build_display_rows"](matched, snapshots, 2027, 2027)
    row = frame.iloc[0]
    assert row["План"] == "50"
    assert row["Факт"] == "45"
    assert row["Виконання, %"] == "90"
    assert row["2021 базовий рівень (факт)"] == "10"
    assert row["2024 звіт"] == "20"
    assert row["2025 факт"] == "30"


def test_shared_v3_is_the_only_execution_source():
    assert "dashboard_breakdowns_v3.build_period_results(" in SRC
    assert "dashboard_breakdowns_v3.aggregate_plan(" in SRC
    assert "dashboard_sources_v3.build_period_source_overrides(" in SRC
    assert "actual /" not in SRC and "fact /" not in SRC


def test_year_selector_and_no_quarter_selector():
    assert "YEAR_OPTIONS = [2026, 2027, 2028]" in SRC
    assert 'st.selectbox("Рік", YEAR_OPTIONS' in SRC
    assert "st.multiselect(\"Квартал\"" not in SRC


def test_ppdu_button_is_preserved():
    assert '"🎯 ППДУ-2026"' in SRC
    assert "on_click=_choose_ppdu" in SRC
    assert "PPDU_2026_LABEL" in SRC


def test_excel_export_is_single_sheet_with_exact_display_table():
    ns = _helper_namespace()
    kpis = [
        {"label": "Заходів", "value": "113"},
        {"label": "Головних виконавців", "value": "33"},
        {"label": "Виконано заходів", "value": "64 із 113"},
        {"label": "Виконання за 2026 рік", "value": "72.73%"},
    ]
    display = pd.DataFrame([{
        "Код заходу": "1.1.1.",
        "Захід": "Тестовий захід",
        "Індикатор": "Тестовий індикатор",
        "Тип продукту": "Інше",
        "Головний виконавець": "деп. 10",
        "Стан подання": "Погоджено",
        "Стан виконання": "Виконано",
        "2021 базовий рівень (факт)": "10",
        "2024 звіт": "20",
        "2025 факт": "30",
        "План": "100",
        "Факт": "72.73",
        "Початок виконання": "I квартал 2026",
        "Кінець виконання": "IV квартал 2026",
        "Виконання, %": "72.73",
    }], columns=ns["TABLE_COLUMNS"])
    xlsx = ns["_build_filter_document_excel"](display, kpis)
    assert isinstance(xlsx, (bytes, bytearray)) and len(xlsx) > 1000

    with zipfile.ZipFile(io.BytesIO(xlsx)) as archive:
        workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
        sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        shared_strings = archive.read("xl/sharedStrings.xml").decode("utf-8")

    assert workbook_xml.count("<sheet ") == 1
    assert 'name="Заходи за документом"' in workbook_xml
    assert "<autoFilter" not in sheet_xml
    for merged in ["A1:C2", "A3:C3", "E1:G2", "E3:G3", "I1:K2", "I3:K3", "M1:O2", "M3:O3"]:
        assert merged in sheet_xml

    # The export must be the exact 15-column table displayed on the page, in the same order.
    for column in ns["TABLE_COLUMNS"]:
        assert column in shared_strings, column
    for obsolete in [
        "Одиниці виміру", "Співвиконавець", "Глобальний рівень", "Національний рівень",
        "Опис прогресу", "Останнє подання", "Фактичне значення",
    ]:
        assert obsolete not in shared_strings, obsolete

    for token in ["Заходів", "Головних виконавців", "Виконано заходів", "Виконання за 2026 рік"]:
        assert token in shared_strings

    assert "extra_sheets_no_style" not in SRC
    assert "worksheet.autofilter(" not in SRC
    assert "_build_filter_document_excel(display_rows, kpi_items)" in SRC
    assert 'file_name="Фільтр_за_документом_DEMO_1_9.xlsx"' in SRC

    # Excel width/alignment contracts mirror the already fixed Signal Grid presentation.
    assert ns["EXCEL_COLUMN_WIDTHS_PX"] == {
        "Код заходу": 90, "Захід": 360, "Індикатор": 430, "Тип продукту": 170,
        "Головний виконавець": 210, "Стан подання": 160, "Стан виконання": 160,
        "2021 базовий рівень (факт)": 130, "2024 звіт": 130, "2025 факт": 130,
        "План": 130, "Факт": 130, "Початок виконання": 130,
        "Кінець виконання": 130, "Виконання, %": 130,
    }
    for column in [
        "Тип продукту", "Головний виконавець", "2021 базовий рівень (факт)",
        "2024 звіт", "2025 факт", "План", "Факт", "Початок виконання",
        "Кінець виконання", "Виконання, %",
    ]:
        assert column in ns["EXCEL_CENTER_COLUMNS"]


def test_table_uses_home_widths_and_signal_grid():
    for token in [
        '"Код заходу": 90', '"Захід": 360', '"Індикатор": 430', '"Тип продукту": 170',
        '"Головний виконавець": 210', '"2021 базовий рівень (факт)": 130',
        'height=350', 'visual_style="signal"', 'enforce_column_widths=True',
    ]:
        assert token in SRC



def test_kpi_cards_use_system_colors_and_table_alignment():
    for token in [
        '"background": "#EAF1FF"',
        '"background": "#E4F5EC"',
        '"accent": "#005BBB"',
        '"accent": "#118847"',
        '"Тип продукту": "center"',
        '"Головний виконавець": "center"',
        '"2021 базовий рівень (факт)": "center"',
        '"2024 звіт": "center"',
        '"2025 факт": "center"',
        '"План": "center"',
        '"Факт": "center"',
        '"Початок виконання": "center"',
        '"Кінець виконання": "center"',
        '"Виконання, %": "center"',
        'height=350',
    ]:
        assert token in SRC



def test_dashboard_page_shell_and_reactive_filter_card():
    # Dashboard-identical branded composition replaces the raw Streamlit title/caption.
    for token in [
        'class="ua-stripe"',
        'max-width: min(1500px, 98vw);',
        'class="ministry-label"',
        'class="header-card"',
        'class="header-title">Фільтр за документом</div>',
        'class="header-subtitle"',
        'Міністерство економіки, довкілля та сільського господарства України',
        'with st.container(key="npa_filter_panel")',
        'class="filter-title">Параметри відбору</div>',
        'class="filter-subtitle npa-filter-subtitle">Документ і період</div>',
        'class="section-card"',
        'class="section-title">Обраний документ</div>',
        'class="npa-kpi-grid"',
    ]:
        assert token in SRC, token
    assert 'st.title("Фільтр за документом")' not in SRC
    assert 'st.caption("Перегляд усіх заходів' not in SRC
    # Controls stay reactive: the page shell fix must not wrap them in a Streamlit form.
    assert 'with st.form(' not in SRC
    assert 'with st.container(border=True):' not in SRC

def test_document_card_uses_exact_registry_and_valid_url():
    ns = _helper_namespace()
    assert ns["_first_http_url"]("text https://example.org/a more") == "https://example.org/a"
    assert ns["_first_http_url"]("не посилання") == ""
    assert "Реквізити документа не знайдено у «Переліку НПА»." in SRC


def test_home_historical_semantics_and_widths_are_reused():
    positions = [HOME_SRC.index('measure.get(\'base_2021\''), HOME_SRC.index('measure.get(\'fact_2024\''), HOME_SRC.index('measure.get(\'fact_2025\'' )]
    assert positions == sorted(positions)
    for token in [".col-code { width: 90px; }", ".col-measure { width: 360px; }", ".col-product { width: 170px; }", ".col-indicator { width: 430px; }", ".col-year { width: 130px; }"]:
        assert token in HOME_SRC


def test_empty_state_precedes_kpi_and_table():
    empty_pos = SRC.index('if not selected_doc:')
    kpi_pos = SRC.index('kpi_items = [')
    table_pos = SRC.index('render_readonly_table(')
    assert empty_pos < kpi_pos < table_pos
    assert 'Оберіть документ, щоб переглянути пов’язану з ним інформацію.' in SRC


def test_no_old_quarter_or_mode_filters_remain():
    for token in ['npa_quarters_pending', 'npa_active_pending', 'npa_official_pending', 'st.multiselect("Квартал"', 'Лише активні заходи', 'Лише офіційні дані']:
        assert token not in SRC


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    passed = 0
    for test in tests:
        test()
        passed += 1
        print(f"PASS {test.__name__}")
    print(f"Filter by Document: {passed}/{len(tests)} PASS")
