from __future__ import annotations

import pandas as pd
import streamlit as st

from core.archive import (
    decode_snapshot_payload,
    export_snapshot_docx,
    export_snapshot_excel,
    export_snapshot_pdf,
    format_kyiv,
)
from core.db import fetch_all, get_supabase_client
from core.errors import show_incident
from core.page_setup import page_setup, render_footer


page_setup("Архів", page_name="Архів")
supabase = get_supabase_client()

st.markdown('<div class="section-title">Архів</div>', unsafe_allow_html=True)
st.warning("ТЕСТОВИЙ РЕЖИМ · Архівні знімки є незмінними після створення.")
st.caption(
    "Архів містить повну фотографію системи на момент створення: стратегічну матрицю, "
    "усі заявки та їх версії, розрахункові складові МіО і повний журнал дій."
)


@st.cache_data(ttl=60, show_spinner=False)
def load_archive_index() -> pd.DataFrame:
    rows = fetch_all(
        "archive_snapshots",
        (
            "id,year,quarter,archived_by,archived_at,snapshot_type,reason,replacement_reason,"
            "replaces_snapshot_id,payload_size_bytes,coverage_label,coverage_year_from,"
            "coverage_year_to,structure_row_count,request_count,version_count,measure_count,mio_record_count,"
            "log_count,closeout_count,closeout_version_count"
        ),
        order=("archived_at", True),
    )
    return pd.DataFrame(rows)


