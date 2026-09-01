from __future__ import annotations

"""Analytical interpretation over prepared factual metrics.

Findings may rank/connect facts but never create new user-facing numbers.
"""

from typing import Any, Iterable

from .models import AnalyticsContext, AnalyticalFinding, AnalyticalQuestion, Signal
from .analytical_metrics import MetricFloat, MetricInt
from .compatibility import SUPPORTED_FINDING_CODES, compatibility_for


QUESTIONS: tuple[AnalyticalQuestion, ...] = (
    AnalyticalQuestion("what_is_overall_state", (), ("execution", "coverage"), 100),
    AnalyticalQuestion("what_is_trajectory", (), ("periods",), 95),
    AnalyticalQuestion("where_is_current_attention", (), ("goals", "tasks", "departments"), 100),
    AnalyticalQuestion("where_is_data_incomplete", (), ("goals", "departments"), 92),
    AnalyticalQuestion("which_components_drive_result", (), ("goals", "tasks", "departments"), 95),
    AnalyticalQuestion("what_does_mio_add", (), ("mio",), 88),
    AnalyticalQuestion("what_requires_management_attention", (), ("management",), 100),
)


def _f(code: str, topic: str, importance: int, polarity: str = "neutral", *, facts: dict[str, Any] | None = None,
       source_signals: Iterable[str] = (), question: str | None = None) -> AnalyticalFinding:
    return AnalyticalFinding(code=code, topic=topic, importance=importance, polarity=polarity,
                             facts=facts or {}, source_signals=tuple(source_signals), question_code=question)


def _num(value: Any) -> float | None:
    if isinstance(value, (MetricFloat, MetricInt)):
        return float(value)
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int:
    try:
        return 0 if value is None else int(value)
    except (TypeError, ValueError):
        return 0


def _trajectory(ctx: AnalyticsContext) -> list[AnalyticalFinding]:
    facts = dict(ctx.factual_structure("trajectory", {}) or {})
    if not facts:
        return [_f("trajectory_unavailable", "dynamics", 35, facts={}, question="what_is_trajectory")]
    values = list(facts.get("values") or [])
    if len(values) <= 1:
        return [_f("trajectory_single_period", "dynamics", 45, facts=facts, question="what_is_trajectory")]
    deltas = [float(x) for x in (facts.get("deltas") or [])]
    cumulative = _num(facts.get("cumulative_delta")) or 0.0
    if deltas and all(x > 0.5 for x in deltas):
        code, polarity = "trajectory_continuous_growth", "positive"
    elif deltas and all(x < -0.5 for x in deltas):
        code, polarity = "trajectory_continuous_decline", "negative"
    elif len(deltas) >= 2 and deltas[-2] < -0.5 and deltas[-1] > 0.5:
        code, polarity = "trajectory_recovery", "positive"
    elif len(deltas) >= 2 and deltas[-2] > 0.5 and deltas[-1] < -0.5:
        code, polarity = "trajectory_reversal_negative", "negative"
    elif max((abs(x) for x in deltas), default=0) <= 1.0:
        code, polarity = "trajectory_plateau", "neutral"
    elif cumulative > 0:
        code, polarity = "trajectory_net_growth", "positive"
    elif cumulative < 0:
        code, polarity = "trajectory_net_decline", "negative"
    else:
        code, polarity = "trajectory_mixed", "warning"
    out = [_f(code, "dynamics", 93, polarity, facts=facts, question="what_is_trajectory")]
    if len(deltas) >= 2:
        if deltas[-1] > deltas[-2] > 0:
            out.append(_f("trajectory_late_acceleration", "dynamics", 72, "positive", facts={"previous_delta": facts.get("previous_delta"), "latest_delta": facts.get("latest_delta")}, question="what_is_trajectory"))
        elif 0 < deltas[-1] < deltas[-2]:
            out.append(_f("trajectory_growth_slowing", "dynamics", 66, "warning", facts={"previous_delta": facts.get("previous_delta"), "latest_delta": facts.get("latest_delta")}, question="what_is_trajectory"))
        elif deltas[-1] < deltas[-2] < 0:
            out.append(_f("trajectory_decline_accelerating", "dynamics", 84, "negative", facts={"previous_delta": facts.get("previous_delta"), "latest_delta": facts.get("latest_delta")}, question="what_is_trajectory"))
    return out


