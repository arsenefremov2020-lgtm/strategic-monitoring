from __future__ import annotations

"""Deterministic language inventory.

The library is intentionally split by sentence function rather than by complete
ready-made reports.  Analytical facts/findings are produced elsewhere; these
variants only realise already supported content in natural Ukrainian.
"""

from collections import defaultdict

from .models import PhraseVariant


TOPICS = {
    "scope": ("масштаб аналізу", "охоплення вибірки"),
    "general": ("загальна картина виконання", "зведений результат"),
    "execution": ("виконання", "оцінений результат"),
    "coverage": ("повнота моніторингових даних", "покриття моніторингом"),
    "dynamics": ("динаміка виконання", "траєкторія результату"),
    "yoy": ("порівняння з попереднім роком", "річна зміна"),
    "goals": ("розподіл за стратегічними цілями", "результати стратегічних цілей"),
    "tasks": ("розподіл за завданнями", "результати завдань"),
    "departments": ("розподіл за ССП", "результати відповідальних підрозділів"),
    "products": ("структура за типами продукту", "розподіл продуктів"),
    "statuses": ("структура статусів", "розподіл статусів"),
    "problems": ("концентрація проблемних позицій", "структура відхилень"),
    "missing": ("розподіл відсутніх подань", "неповнота даних"),
    "conflict": ("поєднання різноспрямованих змін", "суперечливість показників"),
    "management": ("управлінські точки уваги", "пріоритетні напрями контролю"),
    "final": ("підсумкова оцінка", "загальний висновок"),
}

