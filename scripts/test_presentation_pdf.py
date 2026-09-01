"""Runtime regression tests for Dashboard Presentation/PDF parity.

Run from repository root:
    python scripts/test_presentation_pdf.py

Test-only dependency for text extraction:
    pypdf
"""
from __future__ import annotations

import io
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pypdf import PdfReader  # noqa: E402

from core.exports import (  # noqa: E402
    build_legacy_presentation_pdf,
    build_presentation_pdf,
)
from core.presentation import (  # noqa: E402
    REFERENCE_HEIGHT,
    REFERENCE_WIDTH,
    SLIDE_ORDER,
    build_presentation_html,
    build_presentation_payload,
    presentation_slides_by_key,
)

LONG_CONCLUSION = (
    "Система фіксує переважно контрольований хід реалізації стратегічного плану, "
    "водночас окремі заходи потребують управлінської уваги через неповне подання "
    "даних, відхилення від очікуваної траєкторії та ризики недосягнення запланованих "
    "результатів. Пріоритетом наступного циклу моніторингу є закриття прогалин у "
    "звітності та робота з найбільш проблемними заходами без зміни затвердженої "
    "методології оцінювання."
)

LONG_GOALS = [
    "Забезпечення антикризової стійкості та підтримки економіки воєнного часу",
    "Підвищення інвестиційної привабливості України та залучення інвестицій у сектори з високою доданою вартістю",
    "Розвиток підприємництва, промислової політики та конкурентоспроможного внутрішнього виробництва",
    "Розширення міжнародної торгівлі та інтеграція українських виробників до європейських і глобальних ринків",
    "Розвиток людського капіталу, зайнятості та сучасної системи професійних навичок",
    "Підвищення ефективності управління державною власністю та корпоративного врядування",
    "Забезпечення сталого екологічного розвитку та зеленої трансформації економіки",
    "Формування сучасної цифрової держави, інноваційної економіки та інституційної спроможності",
]

LONG_TOP5 = [
    "Забезпечення повного запуску комплексного механізму підтримки інвестиційних проектів зі значними інвестиціями",
    "Розроблення та впровадження оновленої системи моніторингу результативності державних програм підтримки бізнесу",
    "Підготовка нормативних змін для прискорення процедур приватизації та підвищення прозорості управління активами",
    "Розширення інструментів страхування воєнних ризиків для нових інвестиційних проектів у пріоритетних секторах",
    "Створення узгодженого механізму підтримки експорту продукції з високою доданою вартістю на стратегічні ринки",
]


def _risk_fixture(mode: str):
    if mode == "q1":
        return {
            "section": "Попередні сигнали I кварталу",
            "title": "Попередній прогноз без стандартної категоризації ризику",
            "cards": [
                {"label": "Сигнали уваги", "value": 23, "value_text": "23", "sub_text": "12.04% від усіх заходів", "kind": "high", "color": "#DC4A4A"},
                {"label": "Сформовано попередніх прогнозів", "value": 62, "value_text": "62", "sub_text": "32.46% від усіх заходів", "kind": "medium", "color": "#F4B400"},
                {"label": "Стандартних категорій ризику", "value": 0, "value_text": "0", "sub_text": "0.0% від усіх заходів", "kind": "low", "color": "#1E9E57"},
            ],
            "tag": "Попередніх сигналів уваги: 12%",
            "fourth_label": "Середнє попереднє досягнення",
            "fourth_value": 58.4,
            "fourth_text": "58.4%",
            "quarter": "I",
        }
    if mode == "q4":
        return {
            "section": "Підсумок року",
            "title": "Фактичні річні результати",
            "cards": [
                {"label": "🔴 Результат не досягнуто", "value": 24, "value_text": "24", "sub_text": "12.57% від усіх заходів", "kind": "high", "color": "#DC4A4A"},
                {"label": "🟡 Частково виконано", "value": 41, "value_text": "41", "sub_text": "21.47% від усіх заходів", "kind": "medium", "color": "#F4B400"},
                {"label": "🟢 Результат досягнуто", "value": 92, "value_text": "92", "sub_text": "48.17% від усіх заходів", "kind": "low", "color": "#1E9E57"},
            ],
            "tag": "Не досягнуто: 12.6%",
            "fourth_label": "Результатів досягнуто",
            "fourth_value": 79.3,
            "fourth_text": "79.3%",
            "quarter": "IV",
        }
    return {
        "section": "Автоматична оцінка ризиків",
        "title": "Розподіл ризиків недосягнення",
        "cards": [
            {"label": "🔴 Критичний / високий ризик", "value": 14, "value_text": "14", "sub_text": "7.33% від усіх заходів", "kind": "high", "color": "#DC4A4A"},
            {"label": "🟡 Середній ризик", "value": 34, "value_text": "34", "sub_text": "17.8% від усіх заходів", "kind": "medium", "color": "#F4B400"},
            {"label": "🟢 Низький ризик", "value": 14, "value_text": "14", "sub_text": "7.33% від усіх заходів", "kind": "low", "color": "#1E9E57"},
        ],
        "tag": "Частка з ризиком: 10%",
        "fourth_label": "Частка без суттєвого ризику",
        "fourth_value": 65.7,
        "fourth_text": "65.7%",
        "quarter": "III",
    }


