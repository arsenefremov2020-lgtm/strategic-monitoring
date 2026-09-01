from __future__ import annotations

"""Surgical production overlay for the existing Analytics narrative engine.

The large production composer, scenario library, morphology and templates remain
unchanged. This module only adapts their orchestration to the current Analytics
contract: exact-latest execution, dual coverage, latest-only quarter-aware
management attention, without the retired annual-comparison or accumulated-attention blocks.
"""

import re
from dataclasses import replace
from typing import Iterable

from . import composer as base
from .findings_current import derive_findings as current_derive_findings
from .compatibility import RENDERED, INTERNAL_ONLY, SUPPORTING_ONLY, resolve_findings
from .models import (
    AnalyticsContext,
    AnalyticalBlock,
    AnalyticalFinding,
    GeneratedNote,
    GenerationDebug,
    GenerationState,
    Signal,
)
from .planner import build_text_plan
from .scenarios_current import activate_scenarios
from .signals_current import detect_signals as current_detect_signals
from .validation import annotate_numeric, assess_quality, clean_text, strip_numeric_markers, trace_numeric_provenance, validate_text


def _current_attention_signal(ctx: AnalyticsContext) -> Signal | None:
    """Return the current-quarter attention signal from the prepared current contract."""
    count = ctx.metric("attention_count")
    try:
        count = int(count or 0)
    except (TypeError, ValueError, OverflowError):
        count = 0
    return Signal(
        code="management_attention_present" if count > 0 else "management_attention_none",
        severity="warning" if count > 0 else "positive",
        importance=92 if count > 0 else 35,
        dimension="management_attention",
        values={
            "count": count,
            "attention_type": ctx.metrics.get("attention_type"),
            "attention_label": ctx.metrics.get("attention_label"),
        },
    )


def _signals(ctx: AnalyticsContext) -> list[Signal]:
    """Current-contract signals only; retired concepts are never calculated."""
    raw = current_detect_signals(ctx)
    current = _current_attention_signal(ctx)
    strongest: dict[str, Signal] = {item.code: item for item in raw}
    if current.code not in strongest or current.importance > strongest[current.code].importance:
        strongest[current.code] = current
    return sorted(strongest.values(), key=lambda item: (-item.importance, item.code))


def _findings(ctx: AnalyticsContext, signals: list[Signal]):
    """Current-contract questions/findings; no post-hoc filtering."""
    return current_derive_findings(ctx, signals)


def _scenarios(signals: list[Signal], findings: list[AnalyticalFinding]):
    """Activate only the current scenario registry."""
    return activate_scenarios(signals, findings)


def _measure_count_text(value, raw_number: int) -> str:
    """Render a provenance-bound Ukrainian measure count."""
    n = abs(int(raw_number))
    last_two = n % 100
    last = n % 10
    noun = "захід" if last == 1 and last_two != 11 else ("заходи" if last in {2, 3, 4} and last_two not in {12, 13, 14} else "заходів")
    return f"{annotate_numeric(str(raw_number), value)} {noun}"


def _dimension_label(kind: str, label: str) -> str:
    value = str(label or "").strip()
    if not value:
        return ""
    if kind == "department":
        return value if value.upper().startswith("ССП") else f"ССП «{value}»"
    if kind == "goal":
        return value if value.upper().startswith("СЦ") else f"СЦ {value}"
    return value


def _tied_leaders_text(facts: dict, kind: str) -> str:
    labels = [_dimension_label(kind, value) for value in list(facts.get("top_labels") or [])]
    labels = [value for value in labels if value]
    if not labels:
        return "максимальний рівень однаковий для кількох позицій"
    if len(labels) <= 3:
        return "однаковий максимальний рівень мають " + base.join_uk(labels)
    return "максимальний рівень однаковий для кількох позицій, зокрема " + base.join_uk(labels[:3])



def _group_text(labels: Iterable[str], kind: str | None = None) -> str:
    values = []
    for raw in labels:
        value = _dimension_label(kind, raw) if kind else str(raw or "").strip()
        if value:
            values.append(value)
    if not values:
        return "кілька позицій"
    if len(values) <= 4:
        return base.join_uk(values)
    return "кілька позицій, зокрема " + base.join_uk(values[:3])


def _distribution_semantic_sentences(finding: AnalyticalFinding, kind: str) -> list[str]:
    """Render cross-sectional extrema only when factual uniqueness supports them."""
    f = finding.facts
    count = int(f.get("count") or 0)
    if count <= 1:
        return []
    entity_gen = {"goal": "стратегічних цілей", "task": "завдань", "department": "ССП"}[kind]
    sentences: list[str] = []
    gap = f.get("gap")
    if bool(f.get("all_equal")) or (gap is not None and abs(float(gap)) <= 1e-9):
        sentences.append(
            f"У розрізі {entity_gen} рівень виконання однаковий для всіх "
            f"{annotate_numeric(str(count), f.get('count'))} оцінених позицій — {base._pct(f.get('best_value'))}; "
            "розрив між максимумом і мінімумом відсутній."
        )
    else:
        high_labels = list(f.get("best_labels") or [])
        low_labels = list(f.get("worst_labels") or [])
        if bool(f.get("best_is_unique")):
            high = f"найвищий рівень має {_group_text(high_labels, kind)} — {base._pct(f.get('best_value'))}"
        else:
            high = f"однаковий найвищий рівень мають {_group_text(high_labels, kind)} — {base._pct(f.get('best_value'))}"
        if bool(f.get("worst_is_unique")):
            low = f"найнижчий рівень має {_group_text(low_labels, kind)} — {base._pct(f.get('worst_value'))}"
        else:
            low = f"однаковий найнижчий рівень мають {_group_text(low_labels, kind)} — {base._pct(f.get('worst_value'))}"
        sentences.append(
            f"У розрізі {entity_gen} результати відрізняються: {high}; {low}; "
            f"розрив становить {base._delta_words(gap)}."
        )

    above = int(f.get("above_reference") or 0)
    below = int(f.get("below_reference") or 0)
    reference = f.get("reference")
    if reference is not None:
        relative = (
            f"Порівняно із загальним рівнем виконання {base._pct(reference)}, вище нього перебувають "
            f"{annotate_numeric(str(above), f.get('above_reference'))} із {annotate_numeric(str(count), f.get('count'))} позицій, "
            f"нижче — {annotate_numeric(str(below), f.get('below_reference'))} із {annotate_numeric(str(count), f.get('count'))}."
        )
        deviation = int(f.get("deviation_count") or 0)
        if bool(f.get("deviation_is_material")):
            relative += (
                f" Сукупно відхилення від загального рівня виконання охоплюють {annotate_numeric(str(deviation), f.get('deviation_count'))} "
                f"із {annotate_numeric(str(count), f.get('count'))} позицій, тобто помітну частину розподілу."
            )
        sentences.append(relative)

    top = list(f.get("top") or [])
    bottom = list(f.get("bottom") or [])
    if (
        count >= 3 and not bool(f.get("all_equal")) and top and bottom
        and bool(f.get("top3_boundary_unique", True)) and bool(f.get("bottom3_boundary_unique", True))
    ):
        top_text = ", ".join(f"{label} ({base._pct(value)})" for label, value in top[:3])
        bottom_text = ", ".join(f"{label} ({base._pct(value)})" for label, value in bottom[:3])
        sentences.append(f"Три найвищі результати — {top_text}; нижню частину розподілу формують {bottom_text}.")
    return sentences


