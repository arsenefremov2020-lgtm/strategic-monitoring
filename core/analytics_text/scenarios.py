from __future__ import annotations

from .models import AnalyticalFinding, Scenario, Signal
from .findings import SUPPORTED_FINDING_CODES


# Scenario rules deliberately describe content priorities, not complete texts.
# Names that reference execution/coverage bands are internal language-planning labels,
# not official monitoring grades or methodological classifications.
SCENARIOS: tuple[Scenario, ...] = (
    Scenario("lower_exec_limited_cov", "combined", 100, 100, ("lower_execution_limited_coverage",), (), ("overall_state","coverage","data_quality","goals","departments","final_assessment")),
    Scenario("lower_exec_broad_cov", "combined", 100, 99, ("lower_execution_broad_coverage",), (), ("overall_state","execution","dynamics","goals","departments","risks","final_assessment")),
    Scenario("exec_up_cov_down", "combined", 100, 98, ("execution_up_coverage_down",), (), ("dynamics","coverage","overall_state","goals","data_quality","final_assessment")),
    Scenario("exec_down_broad_cov", "combined", 100, 97, ("execution_down_broad_coverage",), (), ("dynamics","overall_state","goals","tasks","departments","risks","final_assessment")),
    Scenario("upper_exec_limited_cov", "combined", 95, 96, ("upper_execution_limited_coverage",), (), ("coverage","overall_state","data_quality","goals","final_assessment")),
    Scenario("exec_up_cov_up", "combined", 90, 95, ("execution_up_coverage_up",), (), ("dynamics","overall_state","coverage","goals","departments","final_assessment")),
    Scenario("exec_down_cov_up", "combined", 90, 94, ("execution_down_coverage_up",), (), ("dynamics","coverage","overall_state","goals","risks","final_assessment")),
    Scenario("exec_up_problems_up", "conflict", 95, 93, ("execution_up_problems_up",), (), ("dynamics","risks","goals","departments","final_assessment")),
    Scenario("overall_up_component_down", "conflict", 85, 92, ("overall_up_but_component_down",), (), ("dynamics","goals","departments","final_assessment")),
    Scenario("very_limited_coverage", "coverage", 100, 91, ("coverage_very_limited",), (), ("coverage","data_quality","scope","overall_state","final_assessment")),
    Scenario("limited_coverage", "coverage", 90, 90, ("coverage_limited",), (), ("coverage","data_quality","overall_state","goals","final_assessment")),
    Scenario("partial_coverage_band", "coverage", 75, 89, ("coverage_partial",), (), ("overall_state","coverage","data_quality","dynamics","final_assessment")),
    Scenario("large_missing_share", "coverage", 90, 88, ("missing_share_large",), (), ("data_quality","coverage","goals","departments","final_assessment")),
    Scenario("material_missing_share", "coverage", 70, 87, ("missing_share_material",), (), ("coverage","data_quality","goals","departments","final_assessment")),
    Scenario("very_low_execution_band", "execution", 95, 86, ("execution_very_low",), ("coverage_very_limited",), ("execution","overall_state","goals","tasks","departments","risks","final_assessment")),
    Scenario("lower_execution_band", "execution", 80, 85, ("execution_low",), ("coverage_limited","coverage_very_limited"), ("overall_state","execution","goals","tasks","risks","final_assessment")),
    Scenario("top_execution_band", "execution", 70, 84, ("execution_very_high",), (), ("overall_state","execution","coverage","goals","statuses","final_assessment")),
    Scenario("upper_execution_band", "execution", 60, 83, ("execution_high",), (), ("overall_state","execution","coverage","goals","final_assessment")),
    Scenario("middle_execution_band", "execution", 50, 82, ("execution_medium",), (), ("scope","overall_state","coverage","goals","statuses","final_assessment")),
    Scenario("strong_growth", "dynamics", 85, 81, ("execution_increased_strongly",), (), ("dynamics","overall_state","goals","departments","final_assessment")),
    Scenario("moderate_growth", "dynamics", 70, 80, ("execution_increased_moderately",), (), ("dynamics","overall_state","goals","final_assessment")),
    Scenario("slight_growth", "dynamics", 55, 79, ("execution_increased_slightly",), (), ("overall_state","dynamics","coverage","final_assessment")),
    Scenario("strong_decline", "dynamics", 90, 78, ("execution_decreased_strongly",), (), ("dynamics","goals","tasks","departments","risks","final_assessment")),
    Scenario("moderate_decline", "dynamics", 75, 77, ("execution_decreased_moderately",), (), ("dynamics","overall_state","goals","risks","final_assessment")),
    Scenario("slight_decline", "dynamics", 60, 76, ("execution_decreased_slightly",), (), ("overall_state","dynamics","goals","final_assessment")),
    Scenario("stable_dynamics", "dynamics", 45, 75, ("execution_stable",), (), ("scope","overall_state","coverage","goal_distribution","statuses","final_assessment")),
    Scenario("two_period_growth", "dynamics", 70, 74, ("execution_two_period_growth",), (), ("dynamics","overall_state","goals","final_assessment")),
    Scenario("three_period_growth", "dynamics", 80, 73, ("execution_three_period_growth",), (), ("dynamics","overall_state","goals","departments","final_assessment")),
    Scenario("two_period_decline", "dynamics", 85, 72, ("execution_two_period_decline",), (), ("dynamics","goals","tasks","final_assessment")),
    Scenario("three_period_decline", "dynamics", 95, 71, ("execution_three_period_decline",), (), ("dynamics","goals","tasks","departments","risks","final_assessment")),
    Scenario("positive_reversal", "dynamics", 80, 70, ("execution_reversal_positive",), (), ("dynamics","overall_state","coverage","final_assessment")),
    Scenario("negative_reversal", "dynamics", 90, 69, ("execution_reversal_negative",), (), ("dynamics","goals","risks","final_assessment")),
    Scenario("volatile", "dynamics", 70, 68, ("execution_high_volatility",), (), ("dynamics","coverage","goals","final_assessment")),
    Scenario("goal_gap_very_wide", "goals", 85, 67, ("goal_gap_very_wide",), (), ("goals","concentration","tasks","final_assessment")),
    Scenario("goal_gap_wide", "goals", 70, 66, ("goal_gap_wide",), (), ("goals","tasks","final_assessment")),
    Scenario("goal_gap_narrow", "goals", 45, 65, ("goal_gap_narrow",), (), ("goal_distribution","overall_state","statuses","final_assessment")),
    Scenario("goal_problem_concentration", "concentration", 90, 64, ("goal_problem_concentration_half_or_more",), (), ("concentration","goals","tasks","final_assessment")),
    Scenario("department_problem_concentration", "concentration", 90, 63, ("department_problem_concentration_half_or_more",), (), ("concentration","departments","final_assessment")),
    Scenario("problems_distributed", "concentration", 45, 62, ("goal_problems_distributed","department_problems_distributed"), (), ("overall_state","goals","departments","final_assessment")),
    Scenario("department_gap_wide", "departments", 70, 61, ("department_gap_wide",), (), ("departments","goals","final_assessment")),
    Scenario("department_gap_very_wide", "departments", 85, 60, ("department_gap_very_wide",), (), ("departments","concentration","goals","final_assessment")),
    Scenario("task_gap_wide", "tasks", 65, 59, ("task_gap_wide",), (), ("tasks","goals","final_assessment")),
    Scenario("task_gap_very_wide", "tasks", 80, 58, ("task_gap_very_wide",), (), ("tasks","goals","risks","final_assessment")),
    Scenario("status_not_done", "statuses", 80, 57, ("status_not_done_material_share",), (), ("statuses","risks","goals","final_assessment")),
    Scenario("status_not_submitted", "statuses", 85, 56, ("status_not_submitted_material_share",), (), ("statuses","data_quality","coverage","final_assessment")),
    Scenario("status_partial", "statuses", 55, 55, ("status_partial_material_share",), (), ("statuses","execution","goals","final_assessment")),
    Scenario("status_done", "statuses", 55, 54, ("status_done_material_share",), (), ("overall_state","statuses","goals","final_assessment")),
    Scenario("product_concentrated", "products", 55, 53, ("product_concentration_half_or_more",), (), ("products","overall_state","final_assessment")),
    Scenario("single_measure", "sample", 100, 52, ("sample_single",), (), ("scope","overall_state","coverage","final_assessment")),
    Scenario("very_small_sample", "sample", 85, 51, ("sample_very_small",), (), ("scope","overall_state","coverage","final_assessment")),
    Scenario("single_goal", "sample", 70, 50, ("single_goal",), (), ("scope","overall_state","coverage","tasks","final_assessment")),
    Scenario("single_department", "sample", 65, 49, ("single_department",), (), ("scope","overall_state","coverage","goals","final_assessment")),
    Scenario("yoy_execution_up", "yoy", 70, 48, ("yoy_execution_increased_moderately",), (), ("year_over_year","dynamics","overall_state","final_assessment")),
    Scenario("yoy_execution_down", "yoy", 80, 47, ("yoy_execution_decreased_moderately",), (), ("year_over_year","dynamics","goals","final_assessment")),
    Scenario("yoy_coverage_down", "yoy", 75, 46, ("yoy_coverage_decreased_moderately",), (), ("year_over_year","coverage","data_quality","final_assessment")),
    Scenario("yoy_problems_up", "yoy", 75, 45, ("yoy_problem_increased",), (), ("year_over_year","risks","goals","final_assessment")),
    Scenario("no_dynamics", "dynamics", 55, 44, ("dynamics_insufficient",), (), ("scope","overall_state","coverage","goal_distribution","final_assessment")),
)


