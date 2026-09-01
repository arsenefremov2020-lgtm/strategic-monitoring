from __future__ import annotations

"""Deterministic signal detection over prepared Analytics facts."""

from typing import Any

from .models import AnalyticsContext, Signal


def _num(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _s(code: str, severity: str, importance: int, dimension: str, **values: Any) -> Signal:
    return Signal(code=code, severity=severity, importance=importance, dimension=dimension, values=values)


def detect_signals(ctx: AnalyticsContext) -> list[Signal]:
    out: list[Signal] = []
    execution = _num(ctx.factual_value("page.completion"))
    coverage_latest = _num(ctx.factual_value("page.coverage_latest"))
    coverage_average = _num(ctx.factual_value("page.coverage"))
    missing_share = _num(ctx.factual_value("overall.missing_latest_share_pct"))
    attention_share = _num(ctx.factual_value("overall.attention_latest_share_pct"))
    attention_count = int(ctx.factual_value("page.attention_count", 0) or 0)
    attention_type = str(ctx.metrics.get("attention_type") or "unavailable")

    if execution is None:
        out.append(_s("execution_unavailable_latest", "warning", 100, "execution"))
    elif execution < 40:
        out.append(_s("execution_very_low", "critical", 95, "execution", value=execution))
    elif execution < 65:
        out.append(_s("execution_low", "high", 85, "execution", value=execution))
    elif execution < 85:
        out.append(_s("execution_medium", "medium", 60, "execution", value=execution))
    elif execution < 97:
        out.append(_s("execution_high", "positive", 55, "execution", value=execution))
    else:
        out.append(_s("execution_very_high", "positive", 65, "execution", value=execution))

    if coverage_latest is None:
        out.append(_s("coverage_unavailable_latest", "warning", 95, "coverage"))
    elif coverage_latest < 50:
        out.append(_s("coverage_very_limited", "critical", 100, "coverage", value=coverage_latest))
    elif coverage_latest < 75:
        out.append(_s("coverage_limited", "high", 90, "coverage", value=coverage_latest))
    elif coverage_latest < 90:
        out.append(_s("coverage_partial", "medium", 70, "coverage", value=coverage_latest))
    else:
        out.append(_s("coverage_broad", "positive", 45, "coverage", value=coverage_latest))

    if coverage_average is not None and coverage_latest is not None:
        gap = coverage_latest - coverage_average
        if gap >= 5:
            out.append(_s("coverage_latest_above_range_mean", "positive", 62, "coverage", gap=gap))
        elif gap <= -5:
            out.append(_s("coverage_latest_below_range_mean", "warning", 76, "coverage", gap=gap))

    if missing_share is not None:
        if missing_share >= 25:
            out.append(_s("missing_share_large", "critical", 94, "data_completeness", value=missing_share))
        elif missing_share >= 10:
            out.append(_s("missing_share_material", "high", 82, "data_completeness", value=missing_share))
        elif missing_share > 0:
            out.append(_s("missing_share_small", "medium", 45, "data_completeness", value=missing_share))
        else:
            out.append(_s("no_missing_latest", "positive", 35, "data_completeness"))

    if attention_count > 0:
        out.append(_s(f"attention_{attention_type}_present", "high", 94, "management_attention", count=attention_count, share=attention_share))
    else:
        out.append(_s(f"attention_{attention_type}_none", "positive", 42, "management_attention", count=0))

    trajectory = dict(ctx.factual_structure("trajectory", {}) or {})
    delta = _num(trajectory.get("cumulative_delta"))
    if delta is None:
        out.append(_s("dynamics_insufficient", "neutral", 35, "dynamics"))
    elif delta >= 10:
        out.append(_s("execution_increased_strongly", "positive", 88, "dynamics", delta=delta))
    elif delta >= 3:
        out.append(_s("execution_increased_moderately", "positive", 72, "dynamics", delta=delta))
    elif delta <= -10:
        out.append(_s("execution_decreased_strongly", "critical", 96, "dynamics", delta=delta))
    elif delta <= -3:
        out.append(_s("execution_decreased_moderately", "high", 84, "dynamics", delta=delta))
    else:
        out.append(_s("execution_stable", "neutral", 48, "dynamics", delta=delta))

    cov_delta = _num(trajectory.get("coverage_cumulative_delta"))
    if delta is not None and cov_delta is not None:
        if delta > 3 and cov_delta < -3:
            out.append(_s("execution_up_coverage_down", "warning", 96, "conflict", execution_delta=delta, coverage_delta=cov_delta))
        elif delta < -3 and cov_delta > 3:
            out.append(_s("execution_down_coverage_up", "warning", 95, "conflict", execution_delta=delta, coverage_delta=cov_delta))

    for kind in ("goal", "task", "department"):
        dist = dict(ctx.factual_structure(f"{kind}.distribution", {}) or {})
        gap = _num(dist.get("gap"))
        if gap is not None:
            if gap >= 30:
                out.append(_s(f"{kind}_gap_very_wide", "high", 82, kind, gap=gap))
            elif gap >= 15:
                out.append(_s(f"{kind}_gap_wide", "medium", 68, kind, gap=gap))
        attention = dict(ctx.factual_structure(f"{kind}.attention", {}) or {})
        top_share = _num(attention.get("top_share"))
        if attention.get("concentration_class") == "concentrated" and top_share is not None:
            out.append(_s(f"{kind}_attention_concentrated", "high", 86, kind, share=top_share))
        missing = dict(ctx.factual_structure(f"{kind}.missing", {}) or {})
        missing_top = _num(missing.get("top_share"))
        if missing.get("concentration_class") == "concentrated" and missing_top is not None:
            out.append(_s(f"{kind}_missing_concentrated", "high", 80, kind, share=missing_top))

    if ctx.sample_size <= 1:
        out.append(_s("sample_single", "neutral", 90, "sample", size=ctx.sample_size))
    elif ctx.sample_size <= 5:
        out.append(_s("sample_very_small", "neutral", 70, "sample", size=ctx.sample_size))

    # Deterministic de-duplication by signal code.
    strongest: dict[str, Signal] = {}
    for item in out:
        if item.code not in strongest or item.importance > strongest[item.code].importance:
            strongest[item.code] = item
    return sorted(strongest.values(), key=lambda item: (-item.importance, item.dimension, item.code))


SUPPORTED_SIGNAL_CODES = frozenset({
    "execution_unavailable_latest", "execution_very_low", "execution_low", "execution_medium", "execution_high", "execution_very_high",
    "coverage_unavailable_latest", "coverage_very_limited", "coverage_limited", "coverage_partial", "coverage_broad",
    "coverage_latest_above_range_mean", "coverage_latest_below_range_mean",
    "missing_share_large", "missing_share_material", "missing_share_small", "no_missing_latest",
    "execution_increased_strongly", "execution_increased_moderately", "execution_decreased_strongly", "execution_decreased_moderately", "execution_stable",
    "execution_up_coverage_down", "execution_down_coverage_up", "dynamics_insufficient",
    "sample_single", "sample_very_small",
    "management_attention_present", "management_attention_none",
} | {
    f"attention_{kind}_{state}"
    for kind in ("preliminary_attention", "forecast_risk", "final_nonachievement", "unavailable")
    for state in ("present", "none")
} | {
    f"{kind}_{suffix}"
    for kind in ("goal", "task", "department")
    for suffix in ("gap_very_wide", "gap_wide", "attention_concentrated", "missing_concentrated")
})
