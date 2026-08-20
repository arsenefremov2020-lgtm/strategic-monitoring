from __future__ import annotations

from typing import Any

import pandas as pd

from .language import fmt_delta, fmt_pct, intensity_from_delta, is_number, join_uk
from .models import AnalyticsContext, GeneratedNote, GenerationDebug, GenerationState, PhraseVariant, Signal
from .morphology import count_uk
from .planner import build_text_plan
from .scenarios import activate_scenarios
from .selector import choose_variant
from .signals import detect_signals
from .templates import phrase_pool
from .validation import clean_text, validate_text


def _signals_by_code(signals: list[Signal]) -> dict[str, Signal]:
    return {item.code: item for item in signals}


def _first(signals: list[Signal], *prefixes: str) -> Signal | None:
    for item in signals:
        if any(item.code.startswith(prefix) for prefix in prefixes):
            return item
    return None


def _choose(category: str, tag: str, ctx: AnalyticsContext, scenario: str, block: str, state: GenerationState, debug: GenerationDebug) -> PhraseVariant:
    variant = choose_variant(
        phrase_pool(category, tag),
        key=f"{ctx.signature}:{scenario}:{block}:{tag}",
        state=state,
    )
    debug.selected_phrase_ids.append(variant.id)
    return variant


def _scope(ctx: AnalyticsContext) -> str:
    years = ", ".join(map(str, ctx.filters.get("years", []))) or "усі доступні роки"
    quarters = ", ".join(map(str, ctx.filters.get("quarters", []))) or "усі квартали"
    parts = [f"роки: {years}", f"квартали: {quarters}"]
    for key, label in (("ssp", "ССП"), ("deputies", "заступники Міністра"), ("goal_labels", "стратегічні цілі"), ("task_labels", "завдання"), ("product_types", "типи продукту")):
        values = ctx.filters.get(key, []) or []
        if values:
            parts.append(f"{label}: {join_uk([str(x) for x in values], 3)}")
    return "Параметри вибірки — " + "; ".join(parts)


def _sample_text(ctx: AnalyticsContext) -> str:
    return count_uk(ctx.sample_size, "measure")


def _rows_text(ctx: AnalyticsContext) -> str:
    return count_uk(ctx.row_count, "record") + " «захід-період»"


def _render_opening(ctx: AnalyticsContext, plan, state, debug) -> str:
    variant = _choose("opening", plan.opening, ctx, plan.scenario_key, "opening", state, debug)
    return variant.template.format(scope=_scope(ctx))


def _render_overall(ctx: AnalyticsContext, signals: list[Signal], plan, state, debug) -> str:
    codes = {s.code for s in signals}
    if codes & {"coverage_limited", "coverage_very_limited", "lower_execution_limited_coverage"}:
        tag = "cautious"
    elif codes & {"execution_low", "execution_very_low", "execution_down_broad_coverage"}:
        tag = "negative"
    elif codes & {"execution_high", "execution_very_high", "execution_up_coverage_up"}:
        tag = "positive"
    else:
        tag = "neutral"
    v = _choose("general", tag, ctx, plan.scenario_key, "overall_state", state, debug)
    return v.template.format(
        sample=_sample_text(ctx), rows=_rows_text(ctx),
        execution=fmt_pct(ctx.metric("completion")), coverage=fmt_pct(ctx.metric("coverage")),
    )


def _render_execution(ctx: AnalyticsContext, signals: list[Signal], plan, state, debug) -> str:
    tag = "medium"
    for name in ("very_high", "high", "medium", "low", "very_low"):
        if any(s.code == f"execution_{name}" for s in signals):
            tag = name; break
    v = _choose("execution", tag, ctx, plan.scenario_key, "execution", state, debug)
    return v.template.format(execution=fmt_pct(ctx.metric("completion")))


def _render_coverage(ctx: AnalyticsContext, signals: list[Signal], plan, state, debug) -> str:
    tag = "incomplete"
    for name in ("near_full", "broad", "partial", "limited", "very_limited"):
        if any(s.code == f"coverage_{name}" for s in signals):
            tag = name; break
    v = _choose("coverage", tag, ctx, plan.scenario_key, "coverage", state, debug)
    text = v.template.format(coverage=fmt_pct(ctx.metric("coverage")))
    missing = int(ctx.metric("no_data") or 0)
    if missing > 0 and "data_quality" not in plan.blocks:
        state.used_fact_ids.add("missing_count")
        text += f" Відсутнє обов'язкове поточне подання за {count_uk(missing, 'record')}."
    return text


