"""Behavioral Stage 3 regression checks for Analytics parity with Dashboard v3."""
from __future__ import annotations

import ast
import math
import sys
import types
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "streamlit" not in sys.modules:
    st_stub = types.ModuleType("streamlit")
    st_stub.session_state = {}
    st_stub.secrets = {}
    st_stub.cache_resource = lambda *a, **k: (lambda fn: fn)
    st_stub.cache_data = lambda *a, **k: (lambda fn: fn)
    st_stub.warning = lambda *a, **k: None
    st_stub.error = lambda *a, **k: None
    sys.modules["streamlit"] = st_stub
if "supabase" not in sys.modules:
    supabase_stub = types.ModuleType("supabase")
    supabase_stub.create_client = lambda *a, **k: None
    sys.modules["supabase"] = supabase_stub

from core import operational, periods as core_periods
from core.dashboard_breakdowns import (
    build_period_results, aggregate_plan, aggregate_objects, dynamics_frame,
    ssp_summary, deputy_summary, filter_results_by_ssp,
)
from core.dashboard_execution import score_measure, plan_scores
from core.dashboard_risk import attention_mask, risk_summary

ANALYTICS = ROOT / "pages" / "7_Аналітика.py"
SRC = ANALYTICS.read_text(encoding="utf-8")
TREE = ast.parse(SRC)


def _function(name: str) -> ast.FunctionDef:
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function {name}")


def _load_functions(*names):
    nodes = [node for node in TREE.body if isinstance(node, ast.FunctionDef)]
    module = ast.Module(body=nodes, type_ignores=[])
    ns = {
        "pd": pd, "build_period_results": build_period_results, "attention_mask": attention_mask,
        "aggregate_plan": aggregate_plan, "aggregate_objects": aggregate_objects,
        "dynamics_frame": dynamics_frame, "ssp_summary": ssp_summary, "deputy_summary": deputy_summary,
        "filter_results_by_ssp": filter_results_by_ssp, "plan_scores": plan_scores,
        "risk_summary": risk_summary, "DEPUTY_MINISTER_BY_SSP": {}, "core_periods": core_periods, "escape": lambda v: v, "raw_value": lambda v: "" if v is None else str(v).strip(),
    }
    exec(compile(ast.fix_missing_locations(module), str(ANALYTICS), "exec"), ns)
    return [ns[name] for name in names]


def measure(code, target=100, start="I квартал 2026", end="IV квартал 2026", task="1.1", goal="1"):
    return {
        "object_type": "measure", "code": code, "name": code,
        "target_2026": target, "measure_start_date": start, "measure_end_date": end,
        "parent_task_code": task, "parent_task_name": task,
        "parent_goal_code": goal, "parent_goal_name": goal,
        "resp_main": "ССП 5", "resp_co_1": "", "resp_co_2": "",
        "product_type": "Продукт",
    }


def request(code, quarter, value, status="Частково виконано", year=2026, rid=1):
    return {
        "id": rid, "strat_code": code, "year": year, "quarter": quarter,
        "status": status, "approval_status": "Погоджено", "object_kind": "measure",
        "numeric_value": value if isinstance(value, (int, float)) else None,
        "value_text": value if isinstance(value, str) else None,
        "submitted_at": f"{year}-01-01T00:00:00Z", "updated_at": f"{year}-01-01T00:00:00Z",
    }


def approx(actual, expected, tol=0.02):
    assert actual is not None and not pd.isna(actual), (actual, expected)
    assert math.isclose(float(actual), float(expected), abs_tol=tol), (actual, expected)


def test_super_admin_only_guard_is_early():
    assert "from core.access import is_super_admin_user" in SRC
    setup_pos = SRC.index('current_user = page_setup("Аналітика"')
    guard_pos = SRC.index("if not is_super_admin_user(current_user):")
    db_pos = SRC.index("supabase = get_supabase_client()")
    load_pos = SRC.index("strat_df = load_strat_matrix()")
    assert setup_pos < guard_pos < db_pos < load_pos
    guard_tail = SRC[guard_pos:db_pos]
    assert "st.stop()" in guard_tail
    assert "filter_requests_for_user" not in SRC and "filter_actions_for_user" not in SRC


