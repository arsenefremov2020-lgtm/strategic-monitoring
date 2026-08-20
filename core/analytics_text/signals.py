from __future__ import annotations

from typing import Any

import pandas as pd

from .config import (
    CONCENTRATION_LANGUAGE_BANDS,
    COVERAGE_LANGUAGE_BANDS,
    DELTA_LANGUAGE_BANDS,
    EXECUTION_LANGUAGE_BANDS,
    GAP_LANGUAGE_BANDS,
    SAMPLE_THRESHOLDS,
    MISSING_SHARE_LANGUAGE_BANDS,
    PROBLEM_SHARE_LANGUAGE_BANDS,
    STATUS_SHARE_LANGUAGE_BANDS,
    VOLATILITY_LANGUAGE_BAND,
)
from .language import is_number
from .models import AnalyticsContext, Signal


def _signal(code: str, severity: str, importance: int, dimension: str, **values: Any) -> Signal:
    return Signal(code=code, severity=severity, importance=importance, dimension=dimension, values=values)


def _safe_int(value: Any) -> int:
    try:
        if value is None or pd.isna(value):
            return 0
    except (TypeError, ValueError):
        return 0
    try:
        number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        return 0 if pd.isna(number) else int(number)
    except (TypeError, ValueError, OverflowError):
        return 0


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").dropna()


def _level_signal(value: Any, prefix: str, thresholds: dict[str, float], dimension: str) -> Signal:
    """Map a canonical percentage to an internal language-selection band.

    The returned code is not an official performance grade. It only controls
    wording/composition and must never be exposed as a formal monitoring category.
    """
    if not is_number(value):
        return _signal(f"{prefix}_unavailable", "neutral", 75, dimension, value=None, basis="canonical_fact")
    val = float(value)
    if prefix == "execution":
        if val >= thresholds["top"]:
            label, sev, imp = "very_high", "positive", 70
        elif val >= thresholds["upper"]:
            label, sev, imp = "high", "positive", 60
        elif val >= thresholds["middle"]:
            label, sev, imp = "medium", "neutral", 50
        elif val >= thresholds["lower"]:
            label, sev, imp = "low", "negative", 75
        else:
            label, sev, imp = "very_low", "negative", 95
    else:
        if val >= thresholds["near_full"]:
            label, sev, imp = "near_full", "positive", 65
        elif val >= thresholds["broad"]:
            label, sev, imp = "broad", "positive", 55
        elif val >= thresholds["partial"]:
            label, sev, imp = "partial", "warning", 70
        elif val >= thresholds["limited"]:
            label, sev, imp = "limited", "negative", 85
        else:
            label, sev, imp = "very_limited", "negative", 100
    return _signal(
        f"{prefix}_{label}", sev, imp, dimension, value=val,
        classification_basis="language_only_band",
    )


def _delta_code(delta: float, prefix: str) -> tuple[str, str, int]:
    magnitude = abs(delta)
    if magnitude < DELTA_LANGUAGE_BANDS["small"]:
        return f"{prefix}_stable", "neutral", 45
    direction = "increased" if delta > 0 else "decreased"
    if magnitude >= DELTA_LANGUAGE_BANDS["strong"]:
        strength, imp = "strongly", 85
    elif magnitude >= DELTA_LANGUAGE_BANDS["moderate"]:
        strength, imp = "moderately", 70
    else:
        strength, imp = "slightly", 55
    severity = "positive" if delta > 0 else "negative"
    return f"{prefix}_{direction}_{strength}", severity, imp


