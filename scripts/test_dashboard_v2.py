"""Pure calculation/control tests for Dashboard execution v2.

Run from repository root:
    python scripts/test_dashboard_v2.py
No Supabase writes are performed.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.dashboard_execution import (  # noqa: E402
    build_quarter_snapshot,
    goal_scores,
    hierarchy_for_period,
    plan_scores,
    score_measure,
    task_scores,
)
from core.dashboard_filters import (  # noqa: E402
    apply_stable_cohort,
    filter_measures,
    stable_cohort_codes,
)
from core.dashboard_risk import numeric_trajectory, risk_level, attach_risk, yes_no_trajectory, attention_mask  # noqa: E402


def approx(actual, expected, tol=0.02):
    assert actual is not None, f"expected {expected}, got None"
    assert math.isclose(float(actual), float(expected), abs_tol=tol), (actual, expected)


def measure(code, target=100, start="I квартал 2026", end="IV квартал 2026", task="1.1", goal="1"):
    return {
        "object_type": "measure", "code": code, "name": code,
        "target_2026": target, "measure_start_date": start, "measure_end_date": end,
        "parent_task_code": task, "parent_task_name": task,
        "parent_goal_code": goal, "parent_goal_name": goal,
        "resp_main": "ССП 5", "resp_co_1": "", "resp_co_2": "",
    }


def request(code, quarter, value, status="Частково виконано", year=2026, rid=1):
    numeric = value if isinstance(value, (int, float)) else None
    text = value if isinstance(value, str) else None
    return {
        "id": rid, "strat_code": code, "year": year, "quarter": quarter,
        "status": status, "approval_status": "Погоджено", "object_kind": "measure",
        "numeric_value": numeric, "value_text": text,
        "submitted_at": f"{year}-01-01T00:00:00Z", "updated_at": f"{year}-01-01T00:00:00Z",
    }


def test_numeric_control_cases():
    # 1.1.2
    q2 = numeric_trajectory(51, 85, "II", previous_fact=17)
    approx(q2["current_execution_pct"], 60)
    approx(q2["current_increment"], 34)
    approx(q2["forecast_year"], 119)
    approx(q2["forecast_attainment_pct"], 140)
    approx(q2["required_increment"], 17)
    approx(q2["pace_sufficiency_pct"], 200)
    q3 = numeric_trajectory(85, 85, "III", previous_fact=51)
    assert q3["result_achieved"] and q3["current_execution_pct"] == 100
    assert score_measure("Частково виконано", 119, 85)["execution_score"] == 100
    approx(score_measure("Частково виконано", 119, 85)["raw_attainment_pct"], 140)

    # 1.1.10
    q2 = numeric_trajectory(6.75, 15, "II", previous_fact=1.5)
    approx(q2["current_execution_pct"], 45)
    approx(q2["forecast_year"], 17.25)
    approx(q2["forecast_attainment_pct"], 115)
    approx(q2["pace_sufficiency_pct"], 127.27)
    q3 = numeric_trajectory(9, 15, "III", previous_fact=6.75)
    approx(q3["current_execution_pct"], 60)
    approx(q3["forecast_year"], 11.25)
    approx(q3["forecast_attainment_pct"], 75)
    approx(q3["pace_sufficiency_pct"], 37.5)

    # 1.1.3
    q2 = numeric_trajectory(900, 1800, "II", previous_fact=450)
    approx(q2["current_execution_pct"], 50)
    approx(q2["forecast_attainment_pct"], 100)
    approx(q2["pace_sufficiency_pct"], 100)
    q3 = numeric_trajectory(1260, 1800, "III", previous_fact=900)
    approx(q3["current_execution_pct"], 70)
    approx(q3["forecast_attainment_pct"], 90)
    approx(q3["pace_sufficiency_pct"], 66.67)
    q4 = numeric_trajectory(1530, 1800, "IV", previous_fact=1260)
    assert q4["forecast_attainment_pct"] is None
    approx(q4["final_attainment_pct"], 85)

    # 1.1.4 – current execution does not directly determine risk
    q2 = numeric_trajectory(6700, 10000, "II", previous_fact=4000)
    approx(q2["current_execution_pct"], 67)
    approx(q2["forecast_attainment_pct"], 121)
    approx(q2["pace_sufficiency_pct"], 163.64)
    q3 = numeric_trajectory(7900, 10000, "III", previous_fact=6700)
    approx(q3["current_execution_pct"], 79)
    approx(q3["forecast_attainment_pct"], 91)
    approx(q3["pace_sufficiency_pct"], 57.14)
    assert q3["risk_level"] == "Низький ризик"

    # 1.1.15
    q2 = numeric_trajectory(51.59, 67, "II", previous_fact=50.25)
    approx(q2["current_execution_pct"], 77, 0.1)
    approx(q2["forecast_year"], 54.27, 0.02)
    approx(q2["forecast_attainment_pct"], 81, 0.1)
    approx(q2["pace_sufficiency_pct"], 17.39, 0.1)
    q3 = numeric_trajectory(51.59, 67, "III", previous_fact=51.59)
    approx(q3["current_increment"], 0)
    approx(q3["forecast_year"], 51.59)
    approx(q3["forecast_attainment_pct"], 77, 0.1)
    approx(q3["pace_sufficiency_pct"], 0)

    # 1.2.12
    q2 = numeric_trajectory(8, 10, "II", previous_fact=7.5)
    approx(q2["current_execution_pct"], 80)
    approx(q2["forecast_attainment_pct"], 90)
    approx(q2["pace_sufficiency_pct"], 50)
    q3 = numeric_trajectory(9.2, 10, "III", previous_fact=8)
    approx(q3["current_execution_pct"], 92)
    approx(q3["forecast_attainment_pct"], 104)
    approx(q3["pace_sufficiency_pct"], 150)
    assert numeric_trajectory(10, 10, "IV", previous_fact=9.2)["current_execution_pct"] == 100


def test_snapshot_period_semantics():
    # Active without current submission: Q4 must be 0, not carry Q3 fact.
    strat = pd.DataFrame([measure("1.1.9.", 118)])
    req = pd.DataFrame([request("1.1.9.", 3, 110.92, rid=1)])
    snap = build_quarter_snapshot(strat, req, 2026, "IV", locked_periods=set())
    row = snap.iloc[0]
    assert row["period_state"] == "active"
    assert row["status"] == "Не подано" and not row["submitted"] and row["execution_score"] == 0

    # Synthetic inherited yes/no rows must not count as a current submission.
    synthetic = request("1.1.9.", 4, "так", status="Виконано", rid=2)
    synthetic["_auto_inherited"] = True
    snap = build_quarter_snapshot(strat, pd.DataFrame([*req.to_dict("records"), synthetic]), 2026, "IV", locked_periods=set())
    assert snap.iloc[0]["status"] == "Не подано"

    # Ended measure: carry latest approved Q3 result into Q4.
    strat = pd.DataFrame([measure("4.2.3.", "так", end="III квартал 2026")])
    req = pd.DataFrame([request("4.2.3.", 3, "так", status="Виконано")])
    snap = build_quarter_snapshot(strat, req, 2026, "IV", locked_periods=set())
    row = snap.iloc[0]
    assert row["period_state"] == "ended" and row["carry_forward"] and row["execution_score"] == 100

    # Future measure is outside population.
    strat = pd.DataFrame([measure("future", 100, start="I квартал 2027", end="IV квартал 2027")])
    assert build_quarter_snapshot(strat, pd.DataFrame(), 2026, "IV", locked_periods=set()).empty

    # Locked/no-monitoring period -> None, never zero.
    strat = pd.DataFrame([measure("locked", 100)])
    snap = build_quarter_snapshot(strat, pd.DataFrame(), 2026, "II", locked_periods={("2026", 2)})
    assert pd.isna(snap.iloc[0]["execution_score"])
    assert not snap.iloc[0]["monitoring_conducted"]

    # Не настав час is excluded from execution and risk denominators.
    strat = pd.DataFrame([measure("1.2.10.", 10)])
    req = pd.DataFrame([request("1.2.10.", 2, "x", status="Не настав час")])
    snap = build_quarter_snapshot(strat, req, 2026, "II", locked_periods=set())
    assert pd.isna(snap.iloc[0]["execution_score"])
    assert not snap.iloc[0]["risk_eligible"]


def test_numeric_priority_and_conflict():
    scored = score_measure("Частково виконано", 85, 85)
    assert scored["execution_score"] == 100 and scored["data_quality_conflict"]
    scored = score_measure("Виконано", 50, 100)
    assert scored["execution_score"] == 50 and scored["data_quality_conflict"]


def test_hierarchy():
    rows = []
    # Task A four measures mean 81.5
    for i, score in enumerate([100, 100, 75, 51], 1):
        rows.append({**measure(f"A{i}", 100, task="A", goal="G"), "_score": score})
    # Task B two measures mean 46
    for i, score in enumerate([92, 0], 1):
        rows.append({**measure(f"B{i}", 100, task="B", goal="G"), "_score": score})
    snapshot = pd.DataFrame(rows)
    snapshot["execution_score"] = snapshot["_score"]
    snapshot["submitted"] = True
    snapshot["coverage_eligible"] = True
    snapshot["monitoring_conducted"] = True
    tasks = task_scores(snapshot)
    a = tasks.loc[tasks.task_code.eq("A"), "execution"].iloc[0]
    b = tasks.loc[tasks.task_code.eq("B"), "execution"].iloc[0]
    approx(a, 81.5); approx(b, 46)
    goals = goal_scores(snapshot, tasks)
    approx(goals.iloc[0]["by_tasks"], 63.75)
    by_measures = goals.iloc[0]["by_measures"]
    assert not math.isclose(by_measures, 63.75)
    plan = plan_scores(snapshot)
    approx(plan["execution_by_goals"], 63.75)


def test_filters_and_cross_page_consistency():
    strat = pd.DataFrame([
        {**measure("m1", 100, task="T1", goal="G"), "resp_main": "ССП 5", "resp_co_1": "ССП 8"},
        {**measure("m2", 100, task="T2", goal="G"), "resp_main": "ССП 8", "resp_co_1": "ССП 5"},
    ])
    filtered = filter_measures(strat, ssp=["5"])
    assert len(filtered) == 2 and filtered["code"].nunique() == 2
    from core.dashboard_filters import expand_ssp_rows
    graph_rows = expand_ssp_rows(filtered, ["5"])
    assert set(graph_rows["ssp"]) == {"5"} and len(graph_rows) == 2
    req = pd.DataFrame([
        request("m1", 2, 100, status="Виконано", rid=1),
        request("m2", 2, 50, status="Частково виконано", rid=2),
    ])
    shared = hierarchy_for_period(filtered, req, 2026, "II", locked_periods=set())
    # This same dict/dataframe is what both pages consume; no page formula exists.
    tasks = shared["task_scores"].set_index("task_code")["execution"].to_dict()
    assert tasks == {"T1": 100.0, "T2": 50.0}
    approx(shared["goal_scores"].iloc[0]["by_tasks"], 75)

    latest = shared["snapshot"].copy()
    latest.loc[latest.code.eq("m1"), "status"] = "Виконано"
    latest.loc[latest.code.eq("m2"), "status"] = "Не виконано"
    cohort = stable_cohort_codes(latest, ["Не виконано"])
    assert cohort == {"m2"}
    assert apply_stable_cohort(shared["snapshot"], cohort)["code"].tolist() == ["m2"]


def test_q1_and_yes_no():
    q1 = numeric_trajectory(20, 100, "I")
    assert q1["forecast_kind"] == "preliminary"
    approx(q1["forecast_year"], 80)
    approx(q1["forecast_attainment_pct"], 80)
    assert q1["risk_level"] is None
    assert q1["preliminary_attention"] is True
    assert "одним квартальним" in q1["forecast_explanation"]

    # Q1 qualitative status is an attention signal, never a standard risk category.
    qualitative = pd.DataFrame([{
        "code": "qual", "year": 2026, "quarter": "I", "period_state": "active",
        "monitoring_conducted": True, "yes_no": False, "numeric": False,
        "status": "Не виконано", "execution_score": 0.0, "result_achieved": False,
    }])
    qualitative_risk = attach_risk(qualitative).iloc[0]
    assert pd.isna(qualitative_risk["risk_level"]) or qualitative_risk["risk_level"] is None
    assert qualitative_risk["forecast_kind"] == "preliminary"
    assert bool(qualitative_risk["preliminary_attention"])

    # Q1 yes/no near its deadline may warn, but never becomes High/Critical risk.
    approaching_q1 = yes_no_trajectory(
        "ні", selected_year=2026, selected_quarter="I", deadline="II квартал 2026"
    )
    assert approaching_q1["risk_level"] is None
    assert approaching_q1["forecast_kind"] == "preliminary"
    assert approaching_q1["preliminary_attention"]
    assert "наближається" in approaching_q1["deadline_warning"]

    early = yes_no_trajectory("ні", selected_year=2026, selected_quarter="II", deadline="IV квартал 2026")
    assert early["risk_level"] is None
    approaching = yes_no_trajectory("ні", selected_year=2026, selected_quarter="III", deadline="IV квартал 2026")
    assert approaching["risk_level"] == "Високий ризик"
    assert "наближається" in approaching["deadline_warning"]
    final = yes_no_trajectory("ні", selected_year=2026, selected_quarter="IV", deadline="IV квартал 2026")
    assert final["risk_level"] is None
    assert final["forecast_kind"] == "final" and final["final_outcome"] == "Результат не досягнуто"
    achieved = yes_no_trajectory("так", selected_year=2026, selected_quarter="I", deadline="IV квартал 2026")
    assert achieved["result_achieved"] and achieved["risk_level"] is None


def test_attach_risk_uses_previous_quarter():
    from core.dashboard_risk import attach_risk
    strat = pd.DataFrame([measure("trajectory", 100)])
    req = pd.DataFrame([
        request("trajectory", 1, 20, rid=1),
        request("trajectory", 2, 50, rid=2),
    ])
    q1 = build_quarter_snapshot(strat, req, 2026, "I", locked_periods=set())
    q2 = build_quarter_snapshot(strat, req, 2026, "II", locked_periods=set())
    risked = attach_risk(q2, q1)
    row = risked.iloc[0]
    approx(row["current_increment"], 30)
    approx(row["forecast_year"], 110)
    approx(row["forecast_attainment_pct"], 110)


def test_multi_period_aggregation_and_locked_gap():
    from core.dashboard_breakdowns import aggregate_plan, build_period_results, dynamics_frame, ssp_period_frame
    strat = pd.DataFrame([{**measure("multi", 100), "resp_main":"ССП 5"}])
    req = pd.DataFrame([request("multi", 1, 25, rid=1), request("multi", 2, 50, rid=2)])
    results = build_period_results(strat, req, [(2026,"I"),(2026,"II")], locked_periods=set())
    agg = aggregate_plan(results)
    approx(agg["execution_by_measures_average"], 37.5)
    approx(agg["execution_by_measures_latest"], 50)
    approx(agg["execution_by_measures_change"], 25)
    # If Q1 had no monitoring, it is ignored rather than contributing 0.
    locked = build_period_results(strat, req, [(2026,"I"),(2026,"II")], locked_periods={("2026",1)})
    locked_agg = aggregate_plan(locked)
    approx(locked_agg["execution_by_measures_average"], 50)
    dyn = dynamics_frame(locked)
    q1_exec = dyn[(dyn["period"].eq("I кв. 2026")) & (dyn["series"].eq("Виконання за заходами"))]["value"].iloc[0]
    assert q1_exec is None or pd.isna(q1_exec)
    # A real assessed 0 remains numeric 0 for heatmap/SSP views.
    req_zero = pd.DataFrame([request("multi", 2, 0, status="Не виконано", rid=3)])
    zero_results = build_period_results(strat, req_zero, [(2026,"II")], locked_periods=set())
    ssp = ssp_period_frame(zero_results,["5"] )
    assert float(ssp.iloc[0]["execution"]) == 0.0


def test_current_reporting_period():
    from core.dashboard_periods import (
        current_reporting_period, latest_reporting_period_in_year,
        monitoring_conducted, reporting_period_range,
    )

    # A/F: Aug 12 calendar ceiling is Q3; a future Q4 row cannot move the default.
    q1_q4 = pd.DataFrame([
        request("p", 1, 10, rid=1), request("p", 2, 20, rid=2),
        request("p", 3, 30, rid=3), request("p", 4, 40, rid=4),
    ])
    assert current_reporting_period(
        q1_q4, locked_periods=set(), as_of="2026-08-12"
    ) == (2026, "III")
    assert latest_reporting_period_in_year(
        q1_q4, 2026, locked_periods=set(), as_of="2026-08-12"
    ) == (2026, "III")

    # B: when data only exists through Q2, Q2 remains current even during Q3.
    q1_q2 = q1_q4[q1_q4["quarter"].isin([1, 2])].copy()
    assert current_reporting_period(
        q1_q2, locked_periods=set(), as_of="2026-08-12"
    ) == (2026, "II")

    # C: opening Q4 on the calendar does not invent Q4 if reporting exists only through Q3.
    q1_q3 = q1_q4[q1_q4["quarter"].isin([1, 2, 3])].copy()
    assert current_reporting_period(
        q1_q3, locked_periods=set(), as_of="2026-10-01"
    ) == (2026, "III")

    # D/E: period_locks is the only blocker; Q1/Q2 2026 are valid when unlocked.
    assert current_reporting_period(
        q1_q2, locked_periods={("2026", 2)}, as_of="2026-08-12"
    ) == (2026, "I")
    assert monitoring_conducted(2026, "I", locked_periods=set()) is True
    assert monitoring_conducted(2026, "II", locked_periods=set()) is True

    # Synthetic inherited records and invalid period labels are never candidates.
    inherited = request("p", 3, "так", status="Виконано", rid=10)
    inherited["_auto_inherited"] = True
    invalid = request("p", 1, 10, rid=11); invalid["quarter"] = "невідомий"
    mixed = pd.DataFrame([*q1_q2.to_dict("records"), inherited, invalid])
    assert current_reporting_period(
        mixed, locked_periods=set(), as_of="2026-08-12"
    ) == (2026, "II")

    # No requests: fallback is the latest non-future unlocked calendar period.
    assert current_reporting_period(
        pd.DataFrame(), locked_periods=set(), as_of="2026-08-12"
    ) == (2026, "III")

    # G/H/I: explicit cross-year range is chronological and never Cartesian.
    exact = reporting_period_range(2026, "IV", 2027, "II")
    assert exact == [(2026, "IV"), (2027, "I"), (2027, "II")]
    assert len(exact) == 3
    try:
        reporting_period_range(2027, "II", 2026, "IV")
    except ValueError as exc:
        assert str(exc) == "Початок періоду не може бути пізніше за кінець періоду."
    else:
        raise AssertionError("invalid reporting range must be rejected")


def test_page_integration_contracts():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    dashboard = (ROOT / "pages" / "2_Dashboard.py").read_text(encoding="utf-8")
    all_changed = "\n".join(p.read_text(encoding="utf-8") for p in [
        ROOT / "app.py", ROOT / "pages" / "2_Dashboard.py",
        ROOT / "core" / "dashboard_metrics.py", ROOT / "core" / "dashboard_execution.py",
        ROOT / "core" / "dashboard_periods.py", ROOT / "core" / "dashboard_risk.py",
        ROOT / "core" / "dashboard_breakdowns.py", ROOT / "core" / "dashboard_filters.py",
        ROOT / "core" / "dashboard_finance.py",
    ])
    assert "def calculate_completion" not in app
    assert "def calculate_completion" not in dashboard
    assert "hierarchy_for_period" in app and "build_period_results" in dashboard
    assert "dashboard_periods_v2.current_reporting_period(monitoring_df)" in app
    assert "dashboard_periods_v2.selected_reporting_period(selected_years, selected_quarters)" in app
    assert "Оцінка через виконання завдань стратегічної цілі." in app
    assert "Розрахунок виконання — станом на" in app
    assert "Застосувати фільтри" in app and "Застосувати фільтри" in dashboard
    assert "Стан виконання" in dashboard and "Порівняння результатів" in dashboard and "Динаміка виконання" in dashboard and "Фінансування" in dashboard
    # Comparison/dynamics use explicit start/end pairs, never independent years×quarters.
    assert "dash_breakdown_start_period" in dashboard and "dash_breakdown_end_period" in dashboard
    assert "dash_dynamics_start_period" in dashboard and "dash_dynamics_end_period" in dashboard
    assert "_render_period_range_panel" in dashboard and "reporting_period_range" in dashboard
    for legacy in [
        "dash_breakdown_years", "dash_breakdown_quarters",
        "dash_dynamics_years", "dash_dynamics_quarters",
        "dash_finance_quarter", "applied_finance_quarter", "finance_quarter",
        "_render_multi_period_panel", "dashboard_breakdowns_v2.period_pairs",
    ]:
        assert legacy not in dashboard, legacy
    assert "st.error(_period_range_error)" in dashboard
    assert "except ValueError as exc" in dashboard
    # J/K defaults: I quarter of current reporting year through current reporting period.
    assert '_default_range_start_period = (_default_reporting_year, "I")' in dashboard
    assert '_default_range_end_period = (_default_reporting_year, _default_reporting_quarter)' in dashboard
    assert 'def _reset_dashboard_common_filters_v21' in dashboard
    assert 'st.session_state["dash_common_filters_applied_v21"] = _dash_common_defaults.copy()' in dashboard
    # Finance is annual-only and automatically resolves execution context.
    assert '"dash_finance_year"' in dashboard
    assert "latest_reporting_period_in_year" in dashboard
    assert "Фінансові показники за обраний рік." in dashboard
    assert "Станом на квартал" not in dashboard
    assert "Виконання завдань" in dashboard
    assert "Структура статусів виконання" in dashboard
    assert "Прогнозована вірогідність" not in all_changed
    assert "dashboard-execution-v2" in all_changed


def test_risk_thresholds():
    assert risk_level(86) == "Низький ризик"
    assert risk_level(85) == "Середній ризик"
    assert risk_level(51) == "Середній ризик"
    assert risk_level(50.99) == "Високий ризик"
    assert risk_level(20) == "Високий ризик"
    assert risk_level(19.99) == "Критичний ризик"



def test_review_methodology_edge_cases():
    from core.dashboard_periods import parse_measure_period, period_state
    # Bare year parser must not be intercepted by generic date parsing.
    assert parse_measure_period("2026", end=False) == 20261
    assert parse_measure_period("2026", end=True) == 20264
    assert period_state(None, 20264, 20262) == "unknown_period"

    # Unknown period is explicit and excluded rather than auto-zeroed.
    strat = pd.DataFrame([measure("unknown", 100, start="невідомо", end="IV квартал 2026")])
    snap = build_quarter_snapshot(strat, pd.DataFrame(), 2026, "II", locked_periods=set())
    row = snap.iloc[0]
    assert row["period_state"] == "unknown_period" and pd.isna(row["execution_score"])
    assert row["data_quality_conflict"] and not row["included_in_assessment"]

    # Ended without any valid final result is assessed as zero with a final-missing signal.
    strat = pd.DataFrame([measure("ended-missing", 100, end="II квартал 2026")])
    snap = build_quarter_snapshot(strat, pd.DataFrame(), 2026, "III", locked_periods=set())
    row = snap.iloc[0]
    assert row["period_state"] == "ended" and row["status"] == "Не подано"
    assert row["execution_score"] == 0 and row["final_missing_result"]
    assert not row["coverage_eligible"] and attention_mask(snap).iloc[0]

    # Obsolete is excluded from both execution and risk.
    strat = pd.DataFrame([measure("obsolete", 100)])
    req = pd.DataFrame([request("obsolete", 2, "x", status="Втратило актуальність")])
    snap = build_quarter_snapshot(strat, req, 2026, "II", locked_periods=set())
    assert pd.isna(snap.iloc[0]["execution_score"]) and not snap.iloc[0]["risk_eligible"]

    # Negative forecast is clamped at zero while negative increment is preserved.
    traj = numeric_trajectory(10, 100, "III", previous_fact=80)
    approx(traj["current_increment"], -70)
    assert traj["negative_trajectory"] and traj["forecast_year"] == 0
    assert traj["forecast_attainment_pct"] == 0

    # Q4 numeric and yes/no are final outcomes, never predictive risk.
    final_num = numeric_trajectory(90, 100, "IV", previous_fact=80)
    assert final_num["risk_level"] is None and final_num["forecast_attainment_pct"] is None
    approx(final_num["final_attainment_pct"], 90)
    final_no = yes_no_trajectory("ні", selected_year=2026, selected_quarter="IV", deadline="IV квартал 2026")
    assert final_no["risk_level"] is None and final_no["final_outcome"] == "Результат не досягнуто"


def test_locked_observation_excluded_from_future_risk_history():
    from core.dashboard_breakdowns import build_period_results
    strat = pd.DataFrame([measure("locked-history", 100)])
    req = pd.DataFrame([
        request("locked-history", 1, 20, rid=1),
        request("locked-history", 2, 50, rid=2),
    ])
    results = build_period_results(
        strat, req, [(2026, "I"), (2026, "II")], locked_periods={("2026", 1)}
    )
    q2 = results[(2026, "II")]["snapshot"].iloc[0]
    assert q2["current_increment"] is None or pd.isna(q2["current_increment"])
    assert q2["forecast_kind"] == "insufficient_history"
    assert q2["risk_level"] is None


def test_stable_cohort_previous_current_consistency():
    from core.dashboard_breakdowns import build_period_results, aggregate_plan
    strat = pd.DataFrame([measure("m1", 100), measure("m2", 100)])
    req = pd.DataFrame([
        request("m1", 1, 50, status="Частково виконано", rid=1),
        request("m2", 1, 0, status="Не виконано", rid=2),
        request("m1", 2, 100, status="Виконано", rid=3),
        request("m2", 2, 50, status="Частково виконано", rid=4),
    ])
    results = build_period_results(
        strat, req, [(2026, "I"), (2026, "II")], locked_periods=set(),
        stable_statuses=["Виконано"],
    )
    assert results[(2026, "II")]["stable_cohort_codes"] == {"m1"}
    assert set(results[(2026, "I")]["snapshot"]["code"]) == {"m1"}
    assert set(results[(2026, "II")]["snapshot"]["code"]) == {"m1"}
    agg = aggregate_plan(results)
    approx(agg["execution_by_measures_average"], 75)
    approx(agg["execution_by_measures_change"], 50)


def test_multi_period_group_summaries_and_matrix():
    from core.dashboard_breakdowns import (
        build_period_results, aggregate_objects, ssp_summary, deputy_summary,
        execution_forecast_matrix,
    )
    strat = pd.DataFrame([
        {**measure("g1", 100, task="T1", goal="G"), "resp_main":"ССП 5", "deputy_minister_raw":"Заступник А"},
        {**measure("g2", 100, task="T2", goal="G"), "resp_main":"ССП 5", "deputy_minister_raw":"Заступник А"},
    ])
    req = pd.DataFrame([
        request("g1", 1, 25, rid=1), request("g2", 1, 50, rid=2),
        request("g1", 2, 50, rid=3), request("g2", 2, 100, status="Виконано", rid=4),
    ])
    results = build_period_results(strat, req, [(2026,"I"),(2026,"II")], locked_periods=set())
    goals = aggregate_objects(results, object_type="goal")
    tasks = aggregate_objects(results, object_type="task")
    assert {"average_by_measures","latest_by_measures","change_by_measures","average_by_tasks","latest_by_tasks","change_by_tasks"}.issubset(goals.columns)
    assert {"average_execution","latest_execution","change_execution"}.issubset(tasks.columns)
    ssp = ssp_summary(results, ["5"])
    assert {"average","latest","change","average_coverage","latest_coverage","risk_high_critical_latest"}.issubset(ssp.columns)
    deputy = deputy_summary(results)
    assert {"average","latest","change","average_coverage","latest_coverage","risk_high_critical_latest"}.issubset(deputy.columns)
    matrix = execution_forecast_matrix(results[(2026,"II")]["snapshot"])
    assert {"execution","forecast_attainment","risk_level","group_size"}.issubset(matrix.columns)
    # Q4 matrix is not applicable.
    q4 = build_period_results(strat, req, [(2026,"IV")], locked_periods=set())[(2026,"IV")]["snapshot"]
    assert execution_forecast_matrix(q4).empty


def test_q1_risk_summary_and_matrix_are_preliminary():
    from core.dashboard_breakdowns import build_period_results, execution_forecast_matrix
    from core.dashboard_risk import risk_summary
    strat = pd.DataFrame([
        {**measure("q1-matrix", 100), "resp_main": "ССП 5"}
    ])
    req = pd.DataFrame([request("q1-matrix", 1, 20, rid=1)])
    result = build_period_results(
        strat, req, [(2026, "I")], locked_periods=set()
    )[(2026, "I")]
    row = result["snapshot"].iloc[0]
    assert row["forecast_kind"] == "preliminary" and pd.isna(row["risk_level"])
    summary = risk_summary(result["snapshot"])
    assert summary["share_high_critical_risk"] is None
    assert summary["share_without_substantial_risk"] is None
    assert summary["preliminary_forecast_count"] == 1
    assert summary["preliminary_attention_count"] == 1
    matrix = execution_forecast_matrix(result["snapshot"])
    assert not matrix.empty
    assert matrix["preliminary"].all()
    assert set(matrix["risk_level"]) == {"Попередній прогноз"}


def test_finance_four_categories():
    from core.dashboard_finance import classify_finance_sources, build_finance_frame, finance_kpis
    rows = [
        {"budget_kpkvk":"1201010", "budget_2026_approved":1, "other_source":"", "other_2026_plan":""},
        {"budget_kpkvk":"", "budget_2026_approved":"", "other_source":"МТД / кошти партнерів", "other_2026_plan":1},
        {"budget_kpkvk":"", "budget_2026_approved":"", "other_source":"власні кошти підприємств", "other_2026_plan":1},
        {"budget_kpkvk":"", "budget_2026_approved":"", "other_source":"", "other_2026_plan":""},
    ]
    cats = [classify_finance_sources(row) for row in rows]
    assert "Державний бюджет" in cats[0]
    assert "МТД / кошти партнерів" in cats[1]
    assert "Небюджетні / інші" in cats[2]
    assert cats[3] == ["Без фінансування"]
    assert "Державний бюджет" in classify_finance_sources({"budget_2026_approved": 1.2})
    assert "Небюджетні / інші" in classify_finance_sources({"other_2026_plan": 0.3})

    # T/U: finance identity is exactly (code, year), never code+year+quarter.
    fin_index = {
        ("fin", "2026"): {
            "kpkvk": "1201010", "other_source": "",
            "plan_bln": 2.0, "fact_bln": 1.0,
        }
    }
    snap_q2 = pd.DataFrame([{
        **measure("fin", 100), "execution_score": 50.0, "budget_2026_approved": 2.0
    }])
    snap_q3 = snap_q2.copy(); snap_q3["execution_score"] = 75.0
    fin_q2 = build_finance_frame(snap_q2, 2026, fin_index=fin_index)
    fin_q3 = build_finance_frame(snap_q3, 2026, fin_index=fin_index)
    assert len(fin_q2) == len(fin_q3) == 1
    approx(fin_q2.iloc[0]["plan_bln"], 2)
    approx(fin_q2.iloc[0]["fact_bln"], 1)
    approx(fin_q2.iloc[0]["financial_execution_pct"], 50)
    # V: annual financial values do not change when reporting execution context changes.
    for field in ["plan_bln", "fact_bln", "financial_execution_pct"]:
        approx(fin_q2.iloc[0][field], fin_q3.iloc[0][field])
    assert fin_q2.iloc[0]["elasticity"] != fin_q3.iloc[0]["elasticity"]
    future = snap_q2.copy(); future["execution_score"] = pd.NA
    future_fin = build_finance_frame(future, 2026, fin_index=fin_index)
    approx(future_fin.iloc[0]["plan_bln"], 2)
    approx(future_fin.iloc[0]["fact_bln"], 1)
    assert future_fin.iloc[0]["elasticity"] is None
    kpis = finance_kpis(fin_q2)
    approx(kpis["financial_execution_pct"], 50)


def test_management_conclusion_thresholds():
    from core.dashboard_risk import management_conclusion, COVERAGE_GATE_MIN
    assert COVERAGE_GATE_MIN == 70.0

    def frame(q, high_count=0, total=10):
        risks = ["Високий ризик"] * high_count + ["Низький ризик"] * (total - high_count)
        return pd.DataFrame([
            {
                "quarter": q, "execution_score": 80, "result_achieved": False,
                "risk_level": risk, "forecast_attainment_pct": 80,
                "pace_sufficiency_pct": 90, "forecast_kind": "trajectory",
            }
            for risk in risks
        ])

    # L + coverage None: gate is evaluated before any risk verdict.
    insufficient = management_conclusion(
        frame("II", 0), execution_by_measures=70, execution_by_goals=72, coverage=69
    )
    assert insufficient["title"] == "Недостатньо даних для управлінського висновку"
    missing_cov = management_conclusion(
        frame("II", 0), execution_by_measures=70, execution_by_goals=72, coverage=None
    )
    assert missing_cov["title"] == "Недостатньо даних для управлінського висновку"

    # M/N/O: 70% coverage unlocks exactly the agreed 15/35 problem-share thresholds.
    controlled = management_conclusion(
        frame("II", 1), execution_by_measures=70, execution_by_goals=72, coverage=70
    )
    assert controlled["title"] == "Реалізація переважно контрольована"
    for fragment in [
        "Покриття", "високий + критичний ризик", "без суттєвого ризику",
        "середнє прогнозоване досягнення", "середня достатність темпу",
    ]:
        assert fragment in controlled["explanation"]
    risk_source = (ROOT / "core" / "dashboard_risk.py").read_text(encoding="utf-8")
    assert "coverage >= 80" not in risk_source and "coverage > 80" not in risk_source
    attention = management_conclusion(
        frame("II", 2), execution_by_measures=70, execution_by_goals=72, coverage=70
    )
    assert attention["title"] == "Потрібна увага до окремих напрямів"
    severe = management_conclusion(
        frame("II", 4), execution_by_measures=70, execution_by_goals=72, coverage=70
    )
    assert severe["title"] == "Суттєвий ризик недосягнення результатів"

    # Q1 remains preliminary and Q4 remains final, both coverage-aware.
    q1 = frame("I", 0)
    q1["risk_level"] = None; q1["forecast_kind"] = "preliminary"
    q1["preliminary_attention"] = False
    q1_low = management_conclusion(q1, execution_by_measures=40, execution_by_goals=45, coverage=69)
    assert q1_low["title"] == "Початковий стан реалізації" and "нижче" in q1_low["explanation"]
    q1_ok = management_conclusion(q1, execution_by_measures=40, execution_by_goals=45, coverage=70)
    assert q1_ok["title"] == "Початковий стан реалізації"
    assert "Попередній прогноз сформовано" in q1_ok["explanation"]
    assert "високого/критичного ризику" not in q1_ok["explanation"]
    q4f = frame("IV", 0); q4f["risk_level"] = None; q4f["forecast_kind"] = "final"
    q4f.loc[:7, "result_achieved"] = True
    q4_low = management_conclusion(q4f, execution_by_measures=80, execution_by_goals=82, coverage=69)
    assert q4_low["title"] == "Підсумок року: недостатньо даних для повної оцінки"
    q4 = management_conclusion(q4f, execution_by_measures=80, execution_by_goals=82, coverage=100)
    assert q4["title"].startswith("Підсумок року")


def test_feature_preservation_contracts():
    """Static integration checks inspect executable structure/calls, not only labels."""
    import ast
    dashboard_path = ROOT / "pages" / "2_Dashboard.py"
    app_path = ROOT / "app.py"
    dashboard = dashboard_path.read_text(encoding="utf-8")
    app = app_path.read_text(encoding="utf-8")
    assert dashboard_path.stat().st_size > 200_000, "full current Dashboard base was not preserved"
    assert app_path.stat().st_size > 70_000, "full current Home base was not preserved"
    tree = ast.parse(dashboard)
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                calls.append(fn.id)
            elif isinstance(fn, ast.Attribute):
                parts=[]; cur=fn
                while isinstance(cur, ast.Attribute):
                    parts.append(cur.attr); cur=cur.value
                if isinstance(cur, ast.Name): parts.append(cur.id)
                calls.append(".".join(reversed(parts)))
    required_call_fragments = [
        "render_measure_rows_with_card_links", "_render_indicator_trajectory_section",
        "_prepare_dashboard_finance_measures", "build_presentation_pdf", "render_plotly_chart",
        "operational.apply_operational_mode", "append_confirmed_closeout_facts", "render_scope_toggle",
        "dashboard_breakdowns_v2.aggregate_objects", "dashboard_breakdowns_v2.ssp_summary",
        "dashboard_breakdowns_v2.deputy_summary", "dashboard_breakdowns_v2.execution_forecast_matrix",
        "dashboard_risk_v2.attention_mask",
    ]
    for name in required_call_fragments:
        assert any(call.endswith(name) or call == name for call in calls), name
    assert calls.count("render_plotly_chart") >= 8
    assert "operational.operational_indicator_rows" in calls

    # Key preserved charts must still be executable assignments, not labels.
    assigned_call_targets = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            fn = node.value.func
            if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
                call_name = f"{fn.value.id}.{fn.attr}"
            elif isinstance(fn, ast.Name):
                call_name = fn.id
            else:
                call_name = ""
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned_call_targets[target.id] = call_name
    assert assigned_call_targets.get("fig_donut") == "px.pie"
    assert assigned_call_targets.get("fig_tl2") == "px.bar"
    assert assigned_call_targets.get("fig_matrix") == "px.scatter"
    assert assigned_call_targets.get("fig_trend") == "px.line"
    assert "fig_goals" in assigned_call_targets and "fig_tasks" in assigned_call_targets
    assert '"toImageButtonOptions"' in dashboard and '"format": "png"' in dashboard
    assert "_build_period_source_overrides" in calls
    # Actual branches/functions remain, not merely text labels.
    assert any(isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == "presentation_mode" for n in ast.walk(tree))
    assert "def _render_indicator_trajectory_section" in dashboard
    assert "Проблемні заходи" in dashboard and "Повна таблиця заходів у зрізі" in dashboard
    assert "Таймлайн" in dashboard or "дедлайн" in dashboard.lower()
    assert "Структура джерел фінансування" in dashboard
    assert "core_exports.build_main_monitoring_export" in app
    assert "dashboard_execution_v2.hierarchy_for_period" in app
    assert "_home_task_score_map" in app and "_home_goal_score_map" in app
    assert "indicator_row_matches_search" in app and "row_matches_search" in app
    assert "render_scope_toggle(\"app\"" in app
    # Old management formulas/terminology are gone from the page.
    forbidden = ["risk_probability", "risk_score_calc", "traffic_light", "expected_completion_for_quarter", "deviation_for_period", "Прогнозована вірогідність"]
    for token in forbidden:
        assert token not in dashboard, token



def test_archive_source_override_and_unlocked_2026():
    from core.dashboard_breakdowns import build_period_results
    from core.dashboard_periods import monitoring_conducted

    # Q1/Q2 2026 are ordinary reporting periods when period_locks does not lock them.
    assert monitoring_conducted(2026, "I", locked_periods=set()) is True
    assert monitoring_conducted(2026, "II", locked_periods=set()) is True

    # Archive inputs are recalculated with the same v2 core and Q2 may use Q1
    # as its immediate previous observation now that Q1 is not hardcoded away.
    strat = pd.DataFrame([measure("arch", 100)])
    current_req = pd.DataFrame([
        request("arch", 1, 99, rid=1),
        request("arch", 2, 50, rid=2),
    ])
    archived_q1 = pd.DataFrame([request("arch", 1, 20, rid=10)])
    period_sources = {
        (2026, "I"): {
            "strat_df": strat,
            "requests_df": archived_q1,
            "locked_periods": set(),
        }
    }
    results = build_period_results(
        strat, current_req, [(2026, "I"), (2026, "II")],
        locked_periods=set(), period_sources=period_sources,
    )
    approx(results[(2026, "I")]["execution_by_measures"], 20)
    q2 = results[(2026, "II")]["snapshot"].iloc[0]
    approx(q2["current_increment"], 30)
    assert q2["forecast_kind"] == "trajectory"


def main():
    tests = [
        test_numeric_control_cases,
        test_snapshot_period_semantics,
        test_numeric_priority_and_conflict,
        test_hierarchy,
        test_filters_and_cross_page_consistency,
        test_q1_and_yes_no,
        test_attach_risk_uses_previous_quarter,
        test_multi_period_aggregation_and_locked_gap,
        test_current_reporting_period,
        test_archive_source_override_and_unlocked_2026,
        test_review_methodology_edge_cases,
        test_locked_observation_excluded_from_future_risk_history,
        test_stable_cohort_previous_current_consistency,
        test_multi_period_group_summaries_and_matrix,
        test_q1_risk_summary_and_matrix_are_preliminary,
        test_finance_four_categories,
        test_management_conclusion_thresholds,
        test_page_integration_contracts,
        test_feature_preservation_contracts,
        test_risk_thresholds,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"PASS {len(tests)} test groups")


if __name__ == "__main__":
    main()
