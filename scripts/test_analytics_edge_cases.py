from __future__ import annotations

"""RCv7 edge-case release gate for current Analytics semantics.

Each narrative scenario executes the real current path:
    context -> factual registry -> findings -> planner -> renderer -> validator -> final note

Run from repository root:
    PYTHONPATH=. python -m unittest scripts.test_analytics_edge_cases -v
"""

import unittest

import pandas as pd

from core.analytics_calculations import build_analytics_ssp_summary
from core.analytics_text import generate_analytics_note
from core.analytics_text.compatibility import RENDERED
from core.dashboard_breakdowns import build_period_results, ssp_summary
from core.dashboard_risk import risk_summary

import scripts.test_analytics_compatibility as compat
import scripts.test_analytics_v3 as v3


def _assert_clean_pipeline(testcase: unittest.TestCase, ctx):
    signals, findings, plan, result = compat._pipeline(ctx)
    testcase.assertTrue(result.text.strip())
    testcase.assertEqual(result.debug.important_findings_skipped, [])
    testcase.assertFalse(result.debug.validation_warnings)
    testcase.assertTrue(all(item.get("provenance_valid") for item in result.debug.numeric_provenance))
    return signals, findings, plan, result


def _zero_assessed_risk_context(quarter: str):
    snapshot = pd.DataFrame({
        "quarter": [quarter, quarter],
        "execution_score": [None, None],
        "result_achieved": [False, False],
        "risk_level": [None, None],
    })
    summary = risk_summary(snapshot)
    base = v3.NarrativeTests()._context(attention=0, dynamics=(60.0,))
    metrics = dict(base.metrics)
    metrics.update({
        "unique_measures": 2,
        "total_rows": 2,
        "latest_measure_count": 2,
        "no_data": 2,
        "attention_count": 0,
        "attention_type": "forecast_risk",
        "attention_label": "Високий або критичний ризик",
        "attention_assessed_count": 0,
        "latest_period": (2026, quarter),
        "latest_risk_summary": summary,
    })
    ctx = compat._rebuild(
        base,
        metrics=metrics,
        goal_progress=pd.DataFrame(),
        task_progress=pd.DataFrame(),
        department_progress=pd.DataFrame(),
        product_progress=pd.DataFrame(),
        status_counts=pd.DataFrame(),
        active=pd.DataFrame(),
    )
    return ctx, summary


def _persistence_context(missing_periods: int):
    base = v3.NarrativeTests()._context(attention=0)
    periods = ("I", "II", "III")
    rows = []
    for pos, quarter in enumerate(periods):
        rows.append({
            "code": "M1",
            "goal_code": "1.",
            "department": "ССП 1",
            "report_year": 2026,
            "report_quarter": quarter,
            "missing_required_submission": pos < missing_periods,
        })
        rows.append({
            "code": "M2",
            "goal_code": "2.",
            "department": "ССП 2",
            "report_year": 2026,
            "report_quarter": quarter,
            "missing_required_submission": False,
        })
    metrics = dict(base.metrics)
    metrics.update({"attention_count": 0, "no_data": 0})
    return compat._rebuild(base, metrics=metrics, active=pd.DataFrame(rows))


def _balanced_context(entity_count: int, per_entity_count: int, *, topic: str):
    if topic not in {"attention", "missing"}:
        raise ValueError(topic)
    base = v3.NarrativeTests()._context(attention=0)
    total = entity_count * per_entity_count
    goals, tasks, departments = compat._attention_frames([0] * entity_count)
    for frame in (goals, tasks, departments):
        frame["Актуальна_увага"] = per_entity_count if topic == "attention" else 0
        frame["Без_даних"] = per_entity_count if topic == "missing" else 0
    goals["Унікальних_заходів"] = per_entity_count
    departments["Унікальних_заходів"] = per_entity_count
    metrics = dict(base.metrics)
    metrics.update({
        "unique_measures": total,
        "total_rows": total,
        "latest_measure_count": total,
        "attention_count": total if topic == "attention" else 0,
        "attention_assessed_count": total,
        "no_data": total if topic == "missing" else 0,
    })
    return compat._rebuild(
        base,
        metrics=metrics,
        goal_progress=goals,
        task_progress=tasks,
        department_progress=departments,
        product_progress=pd.DataFrame(),
        status_counts=pd.DataFrame(),
        active=pd.DataFrame(),
    )


