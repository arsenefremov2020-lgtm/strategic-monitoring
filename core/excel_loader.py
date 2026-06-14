"""Shared Excel loading helpers.

Pages may keep their own column-mapping formulas where the approved calculation
logic is page-specific. This module centralizes the low-level file/sheet read so
new pages do not duplicate the same Excel access code.
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from core.config import FILE_PATH, SHEET_NAME


@lru_cache(maxsize=16)
def read_excel_sheet(file_path: str = FILE_PATH, sheet_name: str = SHEET_NAME, header: int | None = None) -> pd.DataFrame:
    """Read an Excel sheet with openpyxl and cache the raw DataFrame."""
    return pd.read_excel(file_path, sheet_name=sheet_name, header=header, engine="openpyxl")
