from __future__ import annotations

"""Prepared factual registry for the deterministic Analytics narrative.

Only this layer may create user-facing numerical derivatives.  Every number
available to findings/composition is registered with source, aggregation and,
where relevant, an explicit observation unit.
"""

from dataclasses import dataclass, field
from statistics import pstdev
from typing import Any, Mapping

import pandas as pd


class MetricFloat(float):
    def __new__(cls, value: float, metric_code: str):
        obj = float.__new__(cls, value)
        obj.metric_code = metric_code
        return obj


class MetricInt(int):
    def __new__(cls, value: int, metric_code: str):
        obj = int.__new__(cls, value)
        obj.metric_code = metric_code
        return obj


def metric_code_of(value: Any) -> str | None:
    code = getattr(value, "metric_code", None)
    return str(code) if code else None


def bind_metric_value(metric: "FactualMetric") -> int | float:
    return MetricInt(int(metric.value), metric.code) if metric.unit == "count" else MetricFloat(float(metric.value), metric.code)


@dataclass(frozen=True)
class FactualMetric:
    code: str
    value: float | int
    unit: str
    source: str
    aggregation: str
    numerator: float | int | None = None
    denominator: float | int | None = None
    dependencies: tuple[str, ...] = ()
    scope: Mapping[str, Any] = field(default_factory=dict)
    allow_over_100: bool = False
    observation_unit: str | None = None


@dataclass(frozen=True)
class PreparedAnalyticalFacts:
    metrics: Mapping[str, FactualMetric]
    structures: Mapping[str, Any]

    def value(self, code: str, default: Any = None) -> Any:
        item = self.metrics.get(code)
        return bind_metric_value(item) if item is not None else default

    def metric(self, code: str) -> FactualMetric | None:
        return self.metrics.get(code)


class _Builder:
    def __init__(self, scope: Mapping[str, Any]):
        self.scope = dict(scope)
        self.metrics: dict[str, FactualMetric] = {}
        self.structures: dict[str, Any] = {}

    def add(
        self, code: str, value: Any, *, unit: str, source: str, aggregation: str,
        numerator: Any = None, denominator: Any = None, dependencies: tuple[str, ...] = (),
        allow_over_100: bool = False, observation_unit: str | None = None,
    ) -> Any:
        if value is None or isinstance(value, bool):
            return None
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            return None
        try:
            number = int(value) if unit == "count" else float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if unit == "percent" and not allow_over_100 and not 0.0 <= float(number) <= 100.0:
            raise ValueError(f"Analytical metric {code} outside 0..100%: {number}")
        if denominator is not None and float(denominator) <= 0:
            raise ValueError(f"Analytical metric {code} has non-positive denominator: {denominator}")
        metric = FactualMetric(
            code=code, value=number, unit=unit, source=source, aggregation=aggregation,
            numerator=numerator, denominator=denominator, dependencies=dependencies,
            scope=self.scope, allow_over_100=allow_over_100, observation_unit=observation_unit,
        )
        self.metrics[code] = metric
        return bind_metric_value(metric)

    def ratio_pct(
        self, code: str, numerator: Any, denominator: Any, *, source: str, aggregation: str,
        numerator_unit: str, denominator_unit: str, dependencies: tuple[str, ...] = (),
    ) -> float | None:
        if numerator_unit != denominator_unit:
            raise ValueError(f"Incompatible units for {code}: {numerator_unit} / {denominator_unit}")
        try:
            num, den = float(numerator), float(denominator)
        except (TypeError, ValueError):
            return None
        if den <= 0:
            return None
        return self.add(
            code, num / den * 100.0, unit="percent", source=source, aggregation=aggregation,
            numerator=numerator, denominator=denominator, dependencies=dependencies,
            observation_unit=numerator_unit,
        )

    def pp(self, code: str, left: Any, right: Any, *, source: str, aggregation: str,
           dependencies: tuple[str, ...] = ()) -> float | None:
        try:
            value = float(left) - float(right)
        except (TypeError, ValueError):
            return None
        return self.add(code, value, unit="pp", source=source, aggregation=aggregation, dependencies=dependencies)


