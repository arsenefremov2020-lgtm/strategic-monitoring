# core/navigation.py

"""
Навігація системи моніторингу стратегічного плану.

Цей файл відповідає за:
1. отримання дозволених вкладок для ролі користувача;
2. перевірку доступу до вкладки;
3. вибір стартової вкладки;
4. побудову меню в sidebar.

Тут не має бути логіки Excel, Supabase, розрахунків або конкретного наповнення сторінок.
"""


import streamlit as st

from config.roles import (
    ROLE_GUEST,
    ALL_PAGES,
    get_pages_for_role,
    get_default_page_for_role,
    can_access_page,
)

from core.auth import (
    get_current_user,
    get_current_user_role,
)


# -----------------------------
# Ключі session_state
# -----------------------------

SESSION_SELECTED_PAGE_KEY = "selected_page"


# -----------------------------
# Базові функції навігації
# -----------------------------

def get_available_pages_for_current_user() -> list[str]:
    """
    Повертає список вкладок, доступних поточному користувачу.
    """

    role = get_current_user_role()
    return get_pages_for_role(role)


def get_default_page_for_current_user() -> str:
    """
    Повертає стартову вкладку для поточного користувача.
    """

    role = get_current_user_role()
    return get_default_page_for_role(role)


def init_navigation_state() -> None:
    """
    Ініціалізує вибрану вкладку в session_state.
    Якщо поточна вкладка недоступна для ролі — скидає її на стартову.
    """

    available_pages = get_available_pages_for_current_user()
    default_page = get_default_page_for_current_user()

    if not available_pages:
        available_pages = get_pages_for_role(ROLE_GUEST)
        default_page = get_default_page_for_role(ROLE_GUEST)

    current_page = st.session_state.get(SESSION_SELECTED_PAGE_KEY)

    if not current_page:
        st.session_state[SESSION_SELECTED_PAGE_KEY] = default_page
        return

    if current_page not in available_pages:
        st.session_state[SESSION_SELECTED_PAGE_KEY] = default_page


def get_selected_page() -> str:
    """
    Повертає поточну вибрану вкладку.
    """

    init_navigation_state()
    return st.session_state.get(
        SESSION_SELECTED_PAGE_KEY,
        get_default_page_for_current_user(),
    )


def set_selected_page(page_name: str) -> None:
    """
    Встановлює поточну вкладку, якщо користувач має до неї доступ.
    """

    role = get_current_user_role()

    if can_access_page(role, page_name):
        st.session_state[SESSION_SELECTED_PAGE_KEY] = page_name
    else:
        st.session_state[SESSION_SELECTED_PAGE_KEY] = get_default_page_for_role(role)


def current_user_can_access_page(page_name: str) -> bool:
    """
    Перевіряє, чи поточний користувач має доступ до вкладки.
    """

    role = get_current_user_role()
    return can_access_page(role, page_name)


# -----------------------------
# Побудова меню
# -----------------------------

def render_sidebar_navigation() -> str:
    """
    Виводить меню доступних вкладок у sidebar.

    Повертає назву вибраної вкладки.
    """

    init_navigation_state()

    user = get_current_user()
    role = user.get("role", ROLE_GUEST)

    available_pages = get_pages_for_role(role)

    if not available_pages:
        available_pages = get_pages_for_role(ROLE_GUEST)

    current_page = get_selected_page()

    if current_page not in available_pages:
        current_page = available_pages[0]
        st.session_state[SESSION_SELECTED_PAGE_KEY] = current_page

    st.sidebar.markdown("### Навігація")

    selected_page = st.sidebar.radio(
        "Оберіть вкладку",
        available_pages,
        index=available_pages.index(current_page),
        key="sidebar_page_navigation",
    )

    st.session_state[SESSION_SELECTED_PAGE_KEY] = selected_page

    return selected_page


# -----------------------------
# Захист сторінок
# -----------------------------

def require_page_access(page_name: str) -> bool:
    """
    Перевіряє доступ до сторінки.

    Якщо доступу немає — показує попередження і повертає False.
    Якщо доступ є — повертає True.
    """

    if current_user_can_access_page(page_name):
        return True

    st.warning("У вас немає доступу до цієї вкладки.")
    return False


def get_blocked_pages_for_current_user() -> list[str]:
    """
    Повертає список вкладок, які існують у системі,
    але недоступні поточному користувачу.
    """

    available_pages = get_available_pages_for_current_user()

    return [
        page
        for page in ALL_PAGES
        if page not in available_pages
    ]
