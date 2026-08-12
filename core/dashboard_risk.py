"""Trajectory, forecast, risk and management conclusion for Dashboard v2."""
from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

from core.dashboard_execution import NO_VALUES, YES_VALUES, to_number
from core.dashboard_periods import clean, parse_measure_period, period_number, quarter_to_roman, valid_observation_history

RISK_LABELS = ["Низький ризик", "Середній ризик", "Високий ризик", "Критичний ризик"]
RISKY_LEVELS = {"Високий ризик", "Критичний ризик"}
PROBLEM_SHARE_CONTROLLED_MAX = 15.0
PROBLEM_SHARE_ATTENTION_MAX = 35.0


def risk_level(forecast_attainment_pct: Any) -> str | None:
    value = to_number(forecast_attainment_pct)
    if value is None:
        return None
    if value > 85:
        return "Низький ризик"
    if value >= 51:
        return "Середній ризик"
    if value >= 20:
        return "Високий ризик"
    return "Критичний ризик"


def fact_history(requests_df: pd.DataFrame, code: Any, year: int, *, locked_periods=None, approved_only: bool = True) -> pd.DataFrame:
    """Valid analytical observation history; locked periods are excluded."""
    return valid_observation_history(
        requests_df, code, year, approved_only=approved_only, locked_periods=locked_periods
    )


def numeric_trajectory(
    current_fact: Any,
    annual_target: Any,
    quarter: Any,
    *,
    previous_fact: Any = None,
) -> dict[str, Any]:
    fact, target = to_number(current_fact), to_number(annual_target)
    q = {"I": 1, "II": 2, "III": 3, "IV": 4}.get(quarter_to_roman(quarter))
    result = {
        "current_execution_pct": None, "current_increment": None,
        "remaining_quarters": None, "forecast_year": None,
        "forecast_attainment_pct": None, "final_attainment_pct": None,
        "required_increment": None, "pace_sufficiency_pct": None,
        "forecast_kind": None, "forecast_explanation": "",
        "risk_level": None, "risk_explanation": "", "result_achieved": False,
        "negative_trajectory": False,
    }
    if fact is None or target in (None, 0) or q is None:
        result["forecast_kind"] = "not_assessable"
        result["forecast_explanation"] = "Недостатньо числових даних для прогнозу."
        return result

    current_execution = min(fact / target * 100.0, 100.0)
    result["current_execution_pct"] = current_execution
    result["result_achieved"] = fact >= target

    # Q4 is an actual annual outcome. Forecast risk no longer exists.
    if q == 4:
        result.update({
            "remaining_quarters": 0,
            "final_attainment_pct": fact / target * 100.0,
            "forecast_kind": "final",
            "forecast_explanation": "Підсумок року: використовується фактичний річний результат; прогноз не розраховується.",
            "risk_level": None,
            "risk_explanation": "IV квартал не оцінюється як прогнозний ризик.",
        })
        return result

    remaining = 4 - q
    result["remaining_quarters"] = remaining
    required = (target - fact) / remaining if remaining > 0 else None
    result["required_increment"] = required

    if q == 1:
        forecast = max(fact * 4.0, 0.0)
        attainment = max(forecast / target * 100.0, 0.0)
        result.update({
            "forecast_year": forecast,
            "forecast_attainment_pct": attainment,
            "forecast_kind": "preliminary",
            "forecast_explanation": "Прогноз сформовано лише за одним квартальним спостереженням.",
            "risk_level": risk_level(attainment),
            "risk_explanation": "Попередній сигнал ризику за першим квартальним спостереженням.",
        })
        return result

    prev = to_number(previous_fact)
    if prev is None:
        result["forecast_kind"] = "insufficient_history"
        result["forecast_explanation"] = "Немає валідного факту безпосередньо попереднього кварталу для оцінки темпу."
        return result

    increment = fact - prev
    forecast = max(fact + increment * remaining, 0.0)
    attainment = max(forecast / target * 100.0, 0.0)
    pace = None
    if required is not None:
        if required > 0:
            pace = increment / required * 100.0
        elif required <= 0 and fact >= target:
            pace = None
    result.update({
        "current_increment": increment,
        "negative_trajectory": increment < 0,
        "forecast_year": forecast,
        "forecast_attainment_pct": attainment,
        "pace_sufficiency_pct": pace,
        "forecast_kind": "trajectory",
        "risk_level": risk_level(attainment),
    })
    if increment < 0:
        result["risk_explanation"] = "Зафіксовано від’ємну квартальну динаміку; прогноз обмежено нулем знизу."
    elif attainment > 85:
        result["risk_explanation"] = "Поточна траєкторія вказує на досягнення більш як 85% річного плану."
    elif attainment >= 51:
        result["risk_explanation"] = "Поточна траєкторія вказує на часткове досягнення річного плану."
    else:
        result["risk_explanation"] = "Поточна траєкторія вказує на суттєвий ризик недосягнення річного плану."
    return result


