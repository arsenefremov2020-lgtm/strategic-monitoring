from __future__ import annotations

"""
Службова read-only сторінка «Розрахунки».

Призначення сторінки — прозоро показати, як поточні shared-модулі системи
формують показники Dashboard і сторінки «Аналітика». Сторінка нічого не
записує до БД, не змінює методологію і не дублює розрахунки в production-коді.

Фіксований діагностичний контекст:
- 2026 рік;
- поточний зріз — IV квартал;
- динаміка — I → IV квартал;
- повний Стратегічний план;
- confirmed/погоджені дані;
- без додаткових організаційних і продуктових фільтрів.
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
from core.dashboard_breakdowns import (
    build_period_results,
    aggregate_plan,
    aggregate_objects,
    dynamics_frame,
    ssp_summary,
    deputy_summary,
)
from core.dashboard_risk import attention_mask, risk_summary
from core.dashboard_finance import build_finance_frame, finance_kpis


# =============================================================================
# ФІКСОВАНИЙ ДІАГНОСТИЧНИЙ КОНТЕКСТ
# =============================================================================

YEAR = 2026
QUARTERS = ["I", "II", "III", "IV"]
LATEST_QUARTER = "IV"
PAIRS = [(YEAR, q) for q in QUARTERS]
LATEST_KEY = (YEAR, LATEST_QUARTER)
TOL = 0.05


# =============================================================================
# СТАРТ СТОРІНКИ
# =============================================================================

current_user = page_setup("Розрахунки", page_name=None)

if not is_super_admin_user(current_user):
    st.error("Сторінка «Розрахунки» доступна лише супер-адміністратору.")
    st.stop()

# Локальний CSS навмисно не змінює висоту Streamlit-компонентів. Це важливо:
# таблиці мають самі резервувати місце в layout і не накладатися на наступний текст.
st.markdown(
    """
    <style>
    .main .block-container {
        max-width: 1380px;
        padding-top: 1.25rem;
        padding-bottom: 3rem;
    }
    .calc-hero {
        background: #FFFFFF;
        border: 1px solid #DCE4F0;
        border-radius: 16px;
        padding: 20px 24px;
        margin: 4px 0 18px 0;
        box-shadow: 0 6px 20px rgba(15, 23, 42, 0.05);
    }
    .calc-hero-title {
        color: #132238;
        font-size: 30px;
        font-weight: 900;
        line-height: 1.15;
        margin-bottom: 7px;
    }
    .calc-hero-subtitle {
        color: #61708A;
        font-size: 14px;
        line-height: 1.55;
    }
    .calc-section-title {
        color: #132238;
        font-size: 23px;
        font-weight: 900;
        line-height: 1.25;
        margin: 1.4rem 0 0.45rem 0;
    }
    .calc-section-note {
        color: #52637A;
        line-height: 1.65;
        margin-bottom: 0.9rem;
    }
    .calc-callout {
        background: #F7F9FC;
        border: 1px solid #DCE4F0;
        border-left: 5px solid #005BBB;
        border-radius: 12px;
        padding: 13px 16px;
        margin: 10px 0 16px 0;
        color: #34445C;
        line-height: 1.55;
    }
    .calc-warning {
        background: #FFF8E6;
        border-color: #F4B400;
        border-left-color: #F4B400;
    }
    .calc-after-table {
        height: 18px;
        width: 100%;
        clear: both;
    }
    div[data-testid="stDataFrame"] {
        margin-bottom: 0.35rem;
    }
    div[data-testid="stExpander"] {
        margin-bottom: 0.7rem;
    }
    div[data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #DCE4F0;
        border-radius: 12px;
        padding: 8px 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="calc-hero">
        <div class="calc-hero-title">Розрахунки</div>
        <div class="calc-hero-subtitle">
            Службова сторінка прозорості методології. Тут кожний показник розкладено
            за принципом: <b>які дані взяли → кого включили → як порахували → що означає результат</b>.
            Фіксований контекст: 2026 рік, IV квартал як поточний зріз, динаміка I–IV квартали,
            повний Стратегічний план, погоджені дані.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.info(
    "Сторінка read-only. Вона не змінює формули та не записує дані. "
    "Усі production-значення беруться з тих самих shared-модулів, що використовують Dashboard і «Аналітика»."
)


# =============================================================================
# ДОПОМІЖНІ ФУНКЦІЇ ВІДОБРАЖЕННЯ
# =============================================================================

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
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.{digits}f} в.п."


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


def _safe_bool_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=bool)
    if column not in frame.columns:
        return pd.Series(False, index=frame.index, dtype=bool)
    return frame[column].fillna(False).astype(bool)


def _safe_numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _close(a: Any, b: Any, tol: float = TOL) -> bool:
    aa, bb = _num(a), _num(b)
    if aa is None or bb is None:
        return aa is None and bb is None
    return abs(aa - bb) <= tol


def _parity_text(a: Any, b: Any) -> str:
    return "ЗБІГАЄТЬСЯ" if _close(a, b) else "ВІДРІЗНЯЄТЬСЯ"


def _display_df(
    frame: pd.DataFrame,
    *,
    max_height: int = 520,
    min_height: int = 120,
) -> None:
    """Показує таблицю без накладання на наступний контент.

    Для коротких таблиць висота обчислюється з кількості рядків, щоб не було
    зайвого внутрішнього скролу. Для великих таблиць висота обмежена, а скрол
    залишається всередині dataframe.
    """
    if frame is None or frame.empty:
        st.caption("Немає рядків для відображення.")
        st.markdown('<div class="calc-after-table"></div>', unsafe_allow_html=True)
        return

    visible_rows = min(len(frame), 12)
    calculated = 40 * (visible_rows + 1) + 16
    height = min(max_height, max(min_height, calculated))
    st.dataframe(frame, use_container_width=True, height=height, hide_index=True)
    st.markdown('<div class="calc-after-table"></div>', unsafe_allow_html=True)


def _raw_table(
    title: str,
    frame: pd.DataFrame,
    *,
    note: str = "",
    max_height: int = 520,
    expanded: bool = False,
) -> None:
    with st.expander(title, expanded=expanded):
        if note:
            st.caption(note)
        _display_df(frame, max_height=max_height)


def _section(title: str, note: str | None = None) -> None:
    st.markdown(f'<div class="calc-section-title">{title}</div>', unsafe_allow_html=True)
    if note:
        st.markdown(f'<div class="calc-section-note">{note}</div>', unsafe_allow_html=True)


def _callout(text: str, *, warning: bool = False) -> None:
    cls = "calc-callout calc-warning" if warning else "calc-callout"
    st.markdown(f'<div class="{cls}">{text}</div>', unsafe_allow_html=True)


def _show_formula(
    title: str,
    *,
    meaning: str,
    population: str,
    formula: str,
    substitution: str,
    result: str,
    interpretation: str,
    caveat: str | None = None,
) -> None:
    st.markdown(f"#### {title}")
    st.markdown(f"**Що означає показник.** {meaning}")
    st.markdown(f"**Хто входить у розрахунок.** {population}")
    st.markdown(f"**Формула.** `{formula}`")
    st.markdown(f"**Підстановка поточних даних.** {substitution}")
    st.markdown(f"**Поточний результат.** **{result}**")
    st.markdown(f"**Як читати результат.** {interpretation}")
    if caveat:
        _callout(f"<b>Важливо.</b> {caveat}", warning=True)


def _source_label(source_overrides: dict, key: tuple[int, str]) -> str:
    return "Архівний snapshot" if key in source_overrides else "Поточні live-дані"


def _quarter_result_table(results: dict) -> pd.DataFrame:
    rows = []
    for q in QUARTERS:
        item = results.get((YEAR, q), {})
        snapshot = item.get("snapshot")
        rows.append(
            {
                "Квартал": q,
                "Рядків snapshot": 0 if snapshot is None else len(snapshot),
                "Унікальних заходів": (
                    0
                    if snapshot is None or snapshot.empty or "code" not in snapshot.columns
                    else snapshot["code"].nunique()
                ),
                "Виконання за заходами, %": item.get("execution_by_measures"),
                "Виконання за стратегічними цілями, %": item.get("execution_by_goals"),
                "Покриття, %": item.get("coverage"),
                "Оцінених заходів": item.get("assessed_measure_count"),
            }
        )
    return pd.DataFrame(rows)


def _q1_q4_delta(frame: pd.DataFrame, value_col: str) -> float | None:
    if frame is None or frame.empty or "Квартал" not in frame.columns:
        return None
    q1 = frame.loc[frame["Квартал"].eq("I"), value_col]
    q4 = frame.loc[frame["Квартал"].eq("IV"), value_col]
    if q1.empty or q4.empty:
        return None
    a = _num(q1.iloc[0])
    b = _num(q4.iloc[0])
    return None if a is None or b is None else b - a