def _distribution(ctx: AnalyticsContext, kind: str) -> list[AnalyticalFinding]:
    facts = dict(ctx.factual_structure(f"{kind}.distribution", {}) or {})
    if not facts:
        return []
    count = _int(facts.get("count"))
    if count <= 1:
        return [_f(f"{kind}_single_entity", kind, 30, facts=facts)]
    out = [_f(f"{kind}_distribution", kind, 80 if kind in {"goal", "department"} else 70, facts=facts, question="which_components_drive_result")]
    changes = dict(ctx.factual_structure(f"{kind}.change", {}) or {})
    if changes:
        improved, declined = _int(changes.get("improved")), _int(changes.get("declined"))
        if improved and declined:
            code, polarity = f"{kind}_change_polarised", "warning"
        elif improved:
            code, polarity = f"{kind}_change_positive", "positive"
        elif declined:
            code, polarity = f"{kind}_change_negative", "negative"
        else:
            code, polarity = f"{kind}_change_stable", "neutral"
        out.append(_f(code, kind, 78 if kind != "task" else 66, polarity, facts=changes, question="which_components_drive_result"))
    return out


def _concentration(ctx: AnalyticsContext, kind: str, topic: str) -> AnalyticalFinding | None:
    facts = dict(ctx.factual_structure(f"{kind}.{topic}", {}) or {})
    if not facts:
        return None
    # A single goal/task/SSP is not a concentration/distribution. There is no
    # within-dimension comparison to classify, regardless of its current count.
    if _int(facts.get("entity_count")) <= 1:
        return None
    total = _int(facts.get("total"))
    if total <= 0:
        return _f(f"{kind}_{topic}_none", topic, 34, "positive", facts=facts)
    family = str(facts.get("concentration_class") or "").strip()
    if family not in {"concentrated", "localised", "distributed"}:
        # Fail closed rather than silently reintroducing an independent threshold
        # implementation that could diverge from signal/renderer semantics.
        return None
    code = f"{kind}_{topic}_{family}"
    finding_topic = kind if topic == "missing" and kind == "task" else topic
    return _f(code, finding_topic, 92 if topic == "attention" else 84, "warning", facts=facts,
              question="where_is_current_attention" if topic == "attention" else "where_is_data_incomplete")


def _conflicts(ctx: AnalyticsContext) -> list[AnalyticalFinding]:
    trajectory = dict(ctx.factual_structure("trajectory", {}) or {})
    ex_delta, cov_delta = _num(trajectory.get("cumulative_delta")), _num(trajectory.get("coverage_cumulative_delta"))
    out = []
    if ex_delta is not None and cov_delta is not None:
        if ex_delta > 3 and cov_delta < -3:
            out.append(_f("conflict_execution_up_coverage_down", "conflict", 99, "warning", facts={"execution_delta": trajectory.get("cumulative_delta"), "coverage_delta": trajectory.get("coverage_cumulative_delta")}, question="what_is_overall_state"))
        elif ex_delta < -3 and cov_delta > 3:
            out.append(_f("conflict_execution_down_coverage_up", "conflict", 98, "negative", facts={"execution_delta": trajectory.get("cumulative_delta"), "coverage_delta": trajectory.get("coverage_cumulative_delta")}, question="what_is_overall_state"))
    goal_change = dict(ctx.factual_structure("goal.change", {}) or {})
    if ex_delta is not None and abs(ex_delta) < 2 and _int(goal_change.get("improved")) > 0 and _int(goal_change.get("declined")) > 0:
        up, down = _num(goal_change.get("largest_improvement")), _num(goal_change.get("largest_deterioration"))
        if max(abs(up or 0), abs(down or 0)) >= 7:
            out.append(_f("stable_aggregate_hidden_internal_movement", "conflict", 97, "warning", facts={
                "aggregate_delta": trajectory.get("cumulative_delta"),
                "largest_improvement_label": goal_change.get("largest_improvement_label"), "largest_improvement": goal_change.get("largest_improvement"),
                "largest_deterioration_label": goal_change.get("largest_deterioration_label"), "largest_deterioration": goal_change.get("largest_deterioration"),
                "improved": goal_change.get("improved"), "declined": goal_change.get("declined"),
            }, question="what_is_overall_state"))
    return out


