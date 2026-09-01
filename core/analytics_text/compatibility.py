from __future__ import annotations

"""Explicit compatibility contract between current findings and production renderers.

The current Analytics engine deliberately keeps the mature production renderer set,
but every finding produced by ``findings_current`` must have an explicit disposition.
There is no implicit/silent fallback: a finding is either renderer-backed, explicitly
supporting-only, or internal/ranking-only.
"""

from dataclasses import dataclass
from typing import Iterable

from .models import AnalyticsContext, AnalyticalFinding

RENDERED = "rendered"
SUPPORTING_ONLY = "supporting-only"
INTERNAL_ONLY = "internal/ranking-only"
_VALID_DISPOSITIONS = frozenset({RENDERED, SUPPORTING_ONLY, INTERNAL_ONLY})


@dataclass(frozen=True)
class FindingCompatibility:
    code: str
    topic: str
    planner_block: str
    renderer: str
    disposition: str = RENDERED
    note: str = ""


@dataclass(frozen=True)
class FindingDisposition:
    code: str
    topic: str
    planner_block: str
    renderer: str
    disposition: str
    reason: str = ""


_registry: dict[str, FindingCompatibility] = {}


def _register(
    code: str,
    topic: str,
    planner_block: str,
    renderer: str,
    disposition: str = RENDERED,
    note: str = "",
) -> None:
    if disposition not in _VALID_DISPOSITIONS:
        raise ValueError(f"Unknown finding disposition: {disposition}")
    if code in _registry:
        raise ValueError(f"Duplicate finding compatibility code: {code}")
    _registry[code] = FindingCompatibility(
        code=code,
        topic=topic,
        planner_block=planner_block,
        renderer=renderer,
        disposition=disposition,
        note=note,
    )


# Headline / overall state.
_register("overall_state", "general", "overall_state", "composer_overlay._overall_current_block")
_register("execution_goal_divergence", "general", "overall_state", "composer_overlay._overall_current_block")
_register("execution_goal_alignment", "general", "overall_state", "composer_overlay._overall_current_block")

# Trajectory. ``trajectory_unavailable`` is an evidence-state flag; when there is
# no evaluated trajectory there is no dynamics block to render, so its supporting
# disposition is deliberate rather than an accidental renderer miss.
_register(
    "trajectory_unavailable", "dynamics", "dynamics", "planner/evidence gate",
    SUPPORTING_ONLY, "No evaluated trajectory exists; no directional claim is rendered.",
)
for _code in (
    "trajectory_single_period",
    "trajectory_continuous_growth",
    "trajectory_continuous_decline",
    "trajectory_recovery",
    "trajectory_reversal_negative",
    "trajectory_plateau",
    "trajectory_net_growth",
    "trajectory_net_decline",
    "trajectory_mixed",
    "trajectory_late_acceleration",
    "trajectory_growth_slowing",
    "trajectory_decline_accelerating",
):
    _register(_code, "dynamics", "dynamics", "composer_overlay._dynamics_current_block")

# Cross-sectional distribution / movement / latest-attention / missing data.
for _kind, _block in (("goal", "goals"), ("task", "tasks"), ("department", "departments")):
    _register(
        f"{_kind}_single_entity", _kind, _block, "planner narrow-context gate",
        SUPPORTING_ONLY, "Single-entity state suppresses meaningless within-dimension comparison.",
    )
    _register(f"{_kind}_distribution", _kind, _block, "composer_overlay._distribution_current_block")
    for _suffix in ("change_polarised", "change_positive", "change_negative", "change_stable"):
        _register(f"{_kind}_{_suffix}", _kind, _block, "composer_overlay._distribution_current_block")

    _register(
        f"{_kind}_attention_none", "attention", "management_attention", "current attention headline",
        SUPPORTING_ONLY, "Zero-count dimension is supporting evidence for the global current-attention state.",
    )
    for _suffix in ("attention_concentrated", "attention_localised", "attention_distributed"):
        _register(f"{_kind}_{_suffix}", "attention", "management_attention", "composer_overlay._management_priorities_block")

    _missing_topic = _kind if _kind == "task" else "missing"
    _missing_block = "tasks" if _kind == "task" else "coverage"
    # ``_concentration`` returns the raw ``missing`` topic for the zero-total
    # evidence state before the task-specific nonzero remap is applied.
    _none_topic = "missing"
    _none_block = "coverage"
    _register(
        f"{_kind}_missing_none", _none_topic, _none_block, "coverage/detail evidence gate",
        SUPPORTING_ONLY, "Zero missing submissions need no separate concentration sentence.",
    )
    for _suffix in ("missing_concentrated", "missing_localised", "missing_distributed"):
        _register(f"{_kind}_{_suffix}", _missing_topic, _missing_block, "production coverage/distribution renderer")

