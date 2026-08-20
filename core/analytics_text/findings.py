from __future__ import annotations

"""Cross-dimensional analytical layer for the management note.

This module never recalculates canonical monitoring KPIs.  It receives already
calculated aggregates and performs descriptive/analytical operations over them:
comparison, dispersion, concentration, breadth of change, localisation and
narrative prioritisation.  That distinction is deliberate: a contributor is a
mathematical part of the observed portfolio, not a causal explanation.
"""

from dataclasses import dataclass
from statistics import median
from typing import Any, Iterable

import pandas as pd

from .config import DELTA_LANGUAGE_BANDS, VOLATILITY_LANGUAGE_BAND
from .language import is_number
from .models import AnalyticsContext, AnalyticalFinding, AnalyticalQuestion, Signal


QUESTIONS: tuple[AnalyticalQuestion, ...] = (
    AnalyticalQuestion("what_is_scope", (), ("scope",), 50),
    AnalyticalQuestion("what_is_overall_state", (), ("execution", "coverage"), 80),
    AnalyticalQuestion("what_is_full_trajectory", ("execution_increased", "execution_decreased"), ("periods",), 90),
    AnalyticalQuestion("is_change_broad_based", ("execution_increased", "execution_decreased"), ("goals", "departments"), 90),
    AnalyticalQuestion("where_are_problems", ("problem_signals_present", "problem_signals_large_share"), ("goals", "tasks", "departments"), 95),
    AnalyticalQuestion("where_is_missing", ("missing_share_small", "missing_share_material", "missing_share_large"), ("goals", "departments"), 90),
    AnalyticalQuestion("which_goals_drive_picture", (), ("goals",), 85),
    AnalyticalQuestion("which_tasks_localise_deviation", (), ("tasks",), 75),
    AnalyticalQuestion("which_ssp_matter_by_scale", (), ("departments",), 90),
    AnalyticalQuestion("what_changed_yoy", (), ("yoy",), 75),
    AnalyticalQuestion("are_signals_conflicting", (), ("execution", "coverage", "problems"), 90),
    AnalyticalQuestion("what_requires_management_attention", (), ("goals", "tasks", "departments"), 100),
)


def _f(code: str, topic: str, importance: int, polarity: str = "neutral", *, facts: dict[str, Any] | None = None,
       source_signals: Iterable[str] = (), question: str | None = None) -> AnalyticalFinding:
    return AnalyticalFinding(
        code=code, topic=topic, importance=importance, polarity=polarity,
        facts=facts or {}, source_signals=tuple(source_signals), question_code=question,
    )


def _num(value: Any) -> float | None:
    return float(value) if is_number(value) else None


def _int(value: Any) -> int:
    try:
        if pd.isna(value):
            return 0
    except (TypeError, ValueError):
        pass
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _numeric_col(frame: pd.DataFrame, column: str, default: float | None = None) -> pd.Series:
    if column in frame.columns:
        return pd.to_numeric(frame[column], errors="coerce")
    fill = float("nan") if default is None else default
    return pd.Series(fill, index=frame.index, dtype=float)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _label_for(frame: pd.DataFrame, row: pd.Series, kind: str) -> str:
    if kind == "goal":
        code = _safe_str(row.get("goal_code"))
        return f"СЦ {code}" if code and not code.upper().startswith("СЦ") else code
    if kind == "task":
        code = _safe_str(row.get("task_code"))
        name = _safe_str(row.get("task_name"))
        return f"{code} — {name}" if code and name else (code or name)
    if kind == "department":
        return _safe_str(row.get("department")) or _safe_str(row.get("ssp_index"))
    if kind == "product":
        return _safe_str(row.get("product_type"))
    return ""


def _sorted_periods(ctx: AnalyticsContext) -> pd.DataFrame:
    frame = ctx.period_dynamics.copy()
    if frame.empty:
        return frame
    qmap = {"I": 1, "II": 2, "III": 3, "IV": 4, "1": 1, "2": 2, "3": 3, "4": 4}
    frame["_year"] = pd.to_numeric(frame.get("report_year"), errors="coerce")
    q = frame.get("report_quarter", pd.Series(index=frame.index, dtype=object)).astype(str)
    frame["_q"] = q.map(qmap)
    return frame.sort_values(["_year", "_q"], na_position="last").reset_index(drop=True)


def _trajectory_finding(ctx: AnalyticsContext) -> list[AnalyticalFinding]:
    frame = _sorted_periods(ctx)
    if frame.empty or "Виконання" not in frame.columns:
        return [_f("trajectory_unavailable", "dynamics", 35, facts={"period_count": 0}, question="what_is_full_trajectory")]
    valid = frame[pd.to_numeric(frame["Виконання"], errors="coerce").notna()].copy()
    if valid.empty:
        return [_f("trajectory_unavailable", "dynamics", 35, facts={"period_count": 0}, question="what_is_full_trajectory")]
    valid["_exec"] = pd.to_numeric(valid["Виконання"], errors="coerce")
    valid["_cov"] = _numeric_col(valid, "Покриття_%")
    vals = valid["_exec"].tolist()
    periods = [_safe_str(x) for x in valid.get("Період", pd.Series(range(len(valid)))).tolist()]
    facts: dict[str, Any] = {
        "period_count": len(valid), "periods": periods, "values": vals,
        "first_period": periods[0], "first": vals[0], "last_period": periods[-1], "last": vals[-1],
    }
    if valid["_cov"].notna().any():
        facts["coverage_values"] = [None if pd.isna(x) else float(x) for x in valid["_cov"].tolist()]
        facts["coverage_first"] = _num(valid["_cov"].iloc[0])
        facts["coverage_last"] = _num(valid["_cov"].iloc[-1])
        if facts["coverage_first"] is not None and facts["coverage_last"] is not None:
            facts["coverage_cumulative_delta"] = facts["coverage_last"] - facts["coverage_first"]
    if len(vals) == 1:
        return [_f("trajectory_single_period", "dynamics", 45, facts=facts, question="what_is_full_trajectory")]

    deltas = [vals[i] - vals[i - 1] for i in range(1, len(vals))]
    facts["deltas"] = deltas
    facts["cumulative_delta"] = vals[-1] - vals[0]
    max_up = max(deltas)
    max_down = min(deltas)
    small_delta = float(DELTA_LANGUAGE_BANDS["small"])
    facts.update({
        "max_increase": max_up,
        "max_increase_period": periods[deltas.index(max_up) + 1],
        "max_decrease": max_down,
        "max_decrease_period": periods[deltas.index(max_down) + 1],
        # Mutually exclusive narrative buckets; tiny movements belong to flat_steps.
        "positive_steps": sum(d >= small_delta for d in deltas),
        "negative_steps": sum(d <= -small_delta for d in deltas),
        "flat_steps": sum(abs(d) < small_delta for d in deltas),
    })
    # Language-only trajectory classifications. They are narrative descriptors,
    # never official monitoring grades. Plateau is checked first so a sequence of
    # tiny positive increments is not mislabeled as substantive continuous growth.
    if all(abs(d) < small_delta for d in deltas):
        code, polarity = "trajectory_plateau", "neutral"
    elif all(d > 0 for d in deltas):
        code, polarity = "trajectory_continuous_growth", "positive"
    elif all(d < 0 for d in deltas):
        code, polarity = "trajectory_continuous_decline", "negative"
    elif len(deltas) >= 2 and deltas[-2] <= -small_delta and deltas[-1] >= small_delta:
        code, polarity = "trajectory_recovery", "positive"
    elif len(deltas) >= 2 and deltas[-2] >= small_delta and deltas[-1] <= -small_delta:
        code, polarity = "trajectory_reversal_negative", "negative"
    elif max(vals) - min(vals) >= VOLATILITY_LANGUAGE_BAND and any(d > 0 for d in deltas) and any(d < 0 for d in deltas):
        code, polarity = "trajectory_volatile", "warning"
    elif vals[-1] > vals[0]:
        code, polarity = "trajectory_net_growth", "positive"
    elif vals[-1] < vals[0]:
        code, polarity = "trajectory_net_decline", "negative"
    else:
        code, polarity = "trajectory_mixed_stable", "neutral"
    findings = [_f(code, "dynamics", 92 if len(vals) >= 3 else 80, polarity, facts=facts, question="what_is_full_trajectory")]
    if len(deltas) >= 2:
        if deltas[-1] > deltas[-2] > 0:
            findings.append(_f("trajectory_late_acceleration", "dynamics", 72, "positive", facts={"previous_delta": deltas[-2], "latest_delta": deltas[-1]}, question="what_is_full_trajectory"))
        elif 0 < deltas[-1] < deltas[-2]:
            findings.append(_f("trajectory_growth_slowing", "dynamics", 62, "warning", facts={"previous_delta": deltas[-2], "latest_delta": deltas[-1]}, question="what_is_full_trajectory"))
        elif deltas[-1] < deltas[-2] < 0:
            findings.append(_f("trajectory_decline_accelerating", "dynamics", 82, "negative", facts={"previous_delta": deltas[-2], "latest_delta": deltas[-1]}, question="what_is_full_trajectory"))
    return findings


