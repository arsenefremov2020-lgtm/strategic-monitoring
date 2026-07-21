# core/auth.py

"""Авторизація, підписана добова cookie-сесія та контроль бездіяльності."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime, time as datetime_time, timedelta
from html import escape
from typing import Any

import streamlit as st

from core.timeutils import KYIV_TZ, now_kyiv

try:
    import extra_streamlit_components as stx
except ImportError:  # застосунок лишається доступним до встановлення requirements.txt
    stx = None

from config.users import (
    GUEST_USER,
    get_user_by_email,
    normalize_email,
    user_exists,
)
from config.roles import ROLE_GUEST, get_role_label


SESSION_USER_KEY = "current_user"
SESSION_AUTH_EMAIL_KEY = "auth_email"
SESSION_IS_AUTHENTICATED_KEY = "is_authenticated"
SESSION_LOGIN_ERROR_KEY = "login_error"
SESSION_LAST_ACTIVITY_KEY = "auth_last_activity_epoch"
SESSION_LAST_COOKIE_REFRESH_KEY = "auth_last_cookie_refresh_epoch"
SESSION_TIMEOUT_MESSAGE_KEY = "auth_timeout_message"
SESSION_COOKIE_MANAGER_KEY = "auth_cookie_manager_instance"
SESSION_LOGOUT_GUARD_KEY = "auth_explicit_logout"

AUTH_COOKIE_NAME = "strategic_monitoring_auth"
AUTH_LOGOUT_TOMBSTONE = "__strategic_monitoring_logged_out__"
AUTH_COOKIE_REFRESH_SECONDS = 30
INACTIVITY_TIMEOUT_SECONDS = 60 * 60
LOGGER = logging.getLogger(__name__)


def _now_epoch() -> int:
    return int(time.time())


def _kyiv_now() -> datetime:
    return now_kyiv()


def _end_of_kyiv_day() -> datetime:
    now = _kyiv_now()
    tomorrow = now.date() + timedelta(days=1)
    return datetime.combine(tomorrow, datetime_time.min, tzinfo=KYIV_TZ)


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _auth_secret() -> str | None:
    """Читає секрет підпису cookie без жодного небезпечного fallback."""
    try:
        nested = st.secrets.get("auth", {})
        if nested and nested.get("cookie_secret"):
            return str(nested.get("cookie_secret")).strip()
        root_value = st.secrets.get("AUTH_COOKIE_SECRET")
        if root_value:
            return str(root_value).strip()
    except Exception as exc:
        LOGGER.debug("Секрет cookie не прочитано зі Streamlit secrets: %s", exc)
    env_value = os.environ.get("AUTH_COOKIE_SECRET", "").strip()
    return env_value or None


def _cookie_manager():
    """Повертає один CookieManager у межах поточної сесії Streamlit."""
    if stx is None:
        return None
    manager = st.session_state.get(SESSION_COOKIE_MANAGER_KEY)
    if manager is None:
        manager = stx.CookieManager(key="strategic_monitoring_auth_cookie_manager")
        st.session_state[SESSION_COOKIE_MANAGER_KEY] = manager
    return manager


def _get_cookie() -> str | None:
    manager = _cookie_manager()
    if manager is None:
        return None
    try:
        cookies = manager.get_all(key="strategic_monitoring_auth_cookie_get") or {}
        value = cookies.get(AUTH_COOKIE_NAME)
        return str(value) if value else None
    except Exception as exc:
        LOGGER.warning("Не вдалося прочитати cookie входу: %s", exc)
        return None


def _set_cookie(token: str) -> bool:
    manager = _cookie_manager()
    if manager is None:
        return False
    try:
        manager.set(
            AUTH_COOKIE_NAME,
            token,
            key="strategic_monitoring_auth_cookie_set",
            path="/",
            expires_at=_end_of_kyiv_day(),
            secure=True,
            same_site="strict",
        )
        return True
    except Exception as exc:
        LOGGER.warning("Не вдалося записати cookie входу: %s", exc)
        return False


def _delete_cookie() -> None:
    manager = _cookie_manager()
    if manager is None:
        return
    try:
        manager.delete(AUTH_COOKIE_NAME, key="strategic_monitoring_auth_cookie_delete")
    except Exception as exc:
        LOGGER.warning("Не вдалося видалити cookie входу: %s", exc)
        return


def _set_logout_tombstone() -> bool:
    """Надійно перекриває попередню cookie-сесію після явного виходу.

    CookieManager виконує браузерні операції через компонент Streamlit. Якщо одразу
    після ``delete`` зробити ``st.rerun()``, браузер інколи ще встигає повернути стару
    cookie, і користувача автоматично авторизує знову. Тому при виході спочатку
    перезаписуємо auth-cookie спеціальним невалідним значенням. Навіть якщо фізичне
    видалення затримається, старий підписаний токен уже не може відновити сесію.
    Наступний успішний вхід просто перезапише tombstone новим валідним токеном.
    """
    manager = _cookie_manager()
    if manager is None:
        return False
    try:
        manager.set(
            AUTH_COOKIE_NAME,
            AUTH_LOGOUT_TOMBSTONE,
            key="strategic_monitoring_auth_cookie_logout_tombstone",
            path="/",
            expires_at=_end_of_kyiv_day(),
            secure=True,
            same_site="strict",
        )
        return True
    except Exception as exc:
        LOGGER.warning("Не вдалося перекрити cookie входу під час виходу: %s", exc)
        return False


def _issue_token(email: str, last_activity: int | None = None) -> str | None:
    secret = _auth_secret()
    if not secret:
        return None
    now = _kyiv_now()
    payload = {
        "email": normalize_email(email),
        "day": now.date().isoformat(),
        "issued_at": _now_epoch(),
        "last_activity": int(last_activity or _now_epoch()),
        "expires_at": int(_end_of_kyiv_day().timestamp()),
    }
    payload_bytes = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    return f"{_b64encode(payload_bytes)}.{_b64encode(signature)}"


def _verify_token(token: str | None) -> dict[str, Any] | None:
    secret = _auth_secret()
    if not secret or not token or "." not in token:
        return None
    try:
        payload_part, signature_part = token.split(".", 1)
        payload_bytes = _b64decode(payload_part)
        supplied_signature = _b64decode(signature_part)
        expected_signature = hmac.new(
            secret.encode("utf-8"), payload_bytes, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None
        payload = json.loads(payload_bytes.decode("utf-8"))
        if payload.get("day") != _kyiv_now().date().isoformat():
            return None
        if int(payload.get("expires_at") or 0) <= _now_epoch():
            return None
        email = normalize_email(payload.get("email"))
        if not email or not user_exists(email):
            return None
        user = get_user_by_email(email)
        if user.get("role") == ROLE_GUEST:
            return None
        payload["email"] = email
        return payload
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def init_auth_state() -> None:
    if SESSION_USER_KEY not in st.session_state:
        st.session_state[SESSION_USER_KEY] = GUEST_USER.copy()
    if SESSION_AUTH_EMAIL_KEY not in st.session_state:
        st.session_state[SESSION_AUTH_EMAIL_KEY] = None
    if SESSION_IS_AUTHENTICATED_KEY not in st.session_state:
        st.session_state[SESSION_IS_AUTHENTICATED_KEY] = False
    if SESSION_LOGIN_ERROR_KEY not in st.session_state:
        st.session_state[SESSION_LOGIN_ERROR_KEY] = None
    if SESSION_LAST_ACTIVITY_KEY not in st.session_state:
        st.session_state[SESSION_LAST_ACTIVITY_KEY] = None
    if SESSION_LAST_COOKIE_REFRESH_KEY not in st.session_state:
        st.session_state[SESSION_LAST_COOKIE_REFRESH_KEY] = 0
    if SESSION_LOGOUT_GUARD_KEY not in st.session_state:
        st.session_state[SESSION_LOGOUT_GUARD_KEY] = False


def get_current_user() -> dict:
    init_auth_state()
    user = st.session_state.get(SESSION_USER_KEY)
    return user if user else GUEST_USER.copy()


def set_current_user(user: dict | None, *, persist: bool = False,
                     last_activity: int | None = None) -> None:
    if not user:
        user = GUEST_USER.copy()
    is_real_user = user.get("role") != ROLE_GUEST
    activity = int(last_activity or _now_epoch()) if is_real_user else None
    st.session_state[SESSION_USER_KEY] = user
    st.session_state[SESSION_AUTH_EMAIL_KEY] = user.get("email")
    st.session_state[SESSION_IS_AUTHENTICATED_KEY] = is_real_user
    st.session_state[SESSION_LAST_ACTIVITY_KEY] = activity
    if is_real_user:
        # Успішний явний вхід знімає локальний захист, встановлений кнопкою «Вийти».
        st.session_state[SESSION_LOGOUT_GUARD_KEY] = False
    if persist and is_real_user:
        token = _issue_token(str(user.get("email") or ""), activity)
        if token and _set_cookie(token):
            st.session_state[SESSION_LAST_COOKIE_REFRESH_KEY] = activity


def logout_user(*, timeout: bool = False) -> None:
    # Спочатку блокуємо автоматичне відновлення в поточній Streamlit-сесії.
    # Потім перекриваємо браузерну cookie tombstone-значенням. Це надійніше за
    # delete + негайний rerun, бо старий токен не може «ожити» на наступному запуску.
    st.session_state[SESSION_LOGOUT_GUARD_KEY] = True
    if not _set_logout_tombstone():
        # Fallback для середовищ, де CookieManager не підтримав set.
        _delete_cookie()
    st.session_state[SESSION_USER_KEY] = GUEST_USER.copy()
    st.session_state[SESSION_AUTH_EMAIL_KEY] = None
    st.session_state[SESSION_IS_AUTHENTICATED_KEY] = False
    st.session_state[SESSION_LOGIN_ERROR_KEY] = None
    st.session_state[SESSION_LAST_ACTIVITY_KEY] = None
    st.session_state[SESSION_LAST_COOKIE_REFRESH_KEY] = 0
    if timeout:
        st.session_state[SESSION_TIMEOUT_MESSAGE_KEY] = (
            "Сесію завершено через бездіяльність. Увійдіть знову."
        )


def is_authenticated() -> bool:
    init_auth_state()
    return bool(st.session_state.get(SESSION_IS_AUTHENTICATED_KEY, False))


def is_guest() -> bool:
    return get_current_user().get("role") == ROLE_GUEST


def get_current_user_email() -> str | None:
    return get_current_user().get("email")


def get_current_user_role() -> str:
    return get_current_user().get("role", ROLE_GUEST)


def get_current_user_role_label() -> str:
    user = get_current_user()
    return user.get("role_label") or get_role_label(user.get("role"))


def get_current_user_ssp() -> str | None:
    return get_current_user().get("ssp")


def is_current_user_owner() -> bool:
    return bool(get_current_user().get("is_owner", False))


def get_password_from_user_profile(email: str | None) -> str | None:
    email = normalize_email(email)
    if not email:
        return None
    password = get_user_by_email(email).get("password")
    if not password:
        return None
    password = str(password).strip()
    return password[:-2] if password.endswith(".0") else password


def get_password_from_secrets(email: str | None) -> str | None:
    email = normalize_email(email)
    if not email:
        return None
    try:
        passwords = st.secrets.get("passwords", {})
    except Exception as exc:
        LOGGER.debug("Паролі не прочитано зі Streamlit secrets: %s", exc)
        return None
    return passwords.get(email) if passwords else None


def check_password(email: str | None, password: str | None) -> bool:
    email = normalize_email(email)
    if not email or not password:
        return False
    expected_password = get_password_from_user_profile(email) or get_password_from_secrets(email)
    if not expected_password:
        return False
    entered_password = str(password).strip()
    if entered_password.endswith(".0"):
        entered_password = entered_password[:-2]
    return entered_password == str(expected_password).strip()


def login_by_email_and_password(
    email: str | None, password: str | None
) -> tuple[bool, dict, str | None]:
    email = normalize_email(email)
    if not email:
        return False, GUEST_USER.copy(), "Введіть електронну пошту."
    if not password:
        return False, GUEST_USER.copy(), "Введіть пароль."
    if not user_exists(email):
        return False, GUEST_USER.copy(), "Користувача з такою електронною поштою не знайдено."
    user = get_user_by_email(email)
    if user.get("role") == ROLE_GUEST:
        return False, GUEST_USER.copy(), "Користувач неактивний або не має доступу до системи."
    if not check_password(email, password):
        return False, GUEST_USER.copy(), "Невірний пароль."
    set_current_user(user, persist=True)
    return True, user, None


def _restore_from_cookie() -> bool:
    # Після натискання «Вийти» не дозволяємо цьому ж Streamlit-сеансу
    # автоматично відновити користувача зі старої cookie навіть на один rerun.
    if st.session_state.get(SESSION_LOGOUT_GUARD_KEY, False):
        return False
    if is_authenticated():
        return True
    token = _get_cookie()
    if not token:
        return False
    if token == AUTH_LOGOUT_TOMBSTONE:
        return False
    payload = _verify_token(token)
    if not payload:
        _delete_cookie()
        return False
    last_activity = int(payload.get("last_activity") or 0)
    if _now_epoch() - last_activity > INACTIVITY_TIMEOUT_SECONDS:
        logout_user(timeout=True)
        return False
    user = get_user_by_email(payload["email"])
    set_current_user(user, persist=False, last_activity=last_activity)
    return True


def _enforce_and_touch_activity() -> bool:
    if not is_authenticated():
        return False
    now = _now_epoch()
    previous = int(st.session_state.get(SESSION_LAST_ACTIVITY_KEY) or 0)
    if previous and now - previous > INACTIVITY_TIMEOUT_SECONDS:
        logout_user(timeout=True)
        return False
    st.session_state[SESSION_LAST_ACTIVITY_KEY] = now
    last_refresh = int(st.session_state.get(SESSION_LAST_COOKIE_REFRESH_KEY) or 0)
    if now - last_refresh >= AUTH_COOKIE_REFRESH_SECONDS:
        email = str(get_current_user().get("email") or "")
        token = _issue_token(email, now)
        if token and _set_cookie(token):
            st.session_state[SESSION_LAST_COOKIE_REFRESH_KEY] = now
    return True


def _render_sidebar_auth_notice(message: str, kind: str) -> None:
    """Render a semantic auth notice whose appearance is controlled by assets/app.css."""
    safe_kind = "success" if kind == "success" else "warning"
    st.sidebar.markdown(
        f'<div data-auth-sidebar-notice="{safe_kind}">{escape(str(message))}</div>',
        unsafe_allow_html=True,
    )


def _render_sidebar_auth_profile(user: dict) -> None:
    """Render authenticated-user metadata as one stable sidebar block."""
    full_name = escape(str(user.get("full_name") or "Користувач"))
    role_label = escape(str(user.get("role_label") or get_role_label(user.get("role"))))
    lines = [
        f'<div data-auth-sidebar-profile-line="true">Користувач: {full_name}</div>',
        f'<div data-auth-sidebar-profile-line="true">Роль: {role_label}</div>',
    ]

    email = str(user.get("email") or "").strip()
    if email:
        safe_email = escape(email)
        safe_mailto = escape(email, quote=True)
        lines.append(
            '<div data-auth-sidebar-profile-line="true">'
            f'Email: <a href="mailto:{safe_mailto}">{safe_email}</a></div>'
        )

    ssp = str(user.get("ssp") or "").strip()
    if ssp:
        lines.append(
            '<div data-auth-sidebar-profile-line="true">'
            f'ССП: {escape(ssp)}</div>'
        )

    st.sidebar.markdown(
        '<div data-auth-sidebar-profile="true">' + "".join(lines) + "</div>",
        unsafe_allow_html=True,
    )


def render_login_form() -> dict:
    init_auth_state()
    _restore_from_cookie()
    _enforce_and_touch_activity()
    user = get_current_user()

    st.sidebar.markdown(
        '<div data-auth-sidebar-title="login">Вхід до системи</div>',
        unsafe_allow_html=True,
    )

    timeout_message = st.session_state.pop(SESSION_TIMEOUT_MESSAGE_KEY, None)
    if timeout_message and not is_authenticated():
        _render_sidebar_auth_notice(timeout_message, "warning")

    if is_authenticated():
        _render_sidebar_auth_notice("Вхід виконано", "success")
        _render_sidebar_auth_profile(user)
        if not _auth_secret():
            _render_sidebar_auth_notice(
                "Запам’ятовування входу вимкнено: адміністратор ще не додав секрет cookie.",
                "warning",
            )
        if st.sidebar.button("Вийти з системи", key="logout_button"):
            logout_user()
            st.rerun()
        return user

    with st.sidebar.form("login_form"):
        email = st.text_input(
            "Електронна пошта", placeholder="name@example.com", key="login_email_input"
        )
        password = st.text_input("Пароль", type="password", key="login_password_input")
        submitted = st.form_submit_button("Увійти")

    if submitted:
        success, _, error_message = login_by_email_and_password(email, password)
        if success:
            st.session_state[SESSION_LOGIN_ERROR_KEY] = None
            st.rerun()
        else:
            logout_user()
            st.session_state[SESSION_LOGIN_ERROR_KEY] = error_message

    login_error = st.session_state.get(SESSION_LOGIN_ERROR_KEY)
    if login_error:
        st.sidebar.error(login_error)
    return get_current_user()

