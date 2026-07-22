"""Compatibility redirect for legacy links to the former page path.

The visible/custom navigation uses pages/3_Мої_заявки.py.
This shim remains because pages/0_Центр_задач.py is intentionally forbidden
for direct edits and still contains a legacy link to this path.
"""

import streamlit as st

st.switch_page("pages/3_Мої_заявки.py")
