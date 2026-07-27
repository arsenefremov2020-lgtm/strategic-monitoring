"""Валідація фактичних значень моніторингу DEMO 1.9."""

from __future__ import annotations

import re
from typing import Any, Iterable

from core.errors import log_cosmetic_error
from core.operational import target_met

YES_VALUES = {"так", "yes", "true", "1", "+"}
NO_VALUES = {"ні", "нi", "no", "false", "0", "-"}
NA_VALUES = {"", "н.д.", "нд", "nan", "none", "-", "—"}
X_VALUES = {"x", "х", "×"}


def text(value: Any) -> str:
    if value is None:
        return ""
    try:
        # pandas NA safe enough without importing pandas
        if str(value) == "nan":
            return ""
    except Exception as exc:
        log_cosmetic_error("Нормалізація значення у validation", exc)
    return str(value).strip()


def normalized_unit(unit: Any) -> str:
    return text(unit).lower().replace(" ", "")


def is_yes_no_unit(unit: Any) -> bool:
    u = normalized_unit(unit)
    return u in {"так/ні", "так/нi", "так-ні", "так-нi", "такні", "такнi"} or "так/ні" in text(unit).lower()


def is_numeric_unit(unit: Any) -> bool:
    if is_yes_no_unit(unit):
        return False
    u = normalized_unit(unit)
    if not u:
        return False
    # Найпоширеніші числові одиниці у матриці; текстові описи не блокуємо.
    numeric_markers = [
        "%", "грн", "млн", "млрд", "тис", "од", "шт", "кільк", "осіб", "га",
        "км", "м2", "кв.м", "бал", "днів", "років", "тон", "т.", "usd", "eur",
    ]
    return any(marker in u for marker in numeric_markers)


def parse_number(value: Any) -> float | None:
    s = text(value)
    if s.lower().replace(" ", "") in NA_VALUES:
        return None
    s = s.replace("\u00a0", " ").replace(" ", "")
    s = s.replace(",", ".")
    # лишаємо перше число, щоб "12,5 %" теж читалось
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def quarter_number(value: Any) -> int | None:
    """Нормалізує I–IV / Q1–Q4 / 1–4 до номера кварталу."""
    raw = text(value).upper().replace("І", "I").replace("Ї", "I")
    raw = raw.replace("КВАРТАЛ", "").replace("КВ.", "").replace("Q", "")
    raw = raw.replace(".", "").strip()
    mapping = {"I": 1, "II": 2, "III": 3, "IV": 4}
    if raw in mapping:
        return mapping[raw]
    match = re.search(r"[1-4]", raw)
    return int(match.group(0)) if match else None


def _record_rows(records):
    if records is None:
        return []
    if hasattr(records, "iterrows"):
        return (row for _, row in records.iterrows())
    if isinstance(records, dict):
        return iter([records])
    try:
        return iter(records)
    except TypeError:
        return []


def _record_get(record, key: str, default: Any = "") -> Any:
    if hasattr(record, "get"):
        return record.get(key, default)
    return default


def _code_key(value: Any) -> str:
    return text(value).strip().rstrip(".").casefold()


def _year_key(value: Any) -> str:
    match = re.search(r"20\d{2}", text(value))
    return match.group(0) if match else text(value)


def _department_key(value: Any) -> str:
    raw = text(value).casefold()
    match = re.search(r"\d+", raw)
    return match.group(0) if match else raw