def _mio(ctx: AnalyticsContext) -> list[AnalyticalFinding]:
    """Expose the complete target-compatible MіO finding contract.

    Finding codes intentionally match the production base composer so existing
    render branches continue to work without silent loss of task, measure or
    financing analysis. The underlying task execution facts remain exact-latest.
    """
    out: list[AnalyticalFinding] = []
    goals = dict(ctx.factual_structure("mio.goals", {}) or {})
    if goals:
        out.append(_f("mio_integral_profile", "mio", 94, facts=goals, question="what_does_mio_add"))
        if goals.get("divergences"):
            out.append(_f(
                "mio_execution_result_divergence", "mio", 96, "warning",
                facts={"year": goals.get("year"), "items": goals.get("divergences")},
                question="what_does_mio_add",
            ))

    tasks = dict(ctx.factual_structure("mio.tasks", {}) or {})
    if tasks:
        out.append(_f("mio_task_indicator_profile", "mio", 86, facts=tasks, question="what_does_mio_add"))
        if tasks.get("divergences"):
            out.append(_f(
                "mio_task_execution_result_divergence", "mio", 92, "warning",
                facts={"year": tasks.get("year"), "items": tasks.get("divergences")},
                question="what_does_mio_add",
            ))

    measures = dict(ctx.factual_structure("mio.measures", {}) or {})
    if measures:
        out.append(_f("mio_measure_profile", "mio", 72, facts=measures, question="what_does_mio_add"))

    financing = dict(ctx.factual_structure("mio.financing", {}) or {})
    if financing:
        out.append(_f("mio_financing_profile", "mio", 78, facts=financing, question="what_does_mio_add"))
    return out


def _management_priorities(ctx: AnalyticsContext) -> AnalyticalFinding | None:
    """Rank current management priorities without bypassing factual provenance.

    Every user-facing numeric value placed into the finding is taken back from
    the prepared factual registry. Raw pandas values are used only after binding
    for local ranking arithmetic and are never exposed through ``facts``.
    """
    if ctx.sample_size <= 1:
        return None

    candidates: list[dict[str, Any]] = []
    overall_metric = ctx.factual_value("page.completion")
    overall = _num(overall_metric)

    for frame, kind in ((ctx.goal_progress, "goal"), (ctx.department_progress, "department")):
        if frame is None or frame.empty or "Виконання" not in frame.columns:
            continue
        source_name = f"{kind}_progress"
        for pos, (_, row) in enumerate(frame.iterrows()):
            def bound(column: str):
                return ctx.factual_value(f"source.{source_name}.row{pos}.{column}")

            execution_metric = bound("Виконання")
            execution = _num(execution_metric)
            if execution is None:
                # A numeric execution without a factual binding must never enter
                # a user-facing management finding. Fail closed for this row.
                continue

            change_metric = bound("Зміна")
            attention_metric = bound("Актуальна_увага")
            missing_metric = bound("Без_даних")
            weight_metric = bound("portfolio_weight_pct") if kind == "department" else None
            under_metric = bound("underperformance_contribution_pct") if kind == "department" else None

            change = _num(change_metric) or 0.0
            attention = _num(attention_metric) or 0.0
            missing = _num(missing_metric) or 0.0
            weight = _num(weight_metric) or 0.0
            under = _num(under_metric) or 0.0

            label = str(row.get("goal_code") if kind == "goal" else (row.get("department") or row.get("ssp_index") or "")).strip()
            if kind == "goal" and label and not label.upper().startswith("СЦ"):
                label = f"СЦ {label}"

            reasons: list[str] = []
            if attention > 0:
                reasons.append("management_attention")
            if missing > 0:
                reasons.append("data_completeness")
            if change < -2:
                reasons.append("decline")
            if overall is not None and execution < overall - 3:
                reasons.append("underperformance")
            if under > weight + 5:
                reasons.append("structural_contribution")
            if not reasons or not label:
                continue

            # Local ranking score is intentionally not exposed as a finding fact.
            score = (
                max(0.0, 100.0 - min(execution, 100.0)) * 0.25
                + attention * 4.0
                + missing * 2.5
                + max(0.0, -change) * 1.5
                + under * 0.5
                + weight * 0.1
            )
            candidates.append({
                "kind": kind,
                "label": label,
                "score": score,
                "execution": execution_metric,
                "change": change_metric,
                "attention": attention_metric,
                "missing": missing_metric,
                "portfolio_weight": weight_metric,
                "underperformance_contribution": under_metric,
                "reason_types": tuple(reasons),
            })

    if not candidates:
        return None
    ranked = sorted(candidates, key=lambda x: (-x["score"], x["kind"], x["label"]))[:3]
    public = [{k: v for k, v in item.items() if k != "score"} for item in ranked]
    return _f(
        "management_priorities",
        "management_attention",
        100,
        "warning",
        facts={
            "priorities": public,
            "attention_type": ctx.metrics.get("attention_type"),
            "attention_label": ctx.metrics.get("attention_label"),
        },
        question="what_requires_management_attention",
    )


