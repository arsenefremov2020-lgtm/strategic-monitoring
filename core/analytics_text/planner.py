from __future__ import annotations

from collections import defaultdict

from .models import AnalyticsContext, AnalyticalFinding, BlockPlan, Scenario, Signal, TextPlan


BASE_BLOCK_ORDER = (
    "scope", "overall_state", "dynamics", "year_over_year", "coverage", "goals", "tasks",
    "departments", "statuses", "products", "problem_concentration", "management_attention", "final_assessment",
)

TOPIC_TO_BLOCK = {
    "scope": "scope", "general": "overall_state", "dynamics": "dynamics", "yoy": "year_over_year",
    "coverage": "coverage", "missing": "coverage", "goal": "goals", "task": "tasks",
    "department": "departments", "departments": "departments", "statuses": "statuses", "products": "products",
    "problems": "problem_concentration", "risk": "problem_concentration", "conflict": "problem_concentration", "management_attention": "management_attention",
}

DEPTH_SENTENCES = {
    "brief": (2, 3), "standard": (3, 4), "deep": (4, 6), "critical": (5, 7),
}


def context_complexity_score(ctx: AnalyticsContext, signals: list[Signal], findings: list[AnalyticalFinding]) -> str:
    periods = len(ctx.period_dynamics) if ctx.period_dynamics is not None else 0
    goals = len(ctx.goal_progress) if ctx.goal_progress is not None else 0
    tasks = len(ctx.task_progress) if ctx.task_progress is not None else 0
    departments = len(ctx.department_progress) if ctx.department_progress is not None else 0
    years = len(set(ctx.filters.get("years", []) or []))
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
    score += 2 if years >= 2 else 0
    score += 1 if ctx.yoy_comparison is not None and not ctx.yoy_comparison.empty else 0
    score += 2 if rich_findings >= 10 else 1 if rich_findings >= 5 else 0
    if score >= 11:
        return "very_wide"
    if score >= 7:
        return "wide"
    return "standard"


def _targets(complexity: str) -> tuple[int, int]:
    return {
        "tiny": (3, 4), "narrow": (4, 6), "standard": (6, 8), "wide": (8, 11), "very_wide": (9, 13),
    }[complexity]


def _opening_tag(signals: list[Signal], findings: list[AnalyticalFinding]) -> str:
    fc = {f.code for f in findings}
    sc = {s.code for s in signals}
    if fc & {"conflict_execution_up_coverage_down", "stable_aggregate_hidden_internal_movement"}:
        return "mixed"
    if sc & {"coverage_very_limited", "coverage_limited"}:
        return "cautious"
    if fc & {"trajectory_continuous_decline", "trajectory_net_decline"} or sc & {"execution_low", "execution_very_low"}:
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
        if not selected or scenario.category not in categories or scenario.category in {"conflict", "combined", "management"}:
            selected.append(scenario)
            categories.add(scenario.category)
    return selected


def _finding_blocks(findings: list[AnalyticalFinding]) -> dict[str, list[AnalyticalFinding]]:
    grouped: dict[str, list[AnalyticalFinding]] = defaultdict(list)
    for finding in findings:
        block = TOPIC_TO_BLOCK.get(finding.topic, "overall_state")
        grouped[block].append(finding)
    for items in grouped.values():
        items.sort(key=lambda item: (-item.importance, item.code))
    return grouped


def _depth(importance: int, complexity: str) -> str:
    if importance >= 90:
        value = "critical"
    elif importance >= 70:
        value = "deep"
    elif importance >= 45:
        value = "standard"
    else:
        value = "brief"
    # Wide contexts should use full paragraphs for central blocks.
    if complexity in {"wide", "very_wide"} and value == "brief":
        value = "standard"
    return value


