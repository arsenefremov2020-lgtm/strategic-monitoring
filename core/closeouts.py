"""Shared helper for the admin/super-admin manual closeout workflow.

Reads confirmed ("Підтверджено") closeout_requests rows so the "Закрито
вручну" badge can be rendered consistently wherever a measure's status is
shown (app.py, monitoring submission page, dashboard).
"""

import streamlit as st

from core.db import get_supabase_client
from core.strategic_data import raw_value


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
    except Exception:
        return set()

    if not response.data:
        return set()

    return {
        (raw_value(r.get("strat_code")), raw_value(r.get("period_year")), raw_value(r.get("period_quarter")))
        for r in response.data
    }
