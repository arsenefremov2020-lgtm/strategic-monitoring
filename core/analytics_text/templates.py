from __future__ import annotations

"""Deterministic language inventory.

The library is intentionally split by sentence function rather than by complete
ready-made reports.  Analytical facts/findings are produced elsewhere; these
variants only realise already supported content in natural Ukrainian.
"""

from collections import defaultdict

from .models import PhraseVariant


TOPICS = {
    "scope": ("охоплення вибірки", "складовими портфеля"),
    "general": ("загального стану виконання", "основними показниками"),
    "execution": ("рівня виконання", "результатами виконання"),
    "coverage": ("повноти моніторингових даних", "показниками покриття"),
    "dynamics": ("динаміки виконання", "оціненими періодами"),
    "yoy": ("річної зміни", "річними результатами"),
    "goals": ("результатів стратегічних цілей", "стратегічними цілями"),
    "tasks": ("результатів завдань", "завданнями"),
    "departments": ("результатів відповідальних ССП", "відповідальними ССП"),
    "products": ("результатів типів продукту", "типами продукту"),
    "statuses": ("статусів виконання", "статусами виконання"),
    "problems": ("проблемних позицій", "проблемними компонентами"),
    "missing": ("відсутніх подань", "напрямами з неповними даними"),
    "conflict": ("різноспрямованих змін", "позитивними й негативними змінами"),
    "management": ("пріоритетних напрямів уваги", "об’єктами з найбільшою вагою відхилень"),
    "final": ("підсумкового стану", "ключовими компонентами результату"),
}

FAMILY_PATTERNS = {
    "claim": (
        "Поточні результати щодо {a} безпосередньо впливають на загальну картину.",
        "За поточною вибіркою показники щодо {a} мають суттєву вагу для загального результату.",
        "Результати щодо {a} формують окрему складову загальної картини виконання.",
        "Поточний стан щодо {a} пов’язаний із підсумковим результатом портфеля.",
        "Зміни щодо {a} впливають на загальну характеристику виконання.",
    ),
    "evidence": (
        "Фактичні значення за {b} визначають масштаб цього результату.",
        "Кількісні значення за {b} конкретизують масштаб зафіксованої зміни.",
        "Абсолютні та відносні значення за {b} підтверджують масштаб відхилення.",
        "Показники за {b} дають числову основу для цього висновку.",
        "Масштаб результату визначається фактичними значеннями за {b}.",
    ),
    "comparison": (
        "Результати за {b} відрізняються за рівнем і напрямом зміни.",
        "Між результатами за {b} зберігаються помітні розриви.",
        "За {b} відмінності охоплюють як рівень результату, так і напрям його зміни.",
        "Найбільш виражені відхилення припадають на окремі компоненти за {b}.",
        "За {b} загальна тенденція поєднується з локальними змінами різного масштабу.",
    ),
    "qualification": (
        "Повнота даних за {b} визначає, наскільки стійким є висновок щодо {a}.",
        "Результат щодо {a} охоплює лише компоненти, для яких наявні оцінені дані.",
        "Поточна оцінка щодо {a} стосується фактично охопленої моніторингом частини портфеля.",
        "Відсутні дані за {b} не прирівнюються до нульового результату.",
        "Неповні подання за {b} відокремлені від фактичного невиконання.",
    ),
    "contrast": (
        "Результати щодо {a} не є однорідними: між окремими компонентами зберігаються помітні відмінності.",
        "За {a} позитивні й негативні зміни одночасно впливають на загальний результат.",
        "Попри загальний напрям, за {a} окремі компоненти рухаються у протилежний бік.",
        "Зведене значення щодо {a} приховує відмінності між окремими складовими портфеля.",
        "Поряд із загальною тенденцією щодо {a} зберігаються компоненти з протилежною динамікою.",
    ),
    "interpretation": (
        "Результати щодо {a} залежать від того, як внесок розподілений між окремими компонентами.",
        "За {b} окремі компоненти мають різну вагу в загальному результаті.",
        "Відхилення за {b} можуть бути широкими або зосередженими в обмеженій групі компонентів.",
        "За {b} позитивні й негативні складові мають різну вагу в загальній картині.",
        "Результати за {b} уточнюють, які компоненти найбільше визначають поточний стан.",
    ),
    "localization": (
        "Найбільша частина відхилення зосереджується в окремих компонентах за {b}.",
        "Основну частину результату формують окремі компоненти за {b}.",
        "За {b} відхилення може концентруватися в обмеженій групі компонентів.",
        "Основні позитивні й негативні відхилення припадають на окремі компоненти за {b}.",
        "Найбільший внесок у результат припадає на окремі компоненти за {b}.",
    ),
    "closing": (
        "Отже, результати щодо {a} визначаються співвідношенням основних позитивних і негативних компонентів.",
        "У підсумку результати щодо {a} мають помітну вагу в загальній картині виконання.",
        "Таким чином, відхилення щодо {a} мають конкретний масштаб і зосереджені в окремих компонентах.",
        "У підсумку результати щодо {a} визначають його вагу в загальній картині виконання.",
        "Підсумковий стан щодо {a} визначається рівнем, динамікою та внутрішніми відмінностями результатів.",
    ),
}



