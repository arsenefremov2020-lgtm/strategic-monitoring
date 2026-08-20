from __future__ import annotations

import re
from statistics import median
from typing import Any, Iterable

import pandas as pd

from .models import AnalyticsContext, AnalyticalFinding, NoteQualityMetrics, Signal
from .analytical_metrics import MetricFloat, MetricInt, metric_code_of


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
    "деталізація до рівня завдань показує", "структурна деталізація", "до підсумкового висновку",
    "розріз включено", "це показує ширину внутрішнього розподілу", "використано насамперед частки статусів",
    "продуктовий розріз додатково показує", "часовий розріз показує", "локалізація проблемних позицій показує",
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


_METRIC_MARKER_RE = re.compile(r"⟦metric:([^⟧]+)⟧")


def annotate_numeric(rendered: str, value: Any) -> str:
    """Attach the exact factual metric code used to render one number.

    The marker exists only inside the pre-validation representation and is
    stripped before user-facing text is returned.
    """
    code = metric_code_of(value)
    if not code or not rendered:
        return rendered
    return f"{rendered}⟦metric:{code}⟧"


def strip_numeric_markers(text: str) -> str:
    return _METRIC_MARKER_RE.sub("", text)


def allowed_numeric_values(
    ctx: AnalyticsContext,
    signals: Iterable[Signal] = (),
    findings: Iterable[AnalyticalFinding] = (),
) -> set[float]:
    facts = getattr(ctx, "analytical_facts", None)
    if facts is None:
        return set()
    return {round(float(metric.value), 4) for metric in facts.metrics.values()}


def _rendered_value_before_marker(text: str, marker_start: int) -> tuple[str, float | None, str | None]:
    prefix = text[:marker_start]
    patterns = (
        (r"([+-]?\d+(?:,\d+)?)%$", "percent"),
        (r"([+-]?\d+(?:,\d+)?)\s*в\.п\.$", "pp"),
        (r"([+-]?\d+(?:[.,]\d+)?)$", "number"),
    )
    for pattern, unit in patterns:
        match = re.search(pattern, prefix)
        if match:
            token = match.group(0)
            raw = match.group(1).replace(",", ".")
            try:
                return token, float(raw), unit
            except ValueError:
                return token, None, unit
    return "", None, None


def trace_numeric_provenance(text: str, ctx: AnalyticsContext) -> list[dict[str, Any]]:
    """Trace every rendered number to the exact metric code carried by Composer."""
    facts = getattr(ctx, "analytical_facts", None)
    traced: list[dict[str, Any]] = []
    for marker in _METRIC_MARKER_RE.finditer(text):
        code = marker.group(1)
        metric = facts.metric(code) if facts is not None else None
        rendered, rendered_value, rendered_unit = _rendered_value_before_marker(text, marker.start())
        valid = metric is not None and rendered_value is not None
        if valid:
            expected_unit = metric.unit
            if rendered_unit == "percent":
                valid = expected_unit == "percent"
            elif rendered_unit == "pp":
                valid = expected_unit == "pp"
            else:
                valid = expected_unit in {"count", "number", "currency"}
            # Display rounding is one decimal by default. Absolute wording of a
            # decrease may render a negative pp metric without the minus sign.
            if valid:
                target = float(metric.value)
                if rendered_value >= 0 and target < 0:
                    target = abs(target)
                valid = abs(float(rendered_value) - target) <= 0.11
        traced.append({
            "rendered": rendered,
            "value": rendered_value,
            "unit": rendered_unit,
            "metric_code": code if valid else None,
            "claimed_metric_code": code,
            "source": metric.source if metric else None,
            "aggregation": metric.aggregation if metric else None,
            "numerator": metric.numerator if metric else None,
            "denominator": metric.denominator if metric else None,
            "dependencies": list(metric.dependencies) if metric else [],
            "observation_unit": metric.observation_unit if metric else None,
            "scope": dict(metric.scope) if metric else {},
            "provenance_valid": bool(valid),
        })
    return traced


