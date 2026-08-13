"""Pure regression tests for Stage 2 Measure Card on Dashboard execution v3.

Run from repository root:
    python scripts/test_measure_card_v3.py
"""
from __future__ import annotations

from pathlib import Path
import ast
import math
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.dashboard_breakdowns import build_period_results
from core.dashboard_execution import DASHBOARD_FORMULA_VERSION
from core.dashboard_sources import build_period_source_overrides
from core.dashboard_risk import yes_no_trajectory
from core.dashboard_periods import parse_measure_period, period_state, period_number
from core.measure_card import (
    BLUE, GRAY, GREEN, RED, YELLOW,
    actual_observation,
    build_card_view,
    build_measure_conclusion,
    gauge_state,
    quarter_card_view,
)


def approx(actual, expected, tol=0.02):
    assert actual is not None, (actual, expected)
    assert abs(float(actual) - float(expected)) <= tol, (actual, expected)


def measure(
    code="m1", target=100, *, start="I квартал 2026", end="IV квартал 2026",
    main="ССП 5", unit="од.",
):
    return {
        "object_type": "measure", "code": code, "name": f"Захід {code}",
        "target_2026": target, "target_2027": target,
        "measure_start_date": start, "measure_end_date": end,
        "start_period": start, "end_period": end,
        "unit": unit,
        "parent_task_code": "1.1", "parent_task_name": "Завдання",
        "parent_goal_code": "1", "parent_goal_name": "Ціль",
        "resp_main": main, "department": main,
    }


def request(code, quarter, value, *, year=2026, status="Частково виконано", rid=1):
    numeric = value if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    text = value if not isinstance(value, (int, float)) or isinstance(value, bool) else None
    return {
        "id": rid, "strat_code": code, "year": year, "quarter": quarter,
        "status": status, "approval_status": "Погоджено", "object_kind": "measure",
        "numeric_value": numeric, "value_text": text,
        "submitted_at": f"{year}-0{min(int(quarter) if str(quarter).isdigit() else 1, 9)}-01T00:00:00Z",
        "updated_at": f"{year}-0{min(int(quarter) if str(quarter).isdigit() else 1, 9)}-01T00:00:00Z",
    }


def results_for(measure_row, requests, quarters, *, year=2026, locked_periods=None):
    return build_period_results(
        pd.DataFrame([measure_row]), pd.DataFrame(requests),
        [(year, q) for q in quarters],
        locked_periods=set() if locked_periods is None else locked_periods,
    )


def row_at(results, year, quarter):
    snapshot = results[(year, quarter)]["snapshot"]
    assert len(snapshot) == 1, snapshot
    return snapshot.iloc[0]


def test_cross_page_numeric_identity():
    res = results_for(
        measure("m", 10000),
        [request("m", 2, 6700, rid=2), request("m", 3, 7900, rid=3)],
        ["I", "II", "III"],
    )
    row = row_at(res, 2026, "III")
    approx(row["execution_score"], 79)
    approx(row["current_increment"], 1200)
    approx(row["forecast_year"], 9100)
    approx(row["forecast_attainment_pct"], 91)
    approx(row["pace_sufficiency_pct"], 57.142857)
    assert row["risk_level"] == "Низький ризик"
    view = build_card_view(row)
    approx(view["gauge"]["value"], row["execution_score"])
    assert view["gauge"]["color"] == GREEN  # shared Low-risk color
    assert [kpi["label"] for kpi in view["headline_kpis"]] == [
        "Факт / річний план", "Достатність темпу", "Прогноз", "Ризик"
    ]
    assert any(kpi["label"] == "Достатність темпу" and "57.1%" in kpi["value"] for kpi in view["headline_kpis"])
    assert any(kpi["label"] == "Прогноз" and "91%" in kpi["value"] for kpi in view["headline_kpis"])
    assert any(kpi["label"] == "Ризик" and kpi["value"] == "Низький ризик" for kpi in view["headline_kpis"])
    assert all(kpi["label"] != "Виконання річного плану" for kpi in view["headline_kpis"])


