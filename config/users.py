# config/users.py

"""
Список користувачів системи моніторингу стратегічного плану.

Цей файл відповідає за:
1. перелік користувачів;
2. їхні ролі;
3. контактні дані користувачів;
4. прив'язку користувачів до ССП;
5. перелік ССП, доступних конкретному користувачу;
6. службові функції для пошуку користувача за email.

Тут не має бути логіки Streamlit, Supabase, Excel або розрахунків.
"""


from config.roles import (
    ROLE_SSP,
    ROLE_SSP_HEAD,
    ROLE_ADMIN,
    ROLE_SUPER_ADMIN,
    ROLE_GUEST,
    normalize_role,
    get_role_label,
)


# ------------------------------------------------------------
# Важлива логіка
# ------------------------------------------------------------
#
# ssp_index:
#   Основний індекс ССП користувача.
#   Для ССП і керівника ССП це конкретний номер, наприклад "30".
#   Для адміна і супер-адміна — None.
#
# ssp_label:
#   Людський підпис ССП у форматі, який зручно показувати в інтерфейсі.
#   Наприклад: "деп. 30", "упр. 26".
#
# allowed_ssp_indexes:
#   Перелік індексів ССП, до яких користувач має доступ.
#   Для ССП: тільки власний індекс.
#   Для керівника ССП: тільки власний індекс.
#   Для адміна: перелік закріплених за ним ССП.
#   Для супер-адміна: ["*"] — доступ до всіх ССП.
#
# allowed_ssp_labels:
#   Людські назви для відображення у випадних списках.
#
# phone:
#   Контактний номер користувача.
#   Зараз може бути порожній, потім заповниш реальними номерами.
#
# ssp:
#   Старе поле для сумісності з уже наявним кодом.
#   Поки залишаємо, щоб нічого не зламати.
# ------------------------------------------------------------


USERS = {
    "vperun80@gmail.com": {
        "email": "vperun80@gmail.com",
        "full_name": "Вікторія Перун",
        "phone": "+380 66 322 5628",
        "role": ROLE_SUPER_ADMIN,
        "role_label": "Супер-адмін",

        "ssp_index": None,
        "ssp_label": None,
        "ssp_name": None,
        "ssp": None,

        "allowed_ssp_indexes": ["*"],
        "allowed_ssp_labels": ["*"],

        "is_active": True,
        "is_owner": False,
    },

    "arsen.efremov.2020@gmail.com": {
        "email": "arsen.efremov.2020@gmail.com",
        "full_name": "Арсен Єфремов",
        "phone": "+380 50 764 9372",
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
    },

    "chemodanovayuliya123@gmail.com": {
        "email": "chemodanovayuliya123@gmail.com",
        "full_name": "Юлія Чемоданова",
        "phone": "+380 66 917 2801",
        "role": ROLE_ADMIN,
        "role_label": "Адміністратор",

        "ssp_index": None,
        "ssp_label": None,
        "ssp_name": None,
        "ssp": None,

        # Тимчасово для тесту.
        # Потім тут пропишеш реальні закріплені ССП цього адміністратора.
        "allowed_ssp_indexes": ["30"],
        "allowed_ssp_labels": ["деп. 30"],

        "is_active": True,
        "is_owner": False,
    },

    "kanevska150881@gmail.com": {
        "email": "kanevska150881@gmail.com",
        "full_name": "Каневська",
        "phone": "+380 97 701 7291",
        "role": ROLE_SUPER_ADMIN,
        "role_label": "Супер-адмін",

        "ssp_index": None,
        "ssp_label": None,
        "ssp_name": None,
        "ssp": None,

        "allowed_ssp_indexes": ["*"],
        "allowed_ssp_labels": ["*"],

        "is_active": True,
        "is_owner": False,
    },

    "t.kovalchuk1979@gmail.com": {
        "email": "t.kovalchuk1979@gmail.com",
        "full_name": "Тетяна Ковальчук",
        "phone": "+380 99 908 7025",
        "role": ROLE_ADMIN,
        "role_label": "Адміністратор",

        "ssp_index": None,
        "ssp_label": None,
        "ssp_name": None,
        "ssp": None,

        # Тимчасово для тесту.
        # Потім тут пропишеш реальні закріплені ССП цього адміністратора.
        "allowed_ssp_indexes": ["26"],
        "allowed_ssp_labels": ["упр. 26"],

        "is_active": True,
        "is_owner": False,
    },

    "arsen.yefremov.25@kse.org.ua": {
        "email": "arsen.yefremov.25@kse.org.ua",
        "full_name": "Тестовий користувач ССП",
        "phone": "",
        "role": ROLE_SSP,
        "role_label": "Кабінет ССП",

        # Тестовий ССП.
        # Потім заміниш на реальний індекс і назву.
        "ssp_index": "30",
        "ssp_label": "деп. 30",
        "ssp_name": "Тестовий ССП",
        "ssp": "Тестовий ССП",

        "allowed_ssp_indexes": ["30"],
        "allowed_ssp_labels": ["деп. 30"],

        "is_active": True,
        "is_owner": False,
    },

    "inna.mogilat@gmail.com": {
        "email": "inna.mogilat@gmail.com",
        "full_name": "Інна Могилат",
        "phone": "+380 50 409 2929",
        "role": ROLE_SUPER_ADMIN,
        "role_label": "Супер-адмін",

        "ssp_index": None,
        "ssp_label": None,
        "ssp_name": None,
        "ssp": None,

        "allowed_ssp_indexes": ["*"],
        "allowed_ssp_labels": ["*"],

        "is_active": True,
        "is_owner": False,
    },

    "test.ssp.head@example.com": {
        "email": "test.ssp.head@example.com",
        "full_name": "Тестовий керівник ССП",
        "phone": "",
        "role": ROLE_SSP_HEAD,
        "role_label": "Керівник ССП",

        # Тестовий керівник того самого ССП, що й тестовий користувач ССП.
        "ssp_index": "30",
        "ssp_label": "деп. 30",
        "ssp_name": "Тестовий ССП",
        "ssp": "Тестовий ССП",

        "allowed_ssp_indexes": ["30"],
        "allowed_ssp_labels": ["деп. 30"],

        "is_active": True,
        "is_owner": False,
    },
}


