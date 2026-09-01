from __future__ import annotations

"""RCv8 behavioral gate for comparative extrema / superlative semantics.

Every scenario executes the full current Analytics path:
    context -> factual registry -> findings -> planner -> renderer -> validator -> final note

Run from repository root:
    PYTHONPATH=. python -m unittest scripts.test_analytics_comparative_extrema -v
"""

import unittest
from pathlib import Path

import pandas as pd

import scripts.test_analytics_compatibility as compat
import scripts.test_analytics_v3 as v3


def _assert_clean_pipeline(testcase: unittest.TestCase, ctx):
    signals, findings, plan, result = compat._pipeline(ctx)
    testcase.assertTrue(plan.blocks)
    testcase.assertTrue(result.text.strip())
    testcase.assertEqual(result.debug.important_findings_skipped, [])
    testcase.assertFalse(result.debug.validation_warnings)
    testcase.assertTrue(all(item.get("provenance_valid") for item in result.debug.numeric_provenance))
    # Release-cleanup language invariant: user-facing automated notes must not
    # leak internal English analytical fragments.
    rendered_text = result.text.casefold()
    testcase.assertNotIn("reference", rendered_text)
    testcase.assertNotIn("best/worst", rendered_text)
    compat._assert_compatibility_invariant(testcase, findings, plan, result)
    return signals, findings, plan, result


def _neutral_context(*, completion: float = 60.0):
    """A validation-clean context whose comparison dimensions are tied by default."""
    base = v3.NarrativeTests()._context(completion=completion, attention=0)
    metrics = dict(base.metrics)
    metrics.update({
        "completion": completion,
        "goal_completion": completion,
        "total_rows": 10,
        "unique_measures": 10,
        "latest_measure_count": 10,
        "goals": 2,
        "tasks": 2,
        "no_data": 0,
        "attention_count": 0,
        "attention_assessed_count": 0,
        "latest_risk_summary": {},
    })
    goals = pd.DataFrame([
        {"goal_code": "1.", "strategic_goal": "Ціль 1", "Виконання": completion, "Зміна": 0.0,
         "Унікальних_заходів": 5, "Актуальна_увага": 0, "Без_даних": 0},
        {"goal_code": "2.", "strategic_goal": "Ціль 2", "Виконання": completion, "Зміна": 0.0,
         "Унікальних_заходів": 5, "Актуальна_увага": 0, "Без_даних": 0},
    ])
    tasks = pd.DataFrame([
        {"goal_code": "1.", "task_code": "1.1.", "task_name": "Завдання 1", "Виконання": completion,
         "Зміна": 0.0, "Актуальна_увага": 0, "Без_даних": 0},
        {"goal_code": "2.", "task_code": "2.1.", "task_name": "Завдання 2", "Виконання": completion,
         "Зміна": 0.0, "Актуальна_увага": 0, "Без_даних": 0},
    ])
    departments = pd.DataFrame([
        {"ssp_index": "1", "department": "ССП 1", "Виконання": completion, "Зміна": 0.0,
         "Унікальних_заходів": 5, "Актуальна_увага": 0, "Без_даних": 0,
         "portfolio_weight_pct": 50.0, "underperformance_contribution_pct": 50.0},
        {"ssp_index": "2", "department": "ССП 2", "Виконання": completion, "Зміна": 0.0,
         "Унікальних_заходів": 5, "Актуальна_увага": 0, "Без_даних": 0,
         "portfolio_weight_pct": 50.0, "underperformance_contribution_pct": 50.0},
    ])
    products = pd.DataFrame([
        {"product_type": "Тип А", "Унікальних_заходів": 5, "Виконання": completion, "Актуальна_увага": 0, "Без_даних": 0},
        {"product_type": "Тип Б", "Унікальних_заходів": 5, "Виконання": completion, "Актуальна_увага": 0, "Без_даних": 0},
    ])
    statuses = pd.DataFrame([
        {"status": "Виконано", "Кількість": 5},
        {"status": "Частково виконано", "Кількість": 5},
    ])
    active = pd.DataFrame([
        {"code": str(i), "report_year": 2026, "report_quarter": "II", "missing_required_submission": False}
        for i in range(10)
    ])
    return compat._rebuild(
        base,
        metrics=metrics,
        goal_progress=goals,
        task_progress=tasks,
        department_progress=departments,
        product_progress=products,
        status_counts=statuses,
        active=active,
        mio_goal_evaluation=pd.DataFrame(),
        mio_goal_task_evaluation=pd.DataFrame(),
        mio_measure_evaluation=pd.DataFrame(),
        mio_financing=pd.DataFrame(),
    )