def _distribution_findings(frame: pd.DataFrame, kind: str, overall: float | None = None) -> list[AnalyticalFinding]:
    if frame is None or frame.empty or "Виконання" not in frame.columns:
        return []
    data = frame.copy()
    data["_exec"] = pd.to_numeric(data["Виконання"], errors="coerce")
    data = data.dropna(subset=["_exec"])
    if data.empty:
        return []
    labels = [_label_for(data, row, kind) for _, row in data.iterrows()]
    data["_label"] = labels
    data = data[data["_label"].astype(bool)].copy()
    if data.empty:
        return []
    values = data["_exec"].astype(float)
    best = data.loc[values.idxmax()]
    worst = data.loc[values.idxmin()]
    mean = float(values.mean())
    med = float(values.median())
    gap = float(values.max() - values.min()) if len(values) > 1 else 0.0
    reference = overall if overall is not None else mean
    above = int((values > reference).sum())
    below = int((values < reference).sum())
    equal = int(len(values) - above - below)
    top = data.sort_values("_exec", ascending=False).head(3)
    bottom = data.sort_values("_exec", ascending=True).head(3)
    facts: dict[str, Any] = {
        "count": len(data), "mean": mean, "median": med, "reference": reference,
        "best_label": best["_label"], "best_value": float(best["_exec"]),
        "worst_label": worst["_label"], "worst_value": float(worst["_exec"]), "gap": gap,
        "above_reference": above, "below_reference": below, "equal_reference": equal,
        "top": [(r["_label"], float(r["_exec"])) for _, r in top.iterrows()],
        "bottom": [(r["_label"], float(r["_exec"])) for _, r in bottom.iterrows()],
    }
    if len(data) == 1:
        return [_f(f"{kind}_single_entity", kind, 40, facts=facts)]
    result = [_f(f"{kind}_distribution", kind, 82 if kind in {"goal", "department"} else 68, "neutral", facts=facts)]

    if "Зміна" in data.columns:
        data["_change"] = pd.to_numeric(data["Зміна"], errors="coerce")
        change = data.dropna(subset=["_change"])
        if not change.empty:
            # Language-only band: changes below 2 p.p. are described as minimal.
            # The three groups must be mutually exclusive so narrative counts always reconcile.
            small_delta = float(DELTA_LANGUAGE_BANDS["small"])
            stable = change[change["_change"].abs() < small_delta]
            improved = change[change["_change"] >= small_delta]
            declined = change[change["_change"] <= -small_delta]
            top_change = change.loc[change["_change"].idxmax()]
            bottom_change = change.loc[change["_change"].idxmin()]
            change_facts = {
                "count_with_change": len(change), "improved": len(improved), "declined": len(declined), "stable": len(stable),
                "improved_share": len(improved) / len(change) if len(change) else 0,
                "declined_share": len(declined) / len(change) if len(change) else 0,
                "largest_improvement_label": top_change["_label"], "largest_improvement": float(top_change["_change"]),
                "largest_deterioration_label": bottom_change["_label"], "largest_deterioration": float(bottom_change["_change"]),
            }
            if len(improved) >= max(1, int(0.7 * len(change))) and len(improved) > len(declined):
                code, polarity = f"{kind}_change_broad_positive", "positive"
            elif len(declined) >= max(1, int(0.7 * len(change))) and len(declined) > len(improved):
                code, polarity = f"{kind}_change_broad_negative", "negative"
            elif len(improved) and len(declined):
                code, polarity = f"{kind}_change_polarised", "warning"
            elif len(improved):
                code, polarity = f"{kind}_change_positive", "positive"
            elif len(declined):
                code, polarity = f"{kind}_change_negative", "negative"
            else:
                code, polarity = f"{kind}_change_stable", "neutral"
            result.append(_f(code, kind, 85 if kind in {"goal", "department"} else 70, polarity, facts=change_facts, question="is_change_broad_based"))
    return result