# ------------------------------------------------------------
# Гостьовий користувач
# ------------------------------------------------------------

GUEST_USER = {
    "email": None,
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
}


# ------------------------------------------------------------
# Службові функції
# ------------------------------------------------------------

def normalize_email(email: str | None) -> str | None:
    """
    Нормалізує email:
    - прибирає пробіли;
    - переводить у нижній регістр;
    - якщо email порожній — повертає None.
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
    Нормалізує запис користувача:
    - роль;
    - role_label;
    - ssp_index;
    - allowed_ssp_indexes.
    """

    if not user:
        return GUEST_USER.copy()

    user_data = user.copy()

    role = normalize_role(user_data.get("role"))
    user_data["role"] = role
    user_data["role_label"] = user_data.get("role_label") or get_role_label(role)

    user_data["email"] = normalize_email(user_data.get("email"))

    user_data["ssp_index"] = normalize_ssp_index(user_data.get("ssp_index"))

    allowed_indexes = user_data.get("allowed_ssp_indexes", [])

    # Супер-адмін завжди має доступ до всіх ССП.
    if role == ROLE_SUPER_ADMIN or user_data.get("is_owner", False):
        user_data["allowed_ssp_indexes"] = ["*"]
        user_data["allowed_ssp_labels"] = ["*"]
    else:
        user_data["allowed_ssp_indexes"] = normalize_ssp_indexes(allowed_indexes)

    if "phone" not in user_data:
        user_data["phone"] = ""

    if "ssp_label" not in user_data:
        user_data["ssp_label"] = None

    if "ssp_name" not in user_data:
        user_data["ssp_name"] = user_data.get("ssp")

    if "ssp" not in user_data:
        user_data["ssp"] = user_data.get("ssp_name")

    return user_data


def get_user_by_email(email: str | None) -> dict:
    """
    Повертає користувача за email.
    Якщо email не знайдено — повертає гостьового користувача.
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
    Якщо користувача немає — повертає guest.
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
    Повертає копію всіх користувачів.
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