def _finding_block(code: str) -> tuple[str, tuple[str, ...], str, int]:
    if code.startswith("trajectory_"):
        return "trajectory", ("dynamics", "goals", "departments", "final_assessment"), "dynamics", 82
    if code.startswith("goal_"):
        block = "tasks" if code == "goal_drilldown" else ("problem_concentration" if "problems_" in code or "missing_" in code else "goals")
        return "goal_analysis", (block, "goals", "tasks", "management_attention", "final_assessment"), "goals", 78
    if code.startswith("task_"):
        return "task_analysis", ("tasks", "goals", "management_attention", "final_assessment"), "tasks", 68
    if code.startswith("department_") or code.startswith("ssp_"):
        return "ssp_analysis", ("departments", "problem_concentration", "management_attention", "final_assessment"), "departments", 84
    if code == "risk_structure" or code.startswith("persistent_"):
        return "risk", ("problem_concentration", "departments", "management_attention", "final_assessment"), "risk", 82
    if code.startswith("conflict_") or code.startswith("stable_aggregate"):
        return "conflict", ("dynamics", "coverage", "goals", "departments", "problem_concentration", "final_assessment"), "conflict", 96
    if code.startswith("yoy_"):
        return "yoy", ("year_over_year", "dynamics", "coverage", "final_assessment"), "yoy", 75
    if code == "status_structure":
        return "statuses", ("statuses", "overall_state", "final_assessment"), "statuses", 55
    if code == "product_structure":
        return "products", ("products", "overall_state", "final_assessment"), "products", 45
    if code == "management_priorities":
        return "management", ("management_attention", "problem_concentration", "final_assessment"), "management", 100
    if code == "overall_state":
        return "general", ("overall_state", "coverage", "dynamics", "final_assessment"), "general", 88
    return "general", ("overall_state", "final_assessment"), "general", 50


