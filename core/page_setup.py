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

from core.errors import log_cosmetic_error

from core.config import APP_VERSION
from core.theme import inject_theme, apply_plotly_theme
from core.ui import load_css
from core.auth import init_auth_state, render_login_form
from core.navigation import render_role_page_links, require_page_access


def _hide_streamlit_fixed_chrome() -> None:
    """Прибирає фіксовані верхню й нижню службові панелі Streamlit.

    Верхня панель перекривала верх сторінки під час прокрутки, а порожній
    нижній контейнер залишав нерухомий білий блок поверх контенту. Наш
    власний футер `.app-footer` не зачіпається.
    """
    st.markdown(
        """
        <style>
        /* Верхня службова панель Streamlit (Share / GitHub / меню тощо). */
        header[data-testid="stHeader"],
        div[data-testid="stHeader"] {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            min-height: 0 !important;
        }

        /* Фіксований нижній службовий/порожній контейнер Streamlit. */
        div[data-testid="stBottom"],
        div[data-testid="stBottomBlockContainer"],
        .stBottom,
        .stBottomBlockContainer,
        footer {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            min-height: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
        }

        /* Після приховування панелей не залишаємо зарезервовані відступи. */
        div.block-container,
        .main .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
        }

        div[data-testid="stAppViewContainer"] > .main,
        section.main {
            padding-bottom: 0 !important;
            margin-bottom: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_setup(page_title: str, page_name: str | None = None,
               layout: str = "wide", stop_if_no_access: bool = True):
    """
    Виконує стандартний старт сторінки. Повертає поточного користувача.

    page_name — назва вкладки в системі доступів (config/roles.ROLE_PAGES);
    якщо не передано, перевірка доступу не виконується (для app.py доступ
    відкритий усім ролям).

    ВАЖЛИВО: кнопку "Переглянути загальну інформацію" тут більше НЕ
    малюємо автоматично — за фідбеком вона має стояти поруч із кнопкою
    "Скинути фільтри" (як на app.py), а не окремим блоком угорі сторінки.
    Кожна сторінка викликає core.ui.render_scope_toggle(page_name, current_user)
    сама, у потрібному місці — поруч зі своїми фільтрами.
    """
    st.set_page_config(page_title=page_title, layout=layout)

    try:
        st.logo(
            "assets/Мінекономіки.png",
            size="large",
        )
    except Exception as exc:
        log_cosmetic_error("Відображення логотипа в сайдбарі", exc)

    load_css()
    _hide_streamlit_fixed_chrome()
    inject_theme()
    apply_plotly_theme()

    init_auth_state()
    current_user = render_login_form()
    render_role_page_links()

    if page_name and not require_page_access(page_name):
        if stop_if_no_access:
            st.stop()

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
