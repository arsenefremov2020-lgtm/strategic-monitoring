#!/usr/bin/env python3
# scripts/send_notifications.py

"""
Планова email-розсилка системи моніторингу.

Скрипт запускається GitHub Actions двічі на будній день і формує для кожного
отримувача повний зріз незакритих питань станом на момент запуску. Порожні
дайджести не надсилаються. Миттєві листи зі Streamlit-сторінок вимкнені в
core/notify_events.py.

Антидубль прив'язаний до конкретного слоту дня: morning / evening. Тому
ранковий лист не блокує вечірній, а випадковий повтор того самого слоту не
створює дубль.

Необхідні змінні середовища:
    SUPABASE_URL, SUPABASE_KEY
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM (опц.)
    NOTIFICATIONS_DRY_RUN=1  → тестовий прогін без реальної відправки
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

# Скрипт запускається з кореня репозиторію: python scripts/send_notifications.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.data_types import normalise_closeout_frame, normalise_monitoring_frame  # noqa: E402
from core import approval_schemes as schemes  # noqa: E402
from core.db import fetch_all  # noqa: E402
from core.emails import send_email  # noqa: E402
from core.timeutils import now_kyiv  # noqa: E402
from core.superadmin_routing import resolve_manual_closeout_route  # noqa: E402

DEADLINE_DAY = 15    # подання до 15 числа місяця, наступного за звітним кварталом
REMINDER_DAYS_BEFORE = [10, 5, 2, 1]   # за скільки днів до дедлайну нагадуємо
STALE_DAYS = 5                          # "заявка висить понад N днів"
RETURNED_STALE_DAYS = 7                 # повернута й не переподана понад N днів

DRY_RUN = os.environ.get("NOTIFICATIONS_DRY_RUN", "0") == "1"
FORCE_RUN = os.environ.get("NOTIFICATIONS_FORCE_RUN", "0") == "1"


# ------------------------------------------------------------
# Службові
# ------------------------------------------------------------


def clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none", "null") else text


def get_supabase():
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)


def current_reporting_period(today: datetime) -> tuple[str, str, datetime] | None:
    """
    Якщо сьогодні — "вікно подання" (з 1 по 15 число місяця після кварталу),
    повертає (рік, квартал, дедлайн). Інакше None.

    Приклад: 02.07.2026 → звітний період II квартал 2026, дедлайн 15.07.2026.
    """
    first_month_after_quarter = {1: 4, 2: 7, 3: 10, 4: 1}
    month = today.month
    for quarter, m_after in first_month_after_quarter.items():
        if month == m_after and today.day <= DEADLINE_DAY:
            year = today.year if quarter != 4 else today.year - 1
            deadline = today.replace(day=DEADLINE_DAY)
            roman = {1: "I", 2: "II", 3: "III", 4: "IV"}[quarter]
            return str(year), roman, deadline
    return None


# ------------------------------------------------------------
# Користувачі (users_access.xlsx — те саме джерело, що і застосунок)
# ------------------------------------------------------------

def load_users() -> list[dict]:
    """Мінімалістичне читання users_access.xlsx без залежності від Streamlit."""
    path = Path("users_access.xlsx")
    if not path.exists():
        print("!! users_access.xlsx не знайдено — розсилка неможлива.")
        return []

    users: list[dict] = []

    def read_sheet(sheet: str) -> pd.DataFrame:
        try:
            return pd.read_excel(path, sheet_name=sheet)
        except Exception:
            return pd.DataFrame()

    def norm_index(value) -> str:
        import re
        text = clean(value)
        digits = re.findall(r"\d+", text)
        return "".join(digits) if digits else ""

    # Адміністратори / супер-адміни
    for _, row in read_sheet("Адміністратори").iterrows():
        email = clean(row.get("email")).lower()
        if not email or not _truthy(row.get("is_active")):
            continue
        role = clean(row.get("role")) or "admin"
        if role not in ("admin", "super_admin"):
            role = "admin"
        assigned = [
            norm_index(part)
            for part in str(clean(row.get("assigned_ssp_indexes"))).replace(";", ",").split(",")
            if norm_index(part)
        ]
        users.append({
            "email": email,
            "full_name": clean(row.get("full_name")),
            "role": role,
            "ssp_index": None,
            "allowed": ["*"] if role == "super_admin" else assigned,
        })

    for sheet, role in (("Керівники ССП", "ssp_head"), ("Відповідальні за ССП", "ssp"),
                        ("Заступники керівників ССП", "ssp_deputy")):
        for _, row in read_sheet(sheet).iterrows():
            email = clean(row.get("email")).lower()
            if not email or not _truthy(row.get("is_active")):
                continue
            idx = norm_index(row.get("ssp_index"))
            users.append({
                "email": email,
                "full_name": clean(row.get("full_name")),
                "role": clean(row.get("role")) or role,
                "ssp_index": idx,
                "allowed": [idx] if idx else [],
            })

    return users


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return clean(value).lower() in ("true", "1", "yes", "так", "активний", "active")


# ------------------------------------------------------------
# Дані Supabase
# ------------------------------------------------------------

def load_requests(supabase) -> pd.DataFrame:
    try:
        rows = fetch_all(
            "monitoring_requests",
            "*",
            order=("id", False),
            client=supabase,
        )
        return normalise_monitoring_frame(pd.DataFrame(rows))
    except Exception as exc:
        print(f"!! Не вдалося прочитати monitoring_requests: {exc}")
        return pd.DataFrame()


def load_pending_closeouts(supabase) -> pd.DataFrame:
    try:
        rows = fetch_all(
            "closeout_requests",
            "*",
            filters=[("eq", "approval_status", "Очікує підтвердження")],
            order=("id", False),
            client=supabase,
        )
        return normalise_closeout_frame(pd.DataFrame(rows))
    except Exception:
        return pd.DataFrame()


def already_sent(supabase, email: str, ntype: str, related_key: str) -> bool:
    """Чи був уже успішно надісланий саме цей денний слот дайджеста."""
    try:
        resp = (
            supabase.table("notification_log")
            .select("id")
            .eq("recipient_email", email)
            .eq("notification_type", ntype)
            .eq("related_key", related_key)
            .eq("status", "sent")
            .limit(1)
            .execute()
        )
        return bool(resp.data)
    except Exception as exc:
        # Fail closed: без журналу не ризикуємо подвоїти розсилку.
        print(f"!! notification_log недоступний ({exc}) — пропускаю {ntype} для {email}")
        return True


def log_notification(supabase, email: str, role: str, ntype: str,
                     related_key: str, subject: str, body: str,
                     ok: bool, error: str | None) -> None:
    try:
        supabase.table("notification_log").insert({
            "recipient_email": email,
            "recipient_role": role,
            "notification_type": ntype,
            "related_key": related_key,
            "subject": subject,
            "body_preview": body[:500],
            "status": "sent" if ok else "failed",
            "error": error,
        }).execute()
    except Exception as exc:
        print(f"!! Не вдалося записати notification_log: {exc}")


# ------------------------------------------------------------
# Побудова блоків вмісту
# ------------------------------------------------------------

def _hours_since(value) -> float:
    dt = pd.to_datetime(clean(value), errors="coerce", utc=True)
    if pd.isna(dt):
        return 0.0
    return (pd.Timestamp.now(tz=timezone.utc) - dt).total_seconds() / 3600.0


def _hours_since_or_none(value):
    """Як _hours_since, але «немає дати» → None (не плутається з 0 годин)."""
    dt = pd.to_datetime(clean(value), errors="coerce", utc=True)
    if pd.isna(dt):
        return None
    return (pd.Timestamp.now(tz=timezone.utc) - dt).total_seconds() / 3600.0


def _days_since_or_none(value):
    h = _hours_since_or_none(value)
    return None if h is None else int(h // 24)


def _days_since(value) -> int:
    return int(_hours_since(value) // 24)


def _req_for_ssp(requests: pd.DataFrame, allowed: list[str]) -> pd.DataFrame:
    """Фільтр заявок за індексами ССП користувача.
    Фактична колонка ССП у monitoring_requests — department (індекс підрозділу)."""
    if requests.empty or not allowed:
        return requests.iloc[0:0]
    if "*" in allowed:
        return requests
    import re

    def matches(row) -> bool:
        found = re.findall(r"\d+", clean(row.get("department", "")))
        return any(f in allowed for f in found)

    mask = requests.apply(matches, axis=1)
    return requests[mask]


def load_logs(supabase) -> pd.DataFrame:
    try:
        rows = fetch_all(
            "monitoring_logs",
            "request_id,old_status,new_status,changed_at",
            order=("id", False),
            client=supabase,
        )
        return pd.DataFrame(rows)
    except Exception as exc:
        print(f"!! Не вдалося прочитати monitoring_logs: {exc}")
        return pd.DataFrame()


def build_log_maps(logs: pd.DataFrame):
    """Build timestamps for recent events and the beginning of the current status run.

    Repeated journal entries that keep the same status do not reset the waiting
    period. A transition away and later back to a status starts a new run.
    """
    last_change, approved, returned, stage_since = {}, {}, {}, {}
    if logs.empty:
        return last_change, approved, returned, stage_since
    logs = logs.copy()
    logs["_dt"] = pd.to_datetime(logs["changed_at"], errors="coerce", utc=True)
    logs = logs.sort_values(["request_id", "_dt"], na_position="last")
    current_status_by_request: dict[object, str] = {}
    for _, r in logs.iterrows():
        rid = r.get("request_id")
        ts = r.get("changed_at")
        # Журнальні записи ручного закриття можуть не мати request_id.
        # У DataFrame такі NULL стають NaN; якщо не відкинути їх тут,
        # у словнику з'являються кілька NaN-ключів, а pandas Series.map()
        # перетворює словник на Series з неунікальним індексом і падає з
        # InvalidIndexError. Для реальних заявок нормалізуємо id до int.
        if rid is None or pd.isna(rid) or pd.isna(r["_dt"]):
            continue
        try:
            rid = int(rid)
        except (TypeError, ValueError, OverflowError):
            continue
        last_change[rid] = ts
        ns = clean(r.get("new_status"))
        previous = current_status_by_request.get(rid, clean(r.get("old_status")))
        if ns and ns != previous:
            stage_since[rid] = ts
            current_status_by_request[rid] = ns
        elif ns and rid not in current_status_by_request:
            current_status_by_request[rid] = ns
            stage_since.setdefault(rid, ts)
        if ns == "Погоджено":
            approved[rid] = ts
        elif ns in set(schemes.ALL_RETURNED_STATUSES):
            returned[rid] = ts
    return last_change, approved, returned, stage_since


def _parse_chain(value) -> list[dict]:
    return schemes.parse_chain(value)


def digest_slot(today: datetime, *, force_run: bool = False) -> str | None:
    """Повертає morning/evening для двох київських слотів розсилки."""
    if today.hour == 8:
        return "morning"
    if today.hour == 16:
        return "evening"
    if force_run:
        return "morning" if today.hour < 12 else "evening"
    return None


def _stage_index(value) -> int:
    return schemes.parse_stage(value)


def _current_stage(row) -> dict:
    chain = _parse_chain(row.get("approval_chain"))
    stage = _stage_index(row.get("chain_stage"))
    return chain[stage] if stage < len(chain) else {}


def _name_tokens(value) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zа-яіїєґ']+", clean(value).lower())
        if len(token) >= 4
    }


def _stage_matches_user(stage: dict, user: dict) -> bool:
    stage_email = clean(stage.get("email")).lower()
    user_email = clean(user.get("email")).lower()
    if stage_email:
        return bool(user_email and stage_email == user_email)

    user_role = clean(user.get("role"))
    stage_role = clean(stage.get("role"))
    if user_role == "super_admin":
        stage_tokens = _name_tokens(stage.get("name"))
        user_tokens = _name_tokens(user.get("full_name"))
        return bool(stage_tokens and user_tokens and stage_tokens & user_tokens)
    return bool(stage_role and stage_role == user_role)


def _request_waits_for_user(row, user: dict) -> bool:
    status = clean(row.get("approval_status"))
    expected_statuses = {
        "admin": {schemes.STATUS_COORDINATOR_REVIEW},
        "super_admin": {schemes.STATUS_SUPERADMIN_REVIEW},
        "ssp_head": {schemes.STATUS_MANAGER_REVIEW},
        "ssp_deputy": {schemes.STATUS_MANAGER_REVIEW},
    }.get(clean(user.get("role")), set())
    if status not in expected_statuses:
        return False
    current = _current_stage(row)
    return bool(current and _stage_matches_user(current, user))


def _route_matches_superadmin(route: dict, superadmin: dict) -> bool:
    email = clean(superadmin.get("email")).lower()
    route_emails = {
        clean(route.get("assigned_superadmin_email")).lower(),
        clean(route.get("senior_superadmin_email")).lower(),
    }
    route_emails.discard("")
    if email and email in route_emails:
        return True

    user_tokens = _name_tokens(superadmin.get("full_name"))
    route_tokens = (
        _name_tokens(route.get("assigned_superadmin_name"))
        | _name_tokens(route.get("senior_superadmin_name"))
    )
    return bool(user_tokens and route_tokens and user_tokens & route_tokens)


def assigned_admin_emails_for_superadmin(users: list[dict], superadmin: dict) -> set[str]:
    """Адміністратори, закріплені за супер-адміном чинною route-логікою."""
    result: set[str] = set()
    for admin in users:
        if clean(admin.get("role")) != "admin":
            continue
        route = resolve_manual_closeout_route(admin)
        if _route_matches_superadmin(route, superadmin):
            email = clean(admin.get("email")).lower()
            if email:
                result.add(email)
    return result


def _department_indexes(row) -> set[str]:
    return set(re.findall(r"\d+", clean(row.get("department"))))


def _current_admin_email(row, admin_users: list[dict]) -> str:
    current = _current_stage(row)
    if clean(current.get("role")) == "admin":
        email = clean(current.get("email")).lower()
        if email:
            return email

    if clean(row.get("approval_status")) != schemes.STATUS_COORDINATOR_REVIEW:
        return ""
    indexes = _department_indexes(row)
    matches = []
    for admin in admin_users:
        allowed = set(admin.get("allowed") or [])
        if "*" in allowed or (indexes and indexes & allowed):
            email = clean(admin.get("email")).lower()
            if email:
                matches.append(email)
    return matches[0] if len(set(matches)) == 1 else ""


def build_superadmin_stuck_map(
    requests: pd.DataFrame,
    users: list[dict],
) -> dict[str, list[dict]]:
    """Заявки на адмінській ланці >5 днів для закріплених адміністраторів."""
    result: dict[str, list[dict]] = {}
    if requests.empty:
        return result

    admins = [user for user in users if clean(user.get("role")) == "admin"]
    superadmins = [
        user for user in users if clean(user.get("role")) == "super_admin"
    ]
    assigned = {
        clean(user.get("email")).lower(): assigned_admin_emails_for_superadmin(users, user)
        for user in superadmins
        if clean(user.get("email"))
    }

    for _, row in requests.iterrows():
        current = _current_stage(row)
        if current and clean(current.get("role")) != "admin":
            continue
        if not current and clean(row.get("approval_status")) != schemes.STATUS_COORDINATOR_REVIEW:
            continue

        admin_email = _current_admin_email(row, admins)
        if not admin_email:
            continue
        days = _days_since_or_none(row.get("_stage_since"))
        # Важливо: без журналу не підміняємо момент входу submitted_at.
        if days is None or days <= STALE_DAYS:
            continue

        item = {
            "id": row.get("id"),
            "strat_code": clean(row.get("strat_code")),
            "year": clean(row.get("year")),
            "quarter": clean(row.get("quarter")),
            "days": days,
            "admin_email": admin_email,
        }
        for superadmin_email, admin_emails in assigned.items():
            if admin_email in admin_emails:
                result.setdefault(superadmin_email, []).append(item)

    for items in result.values():
        items.sort(key=lambda item: (-int(item["days"]), str(item["strat_code"])))
    return result


def _closeout_matches_superadmin(row, superadmin: dict) -> bool:
    route = {
        "assigned_superadmin_email": row.get("assigned_superadmin_email"),
        "assigned_superadmin_name": row.get("assigned_superadmin_name"),
        "senior_superadmin_email": row.get("senior_superadmin_email"),
        "senior_superadmin_name": row.get("senior_superadmin_name"),
    }
    if not any(clean(value) for value in route.values()):
        route = resolve_manual_closeout_route({
            "email": row.get("admin_email"),
            "full_name": row.get("admin_id") or row.get("admin_name"),
        })
    return _route_matches_superadmin(route, superadmin)


def li(text: str) -> str:
    return f'<li style="margin:4px 0;">{text}</li>'


def block(title: str, items: list[str], accent: str = "#005BBB") -> str:
    rows = "".join(items)
    return (
        f'<div style="margin:14px 0;">'
        f'<div style="font-weight:900;color:{accent};margin-bottom:6px;">{title}</div>'
        f'<ul style="margin:0;padding-left:18px;">{rows}</ul></div>'
    )


# ------------------------------------------------------------
# Головна логіка
# ------------------------------------------------------------

def main() -> int:
    today = now_kyiv()
    slot = digest_slot(today, force_run=FORCE_RUN)
    print(
        f"== Дайджест моніторингу, Київ: {today:%d.%m.%Y %H:%M %Z}, "
        f"slot={slot or 'none'}, DRY_RUN={DRY_RUN}, FORCE_RUN={FORCE_RUN} =="
    )
    if not FORCE_RUN and today.weekday() >= 5:
        print("-- Вихідний день; планову розсилку завершено.")
        return 0
    if slot is None:
        print("-- Зараз у Києві не плановий слот 08:30 або 16:30; завершено.")
        return 0

    supabase = get_supabase()
    users = load_users()
    requests = load_requests(supabase)
    closeouts = load_pending_closeouts(supabase)

    if not users:
        return 0

    for col in (
        "approval_status", "submitted_at", "admin_comment", "strat_code",
        "year", "quarter", "department", "object_kind", "id",
        "approval_chain", "chain_stage",
    ):
        if not requests.empty and col not in requests.columns:
            requests[col] = ""

    logs = load_logs(supabase)
    last_change_at, approved_at, returned_at, stage_since = build_log_maps(logs)
    if not requests.empty:
        ids = pd.to_numeric(requests["id"], errors="coerce")
        requests["_last_change_at"] = ids.map(last_change_at).fillna(requests["submitted_at"])
        requests["_approved_at"] = ids.map(approved_at)
        requests["_returned_at"] = ids.map(returned_at)
        # Не підміняємо submitted_at: для супер-адмінського правила потрібен
        # саме початок поточного статусного відрізка з monitoring_logs.
        requests["_stage_since"] = ids.map(stage_since)

    superadmin_stuck = build_superadmin_stuck_map(requests, users)
    period = current_reporting_period(today)
    day_str = today.strftime("%Y-%m-%d")
    slot_label = "ранковий" if slot == "morning" else "вечірній"

    sent_count = 0

    for user in users:
        email = clean(user.get("email")).lower()
        role = clean(user.get("role"))
        allowed = user.get("allowed") or []
        name = clean(user.get("full_name")) or "колего"
        if not email:
            continue

        sections: list[str] = []
        ntype = f"{role}_digest"
        related_key = f"digest:{day_str}:{slot}"
        my_requests = _req_for_ssp(requests, allowed) if not requests.empty else requests

        # ---------- ССП: дедлайн і всі повернуті заявки ----------
        if role == "ssp" and period:
            year, quarter, deadline = period
            days_left = (deadline.date() - today.date()).days
            if days_left in REMINDER_DAYS_BEFORE:
                has_submission = False
                if not my_requests.empty:
                    kinds = my_requests["object_kind"].astype(str).str.lower()
                    mask = (
                        (my_requests["year"].astype(str).str.strip() == str(year))
                        & (my_requests["quarter"].astype(str).str.strip() == str(quarter))
                        & (kinds != "indicator")
                    )
                    has_submission = bool(mask.any())
                if not has_submission:
                    urgency = "🔴" if days_left <= 2 else ("🟡" if days_left <= 5 else "🔵")
                    sections.append(block(
                        f"{urgency} Нагадування про подання відомостей",
                        [li(
                            f"До <b>{deadline:%d.%m.%Y}</b> (залишилось <b>{days_left} дн.</b>) "
                            f"необхідно подати відомості за <b>{quarter} квартал {year} року</b>."
                        )],
                        accent="#b45309" if days_left > 2 else "#b91c1c",
                    ))

        if role == "ssp" and not my_requests.empty:
            returned = my_requests[
                my_requests["approval_status"].astype(str).isin(schemes.ALL_RETURNED_STATUSES)
            ]
            if not returned.empty:
                items = []
                for _, row in returned.head(20).iterrows():
                    comment = clean(row.get("admin_comment"))
                    comment_part = f" Коментар до повернення: «{comment[:160]}»" if comment else ""
                    items.append(li(
                        f"Захід <b>{clean(row.get('strat_code'))}</b> "
                        f"({clean(row.get('quarter'))} кв. {clean(row.get('year'))}) — "
                        f"повернуто на доопрацювання.{comment_part}"
                    ))
                sections.append(block(
                    f"↩️ Повернуто на доопрацювання: {len(returned)}",
                    items,
                    accent="#b91c1c",
                ))

        if role == "ssp" and not my_requests.empty:
            manager_selection = my_requests[
                my_requests["approval_status"].astype(str)
                == schemes.STATUS_WAITING_MANAGER_SELECTION
            ]
            if not manager_selection.empty:
                sections.append(block(
                    f"👤 Потрібно обрати керівника: {len(manager_selection)}",
                    [li(
                        f"Заявка №{clean(row.get('id'))}: захід "
                        f"<b>{clean(row.get('strat_code'))}</b> "
                        f"({clean(row.get('quarter'))} кв. {clean(row.get('year'))}) — "
                        "перевірте дані та направте керівнику ССП або заступнику."
                    ) for _, row in manager_selection.head(20).iterrows()],
                    accent="#b45309",
                ))

        # ---------- Ланки вертикалі: повний зріз заявок на їхній ланці ----------
        if role in {"ssp_head", "ssp_deputy"} and not my_requests.empty:
            mask = my_requests.apply(lambda row: _request_waits_for_user(row, user), axis=1)
            waiting = my_requests[mask]
            if not waiting.empty:
                items = []
                for _, row in waiting.head(25).iterrows():
                    days = _days_since_or_none(row.get("_stage_since"))
                    if days is None:
                        days = _days_since(row.get("submitted_at"))
                    flag = " ⚠️" if days > STALE_DAYS else ""
                    items.append(li(
                        f"Захід <b>{clean(row.get('strat_code'))}</b> "
                        f"({clean(row.get('quarter'))} кв. {clean(row.get('year'))}) — "
                        f"очікує вашого рішення <b>{days} дн.</b>{flag}"
                    ))
                sections.append(block(
                    f"✍️ Очікують вашого рішення: {len(waiting)}",
                    items,
                ))

        # ---------- Координатор: усі на його ланці + усі повернуті ----------
        if role == "admin" and not my_requests.empty:
            pending_mask = my_requests.apply(
                lambda row: _request_waits_for_user(row, user),
                axis=1,
            )
            pending = my_requests[pending_mask]
            if not pending.empty:
                items = []
                for _, row in pending.head(25).iterrows():
                    days = _days_since_or_none(row.get("_stage_since"))
                    if days is None:
                        days = _days_since(row.get("submitted_at"))
                    items.append(li(
                        f"Заявка №{clean(row.get('id'))}: захід "
                        f"<b>{clean(row.get('strat_code'))}</b> "
                        f"({clean(row.get('quarter'))} кв. {clean(row.get('year'))}) — "
                        f"на вашій ланці <b>{days} дн.</b>"
                    ))
                sections.append(block(
                    f"📬 На координаторському розгляді: {len(pending)}",
                    items,
                ))

            returned = my_requests[
                my_requests["approval_status"].astype(str).isin(schemes.ALL_RETURNED_STATUSES)
            ]
            if not returned.empty:
                items = []
                for _, row in returned.head(20).iterrows():
                    days = _days_since_or_none(row.get("_returned_at"))
                    days_text = f"; не переподано {days} дн." if days is not None else ""
                    items.append(li(
                        f"Заявка №{clean(row.get('id'))}: захід "
                        f"<b>{clean(row.get('strat_code'))}</b> "
                        f"({clean(row.get('quarter'))} кв. {clean(row.get('year'))})"
                        f"{days_text}"
                    ))
                sections.append(block(
                    f"↩️ Повернуті й ще не переподані: {len(returned)}",
                    items,
                    accent="#b45309",
                ))

        # ---------- Супер-адмін: лише дві дозволені умови ----------
        if role == "super_admin":
            stuck = superadmin_stuck.get(email, [])
            if stuck:
                sections.append(block(
                    f"🚨 Заявки закріплених адміністраторів на їхній ланці понад {STALE_DAYS} днів: {len(stuck)}",
                    [li(
                        f"Адміністратор: <b>{item['admin_email']}</b>; заявка №{item['id']} — "
                        f"захід <b>{item['strat_code']}</b> "
                        f"({item['quarter']} кв. {item['year']}); "
                        f"на адмінській ланці <b>{item['days']} дн.</b>"
                    ) for item in stuck[:25]],
                    accent="#b91c1c",
                ))

            if not requests.empty:
                own_mask = requests.apply(
                    lambda row: _request_waits_for_user(row, user),
                    axis=1,
                )
                own_waiting = requests[own_mask]
            else:
                own_waiting = requests
            if not own_waiting.empty:
                sections.append(block(
                    f"🧭 Надійшло на ваше погодження: {len(own_waiting)}",
                    [li(
                        f"Заявка №{clean(row.get('id'))}: захід "
                        f"<b>{clean(row.get('strat_code'))}</b> "
                        f"({clean(row.get('quarter'))} кв. {clean(row.get('year'))})"
                    ) for _, row in own_waiting.head(25).iterrows()],
                    accent="#6d28d9",
                ))

            if not closeouts.empty:
                own_closeouts = closeouts[
                    closeouts.apply(
                        lambda row: _closeout_matches_superadmin(row, user),
                        axis=1,
                    )
                ]
            else:
                own_closeouts = closeouts
            if not own_closeouts.empty:
                sections.append(block(
                    f"🔐 Запити на ручне закриття на вашому розгляді: {len(own_closeouts)}",
                    [li(
                        f"Запит №{clean(row.get('id'))}: захід "
                        f"<b>{clean(row.get('strat_code'))}</b> "
                        f"({clean(row.get('period_quarter'))} кв. "
                        f"{clean(row.get('period_year'))}) — "
                        f"від {clean(row.get('admin_email'))}"
                    ) for _, row in own_closeouts.head(25).iterrows()],
                    accent="#6d28d9",
                ))

        if not sections:
            continue

        if already_sent(supabase, email, ntype, related_key):
            print(f"-- {email}: {slot_label} слот уже надсилався, пропускаю")
            continue

        role_label = {
            "ssp": "відповідальної особи ССП",
            "ssp_head": "керівника ССП",
            "ssp_deputy": "заступника керівника ССП",
            "admin": "координатора",
            "super_admin": "супер-адміністратора",
        }.get(role, role)

        subject = (
            f"Моніторинг СП — {slot_label} дайджест для {role_label} · "
            f"{today:%d.%m.%Y}"
        )
        body = (
            f'<p>Вітаємо, <b>{name}</b>!</p>'
            f'<p>Повний зріз незакритих питань станом на '
            f'<b>{today:%d.%m.%Y %H:%M}</b> за київським часом:</p>'
            + "".join(sections)
            + '<p style="margin-top:16px;">Перейдіть у систему, щоб опрацювати зазначені пункти.</p>'
        )

        if DRY_RUN:
            print(f"[DRY] {email} ({role}) ← {subject} ({len(sections)} блок(ів))")
            sent_count += 1
            continue

        ok, error = send_email(
            email,
            subject,
            body,
            title="Дайджест системи моніторингу",
        )
        log_notification(
            supabase, email, role, ntype, related_key, subject, body, ok, error
        )
        print(f"{'OK ' if ok else 'ERR'} {email} ({role}) — {error or 'надіслано'}")
        if ok:
            sent_count += 1

    print(f"== Готово: надіслано {sent_count} лист(ів) ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