def test_canonical_period_results_and_no_legacy_metrics():
    fn = ast.unparse(_function("prepare_analysis_context"))
    assert "build_period_results" in fn
    assert "prepare_period_slice" not in SRC
    assert "dashboard_metrics" not in SRC
    for legacy in ("performance_score", "expected_progress", "period_deviation"):
        assert legacy not in SRC


def test_attention_uses_canonical_risk_mask():
    fn = ast.unparse(_function("_snapshot_rows_from_period_results"))
    assert "attention_mask" in fn
    assert "is_problem_status" in fn


def test_synthetic_111_q3_q4():
    strat = pd.DataFrame([measure("1.1.1.", 2)])
    req = pd.DataFrame([
        request("1.1.1.", 1, 0.2, rid=1), request("1.1.1.", 2, 0.6, rid=2),
        request("1.1.1.", 3, 1.0, rid=3), request("1.1.1.", 4, 2.0, status="Виконано", rid=4),
    ])
    out = build_period_results(strat, req, [(2026, "III"), (2026, "IV")], locked_periods=set())
    q3 = out[(2026, "III")]["snapshot"].iloc[0]
    approx(q3["actual"], 1.0); approx(q3["execution_score"], 50.0)
    assert not q3["management_zero_due_to_missing_data"]
    q4 = out[(2026, "IV")]["snapshot"].iloc[0]
    approx(q4["actual"], 2.0); approx(q4["execution_score"], 100.0)
    assert bool(q4["result_achieved"])


def test_carry_forward_preserves_missing_submission_coverage_semantics():
    strat = pd.DataFrame([measure("m", 100)])
    req = pd.DataFrame([request("m", 1, 40, rid=1)])
    q2 = build_period_results(strat, req, [(2026, "II")], locked_periods=set())[(2026, "II")]["snapshot"].iloc[0]
    approx(q2["actual"], 40); assert q2["carry_forward"]
    assert not q2["submitted_current_period"] and q2["missing_required_submission"]
    assert q2["coverage_eligible"]


def test_no_lookahead():
    strat = pd.DataFrame([measure("m", 100)])
    req = pd.DataFrame([request("m", 1, 40, rid=1), request("m", 3, 90, rid=3)])
    q2 = build_period_results(strat, req, [(2026, "II")], locked_periods=set())[(2026, "II")]["snapshot"].iloc[0]
    approx(q2["actual"], 40)
    assert q2["source_quarter"] == "I"


def test_valid_zero_variants_are_not_missing():
    for i, value in enumerate((0, 0.0, "0"), start=1):
        strat = pd.DataFrame([measure(f"z{i}", 10)])
        req = pd.DataFrame([request(f"z{i}", 2, value, rid=i)])
        row = build_period_results(strat, req, [(2026, "II")], locked_periods=set())[(2026, "II")]["snapshot"].iloc[0]
        assert row["submitted_current_period"]
        assert not row["management_zero_due_to_missing_data"]
        approx(row["execution_score"], 0)


def test_management_zero_is_canonical_field():
    strat = pd.DataFrame([measure("missing", 10)])
    row = build_period_results(strat, pd.DataFrame(), [(2026, "II")], locked_periods=set())[(2026, "II")]["snapshot"].iloc[0]
    assert row["management_zero_due_to_missing_data"]
    approx(row["execution_score"], 0)


