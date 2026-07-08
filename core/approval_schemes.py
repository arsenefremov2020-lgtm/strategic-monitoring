# core/approval_schemes.py

"""
Схеми погодження заявок моніторингу.

Концепція:
- подавач (ССП) при поданні обирає СХЕМУ — фіксований порядок ланок
  погодження — і КОНКРЕТНИХ осіб для кожної ланки свого ССП;
- координатор (адміністратор) є ОБОВʼЯЗКОВОЮ ланкою в кожній схемі
  (може бути не першим, але без нього заявка не пройде);
- адміністратор може підтвердити або змінити схему — зміна логуються;
- кожна ланка може повернути заявку: подавачу або на будь-яку
  попередню ланку (на вибір).

Ланцюг зберігається в monitoring_requests.approval_chain як JSON-рядок:
    [{"role": "admin", "label": "Координатор",
      "email": "...", "name": "..."}, ...]
chain_stage — індекс ПОТОЧНОЇ ланки, що очікує рішення.

Статуси approval_status синхронізовані з ланцюгом так, щоб
успадкований код (Dashboard, статистика, email-дайджести) продовжував
працювати без змін:
    admin      → "Очікує погодження"        (успадкований статус координатора)
    ssp_head   → "Очікує: Керівник ССП"     (ланка керівника ССП)
    unit_head  → "Очікує: Керівник управління"
    ssp_deputy → "Очікує: Заступник керівника ССП"
    завершено  → "Погоджено"
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from config.roles import (
    ROLE_SSP,
    ROLE_ADMIN,
    ROLE_SSP_HEAD,
    ROLE_UNIT_HEAD,
    ROLE_SSP_DEPUTY,
    ROLE_SUPER_ADMIN,
)


# ------------------------------------------------------------
# Ланки
# ------------------------------------------------------------

STAGE_LABELS = {
    ROLE_ADMIN:      "Координатор",
    ROLE_UNIT_HEAD:  "Керівник управління",
    ROLE_SSP_DEPUTY: "Заступник керівника ССП",
    ROLE_SSP_HEAD:   "Керівник ССП",
}

STAGE_WAITING_STATUS = {
    ROLE_ADMIN:      "Очікує погодження",
    ROLE_SSP_HEAD:   "Очікує: Керівник ССП",
    ROLE_UNIT_HEAD:  "Очікує: Керівник управління",
    ROLE_SSP_DEPUTY: "Очікує: Заступник керівника ССП",
}

APPROVED_STATUS = "Погоджено"
RETURNED_STATUS = "Повернуто на доопрацювання"

# Статуси, за яких заявка «у процесі погодження» (для фільтрів/кабінетів)
ALL_WAITING_STATUSES = list(STAGE_WAITING_STATUS.values())


# ------------------------------------------------------------
# Каталог схем (фіксований; координатор — обовʼязковий у кожній)
# ------------------------------------------------------------

APPROVAL_SCHEMES: dict[str, list[str]] = {
    "Координатор → Керівник ССП":
        [ROLE_ADMIN, ROLE_SSP_HEAD],
    "Координатор → Керівник управління":
        [ROLE_ADMIN, ROLE_UNIT_HEAD],
    "Координатор → Заступник керівника ССП":
        [ROLE_ADMIN, ROLE_SSP_DEPUTY],
    "Координатор → Керівник управління → Керівник ССП":
        [ROLE_ADMIN, ROLE_UNIT_HEAD, ROLE_SSP_HEAD],
    "Координатор → Заступник керівника ССП → Керівник ССП":
        [ROLE_ADMIN, ROLE_SSP_DEPUTY, ROLE_SSP_HEAD],
    "Координатор → Керівник управління → Заступник → Керівник ССП":
        [ROLE_ADMIN, ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY, ROLE_SSP_HEAD],
    "Керівник управління → Координатор → Керівник ССП":
        [ROLE_UNIT_HEAD, ROLE_ADMIN, ROLE_SSP_HEAD],
    "Заступник керівника ССП → Координатор → Керівник ССП":
        [ROLE_SSP_DEPUTY, ROLE_ADMIN, ROLE_SSP_HEAD],
    "Керівник управління → Заступник → Координатор → Керівник ССП":
        [ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY, ROLE_ADMIN, ROLE_SSP_HEAD],

    # Єдина схема для випадків, коли подавач сам є однією з ланок
    # погодження (керівник ССП / керівник управління / заступник):
    # немає сенсу, щоб особа погоджувала саму себе, тож маршрут
    # звужується рівно до обов'язкової ланки координатора.
    "Координатор (без додаткових ланок)":
        [ROLE_ADMIN],
}

DEFAULT_SCHEME = "Координатор → Керівник ССП"

# Схема, яка застосовується примусово (без вибору), коли заявку подає
# роль, що сама фігурує серед ланок погодження.
SUBMITTER_SELF_APPROVAL_SCHEME = "Координатор (без додаткових ланок)"


def scheme_options() -> list[str]:
    return list(APPROVAL_SCHEMES.keys())


def submitter_is_approving_role(role: str) -> bool:
    """
    Чи є роль подавача однією з тих, що самі можуть бути ланкою
    погодження (керівник ССП / керівник управління / заступник).

    Для звичайного «Відповідального від ССП» (ROLE_SSP) — False,
    для нього діють усі схеми без обмежень.
    """
    return role in (ROLE_SSP_HEAD, ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY)


def _approval_role_rank(role: str) -> int:
    """
    Ієрархія для перевірки, що подавач не створює маршрут нижче себе.

    Організаційна вертикаль погодження (ТЗ DEMO 1.9):
        координатор → керівник управління → заступник керівника ССП →
        керівник ССП.
    Тобто заступник керівника ССП СТОЇТЬ ВИЩЕ за керівника управління —
    раніше вони помилково вважалися рівними, і заступник міг обрати
    маршрут із «нижчою» ланкою керівника управління.
    """
    if role == ROLE_ADMIN:
        return 0
    if role == ROLE_UNIT_HEAD:
        return 1
    if role == ROLE_SSP_DEPUTY:
        return 2
    if role == ROLE_SSP_HEAD:
        return 3
    if role == ROLE_SUPER_ADMIN:
        return 4
    return -1


def _scheme_has_required_coordinator(roles: list[str]) -> bool:
    return ROLE_ADMIN in roles and roles[-1] != ROLE_ADMIN


def scheme_options_for_submitter(role: str) -> list[str]:
    """
    Повертає список схем, доступних подавачу DEMO 1.9.

    Правила ТЗ:
    - координатор обов'язковий у кожній схемі;
    - координатор не може бути останньою ланкою, крім спеціального випадку,
      коли дані подає керівник ССП;
    - подавач-ланка погодження не може створити маршрут нижче себе;
    - керівник ССП подає тільки через координатора.
    """
    role = str(role or "").strip()

    if role == ROLE_SSP_HEAD:
        return [SUBMITTER_SELF_APPROVAL_SCHEME]

    if role == ROLE_SSP:
        return [
            name for name, roles in APPROVAL_SCHEMES.items()
            if _scheme_has_required_coordinator(roles)
        ]

    if role in (ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY):
        submitter_rank = _approval_role_rank(role)
        options: list[str] = []
        for name, roles in APPROVAL_SCHEMES.items():
            if not _scheme_has_required_coordinator(roles):
                continue
            # Не дозволяємо маршрути, де є ланка, НИЖЧА за подавача,
            # а також маршрути, що містять САМОГО подавача як ланку
            # (особа не може погоджувати власне подання).
            ranked_roles = [r for r in roles if r in (ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY, ROLE_SSP_HEAD)]
            if any(_approval_role_rank(r) < submitter_rank for r in ranked_roles):
                continue
            if role in ranked_roles:
                continue
            options.append(name)
        return options or [SUBMITTER_SELF_APPROVAL_SCHEME]

    return scheme_options()


# ------------------------------------------------------------
# Побудова та читання ланцюга
# ------------------------------------------------------------

def build_chain(scheme_name: str, persons: dict[str, dict]) -> list[dict]:
    """
    Будує ланцюг для схеми.

    persons: {role: {"email": ..., "name": ...}} — конкретні особи,
    обрані подавачем (або адміністратором при зміні схеми).
    """
    roles = APPROVAL_SCHEMES.get(scheme_name, APPROVAL_SCHEMES[DEFAULT_SCHEME])
    chain = []
    for role in roles:
        person = persons.get(role, {}) or {}
        chain.append({
            "role": role,
            "label": STAGE_LABELS.get(role, role),
            "email": str(person.get("email") or "").strip().lower(),
            "name": str(person.get("name") or "").strip(),
        })
    return chain


def chain_to_json(chain: list[dict]) -> str:
    return json.dumps(chain, ensure_ascii=False)


def parse_chain(raw) -> list[dict]:
    """Безпечно парсить approval_chain із бази (JSON-рядок або список)."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    text = str(raw).strip()
    if not text or text.lower() in ("nan", "none", "null"):
        return []
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def parse_stage(raw) -> int:
    try:
        value = int(float(str(raw)))
        return max(value, 0)
    except Exception:
        return 0


