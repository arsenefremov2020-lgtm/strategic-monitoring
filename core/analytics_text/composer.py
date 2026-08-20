from __future__ import annotations

import re
from typing import Any, Iterable

from .findings import derive_findings
from .language import fmt_delta, fmt_number, fmt_pct, is_number, join_uk
from .models import (
    AnalyticsContext, AnalyticalBlock, AnalyticalFinding, GeneratedNote, GenerationDebug,
    GenerationState, PhraseVariant, Signal,
)
from .morphology import count_case_uk, count_uk
from .planner import build_text_plan
from .scenarios import activate_scenarios
from .selector import choose_variant, deterministic_index
from .signals import detect_signals
from .templates import BLOCK_STRUCTURES, phrase_pool
from .validation import assess_quality, clean_text, validate_text


def _finding_map(findings: Iterable[AnalyticalFinding]) -> dict[str, AnalyticalFinding]:
    return {item.code: item for item in findings}


def _topic(findings: Iterable[AnalyticalFinding], topic: str) -> list[AnalyticalFinding]:
    return sorted([item for item in findings if item.topic == topic], key=lambda x: (-x.importance, x.code))


def _first(findings: Iterable[AnalyticalFinding], *codes: str) -> AnalyticalFinding | None:
    mapping = _finding_map(findings)
    for code in codes:
        if code in mapping:
            return mapping[code]
    return None


def _prefix_finding(findings: Iterable[AnalyticalFinding], prefix: str) -> AnalyticalFinding | None:
    return next((item for item in findings if item.code.startswith(prefix)), None)


def _n(value: Any) -> int:
    try:
        if value is None:
            return 0
        import pandas as _pd
        if _pd.isna(value):
            return 0
    except (TypeError, ValueError):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return 0


def _pct(value: Any) -> str:
    return fmt_pct(value) if is_number(value) else "н/д"


def _delta_words(value: Any) -> str:
    if not is_number(value):
        return "н/д"
    val = float(value)
    return f"{fmt_number(abs(val))} в.п."


def _change_phrase(value: Any) -> str:
    if not is_number(value):
        return "не визначена"
    val = float(value)
    if val > 0:
        return f"зросло на {_delta_words(val)}"
    if val < 0:
        return f"знизилося на {_delta_words(val)}"
    return "не змінилося"


def _count_share(count: int, total: int, entity: str = "record") -> str:
    if total <= 0:
        return count_uk(count, entity)
    share = count / total * 100
    return f"{count_uk(count, entity)}, або {fmt_pct(share)} від відповідної сукупності"


def _choose_opening(ctx: AnalyticsContext, tag: str, state: GenerationState, debug: GenerationDebug) -> str:
    options = {
        "positive": ("Загальна динаміка виконання є позитивною.", "Зведений результат покращується порівняно з попередніми оціненими періодами."),
        "negative": ("Загальна динаміка виконання є негативною.", "Зведений результат погіршується порівняно з попередніми оціненими періодами."),
        "mixed": ("Зведений результат приховує різноспрямовані внутрішні зміни: покращення в одних частинах портфеля відбувається одночасно з погіршенням в інших.", "Загальна картина є неоднорідною: позитивні й негативні зміни відбуваються одночасно в різних частинах портфеля."),
        "cautious": ("Неповнота моніторингових даних обмежує силу загального висновку щодо виконання.", "Поточна оцінка виконання має суттєве обмеження за повнотою моніторингових даних."),
        "neutral": ("Загальний стан виконання не демонструє одного домінуючого напряму зміни.", "Зведений результат залишається відносно стабільним."),
    }
    pool = options.get(tag, options["neutral"])
    return pool[deterministic_index(len(pool), f"{ctx.signature}:opening:{tag}")]

def _transition(ctx: AnalyticsContext, topic: str, sentence: str, state: GenerationState, debug: GenerationDebug) -> str:
    if not sentence:
        return sentence
    low = sentence[0].lower() + sentence[1:]
    if topic == "yoy":
        if low.startswith("рівень виконання"):
            return "Порівняння з попереднім роком доповнює часову картину: " + low
        return "Порівняння з попереднім роком доповнює часову картину. " + sentence
    replacements = {
        "goals": ("у розрізі стратегічних цілей ", "Детальніше за стратегічними цілями "),
        "tasks": ("у розрізі завдань ", "На рівні завдань "),
        "departments": ("у розрізі ссп ", "За відповідальними ССП "),
        "statuses": ("структура статусів ", "Статусна структура "),
        "coverage": ("середнє покриття ", "Щодо повноти даних, середнє покриття "),
    }
    if topic in replacements:
        prefix, lead = replacements[topic]
        if low.lower().startswith(prefix):
            return lead + low[len(prefix):]
    pool = phrase_pool("transition", topic)
    if pool:
        variant = choose_variant(pool, key=f"{ctx.signature}:transition:{topic}", state=state)
        debug.selected_phrase_ids.append(variant.id)
        return variant.template.format(sentence=low)
    lead_options = {
        "dynamics": ("З погляду динаміки", "У часовій динаміці", "За послідовністю періодів"),
        "products": ("За типами продукту", "У структурі продуктів"),
        "problems": ("Щодо концентрації відхилень", "Проблемні позиції концентруються"),
    }.get(topic, ("На цьому тлі", "Поряд із цим"))
    lead = lead_options[deterministic_index(len(lead_options), f"{ctx.signature}:transition:{topic}")]
    return f"{lead}: {low}"


def _period_text(ctx: AnalyticsContext) -> str:
    years = [str(x) for x in (ctx.filters.get("years", []) or [])]
    quarters = [str(x) for x in (ctx.filters.get("quarters", []) or [])]
    if years and quarters:
        if len(years) == 1:
            return f"{years[0]} рік, {join_uk(quarters)} квартали" if len(quarters) > 1 else f"{years[0]} рік, {quarters[0]} квартал"
        return f"{join_uk(years)} роки, {join_uk(quarters)} квартали"
    if years:
        return f"{join_uk(years)}"
    return "обраний період"


def _scope_block(ctx: AnalyticsContext, findings: list[AnalyticalFinding], opening: str, complexity: str) -> AnalyticalBlock:
    scope = _first(findings, "scope_profile")
    f = scope.facts if scope else {}
    measures = _n(f.get("measures", ctx.sample_size)); rows = _n(f.get("rows", ctx.row_count))
    goals = _n(f.get("goals", ctx.metric("goals"))); tasks = _n(f.get("tasks", ctx.metric("tasks")))
    sentences = [opening]
    if complexity in {"wide", "very_wide"}:
        context_bits=[]
        if measures: context_bits.append(count_uk(measures, "measure"))
        if goals: context_bits.append(count_uk(goals, "goal"))
        if tasks: context_bits.append(count_uk(tasks, "task"))
        if context_bits:
            sentences.append(f"Аналіз охоплює {_period_text(ctx)} та {join_uk(context_bits)}.")
    return AnalyticalBlock("scope", "scope", 55, findings=("scope_profile",), sentences=tuple(sentences), facts_used=frozenset({"scope_profile"}))

