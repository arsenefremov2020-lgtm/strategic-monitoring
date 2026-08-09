"""Компактний тестовий варіант Картки заходу.

Сторінка існує паралельно з основною ``4_Картка_заходу.py`` і не замінює її.
Вона використовує ті самі джерела даних та спільні резолвери, але подає
інформацію щільніше для швидкого управлінського перегляду.
"""

from __future__ import annotations

from html import escape
import re

import pandas as pd
import streamlit as st

from core import monitoring_data, operational
from core.access import filter_actions_for_user, filter_requests_for_user
from core.closeouts import append_confirmed_closeout_facts
from core.page_setup import page_setup, render_footer
from core.periods import period_number
from core.strategic_data import load_strat_matrix, raw_value
from core.ui import load_css, render_readonly_table, render_scope_toggle
from core.versioning import load_versions


PAGE_KEY = "measure_card_test"
QUARTERS = ("I", "II", "III", "IV")


def _clean(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "nat"} else text


def _ssp_index(value) -> str:
    match = re.search(r"\d+", _clean(value))
    return match.group(0) if match else _clean(value)


def _status_class(status: str) -> str:
    status = _clean(status)
    if status == "Виконано":
        return "ok"
    if status == "Частково виконано":
        return "partial"
    if status == "Не виконано":
        return "bad"
    if status in {"Не настав час", "Втратило актуальність", "Не подано"}:
        return "neutral"
    return "pending"


def _value(row: pd.Series | dict | None) -> str:
    if row is None:
        return "—"
    getter = row.get
    numeric = _clean(getter("numeric_value", ""))
    if numeric:
        return numeric
    text = _clean(getter("value_text", ""))
    return text or "—"


def _latest_snapshot_request(frame: pd.DataFrame, year: int, quarter: str) -> pd.Series | None:
    if frame is None or frame.empty:
        return None
    data = frame.copy()
    for col in ("year", "quarter", "approval_status", "submitted_at", "updated_at", "id"):
        if col not in data.columns:
            data[col] = ""
    data = data[data["approval_status"].astype(str).str.strip() == "Погоджено"].copy()
    if data.empty:
        return None
    snapshot_no = period_number(year, quarter)
    data["_period_no"] = data.apply(
        lambda row: period_number(row.get("year"), row.get("quarter")), axis=1
    )
    data = data[data["_period_no"] <= snapshot_no].copy()
    if data.empty:
        return None
    data["_sort_ts"] = data["updated_at"].astype(str)
    data.loc[data["_sort_ts"].str.strip() == "", "_sort_ts"] = data["submitted_at"].astype(str)
    data["_sort_id"] = pd.to_numeric(data["id"], errors="coerce").fillna(-1)
    return data.sort_values(["_period_no", "_sort_ts", "_sort_id"]).iloc[-1]


def _quarter_request(frame: pd.DataFrame, year: int, quarter: str) -> pd.Series | None:
    if frame is None or frame.empty:
        return None
    data = frame.copy()
    year_series = pd.to_numeric(data.get("year", pd.Series(index=data.index)), errors="coerce")
    quarter_series = data.get("quarter", pd.Series("", index=data.index)).astype(str).str.strip()
    data = data[(year_series == int(year)) & (quarter_series == quarter)].copy()
    if data.empty:
        return None
    data["_approved"] = data.get("approval_status", "").astype(str).str.strip().eq("Погоджено")
    data["_sort_ts"] = data.get("updated_at", "").astype(str)
    if "submitted_at" in data.columns:
        data.loc[data["_sort_ts"].str.strip() == "", "_sort_ts"] = data["submitted_at"].astype(str)
    data["_sort_id"] = pd.to_numeric(data.get("id", ""), errors="coerce").fillna(-1)
    return data.sort_values(["_approved", "_sort_ts", "_sort_id"]).iloc[-1]


current_user = page_setup("Картка заходу (тест)", page_name="Картка заходу (тест)")
load_css()