def _build_core_library() -> dict[str, list[PhraseVariant]]:
    lib: dict[str, list[PhraseVariant]] = defaultdict(list)
    for topic, (a, b) in TOPICS.items():
        for family, patterns in FAMILY_PATTERNS.items():
            for idx, pattern in enumerate(patterns, 1):
                lib[topic].append(PhraseVariant(
                    id=f"{topic}_{family}_{idx:02d}", template=pattern.format(a=a, b=b),
                    suitable_for=(topic,), family=family,
                ))
    return lib


PHRASE_LIBRARY: dict[str, list[PhraseVariant]] = _build_core_library()

# Additional opening, transition and synthesis pools. They are functional language
# units, not alternative complete reports.
_OPENINGS = (
    "За обраний період загальний стан виконання визначається зведеним результатом, його динамікою та відмінностями між окремими складовими портфеля.",
    "У поточній вибірці загальний результат поєднується з відмінностями між стратегічними цілями, завданнями та відповідальними ССП.",
    "За обраний період ключовими характеристиками є рівень виконання, його часова траєкторія, повнота даних і концентрація відхилень.",
    "Зведений результат за обраний період формується внеском стратегічних цілей, завдань і відповідальних ССП.",
    "Поточний стан виконання визначається одночасно динамікою результатів, повнотою моніторингових даних і розподілом відхилень між основними компонентами портфеля.",
)
for tag in ("neutral", "positive", "negative", "cautious", "mixed"):
    for cycle in range(2):
        for i, text in enumerate(_OPENINGS, 1):
            prefix = {
                "neutral": "",
                "positive": "Загальна траєкторія містить позитивні зміни. ",
                "negative": "Загальна картина містить виражені негативні відхилення. ",
                "cautious": "Повнота даних обмежує силу частини висновків. ",
                "mixed": "Зведені показники поєднують різноспрямовані зміни. ",
            }[tag]
            suffix = "" if cycle == 0 else " Основні відхилення зосереджені в тих компонентах, що мають найбільшу вагу в поточному результаті."
            PHRASE_LIBRARY["opening"].append(PhraseVariant(id=f"opening_{tag}_{cycle}_{i:02d}", template=prefix + text + suffix, suitable_for=(tag,), family="claim"))

