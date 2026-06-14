"""Supabase connection helpers."""

from __future__ import annotations

import streamlit as st
from supabase import create_client


@st.cache_resource(show_spinner=False)
def get_supabase_client():
    """Return a cached Supabase client configured from Streamlit secrets."""
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
