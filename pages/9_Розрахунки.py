from __future__ import annotations

"""Службова read-only сторінка прозорості методології.

LIGHT-режим зберігає попередній принцип сторінки: важкі контури запускаються
лише для обраного розділу. Dashboard і МіО показуються за їхньою чинною shared
методологією. Розділ Analytics відображає актуальний контракт: execution —
точний останній обраний період; coverage — середнє за діапазон + точний latest;
управлінська увага — тільки latest snapshot із quarter-aware семантикою.
"""

from typing import Any

import pandas as pd
import streamlit as st

from core.page_setup import page_setup, render_footer
from core.access import is_super_admin_user
from core.strategic_data import load_strat_matrix
from core import monitoring_data
from core.closeouts import append_confirmed_closeout_facts
from core import analytics_calculations
from core import mio_shared
from core import dashboard_sources
from core.analytics_text import build_context as build_analytics_text_context
from core.dashboard_breakdowns import build_period_results, aggregate_plan, ssp_summary, deputy_summary
from core.dashboard_risk import attention_mask, risk_summary
from core.dashboard_finance import build_finance_frame, finance_kpis


YEAR = 2026
QUARTERS = ["I", "II", "III", "IV"]
LATEST_QUARTER = "IV"
PAIRS = [(YEAR, q) for q in QUARTERS]
LATEST_KEY = (YEAR, LATEST_QUARTER)
TOL = 0.05


current_user = page_setup("Розрахунки", page_name=None)
if not is_super_admin_user(current_user):
    st.error("Сторінка «Розрахунки» доступна лише супер-адміністратору.")
    st.stop()

st.markdown(
    """
<style>
.main .block-container {max-width:1380px;padding-top:1.2rem;padding-bottom:3rem;}
.calc-hero {background:#fff;border:1px solid #DCE4F0;border-radius:16px;padding:20px 24px;margin:4px 0 16px;box-shadow:0 6px 20px rgba(15,23,42,.05);}
.calc-hero-title {color:#132238;font-size:30px;font-weight:900;line-height:1.15;margin-bottom:7px;}
.calc-hero-subtitle,.calc-section-note {color:#61708A;font-size:14px;line-height:1.55;}
.calc-section-title {color:#132238;font-size:23px;font-weight:900;line-height:1.25;margin:1.4rem 0 .45rem;}
.calc-callout {background:#F7F9FC;border:1px solid #DCE4F0;border-left:5px solid #005BBB;border-radius:12px;padding:13px 16px;margin:10px 0 16px;color:#34445C;line-height:1.55;}
.calc-warning {background:#FFF8E6;border-color:#F4B400;border-left-color:#F4B400;}
div[data-testid="stMetric"] {background:#fff;border:1px solid #DCE4F0;border-radius:12px;padding:8px 12px;}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="calc-hero">
  <div class="calc-hero-title">Розрахунки</div>
  <div class="calc-hero-subtitle">
    Службова сторінка прозорості методології. Dashboard і МіО тут не
    переобчислюються за альтернативними формулами. Analytics показує нову
    семантику exact-latest execution, двох coverage-показників та latest-only
    управлінської уваги.
  </div>
</div>
""",
    unsafe_allow_html=True,
)
st.caption("LIGHT · обчислення за вимогою")


