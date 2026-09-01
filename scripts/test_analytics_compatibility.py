from __future__ import annotations

"""Behavioral compatibility gate for the current Analytics finding contract.

Every scenario executes the real path:
    context -> factual registry -> findings -> planner -> renderer -> validator -> final note

Run from repository root:
    python -m unittest scripts.test_analytics_compatibility -v
"""

import unittest

import pandas as pd

from core.analytics_text import (
    FINDING_COMPATIBILITY,
    SUPPORTED_FINDING_CODES,
    build_context,
    derive_findings,
    detect_signals,
    generate_analytics_note,
)
from core.analytics_text.compatibility import INTERNAL_ONLY, RENDERED, SUPPORTING_ONLY
from core.analytics_text.planner import build_text_plan
from core.analytics_text.scenarios_current import activate_scenarios
from core.dashboard_risk import risk_summary
from scripts.test_analytics_v3 import MioRegressionTests, NarrativeTests


_ALLOWED = {RENDERED, SUPPORTING_ONLY, INTERNAL_ONLY}


def _rebuild(ctx, **overrides):
    return build_context(
        filters=overrides.get("filters", ctx.filters),
        metrics=overrides.get("metrics", ctx.metrics),
        goal_progress=overrides.get("goal_progress", ctx.goal_progress),
        task_progress=overrides.get("task_progress", ctx.task_progress),
        department_progress=overrides.get("department_progress", ctx.department_progress),
        product_progress=overrides.get("product_progress", ctx.product_progress),
        status_counts=overrides.get("status_counts", ctx.status_counts),
        period_dynamics=overrides.get("period_dynamics", ctx.period_dynamics),
        active=overrides.get("active", ctx.active),
        mio_goal_evaluation=overrides.get("mio_goal_evaluation", ctx.mio_goal_evaluation),
        mio_goal_task_evaluation=overrides.get("mio_goal_task_evaluation", ctx.mio_goal_task_evaluation),
        mio_measure_evaluation=overrides.get("mio_measure_evaluation", ctx.mio_measure_evaluation),
        mio_financing=overrides.get("mio_financing", ctx.mio_financing),
    )


def _pipeline(ctx):
    signals = detect_signals(ctx)
    _, findings = derive_findings(ctx, signals)
    plan = build_text_plan(ctx, signals, activate_scenarios(signals, findings), findings)
    result = generate_analytics_note(context=ctx, debug=True)
    return signals, findings, plan, result


def _all_block_findings(result) -> set[str]:
    return {code for codes in result.debug.block_findings.values() for code in codes}


def _assert_compatibility_invariant(testcase: unittest.TestCase, findings, plan, result):
    testcase.assertTrue(plan.blocks)
    testcase.assertTrue(result.text.strip())
    rendered_text = result.text.casefold()
    testcase.assertNotIn("reference", rendered_text)
    testcase.assertNotIn("best/worst", rendered_text)
    testcase.assertNotIn("ссп «ссп ", rendered_text)
    testcase.assertEqual(result.debug.important_findings_skipped, [])
    testcase.assertFalse([w for w in result.debug.validation_warnings if w.startswith("compatibility:")])
    testcase.assertTrue(all(item.get("provenance_valid") for item in result.debug.numeric_provenance))
    used = _all_block_findings(result)
    for finding in findings:
        testcase.assertIn(finding.code, result.debug.finding_dispositions)
        disposition = result.debug.finding_dispositions[finding.code]
        testcase.assertIn(disposition, _ALLOWED)
        if disposition == RENDERED:
            planner_block = FINDING_COMPATIBILITY[finding.code].planner_block
            testcase.assertIn(planner_block, plan.blocks, f"rendered finding has no planner block: {finding.code}")
            testcase.assertIn(finding.code, used, f"rendered finding silently lost: {finding.code}")
        if finding.importance >= 60:
            testcase.assertTrue(
                finding.code in used or disposition in {SUPPORTING_ONLY, INTERNAL_ONLY},
                f"important finding silently lost: {finding.code}",
            )


