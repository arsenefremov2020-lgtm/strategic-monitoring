"""Regression tests for the experimental Dashboard interface.

Pure/static checks only; no GitHub or Supabase writes are performed.
Run from repository root:
    python scripts/test_dashboard_test_page.py
"""
from __future__ import annotations

import ast
import hashlib
import math
import sys
from types import SimpleNamespace
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.npa_documents import CANONICAL_NPA_DOCUMENTS  # noqa: E402
from core import dashboard_execution  # noqa: E402
from core.dashboard_matrices import (  # noqa: E402
    GROUP_DEPUTY,
    GROUP_SSP,
    all_groups,
    heatmap_payload,
    matrix_dataset,
    mosaic_frame,
    status_color,
)
from core.dashboard_portfolio import (  # noqa: E402
    build_portfolio_summary,
    canonical_documents,
    goal_sections,
    structural_portfolio,
)

PRODUCTION_DASHBOARD_SHA256 = "25c049bca422089957533460de52a1296c51c31eeaee172c9f50073f1295f56a"
REMOVED_PAGES = [
    "pages/0_Центр_задач.py",
    "pages/4_Картка_заходу_тест.py",
    "pages/B_Довідка.py",
    "pages/9_Розрахунки.py",
]


def _measure(i: int, *, ssp: int = 20, goal: str = "1", task: str = "1.1", source_global: str = "", source_national: str = "") -> dict:
    return {
        "object_type": "measure",
        "code": f"{goal}.{task.split('.')[-1]}.{i:04d}",
        "name": f"Measure {i}",
        "parent_goal_code": goal,
        "parent_goal_name": f"Goal {goal}",
        "parent_task_code": task,
        "parent_task_name": f"Task {task}",
        "resp_main": f"ССП {ssp}",
        "product_type": "НПА" if i % 2 else "Інше",
        "source_global": source_global,
        "source_national": source_national,
        "budget_kpkvk": f"{1000 + (i % 3)}",
        "financing_state_budget": "так" if i % 2 else "",
    }


def _snapshot_row(code: str, *, ssp: int, goal: str, task: str, status: str, execution: float | None) -> dict:
    return {
        "code": code,
        "parent_goal_code": goal,
        "parent_goal_name": f"Goal {goal}",
        "parent_task_code": task,
        "parent_task_name": f"Task {task}",
        "resp_main": f"ССП {ssp}",
        "status_display": status,
        "status": status,
        "execution_score": execution,
        "monitoring_conducted": True,
        "coverage_eligible": status not in {"Не настав час", "Втратило актуальність"},
        "submitted": status != "Не подано",
    }


def test_file_and_navigation_contract() -> None:
    prod = ROOT / "pages/2_Dashboard.py"
    test_page = ROOT / "pages/2_Дашборди_тест.py"
    assert prod.exists() and test_page.exists()
    assert hashlib.sha256(prod.read_bytes()).hexdigest() == PRODUCTION_DASHBOARD_SHA256
    for rel in REMOVED_PAGES:
        assert not (ROOT / rel).exists(), rel

    roles = (ROOT / "config/roles.py").read_text(encoding="utf-8")
    navigation = (ROOT / "core/navigation.py").read_text(encoding="utf-8")
    page = test_page.read_text(encoding="utf-8")
    assert roles.count('"Дашборди (тест)"') == 2  # super-admin + ALL_PAGES only
    assert '"Дашборди (тест)": "pages/2_Дашборди_тест.py"' in navigation
    assert 'page_setup("Дашборди (тест)", page_name="Дашборди (тест)")' in page
    for removed in ("Центр задач", "Картка заходу (тест)", '"Довідка"', '"Розрахунки"'):
        assert removed not in roles
        assert removed not in navigation


def test_only_active_mode_is_built() -> None:
    page = (ROOT / "pages/2_Дашборди_тест.py").read_text(encoding="utf-8")
    assert "st.tabs(" not in page
    # The test page has a single mutually exclusive branch for all four contexts.
    assert "if active_analytic_mode == MODE_SNAPSHOT:" in page
    assert "elif active_analytic_mode == MODE_BREAKDOWN:" in page
    assert "elif active_analytic_mode == MODE_DYNAMICS:" in page
    assert "finance_context = _build_finance_context(selected_finance_year)" in page
    legacy_eager = "snapshot_context = _build_dashboard_context(snapshot_pairs)\nbreakdown_context = _build_dashboard_context(breakdown_pairs)"
    assert legacy_eager not in page
    # Presentation is explicitly snapshot-only.
    assert "if presentation_mode:\n    active_analytic_mode = MODE_SNAPSHOT" in page