def current_stage(chain: list[dict], stage_idx: int) -> dict | None:
    if not chain:
        return None
    if 0 <= stage_idx < len(chain):
        return chain[stage_idx]
    return None


def waiting_status_for_stage(stage: dict | None) -> str:
    if not stage:
        return APPROVED_STATUS
    return STAGE_WAITING_STATUS.get(stage.get("role"), f"Очікує: {stage.get('label', '')}")


def status_after_approve(chain: list[dict], stage_idx: int) -> tuple[str, int]:
    """Статус і новий chain_stage після погодження поточною ланкою."""
    next_idx = stage_idx + 1
    next_stage = current_stage(chain, next_idx)
    if next_stage is None:
        return APPROVED_STATUS, next_idx
    return waiting_status_for_stage(next_stage), next_idx


# ------------------------------------------------------------
# Остаточне закриття заявки (final_locked)
# ------------------------------------------------------------
#
# Правило: щойно ОСТАННЯ ланка схеми погодила заявку — вона закрита
# НАЗАВЖДИ для звичайних дій застосунку (зокрема для зміни/перепризначення
# схеми погодження адміністратором). Це не залежить від того, що станеться
# зі схемою пізніше: final_locked виставляється ОДИН РАЗ і більше жодна
# функція застосунку його не знімає.
#
# Додатково те саме гарантує тригер бази даних (див. migrations/010_final_lock.sql),
# який фізично забороняє зміну approval_status / chain_stage / approval_chain
# для рядка з final_locked = true — незалежно від того, з якого коду
# прийшов запит на зміну.
#
# Право редагувати ДАНІ (не маршрут) уже закритої заявки має лише
# супер-адмін — окремим, явним і аудованим шляхом (див. core/superadmin_edit.py,
# наступна ітерація), який final_locked не знімає.

