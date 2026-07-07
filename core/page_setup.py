# core/page_setup.py

"""
Єдиний «старт сторінки» та футер (правки К6, К4).

Раніше кожна з 13 сторінок повторювала однаковий блок:
конфіг сторінки → логотип → CSS → авторизація → меню → перевірка доступу,
а футер із зашитою версією був скопійований у 10 файлах.

Тепер сторінка починається одним викликом:

    from core.page_setup import page_setup, render_footer
    current_user = page_setup("Dashboard", page_name="Dashboard")
    ...
    render_footer()
"""

from __future__ import annotations

import streamlit as st

from core.config import APP_VERSION
from core.theme import inject_theme, apply_plotly_theme
from core.ui import load_css, render_scope_toggle
from core.auth import init_auth_state, render_login_form
from core.navigation import render_role_page_links, require_page_access


def page_setup(page_title: str, page_name: str | None = None,
               layout: str = "wide", stop_if_no_access: bool = True):
    """
    Виконує стандартний старт сторінки. Повертає поточного користувача.

    page_name — назва вкладки в системі доступів (config/roles.ROLE_PAGES);
    якщо не передано, перевірка доступу не виконується (для app.py доступ
    відкритий усім ролям).

    Для ролей, чиї дані звужені до власного ССП, одразу після перевірки
    доступу малює кнопку "Переглянути загальну інформацію" (окремо для
    кожної вкладки — page_name). Сторінці нічого додатково викликати не
    треба: досить передати той самий page_name у filter_actions_for_user /
    filter_requests_for_user під час завантаження даних.
    """
    st.set_page_config(page_title=page_title, layout=layout)

    try:
        st.logo(
            "assets/Мінекономіки.png",
            size="large",
        )
    except Exception:
        pass

    load_css()
    inject_theme()
    apply_plotly_theme()

    init_auth_state()
    current_user = render_login_form()
    render_role_page_links()

    if page_name and not require_page_access(page_name):
        if stop_if_no_access:
            st.stop()

    if page_name:
        try:
            render_scope_toggle(page_name, current_user)
        except Exception:
            # Кнопка-перемикач — допоміжна; збій у ній не має класти сторінку.
            pass

    return current_user


def render_footer() -> None:
    """Єдиний футер системи. Версія береться з core.config.APP_VERSION."""
    st.markdown(
        f"""
        <div class="app-footer">
            <strong>Розроблено департаментом стратегічного планування
            та макроекономічного прогнозування</strong><br>
            Версія {APP_VERSION} | 2026 | Внутрішня система моніторингу стратегічного плану
        </div>
        """,
        unsafe_allow_html=True,
    )