def test_structural_portfolio_and_canonical_npa() -> None:
    d1, d2 = CANONICAL_NPA_DOCUMENTS[:2]
    rows = [
        _measure(1, ssp=20, goal="1", task="1.1", source_global=f"{d1}; {d2}"),
        _measure(2, ssp=21, goal="1", task="1.2", source_national=d1),
        _measure(3, ssp=22, goal="2", task="2.1", source_global=f"Додатковий текст — {d2}"),
        _measure(4, ssp=23, goal="2", task="2.2", source_global="Не канонічний документ"),
    ]
    df = pd.DataFrame(rows)
    portfolio = structural_portfolio(df)
    docs = canonical_documents(portfolio)
    assert set(docs) == {d1, d2}
    summary = build_portfolio_summary(portfolio)
    assert summary["measure_count"] == 4
    assert summary["ssp_count"] == 4
    assert summary["goal_count"] == 2
    assert summary["task_count"] == 4
    assert summary["npa_count"] == 2

    # Structural filters use the same Dashboard filter implementation.
    narrowed = structural_portfolio(df, ssp=["21"], goals=["1"], tasks=["1.2"], product_types=["Інше"])
    assert narrowed["code"].tolist() == [rows[1]["code"]]


def test_large_portfolio_keeps_every_ssp_and_goal() -> None:
    rows = []
    for i in range(35):
        ssp = 20 + i
        goal = str(1 + (i % 4))
        task = f"{goal}.{1 + (i % 5)}"
        rows.append(_measure(i + 1, ssp=ssp, goal=goal, task=task))
    df = pd.DataFrame(rows)
    summary = build_portfolio_summary(df)
    assert summary["measure_count"] == 35
    assert summary["ssp_count"] == 35
    assert len(summary["ssps"]) == 35
    assert len(all_groups(df, GROUP_SSP)) == 35
    sections = goal_sections(df)
    assert sum(section["measure_count"] for section in sections) == 35
    assert math.isclose(sum(section["portfolio_share_pct"] for section in sections), 100.0, abs_tol=1e-9)

    page = (ROOT / "pages/2_Дашборди_тест.py").read_text(encoding="utf-8")
    assert "Ще +{remaining}" in page
    assert "dashboard-test-scroll-list" in page
    assert ".head(" not in (ROOT / "core/dashboard_matrices.py").read_text(encoding="utf-8")
    assert '"Інше"' not in (ROOT / "core/dashboard_matrices.py").read_text(encoding="utf-8")


def test_matrix_views_share_same_measure_population_and_canonical_execution() -> None:
    snapshot = pd.DataFrame([
        _snapshot_row("m1", ssp=20, goal="1", task="1.1", status="Виконано", execution=100.0),
        _snapshot_row("m2", ssp=20, goal="1", task="1.1", status="Частково виконано", execution=50.0),
        _snapshot_row("m3", ssp=21, goal="1", task="1.1", status="Не виконано", execution=0.0),
        _snapshot_row("m4", ssp=21, goal="1", task="1.2", status="Не настав час", execution=None),
        _snapshot_row("m5", ssp=22, goal="2", task="2.1", status="Виконано", execution=100.0),
    ])

    for grouping in (GROUP_SSP, GROUP_DEPUTY):
        dataset = matrix_dataset(snapshot, grouping)
        assert set(dataset["code"]) == set(snapshot["code"])
        assert dataset["code"].is_unique

        # Mosaic preserves every unique measure exactly once across status leaves for a goal.
        mosaic = mosaic_frame(dataset, "1")
        assert int(mosaic["measure_count"].sum()) == 4

        groups = all_groups(snapshot, grouping)
        heat = heatmap_payload(dataset, "1", groups)
        heat_count = sum(cell["measure_count"] for cell in heat["cells"].values())
        assert heat_count == 4

        # Every populated heat cell must exactly match canonical snapshot_execution on that subset.
        for task_code, _ in heat["tasks"]:
            for group in groups:
                cell = heat["cells"][(task_code, group)]
                subset = dataset[(dataset["goal_code"] == "1") & (dataset["task_code"] == task_code) & (dataset["group"] == group)]
                canonical = dashboard_execution.snapshot_execution(subset)
                expected = canonical["execution_by_measures"]
                actual = cell["execution"]
                if expected is None:
                    assert actual is None
                else:
                    assert math.isclose(float(actual), float(expected), abs_tol=1e-12)