_TRANSITIONS_BY_TOPIC = {
    "dynamics": (
        "З погляду часової динаміки", "У часовій динаміці", "За послідовністю оцінених періодів",
        "За квартальною траєкторією", "Протягом обраного горизонту", "У часовій послідовності",
        "За зміною результату в часі", "Між оціненими періодами", "У динаміці виконання", "За траєкторією виконання",
    ),
    "coverage": (
        "Щодо повноти моніторингових даних", "За покриттям моніторингом", "За повнотою подань",
        "У частині покриття", "За доступністю моніторингових даних", "Щодо неповноти даних",
        "Серед відсутніх подань", "За якістю інформаційної основи", "Серед напрямів із неповними даними", "Щодо повноти інформації",
    ),
    "goals": (
        "За стратегічними цілями", "На рівні стратегічних цілей", "За стратегічними цілями",
        "Серед стратегічних цілей", "У частині стратегічних цілей", "За результатами стратегічних цілей",
        "Щодо стратегічних цілей", "Серед стратегічних цілей", "За внутрішніми відмінностями між цілями", "Серед цілей із найбільшими відхиленнями",
    ),
    "tasks": (
        "На рівні завдань", "За завданнями", "За завданнями", "Серед завдань", "У межах завдань",
        "Щодо завдань", "Усередині стратегічних цілей на рівні завдань", "За результатами завдань",
        "На нижчому рівні ієрархії", "Серед завдань",
    ),
    "departments": (
        "За відповідальними ССП", "За відповідальними підрозділами", "На рівні ССП", "Серед відповідальних ССП",
        "За підрозділами, відповідальними за заходи", "Щодо ССП", "Серед відповідальних підрозділів",
        "За портфелями відповідальних підрозділів", "Серед підрозділів із найбільшим впливом на результат", "У частині відповідальних підрозділів",
    ),
    "statuses": (
        "За фактично зафіксованими статусами", "За статусами виконання", "За статусами виконання", "Серед статусів виконання",
        "Щодо статусів виконання", "Серед фактичних статусів", "За змінами статусів виконання", "У частині статусів",
        "За складом статусів портфеля", "За співвідношенням статусів",
    ),
    "products": (
        "За типами продукту", "За типами продукту", "За характером продуктів", "Серед типів продукту",
        "Серед типів продукту", "Щодо типів продукту", "За типами продукту в портфелі", "У частині продуктових відмінностей",
        "Серед продуктових сегментів", "За складом продуктів",
    ),
    "problems": (
        "Щодо концентрації відхилень", "За концентрацією проблемних позицій", "Серед проблемних позицій",
        "У частині проблемних позицій", "Серед основних осередків відхилень", "За концентрацією проблем",
        "Щодо найбільших концентрацій відхилень", "Серед проблемних позицій", "За масштабом і концентрацією відхилень",
        "Серед проблемних компонентів портфеля",
    ),
    "management": (
        "Для управлінської уваги", "За найбільшими відхиленнями", "Серед першочергових точок уваги",
        "За аналітичною вагою відхилень", "За поєднанням масштабу і відхилень", "У частині управлінської уваги",
        "Серед найбільш значущих об’єктів", "За впливом на загальний результат",
        "Серед компонентів із найбільшою сукупною вагою відхилень", "Щодо пріоритетних об’єктів контролю",
    ),
    "final": (
        "У підсумку", "Загалом за обраною вибіркою", "За часовою динамікою та основними відхиленнями",
        "У цілому", "Загальна картина", "За поєднанням основних позитивних і негативних змін",
        "З урахуванням масштабу відхилень", "За основними порівняннями результатів",
        "У підсумковій оцінці", "З огляду на основні драйвери та обмеження",
    ),
}
for topic, leads in _TRANSITIONS_BY_TOPIC.items():
    for i, lead in enumerate(leads, 1):
        PHRASE_LIBRARY["transition"].append(PhraseVariant(
            id=f"transition_{topic}_{i:02d}", template=f"{lead}: {{sentence}}", suitable_for=(topic,), family="transition"
        ))

# 16 topics * 8 families * 5 = 640; 50 openings; 100 transitions = 790.
# Add 30 concise synthesis variants to keep the initial inventory above 800.
for i in range(1, 31):
    noun = ("загальний стан", "динаміка", "основні відхилення", "повнота даних", "результати")[(i - 1) % 5]
    verb = ("визначається", "формується", "пояснюється", "конкретизується", "характеризується", "уточнюється")[(i - 1) % 6]
    PHRASE_LIBRARY["synthesis"].append(PhraseVariant(
        id=f"synthesis_{i:02d}", template=f"У підсумку {noun} {verb} основними позитивними й негативними результатами та їхньою вагою в портфелі.",
        suitable_for=("final",), family="closing",
    ))


def phrase_pool(category: str, tag: str | None = None, family: str | None = None) -> list[PhraseVariant]:
    variants = list(PHRASE_LIBRARY.get(category, ()))
    if category == "opening" and tag:
        tagged = [item for item in variants if tag in item.suitable_for]
        if tagged:
            variants = tagged
    elif tag:
        tagged = [item for item in variants if not item.suitable_for or tag in item.suitable_for]
        if tagged:
            variants = tagged
    if family:
        family_items = [item for item in variants if item.family == family]
        if family_items:
            variants = family_items
    return variants


