from __future__ import annotations

import math
from typing import Any

from .config import DELTA_LANGUAGE_BANDS


def is_number(value: Any) -> bool:
    try:
        return value is not None and not math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def fmt_number(value: Any, digits: int = 1) -> str:
    if not is_number(value):
        return "н/д"
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.{digits}f}".replace(".", ",")


def fmt_pct(value: Any, digits: int = 1) -> str:
    return "н/д" if not is_number(value) else f"{fmt_number(value, digits)}%"


def fmt_delta(value: Any, digits: int = 1, signed: bool = True) -> str:
    if not is_number(value):
        return "н/д"
    number = float(value)
    prefix = "+" if signed and number > 0 else ""
    return f"{prefix}{fmt_number(number, digits)} в.п."


def fmt_count(value: Any) -> str:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return "0"


def fmt_period(year: Any, quarter: Any) -> str:
    return f"{year} {quarter}".strip()


def intensity_from_delta(delta: Any) -> str:
    if not is_number(delta):
        return ""
    value = abs(float(delta))
    if value >= DELTA_LANGUAGE_BANDS["strong"]:
        return "суттєво"
    if value >= DELTA_LANGUAGE_BANDS["moderate"]:
        return "помітно"
    if value >= DELTA_LANGUAGE_BANDS["small"]:
        return "незначно"
    return "мінімально"


def join_uk(items: list[str], limit: int | None = None) -> str:
    clean = [str(x).strip() for x in items if str(x).strip()]
    if limit is not None:
        clean = clean[:limit]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    if len(clean) == 2:
        return f"{clean[0]} та {clean[1]}"
    return ", ".join(clean[:-1]) + f" та {clean[-1]}"