def _attention_frames(counts: list[int]):
    goals, tasks, departments = [], [], []
    size = len(counts)
    for i, count in enumerate(counts, 1):
        execution = 50.0 + min(i, 40)
        goals.append({
            "goal_code": f"{i}.", "strategic_goal": f"Ціль {i}", "Виконання": execution,
            "Зміна": 0.0, "Унікальних_заходів": 1, "Актуальна_увага": count, "Без_даних": 0,
        })
        tasks.append({
            "goal_code": f"{i}.", "task_code": f"{i}.1.", "task_name": f"Завдання {i}",
            "Виконання": execution, "Зміна": 0.0, "Актуальна_увага": count, "Без_даних": 0,
        })
        departments.append({
            "ssp_index": str(i), "department": f"ССП {i}", "Виконання": execution,
            "Зміна": 0.0, "Унікальних_заходів": 1, "Актуальна_увага": count, "Без_даних": 0,
            "portfolio_weight_pct": 100.0 / size, "underperformance_contribution_pct": 100.0 / size,
        })
    return pd.DataFrame(goals), pd.DataFrame(tasks), pd.DataFrame(departments)


def _attention_context(counts: list[int]):
    base = NarrativeTests()._context(attention=sum(counts))
    goals, tasks, departments = _attention_frames(counts)
    metrics = dict(base.metrics)
    metrics.update({
        "unique_measures": max(10, sum(counts)),
        "total_rows": max(10, sum(counts)),
        "latest_measure_count": max(10, sum(counts)),
        "attention_count": sum(counts),
        "no_data": 0,
    })
    return _rebuild(
        base,
        metrics=metrics,
        goal_progress=goals,
        task_progress=tasks,
        department_progress=departments,
        product_progress=pd.DataFrame(),
        status_counts=pd.DataFrame(),
    )


def _single_ssp_context(*, with_ownership: bool = True):
    base = NarrativeTests()._context()
    metrics = dict(base.metrics)
    metrics.update({
        "unique_measures": 6, "total_rows": 6, "latest_measure_count": 6,
        "goals": 1, "tasks": 2, "attention_count": 2, "no_data": 1,
    })
    goals = pd.DataFrame([{
        "goal_code": "1.", "strategic_goal": "Ціль 1", "Виконання": 55.0, "Зміна": -2.0,
        "Унікальних_заходів": 6, "Актуальна_увага": 2, "Без_даних": 1,
    }])
    tasks = pd.DataFrame([
        {"goal_code": "1.", "task_code": "1.1.", "task_name": "Завдання 1", "Виконання": 30.0, "Зміна": -5.0, "Актуальна_увага": 2, "Без_даних": 1},
        {"goal_code": "1.", "task_code": "1.2.", "task_name": "Завдання 2", "Виконання": 80.0, "Зміна": 2.0, "Актуальна_увага": 0, "Без_даних": 0},
    ])
    departments = pd.DataFrame([{
        "ssp_index": "1", "department": "ССП 1", "Виконання": 55.0, "Зміна": -2.0,
        "Унікальних_заходів": 6, "Актуальна_увага": 2, "Без_даних": 1,
        "portfolio_weight_pct": 100.0, "underperformance_contribution_pct": 100.0,
    }])
    if with_ownership:
        active = pd.DataFrame([
            {
                "code": f"M{i}", "task_code": "1.1." if i < 3 else "1.2.",
                "department": "ССП 1", "ssp_index": "1", "report_year": 2026,
                "report_quarter": "II", "missing_required_submission": False,
            }
            for i in range(6)
        ])
    else:
        active = pd.DataFrame([
            {"code": f"M{i}", "report_year": 2026, "report_quarter": "II", "missing_required_submission": False}
            for i in range(6)
        ])
    filters = dict(base.filters)
    filters.update({"ssp": ["ССП 1"], "ssp_indices": ["1"], "goal_labels": ["1."]})
    return _rebuild(
        base,
        filters=filters,
        metrics=metrics,
        goal_progress=goals,
        task_progress=tasks,
        department_progress=departments,
        product_progress=pd.DataFrame(),
        status_counts=pd.DataFrame(),
        active=active,
    )


