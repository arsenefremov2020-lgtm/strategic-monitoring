import pandas as pd
import streamlit as st

from core.ui import load_css
from core.page_setup import page_setup, render_footer
from core.filters import match_source, PPDU_2026
from core.strategic_data import load_strat_matrix, strip_leading_code
from core.access import filter_actions_for_user


current_user = page_setup("Звітність ППДУ", page_name="Звітність ППДУ")

st.info(
    "Це тестовий варіант сторінки, який перебуває на стадії опрацювання. "
    "Дані не зберігаються в базу — це лише попередній перегляд структури звітності "
    "для Плану пріоритетних дій Уряду на 2026 рік."
)

st.markdown('<div class="section-title">Звітність ППДУ-2026 (тестовий режим)</div>', unsafe_allow_html=True)

df = load_strat_matrix()
measures = df[df["object_type"] == "measure"].copy()
# Пункт 1 нового ТЗ: звужуємо до власного ССП (кнопка "Переглянути
# загальну інформацію" з page_setup() знімає звуження на цій вкладці).
measures = filter_actions_for_user(measures, current_user, page_key="Звітність ППДУ")
ppdu_measures = measures[measures["source_national"].apply(lambda v: match_source(v, [PPDU_2026]))].copy()

st.caption(f"Заходів ППДУ-2026 у стратегічній матриці: {len(ppdu_measures)}")

if ppdu_measures.empty:
    st.warning("Заходів, прив'язаних до ППДУ-2026, не знайдено.")
    st.stop()

table_rows = []
for _, row in ppdu_measures.iterrows():
    code = row.get("code", "")
    table_rows.append({
        "Код": code,
        "Захід": strip_leading_code(row.get("name", ""), code),
        "Тип продукту": row.get("product_type", ""),
        "Індикатор": row.get("indicator", ""),
        "Одиниці виміру": row.get("unit", ""),
        "2021 (базовий)": row.get("base_2021", ""),
        "2024 (звіт)": row.get("fact_2024", ""),
        "2025 (факт)": row.get("fact_2025", ""),
        "2026 (цільовий орієнтир)": row.get("target_2026", ""),
        "2027 (цільовий орієнтир)": row.get("target_2027", ""),
        "2028 (цільовий орієнтир)": row.get("target_2028", ""),
    })

draft_df = pd.DataFrame(table_rows)

edited_draft = st.data_editor(
    draft_df,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    disabled=[
        "Код", "Захід", "Тип продукту", "Індикатор", "Одиниці виміру",
        "2021 (базовий)", "2024 (звіт)", "2025 (факт)",
    ],
)

st.button("Подати тестову звітність ППДУ (нічого не зберігає)", disabled=True, use_container_width=True)

render_footer()