def _tied_context(counts: list[int], *, topic: str):
    base = v3.NarrativeTests()._context(attention=0)
    total = sum(counts)
    goals, tasks, departments = compat._attention_frames([0] * len(counts))
    for frame in (goals, tasks, departments):
        frame["Актуальна_увага"] = counts if topic == "attention" else [0] * len(counts)
        frame["Без_даних"] = counts if topic == "missing" else [0] * len(counts)
    goals["Унікальних_заходів"] = [max(1, n) for n in counts]
    departments["Унікальних_заходів"] = [max(1, n) for n in counts]
    latest_count = max(total, len(counts))
    metrics = dict(base.metrics)
    metrics.update({
        "unique_measures": latest_count,
        "total_rows": latest_count,
        "latest_measure_count": latest_count,
        "attention_count": total if topic == "attention" else 0,
        "attention_assessed_count": latest_count,
        "no_data": total if topic == "missing" else 0,
    })
    return compat._rebuild(
        base,
        metrics=metrics,
        goal_progress=goals,
        task_progress=tasks,
        department_progress=departments,
        product_progress=pd.DataFrame(),
        status_counts=pd.DataFrame(),
        active=pd.DataFrame(),
    )


def _measure(code: str, ssp: str) -> dict:
    return {
        "object_type": "measure",
        "code": code,
        "name": code,
        "target_2026": 100,
        "measure_start_date": "I квартал 2026",
        "measure_end_date": "IV квартал 2026",
        "parent_task_code": "1.1",
        "parent_task_name": "Завдання",
        "parent_goal_code": "1",
        "parent_goal_name": "Ціль",
        "resp_main": f"ССП {ssp}",
        "resp_co_1": "",
        "resp_co_2": "",
    }


