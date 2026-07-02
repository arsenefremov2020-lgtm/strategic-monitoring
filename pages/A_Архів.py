import pandas as pd
import streamlit as st

from core.ui import load_css
from core.auth import init_auth_state, render_login_form
from core.navigation import require_page_access, render_role_page_links
from core.db import get_supabase_client


st.set_page_config(page_title="Архів", layout="wide")

init_auth_state()
render_login_form()
render_role_page_links()

if not require_page_access("Архів"):
    st.stop()

load_css()

st.markdown('<div class="section-title">Архів заархівованих періодів</div>', unsafe_allow_html=True)
st.caption(
    "Тут показані «заморожені» знімки даних, зафіксовані на момент архівування. "
    "Вони не перераховуються і не змінюються разом із живими даними чи логікою розрахунків."
)

supabase = get_supabase_client()


@st.cache_data(ttl=60)
def load_archive_index():
    try:
        resp = (
            supabase.table("archive_snapshots")
            .select("id,year,quarter,archived_by,archived_at")
            .order("archived_at", desc=True)
            .execute()
        )
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()


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