def _ssp_portfolio_sentences(finding: AnalyticalFinding) -> list[str]:
    f = finding.facts
    if bool(f.get("single_entity")) or int(f.get("department_count") or 0) <= 1:
        return []
    sentences: list[str] = []
    largest_labels = list(f.get("largest_departments") or [])
    under_labels = list(f.get("top_underperformance_departments") or [])
    largest_unique = bool(f.get("largest_weight_is_unique"))
    under_unique = bool(f.get("top_underperformance_is_unique"))
    same_unique = largest_unique and under_unique and largest_labels and under_labels and largest_labels[0] == under_labels[0]
    if same_unique and f.get("top_underperformance_contribution") is not None:
        label = largest_labels[0]
        sentences.append(
            f"Найбільший за масштабом портфель і водночас найбільший внесок у недовиконання має {_dimension_label('department', label)}: "
            f"частка портфеля {base._pct(f.get('largest_weight'))}, рівень виконання {base._pct(f.get('largest_execution'))}, "
            f"внесок у недовиконання {base._pct(f.get('top_underperformance_contribution'))}."
        )
    else:
        if largest_labels:
            if largest_unique:
                sentences.append(
                    f"Найбільший за масштабом портфель має {_dimension_label('department', largest_labels[0])} — {base._pct(f.get('largest_weight'))} "
                    f"усіх заходів у загальному портфелі; його рівень виконання становить {base._pct(f.get('largest_execution'))}."
                )
            else:
                sentences.append(
                    f"Однакову найбільшу портфельну вагу мають {_group_text(largest_labels, 'department')} — "
                    f"по {base._pct(f.get('largest_weight'))} кожен; єдиного найбільшого ССП за масштабом немає."
                )
        if under_labels and f.get("top_underperformance_contribution") is not None:
            if under_unique:
                sentences.append(
                    f"Найбільша розрахована частка внеску в недовиконання припадає на {_dimension_label('department', under_labels[0])} — "
                    f"{base._pct(f.get('top_underperformance_contribution'))}, тоді як частка цього ССП у портфелі становить "
                    f"{base._pct(f.get('top_underperformance_weight'))}."
                )
            else:
                sentences.append(
                    f"Однаковий максимальний внесок у недовиконання мають {_group_text(under_labels, 'department')} — "
                    f"по {base._pct(f.get('top_underperformance_contribution'))}; єдиного найбільш вагомого негативного ССП немає."
                )
    if under_unique and under_labels and f.get("top_underperformance_contribution") is not None:
        excess = f.get("top_underperformance_excess_pp")
        if excess is not None and abs(float(excess)) >= 0.05:
            relation = "перевищує" if float(excess) > 0 else "є нижчою за"
            sentences.append(
                f"Частка {_dimension_label('department', under_labels[0])} у загальному недовиконанні {relation} його портфельну вагу на "
                f"{base._delta_words(excess)}; це кількісно визначає непропорційність негативного внеску відносно масштабу відповідальності."
            )
    return sentences

def _current_missing_distribution_sentence(finding: AnalyticalFinding, kind: str) -> str | None:
    """Render current missing-data distribution without inventing a unique leader.

    The factual concentration class is shared by findings/signals.  Tied maxima
    are described as ties; no arbitrary row is promoted to "the largest".
    """
    facts = finding.facts
    try:
        total = int(facts.get("total") or 0)
        affected = int(facts.get("affected_entities") or 0)
        entity_count = int(facts.get("entity_count") or 0)
        top_count = int(facts.get("top_count") or 0)
    except (TypeError, ValueError, OverflowError):
        return None
    if total <= 0 or entity_count <= 1:
        return None
    family = finding.code.rsplit("_", 1)[-1]
    dimension = {"goal": "стратегічних цілей", "task": "завдань", "department": "ССП"}[kind]
    top_is_unique = bool(facts.get("top_is_unique"))
    top_label = _dimension_label(kind, str(facts.get("top_label") or ""))

    if family == "distributed":
        return (
            f"У розрізі {dimension} відсутні подання розподілені без єдиного найбільшого осередку: "
            f"неповнота наявна у {annotate_numeric(str(affected), facts.get('affected_entities'))} із "
            f"{annotate_numeric(str(entity_count), facts.get('entity_count'))} позицій."
        )

    details = [
        f"неповнота наявна у {annotate_numeric(str(affected), facts.get('affected_entities'))} із "
        f"{annotate_numeric(str(entity_count), facts.get('entity_count'))} позицій"
    ]
    if top_is_unique and top_label:
        details.append(
            f"найбільше у {top_label} — {annotate_numeric(str(top_count), facts.get('top_count'))} із "
            f"{annotate_numeric(str(total), facts.get('total'))} відсутніх подань"
        )
    else:
        details.append(_tied_leaders_text(facts, kind))
    adjective = "концентрована" if family == "concentrated" else "локалізована"
    return f"У розрізі {dimension} неповнота даних {adjective}: " + "; ".join(details) + "."


def _attention_block(ctx: AnalyticsContext) -> AnalyticalBlock:
    count = ctx.factual_value("page.attention_count", ctx.metric("attention_count"))
    assessed = ctx.factual_value("page.attention_assessed_count", ctx.metric("attention_assessed_count"))
    label = str(ctx.metrics.get("attention_label") or "Потребують управлінської уваги").strip()
    kind = str(ctx.metrics.get("attention_type") or "").strip()
    try:
        n = int(count or 0)
    except (TypeError, ValueError, OverflowError):
        n = 0
    try:
        assessed_n = int(assessed or 0)
    except (TypeError, ValueError, OverflowError):
        assessed_n = 0

    sentences: list[str] = []
    if n <= 0:
        if assessed_n > 0:
            sentences.append(
                f"За актуальним зрізом показник «{label}» не виділяє заходів, що потребують окремої управлінської реакції."
            )
    else:
        sentences.append(
            f"За актуальним зрізом {label.casefold()} — {_measure_count_text(count, n)}. Це кількість унікальних заходів саме останнього обраного періоду, а не сума сигналів за кварталами."
        )
        # Localise the signal without inventing contribution or causality.
        candidates = []
        for prefix, noun in (("goal", "стратегічних цілей"), ("department", "ССП"), ("task", "завдань")):
            facts = ctx.factual_structure(f"{prefix}.attention", {}) or {}
            try:
                top_count = int(facts.get("top_count") or 0)
            except (TypeError, ValueError, OverflowError):
                top_count = 0
            top_label = str(facts.get("top_label") or "").strip()
            try:
                entity_count = int(facts.get("entity_count") or 0)
            except (TypeError, ValueError, OverflowError):
                entity_count = 0
            # A localisation sentence may name a component only when the
            # maximum is unique.  In a tied distribution, choosing the first
            # sorted row would invent a leader that the data do not establish.
            if entity_count > 1 and top_count > 0 and top_label and bool(facts.get("top_is_unique")):
                candidates.append((top_count, prefix, noun, top_label))
        if candidates:
            candidates.sort(key=lambda item: (-item[0], item[3]))
            _, prefix, noun, top_label = candidates[0]
            if prefix == "department":
                sentences.append(f"У розрізі {noun} найбільше виділяється «{top_label}»: тут концентрується найбільша кількість актуальних сигналів уваги у відповідному розподілі.")
            else:
                display_label = top_label
                if prefix == "goal" and not display_label.upper().startswith("СЦ"):
                    display_label = f"СЦ {display_label}"
                sentences.append(f"Серед {noun} найбільше виділяється {display_label}: тут зосереджено найбільше актуальних сигналів уваги у відповідному розподілі.")
    if kind == "preliminary_attention":
        sentences.append("Для I кварталу це попередній сигнал: стандартна шкала прогнозного ризику ще не застосовується.")
    elif kind == "forecast_risk":
        sentences.append("Для II–III кварталів до управлінської уваги віднесено заходи з високим або критичним прогнозним ризиком за чинною методологією.")
    elif kind == "final_nonachievement":
        sentences.append("Для IV кварталу управлінська увага визначається за фактичним недосягненням фінального результату серед оцінених заходів.")
    return AnalyticalBlock(
        "current_management_attention", "management_attention", 98,
        findings=(), sentences=tuple(sentences), facts_used=frozenset({"page.attention_count"}),
    )


