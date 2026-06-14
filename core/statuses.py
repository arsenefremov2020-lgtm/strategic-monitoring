"""Shared status normalization functions."""

from __future__ import annotations

import pandas as pd


def clean(value: object) -> str:
    """Return a safe stripped string."""
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def status_display(status: object) -> str:
    """Normalize raw monitoring statuses to dashboard display statuses."""
    value = clean(status)
    mapping = {
        "Виконано": "Виконано",
        "Виконано частково": "Частково виконано",
        "Частково виконано": "Частково виконано",
        "Не виконано": "Не виконано",
        "Прострочено": "Не виконано",
        "Не розпочато": "Не виконано",
        "Потребує уваги": "Не виконано",
        "Не подано": "Не виконано",
        "Виконується": "Виконується",
        "Не настав час": "Термін не настав",
        "Термін не настав": "Термін не настав",
        "Втратило актуальність": "Втратив актуальність",
        "Втратив актуальність": "Втратив актуальність",
    }
    return mapping.get(value, value if value else "Не виконано")


def is_excluded_status(status: object) -> bool:
    """Return True for statuses excluded from assessment formulas."""
    return status_display(status) in ["Термін не настав", "Втратив актуальність"]


def status_score(status: object) -> int | None:
    """Return the same status score used by the current dashboards and M&E views."""
    value = clean(status)
    if value == "Виконано":
        return 100
    if value in ["Виконано частково", "Частково виконано"]:
        return 75
    if value == "Виконується":
        return 50
    if value in ["Потребує уваги", "Прострочено", "Не розпочато", "Не подано", "Не виконано"]:
        return 0
    if value in ["Не настав час", "Термін не настав", "Втратило актуальність", "Втратив актуальність"]:
        return None
    return 0
