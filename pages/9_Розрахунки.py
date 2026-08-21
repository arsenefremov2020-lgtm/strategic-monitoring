from __future__ import annotations

"""
Службова read-only сторінка «Розрахунки».

Версія LIGHT:
- сторінка не обчислює всі контури одночасно;
- важкі розділи виконуються лише після вибору користувачем;
- великі технічні таблиці не рендеряться автоматично;
- графічний довідник і методологічні пояснення відкриваються без завантаження БД;
- усі st.dataframe отримують лише display-копії зі строковими значеннями,
  щоб уникнути pyarrow.lib.ArrowInvalid на tuple/list/dict/object.
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


YEAR = 2026
QUARTERS = ["I", "II", "III", "IV"]
LATEST_QUARTER = "IV"
PAIRS = [(YEAR, q) for q in QUARTERS]
LATEST_KEY = (YEAR, LATEST_QUARTER)
TOL = 0.05


# =============================================================================
# PAGE
# =============================================================================

current_user = page_setup("Розрахунки", page_name=None)

if not is_super_admin_user(current_user):
    st.error("Сторінка «Розрахунки» доступна лише супер-адміністратору.")
    st.stop()

st.markdown(
    """
    <style>
    .main .block-container {
        max-width: 1380px;
        padding-top: 1.2rem;
        padding-bottom: 3rem;
    }
    .calc-hero {
        background: #FFFFFF;
        border: 1px solid #DCE4F0;
        border-radius: 16px;
        padding: 20px 24px;
        margin: 4px 0 16px 0;
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
    div[data-testid="stDataFrame"] {
        margin-bottom: 0.8rem;
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
            Службова сторінка прозорості методології. Важкі розрахунки та великі таблиці
            завантажуються <b>лише для обраного розділу</b>, а не всі одночасно.
            Фіксований контекст: 2026 рік; IV квартал як поточний зріз; динаміка I–IV;
            повний Стратегічний план; погоджені дані.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption("Збірка: 21.08.2026 · LIGHT · обчислення за вимогою")


# =============================================================================
# HELPERS
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
                year = int(float(value[0]))
                quarter = str(value[1]).strip()
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
        return "; ".join(
            f"{_display_cell_text(k)}: {_display_cell_text(v)}"
            for k, v in value.items()
        )

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
    names = []
    used: dict[str, int] = {}
    for idx, column in enumerate(safe.columns, start=1):
        base = _display_cell_text(column).strip() or f"Колонка {idx}"
        count = used.get(base, 0)
        used[base] = count + 1
        names.append(base if count == 0 else f"{base} ({count + 1})")
    safe.columns = names
    for column in safe.columns:
        safe[column] = safe[column].map(_display_cell_text).astype("string")
    return safe


def _display_df(
    frame: pd.DataFrame,
    *,
    max_height: int = 430,
    max_rows: int | None = None,
) -> None:
    """Безпечна таблиця. Великі масиви можна свідомо обрізати для UI."""
    if frame is None or frame.empty:
        st.caption("Немає рядків для відображення.")
        return

    data = frame
    if max_rows is not None and len(data) > max_rows:
        st.caption(
            f"Для швидкого перегляду показано перші {max_rows} із {len(data)} рядків. "
            "Розрахунок виконується по повному масиву."
        )
        data = data.head(max_rows).copy()

    display = _safe_display_frame(data)
    visible_rows = min(len(display), 10)
    height = min(max_height, max(120, 38 * (visible_rows + 1) + 12))

    try:
        st.dataframe(
            display,
            use_container_width=True,
            height=height,
            hide_index=True,
        )
    except Exception as exc:
        # Сторінка не повинна падати через renderer технічної таблиці.
        st.warning(f"Таблицю не вдалося відобразити інтерактивно: {type(exc).__name__}.")
        st.code(display.head(40).to_string(index=False), language="text")


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
        {"Причина": label, "Кількість": int(mask.fillna(False).sum())}
        for label, mask in reasons.items()
    ]
    union = attention_mask(snapshot).reindex(snapshot.index, fill_value=False)
    rows.append(
        {
            "Причина": "Унікальний UNION: потребує уваги хоча б з однієї причини",
            "Кількість": int(union.sum()),
        }
    )
    return pd.DataFrame(rows)


def _load_base_data():
    """Завантаження БД виконується лише у розділах, де воно реально потрібне."""
    strat_df = load_strat_matrix()
    all_monitoring = monitoring_data.load_monitoring_requests()
    measure_requests = monitoring_data.measures_only(all_monitoring)
    measure_requests = append_confirmed_closeout_facts(
        measure_requests,
        include_incomplete=True,
    )
    return strat_df, all_monitoring, measure_requests


def _build_dashboard_context(strat_df, measure_requests):
    period_sources = dashboard_sources.build_period_source_overrides(
        PAIRS,
        operational_mode=False,
    )
    results = build_period_results(
        strat_df,
        measure_requests,
        PAIRS,
        period_sources=period_sources,
    )
    aggregate = aggregate_plan(results)
    latest = results.get(LATEST_KEY, {})
    snapshot = latest.get("snapshot", pd.DataFrame())
    rsum = latest.get("risk_summary") or risk_summary(snapshot)
    return period_sources, results, aggregate, latest, snapshot, rsum


def _build_analytics_context(strat_df, measure_requests):
    results, active = analytics_calculations.prepare_analysis_context(
        strat_df,
        measure_requests,
        [YEAR],
        QUARTERS,
    )
    plan = analytics_calculations.build_analytics_plan_summary(results)
    metrics = analytics_calculations.build_metrics(active)
    metrics["completion"] = plan.get("execution_by_measures_average")
    metrics["coverage"] = plan.get("coverage_average")
    metrics["completion_latest"] = plan.get("execution_by_measures_latest")
    metrics["completion_change"] = plan.get("execution_by_measures_change")
    metrics["goal_completion"] = plan.get("execution_by_goals_average")
    metrics["goal_completion_latest"] = plan.get("execution_by_goals_latest")
    metrics["goal_completion_change"] = plan.get("execution_by_goals_change")
    metrics["coverage_latest"] = plan.get("coverage_latest")
    metrics["coverage_change"] = plan.get("coverage_change")
    metrics["latest_period"] = plan.get("latest_period")
    metrics["latest_risk_summary"] = plan.get("latest_risk_summary") or {}
    return results, active, plan, metrics


# =============================================================================
# LIGHT NAVIGATION
# =============================================================================

section = st.radio(
    "Що показати",
    [
        "Огляд",
        "Dashboard — розрахунки",
        "Аналітика — розрахунки",
        "Графіки Аналітики",
        "Показники аналітичної довідки",
        "Технічна звірка",
    ],
    horizontal=True,
    key="calc_light_section",
)

st.caption(
    "Перемикання розділу запускає тільки потрібний контур. "
    "Великі технічні таблиці додатково відкриваються окремим прапорцем."
)


# =============================================================================
# 1. OVERVIEW — ZERO HEAVY CALCULATIONS
# =============================================================================

if section == "Огляд":
    _section(
        "Як користуватися сторінкою",
        "Ця версія навмисно не намагається показати все одразу. "
        "Саме попереднє одночасне виконання Dashboard, Analytics, МіО, factual registry "
        "та десятків великих таблиць робило сторінку надмірно важкою.",
    )

    overview = pd.DataFrame(
        [
            {
                "Розділ": "Dashboard — розрахунки",
                "Що пояснює": "snapshot кварталу, execution_score, покриття, ієрархічну агрегацію, ризик, динаміку",
                "Важкість": "середня",
            },
            {
                "Розділ": "Аналітика — розрахунки",
                "Що пояснює": "average/latest/change, measure-period vs unique measure, проблемні та без даних, МіО за вимогою",
                "Важкість": "середня",
            },
            {
                "Розділ": "Графіки Аналітики",
                "Що пояснює": "точну назву кожного графіка, осі, одиницю спостереження та правильну інтерпретацію",
                "Важкість": "дуже легка — без БД",
            },
            {
                "Розділ": "Показники аналітичної довідки",
                "Що пояснює": "усі ключові показники, які згадує rule-based аналітика; технічний registry — лише за вимогою",
                "Важкість": "легка / важка лише для registry",
            },
            {
                "Розділ": "Технічна звірка",
                "Що пояснює": "Dashboard vs Analytics по кварталах та джерелах",
                "Важкість": "середня",
            },
        ]
    )
    _display_df(overview, max_height=320)

    _callout(
        "<b>Головний принцип.</b> Формули не змінені. Змінено лише спосіб роботи сторінки: "
        "розрахунок виконується тоді, коли він потрібен, а великі таблиці не створюють тисячі DOM-елементів під час старту."
    )


# =============================================================================
# 2. DASHBOARD
# =============================================================================

elif section == "Dashboard — розрахунки":
    with st.spinner("Формую Dashboard-контекст..."):
        try:
            strat_df, all_monitoring, measure_requests = _load_base_data()
            (
                dashboard_period_sources,
                dashboard_results,
                dashboard_aggregate,
                dashboard_latest,
                dashboard_snapshot,
                dashboard_risk,
            ) = _build_dashboard_context(strat_df, measure_requests)
        except Exception as exc:
            st.exception(exc)
            st.stop()

    _section(
        "1. Джерело даних за кварталами",
        "Dashboard використовує archive resolver: історичний квартал може брати архівний snapshot, "
        "а за відсутності архіву — live-дані.",
    )

    rows = []
    for q in QUARTERS:
        key = (YEAR, q)
        item = dashboard_results.get(key, {})
        snap = item.get("snapshot", pd.DataFrame())
        rows.append(
            {
                "Квартал": q,
                "Джерело": _source_label(dashboard_period_sources, key),
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
    _display_df(pd.DataFrame(rows), max_height=260)

    _section(
        "2. Як формується IV квартал",
        "Спочатку визначається стан заходу та джерело факту, і лише після цього формується execution_score.",
    )

    if dashboard_snapshot.empty:
        st.error("Q4 snapshot порожній.")
    else:
        period_state = dashboard_snapshot.get(
            "period_state", pd.Series("", index=dashboard_snapshot.index)
        ).astype(str)

        snapshot_structure = pd.DataFrame(
            [
                {"Категорія": "Усього рядків Q4 snapshot", "Кількість": len(dashboard_snapshot), "Пояснення": "один рядок = один захід у поточному Q4-зрізі"},
                {"Категорія": "Active", "Кількість": int(period_state.eq("active").sum()), "Пояснення": "строк заходу охоплює IV квартал"},
                {"Категорія": "Ended", "Кількість": int(period_state.eq("ended").sum()), "Пояснення": "захід завершився раніше"},
                {"Категорія": "Unknown period", "Кількість": int(period_state.eq("unknown_period").sum()), "Пояснення": "строк неможливо однозначно визначити"},
                {"Категорія": "Подано саме за Q4", "Кількість": int(_safe_bool_series(dashboard_snapshot, "submitted_current_period").sum()), "Пояснення": "є поточне погоджене Q4-подання"},
                {"Категорія": "Carry-forward", "Кількість": int(_safe_bool_series(dashboard_snapshot, "carry_forward").sum()), "Пояснення": "для execution використано попередній підтверджений факт цього року"},
                {"Категорія": "Немає обов'язкового поточного подання", "Кількість": int(_safe_bool_series(dashboard_snapshot, "missing_required_submission").sum()), "Пояснення": "Q4-подання мало бути, але його немає"},
            ]
        )
        _display_df(snapshot_structure, max_height=350)

        _callout(
            "<b>Carry-forward не дорівнює новому поданню.</b> Попередній підтверджений факт може підтримати execution, "
            "але покриття Q4 від цього не стає кращим."
        )

        _section("3. Як захід отримує execution_score")
        score_rules = pd.DataFrame(
            [
                {"Тип": "Числовий показник", "Правило": "факт / річний план × 100", "Бал": "0–100%; перевиконання не піднімає execution вище 100%"},
                {"Тип": "Так / Ні", "Правило": "так = досягнуто; ні = не досягнуто", "Бал": "100% / 0%"},
                {"Тип": "Якісний статус", "Правило": "Виконано / Частково виконано / Не виконано / Не подано", "Бал": "100% / 75% / 0% / 0%"},
                {"Тип": "Не настав час / Втратило актуальність", "Правило": "не повинно штучно псувати середнє", "Бал": "не входить у execution-середнє"},
                {"Тип": "Активний захід без підтвердженого результату", "Правило": "дані мали бути, але їх немає", "Бал": "0% для управлінської оцінки"},
            ]
        )
        _display_df(score_rules, max_height=300)

        assessed = dashboard_snapshot[
            _safe_numeric_series(dashboard_snapshot, "execution_score").notna()
        ].copy()
        score_sum = _safe_numeric_series(assessed, "execution_score").sum(min_count=1)
        assessed_count = len(assessed)
        diagnostic_execution = (
            None
            if assessed_count == 0 or pd.isna(score_sum)
            else float(score_sum) / assessed_count
        )

        _section("4. Головні KPI Q4")
        _show_formula(
            "Рівень виконання Стратегічного плану за заходами",
            meaning="Середній execution_score оцінених заходів IV кварталу.",
            population="Q4-заходи з непорожнім execution_score.",
            formula="сума execution_score / кількість оцінених заходів",
            substitution=f"{_n(score_sum)} / {assessed_count}" if assessed_count else "немає оцінених заходів",
            result=_pct(dashboard_latest.get("execution_by_measures")),
            interpretation=(
                f"Контрольний перерахунок = {_pct(diagnostic_execution)}; "
                f"shared Dashboard = {_pct(dashboard_latest.get('execution_by_measures'))} "
                f"({_parity_text(diagnostic_execution, dashboard_latest.get('execution_by_measures'))})."
            ),
            caveat="Це середнє за заходами, а не рівне зважування стратегічних цілей.",
        )

        coverage_pop = dashboard_snapshot[
            _safe_bool_series(dashboard_snapshot, "coverage_eligible")
        ].copy()
        coverage_den = len(coverage_pop)
        coverage_num = int(_safe_bool_series(coverage_pop, "submitted").sum())
        diagnostic_coverage = (
            None if coverage_den == 0 else coverage_num / coverage_den * 100.0
        )

        _show_formula(
            "Покриття моніторингом",
            meaning="Частка заходів, які повинні були податися саме в Q4 і мають поточне подання.",
            population="coverage_eligible заходи IV кварталу.",
            formula="поточні Q4-подання / coverage_eligible × 100",
            substitution=f"{coverage_num} / {coverage_den} × 100",
            result=_pct(dashboard_latest.get("coverage")),
            interpretation=f"Контрольний перерахунок = {_pct(diagnostic_coverage)}.",
            caveat="Високе execution не гарантує високе покриття: carry-forward може підтримати перше, але не друге.",
        )

        task_scores = dashboard_latest.get("task_scores", pd.DataFrame())
        goal_scores = dashboard_latest.get("goal_scores", pd.DataFrame())
        if isinstance(goal_scores, pd.DataFrame) and not goal_scores.empty:
            goal_by_tasks = _safe_numeric_series(goal_scores, "by_tasks").dropna()
            diagnostic_goal = None if goal_by_tasks.empty else float(goal_by_tasks.mean())
            _show_formula(
                "Виконання за стратегічними цілями",
                meaning="Рівне зважування оцінених стратегічних цілей через ланцюжок заходи → завдання → ціль.",
                population="Цілі з розрахованим by_tasks.",
                formula="сума by_tasks цілей / кількість оцінених цілей",
                substitution=f"{_n(goal_by_tasks.sum())} / {len(goal_by_tasks)}",
                result=_pct(dashboard_latest.get("execution_by_goals")),
                interpretation=f"Контрольний перерахунок = {_pct(diagnostic_goal)}.",
                caveat="Цей KPI закономірно може відрізнятися від простого середнього всіх заходів.",
            )

        _section("5. Ризик і потреба в увазі")
        q4_attention = attention_mask(dashboard_snapshot).reindex(
            dashboard_snapshot.index, fill_value=False
        )
        st.markdown(
            f"**Потребують уваги в Q4: {int(q4_attention.sum())} заходів.** "
            "Один захід у підсумковому UNION рахується один раз незалежно від кількості причин."
        )
        _display_df(_reason_table(dashboard_snapshot), max_height=300)

        _section("6. Динаміка I–IV та часова семантика")
        dashboard_q = _quarter_result_table(dashboard_results)
        _display_df(dashboard_q, max_height=260)

        aggregate_view = pd.DataFrame(
            [
                {
                    "Показник": "Виконання за заходами",
                    "Average I–IV": dashboard_aggregate.get("execution_by_measures_average"),
                    "Latest": dashboard_aggregate.get("execution_by_measures_latest"),
                    "Change": dashboard_aggregate.get("execution_by_measures_change"),
                },
                {
                    "Показник": "Виконання за цілями",
                    "Average I–IV": dashboard_aggregate.get("execution_by_goals_average"),
                    "Latest": dashboard_aggregate.get("execution_by_goals_latest"),
                    "Change": dashboard_aggregate.get("execution_by_goals_change"),
                },
                {
                    "Показник": "Покриття",
                    "Average I–IV": dashboard_aggregate.get("coverage_average"),
                    "Latest": dashboard_aggregate.get("coverage_latest"),
                    "Change": dashboard_aggregate.get("coverage_change"),
                },
            ]
        )
        _display_df(aggregate_view, max_height=240)
        _callout(
            "`average` = середнє доступних квартальних KPI; `latest` = останній квартал; "
            "`change` = останній мінус перший у відсоткових пунктах."
        )

        st.markdown("### Технічна деталізація — лише за вимогою")
        if st.checkbox("Показати таблицю балів заходів", key="calc_dash_scores"):
            columns = [
                "code", "parent_goal_code", "parent_task_code", "period_state", "status",
                "submitted_current_period", "carry_forward", "source_quarter", "actual",
                "annual_target", "raw_attainment_pct", "execution_score", "result_achieved",
                "coverage_eligible", "missing_required_submission", "data_quality_conflict",
            ]
            _display_df(
                dashboard_snapshot[[c for c in columns if c in dashboard_snapshot.columns]].copy(),
                max_height=520,
                max_rows=250,
            )

        if st.checkbox("Показати завдання та стратегічні цілі", key="calc_dash_hierarchy"):
            st.markdown("**Завдання**")
            _display_df(task_scores, max_height=450, max_rows=200)
            st.markdown("**Стратегічні цілі**")
            _display_df(goal_scores, max_height=450, max_rows=100)

        if st.checkbox("Показати ССП, заступників та фінансування", key="calc_dash_org"):
            with st.spinner("Формую організаційні та фінансові таблиці..."):
                st.markdown("**ССП**")
                _display_df(
                    ssp_summary(dashboard_results, base_results=dashboard_results),
                    max_height=480,
                    max_rows=150,
                )
                st.markdown("**Заступники Міністра**")
                _display_df(
                    deputy_summary(dashboard_results),
                    max_height=420,
                    max_rows=100,
                )
                try:
                    finance_frame = build_finance_frame(dashboard_snapshot, YEAR)
                    fin_kpi = finance_kpis(finance_frame)
                    _show_formula(
                        "Фінансове виконання",
                        meaning="Частка сукупного факту від сукупного річного плану фінансування.",
                        population="Валідні фінансові рядки у shared finance frame.",
                        formula="сума факту / сума плану × 100",
                        substitution=f"{_n(fin_kpi.get('fact_bln'))} / {_n(fin_kpi.get('plan_bln'))} × 100",
                        result=_pct(fin_kpi.get("financial_execution_pct")),
                        interpretation="Це ratio of sums для всього портфеля.",
                        caveat="Це не середнє індивідуальних фінансових відсотків заходів.",
                    )
                    _display_df(finance_frame, max_height=450, max_rows=200)
                except Exception as exc:
                    st.warning(f"Фінансовий блок не сформовано: {exc}")


# =============================================================================
# 3. ANALYTICS
# =============================================================================

elif section == "Аналітика — розрахунки":
    with st.spinner("Формую Analytics-контекст..."):
        try:
            strat_df, all_monitoring, measure_requests = _load_base_data()
            analytics_results, analytics_active, analytics_plan, analytics_metrics = (
                _build_analytics_context(strat_df, measure_requests)
            )
        except Exception as exc:
            st.exception(exc)
            st.stop()

    active_rows = len(analytics_active)
    active_unique = (
        analytics_active["code"].nunique()
        if not analytics_active.empty and "code" in analytics_active.columns
        else 0
    )

    _section(
        "1. Що є одиницею спостереження",
        "При виборі I–IV Analytics склеює квартальні snapshots. "
        "Тому один код заходу може з'явитися до чотирьох разів.",
    )

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Рядків захід × квартал", active_rows)
    a2.metric("Унікальних заходів", active_unique)
    a3.metric("Потребують уваги", _int(analytics_metrics.get("problem")))
    a4.metric("Без даних", _int(analytics_metrics.get("no_data")))

    _callout(
        "<b>Не змішуємо одиниці.</b> «Потребують уваги» та «Без даних» можуть бути measure-period counts, "
        "а «Заходів у вибірці» — unique measures. Це не автоматично «X із Y»."
    )

    _section("2. Чотири головні картки Analytics")
    kpi_guide = pd.DataFrame(
        [
            {
                "Назва": "Рівень виконання Стратегічного плану в обраному періоді",
                "Що показує": "execution_by_measures_average",
                "Одиниця": "%",
                "Розрахунок за I–IV": "середнє квартальних KPI",
                "Уточнення": "не тотожне latest Q4",
            },
            {
                "Назва": "Потребують управлінської уваги",
                "Що показує": "сума is_problem_status по active",
                "Одиниця": "захід × квартал",
                "Розрахунок за I–IV": "сума проблемних measure-period rows",
                "Уточнення": "один захід може повторюватися",
            },
            {
                "Назва": "Покриття моніторингом",
                "Що показує": "coverage_average",
                "Одиниця": "%",
                "Розрахунок за I–IV": "середнє квартальних coverage",
                "Уточнення": "не один річний ratio сум",
            },
            {
                "Назва": "Заходів у вибірці",
                "Що показує": "nunique(code)",
                "Одиниця": "унікальний захід",
                "Розрахунок за I–IV": "кількість різних кодів у active",
                "Уточнення": "не дорівнює кількості active rows",
            },
        ]
    )
    _display_df(kpi_guide, max_height=320)

    analytics_q = _quarter_result_table(analytics_results)
    exec_values = analytics_q["Виконання за заходами, %"].dropna().tolist()
    cov_values = analytics_q["Покриття, %"].dropna().tolist()

    _show_formula(
        "Analytics «Рівень виконання»",
        meaning="Середній рівень готових квартальних execution KPI за обраними кварталами.",
        population="Доступні квартальні execution_by_measures.",
        formula="(Q1 + Q2 + Q3 + Q4) / кількість доступних кварталів",
        substitution=(
            f"({' + '.join(_pct(v) for v in exec_values)}) / {len(exec_values)}"
            if exec_values else "немає значень"
        ),
        result=_pct(analytics_metrics.get("completion")),
        interpretation=(
            f"Контрольне середнє = {_pct(_mean(exec_values))}; "
            f"latest Q4 = {_pct(analytics_plan.get('execution_by_measures_latest'))}."
        ),
        caveat="Назва «в обраному періоді» при multi-quarter вибірці фактично означає average квартальних KPI.",
    )

    _show_formula(
        "Analytics «Покриття моніторингом»",
        meaning="Середнє готових квартальних coverage.",
        population="Доступні квартальні coverage.",
        formula="(coverage Q1 + Q2 + Q3 + Q4) / кількість доступних кварталів",
        substitution=(
            f"({' + '.join(_pct(v) for v in cov_values)}) / {len(cov_values)}"
            if cov_values else "немає значень"
        ),
        result=_pct(analytics_metrics.get("coverage")),
        interpretation=f"Контрольне середнє = {_pct(_mean(cov_values))}.",
        caveat="Average квартальних відсотків не обов'язково дорівнює одному ratio всіх річних подань.",
    )

    _section("3. Потребують уваги")
    if not analytics_active.empty:
        attention = _safe_bool_series(analytics_active, "is_problem_status")
        by_q = (
            analytics_active.assign(_attention=attention)
            .groupby("report_quarter", dropna=False)
            .agg(
                Рядків_з_увагою=("_attention", "sum"),
                Усього_рядків=("code", "size"),
                Унікальних_заходів=("code", "nunique"),
            )
            .reset_index()
            .rename(columns={"report_quarter": "Квартал"})
        )
        _display_df(by_q, max_height=260)
        unique_attention = (
            analytics_active.loc[attention, "code"].nunique()
            if "code" in analytics_active.columns else 0
        )
        _show_formula(
            "Поточне число «Потребують управлінської уваги»",
            meaning="Кількість проблемних спостережень у склеєному I–IV масиві.",
            population="active rows, де is_problem_status=True.",
            formula="attention rows Q1 + Q2 + Q3 + Q4",
            substitution=" + ".join(str(int(v)) for v in by_q["Рядків_з_увагою"].tolist()),
            result=str(int(attention.sum())),
            interpretation=f"Унікальних кодів, які хоча б раз потребували уваги: {unique_attention}.",
            caveat="Для частки problem numerator і denominator повинні мати однакову observation unit.",
        )

    _section("4. Цілі, завдання, ССП та типи продукту")
    st.markdown(
        "Виконання/Latest/Change походять із shared aggregation; "
        "лічильники проблемних і без даних можуть залишатися measure-period counts."
    )

    # Ці таблиці розраховуються лише в Analytics-розділі, але не рендеряться всі автоматично.
    if st.checkbox("Показати агреговані таблиці Analytics", key="calc_ana_tables"):
        with st.spinner("Формую агреговані таблиці..."):
            goals = analytics_calculations.build_analytics_goal_summary(
                analytics_results, analytics_active
            )
            tasks = analytics_calculations.build_analytics_task_summary(
                analytics_results, analytics_active
            )
            ssp = analytics_calculations.build_analytics_ssp_summary(
                analytics_results,
                analytics_active,
                base_results=analytics_results,
            )
            products = analytics_calculations.aggregate_product_progress(
                analytics_results, analytics_active
            )

        st.markdown("**Стратегічні цілі**")
        _display_df(goals, max_height=460, max_rows=120)
        st.markdown("**Завдання**")
        _display_df(tasks, max_height=460, max_rows=200)
        st.markdown("**ССП**")
        _display_df(ssp, max_height=460, max_rows=150)
        st.markdown("**Типи продукту**")
        _display_df(products, max_height=420, max_rows=100)

    if st.checkbox("Показати статуси I–IV та Q4", key="calc_ana_status"):
        q4_snapshot = analytics_results.get(LATEST_KEY, {}).get("snapshot", pd.DataFrame())
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**I–IV: measure-period rows**")
            _display_df(_status_counts(analytics_active), max_height=320)
        with c2:
            st.markdown("**Q4: поточний snapshot**")
            _display_df(_status_counts(q4_snapshot), max_height=320)

    _section("5. МіО — тільки за вимогою")
    st.markdown(
        "МіО є окремим річним контуром 20% / 30% / 50%. "
        "Щоб не гальмувати звичайний перегляд Analytics, він не обчислюється автоматично."
    )

    if st.checkbox("Розрахувати і показати МіО 2026", key="calc_ana_mio"):
        with st.spinner("Формую річний контур МіО..."):
            try:
                mio_monitoring = append_confirmed_closeout_facts(
                    all_monitoring,
                    include_incomplete=False,
                )
                outputs = mio_shared.build_mio_analytics(
                    strat_df,
                    mio_monitoring,
                    [YEAR],
                )
                mio_goals = outputs.get("goals", pd.DataFrame())
            except Exception as exc:
                st.warning(f"МіО не сформовано: {exc}")
                mio_goals = pd.DataFrame()

        if not mio_goals.empty:
            summary = mio_shared.summarize_integral_goals(mio_goals, YEAR)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Інтегральна оцінка", _pct(summary.average_integral))
            m2.metric("Виконання заходів", _pct(summary.average_measure_execution))
            m3.metric("Оцінка завдань", _pct(summary.average_task_score))
            m4.metric("Прогрес індикаторів", _pct(summary.average_strategic_progress))

            st.markdown("**Формула цілі:** `0.20 × I + 0.30 × J + 0.50 × K`.")
            if st.checkbox("Показати деталізацію МіО по цілях", key="calc_ana_mio_detail"):
                _display_df(mio_goals, max_height=500, max_rows=100)


# =============================================================================
# 4. GRAPH GUIDE — NO DB
# =============================================================================

elif section == "Графіки Аналітики":
    _section(
        "Графіки сторінки «Аналітика»",
        "Цей розділ не звертається до БД. Він пояснює точний зміст назв, осей та показників поточних графіків.",
    )

    chart_guide = pd.DataFrame(
        [
            {
                "Назва графіка": "Зміна ключових показників рік до року",
                "Осі / значення": "X: показник; Y: Зміна, в.п.; група: період порівняння",
                "Що вимірюється": "різниця між поточним і попереднім роком для виконання та покриття",
                "Одиниця": "відсоткові пункти",
                "Важливо": "це не темп приросту у %",
            },
            {
                "Назва графіка": "Динаміка оціненого виконання",
                "Осі / значення": "X: Період; Y: Виконання",
                "Що вимірюється": "готовий execution KPI кожного звітного кварталу",
                "Одиниця": "%",
                "Важливо": "кожна точка — окремий квартальний зріз, не накопичувальна сума",
            },
            {
                "Назва графіка": "Виконання за стратегічними цілями",
                "Осі / значення": "X: код СЦ; Y: Виконання; hover: назва, заходи, покриття, проблемні, без даних",
                "Що вимірюється": "агрегований execution стратегічної цілі за вибраними періодами",
                "Одиниця": "%",
                "Важливо": "при кількох кварталах поле Виконання є average; latest існує окремо",
            },
            {
                "Назва графіка": "Виконання за самостійними структурними підрозділами",
                "Осі / значення": "X: ССП; Y: Виконання; hover: заступник, портфель, покриття, проблемні, без даних",
                "Що вимірюється": "агрегований execution портфеля ССП",
                "Одиниця": "%",
                "Важливо": "ССП мають різний розмір портфеля",
            },
            {
                "Назва графіка": "Структура заходів за типами продукту",
                "Осі / значення": "X: тип продукту; Y: Унікальних_заходів",
                "Що вимірюється": "розмір портфеля типу продукту",
                "Одиниця": "унікальний захід",
                "Важливо": "висота стовпчика — не execution; execution лише в hover",
            },
            {
                "Назва графіка": "Структура статусів виконання",
                "Осі / значення": "сектори: status; значення: Кількість",
                "Що вимірюється": "кількість status-спостережень у active",
                "Одиниця": "захід × квартал",
                "Важливо": "I–IV — не структура унікальних заходів станом на Q4",
            },
            {
                "Назва графіка": "Завдання з найбільшою кількістю сигналів управлінської уваги",
                "Осі / значення": "X: код завдання; Y: Проблемних; top-10",
                "Що вимірюється": "кількість проблемних measure-period rows по завданнях",
                "Одиниця": "захід × квартал",
                "Важливо": "не обов'язково кількість унікальних проблемних заходів",
            },
            {
                "Назва графіка": "Рейтинг ССП за кількістю повернень",
                "Осі / значення": "X: ССП; Y: кількість повернень",
                "Що вимірюється": "події повернення заявок на доопрацювання",
                "Одиниця": "подія повернення",
                "Важливо": "тестовий workflow-блок; одна заявка може повертатися кілька разів",
            },
            {
                "Назва графіка": "Розподіл за ланками, які повертають",
                "Осі / значення": "X: ланка; Y: кількість повернень",
                "Що вимірюється": "на яких ланках workflow відбуваються повернення",
                "Одиниця": "подія повернення",
                "Важливо": "джерело — monitoring_logs",
            },
        ]
    )
    _display_df(chart_guide, max_height=540)

    explanations = {
        "Динаміка оціненого виконання": (
            "Кожна точка — окремий квартальний execution KPI. Лінія показує напрям зміни, "
            "але не означає, що Q4 є сумою Q1–Q4. Для кількісної зміни використовується "
            "`change = latest − first` у відсоткових пунктах."
        ),
        "Виконання за стратегічними цілями": (
            "Висота стовпчика походить із поля `Виконання` goal_progress. "
            "При multi-quarter вибірці це average. Hover поєднує execution, unique measures, "
            "coverage та measure-period counts, тому кожне поле має власну одиницю."
        ),
        "Виконання за ССП": (
            "Висота стовпчика — execution портфеля ССП. Порівняння результативності не дорівнює "
            "порівнянню масштабу: два ССП можуть мати однаковий execution, але різну кількість заходів."
        ),
        "Структура статусів": (
            "У вибірці I–IV один захід може потрапити в різні статуси в різних кварталах. "
            "Для поточного стану унікальних заходів треба дивитися Q4 snapshot."
        ),
        "Сигнали уваги за завданнями": (
            "Графік пріоритезує завдання за кількістю problem-спостережень. "
            "Він не доводить, що ці завдання мають найнижчий execution."
        ),
    }

    for title, body in explanations.items():
        with st.expander(title):
            st.write(body)


# =============================================================================
# 5. ANALYTICAL METRICS — STATIC FIRST, REGISTRY ON DEMAND
# =============================================================================

elif section == "Показники аналітичної довідки":
    _section(
        "Показники, які згадуються в автоматичній аналітиці",
        "Базовий словник є статичним і відкривається миттєво. "
        "Повний prepared factual registry будується лише за окремою командою нижче.",
    )

    human_metrics = pd.DataFrame(
        [
            {
                "Показник": "Рівень виконання СП",
                "Одиниця": "%",
                "Що означає": "середній execution оцінених заходів; у multi-quarter Analytics основна картка = average квартальних KPI",
                "Не плутати з": "latest Q4 та execution за стратегічними цілями",
            },
            {
                "Показник": "Виконання за стратегічними цілями",
                "Одиниця": "%",
                "Що означає": "ієрархічна оцінка через заходи → завдання → стратегічні цілі",
                "Не плутати з": "простим середнім усіх заходів",
            },
            {
                "Показник": "Покриття моніторингом",
                "Одиниця": "%",
                "Що означає": "частка обов'язкових поточних подань; у multi-quarter Analytics = average квартальних coverage",
                "Не плутати з": "рівнем виконання",
            },
            {
                "Показник": "Потребують управлінської уваги / Проблемних",
                "Одиниця": "захід × квартал у current Analytics",
                "Що означає": "кількість active rows, де канонічний problem flag істинний",
                "Не плутати з": "кількістю унікальних problem-заходів без deduplication",
            },
            {
                "Показник": "Без даних",
                "Одиниця": "захід × квартал",
                "Що означає": "кількість спостережень без потрібного інформаційного покриття за prepared metric",
                "Не плутати з": "підтвердженим фактичним нулем",
            },
            {
                "Показник": "Унікальних заходів",
                "Одиниця": "унікальний захід",
                "Що означає": "кількість різних code у вибірці",
                "Не плутати з": "кількістю measure-period rows",
            },
            {
                "Показник": "Average / Latest / Change",
                "Одиниця": "% / % / в.п.",
                "Що означає": "середнє кварталів / останній квартал / останній мінус перший",
                "Не плутати з": "трьома назвами одного числа",
            },
            {
                "Показник": "Частка високого та критичного ризику",
                "Одиниця": "%",
                "Що означає": "prepared factual metric з risk summary у сумісній популяції",
                "Не плутати з": "будь-якою іншою problem-часткою",
            },
            {
                "Показник": "Частка без поточного подання",
                "Одиниця": "%",
                "Що означає": "missing-подання / сумісна популяція",
                "Не плутати з": "100% − execution",
            },
            {
                "Показник": "Інтегральна оцінка МіО",
                "Одиниця": "%",
                "Що означає": "середнє готових інтегральних оцінок цілей; кожна ціль = 20% заходи + 30% завдання + 50% індикатори",
                "Не плутати з": "20% від виконання заходів",
            },
            {
                "Показник": "Фінансове виконання",
                "Одиниця": "%",
                "Що означає": "сума факту / сума плану × 100",
                "Не плутати з": "середнім індивідуальних фінансових % заходів",
            },
        ]
    )
    _display_df(human_metrics, max_height=520)

    _callout(
        "<b>Чому factual registry винесено окремо.</b> Його побудова запускає Analytics-контекст, "
        "річні порівняння, МіО та підготовку сотень derived facts. Це корисно для діагностики, "
        "але не повинно виконуватися при кожному відкритті сторінки."
    )

    if st.checkbox(
        "Побудувати повний prepared factual registry для 2026 року",
        key="calc_metric_registry",
    ):
        with st.spinner("Будую factual registry — це найважчий діагностичний блок..."):
            try:
                strat_df, all_monitoring, measure_requests = _load_base_data()
                analytics_results, analytics_active, analytics_plan, analytics_metrics = (
                    _build_analytics_context(strat_df, measure_requests)
                )

                goals = analytics_calculations.build_analytics_goal_summary(
                    analytics_results, analytics_active
                )
                tasks = analytics_calculations.build_analytics_task_summary(
                    analytics_results, analytics_active
                )
                ssp = analytics_calculations.build_analytics_ssp_summary(
                    analytics_results,
                    analytics_active,
                    base_results=analytics_results,
                )
                products = analytics_calculations.aggregate_product_progress(
                    analytics_results, analytics_active
                )
                statuses = _status_counts(analytics_active).rename(columns={"Статус": "status"})
                dynamics = analytics_calculations.build_analytics_dynamics(analytics_results)

                try:
                    yoy_results, _ = analytics_calculations.prepare_analysis_context(
                        strat_df,
                        measure_requests,
                        [YEAR - 1, YEAR],
                        QUARTERS,
                    )
                    yoy = analytics_calculations.build_year_over_year_comparison(yoy_results)
                except Exception:
                    yoy = pd.DataFrame()

                mio_monitoring = append_confirmed_closeout_facts(
                    all_monitoring,
                    include_incomplete=False,
                )
                try:
                    mio_outputs = mio_shared.build_mio_analytics(
                        strat_df, mio_monitoring, [YEAR]
                    )
                except Exception:
                    mio_outputs = {}

                filters = {
                    "years": [YEAR],
                    "quarters": QUARTERS.copy(),
                    "ssp": [],
                    "ssp_indices": [],
                    "deputies": [],
                    "goal_labels": [],
                    "task_labels": [],
                    "product_types": [],
                }

                context = build_analytics_text_context(
                    filters=filters,
                    metrics=analytics_metrics,
                    goal_progress=goals,
                    task_progress=tasks,
                    department_progress=ssp,
                    product_progress=products,
                    status_counts=statuses,
                    period_dynamics=dynamics,
                    yoy_comparison=yoy,
                    active=analytics_active,
                    mio_goal_evaluation=mio_outputs.get("goals", pd.DataFrame()),
                    mio_goal_task_evaluation=mio_outputs.get("goals_tasks", pd.DataFrame()),
                    mio_measure_evaluation=mio_outputs.get("measures", pd.DataFrame()),
                    mio_financing=mio_outputs.get("financing", pd.DataFrame()),
                )

                facts = getattr(context, "analytical_facts", None)
                metrics_map = getattr(facts, "metrics", {}) if facts is not None else {}

                rows = []
                for code, metric in sorted(metrics_map.items(), key=lambda item: str(item[0])):
                    rows.append(
                        {
                            "Код": str(code),
                            "Значення": metric.value,
                            "Unit": metric.unit,
                            "Source": metric.source,
                            "Aggregation": metric.aggregation,
                            "Numerator": metric.numerator,
                            "Denominator": metric.denominator,
                            "Observation unit": metric.observation_unit or "—",
                        }
                    )
                facts_df = pd.DataFrame(rows)
            except Exception as exc:
                st.exception(exc)
                facts_df = pd.DataFrame()

        if not facts_df.empty:
            st.metric("Prepared factual metrics", len(facts_df))
            _display_df(facts_df, max_height=600, max_rows=500)
            st.caption(
                "Registry показує prepared facts, які rule-based engine може використовувати без повторного перерахунку у тексті."
            )


# =============================================================================
# 6. TECHNICAL RECONCILIATION
# =============================================================================

elif section == "Технічна звірка":
    with st.spinner("Формую Dashboard та Analytics для звірки..."):
        try:
            strat_df, all_monitoring, measure_requests = _load_base_data()
            (
                dashboard_period_sources,
                dashboard_results,
                dashboard_aggregate,
                dashboard_latest,
                dashboard_snapshot,
                dashboard_risk,
            ) = _build_dashboard_context(strat_df, measure_requests)
            analytics_results, analytics_active, analytics_plan, analytics_metrics = (
                _build_analytics_context(strat_df, measure_requests)
            )
        except Exception as exc:
            st.exception(exc)
            st.stop()

    _section(
        "Dashboard ↔ Analytics по кварталах",
        "Якщо різниця є вже в одному й тому самому кварталі, причина не в average-vs-latest, "
        "а в джерелі або складі snapshot.",
    )

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
                "Execution parity": _parity_text(
                    d.get("execution_by_measures"), a.get("execution_by_measures")
                ),
                "Dashboard coverage": d.get("coverage"),
                "Analytics coverage": a.get("coverage"),
                "Coverage parity": _parity_text(
                    d.get("coverage"), a.get("coverage")
                ),
            }
        )
    _display_df(pd.DataFrame(source_compare), max_height=300)

    if st.checkbox("Показати квартальні summary-таблиці", key="calc_tech_quarters"):
        st.markdown("**Dashboard**")
        _display_df(_quarter_result_table(dashboard_results), max_height=280)
        st.markdown("**Analytics**")
        _display_df(_quarter_result_table(analytics_results), max_height=280)

    if st.checkbox("Показати фрагмент Q4 snapshot Dashboard", key="calc_tech_dash_snapshot"):
        _display_df(dashboard_snapshot, max_height=520, max_rows=250)

    if st.checkbox("Показати фрагмент Analytics active I–IV", key="calc_tech_active"):
        _display_df(analytics_active, max_height=520, max_rows=300)

    _callout(
        "Якщо Dashboard і Analytics не збігаються в одному кварталі, перевіряються archive/live source, "
        "склад стратегічної матриці, closeouts і period locks.",
        warning=True,
    )


render_footer()