def finalize_update_payload(update_data: dict, new_status: str) -> dict:
    """
    Додає до payload оновлення заявки позначку остаточного закриття,
    якщо new_status — це APPROVED_STATUS ("Погоджено").

    ВАЖЛИВО: усі місця коду, які виставляють approval_status="Погоджено"
    (координатор у 3_Адміністрування.py, інші ланки у 1_Мій_кабінет.py),
    мають пропускати свій update-словник через цю функцію — так є
    рівно ОДНЕ місце, де вирішується "заявку закрито остаточно чи ні".
    """
    data = dict(update_data)
    if new_status == APPROVED_STATUS:
        data["final_locked"] = True
        data["final_locked_at"] = datetime.now(timezone.utc).isoformat()
    return data


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in ("true", "1", "t", "yes", "так")


def is_final_locked(row) -> bool:
    """
    Чи заявку остаточно закрито (final_locked).

    Читає колонку final_locked, якщо вона є в рядку. Якщо міграція
    010_final_lock.sql ще не застосована (колонки немає) — фолбек на
    порівняння approval_status == "Погоджено", щоб код не падав і
    поводився принаймні як раніше, доки міграцію не накатили.
    """
    has_col = False
    try:
        has_col = "final_locked" in row.index
    except AttributeError:
        try:
            has_col = "final_locked" in row
        except TypeError:
            has_col = False

    if has_col:
        value = row.get("final_locked") if hasattr(row, "get") else row["final_locked"]
        if value is not None and str(value).strip() not in ("", "none", "nan", "None"):
            return _truthy(value)

    approval_status = row.get("approval_status") if hasattr(row, "get") else row["approval_status"]
    return str(approval_status or "").strip() == APPROVED_STATUS


def chain_progress_text(chain: list[dict], stage_idx: int, approval_status: str) -> str:
    """Людський опис прогресу: «Етап 2/3 · очікує: Керівник управління (ПІБ)»."""
    if not chain:
        return ""
    total = len(chain)
    if approval_status == APPROVED_STATUS:
        return f"Схему пройдено повністю ({total}/{total})"
    stage = current_stage(chain, stage_idx)
    if stage is None:
        return f"Етап {min(stage_idx, total)}/{total}"
    who = stage.get("name") or stage.get("email") or ""
    who_part = f" ({who})" if who else ""
    return f"Етап {stage_idx + 1}/{total} · очікує: {stage.get('label','')}{who_part}"


def chain_route_text(chain: list[dict]) -> str:
    """Схема одним рядком: «Координатор (Іваненко) → Керівник ССП (Петренко)»."""
    parts = []
    for stage in chain:
        who = stage.get("name") or stage.get("email") or ""
        parts.append(f"{stage.get('label','')}" + (f" ({who})" if who else ""))
    return " → ".join(parts)


