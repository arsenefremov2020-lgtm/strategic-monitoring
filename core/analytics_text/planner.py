from __future__ import annotations

from collections import defaultdict

import pandas as pd

from .models import AnalyticsContext, AnalyticalFinding, BlockPlan, Scenario, Signal, TextPlan
from .compatibility import compatibility_for


# Production flow retained with only currently supported Analytics blocks.
BASE_BLOCK_ORDER = (
    "overall_state", "dynamics", "coverage", "goals", "tasks",
    "departments", "mio_assessment", "statuses", "products",
    "management_attention", "final_assessment",
)

TOPIC_TO_BLOCK = {
    "scope": "scope", "general": "overall_state", "conflict": "final_assessment",
    "dynamics": "dynamics", "coverage": "coverage", "missing": "coverage",
    "goal": "goals", "task": "tasks", "tasks": "tasks", "department": "departments",
    "departments": "departments", "statuses": "statuses", "products": "products",
    "risk": "management_attention", "attention": "management_attention",
    "mio": "mio_assessment", "management_attention": "management_attention",
}

DEPTH_SENTENCES = {
    "brief": (2, 3), "standard": (3, 4), "deep": (4, 6), "critical": (5, 7),
}


def _safe_int(value) -> int:
    try:
        if value is None or pd.isna(value):
            return 0
    except (TypeError, ValueError):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return 0


def context_complexity_score(ctx: AnalyticsContext, signals: list[Signal], findings: list[AnalyticalFinding]) -> str:
    periods = len(ctx.period_dynamics) if ctx.period_dynamics is not None else 0
    goals = len(ctx.goal_progress) if ctx.goal_progress is not None else 0
    tasks = len(ctx.task_progress) if ctx.task_progress is not None else 0
    departments = len(ctx.department_progress) if ctx.department_progress is not None else 0
    rich_findings = sum(item.importance >= 60 for item in findings)

    if ctx.sample_size <= 1:
        return "tiny"
    if ctx.sample_size <= 5 or (goals <= 1 and departments <= 1 and tasks <= 3):
        return "narrow"

    score = 0
    score += 2 if ctx.sample_size >= 80 else 1 if ctx.sample_size >= 20 else 0
    score += 2 if goals >= 5 else 1 if goals >= 2 else 0
    score += 2 if tasks >= 12 else 1 if tasks >= 4 else 0
    score += 2 if departments >= 8 else 1 if departments >= 3 else 0
    score += 2 if periods >= 4 else 1 if periods >= 2 else 0
    score += 2 if rich_findings >= 10 else 1 if rich_findings >= 5 else 0
    if score >= 9:
        return "very_wide"
    if score >= 6:
        return "wide"
    return "standard"


def _opening_tag(signals: list[Signal], findings: list[AnalyticalFinding]) -> str:
    fc = {f.code for f in findings}
    sc = {s.code for s in signals}
    if fc & {"conflict_execution_up_coverage_down", "conflict_execution_down_coverage_up", "stable_aggregate_hidden_internal_movement"}:
        return "mixed"
    if sc & {"coverage_very_limited", "coverage_limited", "execution_unavailable_latest"}:
        return "cautious"
    if fc & {"trajectory_continuous_decline", "trajectory_net_decline", "trajectory_reversal_negative"} or sc & {"execution_low", "execution_very_low"}:
        return "negative"
    if fc & {"trajectory_continuous_growth", "trajectory_net_growth", "trajectory_recovery"}:
        return "positive"
    return "neutral"


def _select_scenario_mix(scenarios: list[Scenario], limit: int = 7) -> list[Scenario]:
    selected: list[Scenario] = []
    categories: set[str] = set()
    for scenario in scenarios:
        if len(selected) >= limit:
            break
        if not selected or scenario.category not in categories or scenario.category in {"conflict", "combined", "management", "uncertainty"}:
            selected.append(scenario)
            categories.add(scenario.category)
    return selected


def _finding_blocks(findings: list[AnalyticalFinding]) -> dict[str, list[AnalyticalFinding]]:
    grouped: dict[str, list[AnalyticalFinding]] = defaultdict(list)
    for finding in findings:
        # Current findings are routed by the explicit compatibility contract.
        # Topic mapping remains only as a defensive fallback for non-current callers.
        try:
            block = compatibility_for(finding.code).planner_block
        except KeyError:
            block = TOPIC_TO_BLOCK.get(finding.topic, "overall_state")
        grouped[block].append(finding)
    for items in grouped.values():
        items.sort(key=lambda item: (-item.importance, item.code))
    return grouped


def _has_child_evidence(findings: list[AnalyticalFinding], code: str) -> bool:
    item = next((finding for finding in findings if finding.code == code), None)
    return bool(item and list(item.facts.get("children") or []))


def _depth(importance: int, complexity: str) -> str:
    if importance >= 90:
        value = "critical"
    elif importance >= 70:
        value = "deep"
    elif importance >= 45:
        value = "standard"
    else:
        value = "brief"
    if complexity in {"wide", "very_wide"} and value == "brief":
        value = "standard"
    return value