def test_future_and_no_monitoring_are_not_fake_zero():
    strat = pd.DataFrame([measure("locked", 100)])
    row = build_period_results(strat, pd.DataFrame(), [(2026, "II")], locked_periods={("2026", 2)})[(2026, "II")]["snapshot"].iloc[0]
    assert pd.isna(row["execution_score"]) and not row["monitoring_conducted"]
    future = pd.DataFrame([measure("future", 100, start="I квартал 2027", end="IV квартал 2027")])
    snap = build_period_results(future, pd.DataFrame(), [(2026, "II")], locked_periods=set())[(2026, "II")]["snapshot"]
    assert snap.empty


def test_overachievement_raw_vs_management_score():
    scored = score_measure("Виконано", 2.5, 2)
    approx(scored["raw_attainment_pct"], 125)
    approx(scored["execution_score"], 100)
    assert scored["result_achieved"]


def test_qualitative_and_yes_no_canonical_scores():
    cases = [
        ("Виконано", "Так", "Так", 100), ("Не виконано", "Ні", "Так", 0),
        ("Виконано", None, None, 100), ("Частково виконано", None, None, 75),
        ("Не виконано", None, None, 0),
    ]
    for status, actual, target, expected in cases:
        approx(score_measure(status, actual, target)["execution_score"], expected)


def test_aggregation_uses_canonical_eligibility_and_denominators():
    build_metrics = _load_functions("build_metrics")[0]
    df = pd.DataFrame([
        {"code":"a","goal_code":"1","task_code":"1.1","execution_score":80,"included_in_assessment":True,"assessed":True,"coverage_eligible":True,"submitted":True,"missing_required_submission":False,"is_problem_status":False,"result_achieved":False},
        {"code":"b","goal_code":"1","task_code":"1.1","execution_score":None,"included_in_assessment":False,"assessed":False,"coverage_eligible":False,"submitted":False,"missing_required_submission":False,"is_problem_status":False,"result_achieved":False},
        {"code":"c","goal_code":"1","task_code":"1.1","execution_score":0,"included_in_assessment":True,"assessed":True,"coverage_eligible":True,"submitted":False,"missing_required_submission":True,"is_problem_status":True,"result_achieved":False},
        {"code":"d","goal_code":"1","task_code":"1.1","execution_score":75,"included_in_assessment":True,"assessed":True,"coverage_eligible":True,"submitted":True,"missing_required_submission":False,"is_problem_status":False,"result_achieved":False},
    ])
    m=build_metrics(df)
    assert m["completion"] is None and m["coverage"] is None
    assert m["problem"]==1 and m["no_data"]==1
    assert m["unique_measures"]==4 and m["submitted"]==2


def test_multi_period_analytics_adapter_uses_period_average_not_row_weighted_mean():
    plan_adapter = _load_functions("build_analytics_plan_summary")[0]
    strat = pd.DataFrame([
        measure("a",100),
        measure("b",100,start="II квартал 2026"),
    ])
    req = pd.DataFrame([request("a",1,100,rid=1), request("a",2,0,rid=2), request("b",2,0,rid=3)])
    results=build_period_results(strat,req,[(2026,"I"),(2026,"II")],locked_periods=set())
    analytics=plan_adapter(results); shared=aggregate_plan(results)
    approx(analytics["execution_by_measures_average"], shared["execution_by_measures_average"])
    approx(analytics["execution_by_measures_average"], 50.0)
    rows=pd.concat([r["snapshot"] for r in results.values()],ignore_index=True)
    row_mean=pd.to_numeric(rows["execution_score"],errors="coerce").dropna().mean()
    approx(row_mean, 100/3)
    assert not math.isclose(row_mean, analytics["execution_by_measures_average"], abs_tol=.02)


