from __future__ import annotations

"""Analytical interpretation over prepared factual metrics.

This layer may classify, rank and connect facts, but it must not create new
user-facing numeric metrics. Every number exposed through a finding must already
exist in ``AnalyticsContext.analytical_facts`` with provenance.
"""

from dataclasses import dataclass
from statistics import median
from typing import Any, Iterable

import pandas as pd

from .config import DELTA_LANGUAGE_BANDS, VOLATILITY_LANGUAGE_BAND
from .language import is_number
from .models import AnalyticsContext, AnalyticalFinding, AnalyticalQuestion, Signal
from .analytical_metrics import MetricFloat, MetricInt, metric_code_of


QUESTIONS: tuple[AnalyticalQuestion, ...] = (
    AnalyticalQuestion("what_is_scope", (), ("scope",), 50),
    AnalyticalQuestion("what_is_overall_state", (), ("execution", "coverage"), 80),
    AnalyticalQuestion("what_is_full_trajectory", ("execution_increased", "execution_decreased"), ("periods",), 90),
    AnalyticalQuestion("is_change_broad_based", ("execution_increased", "execution_decreased"), ("goals", "departments"), 90),
    AnalyticalQuestion("where_are_problems", ("problem_signals_present", "problem_signals_large_share"), ("goals", "tasks", "departments"), 95),
    AnalyticalQuestion("where_is_missing", ("missing_share_small", "missing_share_material", "missing_share_large"), ("goals", "departments"), 90),
    AnalyticalQuestion("which_goals_drive_picture", (), ("goals",), 85),
    AnalyticalQuestion("which_tasks_localise_deviation", (), ("tasks",), 75),
    AnalyticalQuestion("which_ssp_matter_by_scale", (), ("departments",), 90),
    AnalyticalQuestion("what_changed_yoy", (), ("yoy",), 75),
    AnalyticalQuestion("are_signals_conflicting", (), ("execution", "coverage", "problems"), 90),
    AnalyticalQuestion("what_requires_management_attention", (), ("goals", "tasks", "departments"), 100),
)


def _f(code: str, topic: str, importance: int, polarity: str = "neutral", *, facts: dict[str, Any] | None = None,
       source_signals: Iterable[str] = (), question: str | None = None) -> AnalyticalFinding:
    return AnalyticalFinding(
        code=code, topic=topic, importance=importance, polarity=polarity,
        facts=facts or {}, source_signals=tuple(source_signals), question_code=question,
    )


def _num(value: Any) -> float | None:
    if isinstance(value, (MetricFloat, MetricInt)):
        return value
    return float(value) if is_number(value) else None


def _int(value: Any) -> int:
    if isinstance(value, MetricInt):
        return value
    try:
        if pd.isna(value):
            return 0
    except (TypeError, ValueError):
        pass
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _numeric_col(frame: pd.DataFrame, column: str, default: float | None = None) -> pd.Series:
    if column in frame.columns:
        return pd.to_numeric(frame[column], errors="coerce")
    fill = float("nan") if default is None else default
    return pd.Series(fill, index=frame.index, dtype=float)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _label_for(frame: pd.DataFrame, row: pd.Series, kind: str) -> str:
    if kind == "goal":
        code = _safe_str(row.get("goal_code"))
        return f"СЦ {code}" if code and not code.upper().startswith("СЦ") else code
    if kind == "task":
        code = _safe_str(row.get("task_code"))
        name = _safe_str(row.get("task_name"))
        return f"{code} — {name}" if code and name else (code or name)
    if kind == "department":
        return _safe_str(row.get("department")) or _safe_str(row.get("ssp_index"))
    if kind == "product":
        return _safe_str(row.get("product_type"))
    return ""