def _overall_block(ctx: AnalyticsContext, findings: list[AnalyticalFinding], complexity: str) -> AnalyticalBlock:
    item = _first(findings, "overall_state")
    f = item.facts if item else {}
    avg = f.get("execution_average"); latest = f.get("execution_latest")
    cov = f.get("coverage_average"); cov_latest = f.get("coverage_latest")
    problems = _n(f.get("problem_count")); missing = _n(f.get("missing_count"))
    divergence = _first(findings, "execution_goal_divergence", "execution_goal_alignment")
    used = {"overall_state"} if item else set()
    parts: dict[str, str] = {}

    if is_number(avg):
        parts["execution"] = f"Загальний рівень виконання за обраною вибіркою становить {_pct(avg)}."
    else:
        parts["execution"] = "За обраною вибіркою зведений рівень виконання не розрахований через відсутність достатнього масиву оцінених результатів."

    if is_number(latest):
        if is_number(avg) and abs(float(latest) - float(avg)) >= 0.05:
            parts["latest"] = f"В останньому оціненому періоді результат становить {_pct(latest)} проти {_pct(avg)} в середньому за вибіркою; різниця становить {_delta_words(float(latest)-float(avg))}."
        else:
            parts["latest"] = f"В останньому оціненому періоді значення становить {_pct(latest)} і практично збігається із середнім рівнем за вибіркою."

    if is_number(cov):
        text = f"Середнє покриття моніторингом становить {_pct(cov)}"
        if is_number(cov_latest) and abs(float(cov_latest) - float(cov)) >= 0.05:
            text += f", тоді як в останньому оціненому періоді — {_pct(cov_latest)}"
        text += "."
        parts["coverage"] = text

    if divergence:
        used.add(divergence.code)
        d = divergence.facts
        if divergence.code == "execution_goal_divergence":
            gap = float(d.get("gap") or 0)
            relation = "вище" if gap > 0 else "нижче"
            parts["divergence"] = (
                f"Окремо простежується розбіжність між виконанням за заходами та результатом за стратегічними цілями: "
                f"{_pct(d.get('measure_execution'))} проти {_pct(d.get('goal_execution'))}; показник за заходами на {_delta_words(gap)} {relation}. "
                "Така розбіжність означає, що операційне виконання заходів не повністю збігається з результатом на рівні стратегічних цілей."
            )
        elif complexity in {"wide", "very_wide"}:
            parts["divergence"] = (
                f"Виконання за заходами ({_pct(d.get('measure_execution'))}) та результат за стратегічними цілями "
                f"({_pct(d.get('goal_execution'))}) залишаються близькими, тому між цими рівнями агрегації не виявлено суттєвого розходження."
            )

    if problems or missing:
        issue_parts = []
        if problems:
            issue_parts.append(count_uk(problems, "record") + " із проблемним статусом або ризиковою ознакою")
        if missing:
            issue_parts.append(f"відсутні подання за {count_uk(missing, 'record')}")
        issue_text = "У структурі масиву окремої уваги потребують " + join_uk(issue_parts) + "."

        # Close the analytical loop already in the opening paragraph: if the
        # engine knows where problems/missing data concentrate, state it rather
        # than telling the reader that the distribution should be inspected.
        candidates = []
        if problems:
            candidates.extend(x for x in findings if x.code.startswith(("goal_problems_", "department_problems_")))
        if missing:
            candidates.extend(x for x in findings if x.code.startswith(("goal_missing_", "department_missing_")))
        candidates = [x for x in candidates if _n(x.facts.get("total")) > 0 and x.facts.get("top_label")]
        if candidates:
            strongest = max(candidates, key=lambda x: (float(x.facts.get("top_share") or 0), x.importance))
            sf = strongest.facts
            used.add(strongest.code)
            topic_name = "проблемних позицій" if "problems" in strongest.code else "відсутніх подань"
            issue_text += (
                f" Найбільший осередок {topic_name} — {sf.get('top_label')}: "
                f"{_n(sf.get('top_count'))} із {_n(sf.get('total'))}, або {_pct(float(sf.get('top_share') or 0) * 100)}."
            )
        parts["issues"] = issue_text
    elif ctx.row_count:
        if ctx.sample_size <= 1:
            parts["issues"] = "У межах єдиного заходу не зафіксовано відсутнього обов’язкового подання або проблемної позиції; тому висновок обмежується фактичним рівнем виконання і повнотою даних цього об’єкта без узагальнень про портфель."
        else:
            parts["issues"] = "У поточному масиві не зафіксовано відсутніх обов’язкових подань або проблемних позицій за відповідними описовими ознаками; основну аналітичну різницю формують динаміка та внутрішній розподіл виконання."

    structures = BLOCK_STRUCTURES["general"]
    order = structures[deterministic_index(len(structures), f"{ctx.signature}:general-structure")]
    rendered = [parts[key] for key in order if key in parts]
    return AnalyticalBlock("overall_state", "general", 90, findings=tuple(used), sentences=tuple(rendered), facts_used=frozenset(used))

def _trajectory_sentence_path(f: dict[str, Any]) -> str:
    periods = f.get("periods", []) or []; values = f.get("values", []) or []
    pairs = [f"{p} — {_pct(v)}" for p, v in zip(periods, values) if is_number(v)]
    return "Послідовність оцінених періодів має такий вигляд: " + "; ".join(pairs) + "." if pairs else ""


def _dynamics_block(ctx: AnalyticsContext, findings: list[AnalyticalFinding], complexity: str) -> AnalyticalBlock:
    traj = next((f for f in findings if f.topic == "dynamics" and f.code.startswith("trajectory_") and "values" in f.facts), None)
    goal_change = _prefix_finding(findings, "goal_change_")
    dep_change = _prefix_finding(findings, "department_change_")
    sentences: dict[str, str] = {}
    used: set[str] = set()
    if not traj:
        return AnalyticalBlock("dynamics", "dynamics", 45, sentences=("Для обраної вибірки недостатньо послідовних оцінених періодів, щоб сформувати висновок про траєкторію виконання.",), facts_used=frozenset())
    f = traj.facts; used.add(traj.code)
    if _n(f.get("period_count")) <= 1:
        period = f.get("last_period") or (f.get("periods") or ["останній доступний період"])[-1]
        value = f.get("last")
        cov = f.get("coverage_last")
        single_sentences = [f"Для часової динаміки доступний лише один оцінений період — {period} із рівнем виконання {_pct(value)}; одного спостереження недостатньо для висновку про зростання, спад або стабільний тренд."]
        if is_number(cov):
            single_sentences.append(f"Покриття моніторингом у цьому періоді становить {_pct(cov)}. Значення виконання {_pct(value)} характеризує лише цей часовий зріз і не свідчить про напрям зміни без другого оціненого періоду.")
        return AnalyticalBlock("dynamics", "dynamics", 50, findings=(traj.code,), sentences=tuple(single_sentences), facts_used=frozenset({traj.code}))
    path = _trajectory_sentence_path(f)
    if path: sentences["path"] = path
    first, last = f.get("first"), f.get("last")
    if is_number(first) and is_number(last) and len(f.get("values", [])) >= 2:
        delta = float(last) - float(first)
        if delta > 0:
            sentences["net"] = f"Від першого до останнього доступного періоду рівень виконання зріс із {_pct(first)} до {_pct(last)}, тобто на {_delta_words(delta)}."
        elif delta < 0:
            sentences["net"] = f"Від першого до останнього доступного періоду рівень виконання знизився з {_pct(first)} до {_pct(last)}, тобто на {_delta_words(delta)}."
        else:
            sentences["net"] = f"Перший і останній доступні періоди мають однаковий результат — {_pct(last)}, однак це не виключає внутрішніх коливань між ними."
    code = traj.code
    direction_text = {
        "trajectory_continuous_growth": "Траєкторія є послідовно висхідною: кожен наступний оцінений період має вищий результат за попередній.",
        "trajectory_continuous_decline": "Траєкторія є послідовно низхідною: кожен наступний оцінений період має нижчий результат за попередній.",
        "trajectory_recovery": "Після попереднього погіршення в останньому періоді відбувся розворот до зростання, тому поточна позитивна зміна є частиною відновлення, а не безперервного річного тренду.",
        "trajectory_reversal_negative": "Останній період змінив попередній позитивний напрям: після зростання зафіксовано зниження, що перериває висхідну траєкторію.",
        "trajectory_volatile": "Зведений результат змінювався різноспрямовано з помітним розмахом між періодами, тому річну картину коректніше характеризувати як нестійку, а не як однорідне зростання або падіння.",
        "trajectory_plateau": "Протягом доступних періодів зміни залишалися мінімальними, тобто результат фактично перебував на плато.",
        "trajectory_net_growth": "Загальний напрям за весь доступний горизонт є позитивним, хоча окремі проміжні періоди могли відхилятися від цього тренду.",
        "trajectory_net_decline": "Загальний напрям за весь доступний горизонт є негативним, навіть якщо окремі проміжні періоди демонстрували тимчасове покращення.",
        "trajectory_mixed_stable": "Зведений результат за початковим і кінцевим періодами майже не змінився, тому основне аналітичне значення мають внутрішні коливання між ними.",
    }.get(code)
    if direction_text: sentences["claim"] = direction_text
    aux = _first(findings, "trajectory_late_acceleration", "trajectory_growth_slowing", "trajectory_decline_accelerating")
    if aux:
        used.add(aux.code)
        if aux.code == "trajectory_late_acceleration":
            sentences["pace"] = f"Темп позитивної зміни наприкінці періоду прискорився: попередній приріст становив {_delta_words(aux.facts.get('previous_delta'))}, останній — {_delta_words(aux.facts.get('latest_delta'))}."
        elif aux.code == "trajectory_growth_slowing":
            sentences["pace"] = f"Позитивний напрям зберігся, але темп приросту наприкінці періоду сповільнився з {_delta_words(aux.facts.get('previous_delta'))} до {_delta_words(aux.facts.get('latest_delta'))}."
        elif aux.code == "trajectory_decline_accelerating":
            sentences["pace"] = f"Негативна динаміка наприкінці періоду посилилася: величина зниження змінилася з {_delta_words(aux.facts.get('previous_delta'))} до {_delta_words(aux.facts.get('latest_delta'))}."
    if "max_increase" in f:
        up = float(f["max_increase"]); down = float(f["max_decrease"])
        if up > 0 or down < 0:
            parts = []
            if up > 0: parts.append(f"найбільший приріст припав на {f.get('max_increase_period')} і становив {_delta_words(up)}")
            if down < 0: parts.append(f"найбільше зниження припало на {f.get('max_decrease_period')} і становило {_delta_words(down)}")
            sentences["extremes"] = "За переходами між оціненими періодами " + "; ".join(parts) + "."
    cov_delta = f.get("coverage_cumulative_delta")
    if is_number(cov_delta):
        if float(cov_delta) > 0:
            sentences["coverage"] = f"За той самий горизонт покриття моніторингом збільшилося на {_delta_words(cov_delta)}, що розширює інформаційну основу порівняння першого й останнього періодів."
        elif float(cov_delta) < 0:
            sentences["coverage"] = f"За той самий горизонт покриття моніторингом зменшилося на {_delta_words(cov_delta)}. Отже, крайні значення виконання сформовані на масивах різної інформаційної повноти, що обмежує силу їх прямого зіставлення незалежно від напряму зміни виконання."
        else:
            sentences["coverage"] = "Покриття моніторингом між першим і останнім періодами практично не змінилося, тому зміна виконання не супроводжується суттєвим зсувом інформаційної бази."
    if goal_change:
        g = goal_change.facts; used.add(goal_change.code)
        total = _n(g.get("count_with_change")); improved = _n(g.get("improved")); declined = _n(g.get("declined"))
        if total:
            sentences["breadth"] = f"У розрізі стратегічних цілей зміна охоплює не лише зведений показник: із {count_uk(total, 'goal')} результат зріс за {count_case_uk(improved, 'goal', 'ins') if improved else 'жодною стратегічною ціллю'} та знизився за {count_case_uk(declined, 'goal', 'ins') if declined else 'жодною'}."
    if dep_change and complexity in {"wide", "very_wide"}:
        d = dep_change.facts; used.add(dep_change.code)
        total = _n(d.get("count_with_change")); improved = _n(d.get("improved")); declined = _n(d.get("declined"))
        if total:
            sentences["ssp_breadth"] = f"За ССП картина також не зводиться до одного середнього: серед {count_uk(total, 'department')} зростання мають {improved}, зниження — {declined}; найбільший приріст має {d.get('largest_improvement_label')} ({fmt_delta(d.get('largest_improvement'))}), найбільше погіршення — {d.get('largest_deterioration_label')} ({fmt_delta(d.get('largest_deterioration'))})."
    structures = BLOCK_STRUCTURES["dynamics"]
    order = structures[deterministic_index(len(structures), f"{ctx.signature}:dynamics-structure")]
    rendered = [sentences[k] for k in order if k in sentences]
    return AnalyticalBlock("dynamics", "dynamics", 92, findings=tuple(used), sentences=tuple(rendered), facts_used=frozenset(used))