def _render_data_quality(ctx: AnalyticsContext, signals: list[Signal]) -> str:
    missing = int(ctx.metric("no_data") or 0)
    if missing <= 0:
        return "Відсутніх обов’язкових поточних подань у цій вибірці не зафіксовано."
    if any(s.code == "missing_share_large" for s in signals):
        return f"Без обов’язкового поточного подання залишаються {count_uk(missing, 'record')}; це безпосередньо обмежує повноту даних вибірки."
    if any(s.code == "missing_share_material" for s in signals):
        return f"Зафіксовано {count_uk(missing, 'record')} без обов’язкового поточного подання; цей факт слід враховувати при читанні агрегованих показників."
    return f"Без обов’язкового поточного подання залишаються {count_uk(missing, 'record')}."


def _render_dynamics(ctx: AnalyticsContext, signals: list[Signal], plan, state, debug) -> str:
    dyn = _first(signals, "execution_increased_", "execution_decreased_", "execution_stable")
    if dyn is None:
        v = _choose("dynamics", "insufficient", ctx, plan.scenario_key, "dynamics", state, debug)
        return v.template
    delta = float(dyn.values.get("delta") or 0.0)
    tag = "growth" if dyn.code.startswith("execution_increased_") else "decline" if dyn.code.startswith("execution_decreased_") else "stable"
    v = _choose("dynamics", tag, ctx, plan.scenario_key, "dynamics", state, debug)
    text = v.template.format(
        intensity=intensity_from_delta(delta), delta=fmt_delta(delta), delta_abs=fmt_delta(abs(delta), signed=False),
        previous=fmt_pct(dyn.values.get("previous")), current=fmt_pct(dyn.values.get("current")),
    )
    if any(s.code in {"execution_reversal_positive", "execution_reversal_negative"} for s in signals):
        rv = _choose("dynamics", "reversal", ctx, plan.scenario_key, "dynamics_reversal", state, debug)
        text += " " + rv.template
    return text


def _render_yoy(ctx: AnalyticsContext, signals: list[Signal], plan, state, debug) -> str:
    sig = _first(signals, "yoy_execution_") or _first(signals, "yoy_coverage_")
    if sig is None:
        return "Порівняння рік до року не містить достатнього набору зіставних значень для окремого висновку."
    delta = float(sig.values.get("delta") or 0.0)
    tag = "positive" if "_increased_" in sig.code else "negative" if "_decreased_" in sig.code else "neutral"
    if sig.code.startswith("yoy_coverage_decreased_"):
        tag = "cautious"
    v = _choose("yoy", tag, ctx, plan.scenario_key, "year_over_year", state, debug)
    return v.template.format(
        delta=fmt_delta(delta), delta_abs=fmt_delta(abs(delta), signed=False),
        previous=fmt_pct(sig.values.get("previous")), current=fmt_pct(sig.values.get("current")),
    )


def _frame_extremes(frame: pd.DataFrame, label_col: str) -> dict[str, Any] | None:
    if frame is None or frame.empty or "Виконання" not in frame.columns:
        return None
    work = frame.copy(); work["_e"] = pd.to_numeric(work["Виконання"], errors="coerce"); work = work.dropna(subset=["_e"])
    if work.empty:
        return None
    best = work.sort_values("_e", ascending=False).iloc[0]
    worst = work.sort_values("_e", ascending=True).iloc[0]
    return {
        "best": str(best.get(label_col, "")), "best_value": float(best["_e"]),
        "worst": str(worst.get(label_col, "")), "worst_value": float(worst["_e"]),
        "gap": float(best["_e"] - worst["_e"]),
    }


def _top_count(frame: pd.DataFrame, label_col: str, count_col: str) -> tuple[str, int] | None:
    if frame is None or frame.empty or count_col not in frame.columns:
        return None
    counts = pd.to_numeric(frame[count_col], errors="coerce").fillna(0)
    if counts.max() <= 0:
        return None
    idx = counts.idxmax()
    return str(frame.loc[idx].get(label_col, "")), int(counts.loc[idx])


def _render_goals(ctx: AnalyticsContext, signals: list[Signal], plan, state, debug) -> str:
    if ctx.goal_progress.empty:
        return "Дані для окремого аналізу стратегічних цілей у поточному зрізі відсутні."
    if len(ctx.goal_progress) == 1:
        v = _choose("goals", "single", ctx, plan.scenario_key, "goals", state, debug)
        return v.template
    ex = _frame_extremes(ctx.goal_progress, "goal_code")
    tag = "uniform" if any(sig.code == "goal_gap_narrow" for sig in signals) else "gap"
    v = _choose("goals", tag, ctx, plan.scenario_key, "goals", state, debug)
    text = v.template.format(
        best=ex["best"], worst=ex["worst"], best_value=fmt_pct(ex["best_value"]),
        worst_value=fmt_pct(ex["worst_value"]), gap=fmt_delta(ex["gap"], signed=False),
    ) if ex else v.template
    problem = _top_count(ctx.goal_progress, "goal_code", "Проблемних")
    missing = _top_count(ctx.goal_progress, "goal_code", "Без_даних")
    if problem and any(s.code in {"goal_most_problematic", "goal_problem_concentration_half_or_more"} for s in signals):
        pv = _choose("goals", "problem", ctx, plan.scenario_key, "goals_problem", state, debug)
        text += " " + pv.template.format(problem_label=problem[0], problem_count=problem[1])
    elif missing and any(s.code in {"goal_most_missing", "missing_share_large", "missing_share_material"} for s in signals):
        mv = _choose("goals", "missing", ctx, plan.scenario_key, "goals_missing", state, debug)
        text += " " + mv.template.format(missing_label=missing[0], missing_count=missing[1])
    return text