def test_goal_hierarchy_uses_tasks_not_direct_measure_mean():
    goal_adapter, rows_adapter = _load_functions("build_analytics_goal_summary","_snapshot_rows_from_period_results")
    strat=pd.DataFrame([
        measure("1.1.1",100,task="1.1",goal="1"),
        measure("1.2.1",100,task="1.2",goal="1"),
        measure("1.2.2",100,task="1.2",goal="1"),
        measure("1.2.3",100,task="1.2",goal="1"),
    ])
    req=pd.DataFrame([
        request("1.1.1",1,100,rid=1), request("1.2.1",1,0,rid=2),
        request("1.2.2",1,0,rid=3), request("1.2.3",1,0,rid=4),
        request("1.1.1",2,80,rid=5), request("1.2.1",2,0,rid=6),
        request("1.2.2",2,0,rid=7), request("1.2.3",2,0,rid=8),
    ])
    results=build_period_results(strat,req,[(2026,"I"),(2026,"II")],locked_periods=set())
    active=rows_adapter(results)
    analytics=goal_adapter(results,active)
    shared=aggregate_objects(results,object_type="goal")
    row=analytics.iloc[0]; canon=shared.iloc[0]
    # Q1 proves the known bug: direct measures=25, canonical hierarchy via tasks=50.
    q1=results[(2026,"I")]["goal_scores"].iloc[0]
    approx(q1["by_measures"],25.0); approx(q1["by_tasks"],50.0)
    approx(row["Виконання"], canon["average_by_tasks"])
    approx(row["Останнє_виконання"], canon["latest_by_tasks"])
    approx(row["Зміна"], canon["change_by_tasks"])
    assert not math.isclose(float(row["Виконання"]), float(canon["average_by_measures"]), abs_tol=.02)


def test_task_hierarchy_adapter_matches_shared_average_latest_change():
    task_adapter, rows_adapter = _load_functions("build_analytics_task_summary","_snapshot_rows_from_period_results")
    strat=pd.DataFrame([
        measure("1.1.1",100,task="1.1",goal="1"),
        measure("1.2.1",100,task="1.2",goal="1"),
        measure("1.2.2",100,task="1.2",goal="1"),
    ])
    req=pd.DataFrame([
        request("1.1.1",1,100,rid=1),request("1.2.1",1,0,rid=2),request("1.2.2",1,0,rid=3),
        request("1.1.1",2,50,rid=4),request("1.2.1",2,50,rid=5),request("1.2.2",2,50,rid=6),
    ])
    results=build_period_results(strat,req,[(2026,"I"),(2026,"II")],locked_periods=set()); active=rows_adapter(results)
    aa=task_adapter(results,active); ss=aggregate_objects(results,object_type="task")
    merged=aa.merge(ss,on=["task_code","task_name"],suffixes=("_a","_s"))
    for _,r in merged.iterrows():
        approx(r["Виконання"],r["average_execution"])
        approx(r["Останнє_виконання"],r["latest_execution"])
        approx(r["Зміна"],r["change_execution"])


def test_ssp_parity_without_filter_and_selected_filter_preserves_base_denominator():
    context_adapter, ssp_adapter, rows_adapter = _load_functions(
        "build_analytics_result_context","build_analytics_ssp_summary","_snapshot_rows_from_period_results"
    )
    strat=pd.DataFrame([measure("a",100),measure("b",100),measure("c",100),measure("d",100)])
    strat.loc[0:1,"resp_main"]="ССП 10"; strat.loc[2:3,"resp_main"]="ССП 20"
    req=pd.DataFrame([request(c,2,50,rid=i+1) for i,c in enumerate(["a","b","c","d"])])
    results=build_period_results(strat,req,[(2026,"II")],locked_periods=set())

    base, display=context_adapter(results,[],[],[],[],[])
    active=rows_adapter(display)
    aa=ssp_adapter(display,active,base_results=base); ss=ssp_summary(base)
    merged=aa.merge(ss,left_on="ssp_index",right_on="ssp",suffixes=("_a","_s"))
    for _,r in merged.iterrows():
        approx(r["portfolio_weight_pct_a"],r["portfolio_weight_pct_s"])

    base, selected=context_adapter(results,["10"],[],[],[],[])
    active=rows_adapter(selected)
    aa=ssp_adapter(selected,active,base_results=base)
    assert len(aa)==1
    approx(aa.iloc[0]["portfolio_weight_pct"],50.0)
    assert not math.isclose(float(aa.iloc[0]["portfolio_weight_pct"]),100.0,abs_tol=.02)