def _sample_payload(*, risk_mode="q2_q3", data_source_mode="confirmed"):
    generated_at = datetime(2026, 9, 2, 1, 42, tzinfo=timezone.utc)
    total = 191
    risk = _risk_fixture(risk_mode)
    operational = data_source_mode == "operational"
    approval_label = "Пройшли координатора" if operational else "Погоджено"
    approval_value = 184 if operational else 182
    period = f"{risk['quarter']} кв. 2026"

    payload = build_presentation_payload(
        generated_at=generated_at,
        applied_filters={
            "years": [2026],
            "quarters": [risk["quarter"]],
            "departments": [],
            "goals": [],
            "tasks": [],
            "measures": [],
            "product_types": [],
            "deputies": [],
            "sources": [],
            "financing": [],
            "kpkvk": [],
            "data_source_mode": data_source_mode,
        },
        title={
            "eyebrow": "🇺🇦 Міністерство економіки, довкілля та сільського господарства України",
            "title": "Аналітичний дашборд результативності стратегічного плану",
            "subtitle": (
                "Комплексна панель моніторингу та оцінювання стратегічних результатів — "
                "в розрізі стратегічних цілей, завдань та самостійних структурних підрозділів."
            ),
            "filter_pills": [
                "📅 2026",
                f"🗓 {risk['quarter']} кв.",
                "🏢 Усі підрозділи",
                "📌 191 заходів у зрізі",
                "🕐 02.09.2026 01:42",
            ],
        },
        verdict={
            "section": "Висновок системи",
            "severity": "low",
            "emoji": "🟢",
            "title": "Реалізація переважно контрольована",
            "text": LONG_CONCLUSION,
            "cards": [
                {"label": "Виконання СП", "value": 68.2256, "value_text": "68.2%", "subtitle": "Середнє по заходах у зрізі", "color": "#FFFFFF"},
                {"label": "Покриття", "value": 95.8042, "value_text": "95.8%", "subtitle": "Заходів з поданими даними", "color": "#FFFFFF"},
                {"label": "Виконання за цілями", "value": 64.5087, "value_text": "64.5%", "subtitle": "Ієрархічна оцінка через завдання", "color": "#4D8DFF"},
            ],
        },
        key_metrics={
            "section": "Ключові показники",
            "title": "Статистика виконання заходів",
            "subtitle": f"{period} · 191 заходів у зрізі",
            "cards": [
                {"label": "Всього заходів", "value": 191, "value_text": "191", "sub_text": "100%", "kind": "blue", "color": "#4D8DFF"},
                {"label": "Виконано", "value": 92, "value_text": "92", "sub_text": "48.17%", "kind": "green", "color": "#00A8A8"},
                {"label": approval_label, "value": approval_value, "value_text": str(approval_value), "sub_text": "96.34%" if operational else "95.29%", "kind": "green", "color": "#00A8A8"},
                {"label": "Частково виконано", "value": 41, "value_text": "41", "sub_text": "21.47%", "kind": "yellow", "color": "#F4B400"},
                {"label": "Не подано", "value": 7, "value_text": "7", "sub_text": "3.66%", "kind": "red", "color": "#FF7A45"},
                {"label": "Не виконано", "value": 24, "value_text": "24", "sub_text": "12.57%", "kind": "red", "color": "#FF7A45"},
                {"label": "Не настав час", "value": 27, "value_text": "27", "sub_text": "14.14%", "kind": "gray", "color": "#8A96A8"},
            ],
            "bars": [
                {"label": "Виконання за заходами", "value": 68.2256, "value_text": "68.2256%", "color": "#005BBB"},
                {"label": "Виконання за цілями", "value": 64.5087, "value_text": "64.5087%", "color": "#4D8DFF"},
                {"label": "Покриття моніторингом", "value": 95.8042, "value_text": "95.8042%", "color": "#00A8A8"},
                {"label": risk["fourth_label"], "value": risk["fourth_value"], "value_text": risk["fourth_text"], "color": "#118847"},
            ],
        },
        strategic_goals={
            "section": "Стратегічні цілі",
            "title": "Виконання за стратегічними цілями",
            "subtitle": f"Відсоток виконання по кожній стратегічній цілі · {period}",
            "rows": [
                {
                    "code": str(i + 1),
                    "name": LONG_GOALS[i],
                    "full_name": LONG_GOALS[i],
                    "value": value,
                    "value_text": f"{value}%",
                    "color": "#118847" if value >= 70 else ("#FF7A45" if value >= 35 else "#DC4A4A"),
                }
                for i, value in enumerate([75, 69, 71, 55, 49, 74, 48, 76])
            ],
            "empty_text": "Дані відсутні за обраними фільтрами",
        },
        risks={
            "section": risk["section"],
            "title": risk["title"],
            "subtitle": f"191 заходів у зрізі · {period}",
            "cards": risk["cards"],
            "summary_label": "Загальний висновок системи",
            "summary_text": LONG_CONCLUSION,
            "tags": [risk["tag"], "Без даних: 6 заходів"],
            "mode": risk_mode,
        },
        top5={
            "section": "Увага керівництва",
            "title": "Топ-5 проблемних заходів",
            "subtitle": f"V3 attention signals: ризик, відсутність подання, final failure або конфлікт даних · {period}",
            "rows": [
                {
                    "risk_label": ["Критичний ризик", "Високий ризик", "Високий ризик", "Середній ризик", "Середній ризик"][i],
                    "risk_color": ["#DC4A4A", "#FF7A45", "#FF7A45", "#F4B400", "#F4B400"][i],
                    "name": LONG_TOP5[i],
                    "full_name": LONG_TOP5[i],
                    "code": f"1.{i + 1}.{i + 3}",
                    "department": f"ССП {i + 1}",
                    "status": "Не виконано" if i < 3 else "Не подано",
                    "performance": 20.0 + i * 7,
                    "performance_text": f"{20 + i * 7}%",
                }
                for i in range(5)
            ],
            "empty_text": "Критичних заходів не виявлено",
        },
        finance={
            "section": "Фінансування заходів",
            "title": "Структура та обсяги фінансування",
            "subtitle": f"{period} · 191 заходів у зрізі",
            "sources_label": "Джерела фінансування",
            "groups": [
                {"label": "Державний бюджет", "count": 38, "percent": 19.9, "display": "38 (19.9%)", "color": "#005BBB"},
                {"label": "МТД / кошти партнерів", "count": 7, "percent": 3.7, "display": "7 (3.7%)", "color": "#00A8A8"},
                {"label": "Небюджетні / інші", "count": 8, "percent": 4.2, "display": "8 (4.2%)", "color": "#FF7A45"},
                {"label": "Без фінансування", "count": 140, "percent": 73.3, "display": "140 (73.3%)", "color": "#8A96A8"},
            ],
            "budget": {
                "label": "Бюджет ДБ 2026",
                "value": 141.258414,
                "value_text": "141.258414 млрд грн",
                "subtitle": "часткові дані — не всі заходи мають суми",
            },
            "kpkvk_label": "Топ КПКВК за кількістю заходів",
            "kpkvk_rows": [
                {"code": "1201030", "count": 5, "count_text": "5 заходів", "budget_text": "0.002274 млрд грн"},
                {"code": "1201010", "count": 4, "count_text": "4 заходи", "budget_text": "— млрд грн"},
                {"code": "1201350", "count": 4, "count_text": "4 заходи", "budget_text": "1.37 млрд грн"},
                {"code": "1201150", "count": 3, "count_text": "3 заходи", "budget_text": "0.208024 млрд грн"},
                {"code": "1201450", "count": 3, "count_text": "3 заходи", "budget_text": "10.72 млрд грн"},
                {"code": "1201220", "count": 2, "count_text": "2 заходи", "budget_text": "0.0665 млрд грн"},
            ],
            "kpkvk_empty_text": "КПКВК не визначено",
        },
    )
    return payload


