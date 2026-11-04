"""Compact, fragment-isolated navigator for the test Dashboard portfolio.

Only the navigator is interactive. KPI tiles are rendered once on a normal
Dashboard rerun, while navigator controls rerun this Streamlit fragment alone.
This module never loads the matrix, calls Supabase or computes period analytics.
"""
from __future__ import annotations

from html import escape
from pathlib import Path
import hashlib
from typing import Any, Callable

import streamlit as st


_TAB_GOALS = "Цілі"
_TAB_SSP = "ССП"
_TAB_TASKS = "Завдання"
_TAB_DOCUMENTS = "Документи"
_TAB_OTHER = "Інше"
_TABS = [_TAB_GOALS, _TAB_SSP, _TAB_TASKS, _TAB_DOCUMENTS, _TAB_OTHER]
_EXTRA_CATEGORIES = {
    "Заступники": "deputies",
    "Типи продуктів": "product_types",
    "Фінансування": "financing",
    "КПКВК": "kpkvk",
}


def _widget_suffix(value: Any) -> str:
    """Stable, Streamlit-safe IDs even for long Ukrainian document names."""
    return hashlib.blake2s(str(value).encode("utf-8"), digest_size=8).hexdigest()


def _choose(key: str, value: Any) -> None:
    st.session_state[key] = value


def _toggle_picker(expanded_key: str, selected_key: str, first_ids: list[str]) -> None:
    """Collapse without leaving an invisible selection active."""
    was_expanded = bool(st.session_state.get(expanded_key, False))
    st.session_state[expanded_key] = not was_expanded
    if was_expanded and first_ids and st.session_state.get(selected_key) not in first_ids:
        st.session_state[selected_key] = first_ids[0]


def _plural_measures(number: int) -> str:
    n = abs(int(number))
    if n % 10 == 1 and n % 100 != 11:
        noun = "захід"
    elif 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        noun = "заходи"
    else:
        noun = "заходів"
    return f"{number} {noun}"