def _management_priorities_block(ctx: AnalyticsContext, findings: list[AnalyticalFinding]) -> AnalyticalBlock:
    """Render all current management-attention findings with explicit provenance.

    ``management_priorities`` is only one possible source for this block.  Current
    attention concentration and ``risk_structure`` are independent findings and
    must remain renderable even when no ranking finding was produced.
    """
    item = next((f for f in findings if f.code == "management_priorities"), None)
    priorities = list(item.facts.get("priorities") or []) if item is not None else []
    sentences: list[str] = []
    used_findings: list[str] = []

    for idx, priority in enumerate(priorities[:3], start=1):
        label = str(priority.get("label") or "").strip()
        if not label:
            continue
        kind = str(priority.get("kind") or "")
        execution = priority.get("execution")
        change = priority.get("change")
        attention = priority.get("attention")
        missing = priority.get("missing")
        weight = priority.get("portfolio_weight")
        under = priority.get("underperformance_contribution")
        reasons = set(priority.get("reason_types") or ())

        detail: list[str] = []
        if execution is not None:
            detail.append(f"рівень виконання {base._pct(execution)}")
        if attention is not None:
            try:
                attention_n = int(attention)
            except (TypeError, ValueError, OverflowError):
                attention_n = 0
            if attention_n > 0:
                detail.append(f"актуальні сигнали уваги — {_measure_count_text(attention, attention_n)}")
        if missing is not None:
            try:
                missing_n = int(missing)
            except (TypeError, ValueError, OverflowError):
                missing_n = 0
            if missing_n > 0:
                detail.append(f"відсутні необхідні подання за {_measure_count_text(missing, missing_n)}")
        if change is not None and "decline" in reasons:
            detail.append(f"зміна до першого обраного періоду {base._fmt_delta(change)}")
        if kind == "department" and weight is not None and under is not None and "structural_contribution" in reasons:
            detail.append(
                f"частка портфеля {base._pct(weight)}, розрахована частка недовиконання {base._pct(under)}"
            )

        lead = "Серед пріоритетних точок управлінської уваги" if idx == 1 else "Також у пріоритетній групі"
        if detail:
            sentences.append(f"{lead} — {label}: " + "; ".join(detail) + ".")
        else:
            sentences.append(f"{lead} — {label} за сукупністю актуальних сигналів поточного зрізу.")
    if sentences and item is not None:
        used_findings.append(item.code)

    # Consume each current-attention distribution finding independently.  These
    # statements describe only the exact latest selected period; they never use
    # the retired cumulative semantics.
    dimension_names = {
        "goal": "стратегічних цілей",
        "task": "завдань",
        "department": "ССП",
    }
    for kind in ("goal", "task", "department"):
        attention_finding = next((
            finding for finding in findings
            if finding.code in {
                f"{kind}_attention_concentrated",
                f"{kind}_attention_localised",
                f"{kind}_attention_distributed",
            }
        ), None)
        if attention_finding is None:
            continue
        facts = attention_finding.facts
        total = facts.get("total")
        affected = facts.get("affected_entities")
        entity_count = facts.get("entity_count")
        top_label = str(facts.get("top_label") or "").strip()
        top_count = facts.get("top_count")
        top_share = facts.get("top_share")
        top3_share = facts.get("top3_share")
        family = attention_finding.code.rsplit("_", 1)[-1]
        dimension = dimension_names[kind]
        if kind == "goal" and top_label and not top_label.upper().startswith("СЦ"):
            top_label = f"СЦ {top_label}"

        if family == "concentrated":
            detail = []
            if bool(facts.get("top_is_unique")) and top_label and top_count is not None:
                detail.append(f"найбільше у «{top_label}» — {_measure_count_text(top_count, int(top_count))}")
            elif int(facts.get("top_tie_count") or 0) > 1:
                detail.append(_tied_leaders_text(facts, kind))
            if top_share is not None:
                if bool(facts.get("top_is_unique")):
                    detail.append(f"частка найбільшої позиції {base._pct(top_share)}")
            if (
                top3_share is not None
                and int(entity_count or 0) >= 3
                and bool(facts.get("top3_boundary_unique"))
            ):
                detail.append(f"частка трьох найбільших позицій {base._pct(top3_share)}")
            if detail:
                sentences.append(
                    f"У розрізі {dimension} актуальні сигнали управлінської уваги останнього обраного періоду концентровані: "
                    + "; ".join(detail) + "."
                )
                used_findings.append(attention_finding.code)
        elif family == "localised":
            detail = []
            if affected is not None and entity_count is not None:
                detail.append(
                    f"вони наявні у {annotate_numeric(str(int(affected)), affected)} із {annotate_numeric(str(int(entity_count)), entity_count)} позицій"
                )
            if bool(facts.get("top_is_unique")) and top_label and top_count is not None:
                detail.append(f"найбільше у «{top_label}» — {_measure_count_text(top_count, int(top_count))}")
            elif int(facts.get("top_tie_count") or 0) > 1:
                detail.append(_tied_leaders_text(facts, kind))
            if detail:
                sentences.append(
                    f"У розрізі {dimension} актуальні сигнали управлінської уваги останнього обраного періоду локалізовані: "
                    + "; ".join(detail) + "."
                )
                used_findings.append(attention_finding.code)
        else:
            detail = []
            if affected is not None and entity_count is not None:
                detail.append(
                    f"вони охоплюють {annotate_numeric(str(int(affected)), affected)} із {annotate_numeric(str(int(entity_count)), entity_count)} позицій"
                )
            if total is not None:
                detail.append(f"усього {_measure_count_text(total, int(total))}")
            if detail:
                sentences.append(
                    f"У розрізі {dimension} актуальні сигнали управлінської уваги останнього обраного періоду розподілені: "
                    + "; ".join(detail) + "."
                )
                used_findings.append(attention_finding.code)

    # Risk is a standalone current finding, but its semantics are quarter-aware.
    # Q1 is preliminary only; Q2-Q3 are predictive risk; Q4 is a factual outcome.
    risk = next((finding for finding in findings if finding.code == "risk_structure"), None)
    if risk is not None:
        rf = risk.facts
        mode = str(rf.get("mode") or "").strip()
        risk_parts = []
        prefix = ""
        if mode == "preliminary_attention":
            if rf.get("preliminary_forecast_count") is not None:
                n = int(rf.get("preliminary_forecast_count") or 0)
                risk_parts.append(f"попередній прогноз сформовано для {_measure_count_text(rf.get('preliminary_forecast_count'), n)}")
            if rf.get("preliminary_forecast_average") is not None:
                risk_parts.append(f"середнє прогнозоване досягнення — {base._pct(rf.get('preliminary_forecast_average'))}")
            if rf.get("preliminary_attention_count") is not None:
                n = int(rf.get("preliminary_attention_count") or 0)
                risk_parts.append(f"попередніх сигналів уваги — {_measure_count_text(rf.get('preliminary_attention_count'), n)}")
            prefix = "Попередній зріз I кварталу"
        elif mode == "forecast_risk":
            if rf.get("assessment_state") == "zero_assessed":
                risk_parts.append(
                    "у вибірці немає заходів із розрахованим прогнозним ризиком; частки ризику не розраховуються"
                )
            else:
                if rf.get("high_critical_share") is not None:
                    risk_parts.append(f"частка високого/критичного прогнозного ризику — {base._pct(rf.get('high_critical_share'))}")
                if rf.get("without_substantial_risk_share") is not None:
                    risk_parts.append(f"без суттєвого прогнозного ризику — {base._pct(rf.get('without_substantial_risk_share'))}")
            prefix = "Прогнозний ризиковий зріз II–III кварталу"
        elif mode == "final_nonachievement":
            if rf.get("results_achieved_share") is not None:
                risk_parts.append(f"частка фактично досягнутих результатів — {base._pct(rf.get('results_achieved_share'))}")
            if rf.get("assessed_count") is not None:
                n = int(rf.get("assessed_count") or 0)
                risk_parts.append(f"оцінено {_measure_count_text(rf.get('assessed_count'), n)}")
            prefix = "Фактичний підсумок IV кварталу"
        if risk_parts and prefix:
            sentences.append(prefix + ": " + "; ".join(risk_parts) + ".")
            used_findings.append(risk.code)

    if not sentences:
        return AnalyticalBlock("management_attention", "management_attention", 70, sentences=())
    if item is not None and item.code in used_findings:
        sentences.append(
            "Пріоритетність визначена за актуальними сигналами управлінської уваги, відсутніми поданнями та відхиленнями виконання; вона не є окремою офіційною оцінкою."
        )
    importance = max([finding.importance for finding in findings if finding.code in set(used_findings)] or [70])
    used_findings = list(dict.fromkeys(used_findings))
    return AnalyticalBlock(
        "management_attention", "management_attention", importance, findings=tuple(used_findings),
        sentences=tuple(sentences), facts_used=frozenset(used_findings),
    )



def _movement_current_sentence(finding: AnalyticalFinding, kind: str) -> str | None:
    """Render movement extrema only with explicit tie/single-entity semantics."""
    facts = finding.facts
    try:
        total = int(facts.get("count_with_change") or 0)
        improved = int(facts.get("improved") or 0)
        declined = int(facts.get("declined") or 0)
        stable = int(facts.get("stable") or 0)
    except (TypeError, ValueError, OverflowError):
        return None
    if total <= 0:
        return None
    entity_key = {"goal": "goal", "task": "task", "department": "department"}[kind]
    lead = (
        f"Динаміка доступна для {base._count_uk(total, entity_key)}: "
        f"покращення зафіксовано за {base._count_case_uk(improved, entity_key, 'ins')}, "
        f"погіршення — за {base._count_case_uk(declined, entity_key, 'ins')}, "
        f"мінімальні зміни — за {base._count_case_uk(stable, entity_key, 'ins')}."
    )
    if total == 1:
        return lead
    extrema: list[str] = []
    up = facts.get("largest_improvement"); down = facts.get("largest_deterioration")
    try: up_n = float(up) if up is not None else None
    except (TypeError, ValueError, OverflowError): up_n = None
    try: down_n = float(down) if down is not None else None
    except (TypeError, ValueError, OverflowError): down_n = None
    if improved > 0 and up_n is not None and up_n > 0:
        labels = list(facts.get("largest_improvement_labels") or [])
        if bool(facts.get("largest_improvement_is_unique")):
            extrema.append(f"найбільший приріст має {_group_text(labels, kind)} ({base._fmt_delta(up)})")
        else:
            extrema.append(f"однаковий найбільший приріст мають {_group_text(labels, kind)} ({base._fmt_delta(up)})")
    if declined > 0 and down_n is not None and down_n < 0:
        labels = list(facts.get("largest_deterioration_labels") or [])
        if bool(facts.get("largest_deterioration_is_unique")):
            extrema.append(f"найбільше зниження має {_group_text(labels, kind)} ({base._fmt_delta(down)})")
        else:
            extrema.append(f"однакове найбільше зниження мають {_group_text(labels, kind)} ({base._fmt_delta(down)})")
    if extrema:
        detail = "; ".join(extrema)
        return lead + " " + detail[:1].upper() + detail[1:] + "."
    return lead