def yes_no_trajectory(value: Any, *, selected_year: int, selected_quarter: Any, deadline: Any) -> dict[str, Any]:
    text = clean(value).casefold(); q = quarter_to_roman(selected_quarter)
    achieved = text in YES_VALUES
    result = {
        "result_achieved": achieved, "forecast_attainment_pct": None,
        "pace_sufficiency_pct": None, "risk_level": None,
        "risk_explanation": "", "deadline_warning": "",
        "forecast_kind": "yes_no", "final_attainment_pct": None,
        "final_outcome": None,
    }
    if q == "IV":
        result["forecast_kind"] = "final"
        result["final_outcome"] = "Результат досягнуто" if achieved else "Результат не досягнуто"
        result["risk_explanation"] = "IV квартал: фінальний фактичний результат; прогнозний ризик не розраховується."
        return result
    if achieved:
        result["risk_explanation"] = "Результат досягнуто."
        return result
    if text not in NO_VALUES:
        return result

    deadline_period = parse_measure_period(deadline, end=True)
    try:
        selected = period_number(selected_year, selected_quarter)
    except Exception:
        selected = None
    if deadline_period is None or selected is None:
        result["risk_explanation"] = "Результат ще не досягнуто; строк виконання не визначено."
        return result
    if deadline_period <= selected:
        # A deadline-reached non-result is a final failure, not predictive risk.
        result["forecast_kind"] = "final"
        result["final_outcome"] = "Результат не досягнуто"
        result["risk_explanation"] = "Строк виконання настав, а результат не досягнуто."
        return result
    next_period = selected + 1 if selected % 10 < 4 else (selected // 10 + 1) * 10 + 1
    if deadline_period == next_period:
        result["risk_level"] = "Високий ризик"
        result["deadline_warning"] = "Результат ще не досягнуто; строк виконання наближається."
        result["risk_explanation"] = result["deadline_warning"]
    else:
        result["risk_explanation"] = "Результат ще не досягнуто; строк виконання ще не настав."
    return result


def _empty_risk(row: pd.Series, reason: str = "") -> dict[str, Any]:
    return {
        "current_execution_pct": row.get("execution_score"), "current_increment": None,
        "remaining_quarters": None, "forecast_year": None,
        "forecast_attainment_pct": None, "final_attainment_pct": None,
        "required_increment": None, "pace_sufficiency_pct": None,
        "forecast_kind": None, "forecast_explanation": reason,
        "risk_level": None, "risk_explanation": reason,
        "result_achieved": bool(row.get("result_achieved", False)),
        "deadline_warning": "", "negative_trajectory": False,
        "final_outcome": None,
    }


def attach_risk(snapshot: pd.DataFrame, previous_snapshot: pd.DataFrame | None = None) -> pd.DataFrame:
    """Attach trajectory/risk using only a valid immediate previous-quarter snapshot."""
    if snapshot is None or snapshot.empty:
        return snapshot.copy() if hasattr(snapshot, "copy") else pd.DataFrame()
    result = snapshot.copy()
    previous_by_code: dict[str, pd.Series] = {}
    previous_valid = (
        previous_snapshot is not None and not previous_snapshot.empty
        and bool(previous_snapshot.get("monitoring_conducted", pd.Series([True])).iloc[0])
    )
    if previous_valid:
        for _, row in previous_snapshot.iterrows():
            previous_by_code[clean(row.get("code"))] = row

    rows = []
    for _, row in result.iterrows():
        out = row.to_dict(); q = quarter_to_roman(row.get("quarter"))
        state = clean(row.get("period_state"))
        monitoring_ok = bool(row.get("monitoring_conducted", True))

        if not monitoring_ok:
            risk = _empty_risk(row, "Моніторинг у цьому періоді не проводився.")
        elif state == "unknown_period":
            risk = _empty_risk(row, "Ризик не оцінюється до визначення періоду застосовності заходу.")
        elif state == "ended" or bool(row.get("final_missing_result", False)):
            risk = _empty_risk(row, "Захід завершено; прогнозний ризик не розраховується.")
            fact, target = to_number(row.get("actual")), to_number(row.get("annual_target"))
            risk["remaining_quarters"] = 0
            risk["forecast_kind"] = "final"
            risk["final_attainment_pct"] = fact / target * 100.0 if fact is not None and target not in (None, 0) else None
            achieved = bool(row.get("result_achieved", False))
            risk["final_outcome"] = "Результат досягнуто" if achieved else "Результат не досягнуто"
            risk["result_achieved"] = achieved
        elif bool(row.get("yes_no", False)):
            risk = yes_no_trajectory(row.get("actual"), selected_year=int(row.get("year")),
                                     selected_quarter=row.get("quarter"), deadline=row.get("measure_end_date"))
            risk["current_execution_pct"] = row.get("execution_score")
            for key in ["current_increment", "remaining_quarters", "forecast_year", "required_increment"]:
                risk.setdefault(key, None)
            risk.setdefault("negative_trajectory", False)
        elif bool(row.get("numeric", False)):
            prev = previous_by_code.get(clean(row.get("code")))
            prev_fact = None
            if prev is not None and clean(prev.get("period_state")) != "unknown_period":
                prev_fact = prev.get("actual")
            risk = numeric_trajectory(row.get("actual"), row.get("annual_target"), row.get("quarter"), previous_fact=prev_fact)
            risk["deadline_warning"] = ""; risk["final_outcome"] = (
                "Результат досягнуто" if risk.get("result_achieved") else "Результат не досягнуто"
            ) if q == "IV" else None
        else:
            # Qualitative measures: no numeric extrapolation. Q4 is final.
            risk = _empty_risk(row)
            achieved = bool(row.get("result_achieved", False)); status = clean(row.get("status"))
            if q == "IV":
                risk.update({"forecast_kind": "final", "final_outcome": "Результат досягнуто" if achieved else "Результат не досягнуто",
                             "risk_explanation": "Підсумок року за фактичним якісним результатом."})
            elif status == "Частково виконано":
                risk.update({"forecast_kind": "qualitative", "risk_level": "Середній ризик",
                             "risk_explanation": "Попередній ризиковий сигнал визначено за якісним станом."})
            elif status in {"Не виконано", "Не подано"}:
                risk.update({"forecast_kind": "qualitative", "risk_level": "Критичний ризик",
                             "risk_explanation": "Попередній ризиковий сигнал визначено за якісним станом."})
            else:
                risk["forecast_kind"] = "qualitative"

        # Q4 override is absolute: no predictive risk for any measure type.
        if q == "IV":
            risk["risk_level"] = None
            risk["forecast_attainment_pct"] = None
            if risk.get("forecast_kind") != "final":
                risk["forecast_kind"] = "final"
        out.update(risk)
        out["auto_risk"] = risk.get("risk_level") or "Не оцінюється"
        out["risk_reason"] = risk.get("risk_explanation") or risk.get("forecast_explanation") or ""
        out["risk_score"] = None if risk.get("risk_level") is None else max(0.0, 100.0 - float(risk.get("forecast_attainment_pct") or 0.0))
        out["included_in_risk_assessment"] = bool(risk.get("risk_level") in RISK_LABELS or (risk.get("result_achieved") and q != "IV"))
        rows.append(out)
    return pd.DataFrame(rows)


def risk_summary(snapshot_with_risk: pd.DataFrame) -> dict[str, Any]:
    if snapshot_with_risk is None or snapshot_with_risk.empty:
        return {"share_without_substantial_risk": None, "share_high_critical_risk": None,
                "share_results_achieved": None, "risk_assessed_count": 0}
    data = snapshot_with_risk.copy()
    q = quarter_to_roman(data["quarter"].iloc[0]) if "quarter" in data.columns else ""
    achieved = data.get("result_achieved", pd.Series(False, index=data.index)).fillna(False).astype(bool)
    assessed_execution = data[data.get("execution_score", pd.Series(index=data.index, dtype=float)).notna()]
    achieved_share = None if assessed_execution.empty else float(achieved.loc[assessed_execution.index].mean() * 100.0)
    if q == "IV":
        return {"share_without_substantial_risk": None, "share_high_critical_risk": None,
                "share_results_achieved": achieved_share, "risk_assessed_count": 0}
    levels = data.get("risk_level", pd.Series(None, index=data.index))
    denominator_mask = achieved | levels.isin(RISK_LABELS)
    if not denominator_mask.any():
        safe_share = high_share = None; count = 0
    else:
        safe = achieved[denominator_mask] | levels[denominator_mask].eq("Низький ризик")
        high = levels[denominator_mask].isin(RISKY_LEVELS)
        safe_share = float(safe.mean() * 100.0); high_share = float(high.mean() * 100.0); count = int(denominator_mask.sum())
    return {"share_without_substantial_risk": safe_share, "share_high_critical_risk": high_share,
            "share_results_achieved": achieved_share, "risk_assessed_count": count}


def attention_mask(snapshot_with_risk: pd.DataFrame) -> pd.Series:
    """v2 selection for the preserved 'Проблемні заходи' block."""
    if snapshot_with_risk is None or snapshot_with_risk.empty:
        return pd.Series(False, index=getattr(snapshot_with_risk, "index", []), dtype=bool)
    data = snapshot_with_risk
    risk_attention = data.get("risk_level", pd.Series(None, index=data.index)).isin(RISKY_LEVELS)
    missing = data.get("missing_required_submission", pd.Series(False, index=data.index)).fillna(False).astype(bool)
    final_missing = data.get("final_missing_result", pd.Series(False, index=data.index)).fillna(False).astype(bool)
    conflict = data.get("data_quality_conflict", pd.Series(False, index=data.index)).fillna(False).astype(bool)
    final_failure = (
        data.get("forecast_kind", pd.Series("", index=data.index)).eq("final")
        & ~data.get("result_achieved", pd.Series(False, index=data.index)).fillna(False).astype(bool)
    )
    return risk_attention | missing | final_missing | conflict | final_failure


def management_conclusion(
    snapshot_with_risk: pd.DataFrame,
    *,
    execution_by_measures: float | None,
    execution_by_goals: float | None,
    coverage: float | None,
) -> dict[str, Any]:
    """Quarter-aware management conclusion with centralized provisional thresholds."""
    if snapshot_with_risk is None or snapshot_with_risk.empty:
        return {"title": "Недостатньо даних", "explanation": "Немає релевантних заходів для управлінського висновку.", "severity": "neutral"}
    q = quarter_to_roman(snapshot_with_risk["quarter"].iloc[0])
    rsum = risk_summary(snapshot_with_risk)
    cov = coverage

    if q == "I":
        high = rsum.get("share_high_critical_risk")
        explanation = (
            f"Початкова оцінка: виконання за заходами — {_fmt(execution_by_measures)}, "
            f"за стратегічними цілями — {_fmt(execution_by_goals)}, покриття — {_fmt(cov)}. "
            + (f"Попередні сигнали високого/критичного ризику охоплюють {_fmt(high)} оцінюваних результатів." if high is not None else "Для частини заходів ризиковий сигнал ще не може бути оцінений.")
        )
        severity = "medium" if (cov is not None and cov < 70) else "neutral"
        return {"title": "Початковий стан реалізації", "explanation": explanation, "severity": severity}

    if q == "IV":
        assessed = snapshot_with_risk[snapshot_with_risk["execution_score"].notna()]
        nonachieved_share = None if assessed.empty else float((~assessed["result_achieved"].fillna(False).astype(bool)).mean() * 100.0)
        if nonachieved_share is None:
            title, severity = "Підсумок року", "neutral"
        elif nonachieved_share <= PROBLEM_SHARE_CONTROLLED_MAX:
            title, severity = "Підсумок року: більшість результатів досягнуто", "low"
        elif nonachieved_share <= PROBLEM_SHARE_ATTENTION_MAX:
            title, severity = "Підсумок року: частина результатів потребує уваги", "medium"
        else:
            title, severity = "Підсумок року: суттєва частка результатів не досягнута", "high"
        return {"title": title,
                "explanation": f"Фінальний висновок базується на фактичних річних результатах. Частка оцінених заходів без досягнутого результату — {_fmt(nonachieved_share)}; виконання за заходами — {_fmt(execution_by_measures)}, за цілями — {_fmt(execution_by_goals)}.",
                "severity": severity}

    high_share = rsum.get("share_high_critical_risk")
    safe_share = rsum.get("share_without_substantial_risk")
    problem_share = high_share
    if problem_share is None:
        title, severity = "Потрібна увага до якості прогнозних даних", "medium"
    elif problem_share <= PROBLEM_SHARE_CONTROLLED_MAX and (cov is None or cov >= 80):
        title, severity = "Реалізація переважно контрольована", "low"
    elif problem_share <= PROBLEM_SHARE_ATTENTION_MAX:
        title, severity = "Потрібна увага до окремих напрямів", "medium"
    else:
        title, severity = "Суттєвий ризик недосягнення результатів", "high"

    forecast_vals = pd.to_numeric(snapshot_with_risk.get("forecast_attainment_pct"), errors="coerce").dropna()
    pace_vals = pd.to_numeric(snapshot_with_risk.get("pace_sufficiency_pct"), errors="coerce").dropna()
    forecast_avg = float(forecast_vals.mean()) if not forecast_vals.empty else None
    pace_avg = float(pace_vals.mean()) if not pace_vals.empty else None
    explanation = (
        f"Покриття — {_fmt(cov)}; високий + критичний ризик — {_fmt(high_share)}; "
        f"частка заходів без суттєвого ризику — {_fmt(safe_share)}; "
        f"середнє прогнозоване досягнення річного плану — {_fmt(forecast_avg)}; "
        f"середня достатність темпу — {_fmt(pace_avg)}."
    )
    return {"title": title, "explanation": explanation, "severity": severity}


def _fmt(value: Any) -> str:
    number = to_number(value)
    return "н/д" if number is None else f"{number:.1f}%"