st.markdown(
    """
<style>
.main .block-container {max-width: 1500px; padding-top: .8rem;}
.test-hero {background:#fff;border:1px solid #DCE4F0;border-radius:14px;padding:16px 18px;margin-bottom:12px;}
.test-kicker {font-size:12px;font-weight:800;color:#005BBB;text-transform:uppercase;letter-spacing:.04em;}
.test-title {font-size:25px;line-height:1.2;font-weight:950;color:#132238;margin:4px 0 6px;}
.test-sub {font-size:13px;color:#61708A;line-height:1.45;}
.chips {display:flex;gap:7px;flex-wrap:wrap;margin:10px 0 12px;}
.chip {border:1px solid #DCE4F0;background:#F7F9FC;border-radius:999px;padding:6px 9px;font-size:12px;font-weight:800;color:#334155;}
.chip.ok {background:#E4F5EC;border-color:#9FD7B7;color:#0C713A;}
.chip.partial {background:#FFF6D8;border-color:#E8C75B;color:#7C5B00;}
.chip.bad {background:#FDE8E8;border-color:#EAB3B3;color:#A52A2A;}
.chip.pending {background:#EAF1FF;border-color:#BFD3F2;color:#005BBB;}
.compact-card {background:#fff;border:1px solid #DCE4F0;border-radius:13px;padding:13px 15px;height:100%;}
.compact-title {font-size:14px;font-weight:900;color:#132238;margin-bottom:8px;}
.kv {display:grid;grid-template-columns:minmax(120px,.35fr) 1fr;gap:5px 10px;font-size:12.5px;line-height:1.4;}
.k {color:#64748B;font-weight:700;}.v {color:#132238;font-weight:650;overflow-wrap:anywhere;}
.quarter-grid {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:10px 0 14px;}
.qcard {background:#fff;border:1px solid #DCE4F0;border-radius:12px;padding:11px 12px;min-height:112px;}
.qtitle {font-size:13px;font-weight:950;color:#132238}.qfact {font-size:20px;font-weight:950;color:#005BBB;margin:5px 0}.qmeta {font-size:11.5px;color:#64748B;line-height:1.35}
@media (max-width:900px){.quarter-grid{grid-template-columns:repeat(2,minmax(0,1fr));}}
</style>
""",
    unsafe_allow_html=True,
)

render_scope_toggle(PAGE_KEY, current_user)

strat = load_strat_matrix()
measures = strat[strat.get("object_type", "").astype(str) == "measure"].copy()
measures = filter_actions_for_user(measures, current_user, page_key=PAGE_KEY)
if measures.empty:
    st.warning("Немає доступних заходів для перегляду.")
    render_footer()
    st.stop()

measures["_label"] = measures.apply(
    lambda row: f"{_clean(row.get('code'))} — {_clean(row.get('name'))}", axis=1
)
measures = measures.sort_values("code", key=lambda s: s.astype(str))

with st.container(border=True):
    c1, c2, c3, c4 = st.columns([4.4, 1, 1, 1.45])
    with c1:
        selected_label = st.selectbox("Захід", measures["_label"].tolist(), key="card_test_measure")
    with c2:
        selected_year = st.selectbox("Рік", [2026, 2027, 2028], key="card_test_year")
    with c3:
        selected_quarter = st.selectbox("Квартал", list(QUARTERS), index=3, key="card_test_quarter")
    with c4:
        data_mode = st.selectbox("Дані", list(operational.MODE_OPTIONS), key="card_test_mode")

selected_code = selected_label.split(" — ", 1)[0].strip()
measure_row = measures[measures["code"].astype(str).str.strip() == selected_code].iloc[0]

requests = monitoring_data.measures_only(monitoring_data.load_monitoring_requests_live())
requests = filter_requests_for_user(requests, current_user, page_key=PAGE_KEY)
measure_requests = requests[requests.get("strat_code", "").astype(str).str.strip() == selected_code].copy()
if data_mode == operational.MODE_OPERATIONAL and not measure_requests.empty:
    targets = operational.build_target_map(strat)
    measure_requests, _ = operational.apply_operational_mode(measure_requests, targets)
