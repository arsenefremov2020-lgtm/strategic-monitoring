"""Особисті автоматичні чернетки форм подання і повторного подання."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from core.db import fetch_all, get_supabase_client
from core.errors import show_warning

KYIV_TZ = ZoneInfo("Europe/Kyiv")
LOGGER = logging.getLogger(__name__)
_PENDING_KEY = "monitoring_draft_pending_operations"
_SAVED_HASHES_KEY = "monitoring_draft_saved_hashes"


def _clean(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null", "nat"} else text


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception as exc:
            LOGGER.debug("Значення чернетки не приведено через item(): %s", exc)
    return value


def make_draft_key(
    object_kind: str,
    strat_code: Any,
    year: Any,
    quarter: Any,
    *,
    mode: str = "submit",
    request_id: int | None = None,
) -> str:
    parts = [
        _clean(object_kind).lower() or "measure",
        _clean(strat_code),
        _clean(year),
        _clean(quarter),
        _clean(mode).lower() or "submit",
    ]
    if request_id is not None:
        parts.append(str(int(request_id)))
    return ":".join(parts)


def load_drafts_for_keys(user_email: str, object_keys: Iterable[str]) -> list[dict[str, Any]]:
    email = _clean(user_email).lower()
    keys = sorted({_clean(key) for key in object_keys if _clean(key)})
    if not email or not keys:
        return []
    return fetch_all(
        "monitoring_drafts",
        "user_email,object_key,content,created_at,updated_at",
        filters=[("eq", "user_email", email), ("in_", "object_key", keys)],
        order=("updated_at", True),
    )


def _content_from_row(row: dict[str, Any]) -> dict[str, Any]:
    content = row.get("content") or {}
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def drafts_as_map(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        _clean(row.get("object_key")): _content_from_row(row)
        for row in rows
        if _clean(row.get("object_key"))
    }


def save_draft_now(user_email: str, object_key: str, content: dict[str, Any]) -> None:
    email = _clean(user_email).lower()
    key = _clean(object_key)
    if not email or not key:
        return
    payload = {
        "user_email": email,
        "object_key": key,
        "content": _json_safe(content),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    get_supabase_client().table("monitoring_drafts").upsert(
        payload, on_conflict="user_email,object_key"
    ).execute()
    st.session_state.setdefault(_SAVED_HASHES_KEY, {})[key] = _content_hash(content)


def delete_drafts_now(user_email: str, object_keys: Iterable[str]) -> None:
    email = _clean(user_email).lower()
    keys = sorted({_clean(key) for key in object_keys if _clean(key)})
    if not email or not keys:
        return
    (
        get_supabase_client()
        .table("monitoring_drafts")
        .delete()
        .eq("user_email", email)
        .in_("object_key", keys)
        .execute()
    )
    hashes = st.session_state.setdefault(_SAVED_HASHES_KEY, {})
    for key in keys:
        hashes.pop(key, None)


def _content_hash(content: dict[str, Any]) -> str:
    return json.dumps(_json_safe(content), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def forget_draft_state(object_keys: Iterable[str]) -> None:
    """Очищає локальний hash/чергу після атомарного видалення чернетки в RPC."""
    keys = {_clean(key) for key in object_keys if _clean(key)}
    hashes = st.session_state.setdefault(_SAVED_HASHES_KEY, {})
    pending = st.session_state.setdefault(_PENDING_KEY, {})
    for key in keys:
        hashes.pop(key, None)
        pending.pop(key, None)


def queue_draft(user_email: str, object_key: str, content: dict[str, Any]) -> None:
    email = _clean(user_email).lower()
    key = _clean(object_key)
    if not email or not key:
        return
    safe_content = _json_safe(content)
    content_hash = _content_hash(safe_content)
    if st.session_state.setdefault(_SAVED_HASHES_KEY, {}).get(key) == content_hash:
        return
    st.session_state.setdefault(_PENDING_KEY, {})[key] = {
        "operation": "save",
        "user_email": email,
        "object_key": key,
        "content": safe_content,
    }


def queue_draft_delete(user_email: str, object_key: str) -> None:
    email = _clean(user_email).lower()
    key = _clean(object_key)
    if not email or not key:
        return
    st.session_state.setdefault(_PENDING_KEY, {})[key] = {
        "operation": "delete",
        "user_email": email,
        "object_key": key,
    }


@st.fragment(run_every=3)
def render_draft_autosave_worker() -> None:
    """Раз на три секунди зберігає останній стан кожної зміненої чернетки."""
    pending = st.session_state.get(_PENDING_KEY, {})
    if not pending:
        return
    operations = list(pending.values())
    st.session_state[_PENDING_KEY] = {}
    for operation in operations:
        try:
            if operation.get("operation") == "delete":
                delete_drafts_now(
                    operation.get("user_email", ""),
                    [operation.get("object_key", "")],
                )
            else:
                save_draft_now(
                    operation.get("user_email", ""),
                    operation.get("object_key", ""),
                    operation.get("content") or {},
                )
        except Exception as exc:
            # Повертаємо операцію в чергу: наступний цикл спробує ще раз.
            key = _clean(operation.get("object_key"))
            if key:
                st.session_state.setdefault(_PENDING_KEY, {})[key] = operation
            show_warning(
                "Автоматичну чернетку тимчасово не збережено. Введені дані лишаються у формі.",
                exc,
                "Автоматичне збереження чернетки",
            )


def _format_draft_time(value: Any) -> str:
    text = _clean(value)
    if not text:
        return "невідомий час"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(KYIV_TZ).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return text


def _restore_key(context_key: str) -> str:
    return f"draft_restored::{context_key}"


def _generation_key(context_key: str) -> str:
    return f"draft_editor_generation::{context_key}"


def editor_generation(context_key: str) -> int:
    return int(st.session_state.get(_generation_key(context_key), 0))


def clear_draft_recovery(context_key: str) -> None:
    st.session_state.pop(_restore_key(context_key), None)
    st.session_state.pop(f"draft_widgets_applied::{context_key}", None)
    st.session_state[_generation_key(context_key)] = editor_generation(context_key) + 1


def render_draft_recovery(
    *,
    context_key: str,
    user_email: str,
    draft_rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Показує плашку В1 і повертає відновлений вміст за ключами об'єктів."""
    restore_state_key = _restore_key(context_key)
    restored = st.session_state.get(restore_state_key)
    keys = [_clean(row.get("object_key")) for row in draft_rows if _clean(row.get("object_key"))]

    if not draft_rows:
        st.session_state.pop(restore_state_key, None)
        return {}

    latest = max(
        draft_rows,
        key=lambda row: _clean(row.get("updated_at")) or _clean(row.get("created_at")),
    )
    latest_time = _format_draft_time(latest.get("updated_at") or latest.get("created_at"))

    if isinstance(restored, dict):
        st.success(
            f"Чернетку від {latest_time} відновлено. Вона зберігатиметься автоматично до успішного подання."
        )
        if st.button(
            "Відхилити відновлену чернетку",
            key=f"draft_discard_restored::{context_key}",
        ):
            try:
                delete_drafts_now(user_email, keys)
                clear_draft_recovery(context_key)
                st.rerun()
            except Exception as exc:
                show_warning(
                    "Чернетку не вдалося видалити.", exc, "Видалення відновленої чернетки"
                )
        return restored

    st.warning(f"Знайдено незбережену чернетку від {latest_time}.")
    left, right = st.columns(2)
    with left:
        restore_clicked = st.button(
            "Відновити",
            use_container_width=True,
            key=f"draft_restore::{context_key}",
        )
    with right:
        discard_clicked = st.button(
            "Відхилити",
            use_container_width=True,
            key=f"draft_discard::{context_key}",
        )

    if restore_clicked:
        st.session_state[restore_state_key] = drafts_as_map(draft_rows)
        st.session_state[_generation_key(context_key)] = editor_generation(context_key) + 1
        st.rerun()
    if discard_clicked:
        try:
            delete_drafts_now(user_email, keys)
            clear_draft_recovery(context_key)
            st.rerun()
        except Exception as exc:
            show_warning("Чернетку не вдалося видалити.", exc, "Відхилення чернетки")
    return {}
