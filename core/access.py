# core/access.py

"""
Центральна логіка доступу до даних.

Цей файл відповідає за:
1. визначення доступних ССП для поточного користувача;
2. фільтрацію заходів за роллю користувача;
3. фільтрацію заявок за роллю користувача;
4. блокування/розблокування полів у формах;
5. службову нормалізацію індексів ССП.

Основний принцип:
- сторінки не мають самі вигадувати логіку доступу;
- сторінки мають викликати функції з цього файлу.
"""


from __future__ import annotations

import re
from typing import Iterable

import pandas as pd

from config.roles import (
    ROLE_SSP,
    ROLE_SSP_HEAD,
    ROLE_ADMIN,
    ROLE_SUPER_ADMIN,
    ROLE_GUEST,
    normalize_role,
)


# ------------------------------------------------------------
# Колонки, за якими відбираємо заходи для ССП
# ------------------------------------------------------------

DEFAULT_ACTION_EXECUTOR_COLUMNS = [
    "Головний виконавець",
    "Співвиконавець 1",
]


# ------------------------------------------------------------
# Можливі колонки із ССП у заявках
# ------------------------------------------------------------

DEFAULT_REQUEST_SSP_COLUMNS = [
    "ssp_index",
    "ССП",
    "Індекс ССП",
    "Індекс самостійного структурного підрозділу",
    "Самостійний структурний підрозділ",
    "structural_unit_index",
]


# ------------------------------------------------------------
# Нормалізація індексів
# ------------------------------------------------------------

def normalize_ssp_index(value: str | int | float | None) -> str | None:
    """
    Витягує числовий індекс ССП.

    Приклади:
    - "деп. 30" -> "30"
    - "упр. 26" -> "26"
    - "30" -> "30"
    - 30 -> "30"
    - "департамент 3.1" -> "31", якщо в тексті саме так записано

    У твоїй логіці відбір робимо саме по числу.
    """

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    digits = re.findall(r"\d+", text)

    if not digits:
        return None

    return "".join(digits)


def normalize_ssp_indexes(values: Iterable | None) -> list[str]:
    """
    Нормалізує список індексів ССП.
    """

    if not values:
        return []

    result = []

    for value in values:
        if value == "*":
            return ["*"]

        normalized = normalize_ssp_index(value)

        if normalized and normalized not in result:
            result.append(normalized)

    return result


def cell_has_allowed_ssp_index(cell_value, allowed_ssp_indexes: list[str]) -> bool:
    """
    Перевіряє, чи значення клітинки містить індекс ССП,
    який є у списку дозволених.

    Працює для значень:
    - "деп. 30"
    - "упр. 26"
    - "30"
    - "деп. 30; упр. 26"
    """

    if not allowed_ssp_indexes:
        return False

    if "*" in allowed_ssp_indexes:
        return True

    if cell_value is None:
        return False

    text = str(cell_value).strip()

    if not text:
        return False

    found_numbers = re.findall(r"\d+", text)

    if not found_numbers:
        return False

    found_indexes = [normalize_ssp_index(number) for number in found_numbers]
    found_indexes = [index for index in found_indexes if index]

    return any(index in allowed_ssp_indexes for index in found_indexes)


# ------------------------------------------------------------
# Дані користувача
# ------------------------------------------------------------

def get_user_role(user: dict | None) -> str:
    """
    Повертає нормалізовану роль користувача.
    """

    if not user:
        return ROLE_GUEST

    return normalize_role(user.get("role"))


def get_user_ssp_index(user: dict | None) -> str | None:
    """
    Повертає основний індекс ССП користувача.
    """

    if not user:
        return None

    return normalize_ssp_index(user.get("ssp_index"))


def get_user_allowed_ssp_indexes(user: dict | None) -> list[str]:
    """
    Повертає список індексів ССП, доступних користувачу.
    """

    if not user:
        return []

    role = get_user_role(user)

    if role == ROLE_SUPER_ADMIN or user.get("is_owner", False):
        return ["*"]

    allowed = user.get("allowed_ssp_indexes", [])

    return normalize_ssp_indexes(allowed)


def get_user_allowed_ssp_labels(user: dict | None) -> list[str]:
    """
    Повертає підписи ССП для відображення у випадних списках.

    Для супер-адміна повертає ["*"].
    Для інших — allowed_ssp_labels із профілю користувача.
    """

    if not user:
        return []

    role = get_user_role(user)

    if role == ROLE_SUPER_ADMIN or user.get("is_owner", False):
        return ["*"]

    labels = user.get("allowed_ssp_labels", [])

    if not labels:
        indexes = get_user_allowed_ssp_indexes(user)
        return indexes

    return list(labels)