def _pdf_reader(payload):
    pdf = build_presentation_pdf(payload)
    assert pdf is not None
    assert pdf.startswith(b"%PDF")
    return pdf, PdfReader(io.BytesIO(pdf))


def _page_text(reader, index):
    return (reader.pages[index].extract_text() or "").replace("\u00a0", " ")


def _without_marker(value):
    return str(value).replace("🔴 ", "").replace("🟡 ", "").replace("🟢 ", "")


def test_case_a_canonical_payload_and_pdf_content():
    payload = _sample_payload()
    assert tuple(slide["key"] for slide in payload["slides"]) == SLIDE_ORDER
    slides = presentation_slides_by_key(payload)

    cards = slides["key_metrics"]["cards"]
    assert [c["value"] for c in cards] == [191, 92, 182, 41, 7, 24, 27]
    assert len(slides["strategic_goals"]["rows"]) == 8
    assert len(slides["top5"]["rows"]) == 5
    assert len(slides["finance"]["kpkvk_rows"]) == 6
    assert slides["finance"]["budget"]["value"] == 141.258414

    pdf, reader = _pdf_reader(payload)
    assert len(reader.pages) == 7
    for page in reader.pages:
        assert round(float(page.mediabox.width)) == REFERENCE_WIDTH
        assert round(float(page.mediabox.height)) == REFERENCE_HEIGHT

    expected_page_text = [
        "Аналітичний дашборд результативності стратегічного плану",
        "Реалізація переважно контрольована",
        "Статистика виконання заходів",
        "Виконання за стратегічними цілями",
        "Розподіл ризиків недосягнення",
        "Топ-5 проблемних заходів",
        "Структура та обсяги фінансування",
    ]
    for idx, expected in enumerate(expected_page_text):
        assert expected in _page_text(reader, idx), (idx + 1, expected, _page_text(reader, idx))

    page3 = _page_text(reader, 2)
    for value in ("191", "92", "182", "41", "7", "24", "27", "Погоджено", "Не подано"):
        assert value in page3, value

    page4 = _page_text(reader, 3)
    for value in ("75%", "69%", "71%", "55%", "49%", "74%", "48%", "76%"):
        assert value in page4, value

    page5 = _page_text(reader, 4)
    for value in ("14", "34", "Частка з ризиком: 10%", "Без даних: 6 заходів"):
        assert value in page5, value

    page7 = _page_text(reader, 6)
    assert "141.258414 млрд грн" in page7
    for code in ("1201030", "1201010", "1201350", "1201150", "1201450", "1201220"):
        assert code in page7

    all_text = "\n".join(_page_text(reader, i) for i in range(7))
    assert "Мінекономіки · Система моніторингу стратегічного плану" not in all_text
    assert "Статуси виконання заходів" not in all_text