class AnalyticsRCv8ComparativeExtremaTests(unittest.TestCase):
    def test_two_equal_goals_have_zero_gap_and_no_unique_extrema(self):
        ctx = _neutral_context(completion=50.0)
        _, _, _, result = _assert_clean_pipeline(self, ctx)
        f = ctx.factual_structure("goal.distribution")
        self.assertTrue(f["all_equal"])
        self.assertFalse(f["best_is_unique"])
        self.assertFalse(f["worst_is_unique"])
        self.assertEqual(f["best_tie_count"], 2)
        self.assertEqual(float(f["gap"]), 0.0)
        low = result.text.lower()
        self.assertIn("рівень виконання однаковий", low)
        self.assertNotIn("у розрізі стратегічних цілей результати відрізняються", low)
        self.assertNotIn("стратегічні цілі мають різні результати", low)
        self.assertNotIn("найвищий рівень має сц 1.", low)
        self.assertNotIn("найнижчий рівень має сц 1.", low)

    def test_three_equal_tasks_100_have_no_unique_extrema(self):
        ctx = _neutral_context(completion=100.0)
        tasks = pd.DataFrame([
            {"goal_code": "1.", "task_code": f"1.{i}.", "task_name": f"Завдання {i}", "Виконання": 100.0,
             "Зміна": 0.0, "Актуальна_увага": 0, "Без_даних": 0}
            for i in range(1, 4)
        ])
        metrics = dict(ctx.metrics); metrics["tasks"] = 3
        ctx = compat._rebuild(ctx, metrics=metrics, task_progress=tasks)
        _, _, _, result = _assert_clean_pipeline(self, ctx)
        f = ctx.factual_structure("task.distribution")
        self.assertTrue(f["all_equal"]); self.assertEqual(f["best_tie_count"], 3)
        low = result.text.lower()
        self.assertNotIn("на рівні завдань результати відрізняються", low)
        self.assertNotIn("найвищий рівень має 1.1.", low)
        self.assertNotIn("найнижчий рівень має 1.1.", low)

    def test_two_equal_ssp_execution_50_has_no_unique_extrema(self):
        ctx = _neutral_context(completion=50.0)
        _, _, _, result = _assert_clean_pipeline(self, ctx)
        f = ctx.factual_structure("department.distribution")
        self.assertTrue(f["all_equal"]); self.assertEqual(f["best_tie_count"], 2)
        low = result.text.lower()
        self.assertNotIn("за відповідальними ссп результати відрізняються", low)
        self.assertNotIn("найвищий рівень має ссп 1", low)
        self.assertNotIn("найнижчий рівень має ссп 1", low)

    def test_ten_entities_with_only_one_above_and_one_below_reference_are_not_material_deviation(self):
        ctx = _neutral_context(completion=50.0)
        values = [60.0, 40.0] + [50.0] * 8
        goals = pd.DataFrame([
            {"goal_code": f"{i}.", "strategic_goal": f"Ціль {i}", "Виконання": value, "Зміна": 0.0,
             "Унікальних_заходів": 1, "Актуальна_увага": 0, "Без_даних": 0}
            for i, value in enumerate(values, 1)
        ])
        metrics = dict(ctx.metrics); metrics["goals"] = 10
        ctx = compat._rebuild(ctx, metrics=metrics, goal_progress=goals)
        _, _, _, result = _assert_clean_pipeline(self, ctx)
        f = ctx.factual_structure("goal.distribution")
        self.assertEqual(f["deviation_count"], 2)
        self.assertFalse(f["deviation_is_material"])
        self.assertNotIn("помітну частину розподілу", result.text.lower())

    def test_single_product_has_no_largest_or_best_worst_comparison(self):
        ctx = _neutral_context()
        products = pd.DataFrame([
            {"product_type": "Єдиний", "Унікальних_заходів": 10, "Виконання": 73.0, "Актуальна_увага": 0, "Без_даних": 0},
        ])
        ctx = compat._rebuild(ctx, product_progress=products)
        _, _, _, result = _assert_clean_pipeline(self, ctx)
        f = ctx.factual_structure("product")
        self.assertTrue(f["single_entity"]); self.assertEqual(f["execution_count"], 1)
        low = result.text.lower()
        self.assertIn("представлено один тип продукту", low)
        self.assertIn("порівняння масштабу між типами продукту не проводиться", low)
        self.assertNotIn("найбільший сегмент — «єдиний»", low)
        self.assertNotIn("найвищий рівень має «єдиний»", low)
        self.assertNotIn("найнижчий рівень має «єдиний»", low)

    def test_two_equal_size_products_have_no_unique_largest_segment(self):
        ctx = _neutral_context()
        products = pd.DataFrame([
            {"product_type": "А", "Унікальних_заходів": 5, "Виконання": 60.0, "Актуальна_увага": 0, "Без_даних": 0},
            {"product_type": "Б", "Унікальних_заходів": 5, "Виконання": 80.0, "Актуальна_увага": 0, "Без_даних": 0},
        ])
        ctx = compat._rebuild(ctx, product_progress=products)
        _, _, _, result = _assert_clean_pipeline(self, ctx)
        f = ctx.factual_structure("product")
        self.assertTrue(f["all_equal_size"]); self.assertFalse(f["largest_is_unique"])
        low = result.text.lower()
        self.assertIn("єдиного найбільшого сегмента немає", low)
        self.assertNotIn("найбільший сегмент — «а»", low)
        self.assertNotIn("найбільший сегмент — «б»", low)

    def test_two_equal_execution_products_have_no_unique_best_or_worst(self):
        ctx = _neutral_context()
        products = pd.DataFrame([
            {"product_type": "А", "Унікальних_заходів": 6, "Виконання": 70.0, "Актуальна_увага": 0, "Без_даних": 0},
            {"product_type": "Б", "Унікальних_заходів": 4, "Виконання": 70.0, "Актуальна_увага": 0, "Без_даних": 0},
        ])
        ctx = compat._rebuild(ctx, product_progress=products)
        _, _, _, result = _assert_clean_pipeline(self, ctx)
        f = ctx.factual_structure("product")
        self.assertTrue(f["all_equal_execution"]); self.assertFalse(f["best_is_unique"]); self.assertFalse(f["worst_is_unique"])
        low = result.text.lower()
        self.assertIn("рівень виконання однаковий для всіх 2 оцінених типів продукту", low)
        self.assertNotIn("найвищий рівень має «а»", low)
        self.assertNotIn("найнижчий рівень має «а»", low)

    def test_status_one_to_one_has_no_unique_dominant_status(self):
        ctx = _neutral_context()
        statuses = pd.DataFrame([
            {"status": "Виконано", "Кількість": 1},
            {"status": "Не виконано", "Кількість": 1},
        ])
        ctx = compat._rebuild(ctx, status_counts=statuses)
        _, _, _, result = _assert_clean_pipeline(self, ctx)
        f = ctx.factual_structure("status")
        self.assertFalse(f["dominant_is_unique"]); self.assertEqual(f["dominant_tie_count"], 2)
        low = result.text.lower()
        self.assertIn("єдиного найпоширенішого статусу немає", low)
        self.assertNotIn("найпоширеніший фактично зафіксований статус — «виконано»", low)
        self.assertNotIn("найпоширеніший фактично зафіксований статус — «не виконано»", low)

    def test_two_ssp_equal_portfolio_weight_have_no_unique_largest_ssp(self):
        ctx = _neutral_context()
        deps = pd.DataFrame([
            {"ssp_index": "1", "department": "ССП 1", "Виконання": 40.0, "Зміна": 0.0, "Унікальних_заходів": 5,
             "Актуальна_увага": 0, "Без_даних": 0, "portfolio_weight_pct": 50.0, "underperformance_contribution_pct": 70.0},
            {"ssp_index": "2", "department": "ССП 2", "Виконання": 60.0, "Зміна": 0.0, "Унікальних_заходів": 5,
             "Актуальна_увага": 0, "Без_даних": 0, "portfolio_weight_pct": 50.0, "underperformance_contribution_pct": 30.0},
        ])
        ctx = compat._rebuild(ctx, department_progress=deps)
        _, _, _, result = _assert_clean_pipeline(self, ctx)
        f = ctx.factual_structure("ssp.portfolio")
        self.assertFalse(f["largest_weight_is_unique"]); self.assertEqual(f["largest_weight_tie_count"], 2)
        low = result.text.lower()
        self.assertIn("єдиного найбільшого ссп за масштабом немає", low)
        self.assertNotIn("найбільший за масштабом портфель має ссп «ссп 1»", low)
        self.assertNotIn("найбільший за масштабом портфель має ссп «ссп 2»", low)


    def test_calculations_page_does_not_swallow_mio_registry_errors(self):
        source = Path("pages/9_Розрахунки.py").read_text(encoding="utf-8")
        self.assertNotIn("except Exception:\n                    mio = {}", source)
        self.assertIn("mio = mio_shared.build_mio_analytics", source)

    def test_unique_ssp_portfolio_sentence_normalizes_prefixed_label(self):
        ctx = _neutral_context()
        deps = pd.DataFrame([
            {"ssp_index": "1", "department": "ССП 1", "Виконання": 40.0, "Зміна": 0.0, "Унікальних_заходів": 7,
             "Актуальна_увага": 0, "Без_даних": 0, "portfolio_weight_pct": 70.0, "underperformance_contribution_pct": 80.0},
            {"ssp_index": "2", "department": "ССП 2", "Виконання": 80.0, "Зміна": 0.0, "Унікальних_заходів": 3,
             "Актуальна_увага": 0, "Без_даних": 0, "portfolio_weight_pct": 30.0, "underperformance_contribution_pct": 20.0},
        ])
        ctx = compat._rebuild(ctx, department_progress=deps)
        _, findings, _, result = _assert_clean_pipeline(self, ctx)
        self.assertIn("ssp_portfolio_impact", {item.code for item in findings})
        self.assertIn("ssp_portfolio_impact", compat._all_block_findings(result))
        self.assertNotIn("ССП «ССП ", result.text)
        self.assertIn("ССП 1", result.text)
        self.assertIn(
            "У розрізі відповідальних підрозділів найбільш вагомою негативною складовою є ССП 1",
            result.text,
        )

    def test_two_ssp_equal_underperformance_contribution_have_no_unique_negative_ssp_in_final(self):
        ctx = _neutral_context()
        deps = pd.DataFrame([
            {"ssp_index": "1", "department": "ССП 1", "Виконання": 40.0, "Зміна": 0.0, "Унікальних_заходів": 6,
             "Актуальна_увага": 0, "Без_даних": 0, "portfolio_weight_pct": 60.0, "underperformance_contribution_pct": 50.0},
            {"ssp_index": "2", "department": "ССП 2", "Виконання": 60.0, "Зміна": 0.0, "Унікальних_заходів": 4,
             "Актуальна_увага": 0, "Без_даних": 0, "portfolio_weight_pct": 40.0, "underperformance_contribution_pct": 50.0},
        ])
        ctx = compat._rebuild(ctx, department_progress=deps)
        _, findings, _, result = _assert_clean_pipeline(self, ctx)
        f = ctx.factual_structure("ssp.portfolio")
        self.assertFalse(f["top_underperformance_is_unique"]); self.assertEqual(f["top_underperformance_tie_count"], 2)
        self.assertIn("ssp_portfolio_impact", {item.code for item in findings})
        self.assertIn("ssp_portfolio_impact", compat._all_block_findings(result))
        self.assertNotIn("ССП «ССП ", result.text)
        self.assertIn("ССП 1", result.text)
        low = result.text.lower()
        self.assertIn("єдиного найбільш вагомого негативного ссп немає", low)
        self.assertNotIn("найбільш вагомою негативною складовою", low)
        self.assertNotIn("найбільша розрахована частка внеску в недовиконання припадає на ссп «ссп 1»", low)
        self.assertNotIn("найбільша розрахована частка внеску в недовиконання припадає на ссп «ссп 2»", low)


    def test_unique_department_missing_final_sentence_normalizes_prefixed_label(self):
        ctx = _neutral_context()
        deps = pd.DataFrame([
            {"ssp_index": "1", "department": "ССП 1", "Виконання": 45.0, "Зміна": 0.0, "Унікальних_заходів": 5,
             "Актуальна_увага": 0, "Без_даних": 3, "portfolio_weight_pct": 60.0, "underperformance_contribution_pct": 70.0},
            {"ssp_index": "2", "department": "ССП 2", "Виконання": 75.0, "Зміна": 0.0, "Унікальних_заходів": 5,
             "Актуальна_увага": 0, "Без_даних": 1, "portfolio_weight_pct": 40.0, "underperformance_contribution_pct": 30.0},
        ])
        metrics = dict(ctx.metrics); metrics["no_data"] = 4
        ctx = compat._rebuild(ctx, metrics=metrics, department_progress=deps)
        _, findings, _, result = _assert_clean_pipeline(self, ctx)
        missing = next(item for item in findings if item.code.startswith("department_missing_"))
        self.assertTrue(missing.facts.get("top_is_unique"))
        self.assertEqual(missing.facts.get("top_label"), "ССП 1")
        self.assertIn(missing.code, compat._all_block_findings(result))
        self.assertNotIn("ССП «ССП ", result.text)
        self.assertIn("ССП 1", result.text)
        self.assertIn("Основний осередок неповноти даних у розрізі ССП — ССП 1", result.text)

    def test_tied_distributed_department_missing_has_no_legacy_unique_final_sentence(self):
        ctx = _neutral_context()
        deps = pd.DataFrame([
            {"ssp_index": "1", "department": "ССП 1", "Виконання": 60.0, "Зміна": 0.0, "Унікальних_заходів": 5,
             "Актуальна_увага": 0, "Без_даних": 2, "portfolio_weight_pct": 50.0, "underperformance_contribution_pct": 50.0},
            {"ssp_index": "2", "department": "ССП 2", "Виконання": 60.0, "Зміна": 0.0, "Унікальних_заходів": 5,
             "Актуальна_увага": 0, "Без_даних": 2, "portfolio_weight_pct": 50.0, "underperformance_contribution_pct": 50.0},
        ])
        metrics = dict(ctx.metrics); metrics["no_data"] = 4
        ctx = compat._rebuild(ctx, metrics=metrics, department_progress=deps)
        _, findings, _, result = _assert_clean_pipeline(self, ctx)
        missing = next(item for item in findings if item.code.startswith("department_missing_"))
        self.assertEqual(missing.code, "department_missing_distributed")
        self.assertFalse(missing.facts.get("top_is_unique"))
        self.assertIn(missing.code, compat._all_block_findings(result))
        self.assertNotIn("ССП «ССП ", result.text)
        self.assertIn("ССП 1", result.text)
        self.assertNotIn("Основний осередок неповноти даних у розрізі ССП — ССП 1", result.text)
        self.assertIn("без єдиного найбільшого осередку", result.text.lower())

    def test_mio_one_goal_has_no_best_worst_comparison(self):
        ctx = _neutral_context()
        mio_goals = pd.DataFrame([
            {"Код": "1.", "Ціль": "Ціль 1", "Інтеграл 2026": 80.0, "Заходи 2026": 80.0, "Завдання 2026": 80.0, "Прогрес 2026": 80.0},
        ])
        ctx = compat._rebuild(ctx, mio_goal_evaluation=mio_goals)
        _, _, _, result = _assert_clean_pipeline(self, ctx)
        f = ctx.factual_structure("mio.goals")
        self.assertTrue(f["single_entity"]); self.assertEqual(f["goals_count"], 1)
        low = result.text.lower()
        self.assertIn("єдиної оціненої стратегічної цілі", low)
        self.assertNotIn("найвищий результат має 1.", low)
        self.assertNotIn("найнижчий результат має 1.", low)

    def test_mio_two_equal_goals_have_no_unique_best_worst(self):
        ctx = _neutral_context()
        mio_goals = pd.DataFrame([
            {"Код": code, "Ціль": f"Ціль {code}", "Інтеграл 2026": 80.0, "Заходи 2026": 80.0, "Завдання 2026": 80.0, "Прогрес 2026": 80.0}
            for code in ("1.", "2.")
        ])
        ctx = compat._rebuild(ctx, mio_goal_evaluation=mio_goals)
        _, _, _, result = _assert_clean_pipeline(self, ctx)
        f = ctx.factual_structure("mio.goals")
        self.assertTrue(f["all_equal"]); self.assertFalse(f["best_is_unique"]); self.assertEqual(f["best_tie_count"], 2)
        low = result.text.lower()
        self.assertIn("оцінені стратегічні цілі мають однаковий інтегральний результат", low)
        self.assertNotIn("найвищий результат має 1.", low)
        self.assertNotIn("найнижчий результат має 1.", low)

    def test_mio_one_task_has_no_best_worst_comparison(self):
        ctx = _neutral_context()
        mio_tasks = pd.DataFrame([
            {"Рівень": "task", "Код": "1.1.", "Оцінка 2026": 75.0},
        ])
        ctx = compat._rebuild(ctx, mio_goal_task_evaluation=mio_tasks)
        _, _, _, result = _assert_clean_pipeline(self, ctx)
        f = ctx.factual_structure("mio.tasks")
        self.assertTrue(f["single_entity"]); self.assertEqual(f["tasks_count"], 1)
        low = result.text.lower()
        self.assertIn("єдиного оціненого завдання", low)
        self.assertNotIn("найвищий результат має завдання 1.1.", low)
        self.assertNotIn("найнижчий результат має завдання 1.1.", low)

    def test_mio_two_equal_tasks_have_no_unique_best_worst(self):
        ctx = _neutral_context()
        mio_tasks = pd.DataFrame([
            {"Рівень": "task", "Код": "1.1.", "Оцінка 2026": 75.0},
            {"Рівень": "task", "Код": "1.2.", "Оцінка 2026": 75.0},
        ])
        ctx = compat._rebuild(ctx, mio_goal_task_evaluation=mio_tasks)
        _, _, _, result = _assert_clean_pipeline(self, ctx)
        f = ctx.factual_structure("mio.tasks")
        self.assertTrue(f["all_equal"]); self.assertFalse(f["best_is_unique"]); self.assertEqual(f["best_tie_count"], 2)
        low = result.text.lower()
        self.assertIn("оцінені завдання мають однаковий прогрес індикаторів", low)
        self.assertNotIn("найвищий результат має завдання 1.1.", low)
        self.assertNotIn("найнижчий результат має завдання 1.1.", low)


    def test_wide_department_movement_tie_has_no_arbitrary_unique_extremum(self):
        ctx = _neutral_context(completion=60.0)
        rows = []
        changes = [10.0, 10.0, -5.0, -5.0, 0.0, 0.0, 1.0, -1.0]
        for i, change in enumerate(changes, 1):
            rows.append({
                "ssp_index": str(i), "department": f"ССП {i}", "Виконання": 60.0 + change,
                "Зміна": change, "Унікальних_заходів": 10, "Актуальна_увага": 0, "Без_даних": 0,
                "portfolio_weight_pct": 12.5, "underperformance_contribution_pct": 12.5,
            })
        metrics = dict(ctx.metrics)
        metrics.update({"total_rows": 80, "unique_measures": 80, "latest_measure_count": 80})
        ctx = compat._rebuild(ctx, metrics=metrics, department_progress=pd.DataFrame(rows))
        _, _, _, result = _assert_clean_pipeline(self, ctx)
        f = ctx.factual_structure("department.change")
        self.assertFalse(f["largest_improvement_is_unique"])
        self.assertFalse(f["largest_deterioration_is_unique"])
        low = result.text.lower()
        self.assertIn("однаковий найбільший приріст мають", low)
        self.assertIn("однакове найбільше зниження мають", low)
        self.assertNotIn("найбільший приріст має ссп 1", low)
        self.assertNotIn("найбільше погіршення — ссп 3", low)

    def test_attention_top3_boundary_tie_does_not_claim_three_unique_largest_positions(self):
        ctx = compat._attention_context([6, 1, 1, 1])
        _, _, _, result = _assert_clean_pipeline(self, ctx)
        for kind in ("goal", "task", "department"):
            f = ctx.factual_structure(f"{kind}.attention")
            self.assertFalse(f["top3_boundary_unique"])
        self.assertNotIn("частка трьох найбільших позицій", result.text.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