def user_has_all_ssp_access(user: dict | None) -> bool:
    """
    Перевіряє, чи користувач має доступ до всіх ССП.
    """

    allowed = get_user_allowed_ssp_indexes(user)
    return "*" in allowed


def can_user_access_ssp(user: dict | None, ssp_value) -> bool:
    """
    Перевіряє, чи користувач має доступ до конкретного ССП.

    ssp_value може бути:
    - "30"
    - "деп. 30"
    - "упр. 26"
    """

    if not user:
        return False

    allowed = get_user_allowed_ssp_indexes(user)

    if "*" in allowed:
        return True

    return cell_has_allowed_ssp_index(ssp_value, allowed)


# ------------------------------------------------------------
# Режими редагування
# ------------------------------------------------------------

def is_guest_user(user: dict | None) -> bool:
    """
    Перевіряє, чи користувач є гостем.
    """

    return get_user_role(user) == ROLE_GUEST


def is_ssp_user(user: dict | None) -> bool:
    """
    Перевіряє, чи користувач є звичайним ССП.
    """

    return get_user_role(user) == ROLE_SSP


def is_ssp_head_user(user: dict | None) -> bool:
    """
    Перевіряє, чи користувач є керівником ССП.
    """

    return get_user_role(user) == ROLE_SSP_HEAD


def is_admin_user(user: dict | None) -> bool:
    """
    Перевіряє, чи користувач є адміністратором.
    """

    return get_user_role(user) == ROLE_ADMIN


def is_super_admin_user(user: dict | None) -> bool:
    """
    Перевіряє, чи користувач є супер-адміном або власником.
    """

    if not user:
        return False

    return get_user_role(user) == ROLE_SUPER_ADMIN or user.get("is_owner", False)


def is_readonly_user(user: dict | None) -> bool:
    """
    Гість — readonly.
    Інші ролі можуть мати робочі дії залежно від сторінки.
    """

    return is_guest_user(user)


def should_lock_ssp_fields(user: dict | None) -> bool:
    """
    Визначає, чи треба блокувати вибір ССП у формах.

    Для ССП, керівника ССП і адміна — так.
    Для супер-адміна — ні.
    Для гостя — так.
    """

    role = get_user_role(user)

    if role == ROLE_SUPER_ADMIN:
        return False

    return True


def should_prefill_contact_fields(user: dict | None) -> bool:
    """
    Визначає, чи треба автоматично підтягувати ПІБ/email/телефон.
    """

    role = get_user_role(user)
    return role in [ROLE_SSP, ROLE_SSP_HEAD, ROLE_ADMIN, ROLE_SUPER_ADMIN]


# ------------------------------------------------------------
# Фільтрація заходів
# ------------------------------------------------------------

def find_existing_columns(df: pd.DataFrame, candidate_columns: list[str]) -> list[str]:
    """
    Повертає тільки ті колонки, які реально є в датафреймі.
    """

    if df is None or df.empty:
        return []

    return [column for column in candidate_columns if column in df.columns]


def filter_actions_for_user(
    df: pd.DataFrame,
    user: dict | None,
    executor_columns: list[str] | None = None,
) -> pd.DataFrame:
    """
    Фільтрує заходи відповідно до доступу користувача.

    Логіка:
    - guest: бачить усі заходи для публічного перегляду;
    - super_admin / owner: бачить усі заходи;
    - admin: бачить заходи тільки за закріпленими ССП;
    - ssp: бачить заходи, де його ССП є в "Головний виконавець" або "Співвиконавець 1";
    - ssp_head: аналогічно, тільки свій ССП.

    Відбір іде по числу:
    - "деп. 30" -> "30";
    - "упр. 26" -> "26".
    """

    if df is None:
        return df

    if df.empty:
        return df.copy()

    role = get_user_role(user)

    if role == ROLE_GUEST:
        return df.copy()

    if is_super_admin_user(user):
        return df.copy()

    allowed_ssp_indexes = get_user_allowed_ssp_indexes(user)

    if not allowed_ssp_indexes:
        return df.iloc[0:0].copy()

    if "*" in allowed_ssp_indexes:
        return df.copy()

    if executor_columns is None:
        executor_columns = DEFAULT_ACTION_EXECUTOR_COLUMNS

    existing_columns = find_existing_columns(df, executor_columns)

    if not existing_columns:
        return df.iloc[0:0].copy()

    mask = pd.Series(False, index=df.index)

    for column in existing_columns:
        column_mask = df[column].apply(
            lambda value: cell_has_allowed_ssp_index(value, allowed_ssp_indexes)
        )
        mask = mask | column_mask

    return df[mask].copy()