def test_q1_semantics_exact_and_rendered():
    payload = _sample_payload(risk_mode="q1")
    slides = presentation_slides_by_key(payload)
    risks = slides["risks"]
    assert risks["section"] == "Попередні сигнали I кварталу"
    assert risks["title"] == "Попередній прогноз без стандартної категоризації ризику"
    assert [card["label"] for card in risks["cards"]] == [
        "Сигнали уваги",
        "Сформовано попередніх прогнозів",
        "Стандартних категорій ризику",
    ]
    assert risks["cards"][2]["value"] == 0
    assert risks["tags"][0].startswith("Попередніх сигналів уваги:")
    assert slides["key_metrics"]["bars"][3]["label"] == "Середнє попереднє досягнення"

    _, reader = _pdf_reader(payload)
    page5 = _page_text(reader, 4)
    for value in (
        "Попередні сигнали I кварталу",
        "Попередній прогноз без стандартної категоризації ризику",
        "Сигнали уваги",
        "Сформовано попередніх прогнозів",
        "Стандартних категорій ризику",
        "Попередніх сигналів уваги: 12%",
    ):
        assert value in page5, value
    assert "Середнє попереднє досягнення" in _page_text(reader, 2)


def test_q4_semantics_exact_and_rendered():
    payload = _sample_payload(risk_mode="q4")
    slides = presentation_slides_by_key(payload)
    risks = slides["risks"]
    assert risks["section"] == "Підсумок року"
    assert risks["title"] == "Фактичні річні результати"
    assert [_without_marker(card["label"]) for card in risks["cards"]] == [
        "Результат не досягнуто",
        "Частково виконано",
        "Результат досягнуто",
    ]
    assert risks["tags"][0].startswith("Не досягнуто:")
    assert slides["key_metrics"]["bars"][3]["label"] == "Результатів досягнуто"

    _, reader = _pdf_reader(payload)
    page5 = _page_text(reader, 4)
    for value in (
        "Підсумок року",
        "Фактичні річні результати",
        "Результат не досягнуто",
        "Частково виконано",
        "Результат досягнуто",
        "Не досягнуто: 12.6%",
    ):
        assert value in page5, value
    assert "Результатів досягнуто" in _page_text(reader, 2)


