# core/users_access_loader.py

"""
Завантаження користувачів і доступів із Excel-файлу users_access.xlsx.

Очікувана структура файлу:
1. Адміністратори
2. Керівники ССП
3. Відповідальні за ССП
"""

from __future__ import annotations

from pathlib import Path
import re

import pandas as pd

from config.roles import (
    ROLE_ADMIN,
    ROLE_SUPER_ADMIN,
    ROLE_SSP,
    ROLE_SSP_HEAD,
    ROLE_UNIT_HEAD,
    ROLE_SSP_DEPUTY,
    ROLE_GUEST,
)


USERS_ACCESS_FILE = "users_access.xlsx"

SHEET_ADMINS = "Адміністратори"
SHEET_SSP_HEADS = "Керівники ССП"
SHEET_SSP_USERS = "Відповідальні за ССП"
SHEET_UNIT_HEADS = "Керівники управлінь"
SHEET_SSP_DEPUTIES = "Заступники керівників ССП"


def clean_value(value) -> str:
    """
    Очищує значення з Excel.
    """

    if value is None or pd.isna(value):
        return ""

    text = str(value).strip()

    if text.lower() in ["nan", "none", "null"]:
        return ""

    return text


def clean_phone(value) -> str:
    """
    Очищує номер телефону.

    Excel іноді зберігає номер як `+380...
    Цей символ прибираємо.
    """

    text = clean_value(value)

    if text.startswith("`"):
        text = text[1:].strip()

    return text


def clean_email(value) -> str:
    """
    Нормалізує email.
    """

    return clean_value(value).lower()


def clean_password(value) -> str:
    """
    Пароль завжди приводимо до тексту.

    Якщо в Excel пароль записаний як число 123456,
    система все одно сприйме його як "123456".
    """

    text = clean_value(value)

    if text.endswith(".0"):
        text = text[:-2]

    return text


def normalize_ssp_index(value) -> str | None:
    """
    Витягує числовий індекс ССП.

    Приклади:
    - "деп. 30" -> "30"
    - "упр. 26" -> "26"
    - 30 -> "30"
    """

    text = clean_value(value)

    if not text:
        return None

    numbers = re.findall(r"\d+", text)

    if not numbers:
        return None

    return "".join(numbers)


def split_indexes(value) -> list[str]:
    """
    Розбиває перелік індексів ССП.

    Приклад:
    "26, 30, 42" -> ["26", "30", "42"]
    """

    text = clean_value(value)

    if not text:
        return []

    parts = re.split(r"[,;]", text)

    result = []

    for part in parts:
        index = normalize_ssp_index(part)

        if index and index not in result:
            result.append(index)

    return result


def split_labels(value) -> list[str]:
    """
    Розбиває перелік підписів ССП.

    Приклад:
    "упр. 26, деп. 30" -> ["упр. 26", "деп. 30"]
    """

    text = clean_value(value)

    if not text:
        return []

    result = []

    for part in re.split(r"[,;]", text):
        label = clean_value(part)

        if label and label not in result:
            result.append(label)

    return result


def parse_is_active(value) -> bool:
    """
    Перетворює is_active з Excel у True/False.

    Excel часто зберігає 1 як число (1 або 1.0) — це теж True.
    """

    if isinstance(value, bool):
        return value

    # Числові значення (1, 1.0, 0) — типовий випадок для Excel
    try:
        if not isinstance(value, str):
            return float(value) != 0
    except (TypeError, ValueError):
        pass

    text = clean_value(value).lower()

    if text in ["true", "1", "1.0", "yes", "так", "активний", "active"]:
        return True

    return False


def safe_read_sheet(file_path: str | Path, sheet_name: str) -> pd.DataFrame:
    """
    Безпечно читає аркуш Excel.
    Якщо аркуша немає — повертає порожній DataFrame.
    """

    try:
        return pd.read_excel(file_path, sheet_name=sheet_name)
    except Exception:
        return pd.DataFrame()


