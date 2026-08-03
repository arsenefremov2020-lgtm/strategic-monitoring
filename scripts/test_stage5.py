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
    coordinator_request = pd.Series({
        "id": 101,
        "approval_status": "На розгляді координатора",
        "approval_chain": (
            '[{"role":"admin","label":"Координатор",'
            '"email":"coord@example.com"}]'
        ),
        "chain_stage": 0,
        "_stage_since": six_days_ago,
    })
    coordinator = {"email": "coord@example.com", "role": "admin"}
    manager = {"email": "head@example.com", "role": "ssp_head"}
    check(
        module._request_waits_for_user(coordinator_request, coordinator),
        "Координатор отримує заявку лише на своїй поточній ланці",
    )
    check(
        not module._request_waits_for_user(coordinator_request, manager),
        "Керівник не отримує заявку до вибору керівницької ланки",
    )

    manager_request = pd.Series({
        "id": 102,
        "approval_status": "На розгляді керівника",
        "approval_chain": (
            '[{"role":"admin","label":"Координатор",'
            '"email":"coord@example.com"},'
            '{"role":"ssp_head","label":"Керівник ССП",'
            '"email":"head@example.com"}]'
        ),
        "chain_stage": 1,
        "_stage_since": six_days_ago,
    })
    check(
        module._request_waits_for_user(manager_request, manager),
        "Керівник отримує заявку, коли він є поточною ланкою",
    )
    check(
        not module._request_waits_for_user(manager_request, coordinator),
        "Координатор не отримує заявку, яка вже перейшла керівнику",
    )

    keepalive = (ROOT / ".github" / "workflows" / "keepalive.yml").read_text(encoding="utf-8")
    check("|| true" not in keepalive, "Keepalive не приховує помилки")
    check("--fail" in keepalive and "3" in keepalive, "Keepalive має fail і три спроби")

    workflow = (ROOT / ".github" / "workflows" / "notifications.yml").read_text(encoding="utf-8")
    check('30 5 * * 1-5' in workflow and '30 13 * * 1-5' in workflow,
          "Workflow має ранковий і вечірній UTC-розклади")

    migration = (ROOT / "migrations" / "014_stage5_administration_notifications.sql").read_text(encoding="utf-8")
    check("uq_closeout_requests_active_period" in migration,
          "Міграція містить частковий унікальний індекс активних закриттів")
    check("materialize_closeout_requests" in migration,
          "Міграція матеріалізує фактичні дані ручного закриття")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
