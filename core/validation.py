"""Валідація фактичних значень моніторингу DEMO 1.9."""

from __future__ import annotations

import re
from typing import Any

from core.errors import log_cosmetic_error

YES_VALUES = {"так", "yes", "true", "1", "+"}
NO_VALUES = {"ні", "нi", "no", "false", "0", "-"}
NA_VALUES = {"", "н.д.", "нд", "nan", "none", "-", "—"}


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