# ------------------------------------------------------------
# Фільтрація заявок
# ------------------------------------------------------------

def filter_requests_for_user(
    df: pd.DataFrame,
    user: dict | None,
    ssp_columns: list[str] | None = None,
) -> pd.DataFrame:
    """
    Фільтрує заявки відповідно до доступу користувача.

    Логіка:
    - guest: не бачить заявки;
    - super_admin / owner: бачить усі заявки;
    - admin: бачить заявки тільки за закріпленими ССП;
    - ssp: бачить заявки тільки свого ССП;
    - ssp_head: бачить заявки тільки свого ССП.
    """

    if df is None:
        return df

    if df.empty:
        return df.copy()

    role = get_user_role(user)

    if role == ROLE_GUEST:
        return df.iloc[0:0].copy()

    if is_super_admin_user(user):
        return df.copy()

    allowed_ssp_indexes = get_user_allowed_ssp_indexes(user)

    if not allowed_ssp_indexes:
        return df.iloc[0:0].copy()

    if "*" in allowed_ssp_indexes:
        return df.copy()

    if ssp_columns is None:
        ssp_columns = DEFAULT_REQUEST_SSP_COLUMNS

    existing_columns = find_existing_columns(df, ssp_columns)

    if not existing_columns:
        return df.iloc[0:0].copy()

    mask = pd.Series(False, index=df.index)

    for column in existing_columns:
        column_mask = df[column].apply(
            lambda value: cell_has_allowed_ssp_index(value, allowed_ssp_indexes)
        )
        mask = mask | column_mask

    return df[mask].copy()


# ------------------------------------------------------------
# Дані для автозаповнення форм
# ------------------------------------------------------------

def get_prefilled_user_contacts(user: dict | None) -> dict:
    """
    Повертає дані користувача для автозаповнення форм.

    Використовувати на сторінках:
    - Моніторинг виконання;
    - Мої заявки;
    - Мій кабінет;
    - Адміністрування.
    """

    if not user:
        return {
            "full_name": "",
            "email": "",
            "phone": "",
            "ssp_index": None,
            "ssp_label": None,
            "ssp_name": None,
        }

    return {
        "full_name": user.get("full_name", ""),
        "email": user.get("email", ""),
        "phone": user.get("phone", ""),
        "ssp_index": get_user_ssp_index(user),
        "ssp_label": user.get("ssp_label"),
        "ssp_name": user.get("ssp_name") or user.get("ssp"),
    }


def get_available_ssp_options_for_user(
    user: dict | None,
    all_options: list[str] | None = None,
) -> list[str]:
    """
    Повертає список ССП для випадного списку.

    Для супер-адміна:
    - якщо переданий all_options — повертає всі;
    - якщо ні — повертає ["*"].

    Для адміна:
    - повертає тільки allowed_ssp_labels.

    Для ССП і керівника ССП:
    - повертає тільки власний ССП.

    Для гостя:
    - повертає порожній список.
    """

    if not user:
        return []

    role = get_user_role(user)

    if role == ROLE_GUEST:
        return []

    if is_super_admin_user(user):
        if all_options is not None:
            return list(all_options)
        return ["*"]

    labels = get_user_allowed_ssp_labels(user)

    if labels == ["*"]:
        if all_options is not None:
            return list(all_options)
        return ["*"]

    return labels


def get_single_locked_ssp_value(user: dict | None) -> str | None:
    """
    Повертає єдине значення ССП для заблокованого поля.

    Для ССП і керівника ССП:
    - повертає ssp_label, наприклад "деп. 30".

    Для адміна:
    - якщо закріплений один ССП — повертає його;
    - якщо кілька — повертає None, бо адмін має вибрати зі своїх.

    Для супер-адміна:
    - None, бо він може бачити всі.
    """

    if not user:
        return None

    if is_super_admin_user(user):
        return None

    labels = get_user_allowed_ssp_labels(user)

    if len(labels) == 1:
        return labels[0]

    return None
