"""Regression tests for Dashboard Presentation/PDF parity.

Run from repository root:
    python scripts/test_presentation_pdf.py
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.exports import build_presentation_pdf  # noqa: E402
from core.presentation import (  # noqa: E402
    SLIDE_ORDER,
    build_presentation_payload,
    presentation_slides_by_key,
)


def _sample_payload(*, risk_mode="q2_q3", approval_label="Погоджено"):
    generated_at = datetime(2026, 9, 2, 1, 42, tzinfo=timezone.utc)
    total = 191
    return build_presentation_payload(
        generated_at=generated_at,
        applied_filters={
            "years": [2026],
            "quarters": ["III"],
            "departments": [],
            "goals": [],
            "tasks": [],
            "measures": [],
            "product_types": [],
            "deputies": [],
            "sources": [],
            "financing": [],
            "kpkvk": [],
            "data_source_mode": "confirmed",
        },
        title={
            "eyebrow": "🇺🇦 Міністерство економіки, довкілля та сільського господарства України",
            "title": "Аналітичний дашборд результативності стратегічного плану",
            "subtitle": "Комплексна панель моніторингу та оцінювання стратегічних результатів.",
            "filter_pills": ["📅 2026", "🗓 III кв.", "🏢 Усі підрозділи", "📌 191 заходів у зрізі", "🕐 02.09.2026 01:42"],
        },
        verdict={
            "section": "Висновок системи",
            "severity": "low",
            "emoji": "🟢",
            "title": "Реалізація переважно контрольована",
            "text": "Повний текст системного висновку без обрізання за кількістю символів.",
            "cards": [
                {"label": "Виконання СП", "value": 68.2256, "value_text": "68.2%", "subtitle": "Середнє по заходах у зрізі", "color": "#FFFFFF"},
                {"label": "Покриття", "value": 95.8042, "value_text": "95.8%", "subtitle": "Заходів з поданими даними", "color": "#FFFFFF"},
                {"label": "Виконання за цілями", "value": 64.5087, "value_text": "64.5%", "subtitle": "Ієрархічна оцінка через завдання", "color": "#4D8DFF"},
            ],
        },
        key_metrics={
            "section": "Ключові показники",
            "title": "Статистика виконання заходів",
            "subtitle": "III кв. 2026 · 191 заходів у зрізі",
            "cards": [
                {"label": "Всього заходів", "value": 191, "value_text": "191", "sub_text": "100%", "kind": "blue", "color": "#4D8DFF"},
                {"label": "Виконано", "value": 92, "value_text": "92", "sub_text": "48.17%", "kind": "green", "color": "#00A8A8"},
                {"label": approval_label, "value": 182, "value_text": "182", "sub_text": "95.29%", "kind": "green", "color": "#00A8A8"},
                {"label": "Частково виконано", "value": 41, "value_text": "41", "sub_text": "21.47%", "kind": "yellow", "color": "#F4B400"},
                {"label": "Не подано", "value": 7, "value_text": "7", "sub_text": "3.66%", "kind": "red", "color": "#FF7A45"},
                {"label": "Не виконано", "value": 24, "value_text": "24", "sub_text": "12.57%", "kind": "red", "color": "#FF7A45"},
                {"label": "Не настав час", "value": 27, "value_text": "27", "sub_text": "14.14%", "kind": "gray", "color": "#8A96A8"},
            ],
            "bars": [
                {"label": "Виконання за заходами", "value": 68.2256, "value_text": "68.2256%", "color": "#005BBB"},
                {"label": "Виконання за цілями", "value": 64.5087, "value_text": "64.5087%", "color": "#4D8DFF"},
                {"label": "Покриття моніторингом", "value": 95.8042, "value_text": "95.8042%", "color": "#00A8A8"},
                {"label": "Частка без суттєвого ризику", "value": 65.7, "value_text": "65.7%", "color": "#118847"},
            ],
        },
        strategic_goals={
            "section": "Стратегічні цілі",
            "title": "Виконання за стратегічними цілями",
            "subtitle": "Відсоток виконання по кожній стратегічній цілі · III кв. 2026",
            "rows": [
                {"code": str(i + 1), "name": f"Стратегічна ціль {i + 1}", "full_name": f"Стратегічна ціль {i + 1}", "value": value, "value_text": f"{value}%", "color": "#118847" if value >= 70 else "#FF7A45"}
                for i, value in enumerate([75, 69, 71, 55, 49, 74, 48, 76])
            ],
            "empty_text": "Дані відсутні за обраними фільтрами",
        },
        risks={
            "section": "Автоматична оцінка ризиків" if risk_mode == "q2_q3" else ("Попередні сигнали I кварталу" if risk_mode == "q1" else "Підсумок року"),
            "title": "Розподіл ризиків недосягнення" if risk_mode == "q2_q3" else ("Попередній прогноз без стандартної категоризації ризику" if risk_mode == "q1" else "Фактичні річні результати"),
            "subtitle": "191 заходів у зрізі · III кв. 2026",
            "cards": [
                {"label": "🔴 Критичний / високий ризик", "value": 14, "value_text": "14", "sub_text": "7.33% від усіх заходів", "kind": "high", "color": "#DC4A4A"},
                {"label": "🟡 Середній ризик", "value": 34, "value_text": "34", "sub_text": "17.8% від усіх заходів", "kind": "medium", "color": "#F4B400"},
                {"label": "🟢 Низький ризик", "value": 14, "value_text": "14", "sub_text": "7.33% від усіх заходів", "kind": "low", "color": "#1E9E57"},
            ],
            "summary_label": "Загальний висновок системи",
            "summary_text": "Повний текст системного висновку.",
            "tags": ["Частка з ризиком: 10%", "Без даних: 6 заходів"],
            "mode": risk_mode,
        },
        top5={
            "section": "Увага керівництва",
            "title": "Топ-5 проблемних заходів",
            "subtitle": "V3 attention signals: ризик, відсутність подання, final failure або конфлікт даних · III кв. 2026",
            "rows": [
                {"risk_label": "Високий ризик", "risk_color": "#F4B400", "name": f"Проблемний захід {i + 1}", "full_name": f"Проблемний захід {i + 1}", "code": f"1.1.{i + 1}", "department": "ССП 1", "status": "Не виконано", "performance": 20.0, "performance_text": "20%"}
                for i in range(5)
            ],
            "empty_text": "Критичних заходів не виявлено",
        },
        finance={
            "section": "Фінансування заходів",
            "title": "Структура та обсяги фінансування",
            "subtitle": "III кв. 2026 · 191 заходів у зрізі",
            "sources_label": "Джерела фінансування",
            "groups": [
                {"label": "Державний бюджет", "count": 38, "percent": 19.9, "display": "38 (19.9%)", "color": "#005BBB"},
                {"label": "МТД / кошти партнерів", "count": 7, "percent": 3.7, "display": "7 (3.7%)", "color": "#00A8A8"},
                {"label": "Небюджетні / інші", "count": 8, "percent": 4.2, "display": "8 (4.2%)", "color": "#FF7A45"},
                {"label": "Без фінансування", "count": 140, "percent": 73.3, "display": "140 (73.3%)", "color": "#8A96A8"},
            ],
            "budget": {"label": "Бюджет ДБ 2026", "value": 141.258414, "value_text": "141.258414 млрд грн", "subtitle": "часткові дані — не всі заходи мають суми"},
            "kpkvk_label": "Топ КПКВК за кількістю заходів",
            "kpkvk_rows": [
                {"code": "1201030", "count": 5, "count_text": "5 заходів", "budget_text": "0.002274 млрд грн"},
                {"code": "1201010", "count": 4, "count_text": "4 заходи", "budget_text": "— млрд грн"},
                {"code": "1201350", "count": 4, "count_text": "4 заходи", "budget_text": "1.37 млрд грн"},
            ],
            "kpkvk_empty_text": "КПКВК не визначено",
        },
    )


def test_case_a_seven_pages_and_regression_payload():
    payload = _sample_payload()
    assert tuple(slide["key"] for slide in payload["slides"]) == SLIDE_ORDER
    slides = presentation_slides_by_key(payload)
    cards = slides["key_metrics"]["cards"]
    assert [c["value"] for c in cards] == [191, 92, 182, 41, 7, 24, 27]
    assert len(slides["strategic_goals"]["rows"]) == 8
    assert len(slides["top5"]["rows"]) == 5
    assert slides["finance"]["budget"]["value"] == 141.258414

    pdf = build_presentation_pdf(payload)
    assert pdf is not None and pdf.startswith(b"%PDF")
    pages = len(re.findall(rb"/Type\s*/Page\b", pdf))
    assert pages == 7, pages


def test_cases_b_c_d_modes_and_dynamic_approval():
    assert presentation_slides_by_key(_sample_payload(risk_mode="q1"))["risks"]["mode"] == "q1"
    assert presentation_slides_by_key(_sample_payload(risk_mode="q4"))["risks"]["mode"] == "q4"
    operational = presentation_slides_by_key(
        _sample_payload(approval_label="Пройшли координатора")
    )
    assert operational["key_metrics"]["cards"][2]["label"] == "Пройшли координатора"


def test_cases_e_f_dashboard_uses_one_payload_for_all_filters_and_renderers():
    source = (ROOT / "pages" / "2_Dashboard.py").read_text(encoding="utf-8")
    assert source.count("build_presentation_payload(") == 1
    assert "build_presentation_pdf(_presentation_payload)" in source
    assert "presentation_slides_by_key(_presentation_payload)" in source
    assert "_pdf_kpis" not in source
    assert "_pdf_figures" not in source
    assert "conclusion_text[:110]" not in source

    usages = []
    production_paths = [ROOT / "app.py", *(ROOT / "pages").glob("*.py"), *(ROOT / "core").rglob("*.py")]
    for path in production_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if "build_presentation_pdf(" in line and not line.lstrip().startswith("def build_presentation_pdf"):
                usages.append((path.relative_to(ROOT).as_posix(), line_no, line.strip()))
    assert len(usages) == 1, usages
    assert usages[0][0] == "pages/2_Dashboard.py", usages
    assert usages[0][2] == "_pdf_bytes = build_presentation_pdf(_presentation_payload)", usages

    exports_source = (ROOT / "core" / "exports.py").read_text(encoding="utf-8")
    assert "kpi_items:" not in exports_source
    assert "figures:" not in exports_source
    assert "Мінекономіки · Система моніторингу стратегічного плану" not in exports_source
    assert "setFillColorRGB(0.97, 0.98, 0.99)" not in exports_source

    for key in (
        '"departments": list(selected_department_indices or [])',
        '"goals": list(selected_goals or [])',
        '"tasks": list(selected_tasks or [])',
        '"measures": list(selected_measures or [])',
        '"product_types": list(selected_product_types or [])',
        '"deputies": list(selected_deputies or [])',
        '"sources": list(selected_sources or [])',
        '"financing": list(selected_financing or [])',
        '"kpkvk": list(selected_kpkvk or [])',
    ):
        assert key in source


def main():
    test_case_a_seven_pages_and_regression_payload()
    test_cases_b_c_d_modes_and_dynamic_approval()
    test_cases_e_f_dashboard_uses_one_payload_for_all_filters_and_renderers()
    print("test_presentation_pdf: PASS")


if __name__ == "__main__":
    main()