def _dynamics_current_block(
    ctx: AnalyticsContext,
    findings: list[AnalyticalFinding],
    opening: str,
    complexity: str,
    prior_blocks: list[AnalyticalBlock],
) -> AnalyticalBlock:
    """Keep production trajectory logic while replacing comparative extrema leaks.

    In wide contexts the preserved dynamics renderer repeats department movement
    and picks scalar extrema.  The current factual change contract carries
    explicit tie/unique metadata, so reuse that instead of promoting the first
    row of a tied maximum/minimum.
    """
    block = base._render_block(ctx, "dynamics", findings, opening, complexity, prior_blocks)
    dep_change = next((item for item in findings if item.code.startswith("department_change_")), None)
    if dep_change is None:
        return block
    replacement = _movement_current_sentence(dep_change, "department")
    if replacement is None:
        return block
    sentences = [
        replacement if sentence.startswith("За ССП картина також не зводиться до одного середнього") else sentence
        for sentence in block.sentences
    ]
    return replace(block, sentences=tuple(sentences))


def _distribution_current_block(
    ctx: AnalyticsContext,
    findings: list[AnalyticalFinding],
    code: str,
    opening: str,
    complexity: str,
    prior_blocks: list[AnalyticalBlock],
) -> AnalyticalBlock:
    """Bridge current hierarchical drill-down facts to the preserved renderer.

    The base renderer predates ``children``.  Keep its normal distribution text,
    remove only the unsupported SSP fallback inference, then append a
    provenance-bound child breakdown when factual child evidence exists.
    """
    block = base._render_block(ctx, code, findings, opening, complexity, prior_blocks)
    dist_kind = {"goals": "goal", "tasks": "task", "departments": "department"}[code]
    dist = next((item for item in findings if item.code == f"{dist_kind}_distribution"), None)
    dist_count = int(dist.facts.get("count") or 0) if dist is not None else 0
    sentences = [
        sentence for sentence in block.sentences
        if "немає одного завдання, яке самостійно концентрує" not in sentence
        and "відхилення розподілені між кількома завданнями" not in sentence
        and not sentence.startswith("У розрізі " + {"goal": "стратегічних цілей", "task": "завдань", "department": "ССП"}[dist_kind] + " результати є диференційованими")
        and not sentence.startswith("Порівняно із загальним рівнем виконання")
        and not sentence.startswith("Серед трьох найвищих результатів")
    ]
    if dist is not None:
        sentences = _distribution_semantic_sentences(dist, dist_kind) + sentences

    # The preserved movement sentence always names both a "largest increase" and
    # a "largest decline". For a monodirectional or fully stable cross-section
    # one of those labels can have the wrong sign. Replace that sentence at the
    # renderer layer using the same bound finding facts; do not post-process text.
    change = next((item for item in findings if item.code.startswith(f"{dist_kind}_change_")), None)
    if change is not None:
        movement = _movement_current_sentence(change, dist_kind)
        if movement is not None:
            sentences = [
                movement if sentence.startswith("Динаміка доступна для") else sentence
                for sentence in sentences
            ]

    # Task missing-data wording in the preserved renderer assumes a unique
    # maximum. Replace it from the current factual tie/concentration contract.
    if code == "tasks":
        task_missing = next((
            item for item in findings
            if item.code.startswith("task_missing_") and item.facts.get("total")
        ), None)
        if task_missing is not None:
            replacement = _current_missing_distribution_sentence(task_missing, "task")
            if replacement:
                sentences = [
                    replacement if sentence.startswith("Неповнота даних на рівні завдань") else sentence
                    for sentence in sentences
                ]

    if code == "departments":
        portfolio = next((item for item in findings if item.code == "ssp_portfolio_impact"), None)
        if portfolio is not None:
            sentences = [
                sentence for sentence in sentences
                if not sentence.startswith("Найбільший за масштабом портфель")
                and not sentence.startswith("Найбільша розрахована в системі частка внеску")
                and not sentence.startswith("Частка ССП «")
            ]
            sentences.extend(_ssp_portfolio_sentences(portfolio))

    finding_code = "goal_drilldown" if code == "tasks" else ("ssp_drilldown" if code == "departments" else None)
    drill = next((item for item in findings if item.code == finding_code), None) if finding_code else None
    # The legacy renderer may mark the parent drill-down finding as used even
    # when it produced no child-evidence sentence.  Current provenance removes
    # that optimistic mark and adds it back only after a factual child breakdown
    # is actually rendered below.
    used = [item_code for item_code in block.findings if not finding_code or item_code != finding_code]
    if drill is not None:
        children = list(drill.facts.get("children") or [])
        if children:
            pieces = []
            for child in children[:3]:
                label = str(child.get("label") or "").strip()
                if not label:
                    continue
                detail = []
                execution = child.get("execution")
                attention = child.get("attention_count")
                missing = child.get("missing_count")
                if execution is not None:
                    detail.append(f"виконання {base._pct(execution)}")
                try:
                    attention_n = int(attention or 0)
                except (TypeError, ValueError, OverflowError):
                    attention_n = 0
                if attention_n > 0:
                    detail.append(f"актуальні сигнали уваги — {_measure_count_text(attention, attention_n)}")
                try:
                    missing_n = int(missing or 0)
                except (TypeError, ValueError, OverflowError):
                    missing_n = 0
                if missing_n > 0:
                    detail.append(f"відсутні подання за {_measure_count_text(missing, missing_n)}")
                pieces.append(label + (": " + ", ".join(detail) if detail else ""))
            if pieces:
                if code == "tasks":
                    parent = str(drill.facts.get("goal_label") or "обраної стратегічної цілі")
                    sentences.append(
                        f"У межах {parent} дочірній розподіл за завданнями виглядає так: "
                        + "; ".join(pieces) + "."
                    )
                else:
                    raw_parent = str(drill.facts.get("department") or "").strip()
                    parent = _dimension_label("department", raw_parent) if raw_parent else "обраного ССП"
                    sentences.append(
                        f"У портфелі {parent} фактично розрахований дочірній розподіл за завданнями: "
                        + "; ".join(pieces) + "."
                    )
                if finding_code not in used:
                    used.append(finding_code)
    return replace(block, findings=tuple(used), sentences=tuple(sentences), facts_used=frozenset(set(block.facts_used) | set(used)))


def _coverage_current_block(
    ctx: AnalyticsContext,
    findings: list[AnalyticalFinding],
    opening: str,
    complexity: str,
    prior_blocks: list[AnalyticalBlock],
) -> AnalyticalBlock:
    block = base._render_block(ctx, "coverage", findings, opening, complexity, prior_blocks)
    sentences = list(block.sentences)
    # The preserved renderer assumes a unique largest component and says "three
    # largest" unconditionally. Replace the whole current missing-distribution
    # branch from factual tie/concentration semantics.
    for kind, prefix in (("department", "У розрізі ССП найбільша кількість"), ("goal", "У розрізі стратегічних цілей найбільша кількість")):
        missing = next((item for item in findings if item.code.startswith(f"{kind}_missing_") and item.facts.get("total")), None)
        replacement = _current_missing_distribution_sentence(missing, kind) if missing is not None else None
        if replacement:
            sentences = [replacement if sentence.startswith(prefix) else sentence for sentence in sentences]
    block = replace(block, sentences=tuple(sentences))
    persistence = next((item for item in findings if item.code == "missing_persistence"), None)
    if persistence is None:
        return block
    sentences = list(block.sentences)
    pieces = []
    for item in list(persistence.facts.get("items") or [])[:3]:
        label = str(item.get("label") or "").strip()
        periods = item.get("periods_with_missing")
        observed = item.get("periods_observed")
        if label and periods is not None and observed is not None:
            pieces.append(
                f"{label}: відсутні подання фіксувалися у {annotate_numeric(str(int(periods)), periods)} із {annotate_numeric(str(int(observed)), observed)} доступних періодів"
            )
    if pieces:
        sentences.append("Повторювана неповнота даних за доступною часовою послідовністю: " + "; ".join(pieces) + ".")
    used = tuple(dict.fromkeys((*block.findings, persistence.code)))
    return replace(block, findings=used, sentences=tuple(sentences), facts_used=frozenset(set(block.facts_used) | {persistence.code}))

