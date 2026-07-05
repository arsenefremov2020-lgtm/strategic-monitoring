# core/text_utils.py

"""
Єдині текстові утиліти системи (правка К3).

Раніше ці дрібні функції були скопійовані у 4–8 файлах з однаковою
поведінкою. Тепер джерело одне. Поведінка кожної функції збережена
1-в-1 з попередніми локальними копіями.
"""

from __future__ import annotations

import re
from html import escape

import pandas as pd


def raw_value(value) -> str:
    """Безпечний рядок без HTML-екранування (як в app.py / strategic_data.py)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if text in ("None", "nan", "NaN"):
        return ""
    return text


def clean_value(value) -> str:
    """Безпечний рядок З HTML-екрануванням (для вставки в markdown/HTML)."""
    return escape(raw_value(value))


def clean(value) -> str:
    """Синонім raw_value (історична назва в кількох сторінках)."""
    return raw_value(value)


def is_empty(value) -> bool:
    """True, якщо значення порожнє / '-' / 'н.д.' тощо."""
    t = raw_value(value).lower()
    return t in ("", "-", "—", "–", "н.д.", "нд", "n/a", "na", "none", "nan")


def parse_number(value):
    """
    Парсить число з тексту: '1 234,56' → 1234.56.
    Повертає float або None. (Поведінка як в Оцінці МіО — найповніша версія.)
    """
    t = raw_value(value)
    if not t:
        return None
    t = t.replace("\u00a0", " ").replace(" ", "")
    t = t.replace(",", ".")
    t = re.sub(r"[^0-9.\-+]", "", t)
    if t in ("", "-", "+", ".", "-.", "+."):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def strip_leading_code(text, code) -> str:
    """Прибирає код на початку назви: '1.1. Назва' → 'Назва'."""
    value = raw_value(text)
    code_value = raw_value(code)
    if code_value and value.startswith(code_value):
        value = value[len(code_value):].lstrip(" .—-–|:")
    return value


def extract_ssp_index(value) -> str:
    """Витягує перший числовий індекс ССП: 'деп. 30' → '30'."""
    text = raw_value(value)
    if not text:
        return ""
    match = re.search(r"\d+", text)
    return match.group(0) if match else ""


def normalize_name(value) -> str:
    """
    Нормалізує назву заходу/індикатора для звірки «подання ↔ поточна матриця»
    (механізм захисту від повторного використання коду після актуалізації плану):
    нижній регістр, без апострофів/лапок/розділових, пробіли стиснуті.
    Порівнюються перші 80 символів — щоб дрібні правки хвоста назви не рвали звірку.
    """
    t = raw_value(value).lower().replace("’", "").replace("'", "").replace("`", "")
    # знімаємо код на початку («1.1.1. Назва» → «Назва»), щоб знімок без коду
    # коректно звірявся з назвою в матриці, де код може бути в тексті
    t = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s*", "", t)
    t = re.sub(r"[\"«»().,;:!?/\\\-–—]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:80]


def names_match(stored_name, current_name) -> bool:
    """
    Чи відповідає збережена назва (знімок на момент подання) поточній назві
    у Страт_матриці. Порожня збережена назва (старі записи) вважається сумісною.
    """
    stored = normalize_name(stored_name)
    if not stored:
        return True
    return stored == normalize_name(current_name)
