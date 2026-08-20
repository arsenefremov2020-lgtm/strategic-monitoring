from __future__ import annotations

from typing import Mapping


# Controlled grammatical forms for recurring system entities. Official/free-form
# department names are intentionally not declined automatically.
ENTITY_FORMS: dict[str, Mapping[str, str]] = {
    "measure": {
        "one": "захід", "few": "заходи", "many": "заходів",
        "nom_sg": "захід", "gen_sg": "заходу", "dat_sg": "заходу", "acc_sg": "захід", "ins_sg": "заходом", "loc_sg": "заході",
        "nom_pl": "заходи", "gen_pl": "заходів", "dat_pl": "заходам", "acc_pl": "заходи", "ins_pl": "заходами", "loc_pl": "заходах",
    },
    "goal": {
        "one": "стратегічна ціль", "few": "стратегічні цілі", "many": "стратегічних цілей",
        "nom_sg": "стратегічна ціль", "gen_sg": "стратегічної цілі", "dat_sg": "стратегічній цілі", "acc_sg": "стратегічну ціль", "ins_sg": "стратегічною ціллю", "loc_sg": "стратегічній цілі",
        "nom_pl": "стратегічні цілі", "gen_pl": "стратегічних цілей", "dat_pl": "стратегічним цілям", "acc_pl": "стратегічні цілі", "ins_pl": "стратегічними цілями", "loc_pl": "стратегічних цілях",
    },
    "task": {
        "one": "завдання", "few": "завдання", "many": "завдань",
        "nom_sg": "завдання", "gen_sg": "завдання", "dat_sg": "завданню", "acc_sg": "завдання", "ins_sg": "завданням", "loc_sg": "завданні",
        "nom_pl": "завдання", "gen_pl": "завдань", "dat_pl": "завданням", "acc_pl": "завдання", "ins_pl": "завданнями", "loc_pl": "завданнях",
    },
    "record": {
        "one": "запис", "few": "записи", "many": "записів",
        "nom_sg": "запис", "gen_sg": "запису", "dat_sg": "запису", "acc_sg": "запис", "ins_sg": "записом", "loc_sg": "записі",
        "nom_pl": "записи", "gen_pl": "записів", "dat_pl": "записам", "acc_pl": "записи", "ins_pl": "записами", "loc_pl": "записах",
    },
    "submission": {
        "one": "подання", "few": "подання", "many": "подань",
        "nom_sg": "подання", "gen_sg": "подання", "dat_sg": "поданню", "acc_sg": "подання", "ins_sg": "поданням", "loc_sg": "поданні",
        "nom_pl": "подання", "gen_pl": "подань", "dat_pl": "поданням", "acc_pl": "подання", "ins_pl": "поданнями", "loc_pl": "поданнях",
    },
    "department": {
        "one": "підрозділ", "few": "підрозділи", "many": "підрозділів",
        "nom_sg": "підрозділ", "gen_sg": "підрозділу", "dat_sg": "підрозділу", "acc_sg": "підрозділ", "ins_sg": "підрозділом", "loc_sg": "підрозділі",
        "nom_pl": "підрозділи", "gen_pl": "підрозділів", "dat_pl": "підрозділам", "acc_pl": "підрозділи", "ins_pl": "підрозділами", "loc_pl": "підрозділах",
    },
    "quarter": {
        "one": "квартал", "few": "квартали", "many": "кварталів",
        "nom_sg": "квартал", "gen_sg": "кварталу", "dat_sg": "кварталу", "acc_sg": "квартал", "ins_sg": "кварталом", "loc_sg": "кварталі",
        "nom_pl": "квартали", "gen_pl": "кварталів", "dat_pl": "кварталам", "acc_pl": "квартали", "ins_pl": "кварталами", "loc_pl": "кварталах",
    },
    "year": {
        "one": "рік", "few": "роки", "many": "років",
        "nom_sg": "рік", "gen_sg": "року", "dat_sg": "року", "acc_sg": "рік", "ins_sg": "роком", "loc_sg": "році",
        "nom_pl": "роки", "gen_pl": "років", "dat_pl": "рокам", "acc_pl": "роки", "ins_pl": "роками", "loc_pl": "роках",
    },
    "indicator": {
        "one": "індикатор", "few": "індикатори", "many": "індикаторів",
        "nom_sg": "індикатор", "gen_sg": "індикатора", "dat_sg": "індикатору", "acc_sg": "індикатор", "ins_sg": "індикатором", "loc_sg": "індикаторі",
        "nom_pl": "індикатори", "gen_pl": "індикаторів", "dat_pl": "індикаторам", "acc_pl": "індикатори", "ins_pl": "індикаторами", "loc_pl": "індикаторах",
    },
    "result": {
        "one": "результат", "few": "результати", "many": "результатів",
        "nom_sg": "результат", "gen_sg": "результату", "dat_sg": "результату", "acc_sg": "результат", "ins_sg": "результатом", "loc_sg": "результаті",
        "nom_pl": "результати", "gen_pl": "результатів", "dat_pl": "результатам", "acc_pl": "результати", "ins_pl": "результатами", "loc_pl": "результатах",
    },
    "status": {
        "one": "статус", "few": "статуси", "many": "статусів",
        "nom_sg": "статус", "gen_sg": "статусу", "dat_sg": "статусу", "acc_sg": "статус", "ins_sg": "статусом", "loc_sg": "статусі",
        "nom_pl": "статуси", "gen_pl": "статусів", "dat_pl": "статусам", "acc_pl": "статуси", "ins_pl": "статусами", "loc_pl": "статусах",
    },
    "signal": {
        "one": "сигнал", "few": "сигнали", "many": "сигналів",
        "nom_sg": "сигнал", "gen_sg": "сигналу", "dat_sg": "сигналу", "acc_sg": "сигнал", "ins_sg": "сигналом", "loc_sg": "сигналі",
        "nom_pl": "сигнали", "gen_pl": "сигналів", "dat_pl": "сигналам", "acc_pl": "сигнали", "ins_pl": "сигналами", "loc_pl": "сигналах",
    },
    "risk": {
        "one": "ризик", "few": "ризики", "many": "ризиків",
        "nom_sg": "ризик", "gen_sg": "ризику", "dat_sg": "ризику", "acc_sg": "ризик", "ins_sg": "ризиком", "loc_sg": "ризику",
        "nom_pl": "ризики", "gen_pl": "ризиків", "dat_pl": "ризикам", "acc_pl": "ризики", "ins_pl": "ризиками", "loc_pl": "ризиках",
    },
    "period": {
        "one": "період", "few": "періоди", "many": "періодів",
        "nom_sg": "період", "gen_sg": "періоду", "dat_sg": "періоду", "acc_sg": "період", "ins_sg": "періодом", "loc_sg": "періоді",
        "nom_pl": "періоди", "gen_pl": "періодів", "dat_pl": "періодам", "acc_pl": "періоди", "ins_pl": "періодами", "loc_pl": "періодах",
    },
}


