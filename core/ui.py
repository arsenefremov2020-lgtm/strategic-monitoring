"""Shared UI helpers."""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import Any

import streamlit as st


def init_auth_state(*args: Any, **kwargs: Any) -> Any:
    from core.auth import init_auth_state as _init_auth_state
    return _init_auth_state(*args, **kwargs)


def render_login_form(*args: Any, **kwargs: Any) -> Any:
    from core.auth import render_login_form as _render_login_form
    return _render_login_form(*args, **kwargs)


def render_role_page_links(*args: Any, **kwargs: Any) -> Any:
    from core.navigation import render_role_page_links as _render_role_page_links
    return _render_role_page_links(*args, **kwargs)


def require_page_access(*args: Any, **kwargs: Any) -> Any:
    from core.navigation import require_page_access as _require_page_access
    return _require_page_access(*args, **kwargs)


builtins.init_auth_state = init_auth_state
builtins.render_login_form = render_login_form
builtins.render_role_page_links = render_role_page_links
builtins.require_page_access = require_page_access


def load_css(path: str = "assets/app.css") -> None:
    """Load shared CSS if the stylesheet exists."""
    css_path = Path(path)
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def render_scope_toggle(page_key: str, user: dict | None) -> bool:
    """
    Кнопка "Переглянути загальну інформацію" / "Повернутися до інформації
    свого ССП" — рівно на тій вкладці, де її викликано (page_key).

    Показується тільки ролям, для яких дані звужені до власного ССП
    (ССП, керівник ССП, керівник управління, заступник керівника ССП).
    Для гостя, адміністратора і супер-адміна нічого не малює.

    Повертає True, якщо на ЦІЙ вкладці зараз активний режим "загальна
    інформація" (без прив'язки до ССП) — сторінка може прочитати це
    значення сама, якщо їй потрібна додаткова логіка, але зазвичай
    достатньо просто передати page_key у filter_actions_for_user /
    filter_requests_for_user — вони самі перевірять стан перемикача.
    """
    from core.access import (
        is_scope_lockable_user,
        is_scope_override_active,
        set_scope_override,
    )

    if not is_scope_lockable_user(user):
        return False

    active = is_scope_override_active(page_key)

    left, right = st.columns([5, 2])
    with right:
        if active:
            if st.button(
                "⬅ Повернутися до інформації свого ССП",
                key=f"scope_toggle_off_{page_key}",
                use_container_width=True,
            ):
                set_scope_override(page_key, False)
                st.rerun()
        else:
            if st.button(
                "🔎 Переглянути загальну інформацію",
                key=f"scope_toggle_on_{page_key}",
                use_container_width=True,
            ):
                set_scope_override(page_key, True)
                st.rerun()

    if active:
        with left:
            st.caption(
                "ℹ️ Показано інформацію по всіх ССП (тимчасово, лише на цій вкладці). "
                "Натисніть «Повернутися…», щоб знову бачити тільки своє ССП."
            )

    return active
