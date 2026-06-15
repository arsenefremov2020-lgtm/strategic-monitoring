# core/auth.py

"""
Авторизація користувача в системі моніторингу стратегічного плану.

Цей файл відповідає за:
1. визначення поточного користувача;
2. тестовий вхід через email;
3. збереження користувача в st.session_state;
4. вихід із системи;
5. повернення guest-користувача, якщо користувач не зареєстрований.

Тут не має бути логіки розрахунків, Excel, Supabase або відображення конкретних сторінок.
"""


import streamlit as st

from config.users import (
    USERS,
    GUEST_USER,
    get_user_by_email,
    normalize_email,
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


# -----------------------------
# Базові функції session_state
# -----------------------------

def init_auth_state() -> None:
    """
    Ініціалізує стан авторизації в session_state.
    Викликати один раз на старті app.py.
    """

    if SESSION_USER_KEY not in st.session_state:
        st.session_state[SESSION_USER_KEY] = GUEST_USER.copy()

    if SESSION_AUTH_EMAIL_KEY not in st.session_state:
        st.session_state[SESSION_AUTH_EMAIL_KEY] = None

    if SESSION_IS_AUTHENTICATED_KEY not in st.session_state:
        st.session_state[SESSION_IS_AUTHENTICATED_KEY] = False


def get_current_user() -> dict:
    """
    Повертає поточного користувача.
    Якщо користувач не встановлений — повертає guest.
    """

    init_auth_state()

    user = st.session_state.get(SESSION_USER_KEY)

    if not user:
        return GUEST_USER.copy()

    return user


def set_current_user(user: dict) -> None:
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
    Після виходу користувач стає guest.
    """

    st.session_state[SESSION_USER_KEY] = GUEST_USER.copy()
    st.session_state[SESSION_AUTH_EMAIL_KEY] = None
    st.session_state[SESSION_IS_AUTHENTICATED_KEY] = False


# -----------------------------
# Авторизація через email
# -----------------------------

def login_by_email(email: str | None) -> dict:
    """
    Авторизує користувача за email.

    Якщо email є у USERS і користувач активний — повертає його профіль.
    Якщо email немає — повертає guest.
    """

    email = normalize_email(email)
    user = get_user_by_email(email)

    set_current_user(user)

    return user


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
# Тестовий блок входу
# -----------------------------

def render_test_login_block() -> dict:
    """
    Тимчасовий тестовий блок входу.

    Його використовуємо на етапі розробки, щоб швидко перемикатися
    між ролями: ССП, керівник ССП, адмін, супер-адмін, guest.

    Пізніше цей блок можна буде замінити на реальну авторизацію.
    """

    init_auth_state()

    st.sidebar.markdown("### Вхід до системи")

    user_options = ["Користувач без реєстрації"] + list(USERS.keys())

    current_email = st.session_state.get(SESSION_AUTH_EMAIL_KEY)

    if current_email in USERS:
        default_index = user_options.index(current_email)
    else:
        default_index = 0

    selected_option = st.sidebar.selectbox(
        "Оберіть користувача",
        user_options,
        index=default_index,
        key="test_login_user_selectbox",
    )

    if selected_option == "Користувач без реєстрації":
        selected_user = GUEST_USER.copy()
    else:
        selected_user = get_user_by_email(selected_option)

    set_current_user(selected_user)

    st.sidebar.caption(
        f"Роль: {selected_user.get('role_label', 'Користувач без реєстрації')}"
    )

    if selected_user.get("ssp"):
        st.sidebar.caption(
            f"ССП: {selected_user.get('ssp')}"
        )

    return selected_user


# -----------------------------
# Інформаційний блок користувача
# -----------------------------

def render_current_user_info() -> None:
    """
    Виводить коротку інформацію про поточного користувача в sidebar.
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