def _markup_header(title: str, subtitle: str = "") -> None:
    st.markdown(
        '<div class="dpt-pane-header">'
        f'<div class="dpt-pane-title">{escape(title)}</div>'
        + (f'<div class="dpt-pane-subtitle">{escape(subtitle)}</div>' if subtitle else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def _item_title(item: dict[str, Any], *, coded: bool = False) -> str:
    if coded:
        code = str(item.get("code", ""))
        name = str(item.get("name", ""))
        return f"{code} — {name}" if name else code
    return str(item.get("label", ""))


def _item_identity(item: dict[str, Any], *, coded: bool = False) -> str:
    if coded:
        # Task codes can theoretically repeat under separate goal codes.
        return f"{item.get('goal_code', '')}|{item.get('code', '')}"
    return str(item.get("code", item.get("label", "")))


def _picker(
    items: list[dict[str, Any]],
    *,
    category: str,
    coded: bool = False,
    limit: int = 6,
    searchable: bool = False,
    display: Callable[[dict[str, Any]], str] | None = None,
) -> dict[str, Any] | None:
    """Single-select list with working show-more/show-less and stable state.

    It does not change the global Dashboard filters: selecting an item only
    changes the details shown in the adjacent navigator pane.
    """
    if not items:
        st.caption("За поточними фільтрами немає значень.")
        return None

    state_key = f"dpt_selected_{category}"
    expanded_key = f"dpt_expanded_{category}"
    identities = [_item_identity(item, coded=coded) for item in items]
    if st.session_state.get(state_key) not in identities:
        st.session_state[state_key] = identities[0]

    query = ""
    if searchable:
        query = st.text_input(
            "Пошук у переліку", placeholder="Код або назва…",
            key=f"dpt_search_{category}", label_visibility="collapsed",
        ).strip().casefold()

    filtered = [
        item for item in items
        if not query or query in _item_title(item, coded=coded).casefold()
    ]
    if not filtered:
        st.caption("За цим пошуком нічого не знайдено.")
    elif query and st.session_state[state_key] not in {
        _item_identity(item, coded=coded) for item in filtered
    }:
        # Keep the right pane in sync with the visible search results.
        st.session_state[state_key] = _item_identity(filtered[0], coded=coded)
    show_all = bool(st.session_state.get(expanded_key, False))
    visible = filtered if (query or show_all) else filtered[:limit]

    def render_buttons() -> None:
        for item in visible:
            identity = _item_identity(item, coded=coded)
            title = display(item) if display else _item_title(item, coded=coded)
            count = _plural_measures(int(item.get("measure_count", 0)))
            # A separate count line prevents truncation of very long names.
            label = f"{title}\n{count}"
            st.button(
                label,
                key=f"dpt_{category}_{_widget_suffix(identity)}",
                type="primary" if st.session_state[state_key] == identity else "secondary",
                use_container_width=True,
                on_click=_choose,
                args=(state_key, identity),
            )

    # Keep large expanded lists scrollable instead of increasing the page height.
    if len(visible) > 10:
        with st.container(height=340, border=False, key=f"dpt_scroll_{category}"):
            render_buttons()
    else:
        render_buttons()

    if not query and len(items) > limit:
        remaining = len(items) - limit
        if category == "goals":
            more_label = f"Ще +{remaining} цілі" if remaining > 1 else "Ще +1 ціль"
        else:
            more_label = f"Ще +{remaining}"
        st.button(
            "Згорнути" if show_all else more_label,
            key=f"dpt_more_{category}",
            icon=":material/expand_less:" if show_all else ":material/expand_more:",
            type="tertiary",
            use_container_width=False,
            on_click=_toggle_picker,
            args=(expanded_key, state_key, identities[:limit]),
        )

    selected_identity = st.session_state.get(state_key)
    return next((item for item in items if _item_identity(item, coded=coded) == selected_identity), None)


def _measure_list(measures: list[dict[str, str]], *, title: str = "Заходи") -> None:
    st.markdown(
        f'<div class="dpt-measures-header">{escape(title)}'
        f'<span>{len(measures)}</span></div>',
        unsafe_allow_html=True,
    )
    if not measures:
        st.caption("Пов'язаних заходів немає.")
        return
    html = "".join(
        '<div class="dpt-measure-row">'
        f'<span class="dpt-measure-code">{escape(str(item.get("code", "")))}</span>'
        f'<span class="dpt-measure-name">{escape(str(item.get("name", "")))}</span>'
        '</div>'
        for item in measures
    )
    st.markdown(f'<div class="dpt-measure-list">{html}</div>', unsafe_allow_html=True)


def _goal_details(goal: dict[str, Any] | None) -> None:
    if not goal:
        st.caption("Оберіть стратегічну ціль.")
        return
    _markup_header(
        _item_title(goal, coded=True),
        f"{_plural_measures(goal['measure_count'])} у портфелі",
    )
    tasks = goal.get("tasks", [])
    if not tasks:
        _measure_list(goal.get("measures", []))
        return
    st.markdown('<div class="dpt-subheading">Завдання цієї цілі</div>', unsafe_allow_html=True)
    selected_key = "dpt_selected_goal_task"
    valid = {_item_identity(task, coded=True) for task in tasks}
    if st.session_state.get(selected_key) not in valid:
        st.session_state[selected_key] = _item_identity(tasks[0], coded=True)
    for task in tasks:
        identity = _item_identity(task, coded=True)
        st.button(
            f"{_item_title(task, coded=True)} · {_plural_measures(task['measure_count'])}",
            key=f"dpt_goal_task_{_widget_suffix(identity)}",
            type="primary" if st.session_state[selected_key] == identity else "secondary",
            use_container_width=True,
            on_click=_choose,
            args=(selected_key, identity),
        )
    task = next(task for task in tasks if _item_identity(task, coded=True) == st.session_state[selected_key])
    _measure_list(task["measures"], title=f"Заходи завдання {task['code']}")


def _basic_details(item: dict[str, Any] | None, *, coded: bool = False) -> None:
    if not item:
        st.caption("Оберіть запис ліворуч.")
        return
    _markup_header(
        _item_title(item, coded=coded),
        _plural_measures(item.get("measure_count", 0)) + " у портфелі",
    )
    _measure_list(item.get("measures", []))


def _task_details(item: dict[str, Any] | None) -> None:
    if not item:
        st.caption("Оберіть завдання.")
        return
    _markup_header(
        _item_title(item, coded=True),
        f"Стратегічна ціль {item.get('goal_code', '')}: {item.get('goal_name', '')}",
    )
    _measure_list(item["measures"])


@st.fragment
def _portfolio_navigator_fragment(navigation: dict[str, list[dict[str, Any]]]) -> None:
    """Only this subtree reruns on a click; the rest of Dashboard stays intact."""
    top_left, top_right = st.columns([3, 2], vertical_alignment="center")
    with top_left:
        st.markdown('<div class="dpt-section-title">Склад портфеля</div>', unsafe_allow_html=True)
    with top_right:
        st.markdown(
            '<div class="dpt-section-description">Деталізація не змінює фільтри дашборда</div>',
            unsafe_allow_html=True,
        )

    if hasattr(st, "segmented_control"):
        active_tab = st.segmented_control(
            "Категорія складу портфеля", _TABS, default=_TAB_GOALS,
            key="dpt_portfolio_tab", label_visibility="collapsed",
        ) or _TAB_GOALS
    else:
        active_tab = st.radio(
            "Категорія складу портфеля", _TABS, index=0,
            key="dpt_portfolio_tab", horizontal=True, label_visibility="collapsed",
        )

    if not any(navigation.values()):
        st.info("За застосованими фільтрами портфель порожній.")
        return

    if active_tab == _TAB_OTHER:
        st.segmented_control(
            "Додаткові характеристики", list(_EXTRA_CATEGORIES),
            key="dpt_extra_tab", default="Заступники",
            label_visibility="collapsed",
        )
        sub_tab = st.session_state.get("dpt_extra_tab") or "Заступники"
        category = _EXTRA_CATEGORIES.get(sub_tab, "deputies")
        data = navigation.get(category, [])
        caption = sub_tab
        coded = False
        limit = 7
    else:
        category_map = {
            _TAB_GOALS: ("goals", "Стратегічні цілі", True, 5),
            _TAB_SSP: ("ssps", "Самостійні структурні підрозділи", False, 7),
            _TAB_TASKS: ("tasks", "Завдання", True, 7),
            _TAB_DOCUMENTS: ("documents", "НПА та стратегічні документи", False, 6),
        }
        category, caption, coded, limit = category_map.get(active_tab, category_map[_TAB_GOALS])
        data = navigation.get(category, [])

    left, right = st.columns([1.05, 1.65], gap="medium")
    with left:
        st.markdown(
            f'<div class="dpt-list-heading">{escape(caption)}'
            f'<span>{len(data)}</span></div>',
            unsafe_allow_html=True,
        )
        selected = _picker(
            data, category=category, coded=coded, limit=limit,
            searchable=category in {"ssps", "tasks", "documents", "deputies", "product_types", "financing", "kpkvk"},
        )
    with right:
        with st.container(border=True, key="dpt_details_pane"):
            if category == "goals":
                _goal_details(selected)
            elif category == "tasks":
                _task_details(selected)
            else:
                _basic_details(selected, coded=coded)


def render_portfolio_overview(
    summary: dict[str, Any],
    navigation: dict[str, list[dict[str, Any]]],
) -> None:
    """Complete portfolio section, composed of static KPIs and live navigator."""
    css_path = Path(__file__).resolve().parents[1] / "assets" / "dashboard_portfolio.css"
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    with st.container(key="dashboard_test_portfolio_card"):
        st.markdown('<div class="section-title">Обраний портфель</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="dpt-portfolio-subtitle">Структура заходів за застосованими фільтрами</div>',
            unsafe_allow_html=True,
        )
        kpis = [
            ("Заходи", summary.get("measure_count", 0)),
            ("ССП", summary.get("ssp_count", 0)),
            ("Стратегічні цілі", summary.get("goal_count", 0)),
            ("Завдання", summary.get("task_count", 0)),
            ("НПА та страт. документи", summary.get("npa_count", 0)),
            ("Заступники", summary.get("deputy_count", 0)),
        ]
        html = "".join(
            '<div class="dashboard-test-kpi">'
            f'<div class="dashboard-test-kpi-value">{int(value)}</div>'
            f'<div class="dashboard-test-kpi-label">{escape(label)}</div>'
            '</div>'
            for label, value in kpis
        )
        st.markdown(f'<div class="dashboard-test-kpi-grid">{html}</div>', unsafe_allow_html=True)
        _portfolio_navigator_fragment(navigation)
