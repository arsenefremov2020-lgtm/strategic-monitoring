# config/users.py

"""
Користувачі системи моніторингу стратегічного плану.

Основне джерело користувачів:
- users_access.xlsx

Файл Excel має лежати в корені репозиторію поруч з app.py.

Якщо Excel не знайдено або він порожній, система використовує мінімальний fallback,
щоб застосунок не падав.
"""

from __future__ import annotations

from config.roles import (
    ROLE_SSP,
    ROLE_SSP_HEAD,
    ROLE_ADMIN,
    ROLE_SUPER_ADMIN,
    ROLE_GUEST,
    normalize_role,
    get_role_label,
)

from core.users_access_loader import load_users_from_excel


# ------------------------------------------------------------
# Гостьовий користувач
# ------------------------------------------------------------

GUEST_USER = {
    "email": None,
    "password": "",
    "full_name": "Користувач без реєстрації",
    "phone": "",
    "role": ROLE_GUEST,
    "role_label": "Користувач без реєстрації",

    "ssp_index": None,
    "ssp_label": None,
    "ssp_name": None,
    "ssp": None,

    "allowed_ssp_indexes": [],
    "allowed_ssp_labels": [],

    "is_active": True,
    "is_owner": False,
    "comment": "",
}


# ------------------------------------------------------------
# Мінімальний fallback
# ------------------------------------------------------------

FALLBACK_USERS = {
    "arsen.efremov.2020@gmail.com": {
        "email": "arsen.efremov.2020@gmail.com",
        "password": "123456",
        "full_name": "Арсен Єфремов",
        "phone": "",
        "role": ROLE_SUPER_ADMIN,
        "role_label": "Власник",

        "ssp_index": None,
        "ssp_label": None,
        "ssp_name": None,
        "ssp": None,

        "allowed_ssp_indexes": ["*"],
        "allowed_ssp_labels": ["*"],

        "is_active": True,
        "is_owner": True,
        "comment": "Fallback user",
    }
}


# ------------------------------------------------------------
# Завантаження користувачів
# ------------------------------------------------------------

EXCEL_USERS = load_users_from_excel("users_access.xlsx")

if EXCEL_USERS:
    USERS = EXCEL_USERS
else:
    USERS = FALLBACK_USERS


# ------------------------------------------------------------
# Службові функції
# ------------------------------------------------------------

def normalize_email(email: str | None) -> str | None:
    """
    Нормалізує email.
    """

    if not email:
        return None

    email = str(email).strip().lower()

    if not email:
        return None

    return email


def normalize_ssp_index(value: str | int | float | None) -> str | None:
    """
    Нормалізує індекс ССП.

    Приклади:
    - "деп. 30" -> "30"
    - "упр. 26" -> "26"
    - "30" -> "30"
    - 30 -> "30"
    """

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    digits = "".join(ch for ch in text if ch.isdigit())

    if not digits:
        return None

    return digits


def normalize_ssp_indexes(values: list | tuple | set | None) -> list[str]:
    """
    Нормалізує список індексів ССП.
    """

    if not values:
        return []

    normalized = []

    for value in values:
        if value == "*":
            normalized.append("*")
            continue

        index = normalize_ssp_index(value)

        if index and index not in normalized:
            normalized.append(index)

    return normalized


