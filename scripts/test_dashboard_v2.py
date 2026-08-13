"""Pure calculation/control tests for Dashboard execution v3.

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
    DASHBOARD_FORMULA_VERSION,
    build_quarter_snapshot,
    goal_scores,
    hierarchy_for_period,
    plan_scores,
    score_measure,
    task_scores,
)
from core.dashboard_filters import (  # noqa: E402
    UNASSIGNED_DEPUTY,
    apply_stable_cohort,
    expand_ssp_rows,
    filter_measures,
    main_ssp_deputy,
    main_ssp_index,
    stable_cohort_codes,
)
from core.dashboard_risk import (  # noqa: E402
    numeric_trajectory, risk_level, attach_risk, yes_no_trajectory, attention_mask,
    RISK_COLORS, RISK_ORDER,
)


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
    # V3 active missing-current carries the latest same-year confirmed result for execution.
    strat = pd.DataFrame([measure("1.1.9.", 118)])
    req = pd.DataFrame([request("1.1.9.", 3, 110.92, rid=1)])
    snap = build_quarter_snapshot(strat, req, 2026, "IV", locked_periods=set())
    row = snap.iloc[0]
    assert row["period_state"] == "active"
    assert row["status"] == "Не подано" and not row["submitted"]
    approx(row["execution_score"], 94)
    assert row["carry_forward"] and row["carry_forward_kind"] == "active_previous_result"
    assert row["source_year"] == 2026 and row["source_quarter"] == "III"
    assert row["has_monitoring_data"] and row["missing_required_submission"]

    # Synthetic inherited yes/no rows must not count as a current submission.
    synthetic = request("1.1.9.", 4, "так", status="Виконано", rid=2)
    synthetic["_auto_inherited"] = True
    snap = build_quarter_snapshot(strat, pd.DataFrame([*req.to_dict("records"), synthetic]), 2026, "IV", locked_periods=set())
    assert snap.iloc[0]["status"] == "Не подано"
    approx(snap.iloc[0]["execution_score"], 94)

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
    assert filtered["code"].tolist() == ["m1"]
    graph_rows = expand_ssp_rows(filtered, ["5"])
    assert set(graph_rows["ssp"]) == {"5"} and len(graph_rows) == 1
    req = pd.DataFrame([
        request("m1", 2, 100, status="Виконано", rid=1),
        request("m2", 2, 50, status="Частково виконано", rid=2),
    ])
    shared = hierarchy_for_period(filtered, req, 2026, "II", locked_periods=set())
    # This same dict/dataframe is what both pages consume; no page formula exists.
    tasks = shared["task_scores"].set_index("task_code")["execution"].to_dict()
    assert tasks == {"T1": 100.0}
    approx(shared["goal_scores"].iloc[0]["by_tasks"], 100)

    latest = shared["snapshot"].copy()
    latest.loc[latest.code.eq("m1"), "status"] = "Не виконано"
    cohort = stable_cohort_codes(latest, ["Не виконано"])
    assert cohort == {"m1"}
    assert apply_stable_cohort(shared["snapshot"], cohort)["code"].tolist() == ["m1"]


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
    assert "Застосувати фільтри" in app
    assert "Застосувати загальні фільтри" in dashboard
    assert "Скинути загальні фільтри" in dashboard
    assert "Стан виконання" in dashboard and "Порівняння результатів" in dashboard and "Динаміка виконання" in dashboard and "Фінансування" in dashboard

    # Common filters and section-period applied state are intentionally separate.
    for state_key in [
        "dash_snapshot_period_applied_v1", "dash_breakdown_period_applied_v1",
        "dash_dynamics_period_applied_v1", "dash_finance_period_applied_v1",
    ]:
        assert state_key in dashboard
    assert "dashboard_snapshot_period_form_v1" in dashboard
    assert 'f"dashboard_{section_key}_period_form_v1"' in dashboard
    assert '_render_period_range_panel(\n        "breakdown"' in dashboard
    assert '_render_period_range_panel(\n        "dynamics"' in dashboard
    assert "dashboard_finance_period_form_v1" in dashboard
    assert dashboard.count('"Застосувати параметри"') >= 3
    assert dashboard.count('"Скинути параметри"') >= 3

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
    assert "dash_breakdown_period_error" in dashboard
    assert "dash_dynamics_period_error" in dashboard
    assert "Початок періоду не може бути пізніше за кінець періоду." in dashboard

    # Defaults: I quarter of current reporting year through current reporting period.
    assert '_default_range_start_period = (_default_reporting_year, "I")' in dashboard
    assert '_default_range_end_period = (_default_reporting_year, _default_reporting_quarter)' in dashboard
    assert 'def _reset_dashboard_common_filters_v21' in dashboard
    assert 'def _reset_dashboard_snapshot_period_v1' in dashboard
    assert 'def _reset_dashboard_breakdown_period_v1' in dashboard
    assert 'def _reset_dashboard_dynamics_period_v1' in dashboard
    assert 'def _reset_dashboard_finance_period_v1' in dashboard

    # Finance is annual-only and automatically resolves execution context.
    assert '"dash_finance_year"' in dashboard
    assert "latest_reporting_period_in_year" in dashboard
    assert "Фінансові показники за обраний рік." in dashboard
    assert "Станом на квартал" not in dashboard
    assert "Виконання завдань" in dashboard
    assert "Структура статусів виконання" in dashboard
    assert "Прогнозована вірогідність" not in all_changed
    assert "dashboard-execution-v3" in all_changed


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



def test_live_ui_data_regressions():
    """Regression coverage for the live Streamlit UX/data issues (A-R)."""
    import ast
    import re
    from types import SimpleNamespace
    from core import dashboard_periods as dashboard_periods_v2
    from core import dashboard_risk as dashboard_risk_v2
    from core.dashboard_breakdowns import (
        build_period_results,
        execution_forecast_diagnostics,
        execution_forecast_matrix,
    )

    dashboard_path = ROOT / "pages" / "2_Dashboard.py"
    dashboard = dashboard_path.read_text(encoding="utf-8")
    tree = ast.parse(dashboard)

    # Execute only pure/callback function definitions from the production page;
    # importing the whole Streamlit page would execute UI side effects.
    wanted_functions = {
        "clean", "strip_code_from_name", "_normalise_period_pair",
        "_apply_dashboard_common_filters_v21", "_reset_dashboard_common_filters_v21",
        "_apply_dashboard_snapshot_period_v1", "_reset_dashboard_snapshot_period_v1",
        "_apply_dashboard_breakdown_period_v1", "_reset_dashboard_breakdown_period_v1",
        "_apply_dashboard_dynamics_period_v1", "_reset_dashboard_dynamics_period_v1",
        "_apply_dashboard_finance_period_v1", "_reset_dashboard_finance_period_v1",
        "_dashboard_archive_reporting_period", "_format_summary_number", "_format_percent",
        "_format_table_number", "_short_summary_label", "_task_chart_label",
        "_goal_change_label", "_high_risk_groups", "_high_risk_insight_text",
    }
    selected_defs = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted_functions
    ]

    state = {
        "dash_data_source_mode": "confirmed",
        "dash_presentation_mode": False,
        "dash_department_indices": [], "dash_goals": [], "dash_tasks": [],
        "dash_product_types": [], "dash_deputies": [], "dash_statuses": [],
        "dash_financing": [], "dash_kpkvk": [],
        # Draft values deliberately differ from the currently applied section state.
        "dash_snapshot_year": 2026, "dash_snapshot_quarter": "IV",
        "dash_breakdown_start_period": (2026, "I"), "dash_breakdown_end_period": (2026, "II"),
        "dash_dynamics_start_period": (2026, "I"), "dash_dynamics_end_period": (2026, "II"),
        "dash_finance_year": 2027,
        "dash_snapshot_period_applied_v1": {"year": 2026, "quarter": "III"},
        "dash_breakdown_period_applied_v1": {"start_period": (2026, "I"), "end_period": (2026, "III")},
        "dash_dynamics_period_applied_v1": {"start_period": (2026, "I"), "end_period": (2026, "III")},
        "dash_finance_period_applied_v1": {"year": 2026},
        "dash_breakdown_period_error": "", "dash_dynamics_period_error": "",
    }
    fake_st = SimpleNamespace(session_state=state)
    period_options = dashboard_periods_v2.reporting_period_range(2026, "I", 2028, "IV")
    env = {
        "pd": pd, "re": re, "st": fake_st,
        "dashboard_periods_v2": dashboard_periods_v2,
        "dashboard_risk_v2": dashboard_risk_v2,
        "DASHBOARD_FORMULA_VERSION": DASHBOARD_FORMULA_VERSION,
        "quarter_to_roman": dashboard_periods_v2.quarter_to_roman,
        "_reporting_period_options": period_options,
        "_default_reporting_year": 2026, "_default_reporting_quarter": "III",
        "_default_range_start_period": (2026, "I"), "_default_range_end_period": (2026, "III"),
        "_snapshot_period_default": {"year": 2026, "quarter": "III"},
        "_breakdown_period_default": {"start_period": (2026, "I"), "end_period": (2026, "III")},
        "_dynamics_period_default": {"start_period": (2026, "I"), "end_period": (2026, "III")},
        "_finance_period_default": {"year": 2026},
        "_dash_common_defaults": {
            "data_source_mode": "confirmed", "presentation_mode": False,
            "department_indices": [], "goals": [], "tasks": [], "product_types": [],
            "deputies": [], "statuses": [], "financing": [], "kpkvk": [],
        },
        "_dashboard_common_widget_defaults": {
            "dash_data_source_mode": "confirmed", "dash_presentation_mode": False,
            "dash_department_indices": [], "dash_goals": [], "dash_tasks": [],
            "dash_product_types": [], "dash_deputies": [], "dash_statuses": [],
            "dash_financing": [], "dash_kpkvk": [],
        },
        "operational": SimpleNamespace(MODE_CONFIRMED="confirmed"),
    }
    exec(compile(ast.Module(body=selected_defs, type_ignores=[]), str(dashboard_path), "exec"), env)

    # A/B + live UX scenario: top Apply/Reset cannot touch section period state.
    before_sections = {
        key: dict(state[key]) for key in [
            "dash_snapshot_period_applied_v1", "dash_breakdown_period_applied_v1",
            "dash_dynamics_period_applied_v1", "dash_finance_period_applied_v1",
        ]
    }
    env["_apply_dashboard_common_filters_v21"]()
    for key, expected in before_sections.items():
        assert state[key] == expected
    assert state["dash_snapshot_period_applied_v1"]["quarter"] == "III"  # draft widget is IV
    env["_reset_dashboard_common_filters_v21"]()
    for key, expected in before_sections.items():
        assert state[key] == expected

    # C/D: snapshot local Apply/Reset changes only snapshot state.
    other_before = dict(state["dash_breakdown_period_applied_v1"])
    env["_apply_dashboard_snapshot_period_v1"]()
    assert state["dash_snapshot_period_applied_v1"] == {"year": 2026, "quarter": "IV"}
    assert state["dash_breakdown_period_applied_v1"] == other_before
    env["_reset_dashboard_snapshot_period_v1"]()
    assert state["dash_snapshot_period_applied_v1"] == {"year": 2026, "quarter": "III"}
    assert state["dash_snapshot_quarter"] == "III"

    # E: comparison range is isolated; invalid range preserves previous applied value.
    state["dash_breakdown_start_period"] = (2026, "II")
    state["dash_breakdown_end_period"] = (2026, "III")
    env["_apply_dashboard_breakdown_period_v1"]()
    assert state["dash_breakdown_period_applied_v1"] == {
        "start_period": (2026, "II"), "end_period": (2026, "III")
    }
    previous_breakdown = dict(state["dash_breakdown_period_applied_v1"])
    state["dash_breakdown_start_period"] = (2027, "I")
    state["dash_breakdown_end_period"] = (2026, "IV")
    env["_apply_dashboard_breakdown_period_v1"]()
    assert state["dash_breakdown_period_applied_v1"] == previous_breakdown
    assert "Початок періоду" in state["dash_breakdown_period_error"]
    env["_reset_dashboard_breakdown_period_v1"]()
    assert state["dash_breakdown_period_applied_v1"] == env["_breakdown_period_default"]

    # F/G: dynamics and finance have their own isolated Apply/Reset.
    state["dash_dynamics_start_period"] = (2026, "II")
    state["dash_dynamics_end_period"] = (2026, "III")
    env["_apply_dashboard_dynamics_period_v1"]()
    assert state["dash_dynamics_period_applied_v1"] == {
        "start_period": (2026, "II"), "end_period": (2026, "III")
    }
    env["_reset_dashboard_dynamics_period_v1"]()
    assert state["dash_dynamics_period_applied_v1"] == env["_dynamics_period_default"]
    state["dash_finance_year"] = 2027
    env["_apply_dashboard_finance_period_v1"]()
    assert state["dash_finance_period_applied_v1"] == {"year": 2027}
    env["_reset_dashboard_finance_period_v1"]()
    assert state["dash_finance_period_applied_v1"] == {"year": 2026}

    # H/I: ambiguous legacy archive and incompatible formula never become v3 overrides.
    archive_period = env["_dashboard_archive_reporting_period"]
    ambiguous_row = {"year": 2026, "quarter": 3, "reason": "захотілося"}
    assert archive_period(ambiguous_row, {"dashboard_formula_version": "dashboard-execution-v2"}) is None
    assert archive_period(
        {"reason": "II квартал 2026"},
        {"dashboard_formula_version": "dashboard-execution-v1"},
    ) is None
    assert archive_period(
        {"reason": "II квартал 2026"},
        {"dashboard_formula_version": "dashboard-execution-v2"},
    ) is None
    assert archive_period(
        {"reason": "II квартал 2026"},
        {"dashboard_formula_version": DASHBOARD_FORMULA_VERSION},
    ) == (2026, "II")
    assert "report_quarter = anchor_quarter - 1" not in dashboard
    assert "Legacy snapshots store the anchor quarter" not in dashboard

    # J/K: real Q2 data remains non-zero and supplies Q3 previous-fact trajectory/matrix.
    strat = pd.DataFrame([measure("live", 100)])
    live_requests = pd.DataFrame([
        request("live", 1, 20, rid=1), request("live", 2, 50, rid=2), request("live", 3, 70, rid=3),
    ])
    # The ambiguous archive above produces no key, therefore no period-source override.
    results = build_period_results(
        strat, live_requests, [(2026, "I"), (2026, "II"), (2026, "III")],
        locked_periods=set(), period_sources={},
    )
    approx(results[(2026, "II")]["execution_by_measures"], 50)
    approx(results[(2026, "II")]["coverage"], 100)
    q3_snapshot = results[(2026, "III")]["snapshot"]
    matrix = execution_forecast_matrix(q3_snapshot, group_col="department")
    diagnostics = execution_forecast_diagnostics(q3_snapshot, group_col="department")
    assert not matrix.empty
    assert diagnostics["numeric_current_count"] == 1
    assert diagnostics["numeric_with_previous_fact_count"] == 1
    assert diagnostics["numeric_forecast_count"] == 1
    assert diagnostics["groups_in_matrix"] == 1

    # L: qualitative risk is explained as qualitative, never as a missing percent forecast.
    qualitative = pd.DataFrame([{
        "code": "qual", "goal_code": "4", "strategic_goal": "Ціль 4",
        "risk_level": "Високий ризик", "forecast_attainment_pct": None,
        "pace_sufficiency_pct": None,
    }])
    grouped = env["_high_risk_groups"](qualitative, ["goal_code", "strategic_goal"])
    assert int(grouped.iloc[0]["risk_measure_count"]) == 1
    assert int(grouped.iloc[0]["numeric_forecast_count"]) == 0
    assert int(grouped.iloc[0]["qualitative_risk_count"]) == 1
    qualitative_text = env["_high_risk_insight_text"]("Ціль 4", grouped.iloc[0])
    assert "якісними статусами" in qualitative_text
    assert "числовий прогноз" in qualitative_text and "не застосовується" in qualitative_text
    assert "н/д%" not in qualitative_text and "н/д%" not in dashboard
    assert env["_format_percent"](None) == "н/д"
    mixed = pd.DataFrame([
        {"code": "num", "goal_code": "4", "strategic_goal": "Ціль 4",
         "risk_level": "Високий ризик", "forecast_attainment_pct": 61.4,
         "pace_sufficiency_pct": 52.1},
        {"code": "qual", "goal_code": "4", "strategic_goal": "Ціль 4",
         "risk_level": "Критичний ризик", "forecast_attainment_pct": None,
         "pace_sufficiency_pct": None},
    ])
    mixed_group = env["_high_risk_groups"](mixed, ["goal_code", "strategic_goal"]).iloc[0]
    mixed_text = env["_high_risk_insight_text"]("Ціль 4", mixed_group)
    assert "числовий прогноз доступний для 1" in mixed_text
    assert "61.4%" in mixed_text and "від необхідного темпу" in mixed_text

    # M: canonical risk colors are distinct and shared by all risk visualizations.
    assert RISK_COLORS["Критичний ризик"] == "#DC4A4A"
    assert RISK_COLORS["Високий ризик"] == "#FF7A45"
    assert RISK_COLORS["Критичний ризик"] != RISK_COLORS["Високий ризик"]
    assert RISK_ORDER == ["Критичний ризик", "Високий ризик", "Середній ризик", "Низький ризик"]
    assert "RISK_COLORS = dashboard_risk_v2.RISK_COLORS" in dashboard
    assert 'category_orders={"auto_risk": RISK_ORDER}' in dashboard

    # N/O/P: presentation labels and management tables are display-only, max 2 decimals.
    task_label = env["_task_chart_label"]("1.1", "1.1. Назва")
    assert task_label.count("1.1") == 1 and task_label.endswith("Назва")
    assert env["_format_table_number"](66.6666666667, 2) == "66.67"
    assert env["_format_table_number"](48.2777777777, 2) == "48.28"
    assert env["_format_table_number"](None, 2) == "—"
    assert "_ssp_display_numeric_columns" in dashboard and "_deputy_display_numeric_columns" in dashboard
    assert "formatters={" in dashboard
    assert "y=-0.52" in dashboard and "b=170" in dashboard and "height=445" in dashboard

    # Q/R: goal-change axis contains code+name and hover contains start/latest/change.
    goal_label = env["_goal_change_label"]("1", "1. Розвиток конкурентної економіки")
    assert goal_label.startswith("1 — Розвиток конкурентної економіки")
    for fragment in ["Початок:", "Кінець:", "Зміна:", "start_by_tasks", "latest_by_tasks"]:
        assert fragment in dashboard
    assert 'goals_change["_sort"] = goals_change["goal_code"].apply(code_sort_key)' in dashboard
    assert 'automargin=True' in dashboard
    assert "Додатне значення = покращення; від’ємне = погіршення" in dashboard


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
        "dashboard_breakdowns_v2.execution_forecast_diagnostics", "dashboard_risk_v2.attention_mask",
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



def test_stage1_v3_active_carry_and_missing_semantics():
    """A-H: v3 formula, carry-forward, coverage, year boundary and ended outcomes."""
    from core.dashboard_breakdowns import build_period_results, execution_forecast_diagnostics, execution_forecast_matrix

    assert DASHBOARD_FORMULA_VERSION == "dashboard-execution-v3"

    # B/C/E: Q2=50, Q3 missing -> execution carries, reporting/coverage do not.
    strat = pd.DataFrame([measure("carry-num", 100)])
    req = pd.DataFrame([request("carry-num", 2, 50, status="Частково виконано", rid=1)])
    results = build_period_results(strat, req, [(2026, "III")], locked_periods=set())
    row = results[(2026, "III")]["snapshot"].iloc[0]
    assert row["formula_version"] == DASHBOARD_FORMULA_VERSION
    approx(row["execution_score"], 50)
    approx(row["raw_attainment_pct"], 50)
    assert row["status"] == "Не подано"
    assert row["effective_result_status"] == "Частково виконано"
    assert not row["submitted"] and not row["submitted_current_period"]
    assert row["has_monitoring_data"] and row["has_previous_confirmed_result"]
    assert row["missing_required_submission"] and row["attention_signal"]
    assert row["carry_forward"] and row["carry_forward_kind"] == "active_previous_result"
    assert row["source_year"] == 2026 and row["source_quarter"] == "II"
    approx(results[(2026, "III")]["execution_by_measures"], 50)
    approx(results[(2026, "III")]["coverage"], 0)
    assert pd.isna(row["forecast_attainment_pct"])
    assert pd.isna(row["pace_sufficiency_pct"])
    assert pd.isna(row["current_increment"])
    assert pd.isna(row["risk_level"])
    assert row["forecast_kind"] == "missing_submission"
    assert execution_forecast_matrix(results[(2026, "III")]["snapshot"]).empty
    diagnostics = execution_forecast_diagnostics(results[(2026, "III")]["snapshot"])
    assert diagnostics["numeric_current_count"] == 0
    assert diagnostics["numeric_forecast_count"] == 0

    # Carry-forward must preserve qualitative and yes/no execution, not score "Не подано".
    qual_strat = pd.DataFrame([measure("carry-qual", "x")])
    qual_req = pd.DataFrame([request("carry-qual", 2, "опис", status="Частково виконано")])
    qual = build_period_results(qual_strat, qual_req, [(2026, "III")], locked_periods=set())[(2026, "III")]["snapshot"].iloc[0]
    approx(qual["execution_score"], 75)
    assert qual["status"] == "Не подано" and qual["effective_result_status"] == "Частково виконано"
    assert pd.isna(qual["risk_level"])

    yn_strat = pd.DataFrame([measure("carry-yn", "так")])
    yn_req = pd.DataFrame([request("carry-yn", 2, "так", status="Виконано")])
    yn = build_period_results(yn_strat, yn_req, [(2026, "III")], locked_periods=set())[(2026, "III")]["snapshot"].iloc[0]
    approx(yn["execution_score"], 100)
    assert yn["status"] == "Не подано" and yn["yes_no"]
    assert pd.isna(yn["risk_level"])

    # D: never reported active measure gets management-zero, but not a fabricated fact/risk.
    never = build_period_results(
        pd.DataFrame([measure("never", 100)]), pd.DataFrame(), [(2026, "III")], locked_periods=set()
    )[(2026, "III")]["snapshot"].iloc[0]
    assert never["execution_score"] == 0
    assert never["status"] == "Не подано" and not never["submitted"]
    assert not never["has_monitoring_data"]
    assert never["included_in_assessment"] and never["coverage_eligible"]
    assert never["missing_required_submission"] and never["attention_signal"]
    assert never["management_zero_due_to_missing_data"]
    assert pd.isna(never["actual"]) or never["actual"] is None
    assert pd.isna(never["risk_level"]) and pd.isna(never["forecast_attainment_pct"])

    # F: active carry-forward cannot cross the year boundary.
    cross = measure("cross-year", 100, start="I квартал 2026", end="IV квартал 2027")
    cross["target_2027"] = 100
    cross_snap = build_quarter_snapshot(
        pd.DataFrame([cross]),
        pd.DataFrame([request("cross-year", 4, 80, year=2026)]),
        2027, "I", locked_periods=set(),
    ).iloc[0]
    assert cross_snap["execution_score"] == 0
    assert not cross_snap["has_monitoring_data"]
    assert cross_snap["source_year"] is None
    assert cross_snap["management_zero_due_to_missing_data"]

    # G: ended measure keeps the latest confirmed historical result without coverage penalty.
    ended_strat = pd.DataFrame([
        measure("ended", 100, end="II квартал 2026"),
        measure("active-current", 100),
    ])
    ended_req = pd.DataFrame([
        request("ended", 1, 50, status="Частково виконано", rid=1),
        request("active-current", 3, 100, status="Виконано", rid=2),
    ])
    ended_results = build_period_results(ended_strat, ended_req, [(2026, "III")], locked_periods=set())
    ended_row = ended_results[(2026, "III")]["snapshot"].set_index("code").loc["ended"]
    approx(ended_row["execution_score"], 50)
    assert ended_row["carry_forward_kind"] == "ended_final"
    assert not ended_row["coverage_eligible"] and not ended_row["missing_required_submission"]
    assert not ended_row["final_missing_result"]
    approx(ended_results[(2026, "III")]["coverage"], 100)
    assert pd.isna(ended_row["risk_level"])

    # H: ended measure with no monitoring history is zero + final-missing signal.
    ended_missing = build_quarter_snapshot(
        pd.DataFrame([measure("ended-none", 100, end="II квартал 2026")]),
        pd.DataFrame(), 2026, "III", locked_periods=set(),
    ).iloc[0]
    assert ended_missing["execution_score"] == 0 and ended_missing["final_missing_result"]
    assert ended_missing["attention_signal"]

    # Overachievement: raw is preserved, management execution remains capped.
    over = build_quarter_snapshot(
        pd.DataFrame([measure("over", 100)]),
        pd.DataFrame([request("over", 2, 128, status="Виконано")]),
        2026, "II", locked_periods=set(),
    ).iloc[0]
    approx(over["raw_attainment_pct"], 128)
    approx(over["execution_score"], 100)


def test_stage1_v3_main_ssp_and_deputy_semantics():
    """I/J/P: one measure belongs only to its main SSP and main-SSP deputy."""
    strat = pd.DataFrame([
        {**measure("m1", 100), "resp_main": "ССП 5", "resp_co_1": "ССП 8", "resp_co_2": "ССП 9"},
        {**measure("m2", 100), "resp_main": "ССП 8", "resp_co_1": "ССП 5"},
    ])
    assert filter_measures(strat, ssp=["5"])["code"].tolist() == ["m1"]
    expanded = expand_ssp_rows(strat)
    assert len(expanded) == 2
    assert dict(zip(expanded["code"], expanded["ssp"])) == {"m1": "5", "m2": "8"}
    assert main_ssp_index(strat.iloc[0]) == "5"
    assert main_ssp_deputy(strat.iloc[0]) == UNASSIGNED_DEPUTY

    deputy38 = "КІНДРАТІВ Віталій Зіновійович"
    deputy39 = "ПЕРЕЛИГІН Єгор Євгенович"
    mapped = pd.DataFrame([
        {**measure("m38", 100), "resp_main": "ССП 38", "resp_co_1": "ССП 39"},
        {**measure("m39", 100), "resp_main": "ССП 39", "resp_co_1": "ССП 38"},
    ])
    assert filter_measures(mapped, deputies=[deputy38])["code"].tolist() == ["m38"]
    assert filter_measures(mapped, deputies=[deputy39])["code"].tolist() == ["m39"]
    snap = build_quarter_snapshot(
        mapped,
        pd.DataFrame([
            request("m38", 2, 60, rid=1),
            request("m39", 2, 70, rid=2),
        ]),
        2026, "II", locked_periods=set(),
    ).set_index("code")
    assert snap.loc["m38", "main_ssp"] == "38"
    assert snap.loc["m38", "deputy_minister_by_ssp"] == deputy38
    assert snap.loc["m39", "deputy_minister_by_ssp"] == deputy39


def test_stage1_v3_ssp_weights_and_contributions():
    """K-O: unique-code weights, pre-SSP denominator and normalized contributions."""
    from core.dashboard_breakdowns import (
        build_period_results,
        filter_results_by_ssp,
        ssp_portfolio_weights,
        ssp_summary,
    )

    rows = []
    for code, ssp in [("a1", "1"), ("a2", "1"), ("b1", "2"), ("c1", "3")]:
        row = measure(code, 100)
        row["resp_main"] = f"ССП {ssp}"
        rows.append(row)
    strat = pd.DataFrame(rows)
    req = pd.DataFrame([
        request("a1", 1, 10, rid=1), request("a1", 2, 20, rid=2),
        request("a2", 1, 10, rid=3), request("a2", 2, 20, rid=4),
        request("b1", 1, 10, rid=5), request("b1", 2, 15, rid=6),
        request("c1", 1, 30, rid=7), request("c1", 2, 60, rid=8),
    ])
    base = build_period_results(strat, req, [(2026, "I"), (2026, "II")], locked_periods=set())

    # K/L: repeated quarter rows count once; 2/1/1 ownership = 50/25/25.
    weights = ssp_portfolio_weights(base).set_index("ssp")
    approx(weights.loc["1", "portfolio_weight_pct"], 50)
    approx(weights.loc["2", "portfolio_weight_pct"], 25)
    approx(weights.loc["3", "portfolio_weight_pct"], 25)
    approx(weights["portfolio_weight_pct"].sum(), 100)
    assert int(weights["portfolio_measure_count"].sum()) == 4

    # M: selected SSP display never changes the base denominator.
    display_a = filter_results_by_ssp(base, ["1"])
    summary_a = ssp_summary(display_a, base_results=base)
    assert summary_a["ssp"].tolist() == ["1"]
    approx(summary_a.iloc[0]["portfolio_weight_pct"], 50)

    # N: contribution to total deficit is normalized across the base portfolio.
    summary_all = ssp_summary(base, base_results=base)
    deficit = pd.to_numeric(summary_all["underperformance_contribution_pct"], errors="coerce").dropna()
    approx(deficit.sum(), 100)

    # O: Q2 standard risk contribution is normalized; Q1/Q4 are not applicable.
    risk_contrib = pd.to_numeric(summary_all["risk_contribution_pct"], errors="coerce").dropna()
    approx(risk_contrib.sum(), 100)

    q1_only = build_period_results(strat, req, [(2026, "I")], locked_periods=set())
    assert ssp_summary(q1_only, base_results=q1_only)["risk_contribution_pct"].isna().all()

    q4_req = pd.concat([
        req,
        pd.DataFrame([
            request("a1", 4, 100, status="Виконано", rid=9),
            request("a2", 4, 100, status="Виконано", rid=10),
            request("b1", 4, 100, status="Виконано", rid=11),
            request("c1", 4, 100, status="Виконано", rid=12),
        ])
    ], ignore_index=True)
    q4_only = build_period_results(strat, q4_req, [(2026, "IV")], locked_periods=set())
    assert ssp_summary(q4_only, base_results=q4_only)["risk_contribution_pct"].isna().all()

    # If there is no total underperformance, contributions are missing rather than artificial zeroes.
    perfect_req = pd.DataFrame([
        request(code, 2, 100, status="Виконано", rid=i + 20)
        for i, code in enumerate(["a1", "a2", "b1", "c1"])
    ])
    perfect = build_period_results(strat, perfect_req, [(2026, "II")], locked_periods=set())
    perfect_summary = ssp_summary(perfect, base_results=perfect)
    assert perfect_summary["underperformance_contribution_pct"].isna().all()


def test_stage1_v3_matrix_requires_current_observation():
    """Carry-forward execution is not a new current-quarter trajectory observation."""
    from core.dashboard_breakdowns import build_period_results, execution_forecast_diagnostics, execution_forecast_matrix

    strat = pd.DataFrame([measure("matrix", 100)])
    stale_req = pd.DataFrame([request("matrix", 2, 50, rid=1)])
    stale_results = build_period_results(strat, stale_req, [(2026, "III")], locked_periods=set())
    stale = stale_results[(2026, "III")]["snapshot"]
    approx(stale.iloc[0]["execution_score"], 50)
    assert stale.iloc[0]["carry_forward_kind"] == "active_previous_result"
    assert execution_forecast_matrix(stale).empty
    stale_diag = execution_forecast_diagnostics(stale)
    assert stale_diag["numeric_current_count"] == 0
    assert stale_diag["numeric_with_previous_fact_count"] == 0
    assert stale_diag["numeric_forecast_count"] == 0

    current_req = pd.DataFrame([
        request("matrix", 2, 50, rid=1),
        request("matrix", 3, 70, rid=2),
    ])
    current_results = build_period_results(strat, current_req, [(2026, "III")], locked_periods=set())
    current = current_results[(2026, "III")]["snapshot"]
    matrix = execution_forecast_matrix(current)
    diag = execution_forecast_diagnostics(current)
    assert not matrix.empty
    assert diag["numeric_current_count"] == 1
    assert diag["numeric_with_previous_fact_count"] == 1
    assert diag["numeric_forecast_count"] == 1


def test_stage1_v3_dashboard_source_contracts():
    """Static cross-checks: page consumes shared v3 semantics without parallel formulas."""
    dashboard = (ROOT / "pages" / "2_Dashboard.py").read_text(encoding="utf-8")
    filters = (ROOT / "core" / "dashboard_filters.py").read_text(encoding="utf-8")
    execution = (ROOT / "core" / "dashboard_execution.py").read_text(encoding="utf-8")

    assert 'DASHBOARD_FORMULA_VERSION = "dashboard-execution-v3"' in execution
    assert 'expected_formula = DASHBOARD_FORMULA_VERSION' in dashboard
    assert 'expected_formula = "dashboard-execution-v2"' not in dashboard
    assert "dashboard-execution-v3" not in dashboard  # page must not duplicate the version literal

    # Base portfolio is built without SSP and display results are filtered afterwards.
    assert "base_period_results" in dashboard
    assert "_build_period_source_overrides(pairs, ssp_filter=None)" in dashboard
    assert "filter_results_by_ssp(base_period_results, selected_department_indices)" in dashboard
    assert "base_results=base_period_results" in dashboard

    # Main SSP options/organizational helpers no longer source coexecutors.
    options_block = dashboard[dashboard.index("department_indices_options = sorted("):dashboard.index("goal_options = sorted(")]
    assert '"main_ssp"' in options_block
    assert "resp_co_1" not in options_block and "resp_co_2" not in options_block
    get_depts = dashboard[dashboard.index("def get_all_department_values"):dashboard.index("def explode_departments")]
    assert "resp_co_1" not in get_depts and "resp_co_2" not in get_depts
    assert "resp_co_1" not in filters[filters.index("def measure_ssp_memberships"):filters.index("def filter_measures")]

    # Visible methodology reflects v3 carry-forward and main-only SSP semantics.
    assert "активні використовують тільки дані поточного кварталу" not in dashboard
    assert "Перенесений historical result не створює нового increment" in dashboard
    assert "кожен захід належить лише ССП — головному виконавцю" in dashboard

    # Existing local Apply/Reset and finance methodology remain present.
    for token in [
        "dash_snapshot_period_applied_v1", "dash_breakdown_period_applied_v1",
        "dash_dynamics_period_applied_v1", "dash_finance_period_applied_v1",
        "Застосувати загальні фільтри", "dashboard_finance_period_form_v1",
    ]:
        assert token in dashboard


def test_stage1_correction_q4_missing_submission_semantics():
    """Q4 stale carry stays missing_submission, not a fabricated final observation."""
    from core.dashboard_breakdowns import build_period_results
    from core.dashboard_risk import management_conclusion

    strat = pd.DataFrame([measure("q4-stale", 100)])
    req = pd.DataFrame([request("q4-stale", 3, 80, rid=1)])
    results = build_period_results(strat, req, [(2026, "IV")], locked_periods=set())
    item = results[(2026, "IV")]
    row = item["snapshot"].iloc[0]
    approx(row["execution_score"], 80)
    assert row["status"] == "Не подано"
    assert row["carry_forward_kind"] == "active_previous_result"
    assert row["missing_required_submission"]
    assert not row["submitted_current_period"]
    assert row["forecast_kind"] == "missing_submission"
    assert pd.isna(row["forecast_attainment_pct"])
    assert pd.isna(row["pace_sufficiency_pct"])
    assert pd.isna(row["current_increment"])
    assert pd.isna(row["final_outcome"])
    assert pd.isna(row["risk_level"])

    conclusion = management_conclusion(
        item["snapshot"],
        execution_by_measures=item["execution_by_measures"],
        execution_by_goals=item["execution_by_goals"],
        coverage=item["coverage"],
    )
    assert "актуальне подання за IV квартал відсутнє" in conclusion["explanation"]
    assert "останній підтверджений результат" in conclusion["explanation"]


def test_stage1_correction_operational_kpi_detail_contract():
    """Operational approved detail uses the same current-submission mask as the KPI count."""
    dashboard = (ROOT / "pages" / "2_Dashboard.py").read_text(encoding="utf-8")
    assert 'current_submitted_mask = active.get(' in dashboard
    assert '"submitted_current_period"' in dashboard
    assert 'submitted_count = int(current_submitted_mask.sum())' in dashboard

    start = dashboard.index('if data_source_mode == operational.MODE_OPERATIONAL:', dashboard.index('_selected_kpi = render_kpi_grid'))
    end = dashboard.index('_kpi_detail_frames = {', start)
    operational_detail_block = dashboard[start:end]
    assert '_approved_detail = active[current_submitted_mask].copy()' in operational_detail_block
    assert 'has_monitoring_data' not in operational_detail_block


def test_stage1_correction_canonical_ssp_ownership_across_range():
    """One code uses latest range ownership for all SSP/deputy multi-period aggregates."""
    from core import deputies as deputies_module
    from core.dashboard_breakdowns import (
        build_period_results, deputy_summary, filter_results_by_ssp,
        ssp_portfolio_weights, ssp_summary,
    )

    q1_strat = pd.DataFrame([{**measure("moving", 100), "resp_main": "ССП 1"}])
    q2_strat = pd.DataFrame([{**measure("moving", 100), "resp_main": "ССП 2"}])
    req = pd.DataFrame([
        request("moving", 1, 20, rid=1),
        request("moving", 2, 60, rid=2),
    ])
    period_sources = {
        (2026, "I"): {"strat_df": q1_strat, "requests_df": req, "locked_periods": set()},
        (2026, "II"): {"strat_df": q2_strat, "requests_df": req, "locked_periods": set()},
    }

    sentinel = object()
    old1 = deputies_module.DEPUTY_MINISTER_BY_SSP.get("1", sentinel)
    old2 = deputies_module.DEPUTY_MINISTER_BY_SSP.get("2", sentinel)
    deputies_module.DEPUTY_MINISTER_BY_SSP["1"] = "Deputy One"
    deputies_module.DEPUTY_MINISTER_BY_SSP["2"] = "Deputy Two"
    try:
        base = build_period_results(
            q2_strat, req, [(2026, "I"), (2026, "II")],
            locked_periods=set(), period_sources=period_sources,
        )
        weights = ssp_portfolio_weights(base)
        assert weights["ssp"].tolist() == ["2"]
        approx(weights.iloc[0]["portfolio_weight_pct"], 100)

        summary = ssp_summary(base, base_results=base)
        assert summary["ssp"].tolist() == ["2"]
        approx(summary.iloc[0]["average"], 40)
        assert not summary["portfolio_weight_pct"].isna().any()

        selected = filter_results_by_ssp(base, ["2"] )
        selected_summary = ssp_summary(selected, base_results=base)
        assert selected_summary["ssp"].tolist() == ["2"]
        approx(selected_summary.iloc[0]["average"], 40)
        for item in selected.values():
            assert set(item["snapshot"]["main_ssp"].dropna().astype(str)) == {"2"}

        deputies = deputy_summary(base)
        assert deputies["deputy"].tolist() == ["Deputy Two"]
        approx(deputies.iloc[0]["average"], 40)
    finally:
        if old1 is sentinel:
            deputies_module.DEPUTY_MINISTER_BY_SSP.pop("1", None)
        else:
            deputies_module.DEPUTY_MINISTER_BY_SSP["1"] = old1
        if old2 is sentinel:
            deputies_module.DEPUTY_MINISTER_BY_SSP.pop("2", None)
        else:
            deputies_module.DEPUTY_MINISTER_BY_SSP["2"] = old2


def test_stage1_correction_missing_data_insight_contract():
    """Current missing-data insight counts active missing submissions, not ended final-missing rows."""
    import ast
    dashboard_path = ROOT / "pages" / "2_Dashboard.py"
    dashboard = dashboard_path.read_text(encoding="utf-8")
    tree = ast.parse(dashboard)
    wanted = {"clean", "get_all_department_values", "explode_departments", "_missing_data_by_department"}
    defs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    env = {"pd": pd}
    exec(compile(ast.Module(body=defs, type_ignores=[]), str(dashboard_path), "exec"), env)

    active = pd.DataFrame([
        {
            "code": "active-stale", "department": "ССП 5", "status": "Не подано",
            "missing_required_submission": True, "final_missing_result": False,
        },
        {
            "code": "ended-none", "department": "ССП 8", "status": "Не подано",
            "missing_required_submission": False, "final_missing_result": True,
        },
    ])
    result = env["_missing_data_by_department"](active)
    assert result["Заходів_без_даних"].sum() == 1
    assert result["ssp_department"].tolist() == ["ССП 5"]

    block_start = dashboard.index("def _missing_data_by_department")
    block_end = dashboard.index("def _goal_quarter_drop_signals", block_start)
    block = dashboard[block_start:block_end]
    assert "missing_required_submission" in block
    assert 'departments["status"] == "Не подано"' not in block


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
        test_live_ui_data_regressions,
        test_feature_preservation_contracts,
        test_stage1_v3_active_carry_and_missing_semantics,
        test_stage1_v3_main_ssp_and_deputy_semantics,
        test_stage1_v3_ssp_weights_and_contributions,
        test_stage1_v3_matrix_requires_current_observation,
        test_stage1_v3_dashboard_source_contracts,
        test_stage1_correction_q4_missing_submission_semantics,
        test_stage1_correction_operational_kpi_detail_contract,
        test_stage1_correction_canonical_ssp_ownership_across_range,
        test_stage1_correction_missing_data_insight_contract,
        test_risk_thresholds,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"PASS {len(tests)} test groups")


if __name__ == "__main__":
    main()