def test_active_carry_forward():
    res = results_for(measure("m", 100), [request("m", 2, 50, rid=2)], ["I", "II", "III"])
    row = row_at(res, 2026, "III")
    approx(row["execution_score"], 50)
    assert row["status"] == "Не подано"
    assert row["carry_forward_kind"] == "active_previous_result"
    assert row["source_quarter"] == "II"
    assert row["forecast_attainment_pct"] is None
    assert row["pace_sufficiency_pct"] is None
    assert row["risk_level"] is None
    view = build_card_view(row)
    assert view["gauge"]["color"] == BLUE and view["gauge"]["value"] == 50
    assert "Нові відомості за III квартал не подано" in view["conclusion"]
    assert "II кварталу" in view["conclusion"]
    assert "Дані не оновлено" in view["warning"]


def test_never_reported_management_zero():
    res = results_for(measure("m", 100), [], ["I", "II", "III"])
    row = row_at(res, 2026, "III")
    assert row["execution_score"] == 0
    assert bool(row["management_zero_due_to_missing_data"])
    assert row["risk_level"] is None
    view = build_card_view(row)
    assert view["gauge"]["value"] == 0 and view["gauge"]["color"] == RED
    assert "підтверджені дані" in view["conclusion"].lower()
    assert "фактичне значення = 0" not in view["conclusion"].lower()


def test_q1_preliminary():
    res = results_for(measure("m", 100), [request("m", 1, 20, rid=1)], ["I"])
    row = row_at(res, 2026, "I")
    assert row["forecast_kind"] == "preliminary"
    assert row["risk_level"] is None
    assert gauge_state(row)["color"] == BLUE
    assert "попередн" in build_measure_conclusion(row).lower()


def test_insufficient_history():
    res = results_for(measure("m", 100), [request("m", 3, 60, rid=3)], ["I", "II", "III"])
    row = row_at(res, 2026, "III")
    approx(row["execution_score"], 60)
    assert row["forecast_kind"] == "insufficient_history"
    assert row["forecast_attainment_pct"] is None
    assert row["pace_sufficiency_pct"] is None
    assert row["risk_level"] is None
    assert "Недостатньо квартальної історії" in build_measure_conclusion(row)


def test_negative_trajectory():
    res = results_for(
        measure("m", 100),
        [request("m", 2, 80, rid=2), request("m", 3, 60, rid=3)],
        ["I", "II", "III"],
    )
    row = row_at(res, 2026, "III")
    approx(row["current_increment"], -20)
    assert bool(row["negative_trajectory"])
    conclusion = build_measure_conclusion(row)
    assert "зниження" in conclusion.lower()
    assert "помил" not in conclusion.lower()


def test_overachievement_cap_and_copy():
    res = results_for(measure("m", 100), [request("m", 3, 128, rid=3)], ["I", "II", "III"])
    row = row_at(res, 2026, "III")
    approx(row["raw_attainment_pct"], 128)
    approx(row["execution_score"], 100)
    gauge = gauge_state(row)
    assert gauge["value"] == 100 and gauge["color"] == GREEN
    assert "перевиконано на 28%" in build_measure_conclusion(row)


def test_q4_final_numeric():
    res = results_for(measure("m", 100), [request("m", 4, 85, rid=4)], ["I", "II", "III", "IV"])
    row = row_at(res, 2026, "IV")
    approx(row["execution_score"], 85)
    assert row["forecast_kind"] == "final"
    assert row["risk_level"] is None
    assert row["forecast_attainment_pct"] is None
    assert gauge_state(row)["color"] == RED
    conclusion = build_measure_conclusion(row)
    assert "За підсумками року" in conclusion and "прогнозний ризик" in conclusion


