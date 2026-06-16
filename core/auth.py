# core/auth.py

"""
Авторизація користувача в системі моніторингу стратегічного плану.

Цей файл відповідає за:
1. повноцінний вхід через email і пароль;
2. перевірку користувача за config/users.py;
3. перевірку пароля через st.secrets;
4. збереження поточного користувача в st.session_state;
5. вихід із системи;
6. гостьовий режим для незареєстрованих користувачів.

Важливо:
- паролі не зберігаємо у config/users.py;
- паролі тимчасово зберігаємо у .streamlit/secrets.toml або в Secrets Streamlit Cloud;
- локальний файл secrets.toml не потрібно завантажувати в GitHub.
"""

from __future__ import annotations

import streamlit as st

from config.users import (
    GUEST_USER,
    get_user_by_email,
    normalize_email,
    user_exists,
)

from config.roles import (
    ROLE_GUEST,
    get_role_label,
)


# -----------------------------
# Ключі session_state
# -----------------------------

SESSION_USER_KEY = "current_user"
SESSION_AUTH_EMAIL_KEY = "auth_email"
SESSION_IS_AUTHENTICATED_KEY = "is_authenticated"
SESSION_LOGIN_ERROR_KEY = "login_error"


# -----------------------------
# Ініціалізація авторизації
# -----------------------------

def init_auth_state() -> None:
    """
    Ініціалізує стан авторизації.
    Викликати на старті app.py або сторінки, яка використовує доступи.
    """

    if SESSION_USER_KEY not in st.session_state:
        st.session_state[SESSION_USER_KEY] = GUEST_USER.copy()

    if SESSION_AUTH_EMAIL_KEY not in st.session_state:
        st.session_state[SESSION_AUTH_EMAIL_KEY] = None

    if SESSION_IS_AUTHENTICATED_KEY not in st.session_state:
        st.session_state[SESSION_IS_AUTHENTICATED_KEY] = False

    if SESSION_LOGIN_ERROR_KEY not in st.session_state:
        st.session_state[SESSION_LOGIN_ERROR_KEY] = None


# -----------------------------
# Поточний користувач
# -----------------------------

def get_current_user() -> dict:
    """
    Повертає поточного користувача.
    Якщо користувач не увійшов — повертає guest.
    """

    init_auth_state()

    user = st.session_state.get(SESSION_USER_KEY)

    if not user:
        return GUEST_USER.copy()

    return user


def set_current_user(user: dict | None) -> None:
    """
    Записує користувача в session_state.
    """

    if not user:
        user = GUEST_USER.copy()

    st.session_state[SESSION_USER_KEY] = user
    st.session_state[SESSION_AUTH_EMAIL_KEY] = user.get("email")
    st.session_state[SESSION_IS_AUTHENTICATED_KEY] = user.get("role") != ROLE_GUEST


def logout_user() -> None:
    """
    Вихід із системи.
    Після виходу користувач переходить у режим guest.
    """

    st.session_state[SESSION_USER_KEY] = GUEST_USER.copy()
    st.session_state[SESSION_AUTH_EMAIL_KEY] = None
    st.session_state[SESSION_IS_AUTHENTICATED_KEY] = False
    st.session_state[SESSION_LOGIN_ERROR_KEY] = None


def is_authenticated() -> bool:
    """
    Перевіряє, чи користувач авторизований.
    """

    init_auth_state()
    return bool(st.session_state.get(SESSION_IS_AUTHENTICATED_KEY, False))


def is_guest() -> bool:
    """
    Перевіряє, чи поточний користувач є гостем.
    """

    user = get_current_user()
    return user.get("role") == ROLE_GUEST


# -----------------------------
# Дані поточного користувача
# -----------------------------

def get_current_user_email() -> str | None:
    """
    Повертає email поточного користувача.
    """

    user = get_current_user()
    return user.get("email")


def get_current_user_role() -> str:
    """
    Повертає роль поточного користувача.
    """

    user = get_current_user()
    return user.get("role", ROLE_GUEST)


