# core/emails.py

"""
Надсилання email-сповіщень системи моніторингу.

Модуль спроєктований так, щоб працювати у ДВОХ середовищах:
1. усередині Streamlit-застосунку (конфігурація зі st.secrets);
2. у зовнішньому планувальнику GitHub Actions (конфігурація зі змінних
   середовища) — саме він розсилає щоденні дайджести й нагадування,
   бо Streamlit-застосунок "живе" лише коли відкритий у когось у браузері.

Конфігурація (secrets.toml АБО environment):
    [smtp]                    |  SMTP_HOST
    host = "smtp.gmail.com"   |  SMTP_PORT
    port = 465                |  SMTP_USER
    user = "bot@gmail.com"    |  SMTP_PASSWORD
    password = "app-password" |  SMTP_FROM (необовʼязково)
    from = "Моніторинг СП <bot@gmail.com>"

Рекомендований безкоштовний варіант для старту: окрема Gmail-скринька
(наприклад monitoring.sp.bot@gmail.com) + "пароль застосунку"
(Google Account → Security → App passwords). Ліміт Gmail ~500 листів/добу —
для 100 користувачів із дайджест-підходом цього достатньо.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr


# ------------------------------------------------------------
# Конфігурація
# ------------------------------------------------------------

def _get_smtp_config() -> dict | None:
    """Читає SMTP-конфігурацію зі st.secrets (Streamlit) або env (Actions)."""

    # 1. Streamlit secrets
    try:
        import streamlit as st  # локальний імпорт: модуль має працювати й без Streamlit
        smtp = st.secrets.get("smtp", None)
        if smtp and smtp.get("host") and smtp.get("user") and smtp.get("password"):
            return {
                "host": smtp.get("host"),
                "port": int(smtp.get("port", 465)),
                "user": smtp.get("user"),
                "password": smtp.get("password"),
                "from": smtp.get("from") or smtp.get("user"),
            }
    except Exception:
        pass

    # 2. Environment (GitHub Actions)
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    if host and user and password:
        return {
            "host": host,
            "port": int(os.environ.get("SMTP_PORT", "465")),
            "user": user,
            "password": password,
            "from": os.environ.get("SMTP_FROM") or user,
        }

    return None


def email_configured() -> bool:
    """True, якщо SMTP налаштований (можна показувати статус у інтерфейсі)."""
    return _get_smtp_config() is not None


# ------------------------------------------------------------
# HTML-обгортка листа у фірмовому стилі системи
# ------------------------------------------------------------

def render_email_html(title: str, body_html: str, footer_note: str = "") -> str:
    """Обгортає вміст листа у фірмовий шаблон (синя шапка, охайні картки)."""
    footer = footer_note or (
        "Це автоматичне сповіщення системи моніторингу Стратегічного плану "
        "Мінекономіки. Відповідати на цей лист не потрібно."
    )
    return f"""\
<!DOCTYPE html>
<html lang="uk">
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Arial,sans-serif;">
  <div style="max-width:640px;margin:0 auto;padding:24px 12px;">
    <div style="background:#005BBB;border-radius:16px 16px 0 0;padding:18px 24px;">
      <div style="color:#FFD500;font-size:12px;font-weight:800;letter-spacing:.4px;">
        🇺🇦 МІНЕКОНОМІКИ · СИСТЕМА МОНІТОРИНГУ СТРАТЕГІЧНОГО ПЛАНУ
      </div>
      <div style="color:#ffffff;font-size:20px;font-weight:900;margin-top:6px;">
        {title}
      </div>
    </div>
    <div style="background:#ffffff;border:1px solid #d8dee9;border-top:none;
                border-radius:0 0 16px 16px;padding:22px 24px;color:#0f172a;
                font-size:14px;line-height:1.55;">
      {body_html}
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0 12px 0;">
      <div style="color:#64748b;font-size:11px;">{footer}</div>
    </div>
  </div>
</body>
</html>"""


# ------------------------------------------------------------
# Відправка
# ------------------------------------------------------------

def send_email(
    to_email: str,
    subject: str,
    body_html: str,
    title: str | None = None,
) -> tuple[bool, str | None]:
    """
    Надсилає один лист.

    Повертає (success, error_message).
    Ніколи не кидає виняток назовні — помилка повертається текстом,
    щоб планувальник міг залогувати її в notification_log і рухатися далі.
    """
    config = _get_smtp_config()

    if not config:
        return False, "SMTP не налаштований (немає st.secrets[smtp] або env SMTP_*)."

    if not to_email or "@" not in str(to_email):
        return False, f"Некоректна адреса отримувача: {to_email!r}"

    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = formataddr(("Моніторинг СП · Мінекономіки", config["from"]))
        message["To"] = to_email

        html = render_email_html(title or subject, body_html)
        message.attach(MIMEText(html, "html", "utf-8"))

        context = ssl.create_default_context()
        port = config["port"]

        if port == 465:
            with smtplib.SMTP_SSL(config["host"], port, context=context, timeout=30) as server:
                server.login(config["user"], config["password"])
                server.sendmail(config["from"], [to_email], message.as_string())
        else:
            with smtplib.SMTP(config["host"], port, timeout=30) as server:
                server.starttls(context=context)
                server.login(config["user"], config["password"])
                server.sendmail(config["from"], [to_email], message.as_string())

        return True, None

    except Exception as exc:  # noqa: BLE001 — свідомо ловимо все й повертаємо текстом
        return False, str(exc)
