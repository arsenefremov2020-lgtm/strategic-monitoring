from __future__ import annotations

from .composer import compose_note
from .context import build_context
from .findings import QUESTIONS, SUPPORTED_FINDING_CODES, derive_findings
from .models import (
    AnalyticsContext, AnalyticalBlock, AnalyticalFinding, AnalyticalQuestion, BlockPlan,
    GeneratedNote, GenerationDebug, NoteQualityMetrics, PhraseVariant, Scenario, Signal,
)
from .scenarios import SCENARIOS
from .signals import SUPPORTED_SIGNAL_CODES, detect_signals
from .templates import PHRASE_LIBRARY, phrase_count


def generate_analytics_note(*, context: AnalyticsContext, debug: bool = False):
    """Generate a deterministic, closed-loop Ukrainian analytical note."""
    result = compose_note(context, debug_mode=debug)
    return result if debug else result.text


__all__ = [
    "AnalyticsContext", "AnalyticalBlock", "AnalyticalFinding", "AnalyticalQuestion", "BlockPlan",
    "GeneratedNote", "GenerationDebug", "NoteQualityMetrics", "PhraseVariant", "Scenario", "Signal",
    "SCENARIOS", "PHRASE_LIBRARY", "QUESTIONS", "SUPPORTED_FINDING_CODES", "SUPPORTED_SIGNAL_CODES",
    "build_context", "derive_findings", "detect_signals", "generate_analytics_note", "phrase_count",
]