def get_current_user_role_label() -> str:
    """
    Повертає людську назву ролі поточного користувача.
    """

    user = get_current_user()

    if user.get("role_label"):
        return user.get("role_label")

    return get_role_label(user.get("role"))


def get_current_user_ssp() -> str | None:
    """
    Повертає ССП поточного користувача.
    Для адмінів, супер-адмінів і гостей повертає None.
    """

    user = get_current_user()
    return user.get("ssp")


def is_current_user_owner() -> bool:
    """
    Перевіряє, чи поточний користувач є власником системи.
    """

    user = get_current_user()
    return bool(user.get("is_owner", False))


# -----------------------------
# Перевірка пароля
# -----------------------------

def get_password_from_secrets(email: str | None) -> str | None:
    """
    Дістає пароль користувача з secrets.

    Очікувана структура:

    [passwords]
    user@example.com = "password"
    """

    email = normalize_email(email)

    if not email:
        return None

    try:
        passwords = st.secrets.get("passwords", {})
    except Exception:
        return None

    if not passwords:
        return None

    return passwords.get(email)


def check_password(email: str | None, password: str | None) -> bool:
    """
    Перевіряє пароль користувача.

    Для першої версії пароль звіряється напряму зі st.secrets.
    Пізніше це можна замінити на хешування або Supabase Auth.
    """

    email = normalize_email(email)

    if not email or not password:
        return False

    expected_password = get_password_from_secrets(email)

    if not expected_password:
        return False

    return str(password) == str(expected_password)


# -----------------------------
# Login
# -----------------------------

def login_by_email_and_password(
    email: str | None,
    password: str | None,
) -> tuple[bool, dict, str | None]:
    """
    Авторизує користувача через email і пароль.

    Повертає:
    - success: True / False;
    - user: профіль користувача або guest;
    - error_message: текст помилки або None.
    """

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

    set_current_user(user)

    return True, user, None


# -----------------------------
# Форма входу
# -----------------------------

def render_login_form() -> dict:
    """
    Виводить форму входу в sidebar.

    Якщо користувач уже увійшов — показує дані користувача і кнопку виходу.
    Якщо не увійшов — показує поля email/password.
    """

    init_auth_state()

    user = get_current_user()

    st.sidebar.markdown("### Вхід до системи")

    if is_authenticated():
        full_name = user.get("full_name") or "Користувач"
        role_label = user.get("role_label") or get_role_label(user.get("role"))

        st.sidebar.success("Вхід виконано")
        st.sidebar.caption(f"Користувач: {full_name}")
        st.sidebar.caption(f"Роль: {role_label}")

        if user.get("email"):
            st.sidebar.caption(f"Email: {user.get('email')}")

        if user.get("ssp"):
            st.sidebar.caption(f"ССП: {user.get('ssp')}")

        if st.sidebar.button("Вийти з системи", key="logout_button"):
            logout_user()
            st.rerun()

        return user

    with st.sidebar.form("login_form"):
        email = st.text_input(
            "Електронна пошта",
            placeholder="name@example.com",
            key="login_email_input",
        )

        password = st.text_input(
            "Пароль",
            type="password",
            key="login_password_input",
        )

        submitted = st.form_submit_button("Увійти")

    if submitted:
        success, logged_user, error_message = login_by_email_and_password(email, password)

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


# -----------------------------
# Інформаційний блок користувача
# -----------------------------

def render_current_user_info() -> None:
    """
    Виводить коротку інформацію про поточного користувача в sidebar.

    Якщо render_login_form() вже показує користувача, цей блок не обов'язковий.
    """

    user = get_current_user()

    st.sidebar.markdown("---")
    st.sidebar.caption("Поточний користувач")

    full_name = user.get("full_name") or "Користувач без реєстрації"
    role_label = user.get("role_label") or get_role_label(user.get("role"))

    st.sidebar.caption(f"Ім'я: {full_name}")
    st.sidebar.caption(f"Роль: {role_label}")

    if user.get("email"):
        st.sidebar.caption(f"Email: {user.get('email')}")

    if user.get("ssp"):
        st.sidebar.caption(f"ССП: {user.get('ssp')}")