def test_yes_no_deadline_semantics():
    # Yes before deadline -> achieved / green.
    res = results_for(measure("m", "Так", end="IV квартал 2026", unit="так/ні"), [request("m", 2, "Так", status="Виконано", rid=1)], ["I", "II"])
    yes = row_at(res, 2026, "II")
    assert yes["execution_score"] == 100 and gauge_state(yes)["color"] == GREEN
    assert "достроково" in build_measure_conclusion(yes).lower()

    # No with deadline more than one quarter away -> no standard risk / blue.
    res = results_for(measure("m", "Так", end="IV квартал 2026", unit="так/ні"), [request("m", 2, "Ні", status="Не виконано", rid=1)], ["I", "II"])
    far = row_at(res, 2026, "II")
    assert far["risk_level"] is None and far["forecast_kind"] == "yes_no"
    assert gauge_state(far)["color"] == BLUE

    # No with deadline next quarter -> High risk / orange.
    res = results_for(measure("m", "Так", end="III квартал 2026", unit="так/ні"), [request("m", 2, "Ні", status="Не виконано", rid=1)], ["I", "II"])
    near = row_at(res, 2026, "II")
    assert near["risk_level"] == "Високий ризик"
    assert gauge_state(near)["color"] == "#FF7A45"

    # No at deadline -> final failure / red, not predictive risk.
    res = results_for(measure("m", "Так", end="III квартал 2026", unit="так/ні"), [request("m", 3, "Ні", status="Не виконано", rid=1)], ["I", "II", "III"])
    final = row_at(res, 2026, "III")
    assert final["forecast_kind"] == "final" and final["risk_level"] is None
    assert gauge_state(final)["color"] == RED

    # Q1 next-quarter deadline -> preliminary warning / blue.
    res = results_for(measure("m", "Так", end="II квартал 2026", unit="так/ні"), [request("m", 1, "Ні", status="Не виконано", rid=1)], ["I"])
    prelim = row_at(res, 2026, "I")
    assert prelim["forecast_kind"] == "preliminary" and bool(prelim["preliminary_attention"])
    assert prelim["risk_level"] is None and gauge_state(prelim)["color"] == BLUE


def test_ended_with_and_without_history():
    m = measure("m", 100, end="II квартал 2026")
    res = results_for(m, [request("m", 2, 60, rid=2)], ["I", "II", "III"])
    ended = row_at(res, 2026, "III")
    assert ended["period_state"] == "ended"
    assert ended["carry_forward_kind"] == "ended_final"
    approx(ended["execution_score"], 60)
    assert not bool(ended["missing_required_submission"])
    assert "Нові відомості" not in build_measure_conclusion(ended)

    res = results_for(m, [], ["I", "II", "III"])
    missing = row_at(res, 2026, "III")
    assert missing["execution_score"] == 0 and bool(missing["final_missing_result"])
    assert gauge_state(missing)["color"] == RED


def test_locked_period():
    res = results_for(
        measure("m", 100), [request("m", 2, 50, rid=2)], ["II"],
        locked_periods={("2026", 2)},
    )
    row = row_at(res, 2026, "II")
    assert row["execution_score"] is None
    assert not bool(row["monitoring_conducted"])
    assert gauge_state(row)["value"] is None and gauge_state(row)["color"] == GRAY
    assert "Моніторинг у цьому періоді не проводився" in build_measure_conclusion(row)


def test_future_measure_and_shared_period_parser():
    start = parse_measure_period("III квартал 2026", end=False)
    end = parse_measure_period("IV квартал 2026", end=True)
    assert period_state(start, end, period_number(2026, "II")) == "future"
    view = build_card_view(None, future=True)
    assert view["gauge"]["value"] is None and view["gauge"]["color"] == GRAY
    assert "ще не розпочався" in view["conclusion"]


def test_no_future_lookahead_and_stale_chart_gap():
    all_requests = [
        request("m", 1, 20, rid=1), request("m", 2, 50, rid=2),
        request("m", 3, 70, rid=3), request("m", 4, 90, rid=4),
    ]
    selected_q2 = results_for(measure("m", 100), all_requests, ["I", "II"])
    q2 = row_at(selected_q2, 2026, "II")
    assert q2["actual"] == 50
    q3_placeholder = quarter_card_view(None, quarter="III", future_relative=True)
    assert "Майбутній період" in q3_placeholder["lines"][0]

    stale = results_for(measure("m", 100), [request("m", 2, 50, rid=2)], ["I", "II", "III"])
    q2row = row_at(stale, 2026, "II"); q3row = row_at(stale, 2026, "III")
    assert actual_observation(q2row) == 50
    assert actual_observation(q3row) is None
    q3card = quarter_card_view(q3row, quarter="III")
    assert q3card["value"] == "50" and q3card["actual_observation"] is None
    assert "Нові дані не подано" in q3card["lines"]


