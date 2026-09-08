#!/usr/bin/env python3
"""Статичні та локальні перевірки ДЕМО 2.0, Етап 6."""

from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys
import types
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Локальний тест не потребує Streamlit/Supabase: підміняємо лише імпортні залежності.
core_db = types.ModuleType("core.db")
core_db.fetch_all = lambda *args, **kwargs: []
core_strategic = types.ModuleType("core.strategic_data")
core_strategic.load_strat_matrix = lambda: pd.DataFrame()
sys.modules.setdefault("core.db", core_db)
sys.modules.setdefault("core.strategic_data", core_strategic)

from core.archive import (  # noqa: E402
    build_mio_snapshot,
    decode_snapshot_payload,
    export_snapshot_docx,
    export_snapshot_excel,
    export_snapshot_pdf,
    snapshot_marker,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def main() -> int:
    # 1. Стиснення / розпакування.
    payload = {"schema_version": "TEST", "monitoring_requests": [{"id": 1}]}
    encoded = base64.b64encode(
        gzip.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    ).decode("ascii")
    check(decode_snapshot_payload(encoded) == payload, "gzip+base64 знімок розпаковується без втрат")

    # 2. МіО фіксує складові за кварталами та підсумок ССП.
    strat = pd.DataFrame([
        {
            "object_type": "measure",
            "code": "1.1.1.",
            "name": "Тестовий захід",
            "resp_main": "ССП 1",
            "unit": "%",
            "target_2026": 100,
            "target_2027": 100,
            "target_2028": 100,
            "parent_goal_code": "1.",
            "parent_goal_name": "Ціль",
            "parent_task_code": "1.1.",
            "parent_task_name": "Завдання",
            "indicator": "Індикатор",
        }
    ])
    requests = [
        {
            "id": 1,
            "object_kind": "measure",
            "strat_code": "1.1.1.",
            "year": 2026,
            "quarter": 1,
            "approval_status": "Погоджено",
            "status": "Виконано",
            "numeric_value": 25,
            "submitted_at": "2026-04-01T10:00:00+00:00",
        }
    ]
    detail, summary = build_mio_snapshot(strat, requests)
    check(len(detail) == 3 and len(summary) == 3, "МіО архіву містить усі три роки та підсумки ССП")
    check(detail[0]["Факт · I кв"] == 25, "МіО архіву фіксує фактичне квартальне значення")

    # 3. Усі три формати експорту містять архівну позначку.
    snapshot = {
        "id": 1,
        "archived_at": "2026-07-15T15:00:00+00:00",
        "archived_by": "Тест",
        "snapshot_type": "manual",
        "coverage_label": "I–II кв. 2026",
        "reason": "Тест",
    }
    export_payload = {
        "main_table": [{"Код": "1.1.1."}],
        "monitoring_requests": [{"id": 1, "strat_code": "1.1.1."}],
        "monitoring_request_versions": [],
        "mio_components": [],
        "mio_ssp_summary": [{"Рік": 2026, "ССП": "ССП 1"}],
        "monitoring_logs": [{"action": "Тест"}],
        "closeout_requests": [],
    }
    marker = snapshot_marker(snapshot)
    xlsx = export_snapshot_excel(snapshot, export_payload)
    docx = export_snapshot_docx(snapshot, export_payload)
    pdf = export_snapshot_pdf(snapshot, export_payload)
    check(len(xlsx) > 1000 and len(docx) > 1000 and len(pdf) > 1000, "Excel, Word і PDF архіву формуються")
    check(marker.startswith("Сформовано з архівного знімка від"), "Експорт має обов’язкову архівну позначку")

    # 4. Навігація і доступи. Видалені сторінки не лишають битих маршрутів;
    # тестовий Dashboard доступний тільки супер-адміну.
    roles_text = (ROOT / "config" / "roles.py").read_text(encoding="utf-8")
    navigation_text = (ROOT / "core" / "navigation.py").read_text(encoding="utf-8")
    for removed in ("Центр задач", "Картка заходу (тест)", "Довідка", "Розрахунки"):
        check(f'"{removed}"' not in roles_text, f"{removed}: прибрано з рольових списків")
        check(f'"{removed}":' not in navigation_text, f"{removed}: прибрано з маршрутів")
    check('"Архів": "pages/A_Архів.py"' in navigation_text, "Архів підключено до рольового меню")
    check('"Дашборди (тест)": "pages/2_Дашборди_тест.py"' in navigation_text, "Тестовий Dashboard підключено")
    check(roles_text.count('"Дашборди (тест)"') == 2, "Тестовий Dashboard є лише у super_admin та ALL_PAGES")

    # 5. Футер.
    config_text = (ROOT / "core" / "config.py").read_text(encoding="utf-8")
    footer_text = (ROOT / "core" / "page_setup.py").read_text(encoding="utf-8")
    check('APP_VERSION: str = "ДЕМО 2.0"' in config_text, "Версія системи у футері — ДЕМО 2.0")
    check(
        "Розроблено департаментом стратегічного планування" in footer_text
        and "Версія {APP_VERSION}" in footer_text,
        "Футер перевіряється за чинним production-контрактом, без застарілої контактної адреси",
    )

    # 6. Незмінність і автоматичний workflow закладені в коді/SQL.
    migration = (ROOT / "migrations" / "015_archive_full.sql").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "archive_snapshot.yml").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "create_archive_snapshot.py").read_text(encoding="utf-8")
    archive_page = (ROOT / "pages" / "A_Архів.py").read_text(encoding="utf-8")
    check("trg_archive_snapshots_immutable" in migration and "before update or delete" in migration.lower(), "SQL блокує UPDATE і DELETE знімків")
    check(
        'cron: "0 15 15 1,4,7,10 *"' in workflow and workflow.count("cron:") == 1,
        "Workflow використовує чинний єдиний квартальний UTC-розклад",
    )
    check(
        "now_kyiv()" in script and "now.day in {15, 16}" in script and "now.hour ==" not in script,
        "Автознімок використовує Europe/Kyiv через now_kyiv і date-driven grace window",
    )
    check(".update(" not in archive_page and ".delete(" not in archive_page, "Сторінка Архіву не містить дій редагування або видалення")

    print("OK: перевірки Етапу 6 завершено.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