def previous_quarter_fact_value(
    records,
    *,
    code: Any,
    year: Any,
    quarter: Any,
    department: Any = "",
    object_kind: Any = "measure",
) -> str:
    """Останній поданий факт безпосередньо попереднього кварталу того ж року."""
    current_quarter = quarter_number(quarter)
    if current_quarter is None or current_quarter <= 1:
        return ""

    wanted_code = _code_key(code)
    wanted_year = _year_key(year)
    wanted_department = _department_key(department)
    wanted_kind = text(object_kind).casefold() or "measure"
    previous_quarter = current_quarter - 1
    best_value = ""
    best_key = ("", -1)

    for record in _record_rows(records):
        row_kind = text(_record_get(record, "object_kind")).casefold() or "measure"
        if wanted_kind != "measure" or row_kind != "measure":
            continue
        if _code_key(_record_get(record, "strat_code")) != wanted_code:
            continue
        if _year_key(_record_get(record, "year")) != wanted_year:
            continue
        if quarter_number(_record_get(record, "quarter")) != previous_quarter:
            continue
        if wanted_department and _department_key(_record_get(record, "department")) != wanted_department:
            continue
        if text(_record_get(record, "approval_status")) == "Відкликано":
            continue

        value = text(_record_get(record, "numeric_value")) or text(
            _record_get(record, "value_text")
        )
        if parse_number(value) is None:
            continue
        timestamp = text(_record_get(record, "updated_at")) or text(
            _record_get(record, "submitted_at")
        )
        try:
            row_id = int(float(text(_record_get(record, "id")) or 0))
        except (TypeError, ValueError):
            row_id = 0
        candidate_key = (timestamp, row_id)
        if candidate_key >= best_key:
            best_key = candidate_key
            best_value = value

    return best_value


def cumulative_quarter_decrease_error(
    records,
    *,
    code: Any,
    year: Any,
    quarter: Any,
    value: Any,
    progress_text: Any,
    unit: Any,
    department: Any = "",
    object_kind: Any = "measure",
) -> str:
    """М'яке правило накопичувального факту: зменшення потребує пояснення."""
    if (text(object_kind).casefold() or "measure") != "measure":
        return ""
    if not is_numeric_unit(unit) or is_x_value(value):
        return ""

    current_number = parse_number(value)
    if current_number is None:
        return ""
    previous_value = previous_quarter_fact_value(
        records,
        code=code,
        year=year,
        quarter=quarter,
        department=department,
        object_kind="measure",
    )
    previous_number = parse_number(previous_value)
    if previous_number is None or current_number >= previous_number:
        return ""
    if text(progress_text):
        return ""

    return (
        f"фактичне значення «{text(value)}» менше за значення попереднього "
        f"кварталу «{text(previous_value)}». При зменшенні показника обов’язково "
        "вкажіть причину в полі «Опис прогресу»"
    )


def is_x_value(value: Any) -> bool:
    """True для латинського/кириличного маркера орієнтира «х»."""
    return text(value).lower().replace(" ", "") in X_VALUES


def first_future_target(future_targets: Iterable[Any] | None) -> str:
    """Перший наступний змістовний орієнтир, крім порожнього/«х»."""
    for candidate in future_targets or []:
        candidate_text = text(candidate)
        if not candidate_text or candidate_text.lower().replace(" ", "") in NA_VALUES:
            continue
        if is_x_value(candidate_text):
            continue
        return candidate_text
    return ""


def validate_fact_value(value: Any, unit: Any) -> tuple[bool, str]:
    """Перевірка факту: так/ні для бінарних, число для числових одиниць."""
    s = text(value)
    if not s:
        return False, "фактичне значення не заповнено"
    if is_yes_no_unit(unit):
        low = s.lower().strip()
        if low in YES_VALUES or low in NO_VALUES:
            return True, ""
        return False, "для показника типу так/ні у факті можна вказати лише «так» або «ні»"
    if is_numeric_unit(unit):
        if parse_number(s) is None:
            return False, "для числового показника у факті можна вказати лише число"
    return True, ""