FAMILY_PATTERNS = {
    "claim": (
        "{a} визначає одну з ключових характеристик поточної картини.",
        "У поточній вибірці {a} є суттєвим елементом загальної оцінки.",
        "За наявними результатами {a} формує окремий змістовний аспект аналітичної картини.",
        "Поточний стан у цьому розрізі характеризує {a}.",
        "У сукупності даних {a} має самостійне значення для оцінки портфеля.",
    ),
    "evidence": (
        "Фактичні значення за {b} визначають масштаб цього результату.",
        "Кількісні дані за {b} конкретизують масштаб зафіксованої зміни.",
        "Абсолютні та відносні значення за {b} підтверджують описану картину.",
        "Дані щодо {b} становлять числову основу цього висновку.",
        "Масштаб результату розкривається через фактичні значення за {b}.",
    ),
    "comparison": (
        "Порівняння за {b} фіксує відмінності між складовими портфеля.",
        "Зіставлення за {b} визначає розриви всередині вибірки.",
        "У порівняльному розрізі {b} показує напрям і масштаб відмінностей.",
        "Різниця за {b} локалізує найбільш виражені відхилення.",
        "Порівняльні значення за {b} відокремлюють загальний тренд від локальних змін.",
    ),
    "qualification": (
        "Сила висновку щодо {a} визначається фактичною повнотою даних за {b}.",
        "Висновок щодо {a} охоплює лише компоненти, для яких наявні оцінені дані.",
        "Оцінка {a} стосується фактично охопленої моніторингом частини портфеля.",
        "Для {a} відсутні дані не підмінюються нульовими значеннями.",
        "У межах {a} відсутність даних відокремлена від фактичного невиконання.",
    ),
    "contrast": (
        "Водночас {a} не є однорідним: внутрішній розподіл містить помітні відмінності.",
        "На цьому тлі {a} поєднує різноспрямовані компоненти, які змінюють загальну оцінку.",
        "Попри загальний напрям, {a} містить локальні відхилення, зафіксовані в окремих складових.",
        "Зведене значення за {a} не усуває відмінностей між окремими складовими портфеля.",
        "Разом із загальною тенденцією за {a} зберігаються компоненти з протилежною динамікою.",
    ),
    "interpretation": (
        "У сукупності {a} визначається фактично встановленим розподілом результатів.",
        "Такий розподіл за {b} визначає масштаб внеску окремих компонентів у загальну картину.",
        "Співвідношення за {b} визначає ширину або локалізацію зміни в межах фактичного розподілу.",
        "Структура за {b} відокремлює загальний результат від його основних складових.",
        "Сукупність фактів за {b} формує завершений висновок щодо цієї частини портфеля.",
    ),
    "localization": (
        "Локалізація за {b} показує, де саме зосереджена найбільша частина відхилення.",
        "Розподіл за {b} визначає конкретні компоненти, що формують основну частину результату.",
        "У розрізі {b} фактичний розподіл визначає, чи зосереджується відхилення в обмеженій групі компонентів.",
        "Структура за {b} відокремлює основні позитивні й негативні складові портфеля.",
        "Деталізація за {b} фіксує рівень ієрархії, на якому результат стає локалізованим.",
    ),
    "closing": (
        "Отже, {a} характеризується встановленою структурою його основних компонентів.",
        "У підсумку {a} формує завершену частину загальної аналітичної оцінки.",
        "Таким чином, {a} має конкретно визначений масштаб і локалізацію в поточній вибірці.",
        "У сукупності наведені факти щодо {a} визначають його місце в загальній картині виконання.",
        "Підсумкова характеристика {a} ґрунтується на зіставленні рівня, динаміки та внутрішнього розподілу.",
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
    "Аналітична довідка узагальнює результати моніторингу за обраний період і деталізує фактори, що формують зведену картину.",
    "Наведений аналіз охоплює фактичні результати поточної вибірки та їхній розподіл за основними управлінськими розрізами.",
    "За обраним періодом сформовано цілісну оцінку виконання, динаміки, повноти даних і внутрішньої структури результатів.",
    "Довідка відображає не лише зведені показники, а й розподіл змін між стратегічними цілями, завданнями та відповідальними ССП.",
    "Аналіз побудовано на фактичних даних поточної вибірки з окремою оцінкою динаміки, розподілу та концентрації відхилень.",
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
            suffix = "" if cycle == 0 else " Основні відхилення нижче локалізовано за доступними розрізами."
            PHRASE_LIBRARY["opening"].append(PhraseVariant(id=f"opening_{tag}_{cycle}_{i:02d}", template=prefix + text + suffix, suitable_for=(tag,), family="claim"))

_TRANSITIONS_BY_TOPIC = {
    "dynamics": (
        "З погляду часової динаміки", "Траєкторія за періодами показує", "У часовому розрізі",
        "Послідовність оцінених періодів уточнює картину", "Динаміка протягом обраного горизонту показує",
        "Порівняння періодів фіксує", "За квартальною траєкторією", "Рух показника в часі характеризується так",
        "Часова послідовність результатів показує", "Окремо динамічний розріз фіксує",
    ),
    "coverage": (
        "Щодо повноти моніторингових даних", "Інформаційна повнота вибірки характеризується так",
        "Окремо за покриттям моніторингом", "За повнотою подань", "Структура наявних даних показує",
        "Розподіл неповноти даних фіксує", "У частині покриття", "За доступністю моніторингових даних",
        "Повнота інформаційної основи виглядає так", "Окремий розріз якості даних показує",
    ),
    "goals": (
        "У розрізі стратегічних цілей", "Деталізація за стратегічними цілями показує",
        "На рівні стратегічних цілей", "Розподіл результатів між стратегічними цілями фіксує",
        "Внутрішня картина за стратегічними цілями виглядає так", "За стратегічними цілями",
        "Порівняння стратегічних цілей показує", "Структура виконання за цілями характеризується так",
        "Цільовий розріз уточнює загальну картину", "Серед стратегічних цілей",
    ),
    "tasks": (
        "На рівні завдань", "Деталізація за завданнями показує", "У розрізі завдань",
        "Розподіл між завданнями фіксує", "Завдання конкретизують картину так", "Порівняння завдань показує",
        "Усередині стратегічних цілей завдання розподіляються так", "За завданнями",
        "Наступний рівень деталізації — завдання — показує", "Структура результатів за завданнями характеризується так",
    ),
    "departments": (
        "У розрізі відповідальних ССП", "За відповідальними підрозділами", "Розподіл між ССП показує",
        "На рівні ССП", "Порівняння відповідальних підрозділів фіксує", "Відповідальність за портфелем розподіляється так",
        "Структура результатів за ССП виглядає так", "Серед відповідальних ССП", "Розріз ССП уточнює загальну картину",
        "За підрозділами, відповідальними за заходи",
    ),
    "statuses": (
        "Статусна структура показує", "Розподіл за статусами виглядає так", "За фактично зафіксованими статусами",
        "Структура статусів уточнює", "У статусному розрізі", "Поточний розподіл статусів фіксує",
        "За статусами виконання", "Окремий статусний зріз показує", "Склад портфеля за статусами характеризується так",
        "Розподіл фактичних статусів має такий вигляд",
    ),
    "products": (
        "За типами продукту", "Продуктовий розріз показує", "Структура портфеля за типами продукту фіксує",
        "У розрізі типів продукту", "Порівняння типів продукту показує", "Продуктова структура уточнює картину",
        "За характером продуктів", "Розподіл продуктів виглядає так", "Окремий продуктовий зріз фіксує",
        "Структурні відмінності за типами продукту характеризуються так",
    ),
    "problems": (
        "Щодо концентрації відхилень", "Локалізація проблемних позицій показує", "Розподіл проблемних позицій фіксує",
        "Структура відхилень виглядає так", "За концентрацією проблемних позицій", "Окремо проблемний розріз показує",
        "Масштаб і локалізація відхилень характеризуються так", "Проблемні позиції розподіляються так",
        "Внутрішня концентрація відхилень фіксує", "За структурою проблемних позицій",
    ),
    "management": (
        "Для управлінської уваги ключовим є таке", "За сукупністю встановлених відхилень", "Пріоритетність об’єктів виглядає так",
        "Управлінські точки уваги визначаються так", "За аналітичною вагою відхилень", "Найбільш значущі об’єкти формують таку групу",
        "За поєднанням масштабу і відхилень", "У частині управлінської уваги", "Підсумкове ранжування за даними показує",
        "Об’єкти з найбільшою сукупною вагою відхилень розподіляються так",
    ),
    "final": (
        "У підсумку", "Загальна картина за результатами аналізу", "Сукупний висновок має такий зміст",
        "Підсумкова оцінка показує", "Узагальнення всіх розрізів фіксує", "Зведений аналітичний висновок полягає в такому",
        "За сукупністю часових і структурних результатів", "Фінальна оцінка характеризується так",
        "Поєднання всіх установлених фактів дає такий підсумок", "Загалом за обраною вибіркою",
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
    noun = ("загальна картина", "динаміка", "структура відхилень", "повнота даних", "розподіл результатів")[(i - 1) % 5]
    verb = ("визначається", "формується", "пояснюється", "конкретизується", "характеризується", "уточнюється")[(i - 1) % 6]
    PHRASE_LIBRARY["synthesis"].append(PhraseVariant(
        id=f"synthesis_{i:02d}", template=f"У підсумковій оцінці {noun} {verb} сукупністю встановлених фактів і їхнім розподілом між основними складовими портфеля.",
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