def _render_tasks(ctx: AnalyticsContext, signals: list[Signal], plan, state, debug) -> str:
    if ctx.task_progress.empty:
        return "Окремий аналіз завдань для цієї вибірки не формується."
    if len(ctx.task_progress) == 1:
        return _choose("tasks", "single", ctx, plan.scenario_key, "tasks", state, debug).template
    problem_frame = ctx.task_progress.copy()
    if "Проблемних" in problem_frame.columns:
        problem_frame["_p"] = pd.to_numeric(problem_frame["Проблемних"], errors="coerce").fillna(0)
        ranked = problem_frame.sort_values(["_p", "task_code"], ascending=[False, True]).head(3)
        items = [f"{r.get('task_code')} ({int(r.get('_p', 0))} сигналів)" for _, r in ranked.iterrows() if int(r.get('_p', 0)) > 0]
    else:
        items = []
    if items:
        v = _choose("tasks", "problem", ctx, plan.scenario_key, "tasks", state, debug)
        return v.template.format(items=join_uk(items))
    ex = _frame_extremes(ctx.task_progress, "task_code")
    tag = "uniform" if any(sig.code == "task_gap_narrow" for sig in signals) else "gap"
    v = _choose("tasks", tag, ctx, plan.scenario_key, "tasks", state, debug)
    return v.template.format(gap=fmt_delta(ex["gap"], signed=False) if ex else "н/д")


def _render_departments(ctx: AnalyticsContext, signals: list[Signal], plan, state, debug) -> str:
    if ctx.department_progress.empty:
        return "Дані для окремого аналізу ССП у поточному зрізі відсутні."
    if len(ctx.department_progress) == 1:
        return _choose("departments", "single", ctx, plan.scenario_key, "departments", state, debug).template
    ex = _frame_extremes(ctx.department_progress, "department")
    tag = "uniform" if any(sig.code == "department_gap_narrow" for sig in signals) else "gap"
    v = _choose("departments", tag, ctx, plan.scenario_key, "departments", state, debug)
    text = v.template.format(
        best=ex["best"], worst=ex["worst"], best_value=fmt_pct(ex["best_value"]),
        worst_value=fmt_pct(ex["worst_value"]), gap=fmt_delta(ex["gap"], signed=False),
    ) if ex else v.template
    problem = _top_count(ctx.department_progress, "department", "Проблемних")
    if problem and any(s.code in {"department_most_problematic", "department_problem_concentration_half_or_more"} for s in signals):
        pv = _choose("departments", "problem", ctx, plan.scenario_key, "department_problem", state, debug)
        text += " " + pv.template.format(problem_label=problem[0], problem_count=problem[1])
    return text


def _render_products(ctx: AnalyticsContext, signals: list[Signal], plan, state, debug) -> str:
    frame = ctx.product_progress
    if frame.empty:
        return "Структура за типами продукту для поточного зрізу не формується."
    counts = pd.to_numeric(frame.get("Унікальних_заходів"), errors="coerce").fillna(0)
    if counts.sum() <= 0:
        return "Типи продукту присутні у вибірці, однак їх кількісна структура не визначена."
    idx = counts.idxmax(); dominant = str(frame.loc[idx].get("product_type", "н/д")); dominant_count = int(counts.loc[idx]); share = dominant_count / float(counts.sum())
    tag = "concentration" if any(sig.code == "product_concentration_half_or_more" for sig in signals) else "neutral"
    v = _choose("products", tag, ctx, plan.scenario_key, "products", state, debug)
    return v.template.format(dominant=dominant, dominant_count=count_uk(dominant_count, "measure"), dominant_share=fmt_pct(share * 100))


