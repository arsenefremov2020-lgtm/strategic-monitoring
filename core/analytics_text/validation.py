from __future__ import annotations

import re
from typing import Any, Iterable

import pandas as pd

from .models import AnalyticsContext, Signal


BANNED_FRAGMENTS = (
    "None%", "nan", "н/д — н/д", "..", "()", "1 заходів", "2 захід", "3 захід", "4 захід",
    "являється", "по стратегічних цілях",
)

CAUSAL_BANS = (
    "через неефективне управління",
    "через недостатню роботу",
    "через брак фінансування",
    "це спричинило",
    "це стало причиною",
)

# Semantic wording that the generator may not use unless the source data carries
# a dedicated factual basis. These are intentionally stricter than numeric checks:
# fabricated meaning is as undesirable as a fabricated number.
SEMANTIC_ALWAYS_BANNED = (
    "більшістю ключових індикаторів",
    "переважна більшість",
    "нижчим за бажаний рівень",
    "високорезультатив",
    "критично низьк",
    "критичної концентрації",
    "репрезентатив",
    "адресний контроль може бути ефективнішим",
    "управлінський ефект очікується",
    "системне покращення",
    "системне погіршення",
)

# Claim -> at least one supporting signal. The wording can appear in several
# grammatical forms, therefore fragments are used rather than exact sentences.
SEMANTIC_SIGNAL_RULES: tuple[tuple[str, frozenset[str]], ...] = (
    (
        "домінуюч",
        frozenset({"status_dominant", "product_dominant"}),
    ),
    (
        "найпоширеніший статус",
        frozenset({"status_dominant"}),
    ),
    (
        "понад полов",
        frozenset({"product_concentration_half_or_more", "goal_problem_concentration_half_or_more", "department_problem_concentration_half_or_more"}),
    ),
    (
        "непропорційно велика частка",
        frozenset({"goal_problem_concentration_half_or_more", "department_problem_concentration_half_or_more"}),
    ),
)


def audit_phrase_library() -> list[str]:
    """Static semantic audit for all registered phrase variants."""
    # Local import avoids a module-level templates -> validation cycle.
    from .templates import PHRASE_LIBRARY

    warnings: list[str] = []
    for variants in PHRASE_LIBRARY.values():
        for variant in variants:
            lowered = variant.template.lower()
            for fragment in SEMANTIC_ALWAYS_BANNED:
                if fragment in lowered:
                    warnings.append(f"{variant.id}: banned semantic claim: {fragment}")
    return warnings


def _numbers_from(value: Any) -> set[float]:
    values: set[float] = set()
    if value is None or isinstance(value, bool):
        return values
    if isinstance(value, (int, float)):
        try:
            if not pd.isna(value):
                values.add(round(float(value), 4))
        except (TypeError, ValueError):
            pass
    elif isinstance(value, dict):
        for key, item in value.items():
            item_values = _numbers_from(item)
            values.update(item_values)
            if "ratio" in str(key).lower():
                values.update(round(v * 100, 4) for v in item_values)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            values.update(_numbers_from(item))
    return values


def allowed_numeric_values(ctx: AnalyticsContext, signals: Iterable[Signal] = ()) -> set[float]:
    allowed = _numbers_from(dict(ctx.metrics))
    for frame in (
        ctx.goal_progress, ctx.task_progress, ctx.department_progress, ctx.product_progress,
        ctx.status_counts, ctx.period_dynamics, ctx.yoy_comparison,
    ):
        if frame is None or frame.empty:
            continue
        for column in frame.columns:
            series = pd.to_numeric(frame[column], errors="coerce").dropna()
            allowed.update(round(float(value), 4) for value in series.tolist())
    for signal in signals:
        allowed.update(_numbers_from(dict(signal.values)))
    return allowed


def _has_allowed(value: float, allowed: set[float], tolerance: float = 0.11) -> bool:
    return any(abs(value - candidate) <= tolerance for candidate in allowed)


def validate_text(text: str, ctx: AnalyticsContext, signals: Iterable[Signal] = ()) -> list[str]:
    warnings: list[str] = []
    if not text.strip():
        warnings.append("generated text is empty")
        return warnings
    lowered = text.lower()
    signal_codes = {signal.code for signal in signals}

    for fragment in BANNED_FRAGMENTS:
        if fragment.lower() in lowered:
            warnings.append(f"forbidden fragment: {fragment}")
    for fragment in CAUSAL_BANS:
        if fragment in lowered:
            warnings.append(f"unsupported causal claim: {fragment}")
    for fragment in SEMANTIC_ALWAYS_BANNED:
        if fragment in lowered:
            warnings.append(f"unsupported semantic claim: {fragment}")
    for fragment, required_codes in SEMANTIC_SIGNAL_RULES:
        if fragment in lowered and not signal_codes.intersection(required_codes):
            warnings.append(f"semantic claim lacks supporting signal: {fragment}")

    if "  " in text:
        warnings.append("double spaces")

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    sentences: list[str] = []
    for paragraph in paragraphs:
        sentences.extend([s.strip() for s in re.split(r"(?<=[.!?])\s+", paragraph) if s.strip()])
    for left, right in zip(sentences, sentences[1:]):
        if left == right:
            warnings.append("duplicated adjacent sentence")
            break

    if len(ctx.goal_progress) <= 1 and "найвищ" in lowered and "найнижч" in lowered and "стратегіч" in lowered:
        warnings.append("meaningless best/worst goal comparison")
    if len(ctx.department_progress) <= 1 and "найвищ" in lowered and "найнижч" in lowered and "ссп" in lowered:
        warnings.append("meaningless best/worst department comparison")

    allowed = allowed_numeric_values(ctx, signals)
    for raw in re.findall(r"(?<!\d)(\d+(?:,\d+)?)%", text):
        value = float(raw.replace(",", "."))
        if not _has_allowed(value, allowed):
            warnings.append(f"percentage not supported by context: {raw}%")
    for raw in re.findall(r"([+-]?\d+(?:,\d+)?)\s*в\.п\.", text):
        value = float(raw.replace(",", "."))
        if not (_has_allowed(value, allowed) or _has_allowed(abs(value), allowed)):
            warnings.append(f"delta not supported by context: {raw} в.п.")
    return warnings


def clean_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +([,.;:])", r"\1", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