@st.cache_data(ttl=60, show_spinner=False)
def load_snapshot(snapshot_id: int) -> dict:
    response = (
        supabase.table("archive_snapshots")
        .select("*")
        .eq("id", int(snapshot_id))
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else {}


index_df = load_archive_index()

if index_df.empty:
    st.info("Архівних знімків ще немає.")
    render_footer()
    st.stop()

index_df["archived_at_label"] = index_df["archived_at"].map(format_kyiv)
index_df["type_label"] = index_df["snapshot_type"].map(
    lambda value: "Автоматичний" if value == "automatic" else "Ручний"
)

replacement_map: dict[int, dict] = {}
for _, row in index_df.iterrows():
    old_id = row.get("replaces_snapshot_id")
    if pd.notna(old_id) and str(old_id).strip():
        try:
            old_id_int = int(float(old_id))
        except (TypeError, ValueError):
            continue
        current = replacement_map.get(old_id_int)
        if current is None or str(row.get("archived_at", "")) > str(current.get("archived_at", "")):
            replacement_map[old_id_int] = row.to_dict()

st.markdown("### Перелік знімків")
labels: dict[int, str] = {}
for _, row in index_df.iterrows():
    snapshot_id = int(row["id"])
    suffix = ""
    if snapshot_id in replacement_map:
        newer = replacement_map[snapshot_id]
        suffix = f" · Є новіша версія від {format_kyiv(newer.get('archived_at'))}"
    if pd.notna(row.get("replaces_snapshot_id")) and str(row.get("replaces_snapshot_id")).strip():
        suffix += f" · Заміна знімка №{int(float(row.get('replaces_snapshot_id')))}"
    labels[snapshot_id] = (
        f"№{snapshot_id} · {row.get('archived_at_label', '—')} · "
        f"{row.get('type_label', 'Ручний')} · {row.get('coverage_label', '')}{suffix}"
    )

selected_id = st.selectbox(
    "Оберіть архівний знімок",
    options=list(labels),
    format_func=lambda value: labels[value],
)

snapshot = load_snapshot(int(selected_id))
if not snapshot:
    st.error("Не вдалося завантажити обраний архівний знімок.")
    render_footer()
    st.stop()

try:
    if snapshot.get("snapshot_gzip_b64"):
        payload = decode_snapshot_payload(snapshot.get("snapshot_gzip_b64"))
    else:
        # Сумісність зі старою порожньою/тестовою структурою архіву.
        old_payload = snapshot.get("snapshot_data") or {}
        payload = {
            "main_table": old_payload.get("measures", []),
            "monitoring_requests": old_payload.get("monitoring", []),
            "monitoring_request_versions": [],
            "mio_components": [],
            "mio_ssp_summary": [],
            "monitoring_logs": [],
            "closeout_requests": [],
        }
except Exception as exc:
    show_incident(exc, context="Розпакування архівного знімка")
    render_footer()
    st.stop()

st.markdown(
    f"""
    <div style="background:#fff3cd;border:1px solid #f1c40f;border-radius:12px;padding:14px 16px;margin:12px 0 18px 0;font-weight:800;color:#664d03;">
        Ви переглядаєте архівний знімок від {format_kyiv(snapshot.get('archived_at'))}. Дані незмінні.
    </div>
    """,
    unsafe_allow_html=True,
)

newer = replacement_map.get(int(selected_id))
if newer:
    st.warning(
        f"Є новіша версія від {format_kyiv(newer.get('archived_at'))}: "
        f"знімок №{int(newer.get('id'))}."
    )

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Тип", "Автоматичний" if snapshot.get("snapshot_type") == "automatic" else "Ручний")
with col2:
    st.metric("Заявок", int(snapshot.get("request_count") or 0))
with col3:
    st.metric("Заходів", int(snapshot.get("measure_count") or 0))
with col4:
    st.metric("Записів журналу", int(snapshot.get("log_count") or 0))

st.caption(
    " · ".join([
        f"Рядків структури: {int(snapshot.get('structure_row_count') or 0)}",
        f"Версій заявок: {int(snapshot.get('version_count') or 0)}",
        f"Розрахункових записів МіО: {int(snapshot.get('mio_record_count') or 0)}",
        f"Ручних закриттів: {int(snapshot.get('closeout_count') or 0)}",
        f"Версій ручних закриттів: {int(snapshot.get('closeout_version_count') or 0)}",
    ])
)

st.markdown(
    f"""
**Хто створив:** {snapshot.get('archived_by') or '—'}  
**Дата й час:** {format_kyiv(snapshot.get('archived_at'))}  
**Охоплені періоди:** {snapshot.get('coverage_label') or '—'}  
**Причина:** {snapshot.get('reason') or '—'}  
**Розмір стиснених даних:** {round((snapshot.get('payload_size_bytes') or 0) / 1024, 1)} КБ
"""
)

if snapshot.get("replaces_snapshot_id"):
    st.info(
        f"Цей знімок замінює знімок №{snapshot.get('replaces_snapshot_id')}. "
        f"Причина заміни: {snapshot.get('replacement_reason') or '—'}"
    )

st.markdown("### Вивантаження")
export_name = f"archive_snapshot_{selected_id}"
try:
    excel_bytes = export_snapshot_excel(snapshot, payload)
    docx_bytes = export_snapshot_docx(snapshot, payload)
    pdf_bytes = export_snapshot_pdf(snapshot, payload)
    e1, e2, e3 = st.columns(3)
    with e1:
        st.download_button(
            "Завантажити Excel",
            excel_bytes,
            file_name=f"{export_name}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with e2:
        st.download_button(
            "Завантажити Word",
            docx_bytes,
            file_name=f"{export_name}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    with e3:
        st.download_button(
            "Завантажити PDF",
            pdf_bytes,
            file_name=f"{export_name}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
except Exception as exc:
    show_incident(exc, context="Формування вивантажень архівного знімка")


def show_table(title: str, key: str, empty_message: str) -> None:
    st.markdown(f"### {title}")
    frame = pd.DataFrame(payload.get(key, []) or [])
    if frame.empty:
        st.info(empty_message)
    else:
        st.dataframe(frame, use_container_width=True, hide_index=True)


tab_main, tab_requests, tab_mio, tab_logs = st.tabs(
    ["Головна", "Заявки", "Оцінка МіО", "Журнал"]
)

with tab_main:
    show_table("Структура стратегічного плану", "main_table", "У знімку немає структури стратегічного плану.")

with tab_requests:
    show_table("Заявки на момент архівації", "monitoring_requests", "У знімку немає заявок.")
    with st.expander("Версії заявок", expanded=False):
        frame = pd.DataFrame(payload.get("monitoring_request_versions", []) or [])
        if frame.empty:
            st.info("У знімку немає версій заявок.")
        else:
            st.dataframe(frame, use_container_width=True, hide_index=True)

with tab_mio:
    show_table("Оцінки МіО по ССП", "mio_ssp_summary", "У знімку немає розрахованих оцінок МіО.")
    with st.expander("Розрахункові складові", expanded=False):
        frame = pd.DataFrame(payload.get("mio_components", []) or [])
        if frame.empty:
            st.info("У знімку немає розрахункових складових МіО.")
        else:
            st.dataframe(frame, use_container_width=True, hide_index=True)

with tab_logs:
    show_table("Повний журнал дій", "monitoring_logs", "У знімку немає записів журналу.")

render_footer()
