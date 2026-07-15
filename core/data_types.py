"""Conversion helpers for typed monitoring database fields.

The database stores years and quarters as integers, dates as ISO dates, and
actual values in separate numeric/text columns. The interface continues to use
Roman quarters, Ukrainian dates and one visible "Фактичне значення" field.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

_ROMAN_BY_QUARTER = {1: "I", 2: "II", 3: "III", 4: "IV"}
_QUARTER_BY_TEXT = {
    "I": 1,
    "II": 2,
    "ІІ": 2,
    "III": 3,
    "IV": 4,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
}
_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y")
_NUMERIC_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$")
_PERIOD_RE = re.compile(
    r"(?P<quarter>[1-4]|I{1,3}|IV|І{1,3}|ІV)\s*(?:-?й\s*)?квартал[^0-9]*(?P<year>20\d{2})",
    re.IGNORECASE,
)


def clean_scalar(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null", "nat"} else text


def year_to_db(value: Any) -> int | None:
    text = clean_scalar(value)
    if not text:
        return None
    match = re.search(r"20\d{2}", text)
    if not match:
        raise ValueError(f"Некоректний рік: {text}")
    return int(match.group(0))


def year_to_display(value: Any) -> str:
    try:
        result = year_to_db(value)
    except ValueError:
        return clean_scalar(value)
    return "" if result is None else str(result)


def quarter_to_db(value: Any) -> int | None:
    if isinstance(value, bool):
        raise ValueError(f"Некоректний квартал: {value}")
    if isinstance(value, int) and 1 <= value <= 4:
        return value
    if isinstance(value, float) and not math.isnan(value) and value.is_integer() and 1 <= value <= 4:
        return int(value)

    text = clean_scalar(value).upper()
    if not text:
        return None
    text = text.replace("КВАРТАЛ", "").replace("КВ.", "").replace(".", "").strip()
    text = text.replace("І", "I").replace("Ї", "I")
    if text in _QUARTER_BY_TEXT:
        return _QUARTER_BY_TEXT[text]
    match = re.search(r"[1-4]", text)
    if match:
        return int(match.group(0))
    raise ValueError(f"Некоректний квартал: {clean_scalar(value)}")


def quarter_to_display(value: Any) -> str:
    try:
        number = quarter_to_db(value)
    except ValueError:
        return clean_scalar(value)
    return "" if number is None else _ROMAN_BY_QUARTER[number]


def _quarter_dates(text: str) -> list[tuple[date, date]]:
    normalised = text.replace("\u00a0", " ").replace("\n", " ")
    result: list[tuple[date, date]] = []
    for match in _PERIOD_RE.finditer(normalised):
        quarter = quarter_to_db(match.group("quarter"))
        year = int(match.group("year"))
        if quarter is None:
            continue
        start_month = (quarter - 1) * 3 + 1
        end_month = quarter * 3
        if end_month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, end_month + 1, 1)
        end = next_month - timedelta(days=1)
        result.append((date(year, start_month, 1), end))
    return result


def date_to_db(value: Any, *, boundary: str = "start") -> str | None:
    """Convert a UI/date/quarter-period value to ISO ``YYYY-MM-DD``.

    For source cells containing more than one quarter, the earliest start or
    latest end is used. This preserves the full stated interval instead of
    silently choosing an arbitrary line.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()

    text = clean_scalar(value)
    if not text:
        return None

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    periods = _quarter_dates(text)
    if periods:
        if boundary == "end":
            return max(period[1] for period in periods).isoformat()
        return min(period[0] for period in periods).isoformat()

    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if not pd.isna(parsed):
        return parsed.date().isoformat()
    raise ValueError(f"Некоректна дата: {text}")


def date_to_display(value: Any) -> str:
    text = clean_scalar(value)
    if not text:
        return ""
    try:
        iso_value = date_to_db(value)
    except ValueError:
        return text
    return datetime.strptime(iso_value, "%Y-%m-%d").strftime("%d.%m.%Y") if iso_value else ""


def _normalise_numeric_text(value: Any) -> str:
    return clean_scalar(value).replace("\u00a0", "").replace(" ", "").replace(",", ".")