def _render_statuses(ctx: AnalyticsContext, signals: list[Signal], plan, state, debug) -> str:
    frame = ctx.status_counts
    if frame.empty or not {"status", "Кількість"}.issubset(frame.columns):
        return "Статусна структура для поточного зрізу не визначена."
    work = frame.copy(); work["_c"] = pd.to_numeric(work["Кількість"], errors="coerce").fillna(0)
    idx = work["_c"].idxmax(); total = max(float(work["_c"].sum()), 1.0)
    dominant = str(work.loc[idx, "status"]); count = int(work.loc[idx, "_c"]); share = count / total
    codes = {s.code for s in signals}
    tag = "negative" if codes & {"status_not_done_material_share", "status_not_submitted_material_share", "status_partial_material_share"} else "positive" if "status_done_material_share" in codes else "neutral"
    v = _choose("statuses", tag, ctx, plan.scenario_key, "statuses", state, debug)
    return v.template.format(dominant=dominant, dominant_count=count, dominant_share=fmt_pct(share * 100))


def _render_risks(ctx: AnalyticsContext, signals: list[Signal], plan, state, debug) -> str:
    codes = {s.code for s in signals}
    for tag, code in (
        ("exec_up_cov_down", "execution_up_coverage_down"),
        ("exec_up_problems_up", "execution_up_problems_up"),
        ("low_exec_low_cov", "lower_execution_limited_coverage"),
        ("low_exec_high_cov", "lower_execution_broad_coverage"),
        ("overall_up_component_down", "overall_up_but_component_down"),
    ):
        if code in codes:
            return _choose("contrast", tag, ctx, plan.scenario_key, "risks", state, debug).template.format(
                execution=fmt_pct(ctx.metric("completion")), coverage=fmt_pct(ctx.metric("coverage"))
            )
    problem = int(ctx.metric("problem") or 0)
    if problem:
        return f"У вибірці зафіксовано {count_uk(problem, 'signal')} проблемного типу; вони описують структуру відхилень, але не пояснюють їх причин."
    return "Окремого масиву проблемних сигналів у поточному зрізі не зафіксовано."


def _render_concentration(ctx: AnalyticsContext, signals: list[Signal]) -> str:
    for code in ("goal_problem_concentration_half_or_more", "department_problem_concentration_half_or_more"):
        sig = next((s for s in signals if s.code == code), None)
        if sig:
            unit = "СЦ" if code.startswith("goal") else "ССП"
            return f"На {unit} {sig.values.get('label')} припадає {fmt_pct(float(sig.values.get('ratio', 0)) * 100)} проблемних сигналів відповідного рівня."
    return "Проблемні сигнали розподілені без вираженої концентрації в одному компоненті."


def _final_tag(signals: list[Signal]) -> str:
    codes = {s.code for s in signals}
    if codes & {"coverage_very_limited", "coverage_limited", "missing_share_large", "lower_execution_limited_coverage"}:
        return "coverage"
    if codes & {"execution_very_low", "execution_low", "execution_down_broad_coverage", "execution_three_period_decline"}:
        return "negative"
    if codes & {"goal_problem_concentration_half_or_more", "department_problem_concentration_half_or_more"}:
        return "concentration"
    if codes & {"execution_very_high", "execution_high", "execution_up_coverage_up", "execution_three_period_growth"}:
        return "positive"
    return "neutral"


def _render_final(ctx: AnalyticsContext, signals: list[Signal], plan, state, debug) -> str:
    tag = _final_tag(signals)
    return _choose("final", tag, ctx, plan.scenario_key, "final_assessment", state, debug).template


RENDERERS = {
    "overall_state": _render_overall,
    "execution": _render_execution,
    "coverage": _render_coverage,
    "data_quality": _render_data_quality,
    "dynamics": _render_dynamics,
    "year_over_year": _render_yoy,
    "goals": _render_goals,
    "goal_distribution": _render_goals,
    "tasks": _render_tasks,
    "departments": _render_departments,
    "products": _render_products,
    "statuses": _render_statuses,
    "risks": _render_risks,
    "concentration": _render_concentration,
    "final_assessment": _render_final,
}


def compose_note(ctx: AnalyticsContext, *, debug_mode: bool = False) -> GeneratedNote:
    signals = detect_signals(ctx)
    scenarios = activate_scenarios(signals)
    plan = build_text_plan(ctx, signals, scenarios)
    debug = GenerationDebug(
        detected_signals=[s.code for s in signals],
        activated_scenarios=[s.code for s in scenarios],
        selected_blocks=list(plan.blocks),
    )
    state = GenerationState()
    paragraphs = [_render_opening(ctx, plan, state, debug)]
    for block in plan.blocks:
        renderer = RENDERERS.get(block)
        if renderer is None:
            continue
        if block in {"data_quality", "concentration"}:
            text = renderer(ctx, signals)
        else:
            text = renderer(ctx, signals, plan, state, debug)
        if text and text.strip():
            paragraphs.append(text.strip())
    text = clean_text("\n\n".join(paragraphs))
    debug.validation_warnings = validate_text(text, ctx, signals)
    if debug.validation_warnings:
        raise ValueError("Analytics text validation failed: " + "; ".join(debug.validation_warnings))
    return GeneratedNote(text=text, debug=debug)