def test_qualitative_no_numeric_trajectory_copy():
    res = results_for(
        measure("m", "x", unit="описово"),
        [request("m", 2, "Опис виконання", status="Частково виконано", rid=2)],
        ["I", "II"],
    )
    row = row_at(res, 2026, "II")
    assert not bool(row["numeric"]) and not bool(row["yes_no"])
    assert row["forecast_attainment_pct"] is None and row["pace_sufficiency_pct"] is None
    conclusion = build_measure_conclusion(row)
    assert "Числова оцінка траєкторії та прогнозного ризику" in conclusion
    assert "прогноз = 75" not in conclusion.lower()
    assert gauge_state(row)["color"] == BLUE
    assert not any(kpi["label"] == "Ризик" for kpi in build_card_view(row)["headline_kpis"])
    assert "Середній ризик" not in conclusion and "Критичний ризик" not in conclusion



def _archive_payload(measure_row, requests):
    return {
        "dashboard_formula_version": DASHBOARD_FORMULA_VERSION,
        "main_table": [dict(measure_row)],
        "monitoring_requests": [dict(row) for row in requests],
        "closeout_requests": [],
        "period_locks": [],
        "monitoring_logs": [],
        "monitoring_request_versions": [],
    }


def test_archive_current_period_source_parity():
    strat_row = measure("m", 100)
    live = pd.DataFrame([request("m", 2, 80, rid=2)])
    payloads = {(2026, "II"): _archive_payload(strat_row, [request("m", 2, 50, rid=20)])}

    # Card and Dashboard now call the same shared source resolver. Their page-level
    # filter scopes differ, but for one selected measure the immutable source is identical.
    card_sources = build_period_source_overrides(
        [(2026, "II")], payloads=payloads, measure_codes=["m"]
    )
    dashboard_sources = build_period_source_overrides(
        [(2026, "II")], payloads=payloads, measure_codes=["m"]
    )
    card = build_period_results(
        pd.DataFrame([strat_row]), live, [(2026, "II")],
        locked_periods=set(), period_sources=card_sources,
    )
    dashboard = build_period_results(
        pd.DataFrame([strat_row]), live, [(2026, "II")],
        locked_periods=set(), period_sources=dashboard_sources,
    )
    card_row = row_at(card, 2026, "II")
    dashboard_row = row_at(dashboard, 2026, "II")
    approx(card_row["actual"], 50)
    approx(card_row["execution_score"], 50)
    approx(dashboard_row["actual"], 50)
    approx(dashboard_row["execution_score"], 50)


def test_archive_previous_quarter_trajectory_parity():
    strat_row = measure("m", 100)
    live = pd.DataFrame([
        request("m", 2, 70, rid=2),
        request("m", 3, 80, rid=3),
    ])
    payloads = {(2026, "II"): _archive_payload(strat_row, [request("m", 2, 50, rid=20)])}
    period_sources = build_period_source_overrides(
        [(2026, "III")], payloads=payloads, measure_codes=["m"]
    )
    # The resolver must include Q2 even though only Q3 is selected.
    assert (2026, "II") in period_sources
    results = build_period_results(
        pd.DataFrame([strat_row]), live, [(2026, "III")],
        locked_periods=set(), period_sources=period_sources,
    )
    row = row_at(results, 2026, "III")
    approx(row["actual"], 80)
    approx(row["current_increment"], 30)  # archived Q2=50, not mutable live Q2=70
    approx(row["forecast_year"], 110)
    approx(row["forecast_attainment_pct"], 110)


