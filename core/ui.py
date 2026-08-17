"""Shared UI helpers."""

from __future__ import annotations

import builtins
import logging
import re
from pathlib import Path
from typing import Any, Callable
from html import escape

import pandas as pd

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
        st.button(
            "⬅ Повернутися до свого ССП",
            key=f"scope_toggle_off_{page_key}",
            use_container_width=True,
            on_click=set_scope_override,
            args=(page_key, False),
        )
        st.caption("ℹ️ Показано інформацію по всіх ССП (тимчасово, лише на цій вкладці).")
    else:
        st.button(
            "🔎 Переглянути загальну інформацію",
            key=f"scope_toggle_on_{page_key}",
            use_container_width=True,
            on_click=set_scope_override,
            args=(page_key, True),
        )

    return active



def render_auto_refresh_notice(page_key: str, *, minutes: int = 5, show_note: bool = True) -> None:
    """Deprecated compatibility shim. Auto-refresh notices are intentionally disabled."""
    return None


def _readonly_status_class(value: Any) -> str:
    text = str(value or "").strip()
    # Lazy import avoids turning the generic UI module into a dependency of the
    # approval engine while still keeping workflow-state recognition central.
    from core import approval_schemes as schemes

    if schemes.is_approved(text) or text == "Виконано":
        return "rt-approved"
    if schemes.is_returned(text) or text == "На доопрацюванні":
        return "rt-returned"
    if schemes.is_waiting(text):
        return "rt-review"
    if text == "Не настав час":
        return "rt-notyet"
    if text == "Не виконано":
        return "rt-notdone"
    if text == "Частково виконано":
        return "rt-partly"
    return ""


