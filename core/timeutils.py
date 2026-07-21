"""Єдине джерело поточного локального часу для інтерфейсу системи."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

KYIV_TZ = ZoneInfo("Europe/Kyiv")


def now_kyiv() -> datetime:
    """Повертає timezone-aware поточний час у часовій зоні Europe/Kyiv."""
    return datetime.now(KYIV_TZ)
