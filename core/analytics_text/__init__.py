from __future__ import annotations

from .analytical_metrics import FactualMetric, PreparedAnalyticalFacts
from .composer_overlay import compose_note, detect_signals, derive_findings
from .context import build_context
from .compatibility import FINDING_COMPATIBILITY, compatibility_rows, resolve_finding_disposition
from .findings_current import QUESTIONS, SUPPORTED_FINDING_CODES
from .models import (
    AnalyticsContext, AnalyticalBlock, AnalyticalFinding, AnalyticalQuestion, BlockPlan,
    GeneratedNote, GenerationDebug, NoteQualityMetrics, PhraseVariant, Scenario, Signal,
)
from .scenarios_current import SCENARIOS
from .signals_current import SUPPORTED_SIGNAL_CODES
from .templates import PHRASE_LIBRARY, phrase_count


def generate_analytics_note(*, context: AnalyticsContext, debug: bool = False):
    """Generate the deterministic current-contract Ukrainian analytical note."""
    result = compose_note(context, debug_mode=debug)
    return result if debug else result.text


__all__ = [
    "AnalyticsContext", "AnalyticalBlock", "AnalyticalFinding", "AnalyticalQuestion", "BlockPlan",
    "FactualMetric", "PreparedAnalyticalFacts",
    "GeneratedNote", "GenerationDebug", "NoteQualityMetrics", "PhraseVariant", "Scenario", "Signal",
    "SCENARIOS", "PHRASE_LIBRARY", "QUESTIONS", "SUPPORTED_FINDING_CODES", "SUPPORTED_SIGNAL_CODES",
    "FINDING_COMPATIBILITY", "compatibility_rows", "resolve_finding_disposition",
    "build_context", "derive_findings", "detect_signals", "generate_analytics_note", "phrase_count",
]
