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
    Для гостя, адміністратора і супер-адміна нічого не малює (повертає False).

    За фідбеком розміщується САМЕ поруч із кнопкою "Скинути фільтри" (як на
    app.py) — тому ця функція більше не створює власну колонку/розкладку:
    викликач сам розміщує її у потрібному місці (напр. в одній з колонок
    st.columns() поруч із фільтрами) і сам вирішує ширину.

    Повертає True, якщо на ЦІЙ вкладці зараз активний режим "загальна
    інформація" — після цього виклику досить передати той самий page_key
    у filter_actions_for_user / filter_requests_for_user, вони самі
    прочитають цей стан.
    """
    from core.access import (
        is_scope_lockable_user,
        is_scope_override_active,
        set_scope_override,
    )

    if not is_scope_lockable_user(user):
        return False

    active = is_scope_override_active(page_key)

    from core.access import get_user_allowed_ssp_indexes

    own_indexes = [idx for idx in get_user_allowed_ssp_indexes(user) if idx != "*"]
    own_label = ", ".join(own_indexes) if own_indexes else "—"
    st.caption(f"Ваш ССП: №{own_label}")

    if active:
        if st.button(
            "⬅ Повернутися до свого ССП",
            key=f"scope_toggle_off_{page_key}",
            use_container_width=True,
        ):
            set_scope_override(page_key, False)
            st.rerun()
        st.caption("ℹ️ Показано інформацію по всіх ССП (тимчасово, лише на цій вкладці).")
    else:
        if st.button(
            "🔎 Переглянути загальну інформацію",
            key=f"scope_toggle_on_{page_key}",
            use_container_width=True,
        ):
            set_scope_override(page_key, True)
            st.rerun()

    return active



def render_auto_refresh_notice(page_key: str, *, minutes: int = 5, show_note: bool = True) -> None:
    """Показує службову позначку автооновлення і запускає м'яке browser-refresh.

    Використовується тільки на сторінках, де користувач прямо погодив TTL 5 хв:
    Головна, Dashboard, Картка заходу, Фільтр за документом, Оцінка МіО.
    """
    from datetime import datetime
    import streamlit.components.v1 as components

    ms = max(1, int(minutes)) * 60 * 1000
    if show_note:
        st.info(
            f"Дані автоматично оновлюються кожні {minutes} хвилин. "
            f"Останнє оновлення сторінки: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
    # Малий невидимий компонент. Не чіпає session_state, просто оновлює вкладку браузера.
    components.html(
        f"""
        <script>
        const key = 'auto_refresh_{page_key}';
        if (!window[key]) {{
          window[key] = true;
          setTimeout(function() {{ window.parent.location.reload(); }}, {ms});
        }}
        </script>
        """,
        height=0,
    )


def render_own_ssp_badge(user: dict | None, *, label: str = "Ваш ССП") -> None:
    """Уніфікований підпис для ролей, прив'язаних до власного ССП."""
    try:
        from core.access import get_user_ssp_index
        idx = get_user_ssp_index(user) or "—"
    except Exception:
        idx = "—"
    st.markdown(
        "<div style='font-size:13px;font-weight:700;margin-bottom:4px;'>"
        "Самостійний структурний підрозділ</div>"
        f"<div style='background:#f1f5f9;border:1px solid #cbd5e1;border-radius:10px;"
        f"padding:9px 12px;font-weight:800;'>{label}: №{idx}</div>",
        unsafe_allow_html=True,
    )


def apply_reset_buttons(apply_key: str, reset_key: str, *, apply_label: str = "Застосувати обрані параметри", reset_label: str = "Скинути параметри"):
    """Стандартна пара кнопок. Повертає (apply_clicked, reset_clicked)."""
    a, b = st.columns([1, 1])
    with a:
        apply_clicked = st.button(apply_label, type="primary", use_container_width=True, key=apply_key)
    with b:
        reset_clicked = st.button(reset_label, use_container_width=True, key=reset_key)
    return apply_clicked, reset_clicked


# ------------------------------------------------------------
# Єдиний таймлайн заявки (ТЗ 16.13 — погоджено)
# ------------------------------------------------------------
# Використовується в «Мій кабінет», «Мої заявки», «Адміністрування» та
# «Журнал дій» (через окрему кнопку), щоб історія заявки скрізь виглядала
# і читалася ОДНАКОВО, без дублювання логіки на сторінках.

def render_request_timeline(logs_df, *, title: str | None = None,
                            with_table_expander: bool = True) -> None:
    """Малює хронологічний таймлайн подій заявки з monitoring_logs.

    logs_df — DataFrame з колонками changed_at / action / old_status /
    new_status / admin_comment / changed_by (зайві колонки ігноруються).
    """
    import pandas as pd
    from html import escape as _escape

    def _c(v) -> str:
        if v is None:
            return ""
        try:
            if pd.isna(v):
                return ""
        except (TypeError, ValueError):
            pass
        return str(v).strip()

    if logs_df is None or getattr(logs_df, "empty", True):
        st.info("Історії змін для цієї заявки поки що немає.")
        return

    if title:
        st.markdown(
            f'<div style="font-size:13px;font-weight:800;color:#0f172a;'
            f'margin-bottom:6px;">{_escape(title)}</div>',
            unsafe_allow_html=True,
        )

    _tl = logs_df.copy()
    _tl["_ts"] = pd.to_datetime(_tl.get("changed_at"), errors="coerce", utc=True)
    _tl = _tl.sort_values("_ts")

    items = []
    for _, ev in _tl.iterrows():
        ts = ev["_ts"]
        when = ts.strftime("%d.%m.%Y %H:%M") if pd.notna(ts) else ""
        act = _c(ev.get("action", ""))
        who = _c(ev.get("changed_by", ""))
        new = _c(ev.get("new_status", ""))
        cmt = _c(ev.get("admin_comment", ""))
        dot = "#22c55e" if new == "Погоджено" else (
            "#f59e0b" if "Повернуто" in new else (
                "#8b5cf6" if "закрит" in act.lower() else "#3b82f6"))
        items.append(
            f'<div style="display:flex;gap:10px;margin-bottom:8px;">'
            f'<div style="width:10px;min-width:10px;height:10px;border-radius:50%;'
            f'background:{dot};margin-top:5px;"></div>'
            f'<div style="font-size:12.5px;line-height:1.45;color:#0f172a;">'
            f'<b>{_escape(when)}</b> — {_escape(act)}'
            + (f' <span style="color:#475569;">({_escape(new)})</span>' if new else "")
            + (f'<br><span style="color:#334155;">💬 {_escape(cmt)}</span>' if cmt else "")
            + (f'<br><span style="color:#64748b;font-size:11.5px;">👤 {_escape(who)}</span>' if who else "")
            + '</div></div>'
        )

    st.markdown(
        '<div style="border-left:2px solid #e2e8f0;padding-left:12px;'
        'margin:4px 0 10px 2px;">' + "".join(items) + "</div>",
        unsafe_allow_html=True,
    )

    if with_table_expander:
        with st.expander("Таблиця історії (усі поля)"):
            show = logs_df.rename(columns={
                "changed_at": "Дата", "action": "Дія",
                "old_status": "Попередній статус", "new_status": "Новий статус",
                "admin_comment": "Коментар", "changed_by": "Ким змінено",
            })
            cols = ["Дата", "Дія", "Попередній статус", "Новий статус",
                    "Коментар", "Ким змінено"]
            st.dataframe(show[[c for c in cols if c in show.columns]],
                         use_container_width=True, hide_index=True)