def _yoy_block(ctx: AnalyticsContext, findings: list[AnalyticalFinding]) -> AnalyticalBlock:
    item = next((f for f in findings if f.topic == "yoy"), None)
    if not item:
        return AnalyticalBlock("year_over_year", "yoy", 40, sentences=())

    facts = item.facts
    comparisons = facts.get("comparisons", []) or []
    if not comparisons:
        comparisons = [{"comparison": facts.get("comparison"), "metrics": facts.get("metrics", {}) or {}}]
    sentences: list[str] = []

    def render_pair(comp: dict[str, Any], *, ordinal: int, total_pairs: int) -> list[str]:
        pair = comp.get("comparison") or "доступний річний інтервал"
        metrics = comp.get("metrics", {}) or {}
        execution = metrics.get("Рівень виконання СП", {})
        coverage = metrics.get("Покриття моніторингом", {})
        problems = metrics.get("Проблемні / ризикові", {})
        missing = metrics.get("Без поданих погоджених даних", {})
        measures = metrics.get("Унікальні заходи", {})
        parts: list[str] = []

        if is_number(execution.get("previous")) and is_number(execution.get("current")):
            change = execution.get("change")
            delta_text = fmt_delta(change) if is_number(change) else "н/д"
            parts.append(
                f"У порівнянні {pair} рівень виконання змінився з {_pct(execution['previous'])} до {_pct(execution['current'])}; "
                f"річна різниця становить {delta_text}."
            )

        companion: list[str] = []
        if is_number(coverage.get("previous")) and is_number(coverage.get("current")):
            companion.append(
                f"покриття моніторингом змінилося з {_pct(coverage['previous'])} до {_pct(coverage['current'])} "
                f"({_change_phrase(coverage.get('change'))})"
            )
        if is_number(problems.get("change")):
            delta = float(problems["change"])
            companion.append(
                f"кількість проблемних/ризикових позицій {'зросла' if delta > 0 else 'скоротилася' if delta < 0 else 'не змінилася'}"
                + (f" на {fmt_number(abs(delta))}" if delta else "")
            )
        if is_number(missing.get("change")):
            delta = float(missing["change"])
            companion.append(
                f"кількість відсутніх подань {'зросла' if delta > 0 else 'скоротилася' if delta < 0 else 'не змінилася'}"
                + (f" на {fmt_number(abs(delta))}" if delta else "")
            )
        if companion:
            lead = "Супровідні показники за цей самий інтервал показують, що " if total_pairs == 1 else "За цей самий річний інтервал "
            parts.append(lead + "; ".join(companion) + ".")

        if is_number(measures.get("previous")) and is_number(measures.get("current")) and float(measures["previous"]) != float(measures["current"]):
            parts.append(
                f"Склад порівнюваного портфеля у {pair} також відрізняється: кількість унікальних заходів змінилася "
                f"з {fmt_number(measures['previous'])} до {fmt_number(measures['current'])}. Отже, річна різниця відображає зміну між "
                "фактично сформованими у відповідні роки масивами, а не між двома повністю ідентичними наборами об’єктів."
            )
        return parts

    for ordinal, comp in enumerate(comparisons, start=1):
        sentences.extend(render_pair(comp, ordinal=ordinal, total_pairs=len(comparisons)))

    if len(comparisons) > 1:
        execution_changes = [float(x) for x in (facts.get("execution_changes", []) or []) if is_number(x)]
        coverage_changes = [float(x) for x in (facts.get("coverage_changes", []) or []) if is_number(x)]
        if item.code == "yoy_multi_continuous_improvement":
            sentences.append(
                f"Усі {len(execution_changes)} доступні міжрічні переходи за рівнем виконання мають позитивний напрям. "
                "Отже, покращення не обмежується одним річним порівнянням, а простежується послідовно в доступному річному ряді."
            )
        elif item.code == "yoy_multi_continuous_deterioration":
            sentences.append(
                f"Усі {len(execution_changes)} доступні міжрічні переходи за рівнем виконання мають негативний напрям. "
                "Погіршення, таким чином, має послідовний характер у доступному річному ряді, а не є одиничним відхиленням останнього року."
            )
        elif item.code == "yoy_multi_reversal":
            positives = sum(x > 0 for x in execution_changes)
            negatives = sum(x < 0 for x in execution_changes)
            sentences.append(
                f"Міжрічна траєкторія не є односпрямованою: серед доступних переходів {positives} показують зростання виконання, "
                f"а {negatives} — зниження. Це означає зміну напряму між окремими роками, яку неможливо коректно звести лише до останньої річної різниці."
            )
        elif item.code == "yoy_multi_mixed":
            sentences.append(
                "Міжрічні порівняння дають змішану картину: напрям виконання та супровідних показників не є узгодженим у всіх доступних переходах. "
                "Тому оцінка багаторічної зміни спирається на сукупність річних переходів, а не на один підсумковий знак зміни."
            )
        else:
            sentences.append(
                "Доступні річні порівняння не формують достатньо однорідної послідовності для висновку про стійкий багаторічний напрям; "
                "у довідці відображено фактичні зміни кожного доступного річного переходу окремо."
            )
        if coverage_changes and len(coverage_changes) == len(comparisons):
            up = sum(x > 0 for x in coverage_changes); down = sum(x < 0 for x in coverage_changes)
            if up == len(coverage_changes):
                sentences.append("Повнота моніторингових даних водночас покращувалася в кожному доступному міжрічному переході, що посилює інформаційну основу для порівняння результатів у часі.")
            elif down == len(coverage_changes):
                sentences.append("Повнота моніторингових даних знижувалася в кожному доступному міжрічному переході; це є окремим обмеженням для сили багаторічної інтерпретації, навіть якщо напрям виконання є однозначним.")
            elif up and down:
                sentences.append("Покриття моніторингом змінювалося різноспрямовано між роками, тому інформаційна повнота окремих річних порівнянь також є неоднаковою.")
    else:
        if item.code == "yoy_mixed_change":
            sentences.append("Річні зміни є різноспрямованими: покращення одного зведеного показника супроводжується погіршенням принаймні одного іншого виміру, тому підсумкова оцінка не зводиться до однозначного «краще/гірше».")
        elif item.code == "yoy_broad_improvement":
            sentences.append("Основні доступні річні показники змінюються у сприятливому напрямі без виявленого протилежного руху ключових супровідних метрик.")
        elif item.code == "yoy_broad_deterioration":
            sentences.append("Основні доступні річні показники переважно погіршилися, тому негативна зміна не обмежується одним зведеним показником.")

    return AnalyticalBlock(
        "year_over_year", "yoy", item.importance, findings=(item.code,),
        sentences=tuple(sentences), facts_used=frozenset({item.code}),
    )


