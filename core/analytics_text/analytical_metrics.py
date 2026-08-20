from __future__ import annotations

"""Prepared numerical facts for the rule-based Analytics narrative.

This module is the only analytics-text layer allowed to create user-facing
numerical derivatives. Dashboard and MIO values are consumed as prepared shared
outputs; additional descriptive metrics are calculated here once, before
signals/findings/composition. Percentage values are stored in percentage form
(0..100 unless the metric explicitly allows values above 100).
"""

from dataclasses import dataclass, field
from typing import Any, Mapping
from statistics import pstdev

import pandas as pd

from .config import DELTA_LANGUAGE_BANDS




class MetricFloat(float):
    """Numeric fact value bound to one concrete factual metric code."""
    def __new__(cls, value: float, metric_code: str):
        obj = float.__new__(cls, value)
        obj.metric_code = metric_code
        return obj


class MetricInt(int):
    """Integer fact value bound to one concrete factual metric code."""
    def __new__(cls, value: int, metric_code: str):
        obj = int.__new__(cls, value)
        obj.metric_code = metric_code
        return obj


def metric_code_of(value: Any) -> str | None:
    code = getattr(value, "metric_code", None)
    return str(code) if code else None


def bind_metric_value(metric: "FactualMetric") -> int | float:
    if metric.unit == "count":
        return MetricInt(int(metric.value), metric.code)
    return MetricFloat(float(metric.value), metric.code)


@dataclass(frozen=True)
class FactualMetric:
    code: str
    value: float | int
    unit: str  # percent | pp | count | number | currency
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

    def add(self, code: str, value: Any, *, unit: str, source: str, aggregation: str,
            numerator: Any = None, denominator: Any = None, dependencies: tuple[str, ...] = (),
            allow_over_100: bool = False, observation_unit: str | None = None) -> Any:
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
        if unit == "percent" and not allow_over_100 and not (0.0 <= float(number) <= 100.0):
            raise ValueError(f"Analytical metric {code} outside 0..100%: {number}")
        if denominator is not None:
            try:
                den = float(denominator)
                if den <= 0:
                    raise ValueError(f"Analytical metric {code} has non-positive denominator: {denominator}")
            except (TypeError, ValueError):
                raise ValueError(f"Analytical metric {code} has invalid denominator: {denominator}")
        metric = FactualMetric(
            code=code, value=number, unit=unit, source=source, aggregation=aggregation,
            numerator=numerator, denominator=denominator, dependencies=dependencies,
            scope=self.scope, allow_over_100=allow_over_100, observation_unit=observation_unit,
        )
        self.metrics[code] = metric
        return bind_metric_value(metric)

    def ratio_pct(self, code: str, numerator: Any, denominator: Any, *, source: str, aggregation: str,
                  numerator_unit: str, denominator_unit: str, dependencies: tuple[str, ...] = ()) -> float | None:
        if numerator_unit != denominator_unit:
            raise ValueError(f"Incompatible units for {code}: {numerator_unit} / {denominator_unit}")
        try:
            num, den = float(numerator), float(denominator)
        except (TypeError, ValueError):
            return None
        if den <= 0:
            return None
        value = num / den * 100.0
        return self.add(code, value, unit="percent", source=source, aggregation=aggregation,
                        numerator=numerator, denominator=denominator, dependencies=dependencies,
                        observation_unit=numerator_unit)

    def pp(self, code: str, left: Any, right: Any, *, source: str, aggregation: str,
           dependencies: tuple[str, ...] = ()) -> float | None:
        try:
            value = float(left) - float(right)
        except (TypeError, ValueError):
            return None
        return self.add(code, value, unit="pp", source=source, aggregation=aggregation,
                        dependencies=dependencies)


