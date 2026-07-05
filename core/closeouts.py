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

from core.db import get_supabase_client
from core.strategic_data import raw_value

_YEAR_MARKERS = {"рік", "весь рік", ""}
_ALL_QUARTERS = ("I", "II", "III", "IV")


@st.cache_data(ttl=300)
def load_manual_closeouts():
    """Returns a set of (strat_code, year, quarter) confirmed as 'Закрито вручну'."""
    supabase = get_supabase_client()
    try:
        response = (
            supabase.table("closeout_requests")
            .select("strat_code,period_year,period_quarter,approval_status")
            .eq("approval_status", "Підтверджено")
            .execute()
        )
    except Exception as exc:
        st.warning(
            "⚠️ Не вдалося прочитати ручні закриття (closeout_requests) — "
            "статуси «Закрито вручну» тимчасово не враховуються. "
            f"Технічна причина: {type(exc).__name__}: {exc}"
        )
        return set()

    if not response.data:
        return set()

    result = set()
    for r in response.data:
        code = raw_value(r.get("strat_code"))
        year = raw_value(r.get("period_year"))
        quarter = raw_value(r.get("period_quarter"))

        if quarter.strip().lower() in _YEAR_MARKERS:
            # Закриття на весь рік — позначає всі квартали
            for q in _ALL_QUARTERS:
                result.add((code, year, q))
        else:
            result.add((code, year, quarter))

    return result
