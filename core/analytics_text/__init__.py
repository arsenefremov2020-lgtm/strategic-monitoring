from __future__ import annotations

from .composer import compose_note
from .context import build_context
from .models import AnalyticsContext, GeneratedNote, GenerationDebug, PhraseVariant, Scenario, Signal
from .scenarios import SCENARIOS
from .signals import SUPPORTED_SIGNAL_CODES, detect_signals
from .templates import PHRASE_LIBRARY, phrase_count


def generate_analytics_note(*, context: AnalyticsContext, debug: bool = False):
    """Generate a deterministic Ukrainian analytical note from canonical facts."""
    result = compose_note(context, debug_mode=debug)
    return result if debug else result.text


__all__ = [
    "AnalyticsContext", "GeneratedNote", "GenerationDebug", "PhraseVariant", "Scenario", "Signal",
    "SCENARIOS", "PHRASE_LIBRARY", "SUPPORTED_SIGNAL_CODES", "build_context", "detect_signals", "generate_analytics_note", "phrase_count",
]
