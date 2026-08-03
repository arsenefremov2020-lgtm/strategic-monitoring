"""Smoke tests for DEMO 2.0 Stage 4.

Run from the repository root:
    python scripts/test_stage4.py

The script uses only synthetic data, does not connect to Supabase, and does not
modify any application data.
"""

from __future__ import annotations

import sys
import types
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import streamlit  # noqa: F401
except ImportError:
    # The pure Stage 4 helpers only need Streamlit at import time. A tiny stub
    # lets this smoke test run in a minimal CI/container without the UI package.
    streamlit_stub = types.ModuleType("streamlit")
    streamlit_stub.session_state = {}
    streamlit_stub.query_params = {}
    streamlit_stub.__path__ = []
    sys.modules["streamlit"] = streamlit_stub

from core.stage4 import (  # noqa: E402
    build_approval_speed_analytics,
    build_measure_card_pdf,
    build_return_analytics,
    human_versions_table,
    version_differences,
)
from core.ui import prepare_human_log_table  # noqa: E402


def _synthetic_requests() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": 1,
                "department": "40",
                "strat_code": "1.1.1.",
                "year": 2026,
                "quarter": 1,
                "responsible_person": "Тестова відповідальна особа",
                "approval_status": "Погоджено",
                "submitted_at": "2026-07-01T08:00:00Z",
                "chain_stage": 1,
                "approval_chain": (
                    '[{"role":"admin","label":"Координатор"},'
                    '{"role":"ssp_head","label":"Керівник ССП"}]'
                ),
                "status": "Виконано",
                "numeric_value": 10,
                "value_text": None,
                "progress_text": "Довгий опис прогресу " * 20,
                "risks": "Ризик " * 20,
            },
            {
                "id": 2,
                "department": "56",
                "strat_code": "2.1.1.",
                "year": 2026,
                "quarter": 1,
                "responsible_person": "Тестова особа 2",
                "approval_status": "На розгляді керівника",
                "submitted_at": "2026-07-02T08:00:00Z",
                "chain_stage": 1,
                "approval_chain": (
                    '[{"role":"admin","label":"Координатор"},'
                    '{"role":"ssp_head","label":"Керівник ССП"}]'
                ),
                "status": "Частково виконано",
                "numeric_value": 5,
                "value_text": None,
                "progress_text": "Прогрес",
                "risks": "",
            },
        ]
    )


def _synthetic_logs() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "request_id": 1,
                "changed_at": "2026-07-01T09:00:00Z",
                "action": "Погодження координатором",
                "old_status": "На розгляді координатора",
                "new_status": "На розгляді керівника",
                "actor_role": "admin",
                "actor_name": "Координатор",
                "changed_by": "Адміністратор · Координатор",
                "admin_comment": "",
            },
            {
                "request_id": 1,
                "changed_at": "2026-07-02T09:00:00Z",
                "action": "Повернення на доопрацювання",
                "old_status": "На розгляді керівника",
                "new_status": "Повернуто на доопрацювання керівником",
                "actor_role": "ssp_head",
                "actor_name": "Керівник",
                "changed_by": "Керівник ССП · Керівник",
                "admin_comment": "Виправити",
            },
            {
                "request_id": 1,
                "changed_at": "2026-07-03T09:00:00Z",
                "action": "Повторне подання",
                "old_status": "Повернуто на доопрацювання керівником",
                "new_status": "На розгляді координатора",
                "actor_role": "ssp",
                "actor_name": "Подавач",
                "changed_by": "ССП · Подавач",
                "admin_comment": "",
            },
            {
                "request_id": 1,
                "changed_at": "2026-07-03T10:00:00Z",
                "action": "Погодження координатором",
                "old_status": "На розгляді координатора",
                "new_status": "На розгляді керівника",
                "actor_role": "admin",
                "actor_name": "Координатор",
                "changed_by": "Адміністратор · Координатор",
                "admin_comment": "",
            },
            {
                "request_id": 1,
                "changed_at": "2026-07-04T10:00:00Z",
                "action": "Погодження керівником",
                "old_status": "На розгляді керівника",
                "new_status": "Погоджено",
                "actor_role": "ssp_head",
                "actor_name": "Керівник",
                "changed_by": "Керівник ССП · Керівник",
                "admin_comment": "",
            },
            {
                "request_id": 2,
                "changed_at": "2026-07-02T10:00:00Z",
                "action": "Погодження координатором",
                "old_status": "На розгляді координатора",
                "new_status": "На розгляді керівника",
                "actor_role": "admin",
                "actor_name": "Координатор",
                "changed_by": "Адміністратор · Координатор",
                "admin_comment": "",
            },
        ]
    )