def _request(code: str, quarter: int, value: float, rid: int) -> dict:
    return {
        "id": rid,
        "strat_code": code,
        "year": 2026,
        "quarter": quarter,
        "status": "Частково виконано",
        "approval_status": "Погоджено",
        "object_kind": "measure",
        "numeric_value": value,
        "value_text": None,
        "submitted_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


class AnalyticsRCv7EdgeCaseTests(unittest.TestCase):
    def _assert_zero_assessed_risk(self, quarter: str):
        ctx, summary = _zero_assessed_risk_context(quarter)
        self.assertEqual(summary["risk_assessed_count"], 0)
        self.assertIsNone(summary["share_high_critical_risk"])
        self.assertIsNone(summary["share_without_substantial_risk"])
        _, findings, plan, result = _assert_clean_pipeline(self, ctx)
        risk = next(item for item in findings if item.code == "risk_structure")
        self.assertEqual(risk.facts.get("mode"), "forecast_risk")
        self.assertEqual(risk.facts.get("assessment_state"), "zero_assessed")
        self.assertEqual(int(risk.facts.get("assessed_count")), 0)
        self.assertIn("management_attention", plan.blocks)
        self.assertIn("risk_structure", result.debug.block_findings.get("management_attention", []))
        self.assertEqual(result.debug.finding_dispositions["risk_structure"], RENDERED)
        low = result.text.lower()
        self.assertIn("немає заходів із розрахованим прогнозним ризиком", low)
        self.assertIn("частки ризику не розраховуються", low)
        self.assertNotIn("частка високого/критичного прогнозного ризику —", low)

    def test_q2_zero_risk_assessed_is_explicit_and_consumed(self):
        self._assert_zero_assessed_risk("II")

    def test_q3_zero_risk_assessed_is_explicit_and_consumed(self):
        self._assert_zero_assessed_risk("III")

    def test_missing_persistence_requires_two_or_more_missing_periods(self):
        for missing_periods in (0, 1, 2):
            with self.subTest(missing_periods=missing_periods):
                ctx = _persistence_context(missing_periods)
                _, findings, _, result = _assert_clean_pipeline(self, ctx)
                codes = {item.code for item in findings}
                if missing_periods < 2:
                    self.assertNotIn("missing_persistence", codes)
                    self.assertNotIn("Повторювана неповнота даних", result.text)
                else:
                    self.assertIn("missing_persistence", codes)
                    self.assertIn("missing_persistence", result.debug.block_findings.get("coverage", []))
                    self.assertIn("Повторювана неповнота даних", result.text)

    def test_equal_attention_distributions_2_2_3_3_4_4_are_not_concentrated(self):
        for n in (2, 3, 4):
            with self.subTest(entity_count=n):
                ctx = _balanced_context(n, n, topic="attention")
                signals, findings, _, result = _assert_clean_pipeline(self, ctx)
                signal_codes = {item.code for item in signals}
                finding_codes = {item.code for item in findings}
                for kind in ("goal", "task", "department"):
                    self.assertNotIn(f"{kind}_attention_concentrated", signal_codes)
                    self.assertIn(f"{kind}_attention_distributed", finding_codes)
                    self.assertNotIn(f"{kind}_attention_concentrated", finding_codes)
                self.assertNotIn("найбільше у «", result.text.lower())
                self.assertNotIn("найбільше виділяється", result.text.lower())

    def test_equal_missing_distributions_2_2_3_3_4_4_are_not_concentrated(self):
        for n in (2, 3, 4):
            with self.subTest(entity_count=n):
                ctx = _balanced_context(n, n, topic="missing")
                signals, findings, _, result = _assert_clean_pipeline(self, ctx)
                signal_codes = {item.code for item in signals}
                finding_codes = {item.code for item in findings}
                for kind in ("goal", "task", "department"):
                    self.assertNotIn(f"{kind}_missing_concentrated", signal_codes)
                    self.assertIn(f"{kind}_missing_distributed", finding_codes)
                    self.assertNotIn(f"{kind}_missing_concentrated", finding_codes)
                low = result.text.lower()
                self.assertIn("без єдиного найбільшого осередку", low)
                self.assertNotIn("основний осередок неповноти даних", low)

    def test_tied_localised_attention_has_no_arbitrary_largest_entity(self):
        ctx = _tied_context([2, 2, 0, 0], topic="attention")
        signals, findings, _, result = _assert_clean_pipeline(self, ctx)
        signal_codes = {item.code for item in signals}
        finding_codes = {item.code for item in findings}
        for kind in ("goal", "task", "department"):
            self.assertNotIn(f"{kind}_attention_concentrated", signal_codes)
            self.assertIn(f"{kind}_attention_localised", finding_codes)
        low = result.text.lower()
        self.assertIn("однаковий максимальний рівень мають", low)
        self.assertNotIn("найбільше у «", low)
        self.assertNotIn("найбільше виділяється", low)

    def test_tied_localised_missing_has_no_arbitrary_largest_entity(self):
        ctx = _tied_context([2, 2, 0, 0], topic="missing")
        signals, findings, _, result = _assert_clean_pipeline(self, ctx)
        signal_codes = {item.code for item in signals}
        finding_codes = {item.code for item in findings}
        for kind in ("goal", "task", "department"):
            self.assertNotIn(f"{kind}_missing_concentrated", signal_codes)
            self.assertIn(f"{kind}_missing_localised", finding_codes)
        low = result.text.lower()
        self.assertIn("однаковий максимальний рівень мають", low)
        self.assertNotIn("основний осередок неповноти даних", low)

    def test_tied_concentrated_top_group_does_not_invent_single_leader(self):
        for topic in ("attention", "missing"):
            with self.subTest(topic=topic):
                ctx = _tied_context([4, 4, 4, 1, 1], topic=topic)
                _, findings, _, result = _assert_clean_pipeline(self, ctx)
                suffix = "attention" if topic == "attention" else "missing"
                for kind in ("goal", "task", "department"):
                    self.assertIn(f"{kind}_{suffix}_concentrated", {item.code for item in findings})
                low = result.text.lower()
                self.assertIn("однаковий максимальний рівень мають", low)
                self.assertNotIn("найбільше у «", low)
                if topic == "missing":
                    self.assertNotIn("основний осередок неповноти даних", low)

    def test_ssp_underperformance_contribution_uses_exact_latest_execution(self):
        strat = pd.DataFrame([_measure("a", "1"), _measure("b", "2")])
        requests = pd.DataFrame([
            _request("a", 1, 0.0, 1),
            _request("a", 2, 100.0, 2),
            _request("b", 1, 50.0, 3),
            _request("b", 2, 50.0, 4),
        ])
        results = build_period_results(
            strat, requests, [(2026, "I"), (2026, "II")], locked_periods=set()
        )
        shared = ssp_summary(results, base_results=results).set_index("ssp")
        analytics = build_analytics_ssp_summary(results, pd.DataFrame(), base_results=results).set_index("ssp_index")

        # Demonstrate the exact leak being guarded: shared Dashboard methodology
        # remains average-based, while Analytics must use the exact latest SSP execution.
        self.assertGreater(float(shared.loc["1", "underperformance_contribution_pct"]), 0.0)
        self.assertEqual(float(analytics.loc["1", "Виконання"]), 100.0)
        self.assertEqual(float(analytics.loc["1", "underperformance_contribution_pct"]), 0.0)
        self.assertEqual(float(analytics.loc["2", "Виконання"]), 50.0)
        self.assertEqual(float(analytics.loc["2", "underperformance_contribution_pct"]), 100.0)

        base_ctx = v3.NarrativeTests()._context(attention=0)
        ctx = compat._rebuild(base_ctx, department_progress=analytics.reset_index())
        _, findings, _, result = _assert_clean_pipeline(self, ctx)
        portfolio = next(item for item in findings if item.code == "ssp_portfolio_impact")
        self.assertEqual(str(portfolio.facts.get("top_underperformance_department")), "ССП 2")
        self.assertNotIn("ССП «1»: на нього припадає", result.text)

    def test_product_structure_reaches_existing_products_renderer(self):
        ctx = v3.NarrativeTests()._context()
        _, findings, plan, result = _assert_clean_pipeline(self, ctx)
        self.assertIn("product_structure", {item.code for item in findings})
        self.assertIn("products", plan.blocks)
        self.assertEqual(result.debug.finding_dispositions["product_structure"], RENDERED)
        self.assertIn("product_structure", result.debug.block_findings.get("products", []))
        self.assertIn("за типами продукту", result.text.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
