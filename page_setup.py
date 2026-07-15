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
import streamlit.components.v1 as components

from core.errors import log_cosmetic_error

from core.config import APP_VERSION
from core.theme import inject_theme, apply_plotly_theme
from core.ui import load_css
from core.auth import init_auth_state, render_login_form
from core.navigation import render_role_page_links, require_page_access


def _hide_streamlit_fixed_chrome() -> None:
    """Прибирає верхній toolbar і нижні службові overlay-панелі Streamlit/Cloud.

    CSS прибирає стандартні елементи Streamlit. Додатковий нульової висоти
    JavaScript-компонент працює з DOM батьківської сторінки й прибирає саме
    платформний нижній overlay Community Cloud, у якому власнику показується
    кнопка «Manage app». Це потрібно, бо цей overlay не є ``stBottom`` і тому
    не зникає від приховування стандартного bottom-container.

    Власний футер системи ``.app-footer`` не зачіпається.
    """
    st.markdown(
        """
        <style>
        /* Верхня службова панель Streamlit. */
        header[data-testid="stHeader"],
        div[data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"] {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            min-height: 0 !important;
            max-height: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
            overflow: hidden !important;
        }

        /* Стандартна нижня область Streamlit. */
        [data-testid="stBottom"],
        [data-testid="stBottomBlockContainer"],
        [data-testid="stBottomContainer"],
        .stBottom,
        .stBottomBlockContainer {
            display: none !important;
            visibility: hidden !important;
            position: static !important;
            width: 0 !important;
            height: 0 !important;
            min-width: 0 !important;
            min-height: 0 !important;
            max-height: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
            overflow: hidden !important;
        }

        /* Spacer, який Streamlit ставить безпосередньо перед stBottom. */
        [data-testid="stMain"] > div:not([data-testid]):has(+ [data-testid="stBottom"]),
        [data-testid="stMain"] > [class*="AppViewBlockSpacer"],
        [data-testid="stMain"] > [class*="BlockSpacer"]:has(+ [data-testid="stBottom"]) {
            display: none !important;
            visibility: hidden !important;
            flex: 0 0 0 !important;
            flex-grow: 0 !important;
            width: 0 !important;
            height: 0 !important;
            min-height: 0 !important;
            max-height: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
            overflow: hidden !important;
        }

        /* Відомі службові badges / owner controls Community Cloud. */
        [data-testid="stAppDeployButton"],
        [data-testid="stStatusWidget"],
        [class*="viewerBadge"],
        [class*="ViewerBadge"],
        [class*="manageApp"],
        [class*="ManageApp"] {
            display: none !important;
            visibility: hidden !important;
        }

        /* Контент має використовувати всю висоту viewport без резерву знизу. */
        div.block-container,
        .main .block-container,
        [data-testid="stMainBlockContainer"] {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
            margin-bottom: 0 !important;
        }

        [data-testid="stAppViewContainer"] > .main,
        section.main,
        [data-testid="stMain"] {
            padding-bottom: 0 !important;
            margin-bottom: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Community Cloud додає owner-overlay («Manage app») поза стандартним
    # stBottom. Його клас може змінюватися, тому знаходимо overlay за реально
    # видимим текстом кнопки та геометрією елемента, а не за нестабільним класом.
    components.html(
        r"""
        <script>
        (() => {
          const parentDoc = window.parent && window.parent.document;
          if (!parentDoc) return;

          const HIDDEN_ATTR = 'data-strategic-monitoring-hidden-platform-overlay';

          function hideElement(el) {
            if (!el || el === parentDoc.body || el === parentDoc.documentElement) return;
            el.setAttribute(HIDDEN_ATTR, '1');
            el.style.setProperty('display', 'none', 'important');
            el.style.setProperty('visibility', 'hidden', 'important');
            el.style.setProperty('height', '0', 'important');
            el.style.setProperty('min-height', '0', 'important');
            el.style.setProperty('max-height', '0', 'important');
            el.style.setProperty('padding', '0', 'important');
            el.style.setProperty('margin', '0', 'important');
            el.style.setProperty('overflow', 'hidden', 'important');
          }

          function isSidebar(el) {
            return !!(
              el.matches?.('[data-testid="stSidebar"], section[data-testid="stSidebar"]') ||
              el.closest?.('[data-testid="stSidebar"]')
            );
          }

          function findPlatformOverlayFromManageButton() {
            const all = parentDoc.querySelectorAll('button, a, div, span');
            for (const node of all) {
              const text = (node.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
              if (text !== 'manage app') continue;

              let current = node;
              let best = null;
              for (let i = 0; i < 10 && current && current !== parentDoc.body; i++, current = current.parentElement) {
                if (isSidebar(current)) continue;
                const style = window.parent.getComputedStyle(current);
                const rect = current.getBoundingClientRect();
                const pinnedBottom = rect.bottom >= window.parent.innerHeight - 4;
                const wideEnough = rect.width >= Math.min(320, window.parent.innerWidth * 0.25);
                const overlayLike = style.position === 'fixed' || style.position === 'sticky';

                if (pinnedBottom && wideEnough) {
                  best = current;
                  if (overlayLike) break;
                }
              }

              hideElement(best || node);
            }
          }

          function hideKnownBottomContainers() {
            const selectors = [
              '[data-testid="stBottom"]',
              '[data-testid="stBottomBlockContainer"]',
              '[data-testid="stBottomContainer"]',
              '[data-testid="stAppDeployButton"]',
              '[data-testid="stStatusWidget"]',
              '[class*="viewerBadge"]',
              '[class*="ViewerBadge"]',
              '[class*="manageApp"]',
              '[class*="ManageApp"]'
            ];
            for (const selector of selectors) {
              parentDoc.querySelectorAll(selector).forEach(hideElement);
            }
          }

          function hideLargePinnedBottomOverlays() {
            const viewportH = window.parent.innerHeight;
            const viewportW = window.parent.innerWidth;

            parentDoc.querySelectorAll('body *').forEach((el) => {
              if (isSidebar(el)) return;
              if (el.hasAttribute(HIDDEN_ATTR)) return;
              if (el.classList?.contains('app-footer') || el.closest?.('.app-footer')) return;

              const style = window.parent.getComputedStyle(el);
              if (style.position !== 'fixed' && style.position !== 'sticky') return;

              const rect = el.getBoundingClientRect();
              if (rect.width <= 0 || rect.height <= 0) return;

              const pinnedBottom = rect.bottom >= viewportH - 3;
              const coversMainWidth = rect.width >= viewportW * 0.45;
              const significantHeight = rect.height >= 45;
              const startsBelowTop = rect.top > viewportH * 0.35;

              if (pinnedBottom && coversMainWidth && significantHeight && startsBelowTop) {
                hideElement(el);
              }
            });
          }

          function cleanup() {
            hideKnownBottomContainers();
            findPlatformOverlayFromManageButton();
            hideLargePinnedBottomOverlays();
          }

          cleanup();

          // Cloud може домалювати owner-controls уже після завершення Python-run.
          // Observer повторює очищення тільки при зміні DOM.
          const observer = new MutationObserver(() => cleanup());
          observer.observe(parentDoc.body, { childList: true, subtree: true });

          // Додаткова коротка серія перевірок на випадок асинхронного mount.
          [100, 300, 800, 1500, 3000].forEach(ms => setTimeout(cleanup, ms));
        })();
        </script>
        """,
        height=0,
        scrolling=False,
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