measure_requests = append_confirmed_closeout_facts(measure_requests)

latest = _latest_snapshot_request(measure_requests, int(selected_year), selected_quarter)
target_col = f"target_{selected_year}"
target = _clean(measure_row.get(target_col, "")) or "—"
status = _clean(latest.get("status")) if latest is not None else "Не подано"
fact = _value(latest)
approval = _clean(latest.get("approval_status")) if latest is not None else "Не подано"
ssp = _ssp_index(measure_row.get("resp_main", "")) or "—"

st.markdown(
    f"""
<div class="test-hero">
  <div class="test-kicker">Картка заходу · тестовий компактний макет</div>
  <div class="test-title">{escape(selected_code)} · {escape(_clean(measure_row.get('name')))}</div>
  <div class="test-sub">Станом на {escape(str(selected_quarter))} квартал {selected_year} року. Основна Картка заходу залишається окремою сторінкою.</div>
  <div class="chips">
    <span class="chip {_status_class(status)}">{escape(status)}</span>
    <span class="chip">Факт: {escape(fact)}</span>
    <span class="chip">План {selected_year}: {escape(target)}</span>
    <span class="chip">{escape(selected_quarter)} кв. {selected_year}</span>
    <span class="chip pending">Погодження: {escape(approval)}</span>
    <span class="chip">ССП {escape(ssp)}</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

left, right = st.columns([1.25, 1], gap="small")
with left:
    goal = _clean(measure_row.get("parent_goal_name", ""))
    task = _clean(measure_row.get("parent_task_name", ""))
    st.markdown(
        f"""
<div class="compact-card"><div class="compact-title">Паспорт заходу</div><div class="kv">
<div class="k">Стратегічна ціль</div><div class="v">{escape(goal or '—')}</div>
<div class="k">Завдання</div><div class="v">{escape(task or '—')}</div>
<div class="k">Індикатор</div><div class="v">{escape(_clean(measure_row.get('indicator')) or '—')}</div>
<div class="k">Одиниця</div><div class="v">{escape(_clean(measure_row.get('unit')) or '—')}</div>
<div class="k">Головний виконавець</div><div class="v">{escape(_clean(measure_row.get('resp_main')) or '—')}</div>
<div class="k">Співвиконавець</div><div class="v">{escape(_clean(measure_row.get('resp_co_1')) or '—')}</div>
<div class="k">Період</div><div class="v">{escape(_clean(measure_row.get('start_period')) or '—')} — {escape(_clean(measure_row.get('end_period')) or '—')}</div>
</div></div>
""",
        unsafe_allow_html=True,
    )
with right:
    progress = _clean(latest.get("progress_text")) if latest is not None else ""
    risks = _clean(latest.get("risks")) if latest is not None else ""
    submitted = _clean(latest.get("updated_at")) if latest is not None else ""
    if not submitted and latest is not None:
        submitted = _clean(latest.get("submitted_at"))
    st.markdown(
        f"""
<div class="compact-card"><div class="compact-title">Поточний стан</div><div class="kv">
<div class="k">Фактичний статус</div><div class="v">{escape(status)}</div>
<div class="k">Факт</div><div class="v">{escape(fact)}</div>
<div class="k">План</div><div class="v">{escape(target)}</div>
<div class="k">Опис прогресу</div><div class="v">{escape(progress or '—')}</div>
<div class="k">Ризики</div><div class="v">{escape(risks or '—')}</div>
<div class="k">Останнє оновлення</div><div class="v">{escape(submitted or '—')}</div>
</div></div>
""",
        unsafe_allow_html=True,
    )

q_html = []
for q in QUARTERS:
    qrow = _quarter_request(measure_requests, int(selected_year), q)
    qstatus = _clean(qrow.get("status")) if qrow is not None else "Не подано"
    qfact = _value(qrow)
    qapproval = _clean(qrow.get("approval_status")) if qrow is not None else "Не подано"
    q_html.append(
        f'<div class="qcard"><div class="qtitle">{q} квартал</div>'
        f'<div class="qfact">{escape(qfact)}</div>'
        f'<div class="qmeta">{escape(qstatus)}<br>{escape(qapproval)}</div></div>'
    )
st.markdown('<div class="quarter-grid">' + ''.join(q_html) + '</div>', unsafe_allow_html=True)

with st.expander("Історія подань", expanded=False):
    if measure_requests.empty:
        st.info("Подань за заходом ще немає.")
    else:
        history_cols = [
            col for col in ["year", "quarter", "status", "numeric_value", "value_text", "approval_status", "submitted_at", "progress_text", "risks"]
            if col in measure_requests.columns
        ]
        history = measure_requests[history_cols].copy()
        history = history.sort_values([c for c in ["year", "quarter", "submitted_at"] if c in history.columns])
        render_readonly_table(history, height=285, compact=True)

with st.expander("Фінансування", expanded=False):
    finance_fields = {
        "КПКВК": ["budget_kpkvk"],
        "Бюджет 2026 (затверджено)": ["budget_2026_approved"],
        "Бюджет 2027 (прогноз)": ["budget_2027_forecast"],
        "Бюджет 2028 (прогноз)": ["budget_2028_forecast"],
        "Інше джерело": ["other_source"],
        "Інше 2026 (план)": ["other_2026_plan"],
        "Інше 2027 (прогноз)": ["other_2027_forecast"],
        "Інше 2028 (прогноз)": ["other_2028_forecast"],
    }
    rows = []
    for title, candidates in finance_fields.items():
        value = next((_clean(measure_row.get(name)) for name in candidates if name in measure_row.index and _clean(measure_row.get(name))), "")
        rows.append({"Показник": title, "Значення": value or "—"})
    render_readonly_table(pd.DataFrame(rows), height=185, compact=True)

with st.expander("НПА", expanded=False):
    npa_rows = []
    if "npa_link" in measure_requests.columns:
        for _, r in measure_requests[measure_requests["npa_link"].astype(str).str.strip() != ""].iterrows():
            npa_rows.append({"Рік": r.get("year"), "Квартал": r.get("quarter"), "Посилання": r.get("npa_link")})
    if npa_rows:
        render_readonly_table(pd.DataFrame(npa_rows), height=220, compact=True)
    else:
        st.caption("Посилань на НПА у поданнях немає.")

with st.expander("Версії", expanded=False):
    request_id = latest.get("id") if latest is not None else None
    if request_id is not None:
        try:
            rid = int(float(str(request_id)))
        except Exception:
            rid = 0
        if rid > 0:
            versions = load_versions(rid)
            if versions is not None and not versions.empty:
                render_readonly_table(versions, height=300, compact=True)
            else:
                st.caption("Версій для вибраної заявки немає.")
        else:
            st.caption("Поточний стан сформовано з ручного закриття; окремої monitoring-версії немає.")
    else:
        st.caption("Немає заявки для перегляду версій.")

with st.expander("Файли", expanded=False):
    if latest is None:
        st.caption("Файлів немає.")
    else:
        names = _clean(latest.get("file_names"))
        urls = _clean(latest.get("file_urls"))
        if not names and not urls:
            st.caption("Файлів немає.")
        else:
            st.write(names or "Прикріплені файли")
            if urls:
                st.write(urls)

with st.expander("Методологія відображення", expanded=False):
    st.markdown(
        """
- Картка показує стан **не пізніше обраного року і кварталу**.
- Офіційний факт береться з погоджених подань; в оперативному режимі — зі спільного operational-resolver.
- Підтверджене ручне закриття враховується за **реально зафіксованим** фактом і статусом, а не автоматично як «Виконано».
- План підтягується з `target_{обраний рік}`.
- Ця сторінка є тестовим компактним варіантом; основна Картка заходу залишається доступною окремо.
"""
    )

render_footer()
