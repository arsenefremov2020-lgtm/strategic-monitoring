"""Спільні фінансові розрахунки для «Оцінки МіО» та Dashboard.

Модуль є єдиною точкою читання фактичного освоєння бюджету з окремого
Excel-файлу та обчислення фінансового виконання/еластичності. Він не
імпортує сторінки застосунку й зберігає формули режиму «МіО Фінансування».
"""

from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd

FIN_FILE_PATH = "БП під моніторинг СП.xlsx"
FIN_SHEET_CANDIDATES = ["МіО Фінансування", "Фінансування", "БП", "Sheet1", "Аркуш1"]
FIN_CODE_KEYS = [
    "код заходу",
    "код",
    "захід",
    "strat_code",
    "measure_code",
    "code",
    "кпкв код",
]
FIN_YEAR_KEYS = ["рік", "year", "звітний рік"]
FIN_KPKVK_KEYS = ["кпквк", "kpkvk", "kpkv", "код кпквк", "бюджетна програма"]
FIN_SOURCE_KEYS = [
    "інше джерело фінансування",
    "інше джерело",
    "джерело фінансування",
    "other_source",
    "fin_source",
    "джерело",
]
FIN_PLAN_KEYS = [
    "план (млрд грн)",
    "план, млрд грн",
    "план млрд грн",
    "план млрд",
    "план",
    "plan",
    "fin_plan",
    "fin_plan_bln",
]
FIN_FACT_KEYS = [
    "факт (млрд грн)",
    "факт, млрд грн",
    "факт млрд грн",
    "факт млрд",
    "факт",
    "fact",
    "fin_fact",
    "fin_fact_bln",
]