def _sorted_periods(ctx: AnalyticsContext) -> pd.DataFrame:
    frame = ctx.period_dynamics.copy()
    if frame.empty:
        return frame
    qmap = {"I": 1, "II": 2, "III": 3, "IV": 4, "1": 1, "2": 2, "3": 3, "4": 4}
    frame["_year"] = pd.to_numeric(frame.get("report_year"), errors="coerce")
    q = frame.get("report_quarter", pd.Series(index=frame.index, dtype=object)).astype(str)
    frame["_q"] = q.map(qmap)
    return frame.sort_values(["_year", "_q"], na_position="last").reset_index(drop=True)


def _trajectory_finding(ctx: AnalyticsContext) -> list[AnalyticalFinding]:
    facts = dict(ctx.factual_structure("trajectory", {}) or {})
    if not facts:
        return [_f("trajectory_unavailable", "dynamics", 35, facts={"period_count": 0}, question="what_is_full_trajectory")]
    vals = list(facts.get("values") or [])
    if len(vals) == 1:
        return [_f("trajectory_single_period", "dynamics", 45, facts=facts, question="what_is_full_trajectory")]
    deltas = list(facts.get("deltas") or [])
    small_delta = float(DELTA_LANGUAGE_BANDS["small"])
    if deltas and all(abs(d) < small_delta for d in deltas):
        code, polarity = "trajectory_plateau", "neutral"
    elif deltas and all(d > 0 for d in deltas):
        code, polarity = "trajectory_continuous_growth", "positive"
    elif deltas and all(d < 0 for d in deltas):
        code, polarity = "trajectory_continuous_decline", "negative"
    elif len(deltas) >= 2 and deltas[-2] <= -small_delta and deltas[-1] >= small_delta:
        code, polarity = "trajectory_recovery", "positive"
    elif len(deltas) >= 2 and deltas[-2] >= small_delta and deltas[-1] <= -small_delta:
        code, polarity = "trajectory_reversal_negative", "negative"
    elif vals and max(vals) - min(vals) >= VOLATILITY_LANGUAGE_BAND and any(d > 0 for d in deltas) and any(d < 0 for d in deltas):
        code, polarity = "trajectory_volatile", "warning"
    elif facts.get("cumulative_delta", 0) > 0:
        code, polarity = "trajectory_net_growth", "positive"
    elif facts.get("cumulative_delta", 0) < 0:
        code, polarity = "trajectory_net_decline", "negative"
    else:
        code, polarity = "trajectory_mixed_stable", "neutral"
    findings = [_f(code, "dynamics", 92 if len(vals) >= 3 else 80, polarity, facts=facts, question="what_is_full_trajectory")]
    if len(deltas) >= 2:
        pace = {"previous_delta": facts.get("previous_delta"), "latest_delta": facts.get("latest_delta")}
        if deltas[-1] > deltas[-2] > 0:
            findings.append(_f("trajectory_late_acceleration", "dynamics", 72, "positive", facts=pace, question="what_is_full_trajectory"))
        elif 0 < deltas[-1] < deltas[-2]:
            findings.append(_f("trajectory_growth_slowing", "dynamics", 62, "warning", facts=pace, question="what_is_full_trajectory"))
        elif deltas[-1] < deltas[-2] < 0:
            findings.append(_f("trajectory_decline_accelerating", "dynamics", 82, "negative", facts=pace, question="what_is_full_trajectory"))
    return findings


def _distribution_findings(ctx: AnalyticsContext, kind: str) -> list[AnalyticalFinding]:
    facts = dict(ctx.factual_structure(f"{kind}.distribution", {}) or {})
    if not facts:
        return []
    if _int(facts.get("count")) == 1:
        return [_f(f"{kind}_single_entity", kind, 40, facts=facts)]
    result = [_f(f"{kind}_distribution", kind, 82 if kind in {"goal", "department"} else 68, "neutral", facts=facts)]
    change_facts = dict(ctx.factual_structure(f"{kind}.change", {}) or {})
    if change_facts:
        improved, declined, total = (_int(change_facts.get("improved")), _int(change_facts.get("declined")), _int(change_facts.get("count_with_change")))
        improved_share = _num(change_facts.get("improved_share")) or 0.0
        declined_share = _num(change_facts.get("declined_share")) or 0.0
        if improved_share >= 70.0 and improved > declined:
            code, polarity = f"{kind}_change_broad_positive", "positive"
        elif declined_share >= 70.0 and declined > improved:
            code, polarity = f"{kind}_change_broad_negative", "negative"
        elif improved and declined:
            code, polarity = f"{kind}_change_polarised", "warning"
        elif improved:
            code, polarity = f"{kind}_change_positive", "positive"
        elif declined:
            code, polarity = f"{kind}_change_negative", "negative"
        else:
            code, polarity = f"{kind}_change_stable", "neutral"
        result.append(_f(code, kind, 85 if kind in {"goal", "department"} else 70, polarity, facts=change_facts, question="is_change_broad_based"))
    return result


