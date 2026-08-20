from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import pandas as pd


@dataclass(frozen=True)
class Signal:
    code: str
    severity: str
    importance: int
    dimension: str
    values: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    code: str
    category: str
    importance: int
    priority: int
    required_signals: tuple[str, ...] = ()
    excluded_signals: tuple[str, ...] = ()
    preferred_blocks: tuple[str, ...] = ()


@dataclass(frozen=True)
class PhraseVariant:
    id: str
    template: str
    tone: str = "neutral"
    requires: tuple[str, ...] = ()
    suitable_for: tuple[str, ...] = ()


@dataclass(frozen=True)
class TextPlan:
    opening: str
    blocks: tuple[str, ...]
    primary_scenario: str
    scenario_mix: tuple[str, ...] = ()

    @property
    def scenario_key(self) -> str:
        return "|".join(self.scenario_mix) if self.scenario_mix else self.primary_scenario


@dataclass
class GenerationDebug:
    detected_signals: list[str] = field(default_factory=list)
    activated_scenarios: list[str] = field(default_factory=list)
    selected_blocks: list[str] = field(default_factory=list)
    selected_phrase_ids: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)


@dataclass
class GenerationState:
    used_phrase_ids: set[str] = field(default_factory=set)
    used_fact_ids: set[str] = field(default_factory=set)
    used_openings: set[str] = field(default_factory=set)
    used_lemmas: dict[str, int] = field(default_factory=dict)


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
    yoy_comparison: pd.DataFrame
    active: pd.DataFrame
    signature: str

    @property
    def sample_size(self) -> int:
        return int(self.metrics.get("unique_measures") or 0)

    @property
    def row_count(self) -> int:
        return int(self.metrics.get("total_rows") or 0)

    def metric(self, name: str) -> Any:
        return self.metrics.get(name)


@dataclass(frozen=True)
class GeneratedNote:
    text: str
    debug: GenerationDebug