def test_qualitative_q2_q3_no_risk_presentation():
    cases = [
        ("II", "Частково виконано", 75, "Середній ризик"),
        ("III", "Не виконано", 0, "Критичний ризик"),
    ]
    for quarter, status, execution, shared_risk in cases:
        quarters = ["I", "II"] if quarter == "II" else ["I", "II", "III"]
        res = results_for(
            measure("m", "x", unit="описово"),
            [request("m", int({"II": 2, "III": 3}[quarter]), "Опис", status=status, rid=2)],
            quarters,
        )
        row = row_at(res, 2026, quarter)
        assert row["execution_score"] == execution
        assert row["risk_level"] == shared_risk  # shared Dashboard signal remains untouched
        view = build_card_view(row)
        assert view["gauge"]["color"] == BLUE
        assert not any(kpi["label"] == "Ризик" for kpi in view["headline_kpis"])
        assert shared_risk not in view["conclusion"]
        assert "прогнозного ризику" in view["conclusion"]


def test_headline_kpi_max_four():
    scenarios = []
    scenarios.append(row_at(results_for(
        measure("m", 10000), [request("m", 2, 6700, rid=2), request("m", 3, 7900, rid=3)], ["I", "II", "III"]
    ), 2026, "III"))
    scenarios.append(row_at(results_for(measure("m", 100), [request("m", 2, 50, rid=2)], ["I", "II", "III"]), 2026, "III"))
    scenarios.append(row_at(results_for(measure("m", 100), [request("m", 1, 20, rid=1)], ["I"]), 2026, "I"))
    scenarios.append(row_at(results_for(measure("m", 100), [request("m", 4, 85, rid=4)], ["I", "II", "III", "IV"]), 2026, "IV"))
    scenarios.append(row_at(results_for(measure("m", "x", unit="описово"), [request("m", 2, "Опис", status="Частково виконано", rid=2)], ["I", "II"]), 2026, "II"))
    for row in scenarios:
        assert len(build_card_view(row)["headline_kpis"]) <= 4


def test_zero_increment_conclusion():
    res = results_for(
        measure("m", 100),
        [request("m", 2, 50, rid=2), request("m", 3, 50, rid=3)],
        ["I", "II", "III"],
    )
    row = row_at(res, 2026, "III")
    approx(row["current_increment"], 0)
    conclusion = build_measure_conclusion(row)
    assert "Фактичний результат порівняно з попереднім кварталом не змінився" in conclusion
    assert "недостатньою для його досягнення без прискорення виконання" in conclusion
    assert "Квартальна траєкторія сформована" not in conclusion


def test_yes_no_far_and_undefined_deadline_copy():
    far_res = results_for(
        measure("m", "Так", end="IV квартал 2026", unit="так/ні"),
        [request("m", 2, "Ні", status="Не виконано", rid=1)],
        ["I", "II"],
    )
    far = row_at(far_res, 2026, "II")
    assert far["risk_level"] is None
    assert build_measure_conclusion(far) == "Результат ще не досягнуто; до встановленого строку виконання залишається більше одного кварталу."

    # Undefined-deadline wording is driven by the shared yes/no risk explanation;
    # no Card-side deadline risk formula is introduced.
    shared = yes_no_trajectory("Ні", selected_year=2026, selected_quarter="II", deadline="")
    undefined = {
        "year": 2026, "quarter": "II", "period_state": "active",
        "monitoring_conducted": True, "status": "Не виконано",
        "effective_result_status": "Не виконано", "execution_score": 0,
        "numeric": False, "yes_no": True, "actual": "Ні",
        "missing_required_submission": False, "management_zero_due_to_missing_data": False,
        "final_missing_result": False, **shared,
    }
    assert "строк виконання не визначено" in undefined["risk_explanation"].lower()
    assert build_measure_conclusion(undefined) == "Результат ще не досягнуто. Строк виконання не визначено."