def test_matrix_status_palette_and_lazy_rendering_contract() -> None:
    expected = {
        "Виконано": "#118847",
        "Частково виконано": "#F4B400",
        "Не виконано": "#DC4A4A",
        "Не подано": "#B42318",
        "Не настав час": "#8A96A8",
        "Втратило актуальність": "#5B21B6",
        "Не визначено": "#61708A",
    }
    assert {key: status_color(key) for key in expected} == expected

    page = (ROOT / "pages/2_Дашборди_тест.py").read_text(encoding="utf-8")
    assert 'st.session_state.setdefault("dashboard_test_expanded_goals", [])' in page
    assert 'st.button("Розгорнути все"' in page
    assert 'st.button("Згорнути все"' in page
    assert "code in expanded_codes" in page
    assert "if not expanded:\n            continue" in page
    lazy_index = page.index("if not expanded:\n            continue")
    snapshot_index = page.index("matrix_snapshot = _build_matrix_snapshot", lazy_index)
    assert snapshot_index > lazy_index
    assert page.index("px.treemap(", snapshot_index) > snapshot_index
    assert page.index("heatmap_payload(", snapshot_index) > snapshot_index
    # Only the portfolio details may use an expander; goal graphs do not.
    matrix_start = page.index("def _render_goal_achievement_matrices")
    matrix_end = page.index("if not presentation_mode and active_analytic_mode == MODE_SNAPSHOT", matrix_start)
    assert "st.expander(" not in page[matrix_start:matrix_end]


def test_global_status_filter_does_not_narrow_matrix_snapshot() -> None:
    """Regression for the release-blocking status-cohort plumbing bug."""
    page_path = ROOT / "pages/2_Дашборди_тест.py"
    tree = ast.parse(page_path.read_text(encoding="utf-8"))
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_build_matrix_snapshot"
    )
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)

    full_snapshot = pd.DataFrame([
        _snapshot_row("m1", ssp=20, goal="1", task="1.1", status="Виконано", execution=100.0),
        _snapshot_row("m2", ssp=20, goal="1", task="1.1", status="Частково виконано", execution=50.0),
        _snapshot_row("m3", ssp=21, goal="1", task="1.1", status="Не виконано", execution=0.0),
        _snapshot_row("m4", ssp=21, goal="1", task="1.2", status="Не настав час", execution=None),
    ])
    captured = {}

    def fake_build_period_results(strat_df, requests_df, pairs, **kwargs):
        captured["stable_statuses"] = kwargs.get("stable_statuses")
        return {(2026, "III"): {"snapshot": full_snapshot.copy()}}

    fake_breakdowns = SimpleNamespace(
        build_period_results=fake_build_period_results,
        filter_results_by_ssp=lambda results, selected: results,
    )
    namespace = {
        "pd": pd,
        "dashboard_breakdowns_v2": fake_breakdowns,
        "_dashboard_structural_base": lambda: pd.DataFrame([_measure(1)]),
        "requests_df": pd.DataFrame(),
        "_build_period_source_overrides": lambda pairs, ssp_filter=None: {},
        "selected_department_indices": [],
        # Deliberately active globally: the matrix helper must not use it.
        "selected_statuses": ["Виконано"],
        "quarter_to_roman": lambda value: str(value),
        "core_period_number": lambda year, quarter: int(year) * 10 + {"I": 1, "II": 2, "III": 3, "IV": 4}[quarter],
    }
    exec(compile(module, str(page_path), "exec"), namespace)
    matrix_snapshot = namespace["_build_matrix_snapshot"]([(2026, "III")])

    assert captured["stable_statuses"] is None
    assert set(matrix_snapshot["status_display"]) == {
        "Виконано", "Частково виконано", "Не виконано", "Не настав час"
    }
    assert len(matrix_snapshot) == 4

    page = page_path.read_text(encoding="utf-8")
    assert "_render_goal_achievement_matrices(snapshot_pairs)" in page
    assert "_render_goal_achievement_matrices(active)" not in page


def test_portfolio_is_structural_not_status_bound() -> None:
    source = (ROOT / "core/dashboard_portfolio.py").read_text(encoding="utf-8")
    assert "statuses=" not in source
    assert "Status is deliberately absent" in source


def run() -> None:
    tests = [name for name, value in globals().items() if name.startswith("test_") and callable(value)]
    for name in sorted(tests):
        globals()[name]()
        print(f"PASS {name}")
    print(f"PASS {len(tests)} dashboard-test regression checks")


if __name__ == "__main__":
    run()
