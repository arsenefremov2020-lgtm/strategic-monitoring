"""Pure presentation helpers for the Measure Card on Dashboard execution v3.

This module deliberately does *not* calculate execution, attainment, trajectory,
forecast, pace or risk.  It consumes the canonical fields produced by
``core.dashboard_execution`` + ``core.dashboard_risk`` and turns them into a
small deterministic view model for ``pages/4_Картка_заходу.py``.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

import pandas as pd

from core.dashboard_execution import to_number
from core.dashboard_periods import clean, period_number, quarter_to_roman
from core.dashboard_risk import RISK_COLORS

BLUE = "#005BBB"
GRAY = "#8A96A8"
RED = "#DC4A4A"
YELLOW = "#F4B400"
ORANGE = "#FF7A45"
GREEN = "#118847"




def _row_missing(row: Mapping[str, Any] | None) -> bool:
    if row is None:
        return True
    try:
        return len(row) == 0
    except TypeError:
        return False


def _bool(row: Mapping[str, Any], key: str, default: bool = False) -> bool:
    value = row.get(key, default)
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return bool(value)


def _value(row: Mapping[str, Any], key: str) -> Any:
    value = row.get(key)
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _fmt_number(value: Any, digits: int = 1) -> str:
    number = to_number(value)
    if number is None:
        return "—"
    if abs(number - round(number)) < 1e-9:
        return f"{int(round(number)):,}".replace(",", " ")
    text = f"{number:,.{digits}f}".replace(",", " ")
    return text.rstrip("0").rstrip(".")


def _fmt_pct(value: Any, digits: int = 1) -> str:
    number = to_number(value)
    return "—" if number is None else f"{_fmt_number(number, digits)}%"


def _fmt_signed(value: Any, digits: int = 1) -> str:
    number = to_number(value)
    if number is None:
        return "—"
    sign = "+" if number > 0 else ""
    return f"{sign}{_fmt_number(number, digits)}"


def _quarter_name(value: Any) -> str:
    return quarter_to_roman(value) or clean(value) or "—"


def is_obsolete(row: Mapping[str, Any]) -> bool:
    return clean(row.get("status")) == "Втратило актуальність" or clean(row.get("effective_result_status")) == "Втратило актуальність"


def gauge_state(row: Mapping[str, Any] | None, *, future: bool = False) -> dict[str, Any]:
    """Return gauge display state using *only* canonical v3 analytical fields."""
    if future or _row_missing(row):
        return {"value": None, "color": GRAY, "state": "not_assessed", "label": "Не оцінюється"}

    state = clean(row.get("period_state"))
    q = _quarter_name(row.get("quarter"))
    status = clean(row.get("status"))
    effective_status = clean(row.get("effective_result_status"))
    execution = to_number(row.get("execution_score"))

    if not _bool(row, "monitoring_conducted", True) or state in {"unknown_period", "future"} or is_obsolete(row):
        return {"value": None, "color": GRAY, "state": "not_assessed", "label": status or "Не оцінюється"}

    if _bool(row, "management_zero_due_to_missing_data") or _bool(row, "final_missing_result"):
        return {"value": 0.0, "color": RED, "state": "management_alert", "label": "Потребує уваги"}

    if _bool(row, "missing_required_submission"):
        # A stale carried result is execution evidence, not a new forecast-risk observation.
        return {"value": execution, "color": BLUE, "state": "stale", "label": "Дані не оновлено"}

    if _bool(row, "result_achieved"):
        return {"value": execution, "color": GREEN, "state": "achieved", "label": "Результат досягнуто"}

    # Q4 and ended rows are final actual outcomes, never predictive risk states.
    if q == "IV" or state == "ended" or clean(row.get("forecast_kind")) == "final":
        if _bool(row, "numeric"):
            return {"value": execution, "color": RED, "state": "final_underachievement", "label": "Річний результат не досягнуто"}
        if effective_status == "Частково виконано":
            return {"value": execution, "color": YELLOW, "state": "final_partial", "label": "Частково виконано"}
        if effective_status in {"Не виконано", "Не подано"}:
            return {"value": execution, "color": RED, "state": "final_underachievement", "label": effective_status}
        return {"value": execution, "color": BLUE, "state": "final", "label": effective_status or "Фінальний результат"}

    if q == "I":
        return {"value": execution, "color": BLUE, "state": "preliminary", "label": "Попередня оцінка"}

    # Q2/Q3 qualitative execution fallback is descriptive only on the Card.
    # Shared risk fields may carry a management signal for Dashboard aggregation,
    # but the Measure Card does not present it as a forecast-risk category.
    if not _bool(row, "numeric") and not _bool(row, "yes_no"):
        return {"value": execution, "color": BLUE, "state": "qualitative", "label": effective_status or status or "Якісний результат"}

    risk = clean(row.get("risk_level"))
    if risk:
        return {"value": execution, "color": RISK_COLORS.get(risk, BLUE), "state": "risk", "label": risk}

    return {"value": execution, "color": BLUE, "state": "valid", "label": effective_status or status or "Оцінено"}


def fact_label(row: Mapping[str, Any]) -> str:
    if _bool(row, "management_zero_due_to_missing_data") or _bool(row, "final_missing_result"):
        return "Факт — відсутній"
    if _bool(row, "missing_required_submission") and clean(row.get("carry_forward_kind")) == "active_previous_result":
        return "Останній підтверджений факт"
    if clean(row.get("carry_forward_kind")) == "ended_final" or clean(row.get("period_state")) == "ended":
        return "Фінальний / останній підтверджений факт"
    q = _quarter_name(row.get("quarter"))
    return f"Факт за {q} квартал"


def _fact_display(row: Mapping[str, Any]) -> str:
    if _bool(row, "management_zero_due_to_missing_data") or _bool(row, "final_missing_result"):
        return "—"
    actual = _value(row, "actual")
    if actual is None or clean(actual) == "":
        return "—"
    number = to_number(actual)
    return _fmt_number(number) if number is not None else clean(actual)


def headline_kpis(row: Mapping[str, Any] | None, *, future: bool = False) -> list[dict[str, str]]:
    """Compact scenario-aware headline metrics built from canonical v3 fields."""
    if future:
        return [
            {"label": "Річний план", "value": _fact_or_text(row.get("annual_target")) if not _row_missing(row) else "—"},
            {"label": "Факт", "value": "—"},
        ]
    if _row_missing(row):
        return [
            {"label": "Річний план", "value": "—"},
            {"label": "Факт", "value": "—"},
        ]

    q = _quarter_name(row.get("quarter"))
    numeric = _bool(row, "numeric")
    yes_no = _bool(row, "yes_no")
    qualitative = not numeric and not yes_no
    execution_item = {"label": "Виконання річного плану", "value": _fmt_pct(row.get("execution_score"))}

    # Standard numeric Q2/Q3 trajectory: exactly four analytical KPIs.
    # Execution itself is already the gauge value and is intentionally not duplicated.
    if (
        numeric and q in {"II", "III"}
        and not _bool(row, "missing_required_submission")
        and to_number(row.get("pace_sufficiency_pct")) is not None
        and to_number(row.get("forecast_attainment_pct")) is not None
    ):
        return [
            {"label": "Факт / річний план", "value": f"{_fact_display(row)} / {_fact_or_text(row.get('annual_target'))}"},
            {"label": "Достатність темпу", "value": f"{_fmt_pct(row.get('pace_sufficiency_pct'))} від необхідного"},
            {"label": "Прогноз", "value": f"{_fmt_pct(row.get('forecast_attainment_pct'))} річного плану"},
            {"label": "Ризик", "value": clean(row.get("risk_level")) or "Не оцінюється"},
        ]

    # Q1 is preliminary and must never present a standard Low/Medium/High/Critical KPI.
    if numeric and q == "I" and not _bool(row, "missing_required_submission"):
        return [
            {"label": "Факт / річний план", "value": f"{_fact_display(row)} / {_fact_or_text(row.get('annual_target'))}"},
            execution_item,
            {"label": "Попередній прогноз", "value": f"{_fmt_pct(row.get('forecast_attainment_pct'))} річного плану" if to_number(row.get("forecast_attainment_pct")) is not None else "—"},
            {"label": "Оцінка", "value": "Попередня"},
        ]

    items = [
        {"label": "Річний план", "value": _fact_or_text(row.get("annual_target"))},
        {"label": fact_label(row), "value": _fact_display(row)},
        execution_item,
    ]

    if _bool(row, "missing_required_submission"):
        source_q = _quarter_name(row.get("source_quarter"))
        extra = "Підтверджених даних немає" if _bool(row, "management_zero_due_to_missing_data") else f"Джерело: {source_q} квартал"
        items.append({"label": "Актуальність даних", "value": extra})
        return items[:4]

    if q == "IV" or clean(row.get("forecast_kind")) == "final" or clean(row.get("period_state")) == "ended":
        final = clean(row.get("final_outcome"))
        if final:
            items.append({"label": "Підсумок", "value": final})
    elif not qualitative:
        risk = clean(row.get("risk_level"))
        if risk:
            items.append({"label": "Ризик", "value": risk})

    raw = to_number(row.get("raw_attainment_pct"))
    if raw is not None and raw > 100 and len(items) < 4:
        items.append({"label": "Фактичне досягнення", "value": _fmt_pct(raw)})
    return items[:4]


def _fact_or_text(value: Any) -> str:
    if value is None or clean(value) == "":
        return "—"
    number = to_number(value)
    return _fmt_number(number) if number is not None else clean(value)


def build_measure_conclusion(row: Mapping[str, Any] | None, *, future: bool = False) -> str:
    """Deterministic 2–4 sentence Card conclusion, based only on shared v3 fields."""
    if future:
        return "Станом на обраний період захід ще не розпочався. Оцінка виконання не формується."
    if _row_missing(row):
        return "Для обраного періоду немає аналітичного зрізу. Оцінка виконання не формується."

    if not _bool(row, "monitoring_conducted", True):
        return "Моніторинг у цьому періоді не проводився. Оцінка виконання за цей квартал не формується."
    if clean(row.get("period_state")) == "unknown_period":
        return "Не вдалося однозначно визначити період застосовності заходу. До уточнення строків оцінка виконання не формується."
    if is_obsolete(row):
        return "Захід має статус «Втратило актуальність». Оцінка виконання та прогнозна траєкторія для цього зрізу не формуються."

    execution = _fmt_pct(row.get("execution_score"))
    q = _quarter_name(row.get("quarter"))
    effective_status = clean(row.get("effective_result_status")) or clean(row.get("status"))

    if _bool(row, "final_missing_result"):
        return (
            "Строк реалізації заходу завершився, однак за ним відсутні будь-які підтверджені моніторингові дані. "
            "Для управлінської оцінки враховано 0%. Прогнозний ризик не розраховується."
        )

    if _bool(row, "missing_required_submission"):
        if _bool(row, "management_zero_due_to_missing_data"):
            return (
                "За заходом відсутні підтверджені дані про фактичне виконання за поточний рік. "
                "Для управлінської оцінки враховано 0%. Прогнозна траєкторія не оцінюється."
            )
        source_q = _quarter_name(row.get("source_quarter"))
        return (
            f"Виконання річного плану за останніми підтвердженими даними становить {execution}. "
            f"Нові відомості за {q} квартал не подано; використано результат {source_q} кварталу. "
            f"Прогноз і достатність темпу за {q} квартал не розраховуються."
        )

    state = clean(row.get("period_state"))
    if state == "ended" or clean(row.get("carry_forward_kind")) == "ended_final":
        sentence = "Захід завершено. У поточному зрізі використовується останній підтверджений результат."
        if _bool(row, "result_achieved"):
            return sentence + " Річний результат досягнуто."
        if _bool(row, "numeric") and to_number(row.get("raw_attainment_pct")) is not None:
            return sentence + f" Фактичне досягнення становить {_fmt_pct(row.get('raw_attainment_pct'))} річного плану."
        return sentence + (f" Зафіксований статус результату — «{effective_status}»." if effective_status else "")

    raw = to_number(row.get("raw_attainment_pct"))
    if _bool(row, "result_achieved"):
        if raw is not None and raw > 100:
            return f"Річний результат уже досягнуто. Річний план перевиконано на {_fmt_pct(raw - 100)}."
        if _bool(row, "yes_no") and q != "IV":
            return "Річний результат уже досягнуто. Результат досягнуто достроково."
        return "Річний результат уже досягнуто."

    if _bool(row, "yes_no"):
        if clean(row.get("forecast_kind")) == "final":
            return "Строк виконання настав, а результат не досягнуто. Це фінальний стан, а не прогнозний ризик."
        warning = clean(row.get("deadline_warning"))
        if warning:
            if q == "I":
                return warning + " Оцінка першого кварталу є попередньою; стандартна категорія ризику не присвоюється."
            risk = clean(row.get("risk_level"))
            return warning + (f" Поточний сигнал — {risk.lower()}." if risk else "")
        explanation = clean(row.get("risk_explanation"))
        if "строк виконання не визначено" in explanation.casefold():
            return "Результат ще не досягнуто. Строк виконання не визначено."
        if "строк виконання ще не настав" in explanation.casefold():
            return "Результат ще не досягнуто; до встановленого строку виконання залишається більше одного кварталу."
        return "Результат ще не досягнуто; встановлений строк виконання ще не настав."

    if not _bool(row, "numeric"):
        if q in {"I", "II", "III"}:
            return (
                f"Захід має статус «{effective_status or '—'}». "
                "Числова оцінка траєкторії та прогнозного ризику для якісного результату не застосовується."
            )
        return f"Захід має статус «{effective_status or '—'}». Це фінальний якісний результат за обраний період."

    if q == "IV":
        return (
            f"За підсумками року досягнуто {_fmt_pct(row.get('raw_attainment_pct'))} річного планового значення. "
            "Річний результат не досягнуто повністю; прогнозний ризик у IV кварталі не застосовується."
        )

    if q == "I":
        forecast = to_number(row.get("forecast_attainment_pct"))
        text = f"Станом на I квартал виконання річного плану становить {execution}."
        if forecast is not None:
            text += f" Попередній прогноз досягнення річного плану — {_fmt_pct(forecast)}."
        return text + " Оцінка є попередньою, оскільки базується на одному квартальному спостереженні."

    if clean(row.get("forecast_kind")) == "insufficient_history":
        return (
            f"Станом на {q} квартал виконання річного плану становить {execution}. "
            "Недостатньо квартальної історії для оцінки траєкторії; прогноз, темп і стандартний ризик не розраховуються."
        )

    increment = to_number(row.get("current_increment"))
    pace = to_number(row.get("pace_sufficiency_pct"))
    forecast = to_number(row.get("forecast_attainment_pct"))
    risk = clean(row.get("risk_level"))

    first = f"Станом на {q} квартал виконання річного плану становить {execution}."
    if _bool(row, "negative_trajectory") or (increment is not None and increment < 0):
        second = "Порівняно з попереднім кварталом зафіксовано зниження фактичного значення."
    elif increment is not None and abs(increment) < 1e-12:
        second = "Фактичний результат порівняно з попереднім кварталом не змінився. За наявного залишку до річного плану така динаміка є недостатньою для його досягнення без прискорення виконання."
    elif increment is not None and increment > 0 and pace is not None and pace < 100:
        second = "Фактичний результат зріс порівняно з попереднім кварталом, однак поточний приріст є недостатнім для досягнення річного плану без прискорення виконання."
    elif increment is not None and increment > 0:
        second = "Фактичний результат зріс порівняно з попереднім кварталом; поточний темп відповідає або перевищує необхідний."
    else:
        second = "Квартальна траєкторія сформована на основі підтверджених спостережень."

    third_parts = []
    if forecast is not None:
        third_parts.append(f"прогнозоване досягнення — {_fmt_pct(forecast)}")
    if risk:
        third_parts.append(risk.lower())
    third = ("; ".join(third_parts).capitalize() + ".") if third_parts else ""
    return " ".join(part for part in [first, second, third] if part)


def warning_message(row: Mapping[str, Any] | None) -> str:
    if _row_missing(row):
        return ""
    if _bool(row, "management_zero_due_to_missing_data"):
        return "За заходом відсутні будь-які підтверджені дані про виконання за поточний рік. Для управлінської оцінки враховано 0%."
    if _bool(row, "missing_required_submission"):
        q = _quarter_name(row.get("quarter")); source_q = _quarter_name(row.get("source_quarter"))
        return f"Дані не оновлено за {q} квартал. Використано останній підтверджений результат — {source_q} квартал."
    if _bool(row, "final_missing_result"):
        return "Строк реалізації заходу завершився, але підтверджені моніторингові дані відсутні. Для управлінської оцінки враховано 0%."
    return ""


def quarter_card_view(row: Mapping[str, Any] | None, *, quarter: Any, future_relative: bool = False, future_measure: bool = False) -> dict[str, Any]:
    q = _quarter_name(quarter)
    if future_relative:
        return {"quarter": q, "value": "—", "lines": ["Майбутній період відносно обраного зрізу"], "badge": "Не оцінюється", "color": GRAY, "actual_observation": None}
    if future_measure:
        return {"quarter": q, "value": "—", "lines": ["Захід ще не розпочався"], "badge": "Не настав час", "color": GRAY, "actual_observation": None}
    if _row_missing(row):
        return {"quarter": q, "value": "—", "lines": ["Аналітичний зріз відсутній"], "badge": "Не оцінюється", "color": GRAY, "actual_observation": None}

    gauge = gauge_state(row)
    if not _bool(row, "monitoring_conducted", True):
        return {"quarter": q, "value": "—", "lines": ["Моніторинг не проводився"], "badge": "Не оцінюється", "color": GRAY, "actual_observation": None}
    if is_obsolete(row):
        return {"quarter": q, "value": "—", "lines": ["Захід втратив актуальність"], "badge": "Втратило актуальність", "color": GRAY, "actual_observation": None}
    if _bool(row, "management_zero_due_to_missing_data"):
        return {"quarter": q, "value": "0%", "lines": ["0% для управлінської оцінки", "Підтверджені дані відсутні"], "badge": "Не подано", "color": RED, "actual_observation": None}
    if _bool(row, "final_missing_result"):
        return {"quarter": q, "value": "0%", "lines": ["Фінальний результат відсутній", "0% для управлінської оцінки"], "badge": "Потребує уваги", "color": RED, "actual_observation": None}

    actual_text = _fact_display(row)
    lines: list[str] = []
    if _bool(row, "missing_required_submission"):
        lines.append(f"{_fmt_pct(row.get('execution_score'))} за останніми підтвердженими даними")
        lines.append("Нові дані не подано")
        lines.append(f"Джерело: {_quarter_name(row.get('source_quarter'))} квартал")
    elif clean(row.get("carry_forward_kind")) == "ended_final" or clean(row.get("period_state")) == "ended":
        lines.append("Фінальний результат")
        if clean(row.get("source_quarter")):
            lines.append(f"Джерело: {_quarter_name(row.get('source_quarter'))} квартал")
    else:
        raw = to_number(row.get("raw_attainment_pct"))
        if raw is not None:
            lines.append(f"{_fmt_pct(raw)} річного плану")
        increment = to_number(row.get("current_increment"))
        if increment is not None:
            lines.append(f"{_fmt_signed(increment)} до попереднього кварталу")

    effective = clean(row.get("effective_result_status"))
    reporting = clean(row.get("status"))
    if reporting and reporting != effective:
        lines.append(f"Поточний статус: {reporting}; результат-джерело: {effective or '—'}")

    return {
        "quarter": q,
        "value": actual_text,
        "lines": lines,
        "badge": reporting or gauge["label"],
        "color": gauge["color"],
        "actual_observation": actual_observation(row),
    }


def actual_observation(row: Mapping[str, Any] | None) -> float | None:
    """Numeric chart point only for a real current-quarter observation."""
    if _row_missing(row):
        return None
    if not _bool(row, "monitoring_conducted", True):
        return None
    if not _bool(row, "submitted_current_period", _bool(row, "submitted")):
        return None
    if _bool(row, "missing_required_submission") or not _bool(row, "numeric") or is_obsolete(row):
        return None
    return to_number(row.get("actual"))


def build_card_view(row: Mapping[str, Any] | None, *, future: bool = False) -> dict[str, Any]:
    gauge = gauge_state(row, future=future)
    return {
        "gauge": gauge,
        "headline_kpis": headline_kpis(row, future=future),
        "conclusion": build_measure_conclusion(row, future=future),
        "warning": warning_message(row),
    }


def selected_period_is_after(candidate_year: int, candidate_quarter: Any, selected_year: int, selected_quarter: Any) -> bool:
    return period_number(candidate_year, candidate_quarter) > period_number(selected_year, selected_quarter)