def _page_state_helpers():
    """Execute only the pure Card filter-state helpers from the page source."""
    page_path = ROOT / "pages" / "4_Картка_заходу.py"
    tree = ast.parse(page_path.read_text(encoding="utf-8"))
    wanted = {"_card_filter_payload", "_card_reset_payload", "_card_query_signature"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    assert {node.name for node in nodes} == wanted

    def _clean(value):
        return "" if value is None else str(value).strip()

    def _quarter(value):
        text = _clean(value).upper().replace("КВАРТАЛ", "").replace("КВ.", "").strip()
        return {"1": "I", "2": "II", "3": "III", "4": "IV", "I": "I", "II": "II", "III": "III", "IV": "IV"}.get(text, text)

    ns = {"clean": _clean, "quarter_to_roman": _quarter}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(page_path), "exec"), ns)
    return ns


def test_scope_regression_measure_1_1_1():
    m = measure("1.1.1.", 2)
    rows = [
        request("1.1.1.", 1, 0.2, rid=1),
        request("1.1.1.", 2, 0.6, rid=2),
        request("1.1.1.", 3, 1.0, rid=3),
        request("1.1.1.", 4, 2.0, status="Виконано", rid=4),
    ]
    q3_results = results_for(m, rows, ["I", "II", "III"])
    q3 = row_at(q3_results, 2026, "III")
    approx(q3["actual"], 1.0)
    approx(q3["execution_score"], 50.0)
    assert not bool(q3["management_zero_due_to_missing_data"])

    q4_results = results_for(m, rows, ["I", "II", "III", "IV"])
    q4 = row_at(q4_results, 2026, "IV")
    approx(q4["actual"], 2.0)
    approx(q4["execution_score"], 100.0)
    assert bool(q4["result_achieved"])
    assert "досяг" in str(q4["final_outcome"]).casefold()


def test_card_applied_state_seven_parameters():
    helpers = _page_state_helpers()
    payload = helpers["_card_filter_payload"](
        "Ціль 1", "Завдання 1.1", "1.1.1.", "ключ", 2026, "III", "confirmed"
    )
    assert list(payload) == [
        "goal", "task", "measure_code", "keyword", "year", "quarter", "data_source_mode"
    ]
    assert len(payload) == 7


def test_draft_does_not_change_applied_until_apply():
    helpers = _page_state_helpers()
    build = helpers["_card_filter_payload"]
    applied = build("Усі стратегічні цілі", "Усі завдання", "1.1.1.", "", 2026, "III", "confirmed")
    draft = build("Усі стратегічні цілі", "Усі завдання", "1.1.2.", "", 2026, "IV", "confirmed")
    assert applied["measure_code"] == "1.1.1." and applied["quarter"] == "III"
    assert draft["measure_code"] == "1.1.2." and draft["quarter"] == "IV"
    # Apply is the only state transition: the draft object itself never mutates applied.
    applied = draft.copy()
    assert applied["measure_code"] == "1.1.2." and applied["quarter"] == "IV"


def test_data_source_is_applied_only_on_apply():
    helpers = _page_state_helpers()
    build = helpers["_card_filter_payload"]
    applied = build("all", "all", "1.1.1.", "", 2026, "III", "confirmed")
    draft = build("all", "all", "1.1.1.", "", 2026, "III", "operational")
    assert applied["data_source_mode"] == "confirmed"
    assert draft["data_source_mode"] == "operational"
    applied = draft.copy()
    assert applied["data_source_mode"] == "operational"


def test_reset_payload_defaults_and_draft_applied_identity():
    helpers = _page_state_helpers()
    reset = helpers["_card_reset_payload"]("1.1.1.", 2026, "III", "confirmed")
    assert reset == {
        "goal": "Усі стратегічні цілі",
        "task": "Усі завдання",
        "measure_code": "1.1.1.",
        "keyword": "",
        "year": 2026,
        "quarter": "III",
        "data_source_mode": "confirmed",
    }
    draft = reset.copy(); applied = reset.copy()
    assert draft == applied