def test_deputy_and_dynamics_adapters_match_shared_outputs():
    deputy_adapter, dyn_adapter = _load_functions("build_analytics_deputy_summary","build_analytics_dynamics")
    strat=pd.DataFrame([measure("a",100),measure("b",100)])
    strat.loc[1,"resp_main"]="ССП 6"
    req=pd.DataFrame([request("a",1,100,rid=1),request("b",1,0,rid=2),request("a",2,50,rid=3),request("b",2,50,rid=4)])
    results=build_period_results(strat,req,[(2026,"I"),(2026,"II")],locked_periods=set())
    pd.testing.assert_frame_equal(
        deputy_adapter(results).reset_index(drop=True),
        deputy_summary(results).reset_index(drop=True),
        check_dtype=False,
    )
    ad=dyn_adapter(results); sd=dynamics_frame(results)
    for series,col in [("Виконання за заходами","Виконання")]:
        shared=sd[sd["series"]==series].sort_values(["year","quarter"])["value"].tolist()
        analytics=ad.sort_values(["report_year","report_quarter_num"])[col].tolist()
        assert analytics==shared


def test_static_closure_audit():
    forbidden=[
        "Гнучкий розрахунок відсотка виконання","Виконання за обраною базою",
        "expected_progress","period_deviation","Оцінка темпу","performance_score",
        "if completion >= 70","elif completion >= 40","None%","nan%","NaN%",
    ]
    for token in forbidden: assert token not in SRC, token
    goal_fn=ast.unparse(_function("build_analytics_goal_summary"))
    assert "average_by_tasks" in goal_fn and "latest_by_tasks" in goal_fn and "change_by_tasks" in goal_fn
    ssp_fn=ast.unparse(_function("build_analytics_ssp_summary"))
    assert "base_results=" in ssp_fn


def test_flexible_execution_removed_and_risk_wording_is_canonical():
    assert "Гнучкий розрахунок відсотка виконання" not in SRC
    assert "Виконання за обраною базою" not in SRC
    assert "Оцінка темпу" not in SRC
    assert '"risk_level": "Рівень ризику"' in SRC


def test_no_value_percentage_formatter():
    fmt=_load_functions("format_pct")[0]
    assert fmt(None)=="—" and fmt(float("nan"))=="—"
    assert fmt(50.0)=="50%" and fmt(50.5)=="50.5%"


def test_narrative_has_no_deprecated_pace_and_handles_missing_metrics():
    assert "очікуваний квартальний темп" not in SRC.lower()
    assert "відхилення від очікуваного" not in SRC.lower()
    assert "випередження квартального" not in SRC.lower()
    assert "відставання від очікуваного" not in SRC.lower()
    assert 'metrics["expected"]' not in SRC and 'metrics["deviation"]' not in SRC


def test_source_mode_uses_existing_operational_helper_without_mutating_confirmed():
    assert "operational.apply_operational_mode" in SRC and "operational.MODE_OPTIONS" in SRC
    original = pd.DataFrame([request("m", 2, 10)])
    before = original.copy(deep=True)
    # Empty target map is sufficient to assert helper isolation: input must not be mutated.
    empty_logs = pd.DataFrame(columns=["request_id", "action", "old_status", "new_status", "changed_at", "actor_role", "related_table"])
    operational.apply_operational_mode(original, {}, logs_df=empty_logs, versions_df=pd.DataFrame())
    pd.testing.assert_frame_equal(original, before)


def test_cross_surface_parity_is_real_analytics_adapter():
    plan_adapter = _load_functions("build_analytics_plan_summary")[0]
    strat = pd.DataFrame([measure("m", 100)])
    req = pd.DataFrame([request("m", 1, 25), request("m", 2, 50, rid=2)])
    results=build_period_results(strat,req,[(2026,"I"),(2026,"II")],locked_periods=set())
    analytics=plan_adapter(results); shared=aggregate_plan(results)
    for field in ("execution_by_measures_average","execution_by_measures_latest","coverage_average"):
        approx(analytics[field],shared[field])


