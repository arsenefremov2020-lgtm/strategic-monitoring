"""Єдиний безпечний запис дій у журнал системи.

Модуль навмисно сумісний зі старою схемою таблиці ``monitoring_logs``:
спочатку пробує записати розширений аудит, а якщо відповідні колонки ще
не додані міграцією DEMO 1.9 — автоматично робить fallback на старі поля.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from core.errors import create_incident_code, log_exception


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def actor_identity(user: dict | None, fallback_role: str = "") -> dict[str, str]:
    """Повертає стандартизований опис користувача для журналу."""
    user = user or {}
    role = _safe_text(user.get("role") or fallback_role)
    return {
        "actor_email": _safe_text(user.get("email")).lower(),
        "actor_name": _safe_text(user.get("full_name") or user.get("name") or user.get("email")),
        "actor_role": role,
    }


def compact_payload(data: dict | None) -> str:
    """JSON для службових деталей журналу, без падіння на несеріалізованих типах."""
    if not data:
        return ""
    try:
        return json.dumps(data, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"raw": str(data)}, ensure_ascii=False)


def write_audit_log(
    supabase,
    *,
    request_id: int | str | None = None,
    action: str,
    old_status: str | None = None,
    new_status: str | None = None,
    comment: str | None = None,
    user: dict | None = None,
    fallback_role: str = "system",
    ssp_index: str | None = None,
    strat_code: str | None = None,
    related_table: str = "monitoring_requests",
    related_key: str | None = None,
    details: dict | None = None,
) -> bool:
    """Записує дію в ``monitoring_logs``.

    Повертає True/False, але не ламає користувацький сценарій, якщо журнал
    тимчасово недоступний. Для тестування помилки можна дивитися у Supabase logs.
    """
    actor = actor_identity(user, fallback_role=fallback_role)
    now_iso = datetime.now(timezone.utc).isoformat()
    rid = None
    try:
        if request_id not in (None, "", "nan"):
            rid = int(float(str(request_id)))
    except Exception:
        rid = None

    extended_payload = {
        "request_id": rid,
        "action": _safe_text(action),
        "old_status": _safe_text(old_status),
        "new_status": _safe_text(new_status),
        "admin_comment": _safe_text(comment),
        "changed_by": actor["actor_email"] or actor["actor_name"] or actor["actor_role"],
        "changed_at": now_iso,
        "actor_email": actor["actor_email"],
        "actor_name": actor["actor_name"],
        "actor_role": actor["actor_role"],
        "ssp_index": _safe_text(ssp_index),
        "strat_code": _safe_text(strat_code),
        "related_table": _safe_text(related_table),
        "related_key": _safe_text(related_key),
        "payload_json": compact_payload(details),
    }

    legacy_payload = {
        "request_id": rid,
        "action": _safe_text(action),
        "old_status": _safe_text(old_status),
        "new_status": _safe_text(new_status),
        "admin_comment": _safe_text(comment),
        "changed_by": actor["actor_email"] or actor["actor_name"] or actor["actor_role"],
    }

    try:
        supabase.table("monitoring_logs").insert(extended_payload).execute()
        return True
    except Exception as extended_exc:
        try:
            supabase.table("monitoring_logs").insert(legacy_payload).execute()
            return True
        except Exception as legacy_exc:
            incident_code = create_incident_code()
            log_exception(
                "Запис аудиту в розширеному форматі не виконано",
                extended_exc,
                incident_code=incident_code,
            )
            log_exception(
                "Запис аудиту в сумісному форматі також не виконано",
                legacy_exc,
                incident_code=incident_code,
            )
            return False