def validate_fact_value_for_target(
    value: Any,
    unit: Any,
    target: Any,
    future_targets: Iterable[Any] | None = None,
) -> tuple[bool, str]:
    """Валідація факту з окремим правилом для річного орієнтира «х».

    Для орієнтира «х» дозволено саме «х» або значення типу, який задає
    перший наступний змістовний річний орієнтир цього заходу:
    число для числового орієнтира; «так»/«ні» для бінарного.
    """
    if not is_x_value(target):
        return validate_fact_value(value, unit)

    value_text = text(value)
    if not value_text:
        return False, "фактичне значення не заповнено"
    if is_x_value(value_text):
        return True, ""

    next_target = first_future_target(future_targets)
    next_target_low = next_target.lower().strip()

    if not next_target:
        return False, (
            "для орієнтира «х» без наступного змістовного річного орієнтира "
            "можна вказати лише «х»"
        )

    if parse_number(next_target) is not None:
        if parse_number(value_text) is None:
            return False, "для орієнтира «х» у цьому заході можна вказати «х» або числове значення"
        return True, ""

    if next_target_low in YES_VALUES or next_target_low in NO_VALUES:
        if value_text.lower().strip() in (YES_VALUES | NO_VALUES):
            return True, ""
        return False, "для орієнтира «х» у показнику типу так/ні можна вказати лише «х», «так» або «ні»"

    # Якщо тип наступного орієнтира не вдалося надійно визначити,
    # не вигадуємо новий формат і блокуємо неоднозначне значення.
    return False, (
        "для орієнтира «х» не вдалося визначити допустимий формат "
        "за наступними річними орієнтирами; вкажіть «х»"
    )


def value_reaches_target(value: Any, target: Any, unit: Any, direction: str = "up") -> bool | None:
    """True/False, якщо можна порівняти факт із ціллю; None, якщо не можна."""
    if is_yes_no_unit(unit):
        v = text(value).lower()
        t = text(target).lower()
        if not t or t in NA_VALUES:
            return None
        if t in YES_VALUES:
            return v in YES_VALUES
        if t in NO_VALUES:
            return v in NO_VALUES
        return None
    v_num = parse_number(value)
    t_num = parse_number(target)
    if v_num is None or t_num is None:
        return None
    if direction == "down":
        return v_num <= t_num
    return v_num >= t_num


def status_completion_warning(status: Any, value: Any, target: Any, unit: Any, code: str = "") -> str:
    """Помилка, якщо статус «Виконано», але факт не досягає цілі."""
    if text(status) != "Виконано":
        return ""
    reached = value_reaches_target(value, target, unit)
    if reached is False:
        prefix = f"У заході/індикаторі {code} " if code else ""
        return prefix + "статус «Виконано» не відповідає фактичному значенню відносно планового орієнтира."
    return ""


def status_value_conflict(
    status: Any,
    value: Any,
    target: Any,
    unit: Any,
    code: str = "",
    future_targets: Iterable[Any] | None = None,
) -> str:
    """Жорстко блокує лише однозначні суперечності «Виконано/Не виконано».

    Для поточного орієнтира «х» порівняння виконується з першим наступним
    змістовним орієнтиром. Саме подане значення «х» не є однозначно
    порівнюваним, тому не блокується цією перевіркою.
    """
    status_text = text(status)
    if status_text not in {"Виконано", "Не виконано"}:
        return ""
    if is_x_value(value):
        return ""

    effective_target = first_future_target(future_targets) if is_x_value(target) else text(target)
    if not effective_target or is_x_value(effective_target):
        return ""

    value_text = text(value)
    value_low = value_text.lower().strip()
    target_low = effective_target.lower().strip()

    numeric_comparable = parse_number(value_text) is not None and parse_number(effective_target) is not None
    yes_no_comparable = (
        is_yes_no_unit(unit)
        and value_low in (YES_VALUES | NO_VALUES)
    ) or (
        value_low in (YES_VALUES | NO_VALUES)
        and target_low in (YES_VALUES | NO_VALUES)
    )

    if not numeric_comparable and not yes_no_comparable:
        return ""

    reached = target_met(value_text, effective_target)
    code_label = f"У заході {code}: " if code else ""
    target_note = (
        f" (для орієнтира «х» використано наступний орієнтир «{effective_target}»)"
        if is_x_value(target)
        else ""
    )

    if status_text == "Виконано" and not reached:
        return (
            f"{code_label}обрано статус «Виконано», але подане значення «{value_text}» "
            f"не досягає цільового орієнтира «{effective_target}»{target_note}."
        )
    if status_text == "Не виконано" and reached:
        return (
            f"{code_label}обрано статус «Не виконано», але подане значення «{value_text}» "
            f"досягає або перевищує цільовий орієнтир «{effective_target}»{target_note}."
        )
    return ""