def test_selected_periods_are_explicit_pairs():
    fn = ast.unparse(_function("prepare_analysis_context"))
    assert 'pairs = [(int(year), quarter)' in fn



def test_ssp_coverage_column_collision_and_plot_contract():
    context_adapter, ssp_adapter, rows_adapter = _load_functions(
        "build_analytics_result_context","build_analytics_ssp_summary","_snapshot_rows_from_period_results"
    )
    strat=pd.DataFrame([measure("a",100),measure("b",100)])
    strat.loc[0,"resp_main"]="ССП 10"; strat.loc[1,"resp_main"]="ССП 20"
    req=pd.DataFrame([request("a",2,50,rid=1),request("b",2,50,rid=2)])
    results=build_period_results(strat,req,[(2026,"II")],locked_periods=set())
    base,display=context_adapter(results,[],[],[],[],[])
    active=rows_adapter(display)
    result=ssp_adapter(display,active,base_results=base)
    assert list(result.columns).count("Покриття_%")==1
    assert "Покриття_%_x" not in result.columns and "Покриття_%_y" not in result.columns
    shared=ssp_summary(display,base_results=base)
    merged=result.merge(shared,left_on="ssp_index",right_on="ssp")
    for _,row in merged.iterrows():
        approx(row["Покриття_%"],row["average_coverage"])
    required={"ssp_index","department","deputy_minister","Унікальних_заходів","Покриття_%","Проблемних","Без_даних","Виконання"}
    assert required <= set(result.columns), required-set(result.columns)


def test_product_multi_period_coverage_uses_period_average_not_row_weighted():
    product_adapter, rows_adapter = _load_functions("aggregate_product_progress","_snapshot_rows_from_period_results")
    strat=pd.DataFrame([
        measure("a",100,start="I квартал 2026",end="I квартал 2026"),
        measure("b",100,start="II квартал 2026"),
        measure("c",100,start="II квартал 2026"),
        measure("d",100,start="II квартал 2026"),
    ])
    req=pd.DataFrame([request("a",1,100,rid=1)])
    results=build_period_results(strat,req,[(2026,"I"),(2026,"II")],locked_periods=set())
    active=rows_adapter(results)
    result=product_adapter(results,active)
    approx(results[(2026,"I")]["coverage"],100.0); approx(results[(2026,"II")]["coverage"],0.0)
    approx(result.iloc[0]["Покриття_%"],50.0)
    coverage_pop=active[active["coverage_eligible"].fillna(False).astype(bool)]
    row_weighted=coverage_pop["submitted"].fillna(False).astype(bool).mean()*100
    approx(row_weighted,25.0)
    assert not math.isclose(float(result.iloc[0]["Покриття_%"]),row_weighted,abs_tol=.02)


def test_goal_task_multi_period_coverage_uses_canonical_period_scores():
    goal_adapter,task_adapter,rows_adapter = _load_functions(
        "build_analytics_goal_summary","build_analytics_task_summary","_snapshot_rows_from_period_results"
    )
    strat=pd.DataFrame([
        measure("a",100,start="I квартал 2026",end="I квартал 2026",task="1.1",goal="1"),
        measure("b",100,start="II квартал 2026",task="1.1",goal="1"),
        measure("c",100,start="II квартал 2026",task="1.1",goal="1"),
        measure("d",100,start="II квартал 2026",task="1.1",goal="1"),
    ])
    req=pd.DataFrame([request("a",1,100,rid=1)])
    results=build_period_results(strat,req,[(2026,"I"),(2026,"II")],locked_periods=set())
    active=rows_adapter(results)
    goal=goal_adapter(results,active); task=task_adapter(results,active)
    approx(goal.iloc[0]["Покриття_%"],50.0)
    approx(task.iloc[0]["Покриття_%"],50.0)