def _risk_context(quarter: str):
    if quarter == "I":
        snapshot = pd.DataFrame({
            "quarter": ["I", "I"],
            "execution_score": [20.0, 80.0],
            "result_achieved": [False, False],
            "forecast_kind": ["preliminary", "preliminary"],
            "forecast_attainment_pct": [80.0, 120.0],
            "preliminary_attention": [True, False],
        })
        attention_type, attention_count, assessed = "preliminary_attention", 1, 0
    elif quarter in {"II", "III"}:
        snapshot = pd.DataFrame({
            "quarter": [quarter, quarter, quarter],
            "execution_score": [50.0, 100.0, 60.0],
            "result_achieved": [False, True, False],
            "risk_level": ["Високий ризик", None, "Критичний ризик"],
        })
        attention_type, attention_count, assessed = "forecast_risk", 2, 3
    else:
        snapshot = pd.DataFrame({
            "quarter": ["IV", "IV", "IV"],
            "execution_score": [100.0, 50.0, None],
            "result_achieved": [True, False, False],
        })
        attention_type, attention_count, assessed = "final_nonachievement", 1, 2
    summary = risk_summary(snapshot)
    base = NarrativeTests()._context(attention=attention_count, dynamics=(60.0,))
    metrics = dict(base.metrics)
    metrics.update({
        "unique_measures": len(snapshot), "total_rows": len(snapshot),
        "latest_measure_count": len(snapshot), "no_data": 0,
        "attention_count": attention_count, "attention_type": attention_type,
        "attention_label": {
            "preliminary_attention": "Попередня управлінська увага",
            "forecast_risk": "Високий або критичний ризик",
            "final_nonachievement": "Фактичне недосягнення",
        }[attention_type],
        "attention_assessed_count": assessed,
        "latest_period": (2026, quarter), "latest_risk_summary": summary,
    })
    return _rebuild(
        base, metrics=metrics, goal_progress=pd.DataFrame(), task_progress=pd.DataFrame(),
        department_progress=pd.DataFrame(), product_progress=pd.DataFrame(),
        status_counts=pd.DataFrame(), active=pd.DataFrame(),
    ), summary


def _tiny_context(*, status=False, missing=False, task_missing=False):
    base = NarrativeTests()._context(attention=0, dynamics=(60.0,))
    metrics = dict(base.metrics)
    metrics.update({
        "unique_measures": 1, "total_rows": 1, "latest_measure_count": 1,
        "attention_count": 0, "attention_type": "forecast_risk",
        "attention_label": "Високий або критичний ризик",
        "attention_assessed_count": 1, "no_data": 1 if (missing or task_missing) else 0,
    })
    goals = pd.DataFrame([{
        "goal_code":"1.", "strategic_goal":"Ціль 1", "Виконання": None if task_missing else 60.0,
        "Зміна":0.0, "Унікальних_заходів":1, "Актуальна_увага":0,
        "Без_даних":1 if (missing or task_missing) else 0,
    }])
    tasks = pd.DataFrame([{
        "goal_code":"1.", "task_code":"1.1.", "task_name":"Завдання 1",
        "Виконання": None if task_missing else 60.0, "Зміна":0.0,
        "Актуальна_увага":0, "Без_даних":1 if (missing or task_missing) else 0,
    }])
    deps = pd.DataFrame([{
        "ssp_index":"1", "department":"ССП 1", "Виконання": None if task_missing else 60.0,
        "Зміна":0.0, "Унікальних_заходів":1, "Актуальна_увага":0,
        "Без_даних":1 if (missing or task_missing) else 0,
        "portfolio_weight_pct":100.0, "underperformance_contribution_pct":100.0,
    }])
    statuses = pd.DataFrame([{"status":"Частково виконано", "Кількість":1}]) if status else pd.DataFrame()
    active = pd.DataFrame([{
        "code":"M1", "report_year":2026, "report_quarter":"II",
        "missing_required_submission": bool(missing or task_missing),
    }])
    return _rebuild(
        base, metrics=metrics, goal_progress=goals, task_progress=tasks,
        department_progress=deps, product_progress=pd.DataFrame(),
        status_counts=statuses, active=active,
    )


def _movement_context(changes: list[float], *, dynamics=(50.0, 60.0, 60.0)):
    base = NarrativeTests()._context(attention=0, dynamics=dynamics)
    goals, tasks, departments = _attention_frames([0] * len(changes))
    for frame in (goals, tasks, departments):
        frame["Зміна"] = changes
    size = max(10, len(changes))
    metrics = dict(base.metrics)
    metrics.update({
        "unique_measures": size, "total_rows": size, "latest_measure_count": size,
        "attention_count": 0, "no_data": 0,
    })
    return _rebuild(
        base, metrics=metrics, goal_progress=goals, task_progress=tasks,
        department_progress=departments, product_progress=pd.DataFrame(),
        status_counts=pd.DataFrame(),
    )