def _reason_table(snapshot: pd.DataFrame) -> pd.DataFrame:
    if snapshot is None or snapshot.empty:
        return pd.DataFrame()

    risk_level = snapshot.get(
        "risk_level", pd.Series("", index=snapshot.index, dtype=object)
    ).astype(str)
    final_failure = (
        snapshot.get(
            "forecast_kind", pd.Series("", index=snapshot.index, dtype=object)
        ).astype(str).eq("final")
        & ~_safe_bool_series(snapshot, "result_achieved")
    )

    reasons = {
        "Високий або критичний ризик": risk_level.isin(["Високий ризик", "Критичний ризик"]),
        "Попередній сигнал уваги": _safe_bool_series(snapshot, "preliminary_attention"),
        "Немає обов'язкового подання за квартал": _safe_bool_series(snapshot, "missing_required_submission"),
        "Захід завершився без фінального результату": _safe_bool_series(snapshot, "final_missing_result"),
        "Конфлікт якості даних": _safe_bool_series(snapshot, "data_quality_conflict"),
        "Фінальний результат не досягнуто": final_failure,
    }

    rows = [
        {"Причина": label, "Кількість рядків Q4": int(mask.fillna(False).sum())}
        for label, mask in reasons.items()
    ]
    union = attention_mask(snapshot).reindex(snapshot.index, fill_value=False)
    rows.append(
        {
            "Причина": "Унікальний UNION: потребує уваги хоча б з однієї причини",
            "Кількість рядків Q4": int(union.sum()),
        }
    )
    return pd.DataFrame(rows)


