from __future__ import annotations

from collections import defaultdict

from .models import AnalyticsContext, Scenario, Signal, TextPlan


DEFAULT_BLOCKS = (
    "overall_state",
    "coverage",
    "dynamics",
    "goals",
    "departments",
    "statuses",
    "final_assessment",
)


def _opening_tag(codes: set[str]) -> str:
    if codes & {
        "coverage_very_limited", "coverage_limited", "lower_execution_limited_coverage",
        "upper_execution_limited_coverage",
    }:
        return "low_coverage"
    if codes & {
        "execution_very_low", "execution_low", "execution_down_broad_coverage",
        "execution_three_period_decline",
    }:
        return "negative"
    if codes & {
        "execution_very_high", "execution_high", "execution_up_coverage_up",
        "execution_three_period_growth",
    }:
        return "positive"
    return "neutral"


def _select_scenario_mix(scenarios: list[Scenario], limit: int = 4) -> list[Scenario]:
    """Choose several materially different active scenarios for composition.

    The first scenario remains the primary explanation anchor, but structure is
    merged from multiple categories so that, for example, dynamics + coverage +
    concentration can all shape the note instead of merely appending to a primary
    template.
    """
    if not scenarios:
        return []
    selected: list[Scenario] = []
    seen_categories: set[str] = set()
    for scenario in scenarios:
        if not selected:
            selected.append(scenario)
            seen_categories.add(scenario.category)
            continue
        if len(selected) >= limit:
            break
        # Prefer a new analytical dimension. Combined/conflict scenarios are
        # allowed alongside each other because they encode cross-dimension logic.
        if scenario.category not in seen_categories or scenario.category in {"combined", "conflict"}:
            selected.append(scenario)
            seen_categories.add(scenario.category)
    return selected


def _merge_scenario_blocks(mix: list[Scenario]) -> list[str]:
    if not mix:
        return list(DEFAULT_BLOCKS)

    weighted_position: dict[str, float] = defaultdict(float)
    total_weight: dict[str, float] = defaultdict(float)
    support: dict[str, float] = defaultdict(float)

    for scenario_index, scenario in enumerate(mix):
        base_weight = 1.0 + scenario.priority / 100.0 + scenario.importance / 100.0
        if scenario_index == 0:
            base_weight *= 1.20
        blocks = scenario.preferred_blocks or DEFAULT_BLOCKS
        for position, block in enumerate(blocks):
            if block == "scope":
                continue
            total_weight[block] += base_weight
            weighted_position[block] += base_weight * position
            support[block] += base_weight * (len(blocks) - position)

    ordered = sorted(
        total_weight,
        key=lambda block: (
            weighted_position[block] / total_weight[block],
            -support[block],
            block,
        ),
    )
    return ordered


def build_text_plan(ctx: AnalyticsContext, signals: list[Signal], scenarios: list[Scenario]) -> TextPlan:
    codes = {item.code for item in signals}
    fallback = Scenario(
        code="default", category="general", importance=20, priority=0, preferred_blocks=DEFAULT_BLOCKS
    )
    mix = _select_scenario_mix(scenarios)
    primary = mix[0] if mix else fallback
    ordered = _merge_scenario_blocks(mix) if mix else list(DEFAULT_BLOCKS)

    # Multi-year comparison is a high-value block and should survive length capping.
    if not ctx.yoy_comparison.empty and "year_over_year" not in ordered:
        insert_at = ordered.index("dynamics") + 1 if "dynamics" in ordered else min(2, len(ordered))
        ordered.insert(insert_at, "year_over_year")

    additions: list[tuple[bool, str]] = [
        (bool(codes & {"goal_problem_concentration_half_or_more", "department_problem_concentration_half_or_more"}), "concentration"),
        (bool(codes & {"problem_signals_large_share", "problem_signals_present", "execution_up_problems_up"}), "risks"),
        (not ctx.task_progress.empty and ctx.sample_size > 1, "tasks"),
        (not ctx.product_progress.empty and len(ctx.product_progress) > 1, "products"),
        (not ctx.status_counts.empty, "statuses"),
        (bool(codes & {"missing_share_large", "missing_share_material", "coverage_limited", "coverage_very_limited"}), "data_quality"),
    ]
    for condition, block in additions:
        if condition and block not in ordered:
            before_final = ordered.index("final_assessment") if "final_assessment" in ordered else len(ordered)
            ordered.insert(before_final, block)

    # Narrow selections suppress meaningless structural comparisons.
    if "sample_single" in codes:
        allowed = {"overall_state", "coverage", "data_quality", "statuses", "final_assessment"}
        ordered = [b for b in ordered if b in allowed]
        max_blocks = 3
    elif "sample_very_small" in codes:
        max_blocks = 3
    elif ctx.sample_size <= 15:
        max_blocks = 4
    else:
        max_blocks = 6 if len(set(ctx.filters.get("years", []))) <= 1 else 8

    ordered = ["goals" if b == "goal_distribution" else b for b in ordered if b != "scope"]
    if "overall_state" not in ordered:
        ordered.insert(0, "overall_state")
    if "final_assessment" not in ordered:
        ordered.append("final_assessment")

    unique: list[str] = []
    for block in ordered:
        if block not in unique:
            unique.append(block)

    # Preserve blocks that carry distinct active scenarios, not just the primary.
    force_keep = {"overall_state", "final_assessment"}
    if not ctx.yoy_comparison.empty:
        force_keep.add("year_over_year")
    if codes & {"execution_up_coverage_down", "execution_up_coverage_up", "execution_down_broad_coverage", "execution_down_coverage_up"}:
        force_keep.add("dynamics")
    if codes & {"execution_up_coverage_down", "execution_up_problems_up", "lower_execution_limited_coverage", "lower_execution_broad_coverage", "overall_up_but_component_down"}:
        force_keep.add("risks")
    if codes & {"coverage_limited", "coverage_very_limited", "execution_up_coverage_down"}:
        force_keep.add("coverage")
    if codes & {"goal_problem_concentration_half_or_more", "department_problem_concentration_half_or_more"}:
        force_keep.add("concentration")

    if len(unique) > max_blocks:
        selected = [b for b in unique if b in force_keep and b != "final_assessment"]
        for block in unique:
            if block == "final_assessment" or block in selected:
                continue
            if len(selected) >= max_blocks - 1:
                break
            selected.append(block)
        # Restore narrative order from the merged plan.
        unique = [b for b in unique if b in set(selected)] + ["final_assessment"]

    return TextPlan(
        opening=_opening_tag(codes),
        blocks=tuple(unique),
        primary_scenario=primary.code,
        scenario_mix=tuple(item.code for item in mix) or (primary.code,),
    )