def _missing_context(counts: list[int]):
    base = NarrativeTests()._context(attention=0)
    goals, tasks, departments = _attention_frames([0] * len(counts))
    for frame in (goals, tasks, departments):
        frame["Без_даних"] = counts
    total = sum(counts)
    size = max(10, total, len(counts))
    metrics = dict(base.metrics)
    metrics.update({
        "unique_measures": size, "total_rows": size, "latest_measure_count": size,
        "attention_count": 0, "no_data": total,
    })
    return _rebuild(
        base, metrics=metrics, goal_progress=goals, task_progress=tasks,
        department_progress=departments, product_progress=pd.DataFrame(),
        status_counts=pd.DataFrame(),
    )


def _persistence_context():
    base = NarrativeTests()._context(attention=0)
    rows = []
    for quarter, missing in (("I", True), ("II", True), ("III", False)):
        rows.extend([
            {
                "code": "M1", "goal_code": "1.", "department": "ССП 1",
                "report_year": 2026, "report_quarter": quarter,
                "missing_required_submission": missing,
            },
            {
                "code": "M2", "goal_code": "2.", "department": "ССП 2",
                "report_year": 2026, "report_quarter": quarter,
                "missing_required_submission": False,
            },
        ])
    metrics = dict(base.metrics)
    metrics.update({"attention_count": 0, "no_data": 1})
    return _rebuild(base, metrics=metrics, active=pd.DataFrame(rows))


def _single_entities_context():
    base = NarrativeTests()._context(attention=0, dynamics=(60.0,))
    goals, tasks, departments = _attention_frames([0])
    metrics = dict(base.metrics)
    metrics.update({
        "unique_measures": 5, "total_rows": 5, "latest_measure_count": 5,
        "attention_count": 0, "no_data": 0,
    })
    return _rebuild(
        base, metrics=metrics, goal_progress=goals, task_progress=tasks,
        department_progress=departments, product_progress=pd.DataFrame(),
        status_counts=pd.DataFrame(),
    )


def _all_finding_audit_contexts():
    """Behavioral corpus that actually generates every supported current finding code."""
    contexts = [
        ("baseline", NarrativeTests()._context()),
        ("mio", MioRegressionTests()._context_with_mio()),
    ]
    for name, counts in (
        ("concentrated", [6, 1, 1, 1]),
        ("localised", [1] * 5 + [0] * 15),
        ("distributed", [1] * 10),
        ("none", [0] * 5),
    ):
        contexts.append((f"attention_{name}", _attention_context(counts)))
        contexts.append((f"missing_{name}", _missing_context(counts)))
    for name, changes in (
        ("positive", [3.0, 2.0, 1.0]),
        ("negative", [-3.0, -2.0, -1.0]),
        ("stable", [0.0, 0.0, 0.0]),
        ("polarised", [8.0, -8.0, 0.0]),
    ):
        contexts.append((f"movement_{name}", _movement_context(changes)))
    for name, dynamics in (
        ("continuous_growth", (50.0, 60.0, 70.0)),
        ("continuous_decline", (70.0, 60.0, 50.0)),
        ("recovery", (70.0, 50.0, 60.0)),
        ("reversal", (50.0, 70.0, 60.0)),
        ("plateau", (50.0, 50.5, 50.8)),
        ("net_growth", (50.0, 60.0, 60.0)),
        ("net_decline", (60.0, 50.0, 50.0)),
        ("mixed", (50.0, 60.0, 60.0, 50.0)),
        ("late_acceleration", (50.0, 55.0, 70.0)),
        ("growth_slowing", (50.0, 70.0, 75.0)),
        ("decline_accelerating", (80.0, 75.0, 60.0)),
        ("single_period", (60.0,)),
    ):
        contexts.append((f"trajectory_{name}", NarrativeTests()._context(dynamics=dynamics)))
    for quarter in ("I", "II", "III", "IV"):
        contexts.append((f"risk_{quarter}", _risk_context(quarter)[0]))
    contexts.extend([
        ("ssp_children", _single_ssp_context(with_ownership=True)),
        ("ssp_no_children", _single_ssp_context(with_ownership=False)),
        ("missing_persistence", _persistence_context()),
        ("trajectory_unavailable", _rebuild(NarrativeTests()._context(attention=0), period_dynamics=pd.DataFrame())),
        ("single_entities", _single_entities_context()),
        (
            "conflict_execution_down_coverage_up",
            NarrativeTests()._context(completion=50.0, coverage=50.0, coverage_latest=90.0, dynamics=(70.0, 50.0)),
        ),
        (
            "conflict_execution_up_coverage_down",
            NarrativeTests()._context(completion=70.0, coverage=90.0, coverage_latest=55.0, dynamics=(50.0, 70.0)),
        ),
        ("stable_internal_movement", _movement_context([8.0, -8.0, 0.0], dynamics=(60.0, 60.5))),
    ])
    aligned = NarrativeTests()._context(completion=72.0)
    aligned_metrics = dict(aligned.metrics)
    aligned_metrics["goal_completion"] = 71.0
    contexts.append(("execution_goal_alignment", _rebuild(aligned, metrics=aligned_metrics)))
    return contexts