def _unmarked_quantitative_tokens(annotated_text: str) -> list[str]:
    """Return percentages/deltas that Composer emitted without an exact metric marker."""
    warnings: list[str] = []
    # Percentages and pp are always analytical values, never identifiers.
    for pattern, label in ((r"(?<![\d,])\d+(?:,\d+)?%", "percentage"), (r"(?<![\d,])[+-]?\d+(?:,\d+)?\s*в\.п\.", "delta")):
        for match in re.finditer(pattern, annotated_text):
            tail = annotated_text[match.end():match.end()+9]
            if not tail.startswith("⟦metric:"):
                warnings.append(f"{label} has no factual metric provenance (without metric code): {match.group(0)}")
    return warnings


def validate_finding_numeric_provenance(ctx: AnalyticsContext, findings: Iterable[AnalyticalFinding]) -> list[str]:
    """Require each user-facing finding number to carry its exact factual metric code."""
    warnings: list[str] = []
    facts = getattr(ctx, "analytical_facts", None)
    percentage_tokens = ("share", "rate", "weight", "contribution", "execution", "coverage", "integral", "progress", "value", "average", "median")
    pp_tokens = ("gap", "delta", "change", "excess")

    def walk(value: Any, path: str):
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else str(key))
            return
        if isinstance(value, (list, tuple)):
            for idx, item in enumerate(value):
                walk(item, f"{path}[{idx}]")
            return
        if isinstance(value, bool) or value is None or not isinstance(value, (int, float)):
            return
        leaf = path.rsplit(".", 1)[-1].lower()
        # Years and purely internal ordering scores are identifiers/sorters, not narrative metrics.
        if leaf in {"year", "score"}:
            return
        is_user_numeric = (
            "count" in leaf or leaf in {"rows", "measures", "goals", "tasks", "departments", "products", "period_count", "pair_count", "periods_observed", "periods_with_problem", "periods_with_missing", "evaluated_measures", "paired_count"}
            or any(token in leaf for token in percentage_tokens + pp_tokens)
        )
        if not is_user_numeric:
            return
        code = metric_code_of(value)
        if not code:
            warnings.append(f"finding numeric value has no metric code: {path}={value}")
            return
        metric = facts.metric(code) if facts is not None else None
        if metric is None:
            warnings.append(f"finding metric code not registered: {path}->{code}")
            return
        if abs(float(metric.value) - float(value)) > 1e-9:
            warnings.append(f"finding metric/value mismatch: {path}->{code}: {value} != {metric.value}")

    for finding in findings:
        walk(dict(finding.facts), finding.code)
    return warnings

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
    *,
    annotated_text: str | None = None,
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
    _goal_comparison_count = max(
        len(ctx.goal_progress) if ctx.goal_progress is not None else 0,
        len(ctx.mio_goal_evaluation) if ctx.mio_goal_evaluation is not None else 0,
    )
    # Guard only an actual within-dimension best/worst comparison. The previous
    # whole-note keyword check produced false positives whenever, for example,
    # a one-SSP note also contained best/worst product or task sentences.
    if _goal_comparison_count <= 1 and re.search(
        r"у розрізі стратегічних цілей[^.]*найвищ[^.]*найнижч", lowered
    ):
        warnings.append("meaningless best/worst goal comparison")
    if len(ctx.department_progress) <= 1 and re.search(
        r"у розрізі ссп[^.]*найвищ[^.]*найнижч", lowered
    ):
        warnings.append("meaningless best/worst department comparison")

    provenance_input = annotated_text if annotated_text is not None else text
    provenance = trace_numeric_provenance(provenance_input, ctx)
    warnings.extend(_unmarked_quantitative_tokens(provenance_input))
    for item in provenance:
        if not item.get("provenance_valid"):
            warnings.append(
                f"numeric provenance mismatch: {item.get('rendered') or '?'} -> {item.get('claimed_metric_code') or 'NONE'}"
            )
    warnings.extend(validate_finding_numeric_provenance(ctx, findings))
    return warnings


def clean_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +([,.;:])", r"\1", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