def _distribution_signals(ctx: AnalyticsContext, prefix: str) -> list[Signal]:
    """Classify prepared distribution facts without creating new numeric metrics."""
    signals: list[Signal] = []
    facts = ctx.factual_structure(f"{prefix}.distribution", {}) or {}
    count = int(facts.get("count") or 0)
    if count <= 0:
        return signals
    if count == 1:
        top = (facts.get("top") or [("", None)])[0]
        signals.append(_signal(f"single_{prefix}", "neutral", 40, prefix, label=str(top[0] or "")))
        return signals

    best_label = str(facts.get("best_label") or "")
    worst_label = str(facts.get("worst_label") or "")
    best_value = facts.get("best")
    worst_value = facts.get("worst")
    gap = facts.get("gap")
    if is_number(best_value):
        signals.append(_signal(f"{prefix}_leader", "positive", 45, prefix, label=best_label, value=float(best_value)))
    if is_number(worst_value):
        signals.append(_signal(f"{prefix}_laggard", "negative", 60, prefix, label=worst_label, value=float(worst_value)))
    if is_number(gap):
        gap_val = float(gap)
        if gap_val >= GAP_LANGUAGE_BANDS["very_wide"]:
            code, imp = f"{prefix}_gap_very_wide", 85
        elif gap_val >= GAP_LANGUAGE_BANDS["wide"]:
            code, imp = f"{prefix}_gap_wide", 70
        elif gap_val >= GAP_LANGUAGE_BANDS["moderate"]:
            code, imp = f"{prefix}_gap_moderate", 55
        else:
            code, imp = f"{prefix}_gap_narrow", 45
        signals.append(_signal(code, "warning" if gap_val >= GAP_LANGUAGE_BANDS["wide"] else "neutral", imp, prefix, gap=gap_val, best=best_label, worst=worst_label, classification_basis="language_only_band"))

    changes = ctx.factual_structure(f"{prefix}.change", {}) or {}
    if changes:
        top_delta = changes.get("largest_improvement")
        bottom_delta = changes.get("largest_deterioration")
        if is_number(top_delta) and float(top_delta) >= DELTA_LANGUAGE_BANDS["small"]:
            signals.append(_signal(f"{prefix}_most_improved", "positive", 55, prefix, label=str(changes.get("largest_improvement_label") or ""), delta=float(top_delta)))
        if is_number(bottom_delta) and float(bottom_delta) <= -DELTA_LANGUAGE_BANDS["small"]:
            signals.append(_signal(f"{prefix}_most_deteriorated", "negative", 70, prefix, label=str(changes.get("largest_deterioration_label") or ""), delta=float(bottom_delta)))

    for topic, suffix, imp in (("problems", "most_problematic", 80), ("missing", "most_missing", 75)):
        concentration = ctx.factual_structure(f"{prefix}.{topic}", {}) or {}
        if _safe_int(concentration.get("top_count")) > 0:
            signals.append(_signal(f"{prefix}_{suffix}", "negative", imp, prefix, label=str(concentration.get("top_label") or ""), count=_safe_int(concentration.get("top_count"))))

    # Highest/lowest coverage are direct prepared source facts, not derived arithmetic.
    frame = getattr(ctx, {"goal":"goal_progress", "task":"task_progress", "department":"department_progress"}[prefix])
    label_col = {"goal":"goal_code", "task":"task_code", "department":"department"}[prefix]
    if frame is not None and not frame.empty and "Покриття_%" in frame.columns:
        cov = pd.to_numeric(frame["Покриття_%"], errors="coerce")
        if cov.notna().any():
            hi = frame.loc[cov.idxmax()]
            lo = frame.loc[cov.idxmin()]
            signals.append(_signal(f"{prefix}_highest_coverage", "positive", 35, prefix, label=str(hi.get(label_col, "")), value=float(cov.max())))
            signals.append(_signal(f"{prefix}_lowest_coverage", "warning", 55, prefix, label=str(lo.get(label_col, "")), value=float(cov.min())))
    return signals

