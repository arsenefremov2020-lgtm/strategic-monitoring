"""Helpers for DEMO 2.0 Stage 5 administration and notification diagnostics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from core.db import fetch_all, get_supabase_client
from core.errors import show_warning

KYIV_TZ = ZoneInfo("Europe/Kyiv")


NOTIFICATION_TYPE_LABELS = {
    "stage_assigned": "Заявка передана на погодження",
    "returned": "Заявку повернуто",
    "approved": "Заявку погоджено",
    "superadmin_correction": "Коригування закритої заявки",
    "closeout_to_head": "Ручне закриття — повідомлення керівнику",
    "ssp_digest": "Щоденний дайджест відповідальної особи ССП",
    "ssp_head_digest": "Щоденний дайджест керівника ССП",
    "unit_head_digest": "Щоденний дайджест керівника управління",
    "ssp_deputy_digest": "Щоденний дайджест заступника керівника ССП",
    "admin_digest": "Щоденний дайджест координатора",
    "super_admin_digest": "Щоденний дайджест супер-адміністратора",
}


def _to_utc(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        ts = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    except (TypeError, ValueError, OverflowError):
        return None


def format_kyiv(value: object) -> str:
    dt = _to_utc(value)
    if dt is None:
        return "—"
    return dt.astimezone(KYIV_TZ).strftime("%d.%m.%Y %H:%M")


@st.cache_data(ttl=60, show_spinner=False)
def latest_system_update() -> tuple[datetime | None, str]:
    """Return the newest timestamp among requests and action log."""
    try:
        client = get_supabase_client()
        req = (
            client.table("monitoring_requests")
            .select("updated_at")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        log = (
            client.table("monitoring_logs")
            .select("changed_at")
            .order("changed_at", desc=True)
            .limit(1)
            .execute()
        )
        candidates = []
        if req.data:
            candidates.append(_to_utc(req.data[0].get("updated_at")))
        if log.data:
            candidates.append(_to_utc(log.data[0].get("changed_at")))
        candidates = [value for value in candidates if value is not None]
        latest = max(candidates) if candidates else None
        return latest, format_kyiv(latest)
    except Exception as exc:  # UI remains available when diagnostic query fails
        show_warning(
            "Час останнього оновлення тимчасово недоступний.",
            exc,
            "Визначення останньої зміни заявок і журналу",
        )
        return None, "—"


def humanize_email_error(value: object) -> str:
    raw = str(value or "").strip()
    text = raw.lower()
    if not raw:
        return "Причину не зафіксовано."
    if "smtp не налашт" in text or "smtp_*" in text or "st.secrets[smtp]" in text:
        return "Поштову скриньку відправника не налаштовано."
    if any(token in text for token in (
        "user unknown", "recipient address rejected", "address not found",
        "no such user", "mailbox unavailable", "invalid recipient", "550 ", "5.1.1",
        "некоректна адреса",
    )):
        return "Адресу отримувача не знайдено або її відхилив поштовий сервер."
    if any(token in text for token in (
        "authentication", "auth", "username and password not accepted", "535 ",
    )):
        return "Не вдалося увійти до поштової скриньки відправника."
    if any(token in text for token in (
        "timed out", "timeout", "connection refused", "network is unreachable",
        "temporary failure", "name or service not known",
    )):
        return "Поштовий сервер не відповів вчасно або був недоступний."
    if any(token in text for token in ("quota", "rate limit", "too many", "daily limit")):
        return "Поштовий сервер тимчасово обмежив кількість листів."
    # Keep an unfamiliar provider message available, but not as an unbounded traceback.
    compact = " ".join(raw.split())
    return compact[:240] + ("…" if len(compact) > 240 else "")


@st.cache_data(ttl=60, show_spinner=False)
def failed_notifications_last_30_days() -> pd.DataFrame:
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    try:
        rows = fetch_all(
            "notification_log",
            "id,recipient_email,recipient_role,notification_type,subject,sent_at,status,error",
            filters=[("eq", "status", "failed"), ("gte", "sent_at", since)],
            order=("sent_at", True),
        )
    except Exception as exc:
        show_warning(
            "Не вдалося завантажити журнал недоставлених листів.",
            exc,
            "Читання notification_log за останні 30 днів",
        )
        return pd.DataFrame()

    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    frame["Кому"] = frame["recipient_email"].fillna("").astype(str)
    frame["Коли"] = frame["sent_at"].map(format_kyiv)
    frame["Тип листа"] = frame["notification_type"].map(
        lambda value: NOTIFICATION_TYPE_LABELS.get(str(value or ""), str(value or "—"))
    )
    frame["Тема"] = frame["subject"].fillna("").astype(str)
    frame["Причина недоставлення"] = frame["error"].map(humanize_email_error)
    return frame[["Кому", "Коли", "Тип листа", "Тема", "Причина недоставлення"]]