def _build_finding_scenarios() -> tuple[Scenario, ...]:
    result: list[Scenario] = []
    for idx, code in enumerate(sorted(SUPPORTED_FINDING_CODES)):
        if code in {"scope_profile", "trajectory_unavailable", "trajectory_single_period"}:
            continue
        category, blocks, _dimension, importance = _finding_block(code)
        result.append(Scenario(
            code=f"finding_{code}", category=category, importance=importance,
            priority=max(20, 94 - (idx % 25)), preferred_blocks=blocks, required_findings=(code,),
        ))
    return tuple(result)


FINDING_SCENARIOS = _build_finding_scenarios()
SCENARIOS = SCENARIOS + FINDING_SCENARIOS


def activate_scenarios(signals: list[Signal], findings: list[AnalyticalFinding] | tuple[AnalyticalFinding, ...] = ()) -> list[Scenario]:
    signal_codes = {item.code for item in signals}
    finding_codes = {item.code for item in findings}
    active: list[Scenario] = []
    for scenario in SCENARIOS:
        if not all(code in signal_codes for code in scenario.required_signals):
            continue
        if any(code in signal_codes for code in scenario.excluded_signals):
            continue
        if not all(code in finding_codes for code in scenario.required_findings):
            continue
        if any(code in finding_codes for code in scenario.excluded_findings):
            continue
        active.append(scenario)
    active.sort(key=lambda item: (-item.priority, -item.importance, item.code))
    return active
