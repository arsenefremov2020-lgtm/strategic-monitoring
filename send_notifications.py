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

   Керівник ССП:
   • дайджест: заявки його ССП зі статусом "Направлено на підпис"
     (тобто ті, що чекають саме його рішення), з тривалістю очікування.

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

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

# Скрипт запускається з кореня репозиторію: python scripts/send_notifications.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.emails import send_email  # noqa: E402

KYIV_UTC_OFFSET = 3  # прийнятне наближення для щоденного джоба (EEST)
DEADLINE_DAY = 15    # подання до 15 числа місяця, наступного за звітним кварталом
REMINDER_DAYS_BEFORE = [10, 5, 2, 1]   # за скільки днів до дедлайну нагадуємо
STALE_DAYS = 5                          # "заявка висить понад N днів"
RETURNED_STALE_DAYS = 7                 # повернута й не переподана понад N днів

DRY_RUN = os.environ.get("NOTIFICATIONS_DRY_RUN", "0") == "1"


# ------------------------------------------------------------
# Службові
# ------------------------------------------------------------

def now_kyiv() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=KYIV_UTC_OFFSET)


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

    for sheet, role in (("Керівники ССП", "ssp_head"), ("Відповідальні за ССП", "ssp")):
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
        resp = supabase.table("monitoring_requests").select("*").execute()
        return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    except Exception as exc:
        print(f"!! Не вдалося прочитати monitoring_requests: {exc}")
        return pd.DataFrame()


def load_pending_closeouts(supabase) -> pd.DataFrame:
    try:
        resp = (
            supabase.table("closeout_requests")
            .select("*")
            .eq("approval_status", "Очікує підтвердження")
            .execute()
        )
        return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
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


def _days_since(value) -> int:
    return int(_hours_since(value) // 24)


def _req_for_ssp(requests: pd.DataFrame, allowed: list[str]) -> pd.DataFrame:
    """Фільтр заявок за індексами ССП користувача (за колонкою ssp_index або текстовою)."""
    if requests.empty or not allowed:
        return requests.iloc[0:0]
    if "*" in allowed:
        return requests
    import re

    def matches(row) -> bool:
        for col in ("ssp_index", "ССП", "Індекс ССП", "structural_unit_index"):
            if col in row.index:
                found = re.findall(r"\d+", clean(row[col]))
                joined = "".join(found) if found else ""
                if joined and joined in allowed:
                    return True
                if any(f in allowed for f in found):
                    return True
        return False

    mask = requests.apply(matches, axis=1)
    return requests[mask]


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
    print(f"== Розсилка сповіщень, Київ: {today:%d.%m.%Y %H:%M}, DRY_RUN={DRY_RUN} ==")

    supabase = get_supabase()
    users = load_users()
    requests = load_requests(supabase)
    closeouts = load_pending_closeouts(supabase)

    if not users:
        return 0

    for col in ("approval_status", "submitted_at", "updated_at", "period_year",
                "period_quarter", "admin_comment", "strat_code"):
        if not requests.empty and col not in requests.columns:
            requests[col] = ""

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

        # ---------- ССП: дедлайн-нагадування ----------
        if role == "ssp" and period:
            year, quarter, deadline = period
            days_left = (deadline.date() - today.date()).days
            if days_left in REMINDER_DAYS_BEFORE:
                has_submission = False
                if not my_requests.empty:
                    mask = (
                        my_requests["period_year"].astype(str).str.contains(year, na=False)
                        & my_requests["period_quarter"].astype(str).str.contains(quarter, na=False)
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
                        f"({clean(r.get('period_quarter'))} кв. {clean(r.get('period_year'))}) — "
                        f"повернуто на доопрацювання.{comment_part}"
                    ))
                sections.append(block("↩️ Повернуто на доопрацювання", items, accent="#b91c1c"))

            approved_recent = my_requests[
                (statuses == "Погоджено")
                & (my_requests["updated_at"].apply(_hours_since) <= 26)
            ]
            if not approved_recent.empty:
                sections.append(block(
                    "✅ Погоджено за останню добу",
                    [li(
                        f"Захід <b>{clean(r.get('strat_code'))}</b> "
                        f"({clean(r.get('period_quarter'))} кв. {clean(r.get('period_year'))})"
                    ) for _, r in approved_recent.head(10).iterrows()],
                    accent="#15803d",
                ))

        # ---------- Керівник ССП: очікує підпису ----------
        if role == "ssp_head" and not my_requests.empty:
            waiting_sign = my_requests[my_requests["approval_status"].astype(str) == "Направлено на підпис"]
            if not waiting_sign.empty:
                items = []
                for _, r in waiting_sign.head(15).iterrows():
                    days = _days_since(r.get("updated_at") or r.get("submitted_at"))
                    flag = " ⚠️" if days >= STALE_DAYS else ""
                    items.append(li(
                        f"Захід <b>{clean(r.get('strat_code'))}</b> "
                        f"({clean(r.get('period_quarter'))} кв. {clean(r.get('period_year'))}) — "
                        f"очікує вашого підпису {days} дн.{flag}"
                    ))
                sections.append(block(
                    f"✍️ Очікують вашого підпису: {len(waiting_sign)}",
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
                        f"({clean(r.get('period_quarter'))} кв. {clean(r.get('period_year'))})"
                    ) for _, r in new_pending.head(15).iterrows()],
                ))

            stale = my_requests[
                (statuses == "Очікує погодження")
                & (my_requests["submitted_at"].apply(_days_since) >= STALE_DAYS)
            ]
            if not stale.empty:
                sections.append(block(
                    f"⏳ На розгляді понад {STALE_DAYS} днів: {len(stale)}",
                    [li(
                        f"Захід <b>{clean(r.get('strat_code'))}</b> — чекає "
                        f"{_days_since(r.get('submitted_at'))} дн."
                    ) for _, r in stale.head(15).iterrows()],
                    accent="#b91c1c",
                ))

            returned_stuck = my_requests[
                (statuses == "Повернуто на доопрацювання")
                & (my_requests["updated_at"].apply(_days_since) >= RETURNED_STALE_DAYS)
            ]
            if not returned_stuck.empty:
                sections.append(block(
                    f"🕳 Повернуті й не переподані понад {RETURNED_STALE_DAYS} днів: {len(returned_stuck)}",
                    [li(
                        f"Захід <b>{clean(r.get('strat_code'))}</b> "
                        f"({clean(r.get('period_quarter'))} кв. {clean(r.get('period_year'))})"
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
