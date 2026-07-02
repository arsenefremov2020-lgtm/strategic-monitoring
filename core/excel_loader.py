"""Shared Excel loading helpers.

ЄДИНА точка читання великого Excel-файлу стратегічної матриці.

Чому це важливо для швидкодії:
- файл "Під моніторинг СП.xlsx" важить ~5 МБ і містить 35 аркушів;
- раніше КОЖНА сторінка викликала pd.read_excel(...) самостійно, тобто
  перехід між сторінками (і навіть перший рендер кількох завантажувачів
  на одній сторінці) заново розпаковував і парсив увесь файл;
- тепер кожен аркуш парситься РІВНО ОДИН РАЗ на процес (lru_cache) і
  спільний для всіх сесій усіх користувачів;
- сторінки зберігають власні мапінги колонок — змінюється лише джерело
  сирого DataFrame.

ВАЖЛИВО: read_excel_sheet повертає спільний кешований DataFrame.
Його НЕ МОЖНА мутувати. Усі сторінки одразу роблять .iloc[...].copy() —
цю домовленість треба зберігати й у новому коді.
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from core.config import FILE_PATH, SHEET_NAME


@lru_cache(maxsize=64)
def read_excel_sheet(
    file_path: str = FILE_PATH,
    sheet_name: str = SHEET_NAME,
    header: int | None = None,
) -> pd.DataFrame:
    """Read an Excel sheet with openpyxl and cache the raw DataFrame per process."""
    return pd.read_excel(file_path, sheet_name=sheet_name, header=header, engine="openpyxl")


def clear_excel_cache() -> None:
    """Скидає кеш сирих аркушів (використовується кнопкою оновлення / після заміни файлу)."""
    read_excel_sheet.cache_clear()
