from __future__ import annotations

import re
from statistics import median
from typing import Any, Iterable

import pandas as pd

from .models import AnalyticsContext, AnalyticalFinding, NoteQualityMetrics, Signal


BANNED_FRAGMENTS = (
    "None%", "nan", "н/д — н/д", "..", "()", "1 заходів", "2 захід", "3 захід", "4 захід",
    "являється", "по стратегічних цілях",
)

CAUSAL_BANS = (
    "через неефективне управління", "через недостатню роботу", "через брак фінансування",
    "це спричинило", "це стало причиною", "внаслідок неналежної роботи",
)

TECHNICAL_USER_BANS = (
    "canonical", "канонічн", "payload", "dataframe", "scenario", "engine", "context", "контекст генератора",
    "signal code", "phrase id", "rule-based", "hash", "sha-256",
)

UNFINISHED_ANALYSIS_BANS = (
    "необхідно додатково проаналізувати", "варто розглянути розподіл", "результати можуть відрізнятися",
    "це потребує аналізу в розрізі", "для більш повного висновку слід порівняти", "необхідно визначити, які",
    "доцільно перевірити", "варто звернутися до детальнішого розподілу", "важливо зрозуміти, чи",
    "для повнішої картини необхідно", "для розуміння цієї зміни важливо враховувати", "цей показник слід оцінювати разом із",
    "варто також звернути увагу на", "подальший аналіз має бути спрямований", "показує, чи",
)

FILLER_BANS = (
    "слід зазначити, що", "необхідно відзначити, що", "важливо наголосити на тому, що",
    "варто звернути увагу на те, що", "як можна побачити", "як видно з наведених даних",
)

SEMANTIC_ALWAYS_BANNED = (
    "більшістю ключових індикаторів", "переважна більшість", "нижчим за бажаний рівень",
    "високорезультатив", "критично низьк", "критичної концентрації", "репрезентатив",
    "адресний контроль може бути ефективнішим", "управлінський ефект очікується",
    "системне покращення", "системне погіршення",
)


def audit_phrase_library() -> list[str]:
    from .templates import PHRASE_LIBRARY
    warnings: list[str] = []
    forbidden = tuple(x.lower() for x in TECHNICAL_USER_BANS + UNFINISHED_ANALYSIS_BANS + FILLER_BANS + SEMANTIC_ALWAYS_BANNED)
    ids: set[str] = set()
    for variants in PHRASE_LIBRARY.values():
        for variant in variants:
            if variant.id in ids:
                warnings.append(f"duplicate phrase id: {variant.id}")
            ids.add(variant.id)
            lowered = variant.template.lower()
            for fragment in forbidden:
                if fragment in lowered:
                    warnings.append(f"{variant.id}: banned wording: {fragment}")
    return warnings


def _numbers_from(value: Any, key_hint: str = "") -> set[float]:
    values: set[float] = set()
    if value is None or isinstance(value, bool):
        return values
    if isinstance(value, (int, float)):
        try:
            if not pd.isna(value):
                number = round(float(value), 4)
                values.add(number)
                hint = key_hint.lower()
                if any(token in hint for token in ("ratio", "share", "rate")) and abs(number) <= 1.0001:
                    values.add(round(number * 100, 4))
        except (TypeError, ValueError):
            pass
    elif isinstance(value, dict):
        for key, item in value.items():
            values.update(_numbers_from(item, f"{key_hint}.{key}" if key_hint else str(key)))
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            values.update(_numbers_from(item, key_hint))
    return values


def allowed_numeric_values(
    ctx: AnalyticsContext,
    signals: Iterable[Signal] = (),
    findings: Iterable[AnalyticalFinding] = (),
) -> set[float]:
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
    for finding in findings:
        allowed.update(_numbers_from(dict(finding.facts)))
    # Common structural integers are harmless grammatical/count constructs.
    allowed.update(float(i) for i in range(0, max(ctx.row_count, ctx.sample_size, 20) + 1))
    return allowed


def _has_allowed(value: float, allowed: set[float], tolerance: float = 0.12) -> bool:
    return any(abs(value - candidate) <= tolerance for candidate in allowed)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def assess_quality(
    text: str,
    complexity: str,
    findings: Iterable[AnalyticalFinding],
    used_findings: set[str],
    phrase_ids: Iterable[str],
    facts_used: Iterable[str],
) -> NoteQualityMetrics:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    sentence_counts = [len(_sentences(p)) for p in paragraphs]
    important = {f.code for f in findings if f.importance >= 60}
    coverage = len(important & used_findings) / len(important) if important else 1.0
    phrase_list = list(phrase_ids)
    repeated = len(phrase_list) - len(set(phrase_list))
    return NoteQualityMetrics(
        word_count=len(re.findall(r"\b[\w’'-]+\b", text, flags=re.UNICODE)),
        paragraph_count=len(paragraphs), sentence_count=sum(sentence_counts),
        important_finding_coverage=coverage, repeated_phrase_count=repeated,
        unique_fact_count=len(set(facts_used)),
        median_sentences_per_paragraph=float(median(sentence_counts)) if sentence_counts else 0.0,
    )


def validate_text(
    text: str,
    ctx: AnalyticsContext,
    signals: Iterable[Signal] = (),
    findings: Iterable[AnalyticalFinding] = (),
) -> list[str]:
    warnings: list[str] = []
    if not text.strip():
        return ["generated text is empty"]
    lowered = text.lower()
    for fragment in BANNED_FRAGMENTS:
        if fragment.lower() in lowered:
            warnings.append(f"forbidden fragment: {fragment}")
    for fragment in CAUSAL_BANS:
        if fragment in lowered:
            warnings.append(f"unsupported causal claim: {fragment}")
    for fragment in TECHNICAL_USER_BANS:
        if fragment in lowered:
            warnings.append(f"technical user-facing wording: {fragment}")
    for fragment in UNFINISHED_ANALYSIS_BANS:
        if fragment in lowered:
            warnings.append(f"unfinished analytical wording: {fragment}")
    for fragment in FILLER_BANS:
        if fragment in lowered:
            warnings.append(f"filler wording: {fragment}")
    for fragment in SEMANTIC_ALWAYS_BANNED:
        if fragment in lowered:
            warnings.append(f"unsupported semantic claim: {fragment}")
    if "  " in text:
        warnings.append("double spaces")

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    all_sentences: list[str] = []
    for paragraph in paragraphs:
        all_sentences.extend(_sentences(paragraph))
    for left, right in zip(all_sentences, all_sentences[1:]):
        if left == right:
            warnings.append("duplicated adjacent sentence")
            break
    if len(ctx.goal_progress) <= 1 and "найвищ" in lowered and "найнижч" in lowered and "стратегіч" in lowered:
        warnings.append("meaningless best/worst goal comparison")
    if len(ctx.department_progress) <= 1 and "найвищ" in lowered and "найнижч" in lowered and "ссп" in lowered:
        warnings.append("meaningless best/worst department comparison")

    allowed = allowed_numeric_values(ctx, signals, findings)
    for raw in re.findall(r"(?<!\d)(\d+(?:,\d+)?)%", text):
        value = float(raw.replace(",", "."))
        if not _has_allowed(value, allowed):
            warnings.append(f"percentage not supported by analytical facts: {raw}%")
    for raw in re.findall(r"([+-]?\d+(?:,\d+)?)\s*в\.п\.", text):
        value = float(raw.replace(",", "."))
        if not (_has_allowed(value, allowed) or _has_allowed(abs(value), allowed)):
            warnings.append(f"delta not supported by analytical facts: {raw} в.п.")
    return warnings


def clean_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +([,.;:])", r"\1", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
