import pandas as pd
import streamlit as st

from core.ui import load_css
from core.page_setup import page_setup, render_footer
from core.data_types import quarter_to_display, year_to_display
from core.db import fetch_all, get_supabase_client


page_setup("Архів", page_name="Архів")

st.markdown('<div class="section-title">Архів заархівованих періодів</div>', unsafe_allow_html=True)
st.caption(
    "Тут показані «заморожені» знімки даних, зафіксовані на момент архівування. "
    "Вони не перераховуються і не змінюються разом із живими даними чи логікою розрахунків."
)

supabase = get_supabase_client()


@st.cache_data(ttl=60)
def load_archive_index():
    try:
        data = pd.DataFrame(fetch_all(
            "archive_snapshots",
            "id,year,quarter,archived_by,archived_at",
            order=("archived_at", True),
        ))
    except Exception:
        return pd.DataFrame()
    if not data.empty:
        data["year"] = data["year"].map(year_to_display)
        data["quarter"] = data["quarter"].map(quarter_to_display)
    return data


@st.cache_data(ttl=60)
def load_snapshot(snapshot_id):
    resp = supabase.table("archive_snapshots").select("*").eq("id", snapshot_id).execute()
    return resp.data[0] if resp.data else None


index_df = load_archive_index()

if index_df.empty:
    st.info("Заархівованих періодів ще немає.")
    st.stop()

index_df["label"] = index_df.apply(
    lambda r: f"{r['quarter'] if r['quarter'] else 'Весь рік'} {r['year']} (заархівовано {r['archived_at']})",
    axis=1,
)

selected_label = st.selectbox("Оберіть заархівований період", index_df["label"])
selected_id = int(index_df.loc[index_df["label"] == selected_label, "id"].iloc[0])

snapshot = load_snapshot(selected_id)

if snapshot is None:
    st.warning("Не вдалося завантажити обраний знімок.")
    st.stop()

st.caption(f"Заархівовано: {snapshot.get('archived_by', '')} о {snapshot.get('archived_at', '')}")

snapshot_data = snapshot.get("snapshot_data") or {}
measures = pd.DataFrame(snapshot_data.get("measures", []))
monitoring = pd.DataFrame(snapshot_data.get("monitoring", []))

st.markdown('<div class="section-title">Заходи (на момент архівування)</div>', unsafe_allow_html=True)
if measures.empty:
    st.info("У цьому знімку немає даних про заходи.")
else:
    measure_rows = measures[measures.get("object_type") == "measure"] if "object_type" in measures.columns else measures
    st.dataframe(measure_rows, use_container_width=True, hide_index=True)

st.markdown('<div class="section-title">Подані відомості моніторингу (на момент архівування)</div>', unsafe_allow_html=True)
if monitoring.empty:
    st.info("У цьому знімку немає поданих відомостей моніторингу за обраний період.")
else:
    st.dataframe(monitoring, use_container_width=True, hide_index=True)

render_footer()
