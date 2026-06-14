"""Derived notification panels for approval workflows.

This module intentionally derives notifications from existing request data and logs,
without requiring a new Supabase table.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st


def _clean(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _days_waiting(value: object) -> int:
    text = _clean(value)
    if not text:
        return 0
    try:
        dt = pd.to_datetime(text, errors="coerce")
        if pd.isna(dt):
            return 0
        if dt.tzinfo is None:
            dt = dt.tz_localize(timezone.utc)
        now = pd.Timestamp.now(tz=timezone.utc)
        return max(int((now - dt).days), 0)
    except Exception:
        return 0


def build_admin_notifications(requests_df: pd.DataFrame) -> list[dict[str, object]]:
    """Build approval notifications for the Administration page from requests data."""
    if requests_df is None or requests_df.empty:
        return []
    data = requests_df.copy()
    for col in ["approval_status", "submitted_at"]:
        if col not in data.columns:
            data[col] = ""
    statuses = data["approval_status"].astype(str)
    data["_days_waiting"] = data["submitted_at"].apply(_days_waiting)
    return [
        {
            "value": int((statuses == "Очікує погодження").sum()),
            "label": "Нові заявки на погодження",
        },
        {
            "value": int((statuses == "Повернуто на доопрацювання").sum()),
            "label": "Повернуті на доопрацювання",
        },
        {
            "value": int((statuses == "Направлено на підпис").sum()),
            "label": "Направлено на підпис",
        },
        {
            "value": int(((statuses == "Очікує погодження") & (data["_days_waiting"] > 5)).sum()),
            "label": "Очікують понад 5 днів",
        },
    ]


def build_cabinet_notifications(requests_df: pd.DataFrame) -> list[dict[str, object]]:
    """Build approval notifications for the user's cabinet from requests data."""
    if requests_df is None or requests_df.empty:
        return []
    data = requests_df.copy()
    for col in ["approval_status", "admin_comment"]:
        if col not in data.columns:
            data[col] = ""
    statuses = data["approval_status"].astype(str)
    comments = data["admin_comment"].astype(str).str.strip()
    return [
        {
            "value": int((statuses == "Повернуто на доопрацювання").sum()),
            "label": "Повернуто на доопрацювання",
        },
        {
            "value": int((statuses == "Направлено на підпис").sum()),
            "label": "Очікує підпису керівника",
        },
        {
            "value": int((statuses == "Погоджено").sum()),
            "label": "Погоджено",
        },
        {
            "value": int(((comments != "") & (comments.str.lower() != "nan")).sum()),
            "label": "Є коментар координатора",
        },
    ]


def render_notifications_panel(requests_df: pd.DataFrame, mode: str) -> None:
    """Render a compact notification panel for approval pages.

    mode accepts "admin" for the Administration page and "cabinet" for the
    user's cabinet / requests pages. The function does not mutate data.
    """
    if mode == "admin":
        items = build_admin_notifications(requests_df)
    else:
        items = build_cabinet_notifications(requests_df)

    if not items:
        return

    cards = "".join(
        f"""
        <div class=\"app-notification-card\">
            <strong>{int(item['value'])}</strong>
            <span>{_clean(item['label'])}</span>
        </div>
        """
        for item in items
    )
    st.markdown(
        f"""
        <div class=\"app-notification-panel\">
            <div class=\"app-notification-title\">Сповіщення погодження</div>
            <div class=\"app-notification-grid\">{cards}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