def _render_readonly_table_legacy(
    data: Any,
    *,
    height: int = 325,
    min_width: int | None = None,
    max_cell_height: int = 74,
    compact: bool = False,
    empty_message: str = "Немає даних для відображення.",
    value_formatter: Callable[[Any], str] | None = None,
    formatters: dict[str, Callable[[Any], Any]] | None = None,
    row_class_fn: Callable[[pd.Series, int], str] | None = None,
    show_index: bool = False,
    column_widths: dict[str, int | str] | None = None,
    scroll_columns: list[str] | set[str] | tuple[str, ...] | None = None,
    table_width: str | int | None = None,
) -> None:
    """Єдиний HTML-стандарт для НЕінтерактивних таблиць системи.

    Повторює поведінку таблиць Головної: зовнішній вертикальний/горизонтальний
    скрол, sticky-заголовок, центровані комірки, перенос тексту та внутрішній
    скрол довгого вмісту. ``st.data_editor`` цим рендерером не замінюється.
    """
    if data is None:
        st.info(empty_message)
        return
    # Pandas Styler: беремо його вихідний DataFrame; стандарт таблиць важливіший
    # за локальні стилі Styler, а статуси підсвічуються централізовано нижче.
    if hasattr(data, "data") and isinstance(getattr(data, "data"), pd.DataFrame):
        frame = data.data.copy()
    elif isinstance(data, pd.DataFrame):
        frame = data.copy()
    else:
        try:
            frame = pd.DataFrame(data)
        except Exception:
            st.info(empty_message)
            return
    if frame.empty:
        st.info(empty_message)
        return

    formatter = value_formatter or (lambda value: "—" if pd.isna(value) or value is None or str(value).strip() == "" else str(value))
    formatters = formatters or {}
    column_widths = {str(key): value for key, value in (column_widths or {}).items()}
    scroll_columns = {str(value) for value in (scroll_columns or [])}
    columns = [str(c) for c in frame.columns]
    display_column_count = len(columns) + (1 if show_index else 0)
    if min_width is None:
        min_width = max(900, min(5600, 165 * max(1, display_column_count)))
    row_pad = "6px 8px" if compact else "8px 10px"
    font_size = 12 if compact else 13

    # Ширина таблиці може працювати у трьох режимах:
    # - None: історичний системний стандарт (wrapper 100%, table >= min_width);
    # - відсоток / px: wrapper займає рівно задану ширину, table заповнює його;
    # - "fit-columns": ширина table = сумі заданих колонок, wrapper лише обрізає
    #   її по viewport і дає зовнішній горизонтальний скрол. Це прибирає порожній
    #   білий хвіст після останньої колонки у широких Dashboard-таблицях.
    fit_columns = str(table_width).strip().lower() == "fit-columns"
    explicit_wrapper_width = None
    if table_width is not None and not fit_columns:
        if isinstance(table_width, (int, float)):
            explicit_wrapper_width = f"{max(1, int(table_width))}px"
        else:
            explicit_wrapper_width = str(table_width).strip() or None

    def _column_css_width(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return f"{max(1, int(value))}px"
        text = str(value).strip()
        return text if text else ""

    col_parts = []
    if show_index:
        col_parts.append("<col style='width:54px'>")
    for col in columns:
        width = _column_css_width(column_widths.get(col))
        col_parts.append(f"<col style='width:{escape(width)}'>" if width else "<col>")
    colgroup = "<colgroup>" + "".join(col_parts) + "</colgroup>"

    if fit_columns:
        def _column_px(value: Any) -> int:
            if isinstance(value, (int, float)):
                return max(1, int(value))
            text = str(value or "").strip().lower()
            if text.endswith("px"):
                try:
                    return max(1, int(float(text[:-2].strip())))
                except ValueError:
                    pass
            return 165

        exact_width = (54 if show_index else 0) + sum(
            _column_px(column_widths.get(col)) for col in columns
        )
        wrapper_width_css = "fit-content"
        wrapper_max_width_css = "100%"
        table_width_css = f"{exact_width}px"
        table_min_width_css = table_width_css
    elif explicit_wrapper_width:
        wrapper_width_css = explicit_wrapper_width
        wrapper_max_width_css = "100%"
        table_width_css = "100%"
        table_min_width_css = "100%"
    else:
        wrapper_width_css = "100%"
        wrapper_max_width_css = "100%"
        table_width_css = "100%"
        table_min_width_css = f"{int(min_width)}px"

    css = f"""
    <style>
    .readonly-table-scroll {{ overflow:auto; width:{wrapper_width_css} !important; max-width:{wrapper_max_width_css} !important; max-height:{int(height)}px; border:1px solid #DCE4F0; border-radius:10px; margin:8px 0 18px 0; background:#fff; }}
    table.readonly-table {{ border-collapse:collapse; table-layout:fixed; min-width:{table_min_width_css} !important; width:{table_width_css} !important; max-width:none !important; font-size:{font_size}px; color:#132238; }}
    table.readonly-table th {{ position:sticky; top:0; z-index:3; background:#EAF1FF; color:#132238; padding:9px 10px; border:1px solid #DCE4F0; text-align:center; vertical-align:middle; white-space:normal; font-weight:850; line-height:1.22; }}
    table.readonly-table td {{ padding:{row_pad}; border:1px solid #DCE4F0; vertical-align:middle; text-align:center; white-space:normal; overflow-wrap:anywhere; line-height:1.32; }}
    table.readonly-table tr:nth-child(even) {{ background:#F7F9FC; }}
    table.readonly-table tr:nth-child(odd) {{ background:#FFFFFF; }}
    table.readonly-table .readonly-cell {{ display:block; max-height:{int(max_cell_height)}px; overflow:hidden; }}
    table.readonly-table .readonly-cell:hover {{ overflow:auto; }}
    table.readonly-table .readonly-cell-scroll {{ overflow:auto !important; scrollbar-width:thin; padding-right:2px; }}
    table.readonly-table td.rt-approved {{ color:#0C713A; font-weight:850; }}
    table.readonly-table td.rt-returned, table.readonly-table td.rt-notdone {{ color:#B3261E; font-weight:850; }}
    table.readonly-table td.rt-review {{ color:#032A63; font-weight:850; }}
    table.readonly-table td.rt-partly {{ color:#8A6400; font-weight:850; }}
    table.readonly-table td.rt-notyet {{ color:#61708A; font-weight:750; }}
    table.readonly-table tr.dashboard-rank-green td, table.readonly-table tr.rt-row-green td {{ background:#EEF9F2 !important; }}
    table.readonly-table tr.dashboard-rank-yellow td, table.readonly-table tr.rt-row-yellow td {{ background:#FFF8E6 !important; }}
    table.readonly-table tr.dashboard-rank-red td, table.readonly-table tr.rt-row-red td {{ background:#FDEEEE !important; }}
    </style>
    """
    head = ("<th></th>" if show_index else "") + "".join(f"<th>{escape(col)}</th>" for col in columns)
    rows = []
    total_rows = len(frame)
    for index_value, row in frame.iterrows():
        row_class = ""
        if row_class_fn is not None:
            try:
                row_class = str(row_class_fn(row, total_rows) or "").strip()
            except Exception:
                row_class = ""
        cells = []
        if show_index:
            shown_index = formatter(index_value)
            cells.append(f"<td><span class='readonly-cell'>{escape(str(shown_index)).replace(chr(10), '<br>')}</span></td>")
        for col in frame.columns:
            raw = row.get(col)
            try:
                local_formatter = formatters.get(str(col)) or formatters.get(col)
                shown = local_formatter(raw) if local_formatter is not None else formatter(raw)
            except Exception:
                shown = str(raw) if raw is not None else "—"
            status_class = _readonly_status_class(shown)
            safe_shown = escape(str(shown)).replace("\n", "<br>")
            span_class = (
                "readonly-cell readonly-cell-scroll"
                if str(col) in scroll_columns else "readonly-cell"
            )
            cells.append(
                f"<td class='{status_class}'><span class='{span_class}'>{safe_shown}</span></td>"
            )
        class_attr = f" class='{escape(row_class)}'" if row_class else ""
        rows.append(f"<tr{class_attr}>" + "".join(cells) + "</tr>")
    html = css + (
        "<div class='readonly-table-scroll'><table class='readonly-table'>"
        f"{colgroup}<thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )
    # st.html is the dedicated Streamlit renderer for trusted application HTML.
    # It is more robust than routing a large table through the Markdown parser
    # (large locked tables could otherwise appear as literal <div>/<table> text).
    if hasattr(st, "html"):
        st.html(html)
    else:  # compatibility fallback for older Streamlit releases
        st.markdown(html, unsafe_allow_html=True)



_SIGNAL_GRID_LOGGER = logging.getLogger(__name__)
_SIGNAL_GRID_VARIANTS = {
    "standard", "compact", "history", "log", "analytics", "ranking",
    "problems", "finance", "wide", "status-grid",
}
_SIGNAL_GRID_CROWN_COLORS = {
    "navy": "#032A63", "blue": "#005BBB", "light-blue": "#BFD3F2",
    "red": "#DC4A4A", "green": "#118847", "yellow": "#F4B400",
}


def _signal_grid_frame(data: Any) -> pd.DataFrame | None:
    """Presentation-only normalization; never mutate the caller's DataFrame."""
    if data is None:
        return None
    if hasattr(data, "data") and isinstance(getattr(data, "data"), pd.DataFrame):
        return data.data.copy()
    if isinstance(data, pd.DataFrame):
        return data.copy()
    try:
        return pd.DataFrame(data)
    except Exception:
        return None


def _signal_grid_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        missing = pd.isna(value)
        if isinstance(missing, bool):
            return missing
    except (TypeError, ValueError):
        pass
    return False


def _signal_grid_default_text(value: Any) -> str:
    if _signal_grid_missing(value):
        return "—"
    text = str(value).strip()
    return text if text and text.lower() not in {"none", "nan", "nat", "<na>"} else "—"


def _signal_grid_numeric(value: Any) -> float | None:
    """Best-effort parser for decorative underlines only; calculation data is untouched."""
    if _signal_grid_missing(value) or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    text = str(value).strip().replace("\u00a0", " ").replace(" ", "")
    if not text or text in {"—", "-"}:
        return None
    text = text.replace(",", ".")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _signal_grid_risk_class(value: Any) -> str:
    text = _signal_grid_default_text(value).casefold()
    if "крит" in text:
        return "sg-risk-critical"
    if "висок" in text:
        return "sg-risk-high"
    if "серед" in text:
        return "sg-risk-medium"
    if "низьк" in text:
        return "sg-risk-low"
    return ""


def _signal_grid_columns(value: Any, columns: list[str]) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, dict):
        candidates = value.keys()
    elif isinstance(value, str):
        candidates = [value]
    else:
        try:
            candidates = list(value)
        except TypeError:
            candidates = []
    existing = set(columns)
    return {str(col) for col in candidates if str(col) in existing}


def _signal_grid_metric_colors(value: Any, columns: list[str]) -> dict[str, str]:
    allowed = {
        "blue": "#005BBB", "green": "#118847", "red": "#DC4A4A",
        "yellow": "#F4B400", "navy": "#032A63",
    }
    active = _signal_grid_columns(value, columns)
    result = {col: allowed["blue"] for col in active}
    if isinstance(value, dict):
        for col in active:
            raw = str(value.get(col, "blue")).strip().casefold()
            result[col] = allowed.get(raw, allowed["blue"])
    return result


def _signal_grid_crowns(column_groups: Any, columns: list[str]) -> dict[str, str]:
    """Return per-column accent colors. Invalid/missing columns are safe no-ops."""
    if not isinstance(column_groups, dict):
        return {}
    existing = set(columns)
    result: dict[str, str] = {}
    for group, spec in column_groups.items():
        color = "#005BBB"
        group_columns: Any = []
        if isinstance(spec, dict):
            group_columns = spec.get("columns", [])
            raw_color = str(spec.get("color", "blue")).strip().casefold()
            color = _SIGNAL_GRID_CROWN_COLORS.get(raw_color, "#005BBB")
        else:
            group_columns = spec
            raw_group = str(group).strip().casefold()
            color = _SIGNAL_GRID_CROWN_COLORS.get(raw_group, "#005BBB")
        if isinstance(group_columns, str):
            group_columns = [group_columns]
        try:
            for col in group_columns:
                if str(col) in existing:
                    result[str(col)] = color
        except TypeError:
            continue
    return result


def _render_readonly_table_signal(
    data: Any,
    *,
    height: int = 325,
    min_width: int | None = None,
    max_cell_height: int = 74,
    compact: bool = False,
    empty_message: str = "Немає даних для відображення.",
    value_formatter: Callable[[Any], str] | None = None,
    formatters: dict[str, Callable[[Any], Any]] | None = None,
    row_class_fn: Callable[[pd.Series, int], str] | None = None,
    show_index: bool = False,
    column_widths: dict[str, int | str] | None = None,
    scroll_columns: list[str] | set[str] | tuple[str, ...] | None = None,
    table_width: str | int | None = None,
    variant: str = "standard",
    focus_column: str | None = None,
    metric_columns: list[str] | set[str] | tuple[str, ...] | dict[str, str] | None = None,
    status_columns: list[str] | set[str] | tuple[str, ...] | None = None,
    risk_columns: list[str] | set[str] | tuple[str, ...] | None = None,
    delta_columns: list[str] | set[str] | tuple[str, ...] | None = None,
    column_groups: dict[str, Any] | None = None,
    signal_edges: bool = False,
) -> None:
    """Opt-in Signal Grid. Decorative configuration is defensive and presentation-only."""
    frame = _signal_grid_frame(data)
    if frame is None or frame.empty:
        st.info(empty_message)
        return

    columns = [str(c) for c in frame.columns]
    formatter = value_formatter or _signal_grid_default_text
    formatters = formatters or {}
    column_widths = {str(key): value for key, value in (column_widths or {}).items() if str(key) in set(columns)}
    scroll_columns_set = _signal_grid_columns(scroll_columns, columns)
    status_columns_set = _signal_grid_columns(status_columns, columns)
    risk_columns_set = _signal_grid_columns(risk_columns, columns)
    delta_columns_set = _signal_grid_columns(delta_columns, columns)
    metric_colors = _signal_grid_metric_colors(metric_columns, columns)
    focus_column = str(focus_column) if focus_column is not None and str(focus_column) in set(columns) else None
    crowns = _signal_grid_crowns(column_groups, columns)
    variant = str(variant or "standard").strip().casefold()
    if variant not in _SIGNAL_GRID_VARIANTS:
        variant = "standard"

    dense = compact or variant in {"compact", "history", "log"}
    row_pad = "5px 8px" if dense else "7px 10px"
    font_size = 12 if dense else 13
    display_column_count = len(columns) + (1 if show_index else 0)
    if min_width is None:
        min_width = max(900, min(5600, 165 * max(1, display_column_count)))

    fit_columns = str(table_width).strip().lower() == "fit-columns"
    explicit_wrapper_width = None
    if table_width is not None and not fit_columns:
        if isinstance(table_width, (int, float)):
            explicit_wrapper_width = f"{max(1, int(table_width))}px"
        else:
            explicit_wrapper_width = str(table_width).strip() or None

    def _column_css_width(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return f"{max(1, int(value))}px"
        text = str(value).strip()
        return text if text else ""

    col_parts = ["<col style='width:54px'>"] if show_index else []
    for col in columns:
        width = _column_css_width(column_widths.get(col))
        col_parts.append(f"<col style='width:{escape(width)}'>" if width else "<col>")
    colgroup = "<colgroup>" + "".join(col_parts) + "</colgroup>"

    if fit_columns:
        def _column_px(value: Any) -> int:
            if isinstance(value, (int, float)):
                return max(1, int(value))
            text = str(value or "").strip().lower()
            if text.endswith("px"):
                try:
                    return max(1, int(float(text[:-2].strip())))
                except ValueError:
                    pass
            return 165
        exact_width = (54 if show_index else 0) + sum(_column_px(column_widths.get(col)) for col in columns)
        wrapper_width_css, wrapper_max_width_css = "fit-content", "100%"
        table_width_css = table_min_width_css = f"{exact_width}px"
    elif explicit_wrapper_width:
        wrapper_width_css, wrapper_max_width_css = explicit_wrapper_width, "100%"
        table_width_css = table_min_width_css = "100%"
    else:
        wrapper_width_css, wrapper_max_width_css = "100%", "100%"
        table_width_css, table_min_width_css = "100%", f"{int(min_width)}px"

    variant_class = f"signal-grid-{variant}"
    css = f"""
    <style>
    .signal-grid-wrap {{ width:{wrapper_width_css} !important; max-width:{wrapper_max_width_css} !important; border:1px solid #DCE4F0; border-radius:13px; background:#FFFFFF; box-shadow:0 4px 14px rgba(15,23,42,.04); margin:8px 0 18px 0; }}
    .signal-grid-scroll {{ overflow:auto; width:100%; max-width:100%; max-height:{int(height)}px; border-radius:13px; scrollbar-width:thin; }}
    table.signal-grid-table {{ border-collapse:separate; border-spacing:0; table-layout:fixed; min-width:{table_min_width_css} !important; width:{table_width_css} !important; max-width:none !important; font-size:{font_size}px; color:#132238; background:#FFFFFF; }}
    table.signal-grid-table th {{ position:sticky; top:0; z-index:3; background:#F5F8FD; color:#61708A; padding:8px 10px; border:0; border-bottom:1px solid #DCE4F0; text-align:left; vertical-align:middle; white-space:normal; font-weight:700; line-height:1.2; }}
    table.signal-grid-table td {{ padding:{row_pad}; border:0; border-bottom:1px solid #E8EDF4; vertical-align:middle; text-align:left; white-space:normal; overflow-wrap:anywhere; line-height:1.3; background:#FFFFFF; }}
    table.signal-grid-table tbody tr:last-child td {{ border-bottom:0; }}
    table.signal-grid-table tbody tr:hover td {{ background:#F8FAFD; }}
    table.signal-grid-table .sg-align-right {{ text-align:right; font-variant-numeric:tabular-nums; }}
    table.signal-grid-table .sg-align-center {{ text-align:center; }}
    table.signal-grid-table .sg-primary {{ color:#132238; font-weight:650; }}
    table.signal-grid-table .sg-focus {{ background:#F3F7FD !important; }}
    table.signal-grid-table .signal-grid-cell {{ display:block; max-height:{int(max_cell_height)}px; overflow:hidden; }}
    table.signal-grid-table .signal-grid-cell:hover {{ overflow:auto; }}
    table.signal-grid-table .signal-grid-cell-scroll {{ overflow:auto !important; scrollbar-width:thin; padding-right:2px; }}
    table.signal-grid-table .signal-grid-status {{ display:inline-flex; align-items:center; gap:5px; max-width:100%; border-radius:999px; padding:2px 7px; font-weight:700; line-height:1.25; }}
    table.signal-grid-table .signal-grid-status::before {{ content:""; flex:0 0 auto; width:6px; height:6px; border-radius:50%; background:currentColor; }}
    table.signal-grid-table td.rt-approved .signal-grid-status {{ color:#0C713A; background:#E4F5EC; }}
    table.signal-grid-table td.rt-returned .signal-grid-status, table.signal-grid-table td.rt-notdone .signal-grid-status {{ color:#B3261E; background:#FBE5E5; }}
    table.signal-grid-table td.rt-review .signal-grid-status {{ color:#005BBB; background:#EAF1FF; }}
    table.signal-grid-table td.rt-partly .signal-grid-status {{ color:#8A6400; background:#FDF3D8; }}
    table.signal-grid-table td.rt-notyet .signal-grid-status {{ color:#61708A; background:#F1F4F8; }}
    table.signal-grid-table .signal-grid-metric {{ display:inline-block; min-width:42px; max-width:100%; font-weight:700; font-variant-numeric:tabular-nums; text-align:right; }}
    table.signal-grid-table .signal-grid-metric::after {{ content:""; display:block; height:2px; width:var(--sg-width,0%); max-width:100%; margin-top:2px; margin-left:auto; border-radius:99px; background:var(--sg-color,#005BBB); }}
    table.signal-grid-table .sg-delta-positive {{ color:#0C713A; font-weight:700; }}
    table.signal-grid-table .sg-delta-negative {{ color:#B3261E; font-weight:700; }}
    table.signal-grid-table .sg-risk-low {{ color:#0C713A; font-weight:700; }}
    table.signal-grid-table .sg-risk-medium {{ color:#8A6400; font-weight:700; }}
    table.signal-grid-table .sg-risk-high, table.signal-grid-table .sg-risk-critical {{ color:#B3261E; font-weight:750; }}
    table.signal-grid-table tr.dashboard-rank-green td:first-child, table.signal-grid-table tr.rt-row-green td:first-child {{ box-shadow:inset 3px 0 0 #118847; }}
    table.signal-grid-table tr.dashboard-rank-yellow td:first-child, table.signal-grid-table tr.rt-row-yellow td:first-child {{ box-shadow:inset 3px 0 0 #F4B400; }}
    table.signal-grid-table tr.dashboard-rank-red td:first-child, table.signal-grid-table tr.rt-row-red td:first-child {{ box-shadow:inset 3px 0 0 #DC4A4A; }}
    table.signal-grid-table.signal-grid-log th, table.signal-grid-table.signal-grid-history th {{ padding-top:7px; padding-bottom:7px; }}
    </style>
    """

    def _alignment_class(col: str) -> str:
        if col in status_columns_set or col in risk_columns_set:
            return "sg-align-center"
        if col in metric_colors or col in delta_columns_set:
            return "sg-align-right"
        try:
            source = frame[col]
            if pd.api.types.is_numeric_dtype(source.dtype):
                return "sg-align-right"
        except Exception:
            pass
        return ""

    head_parts = []
    if show_index:
        head_parts.append("<th class='sg-align-center'></th>")
    for col in columns:
        classes = [_alignment_class(col)]
        if col == focus_column:
            classes.append("sg-focus")
        crown_style = f" style='border-top:3px solid {escape(crowns[col])}'" if col in crowns else ""
        head_parts.append(f"<th class='{escape(' '.join(filter(None, classes)))}'{crown_style}>{escape(col)}</th>")
    head = "".join(head_parts)

    rows = []
    total_rows = len(frame)
    for index_value, row in frame.iterrows():
        row_class = ""
        if row_class_fn is not None:
            try:
                row_class = str(row_class_fn(row, total_rows) or "").strip()
            except Exception as exc:
                _SIGNAL_GRID_LOGGER.warning("Signal Grid row class skipped: %s", exc)
        cells = []
        if show_index:
            shown_index = _signal_grid_default_text(index_value)
            cells.append(f"<td class='sg-align-center'><span class='signal-grid-cell'>{escape(shown_index)}</span></td>")
        for original_col in frame.columns:
            col = str(original_col)
            raw = row.get(original_col)
            try:
                local_formatter = formatters.get(col) or formatters.get(original_col)
                shown = local_formatter(raw) if local_formatter is not None else formatter(raw)
            except Exception as exc:
                _SIGNAL_GRID_LOGGER.warning("Signal Grid formatter skipped for %s: %s", col, exc)
                shown = _signal_grid_default_text(raw)
            shown_text = _signal_grid_default_text(shown)
            status_class = _readonly_status_class(shown_text)
            classes = [status_class, _alignment_class(col)]
            if col == focus_column:
                classes.append("sg-focus")
            if col in risk_columns_set:
                classes.append(_signal_grid_risk_class(shown_text))
            numeric = _signal_grid_numeric(shown)
            if col in delta_columns_set and numeric is not None:
                classes.append("sg-delta-positive" if numeric > 0 else "sg-delta-negative" if numeric < 0 else "")
            span_class = "signal-grid-cell signal-grid-cell-scroll" if col in scroll_columns_set else "signal-grid-cell"
            safe_shown = escape(shown_text).replace("\n", "<br>")
            if status_class or col in status_columns_set:
                content = f"<span class='signal-grid-status'>{safe_shown}</span>"
            elif col in metric_colors and numeric is not None:
                width = max(0.0, min(100.0, abs(float(numeric))))
                color = metric_colors[col]
                if col in delta_columns_set:
                    color = "#118847" if numeric > 0 else "#DC4A4A" if numeric < 0 else "#61708A"
                content = (
                    f"<span class='signal-grid-metric' style='--sg-width:{width:.2f}%;--sg-color:{escape(color)}'>"
                    f"{safe_shown}</span>"
                )
            else:
                content = safe_shown
            cells.append(
                f"<td class='{escape(' '.join(filter(None, classes)))}'><span class='{span_class}'>{content}</span></td>"
            )
        class_attr = f" class='{escape(row_class)}'" if row_class and signal_edges else ""
        rows.append(f"<tr{class_attr}>" + "".join(cells) + "</tr>")

    html = css + (
        f"<div class='signal-grid-wrap {variant_class}'><div class='signal-grid-scroll'>"
        f"<table class='signal-grid-table {variant_class}'>{colgroup}<thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div></div>"
    )
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


def render_readonly_table(
    data: Any,
    *,
    height: int = 325,
    min_width: int | None = None,
    max_cell_height: int = 74,
    compact: bool = False,
    empty_message: str = "Немає даних для відображення.",
    value_formatter: Callable[[Any], str] | None = None,
    formatters: dict[str, Callable[[Any], Any]] | None = None,
    row_class_fn: Callable[[pd.Series, int], str] | None = None,
    show_index: bool = False,
    column_widths: dict[str, int | str] | None = None,
    scroll_columns: list[str] | set[str] | tuple[str, ...] | None = None,
    table_width: str | int | None = None,
    visual_style: str = "legacy",
    variant: str = "standard",
    focus_column: str | None = None,
    metric_columns: list[str] | set[str] | tuple[str, ...] | dict[str, str] | None = None,
    status_columns: list[str] | set[str] | tuple[str, ...] | None = None,
    risk_columns: list[str] | set[str] | tuple[str, ...] | None = None,
    delta_columns: list[str] | set[str] | tuple[str, ...] | None = None,
    column_groups: dict[str, Any] | None = None,
    signal_edges: bool = False,
) -> None:
    """Render a read-only table. Default is the unchanged legacy renderer.

    Signal Grid is opt-in. Any cosmetic Signal Grid exception falls back to the
    same legacy renderer without surfacing a red Streamlit error block.
    """
    legacy_kwargs = dict(
        height=height, min_width=min_width, max_cell_height=max_cell_height,
        compact=compact, empty_message=empty_message, value_formatter=value_formatter,
        formatters=formatters, row_class_fn=row_class_fn, show_index=show_index,
        column_widths=column_widths, scroll_columns=scroll_columns, table_width=table_width,
    )
    if str(visual_style or "legacy").strip().casefold() != "signal":
        return _render_readonly_table_legacy(data, **legacy_kwargs)
    try:
        return _render_readonly_table_signal(
            data, **legacy_kwargs, variant=variant, focus_column=focus_column,
            metric_columns=metric_columns, status_columns=status_columns,
            risk_columns=risk_columns, delta_columns=delta_columns,
            column_groups=column_groups, signal_edges=signal_edges,
        )
    except Exception:
        _SIGNAL_GRID_LOGGER.exception("Signal Grid presentation failed; using legacy table renderer")
        return _render_readonly_table_legacy(data, **legacy_kwargs)

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
    render_readonly_table(
        style_status_columns(table, ["Попередній статус", "Новий статус"]),
        height=325,
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
