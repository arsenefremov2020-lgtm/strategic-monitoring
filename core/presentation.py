"""Canonical presentation payload for Dashboard browser/PDF renderers.

This module intentionally contains no Dashboard calculations. It only fixes the
renderer contract: both Presentation mode and PDF consume the same ordered,
already-prepared slide payload.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

SLIDE_ORDER = (
    "title",
    "verdict",
    "key_metrics",
    "strategic_goals",
    "risks",
    "top5",
    "finance",
)


def build_presentation_payload(
    *,
    generated_at: datetime,
    applied_filters: Mapping[str, Any],
    title: Mapping[str, Any],
    verdict: Mapping[str, Any],
    key_metrics: Mapping[str, Any],
    strategic_goals: Mapping[str, Any],
    risks: Mapping[str, Any],
    top5: Mapping[str, Any],
    finance: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the one canonical, ordered model used by both presentation renderers."""
    slides = [
        {"key": "title", **dict(title)},
        {"key": "verdict", **dict(verdict)},
        {"key": "key_metrics", **dict(key_metrics)},
        {"key": "strategic_goals", **dict(strategic_goals)},
        {"key": "risks", **dict(risks)},
        {"key": "top5", **dict(top5)},
        {"key": "finance", **dict(finance)},
    ]
    payload = {
        "version": 1,
        "generated_at": generated_at.isoformat(),
        "generated_at_display": generated_at.strftime("%d.%m.%Y %H:%M"),
        "applied_filters": dict(applied_filters),
        "slides": slides,
    }
    validate_presentation_payload(payload)
    return payload


def validate_presentation_payload(payload: Mapping[str, Any]) -> None:
    slides = list(payload.get("slides") or [])
    keys = tuple(str(slide.get("key") or "") for slide in slides)
    if keys != SLIDE_ORDER:
        raise ValueError(f"Presentation slide order must be {SLIDE_ORDER}, got {keys}")
    if len(slides) != 7:
        raise ValueError(f"Presentation payload must contain exactly 7 slides, got {len(slides)}")


def presentation_slides_by_key(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Convenience view for renderers; does not change the canonical slide order."""
    validate_presentation_payload(payload)
    return {str(slide["key"]): slide for slide in payload["slides"]}
