"""Small error-handling utilities for user-facing Streamlit pages."""

from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar

import streamlit as st

T = TypeVar("T")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("monitoring_app")


def log_exception(context: str, error: Exception) -> None:
    """Write a structured exception to the application log."""
    logger.exception("%s failed: %s", context, error)


def show_error(message: str, error: Exception | None = None, context: str | None = None) -> None:
    """Show a readable error message and optionally log the technical exception."""
    if error is not None:
        log_exception(context or message, error)
    st.error(message)


def show_warning(message: str, error: Exception | None = None, context: str | None = None) -> None:
    """Show a readable warning and optionally log the technical exception."""
    if error is not None:
        log_exception(context or message, error)
    st.warning(message)


def safe_execute(action: Callable[[], T], fallback: T, user_message: str, context: str) -> T:
    """Run an action and return fallback with a visible warning if it fails."""
    try:
        return action()
    except Exception as exc:
        show_warning(user_message, exc, context)
        return fallback
