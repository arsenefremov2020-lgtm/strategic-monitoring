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
    """Load shared CSS from the project root on every Streamlit page."""
    css_path = Path(path)
    if not css_path.is_absolute():
        project_root = Path(__file__).resolve().parent.parent
        css_path = project_root / css_path

    if css_path.is_file():
        st.markdown(
            f"<style>{css_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )


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
    from core.timeutils import now_kyiv
    import streamlit.components.v1 as components

    ms = max(1, int(minutes)) * 60 * 1000
    if show_note:
        st.info(
            f"Дані автоматично оновлюються кожні {minutes} хвилин. "
            f"Останнє оновлення сторінки: {now_kyiv().strftime('%d.%m.%Y %H:%M')}"
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
        f"<div style='background:#F7F9FC;border:1px solid #DCE4F0;border-radius:10px;"
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

def prepare_human_log_table(logs_df, *, extra_columns: list[str] | None = None):
    """Return a user-facing history table without internal identifiers."""
    import pandas as pd
    from core.stage4 import clean, format_kyiv_datetime

    if logs_df is None or getattr(logs_df, "empty", True):
        return pd.DataFrame()

    show = logs_df.copy()

    def _col(name: str) -> pd.Series:
        if name in show.columns:
            return show[name]
        return pd.Series([""] * len(show), index=show.index, dtype="object")

    show["Дата і час"] = _col("changed_at").apply(format_kyiv_datetime)
    show["Дія"] = _col("action").apply(lambda x: clean(x) or "—")
    show["Попередній статус"] = _col("old_status").apply(lambda x: clean(x) or "—")
    show["Новий статус"] = _col("new_status").apply(lambda x: clean(x) or "—")
    show["Коментар"] = _col("admin_comment").apply(lambda x: clean(x) or "—")

    actor_name = _col("actor_name").apply(clean)
    changed_by = _col("changed_by").apply(clean)
    show["Ким змінено"] = [name or changed or "—" for name, changed in zip(actor_name, changed_by)]

    columns = [
        "Дата і час", "Дія", "Попередній статус", "Новий статус",
        "Коментар", "Ким змінено",
    ]
    for column in extra_columns or []:
        if column in show.columns and column not in columns:
            columns.insert(-2, column)
    return show[[column for column in columns if column in show.columns]]


def render_human_log_table(logs_df, *, extra_columns: list[str] | None = None) -> None:
    """Render the human history table with light status highlighting."""
    from core.stage4 import style_status_columns

    table = prepare_human_log_table(logs_df, extra_columns=extra_columns)
    if table.empty:
        st.info("Історії змін для цієї заявки поки що немає.")
        return
    st.dataframe(
        style_status_columns(table, ["Попередній статус", "Новий статус"]),
        use_container_width=True,
        hide_index=True,
    )


def render_request_timeline(logs_df, *, title: str | None = None,
                            with_table_expander: bool = True) -> None:
    """Render a chronological, human-readable timeline from monitoring_logs."""
    import pandas as pd
    from html import escape as _escape
    from core.stage4 import clean, format_kyiv_datetime

    if logs_df is None or getattr(logs_df, "empty", True):
        st.info("Історії змін для цієї заявки поки що немає.")
        return

    if title:
        st.markdown(
            f'<div style="font-size:13px;font-weight:800;color:#132238;'
            f'margin-bottom:6px;">{_escape(title)}</div>',
            unsafe_allow_html=True,
        )

    timeline = logs_df.copy()
    timeline["_ts"] = pd.to_datetime(timeline.get("changed_at"), errors="coerce", utc=True)
    timeline = timeline.sort_values("_ts")

    items = []
    for _, event in timeline.iterrows():
        when = format_kyiv_datetime(event.get("changed_at"), fallback="Час не визначено")
        action = clean(event.get("action")) or "Зміна заявки"
        actor = clean(event.get("actor_name")) or clean(event.get("changed_by"))
        old_status = clean(event.get("old_status"))
        new_status = clean(event.get("new_status"))
        comment = clean(event.get("admin_comment"))
        dot = "#1E9E57" if new_status == "Погоджено" else (
            "#DC4A4A" if "Повернуто" in new_status else (
                "#8b5cf6" if "закрит" in action.lower() else "#4D8DFF"
            )
        )
        transition = ""
        if old_status and new_status and old_status != new_status:
            transition = (
                f'<br><span style="display:inline-block;margin-top:3px;padding:2px 7px;'
                f'border-radius:999px;background:#F7F9FC;color:#61708A;font-size:11px;">'
                f'{_escape(old_status)} → {_escape(new_status)}</span>'
            )
        elif new_status:
            transition = (
                f'<br><span style="display:inline-block;margin-top:3px;padding:2px 7px;'
                f'border-radius:999px;background:#EAF1FF;color:#005BBB;font-size:11px;">'
                f'{_escape(new_status)}</span>'
            )
        items.append(
            f'<div style="display:flex;gap:10px;margin-bottom:10px;">'
            f'<div style="width:10px;min-width:10px;height:10px;border-radius:50%;'
            f'background:{dot};margin-top:5px;"></div>'
            f'<div style="font-size:12.5px;line-height:1.45;color:#132238;">'
            f'<b>{_escape(when)}</b> — {_escape(action)}'
            f'{transition}'
            + (f'<br><span style="color:#61708A;">Коментар: {_escape(comment)}</span>' if comment else "")
            + (f'<br><span style="color:#61708A;font-size:11.5px;">Ким змінено: {_escape(actor)}</span>' if actor else "")
            + '</div></div>'
        )

    st.markdown(
        '<div style="border-left:2px solid #DCE4F0;padding-left:12px;'
        'margin:4px 0 10px 2px;">' + "".join(items) + "</div>",
        unsafe_allow_html=True,
    )

    if with_table_expander:
        with st.expander("Таблиця історії"):
            render_human_log_table(logs_df)