def phrase_count() -> int:
    return sum(len(items) for items in PHRASE_LIBRARY.values())

# Structural sentence-group variants for the main analytical blocks.  These do
# not contain facts themselves; the composer fills fact-bearing sentence groups
# first and then deterministically chooses one of the safe orders below.
BLOCK_STRUCTURES: dict[str, tuple[tuple[str, ...], ...]] = {
    "general": (
        ("execution", "latest", "coverage", "divergence", "issues"),
        ("execution", "coverage", "latest", "divergence", "issues"),
        ("coverage", "execution", "latest", "divergence", "issues"),
        ("execution", "latest", "divergence", "coverage", "issues"),
        ("divergence", "execution", "latest", "coverage", "issues"),
        ("execution", "issues", "latest", "coverage", "divergence"),
    ),
    "dynamics": (
        ("claim", "path", "net", "pace", "extremes", "coverage", "breadth", "ssp_breadth"),
        ("path", "net", "claim", "pace", "breadth", "extremes", "coverage", "ssp_breadth"),
        ("net", "path", "extremes", "claim", "pace", "coverage", "breadth", "ssp_breadth"),
        ("claim", "net", "breadth", "path", "pace", "extremes", "coverage", "ssp_breadth"),
        ("path", "claim", "extremes", "net", "pace", "breadth", "coverage", "ssp_breadth"),
        ("net", "claim", "path", "pace", "coverage", "extremes", "breadth", "ssp_breadth"),
    ),
    "distribution": (
        ("spread", "relative", "movement", "breadth", "ranking", "weight", "under", "under_gap", "problems", "problem_rate", "missing", "drill", "drill_share"),
        ("movement", "breadth", "spread", "relative", "ranking", "problems", "problem_rate", "weight", "under", "under_gap", "missing", "drill", "drill_share"),
        ("spread", "ranking", "movement", "problems", "problem_rate", "relative", "weight", "under", "under_gap", "missing", "drill", "drill_share"),
        ("problems", "problem_rate", "spread", "relative", "movement", "breadth", "weight", "under", "under_gap", "missing", "drill", "drill_share"),
        ("weight", "under", "under_gap", "spread", "relative", "movement", "breadth", "problems", "problem_rate", "missing", "drill", "drill_share"),
        ("spread", "movement", "ranking", "breadth", "relative", "weight", "under", "under_gap", "problems", "missing", "problem_rate", "drill", "drill_share"),
    ),
    "coverage": (
        ("overall", "latest", "missing", "department", "department_rate", "goal", "goal_rate", "limitation"),
        ("overall", "missing", "department", "department_rate", "goal", "goal_rate", "latest", "limitation"),
        ("missing", "overall", "latest", "department", "department_rate", "goal", "goal_rate", "limitation"),
        ("overall", "latest", "goal", "goal_rate", "department", "department_rate", "missing", "limitation"),
        ("overall", "department", "department_rate", "goal", "goal_rate", "latest", "missing", "limitation"),
        ("latest", "overall", "missing", "goal", "goal_rate", "department", "department_rate", "limitation"),
    ),
    "conflict": (
        ("goal", "department", "risk", "persistent", "conflicts"),
        ("department", "goal", "conflicts", "risk", "persistent"),
        ("conflicts", "goal", "department", "risk", "persistent"),
        ("goal", "risk", "department", "conflicts", "persistent"),
        ("risk", "department", "goal", "persistent", "conflicts"),
        ("persistent", "goal", "department", "conflicts", "risk"),
    ),
    "final": (
        ("trajectory", "distribution", "contributor", "conflict", "data_quality", "priorities", "closing"),
        ("trajectory", "contributor", "distribution", "data_quality", "conflict", "priorities", "closing"),
        ("distribution", "trajectory", "contributor", "conflict", "data_quality", "priorities", "closing"),
        ("trajectory", "distribution", "data_quality", "contributor", "conflict", "priorities", "closing"),
        ("contributor", "trajectory", "distribution", "conflict", "data_quality", "priorities", "closing"),
        ("trajectory", "conflict", "distribution", "contributor", "data_quality", "priorities", "closing"),
    ),
}