def build_admin_or_super_admin(row: dict) -> dict | None:
    """
    Формує користувача з аркуша 'Адміністратори'.

    У цьому аркуші можуть бути як admin, так і super_admin.
    """

    email = clean_email(row.get("email"))

    if not email:
        return None

    role = clean_value(row.get("role")) or ROLE_ADMIN

    if role not in [ROLE_ADMIN, ROLE_SUPER_ADMIN]:
        role = ROLE_ADMIN

    role_label = clean_value(row.get("role_label"))

    if not role_label:
        role_label = "Супер-адмін" if role == ROLE_SUPER_ADMIN else "Адміністратор"

    is_owner = email == "arsen.efremov.2020@gmail.com"

    # Конкретні ССП, вписані в таблиці, — вони роблять адміна КООРДИНАТОРОМ
    # саме цих підрозділів (незалежно від широкого доступу '*').
    assigned_indexes = split_indexes(row.get("assigned_ssp_indexes"))
    assigned_labels = split_labels(row.get("assigned_ssp_labels"))

    if role == ROLE_SUPER_ADMIN or is_owner:
        # Широкий доступ до всіх сторінок/ССП…
        allowed_indexes = ["*"]
        allowed_labels = ["*"]
        # …але координатором є лише для явно закріплених у таблиці ССП.
        coordinator_indexes = [i for i in assigned_indexes if i != "*"]
    else:
        allowed_indexes = assigned_indexes
        allowed_labels = assigned_labels
        coordinator_indexes = [i for i in assigned_indexes if i != "*"]

    return {
        "email": email,
        "password": clean_password(row.get("password")),
        "full_name": clean_value(row.get("full_name")),
        "phone": clean_phone(row.get("phone")),
        "role": role,
        "role_label": "Власник" if is_owner else role_label,

        "ssp_index": None,
        "ssp_label": None,
        "ssp_name": None,
        "ssp": None,

        "allowed_ssp_indexes": allowed_indexes,
        "allowed_ssp_labels": allowed_labels,
        # Окреме поле: за якими ССП адмін є координатором (ланкою погодження).
        "coordinator_ssp_indexes": coordinator_indexes,

        "is_active": parse_is_active(row.get("is_active")),
        "is_owner": is_owner,
        "comment": clean_value(row.get("comment")),
    }


def build_ssp_user(row: dict, role: str, default_role_label: str) -> dict | None:
    """
    Формує користувача ССП або керівника ССП.
    """

    email = clean_email(row.get("email"))

    if not email:
        return None

    ssp_index = normalize_ssp_index(row.get("ssp_index"))
    ssp_label = clean_value(row.get("ssp_label"))
    ssp_name = clean_value(row.get("ssp_name"))

    allowed_indexes = [ssp_index] if ssp_index else []
    allowed_labels = [ssp_label] if ssp_label else allowed_indexes

    role_from_excel = clean_value(row.get("role")) or role

    if role_from_excel not in [ROLE_SSP, ROLE_SSP_HEAD, ROLE_UNIT_HEAD, ROLE_SSP_DEPUTY]:
        role_from_excel = role

    role_label = clean_value(row.get("role_label")) or default_role_label

    return {
        "email": email,
        "password": clean_password(row.get("password")),
        "full_name": clean_value(row.get("full_name")),
        "phone": clean_phone(row.get("phone")),
        "role": role_from_excel,
        "role_label": role_label,

        "ssp_index": ssp_index,
        "ssp_label": ssp_label,
        "ssp_name": ssp_name,
        "ssp": ssp_name,

        "unit_name": clean_value(row.get("unit_name")) or clean_value(row.get("Управління")),

        "allowed_ssp_indexes": allowed_indexes,
        "allowed_ssp_labels": allowed_labels,

        "is_active": parse_is_active(row.get("is_active")),
        "is_owner": False,
        "comment": clean_value(row.get("comment")),
    }


def load_users_from_excel(file_path: str | Path = USERS_ACCESS_FILE) -> dict:
    """
    Завантажує всіх користувачів із Excel.

    Повертає словник:
    {
        "email@example.com": {user_data}
    }
    """

    file_path = Path(file_path)

    if not file_path.exists():
        return {}

    users = {}

    admins_df = safe_read_sheet(file_path, SHEET_ADMINS)
    heads_df = safe_read_sheet(file_path, SHEET_SSP_HEADS)
    ssp_users_df = safe_read_sheet(file_path, SHEET_SSP_USERS)

    for _, row in admins_df.iterrows():
        user = build_admin_or_super_admin(row.to_dict())

        if user and user.get("is_active"):
            users[user["email"]] = user

    for _, row in heads_df.iterrows():
        user = build_ssp_user(
            row.to_dict(),
            role=ROLE_SSP_HEAD,
            default_role_label="Керівник ССП",
        )

        if user and user.get("is_active"):
            users[user["email"]] = user

    for _, row in ssp_users_df.iterrows():
        user = build_ssp_user(
            row.to_dict(),
            role=ROLE_SSP,
            default_role_label="Кабінет ССП",
        )

        if user and user.get("is_active"):
            users[user["email"]] = user

    # Нові ролі схем погодження
    unit_heads_df = safe_read_sheet(file_path, SHEET_UNIT_HEADS)
    deputies_df = safe_read_sheet(file_path, SHEET_SSP_DEPUTIES)

    for _, row in unit_heads_df.iterrows():
        user = build_ssp_user(
            row.to_dict(),
            role=ROLE_UNIT_HEAD,
            default_role_label="Керівник управління",
        )
        if user and user.get("is_active"):
            users[user["email"]] = user

    for _, row in deputies_df.iterrows():
        user = build_ssp_user(
            row.to_dict(),
            role=ROLE_SSP_DEPUTY,
            default_role_label="Заступник керівника ССП",
        )
        if user and user.get("is_active"):
            users[user["email"]] = user

    return users