def _safe_number(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    try:
        if value is None or pd.isna(value):
            return 0
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return 0


def _label(row: pd.Series, kind: str) -> str:
    def s(v: Any) -> str:
        try:
            if v is None or pd.isna(v): return ""
        except (TypeError, ValueError): return ""
        return str(v).strip()
    if kind == "goal":
        code=s(row.get("goal_code")); return f"СЦ {code}" if code and not code.upper().startswith("СЦ") else code
    if kind == "task":
        code=s(row.get("task_code")); name=s(row.get("task_name")); return f"{code} — {name}" if code and name else (code or name)
    if kind == "department": return s(row.get("department")) or s(row.get("ssp_index"))
    if kind == "product": return s(row.get("product_type"))
    return ""


def _numeric(frame: pd.DataFrame, col: str, default: float | None = None) -> pd.Series:
    if col in frame.columns: return pd.to_numeric(frame[col], errors="coerce")
    fill=float("nan") if default is None else default
    return pd.Series(fill,index=frame.index,dtype=float)


def _prepare_distribution(b: _Builder, frame: pd.DataFrame, kind: str, overall: float | None) -> None:
    if frame is None or frame.empty or "Виконання" not in frame.columns: return
    d=frame.copy(); d["_exec"]=_numeric(d,"Виконання"); d=d.dropna(subset=["_exec"])
    if d.empty: return
    d["_label"]=[_label(r,kind) for _,r in d.iterrows()]; d=d[d["_label"].astype(bool)].copy()
    if d.empty: return
    vals=d["_exec"].astype(float); src=f"analytics.{kind}_progress"
    best=d.loc[vals.idxmax()]; worst=d.loc[vals.idxmin()]
    prefix=f"{kind}.distribution"
    facts={
        "count": b.add(f"{prefix}.count",len(d),unit="count",source=src,aggregation="entities",observation_unit=kind),
        "mean": b.add(f"{prefix}.mean",vals.mean(),unit="percent",source=src,aggregation="mean execution"),
        "median": b.add(f"{prefix}.median",vals.median(),unit="percent",source=src,aggregation="median execution"),
        "reference": b.add(f"{prefix}.reference",overall if overall is not None else vals.mean(),unit="percent",source="dashboard.execution" if overall is not None else src,aggregation="reference execution"),
        "best_label":best["_label"],"best_value":b.add(f"{prefix}.best",best["_exec"],unit="percent",source=src,aggregation="maximum execution"),
        "worst_label":worst["_label"],"worst_value":b.add(f"{prefix}.worst",worst["_exec"],unit="percent",source=src,aggregation="minimum execution"),
    }
    facts["gap"]=b.pp(f"{prefix}.gap_pp",facts["best_value"],facts["worst_value"],source=src,aggregation="best minus worst",dependencies=(f"{prefix}.best",f"{prefix}.worst"))
    ref=float(facts["reference"]); above=int((vals>ref).sum()); below=int((vals<ref).sum()); equal=int(len(vals)-above-below)
    facts.update({
        "above_reference":b.add(f"{prefix}.above_reference",above,unit="count",source=src,aggregation="entities above reference",observation_unit=kind),
        "below_reference":b.add(f"{prefix}.below_reference",below,unit="count",source=src,aggregation="entities below reference",observation_unit=kind),
        "equal_reference":b.add(f"{prefix}.equal_reference",equal,unit="count",source=src,aggregation="entities equal reference",observation_unit=kind),
        "top":[(r["_label"],b.add(f"{prefix}.top.{i}.value",r["_exec"],unit="percent",source=src,aggregation=f"rank {i} execution")) for i,(_,r) in enumerate(d.sort_values("_exec",ascending=False).head(3).iterrows(),1)],
        "bottom":[(r["_label"],b.add(f"{prefix}.bottom.{i}.value",r["_exec"],unit="percent",source=src,aggregation=f"bottom rank {i} execution")) for i,(_,r) in enumerate(d.sort_values("_exec").head(3).iterrows(),1)],
    })
    b.structures[prefix]=facts
    if "Зміна" in d.columns:
        d["_change"]=_numeric(d,"Зміна"); c=d.dropna(subset=["_change"])
        if not c.empty:
            small=float(DELTA_LANGUAGE_BANDS["small"]); stable=c[c["_change"].abs()<small]; improved=c[c["_change"]>=small]; declined=c[c["_change"]<=-small]
            hi=c.loc[c["_change"].idxmax()]; lo=c.loc[c["_change"].idxmin()]; cp=f"{kind}.change"
            cf={
                "count_with_change":b.add(f"{cp}.count",len(c),unit="count",source=src,aggregation="comparable entities",observation_unit=kind),
                "improved":b.add(f"{cp}.improved_count",len(improved),unit="count",source=src,aggregation="improved entities",observation_unit=kind),
                "declined":b.add(f"{cp}.declined_count",len(declined),unit="count",source=src,aggregation="declined entities",observation_unit=kind),
                "stable":b.add(f"{cp}.stable_count",len(stable),unit="count",source=src,aggregation="stable entities",observation_unit=kind),
                "largest_improvement_label":hi["_label"],"largest_improvement":b.add(f"{cp}.largest_improvement_pp",hi["_change"],unit="pp",source=src,aggregation="maximum change"),
                "largest_deterioration_label":lo["_label"],"largest_deterioration":b.add(f"{cp}.largest_deterioration_pp",lo["_change"],unit="pp",source=src,aggregation="minimum change"),
            }
            cf["improved_share"]=b.ratio_pct(f"{cp}.improved_share_pct",len(improved),len(c),source=src,aggregation="share improved",numerator_unit=kind,denominator_unit=kind)
            cf["declined_share"]=b.ratio_pct(f"{cp}.declined_share_pct",len(declined),len(c),source=src,aggregation="share declined",numerator_unit=kind,denominator_unit=kind)
            b.structures[cp]=cf


def _prepare_concentration(b:_Builder, frame:pd.DataFrame, kind:str, count_col:str, topic:str, active:pd.DataFrame)->None:
    key=f"{kind}.{topic}"; src=f"analytics.{kind}_progress.{count_col}"
    if frame is None or frame.empty or count_col not in frame.columns:return
    d=frame.copy(); counts=pd.to_numeric(d[count_col],errors="coerce").fillna(0); total=int(counts.sum())
    if total<=0:
        b.structures[key]={"total":b.add(f"{key}.total",0,unit="count",source=src,aggregation="total",observation_unit="measure-period")};return
    d["_count"]=counts.astype(int); d["_label"]=[_label(r,kind) for _,r in d.iterrows()]; ranked=d.sort_values("_count",ascending=False); top=ranked.iloc[0]; top3=ranked.head(3); top3_count=int(top3["_count"].sum()); affected=int((d["_count"]>0).sum())
    f={
      "total":b.add(f"{key}.total",total,unit="count",source=src,aggregation="total",observation_unit="measure-period"),
      "affected_entities":b.add(f"{key}.affected_entities",affected,unit="count",source=src,aggregation="affected entities",observation_unit=kind),
      "entity_count":b.add(f"{key}.entity_count",len(d),unit="count",source=src,aggregation="entities",observation_unit=kind),
      "top_label":top["_label"],"top_count":b.add(f"{key}.top_count",int(top["_count"]),unit="count",source=src,aggregation="top count",observation_unit="measure-period"),
      "top3_count":b.add(f"{key}.top3_count",top3_count,unit="count",source=src,aggregation="top3 count",observation_unit="measure-period"),
      "top3":[(r["_label"],int(r["_count"])) for _,r in top3.iterrows() if int(r["_count"])>0],
    }
    f["top_share"]=b.ratio_pct(f"{key}.top_share_pct",f["top_count"],f["total"],source=src,aggregation="top1 concentration",numerator_unit="measure-period",denominator_unit="measure-period")
    f["top3_share"]=b.ratio_pct(f"{key}.top3_share_pct",f["top3_count"],f["total"],source=src,aggregation="top3 concentration",numerator_unit="measure-period",denominator_unit="measure-period")
    portfolios=None
    if "Унікальних_заходів" in d.columns: portfolios=pd.to_numeric(d["Унікальних_заходів"],errors="coerce").fillna(0)
    elif "portfolio_measure_count" in d.columns: portfolios=pd.to_numeric(d["portfolio_measure_count"],errors="coerce").fillna(0)
    if portfolios is not None:
        idx=top.name; portfolio=int(portfolios.loc[idx]) if idx in portfolios.index else 0; total_portfolio=int(portfolios.sum())
        f["top_portfolio_size"]=b.add(f"{key}.top_portfolio_size",portfolio,unit="count",source=f"analytics.{kind}_portfolio",aggregation="top portfolio size",observation_unit="unique-measure")
        # Never divide measure-period problem/missing rows by a unique-measure portfolio.
        # If row-level canonical data are available, prepare the internal rate from
        # compatible measure-period numerator and denominator instead.
        f["top_internal_rate"] = None
        dim_col = {"goal": "goal_code", "task": "task_code", "department": "department"}.get(kind)
        flag_col = "is_problem_status" if topic == "problems" else "missing_required_submission"
        if active is not None and not active.empty and dim_col in active.columns and flag_col in active.columns:
            raw_label = str(top["_label"] or "").strip()
            lookup_label = raw_label[3:].strip() if kind == "goal" and raw_label.startswith("СЦ ") else raw_label
            part = active[active[dim_col].astype(str).eq(lookup_label)]
            denominator_rows = int(len(part))
            numerator_rows = int(part[flag_col].fillna(False).astype(bool).sum()) if denominator_rows else 0
            f["top_internal_row_count"] = b.add(f"{key}.top_internal_row_count", numerator_rows, unit="count", source=f"analytics.active.{flag_col}", aggregation="flagged rows in top entity", observation_unit="measure-period")
            f["top_internal_row_denominator"] = b.add(f"{key}.top_internal_row_denominator", denominator_rows, unit="count", source="analytics.active", aggregation="rows in top entity", observation_unit="measure-period")
            if denominator_rows > 0:
                f["top_internal_rate"] = b.ratio_pct(f"{key}.top_internal_rate_pct", numerator_rows, denominator_rows, source=f"analytics.active.{flag_col}", aggregation="internal flagged-row rate", numerator_unit="measure-period", denominator_unit="measure-period")
        if total_portfolio>0:
            f["top_portfolio_share"]=b.ratio_pct(f"{key}.top_portfolio_share_pct",portfolio,total_portfolio,source=f"analytics.{kind}_portfolio",aggregation="portfolio weight",numerator_unit="unique-measure",denominator_unit="unique-measure")
            if f["top_share"] is not None:
                f["concentration_excess_pp"]=b.pp(f"{key}.concentration_excess_pp",f["top_share"],f["top_portfolio_share"],source="analytics.derived",aggregation="concentration minus portfolio weight",dependencies=(f"{key}.top_share_pct",f"{key}.top_portfolio_share_pct"))
    b.structures[key]=f


def _prepare_trajectory(b:_Builder, period:pd.DataFrame)->None:
    if period is None or period.empty or "Виконання" not in period.columns:return
    d=period.copy(); qmap={"I":1,"II":2,"III":3,"IV":4,"1":1,"2":2,"3":3,"4":4}; d["_year"]=pd.to_numeric(d.get("report_year"),errors="coerce"); d["_q"]=d.get("report_quarter",pd.Series(index=d.index,dtype=object)).astype(str).map(qmap); d=d.sort_values(["_year","_q"],na_position="last"); d["_exec"]=_numeric(d,"Виконання"); d=d.dropna(subset=["_exec"])
    if d.empty:return
    periods=[str(x).strip() for x in d.get("Період",pd.Series(range(len(d)))).tolist()]; raw_vals=[float(x) for x in d["_exec"]]
    vals=[b.add(f"trajectory.period.{i}.execution", value, unit="percent", source="dashboard.period_dynamics", aggregation=f"period {i} execution") for i,value in enumerate(raw_vals)]
    f={"period_count":b.add("trajectory.period_count",len(vals),unit="count",source="dashboard.period_dynamics",aggregation="evaluated periods",observation_unit="period"),"periods":periods,"values":vals,"first_period":periods[0],"last_period":periods[-1]}
    f["first"]=b.add("trajectory.first_execution",vals[0],unit="percent",source="dashboard.period_dynamics",aggregation="first period execution"); f["last"]=b.add("trajectory.last_execution",vals[-1],unit="percent",source="dashboard.period_dynamics",aggregation="last period execution")
    if len(vals)>=2:
        deltas=[]
        for i in range(1,len(vals)):
            delta=b.pp(f"trajectory.step.{i}.delta_pp",vals[i],vals[i-1],source="dashboard.period_dynamics",aggregation="period over period delta"); deltas.append(delta)
        f["deltas"]=deltas; f["cumulative_delta"]=b.pp("trajectory.cumulative_delta_pp",vals[-1],vals[0],source="dashboard.period_dynamics",aggregation="last minus first")
        max_up=max(deltas); max_down=min(deltas); f["max_increase"]=max_up; f["max_decrease"]=max_down; f["max_increase_period"]=periods[deltas.index(max_up)+1]; f["max_decrease_period"]=periods[deltas.index(max_down)+1]
        small=float(DELTA_LANGUAGE_BANDS["small"])
        f["positive_steps"]=b.add("trajectory.positive_step_count",sum(x>=small for x in deltas),unit="count",source="analytics.derived.trajectory",aggregation="positive period changes",observation_unit="period-transition")
        f["negative_steps"]=b.add("trajectory.negative_step_count",sum(x<=-small for x in deltas),unit="count",source="analytics.derived.trajectory",aggregation="negative period changes",observation_unit="period-transition")
        f["flat_steps"]=b.add("trajectory.flat_step_count",sum(abs(x)<small for x in deltas),unit="count",source="analytics.derived.trajectory",aggregation="near-flat period changes",observation_unit="period-transition")
        if len(deltas)>=2: f["previous_delta"]=deltas[-2]; f["latest_delta"]=deltas[-1]
        if len(vals)>=3:
            f["volatility_stddev"]=b.add("trajectory.volatility_stddev_pp",pstdev(vals),unit="pp",source="analytics.derived.trajectory",aggregation="population stddev of period execution",dependencies=tuple(f"trajectory.step.{i}.delta_pp" for i in range(1,len(vals))))
    cov=_numeric(d,"Покриття_%")
    if cov.notna().any():
        cv=[None if pd.isna(x) else b.add(f"trajectory.period.{i}.coverage",float(x),unit="percent",source="dashboard.period_dynamics",aggregation=f"period {i} coverage") for i,x in enumerate(cov.tolist())]; f["coverage_values"]=cv
        coverage_deltas=[]
        for i in range(1,len(cv)):
            if cv[i] is not None and cv[i-1] is not None:
                coverage_deltas.append(b.pp(f"trajectory.coverage_step.{i}.delta_pp",cv[i],cv[i-1],source="dashboard.period_dynamics",aggregation="coverage period over period delta"))
            else:
                coverage_deltas.append(None)
        f["coverage_deltas"]=coverage_deltas
        if cv[0] is not None and cv[-1] is not None:
            f["coverage_first"]=b.add("trajectory.coverage_first",cv[0],unit="percent",source="dashboard.period_dynamics",aggregation="first coverage"); f["coverage_last"]=b.add("trajectory.coverage_last",cv[-1],unit="percent",source="dashboard.period_dynamics",aggregation="last coverage"); f["coverage_cumulative_delta"]=b.pp("trajectory.coverage_cumulative_delta_pp",cv[-1],cv[0],source="dashboard.period_dynamics",aggregation="coverage last minus first")
    b.structures["trajectory"]=f


def _prepare_status(b:_Builder,status_counts:pd.DataFrame,active:pd.DataFrame)->None:
    if status_counts is None or status_counts.empty or not {"status","Кількість"}.issubset(status_counts.columns):return
    raw_rows=[(str(r["status"]),_safe_int(r["Кількість"])) for _,r in status_counts.iterrows()]; total=sum(v for _,v in raw_rows)
    rows=[(label,b.add(f"status.count.{i}",count,unit="count",source="dashboard.status_counts",aggregation=f"status {label} count",observation_unit="measure-period")) for i,(label,count) in enumerate(raw_rows)]
    if total<=0:return
    ranked=sorted(rows,key=lambda x:x[1],reverse=True); shares={}
    for label,count in rows: shares[label]=b.ratio_pct(f"status.share.{label}",count,total,source="dashboard.status_counts",aggregation="status share",numerator_unit="measure-period",denominator_unit="measure-period")
    f={"total":b.add("status.total",total,unit="count",source="dashboard.status_counts",aggregation="total statuses",observation_unit="measure-period"),"ranked":ranked,"shares":shares,"dominant_label":ranked[0][0],"dominant_count":ranked[0][1],"dominant_share":shares.get(ranked[0][0])}
    # period comparison shares
    if active is not None and not active.empty and {"report_year","report_quarter","status"}.issubset(active.columns):
        d=active.copy(); qmap={"I":1,"II":2,"III":3,"IV":4,"1":1,"2":2,"3":3,"4":4}; d["_year"]=pd.to_numeric(d["report_year"],errors="coerce"); d["_q"]=d["report_quarter"].astype(str).map(qmap); d=d.dropna(subset=["_year","_q"]); periods=sorted({(int(y),int(q)) for y,q in zip(d["_year"],d["_q"])})
        if len(periods)>=2:
            inv={1:"I",2:"II",3:"III",4:"IV"}; pk,lk=periods[-2],periods[-1]
            def one(key):
                y,q=key; part=d[(d["_year"]==y)&(d["_q"]==q)]; counts={str(k):int(v) for k,v in part["status"].fillna("н/д").astype(str).value_counts().to_dict().items()}; n=len(part); sh={}
                for lab,c in counts.items(): sh[lab]=b.ratio_pct(f"status.period.{y}.{q}.{lab}.share_pct",c,n,source="analytics.active.status",aggregation="period status share",numerator_unit="measure-period",denominator_unit="measure-period") if n else None
                total_metric=b.add(f"status.period.{y}.{q}.total",n,unit="count",source="analytics.active.status",aggregation="period status total",observation_unit="measure-period")
                return total_metric,counts,sh
            pn,pc,ps=one(pk); ln,lc,ls=one(lk); changes={};
            for lab in sorted(set(ps)|set(ls)):
                changes[lab]=b.pp(f"status.period_change.{lab}.pp",ls.get(lab,0.0) or 0.0,ps.get(lab,0.0) or 0.0,source="analytics.active.status",aggregation="latest share minus previous")
            f["period_comparison"]={"previous_period":f"{pk[0]} {inv.get(pk[1],pk[1])}","latest_period":f"{lk[0]} {inv.get(lk[1],lk[1])}","previous_total":pn,"latest_total":ln,"previous_counts":pc,"latest_counts":lc,"previous_shares":ps,"latest_shares":ls,"share_changes_pp":changes}
    b.structures["status"]=f


def _prepare_product(b:_Builder,frame:pd.DataFrame)->None:
    if frame is None or frame.empty:return
    d=frame.copy(); d["_portfolio"]=_numeric(d,"Унікальних_заходів",0).fillna(0); d["_exec"]=_numeric(d,"Виконання"); d["_problems"]=_numeric(d,"Проблемних",0).fillna(0); d["_missing"]=_numeric(d,"Без_даних",0).fillna(0); ranked=d.sort_values("_portfolio",ascending=False); top=ranked.iloc[0]; total_size=int(d["_portfolio"].sum()); problem_total=int(d["_problems"].sum()); missing_total=int(d["_missing"].sum()); f={"count":b.add("product.count",len(d),unit="count",source="dashboard.product_progress",aggregation="product types",observation_unit="product"),"largest_label":_label(top,"product"),"largest_size":b.add("product.largest_size",int(top["_portfolio"]),unit="count",source="dashboard.product_progress",aggregation="largest product portfolio size",observation_unit="unique-measure"),"total_size":b.add("product.total_size",total_size,unit="count",source="dashboard.product_progress",aggregation="total product portfolio size",observation_unit="unique-measure"),"problem_total":b.add("product.problem_total",problem_total,unit="count",source="dashboard.product_progress",aggregation="product problem rows",observation_unit="measure-period"),"missing_total":b.add("product.missing_total",missing_total,unit="count",source="dashboard.product_progress",aggregation="product missing rows",observation_unit="measure-period")}
    if total_size: f["largest_share"]=b.ratio_pct("product.largest_share_pct",f["largest_size"],total_size,source="dashboard.product_progress",aggregation="largest product portfolio share",numerator_unit="unique-measure",denominator_unit="unique-measure")
    valid=d.dropna(subset=["_exec"])
    if len(valid)>=2:
        best=valid.loc[valid["_exec"].idxmax()]; worst=valid.loc[valid["_exec"].idxmin()]; f.update({"best_label":_label(best,"product"),"best_value":b.add("product.best_execution",best["_exec"],unit="percent",source="dashboard.product_progress",aggregation="maximum execution"),"worst_label":_label(worst,"product"),"worst_value":b.add("product.worst_execution",worst["_exec"],unit="percent",source="dashboard.product_progress",aggregation="minimum execution")}); f["gap"]=b.pp("product.execution_gap_pp",f["best_value"],f["worst_value"],source="dashboard.product_progress",aggregation="best minus worst")
    if problem_total>0:
        r=d.loc[d["_problems"].idxmax()]; c=int(r["_problems"]); f.update({"top_problem_label":_label(r,"product"),"top_problem_count":b.add("product.top_problem_count",c,unit="count",source="dashboard.product_progress",aggregation="top product problem rows",observation_unit="measure-period"),"top_problem_share":b.ratio_pct("product.top_problem_share_pct",c,problem_total,source="dashboard.product_progress",aggregation="problem concentration",numerator_unit="measure-period",denominator_unit="measure-period")})
    if missing_total>0:
        r=d.loc[d["_missing"].idxmax()]; c=int(r["_missing"]); f.update({"top_missing_label":_label(r,"product"),"top_missing_count":b.add("product.top_missing_count",c,unit="count",source="dashboard.product_progress",aggregation="top product missing rows",observation_unit="measure-period"),"top_missing_share":b.ratio_pct("product.top_missing_share_pct",c,missing_total,source="dashboard.product_progress",aggregation="missing concentration",numerator_unit="measure-period",denominator_unit="measure-period")})
    b.structures["product"]=f


def _prepare_mio(b:_Builder,goals:pd.DataFrame,tasks:pd.DataFrame,measures:pd.DataFrame,fin:pd.DataFrame,year:int,task_progress:pd.DataFrame)->None:
    int_col,meas_col,task_col,prog_col=(f"Інтеграл {year}",f"Заходи {year}",f"Завдання {year}",f"Прогрес {year}")
    if goals is not None and not goals.empty and int_col in goals.columns:
        d=goals.copy()
        for c in (int_col,meas_col,task_col,prog_col):
            if c in d.columns:d[c]=pd.to_numeric(d[c],errors="coerce")
        v=d.dropna(subset=[int_col])
        if not v.empty:
            best=v.sort_values(int_col,ascending=False).iloc[0]; worst=v.sort_values(int_col).iloc[0]
            f={
                "year":year,
                "goals_count":b.add("mio.goal_count",len(v),unit="count",source="mio_shared.goal_evaluation",aggregation="evaluated goals",observation_unit="goal"),
                "average_integral":b.add("mio.average_integral",v[int_col].mean(),unit="percent",source="mio_shared.goal_evaluation",aggregation="mean goal integral",allow_over_100=True),
                "best_code":str(best.get("Код","")),"best_name":str(best.get("Ціль","")),
                "best_integral":b.add("mio.best_integral",best[int_col],unit="percent",source="mio_shared.goal_evaluation",aggregation="maximum integral",allow_over_100=True),
                "worst_code":str(worst.get("Код","")),"worst_name":str(worst.get("Ціль","")),
                "worst_integral":b.add("mio.worst_integral",worst[int_col],unit="percent",source="mio_shared.goal_evaluation",aggregation="minimum integral",allow_over_100=True),
            }
            f["gap"]=b.pp("mio.integral_gap_pp",f["best_integral"],f["worst_integral"],source="mio_shared.goal_evaluation",aggregation="best minus worst")
            for c,key,code in ((meas_col,"average_measures","mio.average_measures"),(task_col,"average_tasks","mio.average_tasks"),(prog_col,"average_progress","mio.average_progress")):
                if c in v.columns and v[c].notna().any():f[key]=b.add(code,v[c].dropna().mean(),unit="percent",source="mio_shared.goal_evaluation",aggregation="mean component",allow_over_100=True)
            div=[]
            for i,(_,r) in enumerate(v.iterrows()):
                m=_safe_number(r.get(meas_col)); integ=_safe_number(r.get(int_col)); prog=_safe_number(r.get(prog_col))
                if m is not None and integ is not None:
                    m_metric=b.add(f"mio.goal.{i}.measure_execution_pct",m,unit="percent",source="mio_shared.goal_evaluation",aggregation="goal measure component",allow_over_100=True)
                    integ_metric=b.add(f"mio.goal.{i}.integral_pct",integ,unit="percent",source="mio_shared.goal_evaluation",aggregation="goal integral",allow_over_100=True)
                    prog_metric=b.add(f"mio.goal.{i}.progress_pct",prog,unit="percent",source="mio_shared.goal_evaluation",aggregation="goal strategic progress",allow_over_100=True) if prog is not None else None
                    gap=b.pp(f"mio.goal.{i}.measure_integral_gap_pp",m_metric,integ_metric,source="mio_shared.goal_evaluation",aggregation="measure execution minus integral")
                    if abs(float(gap))>=10:div.append({"code":str(r.get("Код","")),"name":str(r.get("Ціль","")),"measure_execution":m_metric,"integral":integ_metric,"gap":gap,"progress":prog_metric})
            f["divergences"]=sorted(div,key=lambda x:abs(float(x["gap"])),reverse=True)[:4]; b.structures["mio.goals"]=f
    score_col=f"Оцінка {year}"
    if tasks is not None and not tasks.empty and {"Рівень","Код",score_col}.issubset(tasks.columns):
        t=tasks[tasks["Рівень"].astype(str).eq("task")].copy(); t[score_col]=pd.to_numeric(t[score_col],errors="coerce"); scores=t.groupby(t["Код"].astype(str))[score_col].mean().dropna()
        if not scores.empty:
            f={
                "year":year,
                "tasks_count":b.add("mio.task_count",len(scores),unit="count",source="mio_shared.goal_task_evaluation",aggregation="evaluated tasks",observation_unit="task"),
                "average_task_indicator_progress":b.add("mio.task.average_indicator_progress",scores.mean(),unit="percent",source="mio_shared.goal_task_evaluation",aggregation="mean task indicator progress",allow_over_100=True),
                "best_task":str(scores.idxmax()),"best_task_progress":b.add("mio.task.best_progress",scores.max(),unit="percent",source="mio_shared.goal_task_evaluation",aggregation="maximum task progress",allow_over_100=True),
                "worst_task":str(scores.idxmin()),"worst_task_progress":b.add("mio.task.worst_progress",scores.min(),unit="percent",source="mio_shared.goal_task_evaluation",aggregation="minimum task progress",allow_over_100=True),
            }; f["gap"]=b.pp("mio.task.progress_gap_pp",f["best_task_progress"],f["worst_task_progress"],source="mio_shared.goal_task_evaluation",aggregation="best minus worst")
            div=[]
            if task_progress is not None and not task_progress.empty and {"task_code","Виконання"}.issubset(task_progress.columns):
                tp=task_progress.copy();tp["_code"]=tp["task_code"].astype(str);tp["_exec"]=pd.to_numeric(tp["Виконання"],errors="coerce"); execs=tp.dropna(subset=["_exec"]).groupby("_code")["_exec"].mean()
                for i,(code,progress) in enumerate(scores.items()):
                    if code in execs.index:
                        ex_metric=b.add(f"mio.task.{i}.execution_pct",float(execs.loc[code]),unit="percent",source="dashboard.task_progress",aggregation="task execution")
                        prog_metric=b.add(f"mio.task.{i}.indicator_progress_pct",float(progress),unit="percent",source="mio_shared.goal_task_evaluation",aggregation="task indicator progress",allow_over_100=True)
                        gap=b.pp(f"mio.task.{i}.execution_indicator_gap_pp",ex_metric,prog_metric,source="mio_shared+dashboard.task_progress",aggregation="task execution minus indicator progress")
                        if abs(float(gap))>=10:div.append({"code":code,"execution":ex_metric,"indicator_progress":prog_metric,"gap":gap})
            f["divergences"]=sorted(div,key=lambda x:abs(float(x["gap"])),reverse=True)[:4];b.structures["mio.tasks"]=f
    if measures is not None and not measures.empty and "Факт/План, %" in measures.columns:
        ratios=pd.to_numeric(measures["Факт/План, %"],errors="coerce").dropna()
        if not ratios.empty:b.structures["mio.measures"]={"year":year,"measures_count":b.add("mio.measure_count",len(measures),unit="count",source="mio_shared.measure_evaluation",aggregation="measure rows",observation_unit="measure"),"evaluated_measures":b.add("mio.measure_evaluated_count",len(ratios),unit="count",source="mio_shared.measure_evaluation",aggregation="evaluated measures",observation_unit="measure"),"average_fact_plan":b.add("mio.measure.average_fact_plan",ratios.mean(),unit="percent",source="mio_shared.measure_evaluation",aggregation="mean fact/plan",allow_over_100=True),"median_fact_plan":b.add("mio.measure.median_fact_plan",ratios.median(),unit="percent",source="mio_shared.measure_evaluation",aggregation="median fact/plan",allow_over_100=True)}
    if fin is not None and not fin.empty:
        d=fin.copy()
        for c in ("% виконання","Стан виконання заходу, %","План, млрд грн","Факт, млрд грн"):
            if c in d.columns:d[c]=pd.to_numeric(d[c],errors="coerce")
        f={"rows":b.add("mio.fin.rows",len(d),unit="count",source="mio_shared.financing",aggregation="financing rows",observation_unit="measure")}
        if "План, млрд грн" in d.columns and d["План, млрд грн"].notna().any():f["plan_total"]=b.add("mio.fin.plan_total",d["План, млрд грн"].sum(),unit="currency",source="mio_shared.financing",aggregation="sum plan")
        if "Факт, млрд грн" in d.columns and d["Факт, млрд грн"].notna().any():f["fact_total"]=b.add("mio.fin.fact_total",d["Факт, млрд грн"].sum(),unit="currency",source="mio_shared.financing",aggregation="sum fact")
        if {"% виконання","Стан виконання заходу, %"}.issubset(d.columns):
            p=d.dropna(subset=["% виконання","Стан виконання заходу, %"]).copy()
            if not p.empty:
                f["paired_count"]=b.add("mio.fin.paired_count",len(p),unit="count",source="mio_shared.financing",aggregation="paired financial/physical rows",observation_unit="measure")
                f["avg_financial_execution"]=b.add("mio.fin.avg_financial_execution",p["% виконання"].mean(),unit="percent",source="mio_shared.financing",aggregation="mean financial execution",allow_over_100=True)
                f["avg_physical_execution"]=b.add("mio.fin.avg_physical_execution",p["Стан виконання заходу, %"].mean(),unit="percent",source="mio_shared.financing",aggregation="mean physical execution",allow_over_100=True)
                gaps=[]
                for i,(_,r) in enumerate(p.iterrows()):
                    fin_metric=b.add(f"mio.fin.row.{i}.financial_execution_pct",r["% виконання"],unit="percent",source="mio_shared.financing",aggregation="row financial execution",allow_over_100=True)
                    phys_metric=b.add(f"mio.fin.row.{i}.physical_execution_pct",r["Стан виконання заходу, %"],unit="percent",source="mio_shared.financing",aggregation="row physical execution",allow_over_100=True)
                    g=b.pp(f"mio.fin.row.{i}.gap_pp",fin_metric,phys_metric,source="mio_shared.financing",aggregation="financial minus physical");gaps.append((abs(float(g)),r,g,fin_metric,phys_metric))
                top=[]
                for _,r,g,fin_metric,phys_metric in sorted(gaps,key=lambda x:x[0],reverse=True)[:4]:
                    item={k:r.get(k) for k in ("Захід","Назва заходу") if k in p.columns}
                    item.update({"% виконання":fin_metric,"Стан виконання заходу, %":phys_metric,"_gap":g});top.append(item)
                f["largest_gaps"]=top
        b.structures["mio.financing"]=f



def _prepare_yoy(b: _Builder, frame: pd.DataFrame) -> None:
    if frame is None or frame.empty:
        return
    pairs = [str(x) for x in frame["Період порівняння"].dropna().drop_duplicates().tolist()] if "Період порівняння" in frame.columns else [""]
    comparisons: list[dict[str, Any]] = []
    for pair_index, pair in enumerate(pairs):
        for year_token in __import__("re").findall(r"\b20\d{2}\b", pair):
            year_value = int(year_token)
            if f"scope.year.{year_value}" not in b.metrics:
                b.add(f"scope.year.{year_value}", year_value, unit="number", source="dashboard.yoy_comparison.Період порівняння", aggregation="comparison year")
        data = frame[frame["Період порівняння"].astype(str).eq(pair)].copy() if "Період порівняння" in frame.columns else frame.copy()
        metrics: dict[str, dict[str, Any]] = {}
        for row_index, (_, row) in enumerate(data.iterrows()):
            label = str(row.get("Показник") or "").strip()
            if not label:
                continue
            prev = _safe_number(row.get("Попередній рік")); cur = _safe_number(row.get("Поточний рік")); change = _safe_number(row.get("Зміна"))
            base = f"yoy.pair{pair_index}.{row_index}"
            previous = b.add(f"{base}.previous", prev, unit="percent" if "%" in str(row.get("Одиниця") or "") or "викон" in label.lower() or "покрит" in label.lower() else "number", source="dashboard.yoy_comparison", aggregation=f"{label} previous", allow_over_100=(prev is not None and prev > 100)) if prev is not None else None
            current = b.add(f"{base}.current", cur, unit="percent" if "%" in str(row.get("Одиниця") or "") or "викон" in label.lower() or "покрит" in label.lower() else "number", source="dashboard.yoy_comparison", aggregation=f"{label} current", allow_over_100=(cur is not None and cur > 100)) if cur is not None else None
            # The page already supplies YoY change. Register it; do not recompute.
            unit_text = str(row.get("Одиниця") or "").strip()
            change_unit = "pp" if "в.п" in unit_text.lower() or "викон" in label.lower() or "покрит" in label.lower() else "number"
            change_value = b.add(f"{base}.change", change, unit=change_unit, source="dashboard.yoy_comparison", aggregation=f"{label} change") if change is not None else None
            metrics[label] = {"previous": previous, "current": current, "change": change_value, "unit": unit_text}
        comparisons.append({"comparison": pair, "metrics": metrics})
    if not comparisons:
        return
    execution_changes = [c["metrics"].get("Рівень виконання СП", {}).get("change") for c in comparisons]
    execution_changes = [x for x in execution_changes if x is not None]
    coverage_changes = [c["metrics"].get("Покриття моніторингом", {}).get("change") for c in comparisons]
    coverage_changes = [x for x in coverage_changes if x is not None]
    f = {"comparison": comparisons[-1]["comparison"], "metrics": comparisons[-1]["metrics"], "comparisons": comparisons,
         "pair_count": b.add("yoy.pair_count", len(comparisons), unit="count", source="dashboard.yoy_comparison", aggregation="comparison intervals", observation_unit="year-transition"),
         "execution_changes": execution_changes, "coverage_changes": coverage_changes}
    if execution_changes:
        f["execution_positive_count"] = b.add("yoy.execution_positive_count", sum(x > 0 for x in execution_changes), unit="count", source="dashboard.yoy_comparison", aggregation="positive YoY execution transitions", observation_unit="year-transition")
        f["execution_negative_count"] = b.add("yoy.execution_negative_count", sum(x < 0 for x in execution_changes), unit="count", source="dashboard.yoy_comparison", aggregation="negative YoY execution transitions", observation_unit="year-transition")
    if coverage_changes:
        f["coverage_positive_count"] = b.add("yoy.coverage_positive_count", sum(x > 0 for x in coverage_changes), unit="count", source="dashboard.yoy_comparison", aggregation="positive coverage transitions", observation_unit="year-transition")
        f["coverage_negative_count"] = b.add("yoy.coverage_negative_count", sum(x < 0 for x in coverage_changes), unit="count", source="dashboard.yoy_comparison", aggregation="negative coverage transitions", observation_unit="year-transition")
    b.structures["yoy"] = f


def _prepare_drilldowns(b: _Builder, goal_progress: pd.DataFrame, department_progress: pd.DataFrame, active: pd.DataFrame, overall: float | None) -> None:
    # Goal focus selection is an internal ranking; only the resulting public facts are registered.
    if goal_progress is not None and not goal_progress.empty and "goal_code" in goal_progress.columns and active is not None and not active.empty and {"goal_code", "task_code"}.issubset(active.columns):
        gp = goal_progress.copy(); gp["_exec"] = _numeric(gp, "Виконання"); gp["_problem"] = _numeric(gp, "Проблемних", 0).fillna(0)
        valid = gp[gp["_exec"].notna()].copy()
        if not valid.empty:
            valid["_rank"] = (100 - valid["_exec"].clip(0, 100)) + valid["_problem"] * 2
            focus = valid.sort_values("_rank", ascending=False).iloc[0]; goal_code = str(focus.get("goal_code") or "").strip()
            subset = active[active["goal_code"].astype(str).eq(goal_code)].copy()
            if goal_code and not subset.empty:
                problem = subset.get("is_problem_status", pd.Series(False, index=subset.index)).fillna(False).astype(bool)
                missing = subset.get("missing_required_submission", pd.Series(False, index=subset.index)).fillna(False).astype(bool)
                task_name_map = subset.groupby(subset["task_code"].astype(str))["task_name"].first().to_dict() if "task_name" in subset.columns else {}
                rows=[]
                for task, group in subset.groupby(subset["task_code"].astype(str)):
                    ix=group.index; rows.append({"task":task,"name":str(task_name_map.get(task) or "").strip(),"problems":int(problem.loc[ix].sum()),"missing":int(missing.loc[ix].sum())})
                table=pd.DataFrame(rows)
                if not table.empty:
                    table["attention"] = table["problems"] + table["missing"]; ranked=table.sort_values(["attention","problems","missing"],ascending=False); total=int(table["attention"].sum())
                    if total>0:
                        top2=int(ranked.head(2)["attention"].sum()); f={"goal_label":f"СЦ {goal_code}","goal_execution":b.add("drilldown.goal.execution",focus.get("Виконання"),unit="percent",source="dashboard.goal_progress",aggregation="focused goal execution"),"task_count":b.add("drilldown.goal.task_count",len(table),unit="count",source="analytics.active",aggregation="tasks in focused goal",observation_unit="task"),"total_attention_records":b.add("drilldown.goal.total_attention",total,unit="count",source="analytics.active",aggregation="problem + missing rows",observation_unit="measure-period"),"top2_attention":b.add("drilldown.goal.top2_attention",top2,unit="count",source="analytics.active",aggregation="top2 attention rows",observation_unit="measure-period"),"top_tasks":[(f"{r['task']} — {r['name']}" if r['name'] else r['task'],int(r['problems']),int(r['missing'])) for _,r in ranked.head(3).iterrows()]}
                        f["top2_attention_share"] = b.ratio_pct("drilldown.goal.top2_attention_share_pct", top2, total, source="analytics.active", aggregation="top2 share of problem+missing rows", numerator_unit="measure-period", denominator_unit="measure-period")
                        b.structures["drilldown.goal"] = f
    if department_progress is not None and not department_progress.empty and active is not None and not active.empty and "department" in active.columns:
        dp=department_progress.copy(); dp["_exec"]=_numeric(dp,"Виконання"); dp["_contrib"]=_numeric(dp,"underperformance_contribution_pct",0).fillna(0); dp["_weight"]=_numeric(dp,"portfolio_weight_pct",0).fillna(0); dp["_problem"]=_numeric(dp,"Проблемних",0).fillna(0); valid=dp[dp["_exec"].notna()].copy()
        if not valid.empty:
            valid["_priority"]=valid["_contrib"]*1.5+valid["_weight"]*.35+valid["_problem"]*1.5+(100-valid["_exec"].clip(0,100))*.25
            focus=valid.sort_values("_priority",ascending=False).iloc[0]; department=_label(focus,"department")
            has_issue=bool(department) and (float(focus.get("Проблемних") or 0)>0 or float(focus.get("Без_даних") or 0)>0 or float(focus.get("underperformance_contribution_pct") or 0)>0 or (overall is not None and float(focus.get("Виконання")) < overall-2))
            subset=active[active["department"].astype(str).eq(department)].copy() if has_issue else pd.DataFrame()
            if not subset.empty:
                problem=subset.get("is_problem_status",pd.Series(False,index=subset.index)).fillna(False).astype(bool); missing=subset.get("missing_required_submission",pd.Series(False,index=subset.index)).fillna(False).astype(bool); rows=[]
                if "task_code" in subset.columns:
                    for task,group in subset.groupby(subset["task_code"].astype(str)):
                        ix=group.index;rows.append({"task":task,"problems":int(problem.loc[ix].sum()),"missing":int(missing.loc[ix].sum())})
                table=pd.DataFrame(rows); f={"department":department,
                    "execution":b.add("drilldown.ssp.execution",focus.get("Виконання"),unit="percent",source="dashboard.department_progress",aggregation="focused SSP execution"),
                    "portfolio_weight":b.add("drilldown.ssp.portfolio_weight_pct",focus.get("portfolio_weight_pct"),unit="percent",source="dashboard.department_progress",aggregation="focused SSP portfolio weight"),
                    "underperformance_contribution":b.add("drilldown.ssp.underperformance_contribution_pct",focus.get("underperformance_contribution_pct"),unit="percent",source="dashboard.department_progress",aggregation="focused SSP underperformance contribution"),
                    "risk_contribution":b.add("drilldown.ssp.risk_contribution_pct",focus.get("risk_contribution_pct"),unit="percent",source="dashboard.department_progress",aggregation="focused SSP risk contribution"),
                    "problem_count":b.add("drilldown.ssp.problem_count",_safe_int(focus.get("Проблемних")),unit="count",source="dashboard.department_progress",aggregation="focused SSP problem rows",observation_unit="measure-period"),
                    "missing_count":b.add("drilldown.ssp.missing_count",_safe_int(focus.get("Без_даних")),unit="count",source="dashboard.department_progress",aggregation="focused SSP missing rows",observation_unit="measure-period")}
                if not table.empty:
                    table["attention"]=table["problems"]+table["missing"]; ranked=table.sort_values("attention",ascending=False).head(3); total=int(table["attention"].sum()); top=int(ranked["attention"].sum()); f["top_tasks"]=[(r["task"],int(r["problems"]),int(r["missing"])) for _,r in ranked.iterrows() if int(r["attention"])>0]
                    if total>0:f["top_tasks_attention_share"]=b.ratio_pct("drilldown.ssp.top_tasks_attention_share_pct",top,total,source="analytics.active",aggregation="top task share of problem+missing rows",numerator_unit="measure-period",denominator_unit="measure-period")
                b.structures["drilldown.ssp"] = f


def _prepare_ssp_portfolio_and_risk(b: _Builder, department_progress: pd.DataFrame, metrics: Mapping[str, Any]) -> None:
    dp=department_progress.copy() if department_progress is not None else pd.DataFrame()
    if not dp.empty:
        dp["_weight"]=_numeric(dp,"portfolio_weight_pct"); dp["_under"]=_numeric(dp,"underperformance_contribution_pct"); dp["_exec"]=_numeric(dp,"Виконання")
        valid=dp.dropna(subset=["_weight"])
        if not valid.empty:
            largest=valid.loc[valid["_weight"].idxmax()]; f={"largest_department":_label(largest,"department"),
                "largest_weight":b.add("ssp.largest_weight_pct",largest.get("portfolio_weight_pct"),unit="percent",source="dashboard.department_progress",aggregation="largest SSP portfolio weight"),
                "largest_execution":b.add("ssp.largest_execution_pct",largest.get("Виконання"),unit="percent",source="dashboard.department_progress",aggregation="largest SSP execution"),
                "largest_underperformance_contribution":b.add("ssp.largest_underperformance_contribution_pct",largest.get("underperformance_contribution_pct"),unit="percent",source="dashboard.department_progress",aggregation="largest SSP underperformance contribution")}
            under=dp.dropna(subset=["_under"])
            if not under.empty:
                top=under.loc[under["_under"].idxmax()]; tu=_safe_number(top.get("underperformance_contribution_pct")); tw=_safe_number(top.get("portfolio_weight_pct")); f.update({
                    "top_underperformance_department":_label(top,"department"),
                    "top_underperformance_contribution":b.add("ssp.top_underperformance_contribution_pct",tu,unit="percent",source="dashboard.department_progress",aggregation="top SSP underperformance contribution"),
                    "top_underperformance_weight":b.add("ssp.top_underperformance_weight_pct",tw,unit="percent",source="dashboard.department_progress",aggregation="top underperformance SSP portfolio weight"),
                    "top_underperformance_execution":b.add("ssp.top_underperformance_execution_pct",top.get("Виконання"),unit="percent",source="dashboard.department_progress",aggregation="top underperformance SSP execution")})
                if tu is not None and tw is not None:f["top_underperformance_excess_pp"]=b.pp("ssp.top_underperformance_excess_pp",tu,tw,source="dashboard.department_progress",aggregation="underperformance contribution minus portfolio weight")
            b.structures["ssp.portfolio"] = f
        if "risk_contribution_pct" in dp.columns:
            values=pd.to_numeric(dp["risk_contribution_pct"],errors="coerce")
            if values.notna().any():
                row=dp.loc[values.idxmax()]; risk={"top_risk_department":_label(row,"department"),
                    "top_risk_contribution":b.add("risk.top_contribution_pct",row.get("risk_contribution_pct"),unit="percent",source="dashboard.department_progress",aggregation="top SSP risk contribution"),
                    "top_risk_portfolio_weight":b.add("risk.top_portfolio_weight_pct",row.get("portfolio_weight_pct"),unit="percent",source="dashboard.department_progress",aggregation="top risk SSP portfolio weight")}
                if risk["top_risk_contribution"] is not None and risk["top_risk_portfolio_weight"] is not None:risk["top_risk_excess_pp"]=b.pp("risk.top_excess_pp",risk["top_risk_contribution"],risk["top_risk_portfolio_weight"],source="dashboard.department_progress",aggregation="risk contribution minus portfolio weight")
                b.structures["risk.department"] = risk
    summary=metrics.get("latest_risk_summary") or {}
    if isinstance(summary,dict) and summary:
        # Risk summary values are already canonical Dashboard outputs. Register
        # every user-facing scalar as an explicit factual metric instead of
        # copying anonymous numbers into findings. This keeps risk percentages
        # provenance-traceable for narrow scopes as well as full-plan notes.
        assessed_raw = _safe_int(summary.get("risk_assessed_count"))
        high_raw = _safe_number(summary.get("share_high_critical_risk"))
        without_raw = _safe_number(summary.get("share_without_substantial_risk"))
        achieved_raw = _safe_number(summary.get("share_results_achieved"))
        rf={
            "assessed_count": b.add(
                "risk.summary.assessed_count", assessed_raw, unit="count",
                source="dashboard.latest_risk_summary.risk_assessed_count",
                aggregation="latest risk assessed rows", observation_unit="measure-period",
            ),
            "high_critical_share": b.add(
                "risk.summary.high_critical_share_pct", high_raw, unit="percent",
                source="dashboard.latest_risk_summary.share_high_critical_risk",
                aggregation="latest high/critical risk share",
            ),
            "without_substantial_risk_share": b.add(
                "risk.summary.without_substantial_risk_share_pct", without_raw, unit="percent",
                source="dashboard.latest_risk_summary.share_without_substantial_risk",
                aggregation="latest share without substantial risk",
            ),
            "results_achieved_share": b.add(
                "risk.summary.results_achieved_share_pct", achieved_raw, unit="percent",
                source="dashboard.latest_risk_summary.share_results_achieved",
                aggregation="latest results-achieved share",
            ),
        }
        rf.update(b.structures.get("risk.department",{})); b.structures["risk"] = rf


def _prepare_persistence(b:_Builder, active:pd.DataFrame)->None:
    if active is None or active.empty or not {"report_year","report_quarter"}.issubset(active.columns):return
    d=active.copy();d["_period"]=d["report_year"].astype(str)+" "+d["report_quarter"].astype(str)
    if d["_period"].nunique()<3:return
    problem=d.get("is_problem_status",pd.Series(False,index=d.index)).fillna(False).astype(bool);missing=d.get("missing_required_submission",pd.Series(False,index=d.index)).fillna(False).astype(bool);items=[]
    for col,kind in (("goal_code","goal"),("department","department")):
        if col not in d.columns:continue
        rows=[]
        for label,group in d.groupby(d[col].fillna("").astype(str)):
            if not str(label).strip():continue
            pp=mp=0
            for _,pg in group.groupby("_period"):
                ix=pg.index;pp += int(problem.loc[ix].sum()>0);mp += int(missing.loc[ix].sum()>0)
            rows.append((label,pp,mp,int(group["_period"].nunique())))
        if rows:
            tp=max(rows,key=lambda x:x[1]);tm=max(rows,key=lambda x:x[2])
            p_periods=b.add(f"persistent.{kind}.problem_periods",tp[1],unit="count",source="analytics.active",aggregation="periods with problem",observation_unit="period")
            p_observed=b.add(f"persistent.{kind}.problem_observed",tp[3],unit="count",source="analytics.active",aggregation="periods observed",observation_unit="period")
            m_periods=b.add(f"persistent.{kind}.missing_periods",tm[2],unit="count",source="analytics.active",aggregation="periods with missing",observation_unit="period")
            m_observed=b.add(f"persistent.{kind}.missing_observed",tm[3],unit="count",source="analytics.active",aggregation="periods observed",observation_unit="period")
            items.append({"kind":kind,"problem":(tp[0],p_periods,tm[2],p_observed),"missing":(tm[0],tp[1],m_periods,m_observed)})
    if items:b.structures["persistence"] = items

def _register_frame_sources(b: _Builder, name: str, frame: pd.DataFrame) -> None:
    """Register numeric values that already exist in prepared shared outputs.

    These are not recalculated. The registration gives validator/debug a stable
    source path for values copied into findings or narrative blocks.
    """
    if frame is None or frame.empty:
        return
    for row_pos, (_, row) in enumerate(frame.iterrows()):
        for column in frame.columns:
            value = _safe_number(row.get(column))
            if value is None:
                continue
            column_text = str(column).lower()
            if "зміна" in column_text or "delta" in column_text or "gap" in column_text or "excess" in column_text:
                unit = "pp"
            elif any(token in column_text for token in ("%", "виконання", "покриття", "share", "weight", "contribution", "прогрес", "інтеграл", "оцінка")):
                unit = "percent"
            elif any(token in column_text for token in ("кількість", "проблем", "без_даних", "без даних", "унікальних_заходів", "portfolio_measure_count", "rows", "count")):
                unit = "count"
            else:
                unit = "number"
            b.add(
                f"source.{name}.row{row_pos}.{column}", value, unit=unit,
                source=f"shared.{name}.{column}", aggregation="prepared source value",
                allow_over_100=(unit == "percent" and value > 100),
            )

def build_analytical_facts(*, filters:Mapping[str,Any], metrics:Mapping[str,Any], goal_progress:pd.DataFrame, task_progress:pd.DataFrame, department_progress:pd.DataFrame, product_progress:pd.DataFrame, status_counts:pd.DataFrame, period_dynamics:pd.DataFrame, yoy_comparison:pd.DataFrame, active:pd.DataFrame, mio_goal_evaluation:pd.DataFrame, mio_goal_task_evaluation:pd.DataFrame, mio_measure_evaluation:pd.DataFrame, mio_financing:pd.DataFrame) -> PreparedAnalyticalFacts:
    b=_Builder(filters)
    # Scope identifiers are registered separately from analytical values so debug
    # can still trace period numbers without treating them as calculated KPIs.
    for _year in sorted({int(y) for y in (filters.get("years", []) or []) if str(y).isdigit()}):
        b.add(f"scope.year.{_year}", _year, unit="number", source="analytics.filters.years", aggregation="selected year")
    # Register every numeric value that already exists in the prepared inputs.
    for _name, _frame in (
        ("goal_progress", goal_progress), ("task_progress", task_progress),
        ("department_progress", department_progress), ("product_progress", product_progress),
        ("status_counts", status_counts), ("period_dynamics", period_dynamics),
        ("yoy_comparison", yoy_comparison), ("active", active),
        ("mio_goal_evaluation", mio_goal_evaluation), ("mio_goal_task_evaluation", mio_goal_task_evaluation),
        ("mio_measure_evaluation", mio_measure_evaluation), ("mio_financing", mio_financing),
    ):
        _register_frame_sources(b, _name, _frame)
    b.add("scope.department_count", len(department_progress) if department_progress is not None else 0, unit="count", source="analytics.department_progress", aggregation="selected departments", observation_unit="department")
    b.add("scope.product_count", len(product_progress) if product_progress is not None else 0, unit="count", source="analytics.product_progress", aggregation="selected product types", observation_unit="product")
    # Register page/shared metrics without recalculation.
    units={"completion":"percent","coverage":"percent","completion_latest":"percent","coverage_latest":"percent","goal_completion":"percent","goal_completion_latest":"percent"}
    for key,value in metrics.items():
        if _safe_number(value) is None:continue
        unit=units.get(key,"count" if any(t in key.lower() for t in ("count","rows","measures","goals","tasks","problem","no_data","completed")) else "number")
        allow=unit=="percent" and float(value)>100
        b.add(f"page.{key}",value,unit=unit,source=f"analytics.page.metrics.{key}",aggregation="shared page metric",allow_over_100=allow)
    overall=_safe_number(metrics.get("completion"))
    latest=_safe_number(metrics.get("completion_latest"))
    if overall is not None and latest is not None:b.pp("overall.latest_minus_average_pp",latest,overall,source="analytics.page.metrics",aggregation="latest minus selection average")
    cov=_safe_number(metrics.get("coverage"));covl=_safe_number(metrics.get("coverage_latest"))
    if cov is not None and covl is not None:b.pp("overall.coverage_latest_minus_average_pp",covl,cov,source="analytics.page.metrics",aggregation="latest coverage minus average")
    g=_safe_number(metrics.get("goal_completion"));gl=_safe_number(metrics.get("goal_completion_latest"))
    if overall is not None and g is not None:b.pp("overall.measure_goal_gap_pp",overall,g,source="dashboard.shared",aggregation="measure execution minus goal execution")
    if latest is not None and gl is not None:b.pp("overall.latest_measure_goal_gap_pp",latest,gl,source="dashboard.shared",aggregation="latest measure execution minus latest goal execution")
    total_rows=_safe_int(metrics.get("total_rows"))
    if total_rows>0:
        b.ratio_pct("overall.missing_share_pct",_safe_int(metrics.get("no_data")),total_rows,source="analytics.page.metrics",aggregation="missing rows share",numerator_unit="measure-period",denominator_unit="measure-period")
        b.ratio_pct("overall.problem_share_pct",_safe_int(metrics.get("problem")),total_rows,source="analytics.page.metrics",aggregation="problem rows share",numerator_unit="measure-period",denominator_unit="measure-period")
    _prepare_trajectory(b,period_dynamics)
    for frame,kind in ((goal_progress,"goal"),(task_progress,"task"),(department_progress,"department")):
        _prepare_distribution(b,frame,kind,overall)
        _prepare_concentration(b,frame,kind,"Проблемних","problems",active)
        _prepare_concentration(b,frame,kind,"Без_даних","missing",active)
    _prepare_status(b,status_counts,active);_prepare_product(b,product_progress)
    _prepare_yoy(b, yoy_comparison)
    _prepare_drilldowns(b, goal_progress, department_progress, active, overall)
    _prepare_ssp_portfolio_and_risk(b, department_progress, metrics)
    _prepare_persistence(b, active)
    years=sorted({int(y) for y in (filters.get("years",[]) or []) if str(y).isdigit()}); year=max(years) if years else 2026
    _prepare_mio(b,mio_goal_evaluation,mio_goal_task_evaluation,mio_measure_evaluation,mio_financing,year,task_progress)
    return PreparedAnalyticalFacts(metrics=dict(b.metrics),structures=dict(b.structures))
