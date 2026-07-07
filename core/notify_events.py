# core/notify_events.py

"""
Миттєві email-сповіщення про ПОДІЇ (на відміну від щоденних дайджестів
scripts/send_notifications.py, які запускає GitHub Actions).

Викликаються прямо зі Streamlit-сторінок у момент дії:
- заявку подано → лист першій ланці погодження;
- ланка погодила → лист наступній ланці;
- заявку повернуто → лист адресату повернення (подавачу/ланці);
- заявку погоджено остаточно → лист подавачу;
- ручне закриття підтверджено → лист керівнику ССП.

Принципи:
- НІКОЛИ не ламає інтерфейс: будь-яка помилка (не налаштований SMTP,
  мережа) мовчки логуються в notification_log зі status=failed;
- кожен лист фіксується в notification_log (аудит + антидубль).
"""

from __future__ import annotations

from core.emails import send_email, email_configured


def _log(supabase, email: str, ntype: str, related_key: str,
         subject: str, body: str, ok: bool, error: str | None) -> None:
    try:
        supabase.table("notification_log").insert({
            "recipient_email": email,
            "recipient_role": "",
            "notification_type": ntype,
            "related_key": related_key,
            "subject": subject,
            "body_preview": body[:500],
            "status": "sent" if ok else "failed",
            "error": error,
        }).execute()
    except Exception:
        pass


def _fire(to_email: str, subject: str, body_html: str,
          ntype: str, related_key: str) -> None:
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
                 False, "SMTP не налаштований")
        return

    ok, error = send_email(to_email, subject, body_html,
                           title="Сповіщення системи моніторингу")
    if supabase is not None:
        _log(supabase, to_email, ntype, related_key, subject, body_html, ok, error)


def _request_line(code: str, year: str, quarter: str, kind: str = "measure") -> str:
    what = "Захід" if kind != "indicator" else "Індикатор"
    return f"{what} <b>{code}</b> · {quarter} кв. {year}"


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