def _coverage_block(ctx: AnalyticsContext, findings: list[AnalyticalFinding]) -> AnalyticalBlock:
    overall = _first(findings, "overall_state")
    f = overall.facts if overall else {}
    avg = f.get("coverage_average"); latest = f.get("coverage_latest"); missing = _n(f.get("missing_count"))
    goal_missing = next((x for x in findings if x.code.startswith("goal_missing_")), None)
    dep_missing = next((x for x in findings if x.code.startswith("department_missing_")), None)
    parts: dict[str, str] = {}; used: set[str] = {"overall_state"} if overall else set()

    if is_number(avg):
        parts["overall"] = f"Покриття моніторингом у межах вибірки становить {_pct(avg)}."
    if is_number(latest):
        parts["latest"] = f"В останньому оціненому періоді покриття становить {_pct(latest)}."
    if missing == 0:
        parts["missing"] = "Відсутніх обов’язкових подань у поточному масиві не зафіксовано, тому неповнота подань не формує окремого обмеження для цієї вибірки."
    else:
        parts["missing"] = f"У вибірці відсутні {count_uk(missing, 'submission')}; їх розподіл за ССП і стратегічними цілями показує, де саме зосереджена інформаційна неповнота."

    for item, key, label in ((dep_missing, "department", "ССП"), (goal_missing, "goal", "стратегічних цілей")):
        if not item or not item.facts.get("total", 0):
            continue
        used.add(item.code); x = item.facts
        top = x.get("top_label"); top_count = _n(x.get("top_count")); total = _n(x.get("total")); top3 = _n(x.get("top3_count"))
        display = f"ССП «{top}»" if key == "department" else str(top)
        if top:
            parts[key] = f"У розрізі {label} найбільша кількість відсутніх подань припадає на {display}: {top_count} із {total}, або {_pct(top_count/total*100)}; три найбільші компоненти разом охоплюють {top3} подань ({_pct(top3/total*100)})."
        if x.get("top_internal_rate") is not None:
            internal = float(x["top_internal_rate"]) * 100
            if is_number(x.get("top_portfolio_share")) and is_number(x.get("concentration_excess_pp")):
                portfolio_share = float(x["top_portfolio_share"]) * 100
                excess = float(x["concentration_excess_pp"])
                if abs(excess) >= 0.05:
                    relation = "перевищує" if excess > 0 else "нижча за"
                    parts[f"{key}_rate"] = (
                        f"У власному портфелі цього компонента без даних залишається {_pct(internal)} позицій. "
                        f"На нього припадає {_pct(float(x.get('top_share', 0))*100)} усіх відсутніх подань при частці {_pct(portfolio_share)} у відповідному портфелі; "
                        f"частка неповних подань {relation} портфельну вагу на {_delta_words(excess)}."
                    )
                else:
                    parts[f"{key}_rate"] = f"У власному портфелі цього компонента без даних залишається {_pct(internal)} позицій, а його частка серед усіх відсутніх подань практично відповідає частці у відповідному портфелі."
            else:
                parts[f"{key}_rate"] = f"У власному портфелі цього компонента без даних залишається {_pct(internal)} позицій; це внутрішній рівень неповноти для найбільшого абсолютного осередку відсутніх подань."

    if missing and not goal_missing and not dep_missing:
        parts["limitation"] = "Деталізована локалізація відсутніх подань за СЦ або ССП недоступна в поточному наборі агрегованих даних. Це фактичне обмеження доступної деталізації; відсутні дані при цьому не трактуються як нульове виконання."

    structures = BLOCK_STRUCTURES["coverage"]
    order = structures[deterministic_index(len(structures), f"{ctx.signature}:coverage-structure")]
    rendered = [parts[key] for key in order if key in parts]
    return AnalyticalBlock("coverage", "coverage", 88 if missing else 60, findings=tuple(used), sentences=tuple(rendered), facts_used=frozenset(used))

def _distribution_block(ctx: AnalyticsContext, findings: list[AnalyticalFinding], kind: str) -> AnalyticalBlock:
    block = {"goal": "goals", "task": "tasks", "department": "departments"}[kind]
    dist = _first(findings, f"{kind}_distribution")
    change = _prefix_finding(findings, f"{kind}_change_")
    problems = _prefix_finding(findings, f"{kind}_problems_")
    missing = _prefix_finding(findings, f"{kind}_missing_")
    portfolio = _first(findings, "ssp_portfolio_impact") if kind == "department" else None
    drill = _first(findings, "goal_drilldown") if kind == "task" else (_first(findings, "ssp_drilldown") if kind == "department" else None)
    used: set[str] = set(); sentences: dict[str, str] = {}
    entity_gen = {"goal": "стратегічних цілей", "task": "завдань", "department": "ССП"}[kind]
    entity_nom = {"goal": "стратегічні цілі", "task": "завдання", "department": "ССП"}[kind]
    entity_key = {"goal": "goal", "task": "task", "department": "department"}[kind]
    if dist:
        used.add(dist.code); f = dist.facts
        if _n(f.get("count")) > 1:
            sentences["spread"] = f"У розрізі {entity_gen} результати є диференційованими: найвищий рівень виконання має {f.get('best_label')} — {_pct(f.get('best_value'))}, а найнижчий — {f.get('worst_label')} — {_pct(f.get('worst_value'))}; розрив становить {_delta_words(f.get('gap'))}."
            sentences["relative"] = f"Порівняно із загальним рівнем виконання {_pct(f.get('reference'))}, вище нього перебувають {count_uk(_n(f.get('above_reference')), entity_key)}, нижче — {count_uk(_n(f.get('below_reference')), entity_key)}. Отже, відхилення охоплюють не лише окремі крайні позиції, а помітну частину {entity_gen}."
            top = f.get("top", []); bottom = f.get("bottom", [])
            if top and bottom:
                top_text = ", ".join(f"{l} ({_pct(v)})" for l, v in top[:3])
                bottom_text = ", ".join(f"{l} ({_pct(v)})" for l, v in bottom[:3])
                sentences["ranking"] = f"Серед трьох найвищих результатів — {top_text}; нижню частину розподілу формують {bottom_text}."
        else:
            pass
    if change:
        used.add(change.code); f = change.facts; total = _n(f.get("count_with_change")); imp = _n(f.get("improved")); dec = _n(f.get("declined")); stable = _n(f.get("stable"))
        if total:
            sentences["movement"] = f"Динаміка доступна для {count_uk(total, entity_key)}: покращення зафіксовано за {count_case_uk(imp, entity_key, 'ins')}, погіршення — за {count_case_uk(dec, entity_key, 'ins')}, мінімальні зміни — за {count_case_uk(stable, entity_key, 'ins')}. Найбільший приріст має {f.get('largest_improvement_label')} ({fmt_delta(f.get('largest_improvement'))}), а найбільше зниження — {f.get('largest_deterioration_label')} ({fmt_delta(f.get('largest_deterioration'))})."
            if "broad_positive" in change.code:
                sentences["breadth"] = f"Покращення має широкий характер у межах доступних порівнянь: позитивна динаміка охоплює більшу частину {entity_gen}, а не один локальний компонент."
            elif "broad_negative" in change.code:
                sentences["breadth"] = f"Погіршення має широкий характер у межах доступних порівнянь: негативна динаміка охоплює більшу частину {entity_gen}."
            elif "polarised" in change.code:
                sentences["breadth"] = f"Зміна є поляризованою: одночасно присутні компоненти зі зростанням і зі зниженням, тому зведений показник приховує різноспрямований внутрішній рух."
    if kind == "task" and problems and _n(problems.facts.get("total")):
        used.add(problems.code); f = problems.facts; total = _n(f.get("total")); top_count = _n(f.get("top_count")); top3_count = _n(f.get("top3_count"))
        sentences["problems"] = f"Проблемні позиції в цьому розрізі локалізуються нерівномірно: {f.get('top_label')} концентрує {top_count} із {total} ({_pct(top_count/total*100)}), а три найбільші компоненти — {top3_count} ({_pct(top3_count/total*100)})."
        if f.get("top_internal_rate") is not None:
            internal = float(f["top_internal_rate"]) * 100
            if is_number(f.get("top_portfolio_share")) and is_number(f.get("concentration_excess_pp")):
                portfolio_share = float(f["top_portfolio_share"]) * 100
                excess = float(f["concentration_excess_pp"])
                if abs(excess) >= 0.05:
                    relation = "перевищує" if excess > 0 else "нижча за"
                    sentences["problem_rate"] = f"У власному портфелі цього компонента проблемними є {_pct(internal)} позицій. Його частка серед усіх проблемних позицій ({_pct(float(f.get('top_share', 0))*100)}) {relation} частку у відповідному портфелі ({_pct(portfolio_share)}) на {_delta_words(excess)}."
                else:
                    sentences["problem_rate"] = f"У власному портфелі цього компонента проблемними є {_pct(internal)} позицій; його частка серед усіх проблемних позицій практично відповідає портфельній вазі."
            else:
                sentences["problem_rate"] = f"У власному портфелі цього компонента проблемними є {_pct(internal)} позицій; це внутрішня інтенсивність проблемності для найбільшого абсолютного осередку відхилень."
    if kind == "task" and missing and _n(missing.facts.get("total")):
        used.add(missing.code); f = missing.facts; total = _n(f.get("total")); top_count = _n(f.get("top_count"))
        sentences["missing"] = f"Неповнота даних на рівні завдань також має конкретну локалізацію: найбільше відсутніх подань має {f.get('top_label')} — {top_count} із {total}, або {_pct(top_count/total*100)}."
    if portfolio and kind == "department":
        used.add(portfolio.code); f = portfolio.facts
        largest = f.get("largest_department")
        top_under = f.get("top_underperformance_department")
        same_focus = largest and top_under and str(largest) == str(top_under)
        if largest and same_focus and is_number(f.get("top_underperformance_contribution")):
            sentences["weight"] = (
                f"Найбільший за масштабом портфель і водночас найбільший внесок у недовиконання має ССП «{largest}»: "
                f"частка портфеля {_pct(f.get('largest_weight'))}, рівень виконання {_pct(f.get('largest_execution'))}, "
                f"внесок у недовиконання {_pct(f.get('top_underperformance_contribution'))}."
            )
        elif largest:
            sentences["weight"] = f"Найбільший за масштабом портфель має ССП «{largest}» — {_pct(f.get('largest_weight'))} усіх заходів у загальному портфелі; його рівень виконання становить {_pct(f.get('largest_execution'))}."
        if top_under and is_number(f.get("top_underperformance_contribution")) and not same_focus:
            sentences["under"] = f"Найбільша розрахована в системі частка внеску в недовиконання припадає на ССП «{top_under}» — {_pct(f.get('top_underperformance_contribution'))}, тоді як частка цього ССП у портфелі становить {_pct(f.get('top_underperformance_weight'))}."
        if top_under and is_number(f.get("top_underperformance_contribution")):
            excess = f.get("top_underperformance_excess_pp")
            if is_number(excess) and abs(float(excess)) >= 0.05:
                relation = "перевищує" if float(excess) > 0 else "є нижчою за"
                sentences["under_gap"] = f"Частка ССП «{top_under}» у загальному недовиконанні {relation} його портфельну вагу на {_delta_words(excess)}; це кількісно визначає непропорційність негативного внеску відносно масштабу відповідальності."
    if drill:
        used.add(drill.code); f = drill.facts
        if drill.code == "goal_drilldown" and f.get("top_tasks"):
            pieces = [f"{label}: проблемних {pr}, без даних {mi}" for label, pr, mi in f["top_tasks"]]
            sentences["drill"] = f"У межах {f.get('goal_label')} основна частина проблемних і відсутніх позицій припадає на такі завдання: " + "; ".join(pieces) + "."
            if is_number(f.get("top2_attention_share")):
                sentences["drill_share"] = f"Два найбільші завдання охоплюють {_pct(float(f['top2_attention_share'])*100)} усіх проблемних і відсутніх позицій цієї цілі, тобто відхилення на цьому рівні є переважно локалізованим."
        elif drill.code == "ssp_drilldown":
            if f.get("top_tasks"):
                pieces = [f"{label}: проблемних {pr}, без даних {mi}" for label, pr, mi in f["top_tasks"]]
                sentences["drill_share"] = f"У портфелі ССП «{f.get('department')}» основні проблемні й відсутні позиції зосереджені в таких завданнях: " + "; ".join(pieces) + "."
            else:
                sentences["drill"] = f"У ССП «{f.get('department')}» немає одного завдання, яке самостійно концентрує основну частину проблемних або відсутніх позицій; відхилення розподілені між кількома завданнями."
    structures = BLOCK_STRUCTURES["distribution"]
    order = structures[deterministic_index(len(structures), f"{ctx.signature}:{block}-structure")]
    rendered = [sentences[k] for k in order if k in sentences]
    return AnalyticalBlock(block, kind, 88 if kind in {"goal", "department"} else 72, findings=tuple(used), sentences=tuple(rendered), facts_used=frozenset(used))


