"""Маршрутизація ручного закриття до відповідального супер-адміна DEMO 1.9."""

from __future__ import annotations

from typing import Any

# Нижче — службова маршрутизація за поточною організаційною логікою.
# Якщо частина email ще не заведена в users_access.xlsx, значення email лишається
# порожнім, але name/routing_note дозволяють відобразити правильного адресата.

PASTUSHYNA = {"name": "Пастушина", "email": ""}
DELIUSTO = {"name": "Делюсто", "email": ""}
KANIEVSKA = {"name": "Канєвська", "email": "kanevska150881@gmail.com"}
PERUN = {"name": "Перун", "email": "vperun80@gmail.com"}

GROUP_PASTUSHYNA_EMAILS = {
    "test_iryna_1@me.gov.ua",  # Провицька
    "test_iryna_2@me.gov.ua",  # Курдибан
    "test_iryna_3@me.gov.ua",  # Бойко
}

GROUP_KANIEVSKA_EMAILS = {
    "t.kovalchuk1979@gmail.com",      # Ковальчук
    "arsen.efremov.2021@gmail.com",   # Єфремов
    "chemodanovayuliya123@gmail.com", # Чемоданова
}


def _email(user: dict | None) -> str:
    return str((user or {}).get("email") or "").strip().lower()


def _name(user: dict | None) -> str:
    return str((user or {}).get("full_name") or (user or {}).get("name") or "").strip().lower()



def assigned_superadmins_for_admin(admin_user: dict | None) -> list[dict[str, str]]:
    """Повертає всіх супер-адмінів, за якими закріплений адміністратор.

    Перший елемент — основний адресат, другий — старший супер-адмін.
    Єфремов Арсен Олександрович належить до пари Канєвська → Перун.
    """
    email = _email(admin_user)
    name = _name(admin_user)

    if email in GROUP_PASTUSHYNA_EMAILS or any(
        part in name for part in ("провиць", "курдибан", "бойко")
    ):
        return [dict(PASTUSHYNA), dict(DELIUSTO)]

    if email in GROUP_KANIEVSKA_EMAILS or any(
        part in name for part in ("ковальчук", "єфрем", "чемоданов")
    ):
        return [dict(KANIEVSKA), dict(PERUN)]

    return [dict(KANIEVSKA), dict(PERUN)]


def is_superadmin_assigned_to_admin(
    superadmin_user: dict | None,
    admin_user: dict | None,
) -> bool:
    """Чи входить супер-адмін до переліку кураторів цього адміністратора."""
    current_email = _email(superadmin_user)
    current_name = _name(superadmin_user)
    for supervisor in assigned_superadmins_for_admin(admin_user):
        supervisor_email = str(supervisor.get("email") or "").strip().lower()
        supervisor_name = str(supervisor.get("name") or "").strip().lower()
        if supervisor_email and current_email and supervisor_email == current_email:
            return True
        if supervisor_name and current_name and supervisor_name in current_name:
            return True
    return False

def resolve_manual_closeout_route(admin_user: dict | None) -> dict[str, str]:
    """Повертає першого і старшого супер-адміна для заявки ручного закриття."""
    supervisors = assigned_superadmins_for_admin(admin_user)
    first, senior = supervisors[0], supervisors[1]

    return {
        "assigned_superadmin_name": first["name"],
        "assigned_superadmin_email": first["email"],
        "senior_superadmin_name": senior["name"],
        "senior_superadmin_email": senior["email"],
        "routing_note": f"Перший супер-адмін: {first['name']}; старший супер-адмін: {senior['name']}",
    }


def can_superadmin_decide_closeout(user: dict | None, request_row: dict | Any) -> bool:
    """Чи є поточний супер-адмін адресатом ручного закриття.

    Якщо email адресата ще не заведений, усі супер-адміни можуть переглядати,
    але рішення бажано приймати вручну за routing_note.
    """
    email = _email(user)
    if not email:
        return False
    getter = request_row.get if hasattr(request_row, "get") else lambda k, d=None: d
    assigned = str(getter("assigned_superadmin_email", "") or "").strip().lower()
    senior = str(getter("senior_superadmin_email", "") or "").strip().lower()
    if not assigned:
        return True
    return email in {assigned, senior}


def senior_superadmin_for(email: str) -> dict | None:
    """Старший супер-адмін для даного супер-адміна (ескалація Заг.5).

    Пастушина → Делюсто; Канєвська → Перун. Для старших (Делюсто, Перун)
    вищої ланки немає — повертає None.
    """
    e = str(email or "").strip().lower()
    if e and e == str(PASTUSHYNA.get("email") or "").strip().lower():
        return DELIUSTO
    if e and e == str(KANIEVSKA.get("email") or "").strip().lower():
        return PERUN
    return None