class CompatibilityRegistryBehaviorTests(unittest.TestCase):
    def test_registry_is_total_and_has_no_undefined_supported_finding(self):
        self.assertEqual(set(FINDING_COMPATIBILITY), set(SUPPORTED_FINDING_CODES))
        self.assertEqual(len(FINDING_COMPATIBILITY), 75)
        self.assertTrue(all(spec.disposition in _ALLOWED for spec in FINDING_COMPATIBILITY.values()))
        self.assertTrue(all(spec.planner_block and spec.renderer for spec in FINDING_COMPATIBILITY.values()))

    def test_concentrated_localised_distributed_current_attention_are_consumed(self):
        scenarios = {
            "concentrated": [6, 1, 1, 1],
            # 5 affected of 20; top3 share = 60%, so the localised branch is reachable.
            "localised": [1] * 5 + [0] * 15,
            "distributed": [1] * 10,
        }
        for family, counts in scenarios.items():
            with self.subTest(family=family):
                ctx = _attention_context(counts)
                _, findings, plan, result = _pipeline(ctx)
                expected = {f"goal_attention_{family}", f"task_attention_{family}", f"department_attention_{family}"}
                finding_codes = {item.code for item in findings}
                self.assertTrue(expected <= finding_codes)
                self.assertIn("management_attention", plan.blocks)
                self.assertTrue(expected <= set(result.debug.block_findings.get("management_attention", [])))
                self.assertIn("актуальні сигнали управлінської уваги останнього обраного періоду", result.text.lower())
                _assert_compatibility_invariant(self, findings, plan, result)

    def test_execution_goal_divergence_and_alignment_have_renderer_provenance(self):
        for goal_value, expected in ((50.0, "execution_goal_divergence"), (71.0, "execution_goal_alignment")):
            with self.subTest(expected=expected):
                base = NarrativeTests()._context(completion=72.0)
                metrics = dict(base.metrics); metrics["goal_completion"] = goal_value
                ctx = _rebuild(base, metrics=metrics)
                _, findings, plan, result = _pipeline(ctx)
                self.assertIn(expected, {item.code for item in findings})
                self.assertIn(expected, result.debug.block_findings.get("overall_state", []))
                self.assertIn(expected, _all_block_findings(result))
                _assert_compatibility_invariant(self, findings, plan, result)

    def test_risk_structure_renders_without_management_priorities(self):
        base = NarrativeTests()._context(attention=0, dynamics=(50.0,))
        metrics = dict(base.metrics)
        metrics.update({
            "unique_measures": 1, "total_rows": 1, "latest_measure_count": 1,
            "latest_risk_summary": {
                "risk_assessed_count": 1,
                "share_high_critical_risk": 100.0,
                "share_without_substantial_risk": 0.0,
                "share_results_achieved": None,
            },
        })
        goals = pd.DataFrame([{
            "goal_code": "1.", "strategic_goal": "Ціль 1", "Виконання": 50.0, "Зміна": 0.0,
            "Унікальних_заходів": 1, "Актуальна_увага": 0, "Без_даних": 0,
        }])
        tasks = pd.DataFrame([{
            "goal_code": "1.", "task_code": "1.1.", "task_name": "Завдання 1",
            "Виконання": 50.0, "Зміна": 0.0, "Актуальна_увага": 0, "Без_даних": 0,
        }])
        departments = pd.DataFrame([{
            "ssp_index": "1", "department": "ССП 1", "Виконання": 50.0, "Зміна": 0.0,
            "Унікальних_заходів": 1, "Актуальна_увага": 0, "Без_даних": 0,
            "portfolio_weight_pct": 100.0, "underperformance_contribution_pct": 100.0,
        }])
        ctx = _rebuild(
            base, metrics=metrics, goal_progress=goals, task_progress=tasks,
            department_progress=departments, status_counts=pd.DataFrame(),
            product_progress=pd.DataFrame(), active=pd.DataFrame(),
        )
        _, findings, plan, result = _pipeline(ctx)
        codes = {item.code for item in findings}
        self.assertIn("risk_structure", codes)
        self.assertNotIn("management_priorities", codes)
        self.assertIn("management_attention", plan.blocks)
        self.assertIn("risk_structure", result.debug.block_findings.get("management_attention", []))
        self.assertIn("прогнозний ризиковий зріз", result.text.lower())
        _assert_compatibility_invariant(self, findings, plan, result)

    def test_one_ssp_with_multiple_children_survives_narrow_pruning(self):
        ctx = _single_ssp_context(with_ownership=True)
        _, findings, plan, result = _pipeline(ctx)
        self.assertEqual(plan.complexity, "narrow")
        self.assertIn("departments", plan.blocks)
        self.assertIn("ssp_drilldown", plan.block_plan("departments").finding_codes)
        drill = next(item for item in findings if item.code == "ssp_drilldown")
        self.assertGreaterEqual(len(drill.facts.get("children") or []), 2)
        self.assertIn("ssp_drilldown", result.debug.block_findings.get("departments", []))
        self.assertIn("фактично розрахований дочірній розподіл за завданнями", result.text.lower())
        self.assertNotIn("ССП «ССП 1»", result.text)
        self.assertIn("ССП 1", result.text)
        self.assertIn(
            "у портфелі ссп 1 фактично розрахований дочірній розподіл за завданнями",
            result.text.lower(),
        )
        _assert_compatibility_invariant(self, findings, plan, result)

    def test_ssp_without_child_evidence_is_supporting_only_without_inference(self):
        ctx = _single_ssp_context(with_ownership=False)
        _, findings, plan, result = _pipeline(ctx)
        drill = next(item for item in findings if item.code == "ssp_drilldown")
        self.assertFalse(drill.facts.get("children"))
        self.assertEqual(result.debug.finding_dispositions["ssp_drilldown"], SUPPORTING_ONLY)
        self.assertNotIn("ssp_drilldown", _all_block_findings(result))
        low = result.text.lower()
        self.assertNotIn("відхилення розподілені між кількома завданнями", low)
        self.assertNotIn("немає одного завдання, яке самостійно концентрує", low)
        _assert_compatibility_invariant(self, findings, plan, result)

    def test_goal_to_task_children_render_and_task_missing_concentration_is_used(self):
        ctx = _single_ssp_context(with_ownership=True)
        _, findings, plan, result = _pipeline(ctx)
        goal_drill = next(item for item in findings if item.code == "goal_drilldown")
        self.assertGreaterEqual(len(goal_drill.facts.get("children") or []), 2)
        self.assertIn("tasks", plan.blocks)
        self.assertIn("goal_drilldown", result.debug.block_findings.get("tasks", []))
        self.assertIn("task_missing_concentrated", {item.code for item in findings})
        self.assertIn("task_missing_concentrated", result.debug.block_findings.get("tasks", []))
        _assert_compatibility_invariant(self, findings, plan, result)

    def test_acceleration_slowing_reversal_and_single_period_are_behavioral(self):
        scenarios = (
            ((50.0, 55.0, 70.0), "trajectory_late_acceleration"),
            ((50.0, 70.0, 75.0), "trajectory_growth_slowing"),
            ((50.0, 70.0, 60.0), "trajectory_reversal_negative"),
            ((60.0,), "trajectory_single_period"),
        )
        for dynamics, expected in scenarios:
            with self.subTest(expected=expected):
                ctx = NarrativeTests()._context(dynamics=dynamics)
                _, findings, plan, result = _pipeline(ctx)
                self.assertIn(expected, {item.code for item in findings})
                self.assertIn("dynamics", plan.blocks)
                self.assertIn(expected, result.debug.block_findings.get("dynamics", []))
                _assert_compatibility_invariant(self, findings, plan, result)

    def test_mixed_context_conflict_is_planned_and_consumed_in_final_synthesis(self):
        base = NarrativeTests()._context(completion=70.0, coverage=90.0, coverage_latest=55.0, dynamics=(50.0, 70.0))
        ctx = base
        _, findings, plan, result = _pipeline(ctx)
        codes = {item.code for item in findings}
        self.assertIn("conflict_execution_up_coverage_down", codes)
        self.assertIn("final_assessment", plan.blocks)
        self.assertIn("conflict_execution_up_coverage_down", plan.block_plan("final_assessment").finding_codes)
        self.assertIn("conflict_execution_up_coverage_down", result.debug.block_findings.get("final_assessment", []))
        _assert_compatibility_invariant(self, findings, plan, result)

    def test_management_priorities_are_planned_consumed_and_provenance_safe(self):
        ctx = NarrativeTests()._context()
        _, findings, plan, result = _pipeline(ctx)
        self.assertIn("management_priorities", {item.code for item in findings})
        self.assertIn("management_attention", plan.blocks)
        self.assertIn("management_priorities", result.debug.block_findings.get("management_attention", []))
        self.assertEqual(result.debug.important_findings_skipped, [])
        _assert_compatibility_invariant(self, findings, plan, result)

    def test_mio_families_survive_full_pipeline(self):
        ctx = MioRegressionTests()._context_with_mio()
        _, findings, plan, result = _pipeline(ctx)
        mio_codes = {item.code for item in findings if item.code.startswith("mio_")}
        self.assertTrue(mio_codes)
        self.assertIn("mio_assessment", plan.blocks)
        self.assertTrue(mio_codes <= _all_block_findings(result))
        _assert_compatibility_invariant(self, findings, plan, result)

    def test_risk_structure_is_quarter_aware_against_real_dashboard_shapes(self):
        for quarter in ("I", "II", "III", "IV"):
            with self.subTest(quarter=quarter):
                ctx, summary = _risk_context(quarter)
                _, findings, plan, result = _pipeline(ctx)
                risk = next(item for item in findings if item.code == "risk_structure")
                self.assertIn("risk_structure", result.debug.block_findings.get("management_attention", []))
                self.assertFalse(result.debug.validation_warnings)
                low = result.text.lower()
                if quarter == "I":
                    self.assertEqual(risk.facts.get("mode"), "preliminary_attention")
                    self.assertIn("попередній зріз i кварталу", low)
                    self.assertNotIn("ризиковий зріз", low)
                    self.assertNotIn("фінальн", low)
                    self.assertEqual(int(risk.facts.get("preliminary_forecast_count")), summary["preliminary_forecast_count"])
                elif quarter in {"II", "III"}:
                    self.assertEqual(risk.facts.get("mode"), "forecast_risk")
                    self.assertIn("прогнозний ризиковий зріз ii–iii кварталу", low)
                    self.assertIn("високого/критичного прогнозного ризику", low)
                    self.assertNotIn("частка фактично досягнутих результатів", low)
                else:
                    self.assertEqual(risk.facts.get("mode"), "final_nonachievement")
                    self.assertIn("фактичний підсумок iv кварталу", low)
                    self.assertIn("частка фактично досягнутих результатів", low)
                    self.assertNotIn("прогнозний ризиковий зріз", low)
                    self.assertNotIn("високого/критичного прогнозного ризику", low)
                _assert_compatibility_invariant(self, findings, plan, result)

    def test_planner_disposition_invariant_for_tiny_edge_cases(self):
        cases = {
            "1 measure + status": _tiny_context(status=True),
            "1 measure + missing": _tiny_context(missing=True),
            "1 task + missing + no exact execution": _tiny_context(task_missing=True),
        }
        tiny_mio_base = MioRegressionTests()._context_with_mio()
        tiny_metrics = dict(tiny_mio_base.metrics)
        tiny_metrics.update({"unique_measures":1, "total_rows":1, "latest_measure_count":1, "attention_count":1, "attention_assessed_count":1, "no_data":1})
        cases["tiny + MіO"] = _rebuild(tiny_mio_base, metrics=tiny_metrics)
        for name, ctx in cases.items():
            with self.subTest(name=name):
                _, findings, plan, result = _pipeline(ctx)
                self.assertEqual(plan.complexity, "tiny")
                self.assertFalse([w for w in result.debug.validation_warnings if w.startswith("compatibility:")])
                _assert_compatibility_invariant(self, findings, plan, result)
                for finding in findings:
                    if finding.importance >= 60 and result.debug.finding_dispositions[finding.code] == RENDERED:
                        self.assertIn(FINDING_COMPATIBILITY[finding.code].planner_block, plan.blocks)
                        self.assertIn(finding.code, _all_block_findings(result))

    def test_single_entity_attention_and_missing_are_not_classified_as_concentration(self):
        ctx = _tiny_context(missing=True)
        _, findings, plan, result = _pipeline(ctx)
        codes = {item.code for item in findings}
        forbidden = {
            f"{kind}_{topic}_{family}"
            for kind in ("goal", "task", "department")
            for topic in ("attention", "missing")
            for family in ("concentrated", "localised", "distributed")
        }
        self.assertFalse(codes & forbidden)
        self.assertNotIn("три найбільші", result.text.lower())
        _assert_compatibility_invariant(self, findings, plan, result)

    def test_two_entity_rendering_never_says_three_largest(self):
        base = NarrativeTests()._context(attention=3)
        goals, tasks, deps = _attention_frames([2, 1])
        for frame in (goals, tasks, deps):
            frame.loc[0, "Без_даних"] = 2
            frame.loc[1, "Без_даних"] = 1
        metrics = dict(base.metrics)
        metrics.update({"unique_measures":3,"total_rows":3,"latest_measure_count":3,"attention_count":3,"no_data":3})
        ctx = _rebuild(base, metrics=metrics, goal_progress=goals, task_progress=tasks, department_progress=deps, product_progress=pd.DataFrame(), status_counts=pd.DataFrame())
        _, findings, plan, result = _pipeline(ctx)
        self.assertNotIn("три найбільші", result.text.lower())
        self.assertNotIn("серед трьох найвищих", result.text.lower())
        _assert_compatibility_invariant(self, findings, plan, result)

    def test_one_ssp_supporting_portfolio_never_reaches_comparative_renderer(self):
        ctx = _single_ssp_context(with_ownership=True)
        _, findings, plan, result = _pipeline(ctx)
        self.assertIn("ssp_portfolio_impact", {item.code for item in findings})
        self.assertEqual(result.debug.finding_dispositions["ssp_portfolio_impact"], SUPPORTING_ONLY)
        self.assertNotIn("ssp_portfolio_impact", _all_block_findings(result))
        low = result.text.lower()
        self.assertNotIn("найбільший за масштабом портфель має ссп", low)
        self.assertNotIn("найбільший за масштабом портфель і водночас", low)
        _assert_compatibility_invariant(self, findings, plan, result)

    def test_all_75_supported_findings_have_behavioral_compatibility_path(self):
        seen: set[str] = set()
        important_seen: set[str] = set()
        rendered_consumed: set[str] = set()
        explicit_nonrendered: set[str] = set()
        for name, ctx in _all_finding_audit_contexts():
            with self.subTest(context=name):
                _, findings, plan, result = _pipeline(ctx)
                _assert_compatibility_invariant(self, findings, plan, result)
                used = _all_block_findings(result)
                for finding in findings:
                    seen.add(finding.code)
                    if finding.importance >= 60:
                        important_seen.add(finding.code)
                        disposition = result.debug.finding_dispositions[finding.code]
                        if disposition == RENDERED:
                            self.assertIn(FINDING_COMPATIBILITY[finding.code].planner_block, plan.blocks)
                            self.assertIn(finding.code, used)
                            rendered_consumed.add(finding.code)
                        else:
                            self.assertIn(disposition, {SUPPORTING_ONLY, INTERNAL_ONLY})
                            self.assertTrue(result.debug.finding_disposition_reasons.get(finding.code))
                            explicit_nonrendered.add(finding.code)
        self.assertEqual(seen, set(SUPPORTED_FINDING_CODES))
        self.assertEqual(len(seen), 75)
        self.assertTrue(important_seen)
        self.assertEqual(important_seen, rendered_consumed | explicit_nonrendered)

    def test_baseline_structural_families_have_no_silent_important_loss(self):
        ctx = NarrativeTests()._context()
        _, findings, plan, result = _pipeline(ctx)
        codes = {item.code for item in findings}
        for family_code in (
            "overall_state", "goal_distribution", "task_distribution", "department_distribution",
            "status_structure", "management_priorities", "goal_missing_concentrated",
            "department_missing_concentrated", "task_missing_concentrated",
        ):
            self.assertIn(family_code, codes)
        # Product analysis is intentionally below the important-finding threshold,
        # but the existing production products renderer remains a real consumer.
        self.assertIn("product_structure", codes)
        self.assertEqual(FINDING_COMPATIBILITY["product_structure"].planner_block, "products")
        self.assertIn("products", plan.blocks)
        self.assertEqual(result.debug.finding_dispositions["product_structure"], RENDERED)
        self.assertIn("product_structure", result.debug.block_findings.get("products", []))
        _assert_compatibility_invariant(self, findings, plan, result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