# Hierarchical and structural findings.
_register(
    "goal_drilldown", "task", "tasks", "composer_overlay._distribution_current_block",
    RENDERED, "Renderer-backed only when factual children exist; otherwise resolved supporting-only at runtime.",
)
_register(
    "ssp_drilldown", "department", "departments", "composer_overlay._distribution_current_block",
    RENDERED, "Renderer-backed only when factual children exist; otherwise resolved supporting-only at runtime.",
)
_register(
    "ssp_portfolio_impact", "departments", "departments", "composer_overlay._distribution_current_block",
    RENDERED, "For a one-SSP narrow selection this becomes supporting-only because there is no portfolio comparison.",
)
_register("risk_structure", "risk", "management_attention", "composer_overlay._management_priorities_block")
_register("status_structure", "statuses", "statuses", "composer_overlay._statuses_current_block")
_register("missing_persistence", "missing", "coverage", "composer_overlay._coverage_current_block")
_register(
    "product_structure", "products", "products", "composer_overlay._products_current_block",
    RENDERED, "Existing product analysis has a production renderer and is rendered whenever the product block is planned.",
)

# Conflicts are consumed in final synthesis; mapping them to the actual consumer
# keeps planner/debug provenance aligned rather than pretending the headline used them.
for _code in (
    "conflict_execution_up_coverage_down",
    "conflict_execution_down_coverage_up",
    "stable_aggregate_hidden_internal_movement",
):
    _register(_code, "conflict", "final_assessment", "production composer._final_block")

# MіO contract preserved exactly; only compatibility routing is declared here.
for _code in (
    "mio_integral_profile",
    "mio_execution_result_divergence",
    "mio_task_indicator_profile",
    "mio_task_execution_result_divergence",
    "mio_measure_profile",
    "mio_financing_profile",
):
    _register(_code, "mio", "mio_assessment", "composer_overlay._mio_current_block")

_register("management_priorities", "management_attention", "management_attention", "composer_overlay._management_priorities_block")


FINDING_COMPATIBILITY: dict[str, FindingCompatibility] = dict(_registry)
SUPPORTED_FINDING_CODES = frozenset(FINDING_COMPATIBILITY)


def compatibility_for(code: str) -> FindingCompatibility:
    try:
        return FINDING_COMPATIBILITY[code]
    except KeyError as exc:
        raise KeyError(f"Undefined Analytics finding compatibility: {code}") from exc


def resolve_finding_disposition(
    ctx: AnalyticsContext,
    finding: AnalyticalFinding,
    *,
    planned_blocks: set[str] | frozenset[str] | None = None,
    complexity: str | None = None,
) -> FindingDisposition:
    """Resolve the explicit runtime disposition for one current finding.

    Runtime downgrades are intentionally narrow and evidence-driven. They never
    convert absence of child evidence into a claim about concentration/distribution.
    """
    spec = compatibility_for(finding.code)
    disposition = spec.disposition
    reason = spec.note

    if finding.code in {"goal_drilldown", "ssp_drilldown"}:
        children = list(finding.facts.get("children") or [])
        if not children:
            disposition = SUPPORTING_ONLY
            reason = "Child breakdown was not factually prepared; parent-only evidence cannot support a child inference."
        elif ctx.sample_size <= 1:
            disposition = SUPPORTING_ONLY
            reason = "A one-measure context has no meaningful child portfolio comparison; child facts remain supporting evidence only."

    if finding.code == "ssp_portfolio_impact":
        department_count = len(ctx.department_progress) if ctx.department_progress is not None else 0
        if department_count <= 1:
            disposition = SUPPORTING_ONLY
            reason = "One-SSP selection has no meaningful cross-SSP portfolio comparison; keep the fact as supporting context."

    # Planner-aware release invariant: a finding cannot remain renderer-backed if
    # its declared consumer block was deliberately pruned for the current context.
    # This is a documented runtime disposition, never a silent renderer miss.
    if disposition == RENDERED and planned_blocks is not None and spec.planner_block not in planned_blocks:
        disposition = SUPPORTING_ONLY
        ctx_name = complexity or "current"
        reason = (
            f"Planner omitted block '{spec.planner_block}' under {ctx_name} context; "
            "the finding is retained as supporting evidence and is not passed to a legacy comparative renderer."
        )

    return FindingDisposition(
        code=finding.code,
        topic=finding.topic,
        planner_block=spec.planner_block,
        renderer=spec.renderer,
        disposition=disposition,
        reason=reason,
    )


def resolve_findings(
    ctx: AnalyticsContext,
    findings: Iterable[AnalyticalFinding],
    *,
    planned_blocks: set[str] | frozenset[str] | None = None,
    complexity: str | None = None,
) -> dict[str, FindingDisposition]:
    return {
        finding.code: resolve_finding_disposition(
            ctx, finding, planned_blocks=planned_blocks, complexity=complexity
        )
        for finding in findings
    }


def rendered_finding_codes(ctx: AnalyticsContext, findings: Iterable[AnalyticalFinding]) -> set[str]:
    return {
        code for code, item in resolve_findings(ctx, findings).items()
        if item.disposition == RENDERED
    }


def compatibility_rows() -> list[dict[str, str]]:
    """Static registry rows for implementation notes/tests."""
    return [
        {
            "code": spec.code,
            "topic": spec.topic,
            "planner_block": spec.planner_block,
            "renderer": spec.renderer,
            "disposition": spec.disposition,
            "note": spec.note,
        }
        for spec in sorted(FINDING_COMPATIBILITY.values(), key=lambda item: item.code)
    ]