def _num(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _int(value: Any) -> int:
    number = _num(value)
    return 0 if number is None else int(number)


def _pct(value: Any, digits: int = 1) -> str:
    number = _num(value)
    return "—" if number is None else f"{number:.{digits}f}%"


def _pp(value: Any, digits: int = 1) -> str:
    number = _num(value)
    if number is None:
        return "—"
    return f"{'+' if number > 0 else ''}{number:.{digits}f} в.п."


def _n(value: Any, digits: int = 2) -> str:
    number = _num(value)
    if number is None:
        return "—"
    if abs(number - round(number)) < 1e-10:
        return f"{int(round(number)):,}".replace(",", " ")
    return f"{number:,.{digits}f}".replace(",", " ").rstrip("0").rstrip(".")


def _mean(values) -> float | None:
    series = pd.to_numeric(pd.Series(list(values)), errors="coerce").dropna()
    return None if series.empty else float(series.mean())


def _parity_text(a: Any, b: Any) -> str:
    return "ЗБІГАЄТЬСЯ" if _close(a, b) else "ВІДРІЗНЯЄТЬСЯ"


def _safe_bool(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=bool)
    if column not in frame.columns:
        return pd.Series(False, index=frame.index, dtype=bool)
    return frame[column].fillna(False).astype(bool)


def _safe_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _close(a: Any, b: Any, tol: float = TOL) -> bool:
    aa, bb = _num(a), _num(b)
    if aa is None or bb is None:
        return aa is None and bb is None
    return abs(aa - bb) <= tol


def _section(title: str, note: str | None = None) -> None:
    st.markdown(f'<div class="calc-section-title">{title}</div>', unsafe_allow_html=True)
    if note:
        st.markdown(f'<div class="calc-section-note">{note}</div>', unsafe_allow_html=True)


def _callout(text: str, *, warning: bool = False) -> None:
    cls = "calc-callout calc-warning" if warning else "calc-callout"
    st.markdown(f'<div class="{cls}">{text}</div>', unsafe_allow_html=True)


def _display_cell_text(value: Any) -> str:
    """Перетворює будь-яке службове значення на простий текст для st.dataframe."""
    if value is None:
        return ""
    if isinstance(value, tuple):
        if len(value) == 2:
            try:
                year = int(float(value[0])); quarter = str(value[1]).strip()
                if quarter in QUARTERS:
                    return f"{quarter} кв. {year}"
            except (TypeError, ValueError):
                pass
        return " · ".join(_display_cell_text(v) for v in value)
    if isinstance(value, list):
        return "; ".join(_display_cell_text(v) for v in value)
    if isinstance(value, set):
        return "; ".join(sorted(_display_cell_text(v) for v in value))
    if isinstance(value, dict):
        return "; ".join(f"{_display_cell_text(k)}: {_display_cell_text(v)}" for k, v in value.items())
    try:
        missing = pd.isna(value)
        if isinstance(missing, bool) and missing:
            return ""
        if type(missing).__name__ == "bool_" and bool(missing):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.strftime("%d.%m.%Y %H:%M:%S")
    return str(value)


def _safe_display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Display-only копія: усі колонки і значення строкові та Arrow-safe."""
    safe = frame.copy()
    names = []; used: dict[str, int] = {}
    for idx, column in enumerate(safe.columns, start=1):
        base = _display_cell_text(column).strip() or f"Колонка {idx}"
        count = used.get(base, 0); used[base] = count + 1
        names.append(base if count == 0 else f"{base} ({count + 1})")
    safe.columns = names
    for column in safe.columns:
        safe[column] = safe[column].map(_display_cell_text).astype("string")
    return safe


def _display_df(frame: pd.DataFrame, *, max_height: int = 430, max_rows: int | None = None) -> None:
    if frame is None or frame.empty:
        st.caption("Немає рядків для відображення."); return
    data = frame
    if max_rows is not None and len(data) > max_rows:
        st.caption(f"Для швидкого перегляду показано перші {max_rows} із {len(data)} рядків. Розрахунок виконується по повному масиву.")
        data = data.head(max_rows).copy()
    display = _safe_display_frame(data)
    visible_rows = min(len(display), 10)
    height = min(max_height, max(120, 38 * (visible_rows + 1) + 12))
    try:
        st.dataframe(display, use_container_width=True, height=height, hide_index=True)
    except Exception as exc:
        st.warning(f"Таблицю не вдалося відобразити інтерактивно: {type(exc).__name__}.")
        st.code(display.head(40).to_string(index=False), language="text")


def _show_formula(title: str, *, meaning: str, population: str, formula: str, result: str, interpretation: str, substitution: str | None = None, caveat: str | None = None) -> None:
    st.markdown(f"#### {title}")
    st.markdown(f"**Що означає показник.** {meaning}")
    st.markdown(f"**Хто входить у розрахунок.** {population}")
    st.markdown(f"**Формула / правило.** `{formula}`")
    if substitution:
        st.markdown(f"**Підстановка поточних даних.** {substitution}")
    st.markdown(f"**Поточний результат.** **{result}**")
    st.markdown(f"**Як читати результат.** {interpretation}")
    if caveat:
        _callout(f"<b>Важливо.</b> {caveat}", warning=True)


def _load_base_data():
    strat_df = load_strat_matrix()
    all_monitoring = monitoring_data.load_monitoring_requests()
    measures = monitoring_data.measures_only(all_monitoring)
    measures = append_confirmed_closeout_facts(measures, include_incomplete=True)
    return strat_df, all_monitoring, measures


def _build_dashboard_context(strat_df: pd.DataFrame, measure_requests: pd.DataFrame):
    period_sources = dashboard_sources.build_period_source_overrides(PAIRS, operational_mode=False)
    results = build_period_results(strat_df, measure_requests, PAIRS, period_sources=period_sources)
    aggregate = aggregate_plan(results)
    latest = results.get(LATEST_KEY, {})
    snapshot = latest.get("snapshot", pd.DataFrame())
    rsum = latest.get("risk_summary") or risk_summary(snapshot)
    return period_sources, results, aggregate, latest, snapshot, rsum


def _build_analytics_context(strat_df: pd.DataFrame, measure_requests: pd.DataFrame):
    results, active = analytics_calculations.prepare_analysis_context(strat_df, measure_requests, [YEAR], QUARTERS)
    plan = analytics_calculations.build_analytics_plan_summary(results)
    metrics = analytics_calculations.build_metrics(active, results)
    metrics.update({
        "completion": plan.get("execution_by_measures"),
        "completion_change": plan.get("execution_by_measures_change"),
        "goal_completion": plan.get("execution_by_goals"),
        "goal_completion_change": plan.get("execution_by_goals_change"),
        "coverage": plan.get("coverage_average"),
        "coverage_latest": plan.get("coverage_latest"),
        "coverage_change": plan.get("coverage_change"),
        "latest_period": plan.get("latest_period"),
        "latest_risk_summary": plan.get("latest_risk_summary") or {},
    })
    return results, active, plan, metrics


def _quarter_result_table(results: dict) -> pd.DataFrame:
    rows = []
    for q in QUARTERS:
        item = results.get((YEAR, q), {})
        snap = item.get("snapshot", pd.DataFrame())
        rows.append({
            "Квартал": q,
            "Унікальних заходів": snap["code"].nunique() if isinstance(snap, pd.DataFrame) and not snap.empty and "code" in snap.columns else 0,
            "Виконання за заходами, %": item.get("execution_by_measures"),
            "Виконання за цілями, %": item.get("execution_by_goals"),
            "Покриття, %": item.get("coverage"),
        })
    return pd.DataFrame(rows)


def _status_counts(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty or "status" not in frame.columns:
        return pd.DataFrame(columns=["status", "Кількість"])
    return frame["status"].fillna("—").astype(str).value_counts().rename_axis("status").reset_index(name="Кількість")


def _reason_table(snapshot: pd.DataFrame, *, analytics_mode: bool = False) -> pd.DataFrame:
    """Diagnostic reasons; Analytics mode uses the quarter-aware latest-only contract."""
    if snapshot is None or snapshot.empty:
        return pd.DataFrame()
    if analytics_mode:
        quarter = str(snapshot.get("quarter", pd.Series([LATEST_QUARTER])).iloc[0])
        mask = analytics_calculations.management_attention_mask(snapshot, quarter)
        label = analytics_calculations.attention_semantics(quarter)["label"]
        return pd.DataFrame([{
            "Причина": label,
            "Кількість унікальних заходів": int(snapshot.loc[mask, "code"].nunique()) if "code" in snapshot.columns else int(mask.sum()),
        }])
    risk_level = snapshot.get("risk_level", pd.Series("", index=snapshot.index, dtype=object)).astype(str)
    final_failure = (
        snapshot.get("forecast_kind", pd.Series("", index=snapshot.index, dtype=object)).astype(str).eq("final")
        & ~_safe_bool(snapshot, "result_achieved")
    )
    reasons = {
        "Високий або критичний ризик": risk_level.isin(["Високий ризик", "Критичний ризик"]),
        "Попередній сигнал уваги": _safe_bool(snapshot, "preliminary_attention"),
        "Немає обов'язкового подання за квартал": _safe_bool(snapshot, "missing_required_submission"),
        "Захід завершився без фінального результату": _safe_bool(snapshot, "final_missing_result"),
        "Конфлікт якості даних": _safe_bool(snapshot, "data_quality_conflict"),
        "Фінальний результат не досягнуто": final_failure,
    }
    rows = [{"Причина": label, "Кількість": int(mask.fillna(False).sum())} for label, mask in reasons.items()]
    union = attention_mask(snapshot).reindex(snapshot.index, fill_value=False)
    rows.append({"Причина": "Унікальний UNION Dashboard: потребує уваги хоча б з однієї причини", "Кількість": int(union.sum())})
    return pd.DataFrame(rows)


section = st.radio(
    "Що показати",
    ["Огляд", "Dashboard — розрахунки", "Аналітика — розрахунки", "Графіки Аналітики", "Показники аналітичної довідки", "Технічна звірка"],
    horizontal=True,
    key="calc_light_section",
)

if section == "Огляд":
    _section(
        "Як користуватися сторінкою",
        "LIGHT-режим збережено: розрахунок запускається лише для обраного контуру, а великі таблиці відкриваються окремо.",
    )
    overview = pd.DataFrame([
        {"Розділ":"Dashboard — розрахунки","Що пояснює":"snapshot кварталу, execution_score, покриття, ієрархічну агрегацію, ризик, динаміку","Важкість":"середня"},
        {"Розділ":"Аналітика — розрахунки","Що пояснює":"exact-latest execution, dual coverage, current quarter-aware attention, історичну динаміку","Важкість":"середня"},
        {"Розділ":"Графіки Аналітики","Що пояснює":"назву графіка, осі, одиницю спостереження та правильну інтерпретацію","Важкість":"дуже легка — без БД"},
        {"Розділ":"Показники аналітичної довідки","Що пояснює":"prepared factual metrics і provenance; registry будується лише за вимогою","Важкість":"легка / важка лише для registry"},
        {"Розділ":"Технічна звірка","Що пояснює":"Dashboard vs Analytics по кварталах і джерелах","Важкість":"середня"},
    ])
    _display_df(overview, max_height=320)
    _callout(
        "<b>Головний принцип.</b> Shared Dashboard і МіО не переписані. Analytics лише інтерпретує їхні prepared outputs за новим контрактом: exact latest execution, dual coverage та latest-only управлінська увага."
    )

elif section == "Dashboard — розрахунки":
    with st.spinner("Формую Dashboard-контекст..."):
        try:
            strat_df, _, measures = _load_base_data()
            period_sources, results, aggregate, latest, snapshot, rsum = _build_dashboard_context(strat_df, measures)
        except Exception as exc:
            st.exception(exc); st.stop()

    _section("1. Джерело даних за кварталами", "Dashboard використовує чинний archive resolver; історичний квартал може мати архівне або live-джерело.")
    source_rows=[]
    for q in QUARTERS:
        key=(YEAR,q); item=results.get(key,{}); snap=item.get("snapshot",pd.DataFrame())
        source_rows.append({
            "Квартал":q,
            "Джерело":"Архівний snapshot" if key in period_sources else "Поточні live-дані",
            "Унікальних заходів":snap["code"].nunique() if isinstance(snap,pd.DataFrame) and not snap.empty and "code" in snap.columns else 0,
            "Виконання, %":item.get("execution_by_measures"),
            "Виконання за цілями, %":item.get("execution_by_goals"),
            "Покриття, %":item.get("coverage"),
        })
    _display_df(pd.DataFrame(source_rows), max_height=280)

    _section("2. Як формується IV квартал", "Спочатку визначається стан заходу та джерело факту, після цього формується execution_score.")
    if snapshot is None or snapshot.empty:
        st.error("Q4 snapshot порожній.")
    else:
        period_state=snapshot.get("period_state",pd.Series("",index=snapshot.index)).astype(str)
        snapshot_structure=pd.DataFrame([
            {"Категорія":"Усього рядків Q4 snapshot","Кількість":len(snapshot),"Пояснення":"один рядок = один захід у поточному Q4-зрізі"},
            {"Категорія":"Active","Кількість":int(period_state.eq("active").sum()),"Пояснення":"строк заходу охоплює IV квартал"},
            {"Категорія":"Ended","Кількість":int(period_state.eq("ended").sum()),"Пояснення":"захід завершився раніше"},
            {"Категорія":"Unknown period","Кількість":int(period_state.eq("unknown_period").sum()),"Пояснення":"строк неможливо однозначно визначити"},
            {"Категорія":"Подано саме за Q4","Кількість":int(_safe_bool(snapshot,"submitted_current_period").sum()),"Пояснення":"є поточне погоджене Q4-подання"},
            {"Категорія":"Carry-forward","Кількість":int(_safe_bool(snapshot,"carry_forward").sum()),"Пояснення":"для execution використано попередній підтверджений факт цього року"},
            {"Категорія":"Немає обов'язкового поточного подання","Кількість":int(_safe_bool(snapshot,"missing_required_submission").sum()),"Пояснення":"Q4-подання мало бути, але його немає"},
        ])
        _display_df(snapshot_structure,max_height=350)
        _callout("<b>Carry-forward не дорівнює новому поданню.</b> Попередній підтверджений факт може підтримати execution, але покриття Q4 від цього не стає кращим.")

        _section("3. Як захід отримує execution_score")
        score_rules=pd.DataFrame([
            {"Тип":"Числовий показник","Правило":"факт / річний план × 100","Бал":"0–100% у shared Dashboard"},
            {"Тип":"Так / Ні","Правило":"так = досягнуто; ні = не досягнуто","Бал":"100% / 0%"},
            {"Тип":"Якісний статус","Правило":"Виконано / Частково виконано / Не виконано / Не подано","Бал":"100% / 75% / 0% / 0%"},
            {"Тип":"Не настав час / Втратило актуальність","Правило":"не повинно штучно псувати середнє","Бал":"не входить у execution-середнє"},
            {"Тип":"Активний захід без підтвердженого результату","Правило":"дані мали бути, але їх немає","Бал":"за чинною shared-методологією"},
        ])
        _display_df(score_rules,max_height=300)

        assessed=snapshot[_safe_numeric(snapshot,"execution_score").notna()].copy()
        score_sum=_safe_numeric(assessed,"execution_score").sum(min_count=1)
        assessed_count=len(assessed)
        diagnostic_execution=None if assessed_count==0 or pd.isna(score_sum) else float(score_sum)/assessed_count
        _section("4. Головні KPI Q4")
        _show_formula(
            "Рівень виконання Стратегічного плану за заходами",
            meaning="Середній execution_score оцінених заходів IV кварталу.",
            population="Q4-заходи з непорожнім execution_score.",
            formula="сума execution_score / кількість оцінених заходів",
            substitution=f"{_n(score_sum)} / {assessed_count}" if assessed_count else "немає оцінених заходів",
            result=_pct(latest.get("execution_by_measures")),
            interpretation=f"Контрольний перерахунок = {_pct(diagnostic_execution)}; shared Dashboard = {_pct(latest.get('execution_by_measures'))} ({_parity_text(diagnostic_execution,latest.get('execution_by_measures'))}).",
            caveat="Це середнє за заходами, а не рівне зважування стратегічних цілей.",
        )
        coverage_pop=snapshot[_safe_bool(snapshot,"coverage_eligible")].copy(); coverage_den=len(coverage_pop); coverage_num=int(_safe_bool(coverage_pop,"submitted").sum())
        diagnostic_coverage=None if coverage_den==0 else coverage_num/coverage_den*100.0
        _show_formula(
            "Покриття моніторингом",
            meaning="Частка заходів, які повинні були податися саме в Q4 і мають поточне подання.",
            population="coverage_eligible заходи IV кварталу.",
            formula="поточні Q4-подання / coverage_eligible × 100",
            substitution=f"{coverage_num} / {coverage_den} × 100",
            result=_pct(latest.get("coverage")),
            interpretation=f"Контрольний перерахунок = {_pct(diagnostic_coverage)}.",
            caveat="Високе execution не гарантує високе покриття: carry-forward може підтримати перше, але не друге.",
        )
        goal_scores=latest.get("goal_scores",pd.DataFrame()); task_scores=latest.get("task_scores",pd.DataFrame())
        if isinstance(goal_scores,pd.DataFrame) and not goal_scores.empty:
            goal_by_tasks=_safe_numeric(goal_scores,"by_tasks").dropna(); diagnostic_goal=None if goal_by_tasks.empty else float(goal_by_tasks.mean())
            _show_formula(
                "Виконання за стратегічними цілями",
                meaning="Рівне зважування оцінених стратегічних цілей через ланцюжок заходи → завдання → ціль.",
                population="Цілі з розрахованим by_tasks.",
                formula="сума by_tasks цілей / кількість оцінених цілей",
                substitution=f"{_n(goal_by_tasks.sum())} / {len(goal_by_tasks)}" if len(goal_by_tasks) else "немає оцінених цілей",
                result=_pct(latest.get("execution_by_goals")),
                interpretation=f"Контрольний перерахунок = {_pct(diagnostic_goal)}.",
                caveat="Цей KPI закономірно може відрізнятися від простого середнього всіх заходів.",
            )

        _section("5. Ризик і потреба в увазі")
        dash_attention=attention_mask(snapshot).reindex(snapshot.index,fill_value=False)
        st.markdown(f"**Потребують уваги в Q4 за Dashboard-mask: {int(dash_attention.sum())} рядків.**")
        _display_df(_reason_table(snapshot),max_height=320)

        _section("6. Динаміка I–IV та часова семантика")
        _display_df(_quarter_result_table(results),max_height=280)
        aggregate_view=pd.DataFrame([
            {"Показник":"Виконання за заходами","Average I–IV":aggregate.get("execution_by_measures_average"),"Latest":aggregate.get("execution_by_measures_latest"),"Change":aggregate.get("execution_by_measures_change")},
            {"Показник":"Виконання за цілями","Average I–IV":aggregate.get("execution_by_goals_average"),"Latest":aggregate.get("execution_by_goals_latest"),"Change":aggregate.get("execution_by_goals_change")},
            {"Показник":"Покриття","Average I–IV":aggregate.get("coverage_average"),"Latest":aggregate.get("coverage_latest"),"Change":aggregate.get("coverage_change")},
        ])
        _display_df(aggregate_view,max_height=250)
        _callout("`average` / `latest` / `change` у цьому блоці — саме shared Dashboard contract. Analytics нижче має окрему семантику execution.")

        st.markdown("### Технічна деталізація — лише за вимогою")
        if st.checkbox("Показати таблицю балів заходів",key="calc_dash_scores"):
            cols=["code","parent_goal_code","parent_task_code","period_state","status","submitted_current_period","carry_forward","source_quarter","actual","annual_target","raw_attainment_pct","execution_score","result_achieved","coverage_eligible","missing_required_submission","data_quality_conflict"]
            _display_df(snapshot[[c for c in cols if c in snapshot.columns]],max_height=520,max_rows=250)
        if st.checkbox("Показати завдання та стратегічні цілі",key="calc_dash_hierarchy"):
            st.markdown("**Завдання**"); _display_df(task_scores,max_height=450,max_rows=200)
            st.markdown("**Стратегічні цілі**"); _display_df(goal_scores,max_height=450,max_rows=100)
        if st.checkbox("Показати ССП, заступників та фінансування",key="calc_dash_org"):
            st.markdown("**ССП**"); _display_df(ssp_summary(results,base_results=results),max_height=480,max_rows=150)
            st.markdown("**Заступники Міністра**"); _display_df(deputy_summary(results),max_height=420,max_rows=100)
            try:
                finance=build_finance_frame(snapshot,YEAR); fk=finance_kpis(finance)
                _show_formula(
                    "Фінансове виконання",meaning="Частка сукупного факту від сукупного річного плану фінансування.",population="Валідні фінансові рядки у shared finance frame.",formula="сума факту / сума плану × 100",substitution=f"{_n(fk.get('fact_bln'))} / {_n(fk.get('plan_bln'))} × 100",result=_pct(fk.get("financial_execution_pct")),interpretation="Це ratio of sums для всього портфеля.",caveat="Це не середнє індивідуальних фінансових відсотків заходів.")
                _display_df(finance,max_height=450,max_rows=200)
            except Exception as exc:
                st.warning(f"Фінансовий блок не сформовано: {exc}")

elif section == "Аналітика — розрахунки":
    with st.spinner("Формую Analytics-контекст..."):
        try:
            strat_df, _, measures = _load_base_data()
            results, active, plan, metrics = _build_analytics_context(strat_df, measures)
        except Exception as exc:
            st.exception(exc); st.stop()

    latest = metrics.get("latest_period")
    latest_text = f"{latest[1]} кв. {latest[0]}" if latest else "—"
    _section("1. Observation units", "Історичний масив і current snapshot мають різні законні ролі.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Історичних рядків", len(active))
    c2.metric("Унікальних заходів у діапазоні", metrics.get("unique_measures", 0))
    c3.metric("Заходів у latest snapshot", metrics.get("latest_measure_count", 0))
    c4.metric("Latest period", latest_text)
    _callout("Історичні measure-period rows використовуються для динаміки, coverage history та статусів. Вони не сумуються у headline «потребують уваги». ")

    _section("2. Execution = exact latest selected period")
    _show_formula(
        "Рівень виконання Стратегічного плану",
        meaning="Стан виконання саме на останній хронологічно обраний період.",
        population=f"Канонічний snapshot {latest_text}.",
        formula="result[latest_selected_period].execution_by_measures",
        result=_pct(metrics.get("completion")),
        interpretation="Якщо у точному latest-періоді execution недоступний, результат = unavailable/None; попередній квартал не підставляється.",
        caveat="Часове середнє квартальних execution KPI не є метрикою Analytics.",
    )
    _display_df(_quarter_result_table(results), max_height=280)
    st.markdown(f"**Зміна між першим і останнім обраним періодом:** {_pp(metrics.get('completion_change'))}.")

    _section("3. Coverage = average за діапазон + exact latest")
    cov1, cov2 = st.columns(2)
    cov1.metric("Середнє coverage за діапазон", _pct(metrics.get("coverage")))
    cov2.metric(f"Coverage · {latest_text}", _pct(metrics.get("coverage_latest")))
    _show_formula(
        "Середнє coverage",
        meaning="Середнє квартальних canonical coverage лише за методологічно оцінюваними періодами.",
        population="Обрані квартали з валідним coverage.",
        formula="mean(canonical quarter coverage)",
        result=_pct(metrics.get("coverage")),
        interpretation="Цей показник описує повноту моніторингу протягом діапазону, а не execution.",
    )
    _show_formula(
        "Latest coverage",
        meaning="Coverage точного останнього обраного кварталу.",
        population=f"Канонічний snapshot {latest_text}.",
        formula="result[latest_selected_period].coverage",
        result=_pct(metrics.get("coverage_latest")),
        interpretation="Unavailable latest не підміняється нулем або попереднім кварталом.",
    )

    _section("4. Управлінська увага — лише latest snapshot")
    info = plan.get("management_attention") or {}
    st.markdown(f"### {info.get('label') or metrics.get('attention_label')}: **{_int(info.get('count', metrics.get('attention_count')))}**")
    semantics = pd.DataFrame([
        {"Latest квартал": "I", "Headline": "попередні сигнали управлінської уваги", "Популяція": "унікальні заходи Q1 snapshot"},
        {"Latest квартал": "II–III", "Headline": "високий або критичний ризик", "Популяція": "унікальні заходи latest risk-assessed snapshot"},
        {"Latest квартал": "IV", "Headline": "фінальний результат не досягнуто", "Популяція": "лише валідний final assessed cohort"},
    ])
    _display_df(semantics, max_height=250)
    current = analytics_calculations.latest_attention_snapshot(results)
    if not current.empty:
        att = _safe_bool(current, "analytics_attention")
        cols = [c for c in ["code", "parent_goal_code", "parent_task_code", "department", "status", "risk_level", "result_achieved", "analytics_attention_label"] if c in current.columns]
        if st.checkbox("Показати current attention rows", key="calc_current_attention"):
            _display_df(current.loc[att, cols], max_rows=250)

    _section("5. Розрізи Analytics")
    if st.checkbox("Показати СЦ, завдання, ССП і типи продукту", key="calc_ana_tables"):
        goals = analytics_calculations.build_analytics_goal_summary(results, active)
        tasks = analytics_calculations.build_analytics_task_summary(results, active)
        ssp = analytics_calculations.build_analytics_ssp_summary(results, active, base_results=results)
        products = analytics_calculations.aggregate_product_progress(results, active)
        st.markdown("**Стратегічні цілі**"); _display_df(goals, max_rows=120)
        st.markdown("**Завдання**"); _display_df(tasks, max_rows=200)
        st.markdown("**ССП**"); _display_df(ssp, max_rows=150)
        st.markdown("**Типи продукту**"); _display_df(products, max_rows=100)
        _callout("У колонці «Виконання» цих таблиць — exact latest. Coverage позначено окремо як середнє за діапазон і latest. Current attention не є накопиченим історичним лічильником.")

    _section("6. МіО — методологія не змінена")
    if st.checkbox("Розрахувати МіО 2026", key="calc_ana_mio"):
        try:
            strat_df, all_monitoring, _ = _load_base_data()
            mio_requests = append_confirmed_closeout_facts(all_monitoring, include_incomplete=False)
            outputs = mio_shared.build_mio_analytics(strat_df, mio_requests, [YEAR])
            goals = outputs.get("goals", pd.DataFrame())
            if not goals.empty:
                summary = mio_shared.summarize_integral_goals(goals, YEAR)
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Інтегральна", _pct(summary.average_integral)); m2.metric("Заходи", _pct(summary.average_measure_execution)); m3.metric("Завдання", _pct(summary.average_task_score)); m4.metric("Індикатори", _pct(summary.average_strategic_progress))
                st.caption("Формули МіО цією задачею не змінювалися.")
        except Exception as exc:
            st.warning(f"МіО не сформовано: {exc}")

elif section == "Графіки Аналітики":
    _section("Графіки Analytics після методологічного оновлення", "Статичний довідник без завантаження БД.")
    _display_df(pd.DataFrame([
        {"Графік": "Динаміка оціненого виконання", "Зміст": "quarter-by-quarter execution series", "Одиниця": "%", "Семантика": "часова серія зберігається; average не видається за рівень виконання"},
        {"Графік": "Виконання за стратегічними цілями", "Зміст": "execution СЦ exact latest", "Одиниця": "%", "Семантика": "hover окремо показує average/latest coverage та current attention"},
        {"Графік": "Виконання за ССП", "Зміст": "execution портфеля ССП exact latest", "Одиниця": "%", "Семантика": "current risk/attention не накопичується по кварталах"},
        {"Графік": "Структура заходів за типами продукту", "Зміст": "розмір портфеля", "Одиниця": "унікальний захід", "Семантика": "execution у hover = exact latest"},
        {"Графік": "Структура статусів", "Зміст": "історичні status observations", "Одиниця": "захід × період", "Семантика": "явно історичний descriptive breakdown"},
        {"Графік": "Завдання з найбільшою актуальною увагою", "Зміст": "актуальна увага останнього обраного кварталу", "Одиниця": "унікальний захід", "Семантика": "не накопичений історичний лічильник"},
    ]), max_height=500)
    _callout("Окремого графіка порівняння між роками в Analytics більше немає. Квартальна динаміка при цьому зберігається.")

elif section == "Показники аналітичної довідки":
    _section("Показники narrative engine", "Rule-based generator отримує тільки prepared factual metrics із provenance.")
    _display_df(pd.DataFrame([
        {"Показник": "Execution", "Одиниця": "%", "Контракт": "exact latest selected period", "Дозволено в довідці": "так"},
        {"Показник": "Coverage average", "Одиниця": "%", "Контракт": "mean canonical coverage за діапазон", "Дозволено в довідці": "так"},
        {"Показник": "Coverage latest", "Одиниця": "%", "Контракт": "exact latest selected period", "Дозволено в довідці": "так"},
        {"Показник": "Current management attention", "Одиниця": "unique measure", "Контракт": "quarter-aware latest snapshot", "Дозволено в довідці": "так"},
        {"Показник": "Missing latest", "Одиниця": "unique measure", "Контракт": "latest snapshot", "Дозволено в довідці": "так"},
        {"Показник": "Quarterly execution series", "Одиниця": "%", "Контракт": "динаміка", "Дозволено в довідці": "так"},
        {"Показник": "МіО", "Одиниця": "%", "Контракт": "shared annual methodology", "Дозволено в довідці": "лише prepared MIO facts"},
    ]), max_height=430)
    _callout("Generator не отримує temporal-average execution або накопичений multi-period attention як факти. Числа не рахуються повторно всередині composer.")

    if st.checkbox("Побудувати factual registry для 2026", key="calc_registry"):
        with st.spinner("Формую prepared factual registry..."):
            try:
                strat_df, all_monitoring, measures = _load_base_data()
                results, active, plan, metrics = _build_analytics_context(strat_df, measures)
                goals = analytics_calculations.build_analytics_goal_summary(results, active)
                tasks = analytics_calculations.build_analytics_task_summary(results, active)
                ssp = analytics_calculations.build_analytics_ssp_summary(results, active, base_results=results)
                products = analytics_calculations.aggregate_product_progress(results, active)
                statuses = _status_counts(active)
                dynamics = analytics_calculations.build_analytics_dynamics(results)
                # Factual-registry construction must not downgrade a real MіO failure to an empty dataset.
                # Let the surrounding visible validation/error path receive the original exception instead.
                # This preserves the MіO methodology while keeping failures observable during diagnostics.
                mio_requests = append_confirmed_closeout_facts(all_monitoring, include_incomplete=False)
                mio = mio_shared.build_mio_analytics(strat_df, mio_requests, [YEAR])
                context = build_analytics_text_context(
                    filters={"years":[YEAR],"quarters":QUARTERS.copy(),"ssp":[],"ssp_indices":[],"deputies":[],"goal_labels":[],"task_labels":[],"product_types":[]},
                    metrics=metrics,
                    goal_progress=goals,
                    task_progress=tasks,
                    department_progress=ssp,
                    product_progress=products,
                    status_counts=statuses,
                    period_dynamics=dynamics,
                    active=active,
                    mio_goal_evaluation=mio.get("goals", pd.DataFrame()),
                    mio_goal_task_evaluation=mio.get("goals_tasks", pd.DataFrame()),
                    mio_measure_evaluation=mio.get("measures", pd.DataFrame()),
                    mio_financing=mio.get("financing", pd.DataFrame()),
                )
                facts = context.analytical_facts.metrics if context.analytical_facts is not None else {}
                rows = [{"Код":code,"Значення":m.value,"Unit":m.unit,"Source":m.source,"Aggregation":m.aggregation,"Observation unit":m.observation_unit or "—"} for code,m in sorted(facts.items())]
                _display_df(pd.DataFrame(rows), max_height=600, max_rows=600)
            except Exception as exc:
                st.exception(exc)

elif section == "Технічна звірка":
    with st.spinner("Формую Dashboard та Analytics для звірки..."):
        try:
            strat_df, _, measures = _load_base_data()
            _, dashboard_results, _, _, _, _ = _build_dashboard_context(strat_df, measures)
            analytics_results, _, _, analytics_metrics = _build_analytics_context(strat_df, measures)
        except Exception as exc:
            st.exception(exc); st.stop()
    rows = []
    for q in QUARTERS:
        d = dashboard_results.get((YEAR, q), {}); a = analytics_results.get((YEAR, q), {})
        rows.append({
            "Квартал":q,
            "Dashboard execution":d.get("execution_by_measures"),
            "Analytics source execution":a.get("execution_by_measures"),
            "Execution parity":"ЗБІГАЄТЬСЯ" if _close(d.get("execution_by_measures"), a.get("execution_by_measures")) else "ВІДРІЗНЯЄТЬСЯ",
            "Dashboard coverage":d.get("coverage"),
            "Analytics source coverage":a.get("coverage"),
            "Coverage parity":"ЗБІГАЄТЬСЯ" if _close(d.get("coverage"), a.get("coverage")) else "ВІДРІЗНЯЄТЬСЯ",
        })
    _display_df(pd.DataFrame(rows), max_height=300)
    latest = analytics_metrics.get("latest_period")
    _callout(
        f"Analytics headline execution бере значення тільки з точного latest-періоду {latest}. "
        "Якщо такого значення немає, він не шукає попереднє валідне. Shared квартальні Dashboard values при цьому залишаються незмінними."
    )

render_footer()
