from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import pandas as pd


@dataclass(frozen=True)
class Signal:
    code: str
    severity: str
    importance: int
    dimension: str
    values: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalyticalQuestion:
    code: str
    triggered_by: tuple[str, ...] = ()
    required_dimensions: tuple[str, ...] = ()
    importance: int = 50


@dataclass(frozen=True)
class AnalyticalFinding:
    code: str
    topic: str
    importance: int
    polarity: str = "neutral"
    facts: Mapping[str, Any] = field(default_factory=dict)
    source_signals: tuple[str, ...] = ()
    question_code: str | None = None


@dataclass(frozen=True)
class Scenario:
    code: str
    category: str
    importance: int
    priority: int
    required_signals: tuple[str, ...] = ()
    excluded_signals: tuple[str, ...] = ()
    preferred_blocks: tuple[str, ...] = ()
    required_findings: tuple[str, ...] = ()
    excluded_findings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PhraseVariant:
    id: str
    template: str
    tone: str = "neutral"
    requires: tuple[str, ...] = ()
    suitable_for: tuple[str, ...] = ()
    family: str = "claim"


@dataclass(frozen=True)
class BlockPlan:
    code: str
    importance: int
    depth: str
    target_sentences: tuple[int, int]
    finding_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TextPlan:
    opening: str
    blocks: tuple[str, ...]
    primary_scenario: str
    scenario_mix: tuple[str, ...] = ()
    complexity: str = "standard"
    block_plans: tuple[BlockPlan, ...] = ()
    # Retained as optional debug metadata for API compatibility.  It is no
    # longer a generation quota: content selection determines note length.
    target_paragraphs: tuple[int, int] | None = None

    @property
    def scenario_key(self) -> str:
        return "|".join(self.scenario_mix) if self.scenario_mix else self.primary_scenario

    def block_plan(self, code: str) -> BlockPlan | None:
        return next((item for item in self.block_plans if item.code == code), None)


@dataclass(frozen=True)
class AnalyticalBlock:
    code: str
    topic: str
    importance: int
    signals: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    sentences: tuple[str, ...] = ()
    facts_used: frozenset[str] = frozenset()

    @property
    def text(self) -> str:
        return " ".join(sentence.strip() for sentence in self.sentences if sentence.strip()).strip()


@dataclass(frozen=True)
class NoteQualityMetrics:
    word_count: int
    paragraph_count: int
    sentence_count: int
    important_finding_coverage: float
    repeated_phrase_count: int
    unique_fact_count: int
    median_sentences_per_paragraph: float


@dataclass
class GenerationDebug:
    detected_signals: list[str] = field(default_factory=list)
    analytical_questions: list[str] = field(default_factory=list)
    analytical_findings: list[str] = field(default_factory=list)
    activated_scenarios: list[str] = field(default_factory=list)
    selected_scenarios: list[str] = field(default_factory=list)
    context_complexity: str = ""
    target_paragraph_count: tuple[int, int] | None = None
    selected_blocks: list[str] = field(default_factory=list)
    block_depths: dict[str, str] = field(default_factory=dict)
    sentences_per_block: dict[str, int] = field(default_factory=dict)
    selected_phrase_ids: list[str] = field(default_factory=list)
    facts_used: list[str] = field(default_factory=list)
    important_findings_used: list[str] = field(default_factory=list)
    important_findings_skipped: list[str] = field(default_factory=list)
    planned_findings: dict[str, list[str]] = field(default_factory=dict)
    block_findings: dict[str, list[str]] = field(default_factory=dict)
    finding_dispositions: dict[str, str] = field(default_factory=dict)
    finding_disposition_reasons: dict[str, str] = field(default_factory=dict)
    supporting_findings: list[str] = field(default_factory=list)
    internal_findings: list[str] = field(default_factory=list)
    word_count: int = 0
    quality_metrics: NoteQualityMetrics | None = None
    validation_warnings: list[str] = field(default_factory=list)
    numeric_provenance: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class GenerationState:
    used_phrase_ids: set[str] = field(default_factory=set)
    used_fact_ids: set[str] = field(default_factory=set)
    used_openings: set[str] = field(default_factory=set)
    used_lemmas: dict[str, int] = field(default_factory=dict)
    paragraph_openings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AnalyticsContext:
    filters: Mapping[str, Any]
    metrics: Mapping[str, Any]
    goal_progress: pd.DataFrame
    task_progress: pd.DataFrame
    department_progress: pd.DataFrame
    product_progress: pd.DataFrame
    status_counts: pd.DataFrame
    period_dynamics: pd.DataFrame
    active: pd.DataFrame
    signature: str
    mio_goal_evaluation: pd.DataFrame = field(default_factory=pd.DataFrame)
    mio_goal_task_evaluation: pd.DataFrame = field(default_factory=pd.DataFrame)
    mio_measure_evaluation: pd.DataFrame = field(default_factory=pd.DataFrame)
    mio_financing: pd.DataFrame = field(default_factory=pd.DataFrame)
    analytical_facts: Any = None

    def factual_metric(self, code: str) -> Any:
        return self.analytical_facts.metric(code) if self.analytical_facts is not None else None

    def factual_value(self, code: str, default: Any = None) -> Any:
        return self.analytical_facts.value(code, default) if self.analytical_facts is not None else default

    def factual_structure(self, code: str, default: Any = None) -> Any:
        if self.analytical_facts is None:
            return default
        return self.analytical_facts.structures.get(code, default)

    @staticmethod
    def _safe_metric_int(value: Any) -> int:
        try:
            if value is None or pd.isna(value):
                return 0
        except (TypeError, ValueError):
            return 0
        number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        return 0 if pd.isna(number) else int(number)

    @property
    def sample_size(self) -> int:
        return self._safe_metric_int(self.metrics.get("unique_measures"))

    @property
    def row_count(self) -> int:
        return self._safe_metric_int(self.metrics.get("total_rows"))

    def metric(self, name: str) -> Any:
        return self.metrics.get(name)


@dataclass(frozen=True)
class GeneratedNote:
    text: str
    debug: GenerationDebug
