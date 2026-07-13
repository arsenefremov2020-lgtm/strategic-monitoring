"""Incident-coded error handling for the monitoring application.

Every technical error shown to a user receives a Kyiv-time incident code in
``YYYYMMDD-HHMMSS`` format. The same code and the full traceback are written to
the application log so the administrator can find the cause without exposing
technical details in the interface.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, TypeVar
from zoneinfo import ZoneInfo

import streamlit as st

T = TypeVar("T")
KYIV_TZ = ZoneInfo("Europe/Kyiv")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("monitoring_app")


def create_incident_code() -> str:
    """Return an incident code based on the current Kyiv date and time."""
    return datetime.now(KYIV_TZ).strftime("%Y%m%d-%H%M%S")


def log_exception(context: str, error: BaseException, *, incident_code: str | None = None) -> str:
    """Log a full traceback and return the incident code used in the log."""
    code = incident_code or create_incident_code()
    logger.error(
        "INCIDENT %s | %s | %s: %s",
        code,
        context,
        type(error).__name__,
        error,
        exc_info=(type(error), error, error.__traceback__),
    )
    return code


def log_cosmetic_error(context: str, error: BaseException) -> None:
    """Record a non-critical visual/conversion failure without disturbing users."""
    logger.warning(
        "COSMETIC | %s | %s: %s",
        context,
        type(error).__name__,
        error,
        exc_info=(type(error), error, error.__traceback__),
    )


def incident_message(code: str) -> str:
    return f"Сталася помилка. Код: {code}. Повідомте адміністратора."


def show_incident(error: BaseException, *, context: str, warning: bool = False) -> str:
    """Log an exception and show a safe incident-coded message to the user."""
    code = log_exception(context, error)
    if warning:
        st.warning(incident_message(code))
    else:
        st.error(incident_message(code))
    return code


def show_error(message: str, error: BaseException | None = None,
               context: str | None = None) -> str | None:
    """Compatibility wrapper: technical exceptions are always incident-coded."""
    if error is None:
        st.error(message)
        return None
    return show_incident(error, context=context or message, warning=False)


def show_warning(message: str, error: BaseException | None = None,
                 context: str | None = None) -> str | None:
    """Compatibility wrapper for non-fatal technical failures."""
    if error is None:
        st.warning(message)
        return None
    code = log_exception(context or message, error)
    st.warning(f"{message}\n\n{incident_message(code)}")
    return code


def safe_execute(action: Callable[[], T], fallback: T, user_message: str, context: str) -> T:
    """Run an action and return a fallback with an incident-coded warning."""
    try:
        return action()
    except Exception as exc:
        show_warning(user_message, exc, context)
        return fallback