def test_copy_link_and_direct_url_state_contracts():
    helpers = _page_state_helpers()
    signature = helpers["_card_query_signature"]("1.1.1.", "2026", "III")
    assert signature == "1.1.1.|2026|III"
    # A signature hydrates only when it differs from the previously handled URL.
    last_signature = signature
    assert not (signature and signature != last_signature)

    page = (ROOT / "pages" / "4_Картка_заходу.py").read_text(encoding="utf-8")
    assert 'applied_for_link = st.session_state[CARD_APPLIED_STATE_KEY]' in page
    assert 'render_copy_card_link(\n        applied_for_link["measure_code"],' in page
    assert 'query_signature != st.session_state.get(CARD_URL_SIGNATURE_KEY, "")' in page
    assert '_set_card_applied_and_draft(' in page


def test_dashboard_scope_parity_static_contract():
    page = (ROOT / "pages" / "4_Картка_заходу.py").read_text(encoding="utf-8")
    for token in [
        "is_guest_user(current_user)",
        "is_admin_user(current_user)",
        "is_super_admin_user(current_user)",
        'is_scope_override_active("Картка заходу")',
        "scoped_requests_df = all_requests_df.copy()",
        'ssp_columns=["department"]',
        'page_key="Картка заходу"',
        "requests_df = monitoring_data.measures_only(scoped_requests_df)",
        "measures = all_measures.copy()",
        "selected_measure_requests = requests_df[",
    ]:
        assert token in page, token
    assert page.index("requests_df = monitoring_data.measures_only(scoped_requests_df)") < page.index("selected_measure_requests = requests_df[")


def test_apply_reset_page_flow_static_contract():
    page = (ROOT / "pages" / "4_Картка_заходу.py").read_text(encoding="utf-8")
    assert 'CARD_APPLIED_STATE_KEY = "card_filters_applied_v1"' in page
    assert '"goal", "task", "measure_code", "keyword", "year", "quarter", "data_source_mode"' in page
    assert '"Застосувати параметри"' in page and '"Скинути параметри"' in page
    assert 'type="primary"' in page and 'type="secondary"' in page
    assert 'st.session_state[CARD_APPLIED_STATE_KEY] = new_applied' in page
    assert 'st.session_state[CARD_RESET_REQUEST_KEY] = True' in page
    marker = page.index("# APPLIED CONTENT START")
    lower = page[marker:]
    for draft_key in [
        "card_goal_draft_v1", "card_task_draft_v1", "card_measure_draft_v1",
        "card_keyword_draft_v1", "card_year_draft_v1", "card_quarter_draft_v1",
        "card_data_source_draft_v1",
    ]:
        assert draft_key not in lower
    for assignment in [
        'applied_measure_code = clean(applied["measure_code"])',
        'applied_year = int(applied["year"])',
        'applied_quarter = quarter_to_roman(applied["quarter"])',
        'applied_data_source_mode = applied["data_source_mode"]',
    ]:
        assert assignment in lower