def _overall_current_block(ctx: AnalyticsContext, findings: list[AnalyticalFinding]) -> AnalyticalBlock:
    """Render the headline and register every finding actually used by it."""
    item = next((f for f in findings if f.code == "overall_state"), None)
    facts = dict(item.facts) if item else {}
    execution = facts.get("execution_latest")
    goal_execution = facts.get("goal_execution_latest")
    coverage_average = facts.get("coverage_average")
    coverage_latest = facts.get("coverage_latest")
    missing = facts.get("missing_count")
    sentences: list[str] = []
    used: list[str] = [item.code] if item is not None else []
    if execution is not None:
        sentences.append(f"Рівень виконання в останньому обраному періоді становить {base._pct(execution)}.")
    else:
        sentences.append("Для останнього обраного періоду рівень виконання не розраховано: попереднє значення не переноситься вперед.")
    if coverage_average is not None:
        if coverage_latest is not None:
            sentences.append(
                f"Середнє покриття моніторингом за вибраним діапазоном становить {base._pct(coverage_average)}, "
                f"а в останньому обраному періоді — {base._pct(coverage_latest)}."
            )
        else:
            sentences.append(f"Середнє покриття моніторингом за вибраним діапазоном становить {base._pct(coverage_average)}; для останнього обраного періоду покриття не розраховано.")

    relation_finding = next((
        f for f in findings if f.code in {"execution_goal_divergence", "execution_goal_alignment"}
    ), None)
    if relation_finding is not None:
        rf = relation_finding.facts
        measure_value = rf.get("measure_execution")
        goal_value = rf.get("goal_execution")
        gap = rf.get("gap")
        if measure_value is not None and goal_value is not None and gap is not None:
            if relation_finding.code == "execution_goal_divergence":
                relation = "вище" if float(gap) > 0 else "нижче"
                sentences.append(
                    f"На рівні стратегічних цілей результат становить {base._pct(goal_value)}; "
                    f"показник за заходами на {base._delta_words(gap)} {relation}."
                )
            else:
                sentences.append(
                    f"Виконання за заходами ({base._pct(measure_value)}) та за стратегічними цілями ({base._pct(goal_value)}) "
                    f"узгоджене: розрив становить {base._delta_words(gap)}."
                )
            used.append(relation_finding.code)

    try:
        missing_n = int(missing or 0)
    except (TypeError, ValueError, OverflowError):
        missing_n = 0
    if missing_n > 0:
        missing_value = ctx.factual_value("page.no_data", missing)
        sentences.append(f"В актуальному зрізі відсутні необхідні подання за {_measure_count_text(missing_value, missing_n)}.")
    used = list(dict.fromkeys(used))
    return AnalyticalBlock(
        "overall_state", "general", 100, findings=tuple(used),
        sentences=tuple(sentences), facts_used=frozenset(used),
    )




def _statuses_current_block(ctx: AnalyticsContext, findings: list[AnalyticalFinding]) -> AnalyticalBlock:
    item = next((f for f in findings if f.code == "status_structure"), None)
    if item is None:
        return AnalyticalBlock("statuses", "statuses", 40, sentences=())
    f = item.facts
    ranked = list(f.get("ranked") or [])
    total = f.get("total")
    sentences: list[str] = []
    if ranked:
        pieces = [f"{label} — {annotate_numeric(str(int(count)), count)}" for label, count in ranked[:6]]
        sentences.append("Структура статусів у поточній вибірці розподіляється так: " + "; ".join(pieces) + ".")
        labels = list(f.get("dominant_labels") or [])
        if bool(f.get("single_status")):
            label, count = ranked[0]
            sentences.append(
                f"У вибірці зафіксовано лише один статус — «{label}»: {annotate_numeric(str(int(count)), count)} із "
                f"{annotate_numeric(str(int(total)), total)} записів. Порівняння поширеності між статусами тут не проводиться."
            )
        elif bool(f.get("dominant_is_unique")) and labels:
            sentences.append(
                f"Найпоширеніший фактично зафіксований статус — «{labels[0]}»: "
                f"{annotate_numeric(str(int(f.get('dominant_count'))), f.get('dominant_count'))} із "
                f"{annotate_numeric(str(int(total)), total)} записів, або {base._pct(f.get('dominant_share'))}."
            )
        elif labels:
            sentences.append(
                f"Однакову найбільшу кількість записів мають статуси {_group_text([f'«{label}»' for label in labels])} — "
                f"по {annotate_numeric(str(int(f.get('dominant_count'))), f.get('dominant_count'))}; єдиного найпоширенішого статусу немає."
            )
    shares = f.get("shares", {}) or {}
    interpretation_parts = []
    for label in ("Частково виконано", "Не виконано", "Не подано"):
        if label in shares:
            interpretation_parts.append(f"«{label}» — {base._pct(shares[label])}")
    if interpretation_parts:
        sentences.append("Статуси, що безпосередньо впливають на інтерпретацію поточного портфеля, мають такі частки: " + "; ".join(interpretation_parts) + ".")
    sentences.append("Для загальної картини важливими є зміни часток статусів, які формують перехід між невиконанням, частковим та повним виконанням.")
    return AnalyticalBlock("statuses", "statuses", item.importance, findings=(item.code,), sentences=tuple(sentences), facts_used=frozenset({item.code}))


def _products_current_block(ctx: AnalyticsContext, findings: list[AnalyticalFinding]) -> AnalyticalBlock:
    item = next((f for f in findings if f.code == "product_structure"), None)
    if item is None:
        return AnalyticalBlock("products", "products", 35, sentences=())
    f = item.facts
    count = int(f.get("count") or 0)
    sentences: list[str] = []
    largest_labels = list(f.get("largest_labels") or [])
    total_size = f.get("total_size")
    largest_size = f.get("largest_size")
    if count == 1 and largest_labels:
        sentences.append(
            f"За типами продукту в цій вибірці представлено один тип продукту — «{largest_labels[0]}»: "
            f"{annotate_numeric(str(int(largest_size or 0)), largest_size)} із {annotate_numeric(str(int(total_size or 0)), total_size)} унікальних заходів. "
            "Порівняння масштабу між типами продукту не проводиться."
        )
    elif count > 1 and largest_labels and total_size:
        if bool(f.get("all_equal_size")):
            sentences.append(
                f"За масштабом портфеля типи продукту представлені однаково: {_group_text([f'«{x}»' for x in largest_labels])} "
                f"мають по {annotate_numeric(str(int(largest_size or 0)), largest_size)} унікальних заходів; єдиного найбільшого сегмента немає."
            )
        elif bool(f.get("largest_is_unique")):
            sentences.append(
                f"За типами продукту найбільший сегмент — «{largest_labels[0]}»: "
                f"{annotate_numeric(str(int(largest_size or 0)), largest_size)} із {annotate_numeric(str(int(total_size)), total_size)} унікальних заходів, "
                f"або {base._pct(f.get('largest_share'))} портфеля цього розрізу."
            )
        else:
            sentences.append(
                f"Однаковий найбільший сегмент мають типи продукту {_group_text([f'«{x}»' for x in largest_labels])}: "
                f"по {annotate_numeric(str(int(largest_size or 0)), largest_size)} унікальних заходів; єдиного лідера за розміром портфеля немає."
            )

    execution_count = int(f.get("execution_count") or 0)
    if execution_count == 1:
        labels = list(f.get("best_labels") or [])
        if labels:
            sentences.append(
                f"Рівень виконання розраховано лише для типу «{labels[0]}» — {base._pct(f.get('best_value'))}; "
                "порівняння найвищого та найнижчого рівнів за одним оціненим типом не проводиться."
            )
    elif execution_count > 1:
        best_labels = list(f.get("best_labels") or [])
        worst_labels = list(f.get("worst_labels") or [])
        if bool(f.get("all_equal_execution")):
            sentences.append(
                f"Рівень виконання однаковий для всіх {annotate_numeric(str(execution_count), f.get('execution_count'))} оцінених типів продукту — "
                f"{base._pct(f.get('best_value'))}; розрив між максимумом і мінімумом відсутній."
            )
        elif best_labels and worst_labels:
            high = (
                f"найвищий рівень має «{best_labels[0]}»"
                if bool(f.get("best_is_unique"))
                else f"однаковий найвищий рівень мають {_group_text([f'«{x}»' for x in best_labels])}"
            )
            low = (
                f"найнижчий рівень має «{worst_labels[0]}»"
                if bool(f.get("worst_is_unique"))
                else f"однаковий найнижчий рівень мають {_group_text([f'«{x}»' for x in worst_labels])}"
            )
            sentences.append(
                f"За рівнем виконання {high} — {base._pct(f.get('best_value'))}; {low} — {base._pct(f.get('worst_value'))}; "
                f"різниця становить {base._delta_words(f.get('gap'))}."
            )
    return AnalyticalBlock("products", "products", item.importance, findings=(item.code,), sentences=tuple(sentences), facts_used=frozenset({item.code}))