def _concentration_finding(frame: pd.DataFrame, kind: str, count_col: str, topic: str, question: str) -> AnalyticalFinding | None:
    if frame is None or frame.empty or count_col not in frame.columns:
        return None
    data = frame.copy()
    counts = pd.to_numeric(data[count_col], errors="coerce").fillna(0)
    total = int(counts.sum())
    if total <= 0:
        return _f(f"{kind}_{topic}_none", topic, 35, "positive", facts={"total": 0}, question=question)
    data["_count"] = counts.astype(int)
    label_kind = kind if kind in {"goal", "task", "department", "product"} else "department"
    data["_label"] = [_label_for(data, row, label_kind) for _, row in data.iterrows()]
    ranked = data.sort_values("_count", ascending=False)
    top1 = ranked.iloc[0]
    top3 = ranked.head(3)
    top1_share = int(top1["_count"]) / total
    top3_count = int(top3["_count"].sum())
    top3_share = top3_count / total
    affected = int((data["_count"] > 0).sum())
    facts = {
        "total": total, "affected_entities": affected, "entity_count": len(data),
        "top_label": top1["_label"], "top_count": int(top1["_count"]), "top_share": top1_share,
        "top3_count": top3_count, "top3_share": top3_share,
        "top3": [(r["_label"], int(r["_count"])) for _, r in top3.iterrows() if int(r["_count"]) > 0],
    }
    portfolios = None
    if "Унікальних_заходів" in data.columns:
        portfolios = pd.to_numeric(data["Унікальних_заходів"], errors="coerce").fillna(0)
    elif "portfolio_measure_count" in data.columns:
        portfolios = pd.to_numeric(data["portfolio_measure_count"], errors="coerce").fillna(0)
    if portfolios is not None:
        idx = top1.name
        portfolio = int(portfolios.loc[idx]) if idx in portfolios.index else 0
        total_portfolio = float(portfolios.sum())
        facts["top_portfolio_size"] = portfolio
        facts["top_internal_rate"] = (int(top1["_count"]) / portfolio) if portfolio > 0 else None
        facts["top_portfolio_share"] = (portfolio / total_portfolio) if total_portfolio > 0 else None
        if facts["top_portfolio_share"] is not None:
            facts["concentration_excess_pp"] = (top1_share - facts["top_portfolio_share"]) * 100
    if top1_share >= 0.5 or top3_share >= 0.7:
        code, polarity = f"{kind}_{topic}_concentrated", "negative" if topic in {"problems", "missing"} else "warning"
    elif affected <= max(2, len(data) // 4):
        code, polarity = f"{kind}_{topic}_localised", "warning"
    else:
        code, polarity = f"{kind}_{topic}_distributed", "neutral"
    return _f(code, topic, 88 if topic in {"problems", "missing"} else 70, polarity, facts=facts, question=question)


def _status_finding(ctx: AnalyticsContext) -> AnalyticalFinding | None:
    frame = ctx.status_counts
    if frame is None or frame.empty or not {"status", "Кількість"}.issubset(frame.columns):
        return None
    rows = [(str(r["status"]), _int(r["Кількість"])) for _, r in frame.iterrows()]
    total = sum(v for _, v in rows)
    if total <= 0:
        return None
    ranked = sorted(rows, key=lambda x: x[1], reverse=True)
    shares = {label: count / total for label, count in rows}
    facts: dict[str, Any] = {
        "total": total, "ranked": ranked, "shares": shares,
        "dominant_label": ranked[0][0], "dominant_count": ranked[0][1], "dominant_share": ranked[0][1] / total,
    }

    # Descriptive period-to-period status comparison from the already filtered
    # active records. Shares are compared, not raw counts only, because the
    # number of records can differ between periods. This does not alter any KPI.
    active = ctx.active.copy()
    required = {"report_year", "report_quarter", "status"}
    if not active.empty and required.issubset(active.columns):
        qmap = {"I": 1, "II": 2, "III": 3, "IV": 4, "1": 1, "2": 2, "3": 3, "4": 4}
        active["_year"] = pd.to_numeric(active["report_year"], errors="coerce")
        active["_q"] = active["report_quarter"].astype(str).map(qmap)
        period_rows = active.dropna(subset=["_year", "_q"]).copy()
        periods = sorted({(int(y), int(q)) for y, q in zip(period_rows["_year"], period_rows["_q"])})
        if len(periods) >= 2:
            previous_key, latest_key = periods[-2], periods[-1]
            inverse_q = {1: "I", 2: "II", 3: "III", 4: "IV"}
            def _period_status(key: tuple[int, int]) -> tuple[int, dict[str, int], dict[str, float]]:
                year, qnum = key
                part = period_rows[(period_rows["_year"] == year) & (period_rows["_q"] == qnum)]
                counts = part["status"].fillna("н/д").astype(str).value_counts().to_dict()
                n = int(len(part))
                period_shares = {label: count / n for label, count in counts.items()} if n else {}
                return n, {str(k): int(v) for k, v in counts.items()}, period_shares
            prev_total, prev_counts, prev_shares = _period_status(previous_key)
            latest_total, latest_counts, latest_shares = _period_status(latest_key)
            labels = sorted(set(prev_shares) | set(latest_shares))
            changes = {label: (latest_shares.get(label, 0.0) - prev_shares.get(label, 0.0)) * 100 for label in labels}
            facts["period_comparison"] = {
                "previous_period": f"{previous_key[0]} {inverse_q.get(previous_key[1], previous_key[1])}",
                "latest_period": f"{latest_key[0]} {inverse_q.get(latest_key[1], latest_key[1])}",
                "previous_total": prev_total, "latest_total": latest_total,
                "previous_counts": prev_counts, "latest_counts": latest_counts,
                "previous_shares": prev_shares, "latest_shares": latest_shares, "share_changes_pp": changes,
            }

    # Statuses are a supporting analytical dimension. Treat them as important
    # only when the distribution itself is materially concentrated or changes
    # noticeably between periods; otherwise they should not force a prose block.
    importance = 45 if total <= 5 else 48
    if facts.get("dominant_share", 0) >= 0.60:
        importance = max(importance, 65)
    if "period_comparison" in facts:
        changes = facts["period_comparison"].get("share_changes_pp", {}) or {}
        max_change = max((abs(float(v)) for v in changes.values()), default=0.0)
        importance = max(importance, 68 if max_change >= 5.0 else 55)
    return _f("status_structure", "statuses", importance, facts=facts)


def _product_finding(ctx: AnalyticsContext) -> AnalyticalFinding | None:
    frame = ctx.product_progress
    if frame is None or frame.empty:
        return None
    data = frame.copy()
    if "Унікальних_заходів" in data.columns:
        data["_portfolio"] = pd.to_numeric(data["Унікальних_заходів"], errors="coerce").fillna(0)
    else:
        data["_portfolio"] = 0
    data["_exec"] = _numeric_col(data, "Виконання")
    data["_problems"] = _numeric_col(data, "Проблемних", 0).fillna(0)
    data["_missing"] = _numeric_col(data, "Без_даних", 0).fillna(0)
    ranked = data.sort_values("_portfolio", ascending=False)
    top = ranked.iloc[0]
    facts: dict[str, Any] = {
        "count": len(data), "largest_label": _label_for(data, top, "product"), "largest_size": int(top["_portfolio"]),
        "total_size": int(data["_portfolio"].sum()),
        "problem_total": int(data["_problems"].sum()), "missing_total": int(data["_missing"].sum()),
    }
    if facts["total_size"]:
        facts["largest_share"] = facts["largest_size"] / facts["total_size"]
    valid = data.dropna(subset=["_exec"])
    if len(valid) >= 2:
        best = valid.loc[valid["_exec"].idxmax()]; worst = valid.loc[valid["_exec"].idxmin()]
        facts.update({"best_label": _label_for(valid, best, "product"), "best_value": float(best["_exec"]),
                      "worst_label": _label_for(valid, worst, "product"), "worst_value": float(worst["_exec"]),
                      "gap": float(best["_exec"] - worst["_exec"])})
    if facts["problem_total"] > 0:
        top_problem = data.loc[data["_problems"].idxmax()]
        count = int(top_problem["_problems"])
        facts.update({
            "top_problem_label": _label_for(data, top_problem, "product"), "top_problem_count": count,
            "top_problem_share": count / facts["problem_total"],
        })
    if facts["missing_total"] > 0:
        top_missing = data.loc[data["_missing"].idxmax()]
        count = int(top_missing["_missing"])
        facts.update({
            "top_missing_label": _label_for(data, top_missing, "product"), "top_missing_count": count,
            "top_missing_share": count / facts["missing_total"],
        })
    importance = 60 if facts.get("problem_total") or facts.get("missing_total") else 48
    return _f("product_structure", "products", importance, facts=facts)


def _yoy_finding(ctx: AnalyticsContext) -> AnalyticalFinding | None:
    frame = ctx.yoy_comparison
    if frame is None or frame.empty:
        return None

    if "Період порівняння" in frame.columns:
        pairs = [str(x) for x in frame["Період порівняння"].dropna().drop_duplicates().tolist()]
    else:
        pairs = [""]

    comparisons: list[dict[str, Any]] = []
    for pair in pairs:
        data = frame[frame["Період порівняння"].astype(str).eq(pair)].copy() if "Період порівняння" in frame.columns else frame.copy()
        metrics: dict[str, dict[str, Any]] = {}
        for _, row in data.iterrows():
            label = _safe_str(row.get("Показник"))
            if not label:
                continue
            metrics[label] = {
                "previous": _num(row.get("Попередній рік")), "current": _num(row.get("Поточний рік")),
                "change": _num(row.get("Зміна")), "unit": _safe_str(row.get("Одиниця")),
            }
        comparisons.append({"comparison": pair, "metrics": metrics})

    if not comparisons:
        return None

    latest = comparisons[-1]
    facts: dict[str, Any] = {
        "comparison": latest["comparison"], "metrics": latest["metrics"],
        "comparisons": comparisons, "pair_count": len(comparisons),
    }

    def _direction(metrics: dict[str, dict[str, Any]]) -> tuple[int, int]:
        execution = metrics.get("Рівень виконання СП", {}).get("change")
        coverage = metrics.get("Покриття моніторингом", {}).get("change")
        problems = metrics.get("Проблемні / ризикові", {}).get("change")
        missing = metrics.get("Без поданих погоджених даних", {}).get("change")
        positive = sum(x is not None and x > 0 for x in (execution, coverage)) + sum(x is not None and x < 0 for x in (problems, missing))
        negative = sum(x is not None and x < 0 for x in (execution, coverage)) + sum(x is not None and x > 0 for x in (problems, missing))
        return positive, negative

    if len(comparisons) > 1:
        execution_changes = [
            comp["metrics"].get("Рівень виконання СП", {}).get("change") for comp in comparisons
            if comp["metrics"].get("Рівень виконання СП", {}).get("change") is not None
        ]
        coverage_changes = [
            comp["metrics"].get("Покриття моніторингом", {}).get("change") for comp in comparisons
            if comp["metrics"].get("Покриття моніторингом", {}).get("change") is not None
        ]
        facts["execution_changes"] = execution_changes
        facts["coverage_changes"] = coverage_changes
        if execution_changes and all(x > 0 for x in execution_changes):
            code, polarity = "yoy_multi_continuous_improvement", "positive"
        elif execution_changes and all(x < 0 for x in execution_changes):
            code, polarity = "yoy_multi_continuous_deterioration", "negative"
        elif execution_changes and any(x > 0 for x in execution_changes) and any(x < 0 for x in execution_changes):
            code, polarity = "yoy_multi_reversal", "warning"
        else:
            directions = [_direction(comp["metrics"]) for comp in comparisons]
            if any(p and n for p, n in directions):
                code, polarity = "yoy_multi_mixed", "warning"
            else:
                code, polarity = "yoy_multi_limited", "neutral"
        return _f(code, "yoy", 88, polarity, facts=facts, question="what_changed_yoy")

    metrics = latest["metrics"]
    positive, negative = _direction(metrics)
    if positive and negative:
        code, polarity = "yoy_mixed_change", "warning"
    elif positive:
        code, polarity = "yoy_broad_improvement", "positive"
    elif negative:
        code, polarity = "yoy_broad_deterioration", "negative"
    else:
        code, polarity = "yoy_limited_change", "neutral"
    return _f(code, "yoy", 78, polarity, facts=facts, question="what_changed_yoy")

def _active_group_counts(ctx: AnalyticsContext, group_col: str) -> pd.DataFrame:
    data = ctx.active.copy()
    if data.empty or group_col not in data.columns:
        return pd.DataFrame()
    key = data[group_col].fillna("").astype(str)
    data = data.assign(_group=key)
    data = data[data["_group"].str.strip().ne("")]
    if data.empty:
        return pd.DataFrame()
    problem = data.get("is_problem_status", pd.Series(False, index=data.index)).fillna(False).astype(bool)
    missing = data.get("missing_required_submission", pd.Series(False, index=data.index)).fillna(False).astype(bool)
    rows = []
    for label, group in data.groupby("_group", dropna=False):
        ix = group.index
        rows.append({"label": label, "rows": len(group), "measures": group.get("code", pd.Series(index=group.index, dtype=object)).nunique(),
                     "problems": int(problem.loc[ix].sum()), "missing": int(missing.loc[ix].sum())})
    return pd.DataFrame(rows)


def _goal_drilldown(ctx: AnalyticsContext) -> AnalyticalFinding | None:
    if ctx.sample_size <= 1:
        return None
    gp = ctx.goal_progress.copy()
    if gp.empty or "goal_code" not in gp.columns:
        return None
    # Prefer the entity that combines a low canonical execution with many problem records.
    gp["_exec"] = _numeric_col(gp, "Виконання")
    gp["_problem"] = _numeric_col(gp, "Проблемних", 0).fillna(0)
    valid = gp[gp["_exec"].notna()].copy()
    if valid.empty:
        return None
    valid["_rank"] = (100 - valid["_exec"].clip(0, 100)) + valid["_problem"] * 2
    focus = valid.sort_values("_rank", ascending=False).iloc[0]
    goal_code = _safe_str(focus.get("goal_code"))
    active = ctx.active.copy()
    if active.empty or "goal_code" not in active.columns or "task_code" not in active.columns:
        return None
    subset = active[active["goal_code"].astype(str).eq(goal_code)].copy()
    if subset.empty:
        return None
    problem = subset.get("is_problem_status", pd.Series(False, index=subset.index)).fillna(False).astype(bool)
    missing = subset.get("missing_required_submission", pd.Series(False, index=subset.index)).fillna(False).astype(bool)
    task_name_map = subset.groupby(subset["task_code"].astype(str))["task_name"].first().to_dict() if "task_name" in subset.columns else {}
    rows = []
    for task, group in subset.groupby(subset["task_code"].astype(str)):
        ix = group.index
        rows.append({"task": task, "name": _safe_str(task_name_map.get(task)), "rows": len(group),
                     "problems": int(problem.loc[ix].sum()), "missing": int(missing.loc[ix].sum())})
    table = pd.DataFrame(rows)
    if table.empty:
        return None
    table["attention"] = table["problems"] + table["missing"]
    ranked = table.sort_values(["attention", "problems", "missing"], ascending=False)
    total_attention = int(table["attention"].sum())
    if total_attention <= 0:
        return None
    top2 = ranked.head(2)
    top2_attention = int(top2["attention"].sum())
    facts = {
        "goal_label": f"СЦ {goal_code}", "goal_execution": _num(focus.get("Виконання")),
        "task_count": len(table), "total_attention_records": total_attention,
        "top_tasks": [(f"{r['task']} — {r['name']}" if r['name'] else r['task'], int(r["problems"]), int(r["missing"])) for _, r in ranked.head(3).iterrows()],
        "top2_attention": top2_attention, "top2_attention_share": top2_attention / total_attention if total_attention else None,
    }
    return _f("goal_drilldown", "tasks", 83, "negative" if total_attention else "neutral", facts=facts, question="which_tasks_localise_deviation")


def _ssp_drilldown(ctx: AnalyticsContext) -> AnalyticalFinding | None:
    if ctx.sample_size <= 1:
        return None
    dp = ctx.department_progress.copy()
    if dp.empty:
        return None
    dp["_exec"] = _numeric_col(dp, "Виконання")
    dp["_contrib"] = _numeric_col(dp, "underperformance_contribution_pct", 0).fillna(0)
    dp["_weight"] = _numeric_col(dp, "portfolio_weight_pct", 0).fillna(0)
    dp["_problem"] = _numeric_col(dp, "Проблемних", 0).fillna(0)
    valid = dp[dp["_exec"].notna()].copy()
    if valid.empty:
        return None
    # Internal ranking only: prioritises what to describe, does not alter an official KPI.
    valid["_priority"] = valid["_contrib"] * 1.5 + valid["_weight"] * 0.35 + valid["_problem"] * 1.5 + (100 - valid["_exec"].clip(0, 100)) * 0.25
    focus = valid.sort_values("_priority", ascending=False).iloc[0]
    department = _label_for(valid, focus, "department")
    if not department:
        return None
    overall = _num(ctx.metric("completion"))
    has_issue = (
        _int(focus.get("Проблемних")) > 0 or _int(focus.get("Без_даних")) > 0
        or (_num(focus.get("underperformance_contribution_pct")) or 0) > 0
        or (overall is not None and _num(focus.get("Виконання")) is not None and float(focus.get("Виконання")) < overall - 2)
    )
    if not has_issue:
        return None
    active = ctx.active.copy()
    dep_col = "department" if "department" in active.columns else None
    if active.empty or dep_col is None:
        return None
    subset = active[active[dep_col].astype(str).eq(department)].copy()
    if subset.empty:
        return None
    problem = subset.get("is_problem_status", pd.Series(False, index=subset.index)).fillna(False).astype(bool)
    missing = subset.get("missing_required_submission", pd.Series(False, index=subset.index)).fillna(False).astype(bool)
    rows = []
    if "task_code" in subset.columns:
        for task, group in subset.groupby(subset["task_code"].astype(str)):
            ix = group.index
            rows.append({"task": task, "problems": int(problem.loc[ix].sum()), "missing": int(missing.loc[ix].sum()), "rows": len(group)})
    table = pd.DataFrame(rows)
    facts = {
        "department": department, "execution": _num(focus.get("Виконання")),
        "portfolio_weight": _num(focus.get("portfolio_weight_pct")),
        "underperformance_contribution": _num(focus.get("underperformance_contribution_pct")),
        "risk_contribution": _num(focus.get("risk_contribution_pct")),
        "problem_count": _int(focus.get("Проблемних")), "missing_count": _int(focus.get("Без_даних")),
    }
    if not table.empty:
        table["attention"] = table["problems"] + table["missing"]
        ranked = table.sort_values("attention", ascending=False).head(3)
        total = int(table["attention"].sum())
        facts["top_tasks"] = [(r["task"], int(r["problems"]), int(r["missing"])) for _, r in ranked.iterrows() if int(r["attention"]) > 0]
        facts["top_tasks_attention_share"] = int(ranked["attention"].sum()) / total if total else None
    return _f("ssp_drilldown", "departments", 90, "negative", facts=facts, question="which_ssp_matter_by_scale")


def _ssp_portfolio_findings(ctx: AnalyticsContext) -> list[AnalyticalFinding]:
    dp = ctx.department_progress.copy()
    if dp.empty:
        return []
    required = {"portfolio_weight_pct", "underperformance_contribution_pct"}
    if not required.intersection(dp.columns):
        return []
    dp["_weight"] = _numeric_col(dp, "portfolio_weight_pct")
    dp["_under"] = _numeric_col(dp, "underperformance_contribution_pct")
    dp["_exec"] = _numeric_col(dp, "Виконання")
    valid = dp.dropna(subset=["_weight"]).copy()
    if valid.empty:
        return []
    largest = valid.loc[valid["_weight"].idxmax()]
    facts = {
        "largest_department": _label_for(valid, largest, "department"), "largest_weight": _num(largest.get("portfolio_weight_pct")),
        "largest_execution": _num(largest.get("Виконання")), "largest_underperformance_contribution": _num(largest.get("underperformance_contribution_pct")),
    }
    under = dp.dropna(subset=["_under"]).copy()
    if not under.empty:
        top = under.loc[under["_under"].idxmax()]
        top_under = _num(top.get("underperformance_contribution_pct"))
        top_weight = _num(top.get("portfolio_weight_pct"))
        facts.update({"top_underperformance_department": _label_for(under, top, "department"),
                      "top_underperformance_contribution": top_under,
                      "top_underperformance_weight": top_weight,
                      "top_underperformance_execution": _num(top.get("Виконання")),
                      "top_underperformance_excess_pp": (top_under - top_weight) if top_under is not None and top_weight is not None else None})
    return [_f("ssp_portfolio_impact", "departments", 92, "warning", facts=facts, question="which_ssp_matter_by_scale")]


def _risk_finding(ctx: AnalyticsContext) -> AnalyticalFinding | None:
    summary = ctx.metric("latest_risk_summary") or {}
    if not isinstance(summary, dict) or not summary:
        return None
    facts = {
        "assessed_count": _int(summary.get("risk_assessed_count")),
        "high_critical_share": _num(summary.get("share_high_critical_risk")),
        "without_substantial_risk_share": _num(summary.get("share_without_substantial_risk")),
        "results_achieved_share": _num(summary.get("share_results_achieved")),
    }
    dp = ctx.department_progress.copy()
    if not dp.empty and "risk_contribution_pct" in dp.columns:
        values = pd.to_numeric(dp["risk_contribution_pct"], errors="coerce")
        if values.notna().any():
            idx = values.idxmax(); row = dp.loc[idx]
            facts["top_risk_department"] = _label_for(dp, row, "department")
            facts["top_risk_contribution"] = _num(row.get("risk_contribution_pct"))
            facts["top_risk_portfolio_weight"] = _num(row.get("portfolio_weight_pct"))
            if facts["top_risk_contribution"] is not None and facts["top_risk_portfolio_weight"] is not None:
                facts["top_risk_excess_pp"] = facts["top_risk_contribution"] - facts["top_risk_portfolio_weight"]
    if not any(is_number(v) for v in facts.values() if not isinstance(v, str)) and not facts.get("top_risk_department"):
        return None
    return _f("risk_structure", "risk", 82, "warning", facts=facts)


def _execution_divergence_finding(ctx: AnalyticsContext) -> AnalyticalFinding | None:
    measures = _num(ctx.metric("completion")); goals = _num(ctx.metric("goal_completion"))
    latest_measures = _num(ctx.metric("completion_latest")); latest_goals = _num(ctx.metric("goal_completion_latest"))
    if measures is None or goals is None:
        return None
    gap = measures - goals
    latest_gap = (latest_measures - latest_goals) if latest_measures is not None and latest_goals is not None else None
    if abs(gap) < 2 and (latest_gap is None or abs(latest_gap) < 2):
        return _f("execution_goal_alignment", "general", 45, "neutral", facts={
            "measure_execution": measures, "goal_execution": goals, "gap": gap,
            "latest_measure_execution": latest_measures, "latest_goal_execution": latest_goals, "latest_gap": latest_gap,
        })
    return _f("execution_goal_divergence", "general", 86, "warning", facts={
        "measure_execution": measures, "goal_execution": goals, "gap": gap,
        "latest_measure_execution": latest_measures, "latest_goal_execution": latest_goals, "latest_gap": latest_gap,
    })


def _persistent_descriptive_findings(ctx: AnalyticsContext) -> list[AnalyticalFinding]:
    data = ctx.active.copy()
    if data.empty or "report_year" not in data.columns or "report_quarter" not in data.columns:
        return []
    period_key = data["report_year"].astype(str) + " " + data["report_quarter"].astype(str)
    data = data.assign(_period=period_key)
    if data["_period"].nunique() < 3:
        return []
    problem = data.get("is_problem_status", pd.Series(False, index=data.index)).fillna(False).astype(bool)
    missing = data.get("missing_required_submission", pd.Series(False, index=data.index)).fillna(False).astype(bool)
    output: list[AnalyticalFinding] = []
    for col, kind, label_fn in (("goal_code", "goal", lambda x: f"СЦ {x}"), ("department", "department", lambda x: f"ССП «{x}»")):
        if col not in data.columns:
            continue
        rows=[]
        for label, group in data.groupby(data[col].fillna("").astype(str)):
            if not str(label).strip(): continue
            p_periods = 0; m_periods = 0
            for _, pg in group.groupby("_period"):
                ix=pg.index
                if int(problem.loc[ix].sum()) > 0: p_periods += 1
                if int(missing.loc[ix].sum()) > 0: m_periods += 1
            rows.append((label, p_periods, m_periods, group["_period"].nunique()))
        if not rows: continue
        top_problem=max(rows,key=lambda x:x[1]); top_missing=max(rows,key=lambda x:x[2])
        if top_problem[1] >= 3:
            output.append(_f(f"persistent_{kind}_problems", "problems", 78, "negative", facts={
                "label": label_fn(top_problem[0]), "periods_with_problem": top_problem[1], "periods_observed": top_problem[3]
            }))
        if top_missing[2] >= 3:
            output.append(_f(f"persistent_{kind}_missing", "missing", 76, "warning", facts={
                "label": label_fn(top_missing[0]), "periods_with_missing": top_missing[2], "periods_observed": top_missing[3]
            }))
    return output


def _conflict_findings(ctx: AnalyticsContext, findings: list[AnalyticalFinding], signals: list[Signal]) -> list[AnalyticalFinding]:
    codes = {s.code for s in signals}
    result: list[AnalyticalFinding] = []
    trajectory = next((f for f in findings if f.topic == "dynamics" and "cumulative_delta" in f.facts), None)
    goal_change = next((f for f in findings if f.code.startswith("goal_change_")), None)
    if trajectory:
        ex_delta = _num(trajectory.facts.get("cumulative_delta"))
        cov_delta = _num(trajectory.facts.get("coverage_cumulative_delta"))
        if ex_delta is not None and ex_delta > 0 and cov_delta is not None and cov_delta < 0:
            result.append(_f("conflict_execution_up_coverage_down", "conflict", 98, "warning", facts={"execution_delta": ex_delta, "coverage_delta": cov_delta}, question="are_signals_conflicting"))
        if ex_delta is not None and ex_delta < 0 and cov_delta is not None and cov_delta > 0:
            result.append(_f("conflict_execution_down_coverage_up", "conflict", 96, "negative", facts={"execution_delta": ex_delta, "coverage_delta": cov_delta}, question="are_signals_conflicting"))
    if "execution_up_problems_up" in codes:
        yoy_problem = next((sig for sig in signals if sig.code == "yoy_problem_increased"), None)
        result.append(_f("conflict_execution_up_problems_up", "conflict", 96, "warning", facts={
            "problem_count": _int(ctx.metric("problem")),
            "problem_change": _num(yoy_problem.values.get("delta")) if yoy_problem else None,
        }, source_signals=("execution_up_problems_up",), question="are_signals_conflicting"))
    # Aggregate stability can hide strong internal movement.
    if trajectory and goal_change:
        cumulative = abs(float(trajectory.facts.get("cumulative_delta") or 0))
        largest_up = abs(float(goal_change.facts.get("largest_improvement") or 0))
        largest_down = abs(float(goal_change.facts.get("largest_deterioration") or 0))
        if cumulative < 2 and max(largest_up, largest_down) >= 7 and goal_change.facts.get("improved", 0) and goal_change.facts.get("declined", 0):
            result.append(_f("stable_aggregate_hidden_internal_movement", "conflict", 99, "warning", facts={
                "aggregate_delta": trajectory.facts.get("cumulative_delta"),
                "largest_improvement_label": goal_change.facts.get("largest_improvement_label"), "largest_improvement": goal_change.facts.get("largest_improvement"),
                "largest_deterioration_label": goal_change.facts.get("largest_deterioration_label"), "largest_deterioration": goal_change.facts.get("largest_deterioration"),
                "improved": goal_change.facts.get("improved"), "declined": goal_change.facts.get("declined"),
            }, question="are_signals_conflicting"))
    return result


def _management_priorities(ctx: AnalyticsContext) -> AnalyticalFinding | None:
    if ctx.sample_size <= 1:
        return None
    candidates: list[dict[str, Any]] = []
    overall = _num(ctx.metric("completion"))
    # Goals: descriptive priority using only canonical execution and descriptive counts.
    gp = ctx.goal_progress.copy()
    if not gp.empty:
        gp["_exec"] = _numeric_col(gp, "Виконання")
        gp["_change"] = _numeric_col(gp, "Зміна", 0).fillna(0)
        gp["_problem"] = _numeric_col(gp, "Проблемних", 0).fillna(0)
        gp["_missing"] = _numeric_col(gp, "Без_даних", 0).fillna(0)
        for _, row in gp.iterrows():
            if pd.isna(row["_exec"]):
                continue
            is_attention = float(row["_problem"]) > 0 or float(row["_missing"]) > 0 or float(row["_change"]) < -2 or (overall is not None and float(row["_exec"]) < overall - 2)
            if is_attention:
                score = (100 - float(row["_exec"])) * 0.35 + max(0, -float(row["_change"])) * 1.1 + float(row["_problem"]) * 2 + float(row["_missing"]) * 1.3
                candidates.append({"kind": "goal", "label": _label_for(gp, row, "goal"), "score": score,
                                   "execution": float(row["_exec"]), "change": float(row["_change"]), "problems": int(row["_problem"]), "missing": int(row["_missing"])})
    # SSP: canonical portfolio weight and underperformance contribution make this stronger.
    dp = ctx.department_progress.copy()
    if not dp.empty:
        dp["_exec"] = _numeric_col(dp, "Виконання")
        dp["_change"] = _numeric_col(dp, "Зміна", 0).fillna(0)
        dp["_problem"] = _numeric_col(dp, "Проблемних", 0).fillna(0)
        dp["_missing"] = _numeric_col(dp, "Без_даних", 0).fillna(0)
        dp["_weight"] = _numeric_col(dp, "portfolio_weight_pct", 0).fillna(0)
        dp["_under"] = _numeric_col(dp, "underperformance_contribution_pct", 0).fillna(0)
        for _, row in dp.iterrows():
            if pd.isna(row["_exec"]):
                continue
            is_attention = float(row["_problem"]) > 0 or float(row["_missing"]) > 0 or float(row["_change"]) < -2 or float(row["_under"]) > 0 or (overall is not None and float(row["_exec"]) < overall - 2)
            if is_attention:
                score = (100 - float(row["_exec"])) * 0.20 + max(0, -float(row["_change"])) + float(row["_problem"]) * 1.5 + float(row["_missing"]) + float(row["_weight"]) * 0.25 + float(row["_under"]) * 0.8
                candidates.append({"kind": "department", "label": _label_for(dp, row, "department"), "score": score,
                                   "execution": float(row["_exec"]), "change": float(row["_change"]), "problems": int(row["_problem"]), "missing": int(row["_missing"]),
                                   "portfolio_weight": float(row["_weight"]), "underperformance_contribution": float(row["_under"])})
    candidates = [c for c in candidates if c["label"]]
    if not candidates:
        return None
    ranked = sorted(candidates, key=lambda x: (-x["score"], x["kind"], x["label"]))[:5]
    # Score is deliberately omitted from public facts; it is only an internal sorter.
    public = [{k: v for k, v in c.items() if k != "score"} for c in ranked]
    return _f("management_priorities", "management_attention", 100, "warning", facts={"priorities": public}, question="what_requires_management_attention")



def _mio_findings(ctx: AnalyticsContext) -> list[AnalyticalFinding]:
    """Interpret reusable MіO outputs without changing the MіO methodology."""
    out: list[AnalyticalFinding] = []
    goals = ctx.mio_goal_evaluation.copy() if ctx.mio_goal_evaluation is not None else pd.DataFrame()
    years = sorted({int(y) for y in (ctx.filters.get("years", []) or []) if str(y).isdigit()})
    year = max(years) if years else 2026
    int_col, meas_col, task_col, prog_col = (f"Інтеграл {year}", f"Заходи {year}", f"Завдання {year}", f"Прогрес {year}")
    if not goals.empty and int_col in goals.columns:
        frame = goals.copy()
        for c in (int_col, meas_col, task_col, prog_col):
            if c in frame.columns:
                frame[c] = pd.to_numeric(frame[c], errors="coerce")
        valid = frame.dropna(subset=[int_col]).copy()
        if not valid.empty:
            best = valid.sort_values(int_col, ascending=False).iloc[0]
            worst = valid.sort_values(int_col, ascending=True).iloc[0]
            facts = {
                "year": year, "goals_count": int(len(valid)),
                "average_integral": float(valid[int_col].mean()),
                "best_code": str(best.get("Код", "")), "best_name": str(best.get("Ціль", "")), "best_integral": float(best[int_col]),
                "worst_code": str(worst.get("Код", "")), "worst_name": str(worst.get("Ціль", "")), "worst_integral": float(worst[int_col]),
                "gap": float(best[int_col] - worst[int_col]),
            }
            if meas_col in valid.columns: facts["average_measures"] = float(valid[meas_col].dropna().mean()) if valid[meas_col].notna().any() else None
            if task_col in valid.columns: facts["average_tasks"] = float(valid[task_col].dropna().mean()) if valid[task_col].notna().any() else None
            if prog_col in valid.columns: facts["average_progress"] = float(valid[prog_col].dropna().mean()) if valid[prog_col].notna().any() else None
            divergences=[]
            for _, row in valid.iterrows():
                m=row.get(meas_col) if meas_col in valid.columns else None; integ=row.get(int_col); prog=row.get(prog_col) if prog_col in valid.columns else None
                if pd.notna(m) and pd.notna(integ):
                    gap=float(m)-float(integ)
                    if abs(gap)>=10:
                        divergences.append({"code":str(row.get("Код","")),"name":str(row.get("Ціль","")),"measure_execution":float(m),"integral":float(integ),"gap":gap,"progress":float(prog) if pd.notna(prog) else None})
            facts["divergences"] = sorted(divergences, key=lambda x: abs(x["gap"]), reverse=True)[:4]
            out.append(_f("mio_integral_profile", "mio", 94, "neutral", facts=facts, question="how_does_execution_translate_to_strategic_result"))
            if divergences:
                out.append(_f("mio_execution_result_divergence", "mio", 96, "warning", facts={"year":year,"items":facts["divergences"]}, question="where_does_measure_execution_not_translate_to_result"))
    # Task-level MIO indicators: compare indicator progress with monitoring
    # execution only when both are available for the same task code.
    gt = ctx.mio_goal_task_evaluation.copy() if ctx.mio_goal_task_evaluation is not None else pd.DataFrame()
    score_col = f"Оцінка {year}"
    if not gt.empty and {"Рівень", "Код", score_col}.issubset(gt.columns):
        tasks = gt[gt["Рівень"].astype(str).eq("task")].copy()
        tasks[score_col] = pd.to_numeric(tasks[score_col], errors="coerce")
        task_scores = tasks.groupby(tasks["Код"].astype(str))[score_col].mean().dropna()
        if not task_scores.empty:
            facts = {
                "year": year, "tasks_count": int(len(task_scores)),
                "average_task_indicator_progress": float(task_scores.mean()),
                "best_task": str(task_scores.idxmax()), "best_task_progress": float(task_scores.max()),
                "worst_task": str(task_scores.idxmin()), "worst_task_progress": float(task_scores.min()),
                "gap": float(task_scores.max() - task_scores.min()),
            }
            divergences=[]
            tp = ctx.task_progress.copy() if ctx.task_progress is not None else pd.DataFrame()
            if not tp.empty and "task_code" in tp.columns and "Виконання" in tp.columns:
                tp = tp.copy(); tp["_code"] = tp["task_code"].astype(str); tp["_exec"] = pd.to_numeric(tp["Виконання"], errors="coerce")
                execution_by_task = tp.dropna(subset=["_exec"]).groupby("_code")["_exec"].mean()
                for code, progress in task_scores.items():
                    if code in execution_by_task.index:
                        execution=float(execution_by_task.loc[code]); gap=execution-float(progress)
                        if abs(gap) >= 10:
                            divergences.append({"code":code,"execution":execution,"indicator_progress":float(progress),"gap":gap})
            facts["divergences"] = sorted(divergences, key=lambda x: abs(x["gap"]), reverse=True)[:4]
            out.append(_f("mio_task_indicator_profile", "mio", 86, "neutral", facts=facts, question="how_do_task_results_compare_with_execution"))
            if divergences:
                out.append(_f("mio_task_execution_result_divergence", "mio", 92, "warning", facts={"year":year,"items":facts["divergences"]}, question="where_do_task_indicators_diverge_from_execution"))

    measures = ctx.mio_measure_evaluation.copy() if ctx.mio_measure_evaluation is not None else pd.DataFrame()
    if not measures.empty and "Факт/План, %" in measures.columns:
        ratios = pd.to_numeric(measures["Факт/План, %"], errors="coerce").dropna()
        if not ratios.empty:
            out.append(_f("mio_measure_profile", "mio", 72, "neutral", facts={
                "year":year, "measures_count":int(len(measures)), "evaluated_measures":int(len(ratios)),
                "average_fact_plan":float(ratios.mean()), "median_fact_plan":float(ratios.median()),
            }, question="what_is_measure_level_mio_result"))

    fin = ctx.mio_financing.copy() if ctx.mio_financing is not None else pd.DataFrame()
    if not fin.empty:
        for c in ("% виконання", "Стан виконання заходу, %", "План, млрд грн", "Факт, млрд грн", "Коефіцієнт еластичності"):
            if c in fin.columns: fin[c]=pd.to_numeric(fin[c], errors="coerce")
        paired=fin.dropna(subset=[c for c in ["% виконання","Стан виконання заходу, %"] if c in fin.columns]).copy() if all(c in fin.columns for c in ["% виконання","Стан виконання заходу, %"]) else pd.DataFrame()
        facts={"rows":int(len(fin)),"plan_total":float(fin["План, млрд грн"].sum()) if "План, млрд грн" in fin.columns and fin["План, млрд грн"].notna().any() else None,"fact_total":float(fin["Факт, млрд грн"].sum()) if "Факт, млрд грн" in fin.columns and fin["Факт, млрд грн"].notna().any() else None}
        if not paired.empty:
            paired["_gap"]=paired["% виконання"]-paired["Стан виконання заходу, %"]
            facts["paired_count"]=int(len(paired)); facts["avg_financial_execution"]=float(paired["% виконання"].mean()); facts["avg_physical_execution"]=float(paired["Стан виконання заходу, %"].mean())
            facts["largest_gaps"]=paired.assign(_abs=paired["_gap"].abs()).sort_values("_abs",ascending=False).head(4)[[c for c in ["Захід","Назва заходу","% виконання","Стан виконання заходу, %","_gap"] if c in paired.columns or c=="_gap"]].to_dict("records")
        out.append(_f("mio_financing_profile", "mio", 78, "neutral", facts=facts, question="how_does_financing_compare_with_physical_result"))
    return out

def derive_findings(ctx: AnalyticsContext, signals: list[Signal]) -> tuple[list[AnalyticalQuestion], list[AnalyticalFinding]]:
    """Close the analytical loop using all dimensions already available in context."""
    questions = list(QUESTIONS)
    findings: list[AnalyticalFinding] = []
    execution = _num(ctx.metric("completion"))
    coverage = _num(ctx.metric("coverage"))
    findings.append(_f("scope_profile", "scope", 25, facts={
        "rows": ctx.row_count, "measures": ctx.sample_size, "goals": _int(ctx.metric("goals")), "tasks": _int(ctx.metric("tasks")),
        "departments": int(len(ctx.department_progress)) if ctx.department_progress is not None else 0,
        "products": int(len(ctx.product_progress)) if ctx.product_progress is not None else 0,
        "years": list(ctx.filters.get("years", []) or []), "quarters": list(ctx.filters.get("quarters", []) or []),
    }, question="what_is_scope"))
    findings.append(_f("overall_state", "general", 90, facts={
        "execution_average": execution, "coverage_average": coverage,
        "execution_latest": _num(ctx.metric("completion_latest")), "coverage_latest": _num(ctx.metric("coverage_latest")),
        "problem_count": _int(ctx.metric("problem")), "missing_count": _int(ctx.metric("no_data")), "completed_count": _int(ctx.metric("completed")),
    }, question="what_is_overall_state"))
    divergence = _execution_divergence_finding(ctx)
    if divergence: findings.append(divergence)
    findings.extend(_trajectory_finding(ctx))
    findings.extend(_distribution_findings(ctx.goal_progress, "goal", execution))
    findings.extend(_distribution_findings(ctx.task_progress, "task", execution))
    findings.extend(_distribution_findings(ctx.department_progress, "department", execution))
    for frame, kind in ((ctx.goal_progress, "goal"), (ctx.task_progress, "task"), (ctx.department_progress, "department")):
        item = _concentration_finding(frame, kind, "Проблемних", "problems", "where_are_problems")
        if item: findings.append(item)
        item = _concentration_finding(frame, kind, "Без_даних", "missing", "where_is_missing")
        if item: findings.append(item)
    status = _status_finding(ctx)
    if status: findings.append(status)
    risk = _risk_finding(ctx)
    if risk: findings.append(risk)
    findings.extend(_persistent_descriptive_findings(ctx))
    product = _product_finding(ctx)
    if product: findings.append(product)
    yoy = _yoy_finding(ctx)
    if yoy: findings.append(yoy)
    findings.extend(_ssp_portfolio_findings(ctx))
    gd = _goal_drilldown(ctx)
    if gd: findings.append(gd)
    sd = _ssp_drilldown(ctx)
    if sd: findings.append(sd)
    findings.extend(_conflict_findings(ctx, findings, signals))
    findings.extend(_mio_findings(ctx))
    mp = _management_priorities(ctx)
    if mp: findings.append(mp)

    # Deduplicate by code, keeping the highest-importance instance.
    strongest: dict[str, AnalyticalFinding] = {}
    for item in findings:
        if item.code not in strongest or item.importance > strongest[item.code].importance:
            strongest[item.code] = item
    ordered = sorted(strongest.values(), key=lambda item: (-item.importance, item.topic, item.code))
    return questions, ordered


SUPPORTED_FINDING_CODES = frozenset({
    # Dynamic codes are additionally generated by kind; keeping this registry broad
    # makes scenario validation possible without coupling it to test fixtures.
    "scope_profile", "overall_state", "trajectory_unavailable", "trajectory_single_period",
    "trajectory_continuous_growth", "trajectory_continuous_decline", "trajectory_plateau", "trajectory_recovery",
    "trajectory_reversal_negative", "trajectory_volatile", "trajectory_net_growth", "trajectory_net_decline", "trajectory_mixed_stable",
    "trajectory_late_acceleration", "trajectory_growth_slowing", "trajectory_decline_accelerating",
    "status_structure", "product_structure", "yoy_mixed_change", "yoy_broad_improvement", "yoy_broad_deterioration", "yoy_limited_change",
    "yoy_multi_continuous_improvement", "yoy_multi_continuous_deterioration", "yoy_multi_reversal", "yoy_multi_mixed", "yoy_multi_limited",
    "ssp_portfolio_impact", "goal_drilldown", "ssp_drilldown", "management_priorities",
    "risk_structure", "execution_goal_alignment", "execution_goal_divergence",
    "persistent_goal_problems", "persistent_goal_missing", "persistent_department_problems", "persistent_department_missing",
    "conflict_execution_up_coverage_down", "conflict_execution_down_coverage_up", "conflict_execution_up_problems_up",
    "stable_aggregate_hidden_internal_movement", "mio_integral_profile", "mio_execution_result_divergence",
    "mio_task_indicator_profile", "mio_task_execution_result_divergence", "mio_measure_profile", "mio_financing_profile",
} | {
    f"{kind}_{suffix}"
    for kind in ("goal", "task", "department")
    for suffix in (
        "single_entity", "distribution", "change_broad_positive", "change_broad_negative", "change_polarised", "change_positive", "change_negative", "change_stable",
        "problems_none", "problems_concentrated", "problems_localised", "problems_distributed",
        "missing_none", "missing_concentrated", "missing_localised", "missing_distributed",
    )
})
