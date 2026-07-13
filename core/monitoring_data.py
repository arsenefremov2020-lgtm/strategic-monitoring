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

from core.data_types import normalise_monitoring_frame
from core.db import fetch_all
from core.errors import log_cosmetic_error, show_warning

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
    return ensure_monitoring_columns(normalise_monitoring_frame(data))


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