def _mio_current_block(ctx: AnalyticsContext, findings: list[AnalyticalFinding]) -> AnalyticalBlock:
    profile = next((f for f in findings if f.code == "mio_integral_profile"), None)
    divergence = next((f for f in findings if f.code == "mio_execution_result_divergence"), None)
    task_profile = next((f for f in findings if f.code == "mio_task_indicator_profile"), None)
    task_divergence = next((f for f in findings if f.code == "mio_task_execution_result_divergence"), None)
    measure_profile = next((f for f in findings if f.code == "mio_measure_profile"), None)
    financing = next((f for f in findings if f.code == "mio_financing_profile"), None)
    if not any((profile, divergence, task_profile, task_divergence, measure_profile, financing)):
        return AnalyticalBlock("mio_assessment", "mio", 40, sentences=())
    sentences: list[str] = []
    used: list[str] = []
    if profile:
        used.append(profile.code); f = profile.facts; count = int(f.get("goals_count") or 0)
        sentences.append(f"Оцінка МіО за {f.get('year')} рік показує середню інтегральну оцінку стратегічних цілей {base._pct(f.get('average_integral'))}.")
        if count == 1:
            code = str(f.get("best_code") or "")
            sentences.append(
                f"Для єдиної оціненої стратегічної цілі {code} інтегральний результат становить {base._pct(f.get('best_integral'))}; "
                "порівняння найвищого та найнижчого результатів між цілями не проводиться."
            )
        elif count > 1 and bool(f.get("all_equal")):
            sentences.append(
                f"Усі {annotate_numeric(str(count), f.get('goals_count'))} оцінені стратегічні цілі мають однаковий інтегральний результат — "
                f"{base._pct(f.get('best_integral'))}; розрив між максимумом і мінімумом відсутній."
            )
        elif count > 1:
            best_codes = list(f.get("best_codes") or []); worst_codes = list(f.get("worst_codes") or [])
            high = f"найвищий результат має {best_codes[0]}" if bool(f.get("best_is_unique")) and best_codes else f"однаковий найвищий результат мають {_group_text(best_codes)}"
            low = f"найнижчий результат має {worst_codes[0]}" if bool(f.get("worst_is_unique")) and worst_codes else f"однаковий найнижчий результат мають {_group_text(worst_codes)}"
            sentences.append(f"{high} — {base._pct(f.get('best_integral'))}; {low} — {base._pct(f.get('worst_integral'))}; розрив становить {base._delta_words(f.get('gap'))}.")
        comps=[]
        if f.get('average_measures') is not None: comps.append(f"виконання заходів {base._pct(f.get('average_measures'))}")
        if f.get('average_tasks') is not None: comps.append(f"результат завдань за індикаторами {base._pct(f.get('average_tasks'))}")
        if f.get('average_progress') is not None: comps.append(f"прогрес стратегічних індикаторів {base._pct(f.get('average_progress'))}")
        if comps: sentences.append("У середньому компоненти інтегральної оцінки співвідносяться так: " + "; ".join(comps) + ".")
    if divergence:
        used.append(divergence.code); items=list(divergence.facts.get("items") or [])
        if items:
            pieces=[]
            for x in items[:3]:
                direction="вище" if float(x.get('gap') or 0)>0 else "нижче"
                pieces.append(f"{x.get('code')}: виконання заходів {base._pct(x.get('measure_execution'))}, інтеграл {base._pct(x.get('integral'))} ({base._delta_words(x.get('gap'))} {direction})")
            sentences.append("Суттєві розбіжності між операційним виконанням і стратегічним результатом зафіксовано за " + "; ".join(pieces) + ".")
    if task_profile:
        used.append(task_profile.code); f=task_profile.facts; count=int(f.get("tasks_count") or 0)
        sentences.append(f"На рівні завдань прогрес цільових індикаторів у середньому становить {base._pct(f.get('average_task_indicator_progress'))}.")
        if count == 1:
            sentences.append(
                f"Для єдиного оціненого завдання {f.get('best_task')} прогрес індикаторів становить {base._pct(f.get('best_task_progress'))}; "
                "порівняння найвищого та найнижчого результатів між завданнями не проводиться."
            )
        elif count > 1 and bool(f.get("all_equal")):
            sentences.append(
                f"Усі {annotate_numeric(str(count), f.get('tasks_count'))} оцінені завдання мають однаковий прогрес індикаторів — "
                f"{base._pct(f.get('best_task_progress'))}; розрив відсутній."
            )
        elif count > 1:
            best=list(f.get("best_tasks") or []); worst=list(f.get("worst_tasks") or [])
            high=f"найвищий результат має завдання {best[0]}" if bool(f.get("best_is_unique")) and best else f"однаковий найвищий результат мають завдання {_group_text(best)}"
            low=f"найнижчий результат має завдання {worst[0]}" if bool(f.get("worst_is_unique")) and worst else f"однаковий найнижчий результат мають завдання {_group_text(worst)}"
            sentences.append(f"{high} — {base._pct(f.get('best_task_progress'))}; {low} — {base._pct(f.get('worst_task_progress'))}; розрив становить {base._delta_words(f.get('gap'))}.")
    if task_divergence:
        used.append(task_divergence.code); items=list(task_divergence.facts.get("items") or [])
        if items:
            pieces=[]
            for x in items[:3]:
                relation="вище" if float(x.get('gap') or 0)>0 else "нижче"
                pieces.append(f"{x.get('code')}: виконання {base._pct(x.get('execution'))}, прогрес індикаторів {base._pct(x.get('indicator_progress'))} ({base._delta_words(x.get('gap'))} {relation})")
            sentences.append("Суттєві розриви між виконанням завдань і прогресом їхніх індикаторів зафіксовано за " + "; ".join(pieces) + ".")
    if measure_profile:
        used.append(measure_profile.code); f=measure_profile.facts
        if int(f.get('evaluated_measures') or 0):
            n=int(f.get('evaluated_measures') or 0)
            sentences.append(f"На рівні заходів оцінку співвідношення факту до плану доступно для {base._count_uk(n, 'measure')}; середнє значення становить {base._pct(f.get('average_fact_plan'))}, медіанне — {base._pct(f.get('median_fact_plan'))}.")
    if financing:
        used.append(financing.code); f=financing.facts; paired=int(f.get('paired_count') or 0)
        if paired:
            sentences.append(f"Для {base._count_uk(paired, 'measure')} доступне одночасне зіставлення фінансового та фактичного виконання: у середньому фінансове виконання становить {base._pct(f.get('avg_financial_execution'))}, а стан виконання заходів — {base._pct(f.get('avg_physical_execution'))}.")
            gaps=list(f.get('largest_gaps') or [])
            if gaps:
                pieces=[]
                for top in gaps[:3]:
                    delta=top.get('_gap')
                    if delta is None: continue
                    relation="випереджає" if float(delta)>0 else "відстає від"
                    pieces.append(f"{top.get('Захід')}: фінансове виконання {base._pct(top.get('% виконання'))} {relation} фізичний результат {base._pct(top.get('Стан виконання заходу, %'))} на {base._delta_words(delta)}")
                if pieces:
                    sentences.append("Серед розрахованих фінансово-фізичних розривів: " + "; ".join(pieces) + ".")
    return AnalyticalBlock("mio_assessment", "mio", 94, findings=tuple(dict.fromkeys(used)), sentences=tuple(sentences), facts_used=frozenset(used))

def _semantic_key(paragraph: str) -> tuple[str, ...]:
    low = paragraph.casefold()
    tags = []
    for key, words in {
        "goal": ("стратегічн", "сц "),
        "task": ("завдан",),
        "ssp": ("ссп", "підрозділ"),
        "coverage": ("покрит", "повнот"),
        "dynamics": ("динамі", "період"),
        "attention": ("управлінськ", "сигнал", "ризик"),
        "mio": ("міо", "інтеграль"),
    }.items():
        if any(word in low for word in words):
            tags.append(key)
    return tuple(tags[:3]) or (low[:40],)


def _dedupe_paragraphs(paragraphs: Iterable[str]) -> list[str]:
    """Suppress only near-duplicate semantic paragraphs; do not force a quota."""
    result: list[str] = []
    seen: list[tuple[tuple[str, ...], set[str]]] = []
    for paragraph in paragraphs:
        p = paragraph.strip()
        if not p:
            continue
        key = _semantic_key(p)
        words = set(re.findall(r"[а-яіїєґa-z]{4,}", p.casefold()))
        duplicate = False
        for old_key, old_words in seen:
            if key != old_key or not words or not old_words:
                continue
            overlap = len(words & old_words) / max(1, min(len(words), len(old_words)))
            if overlap >= 0.82:
                duplicate = True
                break
        if not duplicate:
            result.append(p)
            seen.append((key, words))
    return result