def _statuses_block(ctx: AnalyticsContext, findings: list[AnalyticalFinding]) -> AnalyticalBlock:
    item = _first(findings, "status_structure")
    if not item:
        return AnalyticalBlock("statuses", "statuses", 40, sentences=())
    f = item.facts; total = _n(f.get("total")); ranked = f.get("ranked", []) or []; sentences: list[str] = []
    if ranked:
        pieces = [f"{label} — {count}" for label, count in ranked[:6]]
        sentences.append("Структура статусів у поточній вибірці розподіляється так: " + "; ".join(pieces) + ".")
        sentences.append(f"Найпоширеніший фактично зафіксований статус — «{f.get('dominant_label')}»: {f.get('dominant_count')} із {total} записів, або {_pct(float(f.get('dominant_share',0))*100)}.")
    shares = f.get("shares", {}) or {}
    interpretation_parts = []
    for label in ("Частково виконано", "Не виконано", "Не подано"):
        if label in shares:
            interpretation_parts.append(f"«{label}» — {_pct(float(shares[label])*100)}")
    if interpretation_parts:
        sentences.append("Статуси, що безпосередньо впливають на інтерпретацію поточного портфеля, мають такі частки: " + "; ".join(interpretation_parts) + ".")

    comparison = f.get("period_comparison") or {}
    if comparison:
        changes = comparison.get("share_changes_pp", {}) or {}
        selected = []
        for label in ("Виконано", "Частково виконано", "Не виконано", "Не подано"):
            delta = changes.get(label)
            if is_number(delta) and abs(float(delta)) >= 0.5:
                selected.append((label, float(delta)))
        if selected:
            parts = [f"частка «{label}» {'зросла' if delta > 0 else 'знизилася'} на {_delta_words(delta)}" for label, delta in selected]
            sentences.append(
                f"Між {comparison.get('previous_period')} та {comparison.get('latest_period')} статусна структура також змінилася: "
                + "; ".join(parts) + "."
            )
        prev_total = _n(comparison.get("previous_total")); latest_total = _n(comparison.get("latest_total"))
        if prev_total and latest_total and prev_total != latest_total:
            sentences.append(
                f"Кількість записів у двох порівнюваних періодах відрізняється — {prev_total} проти {latest_total}; тому зміни часток статусів слід читати як структурний зсув, а не як зміну абсолютної кількості позицій."
            )
    sentences.append("Найбільше значення для загальної картини мають зміни часток статусів, які безпосередньо формують перехід між невиконанням, частковим та повним виконанням.")
    return AnalyticalBlock("statuses", "statuses", item.importance, findings=(item.code,), sentences=tuple(sentences), facts_used=frozenset({item.code}))


def _products_block(ctx: AnalyticsContext, findings: list[AnalyticalFinding]) -> AnalyticalBlock:
    item = _first(findings, "product_structure")
    if not item:
        return AnalyticalBlock("products", "products", 35, sentences=())
    f = item.facts; sentences: list[str] = []
    if f.get("largest_label") and f.get("total_size"):
        sentences.append(
            f"За типами продукту найбільший сегмент — «{f.get('largest_label')}»: {f.get('largest_size')} із {f.get('total_size')} унікальних заходів, "
            f"або {_pct(float(f.get('largest_share',0))*100)} портфеля цього розрізу."
        )
    if f.get("best_label") and f.get("worst_label"):
        sentences.append(
            f"Найвищий рівень виконання за типами продукту має «{f.get('best_label')}» — {_pct(f.get('best_value'))}, "
            f"найнижчий — «{f.get('worst_label')}» — {_pct(f.get('worst_value'))}; різниця становить {_delta_words(f.get('gap'))}."
        )
    if _n(f.get("problem_total")) and f.get("top_problem_label"):
        sentences.append(
            f"Найбільша кількість проблемних позицій у продуктовому розрізі припадає на «{f.get('top_problem_label')}» — "
            f"{f.get('top_problem_count')} із {f.get('problem_total')}, або {_pct(float(f.get('top_problem_share',0))*100)} всіх проблемних позицій за типами продукту."
        )
    if _n(f.get("missing_total")) and f.get("top_missing_label"):
        sentences.append(
            f"Неповнота даних найбільше концентрується у типі «{f.get('top_missing_label')}» — {f.get('top_missing_count')} із "
            f"{f.get('missing_total')} відсутніх подань у цьому розрізі ({_pct(float(f.get('top_missing_share',0))*100)})."
        )
    return AnalyticalBlock("products", "products", item.importance, findings=(item.code,), sentences=tuple(sentences), facts_used=frozenset({item.code}))