def _safe_number(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _safe_int(value: Any) -> int:
    number = _safe_number(value)
    return 0 if number is None else int(number)


def _numeric(frame: pd.DataFrame, column: str, default: float | None = None) -> pd.Series:
    if frame is not None and column in frame.columns:
        return pd.to_numeric(frame[column], errors="coerce")
    fill = float("nan") if default is None else default
    return pd.Series(fill, index=getattr(frame, "index", None), dtype=float)


def _label(row: pd.Series, kind: str) -> str:
    def text(v: Any) -> str:
        try:
            if v is None or pd.isna(v):
                return ""
        except (TypeError, ValueError):
            return ""
        return str(v).strip()
    if kind == "goal":
        code = text(row.get("goal_code"))
        return f"СЦ {code}" if code and not code.upper().startswith("СЦ") else code
    if kind == "task":
        code, name = text(row.get("task_code")), text(row.get("task_name"))
        return f"{code} — {name}" if code and name else (code or name)
    if kind == "department":
        return text(row.get("department")) or text(row.get("ssp_index"))
    if kind == "product":
        return text(row.get("product_type"))
    return ""


def _register_frame_sources(b: _Builder, name: str, frame: pd.DataFrame) -> None:
    if frame is None or frame.empty:
        return
    for pos, (_, row) in enumerate(frame.iterrows()):
        for column in frame.columns:
            value = _safe_number(row.get(column))
            if value is None:
                continue
            low = str(column).lower()
            if "зміна" in low or "delta" in low or "gap" in low or "excess" in low:
                unit = "pp"
            elif any(t in low for t in ("%", "виконання", "покриття", "share", "weight", "contribution", "прогрес", "інтеграл", "оцінка")):
                unit = "percent"
            elif any(t in low for t in ("кількість", "без_даних", "без даних", "актуальна_увага", "унікальних_заходів", "count", "rows")):
                unit = "count"
            else:
                unit = "number"
            observation = None
            if unit == "count":
                observation = "unique-measure" if any(t in low for t in ("актуальна_увага", "без_даних", "унікальних_заходів")) else None
            b.add(
                f"source.{name}.row{pos}.{column}", value, unit=unit,
                source=f"shared.{name}.{column}", aggregation="prepared source value",
                allow_over_100=(unit == "percent" and value > 100), observation_unit=observation,
            )


def _prepare_trajectory(b: _Builder, period: pd.DataFrame) -> None:
    if period is None or period.empty or "Виконання" not in period.columns:
        return
    qmap = {"I": 1, "II": 2, "III": 3, "IV": 4, "1": 1, "2": 2, "3": 3, "4": 4}
    d = period.copy()
    d["_year"] = pd.to_numeric(d.get("report_year"), errors="coerce")
    d["_q"] = d.get("report_quarter", pd.Series(index=d.index, dtype=object)).astype(str).map(qmap)
    d = d.sort_values(["_year", "_q"], na_position="last")
    d["_exec"] = _numeric(d, "Виконання")
    valid = d.dropna(subset=["_exec"]).copy()
    if valid.empty:
        return
    periods = [str(v).strip() for v in valid.get("Період", pd.Series(range(len(valid)))).tolist()]
    values = [b.add(f"trajectory.period.{i}.execution", v, unit="percent", source="dashboard.period_dynamics", aggregation=f"period {i} execution", allow_over_100=True) for i, v in enumerate(valid["_exec"].tolist())]
    facts: dict[str, Any] = {
        "period_count": b.add("trajectory.period_count", len(values), unit="count", source="dashboard.period_dynamics", aggregation="evaluated periods", observation_unit="period"),
        "periods": periods, "values": values, "first_period": periods[0], "last_period": periods[-1],
        "first": b.add("trajectory.first_execution", values[0], unit="percent", source="dashboard.period_dynamics", aggregation="first evaluated period execution", allow_over_100=True),
        "last": b.add("trajectory.last_execution", values[-1], unit="percent", source="dashboard.period_dynamics", aggregation="last evaluated period execution", allow_over_100=True),
    }
    if len(values) >= 2:
        deltas = [b.pp(f"trajectory.step.{i}.delta_pp", values[i], values[i - 1], source="dashboard.period_dynamics", aggregation="period over period delta") for i in range(1, len(values))]
        facts["deltas"] = deltas
        facts["cumulative_delta"] = b.pp("trajectory.cumulative_delta_pp", values[-1], values[0], source="dashboard.period_dynamics", aggregation="last evaluated minus first evaluated")
        facts["positive_steps"] = b.add("trajectory.positive_step_count", sum(float(x) > 0 for x in deltas), unit="count", source="analytics.derived.trajectory", aggregation="positive transitions", observation_unit="period-transition")
        facts["negative_steps"] = b.add("trajectory.negative_step_count", sum(float(x) < 0 for x in deltas), unit="count", source="analytics.derived.trajectory", aggregation="negative transitions", observation_unit="period-transition")
        facts["flat_steps"] = b.add("trajectory.flat_step_count", sum(abs(float(x)) < 0.5 for x in deltas), unit="count", source="analytics.derived.trajectory", aggregation="near-flat transitions", observation_unit="period-transition")
        if len(deltas) >= 2:
            facts["previous_delta"], facts["latest_delta"] = deltas[-2], deltas[-1]
        if len(values) >= 3:
            facts["volatility_stddev"] = b.add("trajectory.volatility_stddev_pp", pstdev(map(float, values)), unit="pp", source="analytics.derived.trajectory", aggregation="population stddev of evaluated period execution")
    # Coverage series keeps unavailable periods unavailable.  No synthetic zero.
    coverage = _numeric(d, "Покриття_%")
    if coverage.notna().any():
        cv = [None if pd.isna(v) else b.add(f"trajectory.coverage.{i}", float(v), unit="percent", source="dashboard.period_dynamics", aggregation=f"period {i} coverage") for i, v in enumerate(coverage.tolist())]
        facts["coverage_values"] = cv
        valid_cov = [(i, v) for i, v in enumerate(cv) if v is not None]
        if valid_cov:
            facts["coverage_first"] = valid_cov[0][1]
            facts["coverage_last"] = valid_cov[-1][1]
            if len(valid_cov) >= 2:
                facts["coverage_cumulative_delta"] = b.pp("trajectory.coverage_cumulative_delta_pp", valid_cov[-1][1], valid_cov[0][1], source="dashboard.period_dynamics", aggregation="last evaluated coverage minus first evaluated coverage")
    b.structures["trajectory"] = facts


def _prepare_distribution(b: _Builder, frame: pd.DataFrame, kind: str, reference: float | None) -> None:
    if frame is None or frame.empty or "Виконання" not in frame.columns:
        return
    d = frame.copy(); d["_exec"] = _numeric(d, "Виконання"); d = d.dropna(subset=["_exec"])
    if d.empty:
        return
    d["_label"] = [_label(r, kind) for _, r in d.iterrows()]; d = d[d["_label"].astype(bool)]
    if d.empty:
        return
    src = f"analytics.{kind}_progress.latest_execution"
    vals = d["_exec"].astype(float)
    max_value, min_value = float(vals.max()), float(vals.min())
    best_rows = d[(d["_exec"].astype(float) - max_value).abs() <= 1e-9]
    worst_rows = d[(d["_exec"].astype(float) - min_value).abs() <= 1e-9]
    best_labels = [str(v) for v in best_rows["_label"].tolist() if str(v)]
    worst_labels = [str(v) for v in worst_rows["_label"].tolist() if str(v)]
    p = f"{kind}.distribution"
    ref = reference if reference is not None else float(vals.mean())
    count = len(d)
    facts: dict[str, Any] = {
        "count": b.add(f"{p}.count", count, unit="count", source=src, aggregation="evaluated entities in exact latest period", observation_unit=kind),
        "single_entity": count == 1,
        "mean": b.add(f"{p}.mean", vals.mean(), unit="percent", source=src, aggregation="cross-sectional mean of latest entity execution", allow_over_100=True),
        "median": b.add(f"{p}.median", vals.median(), unit="percent", source=src, aggregation="cross-sectional median of latest entity execution", allow_over_100=True),
        "reference": b.add(f"{p}.reference", ref, unit="percent", source="analytics.page.metrics.completion" if reference is not None else src, aggregation="latest execution reference", allow_over_100=True),
        "best_label": best_labels[0] if best_labels else "",
        "best_labels": best_labels,
        "best_is_unique": len(best_labels) == 1,
        "best_tie_count": b.add(f"{p}.best_tie_count", len(best_labels), unit="count", source=src, aggregation="entities tied at maximum latest execution", observation_unit=kind),
        "best_value": b.add(f"{p}.best", max_value, unit="percent", source=src, aggregation="maximum latest execution", allow_over_100=True),
        "worst_label": worst_labels[0] if worst_labels else "",
        "worst_labels": worst_labels,
        "worst_is_unique": len(worst_labels) == 1,
        "worst_tie_count": b.add(f"{p}.worst_tie_count", len(worst_labels), unit="count", source=src, aggregation="entities tied at minimum latest execution", observation_unit=kind),
        "worst_value": b.add(f"{p}.worst", min_value, unit="percent", source=src, aggregation="minimum latest execution", allow_over_100=True),
    }
    facts["gap"] = b.pp(f"{p}.gap_pp", facts["best_value"], facts["worst_value"], source=src, aggregation="best minus worst")
    facts["all_equal"] = abs(float(facts["gap"] or 0.0)) <= 1e-9
    above = int((vals > ref).sum()); below = int((vals < ref).sum()); deviation_count = above + below
    facts["above_reference"] = b.add(f"{p}.above_reference", above, unit="count", source=src, aggregation="entities above latest reference", observation_unit=kind)
    facts["below_reference"] = b.add(f"{p}.below_reference", below, unit="count", source=src, aggregation="entities below latest reference", observation_unit=kind)
    facts["deviation_count"] = b.add(f"{p}.deviation_count", deviation_count, unit="count", source=src, aggregation="entities different from latest reference", observation_unit=kind)
    facts["deviation_is_material"] = bool(count > 1 and deviation_count >= 2 and deviation_count * 2 >= count)

    ranked_desc = d.sort_values(["_exec", "_label"], ascending=[False, True]).reset_index(drop=True)
    ranked_asc = d.sort_values(["_exec", "_label"], ascending=[True, True]).reset_index(drop=True)
    facts["top"] = [(r["_label"], b.add(f"{p}.top.{i}", r["_exec"], unit="percent", source=src, aggregation=f"rank {i} latest execution", allow_over_100=True)) for i, (_, r) in enumerate(ranked_desc.head(3).iterrows(), 1)]
    facts["bottom"] = [(r["_label"], b.add(f"{p}.bottom.{i}", r["_exec"], unit="percent", source=src, aggregation=f"bottom rank {i} latest execution", allow_over_100=True)) for i, (_, r) in enumerate(ranked_asc.head(3).iterrows(), 1)]
    facts["top3_boundary_unique"] = not (count > 3 and abs(float(ranked_desc.iloc[2]["_exec"]) - float(ranked_desc.iloc[3]["_exec"])) <= 1e-9)
    facts["bottom3_boundary_unique"] = not (count > 3 and abs(float(ranked_asc.iloc[2]["_exec"]) - float(ranked_asc.iloc[3]["_exec"])) <= 1e-9)
    b.structures[p] = facts

    if "Зміна" in d.columns:
        c = d.assign(_change=_numeric(d, "Зміна")).dropna(subset=["_change"])
        if not c.empty:
            cp = f"{kind}.change"; improved = c[c["_change"] > 0.5]; declined = c[c["_change"] < -0.5]; stable = c[c["_change"].abs() <= 0.5]
            max_change, min_change = float(c["_change"].max()), float(c["_change"].min())
            hi_rows = c[(c["_change"].astype(float) - max_change).abs() <= 1e-9]
            lo_rows = c[(c["_change"].astype(float) - min_change).abs() <= 1e-9]
            hi_labels = [str(v) for v in hi_rows["_label"].tolist() if str(v)]
            lo_labels = [str(v) for v in lo_rows["_label"].tolist() if str(v)]
            cf = {
                "count_with_change": b.add(f"{cp}.count", len(c), unit="count", source=src, aggregation="comparable entities", observation_unit=kind),
                "single_entity": len(c) == 1,
                "improved": b.add(f"{cp}.improved_count", len(improved), unit="count", source=src, aggregation="improved entities", observation_unit=kind),
                "declined": b.add(f"{cp}.declined_count", len(declined), unit="count", source=src, aggregation="declined entities", observation_unit=kind),
                "stable": b.add(f"{cp}.stable_count", len(stable), unit="count", source=src, aggregation="stable entities", observation_unit=kind),
                "largest_improvement_label": hi_labels[0] if hi_labels else "",
                "largest_improvement_labels": hi_labels,
                "largest_improvement_is_unique": len(hi_labels) == 1,
                "largest_improvement_tie_count": b.add(f"{cp}.largest_improvement_tie_count", len(hi_labels), unit="count", source=src, aggregation="entities tied at maximum change", observation_unit=kind),
                "largest_improvement": b.add(f"{cp}.largest_improvement_pp", max_change, unit="pp", source=src, aggregation="maximum entity change"),
                "largest_deterioration_label": lo_labels[0] if lo_labels else "",
                "largest_deterioration_labels": lo_labels,
                "largest_deterioration_is_unique": len(lo_labels) == 1,
                "largest_deterioration_tie_count": b.add(f"{cp}.largest_deterioration_tie_count", len(lo_labels), unit="count", source=src, aggregation="entities tied at minimum change", observation_unit=kind),
                "largest_deterioration": b.add(f"{cp}.largest_deterioration_pp", min_change, unit="pp", source=src, aggregation="minimum entity change"),
            }
            cf["improved_share"] = b.ratio_pct(f"{cp}.improved_share_pct", len(improved), len(c), source=src, aggregation="share improved", numerator_unit=kind, denominator_unit=kind)
            cf["declined_share"] = b.ratio_pct(f"{cp}.declined_share_pct", len(declined), len(c), source=src, aggregation="share declined", numerator_unit=kind, denominator_unit=kind)
            b.structures[cp] = cf

def _prepare_current_concentration(b: _Builder, frame: pd.DataFrame, kind: str, column: str, topic: str) -> None:
    if frame is None or frame.empty or column not in frame.columns:
        return
    d = frame.copy(); d["_count"] = pd.to_numeric(d[column], errors="coerce").fillna(0).astype(int)
    d["_label"] = [_label(r, kind) for _, r in d.iterrows()]
    d = d[d["_label"].astype(bool)]
    if d.empty:
        return
    total = int(d["_count"].sum()); key = f"{kind}.{topic}"; src = f"analytics.{kind}_progress.{column}"
    facts: dict[str, Any] = {
        "total": b.add(f"{key}.total", total, unit="count", source=src, aggregation="current unique measures across entities", observation_unit="unique-measure"),
        "entity_count": b.add(f"{key}.entity_count", len(d), unit="count", source=src, aggregation="entities", observation_unit=kind),
        "affected_entities": b.add(f"{key}.affected_entities", int((d["_count"] > 0).sum()), unit="count", source=src, aggregation="affected entities", observation_unit=kind),
    }
    if total > 0:
        ranked = d.sort_values(["_count", "_label"], ascending=[False, True]).reset_index(drop=True)
        positive = ranked[ranked["_count"] > 0].copy()
        top = ranked.iloc[0]; top3 = ranked.head(3); top3_count = int(top3["_count"].sum())
        top_count = int(top["_count"])
        tied = positive[positive["_count"] == top_count]
        top_labels = [str(value) for value in tied["_label"].tolist() if str(value)]
        affected_entities = int((d["_count"] > 0).sum())
        entity_count = int(len(d))
        facts.update({
            "top_label": top["_label"],
            "top_count": b.add(f"{key}.top_count", top_count, unit="count", source=src, aggregation="top current count", observation_unit="unique-measure"),
            "top3_count": b.add(f"{key}.top3_count", top3_count, unit="count", source=src, aggregation="top3 current count", observation_unit="unique-measure"),
            "top3": [(r["_label"], int(r["_count"])) for _, r in top3.iterrows() if int(r["_count"]) > 0],
            "top_labels": top_labels,
            "top_tie_count": b.add(
                f"{key}.top_tie_count", len(top_labels), unit="count", source=src,
                aggregation="entities tied at maximum current count", observation_unit=kind,
            ),
            "top_is_unique": len(top_labels) == 1,
        })
        facts["top_share"] = b.ratio_pct(f"{key}.top_share_pct", facts["top_count"], facts["total"], source=src, aggregation="top1 concentration", numerator_unit="unique-measure", denominator_unit="unique-measure")
        facts["top3_share"] = b.ratio_pct(f"{key}.top3_share_pct", facts["top3_count"], facts["total"], source=src, aggregation="top3 concentration", numerator_unit="unique-measure", denominator_unit="unique-measure")
        top_share = float(facts["top_share"] or 0)
        top3_share = float(facts["top3_share"] or 0)
        all_affected_equal = bool(
            affected_entities == entity_count
            and affected_entities > 1
            and positive["_count"].nunique() == 1
        )
        top3_has_distinct_boundary = False
        if affected_entities > 3:
            counts = positive["_count"].tolist()
            top3_has_distinct_boundary = len(counts) >= 4 and int(counts[2]) > int(counts[3])
        # Renderer-only comparative metadata.  This does not change the accepted
        # attention/missing concentration mathematics: it only prevents wording
        # such as "three largest" when the third/fourth boundary is tied.
        facts["top3_boundary_unique"] = affected_entities <= 3 or top3_has_distinct_boundary

        # Concentration is a comparative statement, not a mechanical share test.
        # Equal 2/2, 3/3, 4/4 (and analogous fully even distributions) are
        # distributed.  A top-3 concentration is used only when the top three
        # form a factually distinct group rather than an arbitrary cut through a tie.
        if all_affected_equal:
            concentration_class = "distributed"
        elif bool(facts["top_is_unique"]) and top_share >= 50.0:
            concentration_class = "concentrated"
        elif affected_entities > 3 and top3_share >= 75.0 and top3_has_distinct_boundary:
            concentration_class = "concentrated"
        elif affected_entities <= max(2, entity_count // 4):
            concentration_class = "localised"
        else:
            concentration_class = "distributed"
        facts["concentration_class"] = concentration_class
    else:
        facts["concentration_class"] = "none"
    b.structures[key] = facts


def _prepare_status(b: _Builder, status_counts: pd.DataFrame, active: pd.DataFrame) -> None:
    if status_counts is None or status_counts.empty or not {"status", "Кількість"}.issubset(status_counts.columns):
        return
    rows = [(str(r["status"]), _safe_int(r["Кількість"])) for _, r in status_counts.iterrows()]
    total = sum(v for _, v in rows)
    if total <= 0:
        return
    bound = [(label, b.add(f"status.count.{i}", count, unit="count", source="analytics.status_counts", aggregation=f"status {label} historical count", observation_unit="measure-period")) for i, (label, count) in enumerate(rows)]
    ranked = sorted(bound, key=lambda x: (-int(x[1]), str(x[0])))
    shares = {label: b.ratio_pct(f"status.share.{i}", count, total, source="analytics.status_counts", aggregation="historical status share", numerator_unit="measure-period", denominator_unit="measure-period") for i, (label, count) in enumerate(bound)}
    top_count = int(ranked[0][1])
    dominant_labels = [str(label) for label, count in ranked if int(count) == top_count]
    b.structures["status"] = {
        "total": b.add("status.total", total, unit="count", source="analytics.status_counts", aggregation="historical status rows", observation_unit="measure-period"),
        "status_count": b.add("status.distinct_count", len(ranked), unit="count", source="analytics.status_counts", aggregation="distinct status labels", observation_unit="status"),
        "single_status": len(ranked) == 1,
        "ranked": ranked,
        "shares": shares,
        "dominant_label": ranked[0][0],
        "dominant_labels": dominant_labels,
        "dominant_count": ranked[0][1],
        "dominant_share": shares.get(ranked[0][0]),
        "dominant_is_unique": len(dominant_labels) == 1 and len(ranked) > 1,
        "dominant_tie_count": b.add("status.dominant_tie_count", len(dominant_labels), unit="count", source="analytics.status_counts", aggregation="statuses tied at maximum count", observation_unit="status"),
    }

def _prepare_product(b: _Builder, frame: pd.DataFrame) -> None:
    if frame is None or frame.empty:
        return
    d = frame.copy(); d["_portfolio"] = _numeric(d, "Унікальних_заходів", 0).fillna(0); d["_exec"] = _numeric(d, "Виконання")
    d["_attention"] = _numeric(d, "Актуальна_увага", 0).fillna(0); d["_missing"] = _numeric(d, "Без_даних", 0).fillna(0)
    d["_label"] = [_label(row, "product") for _, row in d.iterrows()]
    d = d[d["_label"].astype(bool)].copy()
    if d.empty:
        return
    ranked = d.sort_values(["_portfolio", "_label"], ascending=[False, True]); top = ranked.iloc[0]; total_size = int(d["_portfolio"].sum())
    max_size = float(ranked.iloc[0]["_portfolio"])
    largest_rows = ranked[(ranked["_portfolio"].astype(float) - max_size).abs() <= 1e-9]
    largest_labels = [str(v) for v in largest_rows["_label"].tolist() if str(v)]
    attention_total, missing_total = int(d["_attention"].sum()), int(d["_missing"].sum())
    facts: dict[str, Any] = {
        "count": b.add("product.count", len(d), unit="count", source="analytics.product_progress", aggregation="product types", observation_unit="product"),
        "single_entity": len(d) == 1,
        "largest_label": largest_labels[0] if largest_labels else "",
        "largest_labels": largest_labels,
        "largest_is_unique": len(largest_labels) == 1 and len(d) > 1,
        "largest_tie_count": b.add("product.largest_tie_count", len(largest_labels), unit="count", source="analytics.product_progress", aggregation="product types tied at largest portfolio size", observation_unit="product"),
        "largest_size": b.add("product.largest_size", int(top["_portfolio"]), unit="count", source="analytics.product_progress", aggregation="largest product portfolio", observation_unit="unique-measure"),
        "total_size": b.add("product.total_size", total_size, unit="count", source="analytics.product_progress", aggregation="product portfolio size", observation_unit="unique-measure"),
        "all_equal_size": len(d) > 1 and d["_portfolio"].nunique(dropna=True) == 1,
        "attention_total": b.add("product.attention_total", attention_total, unit="count", source="analytics.product_progress", aggregation="current attention measures", observation_unit="unique-measure"),
        "missing_total": b.add("product.missing_total", missing_total, unit="count", source="analytics.product_progress", aggregation="current missing-submission measures", observation_unit="unique-measure"),
    }
    if total_size:
        facts["largest_share"] = b.ratio_pct("product.largest_share_pct", facts["largest_size"], total_size, source="analytics.product_progress", aggregation="largest portfolio share", numerator_unit="unique-measure", denominator_unit="unique-measure")
    valid = d.dropna(subset=["_exec"]).copy()
    if not valid.empty:
        max_exec, min_exec = float(valid["_exec"].max()), float(valid["_exec"].min())
        best_rows = valid[(valid["_exec"].astype(float) - max_exec).abs() <= 1e-9]
        worst_rows = valid[(valid["_exec"].astype(float) - min_exec).abs() <= 1e-9]
        best_labels = [str(v) for v in best_rows["_label"].tolist() if str(v)]
        worst_labels = [str(v) for v in worst_rows["_label"].tolist() if str(v)]
        facts.update({
            "execution_count": b.add("product.execution_count", len(valid), unit="count", source="analytics.product_progress", aggregation="product types with exact-latest execution", observation_unit="product"),
            "best_label": best_labels[0] if best_labels else "",
            "best_labels": best_labels,
            "best_is_unique": len(best_labels) == 1 and len(valid) > 1,
            "best_tie_count": b.add("product.best_tie_count", len(best_labels), unit="count", source="analytics.product_progress", aggregation="product types tied at maximum latest execution", observation_unit="product"),
            "worst_label": worst_labels[0] if worst_labels else "",
            "worst_labels": worst_labels,
            "worst_is_unique": len(worst_labels) == 1 and len(valid) > 1,
            "worst_tie_count": b.add("product.worst_tie_count", len(worst_labels), unit="count", source="analytics.product_progress", aggregation="product types tied at minimum latest execution", observation_unit="product"),
            "best_value": b.add("product.best_execution", max_exec, unit="percent", source="analytics.product_progress", aggregation="maximum latest execution", allow_over_100=True),
            "worst_value": b.add("product.worst_execution", min_exec, unit="percent", source="analytics.product_progress", aggregation="minimum latest execution", allow_over_100=True),
        })
        facts["gap"] = b.pp("product.execution_gap_pp", facts["best_value"], facts["worst_value"], source="analytics.product_progress", aggregation="best minus worst")
        facts["all_equal_execution"] = abs(float(facts["gap"] or 0.0)) <= 1e-9
    b.structures["product"] = facts

def _prepare_drilldowns(
    b: _Builder,
    goal_progress: pd.DataFrame,
    task_progress: pd.DataFrame,
    department_progress: pd.DataFrame,
    active: pd.DataFrame,
) -> None:
    # Deterministic drill-down selects a salient parent, then exposes prepared child
    # facts already present in its summary rows.  It never infers an unobserved cause.
    if goal_progress is not None and not goal_progress.empty and "Виконання" in goal_progress.columns:
        d = goal_progress.copy(); d["_exec"] = _numeric(d, "Виконання"); d["_attention"] = _numeric(d, "Актуальна_увага", 0).fillna(0); d["_missing"] = _numeric(d, "Без_даних", 0).fillna(0)
        valid = d.dropna(subset=["_exec"])
        if not valid.empty:
            valid["_salience"] = (100 - valid["_exec"].clip(0, 100)) + valid["_attention"] * 4 + valid["_missing"] * 2
            focus = valid.sort_values(["_salience", "_exec"], ascending=[False, True]).iloc[0]
            goal_code = str(focus.get("goal_code") or "").strip()
            goal_facts = {
                "goal_label": _label(focus, "goal"),
                "execution": b.add("drilldown.goal.execution", focus["_exec"], unit="percent", source="analytics.goal_progress", aggregation="salient goal latest execution", allow_over_100=True),
                "attention_count": b.add("drilldown.goal.attention_count", int(focus["_attention"]), unit="count", source="analytics.goal_progress", aggregation="salient goal current attention", observation_unit="unique-measure"),
                "missing_count": b.add("drilldown.goal.missing_count", int(focus["_missing"]), unit="count", source="analytics.goal_progress", aggregation="salient goal current missing submissions", observation_unit="unique-measure"),
            }
            # Child tasks make the drill-down genuinely hierarchical. Only prepared
            # task-level facts are exposed; the engine does not invent a cause.
            children = []
            if task_progress is not None and not task_progress.empty and goal_code and "goal_code" in task_progress.columns:
                td = task_progress[task_progress["goal_code"].astype(str).eq(goal_code)].copy()
                if not td.empty:
                    td["_exec"] = _numeric(td, "Виконання")
                    td["_attention"] = _numeric(td, "Актуальна_увага", 0).fillna(0)
                    td["_missing"] = _numeric(td, "Без_даних", 0).fillna(0)
                    td = td.dropna(subset=["_exec"]).copy()
                    if not td.empty:
                        td["_salience"] = (100 - td["_exec"].clip(0, 100)) + td["_attention"] * 4 + td["_missing"] * 2
                        for child_pos, (_, child) in enumerate(td.sort_values(["_salience", "_exec"], ascending=[False, True]).head(3).iterrows(), start=1):
                            children.append({
                                "label": _label(child, "task"),
                                "execution": b.add(f"drilldown.goal.child{child_pos}.execution", child["_exec"], unit="percent", source="analytics.task_progress", aggregation="salient child task latest execution", allow_over_100=True),
                                "attention_count": b.add(f"drilldown.goal.child{child_pos}.attention_count", int(child["_attention"]), unit="count", source="analytics.task_progress", aggregation="salient child task current attention", observation_unit="unique-measure"),
                                "missing_count": b.add(f"drilldown.goal.child{child_pos}.missing_count", int(child["_missing"]), unit="count", source="analytics.task_progress", aggregation="salient child task current missing submissions", observation_unit="unique-measure"),
                            })
            if children:
                goal_facts["children"] = children
            b.structures["drilldown.goal"] = goal_facts
    if department_progress is not None and not department_progress.empty and "Виконання" in department_progress.columns:
        d = department_progress.copy(); d["_exec"] = _numeric(d, "Виконання"); d["_attention"] = _numeric(d, "Актуальна_увага", 0).fillna(0); d["_missing"] = _numeric(d, "Без_даних", 0).fillna(0); d["_weight"] = _numeric(d, "portfolio_weight_pct", 0).fillna(0); d["_under"] = _numeric(d, "underperformance_contribution_pct", 0).fillna(0)
        valid = d.dropna(subset=["_exec"])
        if not valid.empty:
            valid["_salience"] = valid["_under"] * 1.5 + valid["_attention"] * 3 + valid["_missing"] * 2 + valid["_weight"] * 0.25 + (100 - valid["_exec"].clip(0, 100)) * 0.3
            focus = valid.sort_values("_salience", ascending=False).iloc[0]
            department_label = _label(focus, "department")
            ssp_index = str(focus.get("ssp_index") or "").strip()
            ssp_facts = {
                "department": department_label,
                "ssp_index": ssp_index,
                "execution": b.add("drilldown.ssp.execution", focus["_exec"], unit="percent", source="analytics.department_progress", aggregation="salient SSP latest execution", allow_over_100=True),
                "portfolio_weight": b.add("drilldown.ssp.portfolio_weight_pct", focus["_weight"], unit="percent", source="analytics.department_progress", aggregation="salient SSP portfolio weight"),
                "underperformance_contribution": b.add("drilldown.ssp.underperformance_contribution_pct", focus["_under"], unit="percent", source="analytics.department_progress", aggregation="salient SSP underperformance contribution"),
                "attention_count": b.add("drilldown.ssp.attention_count", int(focus["_attention"]), unit="count", source="analytics.department_progress", aggregation="salient SSP current attention", observation_unit="unique-measure"),
                "missing_count": b.add("drilldown.ssp.missing_count", int(focus["_missing"]), unit="count", source="analytics.department_progress", aggregation="salient SSP current missing submissions", observation_unit="unique-measure"),
            }

            # Resolve child tasks only when factual ownership evidence is available.
            # The task metrics themselves come from the already prepared exact-latest
            # task summary; active rows are used only to identify SSP ownership.
            children = []
            if (
                task_progress is not None and not task_progress.empty
                and active is not None and not active.empty
                and "task_code" in task_progress.columns and "task_code" in active.columns
            ):
                ownership = active.copy()
                owner_mask = pd.Series(False, index=ownership.index)
                if department_label and "department" in ownership.columns:
                    owner_mask = owner_mask | ownership["department"].astype(str).eq(department_label)
                if ssp_index and "ssp_index" in ownership.columns:
                    owner_mask = owner_mask | ownership["ssp_index"].astype(str).eq(ssp_index)
                owned_codes = {
                    str(value).strip()
                    for value in ownership.loc[owner_mask, "task_code"].dropna().tolist()
                    if str(value).strip()
                }
                if owned_codes:
                    td = task_progress[task_progress["task_code"].astype(str).isin(owned_codes)].copy()
                    if not td.empty:
                        td["_exec"] = _numeric(td, "Виконання")
                        td["_attention"] = _numeric(td, "Актуальна_увага", 0).fillna(0)
                        td["_missing"] = _numeric(td, "Без_даних", 0).fillna(0)
                        td = td.dropna(subset=["_exec"]).copy()
                        if not td.empty:
                            td["_salience"] = (100 - td["_exec"].clip(0, 100)) + td["_attention"] * 4 + td["_missing"] * 2
                            for child_pos, (_, child) in enumerate(
                                td.sort_values(["_salience", "_exec"], ascending=[False, True]).head(3).iterrows(), start=1
                            ):
                                children.append({
                                    "label": _label(child, "task"),
                                    "execution": b.add(f"drilldown.ssp.child{child_pos}.execution", child["_exec"], unit="percent", source="analytics.task_progress", aggregation="salient SSP child task exact-latest execution", allow_over_100=True),
                                    "attention_count": b.add(f"drilldown.ssp.child{child_pos}.attention_count", int(child["_attention"]), unit="count", source="analytics.task_progress", aggregation="salient SSP child task current attention", observation_unit="unique-measure"),
                                    "missing_count": b.add(f"drilldown.ssp.child{child_pos}.missing_count", int(child["_missing"]), unit="count", source="analytics.task_progress", aggregation="salient SSP child task current missing submissions", observation_unit="unique-measure"),
                                })
            if children:
                ssp_facts["children"] = children
            b.structures["drilldown.ssp"] = ssp_facts


def _prepare_ssp_and_risk(b: _Builder, department_progress: pd.DataFrame, metrics: Mapping[str, Any]) -> None:
    d = department_progress.copy() if department_progress is not None else pd.DataFrame()
    if not d.empty:
        d["_label"] = [_label(row, "department") for _, row in d.iterrows()]
        d["_weight"] = _numeric(d, "portfolio_weight_pct"); d["_under"] = _numeric(d, "underperformance_contribution_pct"); d["_exec"] = _numeric(d, "Виконання")
        d = d[d["_label"].astype(bool)].copy()
        weighted = d.dropna(subset=["_weight"]).copy()
        if not weighted.empty:
            max_weight = float(weighted["_weight"].max())
            largest_rows = weighted[(weighted["_weight"].astype(float) - max_weight).abs() <= 1e-9].sort_values("_label")
            largest_labels = [str(v) for v in largest_rows["_label"].tolist() if str(v)]
            largest = largest_rows.iloc[0]
            facts = {
                "department_count": b.add("ssp.department_count", len(d), unit="count", source="analytics.department_progress", aggregation="SSP rows", observation_unit="department"),
                "single_entity": len(d) == 1,
                "largest_department": largest_labels[0] if largest_labels else "",
                "largest_departments": largest_labels,
                "largest_weight_is_unique": len(largest_labels) == 1 and len(weighted) > 1,
                "largest_weight_tie_count": b.add("ssp.largest_weight_tie_count", len(largest_labels), unit="count", source="analytics.department_progress", aggregation="SSP tied at maximum portfolio weight", observation_unit="department"),
                "largest_weight": b.add("ssp.largest_weight_pct", max_weight, unit="percent", source="analytics.department_progress", aggregation="largest portfolio weight"),
                "largest_execution": b.add("ssp.largest_execution_pct", largest.get("Виконання"), unit="percent", source="analytics.department_progress", aggregation="execution of first maximum-weight SSP for compatibility only", allow_over_100=True),
            }
            under = d.dropna(subset=["_under"]).copy()
            if not under.empty:
                max_under = float(under["_under"].max())
                top_rows = under[(under["_under"].astype(float) - max_under).abs() <= 1e-9].sort_values("_label")
                top_labels = [str(v) for v in top_rows["_label"].tolist() if str(v)]
                top = top_rows.iloc[0]
                facts["top_underperformance_department"] = top_labels[0] if top_labels else ""
                facts["top_underperformance_departments"] = top_labels
                facts["top_underperformance_is_unique"] = len(top_labels) == 1 and len(under) > 1
                facts["top_underperformance_tie_count"] = b.add("ssp.top_underperformance_tie_count", len(top_labels), unit="count", source="analytics.department_progress", aggregation="SSP tied at maximum underperformance contribution", observation_unit="department")
                facts["top_underperformance_contribution"] = b.add("ssp.top_underperformance_contribution_pct", max_under, unit="percent", source="analytics.department_progress", aggregation="top underperformance contribution")
                facts["top_underperformance_weight"] = b.add("ssp.top_underperformance_weight_pct", top.get("portfolio_weight_pct"), unit="percent", source="analytics.department_progress", aggregation="portfolio weight of first maximum-contribution SSP for compatibility only")
                if facts["top_underperformance_contribution"] is not None and facts["top_underperformance_weight"] is not None:
                    facts["top_underperformance_excess_pp"] = b.pp("ssp.top_underperformance_excess_pp", facts["top_underperformance_contribution"], facts["top_underperformance_weight"], source="analytics.department_progress", aggregation="underperformance contribution minus portfolio weight for unique/top compatibility row")
            b.structures["ssp.portfolio"] = facts
    # Dashboard ``risk_summary()`` is intentionally unchanged. Analytics adapts its
    # quarter-specific shape here so a single internal finding code never mixes
    # preliminary, predictive-risk and final-outcome semantics.
    summary = metrics.get("latest_risk_summary") or {}
    attention_type = str(metrics.get("attention_type") or "").strip()
    if isinstance(summary, dict) and summary and attention_type in {
        "preliminary_attention", "forecast_risk", "final_nonachievement"
    }:
        risk: dict[str, Any] = {"mode": attention_type}
        if attention_type == "preliminary_attention":
            risk.update({
                "preliminary_forecast_count": b.add(
                    "risk.summary.preliminary_forecast_count", summary.get("preliminary_forecast_count"),
                    unit="count", source="dashboard.latest_risk_summary.preliminary_forecast_count",
                    aggregation="Q1 preliminary forecast count", observation_unit="unique-measure",
                ),
                "preliminary_forecast_average": b.add(
                    "risk.summary.preliminary_forecast_average_pct", summary.get("preliminary_forecast_average"),
                    unit="percent", source="dashboard.latest_risk_summary.preliminary_forecast_average",
                    aggregation="Q1 average preliminary forecast attainment", allow_over_100=True,
                ),
                "preliminary_attention_count": b.add(
                    "risk.summary.preliminary_attention_count", summary.get("preliminary_attention_count"),
                    unit="count", source="dashboard.latest_risk_summary.preliminary_attention_count",
                    aggregation="Q1 preliminary attention count", observation_unit="unique-measure",
                ),
            })
        elif attention_type == "forecast_risk":
            assessed_count = b.add(
                    "risk.summary.assessed_count", summary.get("risk_assessed_count"), unit="count",
                    source="dashboard.latest_risk_summary.risk_assessed_count",
                    aggregation="Q2-Q3 predictive risk assessed measures", observation_unit="unique-measure",
                )
            risk.update({
                "assessed_count": assessed_count,
                "assessment_state": "zero_assessed" if int(assessed_count or 0) == 0 else "assessed",
                "high_critical_share": b.add(
                    "risk.summary.high_critical_share_pct", summary.get("share_high_critical_risk"), unit="percent",
                    source="dashboard.latest_risk_summary.share_high_critical_risk",
                    aggregation="Q2-Q3 high/critical predictive risk share",
                ),
                "without_substantial_risk_share": b.add(
                    "risk.summary.without_substantial_risk_share_pct", summary.get("share_without_substantial_risk"), unit="percent",
                    source="dashboard.latest_risk_summary.share_without_substantial_risk",
                    aggregation="Q2-Q3 share without substantial predictive risk",
                ),
            })
        else:
            risk.update({
                "assessed_count": b.add(
                    "risk.summary.final_assessed_count", metrics.get("attention_assessed_count"), unit="count",
                    source="analytics.page.metrics.attention_assessed_count",
                    aggregation="Q4 final assessed measures", observation_unit="unique-measure",
                ),
                "results_achieved_share": b.add(
                    "risk.summary.results_achieved_share_pct", summary.get("share_results_achieved"), unit="percent",
                    source="dashboard.latest_risk_summary.share_results_achieved",
                    aggregation="Q4 factual results-achieved share",
                ),
            })
        b.structures["risk"] = risk


def _prepare_missing_persistence(b: _Builder, active: pd.DataFrame) -> None:
    if active is None or active.empty or not {"report_year", "report_quarter", "missing_required_submission"}.issubset(active.columns):
        return
    d = active.copy(); d["_period"] = d["report_year"].astype(str) + " " + d["report_quarter"].astype(str)
    if d["_period"].nunique() < 2:
        return
    missing = _safe_int
    out = []
    for col, kind in (("goal_code", "goal"), ("department", "department")):
        if col not in d.columns:
            continue
        rows = []
        for label, group in d.groupby(d[col].fillna("").astype(str)):
            if not str(label).strip():
                continue
            periods = 0
            for _, pg in group.groupby("_period"):
                periods += int(_numeric(pg.assign(_m=pg["missing_required_submission"].fillna(False).astype(int)), "_m", 0).sum() > 0)
            if periods >= 2:
                rows.append((str(label), periods, int(group["_period"].nunique())))
        if rows:
            top = max(rows, key=lambda x: x[1])
            out.append({
                "kind": kind, "label": top[0],
                "periods_with_missing": b.add(f"persistence.{kind}.missing_periods", top[1], unit="count", source="analytics.active.missing_required_submission", aggregation="periods with missing submission", observation_unit="period"),
                "periods_observed": b.add(f"persistence.{kind}.observed_periods", top[2], unit="count", source="analytics.active", aggregation="periods observed", observation_unit="period"),
            })
    if out:
        b.structures["missing_persistence"] = out


def _prepare_mio(
    b: _Builder,
    goals: pd.DataFrame,
    tasks: pd.DataFrame,
    measures: pd.DataFrame,
    financing: pd.DataFrame,
    year: int,
    task_progress: pd.DataFrame,
) -> None:
    """Preserve the target MіO factual contract without reintroducing Analytics averages.

    MіO's own annual/component averages, medians and paired finance-vs-physical
    comparisons are part of the established MіO methodology and remain intact.
    The only Analytics-specific adaptation is that task execution used for the
    execution-vs-indicator divergence comes from the exact-latest task summary
    supplied by Analytics, never from a temporal execution average.
    """
    int_col, meas_col, task_col, prog_col = (
        f"Інтеграл {year}", f"Заходи {year}", f"Завдання {year}", f"Прогрес {year}"
    )

    # Strategic-goal MіO profile: restore the complete target factual contract.
    if goals is not None and not goals.empty and int_col in goals.columns:
        d = goals.copy()
        for column in (int_col, meas_col, task_col, prog_col):
            if column in d.columns:
                d[column] = pd.to_numeric(d[column], errors="coerce")
        valid = d.dropna(subset=[int_col]).copy()
        if not valid.empty:
            max_integral, min_integral = float(valid[int_col].max()), float(valid[int_col].min())
            best_rows = valid[(valid[int_col].astype(float) - max_integral).abs() <= 1e-9].sort_values("Код")
            worst_rows = valid[(valid[int_col].astype(float) - min_integral).abs() <= 1e-9].sort_values("Код")
            best = best_rows.iloc[0]; worst = worst_rows.iloc[0]
            best_codes = [str(v) for v in best_rows.get("Код", pd.Series(dtype=object)).tolist() if str(v)]
            worst_codes = [str(v) for v in worst_rows.get("Код", pd.Series(dtype=object)).tolist() if str(v)]
            facts: dict[str, Any] = {
                "year": year,
                "goals_count": b.add(
                    "mio.goal_count", len(valid), unit="count",
                    source="mio_shared.goal_evaluation", aggregation="evaluated goals",
                    observation_unit="goal",
                ),
                "single_entity": len(valid) == 1,
                "average_integral": b.add(
                    "mio.average_integral", valid[int_col].mean(), unit="percent",
                    source="mio_shared.goal_evaluation", aggregation="mean goal integral",
                    allow_over_100=True,
                ),
                "best_code": str(best.get("Код", "")),
                "best_codes": best_codes,
                "best_is_unique": len(best_codes) == 1 and len(valid) > 1,
                "best_tie_count": b.add("mio.goal.best_tie_count", len(best_codes), unit="count", source="mio_shared.goal_evaluation", aggregation="goals tied at maximum integral", observation_unit="goal"),
                "best_name": str(best.get("Ціль", "")),
                "best_integral": b.add(
                    "mio.best_integral", max_integral, unit="percent",
                    source="mio_shared.goal_evaluation", aggregation="maximum integral",
                    allow_over_100=True,
                ),
                "worst_code": str(worst.get("Код", "")),
                "worst_codes": worst_codes,
                "worst_is_unique": len(worst_codes) == 1 and len(valid) > 1,
                "worst_tie_count": b.add("mio.goal.worst_tie_count", len(worst_codes), unit="count", source="mio_shared.goal_evaluation", aggregation="goals tied at minimum integral", observation_unit="goal"),
                "worst_name": str(worst.get("Ціль", "")),
                "worst_integral": b.add(
                    "mio.worst_integral", min_integral, unit="percent",
                    source="mio_shared.goal_evaluation", aggregation="minimum integral",
                    allow_over_100=True,
                ),
            }
            facts["gap"] = b.pp(
                "mio.integral_gap_pp", facts["best_integral"], facts["worst_integral"],
                source="mio_shared.goal_evaluation", aggregation="best minus worst",
            )
            facts["all_equal"] = abs(float(facts["gap"] or 0.0)) <= 1e-9
            for column, key, code in (
                (meas_col, "average_measures", "mio.average_measures"),
                (task_col, "average_tasks", "mio.average_tasks"),
                (prog_col, "average_progress", "mio.average_progress"),
            ):
                if column in valid.columns and valid[column].notna().any():
                    facts[key] = b.add(
                        code, valid[column].dropna().mean(), unit="percent",
                        source="mio_shared.goal_evaluation", aggregation="mean component",
                        allow_over_100=True,
                    )

            divergences = []
            for index, (_, row) in enumerate(valid.iterrows()):
                measure_value = _safe_number(row.get(meas_col))
                integral_value = _safe_number(row.get(int_col))
                progress_value = _safe_number(row.get(prog_col))
                if measure_value is None or integral_value is None:
                    continue
                measure_metric = b.add(
                    f"mio.goal.{index}.measure_execution_pct", measure_value,
                    unit="percent", source="mio_shared.goal_evaluation",
                    aggregation="goal measure component", allow_over_100=True,
                )
                integral_metric = b.add(
                    f"mio.goal.{index}.integral_pct", integral_value,
                    unit="percent", source="mio_shared.goal_evaluation",
                    aggregation="goal integral", allow_over_100=True,
                )
                progress_metric = (
                    b.add(
                        f"mio.goal.{index}.progress_pct", progress_value,
                        unit="percent", source="mio_shared.goal_evaluation",
                        aggregation="goal strategic progress", allow_over_100=True,
                    ) if progress_value is not None else None
                )
                gap = b.pp(
                    f"mio.goal.{index}.measure_integral_gap_pp",
                    measure_metric, integral_metric,
                    source="mio_shared.goal_evaluation",
                    aggregation="measure execution minus integral",
                )
                if abs(float(gap)) >= 10:
                    divergences.append({
                        "code": str(row.get("Код", "")),
                        "name": str(row.get("Ціль", "")),
                        "measure_execution": measure_metric,
                        "integral": integral_metric,
                        "gap": gap,
                        "progress": progress_metric,
                    })
            facts["divergences"] = sorted(
                divergences, key=lambda item: abs(float(item["gap"])), reverse=True
            )[:4]
            b.structures["mio.goals"] = facts

    # Task-indicator MіO profile. Best/worst/gap remain exactly as in target.
    score_col = f"Оцінка {year}"
    if tasks is not None and not tasks.empty and {"Рівень", "Код", score_col}.issubset(tasks.columns):
        t = tasks[tasks["Рівень"].astype(str).eq("task")].copy()
        t[score_col] = pd.to_numeric(t[score_col], errors="coerce")
        scores = t.groupby(t["Код"].astype(str))[score_col].mean().dropna()
        if not scores.empty:
            max_progress, min_progress = float(scores.max()), float(scores.min())
            best_tasks = sorted(str(idx) for idx, value in scores.items() if abs(float(value) - max_progress) <= 1e-9)
            worst_tasks = sorted(str(idx) for idx, value in scores.items() if abs(float(value) - min_progress) <= 1e-9)
            facts = {
                "year": year,
                "tasks_count": b.add(
                    "mio.task_count", len(scores), unit="count",
                    source="mio_shared.goal_task_evaluation", aggregation="evaluated tasks",
                    observation_unit="task",
                ),
                "single_entity": len(scores) == 1,
                "average_task_indicator_progress": b.add(
                    "mio.task.average_indicator_progress", scores.mean(), unit="percent",
                    source="mio_shared.goal_task_evaluation",
                    aggregation="mean task indicator progress", allow_over_100=True,
                ),
                "best_task": best_tasks[0] if best_tasks else "",
                "best_tasks": best_tasks,
                "best_is_unique": len(best_tasks) == 1 and len(scores) > 1,
                "best_tie_count": b.add("mio.task.best_tie_count", len(best_tasks), unit="count", source="mio_shared.goal_task_evaluation", aggregation="tasks tied at maximum indicator progress", observation_unit="task"),
                "best_task_progress": b.add(
                    "mio.task.best_progress", max_progress, unit="percent",
                    source="mio_shared.goal_task_evaluation",
                    aggregation="maximum task progress", allow_over_100=True,
                ),
                "worst_task": worst_tasks[0] if worst_tasks else "",
                "worst_tasks": worst_tasks,
                "worst_is_unique": len(worst_tasks) == 1 and len(scores) > 1,
                "worst_tie_count": b.add("mio.task.worst_tie_count", len(worst_tasks), unit="count", source="mio_shared.goal_task_evaluation", aggregation="tasks tied at minimum indicator progress", observation_unit="task"),
                "worst_task_progress": b.add(
                    "mio.task.worst_progress", min_progress, unit="percent",
                    source="mio_shared.goal_task_evaluation",
                    aggregation="minimum task progress", allow_over_100=True,
                ),
            }
            facts["gap"] = b.pp(
                "mio.task.progress_gap_pp",
                facts["best_task_progress"], facts["worst_task_progress"],
                source="mio_shared.goal_task_evaluation", aggregation="best minus worst",
            )
            facts["all_equal"] = abs(float(facts["gap"] or 0.0)) <= 1e-9

            divergences = []
            if (
                task_progress is not None and not task_progress.empty
                and {"task_code", "Виконання"}.issubset(task_progress.columns)
            ):
                tp = task_progress.copy()
                tp["_code"] = tp["task_code"].astype(str)
                tp["_exec"] = pd.to_numeric(tp["Виконання"], errors="coerce")
                # `task_progress` is already the Analytics exact-latest summary.
                # One task must therefore contribute its latest value only; do
                # not calculate any temporal average here.
                exact_latest = (
                    tp.dropna(subset=["_exec"])
                    .drop_duplicates(subset=["_code"], keep="first")
                    .set_index("_code")["_exec"]
                )
                for index, (code, progress) in enumerate(scores.items()):
                    if code not in exact_latest.index:
                        continue
                    execution_metric = b.add(
                        f"mio.task.{index}.execution_pct", float(exact_latest.loc[code]),
                        unit="percent", source="analytics.task_progress.exact_latest",
                        aggregation="task exact-latest execution", allow_over_100=True,
                    )
                    progress_metric = b.add(
                        f"mio.task.{index}.indicator_progress_pct", float(progress),
                        unit="percent", source="mio_shared.goal_task_evaluation",
                        aggregation="task indicator progress", allow_over_100=True,
                    )
                    gap = b.pp(
                        f"mio.task.{index}.execution_indicator_gap_pp",
                        execution_metric, progress_metric,
                        source="mio_shared+analytics.task_progress.exact_latest",
                        aggregation="exact-latest task execution minus indicator progress",
                    )
                    if abs(float(gap)) >= 10:
                        divergences.append({
                            "code": code,
                            "execution": execution_metric,
                            "indicator_progress": progress_metric,
                            "gap": gap,
                        })
            facts["divergences"] = sorted(
                divergences, key=lambda item: abs(float(item["gap"])), reverse=True
            )[:4]
            b.structures["mio.tasks"] = facts

    # Measure-level MіO: preserve count, evaluated count, mean and median.
    if measures is not None and not measures.empty and "Факт/План, %" in measures.columns:
        ratios = pd.to_numeric(measures["Факт/План, %"], errors="coerce").dropna()
        if not ratios.empty:
            b.structures["mio.measures"] = {
                "year": year,
                "measures_count": b.add(
                    "mio.measure_count", len(measures), unit="count",
                    source="mio_shared.measure_evaluation", aggregation="measure rows",
                    observation_unit="measure",
                ),
                "evaluated_measures": b.add(
                    "mio.measure_evaluated_count", len(ratios), unit="count",
                    source="mio_shared.measure_evaluation", aggregation="evaluated measures",
                    observation_unit="measure",
                ),
                "average_fact_plan": b.add(
                    "mio.measure.average_fact_plan", ratios.mean(), unit="percent",
                    source="mio_shared.measure_evaluation", aggregation="mean fact/plan",
                    allow_over_100=True,
                ),
                "median_fact_plan": b.add(
                    "mio.measure.median_fact_plan", ratios.median(), unit="percent",
                    source="mio_shared.measure_evaluation", aggregation="median fact/plan",
                    allow_over_100=True,
                ),
            }

    # Financing MіO: restore paired financial/physical comparison and top gaps.
    if financing is not None and not financing.empty:
        d = financing.copy()
        for column in ("% виконання", "Стан виконання заходу, %", "План, млрд грн", "Факт, млрд грн"):
            if column in d.columns:
                d[column] = pd.to_numeric(d[column], errors="coerce")
        facts = {
            "rows": b.add(
                "mio.fin.rows", len(d), unit="count", source="mio_shared.financing",
                aggregation="financing rows", observation_unit="measure",
            )
        }
        if "План, млрд грн" in d.columns and d["План, млрд грн"].notna().any():
            facts["plan_total"] = b.add(
                "mio.fin.plan_total", d["План, млрд грн"].sum(), unit="currency",
                source="mio_shared.financing", aggregation="sum plan",
            )
        if "Факт, млрд грн" in d.columns and d["Факт, млрд грн"].notna().any():
            facts["fact_total"] = b.add(
                "mio.fin.fact_total", d["Факт, млрд грн"].sum(), unit="currency",
                source="mio_shared.financing", aggregation="sum fact",
            )
        if {"% виконання", "Стан виконання заходу, %"}.issubset(d.columns):
            paired = d.dropna(subset=["% виконання", "Стан виконання заходу, %"]).copy()
            if not paired.empty:
                facts["paired_count"] = b.add(
                    "mio.fin.paired_count", len(paired), unit="count",
                    source="mio_shared.financing",
                    aggregation="paired financial/physical rows", observation_unit="measure",
                )
                facts["avg_financial_execution"] = b.add(
                    "mio.fin.avg_financial_execution", paired["% виконання"].mean(),
                    unit="percent", source="mio_shared.financing",
                    aggregation="mean financial execution", allow_over_100=True,
                )
                facts["avg_physical_execution"] = b.add(
                    "mio.fin.avg_physical_execution", paired["Стан виконання заходу, %"].mean(),
                    unit="percent", source="mio_shared.financing",
                    aggregation="mean physical execution", allow_over_100=True,
                )
                gaps = []
                for index, (_, row) in enumerate(paired.iterrows()):
                    financial_metric = b.add(
                        f"mio.fin.row.{index}.financial_execution_pct", row["% виконання"],
                        unit="percent", source="mio_shared.financing",
                        aggregation="row financial execution", allow_over_100=True,
                    )
                    physical_metric = b.add(
                        f"mio.fin.row.{index}.physical_execution_pct", row["Стан виконання заходу, %"],
                        unit="percent", source="mio_shared.financing",
                        aggregation="row physical execution", allow_over_100=True,
                    )
                    gap = b.pp(
                        f"mio.fin.row.{index}.gap_pp", financial_metric, physical_metric,
                        source="mio_shared.financing", aggregation="financial minus physical",
                    )
                    gaps.append((abs(float(gap)), row, gap, financial_metric, physical_metric))
                largest = []
                for _, row, gap, financial_metric, physical_metric in sorted(
                    gaps, key=lambda item: item[0], reverse=True
                )[:4]:
                    item = {
                        key: row.get(key)
                        for key in ("Захід", "Назва заходу")
                        if key in paired.columns
                    }
                    item.update({
                        "% виконання": financial_metric,
                        "Стан виконання заходу, %": physical_metric,
                        "_gap": gap,
                    })
                    largest.append(item)
                facts["largest_gaps"] = largest
        b.structures["mio.financing"] = facts


def build_analytical_facts(
    *, filters: Mapping[str, Any], metrics: Mapping[str, Any], goal_progress: pd.DataFrame,
    task_progress: pd.DataFrame, department_progress: pd.DataFrame, product_progress: pd.DataFrame,
    status_counts: pd.DataFrame, period_dynamics: pd.DataFrame, active: pd.DataFrame,
    mio_goal_evaluation: pd.DataFrame, mio_goal_task_evaluation: pd.DataFrame,
    mio_measure_evaluation: pd.DataFrame, mio_financing: pd.DataFrame,
) -> PreparedAnalyticalFacts:
    b = _Builder(filters)
    for year in sorted({int(y) for y in (filters.get("years", []) or []) if str(y).isdigit()}):
        b.add(f"scope.year.{year}", year, unit="number", source="analytics.filters.years", aggregation="selected year")
    for name, frame in (
        ("goal_progress", goal_progress), ("task_progress", task_progress),
        ("department_progress", department_progress), ("product_progress", product_progress),
        ("status_counts", status_counts), ("period_dynamics", period_dynamics), ("active", active),
        ("mio_goal_evaluation", mio_goal_evaluation), ("mio_goal_task_evaluation", mio_goal_task_evaluation),
        ("mio_measure_evaluation", mio_measure_evaluation), ("mio_financing", mio_financing),
    ):
        _register_frame_sources(b, name, frame)

    b.add("scope.department_count", len(department_progress) if department_progress is not None else 0, unit="count", source="analytics.department_progress", aggregation="selected departments", observation_unit="department")
    b.add("scope.product_count", len(product_progress) if product_progress is not None else 0, unit="count", source="analytics.product_progress", aggregation="selected product types", observation_unit="product")

    percent_keys = {"completion", "coverage", "coverage_latest", "goal_completion"}
    count_tokens = ("count", "rows", "measures", "goals", "tasks", "no_data", "completed", "submitted", "attention")
    for key, value in metrics.items():
        if _safe_number(value) is None:
            continue
        unit = "percent" if key in percent_keys else ("count" if any(t in key.lower() for t in count_tokens) else "number")
        observation = "unique-measure" if key in {"unique_measures", "latest_measure_count", "no_data", "completed", "submitted", "attention_count", "attention_assessed_count"} else None
        b.add(f"page.{key}", value, unit=unit, source=f"analytics.page.metrics.{key}", aggregation="prepared page metric", allow_over_100=(unit == "percent" and float(value) > 100), observation_unit=observation)

    execution = _safe_number(metrics.get("completion")); goal_execution = _safe_number(metrics.get("goal_completion"))
    if execution is not None and goal_execution is not None:
        b.pp("overall.measure_goal_gap_pp", execution, goal_execution, source="analytics.page.metrics", aggregation="latest measure execution minus latest goal execution")
    coverage_avg, coverage_latest = _safe_number(metrics.get("coverage")), _safe_number(metrics.get("coverage_latest"))
    if coverage_avg is not None and coverage_latest is not None:
        b.pp("overall.coverage_latest_minus_average_pp", coverage_latest, coverage_avg, source="analytics.page.metrics", aggregation="latest coverage minus selected-period mean coverage")
    latest_n = _safe_int(metrics.get("latest_measure_count")); missing_n = _safe_int(metrics.get("no_data")); attention_n = _safe_int(metrics.get("attention_count"))
    if latest_n > 0:
        b.ratio_pct("overall.missing_latest_share_pct", missing_n, latest_n, source="analytics.page.metrics", aggregation="current missing-submission share", numerator_unit="unique-measure", denominator_unit="unique-measure")
        b.ratio_pct("overall.attention_latest_share_pct", attention_n, latest_n, source="analytics.page.metrics", aggregation="current management-attention share", numerator_unit="unique-measure", denominator_unit="unique-measure")

    _prepare_trajectory(b, period_dynamics)
    for frame, kind in ((goal_progress, "goal"), (task_progress, "task"), (department_progress, "department")):
        _prepare_distribution(b, frame, kind, execution)
        _prepare_current_concentration(b, frame, kind, "Актуальна_увага", "attention")
        _prepare_current_concentration(b, frame, kind, "Без_даних", "missing")
    _prepare_status(b, status_counts, active)
    _prepare_product(b, product_progress)
    _prepare_drilldowns(b, goal_progress, task_progress, department_progress, active)
    _prepare_ssp_and_risk(b, department_progress, metrics)
    _prepare_missing_persistence(b, active)
    years = sorted({int(y) for y in (filters.get("years", []) or []) if str(y).isdigit()}); year = max(years) if years else 2026
    _prepare_mio(b, mio_goal_evaluation, mio_goal_task_evaluation, mio_measure_evaluation, mio_financing, year, task_progress)
    return PreparedAnalyticalFacts(metrics=dict(b.metrics), structures=dict(b.structures))
