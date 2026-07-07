import streamlit as st

from core.ui import load_css
from core.page_setup import page_setup, render_footer
from core.filters import get_source_options, match_source, PPDU_2026
from core.strategic_data import load_strat_matrix, strip_leading_code
from core.access import filter_actions_for_user


current_user = page_setup("Фільтр за документом", page_name="Фільтр за документом")

st.markdown('<div class="section-title">Фільтр заходів за стратегічним документом</div>', unsafe_allow_html=True)
st.caption(
    "Перелік заходів, прив'язаних до обраного національного стратегічного документа "
    "(поле «Національний рівень», Excel-стовпець Q)."
)

df = load_strat_matrix()

if "only_ppdu" not in st.session_state:
    st.session_state.only_ppdu = False


def toggle_only_ppdu():
    st.session_state.only_ppdu = not st.session_state.only_ppdu
    if st.session_state.only_ppdu:
        st.session_state.doc_filter_select = [PPDU_2026]
    else:
        st.session_state.doc_filter_select = []


col_toggle, col_select = st.columns([1, 3])

with col_toggle:
    st.button(
        "Тільки ППДУ-2026" if not st.session_state.only_ppdu else "✓ Тільки ППДУ-2026",
        on_click=toggle_only_ppdu,
        use_container_width=True,
    )

with col_select:
    selected_sources = st.multiselect(
        "Стратегічний документ (національний рівень)",
        get_source_options(),
        key="doc_filter_select",
    )

if not selected_sources:
    st.info("Оберіть документ або натисніть «Тільки ППДУ-2026», щоб побачити відповідні заходи.")
    st.stop()

measures = df[df["object_type"] == "measure"].copy()
# Пункт 1 нового ТЗ: ролі, звужені до власного ССП, бачать за
# замовчуванням лише заходи свого ССП (кнопка "Переглянути загальну
# інформацію" з page_setup() знімає це звуження на цій вкладці).
measures = filter_actions_for_user(measures, current_user, page_key="Фільтр за документом")
matched = measures[measures["source_national"].apply(lambda v: match_source(v, selected_sources))]

st.markdown(f"**Знайдено заходів: {len(matched)}**")

if matched.empty:
    st.warning("За обраним документом заходів не знайдено.")
    st.stop()

display_df = matched[[
    "code", "name", "product_type", "indicator", "unit",
    "resp_main", "resp_co_1", "source_national",
]].copy()

display_df["name"] = display_df.apply(lambda r: strip_leading_code(r["name"], r["code"]), axis=1)

display_df = display_df.rename(columns={
    "code": "Код",
    "name": "Захід",
    "product_type": "Тип продукту",
    "indicator": "Індикатор",
    "unit": "Одиниці виміру",
    "resp_main": "Головний виконавець",
    "resp_co_1": "Співвиконавець",
    "source_national": "Національний рівень",
})

st.dataframe(display_df, use_container_width=True, hide_index=True)

render_footer()