def plural_form_uk(n: int, one: str, few: str, many: str) -> str:
    n_abs = abs(int(n))
    last_two = n_abs % 100
    last = n_abs % 10
    if 11 <= last_two <= 14:
        return many
    if last == 1:
        return one
    if 2 <= last <= 4:
        return few
    return many


def plural_uk(n: int, entity: str) -> str:
    forms = ENTITY_FORMS[entity]
    return plural_form_uk(n, forms["one"], forms["few"], forms["many"])


def count_uk(n: int, entity: str) -> str:
    return f"{int(n)} {plural_uk(int(n), entity)}"


def entity_form_uk(entity: str, case: str = "nom", *, plural: bool = False) -> str:
    """Return a controlled case form for a system entity.

    Supported cases: nom, gen, dat, acc, ins, loc. This is intentionally a
    dictionary for known system terms rather than an unsafe declension engine for
    arbitrary official names.
    """
    key = f"{case}_{'pl' if plural else 'sg'}"
    try:
        return ENTITY_FORMS[entity][key]
    except KeyError as exc:
        raise ValueError(f"Unsupported morphology form: entity={entity!r}, case={case!r}, plural={plural}") from exc


def count_case_uk(n: int, entity: str, case: str = "nom") -> str:
    """Return a number with a case-aware controlled entity form.

    For nominative/accusative counting, Ukrainian numeral agreement uses the
    familiar one/few/many forms. For oblique cases, singular is used only for 1;
    other numerals use the corresponding plural case form.
    """
    n_int = int(n)
    if case in {"nom", "acc"}:
        return count_uk(n_int, entity)
    singular = abs(n_int) % 10 == 1 and abs(n_int) % 100 != 11
    return f"{n_int} {entity_form_uk(entity, case, plural=not singular)}"


def verb_uk(n: int, singular: str, plural: str) -> str:
    return singular if abs(int(n)) % 10 == 1 and abs(int(n)) % 100 != 11 else plural
