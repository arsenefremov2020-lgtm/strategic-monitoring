from __future__ import annotations

"""
Службова діагностична сторінка «Розрахунки».

Мета сторінки — НЕ створювати нову методологію, а покроково показати,
як саме поточні shared-модулі системи формують показники Dashboard та
сторінки «Аналітика» на тих самих даних.

Фіксований контекст:
- рік: 2026;
- поточний/останній зріз: IV квартал;
- динаміка: I → IV квартал;
- без додаткових організаційних/продуктових фільтрів;
- confirmed/погоджені дані;
- повний Стратегічний план.

Сторінка read-only. Вона нічого не записує в БД і не змінює формули.
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

# page_name=None навмисно: сторінка може бути відкрита як службова сторінка
# навіть до внесення «Розрахунки» у ROLE_PAGES/navigation.
current_user = page_setup("Розрахунки", page_name=None)

if not is_super_admin_user(current_user):
    st.error("Сторінка «Розрахунки» доступна лише супер-адміністратору.")
    st.stop()

st.title("Розрахунки")
st.caption(
    "Службова read-only сторінка. Фіксований контекст: 2026 рік; "
    "поточний зріз — IV квартал; порівняння — I → IV квартал; "
    "повний Стратегічний план; без додаткових фільтрів."
)

st.info(
    "Ця сторінка нічого не виправляє і не змінює методологію. "
    "Вона показує, які саме масиви та формули зараз використовують Dashboard "
    "і «Аналітика», щоб було видно, де показники збігаються, а де порівнюються "
    "різні часові зрізи або різні одиниці спостереження."
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
        return f"{int(round(number))}"
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")


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
    if _close(a, b):
        return "ЗБІГАЄТЬСЯ"
    return "ВІДРІЗНЯЄТЬСЯ"


def _show_formula(
    title: str,
    *,
    methodology: str,
    formula: str,
    substitution: str,
    result: str,
    plain: str,
) -> None:
    st.markdown(f"#### {title}")
    st.markdown(f"**Що рахується.** {methodology}")
    st.markdown(f"**Формула.** `{formula}`")
    st.markdown(f"**Підстановка поточних чисел.** {substitution}")
    st.markdown(f"**Результат.** **{result}**")
    st.markdown(f"**Простими словами.** {plain}")


def _display_df(frame: pd.DataFrame, *, height: int = 360) -> None:
    if frame is None or frame.empty:
        st.caption("Немає рядків для відображення.")
        return
    st.dataframe(frame, use_container_width=True, height=height, hide_index=True)


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
        "risk_level",
        pd.Series("", index=snapshot.index, dtype=object),
    ).astype(str)

    final_failure = (
        snapshot.get(
            "forecast_kind",
            pd.Series("", index=snapshot.index, dtype=object),
        )
        .astype(str)
        .eq("final")
        & ~_safe_bool_series(snapshot, "result_achieved")
    )

    reasons = {
        "Високий або критичний ризик": risk_level.isin(
            ["Високий ризик", "Критичний ризик"]
        ),
        "Попередній сигнал уваги": _safe_bool_series(
            snapshot, "preliminary_attention"
        ),
        "Немає обов'язкового подання за квартал": _safe_bool_series(
            snapshot, "missing_required_submission"
        ),
        "Захід завершився без фінального результату": _safe_bool_series(
            snapshot, "final_missing_result"
        ),
        "Конфлікт якості даних": _safe_bool_series(
            snapshot, "data_quality_conflict"
        ),
        "Фінальний результат не досягнуто": final_failure,
    }

    rows = []
    for label, mask in reasons.items():
        rows.append(
            {
                "Причина": label,
                "Кількість рядків Q4": int(mask.fillna(False).sum()),
            }
        )

    union = attention_mask(snapshot).reindex(snapshot.index, fill_value=False)
    rows.append(
        {
            "Причина": "УНІКАЛЬНИЙ UNION: потребує уваги хоча б з однієї причини",
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


# =============================================================================
# ЗАВАНТАЖЕННЯ ПОТОЧНИХ ДАНИХ
# =============================================================================

try:
    strat_df = load_strat_matrix()
    all_monitoring = monitoring_data.load_monitoring_requests()

    # Dashboard / monitoring layer використовує лише подання заходів.
    measure_requests = monitoring_data.measures_only(all_monitoring)

    # Ручні підтверджені закриття входять до офіційного monitoring-контуру.
    measure_requests = append_confirmed_closeout_facts(
        measure_requests,
        include_incomplete=True,
    )
    # MіO uses the full stream (measure + indicator rows). Incomplete legacy
    # closeouts are excluded from MіO exactly as intended by the shared helper.
    mio_monitoring = append_confirmed_closeout_facts(
        all_monitoring,
        include_incomplete=False,
    )
except Exception as exc:
    st.exception(exc)
    st.stop()

matrix_measures = (
    strat_df[strat_df.get("object_type", pd.Series(index=strat_df.index)).astype(str).eq("measure")].copy()
    if strat_df is not None and not strat_df.empty
    else pd.DataFrame()
)

st.markdown("### Вхідний масив")
input_summary = pd.DataFrame(
    [
        {
            "Що": "Заходи у стратегічній матриці",
            "Кількість": len(matrix_measures),
            "Одиниця": "унікальний захід",
        },
        {
            "Що": "Усі записи monitoring_requests",
            "Кількість": 0 if all_monitoring is None else len(all_monitoring),
            "Одиниця": "запис БД",
        },
        {
            "Що": "Записи заходів після відсікання indicator rows",
            "Кількість": len(measure_requests),
            "Одиниця": "подання заходу за період",
        },
    ]
)
_display_df(input_summary, height=180)


# =============================================================================
# 1. DASHBOARD — ТОЧНО ЙОГО ПОТОЧНИЙ КОНТУР
# =============================================================================

# Dashboard використовує archive resolver. Якщо для кварталу є валідний архів,
# build_period_results бере саме його; інакше — поточний strat_df/requests_df.
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

# =============================================================================
# 2. ANALYTICS — ТОЧНО ЇЇ ПОТОЧНИЙ FULL-SCOPE КОНТУР
# =============================================================================

# Поточна Analytics prepare_analysis_context НЕ передає period_sources.
# Тобто тут навмисно відтворюється її нинішня поведінка.
analytics_results, analytics_active = analytics_calculations.prepare_analysis_context(
    strat_df,
    measure_requests,
    [YEAR],
    QUARTERS,
)
analytics_plan = analytics_calculations.build_analytics_plan_summary(
    analytics_results
)
analytics_metrics = analytics_calculations.build_metrics(analytics_active)
analytics_metrics["completion"] = analytics_plan.get(
    "execution_by_measures_average"
)
analytics_metrics["coverage"] = analytics_plan.get("coverage_average")
analytics_metrics["completion_latest"] = analytics_plan.get(
    "execution_by_measures_latest"
)
analytics_metrics["coverage_latest"] = analytics_plan.get("coverage_latest")

analytics_q = _quarter_result_table(analytics_results)
analytics_latest = analytics_results.get(LATEST_KEY, {})
analytics_q4_snapshot = analytics_latest.get("snapshot", pd.DataFrame())


# =============================================================================
# КОРОТКА АВТОМАТИЧНА ЗВІРКА ПЕРЕД ДЕТАЛЯМИ
# =============================================================================

st.markdown("### Головна звірка")
reconciliation = pd.DataFrame(
    [
        {
            "Показник": "Виконання за заходами",
            "Dashboard Q4": dashboard_latest.get("execution_by_measures"),
            "Analytics: те, що зараз показує KPI": analytics_metrics.get("completion"),
            "Analytics: latest Q4": analytics_plan.get("execution_by_measures_latest"),
            "Що порівнюється": "Q4 snapshot vs середнє I–IV vs Q4",
        },
        {
            "Показник": "Покриття",
            "Dashboard Q4": dashboard_latest.get("coverage"),
            "Analytics: те, що зараз показує KPI": analytics_metrics.get("coverage"),
            "Analytics: latest Q4": analytics_plan.get("coverage_latest"),
            "Що порівнюється": "Q4 snapshot vs середнє I–IV vs Q4",
        },
        {
            "Показник": "Виконання за стратегічними цілями",
            "Dashboard Q4": dashboard_latest.get("execution_by_goals"),
            "Analytics: те, що зараз показує KPI": analytics_plan.get("execution_by_goals_average"),
            "Analytics: latest Q4": analytics_plan.get("execution_by_goals_latest"),
            "Що порівнюється": "Q4 snapshot vs середнє I–IV vs Q4",
        },
    ]
)
_display_df(reconciliation, height=210)

dashboard_exec_q4 = dashboard_latest.get("execution_by_measures")
analytics_exec_avg = analytics_plan.get("execution_by_measures_average")
analytics_exec_q4 = analytics_plan.get("execution_by_measures_latest")

dashboard_cov_q4 = dashboard_latest.get("coverage")
analytics_cov_avg = analytics_plan.get("coverage_average")
analytics_cov_q4 = analytics_plan.get("coverage_latest")

if _close(dashboard_exec_q4, analytics_exec_q4):
    st.success(
        "Виконання: Dashboard Q4 і Analytics latest-Q4 збігаються. "
        "Якщо основний KPI Analytics відрізняється, причина — він зараз показує "
        "середнє I–IV, а не Q4."
    )
else:
    st.warning(
        "Виконання: навіть Dashboard Q4 та Analytics latest-Q4 НЕ збігаються. "
        "Отже, крім різної часової семантики, є різниця у джерелі/масиві даних "
        "(найчастіше archive snapshot Dashboard проти live-контуру Analytics)."
    )

if _close(dashboard_cov_q4, analytics_cov_q4):
    st.success(
        "Покриття: Dashboard Q4 і Analytics latest-Q4 збігаються; "
        "відмінність основного KPI Analytics пояснюється середнім I–IV."
    )
else:
    st.warning(
        "Покриття: Dashboard Q4 та Analytics latest-Q4 НЕ збігаються; "
        "потрібно дивитися таблицю джерел по кварталах нижче."
    )


# =============================================================================
# EXPANDER 1 — DASHBOARD
# =============================================================================

with st.expander("Дашборд — повний покроковий розрахунок", expanded=True):
    st.markdown(
        """
        ### 1. Що саме тут відтворюється

        Для **поточних карток Dashboard** беремо **IV квартал 2026 року**.
        Для динаміки беремо **I, II, III, IV квартали 2026 року**.

        Важливий нюанс: Dashboard має окремий resolver історичних джерел.
        Якщо для кварталу існує валідний archive snapshot, Dashboard рахує
        цей квартал з архівного стану матриці та подань. Якщо архіву немає —
        бере поточні live-дані.
        """
    )

    source_rows = []
    for q in QUARTERS:
        key = (YEAR, q)
        item = dashboard_results.get(key, {})
        snap = item.get("snapshot", pd.DataFrame())
        source_rows.append(
            {
                "Квартал": q,
                "Джерело Dashboard": _source_label(
                    dashboard_period_sources, key
                ),
                "Рядків snapshot": len(snap) if isinstance(snap, pd.DataFrame) else 0,
                "Унікальних заходів": (
                    snap["code"].nunique()
                    if isinstance(snap, pd.DataFrame)
                    and not snap.empty
                    and "code" in snap.columns
                    else 0
                ),
                "Виконання, %": item.get("execution_by_measures"),
                "Покриття, %": item.get("coverage"),
            }
        )
    st.markdown("#### Джерело даних за кожним кварталом")
    _display_df(pd.DataFrame(source_rows), height=230)

    st.markdown("### 2. Як формується один Q4 snapshot")
    if dashboard_snapshot.empty:
        st.error("Q4 snapshot порожній — подальші Q4-формули неможливо показати.")
    else:
        snapshot_structure = pd.DataFrame(
            [
                {
                    "Категорія": "Усього рядків Q4 snapshot",
                    "Кількість": len(dashboard_snapshot),
                    "Одиниця": "1 рядок = 1 захід у Q4 snapshot",
                },
                {
                    "Категорія": "Унікальних кодів заходів",
                    "Кількість": dashboard_snapshot["code"].nunique(),
                    "Одиниця": "унікальний захід",
                },
                {
                    "Категорія": "Active",
                    "Кількість": int(
                        dashboard_snapshot.get(
                            "period_state",
                            pd.Series("", index=dashboard_snapshot.index),
                        )
                        .astype(str)
                        .eq("active")
                        .sum()
                    ),
                    "Одиниця": "захід",
                },
                {
                    "Категорія": "Ended",
                    "Кількість": int(
                        dashboard_snapshot.get(
                            "period_state",
                            pd.Series("", index=dashboard_snapshot.index),
                        )
                        .astype(str)
                        .eq("ended")
                        .sum()
                    ),
                    "Одиниця": "захід",
                },
                {
                    "Категорія": "Unknown period",
                    "Кількість": int(
                        dashboard_snapshot.get(
                            "period_state",
                            pd.Series("", index=dashboard_snapshot.index),
                        )
                        .astype(str)
                        .eq("unknown_period")
                        .sum()
                    ),
                    "Одиниця": "захід",
                },
                {
                    "Категорія": "Подано саме за Q4",
                    "Кількість": int(
                        _safe_bool_series(
                            dashboard_snapshot,
                            "submitted_current_period",
                        ).sum()
                    ),
                    "Одиниця": "захід",
                },
                {
                    "Категорія": "Використано попередній підтверджений результат того самого року",
                    "Кількість": int(
                        _safe_bool_series(
                            dashboard_snapshot, "carry_forward"
                        ).sum()
                    ),
                    "Одиниця": "захід",
                },
                {
                    "Категорія": "Немає обов'язкового поточного подання",
                    "Кількість": int(
                        _safe_bool_series(
                            dashboard_snapshot,
                            "missing_required_submission",
                        ).sum()
                    ),
                    "Одиниця": "захід",
                },
            ]
        )
        _display_df(snapshot_structure, height=330)

        st.markdown(
            """
            **Простими словами про snapshot.**
            Для кожного заходу система спочатку визначає, чи він уже активний,
            завершений, ще майбутній або має невизначений період.
            Майбутні заходи у snapshot не входять. Для активного заходу система
            шукає погоджене подання саме за Q4. Якщо його немає, але в цьому ж
            2026 році є раніше підтверджений результат, він може бути використаний
            для управлінської оцінки виконання, але **покриття Q4 все одно
            штрафується**, бо нового Q4-подання немає.
            """
        )

        st.markdown("### 3. Бал кожного заходу")
        st.markdown(
            """
            Система має кілька способів отримати `execution_score`:

            - **Числовий показник:** факт / річний план × 100. Для поточного
              execution результат обмежується зверху 100%.
            - **Так/ні:** «так» = 100%, «ні» = 0%.
            - **Якісний статус без числової пари:** «Виконано» = 100%,
              «Частково виконано» = 75%, «Не виконано» = 0%,
              «Не подано» = 0%.
            - **«Не настав час» / «Втратило актуальність»:** не входять у
              execution-середнє.
            - Якщо активний захід мав бути поданий, але немає жодного
              підтвердженого результату цього року, управлінська оцінка = 0%.
            """
        )

        score_table_columns = [
            "code",
            "parent_goal_code",
            "parent_task_code",
            "period_state",
            "status",
            "submitted_current_period",
            "carry_forward",
            "source_quarter",
            "actual",
            "annual_target",
            "raw_attainment_pct",
            "execution_score",
            "result_achieved",
            "coverage_eligible",
            "missing_required_submission",
            "data_quality_conflict",
        ]
        score_table = dashboard_snapshot[
            [c for c in score_table_columns if c in dashboard_snapshot.columns]
        ].copy()
        _display_df(score_table, height=500)

        st.markdown("### 4. Рівень виконання за заходами — головний Q4 KPI")
        assessed = dashboard_snapshot[
            _safe_numeric_series(
                dashboard_snapshot, "execution_score"
            ).notna()
        ].copy()
        score_sum = _safe_numeric_series(
            assessed, "execution_score"
        ).sum(min_count=1)
        assessed_count = len(assessed)
        diagnostic_execution = (
            None
            if assessed_count == 0 or pd.isna(score_sum)
            else float(score_sum) / assessed_count
        )

        _show_formula(
            "Виконання за заходами",
            methodology=(
                "Беруться лише заходи Q4, для яких сформовано числовий "
                "execution_score. Потім рахується звичайне середнє."
            ),
            formula="сума execution_score усіх оцінених заходів / кількість оцінених заходів",
            substitution=(
                f"{_n(score_sum)} / {assessed_count}"
                if assessed_count
                else "немає оцінених заходів"
            ),
            result=_pct(dashboard_latest.get("execution_by_measures")),
            plain=(
                f"У Q4 оцінено {assessed_count} заходів. Сума їхніх балів "
                f"дорівнює {_n(score_sum)}. Ділимо суму на кількість заходів. "
                f"Контрольний перерахунок дає {_pct(diagnostic_execution)}; "
                f"shared Dashboard дає {_pct(dashboard_latest.get('execution_by_measures'))} "
                f"— {_parity_text(diagnostic_execution, dashboard_latest.get('execution_by_measures'))}."
            ),
        )

        st.markdown("### 5. Покриття моніторингом Q4")
        coverage_mask = _safe_bool_series(
            dashboard_snapshot, "coverage_eligible"
        )
        coverage_pop = dashboard_snapshot[coverage_mask].copy()
        coverage_den = len(coverage_pop)
        coverage_num = int(
            _safe_bool_series(coverage_pop, "submitted").sum()
        )
        diagnostic_coverage = (
            None
            if coverage_den == 0
            else coverage_num / coverage_den * 100.0
        )

        _show_formula(
            "Покриття моніторингом",
            methodology=(
                "Знаменник — заходи, для яких у Q4 моніторинг був обов'язковим "
                "(coverage_eligible). Чисельник — скільки з них реально мають "
                "поточне Q4-подання."
            ),
            formula="поточні Q4-подання / coverage-eligible заходи × 100",
            substitution=f"{coverage_num} / {coverage_den} × 100",
            result=_pct(dashboard_latest.get("coverage")),
            plain=(
                f"Із {coverage_den} заходів, які мали бути охоплені моніторингом "
                f"у Q4, подання є за {coverage_num}. Контрольний розрахунок "
                f"дає {_pct(diagnostic_coverage)}; shared Dashboard дає "
                f"{_pct(dashboard_latest.get('coverage'))} — "
                f"{_parity_text(diagnostic_coverage, dashboard_latest.get('coverage'))}."
            ),
        )

        st.markdown("### 6. Рівень виконання завдань")
        task_scores = dashboard_latest.get("task_scores", pd.DataFrame())
        if isinstance(task_scores, pd.DataFrame) and not task_scores.empty:
            st.markdown(
                """
                Для кожного завдання беруться `execution_score` його оцінених
                заходів і рахується **середнє арифметичне**. Тобто завдання з
                2 заходами і завдання з 20 заходами далі є двома окремими
                значеннями на наступному рівні ієрархії.
                """
            )
            _display_df(task_scores, height=420)
        else:
            st.caption("Немає task_scores за Q4.")

        st.markdown("### 7. Рівень стратегічних цілей")
        goal_scores = dashboard_latest.get("goal_scores", pd.DataFrame())
        if isinstance(goal_scores, pd.DataFrame) and not goal_scores.empty:
            st.markdown(
                """
                Для кожної стратегічної цілі система показує два різні числа:

                - `by_measures` — середній бал **усіх заходів** цієї цілі;
                - `by_tasks` — середнє значення **виконання завдань** цієї цілі.

                Головний KPI Dashboard **«Виконання за стратегічними цілями»**
                = середнє `by_tasks` по стратегічних цілях.
                """
            )
            _display_df(goal_scores, height=420)

            goal_by_tasks = _safe_numeric_series(
                goal_scores, "by_tasks"
            ).dropna()
            diagnostic_goal_execution = (
                None if goal_by_tasks.empty else float(goal_by_tasks.mean())
            )
            _show_formula(
                "Виконання за стратегічними цілями",
                methodology=(
                    "Спочатку кожне завдання отримує середній бал своїх заходів; "
                    "потім кожна ціль — середній бал своїх завдань; "
                    "потім береться середнє по цілях."
                ),
                formula="сума by_tasks стратегічних цілей / кількість цілей із оцінкою",
                substitution=(
                    f"{_n(goal_by_tasks.sum())} / {len(goal_by_tasks)}"
                    if not goal_by_tasks.empty
                    else "немає оцінених цілей"
                ),
                result=_pct(dashboard_latest.get("execution_by_goals")),
                plain=(
                    f"Контрольний розрахунок дає {_pct(diagnostic_goal_execution)}; "
                    f"shared Dashboard — {_pct(dashboard_latest.get('execution_by_goals'))} "
                    f"— {_parity_text(diagnostic_goal_execution, dashboard_latest.get('execution_by_goals'))}."
                ),
            )

        st.markdown("### 8. «Результат уже досягнуто»")
        risk_denom_mask = _safe_numeric_series(
            dashboard_snapshot, "execution_score"
        ).notna()
        risk_denom = int(risk_denom_mask.sum())
        achieved_num = int(
            (
                _safe_bool_series(dashboard_snapshot, "result_achieved")
                & risk_denom_mask
            ).sum()
        )
        achieved_pct = (
            None if risk_denom == 0 else achieved_num / risk_denom * 100
        )
        _show_formula(
            "Частка результатів, які вже досягнуто",
            methodology=(
                "Знаменник — заходи з розрахованим execution_score. "
                "Чисельник — ті з них, де `result_achieved=True`."
            ),
            formula="досягнуті результати / оцінені заходи × 100",
            substitution=f"{achieved_num} / {risk_denom} × 100",
            result=_pct(dashboard_risk.get("share_results_achieved")),
            plain=(
                f"Контрольний розрахунок = {_pct(achieved_pct)}. "
                f"Shared risk_summary = {_pct(dashboard_risk.get('share_results_achieved'))}."
            ),
        )

        st.markdown("### 9. «Потребує уваги» у Q4")
        st.markdown(
            """
            У **Q4 snapshot** один рядок відповідає одному заходу. `attention_mask`
            об'єднує кілька можливих причин через логічне **АБО**.
            Тому один захід із трьома причинами все одно рахується один раз
            у підсумковому UNION.
            """
        )
        q4_attention = attention_mask(dashboard_snapshot).reindex(
            dashboard_snapshot.index, fill_value=False
        )
        q4_attention_count = int(q4_attention.sum())
        q4_unique = (
            dashboard_snapshot["code"].nunique()
            if "code" in dashboard_snapshot.columns
            else len(dashboard_snapshot)
        )
        st.markdown(
            f"**Q4: {q4_attention_count} заходів потребують уваги із "
            f"{q4_unique} унікальних заходів у snapshot.**"
        )
        _display_df(_reason_table(dashboard_snapshot), height=310)
        st.caption(
            "Кількості окремих причин можуть перекриватися. Їх НЕ МОЖНА "
            "просто додавати між собою."
        )

        st.markdown("### 10. Чому у Q4 картки ризику можуть бути «н/д»")
        st.markdown(
            """
            У поточній методології Q4 — **фінальний результат**, а не прогнозний
            квартал. Тому прогнозні категорії «низький / середній / високий /
            критичний ризик» для фінального Q4 не використовуються так само,
            як у Q2–Q3. `risk_summary` при цьому може показувати частку вже
            досягнутих результатів та фінальний управлінський висновок.
            """
        )
        risk_summary_view = pd.DataFrame(
            [
                {"Поле risk_summary": key, "Значення": value}
                for key, value in dashboard_risk.items()
                if not isinstance(value, (dict, list, pd.DataFrame, pd.Series))
            ]
        )
        _display_df(risk_summary_view, height=320)

    st.markdown("### 11. Динаміка I → IV квартал")
    _display_df(dashboard_q, height=260)

    dash_exec_delta = _q1_q4_delta(
        dashboard_q, "Виконання за заходами, %"
    )
    dash_goal_delta = _q1_q4_delta(
        dashboard_q, "Виконання за стратегічними цілями, %"
    )
    dash_cov_delta = _q1_q4_delta(dashboard_q, "Покриття, %")

    q1_exec_series = dashboard_q.loc[
        dashboard_q["Квартал"].eq("I"), "Виконання за заходами, %"
    ]
    q4_exec_series = dashboard_q.loc[
        dashboard_q["Квартал"].eq("IV"), "Виконання за заходами, %"
    ]
    q1_exec = q1_exec_series.iloc[0] if not q1_exec_series.empty else None
    q4_exec = q4_exec_series.iloc[0] if not q4_exec_series.empty else None

    _show_formula(
        "Зміна виконання Q1 → Q4",
        methodology=(
            "Для динаміки не усереднюємо Q1 та Q4. "
            "Беремо два готові квартальні KPI і віднімаємо."
        ),
        formula="виконання Q4 − виконання Q1",
        substitution=f"{_pct(q4_exec)} − {_pct(q1_exec)}",
        result=_pp(dash_exec_delta),
        plain="Це чиста зміна між першим і четвертим кварталом у відсоткових пунктах.",
    )

    dynamics = dynamics_frame(dashboard_results)
    st.markdown("#### Shared dynamics_frame")
    _display_df(dynamics, height=320)

    st.markdown("### 12. Що означає `aggregate_plan`")
    st.markdown(
        """
        `aggregate_plan` НЕ є Q4 snapshot. Він бере готові квартальні KPI
        за I–IV і для кожного показника формує три поля:

        - **average** — середнє арифметичне доступних кварталів;
        - **latest** — останній доступний квартал;
        - **change** — останній мінус перший доступний квартал.

        Саме змішування `average` і `latest` у різних UI-картках може створити
        враження, що «формули різні», хоча базові квартальні KPI ті самі.
        """
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
                "Показник": "Виконання за цілями",
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
    _display_df(aggregate_view, height=210)

    st.markdown("### 13. Стратегічні цілі: average / latest / change")
    goals_agg = aggregate_objects(dashboard_results, object_type="goal")
    _display_df(goals_agg, height=420)

    st.markdown("### 14. Завдання: average / latest / change")
    tasks_agg = aggregate_objects(dashboard_results, object_type="task")
    _display_df(tasks_agg, height=420)

    st.markdown("### 15. ССП")
    dash_ssp = ssp_summary(
        dashboard_results,
        base_results=dashboard_results,
    )
    st.markdown(
        """
        Для ССП `average` — середнє квартальних execution цього ССП,
        `latest` — Q4, `change` — Q4 мінус перший доступний квартал.
        `portfolio_weight`/вага портфеля, якщо присутня, має базуватися на
        унікальному портфелі відповідного shared-модуля, а не на сумі
        measure-period рядків.
        """
    )
    _display_df(dash_ssp, height=450)

    st.markdown("### 16. Заступники Міністра")
    dash_deputies = deputy_summary(dashboard_results)
    _display_df(dash_deputies, height=420)

    st.markdown("### 17. Фінансування")
    try:
        finance_frame = build_finance_frame(dashboard_snapshot, YEAR)
        fin_kpi = finance_kpis(finance_frame)
        plan_bln = fin_kpi.get("plan_bln")
        fact_bln = fin_kpi.get("fact_bln")
        fin_pct = fin_kpi.get("financial_execution_pct")

        _show_formula(
            "Фінансове виконання",
            methodology=(
                "Береться один рядок на унікальний захід Q4. "
                "Річний план підсумовується по портфелю, фактичні витрати "
                "так само підсумовуються."
            ),
            formula="сума факту / сума плану × 100",
            substitution=f"{_n(fact_bln)} / {_n(plan_bln)} × 100",
            result=_pct(fin_pct),
            plain=(
                "Це співвідношення загальної фактичної суми до загальної "
                "планової суми, а не середнє індивідуальних відсотків заходів."
            ),
        )
        _display_df(finance_frame, height=420)
    except Exception as exc:
        st.warning(f"Фінансовий блок не вдалося відтворити: {exc}")


# =============================================================================
# EXPANDER 2 — ANALYTICS
# =============================================================================

with st.expander("Аналітика — повний покроковий розрахунок", expanded=True):
    st.markdown(
        """
        ### 1. Головна відмінність поточного контуру Analytics

        Поточна сторінка `Аналітика` при виборі **I, II, III, IV кварталів**
        створює чотири квартальні snapshots, а потім **склеює їх вертикально**.

        Тобто в `active`:

        **1 рядок ≠ 1 унікальний захід за рік.**

        Тут 1 рядок = **один захід в одному квартальному snapshot**.
        Один і той самий код заходу може з'являтися до чотирьох разів.
        """
    )

    active_rows = len(analytics_active)
    active_unique = (
        analytics_active["code"].nunique()
        if not analytics_active.empty and "code" in analytics_active.columns
        else 0
    )

    structure = pd.DataFrame(
        [
            {
                "Показник": "Рядків у Analytics active",
                "Значення": active_rows,
                "Одиниця": "захід × квартал",
            },
            {
                "Показник": "Унікальних заходів у Analytics active",
                "Значення": active_unique,
                "Одиниця": "унікальний захід",
            },
            {
                "Показник": "Поточний metrics['problem']",
                "Значення": analytics_metrics.get("problem"),
                "Одиниця": "уважні measure-period рядки",
            },
            {
                "Показник": "Поточний metrics['no_data']",
                "Значення": analytics_metrics.get("no_data"),
                "Одиниця": "missing measure-period рядки",
            },
        ]
    )
    _display_df(structure, height=230)

    st.markdown("### 2. По кварталах: що реально входить у Analytics")
    analytics_source_rows = []
    for q in QUARTERS:
        key = (YEAR, q)
        item = analytics_results.get(key, {})
        snap = item.get("snapshot", pd.DataFrame())
        analytics_source_rows.append(
            {
                "Квартал": q,
                "Джерело поточного Analytics": "Поточний live-контур",
                "Чи мав Dashboard архів": "так" if key in dashboard_period_sources else "ні",
                "Рядків snapshot": len(snap) if isinstance(snap, pd.DataFrame) else 0,
                "Унікальних заходів": (
                    snap["code"].nunique()
                    if isinstance(snap, pd.DataFrame)
                    and not snap.empty
                    and "code" in snap.columns
                    else 0
                ),
                "Виконання, %": item.get("execution_by_measures"),
                "Покриття, %": item.get("coverage"),
            }
        )
    _display_df(pd.DataFrame(analytics_source_rows), height=250)

    st.markdown("### 3. Чому Analytics зараз показує інше «Виконання»")
    analytics_exec_values = analytics_q[
        "Виконання за заходами, %"
    ].dropna().tolist()
    analytics_exec_mean_check = _mean(analytics_exec_values)

    expression = " + ".join(_pct(v) for v in analytics_exec_values)
    denominator = len(analytics_exec_values)
    substitution = (
        f"({expression}) / {denominator}"
        if denominator
        else "немає квартальних значень"
    )

    _show_formula(
        "Поточний KPI Analytics «Рівень виконання»",
        methodology=(
            "Сторінка бере `execution_by_measures_average` з aggregate_plan. "
            "Це середнє квартальних KPI I–IV, а НЕ окреме значення Q4."
        ),
        formula="(Q1 + Q2 + Q3 + Q4) / кількість доступних кварталів",
        substitution=substitution,
        result=_pct(analytics_metrics.get("completion")),
        plain=(
            f"Контрольне середнє = {_pct(analytics_exec_mean_check)}. "
            f"Analytics KPI = {_pct(analytics_metrics.get('completion'))}. "
            f"Окремий latest-Q4 = {_pct(analytics_plan.get('execution_by_measures_latest'))}. "
            f"Dashboard Q4 = {_pct(dashboard_latest.get('execution_by_measures'))}."
        ),
    )

    st.markdown("### 4. Чому Analytics зараз показує інше «Покриття»")
    analytics_cov_values = analytics_q["Покриття, %"].dropna().tolist()
    analytics_cov_mean_check = _mean(analytics_cov_values)

    cov_expression = " + ".join(_pct(v) for v in analytics_cov_values)
    cov_denominator = len(analytics_cov_values)
    cov_substitution = (
        f"({cov_expression}) / {cov_denominator}"
        if cov_denominator
        else "немає квартальних значень"
    )

    _show_formula(
        "Поточний KPI Analytics «Покриття»",
        methodology=(
            "Так само використовується `coverage_average`: "
            "середнє готових квартальних coverage I–IV."
        ),
        formula="(coverage Q1 + Q2 + Q3 + Q4) / кількість доступних кварталів",
        substitution=cov_substitution,
        result=_pct(analytics_metrics.get("coverage")),
        plain=(
            f"Контрольне середнє = {_pct(analytics_cov_mean_check)}. "
            f"Analytics KPI = {_pct(analytics_metrics.get('coverage'))}. "
            f"Окремий latest-Q4 = {_pct(analytics_plan.get('coverage_latest'))}. "
            f"Dashboard Q4 = {_pct(dashboard_latest.get('coverage'))}."
        ),
    )

    st.markdown("### 5. Зміна I → IV в Analytics")
    ana_exec_delta = analytics_plan.get("execution_by_measures_change")
    ana_goal_delta = analytics_plan.get("execution_by_goals_change")
    ana_cov_delta = analytics_plan.get("coverage_change")

    changes = pd.DataFrame(
        [
            {
                "Показник": "Виконання за заходами",
                "Q1": (
                    analytics_q.loc[
                        analytics_q["Квартал"].eq("I"),
                        "Виконання за заходами, %",
                    ].iloc[0]
                    if not analytics_q.loc[
                        analytics_q["Квартал"].eq("I")
                    ].empty
                    else None
                ),
                "Q4": analytics_plan.get("execution_by_measures_latest"),
                "Q4 − Q1": ana_exec_delta,
            },
            {
                "Показник": "Виконання за цілями",
                "Q1": (
                    analytics_q.loc[
                        analytics_q["Квартал"].eq("I"),
                        "Виконання за стратегічними цілями, %",
                    ].iloc[0]
                    if not analytics_q.loc[
                        analytics_q["Квартал"].eq("I")
                    ].empty
                    else None
                ),
                "Q4": analytics_plan.get("execution_by_goals_latest"),
                "Q4 − Q1": ana_goal_delta,
            },
            {
                "Показник": "Покриття",
                "Q1": (
                    analytics_q.loc[
                        analytics_q["Квартал"].eq("I"),
                        "Покриття, %",
                    ].iloc[0]
                    if not analytics_q.loc[
                        analytics_q["Квартал"].eq("I")
                    ].empty
                    else None
                ),
                "Q4": analytics_plan.get("coverage_latest"),
                "Q4 − Q1": ana_cov_delta,
            },
        ]
    )
    _display_df(changes, height=210)
    st.caption(
        "Тут `change` уже має правильну часову семантику: останній квартал "
        "мінус перший доступний квартал. Проблема не в change, а в тому, "
        "що основні KPI Analytics зараз показують average."
    )

    st.markdown("### 6. Звідки береться «Потребують управлінської уваги»")
    if analytics_active.empty:
        st.caption("Analytics active порожній.")
    else:
        active_attention = _safe_bool_series(
            analytics_active, "is_problem_status"
        )
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
        _display_df(attention_by_quarter, height=230)

        unique_attention_codes = (
            analytics_active.loc[active_attention, "code"].nunique()
            if "code" in analytics_active.columns
            else 0
        )

        q4_active = analytics_active[
            analytics_active.get(
                "report_quarter",
                pd.Series("", index=analytics_active.index),
            )
            .astype(str)
            .eq("IV")
        ].copy()
        q4_attention_in_analytics = int(
            _safe_bool_series(q4_active, "is_problem_status").sum()
        )

        _show_formula(
            "Поточне число «Потребують уваги» в Analytics",
            methodology=(
                "`build_metrics(active)` просто сумує boolean "
                "`is_problem_status` по СКЛЕЄНИХ рядках I–IV."
            ),
            formula="сума attention-рядків Q1 + Q2 + Q3 + Q4",
            substitution=" + ".join(
                str(int(v))
                for v in attention_by_quarter[
                    "Рядків_з_увагою"
                ].tolist()
            ),
            result=str(attention_rows),
            plain=(
                f"Це **{attention_rows} не унікальних заходів**, а "
                f"attention-спостережень «захід × квартал». "
                f"Унікальних кодів заходів, які хоча б раз потребували уваги "
                f"протягом I–IV, — {unique_attention_codes}. "
                f"У самому Q4 attention-рядків — {q4_attention_in_analytics}. "
                f"Унікальних заходів у всій річній вибірці — {active_unique}. "
                "Тому порівнювати row-level 228 із unique-measure 192 "
                "методологічно некоректно."
            ),
        )

        if attention_rows > active_unique:
            st.error(
                "ВИЯВЛЕНО НЕСУМІСНІ ОДИНИЦІ В UI: картка «Заходів у вибірці» "
                "показує унікальні заходи, а «Потребують уваги» — "
                "measure-period рядки. Саме тому друге число може бути більшим "
                "за перше."
            )

    st.markdown("### 7. Статуси в Analytics")
    st.markdown(
        """
        Якщо статуси групуються по `analytics_active`, вони також є
        **статусами measure-period рядків I–IV**. Це не те саме, що
        «скільки унікальних заходів має такий статус станом на Q4».
        """
    )
    status_compare_left, status_compare_right = st.columns(2)
    with status_compare_left:
        st.markdown("**Analytics I–IV: статуси measure-period rows**")
        _display_df(_status_counts(analytics_active), height=300)
    with status_compare_right:
        st.markdown("**Q4 snapshot: статуси унікальних заходів**")
        _display_df(_status_counts(analytics_q4_snapshot), height=300)

    st.markdown("### 8. Strategic goals у поточному Analytics")
    analytics_goals = analytics_calculations.build_analytics_goal_summary(
        analytics_results,
        analytics_active,
    )
    st.markdown(
        """
        Основні execution-поля беруться зі shared `aggregate_objects`:
        average = середнє по кварталах, latest = Q4,
        change = Q4 мінус перший квартал.

        Але колонки `Проблемних`, `Без_даних`, `Заходів_періодів` після merge
        беруться з `analytics_active`, тобто це **measure-period counts**.
        Колонка `Унікальних_заходів` — окрема, і вона має іншу одиницю.
        """
    )
    _display_df(analytics_goals, height=470)

    st.markdown("### 9. Tasks у поточному Analytics")
    analytics_tasks = analytics_calculations.build_analytics_task_summary(
        analytics_results,
        analytics_active,
    )
    _display_df(analytics_tasks, height=470)

    st.markdown("### 10. ССП у поточному Analytics")
    analytics_ssp = analytics_calculations.build_analytics_ssp_summary(
        analytics_results,
        analytics_active,
        base_results=analytics_results,
    )
    _display_df(analytics_ssp, height=470)

    st.markdown("### 11. Типи продукту")
    analytics_products = analytics_calculations.aggregate_product_progress(
        analytics_results,
        analytics_active,
    )
    st.markdown(
        """
        `Виконання` і `Покриття_%` тут отримуються через shared
        `aggregate_plan` для підмножини конкретного типу продукту, тобто
        це **середні квартальні значення I–IV**. `Проблемних` і `Без_даних`
        — row-level counts із measure-period масиву.
        """
    )
    _display_df(analytics_products, height=420)

    st.markdown("### 12. МіО — окремий річний контур")
    st.markdown(
        """
        МіО НЕ є Q4 snapshot Dashboard. Це річна модель оцінювання 2026 року.
        Вона використовує повний monitoring stream, включно з поданнями
        індикаторів цілей і завдань.

        Для кожної стратегічної цілі поточний інтеграл складається з:

        - **20%** — виконання заходів цілі;
        - **30%** — середня оцінка завдань цілі;
        - **50%** — прогрес власних стратегічних індикаторів цілі.

        Поточна формула не змінюється на цій сторінці.
        """
    )

    try:
        mio_outputs = mio_shared.build_mio_analytics(
            strat_df,
            mio_monitoring,
            [YEAR],
        )
        mio_goals = mio_outputs.get("goals", pd.DataFrame())
        mio_summary = mio_shared.summarize_integral_goals(
            mio_goals,
            YEAR,
        )

        mio_rows = []
        if not mio_goals.empty:
            for _, row in mio_goals.iterrows():
                i = _num(row.get(f"Заходи {YEAR}"))
                j = _num(row.get(f"Завдання {YEAR}"))
                k = _num(row.get(f"Прогрес {YEAR}"))
                integral_shared = _num(row.get(f"Інтеграл {YEAR}"))
                # Контрольний перерахунок лише для пояснення методики.
                diagnostic_integral = (
                    0.20 * (i or 0)
                    + 0.30 * (j or 0)
                    + 0.50 * (k or 0)
                )
                mio_rows.append(
                    {
                        "Код цілі": row.get("Код"),
                        "Ціль": row.get("Ціль"),
                        "Заходи I, %": i,
                        "Завдання J, %": j,
                        "Прогрес K, %": k,
                        "Формула": (
                            f"0.20×{_n(i or 0)} + "
                            f"0.30×{_n(j or 0)} + "
                            f"0.50×{_n(k or 0)}"
                        ),
                        "Контрольний інтеграл, %": diagnostic_integral,
                        "Shared інтеграл, %": integral_shared,
                        "Parity": _parity_text(
                            diagnostic_integral,
                            integral_shared,
                        ),
                    }
                )
        _display_df(pd.DataFrame(mio_rows), height=480)

        st.markdown(
            f"""
            **Підсумок МіО за 2026 рік із shared layer:**

            - стратегічних цілей у зведенні: **{mio_summary.goal_count}**;
            - середня інтегральна оцінка: **{_pct(mio_summary.average_integral)}**;
            - середнє виконання заходів у МіО: **{_pct(mio_summary.average_measure_execution)}**;
            - середня оцінка завдань: **{_pct(mio_summary.average_task_score)}**;
            - середній прогрес індикаторів цілей: **{_pct(mio_summary.average_strategic_progress)}**.
            """
        )
        st.caption(
            "Середній інтеграл = середнє готових інтегральних оцінок "
            "стратегічних цілей. Це не 20% від виконання заходів."
        )

        mio_financing = mio_outputs.get("financing", pd.DataFrame())
        if not mio_financing.empty:
            st.markdown("#### Вхідні фінансові дані МіО")
            _display_df(mio_financing, height=420)
    except Exception as exc:
        st.warning(f"МіО-блок не вдалося відтворити: {exc}")

    st.markdown("### 13. Dashboard Q4 vs Analytics current — підсумок різниць")

    attention_rows_total = _int(
        analytics_metrics.get("problem")
    )
    analytics_unique_attention = (
        analytics_active.loc[
            _safe_bool_series(
                analytics_active,
                "is_problem_status",
            ),
            "code",
        ].nunique()
        if not analytics_active.empty
        and "code" in analytics_active.columns
        else 0
    )
    dash_q4_attention = (
        int(attention_mask(dashboard_snapshot).sum())
        if not dashboard_snapshot.empty
        else 0
    )

    final_diff = pd.DataFrame(
        [
            {
                "Тема": "Виконання",
                "Dashboard": _pct(dashboard_exec_q4),
                "Analytics зараз": _pct(analytics_exec_avg),
                "Що не однаково": "Dashboard = Q4; Analytics KPI = average I–IV",
                "Контроль": (
                    "latest Q4 збігається"
                    if _close(dashboard_exec_q4, analytics_exec_q4)
                    else "latest Q4 теж різний → перевірити source"
                ),
            },
            {
                "Тема": "Покриття",
                "Dashboard": _pct(dashboard_cov_q4),
                "Analytics зараз": _pct(analytics_cov_avg),
                "Що не однаково": "Dashboard = Q4; Analytics KPI = average I–IV",
                "Контроль": (
                    "latest Q4 збігається"
                    if _close(dashboard_cov_q4, analytics_cov_q4)
                    else "latest Q4 теж різний → перевірити source"
                ),
            },
            {
                "Тема": "Потребують уваги",
                "Dashboard": str(dash_q4_attention),
                "Analytics зараз": str(attention_rows_total),
                "Що не однаково": (
                    "Dashboard = Q4 unique snapshot; Analytics = сума "
                    "measure-period attention rows I–IV"
                ),
                "Контроль": (
                    f"unique attention measures I–IV = "
                    f"{analytics_unique_attention}"
                ),
            },
            {
                "Тема": "Заходів у вибірці",
                "Dashboard": str(
                    dashboard_snapshot["code"].nunique()
                    if not dashboard_snapshot.empty
                    and "code" in dashboard_snapshot.columns
                    else 0
                ),
                "Analytics зараз": str(active_unique),
                "Що не однаково": (
                    "Обидва є unique measures, але охоплення може різнитися "
                    "через Q4 applicability vs union I–IV"
                ),
                "Контроль": (
                    f"Analytics має {active_rows} measure-period rows "
                    f"для {active_unique} unique measures"
                ),
            },
        ]
    )
    _display_df(final_diff, height=300)

    st.markdown(
        """
        ### 14. Простий висновок

        **Що зараз точно правильно розділяти:**

        1. `Q4 snapshot` — стан системи в одному конкретному кварталі.
        2. `average I–IV` — середнє чотирьох квартальних KPI.
        3. `measure-period rows I–IV` — всі квартальні спостереження,
           де один захід може повторюватися.
        4. `unique measures` — унікальні коди заходів.
        5. `МіО 2026` — окремий річний інтегральний контур 20/30/50.

        Якщо UI називає два числа так, ніби вони є одним і тим самим
        показником, але одне взяте з Q4, а друге з average I–IV — користувач
        бачить «розходження формул», хоча насправді розходиться часовий зміст.

        Якщо UI ставить поруч `192 унікальні заходи` та `228 attention rows`,
        він змішує **різні одиниці спостереження**. Це вже не просто питання
        назви — ці величини не можна інтерпретувати як «228 із 192».
        """
    )


# =============================================================================
# ТЕХНІЧНА ЗВІРКА ДЖЕРЕЛ ПО КВАРТАЛАХ
# =============================================================================

st.markdown("### Технічна звірка Dashboard ↔ Analytics по кожному кварталу")
source_compare = []
for q in QUARTERS:
    d = dashboard_results.get((YEAR, q), {})
    a = analytics_results.get((YEAR, q), {})
    source_compare.append(
        {
            "Квартал": q,
            "Dashboard source": _source_label(
                dashboard_period_sources,
                (YEAR, q),
            ),
            "Dashboard execution": d.get("execution_by_measures"),
            "Analytics execution": a.get("execution_by_measures"),
            "Execution parity": _parity_text(
                d.get("execution_by_measures"),
                a.get("execution_by_measures"),
            ),
            "Dashboard coverage": d.get("coverage"),
            "Analytics coverage": a.get("coverage"),
            "Coverage parity": _parity_text(
                d.get("coverage"),
                a.get("coverage"),
            ),
        }
    )
_display_df(pd.DataFrame(source_compare), height=270)

st.caption(
    "Якщо при одному й тому самому кварталі Dashboard і Analytics тут не "
    "збігаються, це вже не average-vs-latest. Тоді треба перевіряти source: "
    "archive snapshot Dashboard проти live source Analytics, склад стратегічної "
    "матриці, closeouts або period locks."
)

render_footer()