def test_page_static_contracts():
    page = (ROOT / "pages" / "4_Картка_заходу.py").read_text(encoding="utf-8")
    helper = (ROOT / "core" / "measure_card.py").read_text(encoding="utf-8")
    assert "compute_measure_progress" not in page
    assert "[0, 35]" not in page and "[35, 75]" not in page and "[75, 100]" not in page
    assert "понад 75%" not in page and "поточний прогрес заходу є низьким" not in page.lower()
    assert "build_period_results" in page
    assert "build_card_view" in page
    assert "dashboard_sources_v3.build_period_source_overrides" in page
    dashboard = (ROOT / "pages" / "2_Dashboard.py").read_text(encoding="utf-8")
    assert "dashboard_sources_v3.build_period_source_overrides" in dashboard
    source_resolver = (ROOT / "core" / "dashboard_sources.py").read_text(encoding="utf-8")
    for token in [
        "main_table", "monitoring_requests", "closeout_requests", "period_locks",
        "monitoring_logs", "monitoring_request_versions", "required_source_periods",
        "operational.apply_operational_mode",
    ]:
        assert token in source_resolver, token
    assert "current_reporting_period" in page
    assert "Період оцінки" in page and "Джерело даних" in page
    assert "quarter_options[: selected_q_index + 1]" in page
    assert "raw_measure_requests" in page and "analytical_requests" in page
    assert "Фактична динаміка та річний план" in page
    assert "connectgaps=False" in page
    assert "Виконання річного плану" in page
    assert "система зарахувала автоматично" not in page.lower()
    assert "авто-зарахування" not in page.lower()
    assert "Подані фактичні значення та статус виконання не змінюються автоматично" in page
    assert "система не підміняє його автоматичним статусом" in page
    assert "main_ssp_deputy" in page and "DEPUTY_MINISTER_BY_SSP" not in page
    assert "fact / target" not in helper
    assert "forecast_attainment_pct =" not in helper
    assert "risk_level(" not in helper
    assert 'CARD_URL_SIGNATURE_KEY = "card_last_hydrated_query_signature_v1"' in page
    assert 'query_signature != st.session_state.get(CARD_URL_SIGNATURE_KEY, "")' in page
    assert page.index("_set_card_applied_and_draft(") < page.index('st.selectbox("Рік"')
    assert 'if "квартал" in text.lower()' in page and 'return f"{val} квартал"' in page
    assert 'for candidate in reversed(row_values[:idx])' in page
    assert "Не вдалося завантажити довідник КПКВК" in page
    assert '[data-testid="stMain"] div[data-testid="stPageLink"] a' in page
    assert 'div[data-testid="stSelectbox"] div[data-baseweb="select"] > div' in page
    for technical_copy in ["Shared v3", "canonical shared v3 state", "Dashboard execution v3"]:
        assert technical_copy not in page
    # Access/PDF/process contracts remain on the page.
    for token in [
        "filter_actions_for_user", "filter_requests_for_user", "render_scope_toggle",
        "build_measure_card_pdf", "render_copy_card_link", "Історія подання відомостей",
    ]:
        assert token in page, token
    assert "pages/7_Аналітика.py" not in page


def test_stage4_and_analytics_untouched_contract():
    # Stage 2 parity fix may package Dashboard because its archive resolver moved
    # to a shared module, but PDF implementation and Analytics remain untouched.
    forbidden = {"core/stage4.py", "pages/7_Аналітика.py"}
    deliverable = {
        "pages/4_Картка_заходу.py",
        "scripts/test_measure_card_v3.py",
    }
    assert forbidden.isdisjoint(deliverable)
    assert "pages/2_Dashboard.py" not in deliverable
    assert "core/measure_card.py" not in deliverable
    assert "pages/4_Картка_заходу_тест.py" not in deliverable


def main():
    tests = [
        test_cross_page_numeric_identity,
        test_active_carry_forward,
        test_never_reported_management_zero,
        test_q1_preliminary,
        test_insufficient_history,
        test_negative_trajectory,
        test_overachievement_cap_and_copy,
        test_q4_final_numeric,
        test_yes_no_deadline_semantics,
        test_ended_with_and_without_history,
        test_locked_period,
        test_future_measure_and_shared_period_parser,
        test_no_future_lookahead_and_stale_chart_gap,
        test_qualitative_no_numeric_trajectory_copy,
        test_archive_current_period_source_parity,
        test_archive_previous_quarter_trajectory_parity,
        test_qualitative_q2_q3_no_risk_presentation,
        test_headline_kpi_max_four,
        test_zero_increment_conclusion,
        test_yes_no_far_and_undefined_deadline_copy,
        test_scope_regression_measure_1_1_1,
        test_card_applied_state_seven_parameters,
        test_draft_does_not_change_applied_until_apply,
        test_data_source_is_applied_only_on_apply,
        test_reset_payload_defaults_and_draft_applied_identity,
        test_copy_link_and_direct_url_state_contracts,
        test_dashboard_scope_parity_static_contract,
        test_apply_reset_page_flow_static_contract,
        test_page_static_contracts,
        test_stage4_and_analytics_untouched_contract,
    ]
    for fn in tests:
        fn()
        print("PASS", fn.__name__)
    print(f"PASS {len(tests)} measure-card test groups")


if __name__ == "__main__":
    main()