def split_fact_value(value: Any) -> tuple[int | float | None, str | None]:
    """Split one visible fact value into database numeric and text columns."""
    text = clean_scalar(value)
    if not text:
        return None, None
    normalised = _normalise_numeric_text(text)
    if not _NUMERIC_RE.fullmatch(normalised):
        return None, text
    try:
        number = Decimal(normalised)
    except InvalidOperation:
        return None, text
    if number == number.to_integral_value():
        return int(number), None
    return float(number), None


def numeric_to_display(value: Any) -> str:
    text = clean_scalar(value)
    if not text:
        return ""
    try:
        number = Decimal(text)
    except InvalidOperation:
        return text
    normalised = format(number.normalize(), "f")
    if "." in normalised:
        normalised = normalised.rstrip("0").rstrip(".")
    return normalised.replace(".", ",")


def fact_value_to_display(numeric_value: Any, value_text: Any) -> str:
    text_value = clean_scalar(value_text)
    return text_value if text_value else numeric_to_display(numeric_value)


def prepare_monitoring_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert a monitoring insert/update payload to database-native values."""
    result = dict(payload)
    if "year" in result:
        result["year"] = year_to_db(result.get("year"))
    if "quarter" in result:
        result["quarter"] = quarter_to_db(result.get("quarter"))
    if "start_date" in result:
        result["start_date"] = date_to_db(result.get("start_date"), boundary="start")
    if "end_date" in result:
        result["end_date"] = date_to_db(result.get("end_date"), boundary="end")
    if "as_of_date" in result:
        result["as_of_date"] = date_to_db(result.get("as_of_date"), boundary="end")
    if "numeric_value" in result and "value_text" not in result:
        numeric_value, value_text = split_fact_value(result.get("numeric_value"))
        result["numeric_value"] = numeric_value
        result["value_text"] = value_text
    return result


def prepare_closeout_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    if "period_year" in result:
        result["period_year"] = year_to_db(result.get("period_year"))
    if "period_quarter" in result:
        raw_quarter = clean_scalar(result.get("period_quarter"))
        if raw_quarter.lower() in {"", "рік", "весь рік"}:
            result["period_quarter"] = None
        else:
            result["period_quarter"] = quarter_to_db(raw_quarter)
    # Stage 5 / Ж2: store a typed actual value on the closeout itself.
    # The database later copies the same pair into monitoring_requests.
    if "fact_value" in result:
        numeric_value, value_text = split_fact_value(result.pop("fact_value"))
        result["fact_numeric_value"] = numeric_value
        result["fact_value_text"] = value_text
    elif "fact_numeric_value" in result and "fact_value_text" not in result:
        numeric_value, value_text = split_fact_value(result.get("fact_numeric_value"))
        result["fact_numeric_value"] = numeric_value
        result["fact_value_text"] = value_text
    return result


def normalise_monitoring_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Return a UI-compatible DataFrame from typed monitoring rows."""
    if df is None:
        return pd.DataFrame()
    data = df.copy()
    if "value_text" not in data.columns:
        data["value_text"] = ""
    if "numeric_value" not in data.columns:
        data["numeric_value"] = ""

    data["year"] = data.get("year", pd.Series(index=data.index, dtype=object)).map(year_to_display)
    data["quarter"] = data.get("quarter", pd.Series(index=data.index, dtype=object)).map(quarter_to_display)
    for column in ("start_date", "end_date", "as_of_date"):
        if column in data.columns:
            data[column] = data[column].map(date_to_display)
    data["numeric_value"] = [
        fact_value_to_display(number, text)
        for number, text in zip(data["numeric_value"], data["value_text"])
    ]
    return data.drop(columns=["value_text"], errors="ignore")


def normalise_closeout_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    data = df.copy()
    if "period_year" in data.columns:
        data["period_year"] = data["period_year"].map(year_to_display)
    if "period_quarter" in data.columns:
        data["period_quarter"] = data["period_quarter"].map(quarter_to_display)
        if "scope" in data.columns:
            annual_mask = data["scope"].map(clean_scalar).str.lower().eq("рік")
            data.loc[annual_mask, "period_quarter"] = "Рік"
    if "year" in data.columns:
        data["year"] = data["year"].map(year_to_display)
    if "quarter" in data.columns:
        data["quarter"] = data["quarter"].map(quarter_to_display)
    return data