def _mio_block(ctx: AnalyticsContext, findings: list[AnalyticalFinding]) -> AnalyticalBlock:
    profile = _first(findings, "mio_integral_profile")
    divergence = _first(findings, "mio_execution_result_divergence")
    task_profile = _first(findings, "mio_task_indicator_profile")
    task_divergence = _first(findings, "mio_task_execution_result_divergence")
    measure_profile = _first(findings, "mio_measure_profile")
    financing = _first(findings, "mio_financing_profile")
    if not any((profile, divergence, task_profile, task_divergence, measure_profile, financing)):
        return AnalyticalBlock("mio_assessment", "mio", 40, sentences=())
    sentences=[]; used=set()
    if profile:
        used.add(profile.code); f=profile.facts
        sentences.append(
            f"Оцінка МіО за {f.get('year')} рік показує середню інтегральну оцінку стратегічних цілей {_pct(f.get('average_integral'))}. "
            f"Найвищий результат має {f.get('best_code')} — {_pct(f.get('best_integral'))}, найнижчий — {f.get('worst_code')} — {_pct(f.get('worst_integral'))}; розрив становить {_delta_words(f.get('gap'))}."
        )
        comps=[]
        if is_number(f.get('average_measures')): comps.append(f"виконання заходів {_pct(f.get('average_measures'))}")
        if is_number(f.get('average_tasks')): comps.append(f"результат завдань за індикаторами {_pct(f.get('average_tasks'))}")
        if is_number(f.get('average_progress')): comps.append(f"прогрес стратегічних індикаторів {_pct(f.get('average_progress'))}")
        if comps: sentences.append("У середньому компоненти інтегральної оцінки співвідносяться так: " + "; ".join(comps) + ".")
    if divergence:
        used.add(divergence.code); items=divergence.facts.get('items',[]) or []
        if items:
            pieces=[]
            for item in items[:3]:
                direction="вище" if float(item.get('gap') or 0)>0 else "нижче"
                pieces.append(f"{item.get('code')}: виконання заходів {_pct(item.get('measure_execution'))}, інтеграл {_pct(item.get('integral'))} ({_delta_words(item.get('gap'))} {direction})")
            sentences.append("Найбільша розбіжність між операційним виконанням і стратегічним результатом зафіксована за " + "; ".join(pieces) + ". Це локалізує цілі, де виконання заходів найменше трансформується в інтегральний результат або, навпаки, стратегічний прогрес випереджає операційний компонент.")
    if task_profile:
        used.add(task_profile.code); f=task_profile.facts
        sentences.append(
            f"На рівні завдань прогрес цільових індикаторів у середньому становить {_pct(f.get('average_task_indicator_progress'))}; "
            f"найвищий результат має завдання {f.get('best_task')} — {_pct(f.get('best_task_progress'))}, найнижчий — {f.get('worst_task')} — {_pct(f.get('worst_task_progress'))}, "
            f"а розрив між ними становить {_delta_words(f.get('gap'))}."
        )
    if task_divergence:
        used.add(task_divergence.code); items=task_divergence.facts.get('items',[]) or []
        if items:
            pieces=[]
            for item in items[:3]:
                relation="вище" if float(item.get('gap') or 0)>0 else "нижче"
                pieces.append(f"{item.get('code')}: виконання {_pct(item.get('execution'))}, прогрес індикаторів {_pct(item.get('indicator_progress'))} ({_delta_words(item.get('gap'))} {relation})")
            sentences.append("Найбільші розриви між виконанням завдань і прогресом їхніх індикаторів зафіксовано за " + "; ".join(pieces) + ".")
    if measure_profile:
        used.add(measure_profile.code); f=measure_profile.facts
        if _n(f.get('evaluated_measures')):
            sentences.append(
                f"На рівні заходів оцінку співвідношення факту до плану доступно для {count_uk(_n(f.get('evaluated_measures')), 'measure')}; "
                f"середнє значення становить {_pct(f.get('average_fact_plan'))}, медіанне — {_pct(f.get('median_fact_plan'))}."
            )

    if financing:
        used.add(financing.code); f=financing.facts
        paired=_n(f.get('paired_count'))
        if paired:
            sentences.append(f"Для {count_uk(paired, 'measure')} доступне одночасне зіставлення фінансового та фактичного виконання: у середньому фінансове виконання становить {_pct(f.get('avg_financial_execution'))}, а стан виконання заходів — {_pct(f.get('avg_physical_execution'))}.")
            gaps=f.get('largest_gaps',[]) or []
            if gaps:
                top=gaps[0]; delta=top.get('_gap')
                if is_number(delta):
                    relation="випереджає" if float(delta)>0 else "відстає від"
                    sentences.append(f"Найбільше відхилення має захід {top.get('Захід')}: фінансове виконання {_pct(top.get('% виконання'))} {relation} фізичний результат {_pct(top.get('Стан виконання заходу, %'))} на {_delta_words(delta)}.")
    return AnalyticalBlock("mio_assessment", "mio", 94, findings=tuple(used), sentences=tuple(sentences), facts_used=frozenset(used))