def derive_findings(ctx: AnalyticsContext, signals: list[Signal]) -> tuple[list[AnalyticalQuestion], list[AnalyticalFinding]]:
    findings: list[AnalyticalFinding] = []
    findings.append(_f("overall_state", "general", 100, facts={
        "execution_latest": ctx.factual_value("page.completion"),
        "goal_execution_latest": ctx.factual_value("page.goal_completion"),
        "coverage_average": ctx.factual_value("page.coverage"),
        "coverage_latest": ctx.factual_value("page.coverage_latest"),
        "attention_count": ctx.factual_value("page.attention_count"),
        "attention_type": ctx.metrics.get("attention_type"),
        "attention_label": ctx.metrics.get("attention_label"),
        "missing_count": ctx.factual_value("page.no_data"),
        "latest_measure_count": ctx.factual_value("page.latest_measure_count"),
        "missing_share": ctx.factual_value("overall.missing_latest_share_pct"),
        "attention_share": ctx.factual_value("overall.attention_latest_share_pct"),
    }, question="what_is_overall_state"))
    gap = ctx.factual_value("overall.measure_goal_gap_pp")
    if gap is not None:
        findings.append(_f("execution_goal_divergence" if abs(float(gap)) >= 3 else "execution_goal_alignment", "general", 78 if abs(float(gap)) >= 3 else 40, "warning" if abs(float(gap)) >= 3 else "neutral", facts={"measure_execution": ctx.factual_value("page.completion"), "goal_execution": ctx.factual_value("page.goal_completion"), "gap": gap}, question="what_is_overall_state"))
    findings.extend(_trajectory(ctx))
    for kind in ("goal", "task", "department"):
        findings.extend(_distribution(ctx, kind))
        for topic in ("attention", "missing"):
            item = _concentration(ctx, kind, topic)
            if item: findings.append(item)
    for structure, code, topic, importance in (("drilldown.goal", "goal_drilldown", "task", 90), ("drilldown.ssp", "ssp_drilldown", "department", 92)):
        facts = dict(ctx.factual_structure(structure, {}) or {})
        if facts: findings.append(_f(code, topic, importance, "warning", facts=facts, question="which_components_drive_result"))
    portfolio = dict(ctx.factual_structure("ssp.portfolio", {}) or {})
    if portfolio: findings.append(_f("ssp_portfolio_impact", "departments", 88, "warning", facts=portfolio, question="which_components_drive_result"))
    risk = dict(ctx.factual_structure("risk", {}) or {})
    if risk: findings.append(_f("risk_structure", "risk", 78, "warning", facts=risk))
    status = dict(ctx.factual_structure("status", {}) or {})
    if status: findings.append(_f("status_structure", "statuses", 68, facts=status))
    persistence = list(ctx.factual_structure("missing_persistence", []) or [])
    if persistence: findings.append(_f("missing_persistence", "missing", 76, "warning", facts={"items": persistence}, question="where_is_data_incomplete"))
    product = dict(ctx.factual_structure("product", {}) or {})
    if product: findings.append(_f("product_structure", "products", 52, facts=product))
    findings.extend(_conflicts(ctx))
    findings.extend(_mio(ctx))
    priorities = _management_priorities(ctx)
    if priorities: findings.append(priorities)
    strongest: dict[str, AnalyticalFinding] = {}
    for item in findings:
        if item.code not in SUPPORTED_FINDING_CODES:
            raise ValueError(f"Undefined current Analytics finding contract: {item.code}")
        spec = compatibility_for(item.code)
        if item.topic != spec.topic:
            raise ValueError(
                f"Analytics finding topic mismatch for {item.code}: {item.topic!r} != {spec.topic!r}"
            )
        if item.code not in strongest or item.importance > strongest[item.code].importance:
            strongest[item.code] = item
    return list(QUESTIONS), sorted(strongest.values(), key=lambda item: (-item.importance, item.topic, item.code))