def detect_signals(ctx: AnalyticsContext) -> list[Signal]:
    signals: list[Signal] = []
    execution = ctx.metric("completion")
    coverage = ctx.metric("coverage")
    signals.append(_level_signal(execution, "execution", EXECUTION_LANGUAGE_BANDS, "execution"))
    signals.append(_level_signal(coverage, "coverage", COVERAGE_LANGUAGE_BANDS, "coverage"))

    sample = ctx.sample_size
    if sample <= SAMPLE_THRESHOLDS["single"]:
        signals.append(_signal("sample_single", "warning", 95, "sample", count=sample))
    elif sample <= SAMPLE_THRESHOLDS["very_small"]:
        signals.append(_signal("sample_very_small", "warning", 80, "sample", count=sample))
    elif sample <= SAMPLE_THRESHOLDS["small"]:
        signals.append(_signal("sample_small", "neutral", 55, "sample", count=sample))
    elif sample >= SAMPLE_THRESHOLDS["large"]:
        signals.append(_signal("sample_large", "neutral", 35, "sample", count=sample))
    else:
        signals.append(_signal("sample_standard", "neutral", 25, "sample", count=sample))

    no_data = _safe_int(ctx.metric("no_data"))
    missing_share_pct = ctx.factual_value("overall.missing_share_pct")
    if no_data == 0:
        signals.append(_signal("missing_none", "positive", 30, "coverage", count=0))
    elif is_number(missing_share_pct):
        share = float(missing_share_pct)
        if share >= MISSING_SHARE_LANGUAGE_BANDS["large"] * 100.0:
            signals.append(_signal("missing_share_large", "negative", 90, "coverage", count=no_data, share_pct=share, classification_basis="language_only_band"))
        elif share >= MISSING_SHARE_LANGUAGE_BANDS["material"] * 100.0:
            signals.append(_signal("missing_share_material", "warning", 70, "coverage", count=no_data, share_pct=share, classification_basis="language_only_band"))
        else:
            signals.append(_signal("missing_share_small", "warning", 45, "coverage", count=no_data, share_pct=share, classification_basis="language_only_band"))

    problem = _safe_int(ctx.metric("problem"))
    problem_share_pct = ctx.factual_value("overall.problem_share_pct")
    if problem and is_number(problem_share_pct):
        share = float(problem_share_pct)
        code = "problem_signals_large_share" if share >= PROBLEM_SHARE_LANGUAGE_BANDS["large"] * 100.0 else "problem_signals_present"
        signals.append(_signal(code, "negative", 85 if code == "problem_signals_large_share" else 60, "risk", count=problem, share_pct=share, classification_basis="language_only_band"))
    elif problem:
        signals.append(_signal("problem_signals_present", "negative", 60, "risk", count=problem))
    else:
        signals.append(_signal("problem_signals_none", "positive", 30, "risk", count=0))

    trajectory = ctx.factual_structure("trajectory", {}) or {}
    execution_series = list(trajectory.get("values") or [])
    coverage_series = list(trajectory.get("coverage_values") or [])
    diffs = [x for x in (trajectory.get("deltas") or []) if is_number(x)]
    if len(execution_series) < 2 or not diffs:
        signals.append(_signal("dynamics_insufficient", "neutral", 55, "dynamics", periods=len(execution_series)))
    else:
        delta = float(diffs[-1])
        code, sev, imp = _delta_code(delta, "execution")
        signals.append(_signal(code, sev, imp, "dynamics", delta=delta, previous=trajectory.get("first") if len(execution_series)==2 else execution_series[-2], current=trajectory.get("last"), classification_basis="language_only_band"))
        if len(diffs) >= 2:
            if all(x >= DELTA_LANGUAGE_BANDS["small"] for x in diffs[-2:]):
                signals.append(_signal("execution_two_period_growth", "positive", 70, "dynamics", deltas=diffs[-2:]))
            if all(x <= -DELTA_LANGUAGE_BANDS["small"] for x in diffs[-2:]):
                signals.append(_signal("execution_two_period_decline", "negative", 85, "dynamics", deltas=diffs[-2:]))
            if len(diffs) >= 3 and all(x >= DELTA_LANGUAGE_BANDS["small"] for x in diffs[-3:]):
                signals.append(_signal("execution_three_period_growth", "positive", 80, "dynamics", deltas=diffs[-3:]))
            if len(diffs) >= 3 and all(x <= -DELTA_LANGUAGE_BANDS["small"] for x in diffs[-3:]):
                signals.append(_signal("execution_three_period_decline", "negative", 95, "dynamics", deltas=diffs[-3:]))
            previous_delta = float(diffs[-2]); current_delta = float(diffs[-1])
            if previous_delta < 0 < current_delta:
                signals.append(_signal("execution_reversal_positive", "positive", 80, "dynamics", previous_delta=previous_delta, current_delta=current_delta))
            if previous_delta > 0 > current_delta:
                signals.append(_signal("execution_reversal_negative", "negative", 90, "dynamics", previous_delta=previous_delta, current_delta=current_delta))
            if previous_delta > 0 and current_delta > previous_delta + DELTA_LANGUAGE_BANDS["small"]:
                signals.append(_signal("positive_dynamics_accelerating", "positive", 65, "dynamics", previous_delta=previous_delta, current_delta=current_delta))
            if previous_delta > 0 and 0 < current_delta < previous_delta - DELTA_LANGUAGE_BANDS["small"]:
                signals.append(_signal("positive_dynamics_slowing", "warning", 55, "dynamics", previous_delta=previous_delta, current_delta=current_delta))
            if previous_delta < 0 and current_delta < previous_delta - DELTA_LANGUAGE_BANDS["small"]:
                signals.append(_signal("negative_dynamics_accelerating", "negative", 90, "dynamics", previous_delta=previous_delta, current_delta=current_delta))
        volatility = trajectory.get("volatility_stddev")
        if is_number(volatility) and float(volatility) >= VOLATILITY_LANGUAGE_BAND:
            signals.append(_signal("execution_high_volatility", "warning", 70, "dynamics", volatility=float(volatility), classification_basis="language_only_band"))

    coverage_deltas = [x for x in (trajectory.get("coverage_deltas") or []) if is_number(x)]
    if coverage_deltas:
        cov_delta = float(coverage_deltas[-1])
        code, sev, imp = _delta_code(cov_delta, "coverage")
        previous_cov = next((x for x in reversed(coverage_series[:-1]) if is_number(x)), None) if coverage_series else None
        current_cov = next((x for x in reversed(coverage_series) if is_number(x)), None) if coverage_series else None
        signals.append(_signal(code, sev, imp, "coverage", delta=cov_delta, previous=previous_cov, current=current_cov, classification_basis="language_only_band"))

    # Combined execution/coverage semantics: low coverage limits the strength of conclusions.
    codes = {s.code for s in signals}
    limited_cov = bool(codes & {"coverage_partial", "coverage_limited", "coverage_very_limited"})
    broad_cov = bool(codes & {"coverage_broad", "coverage_near_full"})
    lower_exec = bool(codes & {"execution_low", "execution_very_low"})
    upper_exec = bool(codes & {"execution_high", "execution_very_high"})
    if lower_exec and limited_cov:
        signals.append(_signal("lower_execution_limited_coverage", "warning", 100, "combined"))
    if lower_exec and broad_cov:
        signals.append(_signal("lower_execution_broad_coverage", "negative", 100, "combined"))
    if upper_exec and limited_cov:
        signals.append(_signal("upper_execution_limited_coverage", "warning", 90, "combined"))

    execution_up = any(s.code.startswith("execution_increased_") for s in signals)
    execution_down = any(s.code.startswith("execution_decreased_") for s in signals)
    coverage_up = any(s.code.startswith("coverage_increased_") for s in signals)
    coverage_down = any(s.code.startswith("coverage_decreased_") for s in signals)
    if execution_up and coverage_up:
        signals.append(_signal("execution_up_coverage_up", "positive", 90, "combined"))
    if execution_up and coverage_down:
        signals.append(_signal("execution_up_coverage_down", "warning", 100, "combined"))
    if execution_down and broad_cov:
        signals.append(_signal("execution_down_broad_coverage", "negative", 100, "combined"))
    if execution_down and coverage_up:
        signals.append(_signal("execution_down_coverage_up", "negative", 90, "combined"))

    # Year-over-year signals classify the prepared comparison facts.
    yoy_facts = ctx.factual_structure("yoy", {}) or {}
    last_pair = str(yoy_facts.get("comparison") or "")
    yoy_metrics = yoy_facts.get("metrics") or {}
    for label, prefix in (("Рівень виконання СП", "yoy_execution"), ("Покриття моніторингом", "yoy_coverage"), ("Проблемні / ризикові", "yoy_problem"), ("Без поданих погоджених даних", "yoy_missing")):
        row = yoy_metrics.get(label) or {}
        delta = row.get("delta")
        if not is_number(delta):
            continue
        delta = float(delta)
        if prefix in {"yoy_problem", "yoy_missing"}:
            if delta > 0:
                code, sev, imp = f"{prefix}_increased", "negative", 75
            elif delta < 0:
                code, sev, imp = f"{prefix}_decreased", "positive", 65
            else:
                code, sev, imp = f"{prefix}_stable", "neutral", 35
        else:
            code, sev, imp = _delta_code(delta, prefix)
        signals.append(_signal(code, sev, imp, "yoy", delta=delta, previous=row.get("previous"), current=row.get("current"), comparison=last_pair))

    signals.extend(_distribution_signals(ctx, "goal"))
    signals.extend(_distribution_signals(ctx, "task"))
    signals.extend(_distribution_signals(ctx, "department"))

    # Problem concentration is classified from centrally prepared percent metrics.
    for prefix in ("goal", "department"):
        facts = ctx.factual_structure(f"{prefix}.problems", {}) or {}
        share = facts.get("top_share")
        total = _safe_int(facts.get("total"))
        if not is_number(share) or total <= 0:
            continue
        share = float(share)
        label = str(facts.get("top_label") or "")
        if share >= CONCENTRATION_LANGUAGE_BANDS["majority"] * 100.0:
            signals.append(_signal(f"{prefix}_problem_concentration_half_or_more", "negative", 90, "concentration", label=label, share_pct=share, count=_safe_int(facts.get("top_count")), total=total, classification_basis="language_only_band"))
        elif share >= CONCENTRATION_LANGUAGE_BANDS["material"] * 100.0:
            signals.append(_signal(f"{prefix}_problem_concentration_material", "warning", 70, "concentration", label=label, share_pct=share, count=_safe_int(facts.get("top_count")), total=total, classification_basis="language_only_band"))
        else:
            signals.append(_signal(f"{prefix}_problems_distributed", "neutral", 45, "concentration", share_pct=share, total=total))

    # Product signals use prepared portfolio/execution facts.
    product = ctx.factual_structure("product", {}) or {}
    if product:
        largest_share = product.get("largest_share")
        if product.get("largest_label"):
            signals.append(_signal("product_dominant", "neutral", 45, "products", label=str(product.get("largest_label")), share_pct=largest_share, count=_safe_int(product.get("largest_size"))))
        if is_number(largest_share) and float(largest_share) >= CONCENTRATION_LANGUAGE_BANDS["majority"] * 100.0:
            signals.append(_signal("product_concentration_half_or_more", "warning", 55, "products", label=str(product.get("largest_label") or ""), share_pct=float(largest_share), classification_basis="language_only_band"))
        if is_number(product.get("best_value")) and is_number(product.get("worst_value")):
            signals.append(_signal("product_best", "positive", 40, "products", label=str(product.get("best_label") or ""), value=float(product.get("best_value"))))
            signals.append(_signal("product_weakest", "negative", 50, "products", label=str(product.get("worst_label") or ""), value=float(product.get("worst_value"))))

    # Status structure uses prepared shares in the common 0..100 convention.
    status = ctx.factual_structure("status", {}) or {}
    if status:
        dominant = str(status.get("dominant_label") or "")
        dominant_count = _safe_int(status.get("dominant_count"))
        dominant_share = status.get("dominant_share")
        if dominant:
            signals.append(_signal("status_dominant", "neutral", 40, "statuses", label=dominant, count=dominant_count, share_pct=dominant_share))
        mapping = {
            "Виконано": ("status_done_material_share", "positive", 55),
            "Частково виконано": ("status_partial_material_share", "warning", 55),
            "Не виконано": ("status_not_done_material_share", "negative", 80),
            "Не подано": ("status_not_submitted_material_share", "negative", 85),
            "Не настав час": ("status_not_yet_material_share", "neutral", 35),
            "Втратило актуальність": ("status_obsolete_material_share", "neutral", 35),
        }
        shares = status.get("shares") or {}
        counts = dict(status.get("ranked") or [])
        for label, (code, sev, imp) in mapping.items():
            share = shares.get(label)
            if is_number(share) and float(share) >= STATUS_SHARE_LANGUAGE_BANDS["material"] * 100.0:
                signals.append(_signal(code, sev, imp, "statuses", count=_safe_int(counts.get(label)), share_pct=float(share), classification_basis="language_only_band"))

    # Conflicting signals explicitly called out by the specification.
    codes = {s.code for s in signals}
    if execution_up and "yoy_problem_increased" in codes:
        signals.append(_signal("execution_up_problems_up", "warning", 95, "combined"))
    if execution_up and any(c in codes for c in {"goal_most_deteriorated", "department_most_deteriorated"}):
        signals.append(_signal("overall_up_but_component_down", "warning", 85, "combined"))

    # Remove accidental duplicate codes, keeping the strongest occurrence.
    strongest: dict[str, Signal] = {}
    for item in signals:
        if item.code not in strongest or item.importance > strongest[item.code].importance:
            strongest[item.code] = item
    return sorted(strongest.values(), key=lambda item: (-item.importance, item.code))