# ------------------------------------------------------------
# Повернення на доопрацювання
# ------------------------------------------------------------

def return_targets(chain: list[dict], stage_idx: int) -> list[dict]:
    """
    Куди поточна ланка може повернути заявку:
    - завжди: подавачу (ССП);
    - плюс будь-яка ПОПЕРЕДНЯ ланка ланцюга.

    Повертає список: {"key": "submitter"|"stage:<i>", "label": ...,
                      "status": ..., "new_stage": int}
    """
    targets = [{
        "key": "submitter",
        "label": "Подавачу (відповідальній особі ССП)",
        "status": RETURNED_STATUS,
        "new_stage": 0,
    }]
    for i in range(stage_idx):
        stage = chain[i]
        who = stage.get("name") or stage.get("email") or ""
        who_part = f" ({who})" if who else ""
        targets.append({
            "key": f"stage:{i}",
            "label": f"{stage.get('label','')}{who_part}",
            "status": waiting_status_for_stage(stage),
            "new_stage": i,
        })
    return targets


# ------------------------------------------------------------
# Кандидати на ланки для конкретного ССП
# ------------------------------------------------------------

def _admin_covers_ssp(user: dict, ssp_index: str) -> bool:
    """Чи закріплений адміністратор саме за цим ССП як КООРДИНАТОР.

    Береться окреме поле coordinator_ssp_indexes — конкретні ССП з таблиці.
    Широкий доступ '*' (у власника/супер-адміна) НЕ робить його
    координатором усіх підрозділів: інакше «універсальний» адмін ставав
    координатором геть усіх ССП, зокрема чужих.
    """
    ssp_index = str(ssp_index or "").strip()
    if not ssp_index:
        return False
    coord = [str(a).strip() for a in (user.get("coordinator_ssp_indexes") or [])]
    if coord:
        return ssp_index in coord
    # Фолбек для сумісності зі старими записами без нового поля:
    # явний перелік allowed без '*'.
    allowed = [str(a).strip() for a in (user.get("allowed_ssp_indexes") or [])]
    own = str(user.get("ssp_index") or "").strip()
    if "*" in allowed:
        return ssp_index == own
    return ssp_index == own or ssp_index in allowed


def _user_matches_ssp(user: dict, ssp_index: str) -> bool:
    allowed = user.get("allowed_ssp_indexes") or []
    if "*" in allowed:
        return True
    own = str(user.get("ssp_index") or "")
    return own == str(ssp_index) or str(ssp_index) in [str(a) for a in allowed]


def stage_candidates(role: str, ssp_index: str) -> list[dict]:
    """
    Повертає активних користувачів-кандидатів на ланку для ССП:
    [{"email": ..., "name": ..., "extra": unit_name}]

    Для координатора — адміністратори, за якими закріплений цей ССП
    (якщо таких немає — усі адміністратори), плюс супер-адміни.
    """
    from config.users import get_users_by_role  # локальний імпорт (уникнення циклів)

    ssp_index = str(ssp_index or "").strip()
    result: list[dict] = []

    if role == ROLE_ADMIN:
        # Координатор — РІВНО той адміністратор, за яким закріплений цей ССП
        # (за колонкою доступів). Ніякого фолбеку «усі адміністратори» і
        # без домішування супер-адмінів: інакше у відповідального ССП
        # з'являвся вибір адміна, а ССП міг піти не до свого координатора.
        admins = list(get_users_by_role(ROLE_ADMIN).values())
        pool = [u for u in admins if _admin_covers_ssp(u, ssp_index)]
    else:
        pool = [
            u for u in get_users_by_role(role).values()
            if not ssp_index or _user_matches_ssp(u, ssp_index)
        ]

    seen = set()
    for user in pool:
        email = str(user.get("email") or "").lower()
        if not email or email in seen:
            continue
        seen.add(email)
        result.append({
            "email": email,
            "name": user.get("full_name") or email,
            "extra": str(user.get("unit_name") or ""),
        })
    return result


def candidate_label(candidate: dict) -> str:
    extra = candidate.get("extra") or ""
    return candidate["name"] + (f" — {extra}" if extra else "")