def _concentration_finding(ctx: AnalyticsContext, kind: str, topic: str, question: str) -> AnalyticalFinding | None:
    facts = dict(ctx.factual_structure(f"{kind}.{topic}", {}) or {})
    if not facts:
        return None
    total = _int(facts.get("total"))
    if total <= 0:
        return _f(f"{kind}_{topic}_none", topic, 35, "positive", facts=facts, question=question)
    top1_share = _num(facts.get("top_share")) or 0.0
    top3_share = _num(facts.get("top3_share")) or 0.0
    affected = _int(facts.get("affected_entities")); entity_count = _int(facts.get("entity_count"))
    if top1_share >= 50.0 or top3_share >= 70.0:
        code, polarity = f"{kind}_{topic}_concentrated", "negative" if topic in {"problems", "missing"} else "warning"
    elif affected <= max(2, entity_count // 4):
        code, polarity = f"{kind}_{topic}_localised", "warning"
    else:
        code, polarity = f"{kind}_{topic}_distributed", "neutral"
    return _f(code, topic, 88 if topic in {"problems", "missing"} else 70, polarity, facts=facts, question=question)


def _status_finding(ctx: AnalyticsContext) -> AnalyticalFinding | None:
    facts = dict(ctx.factual_structure("status", {}) or {})
    if not facts:
        return None
    total = _int(facts.get("total"))
    importance = 45 if total <= 5 else 48
    if (_num(facts.get("dominant_share")) or 0.0) >= 60.0:
        importance = max(importance, 65)
    comparison = facts.get("period_comparison") or {}
    changes = comparison.get("share_changes_pp", {}) or {}
    max_change = max((abs(float(v)) for v in changes.values() if is_number(v)), default=0.0)
    importance = max(importance, 68 if max_change >= 5.0 else 55) if comparison else importance
    return _f("status_structure", "statuses", importance, facts=facts)


def _product_finding(ctx: AnalyticsContext) -> AnalyticalFinding | None:
    facts = dict(ctx.factual_structure("product", {}) or {})
    if not facts:
        return None
    importance = 60 if facts.get("problem_total") or facts.get("missing_total") else 48
    return _f("product_structure", "products", importance, facts=facts)


def _yoy_finding(ctx: AnalyticsContext) -> AnalyticalFinding | None:
    facts = dict(ctx.factual_structure("yoy", {}) or {})
    if not facts:
        return None
    comparisons = facts.get("comparisons", []) or []
    def _direction(metrics: dict[str, dict[str, Any]]) -> tuple[int, int]:
        execution = metrics.get("Рівень виконання СП", {}).get("change")
        coverage = metrics.get("Покриття моніторингом", {}).get("change")
        problems = metrics.get("Проблемні / ризикові", {}).get("change")
        missing = metrics.get("Без поданих погоджених даних", {}).get("change")
        positive = sum(x is not None and x > 0 for x in (execution, coverage)) + sum(x is not None and x < 0 for x in (problems, missing))
        negative = sum(x is not None and x < 0 for x in (execution, coverage)) + sum(x is not None and x > 0 for x in (problems, missing))
        return positive, negative
    if len(comparisons) > 1:
        execution_changes = facts.get("execution_changes", []) or []
        if execution_changes and all(x > 0 for x in execution_changes):
            code, polarity = "yoy_multi_continuous_improvement", "positive"
        elif execution_changes and all(x < 0 for x in execution_changes):
            code, polarity = "yoy_multi_continuous_deterioration", "negative"
        elif execution_changes and any(x > 0 for x in execution_changes) and any(x < 0 for x in execution_changes):
            code, polarity = "yoy_multi_reversal", "warning"
        else:
            directions = [_direction(comp.get("metrics", {})) for comp in comparisons]
            code, polarity = ("yoy_multi_mixed", "warning") if any(p and n for p, n in directions) else ("yoy_multi_limited", "neutral")
        return _f(code, "yoy", 88, polarity, facts=facts, question="what_changed_yoy")
    metrics = (comparisons[-1].get("metrics", {}) if comparisons else facts.get("metrics", {})) or {}
    positive, negative = _direction(metrics)
    if positive and negative: code, polarity = "yoy_mixed_change", "warning"
    elif positive: code, polarity = "yoy_broad_improvement", "positive"
    elif negative: code, polarity = "yoy_broad_deterioration", "negative"
    else: code, polarity = "yoy_limited_change", "neutral"
    return _f(code, "yoy", 78, polarity, facts=facts, question="what_changed_yoy")


def _active_group_counts(ctx: AnalyticsContext, group_col: str) -> pd.DataFrame:
    data = ctx.active.copy()
    if data.empty or group_col not in data.columns:
        return pd.DataFrame()
    key = data[group_col].fillna("").astype(str)
    data = data.assign(_group=key)
    data = data[data["_group"].str.strip().ne("")]
    if data.empty:
        return pd.DataFrame()
    problem = data.get("is_problem_status", pd.Series(False, index=data.index)).fillna(False).astype(bool)
    missing = data.get("missing_required_submission", pd.Series(False, index=data.index)).fillna(False).astype(bool)
    rows = []
    for label, group in data.groupby("_group", dropna=False):
        ix = group.index
        rows.append({"label": label, "rows": len(group), "measures": group.get("code", pd.Series(index=group.index, dtype=object)).nunique(),
                     "problems": int(problem.loc[ix].sum()), "missing": int(missing.loc[ix].sum())})
    return pd.DataFrame(rows)


def _goal_drilldown(ctx: AnalyticsContext) -> AnalyticalFinding | None:
    facts = dict(ctx.factual_structure("drilldown.goal", {}) or {})
    if not facts:
        return None
    return _f("goal_drilldown", "tasks", 83, "negative", facts=facts, question="which_tasks_localise_deviation")


def _ssp_drilldown(ctx: AnalyticsContext) -> AnalyticalFinding | None:
    facts = dict(ctx.factual_structure("drilldown.ssp", {}) or {})
    if not facts:
        return None
    return _f("ssp_drilldown", "departments", 90, "negative", facts=facts, question="which_ssp_matter_by_scale")


def _ssp_portfolio_findings(ctx: AnalyticsContext) -> list[AnalyticalFinding]:
    facts = dict(ctx.factual_structure("ssp.portfolio", {}) or {})
    if not facts:
        return []
    return [_f("ssp_portfolio_impact", "departments", 92, "warning", facts=facts, question="which_ssp_matter_by_scale")]


def _risk_finding(ctx: AnalyticsContext) -> AnalyticalFinding | None:
    facts = dict(ctx.factual_structure("risk", {}) or {})
    if not facts:
        return None
    if not any(is_number(v) for v in facts.values() if not isinstance(v, str)) and not facts.get("top_risk_department"):
        return None
    return _f("risk_structure", "risk", 82, "warning", facts=facts)


def _execution_divergence_finding(ctx: AnalyticsContext) -> AnalyticalFinding | None:
    measures = ctx.factual_value("page.completion"); goals = ctx.factual_value("page.goal_completion")
    latest_measures = ctx.factual_value("page.completion_latest"); latest_goals = ctx.factual_value("page.goal_completion_latest")
    if measures is None or goals is None:
        return None
    gap = ctx.factual_value("overall.measure_goal_gap_pp")
    latest_gap = ctx.factual_value("overall.latest_measure_goal_gap_pp")
    facts = {"measure_execution": measures, "goal_execution": goals, "gap": gap,
             "latest_measure_execution": latest_measures, "latest_goal_execution": latest_goals, "latest_gap": latest_gap}
    if gap is not None and abs(float(gap)) < 2 and (latest_gap is None or abs(float(latest_gap)) < 2):
        return _f("execution_goal_alignment", "general", 45, "neutral", facts=facts)
    return _f("execution_goal_divergence", "general", 86, "warning", facts=facts)


def _persistent_descriptive_findings(ctx: AnalyticsContext) -> list[AnalyticalFinding]:
    items = list(ctx.factual_structure("persistence", []) or [])
    out: list[AnalyticalFinding] = []
    for item in items:
        kind = item.get("kind")
        label_fn = (lambda x: f"СЦ {x}") if kind == "goal" else (lambda x: f"ССП «{x}»")
        problem = item.get("problem")
        missing = item.get("missing")
        if problem and problem[1] >= 3:
            out.append(_f(f"persistent_{kind}_problems", "problems", 78, "negative", facts={
                "label": label_fn(problem[0]), "periods_with_problem": problem[1], "periods_observed": problem[3]
            }))
        if missing and missing[2] >= 3:
            out.append(_f(f"persistent_{kind}_missing", "missing", 76, "warning", facts={
                "label": label_fn(missing[0]), "periods_with_missing": missing[2], "periods_observed": missing[3]
            }))
    return out


def _conflict_findings(ctx: AnalyticsContext, findings: list[AnalyticalFinding], signals: list[Signal]) -> list[AnalyticalFinding]:
    codes = {s.code for s in signals}
    result: list[AnalyticalFinding] = []
    trajectory = next((f for f in findings if f.topic == "dynamics" and "cumulative_delta" in f.facts), None)
    goal_change = next((f for f in findings if f.code.startswith("goal_change_")), None)
    if trajectory:
        ex_delta = _num(trajectory.facts.get("cumulative_delta"))
        cov_delta = _num(trajectory.facts.get("coverage_cumulative_delta"))
        if ex_delta is not None and ex_delta > 0 and cov_delta is not None and cov_delta < 0:
            result.append(_f("conflict_execution_up_coverage_down", "conflict", 98, "warning", facts={"execution_delta": ex_delta, "coverage_delta": cov_delta}, question="are_signals_conflicting"))
        if ex_delta is not None and ex_delta < 0 and cov_delta is not None and cov_delta > 0:
            result.append(_f("conflict_execution_down_coverage_up", "conflict", 96, "negative", facts={"execution_delta": ex_delta, "coverage_delta": cov_delta}, question="are_signals_conflicting"))
    if "execution_up_problems_up" in codes:
        yoy_metrics = (ctx.factual_structure("yoy", {}) or {}).get("metrics", {}) or {}
        problem_change = (yoy_metrics.get("Проблемні / ризикові", {}) or {}).get("change")
        result.append(_f("conflict_execution_up_problems_up", "conflict", 96, "warning", facts={
            "problem_count": ctx.factual_value("page.problem", _int(ctx.metric("problem"))),
            "problem_change": problem_change,
        }, source_signals=("execution_up_problems_up",), question="are_signals_conflicting"))
    # Aggregate stability can hide strong internal movement.
    if trajectory and goal_change:
        cumulative = abs(float(trajectory.facts.get("cumulative_delta") or 0))
        largest_up = abs(float(goal_change.facts.get("largest_improvement") or 0))
        largest_down = abs(float(goal_change.facts.get("largest_deterioration") or 0))
        if cumulative < 2 and max(largest_up, largest_down) >= 7 and goal_change.facts.get("improved", 0) and goal_change.facts.get("declined", 0):
            result.append(_f("stable_aggregate_hidden_internal_movement", "conflict", 99, "warning", facts={
                "aggregate_delta": trajectory.facts.get("cumulative_delta"),
                "largest_improvement_label": goal_change.facts.get("largest_improvement_label"), "largest_improvement": goal_change.facts.get("largest_improvement"),
                "largest_deterioration_label": goal_change.facts.get("largest_deterioration_label"), "largest_deterioration": goal_change.facts.get("largest_deterioration"),
                "improved": goal_change.facts.get("improved"), "declined": goal_change.facts.get("declined"),
            }, question="are_signals_conflicting"))
    return result


def _management_priorities(ctx: AnalyticsContext) -> AnalyticalFinding | None:
    if ctx.sample_size <= 1:
        return None
    candidates: list[dict[str, Any]] = []
    overall = ctx.factual_value("page.completion")

    gp = ctx.goal_progress.copy()
    if not gp.empty:
        gp["_exec"] = _numeric_col(gp, "Виконання")
        gp["_change"] = _numeric_col(gp, "Зміна", 0).fillna(0)
        gp["_problem"] = _numeric_col(gp, "Проблемних", 0).fillna(0)
        gp["_missing"] = _numeric_col(gp, "Без_даних", 0).fillna(0)
        for pos, (_, row) in enumerate(gp.iterrows()):
            if pd.isna(row["_exec"]):
                continue
            execution = ctx.factual_value(f"source.goal_progress.row{pos}.Виконання")
            change = ctx.factual_value(f"source.goal_progress.row{pos}.Зміна")
            problems = ctx.factual_value(f"source.goal_progress.row{pos}.Проблемних")
            missing = ctx.factual_value(f"source.goal_progress.row{pos}.Без_даних")
            ex = float(execution if execution is not None else row["_exec"])
            ch = float(change if change is not None else row["_change"])
            pr = float(problems if problems is not None else row["_problem"])
            mi = float(missing if missing is not None else row["_missing"])
            is_attention = pr > 0 or mi > 0 or ch < -2 or (overall is not None and ex < float(overall) - 2)
            if is_attention:
                score = (100 - ex) * 0.35 + max(0, -ch) * 1.1 + pr * 2 + mi * 1.3
                candidates.append({"kind": "goal", "label": _label_for(gp, row, "goal"), "score": score,
                                   "execution": execution, "change": change, "problems": problems, "missing": missing})

    dp = ctx.department_progress.copy()
    if not dp.empty:
        dp["_exec"] = _numeric_col(dp, "Виконання")
        dp["_change"] = _numeric_col(dp, "Зміна", 0).fillna(0)
        dp["_problem"] = _numeric_col(dp, "Проблемних", 0).fillna(0)
        dp["_missing"] = _numeric_col(dp, "Без_даних", 0).fillna(0)
        dp["_weight"] = _numeric_col(dp, "portfolio_weight_pct", 0).fillna(0)
        dp["_under"] = _numeric_col(dp, "underperformance_contribution_pct", 0).fillna(0)
        for pos, (_, row) in enumerate(dp.iterrows()):
            if pd.isna(row["_exec"]):
                continue
            execution = ctx.factual_value(f"source.department_progress.row{pos}.Виконання")
            change = ctx.factual_value(f"source.department_progress.row{pos}.Зміна")
            problems = ctx.factual_value(f"source.department_progress.row{pos}.Проблемних")
            missing = ctx.factual_value(f"source.department_progress.row{pos}.Без_даних")
            weight = ctx.factual_value(f"source.department_progress.row{pos}.portfolio_weight_pct")
            under = ctx.factual_value(f"source.department_progress.row{pos}.underperformance_contribution_pct")
            ex = float(execution if execution is not None else row["_exec"]); ch = float(change if change is not None else row["_change"])
            pr = float(problems if problems is not None else row["_problem"]); mi = float(missing if missing is not None else row["_missing"])
            wt = float(weight if weight is not None else row["_weight"]); un = float(under if under is not None else row["_under"])
            is_attention = pr > 0 or mi > 0 or ch < -2 or un > 0 or (overall is not None and ex < float(overall) - 2)
            if is_attention:
                score = (100 - ex) * 0.20 + max(0, -ch) + pr * 1.5 + mi + wt * 0.25 + un * 0.8
                candidates.append({"kind": "department", "label": _label_for(dp, row, "department"), "score": score,
                                   "execution": execution, "change": change, "problems": problems, "missing": missing,
                                   "portfolio_weight": weight, "underperformance_contribution": under})
    candidates = [c for c in candidates if c["label"]]
    if not candidates:
        return None
    ranked = sorted(candidates, key=lambda x: (-x["score"], x["kind"], x["label"]))[:5]
    public = [{k: v for k, v in c.items() if k != "score"} for c in ranked]
    return _f("management_priorities", "management_attention", 100, "warning", facts={"priorities": public}, question="what_requires_management_attention")



def _mio_findings(ctx: AnalyticsContext) -> list[AnalyticalFinding]:
    """Interpret MIO facts prepared by the shared analytical calculation layer."""
    out: list[AnalyticalFinding] = []
    goals = dict(ctx.factual_structure("mio.goals", {}) or {})
    if goals:
        out.append(_f("mio_integral_profile", "mio", 94, "neutral", facts=goals, question="how_does_execution_translate_to_strategic_result"))
        if goals.get("divergences"):
            out.append(_f("mio_execution_result_divergence", "mio", 96, "warning", facts={"year": goals.get("year"), "items": goals.get("divergences")}, question="where_does_measure_execution_not_translate_to_result"))
    tasks = dict(ctx.factual_structure("mio.tasks", {}) or {})
    if tasks:
        out.append(_f("mio_task_indicator_profile", "mio", 86, "neutral", facts=tasks, question="how_do_task_results_compare_with_execution"))
        if tasks.get("divergences"):
            out.append(_f("mio_task_execution_result_divergence", "mio", 92, "warning", facts={"year": tasks.get("year"), "items": tasks.get("divergences")}, question="where_do_task_indicators_diverge_from_execution"))
    measures = dict(ctx.factual_structure("mio.measures", {}) or {})
    if measures:
        out.append(_f("mio_measure_profile", "mio", 72, "neutral", facts=measures, question="what_is_measure_level_mio_result"))
    financing = dict(ctx.factual_structure("mio.financing", {}) or {})
    if financing:
        out.append(_f("mio_financing_profile", "mio", 78, "neutral", facts=financing, question="how_does_financing_compare_with_physical_result"))
    return out


def derive_findings(ctx: AnalyticsContext, signals: list[Signal]) -> tuple[list[AnalyticalQuestion], list[AnalyticalFinding]]:
    """Close the analytical loop using all dimensions already available in context."""
    questions = list(QUESTIONS)
    findings: list[AnalyticalFinding] = []
    execution = ctx.factual_value("page.completion")
    coverage = ctx.factual_value("page.coverage")
    findings.append(_f("scope_profile", "scope", 25, facts={
        "rows": ctx.factual_value("page.total_rows"),
        "measures": ctx.factual_value("page.unique_measures"),
        "goals": ctx.factual_value("page.goals"),
        "tasks": ctx.factual_value("page.tasks"),
        "departments": ctx.factual_value("scope.department_count", int(len(ctx.department_progress)) if ctx.department_progress is not None else 0),
        "products": ctx.factual_value("scope.product_count", int(len(ctx.product_progress)) if ctx.product_progress is not None else 0),
        "years": list(ctx.filters.get("years", []) or []), "quarters": list(ctx.filters.get("quarters", []) or []),
    }, question="what_is_scope"))
    findings.append(_f("overall_state", "general", 90, facts={
        "execution_average": execution, "coverage_average": coverage,
        "execution_latest": ctx.factual_value("page.completion_latest"), "coverage_latest": ctx.factual_value("page.coverage_latest"),
        "problem_count": ctx.factual_value("page.problem"),
        "missing_count": ctx.factual_value("page.no_data"),
        "completed_count": ctx.factual_value("page.completed"),
    }, question="what_is_overall_state"))
    divergence = _execution_divergence_finding(ctx)
    if divergence: findings.append(divergence)
    findings.extend(_trajectory_finding(ctx))
    findings.extend(_distribution_findings(ctx, "goal"))
    findings.extend(_distribution_findings(ctx, "task"))
    findings.extend(_distribution_findings(ctx, "department"))
    for kind in ("goal", "task", "department"):
        item = _concentration_finding(ctx, kind, "problems", "where_are_problems")
        if item: findings.append(item)
        item = _concentration_finding(ctx, kind, "missing", "where_is_missing")
        if item: findings.append(item)
    status = _status_finding(ctx)
    if status: findings.append(status)
    risk = _risk_finding(ctx)
    if risk: findings.append(risk)
    findings.extend(_persistent_descriptive_findings(ctx))
    product = _product_finding(ctx)
    if product: findings.append(product)
    yoy = _yoy_finding(ctx)
    if yoy: findings.append(yoy)
    findings.extend(_ssp_portfolio_findings(ctx))
    gd = _goal_drilldown(ctx)
    if gd: findings.append(gd)
    sd = _ssp_drilldown(ctx)
    if sd: findings.append(sd)
    findings.extend(_conflict_findings(ctx, findings, signals))
    findings.extend(_mio_findings(ctx))
    mp = _management_priorities(ctx)
    if mp: findings.append(mp)

    # Deduplicate by code, keeping the highest-importance instance.
    strongest: dict[str, AnalyticalFinding] = {}
    for item in findings:
        if item.code not in strongest or item.importance > strongest[item.code].importance:
            strongest[item.code] = item
    ordered = sorted(strongest.values(), key=lambda item: (-item.importance, item.topic, item.code))
    return questions, ordered


SUPPORTED_FINDING_CODES = frozenset({
    # Dynamic codes are additionally generated by kind; keeping this registry broad
    # makes scenario validation possible without coupling it to test fixtures.
    "scope_profile", "overall_state", "trajectory_unavailable", "trajectory_single_period",
    "trajectory_continuous_growth", "trajectory_continuous_decline", "trajectory_plateau", "trajectory_recovery",
    "trajectory_reversal_negative", "trajectory_volatile", "trajectory_net_growth", "trajectory_net_decline", "trajectory_mixed_stable",
    "trajectory_late_acceleration", "trajectory_growth_slowing", "trajectory_decline_accelerating",
    "status_structure", "product_structure", "yoy_mixed_change", "yoy_broad_improvement", "yoy_broad_deterioration", "yoy_limited_change",
    "yoy_multi_continuous_improvement", "yoy_multi_continuous_deterioration", "yoy_multi_reversal", "yoy_multi_mixed", "yoy_multi_limited",
    "ssp_portfolio_impact", "goal_drilldown", "ssp_drilldown", "management_priorities",
    "risk_structure", "execution_goal_alignment", "execution_goal_divergence",
    "persistent_goal_problems", "persistent_goal_missing", "persistent_department_problems", "persistent_department_missing",
    "conflict_execution_up_coverage_down", "conflict_execution_down_coverage_up", "conflict_execution_up_problems_up",
    "stable_aggregate_hidden_internal_movement", "mio_integral_profile", "mio_execution_result_divergence",
    "mio_task_indicator_profile", "mio_task_execution_result_divergence", "mio_measure_profile", "mio_financing_profile",
} | {
    f"{kind}_{suffix}"
    for kind in ("goal", "task", "department")
    for suffix in (
        "single_entity", "distribution", "change_broad_positive", "change_broad_negative", "change_polarised", "change_positive", "change_negative", "change_stable",
        "problems_none", "problems_concentrated", "problems_localised", "problems_distributed",
        "missing_none", "missing_concentrated", "missing_localised", "missing_distributed",
    )
})
