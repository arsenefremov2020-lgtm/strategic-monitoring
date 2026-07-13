"""Shared helper for the admin/super-admin manual closeout workflow.

Reads confirmed ("Підтверджено") closeout_requests rows so the "Закрито
вручну" badge can be rendered consistently wherever a measure's status is
shown (app.py, monitoring submission page, dashboard).

Особливості:
- закриття з масштабом «Рік» (scope='Рік' або period_quarter у
  {'Рік','РІК',''}) розгортається на всі чотири квартали цього року;
- скасовані супер-адміном закриття (approval_status='Скасовано')
  сюди не потрапляють — фільтр лише за «Підтверджено».
"""

import streamlit as st

from core.data_types import quarter_to_display, year_to_display
from core.db import fetch_all
from core.strategic_data import raw_value

_YEAR_MARKERS = {"рік", "весь рік", ""}
_ALL_QUARTERS = ("I", "II", "III", "IV")


@st.cache_data(ttl=300)
def load_manual_closeouts():
    """Returns a set of (strat_code, year, quarter) confirmed as 'Закрито вручну'."""
    try:
        rows = fetch_all(
            "closeout_requests",
            "strat_code,period_year,period_quarter,approval_status",
            filters=[("eq", "approval_status", "Підтверджено")],
            order=("id", False),
        )
    except Exception as exc:
        st.warning(
            "⚠️ Не вдалося прочитати ручні закриття (closeout_requests) — "
            "статуси «Закрито вручну» тимчасово не враховуються. "
            f"Технічна причина: {type(exc).__name__}: {exc}"
        )
        return set()

    if not rows:
        return set()

    result = set()
    for r in rows:
        code = raw_value(r.get("strat_code"))
        year = year_to_display(r.get("period_year"))
        quarter = quarter_to_display(r.get("period_quarter"))

        if quarter.strip().lower() in _YEAR_MARKERS:
            # Закриття на весь рік — позначає всі квартали
            for q in _ALL_QUARTERS:
                result.add((code, year, q))
        else:
            result.add((code, year, quarter))

    return result
