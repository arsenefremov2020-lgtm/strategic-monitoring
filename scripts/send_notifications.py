#!/usr/bin/env python3
# scripts/send_notifications.py

"""
Щоденна розсилка email-сповіщень системи моніторингу.

Запускається ЗЗОВНІ Streamlit-застосунку — з GitHub Actions за розкладом
(.github/workflows/notifications.yml), бо сам застосунок працює лише тоді,
коли відкритий у когось у браузері.

Що робить за один запуск:
1. Читає користувачів із users_access.xlsx (той самий файл, що й застосунок).
2. Читає заявки moніторингу з Supabase (monitoring_requests).
3. Формує ПЕРСОНАЛЬНІ сповіщення за роллю:

   ССП (відповідальна особа):
   • нагадування про дедлайн подання (до 15 числа місяця після кварталу) —
     надсилається у "розумні" дні: за 10, 5, 2 і 1 день до дедлайну,
     і ЛИШЕ якщо за ССП користувача ще немає подання за звітний квартал;
   • дайджест: заявки його ССП, повернуті на доопрацювання (з коментарем
     координатора) + погоджені за останню добу.

   Керівник ССП / Керівник управління / Заступник керівника ССП:
   • дайджест: заявки його ССП зі статусом саме ЙОГО ланки
     ("Очікує: Керівник ССП" / "Очікує: Керівник управління" /
      "Очікує: Заступник керівника ССП"), з тривалістю очікування.

   Адміністратор (координатор):
   • дайджест по ЙОГО закріплених ССП: нові заявки "Очікує погодження"
     за добу; кількість заявок, що чекають понад 5 днів (окремим блоком —
     це критичний сигнал); повернуті, які так і не переподані понад 7 днів.

   Супер-адмін:
   • зведений дайджест по всій системі + запити на ручне закриття,
     що очікують підтвердження (closeout_requests).

4. Антиспам:
   • перед кожною відправкою перевіряє notification_log: той самий
     (отримувач + тип + related_key) не надсилається повторно протягом
     періоду охолодження (дедлайн-нагадування — 1 раз на календарний день
     "розкладу", дайджести — не частіше 1 разу на добу);
   • якщо для користувача НЕМАЄ жодної змістовної події — лист НЕ
     надсилається взагалі (порожні дайджести заборонені);
   • кілька подій одного отримувача обʼєднуються в ОДИН лист.

5. Кожну відправку (успішну чи ні) логує в notification_log.

Необхідні змінні середовища (GitHub Secrets):
    SUPABASE_URL, SUPABASE_KEY
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM (опц.)
    NOTIFICATIONS_DRY_RUN=1  → тестовий прогін без реальної відправки
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

# Скрипт запускається з кореня репозиторію: python scripts/send_notifications.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.data_types import normalise_closeout_frame, normalise_monitoring_frame  # noqa: E402
from core.db import fetch_all  # noqa: E402
from core.emails import send_email  # noqa: E402
from core.timeutils import now_kyiv  # noqa: E402

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
                        ("Керівники управлінь", "unit_head"),
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


def already_sent(supabase, email: str, ntype: str, related_key: str, cooldown_hours: int = 20) -> bool:
    """Перевірка антиспаму через notification_log."""
    since = (datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)).isoformat()
    try:
        resp = (
            supabase.table("notification_log")
            .select("id")
            .eq("recipient_email", email)
            .eq("notification_type", ntype)
            .eq("related_key", related_key)
            .eq("status", "sent")
            .gte("sent_at", since)
            .limit(1)
            .execute()
        )
        return bool(resp.data)
    except Exception as exc:
        # Якщо журнал недоступний — краще НЕ надсилати, ніж заспамити.
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
        elif ns == "Повернуто на доопрацювання":
            returned[rid] = ts
    return last_change, approved, returned, stage_since


def _parse_chain(value) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    raw = clean(value)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def build_escalations(requests: pd.DataFrame, users: list[dict]) -> dict[str, list[dict]]:
    """И1: map recipient email to requests waiting on one stage for >5 days."""
    result: dict[str, list[dict]] = {}
    if requests.empty:
        return result
    superadmins = {
        clean(user.get("email")).lower()
        for user in users
        if user.get("role") == "super_admin" and clean(user.get("email"))
    }
    waiting_statuses = {
        "Очікує погодження",
        "Очікує: Керівник ССП",
        "Очікує: Керівник управління",
        "Очікує: Заступник керівника ССП",
        "Очікує: Супер-адмін",
    }
    for _, row in requests.iterrows():
        status = clean(row.get("approval_status"))
        if status not in waiting_statuses:
            continue
        days = _days_since(row.get("_stage_since") or row.get("submitted_at"))
        if days <= STALE_DAYS:
            continue
        chain = _parse_chain(row.get("approval_chain"))
        try:
            stage = max(int(float(clean(row.get("chain_stage")) or 0)), 0)
        except (TypeError, ValueError):
            stage = 0
        current = chain[stage] if stage < len(chain) else {}
        final = chain[-1] if chain else {}
        recipients = set(superadmins)
        for stage_item in (current, final):
            email = clean(stage_item.get("email")).lower()
            if email:
                recipients.add(email)
        if not recipients:
            continue
        item = {
            "id": row.get("id"),
            "strat_code": clean(row.get("strat_code")),
            "year": clean(row.get("year")),
            "quarter": clean(row.get("quarter")),
            "days": days,
            "stage_label": clean(current.get("label")) or status.replace("Очікує: ", ""),
        }
        for email in recipients:
            result.setdefault(email, []).append(item)
    for items in result.values():
        items.sort(key=lambda item: (-int(item["days"]), str(item["strat_code"])))
    return result


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
    print(
        f"== Розсилка сповіщень, Київ: {today:%d.%m.%Y %H:%M %Z}, "
        f"DRY_RUN={DRY_RUN}, FORCE_RUN={FORCE_RUN} =="
    )
    # A6: GitHub runs at both possible UTC offsets. Exactly one run falls
    # into the Kyiv 08:00–08:59 window. Manual test runs can explicitly force.
    if not FORCE_RUN and today.hour != 8:
        print("-- Зараз у Києві не 08-ма година; розсилку тихо завершено.")
        return 0

    supabase = get_supabase()
    users = load_users()
    requests = load_requests(supabase)
    closeouts = load_pending_closeouts(supabase)

    if not users:
        return 0

    for col in ("approval_status", "submitted_at", "admin_comment", "strat_code",
                "year", "quarter", "department", "object_kind", "id"):
        if not requests.empty and col not in requests.columns:
            requests[col] = ""

    # «Останні зміни» заявок — з журналу дій (updated_at у таблиці немає):
    # request_id → (час останньої зміни, час перших "Погоджено"/"Повернуто")
    logs = load_logs(supabase)
    last_change_at, approved_at, returned_at, stage_since = build_log_maps(logs)
    if not requests.empty:
        _ids = requests["id"]
        requests["_last_change_at"] = _ids.map(last_change_at).fillna(requests["submitted_at"])
        requests["_approved_at"] = _ids.map(approved_at)
        requests["_returned_at"] = _ids.map(returned_at)
        requests["_stage_since"] = _ids.map(stage_since).fillna(requests["submitted_at"])

    escalations_by_email = build_escalations(requests, users)
    period = current_reporting_period(today)
    day_str = today.strftime("%Y-%m-%d")

    sent_count = 0

    for user in users:
        email = user["email"]
        role = user["role"]
        allowed = user["allowed"]
        name = user["full_name"] or "колего"

        sections: list[str] = []
        ntype = f"{role}_digest"
        related_key = f"digest:{day_str}"

        my_requests = _req_for_ssp(requests, allowed) if not requests.empty else requests

        # ---------- И1: ескалація заявок, що зависли на одній ланці ----------
        _escalations = escalations_by_email.get(email.lower(), [])
        if _escalations:
            sections.append(block(
                f"🚨 Заявки, що очікують понад {STALE_DAYS} днів: {len(_escalations)}",
                [li(
                    f"Ланка: <b>{item['stage_label']}</b>; заявка №{item['id']} — "
                    f"захід <b>{item['strat_code']}</b> "
                    f"({item['quarter']} кв. {item['year']}); очікує <b>{item['days']} дн.</b>"
                ) for item in _escalations[:20]],
                accent="#b91c1c",
            ))

        # ---------- ССП: дедлайн-нагадування ----------
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
                            f"До <b>{deadline:%d.%m.%Y}</b> (залишилось <b>{days_left} дн.</b>) необхідно "
                            f"подати відомості моніторингу за <b>{quarter} квартал {year} року</b> "
                            f"по заходах вашого підрозділу. Станом на сьогодні подання за цей "
                            f"період від вашого ССП у системі не зафіксовано."
                        )],
                        accent="#b45309" if days_left > 2 else "#b91c1c",
                    ))

        # ---------- ССП: повернуті та погоджені ----------
        if role == "ssp" and not my_requests.empty:
            statuses = my_requests["approval_status"].astype(str)

            returned = my_requests[statuses == "Повернуто на доопрацювання"]
            if not returned.empty:
                items = []
                for _, r in returned.head(10).iterrows():
                    comment = clean(r.get("admin_comment"))
                    comment_part = f" Коментар координатора: «{comment[:160]}»" if comment else ""
                    items.append(li(
                        f"Захід <b>{clean(r.get('strat_code'))}</b> "
                        f"({clean(r.get('quarter'))} кв. {clean(r.get('year'))}) — "
                        f"повернуто на доопрацювання.{comment_part}"
                    ))
                sections.append(block("↩️ Повернуто на доопрацювання", items, accent="#b91c1c"))

            approved_recent = my_requests[
                (statuses == "Погоджено")
                & (my_requests["_approved_at"].apply(_hours_since_or_none).fillna(9999) <= 26)
            ]
            if not approved_recent.empty:
                sections.append(block(
                    "✅ Погоджено за останню добу",
                    [li(
                        f"Захід <b>{clean(r.get('strat_code'))}</b> "
                        f"({clean(r.get('quarter'))} кв. {clean(r.get('year'))})"
                    ) for _, r in approved_recent.head(10).iterrows()],
                    accent="#15803d",
                ))

        # ---------- Ланки схеми погодження: що чекає САМЕ цієї ролі ----------
        # Статуси ланок — ті самі, що ставить застосунок
        # (core/approval_schemes.STAGE_WAITING_STATUS).
        STAGE_STATUS_BY_ROLE = {
            "ssp_head": "Очікує: Керівник ССП",
            "unit_head": "Очікує: Керівник управління",
            "ssp_deputy": "Очікує: Заступник керівника ССП",
        }
        stage_status = STAGE_STATUS_BY_ROLE.get(role)
        if stage_status and not my_requests.empty:
            waiting_sign = my_requests[
                my_requests["approval_status"].astype(str) == stage_status
            ]
            if not waiting_sign.empty:
                items = []
                for _, r in waiting_sign.head(15).iterrows():
                    days = _days_since(r.get("_last_change_at") or r.get("submitted_at"))
                    flag = " ⚠️" if days >= STALE_DAYS else ""
                    items.append(li(
                        f"Захід <b>{clean(r.get('strat_code'))}</b> "
                        f"({clean(r.get('quarter'))} кв. {clean(r.get('year'))}) — "
                        f"очікує вашого рішення {days} дн.{flag}"
                    ))
                sections.append(block(
                    f"✍️ Очікують вашого рішення: {len(waiting_sign)}",
                    items,
                ))

        # ---------- Адміністратор ----------
        if role in ("admin", "super_admin") and not my_requests.empty:
            statuses = my_requests["approval_status"].astype(str)

            new_pending = my_requests[
                (statuses == "Очікує погодження")
                & (my_requests["submitted_at"].apply(_hours_since) <= 26)
            ]
            if not new_pending.empty:
                sections.append(block(
                    f"📬 Нові заявки за добу: {len(new_pending)}",
                    [li(
                        f"Захід <b>{clean(r.get('strat_code'))}</b> "
                        f"({clean(r.get('quarter'))} кв. {clean(r.get('year'))})"
                    ) for _, r in new_pending.head(15).iterrows()],
                ))

            returned_stuck = my_requests[
                (statuses == "Повернуто на доопрацювання")
                & (my_requests["_returned_at"].apply(_days_since_or_none).fillna(0) >= RETURNED_STALE_DAYS)
            ]
            if not returned_stuck.empty:
                sections.append(block(
                    f"🕳 Повернуті й не переподані понад {RETURNED_STALE_DAYS} днів: {len(returned_stuck)}",
                    [li(
                        f"Захід <b>{clean(r.get('strat_code'))}</b> "
                        f"({clean(r.get('quarter'))} кв. {clean(r.get('year'))})"
                    ) for _, r in returned_stuck.head(10).iterrows()],
                    accent="#b45309",
                ))

        # ---------- Супер-адмін: запити на ручне закриття ----------
        if role == "super_admin" and not closeouts.empty:
            sections.append(block(
                f"🔐 Запити на ручне закриття, що очікують підтвердження: {len(closeouts)}",
                [li(
                    f"Захід <b>{clean(r.get('strat_code'))}</b> "
                    f"({clean(r.get('period_quarter'))} кв. {clean(r.get('period_year'))}) — "
                    f"від {clean(r.get('admin_email'))}"
                ) for _, r in closeouts.head(10).iterrows()],
                accent="#6d28d9",
            ))

        # ---------- Відправка (тільки якщо є що сказати) ----------
        if not sections:
            continue

        if already_sent(supabase, email, ntype, related_key):
            print(f"-- {email}: {ntype} вже надсилався сьогодні, пропускаю")
            continue

        role_label = {
            "ssp": "відповідальної особи ССП",
            "ssp_head": "керівника ССП",
            "unit_head": "керівника управління",
            "ssp_deputy": "заступника керівника ССП",
            "admin": "координатора",
            "super_admin": "супер-адміністратора",
        }.get(role, role)

        subject = f"Моніторинг СП — сповіщення для {role_label} · {today:%d.%m.%Y}"
        body = (
            f'<p>Вітаємо, <b>{name}</b>!</p>'
            f'<p>Актуальні події системи моніторингу, що стосуються вас:</p>'
            + "".join(sections)
            + '<p style="margin-top:16px;">Перейдіть у систему, щоб опрацювати зазначені пункти.</p>'
        )

        if DRY_RUN:
            print(f"[DRY] {email} ({role}) ← {subject} ({len(sections)} блок(ів))")
            sent_count += 1
            continue

        ok, error = send_email(email, subject, body, title="Сповіщення системи моніторингу")
        log_notification(supabase, email, role, ntype, related_key, subject, body, ok, error)
        print(f"{'OK ' if ok else 'ERR'} {email} ({role}) — {error or 'надіслано'}")
        if ok:
            sent_count += 1

    print(f"== Готово: надіслано {sent_count} лист(ів) ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