def build_text_plan(
    ctx: AnalyticsContext,
    signals: list[Signal],
    scenarios: list[Scenario],
    findings: list[AnalyticalFinding] | None = None,
) -> TextPlan:
    findings = findings or []
    complexity = context_complexity_score(ctx, signals, findings)
    grouped = _finding_blocks(findings)
    mix = _select_scenario_mix(scenarios)
    primary = mix[0].code if mix else "default"

    available: set[str] = {"scope", "overall_state", "final_assessment"}
    if ctx.period_dynamics is not None and not ctx.period_dynamics.empty:
        available.add("dynamics")
    if ctx.yoy_comparison is not None and not ctx.yoy_comparison.empty:
        available.add("year_over_year")
    if ctx.goal_progress is not None and not ctx.goal_progress.empty and ctx.sample_size > 1:
        available.add("goals")
    if ctx.task_progress is not None and not ctx.task_progress.empty and ctx.sample_size > 1:
        available.add("tasks")
    if ctx.department_progress is not None and not ctx.department_progress.empty and ctx.sample_size > 1:
        available.add("departments")
    if ctx.status_counts is not None and not ctx.status_counts.empty:
        available.add("statuses")
    if ctx.product_progress is not None and len(ctx.product_progress) > 1:
        available.add("products")
    if ctx.metric("coverage") is not None or int(ctx.metric("no_data") or 0) > 0:
        available.add("coverage")
    if grouped.get("problem_concentration") or any(f.topic == "problems" for f in findings):
        available.add("problem_concentration")
    if grouped.get("management_attention"):
        available.add("management_attention")

    # Tiny selections must not manufacture portfolio/distribution analysis.
    if complexity == "tiny":
        available &= {"scope", "overall_state", "dynamics", "final_assessment"}
    elif complexity == "narrow":
        # Keep only genuinely available selected-entity detail, not every taxonomy block.
        if len(ctx.goal_progress) <= 1:
            available.discard("goals")
        if len(ctx.department_progress) <= 1:
            available.discard("departments")

    # Scenario preferences can reorder but never add unavailable content.
    preference_score: dict[str, float] = defaultdict(float)
    for rank, scenario in enumerate(mix):
        weight = 2.0 - min(rank, 5) * 0.2
        for pos, block in enumerate(scenario.preferred_blocks):
            normal = {"execution": "overall_state", "data_quality": "coverage", "risks": "problem_concentration", "concentration": "problem_concentration", "goal_distribution": "goals"}.get(block, block)
            if normal in available:
                preference_score[normal] += weight * (10 - min(pos, 9))

    # Preserve coherent analytical flow while giving high-priority scenario blocks a modest promotion.
    order_index = {b: i for i, b in enumerate(BASE_BLOCK_ORDER)}
    ordered = sorted(available, key=lambda b: (order_index.get(b, 99) - min(preference_score.get(b, 0) / 30, 2.0), order_index.get(b, 99)))
    # Always begin with scope and finish with synthesis.
    ordered = [b for b in ordered if b not in {"scope", "overall_state", "final_assessment"}]
    ordered.insert(0, "overall_state")
    ordered.insert(0, "scope")
    ordered.append("final_assessment")

    target_min, target_max = _targets(complexity)
    # For narrow/tiny notes, cap paragraphs; for rich contexts, include all useful blocks up to target max.
    if len(ordered) > target_max:
        mandatory = {"scope", "overall_state", "final_assessment"}
        if "dynamics" in available: mandatory.add("dynamics")
        if "coverage" in available: mandatory.add("coverage")
        if "goals" in available: mandatory.add("goals")
        if "departments" in available and complexity in {"wide", "very_wide"}: mandatory.add("departments")
        if "management_attention" in available: mandatory.add("management_attention")
        scored = sorted(
            [b for b in ordered if b not in mandatory],
            key=lambda b: -max([f.importance for f in grouped.get(b, [])] or [preference_score.get(b, 0)]),
        )
        keep = set(mandatory)
        for b in scored:
            if len(keep) >= target_max: break
            keep.add(b)
        ordered = [b for b in ordered if b in keep]

    block_plans: list[BlockPlan] = []
    for block in ordered:
        items = grouped.get(block, [])
        if block == "scope": importance = 55
        elif block == "final_assessment": importance = 100
        elif block == "management_attention": importance = 100
        else: importance = max([item.importance for item in items] or [50])
        depth = _depth(importance, complexity)
        if block == "scope" and complexity in {"tiny", "narrow"}: depth = "brief"
        if block in {"products", "statuses"} and complexity not in {"wide", "very_wide"}: depth = "brief"
        target_sentences = DEPTH_SENTENCES[depth]
        block_plans.append(BlockPlan(
            code=block, importance=importance, depth=depth, target_sentences=target_sentences,
            finding_codes=tuple(item.code for item in items),
        ))

    return TextPlan(
        opening=_opening_tag(signals, findings), blocks=tuple(ordered), primary_scenario=primary,
        scenario_mix=tuple(item.code for item in mix) or (primary,), complexity=complexity,
        block_plans=tuple(block_plans), target_paragraphs=(target_min, target_max),
    )
