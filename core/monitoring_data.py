# core/monitoring_data.py

"""
Єдина точка читання заявок моніторингу з Supabase (правка К2 / П2).

Виправлення П2: раніше сторінки визначали наявність колонок
(npa_link, approval_chain, object_kind…) за завантаженим DataFrame.
Якщо таблиця була ПОРОЖНЯ (наприклад, після очищення тестових даних),
select("*") повертав порожній результат без колонок — і система хибно
вважала, що колонок у базі немає: перше подання йшло без схеми
погодження, посилання на НПА та позначки захід/індикатор.

Тепер перелік колонок таблиці зафіксований константою
MONITORING_COLUMNS (синхронізована з міграціями 001–006), а
ensure_monitoring_columns гарантує їх наявність у DataFrame навіть
для порожньої таблиці.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.data_types import normalise_monitoring_frame, quarter_to_db, quarter_to_display
from core.db import fetch_all
from core.errors import log_cosmetic_error, show_warning
from core.period_locks import is_period_locked

# Повний перелік колонок таблиці monitoring_requests
# (синхронізовано з фактичною схемою Supabase та міграціями 004–006).
MONITORING_COLUMNS = [
    "id", "year", "quarter", "department",
    "responsible_person", "phone", "email",
    "strat_code", "object_name", "indicator_name",
    "status", "progress_text", "numeric_value", "risks",
    "submitted_at", "approval_status", "admin_comment", "created_at",
    "start_date", "end_date",
    "file_names", "file_urls",
    "npa_link",
    "approval_chain", "chain_stage", "scheme_label",
    "object_kind", "as_of_date",
    "final_locked", "final_locked_at",
]

# Колонки, які сторінки перевіряють на існування (П2): тепер — константи.
HAS_NPA_LINK_COLUMN = True
HAS_CHAIN_COLUMNS = True
HAS_OBJECT_KIND_COLUMN = True
HAS_OBJECT_NAME_COLUMN = True


_AUTO_INHERITED_YES_VALUES = {"так", "yes", "true"}


def apply_yes_no_completion_inheritance(monitoring_df: pd.DataFrame) -> pd.DataFrame:
    """Project cumulative ``так`` + ``Виконано`` into later quarters read-only.

    No database rows are created. For every measure/year/target quarter the
    latest *real* prior-quarter record is authoritative: inheritance occurs
    only when that latest record is ``так`` with status ``Виконано``. Therefore
    a later real submission automatically overrides an inherited value and also
    becomes the source of truth for still-later quarters.
    """
    if monitoring_df is None or monitoring_df.empty:
        return ensure_monitoring_columns(
            monitoring_df.copy() if hasattr(monitoring_df, "copy") else pd.DataFrame()
        )

    data = ensure_monitoring_columns(monitoring_df).copy()
    data["_auto_inherited"] = False
    data["_inherited_from_quarter"] = ""

    def _clean(value: object) -> str:
        if value is None:
            return ""
        value_text = str(value).strip()
        return "" if value_text.lower() in {"nan", "none", "null"} else value_text

    # One authoritative real row per (measure, year, quarter). If duplicate
    # rows exist, the highest request id is the newest and therefore wins.
    real_by_period: dict[tuple[str, str, int], pd.Series] = {}
    for _, row in data.iterrows():
        if _clean(row.get("object_kind")).lower() == "indicator":
            continue
        code = _clean(row.get("strat_code"))
        year = _clean(row.get("year"))
        try:
            quarter_num = quarter_to_db(row.get("quarter"))
        except ValueError:
            quarter_num = None
        if not code or not year or not quarter_num:
            continue

        key = (code, year, quarter_num)
        previous = real_by_period.get(key)
        if previous is None:
            real_by_period[key] = row
            continue
        try:
            current_id = int(row.get("id"))
        except (TypeError, ValueError):
            current_id = -1
        try:
            previous_id = int(previous.get("id"))
        except (TypeError, ValueError):
            previous_id = -1
        if current_id >= previous_id:
            real_by_period[key] = row

    measure_years = sorted({(code, year) for code, year, _ in real_by_period})
    inherited_rows: list[pd.Series] = []

    for code, year in measure_years:
        for target_quarter in range(1, 5):
            target_key = (code, year, target_quarter)
            if target_key in real_by_period or is_period_locked(year, target_quarter):
                continue

            prior_real = [
                (quarter_num, row)
                for (row_code, row_year, quarter_num), row in real_by_period.items()
                if row_code == code
                and row_year == year
                and quarter_num < target_quarter
                and not is_period_locked(year, quarter_num)
            ]
            if not prior_real:
                continue

            source_quarter, source = max(prior_real, key=lambda item: item[0])
            if _clean(source.get("status")) != "Виконано":
                continue
            if _clean(source.get("numeric_value")).lower() not in _AUTO_INHERITED_YES_VALUES:
                continue

            inherited = source.copy()
            inherited["id"] = ""
            inherited["quarter"] = quarter_to_display(target_quarter)
            inherited["status"] = "Виконано"
            inherited["numeric_value"] = "так"
            inherited["final_locked"] = False
            inherited["final_locked_at"] = ""
            inherited["_auto_inherited"] = True
            inherited["_inherited_from_quarter"] = quarter_to_display(source_quarter)
            inherited_rows.append(inherited)

    if not inherited_rows:
        return data
    return pd.concat(
        [data, pd.DataFrame(inherited_rows)],
        ignore_index=True,
        sort=False,
    )

def ensure_monitoring_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Гарантує наявність усіх колонок monitoring_requests у DataFrame."""
    if df is None:
        df = pd.DataFrame()
    data = df.copy()
    for col in MONITORING_COLUMNS:
        if col not in data.columns:
            data[col] = ""
    return data


