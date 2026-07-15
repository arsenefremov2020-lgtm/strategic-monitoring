#!/usr/bin/env python3
"""Static/unit checks for DEMO 2.0 Stage 5 without external services."""

from __future__ import annotations

import importlib.util
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# send_notifications only needs these names while importing.
core_db = types.ModuleType("core.db")
core_db.fetch_all = lambda *args, **kwargs: []
core_emails = types.ModuleType("core.emails")
core_emails.send_email = lambda *args, **kwargs: (True, None)
sys.modules.setdefault("core.db", core_db)
sys.modules.setdefault("core.emails", core_emails)

spec = importlib.util.spec_from_file_location(
    "stage5_notifications", ROOT / "scripts" / "send_notifications.py"
)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def main() -> int:
    check(module.now_kyiv().tzinfo is not None, "Київський час timezone-aware")
    check(
        getattr(module.now_kyiv().tzinfo, "key", "") == "Europe/Kyiv",
        "Використовується Europe/Kyiv, а не фіксований UTC-зсув",
    )

    six_days_ago = (datetime.now(timezone.utc) - timedelta(days=6, hours=2)).isoformat()
    requests = pd.DataFrame([
        {
            "id": 101,
            "strat_code": "1.2.3.",
            "year": "2026",
            "quarter": "II",
            "approval_status": "Очікує: Керівник управління",
            "approval_chain": (
                '[{"role":"unit_head","label":"Керівник управління",'
                '"email":"current@example.com"},'
                '{"role":"ssp_head","label":"Керівник ССП",'
                '"email":"last@example.com"}]'
            ),
            "chain_stage": 0,
            "submitted_at": six_days_ago,
            "_stage_since": six_days_ago,
        }
    ])
    users = [
        {"email": "current@example.com", "role": "unit_head"},
        {"email": "last@example.com", "role": "ssp_head"},
        {"email": "super@example.com", "role": "super_admin"},
    ]
    escalations = module.build_escalations(requests, users)
    check(set(escalations) == {"current@example.com", "last@example.com", "super@example.com"},
          "Ескалацію отримують поточна ланка, остання ланка і супер-адмін")
    check(escalations["current@example.com"][0]["days"] > 5,
          "До ескалації потрапляє заявка, що очікує понад 5 днів")

    keepalive = (ROOT / ".github" / "workflows" / "keepalive.yml").read_text(encoding="utf-8")
    check("|| true" not in keepalive, "Keepalive не приховує помилки")
    check("--fail" in keepalive and "3" in keepalive, "Keepalive має fail і три спроби")

    workflow = (ROOT / ".github" / "workflows" / "notifications.yml").read_text(encoding="utf-8")
    check('30 5 * * 1-5' in workflow and '30 6 * * 1-5' in workflow,
          "Workflow має два сезонні UTC-розклади")

    migration = (ROOT / "migrations" / "014_stage5_administration_notifications.sql").read_text(encoding="utf-8")
    check("uq_closeout_requests_active_period" in migration,
          "Міграція містить частковий унікальний індекс активних закриттів")
    check("materialize_closeout_requests" in migration,
          "Міграція матеріалізує фактичні дані ручного закриття")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