def test_return_analytics() -> None:
    result = build_return_analytics(_synthetic_logs(), _synthetic_requests())
    assert result["total_returns"] == 1
    assert result["average_per_request"] == 0.5
    assert int(result["by_department"]["Кількість повернень"].sum()) == 1


def test_approval_speed() -> None:
    result = build_approval_speed_analytics(
        _synthetic_logs(),
        _synthetic_requests(),
        now=datetime(2026, 7, 10, 12, tzinfo=ZoneInfo("Europe/Kyiv")),
    )
    assert result["completed_requests"] == 1
    assert result["average_total_days"] == 3.08
    assert len(result["hanging"]) == 1
    assert result["hanging"].iloc[0]["Поточна ланка"] == "Керівник ССП"


def test_human_versions() -> None:
    versions = pd.DataFrame(
        [
            {
                "version_number": 1,
                "created_at": "2026-07-01T08:00:00Z",
                "created_by": "A",
                "approval_status": "На розгляді координатора",
                "status": "Не виконано",
                "numeric_value": 1,
                "progress_text": "a",
                "risks": "",
            },
            {
                "version_number": 2,
                "created_at": "2026-07-02T08:00:00Z",
                "created_by": "B",
                "approval_status": "Погоджено",
                "status": "Виконано",
                "numeric_value": 2,
                "progress_text": "b",
                "risks": "",
            },
        ]
    )
    table = human_versions_table(versions)
    assert list(table.columns)[0] == "Версія"
    assert table.iloc[1]["Фактичне значення"] == "2"
    assert not any(column.lower().endswith("_id") for column in table.columns)

    differences = version_differences(versions.iloc[0], versions.iloc[1])
    assert set(differences["Поле"]) == {
        "Статус виконання",
        "Статус погодження",
        "Фактичне числове значення",
        "Опис прогресу",
    }
    assert list(differences.columns) == ["Поле", "Було", "Стало"]


def test_human_log_history() -> None:
    raw = _synthetic_logs().copy()
    raw["id"] = range(1, len(raw) + 1)
    raw["payload_json"] = "{}"
    table = prepare_human_log_table(raw)
    assert list(table.columns) == [
        "Дата і час",
        "Дія",
        "Попередній статус",
        "Новий статус",
        "Коментар",
        "Ким змінено",
    ]
    assert table.iloc[0]["Дата і час"] == "01.07.2026 12:00"
    assert "id" not in {column.lower() for column in table.columns}


def test_pdf() -> None:
    measure = {
        "code": "1.1.1.",
        "name": "Надзвичайно довга назва заходу " * 25,
        "indicator": "Довгий індикатор " * 20,
        "unit": "відсоток",
        "department": "ССП 40",
        "department_co_1": "ССП 41",
        "department_co_2": "ССП 42",
        "period": "2026-2028",
        "target_2026": "10",
        "target_2027": "20",
        "target_2028": "30",
    }
    pdf = build_measure_card_pdf(
        measure=measure,
        goal_name="Довга стратегічна ціль " * 20,
        task_name="Довге стратегічне завдання " * 20,
        requests_df=_synthetic_requests().iloc[[0]],
        logs_df=_synthetic_logs().query("request_id == 1"),
        focus_year=2026,
        focus_quarter="I",
        closed_periods=["I кв. 2026"],
    )
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 20_000
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "stage4_card.pdf"
        path.write_bytes(pdf)
        assert path.stat().st_size == len(pdf)


def main() -> None:
    tests = [
        test_return_analytics,
        test_approval_speed,
        test_human_versions,
        test_human_log_history,
        test_pdf,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"Stage 4 smoke tests passed: {len(tests)}/{len(tests)}")


if __name__ == "__main__":
    main()
