from __future__ import annotations

from statistics import pstdev
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


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").dropna()


def _latest_dynamics(ctx: AnalyticsContext) -> tuple[list[float], list[float], pd.DataFrame]:
    frame = ctx.period_dynamics.copy()
    if frame.empty:
        return [], [], frame
    q_order = {"I": 1, "II": 2, "III": 3, "IV": 4}
    frame["_year"] = pd.to_numeric(frame.get("report_year"), errors="coerce")
    frame["_q"] = frame.get("report_quarter", pd.Series(index=frame.index, dtype=object)).map(q_order)
    frame = frame.sort_values(["_year", "_q"], na_position="last")
    execution = pd.to_numeric(frame.get("Виконання"), errors="coerce").dropna().tolist()
    coverage = pd.to_numeric(frame.get("Покриття_%"), errors="coerce").dropna().tolist()
    return execution, coverage, frame


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


def _distribution_signals(frame: pd.DataFrame, prefix: str, label_col: str) -> list[Signal]:
    signals: list[Signal] = []
    if frame is None or frame.empty or "Виконання" not in frame.columns:
        return signals
    valid = frame.copy()
    valid["_exec"] = pd.to_numeric(valid["Виконання"], errors="coerce")
    valid = valid.dropna(subset=["_exec"])
    if valid.empty:
        return signals
    if len(valid) == 1:
        signals.append(_signal(f"single_{prefix}", "neutral", 40, prefix, label=str(valid.iloc[0].get(label_col, ""))))
        return signals
    best = valid.sort_values("_exec", ascending=False).iloc[0]
    worst = valid.sort_values("_exec", ascending=True).iloc[0]
    gap = float(best["_exec"] - worst["_exec"])
    signals.extend([
        _signal(f"{prefix}_leader", "positive", 45, prefix, label=str(best.get(label_col, "")), value=float(best["_exec"])),
        _signal(f"{prefix}_laggard", "negative", 60, prefix, label=str(worst.get(label_col, "")), value=float(worst["_exec"])),
    ])
    if gap >= GAP_LANGUAGE_BANDS["very_wide"]:
        code, imp = f"{prefix}_gap_very_wide", 85
    elif gap >= GAP_LANGUAGE_BANDS["wide"]:
        code, imp = f"{prefix}_gap_wide", 70
    elif gap >= GAP_LANGUAGE_BANDS["moderate"]:
        code, imp = f"{prefix}_gap_moderate", 55
    else:
        code, imp = f"{prefix}_gap_narrow", 45
    signals.append(_signal(code, "warning" if gap >= GAP_LANGUAGE_BANDS["wide"] else "neutral", imp, prefix, gap=gap, best=str(best.get(label_col, "")), worst=str(worst.get(label_col, "")), classification_basis="language_only_band"))

    if "Зміна" in valid.columns:
        valid["_change"] = pd.to_numeric(valid["Зміна"], errors="coerce")
        changes = valid.dropna(subset=["_change"])
        if not changes.empty:
            top = changes.sort_values("_change", ascending=False).iloc[0]
            bottom = changes.sort_values("_change", ascending=True).iloc[0]
            if float(top["_change"]) >= DELTA_LANGUAGE_BANDS["small"]:
                signals.append(_signal(f"{prefix}_most_improved", "positive", 55, prefix, label=str(top.get(label_col, "")), delta=float(top["_change"])))
            if float(bottom["_change"]) <= -DELTA_LANGUAGE_BANDS["small"]:
                signals.append(_signal(f"{prefix}_most_deteriorated", "negative", 70, prefix, label=str(bottom.get(label_col, "")), delta=float(bottom["_change"])))
    for col, suffix, imp in (("Проблемних", "most_problematic", 80), ("Без_даних", "most_missing", 75)):
        if col in valid.columns:
            vals = pd.to_numeric(valid[col], errors="coerce").fillna(0)
            if vals.max() > 0:
                idx = vals.idxmax()
                row = valid.loc[idx]
                signals.append(_signal(f"{prefix}_{suffix}", "negative", imp, prefix, label=str(row.get(label_col, "")), count=int(vals.loc[idx])))
    if "Покриття_%" in valid.columns:
        cov = pd.to_numeric(valid["Покриття_%"], errors="coerce")
        if cov.notna().any():
            hi = valid.loc[cov.idxmax()]
            lo = valid.loc[cov.idxmin()]
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

    no_data = int(ctx.metric("no_data") or 0)
    total_rows = max(int(ctx.metric("total_rows") or 0), 1)
    if no_data == 0:
        signals.append(_signal("missing_none", "positive", 30, "coverage", count=0))
    else:
        ratio = no_data / total_rows
        if ratio >= MISSING_SHARE_LANGUAGE_BANDS["large"]:
            signals.append(_signal("missing_share_large", "negative", 90, "coverage", count=no_data, ratio=ratio, classification_basis="language_only_band"))
        elif ratio >= MISSING_SHARE_LANGUAGE_BANDS["material"]:
            signals.append(_signal("missing_share_material", "warning", 70, "coverage", count=no_data, ratio=ratio, classification_basis="language_only_band"))
        else:
            signals.append(_signal("missing_share_small", "warning", 45, "coverage", count=no_data, ratio=ratio, classification_basis="language_only_band"))

    problem = int(ctx.metric("problem") or 0)
    if problem:
        ratio = problem / total_rows
        code = "problem_signals_large_share" if ratio >= PROBLEM_SHARE_LANGUAGE_BANDS["large"] else "problem_signals_present"
        signals.append(_signal(code, "negative", 85 if ratio >= PROBLEM_SHARE_LANGUAGE_BANDS["large"] else 60, "risk", count=problem, ratio=ratio, classification_basis="language_only_band"))
    else:
        signals.append(_signal("problem_signals_none", "positive", 30, "risk", count=0))

    execution_series, coverage_series, dyn = _latest_dynamics(ctx)
    if len(execution_series) < 2:
        signals.append(_signal("dynamics_insufficient", "neutral", 55, "dynamics", periods=len(execution_series)))
    else:
        delta = float(execution_series[-1] - execution_series[-2])
        code, sev, imp = _delta_code(delta, "execution")
        signals.append(_signal(code, sev, imp, "dynamics", delta=delta, previous=execution_series[-2], current=execution_series[-1], classification_basis="language_only_band"))
        diffs = [b - a for a, b in zip(execution_series[:-1], execution_series[1:])]
        if len(diffs) >= 2:
            if all(x >= DELTA_LANGUAGE_BANDS["small"] for x in diffs[-2:]):
                signals.append(_signal("execution_two_period_growth", "positive", 70, "dynamics", deltas=diffs[-2:]))
            if all(x <= -DELTA_LANGUAGE_BANDS["small"] for x in diffs[-2:]):
                signals.append(_signal("execution_two_period_decline", "negative", 85, "dynamics", deltas=diffs[-2:]))
            if len(diffs) >= 3 and all(x >= DELTA_LANGUAGE_BANDS["small"] for x in diffs[-3:]):
                signals.append(_signal("execution_three_period_growth", "positive", 80, "dynamics", deltas=diffs[-3:]))
            if len(diffs) >= 3 and all(x <= -DELTA_LANGUAGE_BANDS["small"] for x in diffs[-3:]):
                signals.append(_signal("execution_three_period_decline", "negative", 95, "dynamics", deltas=diffs[-3:]))
            if diffs[-2] < 0 < diffs[-1]:
                signals.append(_signal("execution_reversal_positive", "positive", 80, "dynamics", previous_delta=diffs[-2], current_delta=diffs[-1]))
            if diffs[-2] > 0 > diffs[-1]:
                signals.append(_signal("execution_reversal_negative", "negative", 90, "dynamics", previous_delta=diffs[-2], current_delta=diffs[-1]))
            if diffs[-2] > 0 and diffs[-1] > diffs[-2] + DELTA_LANGUAGE_BANDS["small"]:
                signals.append(_signal("positive_dynamics_accelerating", "positive", 65, "dynamics", previous_delta=diffs[-2], current_delta=diffs[-1]))
            if diffs[-2] > 0 and 0 < diffs[-1] < diffs[-2] - DELTA_LANGUAGE_BANDS["small"]:
                signals.append(_signal("positive_dynamics_slowing", "warning", 55, "dynamics", previous_delta=diffs[-2], current_delta=diffs[-1]))
            if diffs[-2] < 0 and diffs[-1] < diffs[-2] - DELTA_LANGUAGE_BANDS["small"]:
                signals.append(_signal("negative_dynamics_accelerating", "negative", 90, "dynamics", previous_delta=diffs[-2], current_delta=diffs[-1]))
        if len(execution_series) >= 3 and pstdev(execution_series) >= VOLATILITY_LANGUAGE_BAND:
            signals.append(_signal("execution_high_volatility", "warning", 70, "dynamics", volatility=pstdev(execution_series), classification_basis="language_only_band"))

    if len(coverage_series) >= 2:
        cov_delta = float(coverage_series[-1] - coverage_series[-2])
        code, sev, imp = _delta_code(cov_delta, "coverage")
        signals.append(_signal(code, sev, imp, "coverage", delta=cov_delta, previous=coverage_series[-2], current=coverage_series[-1], classification_basis="language_only_band"))

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

    # Year-over-year signals use the already prepared comparison table.
    yoy = ctx.yoy_comparison
    if yoy is not None and not yoy.empty:
        last_pair = str(yoy.iloc[-1].get("Період порівняння", ""))
        subset = yoy[yoy["Період порівняння"].astype(str).eq(last_pair)] if "Період порівняння" in yoy.columns else yoy
        lookup = {str(r.get("Показник")): r for _, r in subset.iterrows()}
        for label, prefix in (("Рівень виконання СП", "yoy_execution"), ("Покриття моніторингом", "yoy_coverage"), ("Проблемні / ризикові", "yoy_problem"), ("Без поданих погоджених даних", "yoy_missing")):
            row = lookup.get(label)
            if row is None or not is_number(row.get("Зміна")):
                continue
            delta = float(row.get("Зміна"))
            if prefix in {"yoy_problem", "yoy_missing"}:
                if delta > 0:
                    code, sev, imp = f"{prefix}_increased", "negative", 75
                elif delta < 0:
                    code, sev, imp = f"{prefix}_decreased", "positive", 65
                else:
                    code, sev, imp = f"{prefix}_stable", "neutral", 35
            else:
                c, sev, imp = _delta_code(delta, prefix)
                code = c
            signals.append(_signal(code, sev, imp, "yoy", delta=delta, previous=row.get("Попередній рік"), current=row.get("Поточний рік"), comparison=last_pair))

    signals.extend(_distribution_signals(ctx.goal_progress, "goal", "goal_code"))
    signals.extend(_distribution_signals(ctx.task_progress, "task", "task_code"))
    signals.extend(_distribution_signals(ctx.department_progress, "department", "department"))

    # Concentration of problems in a single goal/department when canonical descriptive counts are available.
    for frame, prefix, label_col in ((ctx.goal_progress, "goal", "goal_code"), (ctx.department_progress, "department", "department")):
        if frame is None or frame.empty or "Проблемних" not in frame.columns:
            continue
        vals = pd.to_numeric(frame["Проблемних"], errors="coerce").fillna(0)
        total = float(vals.sum())
        if total <= 0:
            continue
        idx = vals.idxmax()
        ratio = float(vals.loc[idx] / total)
        label = str(frame.loc[idx].get(label_col, ""))
        if ratio >= CONCENTRATION_LANGUAGE_BANDS["majority"]:
            signals.append(_signal(f"{prefix}_problem_concentration_half_or_more", "negative", 90, "concentration", label=label, ratio=ratio, count=int(vals.loc[idx]), total=int(total), classification_basis="language_only_band"))
        elif ratio >= CONCENTRATION_LANGUAGE_BANDS["material"]:
            signals.append(_signal(f"{prefix}_problem_concentration_material", "warning", 70, "concentration", label=label, ratio=ratio, count=int(vals.loc[idx]), total=int(total), classification_basis="language_only_band"))
        else:
            signals.append(_signal(f"{prefix}_problems_distributed", "neutral", 45, "concentration", ratio=ratio, total=int(total)))

    # Product signals.
    products = ctx.product_progress.copy()
    if products is not None and not products.empty:
        if "Унікальних_заходів" in products.columns:
            counts = pd.to_numeric(products["Унікальних_заходів"], errors="coerce").fillna(0)
            total = float(counts.sum())
            if total > 0:
                idx = counts.idxmax(); ratio = float(counts.loc[idx] / total)
                signals.append(_signal("product_dominant", "neutral", 45, "products", label=str(products.loc[idx].get("product_type", "")), ratio=ratio, count=int(counts.loc[idx])))
                if ratio >= CONCENTRATION_LANGUAGE_BANDS["majority"]:
                    signals.append(_signal("product_concentration_half_or_more", "warning", 55, "products", label=str(products.loc[idx].get("product_type", "")), ratio=ratio, classification_basis="language_only_band"))
        execs = _numeric(products, "Виконання")
        if len(execs) >= 2:
            best_idx = pd.to_numeric(products["Виконання"], errors="coerce").idxmax()
            worst_idx = pd.to_numeric(products["Виконання"], errors="coerce").idxmin()
            signals.append(_signal("product_best", "positive", 40, "products", label=str(products.loc[best_idx].get("product_type", "")), value=float(pd.to_numeric(products.loc[best_idx, "Виконання"]))))
            signals.append(_signal("product_weakest", "negative", 50, "products", label=str(products.loc[worst_idx].get("product_type", "")), value=float(pd.to_numeric(products.loc[worst_idx, "Виконання"]))))

    # Status structure.
    statuses = ctx.status_counts.copy()
    if statuses is not None and not statuses.empty and {"status", "Кількість"}.issubset(statuses.columns):
        counts = {str(r["status"]): int(r["Кількість"]) for _, r in statuses.iterrows()}
        total = max(sum(counts.values()), 1)
        if counts:
            dominant = max(counts, key=counts.get)
            signals.append(_signal("status_dominant", "neutral", 40, "statuses", label=dominant, count=counts[dominant], ratio=counts[dominant] / total))
        mapping = {
            "Виконано": ("status_done_material_share", "positive", 55),
            "Частково виконано": ("status_partial_material_share", "warning", 55),
            "Не виконано": ("status_not_done_material_share", "negative", 80),
            "Не подано": ("status_not_submitted_material_share", "negative", 85),
            "Не настав час": ("status_not_yet_material_share", "neutral", 35),
            "Втратило актуальність": ("status_obsolete_material_share", "neutral", 35),
        }
        for label, (code, sev, imp) in mapping.items():
            ratio = counts.get(label, 0) / total
            if ratio >= STATUS_SHARE_LANGUAGE_BANDS["material"]:
                signals.append(_signal(code, sev, imp, "statuses", count=counts.get(label, 0), ratio=ratio, classification_basis="language_only_band"))

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
