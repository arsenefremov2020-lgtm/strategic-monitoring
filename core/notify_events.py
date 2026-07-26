# core/notify_events.py

"""
Миттєві email-сповіщення про ПОДІЇ (на відміну від щоденних дайджестів
scripts/send_notifications.py, які запускає GitHub Actions).

Викликаються прямо зі Streamlit-сторінок у момент дії:
- заявку подано → пороговий зведений лист першій ланці (не частіше разу на 2 години);
- ланка погодила → лист наступній ланці;
- координатор змінив схему → інформаційний лист новим майбутнім ланкам;
- заявку повернуто → лист адресату повернення (подавачу/ланці);
- заявку погоджено остаточно → лист подавачу;
- ручне закриття підтверджено → лист керівнику ССП.

Принципи:
- НІКОЛИ не ламає інтерфейс: будь-яка помилка (не налаштований SMTP,
  мережа) мовчки логуються в notification_log зі status=failed;
- кожен лист фіксується в notification_log (аудит + антидубль).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from html import escape

from core import approval_schemes as schemes
from core.emails import send_email, email_configured
from core.errors import log_exception
from core.timeutils import now_kyiv


def _log(supabase, email: str, ntype: str, related_key: str,
         subject: str, body: str, ok: bool, error: str | None,
         sent_at: str | None = None) -> None:
    try:
        payload = {
            "recipient_email": email,
            "recipient_role": "",
            "notification_type": ntype,
            "related_key": related_key,
            "subject": subject,
            "body_preview": body[:500],
            "status": "sent" if ok else "failed",
            "error": error,
        }
        if sent_at:
            payload["sent_at"] = sent_at
        supabase.table("notification_log").insert(payload).execute()
    except Exception as exc:
        log_exception("Запис результату миттєвого email у notification_log", exc)


def _fire(to_email: str, subject: str, body_html: str,
          ntype: str, related_key: str, log_sent_at: str | None = None) -> None:
    """Надіслати лист і залогувати результат. Ніколи не кидає винятків."""
    to_email = str(to_email or "").strip().lower()
    if not to_email or "@" not in to_email:
        return
    try:
        from core.db import get_supabase_client
        supabase = get_supabase_client()
    except Exception:
        supabase = None

    if not email_configured():
        if supabase is not None:
            _log(supabase, to_email, ntype, related_key, subject, body_html,
                 False, "SMTP не налаштований", sent_at=log_sent_at)
        return

    ok, error = send_email(to_email, subject, body_html,
                           title="Сповіщення системи моніторингу")
    if supabase is not None:
        _log(
            supabase, to_email, ntype, related_key, subject, body_html, ok, error,
            sent_at=log_sent_at,
        )


def _request_line(code: str, year: str, quarter: str, kind: str = "measure") -> str:
    what = "Захід" if kind != "indicator" else "Індикатор"
    return f"{what} <b>{code}</b> · {quarter} кв. {year}"


INSTANT_NEW_REQUESTS_TYPE = "instant_new_requests"
INSTANT_NEW_REQUESTS_COOLDOWN_HOURS = 2


def _parse_timestamp(value) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _last_sent_instant_notification(supabase, email: str) -> tuple[bool, datetime | None]:
    """Повертає (журнал доступний, останній успішний пороговий лист)."""
    try:
        response = (
            supabase.table("notification_log")
            .select("sent_at")
            .eq("recipient_email", email)
            .eq("notification_type", INSTANT_NEW_REQUESTS_TYPE)
            .eq("related_key", email)
            .eq("status", "sent")
            .order("sent_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return True, (_parse_timestamp(rows[0].get("sent_at")) if rows else None)
    except Exception as exc:
        # Fail closed: якщо антиспам-журнал недоступний, не ризикуємо масовою розсилкою.
        log_exception("Перевірка cooldown миттєвих сповіщень", exc)
        return False, None


def _new_requests_for_first_stage(supabase, email: str, since: datetime,
                                  until: datetime) -> list[dict]:
    """Нові ще не опрацьовані заявки, для яких цей email є першою ланкою."""
    try:
        response = (
            supabase.table("monitoring_requests")
            .select(
                "id,strat_code,indicator_name,object_kind,department,year,quarter,"
                "submitted_at,approval_chain,chain_stage,approval_status"
            )
            .gt("submitted_at", since.isoformat())
            .lte("submitted_at", until.isoformat())
            .order("submitted_at", desc=False)
            .execute()
        )
    except Exception as exc:
        log_exception("Читання нових заявок для порогового сповіщення", exc)
        return []

    matched: list[dict] = []
    for row in response.data or []:
        if schemes.parse_stage(row.get("chain_stage")) != 0:
            continue
        if not str(row.get("approval_status") or "").strip().startswith("Очікує"):
            continue
        chain = schemes.parse_chain(row.get("approval_chain"))
        first_stage = chain[0] if chain else {}
        first_email = str(first_stage.get("email") or "").strip().lower()
        if first_email == email:
            matched.append(row)
    return matched


def _instant_request_item(row: dict) -> str:
    kind = str(row.get("object_kind") or "measure")
    code = escape(str(row.get("strat_code") or "—"))
    indicator_name = escape(str(row.get("indicator_name") or "").strip())
    department = escape(str(row.get("department") or "ССП не вказано").strip())
    year = escape(str(row.get("year") or "—"))
    quarter = escape(str(row.get("quarter") or "—"))
    object_text = (
        f"Індикатор <b>{code}</b>" if kind == "indicator"
        else f"Захід <b>{code}</b>"
    )
    if kind == "indicator" and indicator_name:
        object_text += f" — {indicator_name}"
    return f"<li>{object_text} · {department} · {quarter} кв. {year}</li>"


def notify_new_requests_throttled(stage_email: str, stage_name: str,
                                   stage_label: str) -> None:
    """
    Попередження першій ланці про НОВІ заявки, не частіше одного разу на 2 години.

    Cooldown персональний для отримувача через notification_log. Лист охоплює
    всі ще не опрацьовані заявки, що надійшли після watermark попереднього
    успішного листа; якщо листів ще не було — за останні 2 години. Наступні
    ланки погодження й адресні події використовують notify_stage_assigned(),
    notify_returned() та notify_approved() без цього cooldown.
    """
    email = str(stage_email or "").strip().lower()
    if not email or "@" not in email:
        return

    try:
        from core.db import get_supabase_client
        supabase = get_supabase_client()
    except Exception as exc:
        log_exception("Підготовка порогового сповіщення нових заявок", exc)
        return

    now = now_kyiv()
    log_available, last_sent = _last_sent_instant_notification(supabase, email)
    if not log_available:
        return

    if last_sent is not None:
        last_sent_kyiv = last_sent.astimezone(now.tzinfo)
        if now - last_sent_kyiv < timedelta(hours=INSTANT_NEW_REQUESTS_COOLDOWN_HOURS):
            return
        window_start = last_sent_kyiv
    else:
        window_start = now - timedelta(hours=INSTANT_NEW_REQUESTS_COOLDOWN_HOURS)

    # Watermark фіксуємо ДО запиту/SMTP: усе, що надійде пізніше, буде > watermark
    # і гарантовано залишиться для наступного 2-годинного вікна.
    window_end = now
    requests = _new_requests_for_first_stage(supabase, email, window_start, window_end)
    if not requests:
        return

    items = "".join(_instant_request_item(row) for row in requests)
    subject = f"Моніторинг СП: нові заявки на розгляд ({len(requests)})"
    addressee = escape(str(stage_name or stage_label or "").strip())
    greeting = f"<p>Вітаємо, <b>{addressee}</b>!</p>" if addressee else "<p>Вітаємо!</p>"
    window_phrase = (
        "За останні 2 години" if last_sent is None
        else "Від часу попереднього миттєвого повідомлення"
    )
    body = (
        greeting
        + f"<p>{window_phrase} у вашу зону погодження надійшли нові заявки "
          "на розгляд:</p>"
        + f"<ul>{items}</ul>"
        + "<p>Зверніть увагу — можливо, частину з них ви вже опрацювали; "
          "це повідомлення має характер нагадування.</p>"
        + "<p>Щоденний дайджест продовжує надходити окремо за встановленим "
          "розкладом.</p>"
    )
    _fire(
        email, subject, body, INSTANT_NEW_REQUESTS_TYPE, email,
        log_sent_at=window_end.isoformat(),
    )


# ------------------------------------------------------------
# Публічні події
# ------------------------------------------------------------

def notify_stage_assigned(stage_email: str, stage_name: str, stage_label: str,
                          code: str, year: str, quarter: str,
                          submitter: str, kind: str = "measure") -> None:
    """Заявка надійшла на ланку (перша ланка або після погодження попередньою)."""
    subject = f"Моніторинг СП: заявка очікує вашого рішення ({code})"
    body = (
        f"<p>Вітаємо, <b>{stage_name or stage_label}</b>!</p>"
        f"<p>{_request_line(code, year, quarter, kind)} — надійшла на етап "
        f"«<b>{stage_label}</b>» схеми погодження та очікує вашого рішення.</p>"
        f"<p>Подавач: {submitter}.</p>"
        f"<p>Перейдіть у свій кабінет у системі, щоб опрацювати заявку.</p>"
    )
    _fire(stage_email, subject, body, "stage_assigned",
          f"{kind}:{code}:{year}:{quarter}:{stage_label}:{stage_email}")


def notify_returned(to_email: str, to_name: str, code: str, year: str,
                    quarter: str, by_label: str, comment: str,
                    kind: str = "measure") -> None:
    subject = f"Моніторинг СП: заявку повернуто на доопрацювання ({code})"
    comment_part = f"<p>Коментар: «{comment}»</p>" if comment else ""
    body = (
        f"<p>Вітаємо, <b>{to_name or ''}</b>!</p>"
        f"<p>{_request_line(code, year, quarter, kind)} — повернуто вам "
        f"на доопрацювання ланкою «<b>{by_label}</b>».</p>"
        f"{comment_part}"
        f"<p>Опрацюйте зауваження та подайте заявку повторно.</p>"
    )
    _fire(to_email, subject, body, "returned",
          f"{kind}:{code}:{year}:{quarter}:{to_email}")


def notify_approved(to_email: str, to_name: str, code: str, year: str,
                    quarter: str, kind: str = "measure") -> None:
    subject = f"Моніторинг СП: заявку погоджено ({code})"
    body = (
        f"<p>Вітаємо, <b>{to_name or ''}</b>!</p>"
        f"<p>{_request_line(code, year, quarter, kind)} — успішно пройшла "
        f"всі етапи схеми погодження. Статус: <b>«Погоджено»</b>.</p>"
    )
    _fire(to_email, subject, body, "approved",
          f"{kind}:{code}:{year}:{quarter}:{to_email}")


def notify_closeout_to_head(head_email: str, head_name: str, code: str,
                            year: str, quarter: str, reason: str,
                            superadmin_comment: str) -> None:
    subject = f"Моніторинг СП: захід {code} закрито вручну — потрібна ваша реакція"
    body = (
        f"<p>Вітаємо, <b>{head_name or ''}</b>!</p>"
        f"<p>Захід <b>{code}</b> ({quarter} · {year}) було закрито вручну "
        f"адміністратором і підтверджено супер-адміністратором.</p>"
        f"<p>Підстава: «{reason}»</p>"
        + (f"<p>Коментар супер-адміністратора: «{superadmin_comment}»</p>" if superadmin_comment else "")
        + "<p>У своєму кабінеті ви можете <b>не заперечити</b> або "
          "<b>заперечити з коментарем</b> — у разі заперечення рішення "
          "перегляне супер-адміністратор.</p>"
    )
    _fire(head_email, subject, body, "closeout_head_ack",
          f"closeout:{code}:{year}:{quarter}:{head_email}")


def notify_superadmin_correction(to_email: str, to_name: str, code: str, year: str,
                                 quarter: str, reason: str, editor_name: str,
                                 kind: str = "measure") -> None:
    """
    Пункт 5 нового ТЗ: супер-адмін скоригував дані ВЖЕ закритої
    (final_locked) заявки. Лист летить саме на ту ланку, яка була
    ОСТАННЬОЮ в маршруті погодження цієї заявки (тобто підтвердила
    її остаточно) — з обов'язковим коментарем-обґрунтуванням.
    """
    subject = f"Моніторинг СП: дані закритого заходу {code} скориговано супер-адміном"
    body = (
        f"<p>Вітаємо, <b>{to_name or ''}</b>!</p>"
        f"<p>{_request_line(code, year, quarter, kind)} — заявку, яку ви раніше "
        f"погодили остаточно (статус «Погоджено»), щойно скоригував "
        f"<b>{editor_name or 'супер-адміністратор'}</b>.</p>"
        f"<p><b>Підстава коригування:</b> «{reason}»</p>"
        f"<p>Маршрут погодження заявки не змінювався і статус лишається "
        f"«Погоджено» — це повідомлення суто інформаційне, додаткової дії "
        f"від вас не потрібно. За потреби перегляньте історію версій заявки "
        f"у своєму кабінеті.</p>"
    )
    _fire(to_email, subject, body, "superadmin_correction",
          f"{kind}:{code}:{year}:{quarter}:{to_email}")


def notify_included_in_chain(to_email: str, to_name: str, stage_label: str,
                              changed_by: str, code: str, year: str,
                              quarter: str, kind: str = "measure") -> None:
    """Інформує майбутню ланку, яку координатор додав до схеми погодження."""
    if not str(to_email or "").strip():
        return
    subject = "Зміна схеми погодження: вас включено до схеми"
    body = (
        f"<p>Шановний(а) {to_name or stage_label or ''}!</p>"
        f"<p>{changed_by or 'Координатор'} для "
        f"{_request_line(code, year, quarter, kind)} змінив(ла) схему "
        f"погодження та включив(ла) вас як ланку «<b>{stage_label}</b>».</p>"
        f"<p>Зараз заявка може перебувати на попередній ланці. Коли настане "
        f"ваша черга ухвалювати рішення, система надішле окреме повідомлення.</p>"
    )
    _fire(
        to_email,
        subject,
        body,
        ntype="chain_included",
        related_key=f"{code}|{year}|{quarter}|{stage_label}|{to_email}",
    )


def notify_excluded_from_chain(to_email: str, to_name: str, changed_by: str,
                               code: str, year: str, quarter: str,
                               kind: str = "measure") -> None:
    """Сповіщення особі, яку виключили зі схеми погодження (ТЗ Каб.7/Адм.10)."""
    if not str(to_email or "").strip():
        return
    subject = "Зміна схеми погодження: вас виключено зі схеми"
    body = (
        f"<p>Шановний(а) {to_name or ''}!</p>"
        f"<p>{changed_by or 'Учасник схеми погодження'} для "
        f"{_request_line(code, year, quarter, kind)} змінив(ла) схему "
        f"погодження та виключив(ла) вас із неї.</p>"
        f"<p>Це службове сповіщення системи моніторингу стратегічного плану; "
        f"додаткових дій від вас не потрібно.</p>"
    )
    _fire(to_email, subject, body, ntype="chain_excluded",
          related_key=f"{code}|{year}|{quarter}")
