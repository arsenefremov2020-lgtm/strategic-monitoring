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
    ssp_head   → "Направлено на підпис"     (успадкований статус керівника)
    unit_head  → "Очікує: Керівник управління"
    ssp_deputy → "Очікує: Заступник керівника ССП"
    завершено  → "Погоджено"
"""

from __future__ import annotations

import json

from config.roles import (
    ROLE_ADMIN,
    ROLE_SSP_HEAD,
    ROLE_UNIT_HEAD,
    ROLE_SSP_DEPUTY,
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
    ROLE_SSP_HEAD:   "Направлено на підпис",
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
}

DEFAULT_SCHEME = "Координатор → Керівник ССП"


def scheme_options() -> list[str]:
    return list(APPROVAL_SCHEMES.keys())


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
        admins = list(get_users_by_role(ROLE_ADMIN).values())
        supers = list(get_users_by_role("super_admin").values())
        matched = [u for u in admins if _user_matches_ssp(u, ssp_index)]
        pool = (matched or admins) + supers
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