def raw_value(value: Any) -> str:
    """Локальна копія нормалізації, яку використовувала «Оцінка МіО»."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def is_empty(value: Any) -> bool:
    text = raw_value(value).lower().replace(" ", "")
    return text in ["", "nan", "none", "н.д.", "нд", "-", "—"]


def parse_number(value: Any) -> float | None:
    text = raw_value(value)
    if is_empty(text):
        return None
    text = text.replace("\u00a0", " ").replace("%", "").replace(",", ".")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in ["", ".", "-", "-."]:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _fin_norm_header(value):
    """Нормалізує заголовок колонки: нижній регістр, без зайвих пробілів/переносів."""
    t = raw_value(value).lower().replace("\n", " ").replace("\xa0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _fin_match_col(columns, candidates):
    """Шукає колонку, чий нормалізований заголовок збігається/містить кандидата."""
    norm = {_fin_norm_header(c): c for c in columns}
    for cand in candidates:                      # точний збіг
        if cand in norm:
            return norm[cand]
    for cand in candidates:                      # частковий збіг (план/факт + рік)
        for nk, orig in norm.items():
            if nk.startswith(cand) or cand in nk:
                return orig
    return None


def _fin_year_columns(columns):
    """Для широкого формату: знаходить пари (рік → колонка плану/факту)."""
    plan_by_year, fact_by_year = {}, {}
    for c in columns:
        nk = _fin_norm_header(c)
        m = re.search(r"(20\d{2})", nk)
        if not m:
            continue
        yr = m.group(1)
        if nk.startswith("план") or "план" in nk:
            plan_by_year[yr] = c
        elif nk.startswith("факт") or "факт" in nk:
            fact_by_year[yr] = c
    return plan_by_year, fact_by_year


def load_financing_data():
    """
    Зчитує бюджетні дані заходів із окремого Excel «БП під моніторинг СП.xlsx»
    у вигляді індексу:
        {(code, year_str): {kpkvk, other_source, plan_bln, fact_bln}}

    Автовизначення довгого/широкого формату. Якщо файлу немає або він
    нечитабельний — повертає порожній індекс (режим працює, бюджетні
    колонки — прочерками).
    """
    index = {}
    try:
        xls = pd.ExcelFile(FIN_FILE_PATH, engine="openpyxl")
    except Exception:
        return index  # файл ще не внесено — тиха коректна деградація

    # Вибір аркуша: відомий за назвою, інакше перший.
    sheet = next((s for s in FIN_SHEET_CANDIDATES if s in xls.sheet_names),
                 xls.sheet_names[0] if xls.sheet_names else None)
    if sheet is None:
        return index

    try:
        df = xls.parse(sheet)
    except Exception:
        return index
    if df is None or df.empty:
        return index

    cols = list(df.columns)
    k_code = _fin_match_col(cols, FIN_CODE_KEYS)
    k_year = _fin_match_col(cols, FIN_YEAR_KEYS)
    k_kpkvk = _fin_match_col(cols, FIN_KPKVK_KEYS)
    k_src = _fin_match_col(cols, FIN_SOURCE_KEYS)
    if not k_code:
        return index

    plan_by_year, fact_by_year = _fin_year_columns(cols)
    wide = (not k_year) and (plan_by_year or fact_by_year)

    if wide:
        # ── ШИРОКИЙ формат: роки в колонках ──
        for _, rec in df.iterrows():
            code = raw_value(rec.get(k_code))
            if not code:
                continue
            kpkvk = raw_value(rec.get(k_kpkvk)) if k_kpkvk else ""
            src = raw_value(rec.get(k_src)) if k_src else ""
            years = set(plan_by_year) | set(fact_by_year)
            for yr in years:
                plan = parse_number(rec.get(plan_by_year[yr])) if yr in plan_by_year else None
                fact = parse_number(rec.get(fact_by_year[yr])) if yr in fact_by_year else None
                index[(code, yr)] = {
                    "kpkvk": kpkvk, "other_source": src,
                    "plan_bln": plan, "fact_bln": fact,
                }
    else:
        # ── ДОВГИЙ формат: рядок на захід+рік ──
        k_plan = _fin_match_col(cols, FIN_PLAN_KEYS)
        k_fact = _fin_match_col(cols, FIN_FACT_KEYS)
        for _, rec in df.iterrows():
            code = raw_value(rec.get(k_code))
            if not code:
                continue
            year = raw_value(rec.get(k_year)) if k_year else ""
            # Рік на кшталт «2026.0» → «2026»
            ym = re.search(r"(20\d{2})", year)
            year = ym.group(1) if ym else year
            index[(code, year)] = {
                "kpkvk": raw_value(rec.get(k_kpkvk)) if k_kpkvk else "",
                "other_source": raw_value(rec.get(k_src)) if k_src else "",
                "plan_bln": parse_number(rec.get(k_plan)) if k_plan else None,
                "fact_bln": parse_number(rec.get(k_fact)) if k_fact else None,
            }
    return index


def _fin_lookup(fin_index, code, year):
    """Бере бюджетний запис за (код, рік); якщо немає — пробує без року."""
    return (fin_index.get((code, str(year)))
            or fin_index.get((code, ""))
            or {})


def financial_execution_percent(plan_bln, fact_bln):
    """% фінансового виконання = факт / план × 100; інакше ``None``."""
    if plan_bln not in (None, 0) and fact_bln is not None:
        return fact_bln / plan_bln * 100.0
    return None


def annual_score_percent(annual_score):
    """Стан виконання заходу, % = річний бал заходу × 100."""
    if isinstance(annual_score, (int, float)):
        return annual_score * 100.0
    return annual_score


def financial_elasticity(financial_execution_pct, state_execution_pct):
    """Коефіцієнт еластичності з тією самою IFERROR-логікою моделі МіО."""
    if (
        financial_execution_pct not in (None, 0, 0.0)
        and isinstance(state_execution_pct, (int, float))
        and state_execution_pct not in (0, 0.0)
    ):
        return financial_execution_pct / state_execution_pct
    return None


def calculate_financial_metrics(plan_bln, fact_bln, annual_score):
    """Повертає фінансове виконання, стан виконання та еластичність заходу."""
    financial_execution_pct = financial_execution_percent(plan_bln, fact_bln)
    state_execution_pct = annual_score_percent(annual_score)
    elasticity = financial_elasticity(financial_execution_pct, state_execution_pct)
    return {
        "financial_execution_pct": financial_execution_pct,
        "state_execution_pct": state_execution_pct,
        "elasticity": elasticity,
    }
