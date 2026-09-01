from __future__ import annotations

from .models import AnalyticalFinding, Scenario, Signal
from .findings_current import SUPPORTED_FINDING_CODES


# Scenario rules set content priority only.  Narrative length is selected from
# salient findings; scenarios do not impose paragraph quotas.
SCENARIOS: tuple[Scenario, ...] = (
    Scenario("latest_execution_unavailable", "uncertainty", 100, 100, ("execution_unavailable_latest",), (), ("overall_state", "coverage", "management_attention")),
    Scenario("very_limited_coverage", "coverage", 100, 99, ("coverage_very_limited",), (), ("coverage", "overall_state", "management_attention")),
    Scenario("limited_coverage", "coverage", 90, 98, ("coverage_limited",), (), ("coverage", "overall_state", "management_attention")),
    Scenario("execution_up_coverage_down", "conflict", 100, 97, ("execution_up_coverage_down",), (), ("dynamics", "coverage", "overall_state", "management_attention")),
    Scenario("execution_down_coverage_up", "conflict", 100, 96, ("execution_down_coverage_up",), (), ("dynamics", "coverage", "overall_state", "management_attention")),
    Scenario("strong_decline", "dynamics", 95, 95, ("execution_decreased_strongly",), (), ("dynamics", "goals", "tasks", "management_attention")),
    Scenario("moderate_decline", "dynamics", 85, 94, ("execution_decreased_moderately",), (), ("dynamics", "goals", "management_attention")),
    Scenario("strong_growth", "dynamics", 82, 93, ("execution_increased_strongly",), (), ("dynamics", "overall_state", "goals")),
    Scenario("large_missing", "data_completeness", 92, 92, ("missing_share_large",), (), ("coverage", "departments", "management_attention")),
    Scenario("material_missing", "data_completeness", 82, 91, ("missing_share_material",), (), ("coverage", "departments", "management_attention")),
    Scenario("very_low_execution", "execution", 94, 90, ("execution_very_low",), (), ("overall_state", "goals", "tasks", "management_attention")),
    Scenario("low_execution", "execution", 82, 89, ("execution_low",), (), ("overall_state", "goals", "management_attention")),
    Scenario("small_sample", "sample", 75, 70, ("sample_very_small",), (), ("overall_state", "coverage")),
    Scenario("single_measure", "sample", 90, 71, ("sample_single",), (), ("overall_state", "coverage")),
)


def _finding_blocks(code: str) -> tuple[str, ...]:
    if code.startswith("trajectory_") or code.startswith("conflict_") or code.startswith("stable_aggregate"):
        return ("dynamics", "overall_state")
    if code.startswith("goal_"):
        return ("goals", "tasks", "management_attention")
    if code.startswith("task_"):
        return ("tasks", "management_attention")
    if code.startswith("department_") or code.startswith("ssp_"):
        return ("departments", "management_attention")
    if code.startswith("mio_"):
        return ("mio_assessment",)
    if code.startswith("missing_"):
        return ("coverage", "management_attention")
    if code == "risk_structure":
        return ("management_attention",)
    if code == "product_structure":
        return ("products",)
    if code == "management_priorities":
        return ("management_attention",)
    return ("overall_state",)


def _finding_scenarios() -> tuple[Scenario, ...]:
    return tuple(
        Scenario(
            code=f"finding_{code}", category="finding", importance=70,
            priority=60, preferred_blocks=_finding_blocks(code), required_findings=(code,),
        )
        for code in sorted(SUPPORTED_FINDING_CODES)
        if code not in {"overall_state", "trajectory_unavailable", "trajectory_single_period"}
    )


SCENARIOS = SCENARIOS + _finding_scenarios()


def activate_scenarios(signals: list[Signal], findings: list[AnalyticalFinding] | tuple[AnalyticalFinding, ...] = ()) -> list[Scenario]:
    signal_codes = {item.code for item in signals}; finding_codes = {item.code for item in findings}; active = []
    for scenario in SCENARIOS:
        if not all(code in signal_codes for code in scenario.required_signals): continue
        if any(code in signal_codes for code in scenario.excluded_signals): continue
        if not all(code in finding_codes for code in scenario.required_findings): continue
        if any(code in finding_codes for code in scenario.excluded_findings): continue
        active.append(scenario)
    return sorted(active, key=lambda item: (-item.priority, -item.importance, item.code))