def _problem_block(ctx: AnalyticsContext, findings: list[AnalyticalFinding]) -> AnalyticalBlock:
    goal = next((x for x in findings if x.code.startswith("goal_problems_")), None)
    dep = next((x for x in findings if x.code.startswith("department_problems_")), None)
    conflicts = _topic(findings, "conflict")
    risk = _first(findings, "risk_structure")
    persistent = [x for x in findings if x.code.startswith("persistent_")]
    groups: dict[str, list[str]] = {"goal": [], "department": [], "risk": [], "persistent": [], "conflicts": []}
    used: set[str] = set()

    if goal and _n(goal.facts.get("total")):
        used.add(goal.code); f=goal.facts; total=_n(f.get("total")); top=_n(f.get("top_count")); top3=_n(f.get("top3_count"))
        groups["goal"].append(f"За стратегічними цілями з {total} проблемних позицій {top} ({_pct(top/total*100)}) припадають на {f.get('top_label')}, а три найбільші цілі разом концентрують {top3} ({_pct(top3/total*100)}).")
        if is_number(f.get("top_portfolio_share")) and is_number(f.get("concentration_excess_pp")):
            excess=float(f["concentration_excess_pp"]); pshare=float(f["top_portfolio_share"])*100
            if abs(excess)>=0.05:
                relation="перевищує" if excess>0 else "є нижчою за"
                conclusion = "проблемний внесок цієї цілі є непропорційно вищим за її портфельну вагу" if excess > 0 else "проблемний внесок цієї цілі є нижчим за її портфельну вагу"
                groups["goal"].append(f"Частка {f.get('top_label')} серед усіх проблемних позицій {relation} її частку в портфелі ({_pct(pshare)}) на {_delta_words(excess)}; отже, {conclusion}.")

    if dep and _n(dep.facts.get("total")):
        used.add(dep.code); f=dep.facts; total=_n(f.get("total")); top=_n(f.get("top_count")); top3=_n(f.get("top3_count"))
        groups["department"].append(f"За ССП найбільший абсолютний обсяг проблемних позицій має ССП «{f.get('top_label')}» — {top} із {total} ({_pct(top/total*100)}); три найбільші ССП охоплюють {top3} ({_pct(top3/total*100)}).")
        if f.get("top_internal_rate") is not None:
            groups["department"].append(f"У власному портфелі цього ССП проблемними є {_pct(float(f['top_internal_rate'])*100)} позицій.")
        if is_number(f.get("top_portfolio_share")) and is_number(f.get("concentration_excess_pp")):
            excess=float(f["concentration_excess_pp"]); pshare=float(f["top_portfolio_share"])*100
            if abs(excess)>=0.05:
                relation="перевищує" if excess>0 else "є нижчою за"
                groups["department"].append(f"Його частка серед усіх проблемних позицій {relation} частку у відповідному портфелі ({_pct(pshare)}) на {_delta_words(excess)}, тому масштаб проблемності не зводиться лише до розміру портфеля.")

    if risk:
        used.add(risk.code); r=risk.facts; risk_parts=[]
        if is_number(r.get("high_critical_share")): risk_parts.append(f"частка високого/критичного ризику — {_pct(r.get('high_critical_share'))}")
        if is_number(r.get("without_substantial_risk_share")): risk_parts.append(f"без суттєвого ризику — {_pct(r.get('without_substantial_risk_share'))}")
        if is_number(r.get("results_achieved_share")): risk_parts.append(f"частка досягнутих результатів — {_pct(r.get('results_achieved_share'))}")
        if risk_parts:
            groups["risk"].append("Останній доступний ризиковий зріз характеризується так: " + "; ".join(risk_parts) + ".")
        if r.get("top_risk_department") and is_number(r.get("top_risk_contribution")):
            if is_number(r.get("top_risk_portfolio_weight")):
                groups["risk"].append(f"Найбільша розрахована частка ризикового внеску припадає на ССП «{r.get('top_risk_department')}» — {_pct(r.get('top_risk_contribution'))}, тоді як його частка портфеля становить {_pct(r.get('top_risk_portfolio_weight'))}.")
            else:
                groups["risk"].append(f"Найбільша розрахована частка ризикового внеску припадає на ССП «{r.get('top_risk_department')}» — {_pct(r.get('top_risk_contribution'))}.")
            if is_number(r.get("top_risk_excess_pp")) and abs(float(r["top_risk_excess_pp"])) >= 0.05:
                excess=float(r["top_risk_excess_pp"]); relation="перевищує" if excess>0 else "є нижчою за"
                groups["risk"].append(f"Ризиковий внесок цього ССП {relation} його портфельну вагу на {_delta_words(excess)}; у кількісному розрізі ризикове навантаження є непропорційним масштабу відповідальності.")

    if persistent:
        problem_parts=[]; missing_parts=[]
        for item in persistent:
            used.add(item.code); pf=item.facts; label=str(pf.get("label") or "визначеного компонента")
            if item.code.endswith("_problems"):
                problem_parts.append(f"{label} — у {pf.get('periods_with_problem')} із {pf.get('periods_observed')} доступних періодів")
            elif item.code.endswith("_missing"):
                missing_parts.append(f"{label} — у {pf.get('periods_with_missing')} із {pf.get('periods_observed')} доступних періодів")
        if problem_parts:
            groups["persistent"].append("Повторювана проблемність зафіксована для " + "; ".join(problem_parts) + ". Це відрізняє стійке відхилення від одиничного квартального епізоду.")
        if missing_parts:
            groups["persistent"].append("Повторювана неповнота даних зафіксована для " + "; ".join(missing_parts) + ". Отже, для цих компонентів відсутність подань не є одноразовим явищем у доступній часовій послідовності.")

    for item in conflicts:
        used.add(item.code); f=item.facts
        if item.code == "conflict_execution_up_coverage_down":
            groups["conflicts"].append(f"Зростання виконання супроводжується скороченням покриття: між крайніми доступними періодами виконання збільшилося на {_delta_words(f.get('execution_delta'))}, а покриття зменшилося на {_delta_words(f.get('coverage_delta'))}. Це не скасовує позитивної зміни, але означає, що вона сформована на менш повному останньому масиві даних.")
        elif item.code == "conflict_execution_down_coverage_up":
            groups["conflicts"].append(f"Покриття даними розширилося на {_delta_words(f.get('coverage_delta'))}, тоді як виконання знизилося на {_delta_words(f.get('execution_delta'))}; за такого поєднання негативний результат не пояснюється звуженням інформаційної бази.")
        elif item.code == "conflict_execution_up_problems_up":
            change=f.get("problem_change")
            if is_number(change) and float(change)>0:
                groups["conflicts"].append(f"Позитивна динаміка виконання одночасно супроводжується збільшенням кількості проблемних/ризикових позицій на {fmt_number(change)} у річному порівнянні; у поточній вибірці їх {f.get('problem_count')}. Тому покращення зведеного виконання не означає однорідно позитивного руху всього портфеля.")
            else:
                groups["conflicts"].append(f"Позитивна динаміка виконання поєднується з поточним обсягом проблемних позицій — {f.get('problem_count')}. Тому зростання зведеного показника не означає однорідно позитивної картини всього портфеля.")
        elif item.code == "stable_aggregate_hidden_internal_movement":
            groups["conflicts"].append(f"Майже незмінний зведений результат приховує значні протилежні зміни всередині портфеля: {f.get('largest_improvement_label')} має {fmt_delta(f.get('largest_improvement'))}, тоді як {f.get('largest_deterioration_label')} — {fmt_delta(f.get('largest_deterioration'))}. Формально стабільне середнє в цьому випадку не відображає масштабу внутрішнього руху.")

    if not any(groups.values()):
        return AnalyticalBlock("problem_concentration", "problems", 45, sentences=("Окремого значущого кластеру проблемних позицій у доступних структурних розрізах не виявлено; основні відхилення локалізовано у блоках динаміки, цілей та ССП.",))
    structures=BLOCK_STRUCTURES["conflict"]
    order=structures[deterministic_index(len(structures), f"{ctx.signature}:conflict-structure")]
    rendered=[sentence for key in order for sentence in groups.get(key, [])]
    return AnalyticalBlock("problem_concentration", "problems", 92 if conflicts else 82, findings=tuple(used), sentences=tuple(rendered), facts_used=frozenset(used))

def _management_block(ctx: AnalyticsContext, findings: list[AnalyticalFinding]) -> AnalyticalBlock:
    item = _first(findings, "management_priorities")
    if not item: return AnalyticalBlock("management_attention", "management", 50, sentences=())
    priorities = item.facts.get("priorities", []) or []; sentences=[]
    if not priorities: return AnalyticalBlock("management_attention", "management", 50, sentences=())
    first = priorities[0]
    def describe(p: dict[str,Any]) -> str:
        label = p.get("label"); kind = "стратегічна ціль" if p.get("kind")=="goal" else "ССП"
        parts=[f"виконання {_pct(p.get('execution'))}"]
        if is_number(p.get("change")) and abs(float(p["change"])) >= .05: parts.append(f"зміна {fmt_delta(p.get('change'))}")
        if p.get("problems"): parts.append(f"проблемних позицій {p.get('problems')}")
        if p.get("missing"): parts.append(f"без даних {p.get('missing')}")
        if is_number(p.get("portfolio_weight")) and float(p["portfolio_weight"])>0: parts.append(f"частка портфеля {_pct(p.get('portfolio_weight'))}")
        if is_number(p.get("underperformance_contribution")) and float(p["underperformance_contribution"])>0: parts.append(f"внесок у недовиконання {_pct(p.get('underperformance_contribution'))}")
        return f"{kind} «{label}»: " + ", ".join(parts) if p.get("kind") == "department" else f"{kind} {label}: " + ", ".join(parts)
    sentences.append("За сукупністю величини відхилення, динаміки, проблемних/відсутніх позицій та, для ССП, масштабу портфеля найбільшої управлінської уваги потребує " + describe(first) + ".")
    if len(priorities) > 1:
        sentences.append("Наступну групу точок уваги формують " + "; ".join(describe(p) for p in priorities[1:3]) + ".")
    if len(priorities) > 3:
        sentences.append("Додатково до пріоритетної групи входять " + "; ".join(describe(p) for p in priorities[3:5]) + ".")
    sentences.append("Ці напрями мають найбільшу сукупну вагу в поточних відхиленнях з урахуванням масштабу портфеля, динаміки, проблемних позицій та повноти даних.")
    return AnalyticalBlock("management_attention", "management", 100, findings=(item.code,), sentences=tuple(sentences), facts_used=frozenset({item.code}))


