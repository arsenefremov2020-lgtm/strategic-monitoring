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
    assert "одним квартальним" in q1["forecast_explanation"]

    from core.dashboard_risk import yes_no_trajectory
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
    from core.dashboard_periods import current_reporting_period
    rows=[request("p",1,10,rid=1),request("p",2,20,rid=2)]
    inherited=request("p",3,"так",status="Виконано",rid=3); inherited["_auto_inherited"]=True
    df=pd.DataFrame([*rows,inherited])
    assert current_reporting_period(df,locked_periods=set()) == (2026,"II")
    assert current_reporting_period(df,locked_periods={("2026",2)}) == (2026,"I")


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
    assert "Оцінка через виконання завдань стратегічної цілі." in app
    assert "Розрахунок виконання — станом на" in app
    assert "Застосувати фільтри" in app and "Застосувати фільтри" in dashboard
    assert "Стан виконання" in dashboard and "Порівняння результатів" in dashboard and "Динаміка виконання" in dashboard and "Фінансування" in dashboard
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

    snap = pd.DataFrame([{**measure("fin", 100), "execution_score": 50.0, "budget_2026_approved": 2.0}])
    fin = build_finance_frame(
        snap, 2026,
        fin_index={("fin", "2026"): {"kpkvk": "1201010", "other_source": "", "plan_bln": 2.0, "fact_bln": 1.0}},
    )
    assert len(fin) == 1
    approx(fin.iloc[0]["financial_execution_pct"], 50)
    kpis = finance_kpis(fin)
    approx(kpis["financial_execution_pct"], 50)


def test_management_conclusion_thresholds():
    from core.dashboard_risk import management_conclusion
    def frame(q, risks):
        return pd.DataFrame([
            {"quarter":q, "execution_score":80, "result_achieved":False,
             "risk_level":risk, "forecast_attainment_pct":80, "pace_sufficiency_pct":90}
            for risk in risks
        ])
    q1 = management_conclusion(frame("I", ["Низький ризик"]), execution_by_measures=40, execution_by_goals=45, coverage=90)
    assert q1["title"] == "Початковий стан реалізації"
    controlled = management_conclusion(frame("II", ["Низький ризик"]*9+["Високий ризик"]), execution_by_measures=70, execution_by_goals=72, coverage=90)
    assert controlled["severity"] == "low"
    attention = management_conclusion(frame("III", ["Низький ризик"]*7+["Високий ризик"]*3), execution_by_measures=70, execution_by_goals=72, coverage=90)
    assert attention["severity"] == "medium"
    severe = management_conclusion(frame("III", ["Низький ризик"]*5+["Критичний ризик"]*5), execution_by_measures=70, execution_by_goals=72, coverage=90)
    assert severe["severity"] == "high"
    q4f = frame("IV", [None]*10); q4f.loc[:7,"result_achieved"] = True
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
    assert "indicator_row_matches_search" in app and "row_matches_search" in app
    assert "render_scope_toggle(\"app\"" in app
    # Old management formulas/terminology are gone from the page.
    forbidden = ["risk_probability", "risk_score_calc", "traffic_light", "expected_completion_for_quarter", "deviation_for_period", "Прогнозована вірогідність"]
    for token in forbidden:
        assert token not in dashboard, token



def test_archive_source_override_and_system_nonmonitoring():
    from core.dashboard_breakdowns import build_period_results
    from core.dashboard_periods import monitoring_conducted

    # Production semantics preserve the historical no-monitoring periods.
    assert monitoring_conducted(2026, "I") is False
    assert monitoring_conducted(2026, "II") is False

    # Archive inputs are recalculated with the same v2 core and are also used
    # for the immediate previous-quarter trajectory observation.
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
        test_archive_source_override_and_system_nonmonitoring,
        test_review_methodology_edge_cases,
        test_locked_observation_excluded_from_future_risk_history,
        test_stable_cohort_previous_current_consistency,
        test_multi_period_group_summaries_and_matrix,
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