# ------------------------------------------------------------
# НОВА МОДЕЛЬ МАРШРУТУ (виправлення після тестування, липень 2026)
# ------------------------------------------------------------
#
# Раніше маршрут ПОВНІСТЮ будувався наперед — подавач (чи адмін при зміні
# схеми) визначав усі ланки одразу, включно з тими, кого ще навіть не
# розглядав жоден координатор. Це призводило до збою: координатор міг
# натиснути "погодити" за ланку, чия черга ще не настала (бо ланцюг уже
# містив цю ланку наперед), і заявка стрибала на наступний етап "повз"
# фактичного власника черги.
#
# Тепер маршрут будується ПОКРОКОВО: кожна заявка завжди починається
# рівно з координатора (initial_chain). Коли підходить черга ланки —
# САМЕ вона (а не подавач і не будь-хто інший) вирішує, що далі:
# завершити заявку на собі, чи призначити наступною ланкою когось
# СТАРШОГО за себе (не може "спуститися нижче себе" чи повернути на вже
# пройдений рівень). Ієрархія:
#   Координатор -> {Керівник управління, Заступник керівника ССП} -> Керівник ССП
# Координатор може призначити будь-яку з трьох ролей далі (або завершити
# сам). Керівник управління/Заступник можуть призначити далі лише
# Керівника ССП (або завершити самі). Керівник ССП — завжди останній.

ROLE_RANK: dict[str, int] = {
    ROLE_UNIT_HEAD: 1,
    ROLE_SSP_DEPUTY: 1,
    ROLE_SSP_HEAD: 2,
}


def initial_chain(ssp_index: str) -> list[dict]:
    """
    Ланцюг заявки одразу після подання: РІВНО одна ланка — координатор,
    закріплений за цим ССП. Порожній список, якщо координатора не
    знайдено (подання тоді неможливе — це перевіряється у формі подання).
    """
    candidates = stage_candidates(ROLE_ADMIN, ssp_index)
    if not candidates:
        return []
    c = candidates[0]
    return [{
        "role": ROLE_ADMIN,
        "label": STAGE_LABELS[ROLE_ADMIN],
        "email": c["email"],
        "name": c["name"],
    }]


def next_stage_role_options(current_role: str) -> list[str]:
    """
    Ролі, які поточна ланка (current_role) МОЖЕ призначити наступною.
    Координатор — будь-яку з трьох. Керівник управління/Заступник —
    лише Керівника ССП (єдина роль старша за них). Керівник ССП —
    нікого (він завжди останній, вище нікого немає).
    """
    if current_role == ROLE_ADMIN:
        return [ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY, ROLE_SSP_HEAD]
    current_rank = ROLE_RANK.get(current_role, 99)
    return [role for role, rank in ROLE_RANK.items() if rank > current_rank]


def is_stage_role(chain: list[dict], stage_idx: int, role: str) -> bool:
    """Чи належить ПОТОЧНА ланка ланцюга саме цій ролі (перевірка "чи моя черга")."""
    stage = current_stage(chain, stage_idx)
    return bool(stage) and stage.get("role") == role


def append_stage(chain: list[dict], next_role: str, ssp_index: str,
                  person: dict | None = None) -> list[dict] | None:
    """
    Додає нову ланку в кінець ланцюга і повертає НОВИЙ ланцюг (список).
    person — конкретна обрана особа {"email":..., "name":...}, якщо
    кандидатів на роль було кілька і хтось уже обрав; якщо не передано —
    береться перший (єдиний) кандидат. None, якщо кандидатів немає.
    """
    if person and person.get("email"):
        chosen = person
    else:
        candidates = stage_candidates(next_role, ssp_index)
        if not candidates:
            return None
        chosen = candidates[0]
    new_chain = list(chain)
    new_chain.append({
        "role": next_role,
        "label": STAGE_LABELS.get(next_role, next_role),
        "email": str(chosen.get("email") or "").strip().lower(),
        "name": str(chosen.get("name") or "").strip(),
    })
    return new_chain


def finalize_here(stage_idx: int) -> tuple[str, int]:
    """Поточна ланка стає останньою — заявку погоджено остаточно."""
    return APPROVED_STATUS, stage_idx + 1


def advance_with_new_stage(chain: list[dict], stage_idx: int, next_role: str,
                           ssp_index: str, person: dict | None = None):
    """
    Додає next_role як наступну ланку одразу після поточної й повертає
    (new_chain, new_status, new_stage_idx). (None, None, None), якщо для
    next_role немає жодного кандидата (наприклад, для цього ССП не
    призначено такої ролі).
    """
    new_chain = append_stage(chain, next_role, ssp_index, person)
    if new_chain is None:
        return None, None, None
    new_stage = current_stage(new_chain, stage_idx + 1)
    return new_chain, waiting_status_for_stage(new_stage), stage_idx + 1