def normalize_user_record(user: dict | None) -> dict:
    """
    Нормалізує запис користувача.
    """

    if not user:
        return GUEST_USER.copy()

    user_data = user.copy()

    role = normalize_role(user_data.get("role"))
    user_data["role"] = role
    user_data["role_label"] = user_data.get("role_label") or get_role_label(role)

    user_data["email"] = normalize_email(user_data.get("email"))

    user_data["ssp_index"] = normalize_ssp_index(user_data.get("ssp_index"))

    if role == ROLE_SUPER_ADMIN or user_data.get("is_owner", False):
        user_data["allowed_ssp_indexes"] = ["*"]
        user_data["allowed_ssp_labels"] = ["*"]
    else:
        user_data["allowed_ssp_indexes"] = normalize_ssp_indexes(
            user_data.get("allowed_ssp_indexes", [])
        )

    if "password" not in user_data:
        user_data["password"] = ""

    if "phone" not in user_data:
        user_data["phone"] = ""

    if "ssp_label" not in user_data:
        user_data["ssp_label"] = None

    if "ssp_name" not in user_data:
        user_data["ssp_name"] = user_data.get("ssp")

    if "ssp" not in user_data:
        user_data["ssp"] = user_data.get("ssp_name")

    if "comment" not in user_data:
        user_data["comment"] = ""

    return user_data


def get_user_by_email(email: str | None) -> dict:
    """
    Повертає користувача за email.
    Якщо email не знайдено — повертає guest.
    """

    email = normalize_email(email)

    if not email:
        return GUEST_USER.copy()

    user = USERS.get(email)

    if not user:
        return GUEST_USER.copy()

    if not user.get("is_active", False):
        return GUEST_USER.copy()

    return normalize_user_record(user)


def user_exists(email: str | None) -> bool:
    """
    Перевіряє, чи існує користувач у системі.
    """

    email = normalize_email(email)

    if not email:
        return False

    return email in USERS


def is_active_user(email: str | None) -> bool:
    """
    Перевіряє, чи користувач існує та активний.
    """

    email = normalize_email(email)

    if not email:
        return False

    user = USERS.get(email)

    if not user:
        return False

    return bool(user.get("is_active", False))


def get_user_role(email: str | None) -> str:
    """
    Повертає роль користувача.
    """

    user = get_user_by_email(email)
    return user.get("role", ROLE_GUEST)


def get_user_ssp(email: str | None) -> str | None:
    """
    Повертає старе поле ssp для сумісності.
    """

    user = get_user_by_email(email)
    return user.get("ssp")


def get_user_ssp_index(email: str | None) -> str | None:
    """
    Повертає індекс ССП користувача.
    """

    user = get_user_by_email(email)
    return user.get("ssp_index")


def get_user_allowed_ssp_indexes(email: str | None) -> list[str]:
    """
    Повертає перелік індексів ССП, доступних користувачу.
    """

    user = get_user_by_email(email)
    return user.get("allowed_ssp_indexes", [])


def get_all_users() -> dict:
    """
    Повертає всіх користувачів.
    """

    return {
        email: normalize_user_record(user)
        for email, user in USERS.items()
    }


def get_active_users() -> dict:
    """
    Повертає тільки активних користувачів.
    """

    return {
        email: normalize_user_record(user)
        for email, user in USERS.items()
        if user.get("is_active", False)
    }


def get_users_by_role(role: str) -> dict:
    """
    Повертає користувачів із конкретною роллю.
    """

    role = normalize_role(role)

    return {
        email: normalize_user_record(user)
        for email, user in USERS.items()
        if normalize_role(user.get("role")) == role and user.get("is_active", False)
    }


def get_users_by_ssp_index(ssp_index: str | int | None) -> dict:
    """
    Повертає користувачів, прив'язаних до конкретного індексу ССП.
    """

    ssp_index = normalize_ssp_index(ssp_index)

    if not ssp_index:
        return {}

    result = {}

    for email, user in USERS.items():
        normalized_user = normalize_user_record(user)

        if not normalized_user.get("is_active", False):
            continue

        if normalized_user.get("ssp_index") == ssp_index:
            result[email] = normalized_user

    return result


def get_users_by_ssp(ssp: str | None) -> dict:
    """
    Сумісність зі старою логікою.
    Повертає користувачів, прив'язаних до конкретної назви ССП.
    """

    if not ssp:
        return {}

    ssp = str(ssp).strip()

    return {
        email: normalize_user_record(user)
        for email, user in USERS.items()
        if user.get("ssp") == ssp and user.get("is_active", False)
    }