def _vary_dimension_paragraphs(text: str) -> str:
    """Change information order across dimensions without changing any facts."""
    paragraphs = text.split("\n\n")
    out: list[str] = []
    for paragraph in paragraphs:
        p = paragraph.strip()
        if p.startswith("За відповідальними ССП"):
            dyn = p.find(" Динаміка всередині групи")
            att = p.find(" Поточна управлінська увага")
            if 0 < dyn < att:
                first = p[:dyn].strip()
                dynamics = p[dyn:att].strip()
                attention = p[att:].strip()
                first = first.replace(
                    "За відповідальними ССП розкид між ССП є змістовним:",
                    "Водночас між ССП зберігається суттєвий розрив у рівні виконання:",
                )
                attention = attention.replace(
                    "Поточна управлінська увага найбільше концентрується у",
                    "Найбільше актуальних сигналів управлінської уваги на рівні ССП припадає на",
                )
                p = f"{attention} {first} {dynamics}"
        out.append(p)
    return "\n\n".join(out)


def _language_cleanup(text: str) -> str:
    """Clean only user-visible language; never mutate provenance marker codes."""
    markers: list[str] = []
    marker_re = re.compile(r"⟦metric:[^⟧]+⟧", flags=re.I)
    def protect(match: re.Match) -> str:
        markers.append(match.group(0))
        return f"@@METRICMARKER{len(markers)-1}@@"
    out = marker_re.sub(protect, text)
    replacements = {
        "середньому рівнем": "середнім рівнем",
        "Поточний стан потребує структурованої інтерпретації.": "",
        "У поточному зріз відсутнє": "У поточному зрізі відсутнє",
        "у поточному зріз відсутнє": "у поточному зрізі відсутнє",
        "дані локалізують джерело результату": "дані локалізують ділянку, що потребує детальнішої перевірки",
        "всередині фокусного компонента": "всередині обраної стратегічної цілі",
        "Розкид між стратегічних цілей": "Розкид між стратегічними цілями",
        "розкид між стратегічних цілей": "розкид між стратегічними цілями",
        "execution alone": "лише рівень виконання",
        "latest execution": "рівень виконання в останньому обраному періоді",
        "latest snapshot": "актуальний зріз",
        "точному останньому snapshot": "точному останньому обраному періоді",
        "Drill-down": "Деталізація",
        "drill-down": "деталізація",
        "quarter-aware": "з урахуванням квартальної методології",
        "coverage не оцінюється": "покриття моніторингом не оцінюється",
        "execution змінився": "рівень виконання змінився",
        "у поточному зріз ": "у поточному зрізі ",
        "через високий або критичний ризик та неповнота": "через високий або критичний ризик і неповноту",
    }
    for old, new in replacements.items():
        out = out.replace(old, new)
    out = re.sub(r"\bexecution\b", "рівень виконання", out, flags=re.I)
    out = re.sub(r"\bcoverage\b", "покриття моніторингом", out, flags=re.I)
    out = re.sub(r"\bsnapshot\b", "зріз", out, flags=re.I)
    out = out.replace("поточний рівень на", "поточне покриття на")
    out = out.replace("в.п..", "в.п.")
    for idx, marker in enumerate(markers):
        out = out.replace(f"@@METRICMARKER{idx}@@", marker)
    return clean_text(out)



def _visible_cleanup(text: str) -> str:
    """Final language-only cleanup after provenance markers have been stripped."""
    out = text.replace("в.п..", "в.п.")
    out = out.replace("У поточному зріз відсутнє", "У поточному зрізі відсутнє")
    out = out.replace("у поточному зріз відсутнє", "у поточному зрізі відсутнє")
    out = out.replace("вище за середній за вибіркою", "вище за середній рівень за вибіркою")
    out = out.replace("нижче за середній за вибіркою", "нижче за середній рівень за вибіркою")
    out = re.sub(r"вище за середній(?=[.,;:])", "вище за середній рівень", out)
    out = re.sub(r"нижче за середній(?=[.,;:])", "нижче за середній рівень", out)
    out = out.replace("залишаються 1 захід", "залишається 1 захід")
    out = out.replace("відстає від фізичний результат", "відстає від фізичного результату")
    def _submission_case(match: re.Match) -> str:
        n = int(match.group(1))
        singular = n % 10 == 1 and n % 100 != 11
        return f"подання за {n} {'заходом' if singular else 'заходами'}"
    out = re.sub(r"подання за (\d+) зах(?:ід|оди|одів)", _submission_case, out)
    out = re.sub(r"[ \t]+([,.;:])", r"\1", out)
    return clean_text(out)


def detect_signals(ctx: AnalyticsContext) -> list[Signal]:
    """Public current-contract signal API; retired signal families are not constructed."""
    return _signals(ctx)


def derive_findings(ctx: AnalyticsContext, signals: list[Signal] | None = None):
    """Public current-contract findings API over the preserved production engine."""
    return _findings(ctx, signals if signals is not None else _signals(ctx))


def _final_current_block(
    ctx: AnalyticsContext,
    findings: list[AnalyticalFinding],
    opening: str,
    complexity: str,
    prior_blocks: list[AnalyticalBlock],
) -> AnalyticalBlock:
    """Adapt final synthesis at the analytical renderer layer, not in text cleanup.

    The preserved production renderer remains the source for mature synthesis,
    while current-only findings replace only legacy branches whose factual
    semantics no longer exist in Analytics.
    """
    block = base._render_block(ctx, "final_assessment", findings, opening, complexity, prior_blocks)
    sentences = list(block.sentences)
    used = list(block.findings)

    # The production final synthesis owns legacy SSP/goal missing-data sentences.
    # For departments, always intercept the legacy sentence because its direct
    # SSP wrapper can duplicate an already-prefixed label (for example
    # ``ССП «ССП 1»``). Re-render the department branch from the current finding
    # so unique and tied/distributed cases use the same factual semantics as the
    # detailed coverage block. Goal missing keeps the narrower legacy interception
    # because it has no analogous SSP-prefix duplication.
    for kind, prefix in (
        ("department", "Основний осередок неповноти даних у розрізі ССП"),
        ("goal", "Основний осередок неповноти даних у розрізі стратегічних цілей"),
    ):
        missing = next((
            item for item in findings
            if item.code.startswith(f"{kind}_missing_") and item.facts.get("total")
        ), None)
        if missing is None:
            continue
        family = missing.code.rsplit("_", 1)[-1]
        top_is_unique = bool(missing.facts.get("top_is_unique"))
        if kind == "department":
            sentences = [sentence for sentence in sentences if not sentence.startswith(prefix)]
            if family == "distributed" or not top_is_unique:
                used = [code for code in used if code != missing.code]
            else:
                top_label = _dimension_label("department", str(missing.facts.get("top_label") or ""))
                top_count = missing.facts.get("top_count")
                total = missing.facts.get("total")
                if top_label and top_count is not None and total is not None:
                    sentences.append(
                        f"Основний осередок неповноти даних у розрізі ССП — {top_label}: "
                        f"тут зосереджено {annotate_numeric(str(int(top_count)), top_count)} із "
                        f"{annotate_numeric(str(int(total)), total)} відсутніх подань."
                    )
                if missing.code not in used:
                    used.append(missing.code)
        elif family == "distributed" or not top_is_unique:
            sentences = [sentence for sentence in sentences if not sentence.startswith(prefix)]
            used = [code for code in used if code != missing.code]

    # Cross-sectional final synthesis must respect the same extrema semantics as
    # the detailed distribution block. A zero gap is equality, not differentiation.
    goal_dist = next((item for item in findings if item.code == "goal_distribution"), None)
    if goal_dist is not None and bool(goal_dist.facts.get("all_equal")):
        sentences = [
            sentence for sentence in sentences
            if not sentence.startswith("Внутрішня картина не зводиться до середнього: стратегічні цілі мають різні результати")
        ]
        if int(goal_dist.facts.get("count") or 0) > 1:
            sentences.append(
                f"На рівні стратегічних цілей результати однакові: розрив між максимумом і мінімумом відсутній, "
                f"а рівень виконання становить {base._pct(goal_dist.facts.get('best_value'))}."
            )
        if goal_dist.code not in used:
            used.append(goal_dist.code)

    # Always intercept the production SSP-impact final sentence.  The base
    # composer wraps the selected label directly as ``ССП «{label}»`` and can
    # therefore leak ``ССП «ССП 1»`` for already-prefixed production labels.
    # Current factual extrema metadata decides whether the maximum is unique or
    # tied; both branches are rendered here through the shared department-label
    # normalizer.
    dep_impact = next((item for item in findings if item.code == "ssp_portfolio_impact"), None)
    if dep_impact is not None:
        sentences = [
            sentence for sentence in sentences
            if not sentence.startswith("У розрізі відповідальних підрозділів найбільш вагомою негативною складовою")
        ]
        labels = list(dep_impact.facts.get("top_underperformance_departments") or [])
        contribution = dep_impact.facts.get("top_underperformance_contribution")
        if bool(dep_impact.facts.get("top_underperformance_is_unique")):
            if labels and contribution is not None:
                sentences.append(
                    f"У розрізі відповідальних підрозділів найбільш вагомою негативною складовою є "
                    f"{_dimension_label('department', labels[0])}: її внесок у загальне недовиконання становить "
                    f"{base._pct(contribution)}."
                )
        elif len(labels) > 1 and contribution is not None:
            sentences.append(
                f"У розрізі відповідальних підрозділів однаковий максимальний внесок у недовиконання мають "
                f"{_group_text(labels, 'department')} — по {base._pct(contribution)}; "
                "єдиного найбільш вагомого негативного ССП немає."
            )
        if dep_impact.code not in used:
            used.append(dep_impact.code)

    # The base renderer's management-priority sentence predates current attention
    # semantics. Replace that renderer branch with a sentence built directly from
    # the current ranking finding instead of hiding terminology in language cleanup.
    priorities = next((item for item in findings if item.code == "management_priorities"), None)
    if priorities is not None and priorities.facts.get("priorities"):
        sentences = [
            sentence for sentence in sentences
            if not sentence.startswith("З погляду управлінської уваги першочерговими залишаються")
        ]
        labels: list[str] = []
        for priority in list(priorities.facts.get("priorities") or [])[:3]:
            label = str(priority.get("label") or "").strip()
            if not label:
                continue
            if priority.get("kind") == "department":
                labels.append(_dimension_label("department", label))
            else:
                labels.append(_dimension_label("goal", label))
        if labels:
            sentences.append(
                "До пріоритетної групи управлінської уваги входять "
                + base.join_uk(labels)
                + "; їх визначено за актуальними сигналами управлінської уваги, "
                  "відсутніми поданнями та відхиленнями виконання поточного зрізу."
            )
        if priorities.code not in used:
            used.append(priorities.code)

    trajectory = next((
        item for item in findings
        if item.topic == "dynamics" and item.code.startswith("trajectory_")
    ), None)
    if trajectory is not None and trajectory.code == "trajectory_reversal_negative":
        sentences = [
            sentence.replace(
                "змішаною часовою траєкторією",
                "розворотом до зниження в останньому оціненому періоді",
            )
            for sentence in sentences
        ]

    return replace(
        block,
        findings=tuple(dict.fromkeys(used)),
        sentences=tuple(sentences),
        facts_used=frozenset(set(block.facts_used) | set(used)),
    )