def build_text_plan(
    ctx: AnalyticsContext,
    signals: list[Signal],
    scenarios: list[Scenario],
    findings: list[AnalyticalFinding] | None = None,
) -> TextPlan:
    """Build a content-driven plan. There is no paragraph-count quota.

    Complexity still controls paragraph depth, but blocks are admitted by factual
    availability and salience. A rich context is therefore allowed to be longer
    than a small context without first targeting a fixed paragraph interval.
    """
    findings = findings or []
    complexity = context_complexity_score(ctx, signals, findings)
    grouped = _finding_blocks(findings)
    mix = _select_scenario_mix(scenarios)
    primary = mix[0].code if mix else "default"

    available: set[str] = {"overall_state", "final_assessment"}
    if ctx.period_dynamics is not None and not ctx.period_dynamics.empty:
        available.add("dynamics")
    if ctx.goal_progress is not None and not ctx.goal_progress.empty and ctx.sample_size > 1:
        available.add("goals")
    if ctx.task_progress is not None and not ctx.task_progress.empty and ctx.sample_size > 1:
        available.add("tasks")
    if ctx.department_progress is not None and not ctx.department_progress.empty and ctx.sample_size > 1:
        available.add("departments")

    status_items = grouped.get("statuses", [])
    if ctx.status_counts is not None and not ctx.status_counts.empty and status_items:
        available.add("statuses")

    product_items = grouped.get("products", [])
    if ctx.product_progress is not None and not ctx.product_progress.empty and product_items:
        available.add("products")

    if ctx.metric("coverage") is not None or ctx.metric("coverage_latest") is not None or _safe_int(ctx.metric("no_data")) > 0:
        available.add("coverage")
    if grouped.get("mio_assessment"):
        available.add("mio_assessment")
    if grouped.get("management_attention") or _safe_int(ctx.metric("attention_count")) > 0:
        available.add("management_attention")

    if complexity == "tiny":
        available &= {"overall_state", "dynamics", "coverage", "management_attention", "final_assessment"}
    elif complexity == "narrow":
        if len(ctx.goal_progress) <= 1:
            available.discard("goals")
        # A single parent SSP is not a reason to discard a real child-task
        # drill-down.  Without child evidence the ordinary comparison pruning
        # remains intact.
        if len(ctx.department_progress) <= 1 and not _has_child_evidence(findings, "ssp_drilldown"):
            available.discard("departments")
        if len(ctx.task_progress) <= 1 and not _has_child_evidence(findings, "goal_drilldown"):
            available.discard("tasks")

    preference_score: dict[str, float] = defaultdict(float)
    aliases = {
        "execution": "overall_state", "data_quality": "coverage", "risks": "management_attention",
        "concentration": "management_attention", "goal_distribution": "goals",
    }
    for rank, scenario in enumerate(mix):
        weight = 2.0 - min(rank, 5) * 0.2
        for pos, block in enumerate(scenario.preferred_blocks):
            normal = aliases.get(block, block)
            if normal in available:
                preference_score[normal] += weight * (10 - min(pos, 9))

    order_index = {b: i for i, b in enumerate(BASE_BLOCK_ORDER)}
    ordered = sorted(
        available,
        key=lambda b: (order_index.get(b, 99) - min(preference_score.get(b, 0) / 30, 2.0), order_index.get(b, 99)),
    )
    ordered = [b for b in ordered if b not in {"overall_state", "final_assessment"}]
    ordered.insert(0, "overall_state")
    ordered.append("final_assessment")

    # Information-gain gate: supporting blocks without any material finding are
    # omitted. There is deliberately no hard paragraph-count truncation here.
    essentials = {"overall_state", "final_assessment", "dynamics", "coverage", "management_attention"}
    filtered: list[str] = []
    for block in ordered:
        items = grouped.get(block, [])
        material = max([item.importance for item in items] or [0])
        # ``product_structure`` is an existing production analytical block, not
        # merely a supporting registry entry.  When product facts are available
        # and the block survived context pruning, keep its real renderer path
        # even though the descriptive finding intentionally has importance 52.
        keep_existing_product_analysis = block == "products" and bool(items)
        if block in essentials or keep_existing_product_analysis or material >= 55 or preference_score.get(block, 0) > 0:
            filtered.append(block)
    ordered = filtered

    block_plans: list[BlockPlan] = []
    for block in ordered:
        items = grouped.get(block, [])
        importance = 100 if block in {"final_assessment", "management_attention"} else max([item.importance for item in items] or [50])
        depth = _depth(importance, complexity)
        if block in {"products", "statuses"} and complexity not in {"wide", "very_wide"}:
            depth = "brief"
        block_plans.append(BlockPlan(
            code=block,
            importance=importance,
            depth=depth,
            target_sentences=DEPTH_SENTENCES[depth],
            finding_codes=tuple(item.code for item in items),
        ))

    return TextPlan(
        opening=_opening_tag(signals, findings),
        blocks=tuple(ordered),
        primary_scenario=primary,
        scenario_mix=tuple(item.code for item in mix) or (primary,),
        complexity=complexity,
        block_plans=tuple(block_plans),
        target_paragraphs=None,
    )