def _build_supported_signal_codes() -> frozenset[str]:
    codes: set[str] = set()
    codes.update({
        "execution_very_high", "execution_high", "execution_medium", "execution_low",
        "execution_very_low", "execution_unavailable",
        "coverage_near_full", "coverage_broad", "coverage_partial", "coverage_limited",
        "coverage_very_limited", "coverage_unavailable",
    })
    codes.update({"sample_single", "sample_very_small", "sample_small", "sample_standard", "sample_large"})
    codes.update({"missing_none", "missing_share_large", "missing_share_material", "missing_share_small"})
    codes.update({"problem_signals_large_share", "problem_signals_present", "problem_signals_none"})
    for prefix in ("execution", "coverage", "yoy_execution", "yoy_coverage"):
        codes.add(f"{prefix}_stable")
        for direction in ("increased", "decreased"):
            for strength in ("strongly", "moderately", "slightly"):
                codes.add(f"{prefix}_{direction}_{strength}")
    codes.update({
        "execution_two_period_growth", "execution_two_period_decline", "execution_three_period_growth",
        "execution_three_period_decline", "execution_reversal_positive", "execution_reversal_negative",
        "positive_dynamics_accelerating", "positive_dynamics_slowing", "negative_dynamics_accelerating",
        "execution_high_volatility", "dynamics_insufficient",
        "lower_execution_limited_coverage", "lower_execution_broad_coverage", "upper_execution_limited_coverage",
        "execution_up_coverage_up", "execution_up_coverage_down", "execution_down_broad_coverage",
        "execution_down_coverage_up", "execution_up_problems_up", "overall_up_but_component_down",
    })
    for prefix in ("yoy_problem", "yoy_missing"):
        codes.update({f"{prefix}_increased", f"{prefix}_decreased", f"{prefix}_stable"})
    for prefix in ("goal", "task", "department"):
        codes.update({
            f"single_{prefix}", f"{prefix}_leader", f"{prefix}_laggard", f"{prefix}_gap_very_wide",
            f"{prefix}_gap_wide", f"{prefix}_gap_moderate", f"{prefix}_gap_narrow",
            f"{prefix}_most_improved", f"{prefix}_most_deteriorated", f"{prefix}_most_problematic",
            f"{prefix}_most_missing", f"{prefix}_highest_coverage", f"{prefix}_lowest_coverage",
        })
    for prefix in ("goal", "department"):
        codes.update({f"{prefix}_problem_concentration_half_or_more", f"{prefix}_problem_concentration_material", f"{prefix}_problems_distributed"})
    codes.update({"product_dominant", "product_concentration_half_or_more", "product_best", "product_weakest"})
    codes.update({
        "status_dominant", "status_done_material_share", "status_partial_material_share", "status_not_done_material_share",
        "status_not_submitted_material_share", "status_not_yet_material_share", "status_obsolete_material_share",
    })
    return frozenset(codes)


SUPPORTED_SIGNAL_CODES = _build_supported_signal_codes()