@st.cache_data(ttl=300, show_spinner=False)
def load_monitoring_requests() -> pd.DataFrame:
    """
    Читає ВСІ заявки моніторингу.
    Повертає DataFrame з гарантованим повним набором колонок
    (навіть якщо таблиця порожня).

    Якщо базу прочитати НЕ вдалося — показує помітне попередження
    (а не мовчазне «даних немає»), щоб технічний збій не маскувався
    під порожню систему.
    """
    try:
        data = pd.DataFrame(fetch_all(
            "monitoring_requests", "*",
            filters=[("neq", "approval_status", "Відкликано")],
            order=("id", False),
        ))
    except Exception as exc:
        show_warning(
            "Не вдалося прочитати заявки моніторингу з бази даних; показники можуть бути неповними.",
            exc,
            "Читання monitoring_requests",
        )
        data = pd.DataFrame()
    normalised = ensure_monitoring_columns(normalise_monitoring_frame(data))
    return apply_yes_no_completion_inheritance(normalised)


@st.cache_data(ttl=20, show_spinner=False)
def load_monitoring_requests_live() -> pd.DataFrame:
    """
    «Швидке» читання заявок для РОБОЧИХ сторінок (Мій кабінет,
    Мої заявки, Адміністрування): TTL 20 секунд, щоб рішення інших
    ланок з'являлися практично одразу.

    Оглядові сторінки (Головна, Dashboard, Картка заходу,
    Фільтр за документом, Оцінка МіО) лишаються на load_monitoring_requests
    з TTL 5 хвилин — саме так погоджено в ТЗ DEMO 1.9.
    """
    try:
        data = pd.DataFrame(fetch_all(
            "monitoring_requests", "*",
            filters=[("neq", "approval_status", "Відкликано")],
            order=("id", False),
        ))
    except Exception as exc:
        show_warning(
            "Не вдалося прочитати заявки моніторингу з бази даних; показники можуть бути неповними.",
            exc,
            "Читання monitoring_requests",
        )
        data = pd.DataFrame()
    return ensure_monitoring_columns(normalise_monitoring_frame(data))


def invalidate_monitoring_cache() -> None:
    """
    ТОЧКОВЕ очищення кешу заявок (правка за ТЗ 15.7–15.8).

    Чистить лише лоадери заявок моніторингу та ручних закриттів —
    важка стратегічна матриця з Excel і кеші користувачів НЕ
    перечитуються, тож система реагує на дії миттєво, але без
    зайвого повного перезавантаження всіх даних.
    """
    try:
        load_monitoring_requests.clear()
    except Exception as exc:
        log_cosmetic_error("Очищення кешу load_monitoring_requests", exc)
    try:
        load_monitoring_requests_live.clear()
    except Exception as exc:
        log_cosmetic_error("Очищення кешу load_monitoring_requests_live", exc)
    try:
        from core.closeouts import load_manual_closeouts
        load_manual_closeouts.clear()
    except Exception as exc:
        log_cosmetic_error("Очищення кешу load_manual_closeouts", exc)


def measures_only(monitoring_df: pd.DataFrame) -> pd.DataFrame:
    """
    Лише подання ЗАХОДІВ (object_kind != 'indicator').

    Використовується всюди, де йдеться про аналітику/статуси заходів,
    щоб подання індикаторів цілей і завдань не змішувалися з заходами.
    Старі записи без object_kind вважаються заходами.
    """
    if monitoring_df is None or monitoring_df.empty:
        return ensure_monitoring_columns(pd.DataFrame())
    data = ensure_monitoring_columns(monitoring_df)
    kind = data["object_kind"].astype(str).str.strip().str.lower()
    return data[kind != "indicator"].copy()


def indicators_only(monitoring_df: pd.DataFrame) -> pd.DataFrame:
    """Лише подання ІНДИКАТОРІВ цілей/завдань (object_kind == 'indicator')."""
    if monitoring_df is None or monitoring_df.empty:
        return ensure_monitoring_columns(pd.DataFrame())
    data = ensure_monitoring_columns(monitoring_df)
    kind = data["object_kind"].astype(str).str.strip().str.lower()
    return data[kind == "indicator"].copy()


def approved_only(monitoring_df: pd.DataFrame) -> pd.DataFrame:
    """Лише погоджені подання (офіційний процес)."""
    if monitoring_df is None or monitoring_df.empty:
        return ensure_monitoring_columns(pd.DataFrame())
    data = ensure_monitoring_columns(monitoring_df)
    return data[data["approval_status"].astype(str).str.strip() == "Погоджено"].copy()