def _final_block(ctx: AnalyticsContext, findings: list[AnalyticalFinding], blocks: list[AnalyticalBlock]) -> AnalyticalBlock:
    traj = next((f for f in findings if f.topic == "dynamics" and "values" in f.facts), None)
    goal_dist = _first(findings, "goal_distribution")
    dep_impact = _first(findings, "ssp_portfolio_impact")
    priorities = _first(findings, "management_priorities")
    conflicts = _topic(findings, "conflict")
    overall = _first(findings, "overall_state")
    dep_missing = next((x for x in findings if x.code.startswith("department_missing_")), None)
    goal_missing = next((x for x in findings if x.code.startswith("goal_missing_")), None)
    groups: dict[str, list[str]] = {"trajectory": [], "distribution": [], "contributor": [], "conflict": [], "data_quality": [], "priorities": [], "closing": []}
    used: set[str] = set()

    if traj:
        used.add(traj.code)
        if traj.code == "trajectory_single_period":
            groups["trajectory"].append("Часовий тренд для цієї вибірки не визначається, оскільки доступний лише один оцінений період; підсумкова оцінка ґрунтується на фактичному рівні виконання та повноті даних цього зрізу.")
        else:
            direction = {
                "trajectory_continuous_growth":"послідовним покращенням протягом доступних періодів",
                "trajectory_net_growth":"позитивною зміною між першим і останнім доступними періодами",
                "trajectory_recovery":"відновленням після попереднього погіршення",
                "trajectory_continuous_decline":"послідовним погіршенням протягом доступних періодів",
                "trajectory_net_decline":"негативною зміною між першим і останнім доступними періодами",
                "trajectory_volatile":"суттєвими різноспрямованими коливаннями",
                "trajectory_plateau":"відсутністю помітного зрушення протягом доступного горизонту",
            }.get(traj.code, "змішаною часовою траєкторією")
            groups["trajectory"].append(f"У підсумку часовий профіль виконання характеризується {direction}.")
    elif overall and is_number(overall.facts.get("execution_average")):
        used.add(overall.code)
        groups["trajectory"].append(f"За відсутності достатньої часової послідовності підсумкова оцінка спирається на середній рівень виконання {_pct(overall.facts.get('execution_average'))} та структурний розподіл поточної вибірки, без штучного висновку про тренд.")

    if goal_dist and _n(goal_dist.facts.get("count")) > 1:
        used.add(goal_dist.code)
        groups["distribution"].append("Внутрішня картина не зводиться до середнього: стратегічні цілі мають різні результати, а позитивні та негативні відхилення локалізовані за конкретними цілями і завданнями.")

    if dep_impact and dep_impact.facts.get("top_underperformance_department"):
        used.add(dep_impact.code); f=dep_impact.facts
        sentence=f"У розрізі відповідальних підрозділів найбільш вагомою негативною складовою за розрахованою метрикою внеску в недовиконання є ССП «{f.get('top_underperformance_department')}»"
        if is_number(f.get("top_underperformance_contribution")) and is_number(f.get("top_underperformance_weight")):
            sentence += f": на нього припадає {_pct(f.get('top_underperformance_contribution'))} недовиконання при частці {_pct(f.get('top_underperformance_weight'))} у портфелі"
        groups["contributor"].append(sentence + ".")

    if conflicts:
        used.update(item.code for item in conflicts)
        groups["conflict"].append("Позитивні й негативні зміни не є повністю односпрямованими: покращення зведеного виконання поєднується з локальними внутрішніми відхиленнями та обмеженнями за повнотою даних.")

    if dep_missing and _n(dep_missing.facts.get("total")):
        used.add(dep_missing.code)
        groups["data_quality"].append(f"Основний осередок неповноти даних у розрізі ССП — ССП «{dep_missing.facts.get('top_label')}»; саме там зосереджена найбільша кількість відсутніх подань серед відповідальних підрозділів.")
    elif goal_missing and _n(goal_missing.facts.get("total")):
        used.add(goal_missing.code)
        groups["data_quality"].append(f"Основний осередок неповноти даних у розрізі стратегічних цілей — {goal_missing.facts.get('top_label')}; ця ціль концентрує найбільшу кількість відсутніх подань у відповідному розподілі.")

    if priorities and priorities.facts.get("priorities"):
        used.add(priorities.code); ps=priorities.facts["priorities"][:3]; labels=[]
        for p in ps:
            label=str(p.get("label"))
            labels.append(f"ССП «{label}»" if p.get("kind") == "department" else (("СЦ " if not label.startswith("СЦ") else "") + label))
        groups["priorities"].append("З погляду управлінської уваги першочерговими залишаються " + join_uk(labels) + "; саме вони мають найбільшу сукупну вагу за фактичними відхиленнями, проблемними/відсутніми позиціями та масштабом портфеля там, де такий показник доступний.")

    if ctx.sample_size <= 1:
        groups["closing"].append("Для цієї вузької вибірки визначальними є фактичний результат одного заходу та повнота даних щодо нього; ширші портфельні закономірності за такою сукупністю не встановлюються.")
    elif not priorities and not dep_impact and overall and is_number(overall.facts.get("execution_average")):
        groups["closing"].append(f"Загалом поточна картина визначається рівнем виконання {_pct(overall.facts.get('execution_average'))} у поєднанні з часовою динамікою та структурою відхилень між складовими портфеля.")

    structures=BLOCK_STRUCTURES["final"]
    order=structures[deterministic_index(len(structures), f"{ctx.signature}:final-structure")]
    rendered=[sentence for key in order for sentence in groups.get(key, [])]
    return AnalyticalBlock("final_assessment", "final", 100, findings=tuple(used), sentences=tuple(rendered), facts_used=frozenset(used))

def _render_block(ctx: AnalyticsContext, code: str, findings: list[AnalyticalFinding], opening: str, complexity: str, prior_blocks: list[AnalyticalBlock]) -> AnalyticalBlock:
    if code == "scope": return _scope_block(ctx, findings, opening, complexity)
    if code == "overall_state": return _overall_block(ctx, findings, complexity)
    if code == "dynamics": return _dynamics_block(ctx, findings, complexity)
    if code == "year_over_year": return _yoy_block(ctx, findings)
    if code == "coverage": return _coverage_block(ctx, findings)
    if code == "goals": return _distribution_block(ctx, findings, "goal")
    if code == "tasks": return _distribution_block(ctx, findings, "task")
    if code == "departments": return _distribution_block(ctx, findings, "department")
    if code == "statuses": return _statuses_block(ctx, findings)
    if code == "products": return _products_block(ctx, findings)
    if code == "mio_assessment": return _mio_block(ctx, findings)
    if code == "problem_concentration": return _problem_block(ctx, findings)
    if code == "management_attention": return _management_block(ctx, findings)
    if code == "final_assessment": return _final_block(ctx, findings, prior_blocks)
    return AnalyticalBlock(code, code, 20, sentences=())


def _sentence_count(text: str) -> int:
    return len([s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]) if text.strip() else 0


def compose_note(ctx: AnalyticsContext, debug_mode: bool = False) -> GeneratedNote:
    signals = detect_signals(ctx)
    questions, findings = derive_findings(ctx, signals)
    scenarios = activate_scenarios(signals, findings)
    plan = build_text_plan(ctx, signals, scenarios, findings)
    state = GenerationState()
    debug = GenerationDebug(
        detected_signals=[s.code for s in signals], analytical_questions=[q.code for q in questions],
        analytical_findings=[f.code for f in findings], activated_scenarios=[s.code for s in scenarios],
        selected_scenarios=list(plan.scenario_mix), context_complexity=plan.complexity,
        target_paragraph_count=plan.target_paragraphs, selected_blocks=list(plan.blocks),
        block_depths={bp.code: bp.depth for bp in plan.block_plans},
    )
    opening = _choose_opening(ctx, plan.opening, state, debug)
    blocks: list[AnalyticalBlock] = []
    for index, code in enumerate(plan.blocks):
        block = _render_block(ctx, code, findings, opening, plan.complexity, blocks)
        if code == "overall_state" and block.sentences:
            block = AnalyticalBlock(block.code, block.topic, block.importance, block.signals, block.findings,
                                    (opening,) + block.sentences, block.facts_used)
        if not block.text:
            continue
        # Natural paragraph transition for middle blocks. Do not alter the first or final synthesis.
        if index > 1 and code not in {"final_assessment", "management_attention"} and block.sentences:
            first_sentence = block.sentences[0]
            transitioned = _transition(ctx, {"year_over_year":"yoy", "problem_concentration":"problems"}.get(code, code), first_sentence, state, debug)
            block = AnalyticalBlock(block.code, block.topic, block.importance, block.signals, block.findings,
                                    (transitioned,) + block.sentences[1:], block.facts_used)
        blocks.append(block)
        debug.sentences_per_block[code] = len(block.sentences)
    paragraphs = [block.text for block in blocks if block.text]
    text = clean_text("\n\n".join(paragraphs))

    used_findings = {code for block in blocks for code in block.findings}
    important = {f.code for f in findings if f.importance >= 60}
    debug.important_findings_used = sorted(important & used_findings)
    debug.important_findings_skipped = sorted(important - used_findings)
    debug.facts_used = sorted({fact for block in blocks for fact in block.facts_used})
    debug.word_count = len(re.findall(r"\b[\w’'-]+\b", text, flags=re.UNICODE))
    quality = assess_quality(text, plan.complexity, findings, used_findings, debug.selected_phrase_ids, debug.facts_used)
    debug.quality_metrics = quality
    warnings = validate_text(text, ctx, signals, findings)
    # A wide/full-plan note that collapses back into a short dashboard summary is
    # a generation failure, not an acceptable low-quality result. Since the page
    # no longer falls back to legacy prose, these checks fail visibly and are
    # logged with an incident code.
    if plan.complexity in {"wide", "very_wide"}:
        if quality.paragraph_count < 7: warnings.append(f"quality-hard: wide note has {quality.paragraph_count} paragraphs")
        if quality.sentence_count < 25: warnings.append(f"quality-hard: wide note has {quality.sentence_count} sentences")
        if quality.word_count < 700: warnings.append(f"quality-hard: wide note has {quality.word_count} words")
        if quality.median_sentences_per_paragraph < 3: warnings.append("quality-hard: median paragraph depth below 3 sentences")
    if quality.important_finding_coverage < 0.90 and important:
        prefix = "quality-hard:" if plan.complexity in {"wide", "very_wide"} else "quality:"
        warnings.append(f"{prefix} important finding coverage {quality.important_finding_coverage:.1%}")
    debug.validation_warnings = warnings

    # Hard validation concerns should fail generation; quality warnings remain observable
    # in debug without making the page silently fall back to the legacy summary.
    hard = [w for w in warnings if not w.startswith("quality:")]
    if hard:
        raise ValueError("Analytics text validation failed: " + "; ".join(hard))
    return GeneratedNote(text=text, debug=debug)