def _status_counts(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty or "status" not in frame.columns:
        return pd.DataFrame()
    return (
        frame["status"]
        .fillna("—")
        .astype(str)
        .value_counts(dropna=False)
        .rename_axis("Статус")
        .reset_index(name="Кількість")
    )


def _format_fact_value(value: Any, unit: str) -> str:
    if value is None:
        return "—"
    if unit == "percent":
        return _pct(value, 2)
    if unit == "pp":
        return _pp(value, 2)
    if unit == "count":
        return _n(value, 0)
    return _n(value, 2)


def _metric_group(code: str) -> str:
    prefix = str(code).split(".", 1)[0]
    labels = {
        "plan": "Стратегічний план",
        "dashboard": "Dashboard",
        "risk": "Ризик і увага",
        "goal": "Стратегічні цілі",
        "task": "Завдання",
        "department": "ССП",
        "product": "Типи продукту",
        "status": "Статуси",
        "dynamics": "Динаміка",
        "yoy": "Рік до року",
        "mio": "МіО",
        "finance": "Фінансування",
    }
    return labels.get(prefix, prefix or "Інше")


# =============================================================================
# ЗАВАНТАЖЕННЯ ДАНИХ
# =============================================================================

try:
    strat_df = load_strat_matrix()
    all_monitoring = monitoring_data.load_monitoring_requests()
    measure_requests = monitoring_data.measures_only(all_monitoring)
    measure_requests = append_confirmed_closeout_facts(
        measure_requests,
        include_incomplete=True,
    )
    # МіО працює з повним потоком, включно з indicator rows.
    mio_monitoring = append_confirmed_closeout_facts(
        all_monitoring,
        include_incomplete=False,
    )
except Exception as exc:
    st.exception(exc)
    st.stop()

matrix_measures = (
    strat_df[
        strat_df.get("object_type", pd.Series(index=strat_df.index)).astype(str).eq("measure")
    ].copy()
    if strat_df is not None and not strat_df.empty
    else pd.DataFrame()
)

# Dashboard: archive-aware production contour.
dashboard_period_sources = dashboard_sources.build_period_source_overrides(
    PAIRS,
    operational_mode=False,
)
dashboard_results = build_period_results(
    strat_df,
    measure_requests,
    PAIRS,
    period_sources=dashboard_period_sources,
)
dashboard_aggregate = aggregate_plan(dashboard_results)
dashboard_q = _quarter_result_table(dashboard_results)
dashboard_latest = dashboard_results.get(LATEST_KEY, {})
dashboard_snapshot = dashboard_latest.get("snapshot", pd.DataFrame())
dashboard_risk = dashboard_latest.get("risk_summary") or risk_summary(dashboard_snapshot)

# Analytics: current production full-scope contour (without Dashboard archive overrides).
analytics_results, analytics_active = analytics_calculations.prepare_analysis_context(
    strat_df,
    measure_requests,
    [YEAR],
    QUARTERS,
)
analytics_plan = analytics_calculations.build_analytics_plan_summary(analytics_results)
analytics_metrics = analytics_calculations.build_metrics(analytics_active)
analytics_metrics["completion"] = analytics_plan.get("execution_by_measures_average")
analytics_metrics["coverage"] = analytics_plan.get("coverage_average")
analytics_metrics["completion_latest"] = analytics_plan.get("execution_by_measures_latest")
analytics_metrics["completion_change"] = analytics_plan.get("execution_by_measures_change")
analytics_metrics["goal_completion"] = analytics_plan.get("execution_by_goals_average")
analytics_metrics["goal_completion_latest"] = analytics_plan.get("execution_by_goals_latest")
analytics_metrics["goal_completion_change"] = analytics_plan.get("execution_by_goals_change")
analytics_metrics["coverage_latest"] = analytics_plan.get("coverage_latest")
analytics_metrics["coverage_change"] = analytics_plan.get("coverage_change")
analytics_metrics["latest_period"] = analytics_plan.get("latest_period")
analytics_metrics["latest_risk_summary"] = analytics_plan.get("latest_risk_summary") or {}

analytics_q = _quarter_result_table(analytics_results)
analytics_latest = analytics_results.get(LATEST_KEY, {})
analytics_q4_snapshot = analytics_latest.get("snapshot", pd.DataFrame())
analytics_goals = analytics_calculations.build_analytics_goal_summary(
    analytics_results, analytics_active
)
analytics_tasks = analytics_calculations.build_analytics_task_summary(
    analytics_results, analytics_active
)
analytics_ssp = analytics_calculations.build_analytics_ssp_summary(
    analytics_results,
    analytics_active,
    base_results=analytics_results,
)
analytics_products = analytics_calculations.aggregate_product_progress(
    analytics_results, analytics_active
)
analytics_statuses = _status_counts(analytics_active).rename(columns={"Статус": "status"})
analytics_dynamics = analytics_calculations.build_analytics_dynamics(analytics_results)

# Same year-over-year comparison logic as Analytics for a default 2026 selection.
try:
    comparison_years = [YEAR - 1, YEAR]
    yoy_base_results, _ = analytics_calculations.prepare_analysis_context(
        strat_df,
        measure_requests,
        comparison_years,
        QUARTERS,
    )
    yoy_comparison = analytics_calculations.build_year_over_year_comparison(yoy_base_results)
except Exception:
    yoy_comparison = pd.DataFrame()

# Reusable annual MіO outputs. Failure here must not break the diagnostic page.
try:
    mio_outputs = mio_shared.build_mio_analytics(strat_df, mio_monitoring, [YEAR])
except Exception:
    mio_outputs = {}

mio_goals = mio_outputs.get("goals", pd.DataFrame()) if isinstance(mio_outputs, dict) else pd.DataFrame()
mio_goal_tasks = mio_outputs.get("goals_tasks", pd.DataFrame()) if isinstance(mio_outputs, dict) else pd.DataFrame()
mio_measures = mio_outputs.get("measures", pd.DataFrame()) if isinstance(mio_outputs, dict) else pd.DataFrame()
mio_financing = mio_outputs.get("financing", pd.DataFrame()) if isinstance(mio_outputs, dict) else pd.DataFrame()

# Prepared factual metric registry used by the rule-based analytical text engine.
analytics_text_context = None
analytics_fact_error = None
try:
    fixed_filters = {
        "years": [YEAR],
        "quarters": QUARTERS.copy(),
        "ssp": [],
        "ssp_indices": [],
        "deputies": [],
        "goal_labels": [],
        "task_labels": [],
        "product_types": [],
    }
    analytics_text_context = build_analytics_text_context(
        filters=fixed_filters,
        metrics=analytics_metrics,
        goal_progress=analytics_goals,
        task_progress=analytics_tasks,
        department_progress=analytics_ssp,
        product_progress=analytics_products,
        status_counts=analytics_statuses,
        period_dynamics=analytics_dynamics,
        yoy_comparison=yoy_comparison,
        active=analytics_active,
        mio_goal_evaluation=mio_goals,
        mio_goal_task_evaluation=mio_goal_tasks,
        mio_measure_evaluation=mio_measures,
        mio_financing=mio_financing,
    )
except Exception as exc:
    analytics_fact_error = exc


# =============================================================================
# ВЕРХНЯ ЗВІРКА
# =============================================================================

input_summary = pd.DataFrame(
    [
        {
            "Масив": "Заходи у стратегічній матриці",
            "Кількість": len(matrix_measures),
            "Одиниця спостереження": "унікальний захід",
            "Навіщо потрібен": "визначає повний портфель, ієрархію, строки, план та атрибути заходу",
        },
        {
            "Масив": "Усі записи monitoring_requests",
            "Кількість": 0 if all_monitoring is None else len(all_monitoring),
            "Одиниця спостереження": "запис БД",
            "Навіщо потрібен": "джерело подань заходів та індикаторів; для Dashboard indicator rows відсікаються",
        },
        {
            "Масив": "Подання заходів після фільтрації та closeouts",
            "Кількість": len(measure_requests),
            "Одиниця спостереження": "подання заходу за період",
            "Навіщо потрібен": "з них формується квартальний snapshot і execution_score",
        },
    ]
)

reconciliation = pd.DataFrame(
    [
        {
            "Показник": "Виконання за заходами",
            "Dashboard Q4": dashboard_latest.get("execution_by_measures"),
            "Analytics KPI зараз": analytics_metrics.get("completion"),
            "Analytics latest Q4": analytics_plan.get("execution_by_measures_latest"),
            "Причина можливої різниці": "Dashboard = Q4; Analytics KPI = середнє квартальних KPI I–IV",
        },
        {
            "Показник": "Покриття моніторингом",
            "Dashboard Q4": dashboard_latest.get("coverage"),
            "Analytics KPI зараз": analytics_metrics.get("coverage"),
            "Analytics latest Q4": analytics_plan.get("coverage_latest"),
            "Причина можливої різниці": "Dashboard = Q4; Analytics KPI = середнє квартальних coverage I–IV",
        },
        {
            "Показник": "Виконання за стратегічними цілями",
            "Dashboard Q4": dashboard_latest.get("execution_by_goals"),
            "Analytics KPI зараз": analytics_plan.get("execution_by_goals_average"),
            "Analytics latest Q4": analytics_plan.get("execution_by_goals_latest"),
            "Причина можливої різниці": "Dashboard = Q4; Analytics = average I–IV або latest залежно від поля",
        },
    ]
)

_section("Швидка звірка перед деталями")
_c1, _c2, _c3, _c4 = st.columns(4)
_c1.metric("Dashboard · виконання Q4", _pct(dashboard_latest.get("execution_by_measures")))
_c2.metric("Analytics · виконання I–IV", _pct(analytics_metrics.get("completion")))
_c3.metric("Dashboard · покриття Q4", _pct(dashboard_latest.get("coverage")))
_c4.metric("Analytics · покриття I–IV", _pct(analytics_metrics.get("coverage")))

_display_df(reconciliation, max_height=270)

if _close(
    dashboard_latest.get("execution_by_measures"),
    analytics_plan.get("execution_by_measures_latest"),
):
    st.success(
        "Dashboard Q4 і Analytics latest-Q4 за виконанням збігаються. "
        "Різниця основної картки Analytics пояснюється тим, що вона показує average I–IV."
    )
else:
    st.warning(
        "Dashboard Q4 і Analytics latest-Q4 за виконанням не збігаються. "
        "Це вже не лише average-vs-latest: потрібно дивитися джерело кварталу (archive vs live)."
    )

with st.expander("Короткий словник термінів", expanded=False):
    glossary = pd.DataFrame(
        [
            {
                "Термін": "Snapshot кварталу",
                "Пояснення": "Один канонічний рядок на захід, який належить до оцінюваного стану цього кварталу, з обраним підтвердженим фактом і розрахованими службовими полями.",
            },
            {
                "Термін": "execution_score",
                "Пояснення": "Уніфікована управлінська оцінка виконання одного заходу у відсотках. Саме вона агрегується вище — у завдання, цілі та план.",
            },
            {
                "Термін": "Покриття",
                "Пояснення": "Частка заходів, для яких у конкретному кварталі подання було обов'язковим і фактично подане саме за цей квартал.",
            },
            {
                "Термін": "measure-period",
                "Пояснення": "Спостереження «один захід × один квартал». Один код заходу може мати до чотирьох таких рядків за I–IV квартали.",
            },
            {
                "Термін": "unique measure",
                "Пояснення": "Унікальний код заходу незалежно від кількості кварталів, у яких він зустрічається.",
            },
            {
                "Термін": "average / latest / change",
                "Пояснення": "average — середнє доступних квартальних KPI; latest — останній доступний квартал; change — latest мінус перший доступний квартал у відсоткових пунктах.",
            },
        ]
    )
    _display_df(glossary, max_height=360)


# =============================================================================
# ОСНОВНІ ВКЛАДКИ
# =============================================================================

_tab_dash, _tab_ana, _tab_charts, _tab_metrics, _tab_tech = st.tabs(
    [
        "Dashboard: як рахується",
        "Аналітика: як рахується",
        "Графіки Аналітики",
        "Показники аналітичної довідки",
        "Технічна звірка",
    ]
)


# =============================================================================
# TAB 1 — DASHBOARD
# =============================================================================

with _tab_dash:
    _section(
        "1. Джерело даних Dashboard за кожним кварталом",
        "Dashboard має archive resolver. Якщо для кварталу є валідний архівний snapshot, "
        "розрахунок відтворює зафіксований історичний стан; якщо архіву немає — використовуються live-дані.",
    )

    source_rows = []
    for q in QUARTERS:
        key = (YEAR, q)
        item = dashboard_results.get(key, {})
        snap = item.get("snapshot", pd.DataFrame())
        source_rows.append(
            {
                "Квартал": q,
                "Джерело": _source_label(dashboard_period_sources, key),
                "Рядків snapshot": len(snap) if isinstance(snap, pd.DataFrame) else 0,
                "Унікальних заходів": (
                    snap["code"].nunique()
                    if isinstance(snap, pd.DataFrame) and not snap.empty and "code" in snap.columns
                    else 0
                ),
                "Виконання, %": item.get("execution_by_measures"),
                "Виконання за цілями, %": item.get("execution_by_goals"),
                "Покриття, %": item.get("coverage"),
            }
        )
    _display_df(pd.DataFrame(source_rows), max_height=280)

    _section(
        "2. Як формується snapshot IV кварталу",
        "Перед будь-яким середнім система визначає, чи захід взагалі належить до поточного зрізу, "
        "і який саме підтверджений результат треба використати.",
    )

    if dashboard_snapshot.empty:
        st.error("Q4 snapshot порожній — подальші Q4-формули неможливо показати.")
    else:
        period_state = dashboard_snapshot.get(
            "period_state", pd.Series("", index=dashboard_snapshot.index)
        ).astype(str)
        snapshot_structure = pd.DataFrame(
            [
                {
                    "Категорія": "Усього рядків Q4 snapshot",
                    "Кількість": len(dashboard_snapshot),
                    "Що це означає": "підсумкова робоча вибірка IV кварталу; один рядок відповідає одному заходу",
                },
                {
                    "Категорія": "Active",
                    "Кількість": int(period_state.eq("active").sum()),
                    "Що це означає": "строк виконання заходу охоплює IV квартал",
                },
                {
                    "Категорія": "Ended",
                    "Кількість": int(period_state.eq("ended").sum()),
                    "Що це означає": "захід завершився раніше; оцінюється останній належний підтверджений результат",
                },
                {
                    "Категорія": "Unknown period",
                    "Кількість": int(period_state.eq("unknown_period").sum()),
                    "Що це означає": "строки неможливо однозначно інтерпретувати з матриці",
                },
                {
                    "Категорія": "Подано саме за Q4",
                    "Кількість": int(_safe_bool_series(dashboard_snapshot, "submitted_current_period").sum()),
                    "Що це означає": "є погоджене поточне подання за IV квартал",
                },
                {
                    "Категорія": "Використано попередній підтверджений результат",
                    "Кількість": int(_safe_bool_series(dashboard_snapshot, "carry_forward").sum()),
                    "Що це означає": "нового Q4-подання немає, але для execution використано останній підтверджений факт цього року",
                },
                {
                    "Категорія": "Немає обов'язкового поточного подання",
                    "Кількість": int(_safe_bool_series(dashboard_snapshot, "missing_required_submission").sum()),
                    "Що це означає": "захід мав податися в Q4, але поточного подання немає",
                },
            ]
        )
        _display_df(snapshot_structure, max_height=420)

        _callout(
            "<b>Послідовність вибору факту.</b> Спочатку визначається стан заходу у періоді. "
            "Майбутній захід не потрапляє в оцінюваний snapshot. Для активного заходу система "
            "шукає погоджене подання саме за Q4. Якщо його немає, але є раніший підтверджений "
            "результат 2026 року, цей факт може бути перенесений для оцінки виконання. "
            "Водночас carry-forward не вважається новим Q4-поданням, тому покриття не поліпшується."
        )

        _section(
            "3. Як один захід отримує execution_score",
            "Усі різні типи результатів зводяться до однієї шкали 0–100%, щоб їх можна було агрегувати.",
        )
        score_rules = pd.DataFrame(
            [
                {
                    "Тип даних": "Числовий показник",
                    "Правило": "факт / річний план × 100",
                    "Управлінська оцінка": "результат для execution обмежується зверху 100%",
                    "Приклад": "факт 150, план 200 → 75%; факт 280, план 200 → execution_score 100%",
                },
                {
                    "Тип даних": "Так / Ні",
                    "Правило": "так = досягнуто; ні = не досягнуто",
                    "Управлінська оцінка": "так = 100%; ні = 0%",
                    "Приклад": "«так» → 100%",
                },
                {
                    "Тип даних": "Якісний статус без числової пари",
                    "Правило": "Виконано / Частково виконано / Не виконано / Не подано",
                    "Управлінська оцінка": "100% / 75% / 0% / 0%",
                    "Приклад": "«Частково виконано» → 75%",
                },
                {
                    "Тип даних": "Не настав час / Втратило актуальність",
                    "Правило": "захід не повинен штучно погіршувати середнє",
                    "Управлінська оцінка": "execution_score не включається до середнього",
                    "Приклад": "немає числового балу для агрегації",
                },
                {
                    "Тип даних": "Активний захід без жодного підтвердженого результату року",
                    "Правило": "дані мали бути, але підтвердженого результату немає",
                    "Управлінська оцінка": "0% для управлінського execution",
                    "Приклад": "це не тотожне підтвердженому фактичному нулю",
                },
            ]
        )
        _display_df(score_rules, max_height=420)

        _callout(
            "<b>Перевиконання не компенсує невиконання іншого заходу.</b> Якщо факт перевищив план, "
            "raw attainment може бути вищим за 100%, але execution_score для поточної управлінської "
            "агрегації обмежується 100%."
        )

        score_table_columns = [
            "code", "parent_goal_code", "parent_task_code", "period_state", "status",
            "submitted_current_period", "carry_forward", "source_quarter", "actual",
            "annual_target", "raw_attainment_pct", "execution_score", "result_achieved",
            "coverage_eligible", "missing_required_submission", "data_quality_conflict",
        ]
        score_table = dashboard_snapshot[
            [c for c in score_table_columns if c in dashboard_snapshot.columns]
        ].copy()
        _raw_table(
            "Технічна деталізація: бал кожного заходу",
            score_table,
            note="Тут видно службові поля, з яких безпосередньо формується Q4 execution.",
            max_height=520,
        )

        _section("4. Головні KPI IV кварталу")

        assessed_mask = _safe_numeric_series(dashboard_snapshot, "execution_score").notna()
        assessed = dashboard_snapshot[assessed_mask].copy()
        score_sum = _safe_numeric_series(assessed, "execution_score").sum(min_count=1)
        assessed_count = len(assessed)
        diagnostic_execution = (
            None if assessed_count == 0 or pd.isna(score_sum)
            else float(score_sum) / assessed_count
        )
        _show_formula(
            "Рівень виконання Стратегічного плану за заходами",
            meaning=(
                "Середній управлінський бал усіх заходів, які мають числовий execution_score у Q4. "
                "Показує, наскільки в середньому виконано оцінюваний портфель заходів."
            ),
            population=(
                "Усі рядки Q4 snapshot із непорожнім execution_score. Майбутні та методологічно "
                "виключені заходи без score у знаменник не потрапляють."
            ),
            formula="сума execution_score / кількість оцінених заходів",
            substitution=(
                f"{_n(score_sum)} / {assessed_count}" if assessed_count else "немає оцінених заходів"
            ),
            result=_pct(dashboard_latest.get("execution_by_measures")),
            interpretation=(
                f"У IV кварталі оцінено {assessed_count} заходів. Сума їхніх балів становить "
                f"{_n(score_sum)}. Контрольний перерахунок = {_pct(diagnostic_execution)}; "
                f"shared Dashboard = {_pct(dashboard_latest.get('execution_by_measures'))} "
                f"({_parity_text(diagnostic_execution, dashboard_latest.get('execution_by_measures'))})."
            ),
            caveat=(
                "Це середнє за заходами. Велика стратегічна ціль із великою кількістю заходів має "
                "більшу вагу в цьому KPI, ніж ціль із малою кількістю заходів. Для рівного зважування "
                "цілей існує окремий KPI «Виконання за стратегічними цілями»."
            ),
        )

        coverage_mask = _safe_bool_series(dashboard_snapshot, "coverage_eligible")
        coverage_pop = dashboard_snapshot[coverage_mask].copy()
        coverage_den = len(coverage_pop)
        coverage_num = int(_safe_bool_series(coverage_pop, "submitted").sum())
        diagnostic_coverage = None if coverage_den == 0 else coverage_num / coverage_den * 100.0
        _show_formula(
            "Покриття моніторингом",
            meaning=(
                "Частка заходів, які повинні були мати поточне подання саме за Q4 і справді його мають. "
                "Показник оцінює повноту збору поточних даних, а не рівень виконання."
            ),
            population=(
                "Знаменник — лише coverage_eligible заходи Q4. Чисельник — ті з них, для яких "
                "поточне подання Q4 зараховано як submitted."
            ),
            formula="поточні Q4-подання / coverage_eligible заходи × 100",
            substitution=f"{coverage_num} / {coverage_den} × 100",
            result=_pct(dashboard_latest.get("coverage")),
            interpretation=(
                f"Із {coverage_den} заходів, які мали бути охоплені моніторингом, Q4-подання є за "
                f"{coverage_num}. Контрольний розрахунок = {_pct(diagnostic_coverage)}; shared Dashboard = "
                f"{_pct(dashboard_latest.get('coverage'))}."
            ),
            caveat=(
                "Carry-forward може дати заходу execution_score, але не закриває вимогу нового "
                "квартального подання. Тому виконання може залишатися відносно високим, а покриття — нижчим."
            ),
        )

        _section(
            "5. Агрегація: захід → завдання → стратегічна ціль → весь план",
            "Цей ланцюжок потрібен, щоб окремо бачити середнє за всіма заходами і середнє за ієрархією цілей.",
        )

        task_scores = dashboard_latest.get("task_scores", pd.DataFrame())
        goal_scores = dashboard_latest.get("goal_scores", pd.DataFrame())

        st.markdown(
            "**Рівень завдання.** Для кожного завдання береться середнє арифметичне execution_score "
            "усіх його оцінених заходів. Після цього кожне завдання стає одним окремим значенням на рівні цілі."
        )
        _raw_table(
            "Технічна деталізація: оцінки завдань Q4",
            task_scores,
            max_height=480,
        )

        st.markdown(
            "**Рівень стратегічної цілі.** `by_measures` — середній бал усіх заходів цілі; "
            "`by_tasks` — середнє виконання завдань цієї цілі. Саме `by_tasks` використовується "
            "для головного KPI «Виконання за стратегічними цілями»."
        )
        _raw_table(
            "Технічна деталізація: оцінки стратегічних цілей Q4",
            goal_scores,
            max_height=480,
        )

        if isinstance(goal_scores, pd.DataFrame) and not goal_scores.empty:
            goal_by_tasks = _safe_numeric_series(goal_scores, "by_tasks").dropna()
            diagnostic_goal_execution = (
                None if goal_by_tasks.empty else float(goal_by_tasks.mean())
            )
            _show_formula(
                "Виконання за стратегічними цілями",
                meaning=(
                    "Показує середній рівень виконання стратегічних цілей так, щоб кожна оцінена ціль "
                    "мала однакову вагу незалежно від кількості заходів усередині неї."
                ),
                population="Стратегічні цілі, для яких сформовано by_tasks у Q4.",
                formula="сума by_tasks усіх оцінених цілей / кількість оцінених цілей",
                substitution=(
                    f"{_n(goal_by_tasks.sum())} / {len(goal_by_tasks)}"
                    if not goal_by_tasks.empty else "немає оцінених цілей"
                ),
                result=_pct(dashboard_latest.get("execution_by_goals")),
                interpretation=(
                    f"Контрольний розрахунок = {_pct(diagnostic_goal_execution)}; shared Dashboard = "
                    f"{_pct(dashboard_latest.get('execution_by_goals'))}."
                ),
                caveat=(
                    "Цей KPI не тотожний простому середньому всіх заходів. Різниця між двома KPI є нормальною: "
                    "вони відповідають на різні управлінські питання і по-різному зважують структуру плану."
                ),
            )

        _section("6. Досягнення результату, ризик і «потребує уваги»")

        risk_denom_mask = _safe_numeric_series(dashboard_snapshot, "execution_score").notna()
        risk_denom = int(risk_denom_mask.sum())
        achieved_num = int(
            (_safe_bool_series(dashboard_snapshot, "result_achieved") & risk_denom_mask).sum()
        )
        achieved_pct = None if risk_denom == 0 else achieved_num / risk_denom * 100
        _show_formula(
            "Частка результатів, які вже досягнуто",
            meaning="Показує, для якої частини оцінених заходів цільовий результат уже вважається досягнутим.",
            population="Заходи Q4 з розрахованим execution_score.",
            formula="досягнуті результати / оцінені заходи × 100",
            substitution=f"{achieved_num} / {risk_denom} × 100",
            result=_pct(dashboard_risk.get("share_results_achieved")),
            interpretation=(
                f"Контрольний розрахунок = {_pct(achieved_pct)}; shared risk_summary = "
                f"{_pct(dashboard_risk.get('share_results_achieved'))}."
            ),
        )

        q4_attention = attention_mask(dashboard_snapshot).reindex(
            dashboard_snapshot.index, fill_value=False
        )
        q4_attention_count = int(q4_attention.sum())
        q4_unique = (
            dashboard_snapshot["code"].nunique()
            if "code" in dashboard_snapshot.columns else len(dashboard_snapshot)
        )
        st.markdown(
            f"**Потребує уваги в Q4: {q4_attention_count} із {q4_unique} унікальних заходів snapshot.**"
        )
        st.markdown(
            "`attention_mask` об'єднує причини логічним **АБО**. Якщо один захід одночасно має, наприклад, "
            "високий ризик, пропущене подання і конфлікт даних, у загальному UNION він усе одно рахується один раз."
        )
        _display_df(_reason_table(dashboard_snapshot), max_height=380)
        _callout(
            "Кількості окремих причин можуть перекриватися. Їх не можна просто скласти між собою: "
            "сума причин може бути більшою за кількість унікальних заходів, що потребують уваги.",
            warning=True,
        )

        _raw_table(
            "Технічна деталізація: поля risk_summary Q4",
            pd.DataFrame(
                [
                    {"Поле risk_summary": key, "Значення": value}
                    for key, value in dashboard_risk.items()
                    if not isinstance(value, (dict, list, pd.DataFrame, pd.Series))
                ]
            ),
            note=(
                "У фінальному Q4 прогнозні категорії ризику можуть бути н/д, бо Q4 є фінальним результатом, "
                "а не прогнозним кварталом. Частки досягнення та інші factual metrics при цьому залишаються валідними."
            ),
            max_height=420,
        )

        _section("7. Динаміка I → IV квартал та average / latest / change")
        _display_df(dashboard_q, max_height=300)

        dash_exec_delta = _q1_q4_delta(dashboard_q, "Виконання за заходами, %")
        q1_exec_series = dashboard_q.loc[
            dashboard_q["Квартал"].eq("I"), "Виконання за заходами, %"
        ]
        q4_exec_series = dashboard_q.loc[
            dashboard_q["Квартал"].eq("IV"), "Виконання за заходами, %"
        ]
        q1_exec = q1_exec_series.iloc[0] if not q1_exec_series.empty else None
        q4_exec = q4_exec_series.iloc[0] if not q4_exec_series.empty else None
        _show_formula(
            "Зміна виконання I → IV квартал",
            meaning="Чиста зміна готового квартального KPI між першим і четвертим кварталом.",
            population="Два квартальні значення одного й того самого KPI.",
            formula="виконання Q4 − виконання Q1",
            substitution=f"{_pct(q4_exec)} − {_pct(q1_exec)}",
            result=_pp(dash_exec_delta),
            interpretation="Позитивне значення означає зростання рівня виконання; від'ємне — зниження.",
            caveat="Це відсоткові пункти, а не відсоткова зміна відносно Q1.",
        )

        aggregate_view = pd.DataFrame(
            [
                {
                    "Показник": "Виконання за заходами",
                    "Average I–IV": dashboard_aggregate.get("execution_by_measures_average"),
                    "Latest Q4": dashboard_aggregate.get("execution_by_measures_latest"),
                    "Q4 − Q1": dashboard_aggregate.get("execution_by_measures_change"),
                },
                {
                    "Показник": "Виконання за стратегічними цілями",
                    "Average I–IV": dashboard_aggregate.get("execution_by_goals_average"),
                    "Latest Q4": dashboard_aggregate.get("execution_by_goals_latest"),
                    "Q4 − Q1": dashboard_aggregate.get("execution_by_goals_change"),
                },
                {
                    "Показник": "Покриття",
                    "Average I–IV": dashboard_aggregate.get("coverage_average"),
                    "Latest Q4": dashboard_aggregate.get("coverage_latest"),
                    "Q4 − Q1": dashboard_aggregate.get("coverage_change"),
                },
            ]
        )
        _display_df(aggregate_view, max_height=260)
        _callout(
            "<b>Ключова відмінність.</b> `average` — середнє квартальних KPI, `latest` — останній доступний квартал, "
            "`change` — останній мінус перший. Ці три поля не можна називати одним і тим самим показником без уточнення часу."
        )

        _raw_table(
            "Технічна деталізація: shared dynamics_frame",
            dynamics_frame(dashboard_results),
            max_height=420,
        )
        _raw_table(
            "Технічна деталізація: стратегічні цілі — average / latest / change",
            aggregate_objects(dashboard_results, object_type="goal"),
            max_height=520,
        )
        _raw_table(
            "Технічна деталізація: завдання — average / latest / change",
            aggregate_objects(dashboard_results, object_type="task"),
            max_height=520,
        )

        _section("8. ССП, заступники Міністра та фінансування")
        st.markdown(
            "На рівні ССП і заступників використовуються ті самі квартальні execution-показники, "
            "після чого shared-агрегація формує average, latest і change для відповідного портфеля."
        )
        _raw_table(
            "ССП: детальна таблиця",
            ssp_summary(dashboard_results, base_results=dashboard_results),
            note=(
                "Вага портфеля, якщо присутня, базується на унікальному портфелі shared-модуля, "
                "а не на сумі measure-period рядків."
            ),
            max_height=520,
        )
        _raw_table(
            "Заступники Міністра: детальна таблиця",
            deputy_summary(dashboard_results),
            max_height=520,
        )

        try:
            finance_frame = build_finance_frame(dashboard_snapshot, YEAR)
            fin_kpi = finance_kpis(finance_frame)
            _show_formula(
                "Фінансове виконання",
                meaning="Частка сукупного фактичного фінансування від сукупного річного плану фінансування портфеля.",
                population="Унікальні заходи Q4, для яких фінансовий shared-модуль сформував валідні план/факт.",
                formula="сума факту / сума плану × 100",
                substitution=f"{_n(fin_kpi.get('fact_bln'))} / {_n(fin_kpi.get('plan_bln'))} × 100",
                result=_pct(fin_kpi.get("financial_execution_pct")),
                interpretation="Показує виконання фінансового плану всього портфеля в цілому.",
                caveat="Це ratio of sums, а не середнє індивідуальних відсотків фінансового виконання заходів.",
            )
            _raw_table(
                "Фінансування: вхідна таблиця",
                finance_frame,
                max_height=520,
            )
        except Exception as exc:
            st.warning(f"Фінансовий блок не вдалося відтворити: {exc}")


# =============================================================================
# TAB 2 — ANALYTICS
# =============================================================================

with _tab_ana:
    _section(
        "1. Що саме є вибіркою сторінки «Аналітика»",
        "За фіксованого вибору I, II, III, IV кварталів Analytics створює квартальні snapshots, "
        "а потім вертикально об'єднує їх у `active`. Саме тому один захід може повторюватися кілька разів.",
    )

    active_rows = len(analytics_active)
    active_unique = (
        analytics_active["code"].nunique()
        if not analytics_active.empty and "code" in analytics_active.columns else 0
    )
    _a1, _a2, _a3, _a4 = st.columns(4)
    _a1.metric("Рядків захід × квартал", active_rows)
    _a2.metric("Унікальних заходів", active_unique)
    _a3.metric("Потребують уваги", _int(analytics_metrics.get("problem")))
    _a4.metric("Без даних", _int(analytics_metrics.get("no_data")))

    _callout(
        "<b>Найважливіше для читання Analytics.</b> `active_rows` і частина problem/no_data-показників мають одиницю "
        "<b>захід × квартал</b>, тоді як картка «Заходів у вибірці» має одиницю <b>унікальний захід</b>. "
        "Такі числа не можна автоматично трактувати як «X із Y», якщо одиниці різні."
    )

    analytics_source_rows = []
    for q in QUARTERS:
        key = (YEAR, q)
        item = analytics_results.get(key, {})
        snap = item.get("snapshot", pd.DataFrame())
        analytics_source_rows.append(
            {
                "Квартал": q,
                "Джерело поточного Analytics": "Поточний live-контур",
                "Dashboard мав архів": "так" if key in dashboard_period_sources else "ні",
                "Рядків snapshot": len(snap) if isinstance(snap, pd.DataFrame) else 0,
                "Унікальних заходів": (
                    snap["code"].nunique()
                    if isinstance(snap, pd.DataFrame) and not snap.empty and "code" in snap.columns
                    else 0
                ),
                "Виконання, %": item.get("execution_by_measures"),
                "Покриття, %": item.get("coverage"),
            }
        )
    _display_df(pd.DataFrame(analytics_source_rows), max_height=300)

    _section("2. Чотири головні картки Analytics")
    analytics_kpi_guide = pd.DataFrame(
        [
            {
                "Назва в Analytics": "Рівень виконання Стратегічного плану в обраному періоді",
                "Що показує зараз": "execution_by_measures_average",
                "Одиниця": "%",
                "Як рахується за I–IV": "середнє чотирьох квартальних KPI виконання",
                "Важливе уточнення": "це не Q4; для Q4 існує completion_latest",
            },
            {
                "Назва в Analytics": "Потребують управлінської уваги",
                "Що показує зараз": "сума is_problem_status по active",
                "Одиниця": "захід × квартал",
                "Як рахується за I–IV": "сума проблемних measure-period рядків усіх обраних кварталів",
                "Важливе уточнення": "один захід може бути порахований у кількох кварталах",
            },
            {
                "Назва в Analytics": "Покриття моніторингом",
                "Що показує зараз": "coverage_average",
                "Одиниця": "%",
                "Як рахується за I–IV": "середнє готових квартальних coverage",
                "Важливе уточнення": "це не частка всіх річних подань від усіх річних обов'язкових подань одним ratio",
            },
            {
                "Назва в Analytics": "Заходів у вибірці",
                "Що показує зараз": "unique_measures",
                "Одиниця": "унікальний захід",
                "Як рахується за I–IV": "nunique(code) у склеєному active",
                "Важливе уточнення": "не дорівнює кількості active rows",
            },
        ]
    )
    _display_df(analytics_kpi_guide, max_height=360)

    analytics_exec_values = analytics_q["Виконання за заходами, %"].dropna().tolist()
    analytics_exec_mean_check = _mean(analytics_exec_values)
    expression = " + ".join(_pct(v) for v in analytics_exec_values)
    denominator = len(analytics_exec_values)
    _show_formula(
        "Картка Analytics «Рівень виконання Стратегічного плану в обраному періоді»",
        meaning="Середній рівень квартального виконання за всіма обраними кварталами.",
        population="Готові квартальні KPI execution_by_measures за I, II, III, IV квартали, де значення доступне.",
        formula="(Q1 + Q2 + Q3 + Q4) / кількість доступних квартальних KPI",
        substitution=(
            f"({expression}) / {denominator}" if denominator else "немає квартальних значень"
        ),
        result=_pct(analytics_metrics.get("completion")),
        interpretation=(
            f"Контрольне середнє = {_pct(analytics_exec_mean_check)}. Latest Q4 окремо = "
            f"{_pct(analytics_plan.get('execution_by_measures_latest'))}; Dashboard Q4 = "
            f"{_pct(dashboard_latest.get('execution_by_measures'))}."
        ),
        caveat="Якщо вибрано кілька кварталів, назва «в обраному періоді» означає average квартальних KPI, а не стан на останню дату.",
    )

    analytics_cov_values = analytics_q["Покриття, %"].dropna().tolist()
    analytics_cov_mean_check = _mean(analytics_cov_values)
    cov_expression = " + ".join(_pct(v) for v in analytics_cov_values)
    cov_denominator = len(analytics_cov_values)
    _show_formula(
        "Картка Analytics «Покриття моніторингом»",
        meaning="Середнє квартальних показників повноти поточних подань у межах вибраних кварталів.",
        population="Готові квартальні coverage за I–IV, де значення доступне.",
        formula="(coverage Q1 + Q2 + Q3 + Q4) / кількість доступних кварталів",
        substitution=(
            f"({cov_expression}) / {cov_denominator}" if cov_denominator else "немає квартальних значень"
        ),
        result=_pct(analytics_metrics.get("coverage")),
        interpretation=(
            f"Контрольне середнє = {_pct(analytics_cov_mean_check)}. Latest Q4 = "
            f"{_pct(analytics_plan.get('coverage_latest'))}; Dashboard Q4 = {_pct(dashboard_latest.get('coverage'))}."
        ),
        caveat="Average квартальних відсотків не обов'язково дорівнює ratio суми всіх подань до суми всіх eligible-спостережень за рік.",
    )

    _section("3. «Потребують управлінської уваги» та «Без даних»")
    if analytics_active.empty:
        st.caption("Analytics active порожній.")
    else:
        active_attention = _safe_bool_series(analytics_active, "is_problem_status")
        attention_rows = int(active_attention.sum())
        attention_by_quarter = (
            analytics_active.assign(_attention=active_attention)
            .groupby("report_quarter", dropna=False)
            .agg(
                Рядків_з_увагою=("_attention", "sum"),
                Усього_рядків=("code", "size"),
                Унікальних_заходів=("code", "nunique"),
            )
            .reset_index()
            .rename(columns={"report_quarter": "Квартал"})
        )
        _display_df(attention_by_quarter, max_height=300)

        unique_attention_codes = (
            analytics_active.loc[active_attention, "code"].nunique()
            if "code" in analytics_active.columns else 0
        )
        _show_formula(
            "Поточне число «Потребують управлінської уваги»",
            meaning="Кількість проблемних спостережень у склеєному масиві I–IV.",
            population="Усі active measure-period rows, для яких is_problem_status=True.",
            formula="attention rows Q1 + Q2 + Q3 + Q4",
            substitution=" + ".join(
                str(int(v)) for v in attention_by_quarter["Рядків_з_увагою"].tolist()
            ),
            result=str(attention_rows),
            interpretation=(
                f"Це {attention_rows} спостережень «захід × квартал». Унікальних кодів заходів, які хоча б "
                f"раз потребували уваги протягом року, — {unique_attention_codes}."
            ),
            caveat=(
                "Не діліть це число на «Заходів у вибірці», якщо знаменник є unique measures. "
                "Для відсоткової частки numerator і denominator повинні мати однакову одиницю спостереження."
            ),
        )

        missing_mask = _safe_bool_series(analytics_active, "missing_required_submission")
        if not missing_mask.any() and "has_current_submission" in analytics_active.columns:
            # Це лише пояснювальний fallback для відображення; production metrics уже готові.
            missing_mask = ~_safe_bool_series(analytics_active, "has_current_submission")
        missing_by_quarter = (
            analytics_active.assign(_missing=missing_mask)
            .groupby("report_quarter", dropna=False)
            .agg(Без_даних=("_missing", "sum"), Усього_рядків=("code", "size"))
            .reset_index()
            .rename(columns={"report_quarter": "Квартал"})
        )
        _raw_table(
            "Розклад «Без даних» за кварталами",
            missing_by_quarter,
            note=(
                "Основна картка/текст використовує prepared metric із production-контексту. Ця таблиця потрібна "
                "для розуміння, в яких кварталах концентруються пропуски."
            ),
            max_height=300,
        )

    _section("4. Статуси, цілі, завдання, ССП і типи продукту")
    st.markdown(
        "У багатоквартальній вибірці частина лічильників є measure-period counts. Саме тому в таблицях поряд "
        "існують окремі поля `Заходів_періодів` і `Унікальних_заходів`."
    )

    _raw_table(
        "Статуси Analytics I–IV: measure-period rows",
        _status_counts(analytics_active),
        note="Один захід може потрапити в різні статуси в різних кварталах.",
        max_height=420,
    )
    _raw_table(
        "Статуси Q4 snapshot: стан унікальних заходів в останньому кварталі",
        _status_counts(analytics_q4_snapshot),
        note="Це інша семантика: один поточний Q4-рядок на захід.",
        max_height=420,
    )
    _raw_table(
        "Стратегічні цілі: показники, які використовує Analytics",
        analytics_goals,
        note=(
            "Виконання/Останнє_виконання/Зміна походять із shared object aggregation. "
            "Проблемних і Без_даних — counts по active; Унікальних_заходів — окрема unique-measure величина."
        ),
        max_height=560,
    )
    _raw_table(
        "Завдання: показники, які використовує Analytics",
        analytics_tasks,
        max_height=560,
    )
    _raw_table(
        "ССП: показники, які використовує Analytics",
        analytics_ssp,
        max_height=560,
    )
    _raw_table(
        "Типи продукту: показники, які використовує Analytics",
        analytics_products,
        note=(
            "Виконання і Покриття_% є квартально агрегованими значеннями для підмножини типу продукту; "
            "Унікальних_заходів — висота відповідної колонки на графіку «Структура заходів за типами продукту»."
        ),
        max_height=520,
    )

    _section("5. Оцінка МіО — окремий річний контур")
    st.markdown(
        "МіО не є квартальним Dashboard snapshot. Це річна модель, яка використовує повний monitoring stream, "
        "включно з поданнями індикаторів цілей і завдань. Для кожної стратегічної цілі інтеграл формується з трьох компонентів."
    )
    mio_formula = pd.DataFrame(
        [
            {"Компонент": "Виконання заходів цілі", "Вага": "20%", "Що означає": "середній рівень виконання заходів відповідної стратегічної цілі"},
            {"Компонент": "Оцінка завдань цілі", "Вага": "30%", "Що означає": "середня оцінка завдань, що входять до стратегічної цілі"},
            {"Компонент": "Прогрес індикаторів цілі", "Вага": "50%", "Що означає": "прогрес власних стратегічних індикаторів цілі"},
        ]
    )
    _display_df(mio_formula, max_height=260)
    st.markdown("**Формула інтегралу стратегічної цілі:** `0.20 × I + 0.30 × J + 0.50 × K`.")

    if not mio_goals.empty:
        try:
            mio_summary = mio_shared.summarize_integral_goals(mio_goals, YEAR)
            _m1, _m2, _m3, _m4 = st.columns(4)
            _m1.metric("Інтегральна оцінка", _pct(mio_summary.average_integral))
            _m2.metric("Виконання заходів", _pct(mio_summary.average_measure_execution))
            _m3.metric("Оцінка завдань", _pct(mio_summary.average_task_score))
            _m4.metric("Прогрес індикаторів", _pct(mio_summary.average_strategic_progress))
        except Exception as exc:
            st.warning(f"Зведення МіО не вдалося сформувати: {exc}")

        # Показуємо не лише готовий інтеграл, а й підстановку трьох компонентів
        # для кожної стратегічної цілі. Це контрольне пояснення; shared МіО не змінюється.
        mio_check_rows = []
        for _, row in mio_goals.iterrows():
            i = _num(row.get(f"Заходи {YEAR}"))
            j = _num(row.get(f"Завдання {YEAR}"))
            k = _num(row.get(f"Прогрес {YEAR}"))
            shared_integral = _num(row.get(f"Інтеграл {YEAR}"))
            if i is None and j is None and k is None and shared_integral is None:
                continue
            i_calc, j_calc, k_calc = i or 0.0, j or 0.0, k or 0.0
            control_integral = 0.20 * i_calc + 0.30 * j_calc + 0.50 * k_calc
            mio_check_rows.append(
                {
                    "Код цілі": row.get("Код"),
                    "Стратегічна ціль": row.get("Ціль"),
                    "I — заходи, %": i,
                    "J — завдання, %": j,
                    "K — індикатори, %": k,
                    "Підстановка у формулу": (
                        f"0.20 × {_n(i_calc)} + 0.30 × {_n(j_calc)} + 0.50 × {_n(k_calc)}"
                    ),
                    "Контрольний інтеграл, %": control_integral,
                    "Shared інтеграл, %": shared_integral,
                    "Звірка": _parity_text(control_integral, shared_integral),
                }
            )

        if mio_check_rows:
            st.markdown(
                "**Як читати інтеграл по кожній цілі.** I — виконання заходів, J — оцінка завдань, "
                "K — прогрес стратегічних індикаторів. Колонка «Контрольний інтеграл» показує просту "
                "підстановку у формулу 20/30/50, а «Shared інтеграл» — значення, яке реально повернув "
                "модуль МіО. «ЗБІГАЄТЬСЯ» означає, що контрольний перерахунок підтверджує shared-результат."
            )
            _display_df(pd.DataFrame(mio_check_rows), max_height=520)

        _raw_table(
            "МіО: інтегральні оцінки стратегічних цілей",
            mio_goals,
            max_height=560,
        )
    else:
        st.caption("Річні МіО-дані у поточному контексті відсутні або не сформувалися.")

    _section("6. Dashboard Q4 vs Analytics current — що саме відрізняється")
    dash_q4_attention = (
        int(attention_mask(dashboard_snapshot).sum()) if not dashboard_snapshot.empty else 0
    )
    analytics_unique_attention = (
        analytics_active.loc[
            _safe_bool_series(analytics_active, "is_problem_status"), "code"
        ].nunique()
        if not analytics_active.empty and "code" in analytics_active.columns else 0
    )
    final_diff = pd.DataFrame(
        [
            {
                "Тема": "Виконання",
                "Dashboard": _pct(dashboard_latest.get("execution_by_measures")),
                "Analytics": _pct(analytics_metrics.get("completion")),
                "Одиниця": "%",
                "Чому різниться": "Dashboard = Q4 latest; Analytics = average I–IV",
            },
            {
                "Тема": "Покриття",
                "Dashboard": _pct(dashboard_latest.get("coverage")),
                "Analytics": _pct(analytics_metrics.get("coverage")),
                "Одиниця": "%",
                "Чому різниться": "Dashboard = Q4 latest; Analytics = average I–IV",
            },
            {
                "Тема": "Потребують уваги",
                "Dashboard": str(dash_q4_attention),
                "Analytics": str(_int(analytics_metrics.get("problem"))),
                "Одиниця": "Dashboard: unique Q4 row; Analytics: measure-period",
                "Чому різниться": f"Analytics unique attention measures I–IV окремо = {analytics_unique_attention}",
            },
            {
                "Тема": "Заходів у вибірці",
                "Dashboard": str(
                    dashboard_snapshot["code"].nunique()
                    if not dashboard_snapshot.empty and "code" in dashboard_snapshot.columns else 0
                ),
                "Analytics": str(active_unique),
                "Одиниця": "унікальний захід",
                "Чому різниться": "Q4 applicable portfolio vs union заходів, які потрапили хоча б в один I–IV snapshot",
            },
        ]
    )
    _display_df(final_diff, max_height=360)


# =============================================================================
# TAB 3 — CHART GUIDE
# =============================================================================

with _tab_charts:
    _section(
        "Графіки сторінки «Аналітика»: що саме означає кожна назва",
        "Нижче наведено точну семантику поточних графіків. Це не нові формули — це пояснення того, "
        "які вже готові поля Analytics потрапляють на осі та в hover.",
    )

    chart_guide = pd.DataFrame(
        [
            {
                "Точна назва графіка": "Зміна ключових показників рік до року",
                "Що на осі / у секторі": "X: показник; Y: Зміна, в.п.; групування: період порівняння",
                "Що фактично вимірюється": "різниця між поточним і попереднім роком для покриття та рівня виконання СП",
                "Одиниця": "відсоткові пункти",
                "Ключове застереження": "це різниця двох відсоткових KPI, не темп приросту у %",
            },
            {
                "Точна назва графіка": "Динаміка оціненого виконання",
                "Що на осі / у секторі": "X: Період; Y: Виконання",
                "Що фактично вимірюється": "готовий канонічний execution KPI кожного звітного періоду",
                "Одиниця": "%",
                "Ключове застереження": "лінія не є накопичувальною сумою; кожна точка — окремий квартальний зріз",
            },
            {
                "Точна назва графіка": "Виконання за стратегічними цілями",
                "Що на осі / у секторі": "X: код СЦ; Y: поле Виконання; hover: назва, унікальні заходи, покриття, проблемні, без даних",
                "Що фактично вимірюється": "агрегований execution стратегічної цілі за вибраними періодами",
                "Одиниця": "%",
                "Ключове застереження": "за кількох кварталів поле Виконання є average; останній квартал зберігається окремо",
            },
            {
                "Точна назва графіка": "Виконання за самостійними структурними підрозділами",
                "Що на осі / у секторі": "X: ССП; Y: поле Виконання; hover: заступник, унікальні заходи, покриття, проблемні, без даних",
                "Що фактично вимірюється": "агрегований рівень execution портфеля заходів відповідного ССП",
                "Одиниця": "%",
                "Ключове застереження": "порівнюються портфелі різного розміру; hover окремо показує кількість унікальних заходів",
            },
            {
                "Точна назва графіка": "Структура заходів за типами продукту",
                "Що на осі / у секторі": "X: тип продукту; Y: Унікальних_заходів; hover: виконання, покриття, проблемні, без даних",
                "Що фактично вимірюється": "розмір портфеля кожного типу продукту за кількістю унікальних заходів",
                "Одиниця": "унікальний захід",
                "Ключове застереження": "висота стовпчика — НЕ виконання; execution показується лише в hover",
            },
            {
                "Точна назва графіка": "Структура статусів виконання",
                "Що на осі / у секторі": "сектори: status; значення: Кількість",
                "Що фактично вимірюється": "скільки active measure-period rows мають кожний статус у вибраних кварталах",
                "Одиниця": "захід × квартал",
                "Ключове застереження": "у багатоквартальній вибірці це не структура унікальних заходів станом на Q4",
            },
            {
                "Точна назва графіка": "Завдання з найбільшою кількістю сигналів управлінської уваги",
                "Що на осі / у секторі": "X: код завдання; Y: Проблемних; показуються top-10",
                "Що фактично вимірюється": "кількість проблемних measure-period rows, віднесених до кожного завдання",
                "Одиниця": "сигнал/захід × квартал",
                "Ключове застереження": "це кількість проблемних спостережень, а не обов'язково кількість унікальних проблемних заходів",
            },
            {
                "Точна назва графіка": "Рейтинг ССП за кількістю повернень",
                "Що на осі / у секторі": "X: ССП; Y: кількість повернень",
                "Що фактично вимірюється": "кількість подій повернення заявок на доопрацювання за журналом дій",
                "Одиниця": "подія повернення",
                "Ключове застереження": "це тестовий workflow-блок; одна заявка може повертатися більше одного разу",
            },
            {
                "Точна назва графіка": "Розподіл за ланками, які повертають",
                "Що на осі / у секторі": "X: ланка, що повернула; Y: кількість повернень",
                "Що фактично вимірюється": "на яких ланках workflow виникають події повернення",
                "Одиниця": "подія повернення",
                "Ключове застереження": "це тестовий workflow-блок, джерело — monitoring_logs",
            },
        ]
    )
    _display_df(chart_guide, max_height=560)

    chart_details = [
        (
            "Динаміка оціненого виконання",
            "Кожна точка лінії — окремий квартальний KPI `execution_by_measures`. Якщо вибрано I–IV, "
            "графік показує чотири незалежні квартальні значення у хронологічному порядку. Лінія допомагає побачити "
            "напрям зміни, але не означає накопичення виконання від кварталу до кварталу. Для кількісного висновку "
            "між першим і останнім кварталом використовується `change = latest − first` у відсоткових пунктах."
        ),
        (
            "Виконання за стратегічними цілями",
            "Стовпчик відповідає полю `Виконання` з `goal_progress`. За багатоквартальної вибірки це агреговане average "
            "по кварталах. У hover додатково показуються назва цілі, кількість унікальних заходів, покриття, проблемні "
            "measure-period rows та рядки без даних. Тому hover поєднує показники різних одиниць, і кожен треба читати окремо."
        ),
        (
            "Виконання за самостійними структурними підрозділами",
            "Висота стовпчика — execution портфеля конкретного ССП у вибраному періоді. Поруч у hover є розмір портфеля, "
            "покриття і кількість проблемних/безданих спостережень. Два ССП з однаковим execution можуть мати дуже різний "
            "розмір портфеля, тому сам рейтинг виконання не є рейтингом масштабу або навантаження."
        ),
        (
            "Структура заходів за типами продукту",
            "Цей графік є структурним, а не результативним: висота стовпчика показує кількість унікальних заходів певного "
            "типу продукту. Показники виконання та покриття знаходяться лише у hover і не визначають висоту стовпчика."
        ),
        (
            "Структура статусів виконання",
            "Для вибору I–IV статуси підраховуються в склеєному `active`. Отже, один захід може дати до чотирьох внесків у "
            "діаграму і навіть потрапити в різні сектори в різні квартали. Якщо потрібен саме поточний статус унікальних "
            "заходів, треба дивитися Q4 snapshot, а не річний active."
        ),
        (
            "Завдання з найбільшою кількістю сигналів управлінської уваги",
            "Завдання сортуються за полем `Проблемних`, а при рівності — за `Без_даних`; на графік потрапляють перші 10. "
            "Це інструмент пріоритезації проблемних спостережень. Він не доводить, що саме ці завдання мають найнижчий "
            "відсоток виконання: кількість сигналів і execution — різні характеристики."
        ),
    ]
    for title, body in chart_details:
        with st.expander(title, expanded=False):
            st.write(body)

    _callout(
        "<b>Графіки в DOCX.</b> Експортована аналітична довідка використовує ті самі агрегати, але має трохи інші "
        "підписи: «Динаміка оціненого виконання, %», «Розподіл заходів за статусами виконання», "
        "«Рівень виконання за стратегічними цілями, %» та «Рівень виконання за ССП (топ-15), %». "
        "Методологічно це ті самі джерела даних, що й екранні графіки."
    )


# =============================================================================
# TAB 4 — ANALYTICAL FACT METRICS
# =============================================================================

with _tab_metrics:
    _section(
        "Показники, які може згадувати автоматично сформована аналітична довідка",
        "Rule-based текстовий engine не повинен вигадувати числа. Перед генерацією він отримує реєстр prepared factual metrics. "
        "Нижче спочатку наведено людський словник ключових полів Analytics, а потім — повний фактичний реєстр поточного контексту.",
    )

    human_metrics = pd.DataFrame(
        [
            {
                "Показник": "Рівень виконання СП",
                "Тип": "результативність",
                "Одиниця": "%",
                "Що означає": "середній execution оцінених заходів; у multi-quarter Analytics основна картка показує average квартальних KPI",
                "Не плутати з": "latest Q4 та виконанням за стратегічними цілями",
            },
            {
                "Показник": "Рівень виконання за стратегічними цілями",
                "Тип": "ієрархічна результативність",
                "Одиниця": "%",
                "Що означає": "середній результат цілей через ланцюжок заходи → завдання → ціль",
                "Не плутати з": "простим середнім усіх заходів плану",
            },
            {
                "Показник": "Покриття моніторингом",
                "Тип": "якість/повнота даних",
                "Одиниця": "%",
                "Що означає": "частка обов'язкових поточних подань, які реально подані в кварталі; у Analytics multi-quarter — average квартальних coverage",
                "Не плутати з": "виконанням заходів",
            },
            {
                "Показник": "Потребують управлінської уваги / Проблемних",
                "Тип": "сигнал",
                "Одиниця": "захід × квартал у current Analytics",
                "Що означає": "кількість рядків, де канонічний attention/problem flag істинний",
                "Не плутати з": "кількістю унікальних проблемних заходів без deduplication",
            },
            {
                "Показник": "Без даних",
                "Тип": "якість даних",
                "Одиниця": "захід × квартал",
                "Що означає": "кількість спостережень, для яких немає потрібного поточного/підтвердженого інформаційного покриття за правилом metric builder",
                "Не плутати з": "фактичним значенням 0",
            },
            {
                "Показник": "Унікальних заходів",
                "Тип": "розмір портфеля",
                "Одиниця": "унікальний захід",
                "Що означає": "кількість різних кодів заходів у вибірці",
                "Не плутати з": "кількістю measure-period rows",
            },
            {
                "Показник": "Average / Latest / Change",
                "Тип": "часова семантика",
                "Одиниця": "% / % / в.п.",
                "Що означає": "середнє кварталів / останній квартал / останній мінус перший",
                "Не плутати з": "трьома назвами одного й того самого числа",
            },
            {
                "Показник": "Частка високого та критичного ризику",
                "Тип": "ризик",
                "Одиниця": "%",
                "Що означає": "підготовлений factual metric із risk summary; numerator і denominator мають сумісну одиницю спостереження",
                "Не плутати з": "часткою проблемних рядків, якщо їхні критерії відрізняються",
            },
            {
                "Показник": "Частка без обов'язкового/поточного подання",
                "Тип": "покриття/ризик даних",
                "Одиниця": "%",
                "Що означає": "підготовлена частка missing-подань у відповідній сумісній популяції",
                "Не плутати з": "100% − execution",
            },
            {
                "Показник": "Інтегральна оцінка МіО",
                "Тип": "річна інтегральна оцінка",
                "Одиниця": "%",
                "Що означає": "середнє готових інтегральних оцінок стратегічних цілей; кожна ціль має формулу 20%/30%/50%",
                "Не плутати з": "20% від виконання заходів",
            },
            {
                "Показник": "Фінансове виконання",
                "Тип": "фінанси",
                "Одиниця": "%",
                "Що означає": "сума фактичного фінансування / сума планового фінансування × 100",
                "Не плутати з": "середнім індивідуальних фінансових відсотків заходів",
            },
        ]
    )
    _display_df(human_metrics, max_height=560)

    _callout(
        "<b>Як читати реєстр factual metrics нижче.</b> `Код` — внутрішній стабільний ідентифікатор факту. "
        "`Джерело` показує, з якого prepared/shared масиву взято число. `Агрегація` описує операцію. "
        "Для часток окремо зберігаються чисельник, знаменник та одиниця спостереження — це захист від ділення "
        "несумісних величин на кшталт measure-period / unique-measure."
    )

    if analytics_text_context is None:
        st.warning(
            "Повний factual metric registry не вдалося побудувати в цьому запуску. "
            f"Причина: {analytics_fact_error}"
        )
    else:
        facts = getattr(analytics_text_context, "analytical_facts", None)
        metrics_map = getattr(facts, "metrics", {}) if facts is not None else {}
        fact_rows = []
        for code, metric in sorted(metrics_map.items(), key=lambda item: str(item[0])):
            fact_rows.append(
                {
                    "Група": _metric_group(str(code)),
                    "Код": str(code),
                    "Значення": _format_fact_value(metric.value, metric.unit),
                    "Одиниця": metric.unit,
                    "Джерело": metric.source,
                    "Агрегація": metric.aggregation,
                    "Чисельник": metric.numerator,
                    "Знаменник": metric.denominator,
                    "Одиниця спостереження": metric.observation_unit or "—",
                }
            )
        facts_df = pd.DataFrame(fact_rows)
        _f1, _f2 = st.columns([1, 3])
        with _f1:
            st.metric("Prepared factual metrics", len(facts_df))
        with _f2:
            groups = sorted(facts_df["Група"].dropna().astype(str).unique().tolist()) if not facts_df.empty else []
            selected_group = st.selectbox(
                "Фільтр реєстру за групою",
                ["Усі"] + groups,
                key="calc_fact_metric_group",
            )
        shown_facts = facts_df if selected_group == "Усі" else facts_df[facts_df["Група"].eq(selected_group)]
        _display_df(shown_facts, max_height=620)

        with st.expander("Що означають технічні поля factual metric", expanded=False):
            technical_glossary = pd.DataFrame(
                [
                    {"Поле": "source", "Пояснення": "конкретний prepared/shared масив або KPI, з якого взято факт"},
                    {"Поле": "aggregation", "Пояснення": "спосіб отримання числа: mean, median, total, maximum, ratio, rank, latest тощо"},
                    {"Поле": "numerator / denominator", "Пояснення": "для ratio-показників показує, які дві величини сформували частку"},
                    {"Поле": "observation_unit", "Пояснення": "одиниця спостереження — unique-measure, measure-period, goal, task, department тощо"},
                    {"Поле": "percent", "Пояснення": "значення зберігається у шкалі 0–100, якщо metric явно не дозволяє >100"},
                    {"Поле": "pp", "Пояснення": "відсоткові пункти; зазвичай різниця двох відсоткових значень"},
                ]
            )
            _display_df(technical_glossary, max_height=360)


# =============================================================================
# TAB 5 — TECHNICAL RECONCILIATION
# =============================================================================

with _tab_tech:
    _section(
        "Вхідні масиви та технічна звірка Dashboard ↔ Analytics",
        "Ця вкладка потрібна для пошуку джерела розбіжності. Тут мінімум пояснювального тексту і максимум контрольних таблиць.",
    )
    _display_df(input_summary, max_height=300)

    source_compare = []
    for q in QUARTERS:
        d = dashboard_results.get((YEAR, q), {})
        a = analytics_results.get((YEAR, q), {})
        source_compare.append(
            {
                "Квартал": q,
                "Dashboard source": _source_label(dashboard_period_sources, (YEAR, q)),
                "Dashboard execution": d.get("execution_by_measures"),
                "Analytics execution": a.get("execution_by_measures"),
                "Execution parity": _parity_text(d.get("execution_by_measures"), a.get("execution_by_measures")),
                "Dashboard coverage": d.get("coverage"),
                "Analytics coverage": a.get("coverage"),
                "Coverage parity": _parity_text(d.get("coverage"), a.get("coverage")),
            }
        )
    _display_df(pd.DataFrame(source_compare), max_height=330)

    _callout(
        "Якщо Dashboard і Analytics відрізняються вже в одному й тому самому кварталі, це не average-vs-latest. "
        "Тоді потрібно перевіряти source: archive snapshot Dashboard проти live-контуру Analytics, склад стратегічної "
        "матриці, closeouts, period locks та інші джерельні відмінності.",
        warning=True,
    )

    _raw_table(
        "Повний Dashboard Q4 snapshot",
        dashboard_snapshot,
        max_height=620,
    )
    _raw_table(
        "Повний Analytics active I–IV",
        analytics_active,
        note="Один захід може повторюватися до чотирьох разів — по одному рядку на квартальний snapshot.",
        max_height=620,
    )
    _raw_table(
        "Analytics quarter summary",
        analytics_q,
        max_height=360,
    )
    _raw_table(
        "Dashboard quarter summary",
        dashboard_q,
        max_height=360,
    )


render_footer()