def test_detail_counts_is_descriptive_only():
    detail=_load_functions("_detail_counts")[0]
    df=pd.DataFrame([
        {"code":"a","group":"x","coverage_eligible":True,"submitted":True,"missing_required_submission":False,"is_problem_status":False},
        {"code":"b","group":"x","coverage_eligible":True,"submitted":False,"missing_required_submission":True,"is_problem_status":True},
    ])
    result=detail(df,["group"])
    assert "Покриття_%" not in result.columns
    assert "Виконання" not in result.columns
    assert {"Унікальних_заходів","Проблемних","Без_даних","Подано"} <= set(result.columns)


def test_registry_is_intersection_of_selected_period_and_active_cohort():
    registry_filter=_load_functions("filter_period_requests_to_active_cohort")[0]
    active=pd.DataFrame([{"code":"1.1.1"}])
    requests=pd.DataFrame([
        {"strat_code":"1.1.1","year":2026,"quarter":"II","value":"goal1"},
        {"strat_code":"2.1.1","year":2026,"quarter":"II","value":"goal2"},
        {"strat_code":"1.1.1","year":2026,"quarter":"I","value":"wrong period"},
    ])
    registry=registry_filter(requests,active,[2026],["II"])
    assert set(registry["strat_code"])=={"1.1.1"}
    assert set(registry["strat_code"]) <= set(active["code"])


def test_registry_combined_context_subset_contract():
    registry_filter=_load_functions("filter_period_requests_to_active_cohort")[0]
    # active already represents the canonical Goal+Task+Product+Deputy+SSP calculation cohort.
    active=pd.DataFrame([{"code":"1.1.2"},{"code":"1.1.3"}])
    requests=pd.DataFrame([
        {"strat_code":"1.1.2","year":2026,"quarter":"III"},
        {"strat_code":"1.1.3","year":2026,"quarter":"III"},
        {"strat_code":"1.2.1","year":2026,"quarter":"III"},
        {"strat_code":"2.1.1","year":2026,"quarter":"III"},
    ])
    registry=registry_filter(requests,active,[2026],["III"])
    assert set(registry["strat_code"]) <= set(active["code"])
    assert set(registry["strat_code"])=={"1.1.2","1.1.3"}


def test_registry_ui_excel_share_same_filtered_dataframe_source():
    assert "period_requests = filter_period_requests_to_active_cohort(" in SRC
    # UI may rename headers presentation-only, but must derive from the same filtered dataframe.
    assert '"Реєстр заявок": period_requests' in SRC
    assert "registry_display = period_requests.rename(" in SRC
    assert "render_readonly_table(" in SRC and "registry_display," in SRC
    assert "workflow_requests = period_requests.copy()" in SRC



def test_check_tables_use_ukrainian_presentation_and_two_digit_formatting():
    assert "def format_number_2" in SRC
    assert '"goal_code": "Код стратегічної цілі"' in SRC
    assert '"task_code": "Код завдання"' in SRC
    assert '"ssp_index": "ССП"' in SRC
    assert '"product_type": "Тип продукту"' in SRC
    assert '"object_name": "Назва заходу"' in SRC
    assert '"indicator_name": "Індикатор"' in SRC
    assert 'goal_chart[_column] = pd.to_numeric(goal_chart[_column], errors="coerce").round(2)' in SRC


def test_build_metrics_has_no_dead_execution_or_coverage_formula():
    fn=ast.unparse(_function("build_metrics"))
    assert "execution_score" not in fn
    assert ".mean()" not in fn
    assert "execution_score" not in fn and "coverage_pop" not in fn and "assessed =" not in fn

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for test in tests:
        test(); passed += 1; print(f"PASS {test.__name__}")
    print(f"Analytics: {passed}/{len(tests)} PASS")
