# core/approval_schemes.py

"""Динамічний маршрут погодження заявок моніторингу.

Ланцюг зберігається в ``monitoring_requests.approval_chain`` як JSON-рядок::

    [{"role": "admin", "label": "Координатор",
      "email": "...", "name": "..."}, ...]

``chain_stage`` — індекс поточної ланки, яка очікує рішення. Нова заявка
завжди починається з єдиної ланки координатора відповідного ССП. Наступні
ланки додаються поступово діями учасників маршруту.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from config.roles import (
    ROLE_ADMIN,
    ROLE_SSP_DEPUTY,
    ROLE_SSP_HEAD,
    ROLE_SUPER_ADMIN,
)


# ------------------------------------------------------------
# Статуси заявки
# ------------------------------------------------------------

STATUS_COORDINATOR_REVIEW = "На розгляді координатора"
STATUS_RETURNED_BY_COORDINATOR = "Повернуто на доопрацювання координатором"
STATUS_RETURNED_BY_MANAGER = "Повернуто на доопрацювання керівником"
STATUS_RETURNED_BY_SUPERADMIN = "Повернуто на доопрацювання супер-адміном"
STATUS_WAITING_MANAGER_SELECTION = "Очікує вибору керівника"
STATUS_SUPERADMIN_REVIEW = "На розгляді супер-адміна"
STATUS_MANAGER_REVIEW = "На розгляді керівника"
APPROVED_STATUS = "Погоджено"

ALL_WAITING_STATUSES = [
    STATUS_COORDINATOR_REVIEW,
    STATUS_WAITING_MANAGER_SELECTION,
    STATUS_SUPERADMIN_REVIEW,
    STATUS_MANAGER_REVIEW,
]

ALL_RETURNED_STATUSES = [
    STATUS_RETURNED_BY_COORDINATOR,
    STATUS_RETURNED_BY_MANAGER,
    STATUS_RETURNED_BY_SUPERADMIN,
]

ALL_APPROVAL_STATUSES = [
    STATUS_COORDINATOR_REVIEW,
    STATUS_RETURNED_BY_COORDINATOR,
    STATUS_RETURNED_BY_MANAGER,
    STATUS_RETURNED_BY_SUPERADMIN,
    STATUS_WAITING_MANAGER_SELECTION,
    STATUS_SUPERADMIN_REVIEW,
    STATUS_MANAGER_REVIEW,
    APPROVED_STATUS,
]


# ------------------------------------------------------------
# Ланки
# ------------------------------------------------------------

STAGE_LABELS = {
    ROLE_ADMIN: "Координатор",
    ROLE_SSP_DEPUTY: "Заступник керівника ССП",
    ROLE_SSP_HEAD: "Керівник ССП",
    ROLE_SUPER_ADMIN: "Супер-адмін",
}

STAGE_WAITING_STATUS = {
    ROLE_ADMIN: STATUS_COORDINATOR_REVIEW,
    ROLE_SSP_DEPUTY: STATUS_MANAGER_REVIEW,
    ROLE_SSP_HEAD: STATUS_MANAGER_REVIEW,
    ROLE_SUPER_ADMIN: STATUS_SUPERADMIN_REVIEW,
}


# ------------------------------------------------------------
# Побудова та читання ланцюга
# ------------------------------------------------------------

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
    return STAGE_WAITING_STATUS.get(
        str(stage.get("role") or "").strip(),
        STATUS_MANAGER_REVIEW,
    )


def status_after_approve(chain: list[dict], stage_idx: int) -> tuple[str, int]:
    """Статус і новий ``chain_stage`` після погодження поточною ланкою."""
    next_idx = stage_idx + 1
    next_stage = current_stage(chain, next_idx)
    if next_stage is not None:
        return waiting_status_for_stage(next_stage), next_idx

    stage = current_stage(chain, stage_idx)
    if stage and str(stage.get("role") or "").strip() == ROLE_ADMIN:
        return STATUS_WAITING_MANAGER_SELECTION, next_idx
    return APPROVED_STATUS, next_idx


def scheme_label_for_chain(chain) -> str:
    """Послідовність назв ланок без прив’язки до каталогу сталих схем."""
    return " → ".join(
        str(
            stage.get("label")
            or STAGE_LABELS.get(stage.get("role"), stage.get("role", ""))
        ).strip()
        for stage in parse_chain(chain)
        if str(stage.get("role") or "").strip()
    )


def chain_route_text(chain: list[dict]) -> str:
    """Маршрут одним рядком: «Координатор (Іваненко) → Керівник ССП»."""
    parts = []
    for stage in chain:
        who = stage.get("name") or stage.get("email") or ""
        parts.append(f"{stage.get('label', '')}" + (f" ({who})" if who else ""))
    return " → ".join(parts)


def chain_progress_text(chain: list[dict], stage_idx: int, approval_status: str) -> str:
    """Людський опис прогресу погодження."""
    if not chain:
        return ""
    total = len(chain)
    if approval_status == APPROVED_STATUS:
        return f"Схему пройдено повністю ({total}/{total})"
    if approval_status == STATUS_WAITING_MANAGER_SELECTION:
        return "Координатор погодив · очікує вибору керівника"
    stage = current_stage(chain, stage_idx)
    if stage is None:
        return f"Етап {min(stage_idx, total)}/{total}"
    who = stage.get("name") or stage.get("email") or ""
    who_part = f" ({who})" if who else ""
    return f"Етап {stage_idx + 1}/{total} · очікує: {stage.get('label', '')}{who_part}"


def first_approval_stage_has_acted(chain, logs) -> bool:
    """Чи зафіксовано хоча б одне рішення першої ланки погодження."""
    parsed = parse_chain(chain)
    if not parsed or logs is None:
        return False
    try:
        if hasattr(logs, "empty") and logs.empty:
            return False
    except Exception:
        pass

    first_waiting_status = waiting_status_for_stage(parsed[0])
    first_stage_role = str(parsed[0].get("role") or "").strip()
    accepted_old_statuses = {first_waiting_status}
    if first_stage_role == ROLE_ADMIN:
        accepted_old_statuses.add("Очікує погодження")
    decision_prefixes = (
        "погодження",
        "повернення",
        "редагування координатором",
        "редагування ланкою",
        "ескалація",
        "зміна схеми погодження",
    )
    if hasattr(logs, "iterrows"):
        rows = (row for _, row in logs.iterrows())
    else:
        try:
            rows = iter(logs)
        except TypeError:
            return False

    for row in rows:
        getter = row.get if hasattr(row, "get") else lambda key, default=None: default
        old_status = str(getter("old_status", "") or "").strip()
        action = str(getter("action", "") or "").strip().casefold()
        if old_status in accepted_old_statuses and action.startswith(decision_prefixes):
            return True
    return False


# ------------------------------------------------------------
# Остаточне закриття заявки (final_locked)
# ------------------------------------------------------------

def finalize_update_payload(update_data: dict, new_status: str) -> dict:
    """Єдина точка додавання ознаки остаточного закриття."""
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
    """Чи заявку остаточно закрито (final_locked)."""
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

    approval_status = (
        row.get("approval_status") if hasattr(row, "get") else row["approval_status"]
    )
    return str(approval_status or "").strip() == APPROVED_STATUS


# ------------------------------------------------------------
# Повернення на доопрацювання
# ------------------------------------------------------------

def returned_status_for_role(role: str) -> str:
    role = str(role or "").strip()
    if role == ROLE_ADMIN:
        return STATUS_RETURNED_BY_COORDINATOR
    if role == ROLE_SUPER_ADMIN:
        return STATUS_RETURNED_BY_SUPERADMIN
    return STATUS_RETURNED_BY_MANAGER


def return_targets(chain: list[dict], stage_idx: int) -> list[dict]:
    """Адресати повернення: подавач і попередні ланки маршруту."""
    current = current_stage(chain, stage_idx)
    current_role = str((current or {}).get("role") or "").strip()
    targets = [{
        "key": "submitter",
        "label": "Подавачу (відповідальній особі ССП)",
        "status": returned_status_for_role(current_role),
        "new_stage": 0,
    }]
    for i in range(stage_idx):
        stage = chain[i]
        who = stage.get("name") or stage.get("email") or ""
        who_part = f" ({who})" if who else ""
        targets.append({
            "key": f"stage:{i}",
            "label": f"{stage.get('label', '')}{who_part}",
            "status": waiting_status_for_stage(stage),
            "new_stage": i,
        })
    return targets


# ------------------------------------------------------------
# Кандидати на ланки для конкретного ССП
# ------------------------------------------------------------

def _admin_covers_ssp(user: dict, ssp_index: str) -> bool:
    """Чи закріплений адміністратор саме за цим ССП як координатор."""
    ssp_index = str(ssp_index or "").strip()
    if not ssp_index:
        return False
    coord = [str(a).strip() for a in (user.get("coordinator_ssp_indexes") or [])]
    if coord:
        return ssp_index in coord
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
    """Активні користувачі-кандидати на конкретну ланку для ССП."""
    from config.users import get_users_by_role  # локальний імпорт без циклу

    ssp_index = str(ssp_index or "").strip()
    if role == ROLE_ADMIN:
        admins = list(get_users_by_role(ROLE_ADMIN).values())
        pool = [user for user in admins if _admin_covers_ssp(user, ssp_index)]
    else:
        pool = [
            user
            for user in get_users_by_role(role).values()
            if not ssp_index or _user_matches_ssp(user, ssp_index)
        ]

    result: list[dict] = []
    seen = set()
    for user in pool:
        email = str(user.get("email") or "").strip().lower()
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
# Динамічне формування маршруту
# ------------------------------------------------------------

def initial_chain(ssp_index: str) -> list[dict]:
    """Стартовий маршрут: єдина ланка координатора відповідного ССП."""
    candidates = stage_candidates(ROLE_ADMIN, ssp_index)
    if not candidates:
        return []
    coordinator = candidates[0]
    return [{
        "role": ROLE_ADMIN,
        "label": STAGE_LABELS[ROLE_ADMIN],
        "email": coordinator["email"],
        "name": coordinator["name"],
    }]


def is_stage_role(chain: list[dict], stage_idx: int, role: str) -> bool:
    """Чи належить поточна ланка заданій ролі."""
    stage = current_stage(chain, stage_idx)
    return bool(stage) and stage.get("role") == role


def append_stage(
    chain: list[dict],
    next_role: str,
    ssp_index: str,
    person: dict | None = None,
) -> list[dict] | None:
    """Додає нову ланку в кінець маршруту."""
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


def advance_with_new_stage(
    chain: list[dict],
    stage_idx: int,
    next_role: str,
    ssp_index: str,
    person: dict | None = None,
):
    """Додає наступну ланку й переводить заявку на неї."""
    new_chain = append_stage(chain, next_role, ssp_index, person)
    if new_chain is None:
        return None, None, None
    new_stage = current_stage(new_chain, stage_idx + 1)
    return new_chain, waiting_status_for_stage(new_stage), stage_idx + 1