def test_operational_semantics_filter_label_value_and_pdf_text():
    payload = _sample_payload(data_source_mode="operational")
    slides = presentation_slides_by_key(payload)
    assert payload["applied_filters"]["data_source_mode"] == "operational"
    approval = slides["key_metrics"]["cards"][2]
    assert approval["label"] == "Пройшли координатора"
    assert approval["value"] == 184
    assert approval["value_text"] == "184"

    _, reader = _pdf_reader(payload)
    page3 = _page_text(reader, 2)
    assert "Пройшли координатора" in page3
    assert "184" in page3
    assert "Погоджено" not in page3


def test_mio_legacy_pdf_runtime_smoke():
    pdf = build_legacy_presentation_pdf(
        "test",
        "period",
        [("KPI", "1")],
        "verdict",
        "low",
        [],
        [],
    )
    assert pdf is not None
    assert pdf.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) == 3


def test_dashboard_uses_one_payload_for_browser_and_pdf():
    source = (ROOT / "pages" / "2_Dashboard.py").read_text(encoding="utf-8")
    assert source.count("build_presentation_payload(") == 1
    assert "build_presentation_pdf(_presentation_payload)" in source
    assert "build_presentation_html(_presentation_payload)" in source
    assert "presentation_slides_by_key(_presentation_payload)" in source
    assert "_pdf_kpis" not in source
    assert "_pdf_figures" not in source
    assert "conclusion_text[:110]" not in source
    assert "_pres_css =" not in source

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

    mio_source = (ROOT / "pages" / "3_Оцінка_МіО.py").read_text(encoding="utf-8")
    assert "pdf_bytes = build_legacy_presentation_pdf(" in mio_source
    assert "pdf_bytes = build_presentation_pdf(" not in mio_source

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


def test_production_html_fixture_is_payload_driven():
    html = build_presentation_html(_sample_payload(), include_ui=False)
    assert html.count('data-slide-key=') == 7
    assert "Статистика виконання заходів" in html
    assert LONG_CONCLUSION in html
    assert "141.258414 млрд грн" in html


def main():
    tests = [
        test_case_a_canonical_payload_and_pdf_content,
        test_q1_semantics_exact_and_rendered,
        test_q4_semantics_exact_and_rendered,
        test_operational_semantics_filter_label_value_and_pdf_text,
        test_mio_legacy_pdf_runtime_smoke,
        test_dashboard_uses_one_payload_for_browser_and_pdf,
        test_production_html_fixture_is_payload_driven,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"PASS {len(tests)} presentation/PDF test groups")


if __name__ == "__main__":
    main()