def compose_note(ctx: AnalyticsContext, debug_mode: bool = False) -> GeneratedNote:
    """Compose with the production renderer and a narrow current-contract overlay."""
    signals = _signals(ctx)
    questions, findings = _findings(ctx, signals)
    scenarios = _scenarios(signals, findings)
    plan = build_text_plan(ctx, signals, scenarios, findings)
    selected_blocks = tuple(plan.blocks)
    if "management_attention" in selected_blocks:
        # Current-quarter attention is inserted before the provenance-safe current
        # management-priorities renderer. The legacy base management block is not used.
        insert_at = selected_blocks.index("management_attention")
    else:
        insert_at = max(1, len(selected_blocks) - 1)
    state = GenerationState()
    debug = GenerationDebug(
        detected_signals=[s.code for s in signals],
        analytical_questions=[q.code for q in questions],
        analytical_findings=[f.code for f in findings],
        activated_scenarios=[s.code for s in scenarios],
        selected_scenarios=list(plan.scenario_mix),
        context_complexity=plan.complexity,
        target_paragraph_count=None,
        selected_blocks=list(selected_blocks),
        block_depths={bp.code: bp.depth for bp in plan.block_plans if bp.code in selected_blocks},
        planned_findings={bp.code: list(bp.finding_codes) for bp in plan.block_plans if bp.code in selected_blocks},
    )
    dispositions = resolve_findings(
        ctx, findings, planned_blocks=frozenset(plan.blocks), complexity=plan.complexity
    )
    debug.finding_dispositions = {code: item.disposition for code, item in dispositions.items()}
    debug.finding_disposition_reasons = {code: item.reason for code, item in dispositions.items() if item.reason}
    debug.supporting_findings = sorted(code for code, item in dispositions.items() if item.disposition == SUPPORTING_ONLY)
    debug.internal_findings = sorted(code for code, item in dispositions.items() if item.disposition == INTERNAL_ONLY)
    # Supporting/internal findings are retained in debug but never handed to a
    # direct narrative consumer. This prevents legacy comparative branches from
    # verbalising facts that the runtime contract explicitly downgraded.
    renderable_findings = [
        finding for finding in findings if dispositions[finding.code].disposition == RENDERED
    ]
    opening = base._choose_opening(ctx, plan.opening, state, debug)
    blocks: list[AnalyticalBlock] = []
    for index, code in enumerate(selected_blocks):
        if index == insert_at:
            attention = _attention_block(ctx)
            if attention.text:
                blocks.append(attention)
        if code == "overall_state":
            block = _overall_current_block(ctx, renderable_findings)
        elif code == "management_attention":
            block = _management_priorities_block(ctx, renderable_findings)
        elif code == "dynamics":
            block = _dynamics_current_block(ctx, renderable_findings, opening, plan.complexity, blocks)
        elif code in {"goals", "tasks", "departments"}:
            block = _distribution_current_block(ctx, renderable_findings, code, opening, plan.complexity, blocks)
        elif code == "coverage":
            block = _coverage_current_block(ctx, renderable_findings, opening, plan.complexity, blocks)
        elif code == "statuses":
            block = _statuses_current_block(ctx, renderable_findings)
        elif code == "products":
            block = _products_current_block(ctx, renderable_findings)
        elif code == "mio_assessment":
            block = _mio_current_block(ctx, renderable_findings)
        elif code == "final_assessment":
            block = _final_current_block(ctx, renderable_findings, opening, plan.complexity, blocks)
        else:
            block = base._render_block(ctx, code, renderable_findings, opening, plan.complexity, blocks)
        if code == "overall_state" and block.sentences:
            block = AnalyticalBlock(
                block.code, block.topic, block.importance, block.signals, block.findings,
                (opening,) + block.sentences, block.facts_used,
            )
        if not block.text:
            continue
        if index > 1 and code not in {"final_assessment", "management_attention"} and block.sentences:
            first = block.sentences[0]
            transitioned = base._transition(ctx, code, first, state, debug)
            block = AnalyticalBlock(
                block.code, block.topic, block.importance, block.signals, block.findings,
                (transitioned,) + block.sentences[1:], block.facts_used,
            )
        blocks.append(block)
        debug.sentences_per_block[code] = len(block.sentences)
    if not any(block.code == "current_management_attention" for block in blocks):
        attention = _attention_block(ctx)
        if attention.text:
            blocks.insert(max(1, len(blocks) - 1), attention)

    annotated_text = clean_text("\n\n".join(_dedupe_paragraphs(block.text for block in blocks if block.text)))
    annotated_text = _vary_dimension_paragraphs(annotated_text)
    annotated_text = _language_cleanup(annotated_text)
    text = _visible_cleanup(strip_numeric_markers(annotated_text))

    used_findings = {code for block in blocks for code in block.findings}
    debug.block_findings = {block.code: list(block.findings) for block in blocks}
    important_rendered = {
        f.code for f in findings
        if f.importance >= 60 and dispositions[f.code].disposition == RENDERED
    }
    debug.important_findings_used = sorted(important_rendered & used_findings)
    debug.important_findings_skipped = sorted(important_rendered - used_findings)
    debug.facts_used = sorted({fact for block in blocks for fact in block.facts_used})
    debug.word_count = len(re.findall(r"\b[\w’'-]+\b", text, flags=re.UNICODE))
    debug.quality_metrics = assess_quality(
        text, plan.complexity, findings, used_findings, debug.selected_phrase_ids, debug.facts_used,
        expected_important_findings=important_rendered,
    )
    warnings = validate_text(text, ctx, signals, findings, annotated_text=annotated_text)
    warnings.extend(
        f"compatibility: unconsumed important finding: {code}"
        for code in debug.important_findings_skipped
    )
    debug.numeric_provenance = trace_numeric_provenance(annotated_text, ctx)
    debug.validation_warnings = warnings
    hard = [w for w in warnings if not w.startswith("quality:")]
    if hard:
        error = ValueError("Analytics text validation failed: " + "; ".join(hard))
        setattr(error, "validation_warnings", tuple(warnings))
        raise error
    return GeneratedNote(text=text, debug=debug)
